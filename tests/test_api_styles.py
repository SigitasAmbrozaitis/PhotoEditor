"""The style endpoints (P4.8), end to end on synthetic photos through the HTTP API."""

from __future__ import annotations

import time
from collections.abc import Iterator
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from helpers import write_jpeg
from photoedit.api import create_app
from photoedit.config import Settings, load_settings
from photoedit.models import ConsistencyReport, Job, Page, Photo, PhotoDetail, StyleSummary, StyleView
from photoedit.models.style import StyleDeleted, StyleDiff, StyleVersionInfo
from photoedit.services import Services

TIMEOUT = 30


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    photos = tmp_path / "photos"
    for name, level, shutter in (("a.jpg", 70, 500), ("b.jpg", 100, 250), ("c.jpg", 140, 125)):
        write_jpeg(photos / name, (level, level, level), exposure=(4.0, Fraction(1, shutter), 400))
    settings: Settings = load_settings(
        tmp_path / "missing.toml", project_root=tmp_path, sample_photos_dir=photos
    )
    services = Services(settings)
    with TestClient(create_app(settings, services=services)) as test_client:
        r = test_client.post("/api/library/import", json={"folder": str(photos)})
        assert r.status_code == 201, r.text
        _wait_all(test_client)
        yield test_client


def _wait_all(client: TestClient) -> None:
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        jobs = TypeAdapter(list[Job]).validate_python(client.get("/api/jobs").json())
        if all(j.finished_at is not None for j in jobs):
            return
        time.sleep(0.05)
    raise AssertionError("jobs did not finish")


def _ids(client: TestClient) -> list[str]:
    page = Page[Photo].model_validate(client.get("/api/photos", params={"sort": "name"}).json())
    return [p.id for p in page.items]


def _create(client: TestClient, **fields: Any) -> StyleView:
    r = client.post("/api/styles", json={"name": "Warm", "values": {"tone.contrast": -10}, **fields})
    assert r.status_code == 201, r.text
    return StyleView.model_validate(r.json())


def _detail(client: TestClient, pid: str) -> PhotoDetail:
    return PhotoDetail.model_validate(client.get(f"/api/photos/{pid}").json())


def test_create_update_conflict_and_validation(client: TestClient) -> None:
    style = _create(client, rules=[{"type": "exposure", "metering": "highlights"}])
    assert (style.id, style.version, style.rules[0].type) == ("warm", 1, "exposure")
    r = client.put(f"/api/styles/{style.id}", json={"expected_version": 1, "values": {"tone.contrast": -20}})
    assert r.status_code == 200 and StyleView.model_validate(r.json()).version == 2
    stale = client.put(f"/api/styles/{style.id}", json={"expected_version": 1, "name": "Late"})
    assert stale.status_code == 409 and "at version 2" in stale.json()["detail"]
    bad = client.put(f"/api/styles/{style.id}", json={"expected_version": 2, "values": {"tone.nope": 1}})
    assert bad.status_code == 400 and "unknown parameter 'tone.nope'" in bad.json()["detail"]
    later = client.post("/api/styles", json={"name": "Grain", "values": {"effects.grain.amount": 10}})
    assert later.status_code == 400 and "Phase 9" in later.json()["detail"]
    assert client.put("/api/styles/nope", json={"expected_version": 1}).status_code == 404
    summaries = TypeAdapter(list[StyleSummary]).validate_python(client.get("/api/styles").json())
    assert [s.id for s in summaries] == ["warm"]


def test_photo_style_endpoint_and_reset_keeps_the_style(client: TestClient) -> None:
    style = _create(client)
    pid = _ids(client)[0]
    detail = PhotoDetail.model_validate(
        client.put(f"/api/photos/{pid}/style", json={"style_id": style.id}).json()
    )
    assert detail.edit.style_id == style.id and detail.photo.style_id == style.id
    assert detail.edit.style_values == ["tone.contrast"] and detail.edit.style_version == 1
    tweaked = detail.edit.adjustments.model_copy(deep=True)
    tweaked.presence.vibrance = 30
    client.put(f"/api/photos/{pid}/edit", json=tweaked.model_dump(by_alias=True, mode="json"))
    reset = PhotoDetail.model_validate(client.delete(f"/api/photos/{pid}/edit").json())
    assert reset.edit.style_id == style.id and reset.edit.overridden == []
    removed = client.put(f"/api/photos/{pid}/style", json={"style_id": None}).json()
    assert PhotoDetail.model_validate(removed).edit.style_id is None
    assert client.put(f"/api/photos/{pid}/style", json={"style_id": "nope"}).status_code == 404


