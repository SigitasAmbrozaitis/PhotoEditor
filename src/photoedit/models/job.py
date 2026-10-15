"""Background jobs (apply style, export, ...)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from photoedit.models.export import ExportSettings


class JobKind(StrEnum):
    IMPORT = "import"
    RENDER = "render"
    APPLY_STYLE = "apply_style"
    EXPORT = "export"
    APPLY_AND_EXPORT = "apply_and_export"
    DETECT_SUBJECTS = "detect_subjects"
    PREPARE_EXPORT = "prepare_export"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobItem(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)

    photo_id: str | None = Field(description="None while an import hasn't identified the file yet.")
    filename: str
    status: JobStatus
    message: str | None = None
    output_path: str | None = None
    output_bytes: int | None = Field(default=None, ge=0, description="Size of the written file (exports).")
    output_width: int | None = Field(default=None, ge=1)
    output_height: int | None = Field(default=None, ge=1)
    warnings: list[str] = Field(default_factory=list)


class Job(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)

    id: str
    kind: JobKind
    status: JobStatus
    title: str = Field(description="Human-readable summary, e.g. 'Apply Moody Forest to 12 photos'.")
    created_at: datetime
    finished_at: datetime | None = None
    progress: float = Field(ge=0, le=1)
    total: int = Field(ge=0)
    completed: int = Field(ge=0)
    failed: int = Field(default=0, ge=0)
    style_id: str | None = None
    preset_id: str | None = None
    destination: str | None = None
    folder: str | None = Field(default=None, description="Photo folder an import job reads (read-only).")
    summary: str | None = Field(default=None, description="Outcome in one line, e.g. '67 new, 1 skipped'.")
    review_id: str | None = Field(default=None, description="The review a prepare_export job created.")
    items: list[JobItem] = Field(default_factory=list)


class _JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)

    photo_ids: list[str] = Field(min_length=1, max_length=10000)


class ApplyStyleRequest(_JobRequest):
    kind: Literal[JobKind.APPLY_STYLE] = JobKind.APPLY_STYLE
    style_id: str | None = Field(description="None removes the style from the photos.")
    even_out: bool = Field(
        default=False,
        description="Store the selection's median as each photo's group reference, so the style's exposure "
        "rule evens the photos out against each other.",
    )


class ExportRequest(_JobRequest):
    kind: Literal[JobKind.EXPORT] = JobKind.EXPORT
    preset_id: str | None = Field(default=None, description="Preset the settings started from (for display).")
    settings: ExportSettings
    destination: str = Field(min_length=1)


class ApplyAndExportRequest(_JobRequest):
    kind: Literal[JobKind.APPLY_AND_EXPORT] = JobKind.APPLY_AND_EXPORT
    style_id: str
    even_out: bool = False
    preset_id: str | None = None
    settings: ExportSettings
    destination: str = Field(min_length=1)


class DetectSubjectsRequest(_JobRequest):
    """Detect the photos' main subjects in the background (stored; photos already detected are skipped)."""

    kind: Literal[JobKind.DETECT_SUBJECTS] = JobKind.DETECT_SUBJECTS


class PrepareExportRequest(_JobRequest):
    """Prepare an export for review (Phase 6c): optionally apply a style first, then frame and sort every
    photo into Ready and Check. The job's ``review_id`` names the review."""

    kind: Literal[JobKind.PREPARE_EXPORT] = JobKind.PREPARE_EXPORT
    style_id: str | None = Field(default=None, description="Apply this style first; None = keep the edits.")
    even_out: bool = False
    preset_id: str | None = None
    settings: ExportSettings
    destination: str = Field(min_length=1)

    @model_validator(mode="after")
    def _even_out_needs_style(self) -> Self:
        if self.even_out and self.style_id is None:
            raise ValueError("even_out needs a style")
        return self


JobRequest = Annotated[
    ApplyStyleRequest | ExportRequest | ApplyAndExportRequest | DetectSubjectsRequest | PrepareExportRequest,
    Field(discriminator="kind"),
]
