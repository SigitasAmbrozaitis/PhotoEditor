"""Image analysis (P7.6): exact numbers on small synthetic images, and the Analyzer on a library photo."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pytest

from helpers import fill_folder
from photoedit.config import load_settings
from photoedit.core import color
from photoedit.core.analysis import measure
from photoedit.core.render.pipeline import UnsupportedParameterError
from photoedit.core.render.stages import BAND_HUES
from photoedit.models import AdjustmentParams, PhotoSort
from photoedit.models.analysis import HISTOGRAM_BINS
from photoedit.services import Services


def _image(*colors: tuple[int, int, int], repeat: int = 1) -> npt.NDArray[np.uint8]:
    """One row of pixels, each color ``repeat`` times."""
    return np.array([[c for c in colors for _ in range(repeat)]], dtype=np.uint8)


def _lightness(value: int) -> float:
    """OKLab L of the sRGB gray ``value`` (L = cube root of the linear luminance for a neutral)."""
    return float(np.cbrt(color.srgb_decode(np.array(value / 255))))


def test_gray_ramp_has_every_tone_once_and_no_cast() -> None:
    ramp = _image(*((v, v, v) for v in range(256)))
    m = measure(ramp)
    assert (m.width, m.height) == (256, 1)
    one = round(100 / 256, 4)
    assert (m.clipping.shadows, m.clipping.highlights) == (one, one)
    assert m.clipping.green.shadows == one and m.clipping.blue.highlights == one
    assert len(m.lightness.histogram) == HISTOGRAM_BINS
    assert sum(m.lightness.histogram) == pytest.approx(100, abs=1e-3)
    # 256 values: the median lies halfway between the 128th and 129th, the 1st percentile 2.55 steps in.
    assert m.lightness.median == pytest.approx((_lightness(127) + _lightness(128)) / 2, abs=1e-4)
    assert m.lightness.p1 == pytest.approx(_lightness(2) + 0.55 * (_lightness(3) - _lightness(2)), abs=1e-4)
    assert m.lightness.contrast == pytest.approx(m.lightness.p95 - m.lightness.p5, abs=1e-4)
    assert m.cast is not None and m.cast.direction == "neutral"
    assert m.cast.a == pytest.approx(0, abs=1e-4) and m.cast.b == pytest.approx(0, abs=1e-4)
    assert m.colorful_share == 0 and m.colorfulness == pytest.approx(0, abs=1e-4)
    assert all(band.share == 0 for band in m.bands)


def test_clipped_highlights_are_counted_per_pixel_and_channel() -> None:
    m = measure(_image((255, 255, 255), (255, 40, 40), (90, 90, 90), (0, 0, 0)))
    assert (m.clipping.highlights, m.clipping.shadows) == (25.0, 25.0)
    assert (m.clipping.red.highlights, m.clipping.green.highlights) == (50.0, 25.0)
    assert (m.clipping.red.shadows, m.clipping.green.shadows) == (25.0, 25.0)


def _tinted_gray(band: str, chroma: float) -> tuple[int, int, int]:
    """A mid gray tinted toward ``band``'s hue by ``chroma`` (OKLab), as 8-bit sRGB."""
    hue = np.radians(BAND_HUES[band])
    lab = np.array([0.6, chroma * np.cos(hue), chroma * np.sin(hue)])
    linear = color.apply_matrix(color.oklab_to_rec2020(lab), color.SRGB_FROM_REC2020)
    r, g, b = (int(v) for v in np.round(color.srgb_encode(linear) * 255))
    return r, g, b


@pytest.mark.parametrize("band", ["yellow", "blue", "magenta", "green"])
def test_a_tinted_gray_shows_a_cast_toward_its_hue(band: str) -> None:
    for chroma in (0.012, 0.04):  # slight, and strong enough to pass the colorful limit
        cast = measure(_image(_tinted_gray(band, chroma), repeat=4)).cast
        assert cast is not None and cast.direction == band
        assert cast.strength == pytest.approx(chroma, abs=0.003)
        assert cast.neutral_share == 100


def test_a_slight_tint_is_neutral() -> None:
    cast = measure(_image(_tinted_gray("orange", 0.003), repeat=4)).cast
    assert cast is not None and cast.direction == "neutral"


def test_pure_red_is_all_in_the_red_band_with_no_cast() -> None:
    m = measure(_image((255, 0, 0), repeat=8))
    red = {band.name: band for band in m.bands}["red"]
    assert red.share == 100 and red.chroma == pytest.approx(0.2577, abs=1e-3)
    assert sum(band.share for band in m.bands) == 100
    assert m.colorful_share == 100
    assert m.cast is None  # no near-neutral pixels to measure a cast on
    assert [band.name for band in m.bands][:3] == ["red", "orange", "yellow"]


def test_measure_is_deterministic() -> None:
    rng = np.random.default_rng(7)
    pixels = rng.integers(0, 256, size=(40, 60, 3), dtype=np.uint8)
    assert measure(pixels) == measure(pixels.copy())


# ----------------------------------------------------------------- Analyzer


@pytest.fixture
def services(tmp_path: Path) -> Iterator[Services]:
    photos = tmp_path / "photos"
    fill_folder(photos)
    settings = load_settings(tmp_path / "missing.toml", project_root=tmp_path / "project")
    services = Services(settings)
    services.jobs.wait(services.library.import_folder(photos).id, timeout=30)
    yield services
    services.close()


def test_analyzer_measures_the_saved_edit_or_a_draft(services: Services) -> None:
    pid = services.library.list_photos(sort=PhotoSort.NAME).items[0].id  # a.jpg: pure red, 320 × 200
    saved = services.analysis.analyze(pid)
    assert not saved.draft and (saved.measures.width, saved.measures.height) == (320, 200)
    assert saved.measures.colorful_share > 90
    assert saved.tone.white >= saved.tone.black
    assert not saved.subject.detected
    gray = AdjustmentParams.model_validate({"presence": {"saturation": -100}})
    draft = services.analysis.analyze(pid, gray)
    assert draft.draft and draft.measures.colorful_share == 0
    assert services.library.edit(pid).adjustments == AdjustmentParams.model_validate(
        {"detail": {"sharpening": {"amount": 0}}}
    )  # unchanged: nothing saved
    with pytest.raises(UnsupportedParameterError):
        services.analysis.analyze(pid, AdjustmentParams.model_validate({"presence": {"clarity": 10}}))
