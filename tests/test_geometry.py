from __future__ import annotations

import math

import numpy as np
import pytest

from photoedit.core.errors import InvalidRequestError
from photoedit.core.geometry import (
    Rect,
    apply_change,
    check_geometry,
    constrain_crop,
    crop_inside,
    edited_size,
    fit_scale,
    is_identity,
    largest_crop,
    ratio_matches,
    source_map,
    sub_crop,
    turned_size,
)
from photoedit.models.adjustments import CropRect, Geometry, GeometryChange, QuarterTurn

W, H = 6240, 4160  # X-T3 landscape
FULL = CropRect()


def _crop(left: float, top: float, right: float, bottom: float) -> CropRect:
    return CropRect(left=left, top=top, right=right, bottom=bottom)


def _ratio(crop: CropRect, width: float, height: float) -> float:
    return (crop.right - crop.left) * width / ((crop.bottom - crop.top) * height)


def _apply(m: np.ndarray, x: float, y: float) -> tuple[float, float]:
    p = m @ np.array([x, y, 1.0])
    return float(p[0]), float(p[1])


# ------------------------------------------------------------------ frames and the inside test


def test_turned_size() -> None:
    assert turned_size(W, H, 0) == (W, H)
    assert turned_size(W, H, 90) == (H, W)
    assert turned_size(W, H, 180) == (W, H)
    assert turned_size(W, H, 270) == (H, W)


def test_identity() -> None:
    assert is_identity(Geometry())
    assert is_identity(Geometry(aspect="3:2"))
    assert not is_identity(Geometry(angle=0.5))
    assert not is_identity(Geometry(rotate=90))
    assert not is_identity(Geometry(flip_vertical=True))
    assert not is_identity(Geometry(crop=_crop(0, 0, 0.5, 1)))


def test_full_crop_fits_only_without_angle() -> None:
    assert crop_inside(FULL, 0, W, H)
    assert not crop_inside(FULL, 0.1, W, H)
    assert not crop_inside(FULL, -5, W, H)


@pytest.mark.parametrize(("width", "height"), [(W, H), (H, W), (1000, 1000)])
@pytest.mark.parametrize("angle", [-45, -10, -0.5, 0.5, 3, 30, 45])
def test_largest_crop_matches_the_closed_form(width: int, height: int, angle: float) -> None:
    # A centered w × h rect (w = r·h) fits a frame turned by a when w·cos + h·sin ≤ W and w·sin + h·cos ≤ H.
    crop = largest_crop(None, angle, width, height)
    r = width / height
    a = math.radians(abs(angle))
    expected_h = min(width / (r * math.cos(a) + math.sin(a)), height / (r * math.sin(a) + math.cos(a)))
    assert (crop.bottom - crop.top) * height == pytest.approx(expected_h, rel=1e-6)
    assert _ratio(crop, width, height) == pytest.approx(r, rel=1e-6)
    assert crop_inside(crop, angle, width, height)
    assert (crop.left + crop.right) / 2 == pytest.approx(0.5)
    assert (crop.top + crop.bottom) / 2 == pytest.approx(0.5)


@pytest.mark.parametrize("angle", [-20, 7.5, 45])
def test_a_crop_on_the_rotated_edge_is_in_and_one_pixel_more_is_out(angle: float) -> None:
    crop = largest_crop(0.8, angle, W, H)
    assert crop_inside(crop, angle, W, H)
    px = 1 / W
    grown = _crop(crop.left - px, crop.top, crop.right + px, crop.bottom)
    assert not crop_inside(grown, angle, W, H)


def test_fit_scale_is_zero_when_the_center_is_outside() -> None:
    # Near the top-left corner of the frame: inside the frame, but outside the image turned by 30°.
    assert fit_scale(Rect(10, 10, 5, 5), 30, W, H) == 0
    assert fit_scale(Rect(W / 2, H / 2, W / 4, H / 4), 0, W, H) == pytest.approx(2)


