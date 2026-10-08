"""API endpoints on real services (synthetic photos in tmp_path): status codes and contract models."""

from __future__ import annotations

import io
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import TypeAdapter

from helpers import fill_folder, write_jpeg
from photoedit.api import create_app
from photoedit.config import Settings, load_settings
from photoedit.models import (
    ExportPreset,
    Job,
    LibraryFolder,
    LibraryInfo,
    Page,
    Photo,
    PhotoDetail,
    Style,
    StyleSummary,
)
from photoedit.models.fs import DirListing
from photoedit.services import Services

TIMEOUT = 20


@pytest.fixture
def photos(tmp_path: Path) -> Path:
    folder = tmp_path / "photos"
    fill_folder(folder)
    return folder


@pytest.fixture
def settings_with_photos(tmp_path: Path, photos: Path) -> Settings:
    return load_settings(
        tmp_path / "missing.toml", project_root=tmp_path / "project", sample_photos_dir=photos
    )


@pytest.fixture
def client(settings_with_photos: Settings) -> Iterator[TestClient]:
    services = Services(settings_with_photos, mock_seconds_per_item=0)
    with TestClient(create_app(settings_with_photos, services=services)) as test_client:
        yield test_client


def _wait(client: TestClient, job_id: str) -> Job:
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        job = Job.model_validate(client.get(f"/api/jobs/{job_id}").json())
        if job.finished_at is not None:
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish")


def _import(client: TestClient, folder: Path, **extra: object) -> Job:
    r = client.post("/api/library/import", json={"folder": str(folder), **extra})
    assert r.status_code == 201, r.text
    return _wait(client, Job.model_validate(r.json()).id)


def _photo_ids(client: TestClient) -> list[str]:
    page = Page[Photo].model_validate(client.get("/api/photos", params={"sort": "name"}).json())
    return [p.id for p in page.items]


# ----------------------------------------------------------------- library


def test_library_starts_empty_with_a_suggestion(client: TestClient, photos: Path) -> None:
    info = LibraryInfo.model_validate(client.get("/api/library").json())
    assert info.folder is None and info.photo_count == 0
    assert info.suggested_folder == photos.resolve().as_posix()
    assert Page[Photo].model_validate(client.get("/api/photos").json()).total == 0
    assert client.get("/api/library/folders").json() == []


def test_import_then_browse(client: TestClient, photos: Path) -> None:
    job = _import(client, photos)
    assert job.kind == "import" and job.status == "done"
    assert job.summary == "3 photos: 3 new; 1 other file skipped"
    assert job.folder == photos.resolve().as_posix()

    info = LibraryInfo.model_validate(client.get("/api/library").json())
    assert info.photo_count == 3 and info.folder == photos.resolve().as_posix()
    folders = TypeAdapter(list[LibraryFolder]).validate_python(client.get("/api/library/folders").json())
    assert [(f.path, f.photo_count) for f in folders] == [(photos.resolve().as_posix(), 3)]
    assert folders[0].last_imported_at is not None

    r = client.get("/api/photos", params={"limit": 2, "offset": 1, "sort": "name", "order": "desc"})
    page = Page[Photo].model_validate(r.json())
    assert (page.total, page.offset, page.limit) == (3, 1, 2)
    assert [p.filename for p in page.items] == ["b.jpg", "a.jpg"]


def test_import_errors_are_clear_4xx(client: TestClient, tmp_path: Path) -> None:
    r = client.post("/api/library/import", json={"folder": str(tmp_path / "nope")})
    assert r.status_code == 400 and "folder not found" in r.json()["detail"]
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")
    r = client.post("/api/library/import", json={"folder": str(tmp_path / "file.txt")})
    assert r.status_code == 400 and "not a folder" in r.json()["detail"]
    r = client.post("/api/library/import", json={"folder": "relative/path"})
    assert r.status_code == 400 and "absolute" in r.json()["detail"]
    assert client.post("/api/library/import", json={"folder": ""}).status_code == 422
    assert client.post("/api/library/import", json={}).status_code == 422


