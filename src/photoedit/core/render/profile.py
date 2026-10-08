"""Camera profiles: the default look of an unedited photo (like Lightroom's camera profiles).

A profile is applied before the user's adjustments: baseline exposure and a color matrix on scene-linear data,
then its tone curve takes scene-linear values to display values, and its HSL tweaks shape individual colors.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from photoedit.models.adjustments import Hsl

Row = tuple[float, float, float]
IDENTITY: tuple[Row, Row, Row] = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


class ProfileCurvePoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    stops: float = Field(ge=-16, le=10, description="Scene brightness in stops relative to 18 % gray.")
    value: float = Field(ge=0, le=1, description="Display value (sRGB-encoded) it maps to.")


class CameraProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str
    make: str | None = None
    model: str | None = None
    film_simulation: str | None = None
    baseline_exposure: float = Field(default=0, ge=-4, le=4, description="EV added before everything else.")
    matrix: tuple[Row, Row, Row] = Field(default=IDENTITY, description="Linear Rec.2020 → linear Rec.2020.")
    tone_curve: list[ProfileCurvePoint] = Field(min_length=4, max_length=64)
    hsl: Hsl = Field(default_factory=Hsl)

    @model_validator(mode="after")
    def _monotone_curve(self) -> Self:
        for a, b in pairwise(self.tone_curve):
            if b.stops <= a.stops:
                raise ValueError("profile tone curve: stops must be strictly increasing")
            if b.value < a.value:
                raise ValueError("profile tone curve: values must not decrease")
        if any(abs(v) > 4 for row in self.matrix for v in row):
            raise ValueError("profile matrix: entries must be within ±4")
        return self


def _curve(points: list[tuple[float, float]]) -> list[ProfileCurvePoint]:
    return [ProfileCurvePoint(stops=s, value=v) for s, v in points]


# A gentle S-curve with a highlight shoulder: mid gray lands at ~0.465 (plain sRGB encoding gives
# 0.461), darks get a little deeper and brights roll off over ~5 stops instead of clipping at +2.5.
GENERIC = CameraProfile(
    id="generic",
    name="Generic",
    tone_curve=_curve(
        [
            (-12, 0.0),
            (-8, 0.01),
            (-6, 0.03),
            (-4, 0.085),
            (-2, 0.22),
            (-1, 0.33),
            (0, 0.465),
            (1, 0.61),
            (2, 0.76),
            (3, 0.875),
            (4, 0.945),
            (5, 0.985),
            (6, 1.0),
        ]
    ),
)
