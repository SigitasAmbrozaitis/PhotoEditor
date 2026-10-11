"""Per-photo geometry as pure math: frames, the straighten rotation, crop rules and source maps.

Order (PLAN 4.3, decided 2026-10-11): flips → quarter turn → straighten → crop. The *frame* is the upright
photo after the flips and the quarter turn. The straighten angle turns the image inside the frame around its
center (clockwise positive, with y pointing down as on screen), and the crop is normalized to the frame, so it
stays put while the angle changes. A crop must lie inside the straightened image: no blank corners.

Sizes are floats in whatever pixels the caller works in (full-size, half-size decode, preview base); the
normalized crop means the same framing at every size.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from photoedit.core.errors import InvalidRequestError
from photoedit.models.adjustments import CropRect, Geometry, GeometryChange, QuarterTurn
from photoedit.models.subject import MIN_BOX_SIZE, SubjectBox

# The smallest crop (fraction of the frame on each side) that constrain_crop produces; a little above the
# model's 1 % minimum, so float rounding never takes a constrained crop below it.
_MIN_CROP = 0.012
# Inside tests allow this much (in normalized units): far below a pixel, above float noise.
_TOLERANCE = 1e-7
# Crops the constraint builds are shrunk by this factor, so they pass the inside test despite rounding.
_SAFETY = 1 - 1e-9

type Matrix = npt.NDArray[np.float64]


@dataclass(frozen=True)
class Rect:
    """A crop in frame pixels: center and half sizes."""

    cx: float
    cy: float
    hw: float
    hh: float

    @classmethod
    def from_crop(cls, crop: CropRect, width: float, height: float) -> Rect:
        return cls(
            (crop.left + crop.right) / 2 * width,
            (crop.top + crop.bottom) / 2 * height,
            (crop.right - crop.left) / 2 * width,
            (crop.bottom - crop.top) / 2 * height,
        )

    def to_crop(self, width: float, height: float) -> CropRect:
        def clamp(value: float) -> float:
            return min(1.0, max(0.0, value))

        return CropRect(
            left=clamp((self.cx - self.hw) / width),
            top=clamp((self.cy - self.hh) / height),
            right=clamp((self.cx + self.hw) / width),
            bottom=clamp((self.cy + self.hh) / height),
        )


def is_identity(geometry: Geometry) -> bool:
    """True when the geometry leaves the pixels as they are (an aspect lock alone changes nothing)."""
    return geometry.model_copy(update={"aspect": None}) == Geometry()


def turned_size(width: float, height: float, rotate: QuarterTurn) -> tuple[float, float]:
    """The frame's size after the quarter turn."""
    return (height, width) if rotate in (90, 270) else (width, height)


def parse_ratio(ratio: str) -> float:
    """'4:5' → 0.8 (width ÷ height)."""
    width, height = (float(part) for part in ratio.split(":"))
    if width <= 0 or height <= 0:
        raise InvalidRequestError(f"aspect ratio '{ratio}' must have two positive numbers")
    return width / height


def _rotation(angle: float) -> Matrix:
    """Clockwise on screen (y down) by ``angle`` degrees."""
    a = math.radians(angle)
    return np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])


def fit_scale(rect: Rect, angle: float, width: float, height: float) -> float:
    """The largest k such that ``rect`` scaled by k around its center lies inside the straightened image.

    0 when the center itself is outside. Every corner, turned back by the angle, must land inside the frame;
    each of those conditions is linear in k.
    """
    back = _rotation(-angle)
    u = back @ np.array([rect.cx - width / 2, rect.cy - height / 2])
    limits = (width / 2, height / 2)
    if abs(u[0]) > limits[0] + _TOLERANCE * width or abs(u[1]) > limits[1] + _TOLERANCE * height:
        return 0.0
    k = math.inf
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        v = back @ np.array([sx * rect.hw, sy * rect.hh])
        for axis in (0, 1):
            if v[axis] > 0:
                k = min(k, (limits[axis] - u[axis]) / v[axis])
            elif v[axis] < 0:
                k = min(k, (limits[axis] + u[axis]) / -v[axis])
    return max(0.0, float(k))


def crop_inside(crop: CropRect, angle: float, width: float, height: float) -> bool:
    """True when ``crop`` lies inside the image straightened by ``angle`` in a width × height frame."""
    return fit_scale(Rect.from_crop(crop, width, height), angle, width, height) >= 1 - _TOLERANCE


