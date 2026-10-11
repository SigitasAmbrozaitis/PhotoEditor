"""In-process background jobs (import, apply style, export) with per-item progress and cancellation.

A job is a list of items processed by one function. Items may run in parallel threads inside a job (useful
when the work is I/O or native code that releases the GIL). A failing item is recorded and the job goes on.
"""

from __future__ import annotations

import itertools
import threading
from collections import deque
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime

from photoedit.core.errors import NotFoundError
from photoedit.models import Job, JobItem, JobKind, JobStatus

type Clock = Callable[[], datetime]


class JobNotFoundError(NotFoundError):
    pass


@dataclass(frozen=True)
class ItemSpec:
    filename: str
    photo_id: str | None = None


@dataclass(frozen=True)
class ItemResult:
    photo_id: str | None = None
    output_path: str | None = None
    message: str | None = None
    output_bytes: int | None = None
    output_width: int | None = None
    output_height: int | None = None
    warnings: tuple[str, ...] = ()


type ItemWork = Callable[[int], ItemResult | None]
type Finisher = Callable[[], str | None]


@dataclass
class _State:
    id: str
    kind: JobKind
    title: str
    created_at: datetime
    items: list[JobItem]
    style_id: str | None = None
    preset_id: str | None = None
    destination: str | None = None
    folder: str | None = None
    status: JobStatus = JobStatus.QUEUED
    finished_at: datetime | None = None
    summary: str | None = None
    cancel: threading.Event = field(default_factory=threading.Event)
    done: threading.Event = field(default_factory=threading.Event)


