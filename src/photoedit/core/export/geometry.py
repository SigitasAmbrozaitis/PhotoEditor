"""Export geometry: the aspect crop, the output size and the decode size, as pure functions.

Everything is in the photo's upright full-size pixels. Rounding is to nearest with ties up, defined once in
``_round``, so the same settings always give the same sizes.

A **zoom** (P6c.2) makes the crop tighter than the largest one of its ratio and keeps the output size: zoom 2
crops half the width and height and resizes that to the same output. Two limits matter. Up to the **fast** one
a RAW's half-size decode still covers the output; past it the export needs the full decode (~30× slower, PLAN
§7.1). At the **quality** one the crop has as many pixels as the output; past it the export would enlarge, so
no zoom goes further.
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
# Zooms this close count as equal (a zoom from a slider is rounded; the limits are exact).
ZOOM_TOLERANCE = 1e-6


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
    zoom: float = 1.0  # the zoom used (a requested one stops where the subject plus margin fills the crop)

    @property
    def scale(self) -> float:
        """Output pixels per original pixel (> 1 = enlarged)."""
        return self.width / self.crop.width


@dataclass(frozen=True)
class ZoomPlan:
    """What automatic zoom wants for a photo, and how far any zoom may go."""

    wanted: float  # where the subject fills `subject_fill` of the crop (1 = big enough already)
    fast: float  # the highest zoom a half-size decode still covers
    quality: float  # the highest zoom without enlarging

    @property
    def auto(self) -> float:
        """The automatic zoom: as wanted, but no further than the fast limit."""
        return min(self.wanted, self.fast)

    @property
    def limited(self) -> bool:
        """The subject stays smaller than wanted even at the quality limit."""
        return self.wanted > self.quality + ZOOM_TOLERANCE


def _round(value: float) -> int:
    return math.floor(value + 0.5)


def _fit(width: int, height: int, ratio: float) -> tuple[float, float]:
    """The exact size of the largest box of ``ratio`` (width ÷ height) inside width × height."""
    if width / height > ratio:
        return height * ratio, float(height)
    return float(width), width / ratio


def _zoomed(width: int, height: int, ratio: float, zoom: float) -> tuple[int, int]:
    """The largest box of ``ratio``, ``zoom`` times smaller in each direction, in whole pixels."""
    fit_w, fit_h = _fit(width, height, ratio)
    return min(width, max(1, _round(fit_w / zoom))), min(height, max(1, _round(fit_h / zoom)))


def _framing(
    width: int, height: int, ratio: float, subject: SubjectBox, zoom: float
) -> tuple[Box, str | None, float]:
    """A box of ``ratio`` placed on ``subject`` (normalized to the photo) by the suggested-crop rule (P6b.7,
    centered), ``zoom`` times tighter than the largest one as far as the subject plus margin allows; whether
    the subject is cut off; and the zoom used."""
    found = suggest(subject, ratio=ratio, angle=0, width=width, height=height, zoom=zoom)
    used = max(1.0, found.zoom)
    crop_w, crop_h = _zoomed(width, height, ratio, used)
    cx = (found.crop.left + found.crop.right) / 2 * width
    cy = (found.crop.top + found.crop.bottom) / 2 * height
    left = min(width - crop_w, max(0, _round(cx - crop_w / 2)))
    top = min(height - crop_h, max(0, _round(cy - crop_h / 2)))
    return Box(left, top, crop_w, crop_h), found.cut_off, used


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


def _output(width: int, height: int, settings: ExportSettings) -> tuple[float | None, int, int]:
    """The aspect ratio (None = the photo's own) and the output size, which a zoom doesn't change."""
    size = settings.size
    ratio = _target_ratio(width, height, settings.aspect, size)
    # Sizes come from the exact crop, not the rounded one, so a 4:5 crop of a small photo still gives 4:5.
    crop_w, crop_h = (float(width), float(height)) if ratio is None else _fit(width, height, ratio)
    scale = _scale(size, crop_w, crop_h)
    if size.dont_enlarge:
        scale = min(scale, 1.0)
    return ratio, max(1, _round(crop_w * scale)), max(1, _round(crop_h * scale))


def _half_covers(
    settings: ExportSettings, is_raw: bool, crop_w: int, crop_h: int, out_w: int, out_h: int
) -> bool:
    # LibRaw's half-size decode has half the pixels in each direction (rounded down).
    return (
        is_raw and settings.file.decode == DecodeSize.AUTO and out_w <= crop_w // 2 and out_h <= crop_h // 2
    )


def zoom_plan(
    width: int, height: int, settings: ExportSettings, *, is_raw: bool, subject: SubjectBox | None = None
) -> ZoomPlan:
    """How far a photo of ``width`` × ``height`` may zoom in this export, and the zoom at which ``subject``
    (normalized to the photo) fills ``settings.aspect.subject_fill`` of the crop's width or height (1 without
    a subject)."""
    if width < 1 or height < 1:
        raise InvalidRequestError(f"photo size {width}×{height} is not valid")
    _, out_w, out_h = _output(width, height, settings)
    fit_w, fit_h = _fit(width, height, out_w / out_h)
    quality = max(1.0, min(fit_w / out_w, fit_h / out_h))
    if _half_covers(settings, is_raw, *_zoomed(width, height, out_w / out_h, 1.0), out_w, out_h):
        fast = max(1.0, min(quality, fit_w / (2 * out_w), fit_h / (2 * out_h)))
    else:
        fast = quality  # the full decode already (or not a RAW): zooming costs nothing more
    wanted = 1.0
    if subject is not None:
        share = max(
            (subject.right - subject.left) * width / fit_w, (subject.bottom - subject.top) * height / fit_h
        )
        wanted = max(1.0, settings.aspect.subject_fill / share)
    return ZoomPlan(wanted=wanted, fast=fast, quality=quality)


def export_geometry(
    width: int,
    height: int,
    settings: ExportSettings,
    *,
    is_raw: bool,
    subject: SubjectBox | None = None,
    zoom: float = 1.0,
) -> ExportGeometry:
    """Crop, output size and decode size for a photo of ``width`` × ``height`` (upright, full size).

    With the ``subject`` anchor, the aspect crop frames ``subject`` (normalized to the photo); without a
    subject it is centered. ``zoom`` (≥ 1) tightens the crop around the subject (or the center), up to the
    quality limit and to where the subject plus margin fills the crop.
    """
    if width < 1 or height < 1:
        raise InvalidRequestError(f"photo size {width}×{height} is not valid")
    if zoom < 1:
        raise InvalidRequestError(f"zoom must be at least 1, not {zoom}")
    ratio, out_w, out_h = _output(width, height, settings)
    if zoom > 1:
        zoom = min(zoom, zoom_plan(width, height, settings, is_raw=is_raw).quality)
    # Crop to the output's exact ratio, so resizing never stretches (the difference is under a pixel).
    cut = None
    used = 1.0
    if (out_w, out_h) == (width, height) and zoom <= 1:
        crop = Box(0, 0, width, height)
    elif subject is not None and settings.aspect.anchor == CropAnchor.SUBJECT and ratio is not None:
        crop, cut, used = _framing(width, height, out_w / out_h, subject, zoom)
    else:
        crop_w, crop_h = _zoomed(width, height, out_w / out_h, zoom)
        crop, used = Box((width - crop_w) // 2, (height - crop_h) // 2, crop_w, crop_h), zoom
    decode = DecodeUsed.FULL
    if _half_covers(settings, is_raw, crop.width, crop.height, out_w, out_h):
        decode = DecodeUsed.HALF
    return ExportGeometry(
        crop=crop, width=out_w, height=out_h, decode=decode, subject_cut=cut, zoom=round(used, 6)
    )


def warnings(geometry: ExportGeometry) -> list[str]:
    """Things worth telling the user about this photo's export geometry."""
    if geometry.scale > 1.0 + 1e-9:
        return [f"enlarged {geometry.scale:.2f}×"]
    return []