def largest_crop(ratio: float | None, angle: float, width: float, height: float) -> CropRect:
    """The largest crop of ``ratio`` (width ÷ height; None = the frame's), centered, inside the image."""
    rect = _largest_rect(ratio, width / 2, height / 2, width, height)
    k = fit_scale(rect, angle, width, height)
    return _scaled(rect, min(1.0, k) * _SAFETY).to_crop(width, height)


def _largest_rect(ratio: float | None, cx: float, cy: float, width: float, height: float) -> Rect:
    """The largest axis-aligned rect of ``ratio`` in the frame (ignoring the angle), centered at cx, cy."""
    if ratio is None:
        ratio = width / height
    if width / height > ratio:
        return Rect(cx, cy, height * ratio / 2, height / 2)
    return Rect(cx, cy, width / 2, width / ratio / 2)


def _scaled(rect: Rect, k: float) -> Rect:
    return Rect(rect.cx, rect.cy, rect.hw * k, rect.hh * k)


def constrain_crop(
    crop: CropRect, angle: float, width: float, height: float, *, ratio: float | None = None
) -> CropRect:
    """``crop`` made valid for ``angle``: shrunk around its center until it fits the straightened image.

    With ``ratio`` (a locked aspect) that the crop doesn't have yet, the crop first becomes the largest one of
    that ratio around the same center. If the center is outside the straightened image, or so close to its
    edge that the crop would become tiny, the center moves toward the frame's center just far enough.
    """
    rect = Rect.from_crop(crop, width, height)
    if ratio is not None and not ratio_matches(crop, ratio, width, height):
        rect = _largest_rect(ratio, rect.cx, rect.cy, width, height)
    k_min = min(1.0, max(_MIN_CROP * width / (2 * rect.hw), _MIN_CROP * height / (2 * rect.hh)))
    if fit_scale(rect, angle, width, height) < k_min:
        rect = _move_toward_center(rect, angle, width, height, k_min)
    k = fit_scale(rect, angle, width, height)
    if k >= 1:
        unchanged = ratio is None or ratio_matches(crop, ratio, width, height)
        return crop if unchanged else rect.to_crop(width, height)
    return _scaled(rect, k * _SAFETY).to_crop(width, height)


def _move_toward_center(rect: Rect, angle: float, width: float, height: float, k_min: float) -> Rect:
    """The point on the way to the frame's center closest to ``rect``'s center where k ≥ ``k_min``.

    The fit scale along that line is a minimum of linear functions (concave), so bisection finds it.
    """

    def at(s: float) -> Rect:
        return Rect(
            rect.cx + s * (width / 2 - rect.cx), rect.cy + s * (height / 2 - rect.cy), rect.hw, rect.hh
        )

    if fit_scale(at(1.0), angle, width, height) < k_min:
        return at(1.0)
    low, high = 0.0, 1.0
    for _ in range(60):
        middle = (low + high) / 2
        if fit_scale(at(middle), angle, width, height) >= k_min:
            high = middle
        else:
            low = middle
    return at(high)


def ratio_matches(crop: CropRect, ratio: float, width: float, height: float) -> bool:
    """True when the crop's width ÷ height is ``ratio`` within one pixel (of ``width`` × ``height``)."""
    crop_w = (crop.right - crop.left) * width
    crop_h = (crop.bottom - crop.top) * height
    return abs(crop_w - ratio * crop_h) <= max(1.0, 1e-6 * crop_w)


def edited_size(width: int, height: int, geometry: Geometry) -> tuple[int, int]:
    """The photo's size in full-size pixels after the geometry (``width`` × ``height`` = upright original)."""
    frame_w, frame_h = turned_size(width, height, geometry.rotate)
    crop = geometry.crop
    return (
        max(1, math.floor((crop.right - crop.left) * frame_w + 0.5)),
        max(1, math.floor((crop.bottom - crop.top) * frame_h + 0.5)),
    )


def check_geometry(geometry: Geometry, width: int, height: int) -> None:
    """Raise ``InvalidRequestError`` if the geometry can't be rendered for a ``width`` × ``height`` photo."""
    frame_w, frame_h = turned_size(width, height, geometry.rotate)
    if not crop_inside(geometry.crop, geometry.angle, frame_w, frame_h):
        raise InvalidRequestError(
            f"the crop reaches outside the photo straightened by {geometry.angle:g}° (it would show blank "
            "corners); make it smaller or move it inward"
        )
    if geometry.aspect is not None and not ratio_matches(
        geometry.crop, parse_ratio(geometry.aspect), frame_w, frame_h
    ):
        crop_w, crop_h = edited_size(width, height, geometry)
        raise InvalidRequestError(
            f"the crop is {crop_w}×{crop_h} px, which isn't the locked aspect ratio {geometry.aspect}"
        )