# ------------------------------------------------------------------ constrain


@pytest.mark.parametrize("angle", [-30, -3, 0, 2, 15, 45])
def test_constrain_shrinks_around_the_center(angle: float) -> None:
    crop = _crop(0.2, 0.1, 0.9, 0.95)
    out = constrain_crop(crop, angle, W, H)
    assert crop_inside(out, angle, W, H)
    assert _ratio(out, W, H) == pytest.approx(_ratio(crop, W, H), rel=1e-6)
    assert (out.left + out.right) / 2 == pytest.approx(0.55)
    assert (out.top + out.bottom) / 2 == pytest.approx(0.525)
    assert out.right - out.left <= crop.right - crop.left + 1e-12


def test_constrain_leaves_a_fitting_crop_alone() -> None:
    crop = _crop(0.3, 0.3, 0.6, 0.6)
    assert constrain_crop(crop, 5, W, H) == crop


def test_constrain_moves_a_corner_crop_toward_the_center() -> None:
    crop = _crop(0, 0, 0.1, 0.1)  # its center is outside the image turned by 40°
    out = constrain_crop(crop, 40, W, H)
    assert crop_inside(out, 40, W, H)
    assert out.right - out.left >= 0.01 and out.bottom - out.top >= 0.01
    assert (out.left + out.right) / 2 > 0.05  # moved inward


def test_constrain_to_a_new_ratio_keeps_the_center() -> None:
    out = constrain_crop(_crop(0.25, 0.25, 0.75, 0.75), 0, W, H, ratio=0.8)
    assert ratio_matches(out, 0.8, W, H)
    assert crop_inside(out, 0, W, H)
    assert (out.left + out.right) / 2 == pytest.approx(0.5)
    assert out.bottom - out.top == pytest.approx(1)  # the largest 4:5 at the center is full height


def test_ratio_matches_within_a_pixel() -> None:
    crop = _crop(0, 0, 3328 / W, 1)  # 3328 × 4160 = 4:5
    assert ratio_matches(crop, 0.8, W, H)
    assert ratio_matches(_crop(0, 0, 3329 / W, 1), 0.8, W, H)
    assert not ratio_matches(_crop(0, 0, 3331 / W, 1), 0.8, W, H)


# ------------------------------------------------------------------ sizes and checks


def test_edited_size() -> None:
    assert edited_size(W, H, Geometry()) == (W, H)
    assert edited_size(W, H, Geometry(rotate=90)) == (H, W)
    assert edited_size(W, H, Geometry(crop=_crop(0.25, 0, 0.75, 0.5))) == (3120, 2080)


def test_check_geometry_messages() -> None:
    check_geometry(Geometry(angle=3, crop=largest_crop(None, 3, W, H)), W, H)
    with pytest.raises(InvalidRequestError, match="blank corners"):
        check_geometry(Geometry(angle=3), W, H)
    with pytest.raises(InvalidRequestError, match=r"6240×4160 px.*4:5"):
        check_geometry(Geometry(aspect="4:5"), W, H)
    # The ratio is of the crop as shown, after the quarter turn.
    turned = Geometry(rotate=90, aspect="2:3")
    check_geometry(turned, W, H)


def test_sub_crop() -> None:
    assert sub_crop(_crop(0.2, 0.0, 0.6, 0.5), 0.25, 0, 0.75, 1) == _crop(0.3, 0.0, 0.5, 0.5)


# ------------------------------------------------------------------ changes


def test_quarter_turns_carry_the_crop() -> None:
    start = Geometry(crop=_crop(0.1, 0.2, 0.5, 0.9))
    turned = apply_change(start, GeometryChange(rotate=90), W, H)
    # Clockwise: the old bottom edge becomes the left edge.
    c = turned.crop
    assert (c.left, c.top, c.right, c.bottom) == pytest.approx((0.1, 0.1, 0.8, 0.5))
    assert edited_size(W, H, turned) == edited_size(W, H, start)[::-1]
    geometry = start
    for turn in (90, 180, 270, 0):
        geometry = apply_change(geometry, GeometryChange(rotate=turn), W, H)
    assert geometry.crop.left == pytest.approx(0.1) and geometry.crop.bottom == pytest.approx(0.9)


