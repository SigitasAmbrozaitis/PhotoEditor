from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from photoedit.core.errors import ConflictError, InvalidRequestError, NotFoundError
from photoedit.core.styles import StyleLibrary, slugify
from photoedit.models import StyleSample
from photoedit.models.style import StyleCreate, StyleUpdate
from photoedit.safety import PathGuard, WriteNotAllowedError

T0 = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        self.now += timedelta(minutes=1)
        return self.now


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "styles"


@pytest.fixture
def lib(root: Path) -> StyleLibrary:
    return StyleLibrary(root, PathGuard(writable_roots=[root]), clock=Clock())


def _create(lib: StyleLibrary, name: str = "Warm Matte", **fields: object) -> str:
    request = StyleCreate.model_validate(
        {"name": name, "values": {"tone.contrast": -10}, "rules": [{"type": "exposure"}], **fields}
    )
    return lib.create(request).id


def _update(lib: StyleLibrary, style_id: str, expected: int, note: str = "", **fields: object) -> int:
    update = StyleUpdate.model_validate({"expected_version": expected, "change_note": note, **fields})
    return lib.update(style_id, update).version


# ----------------------------------------------------------------- create / read


def test_create_writes_style_readme_and_history(lib: StyleLibrary, root: Path) -> None:
    sid = _create(lib, best_for=["cats"], description="Soft and warm.")
    assert sid == "warm-matte"
    style = lib.get(sid)
    assert (style.version, style.change_note, style.values) == (1, "created", {"tone.contrast": -10.0})
    files = {p.relative_to(root / sid).as_posix() for p in (root / sid).rglob("*") if p.is_file()}
    assert files == {"style.json", "README.md", "history/v1.json"}
    stored = json.loads((root / sid / "style.json").read_text(encoding="utf-8"))
    assert stored["schema_version"] == 1 and "look_hash" not in stored
    readme = (root / sid / "README.md").read_text(encoding="utf-8")
    for text in (
        "# Warm Matte",
        "Soft and warm.",
        "## Best for",
        "- cats",
        "**exposure**",
        "`tone.contrast` | -10",
    ):
        assert text in readme


def test_slugs_and_collisions(lib: StyleLibrary) -> None:
    assert slugify("Warm Matte (v2)") == "warm-matte-v2"
    assert slugify("Test · Classic B&W") == "test-classic-bw"
    assert slugify("Ambro's look") == "ambros-look"
    assert slugify("Šiltas rūkas") == "siltas-rukas"
    assert slugify("!!!") == "style"
    assert len(slugify("x" * 100)) == 40
    assert [_create(lib, "Test"), _create(lib, "Test"), _create(lib, "test!")] == ["test", "test-2", "test-3"]


def test_list_sorted_by_name_with_broken_files(lib: StyleLibrary, root: Path) -> None:
    _create(lib, "Zebra")
    _create(lib, "apple")
    (root / "broken").mkdir()
    (root / "broken" / "style.json").write_text("{not json", encoding="utf-8")
    (root / "notes").mkdir()  # no style.json: not a style
    (root / "Bad Name").mkdir()
    (root / "Bad Name" / "style.json").write_text("{}", encoding="utf-8")
    listing = lib.listings()
    assert [e.id for e in listing] == ["apple", "broken", "zebra"]
    broken = listing[1]
    assert broken.style is None and broken.error is not None and "not valid JSON" in broken.error


def test_get_errors(lib: StyleLibrary, root: Path) -> None:
    with pytest.raises(NotFoundError):
        lib.get("nope")
    with pytest.raises(NotFoundError):
        lib.get("../outside")
    sid = _create(lib)
    data = json.loads((root / sid / "style.json").read_text(encoding="utf-8"))
    (root / sid / "style.json").write_text(json.dumps({**data, "id": "other"}), encoding="utf-8")
    with pytest.raises(InvalidRequestError, match="folder name wins"):
        lib.get(sid)
    (root / sid / "style.json").write_text(
        json.dumps({**data, "values": {"tone.contrast": 500}}), encoding="utf-8"
    )
    with pytest.raises(InvalidRequestError, match=r"tone\.contrast"):
        lib.get(sid)


