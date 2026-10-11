"""Suggested crops (P6b.7): pure math on synthetic frames and subjects."""

from __future__ import annotations

import pytest

from photoedit.core.geometry import crop_inside, ratio_matches
from photoedit.core.subject.suggest import MARGIN, suggest
from photoedit.models.adjustments import CropRect
from photoedit.models.crop import CropPlacement
from photoedit.models.subject import SubjectBox

W, H = 6000.0, 4000.0
RATIO_4_5 = 4 / 5


def box(left: float, top: float, right: float, bottom: float) -> SubjectBox:
    return SubjectBox(left=left, top=top, right=right, bottom=bottom)


def keeps(crop: CropRect, subject: SubjectBox, margin: float = MARGIN) -> bool:
    """The subject lies inside the crop with ``margin`` of the crop on each side (minus float noise)."""
    mw, mh = margin * (crop.right - crop.left), margin * (crop.bottom - crop.top)
    eps = 1e-6
    return (
        subject.left >= crop.left + mw - eps
        and subject.right <= crop.right - mw + eps
        and subject.top >= crop.top + mh - eps
        and subject.bottom <= crop.bottom - mh + eps
    )


def valid(crop: CropRect, ratio: float, angle: float = 0.0) -> bool:
    return crop_inside(crop, angle, W, H) and ratio_matches(crop, ratio, W, H)


def test_no_subject_gives_the_largest_centered_crop() -> None:
    result = suggest(None, ratio=RATIO_4_5, angle=0, width=W, height=H)
    assert result.zoom == 1 and result.cut_off is None
    # 4:5 in a 6000 × 4000 frame: 3200 × 4000, centered.
    assert result.crop.left * W == pytest.approx(1400) and result.crop.right * W == pytest.approx(4600)
    assert (result.crop.top, result.crop.bottom) == (0, 1)


def test_centered_on_the_subject_as_far_as_the_frame_allows() -> None:
    subject = box(0.55, 0.4, 0.6, 0.5)
    result = suggest(subject, ratio=RATIO_4_5, angle=0, width=W, height=H)
    assert valid(result.crop, RATIO_4_5) and keeps(result.crop, subject)
    assert result.crop.bottom - result.crop.top == pytest.approx(1)  # still the largest crop
    middle = (result.crop.left + result.crop.right) / 2
    assert middle == pytest.approx(0.575)  # the subject's center


@pytest.mark.parametrize(
    ("subject", "edge"),
    [(box(0.0, 0.4, 0.05, 0.5), "left"), (box(0.93, 0.45, 0.99, 0.55), "right")],
)
def test_a_subject_near_an_edge_pulls_the_crop_to_that_edge(subject: SubjectBox, edge: str) -> None:
    result = suggest(subject, ratio=RATIO_4_5, angle=0, width=W, height=H)
    assert valid(result.crop, RATIO_4_5) and result.cut_off is None
    if edge == "left":
        assert result.crop.left == pytest.approx(0)
    else:
        assert result.crop.right == pytest.approx(1)
    # The largest crop, but the margin can't be kept against the frame's edge: the subject is still inside.
    assert subject.left >= result.crop.left - 1e-9 and subject.right <= result.crop.right + 1e-9


def test_a_subject_wider_than_the_crop_is_cut_off_and_centered() -> None:
    subject = box(0.1, 0.4, 0.9, 0.6)  # 4800 px wide; a 4:5 crop is at most 3200
    result = suggest(subject, ratio=RATIO_4_5, angle=0, width=W, height=H)
    assert result.cut_off == "wider" and valid(result.crop, RATIO_4_5)
    assert (result.crop.left + result.crop.right) / 2 == pytest.approx(0.5)
    tall = suggest(box(0.45, 0.0, 0.55, 1.0), ratio=16 / 9, angle=0, width=W, height=H)
    assert tall.cut_off == "taller"


def test_thirds_puts_the_subject_on_the_intersection_on_its_side() -> None:
    subject = box(0.38, 0.30, 0.42, 0.36)  # left of the middle and above it
    result = suggest(subject, ratio=1.0, angle=0, width=W, height=H, placement=CropPlacement.THIRDS, zoom=1.5)
    crop = result.crop
    cx, cy = subject.center
    third_x = crop.left + (crop.right - crop.left) / 3
    third_y = crop.top + (crop.bottom - crop.top) / 3
    assert cx == pytest.approx(third_x) and cy == pytest.approx(third_y)
    assert valid(crop, 1.0) and keeps(crop, subject)
    # On the other side of the middle, the other intersection.
    mirrored = box(0.58, 0.64, 0.62, 0.70)
    other = suggest(mirrored, ratio=1.0, angle=0, width=W, height=H, placement=CropPlacement.THIRDS, zoom=1.5)
    assert mirrored.center[0] == pytest.approx(other.crop.right - (other.crop.right - other.crop.left) / 3)
    assert mirrored.center[1] == pytest.approx(other.crop.bottom - (other.crop.bottom - other.crop.top) / 3)


def test_zoom_tightens_down_to_the_subject_plus_margin() -> None:
    subject = box(0.45, 0.45, 0.55, 0.55)  # 600 × 400 px
    sizes = []
    for zoom in (1.0, 1.5, 100.0):
        result = suggest(subject, ratio=RATIO_4_5, angle=0, width=W, height=H, zoom=zoom)
        assert valid(result.crop, RATIO_4_5) and keeps(result.crop, subject)
        sizes.append((result.crop.right - result.crop.left) * W)
        if zoom == 1.5:
            assert result.zoom == pytest.approx(1.5)
        if zoom == 100:
            # Capped where the subject plus margin fills the crop's width: 600 / 0.9.
            assert sizes[-1] == pytest.approx(600 / (1 - 2 * MARGIN), rel=1e-6)
            assert result.zoom == pytest.approx(3200 / sizes[-1], rel=1e-6)
    assert sizes[0] == pytest.approx(3200) and sizes[1] == pytest.approx(3200 / 1.5)


@pytest.mark.parametrize("angle", [-30.0, -7.5, 3.0, 45.0])
def test_straightened_frames_keep_the_subject_inside_the_image(angle: float) -> None:
    subject = box(0.6, 0.3, 0.68, 0.42)
    result = suggest(subject, ratio=RATIO_4_5, angle=angle, width=W, height=H)
    assert valid(result.crop, RATIO_4_5, angle) and keeps(result.crop, subject)
    centered = suggest(None, ratio=RATIO_4_5, angle=angle, width=W, height=H)
    # Off-center crops of a straightened photo can't be as big as the centered one, but are as big as they
    # can be.
    assert result.crop.right - result.crop.left <= centered.crop.right - centered.crop.left + 1e-9
    slightly_bigger = CropRect(
        left=result.crop.left - 0.002,
        top=result.crop.top - 0.002 * W / H / RATIO_4_5,
        right=result.crop.right + 0.002,
        bottom=result.crop.bottom + 0.002 * W / H / RATIO_4_5,
    )
    assert not crop_inside(slightly_bigger, angle, W, H)


def test_same_inputs_same_crop() -> None:
    subject = box(0.2, 0.6, 0.3, 0.7)
    args = {"ratio": 1.91, "angle": 4.0, "width": W, "height": H, "placement": CropPlacement.THIRDS}
    assert suggest(subject, **args) == suggest(subject, **args)  # type: ignore[arg-type]
