"""Render stages. Each is a pure function on float32 ``(H, W, 3)`` arrays and the identity at its neutral
value.

Domains: stages up to the base curve work on scene-linear Rec.2020; the base curve outputs display-encoded
values (sRGB transfer curve, Rec.2020 primaries), which the curve stage edits; color stages convert to
OKLab and back; the output stage converts to the target RGB space and encodes it.
"""

from __future__ import annotations

import cv2
import numpy as np
import numpy.typing as npt

from photoedit.core import color
from photoedit.core.decode import LinearImage
from photoedit.core.render.curves import pchip
from photoedit.core.render.profile import CameraProfile
from photoedit.models.adjustments import (
    ColorGrading,
    Hsl,
    Presence,
    Sharpening,
    Tone,
    ToneCurve,
    Vignette,
    WhiteBalance,
)

type F32 = npt.NDArray[np.float32]

_EPSILON = np.float32(1e-6)


def luminance(rgb: F32) -> F32:
    """Relative luminance (Y) of linear Rec.2020 pixels."""
    w = color.REC2020_LUMA.astype(np.float32)
    out: F32 = rgb[..., 0] * w[0] + rgb[..., 1] * w[1] + rgb[..., 2] * w[2]
    return out


# ----------------------------------------------------------------- white balance


def white_balance_matrix(image: LinearImage, wb: WhiteBalance) -> npt.NDArray[np.float64]:
    """The 3×3 matrix taking ``image.pixels`` to white-balanced linear Rec.2020.

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
        return matrix
    if unchanged:
        return np.eye(3)
    # "The light was this white": adapt from it to D65, the white the JPEG was already balanced for.
    adapt = color.bradford(color.temperature_tint_to_xy(temperature, tint), color.D65)
    out: npt.NDArray[np.float64] = color.REC2020_FROM_XYZ @ adapt @ color.XYZ_FROM_REC2020
    return out


def white_balance(image: LinearImage, wb: WhiteBalance) -> F32:
    """Apply the white balance and convert to linear Rec.2020 (see ``white_balance_matrix``)."""
    matrix = white_balance_matrix(image, wb)
    if not image.is_raw and np.array_equal(matrix, np.eye(3)):
        return image.pixels
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


def uniform_lookup(values: F32, start: float, step: float, table: npt.NDArray[np.float64]) -> F32:
    """Linear interpolation in ``table`` sampled every ``step`` from ``start`` (clamped at both ends).

    The same result as ``np.interp`` on a uniform grid, but O(1) per value instead of a binary search, which
    matters at millions of pixels per render.
    """
    position = np.clip((values - np.float32(start)) / np.float32(step), 0, table.size - 1)
    index = np.minimum(position.astype(np.int32), table.size - 2)
    fraction = position - index.astype(np.float32)  # int32 - float32 would promote to float64
    lut = table.astype(np.float32)
    out: F32 = lut[index] * (1 - fraction) + lut[index + 1] * fraction
    return out


# ----------------------------------------------------------------- tone (luminance curve in stops)

MID_GRAY = 0.18
# The luminance curve lives on a grid of stops relative to mid gray.
_STOPS_MIN, _STOPS_MAX, _STEPS_PER_STOP = -24, 12, 64
TONE_GRID = np.arange(_STOPS_MIN * _STEPS_PER_STOP, _STOPS_MAX * _STEPS_PER_STOP + 1) / _STEPS_PER_STOP

# The tone sliders act on the photo's own tonal range (decided 2026-10-09), between its black and white points
# (``core.render.anchors``), not at fixed scene stops: most photos never reach mid gray +2, and their median
# pixel sits 3-5 stops below mid gray. The middle of the range is the pivot: it stays put, highlights/whites
# only move pixels above it, shadows/blacks only below, and contrast spreads tones away from it.
_MIN_TONE_RANGE = 4.0  # stops; a flatter photo gets bands as wide as if it spanned this much
# How far each slider at +100 moves the far end of its band (the white point for highlights/whites, the black
# point for shadows/blacks), in stops; positive = brighter. -100 moves it as far the other way.
TONE_SHIFTS = {"blacks": 2.5, "shadows": 2.0, "highlights": 1.0, "whites": 1.0}
_MAX_LOG_SLOPE = 3.0  # local slope stays within ×1/8…×8, so narrow bands can't posterize
_CONTRAST_STRENGTH = 0.6  # contrast ±100 → overall slope ×2^±0.6 (≈ ×1.52 / ×0.66) around the pivot


def tone_bands(black: float, white: float) -> tuple[float, dict[str, tuple[float, float]]]:
    """The pivot (middle of the range) and each slider's band as (center, half width), all in stops.

    Each band is a quarter of the range wide on either side of its center; none crosses the pivot.
    """
    middle = (black + white) / 2
    quarter = max(white - black, _MIN_TONE_RANGE) / 4
    low, high = middle - 2 * quarter, middle + 2 * quarter
    return middle, {
        "blacks": (low + quarter / 2, quarter),
        "shadows": (middle - quarter, quarter),
        "highlights": (middle + quarter, quarter),
        "whites": (high - quarter / 2, quarter),
    }


def _bump(center: float, half_width: float) -> npt.NDArray[np.float64]:
    distance = np.clip(np.abs(TONE_GRID - center) / half_width, 0, 1)
    out: npt.NDArray[np.float64] = 0.5 + 0.5 * np.cos(np.pi * distance)  # 1 at the center, 0 beyond
    return out


def _band_amplitude(bump: npt.NDArray[np.float64], shift: float) -> float:
    """The log2 slope change at the band's center that moves everything past the band by ``shift`` stops.

    Found by bisection (the shift grows strictly with the amplitude), so the curve is exact and reproducible.
    """

    def moved(amplitude: float) -> float:
        return float(np.sum(np.exp2(amplitude * bump) - 1)) / _STEPS_PER_STOP

    low, high = -_MAX_LOG_SLOPE, _MAX_LOG_SLOPE
    if shift <= moved(low):
        return low
    if shift >= moved(high):
        return high
    for _ in range(48):
        middle = (low + high) / 2
        low, high = (middle, high) if moved(middle) < shift else (low, middle)
    return (low + high) / 2


def tone_curve_stops(tone: Tone, black: float, white: float) -> npt.NDArray[np.float64]:
    """Output stops for every input stop on ``TONE_GRID``; ``black``/``white`` are the photo's black and white
    points after exposure.

    The band sliders shape the curve through its slope: each multiplies the local slope by a strictly positive
    factor, and the slope is integrated outward from the pivot, which stays where it is. Contrast then scales
    the result around the pivot. So the curve is monotone for any slider values.
    """
    curve = TONE_GRID.copy()
    pivot, bands = tone_bands(black, white)
    if tone.highlights or tone.shadows or tone.whites or tone.blacks:
        log_slope = np.zeros_like(TONE_GRID)
        for name, (center, half_width) in bands.items():
            value: float = getattr(tone, name)
            if value:
                bump = _bump(center, half_width)
                shift = TONE_SHIFTS[name] * value / 100
                # Below the pivot the slope is integrated downward: a flatter slope there lifts the darks.
                log_slope += _band_amplitude(bump, shift if center > pivot else -shift) * bump
        slope = np.exp2(log_slope)
        integral = np.zeros_like(TONE_GRID)
        integral[1:] = np.cumsum((slope[1:] + slope[:-1]) / 2) / _STEPS_PER_STOP  # trapezoid rule
        curve = integral - np.interp(pivot, TONE_GRID, integral) + pivot
    if tone.contrast:
        curve = pivot + (curve - pivot) * 2.0 ** (_CONTRAST_STRENGTH * tone.contrast / 100)
    return curve


def tone(rgb: F32, params: Tone, black: float, white: float) -> F32:
    """Contrast, highlights, shadows, whites and blacks as one luminance curve (colors keep their ratios).

    ``black``/``white`` are the photo's black and white points in stops after exposure (see ``tone_bands``).
    """
    if not (params.contrast or params.highlights or params.shadows or params.whites or params.blacks):
        return rgb
    return apply_tone_curve(rgb, tone_curve_stops(params, black, white))


def apply_tone_curve(rgb: F32, curve: npt.NDArray[np.float64]) -> F32:
    """Scale each pixel so its luminance follows ``curve`` (from ``tone_curve_stops``)."""
    stops = np.log2(np.maximum(luminance(rgb), _EPSILON) / np.float32(MID_GRAY))
    new_stops = uniform_lookup(stops, _STOPS_MIN, 1 / _STEPS_PER_STOP, curve)
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
    return uniform_lookup(stops, _STOPS_MIN, 1 / _STEPS_PER_STOP, lut)


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
        out[..., channel] = uniform_lookup(encoded[..., channel], 0.0, 1 / (_CURVE_GRID.size - 1), lut)
    return out


# ----------------------------------------------------------------- color (OKLab/OKLCh)


def _oklch_hue_of_srgb(rgb: tuple[float, float, float]) -> float:
    linear = color.apply_matrix(color.srgb_decode(np.array(rgb, dtype=np.float64)), color.REC2020_FROM_SRGB)
    lab = color.rec2020_to_oklab(linear)
    return float(np.degrees(np.arctan2(lab[2], lab[1])) % 360)


# HSL band centers: the OKLCh hue of each named color in sRGB, so "red" means the hue of pure red.
_BANDS: dict[str, tuple[float, float, float]] = {
    "red": (1, 0, 0),
    "orange": (1, 0.5, 0),
    "yellow": (1, 1, 0),
    "green": (0, 1, 0),
    "aqua": (0, 1, 1),
    "blue": (0, 0, 1),
    "purple": (0.5, 0, 1),
    "magenta": (1, 0, 1),
}
BAND_HUES = {name: _oklch_hue_of_srgb(rgb) for name, rgb in _BANDS.items()}
_HSL_HUE_SHIFT = 30.0  # degrees at ±100
_HSL_LUMINANCE = 0.25  # OKLab L at ±100 (for fully colorful pixels)
_GRADE_CHROMA = 0.06  # OKLab chroma added at saturation 100
_GRADE_LUMINANCE = 0.2  # OKLab L at ±100
_VIBRANCE_SKIN_HUE = BAND_HUES["orange"]


def _smoothstep(edge0: float, edge1: float, x: F32) -> F32:
    # A minimum width keeps tiny slider values (e.g. masking 1e-300) from dividing by zero in float32.
    width = np.float32(max(edge1 - edge0, 1e-12))
    t = np.clip((x - np.float32(edge0)) / width, 0, 1)
    out: F32 = t * t * (3 - 2 * t)
    return out


def _segments(hue: F32, centers: npt.NDArray[np.float32]) -> tuple[npt.NDArray[np.intp], F32]:
    """For each hue: the segment between adjacent band centers it falls in, and the smooth 0..1 position in
    it. Found by search, so float rounding can't put a hue in two segments."""
    count = centers.size
    wrapped = hue % np.float32(360)
    segment = (np.searchsorted(centers, wrapped, side="right") - 1) % count
    start = centers[segment]
    span = (centers[(segment + 1) % count] - start) % np.float32(360)
    t = np.clip(((wrapped - start) % np.float32(360)) / span, 0, 1)
    return segment, (t * t * (3 - 2 * t)).astype(np.float32)


