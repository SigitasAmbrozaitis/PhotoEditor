from __future__ import annotations

import io
import threading
from collections.abc import Iterator

import pytest
from PIL import Image

from photoedit.core.errors import NotFoundError
from photoedit.core.jobs import JobManager
from photoedit.mock import MockBackend
from photoedit.models import ApplyStyleRequest, ExportRequest, ExportSettings, JobKind, JobStatus, Photo

TIMEOUT = 10


def _photo(pid: str) -> Photo:
    if not pid.startswith("p"):
        raise NotFoundError(f"photo '{pid}' not found")
    return Photo(
        id=pid,
        path=f"C:/photos/DSCF{pid[1:]}.RAF",
        filename=f"DSCF{pid[1:]}.RAF",
        folder="C:/photos",
        file_size=1,
        width=6240,
        height=4160,
    )


@pytest.fixture
def jobs() -> Iterator[JobManager]:
    manager = JobManager()
    yield manager
    manager.shutdown()


@pytest.fixture
def backend(jobs: JobManager) -> MockBackend:
    return MockBackend(jobs, _photo, seconds_per_item=0)


def test_styles_have_samples(backend: MockBackend) -> None:
    summaries = backend.list_styles()
    assert len(summaries) == 4
    assert [s.name for s in summaries] == sorted(s.name for s in summaries)
    for s in summaries:
        style = backend.style(s.id)
        assert style.samples
        assert style.adjustments.changed_fields()
        data = backend.style_sample_image(s.id, 0, before=False)
        assert Image.open(io.BytesIO(data)).format == "JPEG"


def test_unknown_ids_raise(backend: MockBackend) -> None:
    with pytest.raises(NotFoundError):
        backend.style("nope")
    with pytest.raises(NotFoundError):
        backend.style_sample_image("warm-film", 9, before=True)
    with pytest.raises(NotFoundError):
        backend.preset("nope")


def test_presets_are_the_builtins(backend: MockBackend) -> None:
    presets = backend.list_presets()
    assert len(presets) == 10
    assert backend.preset("instagram-portrait").settings.size.height == 1350


def test_apply_job_runs_on_the_job_manager(backend: MockBackend, jobs: JobManager) -> None:
    job = backend.create_job(ApplyStyleRequest(photo_ids=["p1", "p2", "p3"], style_id="warm-film"))
    assert job.kind == JobKind.APPLY_STYLE
    assert job.title == "Apply Warm Film to 3 photos (simulated)"
    assert [i.photo_id for i in job.items] == ["p1", "p2", "p3"]
    done = jobs.wait(job.id, TIMEOUT)
    assert done.status == JobStatus.DONE and done.progress == 1
    assert all(i.output_path is None for i in done.items)


def test_export_job_reports_output_paths(backend: MockBackend, jobs: JobManager) -> None:
    job = backend.create_job(
        ExportRequest(
            photo_ids=["p5437"], preset_id="web-full", settings=ExportSettings(), destination="D:/out/"
        )
    )
    assert job.title == "Export 1 photo (Web full size) (simulated)"
    done = jobs.wait(job.id, TIMEOUT)
    assert done.items[0].output_path == "D:/out/DSCF5437.jpg"


def test_jobs_take_time_and_can_be_cancelled(jobs: JobManager) -> None:
    gate = threading.Event()
    backend = MockBackend(jobs, _photo, seconds_per_item=1, sleep=lambda s: gate.wait(TIMEOUT))
    job = backend.create_job(ApplyStyleRequest(photo_ids=["p1", "p2", "p3"], style_id="bw-classic"))
    jobs.cancel(job.id)
    gate.set()
    done = jobs.wait(job.id, TIMEOUT)
    assert done.status == JobStatus.CANCELLED
    assert done.items[-1].status == JobStatus.CANCELLED


def test_job_with_unknown_references_rejected(backend: MockBackend, jobs: JobManager) -> None:
    with pytest.raises(NotFoundError):
        backend.create_job(ApplyStyleRequest(photo_ids=["p1", "missing"], style_id="warm-film"))
    with pytest.raises(NotFoundError):
        backend.create_job(ApplyStyleRequest(photo_ids=["p1"], style_id="missing"))
    assert jobs.list() == []
