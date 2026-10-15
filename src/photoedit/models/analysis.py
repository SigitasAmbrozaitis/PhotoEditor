"""Numbers about a rendered photo (P7.6): what Claude reads next to the preview image to judge exposure,
clipping and color. Measured on the photo as the preview shows it (8-bit sRGB), so they describe what the user
sees."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from photoedit.models.subject import SubjectAnalysis

HISTOGRAM_BINS = 32


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ChannelClipping(_Model):
    shadows: float = Field(ge=0, le=100, description="% of pixels where this channel is 0.")
    highlights: float = Field(ge=0, le=100, description="% of pixels where this channel is 255.")


class Clipping(_Model):
    shadows: float = Field(ge=0, le=100, description="% of pixels that are pure black (every channel 0).")
    highlights: float = Field(
        ge=0, le=100, description="% of pixels that are pure white (every channel 255)."
    )
    red: ChannelClipping
    green: ChannelClipping
    blue: ChannelClipping


class Lightness(_Model):
    """Perceptual lightness (OKLab L): 0 = black, 1 = white, ~0.6 = middle gray as people see it."""

    histogram: list[float] = Field(
        min_length=HISTOGRAM_BINS,
        max_length=HISTOGRAM_BINS,
        description=f"% of pixels in each of {HISTOGRAM_BINS} equal steps from 0 to 1.",
    )
    mean: float = Field(ge=0, le=1)
    p1: float = Field(ge=0, le=1, description="1st percentile (the darkest 1 % are below).")
    p5: float = Field(ge=0, le=1)
    median: float = Field(ge=0, le=1)
    p95: float = Field(ge=0, le=1)
    p99: float = Field(ge=0, le=1, description="99th percentile (the brightest 1 % are above).")
    contrast: float = Field(ge=0, le=1, description="p95 - p5: the spread of the main tones.")


class ColorCast(_Model):
    """The average color of the near-neutral pixels (low chroma, not near black or white). A neutral photo has
    a and b near 0; a cast shows as a direction."""

    a: float = Field(description="OKLab a: + toward red/magenta, - toward green.")
    b: float = Field(description="OKLab b: + toward yellow (warm), - toward blue (cool).")
    strength: float = Field(
        ge=0, description="Chroma of the cast: < 0.005 none, ~0.01 slight, > 0.02 strong."
    )
    direction: str = Field(
        description="neutral, or the HSL band whose hue the cast leans to (e.g. yellow, blue, magenta)."
    )
    neutral_share: float = Field(ge=0, le=100, description="% of pixels it was measured on.")


class HueBand(_Model):
    name: str = Field(description="The HSL band (red, orange, yellow, green, aqua, blue, purple, magenta).")
    share: float = Field(ge=0, le=100, description="% of the photo's pixels with color in this band.")
    chroma: float = Field(ge=0, description="Mean OKLab chroma of those pixels (~0.05 muted, > 0.15 vivid).")


class ImageMeasures(_Model):
    width: int = Field(ge=1, description="Size the photo was measured at.")
    height: int = Field(ge=1)
    lightness: Lightness
    clipping: Clipping
    cast: ColorCast | None = Field(description="None when too few pixels are near neutral to tell.")
    colorfulness: float = Field(ge=0, description="Mean OKLab chroma of all pixels.")
    colorful_share: float = Field(ge=0, le=100, description="% of pixels with clear color (chroma ≥ 0.04).")
    bands: list[HueBand] = Field(description="The 8 HSL bands, in the sliders' order.")


class ToneStats(_Model):
    """Measured once per photo on the unedited image (what the adaptive style rules read)."""

    black: float = Field(description="Black point in stops relative to mid gray at exposure 0.")
    white: float = Field(description="White point in stops.")
    middle: float = Field(description="Median brightness in stops.")
    neutral_temperature: float = Field(description="Kelvin that makes near-grays gray.")
    neutral_tint: float


class PhotoAnalysis(_Model):
    photo_id: str
    draft: bool = Field(description="True when measured on unsaved adjustments, not the saved edit.")
    measures: ImageMeasures
    tone: ToneStats
    subject: SubjectAnalysis = Field(description="What subject detection found (the saved edit's framing).")
