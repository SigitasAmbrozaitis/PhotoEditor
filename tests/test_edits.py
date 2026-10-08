from __future__ import annotations

import json
from pathlib import Path

import pytest

from photoedit.core.catalog import CatalogPhoto
from photoedit.core.edits import EditStore, apply_overrides, differences, source_defaults
from photoedit.core.errors import InvalidRequestError
from photoedit.core.render.pipeline import UnsupportedParameterError
from photoedit.core.scan import SourceKind
from photoedit.models import AdjustmentParams
from photoedit.safety import PathGuard, WriteNotAllowedError


def photo(kind: SourceKind = SourceKind.RAW, pid: str = "abc123") -> CatalogPhoto:
    return CatalogPhoto(
        id=pid,
        sha256="f" * 64,
        path=Path("C:/p/x.RAF"),
        kind=kind,
        file_size=1,
        mtime_ns=1,
        width=60,
        height=40,
    )


@pytest.fixture
def store(tmp_path: Path) -> EditStore:
    workspace = tmp_path / "workspace"
    return EditStore(workspace / "edits", PathGuard(writable_roots=[workspace]))


def params(**groups: object) -> AdjustmentParams:
    return AdjustmentParams.model_validate(groups)


def test_source_defaults() -> None:
    assert source_defaults(SourceKind.RAW) == AdjustmentParams()
    assert source_defaults(SourceKind.RASTER).detail.sharpening.amount == 0


def test_unedited_photo_has_default_params_and_a_stable_revision(store: EditStore) -> None:
    edit = store.effective(photo())
    assert edit.adjustments == AdjustmentParams() and edit.overridden == [] and edit.style_id is None
    assert edit.revision == store.default(photo()).revision


def test_save_stores_only_the_differences(store: EditStore) -> None:
    edited = params(tone={"exposure": 0.5, "contrast": 20}, hsl={"blue": {"saturation": -30}})
    result = store.save(photo(), edited)
    assert result.adjustments == edited
    assert result.overridden == ["hsl.blue.saturation", "tone.contrast", "tone.exposure"]
    on_disk = json.loads(store.path("abc123").read_text(encoding="utf-8"))
    assert on_disk == {
        "schema_version": 1,
        "photo_id": "abc123",
        "style_id": None,
        "overrides": {"tone.exposure": 0.5, "tone.contrast": 20.0, "hsl.blue.saturation": -30.0},
    }
    assert store.effective(photo()).adjustments == edited
    assert result.revision != store.default(photo()).revision


def test_curves_are_stored_as_whole_lists(store: EditStore) -> None:
    curve = [{"x": 0, "y": 0.1}, {"x": 0.5, "y": 0.6}, {"x": 1, "y": 1}]
    result = store.save(photo(), params(tone_curve={"rgb": curve}))
    assert result.overridden == ["tone_curve.rgb"]
    assert [p.y for p in store.effective(photo()).adjustments.tone_curve.rgb] == [0.1, 0.6, 1]


def test_saving_the_defaults_removes_the_file(store: EditStore) -> None:
    store.save(photo(), params(tone={"exposure": 1}))
    assert store.path("abc123").is_file()
    store.save(photo(), AdjustmentParams())
    assert not store.path("abc123").exists()


def test_raster_defaults_are_the_baseline_for_differences(store: EditStore) -> None:
    jpeg = photo(SourceKind.RASTER)
    result = store.save(jpeg, source_defaults(SourceKind.RASTER))
    assert result.overridden == []
    sharpened = store.save(jpeg, params(detail={"sharpening": {"amount": 40}}))
    assert sharpened.overridden == ["detail.sharpening.amount"]


def test_reset(store: EditStore) -> None:
    store.save(photo(), params(tone={"exposure": 1}))
    store.reset("abc123")
    assert store.effective(photo()).overridden == []
    store.reset("abc123")  # nothing to delete: fine


def test_later_phase_parameters_are_rejected(store: EditStore) -> None:
    with pytest.raises(UnsupportedParameterError, match=r"geometry.angle"):
        store.save(photo(), params(geometry={"angle": 5}))
    assert not store.path("abc123").exists()


def test_edit_files_go_through_the_guard(tmp_path: Path) -> None:
    store = EditStore(tmp_path / "elsewhere", PathGuard(writable_roots=[tmp_path / "workspace"]))
    with pytest.raises(WriteNotAllowedError):
        store.save(photo(), params(tone={"exposure": 1}))


def test_hand_edited_files_are_validated(store: EditStore) -> None:
    store.path("abc123").parent.mkdir(parents=True)
    store.path("abc123").write_text(
        json.dumps({"schema_version": 1, "photo_id": "abc123", "overrides": {"tone.exposure": 9}}),
        encoding="utf-8",
    )
    with pytest.raises(InvalidRequestError, match=r"tone\.exposure"):
        store.effective(photo())
    store.path("abc123").write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
    with pytest.raises(InvalidRequestError, match="invalid"):
        store.load("abc123")


def test_apply_overrides_rejects_unknown_names() -> None:
    with pytest.raises(InvalidRequestError, match=r"unknown parameter 'tone.brightness'"):
        apply_overrides(AdjustmentParams(), {"tone.brightness": 1})
    with pytest.raises(InvalidRequestError, match="unknown parameter"):
        apply_overrides(AdjustmentParams(), {"nope.x": 1})


def test_differences_and_apply_round_trip() -> None:
    edited = params(
        white_balance={"temperature": 4800, "tint": 5},
        color_grading={"global": {"hue": 30, "saturation": 10}},
        effects={"vignette": {"amount": -20}},
    )
    diff = differences(AdjustmentParams(), edited)
    assert "color_grading.global.hue" in diff  # serialized with the alias
    assert apply_overrides(AdjustmentParams(), diff) == edited
