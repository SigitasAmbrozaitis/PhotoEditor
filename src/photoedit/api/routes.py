"""JSON + image routes under /api. Thin: validation and translation only, logic lives in the core."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends, Query, Request, Response, status

from photoedit.core.fs import list_dirs
from photoedit.core.render.pipeline import LATER_PHASE_PARAMETERS
from photoedit.models import (
    AdjustmentParams,
    ApplyAndExportRequest,
    ConsistencyReport,
    EngineInfo,
    ExportPreset,
    ExportRequest,
    ImportRequest,
    Job,
    JobRequest,
    LibraryFolder,
    LibraryInfo,
    OpenFolderRequest,
    Page,
    Photo,
    PhotoDetail,
    PhotoSort,
    SortOrder,
    StyleSummary,
    StyleView,
)
from photoedit.models.adjustments import Geometry, GeometryChange, GeometryPreviewRequest
from photoedit.models.crop import CropSuggestion, CropSuggestionRequest
from photoedit.models.export import (
    DestinationCheck,
    DestinationCheckRequest,
    ExportPlan,
    PresetCreate,
    PresetDuplicate,
    PresetUpdate,
    RevealRequest,
)
from photoedit.models.fs import DirListing
from photoedit.models.job import DetectSubjectsRequest, PrepareExportRequest
from photoedit.models.photo import ZoomInfo, ZoomLevel
from photoedit.models.review import (
    ExportReview,
    ReviewExportRequest,
    ReviewItemUpdate,
    ReviewSettings,
    ReviewSubjectUpdate,
    ReviewSummary,
)
from photoedit.models.style import (
    PhotoStyleRequest,
    StyleCreate,
    StyleDeleted,
    StyleDiff,
    StyleDuplicate,
    StyleFromPhoto,
    StyleReportRequest,
    StyleRevert,
    StyleSamplesRequest,
    StyleUpdate,
    StyleUpdateFromPhoto,
    StyleVersionInfo,
    style_view,
)
from photoedit.models.subject import SubjectInfo, SubjectUpdate
from photoedit.services import Services

JPEG = "image/jpeg"
IMAGE_RESPONSE: dict[int | str, dict[str, Any]] = {200: {"content": {JPEG: {}}, "description": "JPEG image"}}
# Photo images are addressed by content-hash id and the decoder's render identity is part of the cache, so a
# URL's bytes only change when the decoder changes; a short browser cache keeps the grid snappy.
IMAGE_CACHE = {"Cache-Control": "private, max-age=600"}


def get_services(request: Request) -> Services:
    services: Services = request.app.state.services()
    return services


Svc = Annotated[Services, Depends(get_services)]

router = APIRouter(prefix="/api")


# ----------------------------------------------------------------- library / photos


@router.get("/library", response_model=LibraryInfo, tags=["library"])
def library(svc: Svc) -> LibraryInfo:
    return svc.library.info()


@router.get("/library/folders", response_model=list[LibraryFolder], tags=["library"])
def library_folders(svc: Svc) -> list[LibraryFolder]:
    return svc.library.folders()


@router.put("/library/current", response_model=LibraryInfo, tags=["library"])
def open_folder(request: Annotated[OpenFolderRequest, Body()], svc: Svc) -> LibraryInfo:
    return svc.library.open_folder(Path(request.folder))


@router.post("/library/import", response_model=Job, status_code=status.HTTP_201_CREATED, tags=["library"])
def import_folder(request: Annotated[ImportRequest, Body()], svc: Svc) -> Job:
    return svc.library.import_folder(Path(request.folder), include_subfolders=request.include_subfolders)


@router.get("/fs/dirs", response_model=DirListing, tags=["library"])
def fs_dirs(
    path: Annotated[str | None, Query(description="Folder to list; omit for the drives.")] = None,
) -> DirListing:
    return list_dirs(Path(path) if path else None)


@router.get("/photos", response_model=Page[Photo], tags=["library"])
def list_photos(
    svc: Svc,
    style_id: Annotated[
        str | None, Query(description="Filter by style id; 'none' = photos without a style.")
    ] = None,
    min_rating: Annotated[int, Query(ge=0, le=5)] = 0,
    sort: PhotoSort = PhotoSort.DATE,
    order: SortOrder = SortOrder.ASC,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> Page[Photo]:
    return svc.library.list_photos(
        style_id=style_id, min_rating=min_rating, sort=sort, order=order, offset=offset, limit=limit
    )


@router.get("/photos/{photo_id}", response_model=PhotoDetail, tags=["library"])
def photo_detail(photo_id: str, svc: Svc) -> PhotoDetail:
    return svc.library.photo_detail(photo_id)


@router.get("/photos/{photo_id}/sidecar", response_class=Response, responses=IMAGE_RESPONSE, tags=["library"])
def photo_sidecar(
    photo_id: str,
    svc: Svc,
    size: Annotated[int, Query(ge=256, le=4096, description="Long edge in pixels.")] = 1600,
) -> Response:
    """The camera's own JPEG of a RAW (if it saved one), for comparing with the default look."""
    return Response(content=svc.library.sidecar(photo_id, size), media_type=JPEG, headers=IMAGE_CACHE)


