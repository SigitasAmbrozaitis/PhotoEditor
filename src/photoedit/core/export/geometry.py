"""Export geometry: the aspect crop, the output size and the decode size, as pure functions.

Everything is in the photo's upright full-size pixels. Rounding is to nearest with ties up, defined once in
``_round``, so the same settings always give the same sizes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from photoedit.core.errors import InvalidRequestError
from photoedit.core.geometry import oriented_ratio, parse_ratio
from photoedit.core.subject.suggest import suggest
from photoedit.models.export import (
    AspectSettings,
    CropAnchor,
    DecodeSize,
    DecodeUsed,
    ExportSettings,
    ResizeMode,
    SizeSettings,
)
from photoedit.models.subject import SubjectBox

# In width × height mode, an aspect ratio this close to the box's own ratio is taken as the box's ratio: named
# ratios are rounded (1.91:1 is really 1080×566, A4's 1.414:1 is 3508×2480), and the box is what was meant.
_BOX_RATIO_TOLERANCE = 0.01


@dataclass(frozen=True)
class Box:
    left: int
    top: int
    width: int
    height: int


@dataclass(frozen=True)
class ExportGeometry:
    crop: Box
    width: int
    height: int
    decode: DecodeUsed
    # "wider" or "taller" when the aspect crop can't hold the whole subject it frames.
    subject_cut: str | None = None

    @property
    def scale(self) -> float:
        """Output pixels per original pixel (> 1 = enlarged)."""
        return self.width / self.crop.width


def _round(value: float) -> int:
    return math.floor(value + 0.5)


def _fit(width: int, height: int, ratio: float) -> tuple[float, float]:
    """The exact size of the largest box of ``ratio`` (width ÷ height) inside width × height."""
    if width / height > ratio:
        return height * ratio, float(height)
    return float(width), width / ratio


def _centered(width: int, height: int, ratio: float) -> Box:
    """That box in whole pixels, centered."""
    fit_w, fit_h = _fit(width, height, ratio)
    crop_w = min(width, max(1, _round(fit_w)))
    crop_h = min(height, max(1, _round(fit_h)))
    return Box((width - crop_w) // 2, (height - crop_h) // 2, crop_w, crop_h)


def _framing(width: int, height: int, ratio: float, subject: SubjectBox) -> tuple[Box, str | None]:
    """The centered box's size, placed on ``subject`` (normalized to the photo) by the suggested-crop rule
    (P6b.7, centered, zoom 1), and whether the subject is cut off."""
    box = _centered(width, height, ratio)
    found = suggest(subject, ratio=box.width / box.height, angle=0, width=width, height=height)
    cx = (found.crop.left + found.crop.right) / 2 * width
    cy = (found.crop.top + found.crop.bottom) / 2 * height
    left = min(width - box.width, max(0, _round(cx - box.width / 2)))
    top = min(height - box.height, max(0, _round(cy - box.height / 2)))
    return Box(left, top, box.width, box.height), found.cut_off


def _box(size: SizeSettings, crop_portrait: bool, crop_landscape: bool) -> tuple[int, int]:
    """The width × height box, turned to match the crop's orientation (a square crop leaves it as given)."""
    assert size.width is not None and size.height is not None
    box_w, box_h = size.width, size.height
    if (crop_landscape and box_h > box_w) or (crop_portrait and box_w > box_h):
        box_w, box_h = box_h, box_w
    return box_w, box_h


def _scale(size: SizeSettings, crop_w: float, crop_h: float) -> float:
    match size.mode:
        case ResizeMode.ORIGINAL:
            return 1.0
        case ResizeMode.LONG_EDGE:
            assert size.long_edge is not None
            return size.long_edge / max(crop_w, crop_h)
        case ResizeMode.SHORT_EDGE:
            assert size.short_edge is not None
            return size.short_edge / min(crop_w, crop_h)
        case ResizeMode.WIDTH_HEIGHT:
            box_w, box_h = _box(size, crop_h > crop_w, crop_w > crop_h)
            return min(box_w / crop_w, box_h / crop_h)
        case ResizeMode.MEGAPIXELS:
            assert size.megapixels is not None
            return math.sqrt(size.megapixels * 1e6 / (crop_w * crop_h))
        case ResizeMode.PERCENTAGE:
            assert size.percentage is not None
            return size.percentage / 100


def _target_ratio(width: int, height: int, aspect: AspectSettings, size: SizeSettings) -> float | None:
    if aspect.ratio is None:
        return None
    ratio = oriented_ratio(parse_ratio(aspect.ratio), aspect.orientation, width, height)
    if size.mode == ResizeMode.WIDTH_HEIGHT:
        box_w, box_h = _box(size, ratio < 1, ratio > 1)
        if abs(box_w / box_h - ratio) <= _BOX_RATIO_TOLERANCE * ratio:
            return box_w / box_h
    return ratio


def export_geometry(
    width: int, height: int, settings: ExportSettings, *, is_raw: bool, subject: SubjectBox | None = None
) -> ExportGeometry:
    """Crop, output size and decode size for a photo of ``width`` × ``height`` (upright, full size).

    With the ``subject`` anchor, the aspect crop frames ``subject`` (normalized to the photo); without a
    subject it is centered.
    """
    if width < 1 or height < 1:
        raise InvalidRequestError(f"photo size {width}×{height} is not valid")
    size = settings.size
    ratio = _target_ratio(width, height, settings.aspect, size)
    # Sizes come from the exact crop, not the rounded one, so a 4:5 crop of a small photo still gives 4:5.
    crop_w, crop_h = (float(width), float(height)) if ratio is None else _fit(width, height, ratio)
    scale = _scale(size, crop_w, crop_h)
    if size.dont_enlarge:
        scale = min(scale, 1.0)
    out_w = max(1, _round(crop_w * scale))
    out_h = max(1, _round(crop_h * scale))
    # Crop to the output's exact ratio, so resizing never stretches (the difference is under a pixel).
    cut = None
    if (out_w, out_h) == (width, height):
        crop = Box(0, 0, width, height)
    elif subject is not None and settings.aspect.anchor == CropAnchor.SUBJECT:
        crop, cut = _framing(width, height, out_w / out_h, subject)
    else:
        crop = _centered(width, height, out_w / out_h)
    decode = DecodeUsed.FULL
    # LibRaw's half-size decode has half the pixels in each direction (rounded down).
    if (
        is_raw
        and settings.file.decode == DecodeSize.AUTO
        and out_w <= crop.width // 2
        and out_h <= crop.height // 2
    ):
        decode = DecodeUsed.HALF
    return ExportGeometry(crop=crop, width=out_w, height=out_h, decode=decode, subject_cut=cut)


def warnings(geometry: ExportGeometry) -> list[str]:
    """Things worth telling the user about this photo's export geometry."""
    if geometry.scale > 1.0 + 1e-9:
        return [f"enlarged {geometry.scale:.2f}×"]
    return []
