"""The export service on synthetic JPEG originals (P5.9). Everything is written into tmp_path."""

from __future__ import annotations

import hashlib
import io
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from helpers import write_jpeg
from photoedit.config import Settings, load_settings
from photoedit.core.cache import ImageCache
from photoedit.core.catalog import Catalog
from photoedit.core.errors import InvalidRequestError
from photoedit.core.export import metadata as md
from photoedit.core.export.icc import icc_profile
from photoedit.core.export.service import Exporter, auto_workers
from photoedit.core.jobs import JobManager
from photoedit.core.library import Library
from photoedit.models import Job, JobStatus
from photoedit.models.export import CollisionStatus, ColorSpace, DecodeUsed, ExportSettings
from photoedit.safety import PathGuard

TIMEOUT = 120
PHOTOS = (
    ("b_late.jpg", (200, 120, 60), (320, 200), "2026:08:11 10:00:00"),
    ("a_early.jpg", (60, 120, 200), (320, 200), "2026:08:11 09:00:00"),
    ("c_portrait.jpg", (120, 120, 120), (200, 320), None),
)


@dataclass
class Env:
    library: Library
    jobs: JobManager
    guard: PathGuard
    settings: Settings
    photos: Path
    out: Path

    def exporter(self, **kwargs: Any) -> Exporter:
        return Exporter(self.library, self.jobs, self.guard, self.settings, **kwargs)

    def ids(self) -> list[str]:
        return [p.id for p in self.library.list_photos(limit=50).items]

    def run(self, job: Job) -> Job:
        return self.jobs.wait(job.id, TIMEOUT)


def _settings(tmp_path: Path, **overrides: Any) -> Settings:
    return load_settings(tmp_path / "missing.toml", project_root=tmp_path, **overrides)


@pytest.fixture
def env(tmp_path: Path) -> Iterator[Env]:
    photos = tmp_path / "photos"
    for name, color, size, date in PHOTOS:
        write_jpeg(photos / name, color, size, date=date, camera="X-T3")
    settings = _settings(tmp_path, export_copyright="© {year} Me", export_workers=1)
    guard = PathGuard(writable_roots=settings.writable_dirs, protected_roots=[photos])
    jobs = JobManager()
    catalog = Catalog(settings.workspace_dir / "catalog.sqlite", guard)
    cache = ImageCache(settings.cache_dir, guard, identity="test")
    library = Library(catalog, cache, jobs, guard)
    jobs.wait(library.import_folder(photos).id, TIMEOUT)
    yield Env(library, jobs, guard, settings, photos, tmp_path / "exports")
    jobs.shutdown()


def _web(**changes: Any) -> ExportSettings:
    data: dict[str, Any] = {
        "size": {"mode": "long_edge", "long_edge": 160},
        "metadata": {"policy": "all_except_camera_and_gps"},
        "naming": {"template": "{seq:02}_{original}"},
    }
    for key, value in changes.items():
        data[key] = {**data.get(key, {}), **value} if isinstance(value, dict) else value
    return ExportSettings.model_validate(data)


def _hashes(folder: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}


def test_plan_writes_nothing(env: Env) -> None:
    plan = env.exporter().plan(env.ids(), _web(), str(env.out))
    assert plan.destination == str(env.out)
    assert [(i.output_name, i.width, i.height) for i in plan.items] == [
        ("01_a_early.jpg", 160, 100),  # capture time order; undated last
        ("02_b_late.jpg", 160, 100),
        ("03_c_portrait.jpg", 100, 160),
    ]
    assert all(i.decode == DecodeUsed.FULL and i.collision == CollisionStatus.NEW for i in plan.items)
    assert plan.items[2].warnings == ["no capture date: {year} left out"]
    assert not env.out.exists()


def test_export_writes_planned_files(env: Env) -> None:
    originals = _hashes(env.photos)
    exporter = env.exporter()
    job = env.run(exporter.export(env.ids(), _web(), str(env.out), "web-full"))
    assert job.status == JobStatus.DONE, job
    assert job.summary == f"3 exported → {env.out}"
    assert job.title == "Export 3 photos (web-full)"
    assert sorted(p.name for p in env.out.iterdir()) == [
        "01_a_early.jpg",
        "02_b_late.jpg",
        "03_c_portrait.jpg",
    ]
    first = job.items[0]
    assert (first.output_width, first.output_height) == (160, 100)
    assert first.output_bytes == (env.out / "01_a_early.jpg").stat().st_size
    with Image.open(env.out / "01_a_early.jpg") as image:
        assert image.size == (160, 100)
        assert image.info["icc_profile"] == icc_profile(ColorSpace.SRGB)
        assert image.getexif()[md.COPYRIGHT] == "(c) 2026 Me"
        assert md.MAKE not in image.getexif()
    with Image.open(env.out / "03_c_portrait.jpg") as image:
        assert image.getexif()[md.COPYRIGHT] == "(c) Me"
    assert _hashes(env.photos) == originals  # golden rule 1
    assert exporter.was_exported(env.out / "01_a_early.jpg")
    assert not exporter.was_exported(env.photos / "a_early.jpg")
    # The destination is writable only while its export runs.
    assert not env.guard.is_writable(env.out / "later.jpg")
    assert exporter.recent_destinations() == [str(env.out)]


def test_nothing_written_outside_the_destination(env: Env, tmp_path: Path) -> None:
    tool_dirs = {env.settings.workspace_dir, env.settings.cache_dir}  # catalog, thumbnails (not the export)

    def files() -> set[Path]:
        return {p for p in tmp_path.rglob("*") if p.is_file() and not tool_dirs & set(p.parents)}

    before = files()
    env.run(env.exporter().export(env.ids(), _web(), str(env.out)))
    assert {p.parent for p in files() - before} == {env.out}


