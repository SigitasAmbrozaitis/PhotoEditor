"""Color science: RGB spaces, transfer functions, OKLab, temperature/tint and white balance.

All matrices are derived from the published primaries and white points (and checked against the published
matrices in the tests). Temperature/tint follow Adobe's DNG SDK (Robertson's isotemperature lines, tint scale
-3000), so the numbers mean what they mean in Lightroom: positive tint = magenta.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

type Matrix = npt.NDArray[np.float64]
type Floats = npt.NDArray[np.floating]
type XY = tuple[float, float]

D65: XY = (0.3127, 0.3290)
D50: XY = (0.3457, 0.3585)

SRGB_PRIMARIES = ((0.64, 0.33), (0.30, 0.60), (0.15, 0.06))
REC2020_PRIMARIES = ((0.708, 0.292), (0.170, 0.797), (0.131, 0.046))
DISPLAY_P3_PRIMARIES = ((0.680, 0.320), (0.265, 0.690), (0.150, 0.060))
ADOBE_RGB_PRIMARIES = ((0.64, 0.33), (0.21, 0.71), (0.15, 0.06))
ADOBE_RGB_GAMMA = 563 / 256


def xy_to_xyz(xy: XY, luminance: float = 1.0) -> npt.NDArray[np.float64]:
    x, y = xy
    return np.array([x / y * luminance, luminance, (1 - x - y) / y * luminance])


def xyz_to_xy(xyz: npt.ArrayLike) -> XY:
    x, y, z = (float(v) for v in np.asarray(xyz, dtype=np.float64))
    total = x + y + z
    return (x / total, y / total)


def rgb_to_xyz_matrix(primaries: tuple[XY, XY, XY], white: XY) -> Matrix:
    """Linear RGB with these primaries → XYZ, with RGB (1, 1, 1) mapping to ``white`` at Y = 1."""
    columns = np.column_stack([xy_to_xyz(p) for p in primaries])
    scale = np.linalg.solve(columns, xy_to_xyz(white))
    return columns * scale


XYZ_FROM_SRGB = rgb_to_xyz_matrix(SRGB_PRIMARIES, D65)
SRGB_FROM_XYZ = np.linalg.inv(XYZ_FROM_SRGB)
XYZ_FROM_REC2020 = rgb_to_xyz_matrix(REC2020_PRIMARIES, D65)
REC2020_FROM_XYZ = np.linalg.inv(XYZ_FROM_REC2020)
XYZ_FROM_DISPLAY_P3 = rgb_to_xyz_matrix(DISPLAY_P3_PRIMARIES, D65)
XYZ_FROM_ADOBE_RGB = rgb_to_xyz_matrix(ADOBE_RGB_PRIMARIES, D65)

REC2020_FROM_SRGB = REC2020_FROM_XYZ @ XYZ_FROM_SRGB
SRGB_FROM_REC2020 = SRGB_FROM_XYZ @ XYZ_FROM_REC2020
DISPLAY_P3_FROM_REC2020 = np.linalg.inv(XYZ_FROM_DISPLAY_P3) @ XYZ_FROM_REC2020
ADOBE_RGB_FROM_REC2020 = np.linalg.inv(XYZ_FROM_ADOBE_RGB) @ XYZ_FROM_REC2020

# Relative luminance (Y) of linear Rec.2020: the middle row of its XYZ matrix.
REC2020_LUMA = XYZ_FROM_REC2020[1].copy()


def apply_matrix(pixels: Floats, matrix: Matrix) -> Floats:
    """Multiply every RGB pixel (last axis) by ``matrix``, keeping the input's float dtype.

    Written as explicit per-channel sums instead of ``@``: a multithreaded BLAS may split the work differently
    from run to run, and renders must be bit-identical (golden rule 3).
    """
    m = matrix.astype(pixels.dtype, copy=False)
    r, g, b = pixels[..., 0], pixels[..., 1], pixels[..., 2]
    out = np.empty_like(pixels)
    for row in range(3):
        out[..., row] = r * m[row, 0] + g * m[row, 1] + b * m[row, 2]
    return out


# ----------------------------------------------------------------- transfer functions


def srgb_encode(linear: Floats) -> Floats:
    """Linear → sRGB-encoded (IEC 61966-2-1). Input should already be clipped to 0..1."""
    small = linear * 12.92
    large = 1.055 * np.power(np.maximum(linear, 0.0031308), 1 / 2.4) - 0.055
    return np.where(linear <= 0.0031308, small, large).astype(linear.dtype, copy=False)


def srgb_decode(encoded: Floats) -> Floats:
    """sRGB-encoded → linear."""
    small = encoded / 12.92
    large = np.power((np.maximum(encoded, 0.04045) + 0.055) / 1.055, 2.4)
    return np.where(encoded <= 0.04045, small, large).astype(encoded.dtype, copy=False)


def gamma_encode(linear: Floats, gamma: float) -> Floats:
    return np.power(np.maximum(linear, 0), 1 / gamma).astype(linear.dtype, copy=False)


# ----------------------------------------------------------------- OKLab (Björn Ottosson, 2020)

_LMS_FROM_XYZ = np.array(
    [
        [0.8189330101, 0.3618667424, -0.1288597137],
        [0.0329845436, 0.9293118715, 0.0361456387],
        [0.0482003018, 0.2643662691, 0.6338517070],
    ]
)
_OKLAB_FROM_LMS_ = np.array(
    [
        [0.2104542553, 0.7936177850, -0.0040720468],
        [1.9779984951, -2.4285922050, 0.4505937099],
        [0.0259040371, 0.7827717662, -0.8086757660],
    ]
)
# Scaled so our D65 white lands exactly on LMS (1, 1, 1): neutrals then have exactly zero chroma (Ottosson's
# matrix targets a marginally different D65; the change is ~1e-5).
_LMS_FROM_REC2020 = _LMS_FROM_XYZ @ XYZ_FROM_REC2020
_LMS_FROM_REC2020 = _LMS_FROM_REC2020 / _LMS_FROM_REC2020.sum(axis=1, keepdims=True)
_REC2020_FROM_LMS = np.linalg.inv(_LMS_FROM_REC2020)
_LMS__FROM_OKLAB = np.linalg.inv(_OKLAB_FROM_LMS_)


def xyz_to_oklab(xyz: Floats) -> Floats:
    lms = apply_matrix(xyz, _LMS_FROM_XYZ)
    return apply_matrix(np.cbrt(lms), _OKLAB_FROM_LMS_)


def rec2020_to_oklab(rgb: Floats) -> Floats:
    """Linear Rec.2020 → OKLab (L ≈ 0..1, a/b ≈ -0.4..0.4)."""
    lms = apply_matrix(rgb, _LMS_FROM_REC2020)
    return apply_matrix(np.cbrt(lms), _OKLAB_FROM_LMS_)


def oklab_to_rec2020(lab: Floats) -> Floats:
    lms_ = apply_matrix(lab, _LMS__FROM_OKLAB)
    return apply_matrix(lms_ * lms_ * lms_, _REC2020_FROM_LMS)


def oklab_to_oklch(lab: Floats) -> Floats:
    """OKLab → OKLCh with hue in degrees 0..360."""
    out = np.empty_like(lab)
    out[..., 0] = lab[..., 0]
    out[..., 1] = np.hypot(lab[..., 1], lab[..., 2])
    out[..., 2] = np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) % 360
    return out


def oklch_to_oklab(lch: Floats) -> Floats:
    out = np.empty_like(lch)
    hue = np.radians(lch[..., 2])
    out[..., 0] = lch[..., 0]
    out[..., 1] = lch[..., 1] * np.cos(hue)
    out[..., 2] = lch[..., 1] * np.sin(hue)
    return out


# ----------------------------------------------------------------- temperature / tint (DNG SDK method)

# Robertson's isotemperature lines: reciprocal megakelvin, CIE 1960 u, v, and the line's slope.
_ROBERTSON = (
    (0, 0.18006, 0.26352, -0.24341),
    (10, 0.18066, 0.26589, -0.25479),
    (20, 0.18133, 0.26846, -0.26876),
    (30, 0.18208, 0.27119, -0.28539),
    (40, 0.18293, 0.27407, -0.30470),
    (50, 0.18388, 0.27709, -0.32675),
    (60, 0.18494, 0.28021, -0.35156),
    (70, 0.18611, 0.28342, -0.37915),
    (80, 0.18740, 0.28668, -0.40955),
    (90, 0.18880, 0.28997, -0.44278),
    (100, 0.19032, 0.29326, -0.47888),
    (125, 0.19462, 0.30141, -0.58204),
    (150, 0.19962, 0.30921, -0.70471),
    (175, 0.20525, 0.31647, -0.84901),
    (200, 0.21142, 0.32312, -1.0182),
    (225, 0.21807, 0.32909, -1.2168),
    (250, 0.22511, 0.33439, -1.4512),
    (275, 0.23247, 0.33904, -1.7298),
    (300, 0.24010, 0.34308, -2.0637),
    (325, 0.24792, 0.34655, -2.4681),
    (350, 0.25591, 0.34951, -2.9641),
    (375, 0.26400, 0.35200, -3.5814),
    (400, 0.27218, 0.35407, -4.3633),
    (425, 0.28039, 0.35577, -5.3762),
    (450, 0.28863, 0.35714, -6.7262),
    (475, 0.29685, 0.35823, -8.5955),
    (500, 0.30505, 0.35907, -11.324),
    (525, 0.31320, 0.35968, -15.628),
    (550, 0.32129, 0.36011, -23.325),
    (575, 0.32931, 0.36038, -40.770),
    (600, 0.33724, 0.36051, -116.45),
)
_TINT_SCALE = -3000.0
MIN_TEMPERATURE = 1e6 / 600  # 1667 K: the table's end


def _unit(du: float, dv: float) -> tuple[float, float]:
    length = math.hypot(du, dv)
    return du / length, dv / length


def temperature_tint_to_xy(temperature: float, tint: float) -> XY:
    """Kelvin + tint (Lightroom units) → CIE xy of that white."""
    if temperature < MIN_TEMPERATURE:
        raise ValueError(f"temperature must be at least {MIN_TEMPERATURE:.0f} K, got {temperature}")
    r = 1e6 / temperature
    offset = tint / _TINT_SCALE
    last = len(_ROBERTSON) - 2
    for index in range(len(_ROBERTSON) - 1):
        r0, u0, v0, t0 = _ROBERTSON[index]
        r1, u1, v1, t1 = _ROBERTSON[index + 1]
        if r < r1 or index == last:
            f = (r1 - r) / (r1 - r0)
            u = u0 * f + u1 * (1 - f)
            v = v0 * f + v1 * (1 - f)
            du0, dv0 = _unit(1, t0)
            du1, dv1 = _unit(1, t1)
            du, dv = _unit(du0 * f + du1 * (1 - f), dv0 * f + dv1 * (1 - f))
            u += du * offset
            v += dv * offset
            denominator = u - 4 * v + 2
            return (1.5 * u / denominator, v / denominator)
    raise AssertionError("unreachable")  # pragma: no cover


def xy_to_temperature_tint(xy: XY) -> tuple[float, float]:
    """CIE xy of a white → Kelvin + tint (Lightroom units). The inverse of ``temperature_tint_to_xy``."""
    x, y = xy
    denominator = 1.5 - x + 6 * y
    u, v = 2 * x / denominator, 3 * y / denominator
    last_dt = last_du = last_dv = 0.0
    for index in range(1, len(_ROBERTSON)):
        r0, u0, v0, _ = _ROBERTSON[index - 1]
        r1, u1, v1, t1 = _ROBERTSON[index]
        du, dv = _unit(1, t1)
        dt = -(u - u1) * dv + (v - v1) * du  # distance above this isotemperature line
        if dt <= 0 or index == len(_ROBERTSON) - 1:
            dt = -min(dt, 0)
            f = 0.0 if index == 1 else dt / (last_dt + dt)
            temperature = 1e6 / (r0 * f + r1 * (1 - f))
            uu = u - (u0 * f + u1 * (1 - f))
            vv = v - (v0 * f + v1 * (1 - f))
            du, dv = _unit(du * (1 - f) + last_du * f, dv * (1 - f) + last_dv * f)
            return temperature, (uu * du + vv * dv) * _TINT_SCALE
        last_dt, last_du, last_dv = dt, du, dv
    raise AssertionError("unreachable")  # pragma: no cover


# ----------------------------------------------------------------- adaptation + camera white balance

_BRADFORD = np.array(
    [[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]],
)


def bradford(source_white: XY, target_white: XY) -> Matrix:
    """XYZ → XYZ matrix that makes colors seen under ``source_white`` look as under ``target_white``."""
    source = _BRADFORD @ xy_to_xyz(source_white)
    target = _BRADFORD @ xy_to_xyz(target_white)
    adapted: Matrix = np.linalg.inv(_BRADFORD) @ np.diag(target / source) @ _BRADFORD
    return adapted


def camera_to_rec2020(cam_from_xyz: npt.ArrayLike) -> Matrix:
    """White-balanced camera RGB → linear Rec.2020, built the way LibRaw builds its sRGB matrix.

    ``cam_from_xyz`` is the camera color matrix (LibRaw ``rgb_xyz_matrix``, D65). Rows are normalized so that
    camera RGB (1, 1, 1), i.e. a neutral after white balance, maps to the D65 white.
    """
    cam_from_srgb = np.asarray(cam_from_xyz, dtype=np.float64)[:3, :3] @ XYZ_FROM_SRGB
    cam_from_srgb = cam_from_srgb / cam_from_srgb.sum(axis=1, keepdims=True)
    return REC2020_FROM_SRGB @ np.linalg.inv(cam_from_srgb)


def camera_multipliers(
    cam_from_xyz: npt.ArrayLike, temperature: float, tint: float
) -> npt.NDArray[np.float64]:
    """White balance multipliers (green = 1) that make a white lit by ``temperature``/``tint`` neutral."""
    response = np.asarray(cam_from_xyz, dtype=np.float64)[:3, :3] @ xy_to_xyz(
        temperature_tint_to_xy(temperature, tint)
    )
    if np.any(response <= 0):
        raise ValueError(
            f"{temperature:.0f} K / tint {tint:+.0f} is outside what this camera's matrix can represent"
        )
    multipliers: npt.NDArray[np.float64] = 1 / response
    normalized: npt.NDArray[np.float64] = multipliers / multipliers[1]
    return normalized


def as_shot_temperature_tint(cam_from_xyz: npt.ArrayLike, multipliers: npt.ArrayLike) -> tuple[float, float]:
    """Temperature + tint of the white the camera balanced for, from its WB multipliers."""
    m = np.asarray(multipliers, dtype=np.float64)[:3]
    neutral_camera = 1 / (m / m[1])
    xyz = np.linalg.solve(np.asarray(cam_from_xyz, dtype=np.float64)[:3, :3], neutral_camera)
    return xy_to_temperature_tint(xyz_to_xy(xyz))
