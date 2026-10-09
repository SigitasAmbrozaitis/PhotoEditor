from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from photoedit.core import color

# Adobe's X-T3 color matrix (camera from XYZ, D65), as LibRaw ships it; used as a realistic camera.
XT3_CAM_FROM_XYZ = np.array(
    [[1.6393, -0.7740, -0.1436], [-0.4140, 1.1745, 0.2632], [-0.0536, 0.1413, 0.6614]]
)


# ----------------------------------------------------------------- RGB spaces


@pytest.mark.parametrize(
    ("matrix", "published"),
    [
        (
            color.XYZ_FROM_SRGB,
            [
                [0.4124564, 0.3575761, 0.1804375],
                [0.2126729, 0.7151522, 0.0721750],
                [0.0193339, 0.1191920, 0.9503041],
            ],
        ),
        (
            color.XYZ_FROM_REC2020,
            [
                [0.6369580, 0.1446169, 0.1688810],
                [0.2627002, 0.6779981, 0.0593017],
                [0.0, 0.0280727, 1.0609851],
            ],
        ),
        (
            color.XYZ_FROM_DISPLAY_P3,
            [
                [0.4865709, 0.2656677, 0.1982173],
                [0.2289746, 0.6917385, 0.0792869],
                [0.0, 0.0451134, 1.0439444],
            ],
        ),
        (
            color.XYZ_FROM_ADOBE_RGB,
            [
                [0.5767309, 0.1855540, 0.1881852],
                [0.2973769, 0.6273491, 0.0752741],
                [0.0270343, 0.0706872, 0.9911085],
            ],
        ),
    ],
)
def test_derived_matrices_match_published_values(matrix: np.ndarray, published: list[list[float]]) -> None:
    # Published tables use D65 = (0.312713, 0.329016); we use the sRGB spec's (0.3127, 0.3290): ~2e-4 apart.
    np.testing.assert_allclose(matrix, published, atol=3e-4)


def test_white_maps_to_white_between_spaces() -> None:
    white = np.ones(3)
    for m in (color.REC2020_FROM_SRGB, color.SRGB_FROM_REC2020, color.DISPLAY_P3_FROM_REC2020):
        np.testing.assert_allclose(m @ white, white, atol=1e-12)
    np.testing.assert_allclose(color.REC2020_LUMA.sum(), 1.0, atol=1e-12)


def test_apply_matrix_keeps_dtype() -> None:
    pixels = np.ones((2, 2, 3), dtype=np.float32)
    out = color.apply_matrix(pixels, color.SRGB_FROM_REC2020)
    assert out.dtype == np.float32
    np.testing.assert_allclose(out, 1.0, atol=1e-6)


# ----------------------------------------------------------------- transfer functions


def test_srgb_transfer_reference_values() -> None:
    np.testing.assert_allclose(
        color.srgb_decode(np.array([0.0, 0.04045, 0.5, 1.0])), [0, 0.0031308, 0.2140411, 1], atol=1e-6
    )
    np.testing.assert_allclose(color.srgb_encode(np.array([0.18])), [0.4613561], atol=1e-6)


@given(st.floats(min_value=0, max_value=1))
def test_srgb_round_trip(value: float) -> None:
    x = np.array([value])
    np.testing.assert_allclose(color.srgb_decode(color.srgb_encode(x)), x, atol=1e-9)


# ----------------------------------------------------------------- OKLab


@pytest.mark.parametrize(
    ("xyz", "lab"),
    [  # Björn Ottosson's published test values
        ((0.950, 1.000, 1.089), (1.000, 0.000, 0.000)),
        ((1.000, 0.000, 0.000), (0.450, 1.236, -0.019)),
        ((0.000, 1.000, 0.000), (0.922, -0.671, 0.263)),
        ((0.000, 0.000, 1.000), (0.153, -1.415, -0.449)),
    ],
)
def test_oklab_reference_values(xyz: tuple[float, float, float], lab: tuple[float, float, float]) -> None:
    np.testing.assert_allclose(color.xyz_to_oklab(np.array(xyz)), lab, atol=1e-3)


def test_oklab_round_trip_and_lch() -> None:
    rng = np.random.default_rng(0)
    rgb = rng.uniform(0, 1, (100, 3))
    lab = color.rec2020_to_oklab(rgb)
    np.testing.assert_allclose(color.oklab_to_rec2020(lab), rgb, atol=1e-9)
    lch = color.oklab_to_oklch(lab)
    assert (lch[:, 2] >= 0).all() and (lch[:, 2] < 360).all()
    np.testing.assert_allclose(color.oklch_to_oklab(lch), lab, atol=1e-12)


def test_gray_has_no_chroma() -> None:
    lab = color.rec2020_to_oklab(np.array([[0.18, 0.18, 0.18], [1.0, 1.0, 1.0]]))
    np.testing.assert_allclose(lab[:, 1:], 0, atol=1e-7)  # Ottosson's coefficients cancel to ~4e-8
    assert lab[1, 0] == pytest.approx(1.0, abs=1e-7)


# ----------------------------------------------------------------- temperature / tint


def test_illuminant_a_is_2856k_on_the_planckian_locus() -> None:
    temperature, tint = color.xy_to_temperature_tint((0.44757, 0.40745))
    assert temperature == pytest.approx(2856, abs=5)
    assert abs(tint) < 1


