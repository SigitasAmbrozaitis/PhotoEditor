"""JSON + image routes under /api. Thin: validation and translation only, logic lives in the backend."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends, Query, Request, Response, status

from photoedit.mock import MockBackend
from photoedit.models import (
    ExportPreset,
    Job,
    JobRequest,
    LibraryInfo,
    Page,
    Photo,
    PhotoDetail,
    PhotoSort,
    SortOrder,
    Style,
    StyleSummary,
)

THUMBNAIL_LONG_EDGE = 400
JPEG = "image/jpeg"
IMAGE_RESPONSE: dict[int | str, dict[str, Any]] = {200: {"content": {JPEG: {}}, "description": "JPEG image"}}
# Placeholder images never change for a given URL; let the browser cache them.
IMAGE_CACHE = {"Cache-Control": "public, max-age=3600"}


def get_backend(request: Request) -> MockBackend:
    backend: MockBackend = request.app.state.backend
    return backend


Backend = Annotated[MockBackend, Depends(get_backend)]

router = APIRouter(prefix="/api")


# ----------------------------------------------------------------- library / photos


@router.get("/library", response_model=LibraryInfo, tags=["library"])
def library(backend: Backend) -> LibraryInfo:
    return backend.library()


@router.get("/photos", response_model=Page[Photo], tags=["library"])
def list_photos(
    backend: Backend,
    style_id: Annotated[
        str | None, Query(description="Filter by style id; 'none' = photos without a style.")
    ] = None,
    min_rating: Annotated[int, Query(ge=0, le=5)] = 0,
    sort: PhotoSort = PhotoSort.DATE,
    order: SortOrder = SortOrder.ASC,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> Page[Photo]:
    return backend.list_photos(
        style_id=style_id, min_rating=min_rating, sort=sort, order=order, offset=offset, limit=limit
    )


@router.get("/photos/{photo_id}", response_model=PhotoDetail, tags=["library"])
def photo_detail(photo_id: str, backend: Backend) -> PhotoDetail:
    return backend.photo_detail(photo_id)


@router.get(
    "/photos/{photo_id}/thumbnail", response_class=Response, responses=IMAGE_RESPONSE, tags=["library"]
)
def photo_thumbnail(photo_id: str, backend: Backend) -> Response:
    data = backend.photo_image(photo_id, long_edge=THUMBNAIL_LONG_EDGE)
    return Response(content=data, media_type=JPEG, headers=IMAGE_CACHE)


@router.get("/photos/{photo_id}/preview", response_class=Response, responses=IMAGE_RESPONSE, tags=["library"])
def photo_preview(
    photo_id: str,
    backend: Backend,
    before: Annotated[bool, Query(description="Show the unedited photo.")] = False,
    size: Annotated[int, Query(ge=256, le=4096, description="Long edge in pixels.")] = 1600,
) -> Response:
    data = backend.photo_image(photo_id, long_edge=size, before=before)
    return Response(content=data, media_type=JPEG, headers=IMAGE_CACHE)


# ----------------------------------------------------------------- styles


@router.get("/styles", response_model=list[StyleSummary], tags=["styles"])
def list_styles(backend: Backend) -> list[StyleSummary]:
    return backend.list_styles()


@router.get("/styles/{style_id}", response_model=Style, tags=["styles"])
def style(style_id: str, backend: Backend) -> Style:
    return backend.style(style_id)


@router.get(
    "/styles/{style_id}/samples/{n}/{which}.jpg",
    response_class=Response,
    responses=IMAGE_RESPONSE,
    tags=["styles"],
)
def style_sample(style_id: str, n: int, which: Literal["before", "after"], backend: Backend) -> Response:
    data = backend.style_sample_image(style_id, n, before=which == "before")
    return Response(content=data, media_type=JPEG, headers=IMAGE_CACHE)


# ----------------------------------------------------------------- export presets


@router.get("/export-presets", response_model=list[ExportPreset], tags=["export"])
def list_presets(backend: Backend) -> list[ExportPreset]:
    return backend.list_presets()


@router.get("/export-presets/{preset_id}", response_model=ExportPreset, tags=["export"])
def preset(preset_id: str, backend: Backend) -> ExportPreset:
    return backend.preset(preset_id)


# ----------------------------------------------------------------- jobs


@router.get("/jobs", response_model=list[Job], tags=["jobs"])
def list_jobs(backend: Backend) -> list[Job]:
    return backend.list_jobs()


@router.post("/jobs", response_model=Job, status_code=status.HTTP_201_CREATED, tags=["jobs"])
def create_job(request: Annotated[JobRequest, Body()], backend: Backend) -> Job:
    return backend.create_job(request)


@router.get("/jobs/{job_id}", response_model=Job, tags=["jobs"])
def job(job_id: str, backend: Backend) -> Job:
    return backend.job(job_id)


@router.post("/jobs/{job_id}/cancel", response_model=Job, tags=["jobs"])
def cancel_job(job_id: str, backend: Backend) -> Job:
    return backend.cancel_job(job_id)
