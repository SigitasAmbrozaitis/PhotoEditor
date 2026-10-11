from __future__ import annotations

import numpy as np
import pytest

from photoedit.core.export.sharpen import output_sharpen, radius
from photoedit.models.export import OutputSharpening


def _edge() -> np.ndarray:
    image = np.full((32, 32, 3), 0.3, dtype=np.float32)
    image[:, 16:] = 0.7
    return image


def _settings(target: str, amount: str = "standard") -> OutputSharpening:
    return OutputSharpening.model_validate({"target": target, "amount": amount})


def test_none_is_identity() -> None:
    image = _edge()
    assert output_sharpen(image, _settings("none"), 300) is image
    assert radius(_settings("none"), 300) == 0


@pytest.mark.parametrize("target", ["screen", "glossy_paper", "matte_paper"])
def test_flat_image_unchanged(target: str) -> None:
    flat = np.full((16, 16, 3), 0.5, dtype=np.float32)
    np.testing.assert_allclose(output_sharpen(flat, _settings(target), 300), flat, atol=1e-6)


@pytest.mark.parametrize("target", ["screen", "glossy_paper", "matte_paper"])
def test_edge_gets_steeper_with_amount(target: str) -> None:
    image = _edge()
    overshoot = [
        float(np.ptp(output_sharpen(image, _settings(target, a), 300)[16, :, 1]))
        for a in ("low", "standard", "high")
    ]
    assert 0.4 < overshoot[0] < overshoot[1] < overshoot[2]


def test_paper_radius_follows_ppi_screen_does_not() -> None:
    glossy = _settings("glossy_paper")
    assert radius(glossy, 600) == pytest.approx(2 * radius(glossy, 300))
    assert radius(_settings("matte_paper"), 300) > radius(glossy, 300)
    assert radius(_settings("screen"), 72) == radius(_settings("screen"), 600)


def test_deterministic() -> None:
    image = np.random.default_rng(3).uniform(0, 1, (40, 30, 3)).astype(np.float32)
    settings = _settings("matte_paper", "high")
    np.testing.assert_array_equal(output_sharpen(image, settings, 300), output_sharpen(image, settings, 300))