@pytest.mark.parametrize(("white", "kelvin"), [(color.D65, 6504), (color.D50, 5003)])
def test_daylight_whites(white: color.XY, kelvin: float) -> None:
    temperature, tint = color.xy_to_temperature_tint(white)
    assert temperature == pytest.approx(kelvin, abs=10)
    assert tint > 0  # daylight lies on the magenta side of the Planckian locus


def test_positive_tint_means_greener_light_so_the_photo_turns_magenta() -> None:
    # Like Lightroom: temperature/tint describe the light being corrected for. A greener light (higher y) gets
    # corrected with less green gain, so the photo renders more magenta.
    neutral = np.array(color.temperature_tint_to_xy(5500, 0))
    greener = np.array(color.temperature_tint_to_xy(5500, 50))
    assert greener[1] > neutral[1]
    m0 = color.camera_multipliers(XT3_CAM_FROM_XYZ, 5500, 0)
    m1 = color.camera_multipliers(XT3_CAM_FROM_XYZ, 5500, 50)
    assert m1[0] > m0[0] and m1[2] > m0[2]  # red and blue gain up relative to green = magenta


@given(st.floats(min_value=2000, max_value=50000), st.floats(min_value=-150, max_value=150))
def test_temperature_tint_round_trip(temperature: float, tint: float) -> None:
    back_t, back_tint = color.xy_to_temperature_tint(color.temperature_tint_to_xy(temperature, tint))
    # Forward and inverse interpolate between table lines slightly differently (as in the DNG SDK).
    assert back_t == pytest.approx(temperature, rel=1e-5)
    assert back_tint == pytest.approx(tint, abs=1e-3)


def test_temperature_below_table_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least 1667 K"):
        color.temperature_tint_to_xy(1000, 0)


# ----------------------------------------------------------------- adaptation + camera WB


def test_bradford_d65_to_d50_matches_published_matrix() -> None:
    published = [
        [1.0478112, 0.0228866, -0.0501270],
        [0.0295424, 0.9904844, -0.0170491],
        [-0.0092345, 0.0150436, 0.7521316],
    ]
    np.testing.assert_allclose(color.bradford(color.D65, color.D50), published, atol=1e-3)
    np.testing.assert_allclose(color.bradford(color.D65, color.D65), np.eye(3), atol=1e-12)


def test_camera_matrix_maps_neutral_to_white() -> None:
    m = color.camera_to_rec2020(XT3_CAM_FROM_XYZ)
    np.testing.assert_allclose(m @ np.ones(3), np.ones(3), atol=1e-12)


@pytest.mark.parametrize(("temperature", "tint"), [(2800, 0), (5000, -7), (6500, 10), (9000, 40)])
def test_camera_multipliers_round_trip(temperature: float, tint: float) -> None:
    m = color.camera_multipliers(XT3_CAM_FROM_XYZ, temperature, tint)
    assert m[1] == 1.0 and (m > 0).all()
    back_t, back_tint = color.as_shot_temperature_tint(XT3_CAM_FROM_XYZ, m * 607)  # scale doesn't matter
    assert back_t == pytest.approx(temperature, rel=1e-5)
    assert back_tint == pytest.approx(tint, abs=1e-3)


def test_warmer_light_needs_more_blue_gain() -> None:
    tungsten = color.camera_multipliers(XT3_CAM_FROM_XYZ, 3000, 0)
    daylight = color.camera_multipliers(XT3_CAM_FROM_XYZ, 5500, 0)
    assert tungsten[2] > daylight[2] and tungsten[0] < daylight[0]


def test_extreme_white_balance_stays_finite() -> None:
    m = color.camera_multipliers(XT3_CAM_FROM_XYZ, 2000, 59)  # beyond what the linear matrix can model
    assert np.isfinite(m).all() and (m > 0).all() and m[1] == 1.0


# ----------------------------------------------------------------- CIELAB + CIEDE2000


@pytest.mark.parametrize(
    ("lab1", "lab2", "expected"),
    [  # Sharma, Wu & Dalal (2005) test data
        ((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
        ((50.0, 3.1571, -77.2803), (50.0, 0.0, -82.7485), 2.8615),
        ((50.0, 2.8361, -74.0200), (50.0, 0.0, -82.7485), 3.4412),
        ((50.0, 0.0, 0.0), (50.0, -1.0, 2.0), 2.3669),
        ((50.0, 2.4900, -0.0010), (50.0, -2.4900, 0.0009), 7.1792),
        ((50.0, 2.5, 0.0), (73.0, 25.0, -18.0), 27.1492),
        ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
        ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
    ],
)
def test_ciede2000_reference_pairs(
    lab1: tuple[float, float, float], lab2: tuple[float, float, float], expected: float
) -> None:
    assert float(color.delta_e_2000(np.array(lab1), np.array(lab2))) == pytest.approx(expected, abs=1e-4)
    assert float(color.delta_e_2000(np.array(lab2), np.array(lab1))) == pytest.approx(expected, abs=1e-4)


def test_cielab_of_white_and_black() -> None:
    white = color.xyz_to_cielab(color.xy_to_xyz(color.D65))
    np.testing.assert_allclose(white, [100, 0, 0], atol=1e-9)
    np.testing.assert_allclose(color.xyz_to_cielab(np.zeros(3)), [0, 0, 0], atol=1e-9)
    gray = color.xyz_to_cielab(color.xy_to_xyz(color.D65, 0.18))
    assert gray[0] == pytest.approx(49.496, abs=1e-3)
