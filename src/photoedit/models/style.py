"""Styles: reusable looks applied to many photos."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from photoedit.models.adjustments import AdjustmentParams

STYLE_ID_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"


class StyleSample(BaseModel):
    """A before/after example showing the expected result of a style."""

    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)

    caption: str = ""
    before_url: str
    after_url: str


class StyleSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)

    id: str = Field(pattern=STYLE_ID_PATTERN, description="Slug, also the folder name under styles/.")
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=2000)
    cover_url: str | None = Field(default=None, description="Thumbnail of an 'after' sample.")
    updated_at: datetime


class Style(StyleSummary):
    best_for: list[str] = Field(default_factory=list, description="Scenes/subjects the style suits.")
    avoid_on: list[str] = Field(default_factory=list, description="Scenes/subjects the style handles badly.")
    adjustments: AdjustmentParams = Field(default_factory=AdjustmentParams)
    samples: list[StyleSample] = Field(default_factory=list)
    created_at: datetime
    version: int = Field(default=1, ge=1, description="Incremented on every saved change.")


class StyleView(Style):
    """API response for a style: the stored style plus derived, read-only information."""

    @computed_field(description="Parameters this style changes from neutral, as {dotted.name: value}.")  # type: ignore[prop-decorator]
    @property
    def changed_parameters(self) -> dict[str, Any]:
        return self.adjustments.changed_fields()


def style_view(style: Style) -> StyleView:
    return StyleView.model_validate(style.model_dump(by_alias=True))
