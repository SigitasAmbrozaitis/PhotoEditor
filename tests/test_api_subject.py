"""Subject endpoints (P6b.10): GET/PUT subject, suggest-crop, the detect_subjects job, the plan's subject."""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from helpers import fill_folder
from photoedit.api import create_app
from photoedit.config import load_settings
from photoedit.core.subject.service import Subjects
from photoedit.models import Job, JobStatus, Page, Photo
from photoedit.models.crop import CropSuggestion
from photoedit.models.subject import SubjectBox, SubjectCandidate, SubjectInfo, SubjectKind, SubjectSource
from photoedit.services import Services

CAR = SubjectCandidate(
    box=SubjectBox(left=0.7, top=0.4, right=0.9, bottom=0.6), kind=SubjectKind.CAR, score=0.9, label="car"
)


class Finder:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, _: object) -> list[SubjectCandidate]:
        self.calls += 1
        return [CAR]


@pytest.fixture
def finder() -> Finder:
    return Finder()


@pytest.fixture
def client(tmp_path: Path, finder: Finder) -> Iterator[TestClient]:
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
        services.library, settings.cache_dir, objects=(finder, "fake"), faces=(lambda _: [], "f")
    )
    services.subjects = subjects
    services.exporter._subjects = subjects
    with TestClient(create_app(settings, services=services)) as test_client:
        r = test_client.post("/api/library/import", json={"folder": str(photos)})
        _wait(test_client, r.json()["id"])
        yield test_client


def _wait(client: TestClient, job_id: str) -> Job:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        job = Job.model_validate(client.get(f"/api/jobs/{job_id}").json())
        if job.finished_at is not None:
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish")


def _ids(client: TestClient) -> list[str]:
    page = Page[Photo].model_validate(client.get("/api/photos", params={"sort": "name"}).json())
    return [p.id for p in page.items]


def test_get_and_set_the_subject(client: TestClient, finder: Finder) -> None:
    pid = _ids(client)[0]
    r = client.get(f"/api/photos/{pid}/subject")
    assert r.status_code == 200, r.text
    info = SubjectInfo.model_validate(r.json())
    assert (info.source, info.kind, info.box) == (SubjectSource.DETECTED, SubjectKind.CAR, CAR.box)
    revision = client.get(f"/api/photos/{pid}").json()["edit"]["revision"]

    manual = {"left": 0.1, "top": 0.2, "right": 0.3, "bottom": 0.4}
    r = client.put(f"/api/photos/{pid}/subject", json={"box": manual})
    assert r.status_code == 200, r.text
    assert SubjectInfo.model_validate(r.json()).source is SubjectSource.MANUAL
    assert client.get(f"/api/photos/{pid}").json()["edit"]["revision"] == revision  # no re-render

    r = client.put(f"/api/photos/{pid}/subject", json={"box": None})
    assert SubjectInfo.model_validate(r.json()).source is SubjectSource.DETECTED
    assert finder.calls == 1  # stored after the first detection

    bad = client.put(
        f"/api/photos/{pid}/subject", json={"box": {"left": 0.5, "top": 0, "right": 0.4, "bottom": 1}}
    )
    assert bad.status_code == 422
    assert client.get("/api/photos/nope/subject").status_code == 404


def test_suggest_crop(client: TestClient) -> None:
    pid = _ids(client)[0]
    r = client.post(f"/api/photos/{pid}/suggest-crop", json={"aspect": "1:1", "placement": "thirds"})
    assert r.status_code == 200, r.text
    suggestion = CropSuggestion.model_validate(r.json())
    assert suggestion.source is SubjectSource.DETECTED and suggestion.aspect == "1:1"
    assert suggestion.crop.right == pytest.approx(1)  # the car is near the right edge
    draft = {"geometry": {"rotate": 90}, "aspect": "4:5", "orientation": "portrait"}
    turned = CropSuggestion.model_validate(client.post(f"/api/photos/{pid}/suggest-crop", json=draft).json())
    assert turned.subject is not None and turned.subject.top == pytest.approx(0.7)
    assert client.post(f"/api/photos/{pid}/suggest-crop", json={"aspect": "4/5"}).status_code == 422


def test_detect_subjects_job_and_the_plan(client: TestClient, finder: Finder, tmp_path: Path) -> None:
    ids = _ids(client)
    r = client.post("/api/jobs", json={"kind": "detect_subjects", "photo_ids": ids})
    assert r.status_code == 201, r.text
    job = _wait(client, r.json()["id"])
    assert job.status is JobStatus.DONE and job.kind == "detect_subjects"
    assert all(item.message == "car (detected)" for item in job.items)
    assert finder.calls == len(ids)

    settings = {
        "aspect": {"ratio": "4:5", "anchor": "subject"},
        "size": {"mode": "long_edge", "long_edge": 100},
    }
    plan = client.post(
        "/api/export/plan",
        json={"photo_ids": ids, "settings": settings, "destination": str(tmp_path / "out")},
    )
    assert plan.status_code == 200, plan.text
    assert {(i["subject"], i["subject_kind"]) for i in plan.json()["items"]} == {("detected", "car")}
    assert finder.calls == len(ids)  # the plan reused the stored detections
