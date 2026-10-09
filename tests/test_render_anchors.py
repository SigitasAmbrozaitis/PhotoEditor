from __future__ import annotations

import numpy as np
import pydantic
import pytest

from photoedit.core.cache import resize_linear
from photoedit.core.decode import LinearImage
from photoedit.core.render.anchors import ToneAnchors, measure_anchors
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
