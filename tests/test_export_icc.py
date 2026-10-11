from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image, ImageCms

from photoedit.core import color
from photoedit.core.export.icc import description, icc_profile
from photoedit.core.render import stages
from photoedit.models.export import ColorSpace

SPACES = list(ColorSpace)


def _rec2020(*rgb: tuple[float, float, float]) -> np.ndarray:
    return np.array([rgb], dtype=np.float32)


def test_srgb_output_is_the_old_output_srgb() -> None:
    rng = np.random.default_rng(5)
    pixels = rng.uniform(-0.1, 1.3, size=(16, 16, 3)).astype(np.float32)
    old = stages.output_srgb(pixels)
    np.testing.assert_array_equal(stages.output_encode(pixels, ColorSpace.SRGB), old)


def test_white_and_black_in_every_space() -> None:
    pixels = _rec2020((1, 1, 1), (0, 0, 0), (0.18, 0.18, 0.18))
    for space in SPACES:
        out = stages.output_encode(pixels, space)[0]
        np.testing.assert_allclose(out[0], [1, 1, 1], atol=1e-5)
        np.testing.assert_allclose(out[1], [0, 0, 0], atol=1e-6)
        assert np.ptp(out[2]) < 1e-5  # neutral stays neutral


def test_known_values() -> None:
    # Mid gray: sRGB curve for sRGB and P3, gamma 563/256 for Adobe RGB.
    gray = _rec2020((0.18, 0.18, 0.18))
    assert stages.output_encode(gray, ColorSpace.SRGB)[0, 0, 0] == pytest.approx(0.4613561, abs=1e-5)
    assert stages.output_encode(gray, ColorSpace.DISPLAY_P3)[0, 0, 0] == pytest.approx(0.4613561, abs=1e-5)
    assert stages.output_encode(gray, ColorSpace.ADOBE_RGB)[0, 0, 0] == pytest.approx(
        0.18 ** (256 / 563), abs=1e-5
    )
    # An sRGB red is inside every space; it's less saturated in the wider ones.
    red = color.apply_matrix(np.array([[[0.5, 0.0, 0.0]]]), color.REC2020_FROM_SRGB).astype(np.float32)
    srgb = stages.output_encode(red, ColorSpace.SRGB)[0, 0]
    np.testing.assert_allclose(srgb, [0.7353570, 0, 0], atol=1e-5)
    p3 = stages.output_encode(red, ColorSpace.DISPLAY_P3)[0, 0]
    assert p3[1] > 0 and p3[0] < srgb[0]
    adobe = stages.output_encode(red, ColorSpace.ADOBE_RGB)[0, 0]  # same red primary as sRGB
    assert adobe[1] == pytest.approx(0, abs=1e-6) and adobe[0] < srgb[0]


def test_out_of_gamut_keeps_hue() -> None:
    green = _rec2020((0.0, 0.6, 0.0))  # Rec.2020 green is outside all three spaces
    for space in SPACES:
        out = stages.output_encode(green, space)[0, 0]
        assert out.min() >= 0 and out.max() <= 1
        assert out[1] > out[0] and out[1] > out[2]


@pytest.mark.parametrize("space", SPACES)
def test_profile_opens_in_littlecms(space: ColorSpace) -> None:
    profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_profile(space)))
    assert ImageCms.getProfileDescription(profile).strip() == description(space)
    assert icc_profile(space) is icc_profile(space)  # cached
    assert len(icc_profile(space)) % 4 == 0


_DECODE = {
    ColorSpace.SRGB: (color.srgb_decode, color.XYZ_FROM_SRGB),
    ColorSpace.DISPLAY_P3: (color.srgb_decode, color.XYZ_FROM_DISPLAY_P3),
    ColorSpace.ADOBE_RGB: (lambda v: np.power(v, color.ADOBE_RGB_GAMMA), color.XYZ_FROM_ADOBE_RGB),
}


@pytest.mark.parametrize("space", SPACES)
def test_profile_matches_our_math(space: ColorSpace) -> None:
    """LittleCMS, converting through our profile to sRGB, agrees with our math on the same 8-bit pixels."""
    rng = np.random.default_rng(7)
    srgb_linear = rng.uniform(0, 1, size=(32, 32, 3))  # inside sRGB, so nothing is gamut-mapped
    rec2020 = color.apply_matrix(srgb_linear, color.REC2020_FROM_SRGB).astype(np.float32)
    ours = np.rint(stages.output_encode(rec2020, space) * 255).astype(np.uint8)
    decode, xyz_from_rgb = _DECODE[space]
    linear = color.apply_matrix(decode(ours / 255.0), color.SRGB_FROM_XYZ @ xyz_from_rgb)
    expected = np.rint(color.srgb_encode(np.clip(linear, 0, 1)) * 255).astype(np.int16)
    transform = ImageCms.buildTransform(
        ImageCms.ImageCmsProfile(io.BytesIO(icc_profile(space))),
        ImageCms.createProfile("sRGB"),
        "RGB",
        "RGB",
        ImageCms.Intent.RELATIVE_COLORIMETRIC,
    )
    converted = np.asarray(ImageCms.applyTransform(Image.fromarray(ours, "RGB"), transform), dtype=np.int16)
    assert np.abs(converted - expected).max() <= 1
