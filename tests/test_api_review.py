"""Review endpoints (P6c.7): settings, prepare job, reviews, decisions, previews, export."""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from helpers import fill_folder
from photoedit.api import create_app
from photoedit.config import load_settings
from photoedit.core.subject.service import Subjects
from photoedit.models import Job, JobStatus, Page, Photo
from photoedit.models.review import ExportReview, ReviewSettings, ReviewSummary
from photoedit.models.subject import SubjectBox, SubjectCandidate, SubjectKind
from photoedit.services import Services

TIMEOUT = 30
# Every photo shows the same two cars: ambiguous, so every photo is in Check.
CARS = [
    SubjectCandidate(
        box=SubjectBox(left=0.1, top=0.4, right=0.3, bottom=0.7), kind=SubjectKind.CAR, score=0.9
    ),
    SubjectCandidate(
        box=SubjectBox(left=0.7, top=0.4, right=0.9, bottom=0.7), kind=SubjectKind.CAR, score=0.8
    ),
]
SETTINGS: dict[str, Any] = {
    "size": {"mode": "long_edge", "long_edge": 64},
    "aspect": {"ratio": "1:1", "anchor": "subject", "zoom": "auto"},
}


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    photos = tmp_path / "photos"
    fill_folder(photos)
    settings = load_settings(
        tmp_path / "missing.toml",
        project_root=tmp_path / "project",
        sample_photos_dir=photos,
        export_workers=1,
    )
    services = Services(settings)
    subjects = Subjects(
        services.library, settings.cache_dir, objects=(lambda _: CARS, "fake"), faces=(lambda _: [], "f")
    )
    services.subjects = subjects
    services.exporter._subjects = subjects
    services.reviews._subjects = subjects
    with TestClient(create_app(settings, services=services)) as test_client:
        r = test_client.post("/api/library/import", json={"folder": str(photos)})
        _wait(test_client, r.json()["id"])
        yield test_client


def _wait(client: TestClient, job_id: str) -> Job:
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        job = Job.model_validate(client.get(f"/api/jobs/{job_id}").json())
        if job.finished_at is not None:
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish")


def _ids(client: TestClient) -> list[str]:
    page = Page[Photo].model_validate(client.get("/api/photos", params={"sort": "name"}).json())
    return [p.id for p in page.items]


def _prepare(client: TestClient, tmp_path: Path) -> ExportReview:
    body = {
        "kind": "prepare_export",
        "photo_ids": _ids(client),
        "preset_id": "instagram-square",
        "settings": SETTINGS,
        "destination": str(tmp_path / "out"),
    }
    r = client.post("/api/jobs", json=body)
    assert r.status_code == 201, r.text
    job = _wait(client, r.json()["id"])
    assert (job.kind, job.status) == ("prepare_export", JobStatus.DONE), job
    assert job.review_id is not None
    r = client.get(f"/api/reviews/{job.review_id}")
    assert r.status_code == 200, r.text
    return ExportReview.model_validate(r.json())


def test_review_settings(client: TestClient) -> None:
    assert ReviewSettings.model_validate(client.get("/api/review-settings").json()) == ReviewSettings()
    r = client.put("/api/review-settings", json={**ReviewSettings().model_dump(), "min_score": 0.3})
    assert r.status_code == 200, r.text
    assert client.get("/api/review-settings").json()["min_score"] == 0.3
    for bad in ({"min_score": 2}, {"ambiguity": 0}, {"strict": True}):
        assert client.put("/api/review-settings", json=bad).status_code == 422


def test_prepare_review_and_decide(client: TestClient, tmp_path: Path) -> None:
    review = _prepare(client, tmp_path)
    assert review.counts.check == 3
    assert client.get(f"/api/reviews/{review.id}").json()["counts"]["check"] == 3
    summaries = [ReviewSummary.model_validate(s) for s in client.get("/api/reviews").json()]
    assert [s.id for s in summaries] == [review.id]
    first, second, third = (i.photo_id for i in review.items)

    # Choose the other car: approved.
    r = client.put(f"/api/reviews/{review.id}/items/{first}/subject", json={"candidate": 1})
    assert r.status_code == 200, r.text
    assert next(i for i in r.json()["items"] if i["photo_id"] == first)["approved"] is True
    # A drawn box, and back to the detected one.
    box = {"left": 0.4, "top": 0.4, "right": 0.6, "bottom": 0.6}
    assert (
        client.put(f"/api/reviews/{review.id}/items/{second}/subject", json={"box": box}).status_code == 200
    )
    assert (
        client.put(f"/api/reviews/{review.id}/items/{second}/subject", json={"box": None}).status_code == 200
    )
    # Zoom, then approve as it is.
    r = client.patch(f"/api/reviews/{review.id}/items/{third}", json={"zoom": 1.5})
    assert r.status_code == 200, r.text
    item = next(i for i in r.json()["items"] if i["photo_id"] == third)
    assert (item["zoom_override"], item["approved"]) == (1.5, True)
    r = client.patch(f"/api/reviews/{review.id}/items/{third}", json={"zoom": None, "approved": False})
    item = next(i for i in r.json()["items"] if i["photo_id"] == third)
    assert (item["zoom_override"], item["approved"]) == (None, False)

    r = client.get(f"/api/reviews/{review.id}/items/{first}/preview", params={"v": "x"})
    assert (r.status_code, r.headers["content-type"]) == (200, "image/jpeg")
    assert r.content[:2] == b"\xff\xd8"