def band_weights(hue: F32) -> dict[str, F32]:
    """Weight of each HSL band for every hue (degrees). Neighbouring bands cross-fade; weights sum to 1."""
    names = sorted(BAND_HUES, key=BAND_HUES.__getitem__)
    centers = np.array([BAND_HUES[n] for n in names], dtype=np.float32)
    segment, s = _segments(hue, centers)
    weights: dict[str, F32] = {}
    for k, name in enumerate(names):
        mine = np.where(segment == k, 1 - s, 0)
        from_previous = np.where(segment == (k - 1) % len(names), s, 0)
        weights[name] = (mine + from_previous).astype(np.float32)
    return weights


def _apply_hsl(lightness: F32, chroma: F32, hue: F32, params: Hsl) -> tuple[F32, F32, F32]:
    # Same result as summing band_weights() × band values, but each pixel only ever touches its two
    # neighbouring bands, so gather those from 8-entry tables instead of eight full-image passes.
    names = sorted(BAND_HUES, key=BAND_HUES.__getitem__)
    centers = np.array([BAND_HUES[n] for n in names], dtype=np.float32)
    bands = [getattr(params, n) for n in names]
    shift_table = np.array([b.hue / 100 * _HSL_HUE_SHIFT for b in bands], dtype=np.float32)
    scale_table = np.array([1 + b.saturation / 100 for b in bands], dtype=np.float32)
    lift_table = np.array([b.luminance / 100 * _HSL_LUMINANCE for b in bands], dtype=np.float32)
    segment, s = _segments(hue, centers)
    following = (segment + 1) % len(names)
    shift = shift_table[segment] * (1 - s) + shift_table[following] * s
    scale = scale_table[segment] * (1 - s) + scale_table[following] * s
    lift = lift_table[segment] * (1 - s) + lift_table[following] * s
    colorful = _smoothstep(0, 0.12, chroma)  # grays have no hue: leave their brightness alone
    new_lightness: F32 = (lightness + lift * colorful).astype(np.float32, copy=False)
    return new_lightness, chroma * scale, (hue + shift) % 360


