"""Export, review and job tools (P7.13). Exports go to the folder the call names (decided 2026-10-15), checked
like the UI's: never inside a photo folder or the tool's own folders. Deleting presets and discarding reviews
stay with the user."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.mcpserver import Image, MCPServer
from pydantic import Field

from photoedit.core.errors import InvalidRequestError
from photoedit.mcp.common import (
    CHANGES,
    READ_ONLY,
    Folder,
    JobBrief,
    PhotoRef,
    PhotoRefs,
    Svc,
    brief,
    jpeg,
    photo_id,
    photo_ids,
    tool,
)
from photoedit.models import ExportPreset, Job
from photoedit.models.export import ExportPlan, ExportSettings, PresetCreate, PresetUpdate
from photoedit.models.review import (
    ExportReview,
    ReviewExportScope,
    ReviewItemUpdate,
    ReviewSettings,
    ReviewSubjectUpdate,
    ReviewSummary,
)

MAX_WAIT = 120  # s a get_job call may wait for its job to end

PresetId = Annotated[
    str, Field(min_length=1, description="An export preset's id (from list_export_presets).")
]
Preset = Annotated[
    str | None,
    Field(
        default=None, description="An export preset's id; its settings are used unless `settings` is given."
    ),
]
Settings = Annotated[
    ExportSettings | None,
    Field(
        default=None, description="Full export settings (e.g. a preset's, changed); default: the preset's."
    ),
]
Destination = Annotated[
    str,
    Field(
        min_length=1,
        description="The folder to write to (full path; created if missing). Never a photo folder.",
    ),
]
ReviewId = Annotated[str, Field(min_length=1, description="A review's id (from list_reviews or its job).")]


def register(server: MCPServer[Any], svc: Svc) -> None:
    def settings_of(preset: str | None, settings: ExportSettings | None) -> ExportSettings:
        if settings is not None:
            return settings
        if preset is None:
            raise InvalidRequestError("give a preset or the export settings")
        return svc().presets.get(preset).settings

    # ---- presets

    @tool(server, READ_ONLY)
    def list_export_presets() -> list[ExportPreset]:
        """Export presets (built-in: Instagram, prints, web; plus the user's own) with their settings."""
        return svc().presets.all()

    @tool(server, READ_ONLY)
    def get_export_preset(preset: PresetId) -> ExportPreset:
        """One export preset with all its settings."""
        return svc().presets.get(preset)

    @tool(server, CHANGES)
    def create_export_preset(request: PresetCreate) -> ExportPreset:
        """A new custom export preset."""
        return svc().presets.create(request)

    @tool(server, CHANGES)
    def update_export_preset(preset: PresetId, update: PresetUpdate) -> ExportPreset:
        """Change a custom preset (built-ins can't be changed: create a preset from their settings).
        ``expected_version`` must be its current version."""
        return svc().presets.update(preset, update)

    # ---- export

    @tool(server, READ_ONLY)
    def plan_export(
        destination: Destination,
        photos: PhotoRefs = [],  # noqa: B006 - the SDK copies arguments; a list default is the clearest schema
        folder: Folder = None,
        preset: Preset = None,
        settings: Settings = None,
    ) -> ExportPlan:
        """What an export would write, without writing: per photo the file name, pixel size, framing, subject
        and warnings (enlarged, name taken…). Check it before export_photos."""
        return svc().exporter.plan(
            photo_ids(svc, photos, folder), settings_of(preset, settings), destination, preset
        )

    @tool(server, CHANGES)
    def export_photos(
        destination: Destination,
        photos: PhotoRefs = [],  # noqa: B006
        folder: Folder = None,
        preset: Preset = None,
        settings: Settings = None,
    ) -> Job:
        """Render and write the photos' files into ``destination`` (a job; wait with get_job). Photos whose
        subject is uncertain are better sent through prepare_export, where the user decides."""
        return svc().exporter.export(
            photo_ids(svc, photos, folder), settings_of(preset, settings), destination, preset
        )

    # ---- pre-export review

    @tool(server, CHANGES)
    def prepare_export(
        destination: Destination,
        photos: PhotoRefs = [],  # noqa: B006
        folder: Folder = None,
        preset: Preset = None,
        settings: Settings = None,
        style: Annotated[
            str | None,
            Field(default=None, description="A style to apply first (written to the photos' edits)."),
        ] = None,
        even_out: bool = False,
    ) -> Job:
        """Prepare an export for the user's review: detect subjects, frame each photo, sort them into Ready
        and Check (with reasons). A job; when it ends its ``review_id`` names the review (see get_review),
        which the user also sees in the UI under Reviews."""
        return svc().reviews.prepare(
            photo_ids(svc, photos, folder),
            settings_of(preset, settings),
            destination,
            preset_id=preset,
            style_id=style,
            even_out=even_out,
        )

    @tool(server, READ_ONLY)
    def list_reviews() -> list[ReviewSummary]:
        """Open reviews: destination, preset, counts of Ready / Check / approved."""
        return svc().reviews.summaries()

    @tool(server, READ_ONLY)
    def get_review(review: ReviewId) -> ExportReview:
        """A review, refreshed against the photos' current edits: per photo its status (ready, check,
        unusable), the reasons, the subject and candidates, the framing, zoom and approval."""
        return svc().reviews.get(review)

    @tool(server, CHANGES)
    def update_review_item(review: ReviewId, photo: PhotoRef, update: ReviewItemUpdate) -> ExportReview:
        """Set a photo's zoom (null = automatic) or frame position, or approve it. A zoom or position is a
        decision, so it approves the photo."""
        return svc().reviews.update_item(review, photo_id(svc, photo), update)

    @tool(server, CHANGES)
    def set_review_subject(review: ReviewId, photo: PhotoRef, update: ReviewSubjectUpdate) -> ExportReview:
        """Choose one of the photo's candidates as its subject, draw a box, or go back to the detected one
        ({"box": null}); saved to the photo's edit, and the photo is approved."""
        return svc().reviews.set_subject(review, photo_id(svc, photo), update)

    @tool(server, READ_ONLY)
    def review_preview(review: ReviewId, photo: PhotoRef) -> list[Image | str]:
        """The photo framed as the review's export will frame it (800 px)."""
        pid = photo_id(svc, photo)
        return [jpeg(svc().reviews.preview(review, pid)), f"{svc().library.photo(pid).path.name} as exported"]

    @tool(server, CHANGES)
    def export_review(review: ReviewId, scope: ReviewExportScope = ReviewExportScope.APPROVED) -> Job:
        """Export a review's photos: ``approved`` (Ready + approved Check photos) or ``all`` (also the Check
        photos not approved, with the tool's framing: ask the user first). Exported photos leave the
        review."""
        return svc().reviews.export(review, scope)

    @tool(server, READ_ONLY)
    def get_review_settings() -> ReviewSettings:
        """The review rules: which checks are on and their thresholds (minimum score, ambiguity)."""
        return svc().reviews.settings()

    @tool(server, CHANGES)
    def set_review_settings(settings: ReviewSettings) -> ReviewSettings:
        """Change the review rules (the whole set); open reviews are sorted again."""
        return svc().reviews.set_settings(settings)

    # ---- jobs

    @tool(server, READ_ONLY)
    def list_jobs() -> list[JobBrief]:
        """Recent jobs, newest first."""
        return [brief(job) for job in svc().jobs.list()]

    @tool(server, READ_ONLY)
    def get_job(
        job: Annotated[str, Field(min_length=1)],
        wait_seconds: Annotated[
            int, Field(ge=0, le=MAX_WAIT, description="Wait up to this long for the job to end (0 = now).")
        ] = 0,
    ) -> Job:
        """A job's state, progress, summary and each item's result (files written, failures). With
        ``wait_seconds`` it returns as soon as the job ends, or with its progress when the time is up."""
        jobs = svc().jobs
        if wait_seconds:
            try:
                return jobs.wait(job, wait_seconds)
            except TimeoutError:
                pass
        return jobs.get(job)

    @tool(server, CHANGES)
    def cancel_job(job: Annotated[str, Field(min_length=1)]) -> Job:
        """Stop a job: items not started are cancelled, running ones finish."""
        return svc().jobs.cancel(job)