class JobManager:
    """Runs jobs on a small thread pool (``max_jobs`` at a time; the rest wait as QUEUED)."""

    def __init__(self, *, max_jobs: int = 2, clock: Clock | None = None) -> None:
        self._clock: Clock = clock or (lambda: datetime.now(UTC))
        self._pool = ThreadPoolExecutor(max_workers=max_jobs, thread_name_prefix="job")
        self._jobs: dict[str, _State] = {}
        self._lock = threading.Lock()
        self._seq = itertools.count(1)
        # Jobs of a named queue run one after another (e.g. exports, which use every core).
        self._waiting: dict[str, deque[tuple[_State, Callable[[], None]]]] = {}
        self._busy: set[str] = set()

    def submit(
        self,
        kind: JobKind,
        title: str,
        items: Sequence[ItemSpec],
        work: ItemWork,
        *,
        parallel: int = 1,
        finish: Finisher | None = None,
        style_id: str | None = None,
        preset_id: str | None = None,
        destination: str | None = None,
        folder: str | None = None,
        queue: str | None = None,
        cleanup: Callable[[], None] | None = None,
    ) -> Job:
        """Queue a job. ``work(i)`` processes item i; ``finish()`` runs last and returns a summary.

        Jobs with the same ``queue`` name run one at a time, in submission order; the others wait as QUEUED
        without holding a worker thread. ``cleanup()`` always runs when the job ends, also when it was
        cancelled or failed (``finish`` doesn't run then).
        """
        state = _State(
            id=f"j{next(self._seq):04d}",
            kind=kind,
            title=title,
            created_at=self._clock(),
            items=[JobItem(photo_id=i.photo_id, filename=i.filename, status=JobStatus.QUEUED) for i in items],
            style_id=style_id,
            preset_id=preset_id,
            destination=destination,
            folder=folder,
        )

        def start() -> None:
            self._pool.submit(self._run, state, work, max(1, parallel), finish, queue, cleanup)

        with self._lock:
            self._jobs[state.id] = state
            wait = queue is not None and queue in self._busy
            if wait:
                assert queue is not None
                self._waiting.setdefault(queue, deque()).append((state, start))
            elif queue is not None:
                self._busy.add(queue)
        if not wait:
            start()
        return self.get(state.id)

    def list(self) -> list[Job]:
        with self._lock:
            states = sorted(self._jobs.values(), key=lambda s: (s.created_at, s.id), reverse=True)
            return [self._view(s) for s in states]

    def get(self, job_id: str) -> Job:
        with self._lock:
            return self._view(self._state(job_id))

    def cancel(self, job_id: str) -> Job:
        """Stop a queued or running job: items not started yet are cancelled, running ones finish."""
        with self._lock:
            state = self._state(job_id)
            if state.status in (JobStatus.QUEUED, JobStatus.RUNNING):
                state.cancel.set()
            return self._view(state)

    def wait(self, job_id: str, timeout: float | None = None) -> Job:
        """Block until the job has finished (for the CLI and tests)."""
        with self._lock:
            state = self._state(job_id)
        if not state.done.wait(timeout):
            raise TimeoutError(f"job {job_id} still running after {timeout} s")
        return self.get(job_id)

    def shutdown(self) -> None:
        with self._lock:
            for state in self._jobs.values():
                state.cancel.set()
        self._pool.shutdown(wait=True)

    # ---- internals

    def _state(self, job_id: str) -> _State:
        try:
            return self._jobs[job_id]
        except KeyError:
            raise JobNotFoundError(f"job '{job_id}' not found") from None

    def _run(
        self,
        state: _State,
        work: ItemWork,
        parallel: int,
        finish: Finisher | None,
        queue: str | None = None,
        cleanup: Callable[[], None] | None = None,
    ) -> None:
        try:
            self._run_job(state, work, parallel, finish, cleanup)
        finally:
            if queue is not None:
                self._next(queue)

    def _next(self, queue: str) -> None:
        with self._lock:
            waiting = self._waiting.get(queue)
            entry = waiting.popleft() if waiting else None
            if entry is None:
                self._busy.discard(queue)
        if entry is not None:
            state, start = entry
            try:
                start()
            except RuntimeError:  # shutting down: the pool takes no new work
                self._cancel_waiting(state)
                self._next(queue)

    def _cancel_waiting(self, state: _State) -> None:
        with self._lock:
            state.cancel.set()
            for index in range(len(state.items)):
                self._set_item(state, index, status=JobStatus.CANCELLED)
        self._finish(state)

    def _run_job(
        self,
        state: _State,
        work: ItemWork,
        parallel: int,
        finish: Finisher | None,
        cleanup: Callable[[], None] | None,
    ) -> None:
        summary: str | None = None
        error: str | None = None
        try:
            with self._lock:
                if not state.cancel.is_set():
                    state.status = JobStatus.RUNNING
            if parallel == 1:
                for index in range(len(state.items)):
                    self._run_item(state, work, index)
            else:
                with ThreadPoolExecutor(max_workers=parallel, thread_name_prefix=f"{state.id}-item") as items:
                    futures: list[Future[None]] = [
                        items.submit(self._run_item, state, work, i) for i in range(len(state.items))
                    ]
                    for future in futures:
                        future.result()
            summary = finish() if finish is not None and not state.cancel.is_set() else None
        except Exception as exc:  # a bug in finish() or the manager itself: fail the job, keep the server up
            summary, error = None, f"{type(exc).__name__}: {exc}"
        if cleanup is not None:
            try:
                cleanup()
            except Exception as exc:
                error = error or f"cleanup failed: {type(exc).__name__}: {exc}"
        self._finish(state, summary=summary, error=error)

    def _run_item(self, state: _State, work: ItemWork, index: int) -> None:
        with self._lock:
            if state.cancel.is_set():
                self._set_item(state, index, status=JobStatus.CANCELLED)
                return
            self._set_item(state, index, status=JobStatus.RUNNING)
        try:
            result = work(index) or ItemResult()
        except Exception as exc:
            with self._lock:
                self._set_item(state, index, status=JobStatus.FAILED, message=str(exc) or type(exc).__name__)
            return
        with self._lock:
            item = state.items[index]
            self._set_item(
                state,
                index,
                status=JobStatus.DONE,
                photo_id=result.photo_id or item.photo_id,
                output_path=result.output_path,
                message=result.message,
                output_bytes=result.output_bytes,
                output_width=result.output_width,
                output_height=result.output_height,
                warnings=list(result.warnings),
            )

    def _set_item(self, state: _State, index: int, **changes: object) -> None:
        state.items[index] = state.items[index].model_copy(update=changes)

    def _finish(self, state: _State, *, summary: str | None = None, error: str | None = None) -> None:
        with self._lock:
            statuses = [item.status for item in state.items]
            if error is not None:
                state.status = JobStatus.FAILED
            elif state.cancel.is_set() and JobStatus.CANCELLED in statuses:
                state.status = JobStatus.CANCELLED
            elif statuses and all(s == JobStatus.FAILED for s in statuses):
                state.status = JobStatus.FAILED
            else:
                state.status = JobStatus.DONE
            state.summary = error or summary
            state.finished_at = self._clock()
        state.done.set()

    def _view(self, state: _State) -> Job:
        total = len(state.items)
        finished = sum(1 for i in state.items if i.status in (JobStatus.DONE, JobStatus.FAILED))
        failed = sum(1 for i in state.items if i.status == JobStatus.FAILED)
        return Job(
            id=state.id,
            kind=state.kind,
            status=state.status,
            title=state.title,
            created_at=state.created_at,
            finished_at=state.finished_at,
            progress=finished / total if total else (1.0 if state.done.is_set() else 0.0),
            total=total,
            completed=finished,
            failed=failed,
            style_id=state.style_id,
            preset_id=state.preset_id,
            destination=state.destination,
            folder=state.folder,
            summary=state.summary,
            items=list(state.items),
        )
