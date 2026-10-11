"""Applying a photo's geometry to linear pixels: flips, quarter turn, straighten, crop, then the output size.

Only the pixels the crop keeps are produced. Without a straighten angle everything is exact array slicing
(flips and quarter turns permute pixels); with one, a single cubic ``warpAffine`` in linear light maps the
crop from the source at its own resolution, and the result is resized like any other image.
"""

from __future__ import annotations

import dataclasses
import math

import cv2
import numpy as np

from photoedit.core.decode import LinearImage
from photoedit.core.geometry import source_map, turned_size
from photoedit.models.adjustments import CropRect, Geometry

# Source pixels kept around the mapped crop, so the cubic kernel never reaches past the slice.
_WARP_MARGIN = 3


def _round(value: float) -> int:
    return math.floor(value + 0.5)


def crop_size(geometry: Geometry, crop: CropRect, width: int, height: int) -> tuple[float, float]:
    """The crop's exact size in pixels of a ``width`` × ``height`` upright source."""
    frame_w, frame_h = turned_size(width, height, geometry.rotate)
    return (crop.right - crop.left) * frame_w, (crop.bottom - crop.top) * frame_h


def output_size(
    geometry: Geometry, crop: CropRect, width: int, height: int, long_edge: int | None
) -> tuple[int, int]:
    """The crop's size in source pixels, scaled down so its long edge is at most ``long_edge`` (never up)."""
    crop_w, crop_h = crop_size(geometry, crop, width, height)
    scale = 1.0 if long_edge is None else min(1.0, long_edge / max(crop_w, crop_h))
    return max(1, _round(crop_w * scale)), max(1, _round(crop_h * scale))


def apply_geometry(
    image: LinearImage,
    geometry: Geometry,
    *,
    crop: CropRect | None = None,
    size: tuple[int, int] | None = None,
    long_edge: int | None = None,
    blank_outside: bool = False,
) -> LinearImage:
    """``image`` (upright) with ``geometry`` applied, showing ``crop`` (default: the geometry's own).

    The result is ``size`` (width, height) if given, else the crop at the source's resolution, scaled down to
    ``long_edge`` if that is smaller. ``blank_outside`` makes the parts of the crop outside the straightened
    image black (the crop tool's whole-frame view); a valid crop has none.
    """
    crop = crop or geometry.crop
    height, width = image.pixels.shape[:2]
    if size is None:
        size = output_size(geometry, crop, width, height, long_edge)
    if geometry.angle == 0:
        pixels = _axis_aligned(image.pixels, geometry, crop)
    else:
        pixels = _straightened(image.pixels, geometry, crop, blank_outside=blank_outside)
    return dataclasses.replace(image, pixels=resize_to(pixels, *size))


def _axis_aligned(pixels: np.ndarray, geometry: Geometry, crop: CropRect) -> np.ndarray:
    """Flips, quarter turn and crop as views (no interpolation); only the crop is copied."""
    view = pixels
    if geometry.flip_horizontal:
        view = view[:, ::-1]
    if geometry.flip_vertical:
        view = view[::-1]
    view = np.rot90(view, k=-(geometry.rotate // 90))  # negative k = clockwise
    frame_h, frame_w = view.shape[:2]
    x0, x1 = _round(crop.left * frame_w), _round(crop.right * frame_w)
    y0, y1 = _round(crop.top * frame_h), _round(crop.bottom * frame_h)
    x1, y1 = max(x1, x0 + 1), max(y1, y0 + 1)
    return np.ascontiguousarray(view[y0:y1, x0:x1], dtype=np.float32)


def _straightened(
    pixels: np.ndarray, geometry: Geometry, crop: CropRect, *, blank_outside: bool = False
) -> np.ndarray:
    """One cubic warp from the source slice the crop needs to the crop at the source's resolution."""
    height, width = pixels.shape[:2]
    crop_w, crop_h = crop_size(geometry, crop, width, height)
    out_w, out_h = max(1, _round(crop_w)), max(1, _round(crop_h))
    matrix = source_map(geometry, crop, width, height, out_w, out_h)
    corners = np.array(
        [[-0.5, -0.5, 1], [out_w - 0.5, -0.5, 1], [out_w - 0.5, out_h - 0.5, 1], [-0.5, out_h - 0.5, 1]]
    )
    mapped = corners @ matrix.T
    x0 = max(0, math.floor(mapped[:, 0].min()) - _WARP_MARGIN)
    y0 = max(0, math.floor(mapped[:, 1].min()) - _WARP_MARGIN)
    x1 = min(width, math.ceil(mapped[:, 0].max()) + _WARP_MARGIN + 1)
    y1 = min(height, math.ceil(mapped[:, 1].max()) + _WARP_MARGIN + 1)
    shift = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1]], dtype=np.float64)
    local = (shift @ matrix)[:2]
    region = np.ascontiguousarray(pixels[y0:y1, x0:x1], dtype=np.float32)
    warped = cv2.warpAffine(
        region,
        local,
        (out_w, out_h),
        flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP,
        # Inside the image the cubic kernel may reach a pixel past its edge: repeat the edge there.
        borderMode=cv2.BORDER_CONSTANT if blank_outside else cv2.BORDER_REPLICATE,
    )
    # Cubic interpolation overshoots below black at hard edges.
    return np.maximum(warped, 0)


def resize_to(pixels: np.ndarray, width: int, height: int) -> np.ndarray:
    """Scale linear pixels to exactly ``width`` × ``height``: area averaging down, bicubic up."""
    if pixels.shape[1] == width and pixels.shape[0] == height:
        return np.ascontiguousarray(pixels, dtype=np.float32)
    shrinking = pixels.shape[1] >= width and pixels.shape[0] >= height
    resized = cv2.resize(
        pixels, (width, height), interpolation=cv2.INTER_AREA if shrinking else cv2.INTER_CUBIC
    )
    if not shrinking:
        resized = np.maximum(resized, 0)  # bicubic overshoots below black at hard edges
    return np.ascontiguousarray(resized, dtype=np.float32)
