"""Global adjustment parameters (Lightroom-like, no local edits).

Every field has an explicit range and a neutral default: an all-default ``AdjustmentParams`` is the identity
edit. Descriptions are user- and AI-facing documentation, shown in the UI and exposed through the API/MCP.
"""

from __future__ import annotations

from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Reusable constrained types.
Signed100 = Annotated[float, Field(ge=-100, le=100)]
Unsigned100 = Annotated[float, Field(ge=0, le=100)]
Hue = Annotated[float, Field(ge=0, lt=360)]


class _Group(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class WhiteBalance(_Group):
    temperature: float | None = Field(
        default=None, ge=2000, le=50000, description="Color temperature in Kelvin. None = as shot."
    )
    tint: float | None = Field(
        default=None, ge=-150, le=150, description="Green (-) / magenta (+) tint. None = as shot."
    )


class Tone(_Group):
    exposure: float = Field(default=0, ge=-5, le=5, description="Exposure in EV stops.")
    contrast: Signed100 = Field(default=0, description="Global contrast.")
    highlights: Signed100 = Field(default=0, description="Recover (-) or boost (+) bright areas.")
    shadows: Signed100 = Field(default=0, description="Deepen (-) or lift (+) dark areas.")
    whites: Signed100 = Field(default=0, description="White point.")
    blacks: Signed100 = Field(default=0, description="Black point.")


class Presence(_Group):
    vibrance: Signed100 = Field(default=0, description="Saturation boost weighted toward muted colors.")
    saturation: Signed100 = Field(default=0, description="Uniform saturation.")
    clarity: Signed100 = Field(default=0, description="Midtone local contrast (planned for Phase 9).")
    texture: Signed100 = Field(default=0, description="Fine-detail local contrast (planned for Phase 9).")
    dehaze: Signed100 = Field(
        default=0, description="Remove (+) or add (-) atmospheric haze (planned for Phase 9)."
    )


class CurvePoint(_Group):
    x: float = Field(ge=0, le=1, description="Input level 0..1.")
    y: float = Field(ge=0, le=1, description="Output level 0..1.")


def _identity_curve() -> list[CurvePoint]:
    return [CurvePoint(x=0, y=0), CurvePoint(x=1, y=1)]


class ToneCurve(_Group):
    # Parametric region sliders.
    highlights: Signed100 = Field(default=0, description="Parametric curve: highlights region.")
    lights: Signed100 = Field(default=0, description="Parametric curve: lights region.")
    darks: Signed100 = Field(default=0, description="Parametric curve: darks region.")
    shadows: Signed100 = Field(default=0, description="Parametric curve: shadows region.")
    # Point curves (2..16 points, strictly increasing x).
    rgb: list[CurvePoint] = Field(default_factory=_identity_curve, min_length=2, max_length=16)
    red: list[CurvePoint] = Field(default_factory=_identity_curve, min_length=2, max_length=16)
    green: list[CurvePoint] = Field(default_factory=_identity_curve, min_length=2, max_length=16)
    blue: list[CurvePoint] = Field(default_factory=_identity_curve, min_length=2, max_length=16)

    @model_validator(mode="after")
    def _x_strictly_increasing(self) -> Self:
        for name in ("rgb", "red", "green", "blue"):
            points: list[CurvePoint] = getattr(self, name)
            xs = [p.x for p in points]
            if any(b <= a for a, b in pairwise(xs)):
                raise ValueError(f"tone curve '{name}': point x values must be strictly increasing")
        return self


class HslBand(_Group):
    hue: Signed100 = Field(default=0, description="Shift hue of this color band.")
    saturation: Signed100 = Field(default=0, description="Saturation of this color band.")
    luminance: Signed100 = Field(default=0, description="Brightness of this color band.")


class Hsl(_Group):
    red: HslBand = Field(default_factory=HslBand)
    orange: HslBand = Field(default_factory=HslBand)
    yellow: HslBand = Field(default_factory=HslBand)
    green: HslBand = Field(default_factory=HslBand)
    aqua: HslBand = Field(default_factory=HslBand)
    blue: HslBand = Field(default_factory=HslBand)
    purple: HslBand = Field(default_factory=HslBand)
    magenta: HslBand = Field(default_factory=HslBand)


class GradeWheel(_Group):
    hue: Hue = Field(default=0, description="Tint hue in degrees.")
    saturation: Unsigned100 = Field(default=0, description="Tint strength.")
    luminance: Signed100 = Field(default=0, description="Brightness of this tonal range.")


class ColorGrading(_Group):
    shadows: GradeWheel = Field(default_factory=GradeWheel)
    midtones: GradeWheel = Field(default_factory=GradeWheel)
    highlights: GradeWheel = Field(default_factory=GradeWheel)
    global_: GradeWheel = Field(default_factory=GradeWheel, alias="global")
    blending: Unsigned100 = Field(default=50, description="Overlap between the tonal ranges.")
    balance: Signed100 = Field(default=0, description="Shift the shadows/highlights split point.")

    model_config = ConfigDict(extra="forbid", validate_assignment=True, populate_by_name=True)


class Sharpening(_Group):
    amount: float = Field(default=40, ge=0, le=150, description="Sharpening strength.")
    radius: float = Field(default=1.0, ge=0.5, le=3.0, description="Edge width in pixels.")
    detail: Unsigned100 = Field(default=25, description="How much fine detail is sharpened.")
    masking: Unsigned100 = Field(default=0, description="Limit sharpening to edges (higher = fewer areas).")


class NoiseReduction(_Group):
    luminance: Unsigned100 = Field(default=0, description="Luminance noise reduction (planned for Phase 9).")
    color: Unsigned100 = Field(default=25, description="Color noise reduction (planned for Phase 9).")


class Detail(_Group):
    sharpening: Sharpening = Field(default_factory=Sharpening)
    noise_reduction: NoiseReduction = Field(default_factory=NoiseReduction)


class Vignette(_Group):
    amount: Signed100 = Field(default=0, description="Darken (-) or lighten (+) the corners.")
    midpoint: Unsigned100 = Field(default=50, description="How far the vignette reaches toward the center.")
    roundness: Signed100 = Field(default=0, description="Shape: rectangular (-) to circular (+).")
    feather: Unsigned100 = Field(default=50, description="Softness of the vignette edge.")


class Grain(_Group):
    amount: Unsigned100 = Field(default=0, description="Film grain strength (planned for Phase 9).")
    size: Unsigned100 = Field(default=25, description="Grain size.")
    roughness: Unsigned100 = Field(default=50, description="Grain irregularity.")


class Effects(_Group):
    vignette: Vignette = Field(default_factory=Vignette)
    grain: Grain = Field(default_factory=Grain)


class CropRect(_Group):
    """Crop rectangle in normalized image coordinates (0..1), applied after rotation."""

    left: float = Field(default=0, ge=0, le=1)
    top: float = Field(default=0, ge=0, le=1)
    right: float = Field(default=1, ge=0, le=1)
    bottom: float = Field(default=1, ge=0, le=1)

    @model_validator(mode="after")
    def _non_empty(self) -> Self:
        if self.right - self.left < 0.01 or self.bottom - self.top < 0.01:
            raise ValueError(
                "crop rectangle must be at least 1% wide and tall, with left < right and top < bottom"
            )
        return self


class Geometry(_Group):
    crop: CropRect = Field(default_factory=CropRect)
    aspect: str | None = Field(
        default=None,
        pattern=r"^\d+(\.\d+)?:\d+(\.\d+)?$",
        description="Locked aspect ratio such as '4:5'. None = free.",
    )
    angle: float = Field(default=0, ge=-45, le=45, description="Straighten / rotate angle in degrees.")
    flip_horizontal: bool = False
    flip_vertical: bool = False


class Lens(_Group):
    profile_corrections: bool = Field(default=False, description="Apply lens distortion/vignetting profile.")
    remove_chromatic_aberration: bool = False


class AdjustmentGroup(StrEnum):
    WHITE_BALANCE = "white_balance"
    TONE = "tone"
    PRESENCE = "presence"
    TONE_CURVE = "tone_curve"
    HSL = "hsl"
    COLOR_GRADING = "color_grading"
    DETAIL = "detail"
    EFFECTS = "effects"
    GEOMETRY = "geometry"
    LENS = "lens"


class AdjustmentParams(_Group):
    """Complete set of global adjustments. All defaults = identity (no change)."""

    white_balance: WhiteBalance = Field(default_factory=WhiteBalance)
    tone: Tone = Field(default_factory=Tone)
    presence: Presence = Field(default_factory=Presence)
    tone_curve: ToneCurve = Field(default_factory=ToneCurve)
    hsl: Hsl = Field(default_factory=Hsl)
    color_grading: ColorGrading = Field(default_factory=ColorGrading)
    detail: Detail = Field(default_factory=Detail)
    effects: Effects = Field(default_factory=Effects)
    geometry: Geometry = Field(default_factory=Geometry)
    lens: Lens = Field(default_factory=Lens)

    def changed_fields(self) -> dict[str, object]:
        """Flat ``{"tone.exposure": 0.5, ...}`` of every value that differs from the neutral default."""
        neutral = AdjustmentParams().model_dump(by_alias=True)
        current = self.model_dump(by_alias=True)
        out: dict[str, object] = {}
        _diff(neutral, current, "", out)
        return out


def _diff(neutral: object, current: object, prefix: str, out: dict[str, object]) -> None:
    if isinstance(neutral, dict) and isinstance(current, dict):
        for key, value in current.items():
            _diff(neutral.get(key), value, f"{prefix}{key}.", out)
    elif neutral != current:
        out[prefix.rstrip(".")] = current