@router.put("/photos/{photo_id}/edit", response_model=PhotoDetail, tags=["edit"])
def save_edit(photo_id: str, adjustments: Annotated[AdjustmentParams, Body()], svc: Svc) -> PhotoDetail:
    """Save a photo's adjustments (the full set; only what differs from the defaults is stored)."""
    svc.library.save_edit(photo_id, adjustments)
    return svc.library.photo_detail(photo_id)


@router.post("/photos/{photo_id}/geometry", response_model=PhotoDetail, tags=["edit"])
def change_geometry(photo_id: str, change: Annotated[GeometryChange, Body()], svc: Svc) -> PhotoDetail:
    """Change the photo's crop, straighten angle, aspect lock, quarter turn or flips (only the fields given).
    Flips and turns carry the crop along; after an angle or aspect change the crop shrinks to fit the
    straightened photo. An explicit crop that reaches outside it is rejected."""
    svc.library.set_geometry(photo_id, change)
    return svc.library.photo_detail(photo_id)


@router.post("/photos/{photo_id}/geometry/preview", response_model=Geometry, tags=["edit"])
def preview_geometry(photo_id: str, request: Annotated[GeometryPreviewRequest, Body()], svc: Svc) -> Geometry:
    """The geometry a change would give, starting from ``geometry`` (e.g. the crop tool's draft). Nothing is
    saved; save it with PUT /edit."""
    return svc.library.preview_geometry(photo_id, request.geometry, request.change)


@router.get("/photos/{photo_id}/subject", response_model=SubjectInfo, tags=["edit"])
def photo_subject(photo_id: str, svc: Svc) -> SubjectInfo:
    """The photo's main subject: the box set by hand, else the detected one (detected now if needed, which
    takes a few seconds the first time)."""
    return svc.subjects.subject(svc.library.photo(photo_id))


@router.put("/photos/{photo_id}/subject", response_model=SubjectInfo, tags=["edit"])
def set_photo_subject(photo_id: str, request: Annotated[SubjectUpdate, Body()], svc: Svc) -> SubjectInfo:
    """Set the subject by hand (upright photo coordinates), or ``{"box": null}`` to use the detected one.
    Changes no pixels: the edit's revision and its previews stay."""
    return svc.subjects.set_manual(svc.library.photo(photo_id), request.box)


@router.post("/photos/{photo_id}/suggest-crop", response_model=CropSuggestion, tags=["edit"])
def suggest_crop(
    photo_id: str, request: Annotated[CropSuggestionRequest, Body()], svc: Svc
) -> CropSuggestion:
    """A crop of the ratio framing the photo's subject, in the frame of the given (draft) geometry. Nothing
    is saved."""
    return svc.subjects.suggest_crop(svc.library.photo(photo_id), request)


