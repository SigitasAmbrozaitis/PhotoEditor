"""Image analysis (P7.6): numbers about a rendered photo for Claude to read next to its preview.

``measure`` is a pure function of 8-bit sRGB pixels; ``Analyzer`` renders the photo (its saved edit, or draft
adjustments) at a fixed size and adds the stored tone stats and subject detection. Deterministic: the same
pixels always give the same numbers.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import numpy.typing as npt

from photoedit.core import color
from photoedit.core.library import Library
from photoedit.core.render.stages import BAND_HUES, band_weights
from photoedit.core.subject.service import Subjects
from photoedit.models import AdjustmentParams
from photoedit.models.analysis import (
    HISTOGRAM_BINS,
    ChannelClipping,
    Clipping,
    ColorCast,
    HueBand,
    ImageMeasures,
    Lightness,
    PhotoAnalysis,
    ToneStats,
)

ANALYSIS_LONG_EDGE = 1024
COLORFUL = 0.04  # OKLab chroma from which a pixel counts as having a color (and a hue band)
NEUTRAL = (
    0.06  # chroma below which a mid-tone pixel counts as near neutral for the cast (a strong cast is ~0.03)
)
NEUTRAL_LIGHTNESS = (0.15, 0.95)  # near black or white, a pixel's color says little about a cast
MIN_NEUTRAL_SHARE = 0.01  # fewer near-neutral pixels than this: no cast reported
CAST_NONE = 0.005
_DIGITS = 4

type Floats = npt.NDArray[np.floating[Any]]


def measure(rgb: npt.NDArray[np.uint8]) -> ImageMeasures:
    """Measure ``rgb`` (H × W × 3, 8-bit sRGB)."""
    height, width = rgb.shape[:2]
    pixels = rgb.reshape(-1, 3)
    count = pixels.shape[0]
    linear = color.srgb_decode(pixels.astype(np.float64) / 255)
    lab = color.rec2020_to_oklab(color.apply_matrix(linear, color.REC2020_FROM_SRGB))
    lch = color.oklab_to_oklch(lab)
    lightness = np.clip(lch[:, 0], 0, 1)
    chroma = lch[:, 1]

    def pct(mask: npt.NDArray[np.bool_]) -> float:
        return _round(100 * float(np.count_nonzero(mask)) / count)

    histogram, _ = np.histogram(lightness, bins=HISTOGRAM_BINS, range=(0, 1))
    p1, p5, p50, p95, p99 = (float(v) for v in np.percentile(lightness, [1, 5, 50, 95, 99]))
    channels = [
        ChannelClipping(shadows=pct(pixels[:, c] == 0), highlights=pct(pixels[:, c] == 255)) for c in range(3)
    ]
    colorful = chroma >= COLORFUL
    weights = band_weights(lch[colorful, 2].astype(np.float32))
    bands = []
    for name in BAND_HUES:  # the sliders' order
        weight = weights[name].astype(np.float64)
        total = float(weight.sum())
        band_chroma = float((weight * chroma[colorful]).sum()) / total if total > 0 else 0.0
        bands.append(HueBand(name=name, share=_round(100 * total / count), chroma=_round(band_chroma)))
    return ImageMeasures(
        width=width,
        height=height,
        lightness=Lightness(
            histogram=[_round(100 * int(n) / count) for n in histogram],
            mean=_round(float(lightness.mean())),
            p1=_round(p1),
            p5=_round(p5),
            median=_round(p50),
            p95=_round(p95),
            p99=_round(p99),
            contrast=_round(p95 - p5),
        ),
        clipping=Clipping(
            shadows=pct((pixels == 0).all(axis=1)),
            highlights=pct((pixels == 255).all(axis=1)),
            red=channels[0],
            green=channels[1],
            blue=channels[2],
        ),
        cast=_cast(lab, lightness, chroma),
        colorfulness=_round(float(chroma.mean())),
        colorful_share=pct(colorful),
        bands=bands,
    )


def _cast(lab: Floats, lightness: Floats, chroma: Floats) -> ColorCast | None:
    low, high = NEUTRAL_LIGHTNESS
    neutral = (chroma < NEUTRAL) & (lightness > low) & (lightness < high)
    share = float(np.count_nonzero(neutral)) / lab.shape[0]
    if share < MIN_NEUTRAL_SHARE:
        return None
    a, b = (float(v) for v in lab[neutral, 1:].mean(axis=0))
    strength = float(np.hypot(a, b))
    if strength < CAST_NONE:
        direction = "neutral"
    else:
        # Named like the HSL band whose hue is nearest, so "yellow" means what the yellow sliders change.
        hue = float(np.degrees(np.arctan2(b, a))) % 360
        direction = min(BAND_HUES, key=lambda name: abs((BAND_HUES[name] - hue + 180) % 360 - 180))
    return ColorCast(
        a=_round(a),
        b=_round(b),
        strength=_round(strength),
        direction=direction,
        neutral_share=_round(100 * share),
    )


def _round(value: float) -> float:
    # Rounded so the numbers read well; +0.0 turns a rounded -0.0 into 0.
    return round(value, _DIGITS) + 0.0


class Analyzer:
    def __init__(self, library: Library, subjects: Callable[[], Subjects]) -> None:
        # The subject service is looked up per call: the services' owner may swap it (tests use a fake).
        self._library = library
        self._subjects = subjects

    def analyze(self, photo_id: str, adjustments: AdjustmentParams | None = None) -> PhotoAnalysis:
        """Measure the photo with its saved edit, or with ``adjustments`` (validated like a save; nothing is
        written). Subject detection isn't run here: ``subject`` shows what is stored."""
        library = self._library
        photo = library.photo(photo_id)
        rgb = library.render_pixels(photo_id, adjustments, ANALYSIS_LONG_EDGE)
        stats = library.renderer.stats(photo)
        return PhotoAnalysis(
            photo_id=photo.id,
            draft=adjustments is not None,
            measures=measure(rgb),
            tone=ToneStats.model_validate(stats.model_dump()),
            subject=self._subjects().analysis(photo),
        )