def test_worker_processes_give_identical_files(env: Env) -> None:
    one = env.run(env.exporter().export(env.ids(), _web(), str(env.out / "one")))
    env.settings.export_workers = 2
    two = env.run(env.exporter().export(env.ids(), _web(), str(env.out / "two")))
    assert one.status == two.status == JobStatus.DONE
    assert _hashes(env.out / "one") == _hashes(env.out / "two")


def test_tiff_with_a_square_crop(env: Env) -> None:
    tiff = _web(
        file={"format": "tiff", "bit_depth": 16},
        color_space="adobe_rgb",
        size={"mode": "original"},
        aspect={"ratio": "1:1"},
    )
    job = env.run(env.exporter().export(env.ids()[:1], tiff, str(env.out)))
    assert job.status == JobStatus.DONE, job.items
    name = job.items[0].output_path
    assert name is not None and name.endswith(".tif")
    assert (job.items[0].output_width, job.items[0].output_height) == (200, 200)


@pytest.mark.parametrize(
    ("policy", "names", "status"),
    [
        ("suffix", ["01_a_early.jpg", "01_a_early_2.jpg"], CollisionStatus.RENAMED),
        ("skip", ["01_a_early.jpg"], CollisionStatus.SKIP),
        ("overwrite", ["01_a_early.jpg"], CollisionStatus.OVERWRITE),
    ],
)
def test_collisions(env: Env, policy: str, names: list[str], status: CollisionStatus) -> None:
    ids = env.ids()[:1]
    env.run(env.exporter().export(ids, _web(), str(env.out)))
    settings = _web(naming={"on_collision": policy})
    assert env.exporter().plan(ids, settings, str(env.out)).items[0].collision == status
    job = env.run(env.exporter().export(ids, settings, str(env.out)))
    assert sorted(p.name for p in env.out.iterdir()) == names
    if policy == "skip":
        assert (
            job.items[0].message == "exists, skipped" and job.summary == f"0 exported, 1 skipped → {env.out}"
        )


def test_destination_refusals(env: Env, tmp_path: Path) -> None:
    exporter = env.exporter()
    (tmp_path / "file.txt").write_text("x")
    for destination, message in [
        ("exports", "full folder path"),
        ("", "full folder path"),
        (str(env.photos), "inside the photo folder"),
        (str(env.photos / "sub"), "inside the photo folder"),
        (str(tmp_path / "file.txt"), "is a file"),
        (str(env.settings.workspace_dir / "x"), "tool's own data folders"),
    ]:
        with pytest.raises(InvalidRequestError, match=message):
            exporter.export(env.ids(), _web(), destination)
        check = exporter.check_destination(destination)
        assert not check.ok and check.reason and message in check.reason
    assert exporter.check_destination(str(env.out)).ok
    assert not (env.photos / "sub").exists()


def test_subject_anchor_rejected_before_writing(env: Env) -> None:
    with pytest.raises(InvalidRequestError, match="Phase 6"):
        env.exporter().export(env.ids(), _web(aspect={"ratio": "4:5", "anchor": "subject"}), str(env.out))
    assert not env.out.exists()


def test_a_missing_original_fails_only_that_photo(env: Env) -> None:
    ids = env.ids()
    (env.photos / "b_late.jpg").rename(env.photos.parent / "moved.jpg")
    job = env.run(env.exporter().export(ids, _web(), str(env.out)))
    assert job.status == JobStatus.DONE and job.failed == 1
    failed = next(i for i in job.items if i.status == JobStatus.FAILED)
    assert failed.filename == "b_late.jpg" and "no longer at" in (failed.message or "")
    assert job.summary == f"2 exported, 1 failed → {env.out}"


class _GatedExecutor(Executor):
    """Runs tasks on threads, each waiting for ``gate`` first (to cancel a job halfway)."""

    def __init__(self, gate: threading.Event, started: threading.Event) -> None:
        self._pool = ThreadPoolExecutor(max_workers=2)
        self._gate, self._started = gate, started

    def submit(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Future[Any]:
        def run() -> Any:
            self._started.set()
            self._gate.wait(TIMEOUT)
            return fn(*args, **kwargs)

        return self._pool.submit(run)

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        self._pool.shutdown(wait=wait, cancel_futures=cancel_futures)


def test_cancel_keeps_written_files_complete(env: Env, tmp_path: Path) -> None:
    for i in range(6):
        write_jpeg(env.photos / f"extra{i}.jpg", (90, 90, 90), date=f"2026:08:12 10:00:0{i}")
    env.jobs.wait(env.library.import_folder(env.photos).id, TIMEOUT)
    env.settings.export_workers = 2
    gate, started = threading.Event(), threading.Event()
    exporter = env.exporter(executor_factory=lambda n: _GatedExecutor(gate, started))
    job = exporter.export(env.ids(), _web(), str(env.out))
    assert started.wait(TIMEOUT)
    env.jobs.cancel(job.id)
    gate.set()
    done = env.run(job)
    assert done.status == JobStatus.CANCELLED
    statuses = [i.status for i in done.items]
    assert statuses.count(JobStatus.DONE) == 2 and statuses.count(JobStatus.CANCELLED) == len(statuses) - 2
    for path in env.out.iterdir():
        with Image.open(io.BytesIO(path.read_bytes())) as image:
            image.load()  # complete files only
    assert not env.guard.is_writable(env.out / "x.jpg")


def test_auto_workers() -> None:
    gib = 1024**3
    assert auto_workers(cpus=20, available=64 * gib) == 10
    assert auto_workers(cpus=8, available=64 * gib) == 6
    assert auto_workers(cpus=20, available=6 * gib) == 2
    assert auto_workers(cpus=2, available=1 * gib) == 1