@router.put("/photos/{photo_id}/style", response_model=PhotoDetail, tags=["edit"])
def set_photo_style(photo_id: str, request: Annotated[PhotoStyleRequest, Body()], svc: Svc) -> PhotoDetail:
    """Give the photo a style right away (null removes it). Tweaks of what the style sets are replaced."""
    svc.styling.set_photo_style(photo_id, request.style_id)
    return svc.library.photo_detail(photo_id)


@router.delete("/photos/{photo_id}/edit", response_model=PhotoDetail, tags=["edit"])
def reset_edit(photo_id: str, svc: Svc) -> PhotoDetail:
    """Drop the photo's own tweaks (its style stays; PUT /style with null removes the style)."""
    svc.library.reset_edit(photo_id)
    return svc.library.photo_detail(photo_id)


@router.get("/engine", response_model=EngineInfo, tags=["edit"])
def engine(svc: Svc) -> EngineInfo:
    return EngineInfo(
        render_identity=svc.library.renderer.identity, later_phase_parameters=dict(LATER_PHASE_PARAMETERS)
    )


@router.get(
    "/photos/{photo_id}/thumbnail", response_class=Response, responses=IMAGE_RESPONSE, tags=["library"]
)
def photo_thumbnail(photo_id: str, svc: Svc) -> Response:
    return Response(content=svc.library.thumbnail(photo_id), media_type=JPEG, headers=IMAGE_CACHE)


@router.get("/photos/{photo_id}/preview", response_class=Response, responses=IMAGE_RESPONSE, tags=["library"])
def photo_preview(
    photo_id: str,
    svc: Svc,
    before: Annotated[
        bool, Query(description="The photo's default look with the edit's geometry (same framing).")
    ] = False,
    upright: Annotated[
        bool,
        Query(description="Without any geometry: the whole photo as shot, with its colors (the crop tool)."),
    ] = False,
    size: Annotated[int, Query(ge=256, le=4096, description="Long edge in pixels.")] = 1600,
) -> Response:
    data = svc.library.preview(photo_id, size, before=before, upright=upright)
    return Response(content=data, media_type=JPEG, headers=IMAGE_CACHE)


@router.get("/photos/{photo_id}/zoom/{level}", response_model=ZoomInfo, tags=["library"])
def photo_zoom(photo_id: str, level: ZoomLevel, svc: Svc) -> ZoomInfo:
    """The zoom view at 50 or 100 %. Starts its decode if needed (100 %: ~13 to 25 s the first time); ask
    again until ``state`` is ``ready``."""
    return svc.library.zoom_info(photo_id, level)


@router.get(
    "/photos/{photo_id}/zoom/{level}/tiles/{tx}/{ty}",
    response_class=Response,
    responses={**IMAGE_RESPONSE, 202: {"description": "Still decoding: ask /zoom/{level} until ready"}},
    tags=["library"],
)
def photo_tile(
    photo_id: str,
    level: ZoomLevel,
    tx: int,
    ty: int,
    svc: Svc,
    before: Annotated[bool, Query(description="The default look with the edit's geometry.")] = False,
) -> Response:
    data = svc.library.tile(photo_id, level, tx, ty, before=before)
    if data is None:
        return Response(status_code=status.HTTP_202_ACCEPTED)
    return Response(content=data, media_type=JPEG, headers=IMAGE_CACHE)


# ----------------------------------------------------------------- styles


@router.get("/styles", response_model=list[StyleSummary], tags=["styles"])
def list_styles(svc: Svc) -> list[StyleSummary]:
    return svc.styling.summaries()


@router.get("/styles/{style_id}", response_model=StyleView, tags=["styles"])
def style(style_id: str, svc: Svc) -> StyleView:
    return svc.styling.view(style_id)


@router.post("/styles", response_model=StyleView, status_code=status.HTTP_201_CREATED, tags=["styles"])
def create_style(request: Annotated[StyleCreate, Body()], svc: Svc) -> StyleView:
    return svc.styling.create(request)


