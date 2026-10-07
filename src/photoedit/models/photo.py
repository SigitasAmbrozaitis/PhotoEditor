"""Photos in the library and their edits."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from photoedit.models.adjustments import AdjustmentParams


class Photo(BaseModel):
    """A source photo known to the catalog. The file itself is never modified."""

    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)

    id: str = Field(description="Stable catalog id.")
    path: str = Field(description="Absolute path of the original file (read-only).")
    filename: str
    folder: str
    file_size: int = Field(ge=0, description="Bytes.")
    captured_at: datetime | None = None
    camera: str | None = Field(default=None, description="Camera make and model, e.g. 'FUJIFILM X-T3'.")
    lens: str | None = None
    iso: int | None = Field(default=None, ge=1)
    shutter: str | None = Field(default=None, description="Exposure time as displayed, e.g. '1/250'.")
    aperture: float | None = Field(default=None, gt=0, description="f-number.")
    focal_length: float | None = Field(default=None, gt=0, description="Millimetres.")
    width: int = Field(ge=1, description="Pixel width after orientation.")
    height: int = Field(ge=1, description="Pixel height after orientation.")
    rating: int = Field(default=0, ge=0, le=5)
    style_id: str | None = Field(default=None, description="Style assigned to this photo, if any.")
    has_overrides: bool = Field(default=False, description="Per-photo adjustments on top of the style.")
    sidecar_jpeg: str | None = Field(
        default=None, description="Camera JPEG saved next to a RAW original (read-only), if any."
    )


class PhotoEdit(BaseModel):
    """The edit of one photo: an optional style plus per-photo overrides. Overrides always win."""

    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)

    photo_id: str
    style_id: str | None = None
    adjustments: AdjustmentParams = Field(
        default_factory=AdjustmentParams, description="Effective adjustments (style + overrides)."
    )
    overridden: list[str] = Field(
        default_factory=list,
        description="Dotted parameter names that are overridden per photo, e.g. 'tone.exposure'.",
    )


class PhotoDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)

    photo: Photo
    edit: PhotoEdit


class PhotoSort(StrEnum):
    DATE = "date"
    NAME = "name"
    RATING = "rating"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class LibraryInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)

    folder: str | None = Field(description="Currently opened photo folder.")
    include_subfolders: bool = Field(
        default=False, description="The Library also shows photos in subfolders."
    )
    photo_count: int = Field(ge=0)
    suggested_folder: str | None = Field(
        default=None, description="Folder to offer when nothing is open yet (the configured sample folder)."
    )


class LibraryFolder(BaseModel):
    """A folder that has been imported into the catalog."""

    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)

    path: str
    include_subfolders: bool
    photo_count: int = Field(ge=0)
    last_imported_at: datetime | None = None


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)

    folder: str = Field(min_length=1, description="Absolute path of the photo folder to import (read-only).")
    include_subfolders: bool = False


class OpenFolderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)

    folder: str = Field(min_length=1, description="An already imported folder to show in the Library.")