@pytest.mark.parametrize(
    ("method", "path", "body", "code"),
    [
        ("patch", "items/{pid}", {}, 422),
        ("patch", "items/{pid}", {"zoom": 0.5}, 422),
        ("patch", "items/{pid}", {"zoom": 50}, 422),
        ("patch", "items/{pid}", {"zoom": 15}, 400),
        ("patch", "items/{pid}", {"approved": None}, 422),
        ("patch", "items/nope", {"approved": True}, 404),
        ("put", "items/{pid}/subject", {}, 422),
        ("put", "items/{pid}/subject", {"candidate": 1, "box": None}, 422),
        ("put", "items/{pid}/subject", {"candidate": 9}, 400),
        ("put", "items/{pid}/subject", {"box": {"left": 0.5, "top": 0, "right": 0.4, "bottom": 1}}, 422),
        ("post", "export", {"scope": "everything"}, 422),
    ],
)
def test_invalid_decisions(
    client: TestClient, tmp_path: Path, method: str, path: str, body: dict[str, Any], code: int
) -> None:
    review = _prepare(client, tmp_path)
    url = f"/api/reviews/{review.id}/" + path.format(pid=review.items[0].photo_id)
    r = client.request(method.upper(), url, json=body)
    assert r.status_code == code, r.text


def test_unknown_reviews_404(client: TestClient) -> None:
    for method, url in [
        ("GET", "/api/reviews/abcdefabcdef"),
        ("GET", "/api/reviews/..%2Fx"),
        ("DELETE", "/api/reviews/abcdefabcdef"),
        ("GET", "/api/reviews/abcdefabcdef/items/p/preview"),
    ]:
        assert client.request(method, url).status_code == 404, url
    assert client.post("/api/reviews/abcdefabcdef/export", json={}).status_code == 404


def test_prepare_refusals(client: TestClient, tmp_path: Path) -> None:
    ids = _ids(client)
    base = {
        "kind": "prepare_export",
        "photo_ids": ids,
        "settings": SETTINGS,
        "destination": str(tmp_path / "o"),
    }
    assert client.post("/api/jobs", json={**base, "even_out": True}).status_code == 422
    assert client.post("/api/jobs", json={**base, "style_id": "missing"}).status_code == 404
    assert client.post("/api/jobs", json={**base, "photo_ids": ["nope"]}).status_code == 404
    assert client.post("/api/jobs", json={**base, "destination": "relative"}).status_code == 400
    bad_zoom = {**SETTINGS, "aspect": {"ratio": "1:1", "anchor": "center", "zoom": "auto"}}
    assert client.post("/api/jobs", json={**base, "settings": bad_zoom}).status_code == 422


def test_export_and_discard(client: TestClient, tmp_path: Path) -> None:
    review = _prepare(client, tmp_path)
    r = client.post(f"/api/reviews/{review.id}/export", json={"scope": "approved"})
    assert r.status_code == 400 and "nothing to export" in r.json()["detail"]
    first = review.items[0].photo_id
    client.patch(f"/api/reviews/{review.id}/items/{first}", json={"approved": True})
    r = client.post(f"/api/reviews/{review.id}/export", json={})
    assert r.status_code == 201, r.text
    job = _wait(client, r.json()["id"])
    assert (job.kind, job.status, job.total) == ("export", JobStatus.DONE, 1)
    left = ExportReview.model_validate(client.get(f"/api/reviews/{review.id}").json())
    assert first not in {i.photo_id for i in left.items}
    assert client.delete(f"/api/reviews/{review.id}").status_code == 204
    assert client.get("/api/reviews").json() == []
