from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image

from photoedit.mock import MockBackend, NotFoundError
from photoedit.mock.backend import PHOTO_COUNT, SECONDS_PER_ITEM
from photoedit.models import ApplyStyleRequest, ExportRequest, ExportSettings, JobStatus, PhotoSort, SortOrder


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def backend(clock: FakeClock) -> MockBackend:
    return MockBackend(clock=clock, folder="C:/Photos/Test")


def test_library_and_photos(backend: MockBackend) -> None:
    assert backend.library().photo_count == PHOTO_COUNT
    page = backend.list_photos(limit=10)
    assert page.total == PHOTO_COUNT
    assert len(page.items) == 10
    assert all(p.folder == "C:/Photos/Test" for p in page.items)
    assert len({p.id for p in backend.list_photos(limit=500).items}) == PHOTO_COUNT


def test_photos_are_deterministic(clock: FakeClock) -> None:
    assert MockBackend(clock=clock).list_photos().items == MockBackend(clock=clock).list_photos().items


def test_filter_sort_page(backend: MockBackend) -> None:
    rated = backend.list_photos(min_rating=4).items
    assert rated and all(p.rating >= 4 for p in rated)
    warm = backend.list_photos(style_id="warm-film").items
    assert warm and all(p.style_id == "warm-film" for p in warm)
    unstyled = backend.list_photos(style_id="none").items
    assert unstyled and all(p.style_id is None for p in unstyled)
    names = [p.filename for p in backend.list_photos(sort=PhotoSort.NAME, order=SortOrder.DESC).items]
    assert names == sorted(names, reverse=True)
    second = backend.list_photos(offset=5, limit=5)
    assert second.items == backend.list_photos(limit=500).items[5:10]


def test_photo_detail_uses_style_and_overrides(backend: MockBackend) -> None:
    photos = backend.list_photos(limit=500).items
    styled = next(p for p in photos if p.style_id and not p.has_overrides)
    detail = backend.photo_detail(styled.id)
    assert detail.edit.adjustments == backend.style(styled.style_id or "").adjustments
    assert detail.edit.overridden == []
    overridden = next(p for p in photos if p.has_overrides)
    assert "tone.exposure" in backend.photo_detail(overridden.id).edit.overridden
    plain = next(p for p in photos if p.style_id is None)
    assert backend.photo_detail(plain.id).edit.adjustments.changed_fields() == {}


def test_unknown_ids_raise(backend: MockBackend) -> None:
    for call in (
        lambda: backend.photo("nope"),
        lambda: backend.style("nope"),
        lambda: backend.preset("nope"),
        lambda: backend.job("nope"),
        lambda: backend.style_sample_image("warm-film", 99, before=False),
    ):
        with pytest.raises(NotFoundError):
            call()


def test_images_have_requested_size(backend: MockBackend) -> None:
    landscape = backend.photo("p001")
    portrait = backend.photo("p002")
    img = Image.open(io.BytesIO(backend.photo_image(landscape.id, long_edge=600)))
    assert img.format == "JPEG"
    assert img.size == (600, 400)
    img = Image.open(io.BytesIO(backend.photo_image(portrait.id, long_edge=600)))
    assert img.size == (400, 600)


def test_before_and_after_differ(backend: MockBackend) -> None:
    after = backend.photo_image("p002", long_edge=300)
    before = backend.photo_image("p002", long_edge=300, before=True)
    assert after != before


def test_styles_have_samples(backend: MockBackend) -> None:
    summaries = backend.list_styles()
    assert [s.name for s in summaries] == sorted(s.name for s in summaries)
    for s in summaries:
        style = backend.style(s.id)
        assert style.samples
        assert style.adjustments.changed_fields()
        data = backend.style_sample_image(s.id, 0, before=False)
        assert Image.open(io.BytesIO(data)).format == "JPEG"


def test_seed_jobs(backend: MockBackend) -> None:
    jobs = backend.list_jobs()
    assert len(jobs) == 2
    assert all(j.status == JobStatus.DONE for j in jobs)
    assert sum(j.failed for j in jobs) == 1


def test_job_progresses_with_time(backend: MockBackend, clock: FakeClock) -> None:
    job = backend.create_job(ApplyStyleRequest(photo_ids=["p001", "p002", "p003"], style_id="warm-film"))
    assert job.status == JobStatus.RUNNING
    assert job.progress == 0
    assert job.title == "Apply Warm Film to 3 photos"
    assert [i.status for i in job.items] == [JobStatus.RUNNING, JobStatus.QUEUED, JobStatus.QUEUED]

    clock.advance(SECONDS_PER_ITEM * 1.5)
    job = backend.job(job.id)
    assert job.completed == 1
    assert [i.status for i in job.items] == [JobStatus.DONE, JobStatus.RUNNING, JobStatus.QUEUED]

    clock.advance(SECONDS_PER_ITEM * 5)
    job = backend.job(job.id)
    assert job.status == JobStatus.DONE
    assert job.progress == 1
    assert job.finished_at is not None
    assert backend.list_jobs()[0].id == job.id  # newest first


def test_export_job_reports_output_paths(backend: MockBackend, clock: FakeClock) -> None:
    job = backend.create_job(
        ExportRequest(
            photo_ids=["p001"], preset_id="web-full", settings=ExportSettings(), destination="D:/out"
        )
    )
    assert job.title == "Export 1 photo (Web full size)"
    clock.advance(10)
    job = backend.job(job.id)
    assert job.items[0].output_path == "D:/out/DSCF5437.jpg"


def test_cancel_job(backend: MockBackend, clock: FakeClock) -> None:
    job = backend.create_job(ApplyStyleRequest(photo_ids=["p001", "p002", "p003"], style_id="bw-classic"))
    clock.advance(SECONDS_PER_ITEM * 1.2)
    job = backend.cancel_job(job.id)
    assert job.status == JobStatus.CANCELLED
    assert job.completed == 1
    clock.advance(60)
    job = backend.job(job.id)
    assert job.status == JobStatus.CANCELLED  # stays cancelled
    assert [i.status for i in job.items] == [JobStatus.DONE, JobStatus.CANCELLED, JobStatus.CANCELLED]


def test_job_with_unknown_references_rejected(backend: MockBackend) -> None:
    with pytest.raises(NotFoundError):
        backend.create_job(ApplyStyleRequest(photo_ids=["p001", "missing"], style_id="warm-film"))
    with pytest.raises(NotFoundError):
        backend.create_job(ApplyStyleRequest(photo_ids=["p001"], style_id="missing"))
