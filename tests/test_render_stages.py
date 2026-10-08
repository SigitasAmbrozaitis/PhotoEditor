from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from photoedit.core import color
from photoedit.core.decode import LinearImage
from photoedit.core.render import stages
from photoedit.models.adjustments import Tone, WhiteBalance

XT3 = np.array([[1.6393, -0.7740, -0.1436], [-0.4140, 1.1745, 0.2632], [-0.0536, 0.1413, 0.6614]])


def raw_image(pixels: np.ndarray, temperature: float = 5000, tint: float = 0) -> LinearImage:
    return LinearImage(
        pixels=pixels.astype(np.float32),
        to_rec2020=color.camera_to_rec2020(XT3),
        is_raw=True,
        cam_from_xyz=XT3,
        as_shot_multipliers=color.camera_multipliers(XT3, temperature, tint),
    )


def raster_image(pixels: np.ndarray) -> LinearImage:
    return LinearImage(pixels=pixels.astype(np.float32), to_rec2020=np.eye(3), is_raw=False)


NEUTRAL = np.full((1, 1, 3), 0.5)
PATCHES = np.array([[[0.5, 0.5, 0.5], [0.6, 0.3, 0.1], [0.1, 0.4, 0.7]]])


# ----------------------------------------------------------------- white balance


def test_raw_as_shot_is_just_the_camera_matrix() -> None:
    image = raw_image(PATCHES)
    out = stages.white_balance(image, WhiteBalance())
    np.testing.assert_allclose(out, color.apply_matrix(image.pixels, image.to_rec2020), atol=1e-7)
    np.testing.assert_allclose(out[0, 0], [0.5, 0.5, 0.5], atol=1e-6)  # a neutral stays neutral


def test_raw_explicit_as_shot_values_change_nothing() -> None:
    image = raw_image(PATCHES, 5000, 0)
    temperature, tint = image.as_shot
    out = stages.white_balance(image, WhiteBalance(temperature=temperature, tint=tint))
    np.testing.assert_allclose(out, stages.white_balance(image, WhiteBalance()), atol=1e-5)


def test_raw_lower_temperature_makes_the_photo_bluer() -> None:
    image = raw_image(NEUTRAL, 5000)
    cooler = stages.white_balance(image, WhiteBalance(temperature=3000))[0, 0]
    warmer = stages.white_balance(image, WhiteBalance(temperature=9000))[0, 0]
    assert cooler[2] > cooler[0]  # corrected for warm light → blue
    assert warmer[0] > warmer[2]


def test_raw_tint_alone_keeps_the_as_shot_temperature() -> None:
    image = raw_image(NEUTRAL, 5000)
    magenta = stages.white_balance(image, WhiteBalance(tint=40))[0, 0]
    assert magenta[1] < magenta[0] and magenta[1] < magenta[2]  # green drops: magenta


def test_raster_white_balance() -> None:
    image = raster_image(PATCHES)
    assert stages.white_balance(image, WhiteBalance()) is image.pixels
    as_shot_t, as_shot_tint = image.as_shot
    np.testing.assert_allclose(
        stages.white_balance(image, WhiteBalance(temperature=as_shot_t, tint=as_shot_tint)),
        image.pixels,
        atol=1e-5,
    )
    cooler = stages.white_balance(raster_image(NEUTRAL), WhiteBalance(temperature=3000))[0, 0]
    assert cooler[2] > cooler[0]


# ----------------------------------------------------------------- exposure


def test_exposure_doubles_and_halves_linear_values() -> None:
    rgb = PATCHES.astype(np.float32)
    assert stages.exposure(rgb, 0) is rgb
    np.testing.assert_array_equal(stages.exposure(rgb, 1), rgb * 2)
    np.testing.assert_array_equal(stages.exposure(rgb, -1), rgb / 2)
    assert stages.exposure(rgb, 1).dtype == np.float32


# ----------------------------------------------------------------- output


def test_output_encodes_gray_and_white_exactly() -> None:
    rgb = np.array([[[0.18, 0.18, 0.18], [1.0, 1.0, 1.0], [0.0, 0.0, 0.0]]], dtype=np.float32)
    np.testing.assert_allclose(stages.output_srgb(rgb)[0], [[0.4613561] * 3, [1.0] * 3, [0.0] * 3], atol=1e-5)


