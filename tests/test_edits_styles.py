"""Per-photo edits with a style: precedence, overrides relative to the style, applying, live link (P4.6)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from photoedit.core.catalog import CatalogPhoto
from photoedit.core.edits import EditStore, revision
from photoedit.core.errors import NotFoundError
from photoedit.core.render.anchors import PhotoStats
from photoedit.core.scan import SourceKind
from photoedit.core.style_rules import RuleInputs
from photoedit.core.styles import StyleLibrary
from photoedit.models import AdjustmentParams, GroupReference
from photoedit.models.style import StyleCreate, StyleUpdate
from photoedit.safety import PathGuard

STATS = PhotoStats(black=-7, white=0.5, middle=-3.7, neutral_temperature=4600, neutral_tint=4)


def photo(pid: str = "abc123") -> CatalogPhoto:
    return CatalogPhoto(
        id=pid,
        sha256="0" * 64,
        path=Path("C:/photos/DSCF0001.RAF"),
        kind=SourceKind.RAW,
        file_size=1,
        mtime_ns=1,
        width=6240,
        height=4160,
    )


class Inputs:
    """Counts how often the (possibly expensive) measurements are asked for."""

    def __init__(self) -> None:
        self.calls = 0
        self.group: GroupReference | None = None

    def __call__(self, _: CatalogPhoto) -> RuleInputs:
        self.calls += 1
        return RuleInputs(stats=STATS, as_shot=(5000.0, 2.0), camera_ev=11.0)


@pytest.fixture
def styles(tmp_path: Path) -> StyleLibrary:
    root = tmp_path / "styles"
    return StyleLibrary(
        root, PathGuard(writable_roots=[root]), clock=lambda: datetime(2026, 10, 9, tzinfo=UTC)
    )


@pytest.fixture
def inputs() -> Inputs:
    return Inputs()


@pytest.fixture
def store(tmp_path: Path, styles: StyleLibrary, inputs: Inputs) -> EditStore:
    edits = tmp_path / "edits"
    return EditStore(edits, PathGuard(writable_roots=[edits]), styles=styles, inputs=inputs)


def make_style(
    styles: StyleLibrary, values: dict[str, Any], rules: list[dict[str, Any]] | None = None
) -> str:
    return styles.create(
        StyleCreate.model_validate({"name": "Warm", "values": values, "rules": rules or []})
    ).id


def params(**groups: object) -> AdjustmentParams:
    return AdjustmentParams.model_validate(groups)


def stored(store: EditStore, pid: str = "abc123") -> dict[str, Any]:
    data: dict[str, Any] = json.loads(store.path(pid).read_text(encoding="utf-8"))
    return data


# ----------------------------------------------------------------- precedence


def test_defaults_then_style_then_overrides(store: EditStore, styles: StyleLibrary) -> None:
    sid = make_style(styles, {"tone.contrast": -10, "tone.highlights": -30})
    store.apply_style(photo(), sid)
    store.save(photo(), params(tone={"contrast": 25, "highlights": -30}))
    edit = store.effective(photo())
    assert (edit.adjustments.tone.contrast, edit.adjustments.tone.highlights) == (25, -30)
    assert edit.adjustments.detail.sharpening.amount == 40  # RAW default, untouched by the style
    # Only the tweak is stored; highlights equals the style's value, so it follows the style.
    assert stored(store)["overrides"] == {"tone.contrast": 25.0}
    assert edit.overridden == ["tone.contrast"] and edit.style_values == ["tone.contrast", "tone.highlights"]
    assert edit.style_id == sid and edit.style_version == 1 and edit.style_error is None


def test_moving_a_slider_back_to_the_style_value_follows_the_style_again(
    store: EditStore, styles: StyleLibrary
) -> None:
    sid = make_style(styles, {"tone.contrast": -10})
    store.apply_style(photo(), sid)
    store.save(photo(), params(tone={"contrast": 5}))
    store.save(photo(), params(tone={"contrast": -10}))
    assert stored(store)["overrides"] == {}
    styles.update(sid, StyleUpdate(expected_version=1, values={"tone.contrast": -20}))
    assert store.effective(photo()).adjustments.tone.contrast == -20  # live link


def test_rules_run_on_the_photos_measurements_only_when_the_style_has_rules(
    store: EditStore, styles: StyleLibrary, inputs: Inputs
) -> None:
    plain = make_style(styles, {"tone.contrast": -10})
    store.apply_style(photo(), plain)
    store.effective(photo())
    assert inputs.calls == 0  # measuring may decode the photo: never for a style without rules
    ruled = make_style(styles, {}, [{"type": "exposure", "target": -2.7}])
    edit = store.apply_style(photo(), ruled)
    assert inputs.calls > 0
    assert edit.adjustments.tone.exposure == pytest.approx(1.0)  # -2.7 - (-3.7)
    assert edit.style_values == ["tone.exposure"] and edit.rules[0].values == {"tone.exposure": 1.0}


def test_group_reference_is_stored_and_used(store: EditStore, styles: StyleLibrary) -> None:
    sid = make_style(styles, {}, [{"type": "exposure", "metering": "camera_settings"}])
    group = GroupReference(id="g1", size=4, middle=-3.0, white=0.0, camera_ev=10.0)
    edit = store.apply_style(photo(), sid, group=group)
    assert edit.adjustments.tone.exposure == pytest.approx(1.0)  # camera EV 11 vs group 10
    assert edit.group == group and stored(store)["group"]["camera_ev"] == 10.0
    assert store.apply_style(photo(), sid).group is None  # applying without "even out" clears it


# ----------------------------------------------------------------- applying


def test_applying_replaces_tweaks_of_what_the_style_sets(store: EditStore, styles: StyleLibrary) -> None:
    store.save(photo(), params(tone={"exposure": 0.5, "contrast": 30}, presence={"vibrance": 20}))
    sid = make_style(styles, {"tone.contrast": -10}, [{"type": "exposure", "target": -3.7}])
    edit = store.apply_style(photo(), sid)
    # contrast is a style value and exposure is set by its rule: both tweaks go; vibrance stays.
    assert stored(store)["overrides"] == {"presence.vibrance": 20.0}
    assert (edit.adjustments.tone.contrast, edit.adjustments.tone.exposure) == (-10, 0)
    assert edit.adjustments.presence.vibrance == 20


def test_switching_styles_keeps_other_tweaks_as_they_showed(store: EditStore, styles: StyleLibrary) -> None:
    first = make_style(styles, {"tone.contrast": -10, "presence.saturation": -20})
    second = make_style(styles, {"presence.saturation": 10})
    store.apply_style(photo(), first)
    store.save(photo(), params(tone={"contrast": 15}, presence={"saturation": -20}))
    edit = store.apply_style(photo(), second)
    # The contrast tweak (15) isn't set by the second style, so it keeps showing 15.
    assert edit.adjustments.tone.contrast == 15 and edit.adjustments.presence.saturation == 10
    assert stored(store)["overrides"] == {"tone.contrast": 15.0}


def test_removing_a_style_keeps_tweaks(store: EditStore, styles: StyleLibrary) -> None:
    sid = make_style(styles, {"tone.contrast": -10})
    store.apply_style(photo(), sid)
    store.save(photo(), params(tone={"contrast": -10}, presence={"vibrance": 20}))
    edit = store.apply_style(photo(), None)
    assert edit.style_id is None and edit.adjustments.tone.contrast == 0
    assert edit.adjustments.presence.vibrance == 20
    store.save(photo(), AdjustmentParams())
    assert not store.path("abc123").exists()  # nothing left: the file goes


def test_reset_overrides_keeps_the_style(store: EditStore, styles: StyleLibrary) -> None:
    sid = make_style(styles, {"tone.contrast": -10})
    store.apply_style(photo(), sid)
    store.save(photo(), params(tone={"contrast": 40}))
    edit = store.reset_overrides(photo())
    assert edit.style_id == sid and edit.overridden == [] and edit.adjustments.tone.contrast == -10


def test_applying_an_unknown_style_fails(store: EditStore) -> None:
    with pytest.raises(NotFoundError):
        store.apply_style(photo(), "nope")
    assert not store.path("abc123").exists()


# ----------------------------------------------------------------- revisions + broken styles


def test_unstyled_revisions_are_unchanged_from_phase_3(store: EditStore) -> None:
    store.save(photo(), params(tone={"exposure": 0.5}))
    assert store.effective(photo()).revision == revision(None, {"tone.exposure": 0.5})
    assert store.default(photo()).revision == revision(None, {})


def test_revision_follows_the_look_not_the_name(store: EditStore, styles: StyleLibrary) -> None:
    sid = make_style(styles, {"tone.contrast": -10})
    first = store.apply_style(photo(), sid).revision
    styles.update(sid, StyleUpdate(expected_version=1, name="Renamed", description="new words"))
    assert store.effective(photo()).revision == first
    styles.update(sid, StyleUpdate(expected_version=2, values={"tone.contrast": -12}))
    assert store.effective(photo()).revision != first


def test_a_missing_or_broken_style_renders_unstyled_and_says_why(
    store: EditStore, styles: StyleLibrary, tmp_path: Path
) -> None:
    sid = make_style(styles, {"tone.contrast": -10})
    store.apply_style(photo(), sid)
    store.save(photo(), params(tone={"contrast": -10}, presence={"vibrance": 5}))
    (tmp_path / "styles" / sid / "style.json").write_text("{broken", encoding="utf-8")
    edit = store.effective(photo())
    assert edit.style_id == sid and edit.style_error is not None and "not valid JSON" in edit.style_error
    assert edit.adjustments.tone.contrast == 0 and edit.adjustments.presence.vibrance == 5
    styles.delete(sid)
    edit = store.effective(photo())
    assert edit.style_error is not None and "not found" in edit.style_error


def test_without_a_style_library_styles_are_reported_not_crashed(tmp_path: Path) -> None:
    edits = tmp_path / "edits"
    plain = EditStore(edits, PathGuard(writable_roots=[edits]))
    edits.mkdir()
    plain.path("abc123").write_text(json.dumps({"photo_id": "abc123", "style_id": "warm"}), encoding="utf-8")
    edit = plain.effective(photo())
    assert edit.style_error is not None and "no style library" in edit.style_error