@router.post(
    "/styles/from-photo", response_model=StyleView, status_code=status.HTTP_201_CREATED, tags=["styles"]
)
def create_style_from_photo(request: Annotated[StyleFromPhoto, Body()], svc: Svc) -> StyleView:
    """A new style from a photo's current look (chosen groups; exposure and white balance as rules)."""
    return svc.styling.create_from_photo(request)


@router.put("/styles/{style_id}", response_model=StyleView, tags=["styles"])
def update_style(style_id: str, update: Annotated[StyleUpdate, Body()], svc: Svc) -> StyleView:
    """Change a style (409 if it changed since ``expected_version``). Every photo using it follows."""
    return svc.styling.update(style_id, update)


@router.post("/styles/{style_id}/from-photo", response_model=StyleView, tags=["styles"])
def update_style_from_photo(
    style_id: str, request: Annotated[StyleUpdateFromPhoto, Body()], svc: Svc
) -> StyleView:
    return svc.styling.update_from_photo(style_id, request)


@router.post(
    "/styles/{style_id}/duplicate",
    response_model=StyleView,
    status_code=status.HTTP_201_CREATED,
    tags=["styles"],
)
def duplicate_style(style_id: str, request: Annotated[StyleDuplicate, Body()], svc: Svc) -> StyleView:
    return svc.styling.duplicate(style_id, request.name)


@router.delete("/styles/{style_id}", response_model=StyleDeleted, tags=["styles"])
def delete_style(style_id: str, svc: Svc) -> StyleDeleted:
    """Delete a style; the photos using it drop back to no style and keep their own tweaks."""
    return StyleDeleted(id=style_id, photos=svc.styling.delete(style_id))


@router.get("/styles/{style_id}/history", response_model=list[StyleVersionInfo], tags=["styles"])
def style_history(style_id: str, svc: Svc) -> list[StyleVersionInfo]:
    """Saved versions, newest first."""
    return svc.styles.history(style_id)


@router.get("/styles/{style_id}/versions/{version}", response_model=StyleView, tags=["styles"])
def style_version(style_id: str, version: int, svc: Svc) -> StyleView:
    return style_view(svc.styles.version(style_id, version))


@router.get(
    "/styles/{style_id}/versions/{version}/photos/{photo_id}.jpg",
    response_class=Response,
    responses=IMAGE_RESPONSE,
    tags=["styles"],
)
def style_version_render(
    style_id: str,
    version: int,
    photo_id: str,
    svc: Svc,
    size: Annotated[int, Query(ge=256, le=2048, description="Long edge in pixels.")] = 800,
) -> Response:
    """A photo with one version of the style (none of its own tweaks), to compare versions side by side."""
    data = svc.styling.render_version(style_id, version, photo_id, size)
    return Response(content=data, media_type=JPEG, headers=IMAGE_CACHE)


@router.get("/styles/{style_id}/diff", response_model=StyleDiff, tags=["styles"])
def style_diff(
    style_id: str, svc: Svc, a: Annotated[int, Query(ge=1)], b: Annotated[int, Query(ge=1)]
) -> StyleDiff:
    return svc.styles.diff(style_id, a, b)


@router.post("/styles/{style_id}/revert", response_model=StyleView, tags=["styles"])
def revert_style(style_id: str, request: Annotated[StyleRevert, Body()], svc: Svc) -> StyleView:
    return svc.styling.revert(style_id, request.version, expected_version=request.expected_version)


@router.post(
    "/styles/{style_id}/samples", response_model=Job, status_code=status.HTTP_201_CREATED, tags=["styles"]
)
def render_style_samples(style_id: str, request: Annotated[StyleSamplesRequest, Body()], svc: Svc) -> Job:
    """Render before/after sample pairs from library photos (a job)."""
    return svc.styling.render_samples(style_id, request.photo_ids)


@router.post("/styles/{style_id}/report", response_model=ConsistencyReport, tags=["styles"])
def style_report(
    style_id: str, request: Annotated[StyleReportRequest, Body()], svc: Svc
) -> ConsistencyReport:
    """How consistent the style makes the photos (default: its test set, else the photos using it)."""
    return svc.styling.report(style_id, request.photo_ids)


