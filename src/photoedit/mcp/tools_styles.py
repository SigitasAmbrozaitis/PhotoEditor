"""Style tools (P7.12): read, write and apply styles. Deleting a style stays with the user (UI or CLI;
decided 2026-10-15); removing a style from photos is apply_style with no style."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from photoedit.mcp.common import CHANGES, READ_ONLY, Folder, PhotoRefs, Svc, photo_id, photo_ids, tool
from photoedit.models import ConsistencyReport, Job, StyleSummary, StyleView
from photoedit.models.style import (
    StyleCreate,
    StyleDiff,
    StyleFromPhoto,
    StyleUpdate,
    StyleUpdateFromPhoto,
    StyleVersionInfo,
    style_view,
)

StyleId = Annotated[str, Field(min_length=1, description="The style's id (from list_styles).")]
Version = Annotated[int, Field(ge=1)]


def register(server: MCPServer[Any], svc: Svc) -> None:
    def ids(refs: list[str]) -> list[str]:
        return [photo_id(svc, ref) for ref in refs]

    @tool(server, READ_ONLY)
    def list_styles() -> list[StyleSummary]:
        """The style library: id, name, description, version and how many photos use each style."""
        return svc().styling.summaries()

    @tool(server, READ_ONLY)
    def get_style(
        style: StyleId,
        version: Annotated[int | None, Field(default=None, ge=1, description="An older version.")] = None,
    ) -> StyleView:
        """A style: its values (dotted parameter names), adaptive rules, description, best for / avoid on,
        test photos and samples."""
        services = svc()
        if version is None:
            return services.styling.view(style)
        return style_view(services.styles.version(style, version))

    @tool(server, CHANGES)
    def create_style(request: StyleCreate) -> StyleView:
        """A new style from values (dotted names, e.g. {"tone.contrast": 15, "hsl.orange.saturation": -10})
        and rules. Test photos may be given by name."""
        return svc().styling.create(
            request.model_copy(update={"test_photo_ids": ids(request.test_photo_ids)})
        )

    @tool(server, CHANGES)
    def create_style_from_photo(request: StyleFromPhoto) -> StyleView:
        """A new style from a photo's current look (the chosen adjustment groups; its exposure and white
        balance become rules, so the style adapts to other photos). ``photo_id`` may be a name."""
        return svc().styling.create_from_photo(
            request.model_copy(update={"photo_id": photo_id(svc, request.photo_id)})
        )

    @tool(server, CHANGES)
    def update_style(style: StyleId, update: StyleUpdate) -> StyleView:
        """Change a style (only the fields given). ``expected_version`` must be its current version (from
        get_style), else nothing changes. Every photo using the style follows."""
        if update.test_photo_ids is not None:
            update = update.model_copy(update={"test_photo_ids": ids(update.test_photo_ids)})
        return svc().styling.update(style, update)

    @tool(server, CHANGES)
    def update_style_from_photo(style: StyleId, request: StyleUpdateFromPhoto) -> StyleView:
        """Replace the chosen groups of a style with a photo's current look (a new version)."""
        return svc().styling.update_from_photo(
            style, request.model_copy(update={"photo_id": photo_id(svc, request.photo_id)})
        )

    @tool(server, CHANGES)
    def duplicate_style(
        style: StyleId,
        name: Annotated[str | None, Field(default=None, min_length=1, max_length=80)] = None,
    ) -> StyleView:
        """A copy of a style to change without touching the original (default name: "<name> (copy)")."""
        return svc().styling.duplicate(style, name)

    @tool(server, CHANGES)
    def apply_style(
        style: Annotated[str | None, Field(description="The style's id; null removes the photos' style.")],
        photos: PhotoRefs = [],  # noqa: B006 - the SDK copies arguments; a list default is the clearest schema
        folder: Folder = None,
        even_out: Annotated[
            bool,
            Field(
                description="Bring the photos' exposure and white balance together (an inconsistent series)."
            ),
        ] = False,
    ) -> Job:
        """Give photos a style (writes edit files only; their own tweaks of what the style sets are replaced).
        Returns a job: wait with get_job, then look with contact_sheet."""
        return svc().styling.apply(photo_ids(svc, photos, folder), style, even_out=even_out)

    @tool(server, READ_ONLY)
    def style_report(
        style: StyleId,
        photos: PhotoRefs = [],  # noqa: B006
        folder: Folder = None,
    ) -> ConsistencyReport:
        """How consistent the style makes photos (default: its test set, else the photos using it): the spread
        of brightness and white balance before and after."""
        chosen = photo_ids(svc, photos, folder) if photos or folder else None
        return svc().styling.report(style, chosen)

    @tool(server, READ_ONLY)
    def style_history(style: StyleId) -> list[StyleVersionInfo]:
        """The style's saved versions, newest first."""
        return svc().styles.history(style)

    @tool(server, READ_ONLY)
    def style_diff(style: StyleId, a: Version, b: Version) -> StyleDiff:
        """What changed between two versions of a style."""
        return svc().styles.diff(style, a, b)

    @tool(server, CHANGES)
    def revert_style(style: StyleId, version: Version, expected_version: Version) -> StyleView:
        """Bring back an older version's look and text, as a new version (nothing is lost)."""
        return svc().styling.revert(style, version, expected_version=expected_version)

    @tool(server, CHANGES)
    def render_style_samples(
        style: StyleId,
        photos: Annotated[PhotoRefs, Field(min_length=1, max_length=12)],
    ) -> Job:
        """Render before/after samples of the style on library photos (shown on its card). A job."""
        return svc().styling.render_samples(style, ids(photos))
