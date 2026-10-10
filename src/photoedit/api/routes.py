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
from photoedit.models.export import (
    DestinationCheck,
    DestinationCheckRequest,
    ExportPlan,
    PresetCreate,
    PresetDuplicate,
    PresetUpdate,
)
from photoedit.models.fs import DirListing
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
        bool, Query(description="Show the unedited photo (same as after until Phase 3).")
    ] = False,
    size: Annotated[int, Query(ge=256, le=4096, description="Long edge in pixels.")] = 1600,
) -> Response:
    data = svc.library.preview(photo_id, size, before=before)
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


# ----------------------------------------------------------------- jobs


@router.get("/jobs", response_model=list[Job], tags=["jobs"])
def list_jobs(svc: Svc) -> list[Job]:
    return svc.jobs.list()


@router.post("/jobs", response_model=Job, status_code=status.HTTP_201_CREATED, tags=["jobs"])
def create_job(request: Annotated[JobRequest, Body()], svc: Svc) -> Job:
    """Apply a style, export, or apply then export."""
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
    return svc.styling.apply(request.photo_ids, request.style_id, even_out=request.even_out)


@router.get("/jobs/{job_id}", response_model=Job, tags=["jobs"])
def job(job_id: str, svc: Svc) -> Job:
    return svc.jobs.get(job_id)


@router.post("/jobs/{job_id}/cancel", response_model=Job, tags=["jobs"])
def cancel_job(job_id: str, svc: Svc) -> Job:
    return svc.jobs.cancel(job_id)