def test_newer_schema_is_refused(lib: StyleLibrary, root: Path) -> None:
    sid = _create(lib)
    data = json.loads((root / sid / "style.json").read_text(encoding="utf-8"))
    (root / sid / "style.json").write_text(json.dumps({**data, "schema_version": 2}), encoding="utf-8")
    with pytest.raises(InvalidRequestError, match="newer version of the tool"):
        lib.get(sid)


def test_migration_hook_runs_for_older_files(
    lib: StyleLibrary, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from photoedit.core import styles

    sid = _create(lib)
    data = json.loads((root / sid / "style.json").read_text(encoding="utf-8"))
    data["title"] = data.pop("name")  # pretend format 1 called it "title" and the current format is 2
    (root / sid / "style.json").write_text(json.dumps(data), encoding="utf-8")

    def v1_to_v2(old: dict[str, object]) -> dict[str, object]:
        new = dict(old)
        new["name"] = new.pop("title")
        return new

    monkeypatch.setattr(styles, "STYLE_SCHEMA_VERSION", 2)
    monkeypatch.setitem(styles.MIGRATIONS, 1, v1_to_v2)
    monkeypatch.setattr("photoedit.models.style.STYLE_SCHEMA_VERSION", 2)
    assert lib.get(sid).name == "Warm Matte"


def test_invalid_and_later_phase_values_are_rejected(lib: StyleLibrary) -> None:
    with pytest.raises(InvalidRequestError, match=r"unknown parameter 'tone\.nope'"):
        _create(lib, values={"tone.nope": 1})
    with pytest.raises(InvalidRequestError, match=r"effects.grain.amount \(Phase 9\)"):
        _create(lib, values={"effects.grain.amount": 20})
    with pytest.raises(InvalidRequestError, match="per photo"):
        _create(lib, values={"geometry.angle": 2})
    assert lib.listings() == []  # nothing half-written


# ----------------------------------------------------------------- update / conflicts


def test_update_bumps_version_and_keeps_unset_fields(lib: StyleLibrary) -> None:
    sid = _create(lib, best_for=["cats"])
    assert _update(lib, sid, 1, "less contrast", values={"tone.contrast": -20}) == 2
    style = lib.get(sid)
    assert style.values == {"tone.contrast": -20.0} and style.best_for == ["cats"]
    assert style.change_note == "less contrast" and style.updated_at > style.created_at
    assert style.rules[0].type == "exposure"


def test_update_conflict(lib: StyleLibrary) -> None:
    sid = _create(lib)
    _update(lib, sid, 1, name="New name")
    with pytest.raises(ConflictError, match="at version 2"):
        _update(lib, sid, 1, name="Stale edit")
    assert lib.get(sid).name == "New name"


def test_update_rejects_invalid_and_leaves_file(lib: StyleLibrary) -> None:
    sid = _create(lib)
    with pytest.raises(InvalidRequestError, match="repeated: exposure"):
        _update(lib, sid, 1, rules=[{"type": "exposure"}, {"type": "exposure"}])
    assert lib.get(sid).version == 1


def test_samples_are_not_a_new_version(lib: StyleLibrary) -> None:
    sid = _create(lib)
    look = lib.get(sid).look_hash()
    lib.set_samples(sid, [StyleSample(photo_id="p1", name="01", look_hash=look)])
    style = lib.get(sid)
    assert style.version == 1 and style.samples[0].photo_id == "p1"
    assert lib.sample_path(sid, "01", "after").name == "01-after.jpg"
    assert [v.version for v in lib.history(sid)] == [1]


# ----------------------------------------------------------------- duplicate / delete


def test_duplicate_copies_look_not_samples(lib: StyleLibrary) -> None:
    sid = _create(lib, test_photo_ids=["p1"])
    lib.set_samples(sid, [StyleSample(photo_id="p1", name="01", look_hash="x")])
    copy = lib.duplicate(sid)
    assert (copy.id, copy.name, copy.version) == ("warm-matte-copy", "Warm Matte (copy)", 1)
    assert copy.look_hash() == lib.get(sid).look_hash()
    assert copy.test_photo_ids == ["p1"] and copy.samples == []
    assert "duplicated from 'warm-matte' version 1" in copy.change_note


def test_delete(lib: StyleLibrary, root: Path) -> None:
    sid = _create(lib)
    lib.delete(sid)
    assert not (root / sid).exists()
    with pytest.raises(NotFoundError):
        lib.delete(sid)


# ----------------------------------------------------------------- history / diff / revert


def test_history_diff_and_revert(lib: StyleLibrary) -> None:
    sid = _create(lib, description="first")
    _update(lib, sid, 1, "stronger", values={"tone.contrast": -30, "presence.saturation": -10})
    _update(
        lib, sid, 2, "rename", name="Warm Matte II", rules=[{"type": "exposure", "metering": "highlights"}]
    )
    assert [(v.version, v.change_note) for v in lib.history(sid)] == [
        (3, "rename"),
        (2, "stronger"),
        (1, "created"),
    ]
    assert lib.version(sid, 1).values == {"tone.contrast": -10.0}

    diff = lib.diff(sid, 1, 3)
    assert [(c.name, c.before, c.after) for c in diff.values] == [
        ("presence.saturation", None, -10.0),
        ("tone.contrast", -10.0, -30.0),
    ]
    assert [c.type for c in diff.rules] == ["exposure"] and diff.fields == ["name"]
    assert not diff.same_look

    reverted = lib.revert(sid, 1, expected_version=3)
    assert reverted.version == 4 and reverted.change_note == "reverted to version 1"
    assert reverted.look_hash() == lib.version(sid, 1).look_hash() and reverted.name == "Warm Matte"
    assert lib.diff(sid, 1, 4).same_look
    with pytest.raises(NotFoundError):
        lib.version(sid, 9)
    with pytest.raises(ConflictError):
        lib.revert(sid, 2, expected_version=3)


# ----------------------------------------------------------------- safety


def test_writes_outside_the_styles_folder_are_refused(tmp_path: Path) -> None:
    lib = StyleLibrary(tmp_path / "styles", PathGuard(writable_roots=[tmp_path / "elsewhere"]), clock=Clock())
    with pytest.raises(WriteNotAllowedError):
        _create(lib)


@pytest.fixture
def protected_lib(tmp_path: Path) -> Iterator[StyleLibrary]:
    styles = tmp_path / "photos" / "styles"
    guard = PathGuard(writable_roots=[styles], protected_roots=[tmp_path / "photos"])
    yield StyleLibrary(styles, guard, clock=Clock())


def test_styles_folder_inside_a_protected_photo_folder_is_refused(protected_lib: StyleLibrary) -> None:
    with pytest.raises(WriteNotAllowedError, match="protected"):
        _create(protected_lib)


def test_a_hand_written_style_keeps_its_first_version_in_history(lib: StyleLibrary, root: Path) -> None:
    folder = root / "hand"
    folder.mkdir(parents=True)
    data = {
        "id": "hand",
        "name": "Hand",
        "values": {"tone.contrast": 5},
        "created_at": T0.isoformat(),
        "updated_at": T0.isoformat(),
        "version": 3,
    }
    (folder / "style.json").write_text(json.dumps(data), encoding="utf-8")
    assert [v.version for v in lib.history("hand")] == []
    _update(lib, "hand", 3, "first change", values={})
    assert [v.version for v in lib.history("hand")] == [4, 3]
    assert lib.version("hand", 3).values == {"tone.contrast": 5.0}
