from __future__ import annotations

import numpy as np
import pydantic
import pytest

from photoedit.core import color
from photoedit.core.cache import resize_linear
from photoedit.core.decode import LinearImage
from photoedit.core.render.anchors import ToneAnchors, estimate_neutral, measure_anchors, measure_stats
from photoedit.core.render.profile import GENERIC


def gray_ramp(height: int, width: int, low: float, high: float) -> LinearImage:
    """A raster image whose luminance runs evenly from ``low`` to ``high`` stops (relative to mid gray)."""
    stops = np.linspace(low, high, width)
    pixels = np.repeat((0.18 * 2.0**stops)[None, :, None], height, axis=0).repeat(3, axis=2)
    return LinearImage(pixels=pixels.astype(np.float32), to_rec2020=np.eye(3), is_raw=False)


def test_anchors_are_the_darkest_and_brightest_half_percent() -> None:
    anchors = measure_anchors(gray_ramp(8, 400, -8, 2), None)
    # Even ramp over 10 stops: the 0.5 % / 99.5 % points sit 0.05 stops inside its ends.
    assert anchors.black == pytest.approx(-7.95, abs=0.02)
    assert anchors.white == pytest.approx(1.95, abs=0.02)


def test_profile_baseline_exposure_moves_the_anchors() -> None:
    image = gray_ramp(8, 400, -8, 2)
    plain = measure_anchors(image, GENERIC)
    brighter = measure_anchors(image, GENERIC.model_copy(update={"baseline_exposure": 0.5}))
    assert brighter.black == pytest.approx(plain.black + 0.5, abs=1e-4)
    assert brighter.white == pytest.approx(plain.white + 0.5, abs=1e-4)


def test_the_decoded_image_and_its_working_copy_give_the_same_anchors() -> None:
    rng = np.random.default_rng(7)
    pixels = rng.uniform(0.0005, 1.5, size=(1500, 3000, 3)).astype(np.float32)
    decoded = LinearImage(pixels=pixels, to_rec2020=np.eye(3), is_raw=False)
    working = resize_linear(decoded, 2048)  # what the library keeps in memory
    assert measure_anchors(decoded, None) == measure_anchors(working, None)


def test_black_pixels_do_not_drag_the_black_point_to_minus_infinity() -> None:
    image = gray_ramp(8, 400, -8, 2)
    image.pixels[:, :20] = 0
    anchors = measure_anchors(image, None)
    assert anchors.black == -16.0 and anchors.white == pytest.approx(1.95, abs=0.02)


def test_anchors_validate() -> None:
    with pytest.raises(pydantic.ValidationError, match="white point"):
        ToneAnchors(black=1, white=0)
    assert ToneAnchors(black=-7, white=1).shifted(0.5) == (-6.5, 1.5)


# ----------------------------------------------------------------- PhotoStats (P4.4)


def test_stats_middle_is_the_median_and_anchors_unchanged() -> None:
    image = gray_ramp(8, 400, -8, 2)
    stats = measure_stats(image, None)
    assert stats.middle == pytest.approx(-3.0, abs=0.02)  # middle of an even -8…+2 ramp
    assert stats.anchors == measure_anchors(image, None)  # one pass, same numbers as before P4.4
    lifted = measure_stats(image, GENERIC.model_copy(update={"baseline_exposure": 0.5}))
    assert lifted.middle == pytest.approx(stats.middle + 0.5, abs=1e-4)


def _lit_scene(white_rgb: np.ndarray, *, colored_share: float = 0.3, seed: int = 3) -> np.ndarray:
    """Gray patches of many brightnesses lit by ``white_rgb``, mixed with strongly colored patches."""
    rng = np.random.default_rng(seed)
    n = 128 * 128
    reflectance = np.repeat(rng.uniform(0.02, 0.9, n)[:, None], 3, axis=1)
    colored = rng.random(n) < colored_share
    tints = rng.choice([[0.9, 0.35, 0.1], [0.1, 0.6, 0.15], [0.15, 0.3, 0.9], [0.95, 0.5, 0.05]], size=n)
    reflectance[colored] *= tints[colored]  # e.g. an orange cat, grass, sky, a red car
    return (reflectance * white_rgb).reshape(128, 128, 3).astype(np.float32)


@pytest.mark.parametrize(("temperature", "tint"), [(3200, 0), (4000, 10), (6500, 0), (9000, -10)])
def test_neutral_estimate_on_a_raster_with_a_color_cast(temperature: float, tint: float) -> None:
    light = color.REC2020_FROM_XYZ @ color.xy_to_xyz(color.temperature_tint_to_xy(temperature, tint))
    image = LinearImage(pixels=_lit_scene(light / light[1]), to_rec2020=np.eye(3), is_raw=False)
    found_temperature, found_tint = estimate_neutral(image)
    assert found_temperature == pytest.approx(temperature, abs=100)
    assert found_tint == pytest.approx(tint, abs=3)


@pytest.mark.parametrize("temperature", [3000, 4200, 5500, 7500])
def test_neutral_estimate_on_a_raw_balanced_for_daylight(temperature: float) -> None:
    cam_from_xyz = np.array([[1.2, -0.2, -0.1], [-0.4, 1.3, 0.1], [0.0, 0.1, 0.7]])  # a plausible camera
    as_shot = color.camera_multipliers(cam_from_xyz, 5500, 0)
    light = cam_from_xyz @ color.xy_to_xyz(color.temperature_tint_to_xy(temperature, 0))
    image = LinearImage(
        pixels=_lit_scene(light * as_shot),  # the decoder hands over as-shot-balanced camera RGB
        to_rec2020=color.camera_to_rec2020(cam_from_xyz),
        is_raw=True,
        cam_from_xyz=cam_from_xyz,
        as_shot_multipliers=as_shot,
    )
    assert image.as_shot[0] == pytest.approx(5500, abs=5)
    found_temperature, found_tint = estimate_neutral(image)
    assert found_temperature == pytest.approx(temperature, abs=100)
    assert found_tint == pytest.approx(0, abs=3)


def test_neutral_estimate_falls_back_to_as_shot_without_near_grays() -> None:
    pixels = np.zeros((64, 64, 3), np.float32)
    pixels[..., 0], pixels[..., 1], pixels[..., 2] = 0.6, 0.1, 0.02  # only one saturated color
    image = LinearImage(pixels=pixels, to_rec2020=np.eye(3), is_raw=False)
    assert estimate_neutral(image) == image.as_shot
    black = LinearImage(pixels=np.zeros((64, 64, 3), np.float32), to_rec2020=np.eye(3), is_raw=False)
    assert estimate_neutral(black) == black.as_shot


def test_stats_are_deterministic_and_size_independent() -> None:
    rng = np.random.default_rng(11)
    pixels = rng.uniform(0.0005, 1.2, size=(1500, 3000, 3)).astype(np.float32)
    decoded = LinearImage(pixels=pixels, to_rec2020=np.eye(3), is_raw=False)
    stats = measure_stats(decoded, None)
    assert measure_stats(resize_linear(decoded, 2048), None) == stats == measure_stats(decoded, None)
