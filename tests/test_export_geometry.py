from __future__ import annotations

from typing import Any

import pytest

from photoedit.core.errors import InvalidRequestError
from photoedit.core.export.geometry import Box, export_geometry, parse_ratio, warnings, zoom_plan
from photoedit.core.presets import BUILTIN_PRESETS
from photoedit.models.export import DecodeUsed, ExportSettings
from photoedit.models.subject import SubjectBox

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


def test_subject_anchor_frames_the_subject_with_the_centered_crops_size() -> None:
    settings = _preset("instagram-portrait")
    assert settings.aspect.anchor == "subject"
    centered = export_geometry(*LANDSCAPE, settings, is_raw=True)
    car = SubjectBox(left=0.75, top=0.4, right=0.85, bottom=0.5)  # x 4680-5304 px of 6240
    framed = export_geometry(*LANDSCAPE, settings, is_raw=True, subject=car)
    assert (framed.width, framed.height, framed.decode) == (centered.width, centered.height, centered.decode)
    assert (
        (framed.crop.width, framed.crop.height) == (centered.crop.width, centered.crop.height) == (3328, 4160)
    )
    # Centered on the car (x 4992) as far as the photo allows: against the right edge.
    assert framed.crop == Box(6240 - 3328, 0, 3328, 4160) and framed.subject_cut is None
    near_middle = SubjectBox(left=0.4, top=0.4, right=0.5, bottom=0.5)  # center x 2808
    assert export_geometry(*LANDSCAPE, settings, is_raw=True, subject=near_middle).crop.left == 2808 - 1664


def test_without_a_subject_or_with_the_center_anchor_the_crop_is_centered() -> None:
    car = SubjectBox(left=0.75, top=0.4, right=0.85, bottom=0.5)
    subject_anchor = _settings(aspect={"ratio": "4:5", "anchor": "subject"})
    center_anchor = _settings(aspect={"ratio": "4:5", "anchor": "center"})
    centered = export_geometry(*LANDSCAPE, center_anchor, is_raw=True)
    assert export_geometry(*LANDSCAPE, subject_anchor, is_raw=True).crop == centered.crop
    assert export_geometry(*LANDSCAPE, center_anchor, is_raw=True, subject=car).crop == centered.crop
    # Without an aspect ratio the anchor has nothing to place.
    whole = export_geometry(*LANDSCAPE, _settings(aspect={"anchor": "subject"}), is_raw=True, subject=car)
    assert whole.crop == Box(0, 0, *LANDSCAPE)


def test_a_subject_too_wide_for_the_crop_is_cut_and_centered_on() -> None:
    settings = _settings(aspect={"ratio": "4:5", "orientation": "portrait", "anchor": "subject"})
    wide = SubjectBox(left=0.05, top=0.4, right=0.75, bottom=0.6)  # 4368 px; the crop is 3328
    framed = export_geometry(*LANDSCAPE, settings, is_raw=True, subject=wide)
    assert framed.subject_cut == "wider"
    assert framed.crop.left + framed.crop.width / 2 == pytest.approx(0.4 * 6240, abs=1)


# ---- zoom (P6c.2): X-T3 landscape → Instagram portrait crops 3328×4160 into 1080×1350.

IG_FAST = 3328 / 2160  # 1.5407…: the half-size decode (3328/2 = 1664 ≥ 1080) stops covering past it
IG_QUALITY = 3328 / 1080  # 3.0815…: the crop has 1080 px across


def _box(cx: float, cy: float, w: float, h: float) -> SubjectBox:
    return SubjectBox(left=cx - w / 2, top=cy - h / 2, right=cx + w / 2, bottom=cy + h / 2)


def test_zoom_limits_for_instagram() -> None:
    plan = zoom_plan(*LANDSCAPE, _preset("instagram-portrait"), is_raw=True)
    assert plan.fast == pytest.approx(IG_FAST)
    assert plan.quality == pytest.approx(IG_QUALITY)
    assert plan.wanted == 1.0  # no subject: never zoomed automatically
    # Not a RAW (or a forced full decode): no half-size decode to lose, so fast is the quality limit.
    jpeg = zoom_plan(*LANDSCAPE, _preset("instagram-portrait"), is_raw=False)
    assert jpeg.fast == pytest.approx(IG_QUALITY)


