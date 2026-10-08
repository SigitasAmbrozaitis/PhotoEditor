"""Folder browser listings (read-only views of the file system)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DirEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)

    name: str
    path: str
    photo_count: int | None = Field(
        default=None, ge=0, description="Photos directly in this folder; None if it can't be read."
    )


class DirListing(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)

    path: str | None = Field(description="The listed folder; None for the list of drives.")
    parent: str | None = Field(description="Folder one level up; None at a drive root or the drive list.")
    photo_count: int = Field(ge=0, description="Photos directly in the listed folder.")
    entries: list[DirEntry]
