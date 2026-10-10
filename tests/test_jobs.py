from __future__ import annotations

import threading
import time
from collections.abc import Iterator

import pytest

from photoedit.core.jobs import ItemResult, ItemSpec, JobManager, JobNotFoundError
from photoedit.models import JobKind, JobStatus

TIMEOUT = 10


@pytest.fixture
def manager() -> Iterator[JobManager]:
    jobs = JobManager()
    yield jobs
    jobs.shutdown()


def _items(n: int) -> list[ItemSpec]:
    return [ItemSpec(filename=f"f{i}.RAF", photo_id=f"p{i}") for i in range(n)]


def test_job_runs_every_item_and_finishes(manager: JobManager) -> None:
    seen: list[int] = []
    job = manager.submit(
        JobKind.APPLY_STYLE, "Apply", _items(3), lambda i: seen.append(i) or None, style_id="s"
    )
    assert job.status in (JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.DONE)
    done = manager.wait(job.id, TIMEOUT)
    assert done.status == JobStatus.DONE
    assert (done.progress, done.total, done.completed, done.failed) == (1.0, 3, 3, 0)
    assert sorted(seen) == [0, 1, 2]
    assert done.style_id == "s" and done.finished_at is not None
    assert all(item.status == JobStatus.DONE for item in done.items)


def test_progress_is_visible_while_running(manager: JobManager) -> None:
    gate = threading.Event()
    started = threading.Event()

    def work(i: int) -> None:
        if i == 1:
            started.set()
            gate.wait(TIMEOUT)

    job = manager.submit(JobKind.EXPORT, "Export", _items(3), work)
    assert started.wait(TIMEOUT)
    running = manager.get(job.id)
    assert running.status == JobStatus.RUNNING
    assert running.completed == 1 and running.progress == pytest.approx(1 / 3)
    assert [i.status for i in running.items] == [JobStatus.DONE, JobStatus.RUNNING, JobStatus.QUEUED]
    gate.set()
    assert manager.wait(job.id, TIMEOUT).status == JobStatus.DONE


def test_a_failing_item_does_not_stop_the_job(manager: JobManager) -> None:
    def work(i: int) -> None:
        if i == 1:
            raise ValueError("cannot decode f1.RAF")

    done = manager.wait(manager.submit(JobKind.IMPORT, "Import", _items(3), work).id, TIMEOUT)
    assert done.status == JobStatus.DONE
    assert done.failed == 1 and done.completed == 3
    assert done.items[1].status == JobStatus.FAILED
    assert done.items[1].message == "cannot decode f1.RAF"


def test_all_items_failing_fails_the_job(manager: JobManager) -> None:
    def work(i: int) -> None:
        raise OSError("disk gone")

    assert (
        manager.wait(manager.submit(JobKind.IMPORT, "x", _items(2), work).id, TIMEOUT).status
        == JobStatus.FAILED
    )


def test_item_results_fill_in_photo_ids_and_outputs(manager: JobManager) -> None:
    items = [ItemSpec(filename="a.RAF"), ItemSpec(filename="b.RAF")]
    job = manager.submit(
        JobKind.IMPORT,
        "Import",
        items,
        lambda i: ItemResult(photo_id=f"id{i}", output_path=f"out{i}.jpg", message="new"),
        folder="C:/photos",
    )
    done = manager.wait(job.id, TIMEOUT)
    assert [(i.photo_id, i.output_path, i.message) for i in done.items] == [
        ("id0", "out0.jpg", "new"),
        ("id1", "out1.jpg", "new"),
    ]
    assert done.folder == "C:/photos"


def test_finish_summary(manager: JobManager) -> None:
    job = manager.submit(JobKind.IMPORT, "Import", _items(2), lambda i: None, finish=lambda: "2 new")
    assert manager.wait(job.id, TIMEOUT).summary == "2 new"


def test_cancel_stops_remaining_items(manager: JobManager) -> None:
    gate = threading.Event()
    started = threading.Event()

    def work(i: int) -> None:
        started.set()
        gate.wait(TIMEOUT)

    job = manager.submit(JobKind.EXPORT, "Export", _items(4), work, finish=lambda: "never")
    assert started.wait(TIMEOUT)
    manager.cancel(job.id)
    gate.set()
    done = manager.wait(job.id, TIMEOUT)
    assert done.status == JobStatus.CANCELLED
    assert [i.status for i in done.items] == [JobStatus.DONE] + [JobStatus.CANCELLED] * 3
    assert done.summary is None


