"""Data models shared by the core, API, MCP server and UI (the API contract)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from photoedit.models.adjustments import AdjustmentGroup, AdjustmentParams
from photoedit.models.export import ExportPreset, ExportSettings
from photoedit.models.job import (
    ApplyAndExportRequest,
    ApplyStyleRequest,
    ExportRequest,
    Job,
    JobItem,
    JobKind,
    JobRequest,
    JobStatus,
)
from photoedit.models.photo import LibraryInfo, Photo, PhotoDetail, PhotoEdit, PhotoSort, SortOrder
from photoedit.models.style import Style, StyleSample, StyleSummary


class Page[T](BaseModel):
    """One page of a list result."""

    model_config = ConfigDict(extra="forbid")

    items: list[T]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)


__all__ = [
    "AdjustmentGroup",
    "AdjustmentParams",
    "ApplyAndExportRequest",
    "ApplyStyleRequest",
    "ExportPreset",
    "ExportRequest",
    "ExportSettings",
    "Job",
    "JobItem",
    "JobKind",
    "JobRequest",
    "JobStatus",
    "LibraryInfo",
    "Page",
    "Photo",
    "PhotoDetail",
    "PhotoEdit",
    "PhotoSort",
    "SortOrder",
    "Style",
    "StyleSample",
    "StyleSummary",
]
