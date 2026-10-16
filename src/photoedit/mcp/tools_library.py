"""Library and seeing tools (P7.10): what is there, and what it looks like (images and numbers)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from mcp.server.mcpserver import Image, MCPServer
from pydantic import BaseModel, Field

from photoedit.core.errors import InvalidRequestError
from photoedit.mcp.common import (
    CHANGES,
    READ_ONLY,
    Folder,
    JobBrief,
    PhotoRef,
    PhotoRefs,
    Svc,
    jpeg,
    photo_id,
    photo_ids,
    tool,
)
from photoedit.models import (
    Job,
    JobStatus,
    LibraryFolder,
    LibraryInfo,
    Page,
    Photo,
    PhotoDetail,
    PhotoSort,
    SortOrder,
)
from photoedit.models.analysis import PhotoAnalysis

MAX_SHEET_PHOTOS = 24

Changes = Annotated[
    dict[str, Any] | None,
    Field(
        default=None,
        description="Unsaved changes to look at, as for update_adjustments: only the values to change, "
        'nested (e.g. {"tone": {"exposure": 0.3}}); null puts a value back to the style or default value. '
        "Nothing is saved.",
    ),
]


class LibraryStatus(BaseModel):
    open: LibraryInfo = Field(description="The folder the user's Library shows.")
    folders: list[LibraryFolder] = Field(description="Every imported folder.")
    engine: str = Field(description="The render engine's identity (part of every preview's cache key).")
    active_jobs: list[JobBrief] = Field(description="Jobs queued or running.")


def register(server: MCPServer[Any], svc: Svc) -> None:
    @tool(server, READ_ONLY)
    def library_status() -> LibraryStatus:
        """Start here: the imported folders, the one the user has open, and any running jobs."""
        services = svc()
        active = [j for j in services.jobs.list() if j.status in (JobStatus.QUEUED, JobStatus.RUNNING)]
        return LibraryStatus(
            open=services.library.info(),
            folders=services.library.folders(),
            engine=services.library.renderer.identity,
            active_jobs=[
                JobBrief(id=j.id, title=j.title, status=j.status, progress=j.progress) for j in active
            ],
        )

    @tool(server, CHANGES)
    def import_folder(
        folder: Annotated[str, Field(min_length=1, description="Full path of the folder to import.")],
        include_subfolders: bool = False,
    ) -> Job:
        """Add a folder's photos to the catalog (only reads them; also re-scans an imported folder) and open
        it in the user's Library. Returns a job: wait for it with get_job."""
        return svc().library.import_folder(Path(folder), include_subfolders=include_subfolders)

    @tool(server, CHANGES)
    def open_folder(
        folder: Annotated[str, Field(min_length=1, description="An imported folder.")],
    ) -> LibraryInfo:
        """Show an imported folder in the user's Library (what they see changes)."""
        return svc().library.open_folder(Path(folder))

    @tool(server, READ_ONLY)
    def list_photos(
        folder: Folder = None,
        style: Annotated[
            str | None, Field(default=None, description="Only photos with this style id; 'none' = no style.")
        ] = None,
        min_rating: Annotated[int, Field(ge=0, le=5)] = 0,
        sort: PhotoSort = PhotoSort.DATE,
        order: SortOrder = SortOrder.ASC,
        offset: Annotated[int, Field(ge=0)] = 0,
        limit: Annotated[int, Field(ge=1, le=200)] = 100,
    ) -> Page[Photo]:
        """Photos of a folder (default: the one open in the Library): id, file name, capture time, camera and
        exposure, style, whether it has its own tweaks."""
        return svc().library.list_photos(
            folder=Path(folder) if folder else None,
            style_id=style,
            min_rating=min_rating,
            sort=sort,
            order=order,
            offset=offset,
            limit=limit,
        )

    @tool(server, READ_ONLY)
    def get_photo(photo: PhotoRef) -> PhotoDetail:
        """Everything about one photo: EXIF, its style, its adjustments (and which are its own tweaks), the
        values before them, the style's rule results, the camera's white balance, and Claude's note."""
        return svc().library.photo_detail(photo_id(svc, photo))

    @tool(server, READ_ONLY)
    def render_preview(
        photo: PhotoRef,
        size: Annotated[int, Field(ge=256, le=1600, description="Long edge in pixels.")] = 1024,
        changes: Changes = None,
        before: Annotated[
            bool, Field(description="The photo's default look (no style, no tweaks) with the same framing.")
        ] = False,
    ) -> list[Image | str]:
        """See a photo: its current edit, or with unsaved ``changes`` (to try something before saving it),
        as a JPEG. Look before and after changing a photo."""
        library = svc().library
        pid = photo_id(svc, photo)
        name = library.photo(pid).path.name
        if changes is None:
            data = library.preview(pid, size, before=before)
            what = "default look" if before else "current edit"
        else:
            data = library.render_draft(pid, library.patched(pid, changes), size, before=before)
            what = "default look" if before else "unsaved changes"
        return [jpeg(data), f"{name}: {what}, {size} px long edge"]

    @tool(server, READ_ONLY)
    def contact_sheet(
        photos: PhotoRefs = [],  # noqa: B006 - the SDK copies arguments; a list default is the clearest schema
        folder: Folder = None,
        offset: Annotated[int, Field(ge=0, description="Skip this many of the photos first.")] = 0,
        limit: Annotated[int, Field(ge=1, le=MAX_SHEET_PHOTOS)] = MAX_SHEET_PHOTOS,
        size: Annotated[int, Field(ge=160, le=480, description="Long edge of each photo in pixels.")] = 320,
    ) -> list[Image | str]:
        """Several photos side by side in one image, each labeled with its file name: judge a series'
        consistency at a glance (after applying a style, before exporting)."""
        ids = photo_ids(svc, photos, folder)
        chosen = ids[offset : offset + limit]
        if not chosen:
            raise InvalidRequestError(f"offset {offset} is past the {len(ids)} photos")
        data = svc().library.series_sheet(chosen, size)
        rest = len(ids) - offset - len(chosen)
        more = f"; {rest} more after these (use offset {offset + len(chosen)})" if rest > 0 else ""
        return [jpeg(data), f"{len(chosen)} of {len(ids)} photos{more}"]

    @tool(server, READ_ONLY)
    def analyze_photo(photo: PhotoRef, changes: Changes = None) -> PhotoAnalysis:
        """Numbers about how a photo looks (its current edit, or with unsaved ``changes``): lightness
        histogram and percentiles, clipping, color cast, how colorful each HSL band is, the photo's measured
        tone and neutral white balance, and the detected subject. Read them next to render_preview."""
        services = svc()
        pid = photo_id(svc, photo)
        draft = services.library.patched(pid, changes) if changes is not None else None
        return services.analysis.analyze(pid, draft)
