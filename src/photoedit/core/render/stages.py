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
from photoedit.core.render.curves import pchip
from photoedit.core.render.profile import CameraProfile
from photoedit.models.adjustments import Tone, ToneCurve, WhiteBalance

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


# ----------------------------------------------------------------- tone (exposure-relative luminance curve)

MID_GRAY = 0.18
# The luminance curve lives on a grid of stops relative to mid gray; 0 is on the grid exactly, so mid gray
# maps
# to itself bit-exactly.
_STOPS_MIN, _STOPS_MAX, _STEPS_PER_STOP = -24, 12, 64
TONE_GRID = np.arange(_STOPS_MIN * _STEPS_PER_STOP, _STOPS_MAX * _STEPS_PER_STOP + 1) / _STEPS_PER_STOP
_ZERO_INDEX = -_STOPS_MIN * _STEPS_PER_STOP

# (center in stops, half width in stops, strength in stops of slope change at ±100, sign of a positive
# slider).
# A positive "shadows"/"blacks" lifts dark areas by flattening the curve below mid gray; a positive
# "highlights"/"whites" brightens by steepening it above mid gray.
_TONE_BANDS = {
    "blacks": (-6.5, 2.5, 1.0, -1),
    "shadows": (-2.5, 2.5, 1.0, -1),
    "highlights": (1.5, 1.5, 1.2, +1),
    "whites": (3.5, 1.5, 1.0, +1),
}
_CONTRAST_STRENGTH = 0.6  # contrast ±100 → overall slope ×2^±0.6 (≈ ×1.52 / ×0.66) around mid gray


def tone_curve_stops(tone: Tone) -> npt.NDArray[np.float64]:
    """Output stops for every input stop on ``TONE_GRID``.

    The curve is defined by its slope: each slider multiplies the local slope by a strictly positive factor,
    and the slope is integrated outward from mid gray. So the curve is monotone for any slider values and mid
    gray stays exactly where it is.
    """
    log_slope = np.full(TONE_GRID.shape, _CONTRAST_STRENGTH * tone.contrast / 100)
    for name, (center, half_width, strength, sign) in _TONE_BANDS.items():
        value: float = getattr(tone, name)
        if value:
            distance = np.clip(np.abs(TONE_GRID - center) / half_width, 0, 1)
            bump = 0.5 + 0.5 * np.cos(np.pi * distance)  # 1 at the center, 0 beyond ±half_width
            log_slope += sign * strength * value / 100 * bump
    slope = np.exp2(log_slope)
    steps = (slope[1:] + slope[:-1]) / 2 / _STEPS_PER_STOP  # trapezoid rule
    out = np.zeros_like(TONE_GRID)
    out[_ZERO_INDEX + 1 :] = np.cumsum(steps[_ZERO_INDEX:])
    out[:_ZERO_INDEX] = -np.cumsum(steps[:_ZERO_INDEX][::-1])[::-1]
    return out


def tone(rgb: F32, params: Tone) -> F32:
    """Contrast, highlights, shadows, whites and blacks as one luminance curve (colors keep their ratios)."""
    if not (params.contrast or params.highlights or params.shadows or params.whites or params.blacks):
        return rgb
    curve = tone_curve_stops(params)
    stops = np.log2(np.maximum(luminance(rgb), _EPSILON) / np.float32(MID_GRAY))
    new_stops = np.interp(stops, TONE_GRID, curve)
    gain = np.exp2(new_stops - stops).astype(np.float32)
    out: F32 = rgb * gain[..., None]
    return out


# ----------------------------------------------------------------- curves

_CURVE_GRID = np.linspace(0, 1, 4097)
# Parametric regions move fixed control points by up to ±0.1. The points are 0.25 apart, so the curve through
# them always rises: it can flatten a region but never fold back.
_REGION_POINTS = {"shadows": 0.125, "darks": 0.375, "lights": 0.625, "highlights": 0.875}
_REGION_STRENGTH = 0.1


def base_curve_lut(profile: CameraProfile) -> npt.NDArray[np.float64]:
    """The profile's tone curve sampled on ``TONE_GRID`` (stops → display value)."""
    stops = [p.stops for p in profile.tone_curve]
    values = [p.value for p in profile.tone_curve]
    return pchip(stops, values, TONE_GRID)


def base_curve(rgb: F32, profile: CameraProfile) -> F32:
    """Scene-linear → display-encoded, per channel, through the profile's tone curve.

    Per channel (like film and most cameras), so very bright saturated colors drift toward white instead of
    clipping into a flat patch.
    """
    lut = base_curve_lut(profile)
    stops = np.log2(np.maximum(rgb, _EPSILON) / np.float32(MID_GRAY))
    return np.interp(stops, TONE_GRID, lut).astype(np.float32)


def curve_luts(params: ToneCurve) -> list[npt.NDArray[np.float64]] | None:
    """Per-channel lookup tables on ``_CURVE_GRID`` for the parametric + point curves; None if all neutral."""
    neutral = ToneCurve()
    if params == neutral:
        return None
    region_y = [x + _REGION_STRENGTH * getattr(params, name) / 100 for name, x in _REGION_POINTS.items()]
    parametric = pchip([0, *_REGION_POINTS.values(), 1], [0, *region_y, 1], _CURVE_GRID)
    rgb = pchip([p.x for p in params.rgb], [p.y for p in params.rgb], parametric)
    return [
        pchip([p.x for p in points], [p.y for p in points], rgb)
        for points in (params.red, params.green, params.blue)
    ]


def curves(encoded: F32, params: ToneCurve) -> F32:
    """Parametric regions, then the RGB point curve, then the R/G/B point curves (display-encoded values)."""
    luts = curve_luts(params)
    if luts is None:
        return encoded
    out = np.empty_like(encoded)
    for channel, lut in enumerate(luts):
        out[..., channel] = np.interp(encoded[..., channel], _CURVE_GRID, lut)
    return out
