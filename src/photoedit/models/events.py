"""Change events (P7.8): what the server tells open UIs when something changed, so they refetch it."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EventKind(StrEnum):
    PHOTO_EDIT = "photo_edit"  # a photo's edit file: adjustments, style, subject box, note
    SUBJECT = "subject"  # detection results stored for a photo
    STYLE = "style"
    PRESET = "preset"
    REVIEW = "review"  # a review or the review settings (ids empty)
    JOB = "job"
    LIBRARY = "library"  # folders imported, the open folder
    RESYNC = "resync"  # events were dropped (a slow listener): refetch everything


class Origin(StrEnum):
    """Which front-end caused a change."""

    UI = "ui"
    AI = "ai"
    CLI = "cli"


class ChangeEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", json_schema_serialization_defaults_required=True)

    seq: int = Field(ge=1, description="Increases by one per event, per server run.")
    kind: EventKind
    ids: list[str] = Field(
        default_factory=list, description="What changed: photo, style, preset, review or job ids."
    )
    origin: Origin
    summary: str | None = Field(default=None, description="A short line for people (jobs: title and status).")
