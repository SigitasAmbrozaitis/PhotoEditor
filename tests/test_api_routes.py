"""Mock API endpoints: status codes and that responses match the contract models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from photoedit.api import create_app
from photoedit.config import Settings
from photoedit.mock import MockBackend
from photoedit.models import ExportPreset, Job, LibraryInfo, Page, Photo, PhotoDetail, Style, StyleSummary


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def client(settings: Settings, clock: FakeClock) -> TestClient:
    return TestClient(create_app(settings, backend=MockBackend(clock=clock)))


def test_library(client: TestClient) -> None:
    info = LibraryInfo.model_validate(client.get("/api/library").json())
    assert info.photo_count == 24


def test_default_backend_uses_configured_folder(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from photoedit.config import load_settings

    s = load_settings(tmp_path / "x.toml", project_root=tmp_path, sample_photos_dir=tmp_path / "pics")
    info = TestClient(create_app(s)).get("/api/library").json()
    assert info["folder"] == (tmp_path / "pics").resolve().as_posix()


def test_photos_page(client: TestClient) -> None:
    r = client.get("/api/photos", params={"limit": 5, "offset": 2, "sort": "name", "order": "desc"})
    assert r.status_code == 200
    page = Page[Photo].model_validate(r.json())
    assert (page.total, page.offset, page.limit, len(page.items)) == (24, 2, 5, 5)


@pytest.mark.parametrize(
    "params", [{"limit": 0}, {"limit": 501}, {"offset": -1}, {"min_rating": 6}, {"sort": "size"}]
)
def test_photos_invalid_query(client: TestClient, params: dict[str, object]) -> None:
    assert client.get("/api/photos", params=params).status_code == 422


def test_photo_detail(client: TestClient) -> None:
    detail = PhotoDetail.model_validate(client.get("/api/photos/p002").json())
    assert detail.photo.id == "p002"
    assert detail.edit.photo_id == "p002"


def test_unknown_photo_404(client: TestClient) -> None:
    r = client.get("/api/photos/zzz")
    assert r.status_code == 404
    assert "zzz" in r.json()["detail"]
    assert client.get("/api/photos/zzz/thumbnail").status_code == 404


def test_thumbnail_and_preview(client: TestClient) -> None:
    r = client.get("/api/photos/p001/thumbnail")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert "max-age" in r.headers["cache-control"]
    after = client.get("/api/photos/p001/preview", params={"size": 512})
    before = client.get("/api/photos/p001/preview", params={"size": 512, "before": True})
    assert after.status_code == before.status_code == 200
    assert after.content != before.content
    assert client.get("/api/photos/p001/preview", params={"size": 10}).status_code == 422


def test_styles(client: TestClient) -> None:
    summaries = TypeAdapter(list[StyleSummary]).validate_python(client.get("/api/styles").json())
    assert len(summaries) == 4
    data = client.get(f"/api/styles/{summaries[0].id}").json()
    assert data.pop("changed_parameters")  # derived, read-only field of the API view
    style = Style.model_validate(data)
    assert style.samples
    sample = client.get(style.samples[0].after_url)
    assert sample.status_code == 200
    assert sample.headers["content-type"] == "image/jpeg"
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


def test_jobs_flow(client: TestClient, clock: FakeClock) -> None:
    preset = client.get("/api/export-presets/instagram-portrait").json()
    r = client.post(
        "/api/jobs",
        json={
            "kind": "apply_and_export",
            "photo_ids": ["p001", "p002"],
            "style_id": "moody-forest",
            "preset_id": "instagram-portrait",
            "settings": preset["settings"],
            "destination": "C:/Users/ambro/Pictures/Exports",
        },
    )
    assert r.status_code == 201, r.text
    job = Job.model_validate(r.json())
    assert job.status == "running"
    assert TypeAdapter(list[Job]).validate_python(client.get("/api/jobs").json())[0].id == job.id

    clock.now += timedelta(seconds=10)
    done = Job.model_validate(client.get(f"/api/jobs/{job.id}").json())
    assert done.status == "done"
    assert done.progress == 1


def test_cancel_job_endpoint(client: TestClient, clock: FakeClock) -> None:
    r = client.post(
        "/api/jobs", json={"kind": "apply_style", "photo_ids": ["p001", "p002"], "style_id": "warm-film"}
    )
    job_id = r.json()["id"]
    cancelled = client.post(f"/api/jobs/{job_id}/cancel").json()
    assert cancelled["status"] == "cancelled"
    assert client.post("/api/jobs/nope/cancel").status_code == 404


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


def test_job_with_unknown_style_404(client: TestClient) -> None:
    r = client.post("/api/jobs", json={"kind": "apply_style", "photo_ids": ["p001"], "style_id": "nope"})
    assert r.status_code == 404
