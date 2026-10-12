"""Suggested crops (Phase 6b): a crop of a ratio framed on the photo's subject."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from photoedit.models.adjustments import CropRect, Geometry
from photoedit.models.export import Orientation
from photoedit.models.subject import SubjectBox, SubjectKind, SubjectSource


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


class CropPlacement(StrEnum):
    CENTERED = "centered"  # the subject as close to the crop's center as the frame allows
    THIRDS = "thirds"  # the subject's center on the nearest thirds intersection


class CropSuggestionRequest(_Model):
    geometry: Geometry = Field(
        default_factory=Geometry,
        description="The geometry to suggest in (the crop tool's draft); its flips, turn and angle are kept.",
    )
    aspect: str = Field(pattern=r"^\d+(\.\d+)?:\d+(\.\d+)?$", description="Crop ratio, e.g. '4:5'.")
    orientation: Orientation = Field(
        default=Orientation.AUTO, description="auto = the frame's orientation; otherwise force the ratio's."
    )
    placement: CropPlacement = CropPlacement.CENTERED
    zoom: float = Field(
        default=1.0, ge=1, le=10, description="1 = the largest crop; higher = tighter around the subject."
    )


class CropSuggestion(_Model):
    crop: CropRect = Field(description="The suggested crop, normalized to the frame of the given geometry.")
    aspect: str = Field(description="The ratio used, turned to the chosen orientation (e.g. '5:4').")
    placement: CropPlacement
    zoom: float = Field(description="The zoom actually used (capped where the subject plus margin fills it).")
    source: SubjectSource
    kind: SubjectKind | None = None
    subject: SubjectBox | None = Field(
        default=None, description="The subject used, normalized to the frame of the given geometry."
    )
    warnings: list[str] = Field(default_factory=list)