def test_wanted_zoom_from_subject_fill() -> None:
    settings = _preset("instagram-portrait")
    # 0.3 of 6240 px = 1872 px fills 56 % of the 3328 px crop: big enough.
    assert zoom_plan(*LANDSCAPE, settings, is_raw=True, subject=_box(0.5, 0.5, 0.3, 0.2)).wanted == 1.0
    # 0.1 of the width (624 px) fills 18.75 %: 0.4 / 0.1875 = 2.133×, automatic zoom stops at the fast limit.
    plan = zoom_plan(*LANDSCAPE, settings, is_raw=True, subject=_box(0.5, 0.5, 0.1, 0.1))
    assert plan.wanted == pytest.approx(0.4 / 0.1875)
    assert plan.auto == pytest.approx(IG_FAST)
    assert not plan.limited
    # 2 % of the width (124.8 px) wants 10.7×, past the quality limit.
    tiny = zoom_plan(*LANDSCAPE, settings, is_raw=True, subject=_box(0.5, 0.5, 0.02, 0.02))
    assert tiny.wanted == pytest.approx(0.4 / (124.8 / 3328))
    assert tiny.limited
    # The height can be the larger share: a tall subject (0.5 of 4160 px against a 4160 px crop height).
    assert zoom_plan(*LANDSCAPE, settings, is_raw=True, subject=_box(0.5, 0.5, 0.05, 0.3)).wanted == (
        pytest.approx(0.4 / 0.3)
    )


def test_subject_fill_setting_changes_the_wanted_zoom() -> None:
    settings = _preset("instagram-portrait").model_copy(deep=True)
    settings.aspect.subject_fill = 0.6
    plan = zoom_plan(*LANDSCAPE, settings, is_raw=True, subject=_box(0.5, 0.5, 0.1, 0.1))
    assert plan.wanted == pytest.approx(0.6 / 0.1875)


def test_zoom_tightens_around_the_subject_and_keeps_the_output() -> None:
    subject = _box(0.3, 0.5, 0.1, 0.1)  # centered at x = 1872 px
    g = export_geometry(*LANDSCAPE, _preset("instagram-portrait"), is_raw=True, subject=subject, zoom=2)
    assert (g.width, g.height) == (1080, 1350)
    assert g.crop == Box(left=1872 - 832, top=1040, width=1664, height=2080)
    assert g.zoom == 2.0
    assert g.decode == DecodeUsed.FULL  # 1664 // 2 = 832 < 1080


def test_decode_switches_at_the_fast_limit() -> None:
    settings, subject = _preset("instagram-portrait"), _box(0.5, 0.5, 0.05, 0.05)
    at = export_geometry(*LANDSCAPE, settings, is_raw=True, subject=subject, zoom=IG_FAST)
    assert (at.crop.width, at.crop.height, at.decode) == (2160, 2700, DecodeUsed.HALF)
    past = export_geometry(*LANDSCAPE, settings, is_raw=True, subject=subject, zoom=IG_FAST + 0.01)
    assert past.decode == DecodeUsed.FULL


def test_zoom_capped_at_the_quality_limit() -> None:
    settings, subject = _preset("instagram-portrait"), _box(0.5, 0.5, 0.01, 0.01)
    g = export_geometry(*LANDSCAPE, settings, is_raw=True, subject=subject, zoom=5)
    assert (g.crop.width, g.crop.height) == (1080, 1350)
    assert g.zoom == pytest.approx(IG_QUALITY, abs=1e-6)
    assert g.scale == pytest.approx(1.0)


def test_zoom_stops_where_the_subject_and_margin_fill_the_crop() -> None:
    # 1872 px of subject + 5 % margin on each side fills a 2080 px crop: zoom 3328 / 2080 = 1.6.
    g = export_geometry(
        *LANDSCAPE, _preset("instagram-portrait"), is_raw=True, subject=_box(0.5, 0.5, 0.3, 0.2), zoom=3
    )
    assert g.zoom == pytest.approx(1.6, abs=1e-6)
    assert g.crop.width == 2080


def test_zoom_without_a_subject_zooms_on_the_center() -> None:
    g = export_geometry(*LANDSCAPE, _preset("instagram-portrait"), is_raw=True, zoom=2)
    assert g.crop == Box(left=(6240 - 1664) // 2, top=1040, width=1664, height=2080)


def test_zoom_one_is_the_old_geometry_and_is_deterministic() -> None:
    settings, subject = _preset("instagram-portrait"), _box(0.3, 0.4, 0.1, 0.1)
    plain = export_geometry(*LANDSCAPE, settings, is_raw=True, subject=subject)
    assert export_geometry(*LANDSCAPE, settings, is_raw=True, subject=subject, zoom=1.0) == plain
    zoomed = [
        export_geometry(*LANDSCAPE, settings, is_raw=True, subject=subject, zoom=1.37) for _ in range(3)
    ]
    assert zoomed[0] == zoomed[1] == zoomed[2]
    with pytest.raises(InvalidRequestError, match="zoom must be at least 1"):
        export_geometry(*LANDSCAPE, settings, is_raw=True, zoom=0.5)


def test_original_size_exports_cannot_zoom() -> None:
    settings = _settings(aspect={"ratio": "4:5", "anchor": "subject"})  # original size: crop = output
    plan = zoom_plan(*LANDSCAPE, settings, is_raw=True, subject=_box(0.5, 0.5, 0.05, 0.05))
    assert plan.quality == plan.fast == 1.0
    assert plan.limited