def test_cancelling_a_finished_job_changes_nothing(manager: JobManager) -> None:
    job = manager.wait(manager.submit(JobKind.EXPORT, "x", _items(1), lambda i: None).id, TIMEOUT)
    assert manager.cancel(job.id).status == JobStatus.DONE


def test_parallel_items(manager: JobManager) -> None:
    barrier = threading.Barrier(3, timeout=TIMEOUT)

    def work(i: int) -> None:
        barrier.wait()  # only passes if 3 items really run at the same time

    job = manager.submit(JobKind.IMPORT, "Import", _items(3), work, parallel=3)
    assert manager.wait(job.id, TIMEOUT).status == JobStatus.DONE


def test_finish_errors_fail_the_job(manager: JobManager) -> None:
    def finish() -> str:
        raise RuntimeError("catalog locked")

    done = manager.wait(
        manager.submit(JobKind.IMPORT, "x", _items(1), lambda i: None, finish=finish).id, TIMEOUT
    )
    assert done.status == JobStatus.FAILED
    assert done.summary == "RuntimeError: catalog locked"


def test_empty_job_completes(manager: JobManager) -> None:
    done = manager.wait(manager.submit(JobKind.IMPORT, "Empty folder", [], lambda i: None).id, TIMEOUT)
    assert (done.status, done.progress, done.total) == (JobStatus.DONE, 1.0, 0)


def test_list_is_newest_first_and_unknown_ids_raise(manager: JobManager) -> None:
    first = manager.submit(JobKind.EXPORT, "first", _items(1), lambda i: None)
    second = manager.submit(JobKind.EXPORT, "second", _items(1), lambda i: None)
    manager.wait(second.id, TIMEOUT)
    assert [j.id for j in manager.list()][:2] == [second.id, first.id]
    with pytest.raises(JobNotFoundError):
        manager.get("j9999")
    with pytest.raises(JobNotFoundError):
        manager.cancel("j9999")


def test_jobs_in_one_queue_run_one_at_a_time() -> None:
    manager = JobManager(max_jobs=4)
    running = 0
    peak = 0
    lock = threading.Lock()
    order: list[str] = []

    def make(name: str):  # type: ignore[no-untyped-def]
        def work(index: int) -> None:
            nonlocal running, peak
            with lock:
                running += 1
                peak = max(peak, running)
                order.append(name)
            time.sleep(0.05)
            with lock:
                running -= 1

        return work

    jobs = [manager.submit(JobKind.EXPORT, n, [ItemSpec("a")], make(n), queue="export") for n in "abc"]
    assert manager.get(jobs[1].id).status == JobStatus.QUEUED
    for job in jobs:
        assert manager.wait(job.id, timeout=5).status == JobStatus.DONE
    assert peak == 1 and order == ["a", "b", "c"]
    manager.shutdown()


def test_cancelled_queued_job_finishes_as_cancelled() -> None:
    manager = JobManager(max_jobs=2)
    gate = threading.Event()

    def blocked(index: int) -> None:
        gate.wait(5)

    first = manager.submit(JobKind.EXPORT, "first", [ItemSpec("a")], blocked, queue="export")
    second = manager.submit(JobKind.EXPORT, "second", [ItemSpec("b")], lambda i: None, queue="export")
    manager.cancel(second.id)
    gate.set()
    assert manager.wait(first.id, timeout=5).status == JobStatus.DONE
    assert manager.wait(second.id, timeout=5).status == JobStatus.CANCELLED
    manager.shutdown()


def test_cleanup_runs_also_when_cancelled() -> None:
    manager = JobManager(max_jobs=1)
    cleaned: list[str] = []
    gate = threading.Event()

    def blocked(index: int) -> None:
        gate.wait(5)

    job = manager.submit(
        JobKind.EXPORT, "x", [ItemSpec("a"), ItemSpec("b")], blocked, cleanup=lambda: cleaned.append("x")
    )
    manager.cancel(job.id)
    gate.set()
    assert manager.wait(job.id, timeout=5).status == JobStatus.CANCELLED
    assert cleaned == ["x"]
    manager.shutdown()