def test_quarter_turn_swaps_the_aspect_lock() -> None:
    start = apply_change(Geometry(), GeometryChange(aspect="4:5"), W, H)
    turned = apply_change(start, GeometryChange(rotate=270), W, H)
    assert turned.aspect == "5:4"
    check_geometry(turned, W, H)


def test_flips_mirror_the_crop_and_the_angle() -> None:
    start = Geometry(angle=4, crop=largest_crop(None, 4, W, H))
    start = start.model_copy(update={"crop": sub_crop(start.crop, 0, 0, 0.5, 0.5)})
    flipped = apply_change(start, GeometryChange(flip_horizontal=True), W, H)
    assert flipped.angle == -4 and flipped.flip_horizontal
    assert flipped.crop.left == pytest.approx(1 - start.crop.right)
    assert flipped.crop.top == start.crop.top
    back = apply_change(flipped, GeometryChange(flip_horizontal=False), W, H)
    assert back.angle == 4 and back.crop.left == pytest.approx(start.crop.left)
    # After a quarter turn an upright left-right mirror is a top-bottom mirror of the frame.
    turned = apply_change(Geometry(crop=_crop(0, 0, 0.5, 0.5)), GeometryChange(rotate=90), W, H)
    turned_flip = apply_change(turned, GeometryChange(flip_horizontal=True), W, H)
    assert turned_flip.crop.top == pytest.approx(1 - turned.crop.bottom)
    assert turned_flip.crop.left == turned.crop.left


def test_angle_change_constrains_and_explicit_crop_is_checked() -> None:
    straightened = apply_change(Geometry(), GeometryChange(angle=5), W, H)
    assert crop_inside(straightened.crop, 5, W, H)
    assert straightened.crop.right - straightened.crop.left < 1
    with pytest.raises(InvalidRequestError, match="blank corners"):
        apply_change(straightened, GeometryChange(crop=FULL), W, H)


def test_unlocking_the_aspect_keeps_the_crop() -> None:
    locked = apply_change(Geometry(), GeometryChange(aspect="1:1"), W, H)
    free = apply_change(locked, GeometryChange.model_validate({"aspect": None}), W, H)
    assert free.aspect is None and free.crop == locked.crop
    # Not given at all: the lock stays.
    assert apply_change(locked, GeometryChange(angle=1), W, H).aspect == "1:1"


def test_reset() -> None:
    edited = apply_change(Geometry(), GeometryChange(angle=10, rotate=180, flip_vertical=True), W, H)
    assert apply_change(edited, GeometryChange(reset=True), W, H) == Geometry()


# ------------------------------------------------------------------ source map


def test_source_map_identity_and_scale() -> None:
    m = source_map(Geometry(), FULL, 100, 60, 100, 60)
    assert _apply(m, 0, 0) == (0, 0) and _apply(m, 99, 59) == (99, 59)
    half = source_map(Geometry(), FULL, 100, 60, 50, 30)
    assert _apply(half, 0, 0) == (0.5, 0.5)  # each output pixel covers 2×2 source pixels


@pytest.mark.parametrize(
    ("geometry", "top_left_source"),
    [
        (Geometry(rotate=90), (0, 59)),  # clockwise: the bottom-left corner comes to the top left
        (Geometry(rotate=180), (99, 59)),
        (Geometry(rotate=270), (99, 0)),
        (Geometry(flip_horizontal=True), (99, 0)),
        (Geometry(flip_vertical=True), (0, 59)),
        (Geometry(flip_horizontal=True, rotate=90), (99, 59)),
    ],
)
def test_source_map_turns_and_flips(geometry: Geometry, top_left_source: tuple[int, int]) -> None:
    out_w, out_h = turned_size(100, 60, geometry.rotate)
    m = source_map(geometry, FULL, 100, 60, int(out_w), int(out_h))
    assert _apply(m, 0, 0) == top_left_source