@router.get(
    "/styles/{style_id}/samples/{name}/{which}.jpg",
    response_class=Response,
    responses=IMAGE_RESPONSE,
    tags=["styles"],
)
def style_sample(style_id: str, name: str, which: Literal["before", "after"], svc: Svc) -> Response:
    data = svc.styling.sample_image(style_id, name, which)
    # Sample URLs carry the look they were rendered with (?v=), so a new rendering gets a new URL.
    return Response(content=data, media_type=JPEG, headers=IMAGE_CACHE)


# ----------------------------------------------------------------- export presets


@router.get("/export-presets", response_model=list[ExportPreset], tags=["export"])
def list_presets(svc: Svc) -> list[ExportPreset]:
    return svc.presets.all()


@router.post(
    "/export-presets", response_model=ExportPreset, status_code=status.HTTP_201_CREATED, tags=["export"]
)
def create_preset(request: Annotated[PresetCreate, Body()], svc: Svc) -> ExportPreset:
    return svc.presets.create(request)


@router.get("/export-presets/{preset_id}", response_model=ExportPreset, tags=["export"])
def preset(preset_id: str, svc: Svc) -> ExportPreset:
    return svc.presets.get(preset_id)


@router.put("/export-presets/{preset_id}", response_model=ExportPreset, tags=["export"])
def update_preset(preset_id: str, request: Annotated[PresetUpdate, Body()], svc: Svc) -> ExportPreset:
    return svc.presets.update(preset_id, request)


