from __future__ import annotations

from typing import Any

import pytest

from photoedit.core.errors import InvalidRequestError
from photoedit.core.export.geometry import Box, export_geometry, parse_ratio, warnings
from photoedit.core.presets import BUILTIN_PRESETS
from photoedit.models.export import DecodeUsed, ExportSettings

LANDSCAPE = (6240, 4160)
PORTRAIT = (4160, 6240)


def _settings(**sections: Any) -> ExportSettings:
    return ExportSettings.model_validate(sections)


def _preset(preset_id: str) -> ExportSettings:
    return next(p.settings for p in BUILTIN_PRESETS if p.id == preset_id)


def _size(photo: tuple[int, int], settings: ExportSettings, *, is_raw: bool = True) -> tuple[int, int]:
    g = export_geometry(*photo, settings, is_raw=is_raw)
    return g.width, g.height


def test_parse_ratio() -> None:
    assert parse_ratio("4:5") == 0.8
    assert parse_ratio("1.91:1") == 1.91
    with pytest.raises(InvalidRequestError, match="positive"):
        parse_ratio("0:1")


@pytest.mark.parametrize(
    ("preset_id", "landscape", "portrait"),
    [
        ("instagram-portrait", (1080, 1350), (1080, 1350)),
        ("instagram-square", (1080, 1080), (1080, 1080)),
        ("instagram-landscape", (1080, 566), (1080, 566)),
        ("instagram-story", (1080, 1920), (1080, 1920)),
        ("print-4x6", (1800, 1200), (1200, 1800)),
        ("print-5x7", (2100, 1500), (1500, 2100)),
        ("print-8x10", (3000, 2400), (2400, 3000)),
        ("print-a4", (3508, 2480), (2480, 3508)),
        ("print-a3-fine-art", (4961, 3508), (3508, 4961)),
        ("web-full", (2048, 1365), (1365, 2048)),
    ],
)
def test_builtin_preset_sizes(preset_id: str, landscape: tuple[int, int], portrait: tuple[int, int]) -> None:
    settings = _preset(preset_id)
    assert _size(LANDSCAPE, settings) == landscape
    assert _size(PORTRAIT, settings) == portrait


def test_crop_is_centered_and_matches_the_output_ratio() -> None:
    g = export_geometry(*LANDSCAPE, _preset("instagram-portrait"), is_raw=True)
    assert g.crop == Box(left=1456, top=0, width=3328, height=4160)
    assert g.crop.width * g.height == g.crop.height * g.width


def test_no_ratio_keeps_the_whole_frame() -> None:
    g = export_geometry(*LANDSCAPE, _settings(), is_raw=True)
    assert g.crop == Box(0, 0, 6240, 4160)
    assert (g.width, g.height) == LANDSCAPE


def test_orientation_auto_follows_the_photo_and_can_be_forced() -> None:
    auto = _settings(aspect={"ratio": "3:2"})
    assert export_geometry(*LANDSCAPE, auto, is_raw=False).crop.width == 6240
    assert export_geometry(*PORTRAIT, auto, is_raw=False).crop == Box(0, 0, 4160, 6240)
    forced = _settings(aspect={"ratio": "3:2", "orientation": "landscape"})
    assert export_geometry(*PORTRAIT, forced, is_raw=False).crop == Box(0, 1733, 4160, 2773)
    square = _settings(aspect={"ratio": "4:5"})
    assert export_geometry(1000, 1000, square, is_raw=False).crop == Box(100, 0, 800, 1000)


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        ({"mode": "original"}, (6240, 4160)),
        ({"mode": "long_edge", "long_edge": 1000}, (1000, 667)),
        ({"mode": "short_edge", "short_edge": 1000}, (1500, 1000)),
        ({"mode": "width_height", "width": 800, "height": 1000}, (1000, 667)),  # box turned to landscape
        ({"mode": "megapixels", "megapixels": 6}, (3000, 2000)),
        ({"mode": "percentage", "percentage": 25}, (1560, 1040)),
    ],
)
def test_resize_modes(size: dict[str, Any], expected: tuple[int, int]) -> None:
    assert _size(LANDSCAPE, _settings(size=size)) == expected


def test_dont_enlarge() -> None:
    small = (600, 400)
    big = {"mode": "long_edge", "long_edge": 1200}
    assert _size(small, _settings(size=big), is_raw=False) == (600, 400)
    enlarged = export_geometry(*small, _settings(size={**big, "dont_enlarge": False}), is_raw=False)
    assert (enlarged.width, enlarged.height) == (1200, 800)
    assert warnings(enlarged) == ["enlarged 2.00×"]
    assert warnings(export_geometry(*LANDSCAPE, _settings(size=big), is_raw=True)) == []


def test_odd_ratio_a4_on_a_small_jpeg() -> None:
    a4 = _preset("print-a4")
    g = export_geometry(900, 600, a4, is_raw=False)
    assert (g.width, g.height) == (3508, 2480)
    assert g.decode == DecodeUsed.FULL


def test_decode_choice() -> None:
    web = _preset("web-full")  # 2048 px long edge
    assert export_geometry(*LANDSCAPE, web, is_raw=True).decode == DecodeUsed.HALF
    assert export_geometry(*LANDSCAPE, web, is_raw=False).decode == DecodeUsed.FULL  # JPEGs decode fully
    assert export_geometry(*LANDSCAPE, _preset("print-a4"), is_raw=True).decode == DecodeUsed.FULL  # forced
    original = export_geometry(*LANDSCAPE, _settings(), is_raw=True)
    assert original.decode == DecodeUsed.FULL


def test_decode_choice_boundary() -> None:
    exactly_half = _settings(size={"mode": "long_edge", "long_edge": 3120})
    one_more = _settings(size={"mode": "long_edge", "long_edge": 3121})
    assert export_geometry(*LANDSCAPE, exactly_half, is_raw=True).decode == DecodeUsed.HALF
    assert export_geometry(*LANDSCAPE, one_more, is_raw=True).decode == DecodeUsed.FULL


def test_subject_anchor_is_rejected_until_phase_6() -> None:
    settings = _settings(aspect={"ratio": "4:5", "anchor": "subject"})
    with pytest.raises(InvalidRequestError, match="Phase 6"):
        export_geometry(*LANDSCAPE, settings, is_raw=True)
    # Without a crop the anchor does nothing, so it isn't an error.
    export_geometry(*LANDSCAPE, _settings(aspect={"anchor": "subject"}), is_raw=True)
