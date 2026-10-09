from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError
from scipy.interpolate import PchipInterpolator

from photoedit.core.render import stages
from photoedit.core.render.curves import pchip
from photoedit.core.render.profile import GENERIC, CameraProfile, ProfileCurvePoint
from photoedit.models.adjustments import CurvePoint, ToneCurve

# ----------------------------------------------------------------- PCHIP


@pytest.mark.parametrize(
    ("xs", "ys"),
    [
        ([0, 0.3, 0.5, 1], [0, 0.2, 0.7, 1]),  # monotone
        ([0, 0.25, 0.5, 0.75, 1], [0.1, 0.8, 0.3, 0.9, 0.2]),  # zig-zag
        ([-12, -4, 0, 2, 6], [0, 0.08, 0.46, 0.75, 1]),  # base-curve shaped
    ],
)
def test_pchip_matches_scipy(xs: list[float], ys: list[float]) -> None:
    x = np.linspace(xs[0], xs[-1], 501)
    np.testing.assert_allclose(pchip(xs, ys, x), PchipInterpolator(xs, ys)(x), atol=1e-12)


def test_pchip_two_points_is_linear_and_clamps_outside() -> None:
    np.testing.assert_allclose(pchip([0, 1], [0.2, 0.6], [-1, 0, 0.5, 1, 2]), [0.2, 0.2, 0.4, 0.6, 0.6])


@given(st.lists(st.floats(min_value=0, max_value=1), min_size=3, max_size=10))
def test_pchip_rises_where_the_points_rise(raw: list[float]) -> None:
    ys = np.cumsum(np.abs(raw))
    xs = np.linspace(0, 1, len(ys))
    values = pchip(list(xs), list(ys), np.linspace(0, 1, 2001))
    assert (np.diff(values) >= -1e-12).all()
    assert values.min() >= ys.min() - 1e-12 and values.max() <= ys.max() + 1e-12  # no overshoot


def test_pchip_rejects_bad_points() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        pchip([0, 0], [0, 1], [0.5])
    with pytest.raises(ValueError):
        pchip([0], [0], [0])


# ----------------------------------------------------------------- profile + base curve


def test_profile_validation() -> None:
    def curve(points: list[tuple[float, float]]) -> list[ProfileCurvePoint]:
        return [ProfileCurvePoint(stops=s, value=v) for s, v in points]

    good = curve([(-8, 0), (-2, 0.2), (0, 0.46), (4, 1)])
    CameraProfile(id="ok", name="OK", tone_curve=good)
    with pytest.raises(ValidationError, match="must not decrease"):
        CameraProfile(id="x", name="X", tone_curve=curve([(-8, 0), (-2, 0.5), (0, 0.4), (4, 1)]))
    with pytest.raises(ValidationError, match="strictly increasing"):
        CameraProfile(id="x", name="X", tone_curve=curve([(-8, 0), (0, 0.4), (0, 0.5), (4, 1)]))
    with pytest.raises(ValidationError, match="within ±4"):
        CameraProfile(id="x", name="X", tone_curve=good, matrix=((5, 0, 0), (0, 1, 0), (0, 0, 1)))
    with pytest.raises(ValidationError):
        CameraProfile(id="Bad Id", name="X", tone_curve=good)


def test_generic_base_curve() -> None:
    lut = stages.base_curve_lut(GENERIC)
    assert (np.diff(lut) >= 0).all()
    rgb = np.array([[[0.18, 0.18, 0.18], [0.18 * 2**7, 0.0, 0.18 * 2**-13]]], dtype=np.float32)
    out = stages.base_curve(rgb, GENERIC)
    np.testing.assert_allclose(out[0, 0], [0.465] * 3, atol=1e-6)
    np.testing.assert_allclose(out[0, 1], [1.0, 0.0, 0.0], atol=1e-6)


def test_base_curve_is_per_channel() -> None:
    rgb = np.array([[[0.5, 0.18, 0.02]]], dtype=np.float32)
    out = stages.base_curve(rgb, GENERIC)[0, 0]
    singles = [
        stages.base_curve(np.full((1, 1, 3), v, dtype=np.float32), GENERIC)[0, 0, 0]
        for v in (0.5, 0.18, 0.02)
    ]
    np.testing.assert_allclose(out, singles, atol=1e-7)


# ----------------------------------------------------------------- user curves

GRID = np.linspace(0, 1, 11, dtype=np.float32)
RAMP = np.stack([GRID, GRID, GRID], axis=-1)[None]


def test_neutral_curves_return_the_same_array() -> None:
    assert stages.curves(RAMP, ToneCurve()) is RAMP


def test_inverted_rgb_curve() -> None:
    out = stages.curves(RAMP, ToneCurve(rgb=[CurvePoint(x=0, y=1), CurvePoint(x=1, y=0)]))
    np.testing.assert_allclose(out, 1 - RAMP, atol=1e-6)


def test_parametric_region_moves_its_point_by_a_tenth() -> None:
    point = np.full((1, 1, 3), 0.375, dtype=np.float32)
    np.testing.assert_allclose(stages.curves(point, ToneCurve(darks=100)), 0.475, atol=1e-6)
    np.testing.assert_allclose(stages.curves(point, ToneCurve(darks=-100)), 0.275, atol=1e-6)
    ends = np.array([[[0, 0, 0], [1, 1, 1]]], dtype=np.float32)
    np.testing.assert_allclose(stages.curves(ends, ToneCurve(darks=100, highlights=-100)), ends, atol=1e-7)


region = st.floats(min_value=-100, max_value=100)


@given(region, region, region, region)
def test_parametric_curve_always_rises(s: float, d: float, lt: float, h: float) -> None:
    luts = stages.curve_luts(ToneCurve(shadows=s, darks=d, lights=lt, highlights=h))
    if luts is None:  # all zero: nothing to apply
        return
    for lut in luts:
        assert (np.diff(lut) >= -1e-12).all()


def test_channel_curves_touch_only_their_channel() -> None:
    lift_red = ToneCurve(red=[CurvePoint(x=0, y=0), CurvePoint(x=0.5, y=0.7), CurvePoint(x=1, y=1)])
    out = stages.curves(RAMP, lift_red)
    assert out[0, 5, 0] == pytest.approx(0.7, abs=1e-6)
    np.testing.assert_array_equal(out[..., 1:], RAMP[..., 1:])