def test_out_of_gamut_colors_keep_their_luminance() -> None:
    rec2020_green = np.array([[[0.0, 0.5, 0.0]]], dtype=np.float32)  # far outside sRGB
    encoded = stages.output_srgb(rec2020_green)
    assert encoded.min() >= 0
    srgb_linear = color.srgb_decode(encoded.astype(np.float64))[0, 0]
    assert float(color.XYZ_FROM_SRGB[1] @ srgb_linear) == pytest.approx(
        float(stages.luminance(rec2020_green)[0, 0]), rel=1e-4
    )


def test_in_gamut_colors_are_not_desaturated() -> None:
    srgb = np.array([[[0.2, 0.5, 0.8], [0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]], dtype=np.float32)
    np.testing.assert_array_equal(stages.desaturate_into_gamut(srgb, color.XYZ_FROM_SRGB[1]), srgb)


def test_quantize_rounds_to_nearest() -> None:
    values = np.array([0.0, 0.5, 1.0, 1.5, -0.2], dtype=np.float32)
    np.testing.assert_array_equal(stages.quantize(values), [0, 128, 255, 255, 0])
    assert stages.quantize(values, 16).tolist() == [0, 32768, 65535, 65535, 0]


def test_luminance_of_white_is_one() -> None:
    assert float(stages.luminance(np.ones((1, 1, 3), dtype=np.float32))[0, 0]) == pytest.approx(1.0, abs=1e-6)


# ----------------------------------------------------------------- tone


def gray_at(stops: float) -> np.ndarray:
    return np.full((1, 1, 3), 0.18 * 2.0**stops, dtype=np.float32)


def stops_after(params: Tone, stops: float) -> float:
    out = stages.tone(gray_at(stops), params)
    return float(np.log2(stages.luminance(out)[0, 0] / 0.18))


tone_values = st.floats(min_value=-100, max_value=100)


def test_neutral_tone_is_the_same_array() -> None:
    rgb = PATCHES.astype(np.float32)
    assert stages.tone(rgb, Tone()) is rgb


@given(tone_values, tone_values, tone_values, tone_values, tone_values)
def test_tone_curve_is_monotone_and_keeps_mid_gray(c: float, h: float, s: float, w: float, b: float) -> None:
    params = Tone(contrast=c, highlights=h, shadows=s, whites=w, blacks=b)
    curve = stages.tone_curve_stops(params)
    assert (np.diff(curve) > 0).all()
    np.testing.assert_array_equal(stages.tone(gray_at(0), params), gray_at(0))


def test_tone_preserves_color_ratios() -> None:
    rgb = PATCHES.astype(np.float32)
    out = stages.tone(rgb, Tone(contrast=40, shadows=30, highlights=-50))
    ratios = out / rgb
    np.testing.assert_allclose(ratios, ratios[..., :1].repeat(3, axis=-1), rtol=1e-5)


def test_shadows_lift_darks_and_leave_brights_alone() -> None:
    lifted = Tone(shadows=100)
    assert stops_after(lifted, -4) > -4 + 0.5
    assert stops_after(lifted, 2) == pytest.approx(2, abs=1e-5)
    assert stops_after(Tone(shadows=-100), -4) < -4 - 0.5


def test_highlights_recover_brights_and_leave_darks_alone() -> None:
    recovered = Tone(highlights=-100)
    assert stops_after(recovered, 2.5) < 2.5 - 0.5
    assert stops_after(recovered, -3) == pytest.approx(-3, abs=1e-5)
    assert stops_after(Tone(highlights=100), 2.5) > 2.5 + 0.5


def test_whites_and_blacks_work_at_the_ends() -> None:
    assert stops_after(Tone(whites=100), 4) > 4 + 0.3
    assert stops_after(Tone(whites=100), -2) == pytest.approx(-2, abs=1e-5)
    assert stops_after(Tone(blacks=-100), -7) < -7 - 0.3
    assert stops_after(Tone(blacks=-100), 1) == pytest.approx(1, abs=1e-5)


def test_contrast_spreads_tones_around_mid_gray() -> None:
    more = Tone(contrast=50)
    assert stops_after(more, -3) < -3 and stops_after(more, 3) > 3
    less = Tone(contrast=-50)
    assert stops_after(less, -3) > -3 and stops_after(less, 3) < 3