def _turn_crop(crop: CropRect, turn: int) -> CropRect:
    """The crop carried along by a clockwise quarter turn of the frame (normalized (x, y) → (1 - y, x))."""
    left, top, right, bottom = crop.left, crop.top, crop.right, crop.bottom
    for _ in range(turn // 90 % 4):
        left, top, right, bottom = 1 - bottom, left, 1 - top, right
    return CropRect(left=left, top=top, right=right, bottom=bottom)


def _swap_ratio(aspect: str | None) -> str | None:
    if aspect is None:
        return None
    width, height = aspect.split(":")
    return f"{height}:{width}"


def apply_change(geometry: Geometry, change: GeometryChange, width: int, height: int) -> Geometry:
    """``geometry`` with ``change`` applied (see ``GeometryChange``), checked for a width × height photo."""
    given = change.model_fields_set
    result = Geometry() if change.reset else geometry
    for name in ("flip_horizontal", "flip_vertical"):
        wanted = getattr(change, name)
        if name in given and wanted is not None and wanted != getattr(result, name):
            # A flip happens before the quarter turn: an upright left-right mirror is a top-bottom mirror of
            # the frame after a 90° or 270° turn. Mirroring the image also mirrors its tilt.
            frame_x = (name == "flip_horizontal") == (result.rotate in (0, 180))
            crop = result.crop
            mirrored = (
                CropRect(left=1 - crop.right, top=crop.top, right=1 - crop.left, bottom=crop.bottom)
                if frame_x
                else CropRect(left=crop.left, top=1 - crop.bottom, right=crop.right, bottom=1 - crop.top)
            )
            result = result.model_copy(update={name: wanted, "crop": mirrored, "angle": -result.angle or 0.0})
    if "rotate" in given and change.rotate is not None and change.rotate != result.rotate:
        turn = (change.rotate - result.rotate) % 360
        result = result.model_copy(
            update={
                "rotate": change.rotate,
                "crop": _turn_crop(result.crop, turn),
                "aspect": _swap_ratio(result.aspect) if turn in (90, 270) else result.aspect,
            }
        )
    frame_w, frame_h = turned_size(width, height, result.rotate)
    refit = False
    if "angle" in given and change.angle is not None:
        result = result.model_copy(update={"angle": change.angle})
        refit = True
    if "aspect" in given:
        result = result.model_copy(update={"aspect": change.aspect})
        refit = refit or change.aspect is not None
    if refit:
        ratio = parse_ratio(result.aspect) if result.aspect is not None else None
        crop = constrain_crop(result.crop, result.angle, frame_w, frame_h, ratio=ratio)
        result = result.model_copy(update={"crop": crop})
    if "crop" in given and change.crop is not None:
        result = result.model_copy(update={"crop": change.crop})
    check_geometry(result, width, height)
    return Geometry.model_validate(result.model_dump())


def sub_crop(crop: CropRect, left: float, top: float, right: float, bottom: float) -> CropRect:
    """The part of ``crop`` given in fractions of it (0..1 each), as a crop of the frame."""
    w, h = crop.right - crop.left, crop.bottom - crop.top
    return CropRect(
        left=crop.left + left * w,
        top=crop.top + top * h,
        right=crop.left + right * w,
        bottom=crop.top + bottom * h,
    )


def source_map(
    geometry: Geometry, crop: CropRect, source_w: int, source_h: int, out_w: int, out_h: int
) -> Matrix:
    """3×3 affine map from output pixel coordinates to source pixel coordinates.

    ``source_w`` × ``source_h`` is the upright source (any decode size); the output shows ``crop`` (normalized
    to the frame) at ``out_w`` × ``out_h``. Pixel (i, j) has its center at (i, j), as OpenCV's warps expect.
    """
    frame_w, frame_h = turned_size(source_w, source_h, geometry.rotate)
    crop_w = (crop.right - crop.left) * frame_w
    crop_h = (crop.bottom - crop.top) * frame_h
    # Output pixel centers → frame coordinates (pixel edges at integers).
    to_frame = np.array(
        [
            [crop_w / out_w, 0, crop.left * frame_w + 0.5 * crop_w / out_w],
            [0, crop_h / out_h, crop.top * frame_h + 0.5 * crop_h / out_h],
            [0, 0, 1],
        ]
    )
    # Undo the straightening: turn back around the frame's center.
    back = np.eye(3)
    back[:2, :2] = _rotation(-geometry.angle)
    center = np.array([[1, 0, frame_w / 2], [0, 1, frame_h / 2], [0, 0, 1]])
    uncenter = np.array([[1, 0, -frame_w / 2], [0, 1, -frame_h / 2], [0, 0, 1]])
    unstraighten = center @ back @ uncenter
    # Undo the quarter turn: frame (x, y) → flipped upright (X, Y).
    unturn = {
        0: np.eye(3),
        90: np.array([[0, 1, 0], [-1, 0, source_h], [0, 0, 1]]),
        180: np.array([[-1, 0, source_w], [0, -1, source_h], [0, 0, 1]]),
        270: np.array([[0, -1, source_w], [1, 0, 0], [0, 0, 1]]),
    }[geometry.rotate]
    unflip = np.diag(
        [-1.0 if geometry.flip_horizontal else 1.0, -1.0 if geometry.flip_vertical else 1.0, 1.0]
    )
    unflip[0, 2] = source_w if geometry.flip_horizontal else 0
    unflip[1, 2] = source_h if geometry.flip_vertical else 0
    # Pixel edges → pixel centers.
    to_pixels = np.array([[1, 0, -0.5], [0, 1, -0.5], [0, 0, 1]])
    out: Matrix = to_pixels @ unflip @ unturn @ unstraighten @ to_frame
    return out


def upright_to_frame(geometry: Geometry, width: float, height: float) -> Matrix:
    """3×3 affine map from upright normalized coordinates (0..1) to frame pixel coordinates.

    ``width`` × ``height`` is the upright photo (any size). The inverse of ``source_map``'s chain, without
    the crop: flips, then the quarter turn, then the straighten rotation around the frame's center.
    """
    flip = np.diag([-1.0 if geometry.flip_horizontal else 1.0, -1.0 if geometry.flip_vertical else 1.0, 1.0])
    flip[0, 2] = width if geometry.flip_horizontal else 0
    flip[1, 2] = height if geometry.flip_vertical else 0
    turn = {
        0: np.eye(3),
        90: np.array([[0, -1, height], [1, 0, 0], [0, 0, 1]]),
        180: np.array([[-1, 0, width], [0, -1, height], [0, 0, 1]]),
        270: np.array([[0, 1, 0], [-1, 0, width], [0, 0, 1]]),
    }[geometry.rotate]
    frame_w, frame_h = turned_size(width, height, geometry.rotate)
    straighten = np.eye(3)
    straighten[:2, :2] = _rotation(geometry.angle)
    center = np.array([[1, 0, frame_w / 2], [0, 1, frame_h / 2], [0, 0, 1]])
    uncenter = np.array([[1, 0, -frame_w / 2], [0, 1, -frame_h / 2], [0, 0, 1]])
    scale = np.diag([width, height, 1.0])
    out: Matrix = center @ straighten @ uncenter @ turn @ flip @ scale
    return out


def subject_in_frame(box: SubjectBox, geometry: Geometry, width: float, height: float) -> SubjectBox | None:
    """``box`` (upright, normalized) as a box normalized to the frame of ``geometry``.

    Exact for flips and quarter turns. When straightened, it is the bounding box of the box's turned corners,
    cut to the frame. None when (almost) nothing of it is left inside the frame.
    """
    frame_w, frame_h = turned_size(width, height, geometry.rotate)
    corners = np.array(
        [[box.left, box.right, box.right, box.left], [box.top, box.top, box.bottom, box.bottom], [1, 1, 1, 1]]
    )
    mapped = upright_to_frame(geometry, width, height) @ corners
    left = max(0.0, float(mapped[0].min()) / frame_w)
    right = min(1.0, float(mapped[0].max()) / frame_w)
    top = max(0.0, float(mapped[1].min()) / frame_h)
    bottom = min(1.0, float(mapped[1].max()) / frame_h)
    if right - left < MIN_BOX_SIZE or bottom - top < MIN_BOX_SIZE:
        return None
    return SubjectBox(left=left, top=top, right=right, bottom=bottom)
