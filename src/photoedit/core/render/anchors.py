"""Tone anchors: a photo's own black and white points, which place the highlights/shadows/whites/blacks bands.

They are measured once per photo on its default render's scene luminance (as-shot white balance, camera
profile, exposure 0), always from the same downscaled copy of the decoded image, so previews, thumbnails and
exports of any size use identical numbers (golden rule 3). The library stores them in the catalog.
"""

from __future__ import annotations

from typing import Self

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from photoedit.core import color
from photoedit.core.cache import LINEAR_LONG_EDGE, resize_linear
from photoedit.core.decode import LinearImage
from photoedit.core.render import stages
from photoedit.core.render.profile import CameraProfile
from photoedit.models.adjustments import WhiteBalance

ANCHOR_LONG_EDGE = 512
BLACK_PERCENTILE = 0.5
WHITE_PERCENTILE = 99.5
_DARKEST = -16.0  # stops; black pixels (log of ~0) would otherwise drag the black point to the floor


class ToneAnchors(BaseModel):
    """Black and white points in stops relative to mid gray, at exposure 0 (profile baseline included)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    black: float = Field(ge=_DARKEST, le=16)
    white: float = Field(ge=_DARKEST, le=16)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.white < self.black:
            raise ValueError("tone anchors: the white point must not be below the black point")
        return self

    def shifted(self, ev: float) -> tuple[float, float]:
        """(black, white) after an exposure change of ``ev`` stops."""
        return self.black + ev, self.white + ev


def measure_anchors(base: LinearImage, profile: CameraProfile | None) -> ToneAnchors:
    """Measure on ``base``: the decoded image, or the library's working-size copy of it (same result).

    Both are scaled through the working size to ``ANCHOR_LONG_EDGE``, so whichever a caller has at hand gives
    the same pixels to measure.
    """
    image = resize_linear(resize_linear(base, LINEAR_LONG_EDGE), ANCHOR_LONG_EDGE)
    matrix = stages.white_balance_matrix(image, WhiteBalance())
    baseline = 0.0
    if profile is not None:
        matrix = np.array(profile.matrix, dtype=np.float64) @ matrix
        baseline = profile.baseline_exposure
    luminance = stages.luminance(color.apply_matrix(image.pixels, matrix))
    stops = np.log2(
        np.maximum(luminance.astype(np.float64), 2.0**_DARKEST * stages.MID_GRAY) / stages.MID_GRAY
    )
    black, white = np.clip(
        np.percentile(stops, [BLACK_PERCENTILE, WHITE_PERCENTILE]) + baseline, _DARKEST, 16
    )
    # Rounded so the stored numbers don't carry float noise into the catalog.
    return ToneAnchors(black=round(float(black), 4), white=round(float(white), 4))