def _wheel_direction(hsv_hue: float) -> tuple[float, float]:
    """Unit OKLab (a, b) direction of an HSV hue (0 = red, 120 = green, 240 = blue)."""
    sector, fraction = divmod(hsv_hue / 60, 1)
    rgb = [
        (1, fraction, 0),
        (1 - fraction, 1, 0),
        (0, 1, fraction),
        (0, 1 - fraction, 1),
        (fraction, 0, 1),
        (1, 0, 1 - fraction),
    ][int(sector) % 6]
    angle = np.radians(_oklch_hue_of_srgb((float(rgb[0]), float(rgb[1]), float(rgb[2]))))
    return float(np.cos(angle)), float(np.sin(angle))


def grading_masks(lightness: F32, grading: ColorGrading) -> dict[str, F32]:
    """Shadows/midtones/highlights weights from OKLab lightness; blending widens the overlap."""
    split = 0.5 - 0.2 * grading.balance / 100  # positive balance gives the highlights more room
    width = 0.1 + 0.4 * grading.blending / 100
    shadows = 1 - _smoothstep(split - 0.2 - width / 2, split - 0.2 + width / 2, lightness)
    highlights = _smoothstep(split + 0.2 - width / 2, split + 0.2 + width / 2, lightness)
    midtones = np.clip(1 - shadows - highlights, 0, 1).astype(np.float32)
    return {"shadows": shadows, "midtones": midtones, "highlights": highlights}


