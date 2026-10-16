"""Edit tools (P7.11): change photos' adjustments, framing and subject, and leave notes."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

from photoedit.core.edits import EffectiveEdit
from photoedit.mcp.common import (
    CHANGES,
    READ_ONLY,
    Folder,
    PhotoRef,
    PhotoRefs,
    Svc,
    photo_id,
    photo_ids,
    tool,
)
from photoedit.models import AdjustmentParams, Job
from photoedit.models.adjustments import Geometry, GeometryChange
from photoedit.models.crop import CropPlacement, CropSuggestion, CropSuggestionRequest
from photoedit.models.export import Orientation
from photoedit.models.photo import NOTE_MAX_LENGTH, PhotoNote
from photoedit.models.subject import SubjectBox, SubjectInfo


class EditResult(BaseModel):
    """A photo's edit after a change."""

    photo_id: str
    filename: str
    style_id: str | None
    own_tweaks: list[str] = Field(description="The parameters the photo sets itself (on top of its style).")
    geometry: Geometry
    revision: str = Field(description="Changes whenever the edit changes.")


def register(server: MCPServer[Any], svc: Svc) -> None:
    def result(pid: str, edit: EffectiveEdit) -> EditResult:
        return EditResult(
            photo_id=pid,
            filename=svc().library.photo(pid).path.name,
            style_id=edit.style_id,
            own_tweaks=edit.overridden,
            geometry=edit.adjustments.geometry,
            revision=edit.revision,
        )

    @tool(server, CHANGES)
    def update_adjustments(
        changes: Annotated[
            dict[str, Any],
            Field(
                description="Only the values to change, nested like get_photo's adjustments, e.g. "
                '{"tone": {"exposure": 0.3, "shadows": 20}, "hsl": {"orange": {"saturation": -10}}}. '
                "null puts a value back to the style or default value."
            ),
        ],
        photos: PhotoRefs = [],  # noqa: B006 - the SDK copies arguments; a list default is the clearest schema
        folder: Folder = None,
    ) -> list[EditResult]:
        """Change some adjustments of one or more photos (the same change for each), keeping everything else.
        Every value is checked first: if one is rejected, nothing is saved."""
        library = svc().library
        ids = photo_ids(svc, photos, folder)
        planned = [(pid, library.patched(pid, changes)) for pid in ids]
        return [result(pid, library.save_edit(pid, adjustments)) for pid, adjustments in planned]

    @tool(server, CHANGES)
    def set_adjustments(photo: PhotoRef, adjustments: AdjustmentParams) -> EditResult:
        """Replace a photo's whole set of adjustments (what differs from its style is kept as its own tweaks).
        Prefer update_adjustments for a few values."""
        pid = photo_id(svc, photo)
        return result(pid, svc().library.save_edit(pid, adjustments))

    @tool(server, CHANGES)
    def reset_adjustments(
        photos: PhotoRefs = [],  # noqa: B006
        folder: Folder = None,
    ) -> list[EditResult]:
        """Drop the photos' own tweaks; their style stays (apply_style with no style removes it)."""
        library = svc().library
        return [result(pid, library.reset_edit(pid)) for pid in photo_ids(svc, photos, folder)]

    @tool(server, CHANGES)
    def set_geometry(photo: PhotoRef, change: GeometryChange) -> EditResult:
        """Change a photo's framing: crop, straighten angle, aspect lock, quarter turn, flips (only the fields
        given). Flips and turns carry the crop along; after an angle or aspect change the crop shrinks to fit.
        A crop reaching outside the straightened photo is rejected."""
        pid = photo_id(svc, photo)
        return result(pid, svc().library.set_geometry(pid, change))

    @tool(server, READ_ONLY)
    def suggest_crop(
        photo: PhotoRef,
        aspect: Annotated[str, Field(pattern=r"^\d+(\.\d+)?:\d+(\.\d+)?$", description="Ratio, e.g. '4:5'.")],
        orientation: Orientation = Orientation.AUTO,
        placement: CropPlacement = CropPlacement.CENTERED,
        zoom: Annotated[float, Field(ge=1, le=10, description="1 = largest; higher = tighter.")] = 1.0,
    ) -> CropSuggestion:
        """A crop of the ratio framing the photo's subject, in its current framing (flips, turn, angle).
        Nothing is saved: apply it with set_geometry ({"crop": ...})."""
        services = svc()
        pid = photo_id(svc, photo)
        request = CropSuggestionRequest(
            geometry=services.library.edit(pid).adjustments.geometry,
            aspect=aspect,
            orientation=orientation,
            placement=placement,
            zoom=zoom,
        )
        return services.subjects.suggest_crop(services.library.photo(pid), request)

    @tool(server, READ_ONLY)
    def get_subject(photo: PhotoRef) -> SubjectInfo:
        """The photo's main subject: the box set by hand, else the detected one (detection runs now if it
        hasn't, a few seconds the first time)."""
        services = svc()
        return services.subjects.subject(services.library.photo(photo_id(svc, photo)))

    @tool(server, CHANGES)
    def set_subject(
        photo: PhotoRef,
        box: Annotated[
            SubjectBox | None,
            Field(
                description="The subject in the upright photo (0..1 from left/top); null = the detected one."
            ),
        ],
    ) -> SubjectInfo:
        """Set the photo's main subject by hand (it frames subject crops and exports), or go back to the
        detected one. Changes no pixels."""
        services = svc()
        return services.subjects.set_manual(services.library.photo(photo_id(svc, photo)), box)

    @tool(server, CHANGES)
    def detect_subjects(
        photos: PhotoRefs = [],  # noqa: B006
        folder: Folder = None,
    ) -> Job:
        """Find the subjects of photos that haven't been analysed yet (a job, ~6 s per photo the first time).
        The results show in get_subject, analyze_photo and the user's AI Analysis tab."""
        return svc().subjects.detect_job(photo_ids(svc, photos, folder))

    @tool(server, CHANGES)
    def set_note(
        photo: PhotoRef,
        text: Annotated[
            str | None, Field(max_length=NOTE_MAX_LENGTH, description="The note; null removes it.")
        ],
    ) -> PhotoNote | None:
        """Leave a note about a photo for the user (what you saw, what you changed and why); it shows in the
        photo's AI Analysis tab. Replaces the previous note. Changes no pixels."""
        return svc().library.set_note(photo_id(svc, photo), text)
