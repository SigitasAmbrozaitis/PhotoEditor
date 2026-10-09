"""Tone anchors: a photo's own black and white points, which place the highlights/shadows/whites/blacks bands,
plus the other per-photo measurements styles' adaptive rules use (``PhotoStats``).

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

# Neutral white balance estimate (see estimate_neutral).
_NEUTRAL_LOW, _NEUTRAL_HIGH = 20, 98  # percentiles of brightness: midtones, no deep shadows or clipped lights
# log2 channel-ratio distance from the current estimate that still counts as "near gray", per round: wide
# first (a tungsten scene shot on daylight balance is far from as-shot), then down to ≈ 27 %.
_NEUTRAL_RADII = (1.0, 0.7, 0.5, 0.35, 0.35)
_NEUTRAL_MIN_SHARE = 0.02  # fewer near-gray midtones than this: keep the camera's white balance
# Lights real scenes have. An estimate outside means the "grays" were one colored subject filling the frame
# (an orange cat close-up, a red car), so the camera's white balance is kept instead.
_PLAUSIBLE_TEMPERATURE = (2500.0, 12000.0)
_PLAUSIBLE_TINT = 50.0


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


class PhotoStats(BaseModel):
    """Everything measured once per photo: tone anchors, the middle brightness and a neutral white balance.

    Brightness values are stops relative to mid gray at exposure 0 (profile baseline included). The adaptive
    rules of styles read them; the catalog stores them with the render identity they were measured with.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    black: float = Field(ge=_DARKEST, le=16)
    white: float = Field(ge=_DARKEST, le=16)
    middle: float = Field(ge=_DARKEST, le=16, description="Median brightness.")
    neutral_temperature: float = Field(ge=2000, le=50000, description="Kelvin that makes near-grays gray.")
    neutral_tint: float = Field(ge=-150, le=150)

    @property
    def anchors(self) -> ToneAnchors:
        return ToneAnchors(black=self.black, white=self.white)


def measure_anchors(base: LinearImage, profile: CameraProfile | None) -> ToneAnchors:
    """Measure on ``base``: the decoded image, or the library's working-size copy of it (same result).

    Both are scaled through the working size to ``ANCHOR_LONG_EDGE``, so whichever a caller has at hand gives
    the same pixels to measure.
    """
    black, white = _tone_stops(_measure_image(base), profile, [BLACK_PERCENTILE, WHITE_PERCENTILE])
    return ToneAnchors(black=black, white=white)


def measure_stats(base: LinearImage, profile: CameraProfile | None) -> PhotoStats:
    """``measure_anchors`` plus the middle and the neutral white balance, from the same pixels."""
    image = _measure_image(base)
    black, white, middle = _tone_stops(image, profile, [BLACK_PERCENTILE, WHITE_PERCENTILE, 50])
    temperature, tint = estimate_neutral(image)
    return PhotoStats(
        black=black,
        white=white,
        middle=middle,
        neutral_temperature=round(temperature, 1),
        neutral_tint=round(tint, 2),
    )


def estimate_neutral(image: LinearImage) -> tuple[float, float]:
    """The white balance (temperature, tint) that makes the photo's near-neutral midtones gray.

    A gray world restricted to pixels close to gray: start at the median color of the midtones, then
    repeatedly take the median color of the midtones near the current estimate, with a shrinking radius.
    Saturated areas (a red car, an orange cat, a blue sky) end up outside the radius, so they can't pull the
    estimate. Falls back to as shot when too few pixels qualify, or when the result is no plausible light
    (see ``_PLAUSIBLE_TEMPERATURE``): a frame filled by one colored subject has no grays to find.
    """
    pixels = image.pixels.reshape(-1, 3).astype(np.float64)
    level = pixels.mean(axis=1)
    positive = np.all(pixels > 1e-6, axis=1)
    if positive.sum() < 16:
        return image.as_shot
    low, high = np.percentile(level[positive], [_NEUTRAL_LOW, _NEUTRAL_HIGH])
    usable = positive & (level >= low) & (level <= high)
    safe = np.where(usable[:, None], pixels, 1.0)
    red = np.log2(safe[:, 0] / safe[:, 1])
    blue = np.log2(safe[:, 2] / safe[:, 1])
    if usable.sum() < 16:
        return image.as_shot
    center = np.array([np.median(red[usable]), np.median(blue[usable])])
    for radius in _NEUTRAL_RADII:
        near = usable & (np.hypot(red - center[0], blue - center[1]) < radius)
        if near.sum() < _NEUTRAL_MIN_SHARE * usable.sum() or near.sum() < 16:
            return image.as_shot
        center = np.array([np.median(red[near]), np.median(blue[near])])
    gray = np.array([2.0 ** center[0], 1.0, 2.0 ** center[1]])
    if image.is_raw and image.cam_from_xyz is not None and image.as_shot_multipliers is not None:
        # Gray shows as ``gray`` after the as-shot balance; dividing it out makes it neutral.
        multipliers = image.as_shot_multipliers[:3] / gray
        temperature, tint = color.as_shot_temperature_tint(image.cam_from_xyz, multipliers)
    else:
        # JPEG/TIFF pixels are linear Rec.2020: gray's chromaticity is the light to adapt from.
        temperature, tint = color.xy_to_temperature_tint(color.xyz_to_xy(color.XYZ_FROM_REC2020 @ gray))
    low_k, high_k = _PLAUSIBLE_TEMPERATURE
    if not (low_k <= temperature <= high_k and abs(tint) <= _PLAUSIBLE_TINT):
        return image.as_shot
    return float(temperature), float(tint)


def _measure_image(base: LinearImage) -> LinearImage:
    return resize_linear(resize_linear(base, LINEAR_LONG_EDGE), ANCHOR_LONG_EDGE)


def _tone_stops(image: LinearImage, profile: CameraProfile | None, percentiles: list[float]) -> list[float]:
    matrix = stages.white_balance_matrix(image, WhiteBalance())
    baseline = 0.0
    if profile is not None:
        matrix = np.array(profile.matrix, dtype=np.float64) @ matrix
        baseline = profile.baseline_exposure
    luminance = stages.luminance(color.apply_matrix(image.pixels, matrix))
    stops = np.log2(
        np.maximum(luminance.astype(np.float64), 2.0**_DARKEST * stages.MID_GRAY) / stages.MID_GRAY
    )
    values = np.clip(np.percentile(stops, percentiles) + baseline, _DARKEST, 16)
    # Rounded so the stored numbers don't carry float noise into the catalog.
    return [round(float(v), 4) for v in values]