def _apply_grading(lab: F32, grading: ColorGrading) -> F32:
    masks = grading_masks(lab[..., 0], grading)
    masks["global"] = np.ones_like(lab[..., 0])
    out = lab.copy()
    for name, mask in masks.items():
        wheel = getattr(grading, "global_" if name == "global" else name)
        if wheel.saturation:
            da, db = _wheel_direction(wheel.hue)
            amount = np.float32(wheel.saturation / 100 * _GRADE_CHROMA) * mask
            out[..., 1] += amount * np.float32(da)
            out[..., 2] += amount * np.float32(db)
        if wheel.luminance:
            out[..., 0] += np.float32(wheel.luminance / 100 * _GRADE_LUMINANCE) * mask
    return out


def _apply_presence(chroma: F32, hue: F32, presence: Presence) -> F32:
    out = chroma
    if presence.vibrance:
        muted = 1 - _smoothstep(0, 0.2, chroma)  # vibrance mostly lifts muted colors
        if presence.vibrance > 0:  # and goes easy on skin tones
            distance = np.abs((hue - np.float32(_VIBRANCE_SKIN_HUE) + 180) % 360 - 180)
            muted = muted * (1 - 0.5 * (1 - _smoothstep(0, 40, distance)))
        out = out * (1 + np.float32(presence.vibrance / 100) * muted)
    if presence.saturation:
        out = out * np.float32(1 + presence.saturation / 100)
    return out


def color_adjust(
    display_linear: F32, profile_hsl: Hsl, hsl: Hsl, grading: ColorGrading, presence: Presence
) -> F32:
    """Profile HSL, user HSL, color grading, then vibrance/saturation, all in OKLab. Input/output display-
    linear."""
    neutral_hsl = Hsl()
    neutral_grading = ColorGrading()
    if (
        profile_hsl == neutral_hsl
        and hsl == neutral_hsl
        and grading == neutral_grading
        and not presence.vibrance
        and not presence.saturation
    ):
        return display_linear
    lab = color.rec2020_to_oklab(display_linear)
    lch: F32 | None = None
    for params in (profile_hsl, hsl):
        if params != neutral_hsl:
            lch = color.oklab_to_oklch(lab) if lch is None else lch
            lch[..., 0], lch[..., 1], lch[..., 2] = _apply_hsl(lch[..., 0], lch[..., 1], lch[..., 2], params)
    if grading != neutral_grading:
        lab = color.oklch_to_oklab(lch) if lch is not None else lab
        lch = None
        lab = _apply_grading(lab, grading)
    if presence.vibrance or presence.saturation:
        lch = color.oklab_to_oklch(lab) if lch is None else lch
        lch[..., 1] = _apply_presence(lch[..., 1], lch[..., 2], presence)
    if lch is not None:
        lab = color.oklch_to_oklab(lch)
    return color.oklab_to_rec2020(lab).astype(np.float32, copy=False)