@router.delete("/export-presets/{preset_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["export"])
def delete_preset(preset_id: str, svc: Svc) -> Response:
    svc.presets.delete(preset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/export-presets/{preset_id}/duplicate",
    response_model=ExportPreset,
    status_code=status.HTTP_201_CREATED,
    tags=["export"],
)
def duplicate_preset(
    preset_id: str, svc: Svc, request: Annotated[PresetDuplicate | None, Body()] = None
) -> ExportPreset:
    return svc.presets.duplicate(preset_id, request)


# ----------------------------------------------------------------- export


@router.post("/export/plan", response_model=ExportPlan, tags=["export"])
def export_plan(request: Annotated[ExportRequest, Body()], svc: Svc) -> ExportPlan:
    """What an export would write: names, sizes, collisions and warnings. Nothing is written."""
    return svc.exporter.plan(request.photo_ids, request.settings, request.destination, request.preset_id)


@router.get("/export/destinations", response_model=list[str], tags=["export"])
def export_destinations(svc: Svc) -> list[str]:
    """Recently used export folders, newest first."""
    return svc.exporter.recent_destinations()


@router.post("/export/destination-check", response_model=DestinationCheck, tags=["export"])
def destination_check(request: Annotated[DestinationCheckRequest, Body()], svc: Svc) -> DestinationCheck:
    return svc.exporter.check_destination(request.path)


@router.post("/export/reveal", status_code=status.HTTP_204_NO_CONTENT, tags=["export"])
def reveal_export(request: Annotated[RevealRequest, Body()], svc: Svc) -> Response:
    """Show an exported file in Explorer. Only files exported in this session can be shown."""
    svc.exporter.reveal(Path(request.path))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ----------------------------------------------------------------- jobs


# ----------------------------------------------------------------- pre-export review (Phase 6c)


@router.get("/review-settings", response_model=ReviewSettings, tags=["review"])
def review_settings(svc: Svc) -> ReviewSettings:
    return svc.reviews.settings()


@router.put("/review-settings", response_model=ReviewSettings, tags=["review"])
def set_review_settings(request: Annotated[ReviewSettings, Body()], svc: Svc) -> ReviewSettings:
    """Save the rules; open reviews are sorted again by them."""
    return svc.reviews.set_settings(request)


@router.get("/reviews", response_model=list[ReviewSummary], tags=["review"])
def list_reviews(svc: Svc) -> list[ReviewSummary]:
    return svc.reviews.summaries()


@router.get("/reviews/{review_id}", response_model=ExportReview, tags=["review"])
def get_review(review_id: str, svc: Svc) -> ExportReview:
    """The review, refreshed against the photos' current edits and subjects."""
    return svc.reviews.get(review_id)


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["review"])
def discard_review(review_id: str, svc: Svc) -> Response:
    svc.reviews.discard(review_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/reviews/{review_id}/items/{photo_id}", response_model=ExportReview, tags=["review"])
def update_review_item(
    review_id: str, photo_id: str, request: Annotated[ReviewItemUpdate, Body()], svc: Svc
) -> ExportReview:
    """Set a photo's zoom (null = automatic; a zoom approves it) or approve it."""
    return svc.reviews.update_item(review_id, photo_id, request)


@router.put("/reviews/{review_id}/items/{photo_id}/subject", response_model=ExportReview, tags=["review"])
def set_review_subject(
    review_id: str, photo_id: str, request: Annotated[ReviewSubjectUpdate, Body()], svc: Svc
) -> ExportReview:
    """Choose a candidate, draw a box, or go back to the detected subject; saved to the photo's edit, and
    the photo is approved."""
    return svc.reviews.set_subject(review_id, photo_id, request)


@router.get(
    "/reviews/{review_id}/items/{photo_id}/preview",
    response_class=Response,
    responses=IMAGE_RESPONSE,
    tags=["review"],
)
def review_preview(
    review_id: str,
    photo_id: str,
    svc: Svc,
    v: Annotated[str | None, Query(description="The item's revision (cache busting only).")] = None,
) -> Response:
    """The photo framed as the export will frame it (800 px long edge)."""
    data = svc.reviews.preview(review_id, photo_id)
    return Response(content=data, media_type=JPEG, headers=IMAGE_CACHE)


@router.post(
    "/reviews/{review_id}/export", response_model=Job, status_code=status.HTTP_201_CREATED, tags=["review"]
)
def export_review(review_id: str, request: Annotated[ReviewExportRequest, Body()], svc: Svc) -> Job:
    """Export the approved photos (scope ``approved``) or all but the unusable ones (``all``)."""
    return svc.reviews.export(review_id, request.scope)


@router.get("/jobs", response_model=list[Job], tags=["jobs"])
def list_jobs(svc: Svc) -> list[Job]:
    return svc.jobs.list()


@router.post("/jobs", response_model=Job, status_code=status.HTTP_201_CREATED, tags=["jobs"])
def create_job(request: Annotated[JobRequest, Body()], svc: Svc) -> Job:
    """Apply a style, export, apply then export, detect subjects, or prepare an export for review (the job's
    ``review_id`` names the review)."""
    if isinstance(request, DetectSubjectsRequest):
        return svc.subjects.detect_job(request.photo_ids)
    if isinstance(request, ExportRequest):
        return svc.exporter.export(
            request.photo_ids, request.settings, request.destination, request.preset_id
        )
    if isinstance(request, ApplyAndExportRequest):
        # Everything the export checks (destination, settings, photos) fails before the style is applied.
        svc.exporter.plan(request.photo_ids, request.settings, request.destination, request.preset_id)

        def export() -> None:
            svc.exporter.export(request.photo_ids, request.settings, request.destination, request.preset_id)

        return svc.styling.apply(request.photo_ids, request.style_id, even_out=request.even_out, then=export)
    if isinstance(request, PrepareExportRequest):
        return svc.reviews.prepare(
            request.photo_ids,
            request.settings,
            request.destination,
            preset_id=request.preset_id,
            style_id=request.style_id,
            even_out=request.even_out,
        )
    return svc.styling.apply(request.photo_ids, request.style_id, even_out=request.even_out)


@router.get("/jobs/{job_id}", response_model=Job, tags=["jobs"])
def job(job_id: str, svc: Svc) -> Job:
    return svc.jobs.get(job_id)


@router.post("/jobs/{job_id}/cancel", response_model=Job, tags=["jobs"])
def cancel_job(job_id: str, svc: Svc) -> Job:
    return svc.jobs.cancel(job_id)
