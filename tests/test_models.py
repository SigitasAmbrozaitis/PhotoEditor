from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import TypeAdapter, ValidationError

from photoedit.models import (
    AdjustmentParams,
    ApplyAndExportRequest,
    ApplyStyleRequest,
    ExportPreset,
    ExportRequest,
    ExportSettings,
    JobRequest,
    Page,
    Photo,
)
from photoedit.models.adjustments import ColorGrading, CropRect, Geometry, Tone, ToneCurve
from photoedit.models.export import FileSettings, SizeSettings

NOW = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)

# ----------------------------------------------------------------- adjustments


def test_default_adjustments_are_identity() -> None:
    assert AdjustmentParams().changed_fields() == {}


def test_changed_fields_lists_only_differences() -> None:
    p = AdjustmentParams()
    p.tone.exposure = 0.5
    p.hsl.blue.saturation = -20
    p.color_grading.global_.hue = 30
    assert p.changed_fields() == {
        "tone.exposure": 0.5,
        "hsl.blue.saturation": -20,
        "color_grading.global.hue": 30,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [("exposure", 5.01), ("exposure", -5.01), ("contrast", 101), ("blacks", -101)],
)
def test_tone_ranges_enforced(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        Tone(**{field: value})


def test_assignment_is_validated() -> None:
    p = AdjustmentParams()
    with pytest.raises(ValidationError):
        p.tone.exposure = 9


def test_unknown_parameter_rejected() -> None:
    with pytest.raises(ValidationError):
        AdjustmentParams.model_validate({"tone": {"exposur": 1}})


def test_white_balance_none_means_as_shot() -> None:
    p = AdjustmentParams.model_validate({"white_balance": {"temperature": 5500}})
    assert p.white_balance.temperature == 5500
    assert p.white_balance.tint is None
    with pytest.raises(ValidationError):
        AdjustmentParams.model_validate({"white_balance": {"temperature": 1000}})


def test_tone_curve_requires_increasing_x() -> None:
    ToneCurve.model_validate({"rgb": [{"x": 0, "y": 0}, {"x": 0.5, "y": 0.6}, {"x": 1, "y": 1}]})
    with pytest.raises(ValidationError, match="increase by at least"):
        ToneCurve.model_validate({"rgb": [{"x": 0, "y": 0}, {"x": 0, "y": 1}]})
    with pytest.raises(ValidationError):
        ToneCurve.model_validate({"rgb": [{"x": 0, "y": 0}]})  # too few points


def test_color_grading_global_alias() -> None:
    cg = ColorGrading.model_validate({"global": {"hue": 200, "saturation": 10}})
    assert cg.global_.hue == 200
    assert "global" in cg.model_dump(by_alias=True)
    with pytest.raises(ValidationError):
        ColorGrading.model_validate({"global": {"hue": 360}})  # hue is [0, 360)


def test_crop_rect_must_be_non_empty() -> None:
    CropRect(left=0.1, top=0.1, right=0.9, bottom=0.9)
    with pytest.raises(ValidationError):
        CropRect(left=0.6, right=0.4)


def test_geometry_aspect_format() -> None:
    assert Geometry(aspect="4:5").aspect == "4:5"
    assert Geometry(aspect="1.91:1").aspect == "1.91:1"
    with pytest.raises(ValidationError):
        Geometry(aspect="square")


@given(
    exposure=st.floats(min_value=-5, max_value=5),
    contrast=st.floats(min_value=-100, max_value=100),
    hue=st.floats(min_value=0, max_value=359.99),
)
def test_adjustments_json_round_trip(exposure: float, contrast: float, hue: float) -> None:
    p = AdjustmentParams.model_validate(
        {"tone": {"exposure": exposure, "contrast": contrast}, "color_grading": {"shadows": {"hue": hue}}}
    )
    again = AdjustmentParams.model_validate_json(p.model_dump_json(by_alias=True))
    assert again == p


# ----------------------------------------------------------------- photo / style


def _photo(**overrides: object) -> Photo:
    data: dict[str, object] = {
        "id": "p1",
        "path": "C:/photos/DSCF0001.RAF",
        "filename": "DSCF0001.RAF",
        "folder": "C:/photos",
        "file_size": 1,
        "width": 6240,
        "height": 4160,
    }
    data.update(overrides)
    return Photo.model_validate(data)


def test_photo_rating_range() -> None:
    assert _photo(rating=5).rating == 5
    with pytest.raises(ValidationError):
        _photo(rating=6)


# ----------------------------------------------------------------- export


def test_resize_mode_requires_its_value() -> None:
    SizeSettings(mode="long_edge", long_edge=2048)
    with pytest.raises(ValidationError, match="long_edge"):
        SizeSettings(mode="long_edge")
    with pytest.raises(ValidationError, match="width, height"):
        SizeSettings(mode="width_height")


def test_file_settings_rules() -> None:
    FileSettings(format="tiff", bit_depth=16)
    with pytest.raises(ValidationError, match="8-bit"):
        FileSettings(format="jpeg", bit_depth=16)
    with pytest.raises(ValidationError, match="bit_depth"):
        FileSettings(format="png", bit_depth=12)
    with pytest.raises(ValidationError, match="JPEG only"):
        FileSettings(format="png", max_file_size_kb=500)


def test_export_preset_round_trip() -> None:
    preset = ExportPreset(id="instagram-portrait", name="Instagram portrait", target="instagram")
    preset.settings.aspect.ratio = "4:5"
    assert ExportPreset.model_validate_json(preset.model_dump_json()) == preset


# ----------------------------------------------------------------- jobs


def test_job_request_discriminated_by_kind() -> None:
    adapter: TypeAdapter[object] = TypeAdapter(JobRequest)
    apply = adapter.validate_python({"kind": "apply_style", "photo_ids": ["a"], "style_id": "warm"})
    assert isinstance(apply, ApplyStyleRequest)
    export = adapter.validate_python(
        {"kind": "export", "photo_ids": ["a"], "settings": {}, "destination": "C:/out"}
    )
    assert isinstance(export, ExportRequest)
    both = adapter.validate_python(
        {
            "kind": "apply_and_export",
            "photo_ids": ["a"],
            "style_id": "w",
            "settings": {},
            "destination": "D:/x",
        }
    )
    assert isinstance(both, ApplyAndExportRequest)
    assert both.settings == ExportSettings()


def test_job_request_validation() -> None:
    adapter: TypeAdapter[object] = TypeAdapter(JobRequest)
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "apply_style", "photo_ids": [], "style_id": "w"})  # no photos
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "export", "photo_ids": ["a"], "settings": {}})  # no destination
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "delete_everything", "photo_ids": ["a"]})


def test_page_generic() -> None:
    page = Page[Photo](items=[_photo()], total=1, offset=0, limit=50)
    assert page.items[0].id == "p1"