# ----------------------------------------------------------------- vignette

_VIGNETTE_DARKEN_EV = 2.0  # corners at amount -100


def vignette_mask(height: int, width: int, params: Vignette) -> F32:
    """0 at the center, rising to 1 toward the corners, shaped by midpoint, roundness and feather."""
    y, x = np.meshgrid(
        np.linspace(-1, 1, height, dtype=np.float32),
        np.linspace(-1, 1, width, dtype=np.float32),
        indexing="ij",
    )
    roundness = params.roundness / 100
    longest = max(width, height)
    # Positive roundness bends the frame-shaped ellipse toward a circle; negative squares it off
    # (superellipse).
    sx = 1 + max(roundness, 0) * (width / longest - 1)
    sy = 1 + max(roundness, 0) * (height / longest - 1)
    power = 2 + 6 * max(-roundness, 0)
    distance = (np.abs(x * sx) ** power + np.abs(y * sy) ** power) ** (1 / power)
    corner = float((sx**power + sy**power) ** (1 / power))
    rho = distance / np.float32(corner)
    middle = 0.2 + 0.6 * params.midpoint / 100
    width_ = 0.05 + 0.75 * params.feather / 100
    start = max(middle - width_ / 2, 0.0)
    return _smoothstep(start, middle + width_ / 2, rho.astype(np.float32))


def vignette(display_linear: F32, params: Vignette, mask: F32 | None = None) -> F32:
    """Darken (negative amount) or lighten (positive) toward the corners; the center is never changed.

    ``mask`` (from ``vignette_mask``) lets a caller rendering in strips pass each strip its part of the mask.
    """
    if not params.amount:
        return display_linear
    if mask is None:
        mask = vignette_mask(display_linear.shape[0], display_linear.shape[1], params)
    mask = mask[..., None]
    amount = np.float32(params.amount / 100)
    if amount < 0:
        out: F32 = display_linear * np.exp2(amount * np.float32(_VIGNETTE_DARKEN_EV) * mask)
        return out
    lightened: F32 = display_linear + np.maximum(1 - display_linear, 0) * amount * mask
    return lightened


# ----------------------------------------------------------------- sharpening

cv2.setNumThreads(1)  # determinism first; a 1600 px blur takes ~10 ms single-threaded anyway
_REC709_LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
_SHARPEN_GAIN = 1.2  # amount 100 → 1.2 × the detail signal
_MIN_SIGMA = 0.25  # below this (tiny thumbnails) sharpening has nothing to work on


def sharpen(encoded: F32, params: Sharpening, scale: float) -> F32:
    """Unsharp mask on luminance of display-encoded pixels.

    ``scale`` is output width ÷ original width, so the radius means the same at every output size. ``detail``
    controls halos (low = large edge differences are softly limited); ``masking`` restricts the effect to
    edges.
    """
    sigma = params.radius * scale
    if not params.amount or sigma < _MIN_SIGMA:
        return encoded
    y = (
        encoded[..., 0] * _REC709_LUMA[0]
        + encoded[..., 1] * _REC709_LUMA[1]
        + encoded[..., 2] * _REC709_LUMA[2]
    )
    blurred = cv2.GaussianBlur(y, (0, 0), sigma, borderType=cv2.BORDER_REFLECT)
    detail = y - blurred
    limit = np.float32(0.01 + 0.2 * params.detail / 100)
    delta = limit * np.tanh(detail / limit)
    if params.masking:
        gy, gx = np.gradient(blurred)
        threshold = 0.05 * params.masking / 100
        delta = delta * _smoothstep(0, threshold, np.hypot(gx, gy).astype(np.float32))
    gain = np.float32(params.amount / 100 * _SHARPEN_GAIN)
    out: F32 = np.clip(encoded + (gain * delta)[..., None], 0, 1).astype(np.float32, copy=False)
    return out
