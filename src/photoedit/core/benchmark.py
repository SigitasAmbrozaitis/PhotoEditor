"""Go/no-go speed benchmark: full-resolution decode + a basic render + JPEG encode, per worker count.

Everything happens in memory. Nothing is written near the photos; only the report goes to
``output/benchmark/``.
"""

from __future__ import annotations

import io
import platform
import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import Executor, ProcessPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np
import numpy.typing as npt
import psutil
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, computed_field

from photoedit.core.decode import FULL, decode, render_identity

GO_LIMIT_MINUTES_PER_100 = 5.0
_LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)

type PhotoTask = Callable[[Path], int]
type ExecutorFactory = Callable[[int], Executor]


class BenchmarkRun(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workers: int = Field(ge=1)
    photos: int = Field(ge=1)
    seconds: float = Field(ge=0)
    peak_ram_bytes: int = Field(ge=0, description="Peak resident memory of the whole process tree.")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def seconds_per_photo(self) -> float:
        return self.seconds / self.photos

    @computed_field  # type: ignore[prop-decorator]
    @property
    def minutes_per_100(self) -> float:
        return self.seconds_per_photo * 100 / 60


class BenchmarkReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    folder: Path
    started_at: datetime
    machine: str
    render_identity: str
    runs: list[BenchmarkRun] = Field(min_length=1)

    @property
    def best(self) -> BenchmarkRun:
        return min(self.runs, key=lambda run: run.minutes_per_100)

    @property
    def go(self) -> bool:
        return self.best.minutes_per_100 <= GO_LIMIT_MINUTES_PER_100


def basic_render(pixels: npt.NDArray[np.uint16]) -> npt.NDArray[np.uint8]:
    """A stand-in for the Phase 3 pipeline with a similar cost.

    Linearize, exposure, tone curve, saturation, encode gamma. Works in place on one float32 buffer, the way a
    real pipeline should, so peak RAM is realistic.
    """
    img = pixels.astype(np.float32)
    img *= 1 / 65535
    np.power(img, 2.2, out=img)  # sRGB-ish → linear
    img *= 2**0.3  # +0.3 EV
    np.divide(img, img + 1, out=img)  # soft shoulder tone curve
    img *= 2
    luma = img @ _LUMA
    img -= luma[..., None]
    img *= 1.1  # +10 % saturation
    img += luma[..., None]
    np.clip(img, 0, 1, out=img)
    np.power(img, 1 / 2.2, out=img)
    img *= 255
    img += 0.5
    return img.astype(np.uint8)


def process_photo(path: Path) -> int:
    """One benchmark unit: decode at full size, render, encode a JPEG in memory. Returns the JPEG size."""
    pixels = decode(path, FULL)
    if pixels.dtype == np.uint8:  # JPEG/TIFF originals decode to 8 bits
        pixels = pixels.astype(np.uint16) * 257
    rendered = basic_render(pixels.astype(np.uint16, copy=False))
    buf = io.BytesIO()
    Image.fromarray(rendered).save(buf, "JPEG", quality=90)
    return buf.tell()


def process_pool(workers: int) -> Executor:
    return ProcessPoolExecutor(max_workers=workers)


def run_benchmark(
    folder: Path,
    paths: Sequence[Path],
    worker_counts: Sequence[int],
    *,
    task: PhotoTask = process_photo,
    executor_factory: ExecutorFactory = process_pool,
    progress: Callable[[str], None] | None = None,
) -> BenchmarkReport:
    """Time ``task`` over ``paths`` once per worker count. 1 worker runs in this process, without a pool."""
    if not paths:
        raise ValueError("no photos to benchmark")
    started_at = datetime.now().astimezone()
    runs: list[BenchmarkRun] = []
    for workers in worker_counts:
        if progress:
            progress(f"{len(paths)} photos with {workers} worker{'s' if workers > 1 else ''}...")
        runs.append(_timed_run(paths, workers, task, executor_factory))
        if progress:
            run = runs[-1]
            ram = _gib(run.peak_ram_bytes)
            progress(f"  {run.seconds:.1f} s, {run.minutes_per_100:.2f} min/100, {ram} peak")
    return BenchmarkReport(
        folder=folder,
        started_at=started_at,
        machine=machine_description(),
        render_identity=render_identity(),
        runs=runs,
    )


def machine_description() -> str:
    cores = psutil.cpu_count(logical=False)
    threads = psutil.cpu_count(logical=True)
    ram = _gib(psutil.virtual_memory().total)
    return f"{platform.processor() or platform.machine()}, {cores} cores / {threads} threads, {ram} RAM"


def format_report(report: BenchmarkReport) -> str:
    best = report.best
    verdict = "GO" if report.go else "NO-GO"
    lines = [
        "# Benchmark: full-res decode + basic render + JPEG encode",
        "",
        f"- Started: {report.started_at:%Y-%m-%d %H:%M}",
        f"- Folder: `{report.folder}`",
        f"- Machine: {report.machine}",
        f"- Decoder: `{report.render_identity}` (LibRaw single-threaded per worker)",
        "",
        "| Workers | Photos | Total (s) | s / photo | min / 100 photos | Peak RAM |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    lines += [
        f"| {r.workers} | {r.photos} | {r.seconds:.1f} | {r.seconds_per_photo:.2f} | {r.minutes_per_100:.2f} "
        f"| {_gib(r.peak_ram_bytes)} |"
        for r in report.runs
    ]
    lines += [
        "",
        f"**{verdict}**: best is {best.workers} worker{'s' if best.workers > 1 else ''} at "
        f"{best.minutes_per_100:.2f} min per 100 photos (limit {GO_LIMIT_MINUTES_PER_100:.0f} min).",
        "",
    ]
    return "\n".join(lines)


def _timed_run(
    paths: Sequence[Path], workers: int, task: PhotoTask, factory: ExecutorFactory
) -> BenchmarkRun:
    with _PeakMemory() as memory:
        if workers == 1:
            start = time.perf_counter()
            for path in paths:
                task(path)
            seconds = time.perf_counter() - start
        else:
            with factory(workers) as pool:
                # Start every worker first, so process start-up (importing numpy, rawpy…) isn't timed.
                _warm_up(pool, workers)
                start = time.perf_counter()
                list(pool.map(task, paths))
                seconds = time.perf_counter() - start
    return BenchmarkRun(workers=workers, photos=len(paths), seconds=seconds, peak_ram_bytes=memory.peak)


def _warm_up(pool: Executor, workers: int) -> None:
    list(pool.map(time.sleep, [0.2] * workers))


class _PeakMemory:
    """Samples the resident memory of this process and all its children in a background thread."""

    def __init__(self, interval: float = 0.05) -> None:
        self.peak = 0
        self._interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def __enter__(self) -> _PeakMemory:
        self._thread.start()
        return self

    def __exit__(self, *args: object) -> None:
        self._stop.set()
        self._thread.join()

    def _sample(self) -> None:
        me = psutil.Process()
        while True:
            total = 0
            for process in [me, *me.children(recursive=True)]:
                try:
                    total += process.memory_info().rss
                except psutil.Error:  # a worker may exit between listing and reading
                    continue
            self.peak = max(self.peak, total)
            if self._stop.wait(self._interval):
                return


def _gib(n: int) -> str:
    return f"{n / 2**30:.1f} GiB"
