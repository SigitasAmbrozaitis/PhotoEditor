"""Render stages. Each is a pure function on float32 ``(H, W, 3)`` arrays and the identity at its neutral
value.

Domains: stages up to the base curve work on scene-linear Rec.2020; the base curve outputs display-encoded
values (sRGB transfer curve, Rec.2020 primaries), which the curve stage edits; color stages convert to
OKLab and back; the output stage converts to the target RGB space and encodes it.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from photoedit.core import color
from photoedit.core.decode import LinearImage
from photoedit.models.adjustments import WhiteBalance

type F32 = npt.NDArray[np.float32]

_EPSILON = np.float32(1e-6)


def luminance(rgb: F32) -> F32:
    """Relative luminance (Y) of linear Rec.2020 pixels."""
    w = color.REC2020_LUMA.astype(np.float32)
    out: F32 = rgb[..., 0] * w[0] + rgb[..., 1] * w[1] + rgb[..., 2] * w[2]
    return out


# ----------------------------------------------------------------- white balance


def white_balance(image: LinearImage, wb: WhiteBalance) -> F32:
    """Apply the white balance and convert to linear Rec.2020.

    ``None`` means "as shot" for that component. RAWs are rebalanced in camera space (new ÷ as-shot
    multipliers, then the camera matrix); JPEG/TIFF originals, which are already balanced for D65, get a
    Bradford adaptation.
    """
    as_shot_temperature, as_shot_tint = image.as_shot
    temperature = wb.temperature if wb.temperature is not None else as_shot_temperature
    tint = wb.tint if wb.tint is not None else as_shot_tint
    unchanged = wb.temperature is None and wb.tint is None
    if image.is_raw:
        matrix = image.to_rec2020
        if not unchanged and image.cam_from_xyz is not None and image.as_shot_multipliers is not None:
            gains = (
                color.camera_multipliers(image.cam_from_xyz, temperature, tint) / image.as_shot_multipliers
            )
            matrix = matrix @ np.diag(gains)
        return color.apply_matrix(image.pixels, matrix)
    if unchanged:
        return image.pixels
    # "The light was this white": adapt from it to D65, the white the JPEG was already balanced for.
    adapt = color.bradford(color.temperature_tint_to_xy(temperature, tint), color.D65)
    matrix = color.REC2020_FROM_XYZ @ adapt @ color.XYZ_FROM_REC2020
    return color.apply_matrix(image.pixels, matrix)


# ----------------------------------------------------------------- exposure


def exposure(rgb: F32, ev: float) -> F32:
    """Scale linear light by 2^ev (+1 EV doubles every value)."""
    if ev == 0:
        return rgb
    return rgb * np.float32(2.0**ev)


# ----------------------------------------------------------------- output


def to_display_linear(encoded: F32) -> F32:
    """Display-encoded (sRGB transfer curve) → display-linear, same primaries."""
    return color.srgb_decode(np.clip(encoded, 0, 1))


def output_srgb(display_linear: F32) -> F32:
    """Display-linear Rec.2020 → sRGB-encoded 0..1.

    Colors outside sRGB are pulled toward their own luminance until they fit (instead of clipping each
    channel, which shifts hues), then values above 1 are clipped.
    """
    srgb = color.apply_matrix(display_linear, color.SRGB_FROM_REC2020)
    srgb = desaturate_into_gamut(srgb, color.XYZ_FROM_SRGB[1])
    return color.srgb_encode(np.clip(srgb, 0, 1))


def desaturate_into_gamut(rgb: F32, luma_weights: npt.NDArray[np.float64]) -> F32:
    """Move pixels with a negative channel toward gray (same luminance) just far enough to remove it."""
    w = luma_weights.astype(np.float32)
    y = np.maximum(rgb[..., 0] * w[0] + rgb[..., 1] * w[1] + rgb[..., 2] * w[2], 0)[..., None]
    low = rgb.min(axis=-1, keepdims=True)
    # Fraction of the distance to gray that stays; in-gamut pixels are passed through bit-exactly.
    keep = y / np.maximum(y - low, _EPSILON)
    out: F32 = np.where(low < 0, y + (rgb - y) * keep, rgb).astype(np.float32, copy=False)
    return out


def quantize(encoded: F32, bits: int = 8) -> npt.NDArray[np.uint8] | npt.NDArray[np.uint16]:
    """Encoded 0..1 → integers, rounding to nearest."""
    top = (1 << bits) - 1
    scaled = np.clip(encoded, 0, 1) * np.float32(top) + np.float32(0.5)
    if bits == 8:
        return scaled.astype(np.uint8)
    return scaled.astype(np.uint16)