def test_switch_current_folder(client: TestClient, photos: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    write_jpeg(other / "x.jpg", (9, 9, 9))
    write_jpeg(other / "y.jpg", (8, 8, 8))  # distinct content: identical files would count as one photo
    _import(client, photos)
    _import(client, other)
    assert client.get("/api/library").json()["photo_count"] == 2
    r = client.put("/api/library/current", json={"folder": str(photos)})
    assert r.status_code == 200 and r.json()["photo_count"] == 3
    r = client.put("/api/library/current", json={"folder": str(tmp_path / "never")})
    assert r.status_code == 404 and "not been imported" in r.json()["detail"]


@pytest.mark.parametrize(
    "params", [{"limit": 0}, {"limit": 501}, {"offset": -1}, {"min_rating": 6}, {"sort": "size"}]
)
def test_photos_invalid_query(client: TestClient, params: dict[str, object]) -> None:
    assert client.get("/api/photos", params=params).status_code == 422


def test_photo_detail_thumbnail_preview(client: TestClient, photos: Path) -> None:
    _import(client, photos)
    pid = _photo_ids(client)[0]
    detail = PhotoDetail.model_validate(client.get(f"/api/photos/{pid}").json())
    assert detail.photo.id == pid and detail.edit.photo_id == pid
    assert detail.photo.camera == "Cam A"

    thumb = client.get(f"/api/photos/{pid}/thumbnail")
    assert thumb.status_code == 200 and thumb.headers["content-type"] == "image/jpeg"
    assert "max-age" in thumb.headers["cache-control"]
    preview = client.get(f"/api/photos/{pid}/preview", params={"size": 256})
    assert Image.open(io.BytesIO(preview.content)).size == (256, 160)
    before = client.get(f"/api/photos/{pid}/preview", params={"size": 256, "before": True})
    assert before.content == preview.content  # no edits until Phase 3
    assert client.get(f"/api/photos/{pid}/preview", params={"size": 10}).status_code == 422


def test_unknown_photo_404(client: TestClient) -> None:
    r = client.get("/api/photos/zzz")
    assert r.status_code == 404 and "zzz" in r.json()["detail"]
    assert client.get("/api/photos/zzz/thumbnail").status_code == 404
    assert client.get("/api/photos/zzz/preview").status_code == 404


def test_missing_original_is_404(client: TestClient, photos: Path) -> None:
    _import(client, photos)
    pid = _photo_ids(client)[0]
    (photos / "a.jpg").unlink()
    r = client.get(f"/api/photos/{pid}/preview")
    assert r.status_code == 404 and "no longer at" in r.json()["detail"]


# ----------------------------------------------------------------- folder browser


def test_fs_dirs_lists_subfolders_with_counts(client: TestClient, photos: Path) -> None:
    fill_folder(photos / "day2")
    (photos / "empty").mkdir()
    listing = DirListing.model_validate(client.get("/api/fs/dirs", params={"path": str(photos)}).json())
    assert listing.path == photos.resolve().as_posix()
    assert listing.parent == photos.resolve().parent.as_posix()
    assert listing.photo_count == 3
    assert [(e.name, e.photo_count) for e in listing.entries] == [("day2", 3), ("empty", 0)]


def test_fs_dirs_roots_and_errors(client: TestClient, tmp_path: Path) -> None:
    roots = DirListing.model_validate(client.get("/api/fs/dirs").json())
    assert roots.path is None and roots.entries
    assert client.get("/api/fs/dirs", params={"path": str(tmp_path / "nope")}).status_code == 404
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    assert client.get("/api/fs/dirs", params={"path": str(tmp_path / "f.txt")}).status_code == 400
    assert client.get("/api/fs/dirs", params={"path": "relative"}).status_code == 400


# ----------------------------------------------------------------- styles + presets (mock)


def test_styles(client: TestClient) -> None:
    summaries = TypeAdapter(list[StyleSummary]).validate_python(client.get("/api/styles").json())
    assert len(summaries) == 4
    data = client.get(f"/api/styles/{summaries[0].id}").json()
    assert data.pop("changed_parameters")  # derived, read-only field of the API view
    style = Style.model_validate(data)
    sample = client.get(style.samples[0].after_url)
    assert sample.status_code == 200 and sample.headers["content-type"] == "image/jpeg"
    assert client.get(f"/api/styles/{style.id}/samples/0/sideways.jpg").status_code == 422
    assert client.get("/api/styles/nope").status_code == 404


def test_color_grading_serialized_with_global_alias(client: TestClient) -> None:
    data = client.get("/api/styles/warm-film").json()
    assert "global" in data["adjustments"]["color_grading"]
    assert "global_" not in data["adjustments"]["color_grading"]


def test_presets(client: TestClient) -> None:
    presets = TypeAdapter(list[ExportPreset]).validate_python(client.get("/api/export-presets").json())
    assert len(presets) == 10
    one = ExportPreset.model_validate(client.get("/api/export-presets/instagram-portrait").json())
    assert one.settings.size.height == 1350
    assert client.get("/api/export-presets/nope").status_code == 404


# ----------------------------------------------------------------- jobs


def test_apply_and_export_job_on_real_photos(client: TestClient, photos: Path) -> None:
    _import(client, photos)
    ids = _photo_ids(client)[:2]
    preset = client.get("/api/export-presets/instagram-portrait").json()
    r = client.post(
        "/api/jobs",
        json={
            "kind": "apply_and_export",
            "photo_ids": ids,
            "style_id": "moody-forest",
            "preset_id": "instagram-portrait",
            "settings": preset["settings"],
            "destination": "C:/Users/ambro/Pictures/Exports",
        },
    )
    assert r.status_code == 201, r.text
    job = _wait(client, Job.model_validate(r.json()).id)
    assert job.status == "done" and job.progress == 1
    assert [i.output_path for i in job.items] == [
        "C:/Users/ambro/Pictures/Exports/a.jpg",
        "C:/Users/ambro/Pictures/Exports/b.jpg",
    ]
    listed = TypeAdapter(list[Job]).validate_python(client.get("/api/jobs").json())
    assert [j.kind for j in listed] == ["apply_and_export", "render", "import"]  # newest first


def test_cancel_job_endpoint(client: TestClient, photos: Path) -> None:
    job = _import(client, photos)
    assert client.post(f"/api/jobs/{job.id}/cancel").json()["status"] == "done"  # already finished
    assert client.post("/api/jobs/nope/cancel").status_code == 404
    assert client.get("/api/jobs/nope").status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "apply_style", "photo_ids": [], "style_id": "warm-film"},
        {"kind": "apply_style", "photo_ids": ["p001"]},
        {"kind": "export", "photo_ids": ["p001"], "settings": {}},
        {
            "kind": "export",
            "photo_ids": ["p001"],
            "settings": {"file": {"jpeg_quality": 0}},
            "destination": "C:/x",
        },
        {"kind": "unknown", "photo_ids": ["p001"]},
    ],
)
def test_invalid_job_requests_422(client: TestClient, body: dict[str, object]) -> None:
    assert client.post("/api/jobs", json=body).status_code == 422


def test_job_with_unknown_photo_or_style_404(client: TestClient, photos: Path) -> None:
    r = client.post("/api/jobs", json={"kind": "apply_style", "photo_ids": ["nope"], "style_id": "warm-film"})
    assert r.status_code == 404
    _import(client, photos)
    pid = _photo_ids(client)[0]
    r = client.post("/api/jobs", json={"kind": "apply_style", "photo_ids": [pid], "style_id": "nope"})
    assert r.status_code == 404


def test_create_app_alone_does_not_touch_the_workspace(settings: Settings) -> None:
    create_app(settings).openapi()
    assert not settings.workspace_dir.exists()
