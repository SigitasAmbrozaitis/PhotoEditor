from __future__ import annotations

import threading
from collections.abc import Iterator

import pytest

from photoedit.core.errors import NotFoundError
from photoedit.core.jobs import JobManager
from photoedit.mock import MockBackend
from photoedit.models import JobKind, JobStatus, Photo

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


def test_presets_are_the_builtins(backend: MockBackend) -> None:
    presets = backend.list_presets()
    assert len(presets) == 10
    assert backend.preset("instagram-portrait").settings.size.height == 1350
    with pytest.raises(NotFoundError):
        backend.preset("nope")


def test_export_job_reports_output_paths(backend: MockBackend, jobs: JobManager) -> None:
    job = backend.export_job(["p5437"], "web-full", "D:/out/")
    assert job.kind == JobKind.EXPORT
    assert job.title == "Export 1 photo (Web full size) (simulated)"
    done = jobs.wait(job.id, TIMEOUT)
    assert done.status == JobStatus.DONE and done.items[0].output_path == "D:/out/DSCF5437.jpg"


def test_export_jobs_take_time_and_can_be_cancelled(jobs: JobManager) -> None:
    gate = threading.Event()
    backend = MockBackend(jobs, _photo, seconds_per_item=1, sleep=lambda s: gate.wait(TIMEOUT))
    job = backend.export_job(["p1", "p2", "p3"], None, "D:/out")
    assert job.title == "Export 3 photos (custom settings) (simulated)"
    jobs.cancel(job.id)
    gate.set()
    done = jobs.wait(job.id, TIMEOUT)
    assert done.status == JobStatus.CANCELLED
    assert done.items[-1].status == JobStatus.CANCELLED


def test_export_with_unknown_references_rejected(backend: MockBackend, jobs: JobManager) -> None:
    with pytest.raises(NotFoundError):
        backend.export_job(["p1", "missing"], None, "D:/out")
    with pytest.raises(NotFoundError):
        backend.export_job(["p1"], "nope", "D:/out")
    assert jobs.list() == []