def test_source_map_straighten_turns_around_the_center() -> None:
    geometry = Geometry(angle=10)
    m = source_map(geometry, FULL, 101, 61, 101, 61)
    cx, cy = _apply(m, 50, 30)
    assert cx == pytest.approx(50) and cy == pytest.approx(30)
    # A point right of the center shows content from above-right of it (the image turned clockwise).
    x, y = _apply(m, 60, 30)
    assert x == pytest.approx(50 + 10 * math.cos(math.radians(10)))
    assert y == pytest.approx(30 - 10 * math.sin(math.radians(10)))


@pytest.mark.parametrize("size", [(6240, 4160), (3120, 2080), (2048, 1365)])
def test_source_map_frames_the_same_content_at_every_decode_size(size: tuple[int, int]) -> None:
    geometry = Geometry(angle=-7, rotate=270, flip_vertical=True)
    crop = constrain_crop(_crop(0.1, 0.2, 0.7, 0.6), -7, *turned_size(*size, 270))
    m = source_map(geometry, crop, *size, 400, 300)
    sw, sh = size
    corners = [_apply(m, x, y) for x, y in ((-0.5, -0.5), (399.5, -0.5), (399.5, 299.5))]
    normalized = [((x + 0.5) / sw, (y + 0.5) / sh) for x, y in corners]
    reference = source_map(geometry, crop, 6240, 4160, 400, 300)
    expected = [
        ((x + 0.5) / 6240, (y + 0.5) / 4160)
        for x, y in (_apply(reference, *p) for p in ((-0.5, -0.5), (399.5, -0.5), (399.5, 299.5)))
    ]
    for got, want in zip(normalized, expected, strict=True):
        assert got == pytest.approx(want, abs=1e-3)  # 1365 isn't exactly 2048 × 2/3


@pytest.mark.parametrize("rotate", [0, 90, 180, 270])
@pytest.mark.parametrize("flip", [False, True])
def test_crop_box_to_upright_inverts_subject_in_crop(rotate: QuarterTurn, flip: bool) -> None:
    from photoedit.core.geometry import crop_box_to_upright, subject_in_crop
    from photoedit.models.subject import SubjectBox

    geometry = Geometry(
        rotate=rotate, flip_horizontal=flip, crop=CropRect(left=0.1, top=0.2, right=0.9, bottom=0.95)
    )
    box = SubjectBox(left=0.3, top=0.35, right=0.5, bottom=0.6)
    edited = subject_in_crop(box, geometry, 6240, 4160)
    assert edited is not None
    back = crop_box_to_upright(edited, geometry, 6240, 4160)
    assert back is not None
    for name in ("left", "top", "right", "bottom"):
        assert getattr(back, name) == pytest.approx(getattr(box, name), abs=1e-9)


def test_crop_box_to_upright_straightened_holds_the_box() -> None:
    from photoedit.core.geometry import crop_box_to_upright, subject_in_crop
    from photoedit.models.subject import SubjectBox

    geometry = Geometry(angle=5, crop=CropRect(left=0.1, top=0.1, right=0.9, bottom=0.9))
    edited = SubjectBox(left=0.4, top=0.4, right=0.6, bottom=0.6)
    upright = crop_box_to_upright(edited, geometry, 6240, 4160)
    assert upright is not None
    again = subject_in_crop(upright, geometry, 6240, 4160)
    assert again is not None  # the bounding box grows each way round, so it holds the original box
    assert again.left <= edited.left and again.right >= edited.right
    assert again.top <= edited.top and again.bottom >= edited.bottom
