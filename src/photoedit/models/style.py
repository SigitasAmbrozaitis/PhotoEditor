"""Styles: reusable looks applied to many photos."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from photoedit.models.adjustments import AdjustmentParams

STYLE_ID_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"


class StyleSample(BaseModel):
    """A before/after example showing the expected result of a style."""

    model_config = ConfigDict(extra="forbid")

    caption: str = ""
    before_url: str
    after_url: str


class StyleSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
