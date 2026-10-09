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
from photoedit.models.fs import DirListing
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


@router.delete("/photos/{photo_id}/edit", response_model=PhotoDetail, tags=["edit"])
def reset_edit(photo_id: str, svc: Svc) -> PhotoDetail:
    """Back to the unedited photo."""
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
    return svc.mock.list_presets()


@router.get("/export-presets/{preset_id}", response_model=ExportPreset, tags=["export"])
def preset(preset_id: str, svc: Svc) -> ExportPreset:
    return svc.mock.preset(preset_id)


# ----------------------------------------------------------------- jobs


@router.get("/jobs", response_model=list[Job], tags=["jobs"])
def list_jobs(svc: Svc) -> list[Job]:
    return svc.jobs.list()


@router.post("/jobs", response_model=Job, status_code=status.HTTP_201_CREATED, tags=["jobs"])
def create_job(request: Annotated[JobRequest, Body()], svc: Svc) -> Job:
    """Apply a style (real), export (simulated until Phase 5), or apply then export."""
    if isinstance(request, ExportRequest):
        return svc.mock.export_job(request.photo_ids, request.preset_id, request.destination)
    if isinstance(request, ApplyAndExportRequest):
        if request.preset_id:
            svc.mock.preset(request.preset_id)  # an unknown preset fails before anything is applied

        def export() -> None:
            svc.mock.export_job(request.photo_ids, request.preset_id, request.destination)

        return svc.styling.apply(request.photo_ids, request.style_id, even_out=request.even_out, then=export)
    return svc.styling.apply(request.photo_ids, request.style_id, even_out=request.even_out)


@router.get("/jobs/{job_id}", response_model=Job, tags=["jobs"])
def job(job_id: str, svc: Svc) -> Job:
    return svc.jobs.get(job_id)


@router.post("/jobs/{job_id}/cancel", response_model=Job, tags=["jobs"])
def cancel_job(job_id: str, svc: Svc) -> Job:
    return svc.jobs.cancel(job_id)