def test_from_photo_create_and_update(client: TestClient) -> None:
    pid = _ids(client)[1]
    edit = _detail(client, pid).edit.adjustments.model_copy(deep=True)
    edit.tone.contrast = 25
    edit.tone.exposure = 0.3
    client.put(f"/api/photos/{pid}/edit", json=edit.model_dump(by_alias=True, mode="json"))
    r = client.post(
        "/api/styles/from-photo",
        json={
            "photo_id": pid,
            "name": "From b",
            "groups": ["tone"],
            "exposure": "match",
            "white_balance": "none",
        },
    )
    assert r.status_code == 201, r.text
    style = StyleView.model_validate(r.json())
    assert style.values == {"tone.contrast": 25.0} and [x.type for x in style.rules] == ["exposure"]
    bad = client.post("/api/styles/from-photo", json={"photo_id": pid, "name": "x", "groups": ["geometry"]})
    assert bad.status_code == 422
    client.put(f"/api/photos/{pid}/style", json={"style_id": style.id})
    edit = _detail(client, pid).edit.adjustments.model_copy(deep=True)
    edit.tone.contrast = 40
    client.put(f"/api/photos/{pid}/edit", json=edit.model_dump(by_alias=True, mode="json"))
    r = client.post(
        f"/api/styles/{style.id}/from-photo",
        json={"photo_id": pid, "groups": ["tone"], "expected_version": 1},
    )
    assert r.status_code == 200, r.text
    assert StyleView.model_validate(r.json()).values == {"tone.contrast": 40.0}
    assert _detail(client, pid).edit.overridden == []


def test_duplicate_history_diff_revert_delete(client: TestClient) -> None:
    style = _create(client)
    client.put(f"/api/styles/{style.id}", json={"expected_version": 1, "change_note": "x", "values": {}})
    history = TypeAdapter(list[StyleVersionInfo]).validate_python(
        client.get(f"/api/styles/{style.id}/history").json()
    )
    assert [(v.version, v.change_note) for v in history] == [(2, "x"), (1, "created")]
    old = StyleView.model_validate(client.get(f"/api/styles/{style.id}/versions/1").json())
    assert old.values == {"tone.contrast": -10.0}
    assert client.get(f"/api/styles/{style.id}/versions/7").status_code == 404
    diff = StyleDiff.model_validate(
        client.get(f"/api/styles/{style.id}/diff", params={"a": 1, "b": 2}).json()
    )
    assert [(c.name, c.before, c.after) for c in diff.values] == [("tone.contrast", -10.0, None)]
    reverted = client.post(f"/api/styles/{style.id}/revert", json={"version": 1, "expected_version": 2})
    assert StyleView.model_validate(reverted.json()).values == {"tone.contrast": -10.0}
    copy = client.post(f"/api/styles/{style.id}/duplicate", json={"name": "Warm II"})
    assert copy.status_code == 201 and copy.json()["id"] == "warm-ii"
    ids = _ids(client)
    client.post(
        "/api/jobs", json={"kind": "apply_style", "photo_ids": ids, "style_id": "warm-ii", "even_out": False}
    )
    _wait_all(client)
    deleted = StyleDeleted.model_validate(client.delete("/api/styles/warm-ii").json())
    assert deleted.photos == 3 and all(_detail(client, pid).edit.style_id is None for pid in ids)
    assert client.delete("/api/styles/warm-ii").status_code == 404


def test_even_out_samples_and_report(client: TestClient) -> None:
    ids = _ids(client)
    style = _create(
        client, values={}, rules=[{"type": "exposure", "metering": "camera_settings"}], test_photo_ids=ids
    )
    r = client.post(
        "/api/jobs", json={"kind": "apply_style", "photo_ids": ids, "style_id": style.id, "even_out": True}
    )
    assert r.status_code == 201, r.text
    _wait_all(client)
    exposures = [_detail(client, pid).edit.adjustments.tone.exposure for pid in ids]
    assert exposures == pytest.approx([1.0, 0.0, -1.0], abs=1e-3)  # 1/500, 1/250, 1/125 vs the group's 1/250
    assert _detail(client, ids[0]).edit.group is not None

    job = client.post(f"/api/styles/{style.id}/samples", json={"photo_ids": ids[:2]})
    assert job.status_code == 201
    _wait_all(client)
    view = StyleView.model_validate(client.get(f"/api/styles/{style.id}").json())
    assert len(view.samples) == 2 and view.cover_url == view.samples[0].after_url
    image = client.get(view.samples[0].after_url)
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    assert client.post(f"/api/styles/{style.id}/samples", json={"photo_ids": []}).status_code == 422

    report = ConsistencyReport.model_validate(client.post(f"/api/styles/{style.id}/report", json={}).json())
    assert [p.photo_id for p in report.photos] == ids
    cam = {s.measure: s for s in report.spread}
    assert cam["middle"].after_range < cam["middle"].before_range
    empty = _create(client, name="Empty")
    assert client.post(f"/api/styles/{empty.id}/report", json={}).status_code == 400


def test_render_a_photo_with_any_version(client: TestClient) -> None:
    style = _create(client, name="Bright", values={"tone.exposure": 0.5})
    client.put(f"/api/styles/{style.id}", json={"expected_version": 1, "values": {"tone.exposure": -0.5}})
    pid = _ids(client)[0]
    url = f"/api/styles/{style.id}/versions/{{}}/photos/{pid}.jpg"
    v1, v2 = (client.get(url.format(n), params={"size": 256}) for n in (1, 2))
    assert v1.status_code == v2.status_code == 200 and v1.headers["content-type"] == "image/jpeg"
    assert v1.content != v2.content
    assert client.get(url.format(9)).status_code == 404
