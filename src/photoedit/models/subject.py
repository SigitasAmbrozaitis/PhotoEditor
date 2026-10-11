"""Subjects (Phase 6b): a photo's main subject and the candidates found (crops suggested around it are in
``models.crop``).

Subject boxes are in **upright photo coordinates**: 0..1 of the photo as shot (after the camera orientation,
before any flip, turn, straighten or crop). Detection doesn't depend on the edit, and a flip or turn never has
to move a box. Core maps a box into an edited frame when it needs to.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

# A box must be at least this wide and tall (fraction of the photo): 12 px of a 6000 px photo, smaller than
# any subject worth framing but above float noise.
MIN_BOX_SIZE = 0.002


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


class SubjectBox(_Model):
    """A box in normalized coordinates (0..1): of the upright photo, unless a field says otherwise."""

    model_config = ConfigDict(frozen=True)

    left: float = Field(ge=0, le=1)
    top: float = Field(ge=0, le=1)
    right: float = Field(ge=0, le=1)
    bottom: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _non_empty(self) -> Self:
        if self.right - self.left < MIN_BOX_SIZE or self.bottom - self.top < MIN_BOX_SIZE:
            raise ValueError(
                f"subject box must be at least {MIN_BOX_SIZE:.1%} wide and tall, with left < right and "
                "top < bottom"
            )
        return self

    @property
    def center(self) -> tuple[float, float]:
        return (self.left + self.right) / 2, (self.top + self.bottom) / 2


class SubjectKind(StrEnum):
    CAR = "car"  # car, truck, bus
    MOTORCYCLE = "motorcycle"  # motorcycle, bicycle
    AIRCRAFT = "aircraft"  # airplane (helicopters are labeled as airplanes)
    ANIMAL = "animal"  # cat, dog, bird, horse...
    PERSON = "person"
    FACE = "face"
    SALIENT = "salient"  # stands out by sharpness or saliency, nothing recognized
    AF_POINT = "af_point"  # where the camera focused


class SubjectSource(StrEnum):
    DETECTED = "detected"
    MANUAL = "manual"  # set by the user or the AI; always wins
    AF_POINT = "af_point"  # nothing detected; the camera's focus point
    NONE = "none"


class SubjectCandidate(_Model):
    box: SubjectBox
    kind: SubjectKind
    score: float = Field(ge=0, le=1, description="How likely this is the photo's main subject.")
    label: str | None = Field(default=None, description="What the detector called it, e.g. 'truck'.")


class SubjectInfo(_Model):
    """A photo's main subject: a manual box, the detected one, the AF point, or none."""

    source: SubjectSource
    box: SubjectBox | None = None
    kind: SubjectKind | None = None
    score: float | None = Field(default=None, ge=0, le=1)
    candidates: list[SubjectCandidate] = Field(
        default_factory=list, description="Everything found, best first (the main subject included)."
    )
    detector: str | None = Field(default=None, description="Identity of the detector that found them.")
    notes: list[str] = Field(default_factory=list, description="E.g. that the detector model is missing.")

    @model_validator(mode="after")
    def _box_matches_source(self) -> Self:
        if (self.box is None) != (self.source is SubjectSource.NONE):
            raise ValueError("a subject has a box exactly when its source isn't 'none'")
        return self


class SubjectUpdate(_Model):
    """Set the photo's subject by hand (upright coordinates), or ``null`` to use the detected one."""

    box: SubjectBox | None
