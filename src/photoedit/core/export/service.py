"""The export service: plans an export (a dry run) and runs it as a job.

Validation comes first, so a bad destination or setting fails before anything is written. Photos render in
worker processes (``worker.render_export``); this process writes each file atomically through the path guard,
into the destination the user chose, which is writable only while its export runs.
"""

from __future__ import annotations

import json
import math
import multiprocessing
import os
import re
import subprocess
import sys
import threading
from collections import Counter
from collections.abc import Callable, Sequence
from concurrent.futures import Executor, ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import psutil

from photoedit.config import Settings
from photoedit.core.catalog import CatalogPhoto
from photoedit.core.decode import is_raw
from photoedit.core.errors import InvalidRequestError, NotFoundError
from photoedit.core.export.encode import EXTENSIONS
from photoedit.core.export.geometry import ExportGeometry, export_geometry
from photoedit.core.export.geometry import warnings as geometry_warnings
from photoedit.core.export.naming import NameFields, plan_names
from photoedit.core.export.worker import ExportTask, RenderedExport, render_export
from photoedit.core.jobs import ItemResult, ItemSpec, JobManager
from photoedit.core.library import Library
from photoedit.core.renderer import profile_of
from photoedit.models import Job, JobKind
from photoedit.models.export import (
    CollisionStatus,
    DestinationCheck,
    ExportPlan,
    ExportPlanItem,
    ExportSettings,
)
from photoedit.safety import PathGuard

EXPORT_QUEUE = "export"
RECENT_FILE = "recent-destinations.json"
RECENT_LIMIT = 10
MAX_AUTO_WORKERS = 10
# Peak memory of one worker rendering a full-size X-T3 export (P5.11 measures it). Workers that would not fit
# in the free memory aren't started.
WORKER_PEAK_BYTES = 2 * 1024**3

type ExecutorFactory = Callable[[int], Executor]


def auto_workers(*, cpus: int | None = None, available: int | None = None) -> int:
    """Worker processes for an export on this machine: leave two cores free and stay within memory."""
    cpus = cpus if cpus is not None else (os.cpu_count() or 2)
    available = available if available is not None else psutil.virtual_memory().available
    by_memory = math.floor(available * 0.8 / WORKER_PEAK_BYTES)
    return max(1, min(MAX_AUTO_WORKERS, cpus - 2, by_memory))


def _process_pool(workers: int) -> Executor:
    # Spawned (not forked) workers: the same on every platform, and none inherits this process's threads.
    return ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn"))


@dataclass(frozen=True)
class _Item:
    photo: CatalogPhoto
    geometry: ExportGeometry
    name: str
    collision: CollisionStatus
    copyright: str | None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class _Prepared:
    destination: Path
    settings: ExportSettings
    items: list[_Item]

    def plan(self) -> ExportPlan:
        return ExportPlan(
            destination=str(self.destination),
            items=[
                ExportPlanItem(
                    photo_id=i.photo.id,
                    filename=i.photo.path.name,
                    output_name=i.name,
                    width=i.geometry.width,
                    height=i.geometry.height,
                    decode=i.geometry.decode,
                    collision=i.collision,
                    warnings=[*i.warnings, *([i.error] if i.error else [])],
                )
                for i in self.items
            ],
        )


class Exporter:
    def __init__(
        self,
        library: Library,
        jobs: JobManager,
        guard: PathGuard,
        settings: Settings,
        *,
        executor_factory: ExecutorFactory | None = None,
    ) -> None:
        self._library = library
        self._jobs = jobs
        self._guard = guard
        self._settings = settings
        self._executor_factory = executor_factory or _process_pool
        self._lock = threading.Lock()
        self._writing: Counter[Path] = Counter()  # destinations with an export in flight
        self._exported: set[Path] = set()

    @property
    def workers(self) -> int:
        return self._settings.export_workers or auto_workers()

    # ---- destinations

    def check_destination(self, raw: str) -> DestinationCheck:
        path = Path(raw).expanduser()
        try:
            resolved = self._destination(raw)
        except InvalidRequestError as exc:
            return DestinationCheck(path=str(path), exists=path.is_dir(), ok=False, reason=str(exc))
        return DestinationCheck(path=str(resolved), exists=resolved.is_dir(), ok=True)

    def _destination(self, raw: str) -> Path:
        text = raw.strip()
        path = Path(text).expanduser()
        if not text or not path.is_absolute():
            raise InvalidRequestError(
                "the destination must be a full folder path, e.g. C:\\Users\\you\\Exports"
            )
        protected = self._guard.protected_root_of(path)
        if protected is not None:
            raise InvalidRequestError(
                f"{path} is inside the photo folder {protected}; originals are read-only, so nothing is "
                "written there. Choose another folder."
            )
        resolved = Path(os.path.realpath(path))
        settings = self._settings
        for tool_dir in (
            settings.workspace_dir,
            settings.cache_dir,
            settings.styles_dir,
            settings.presets_dir,
        ):
            if resolved == tool_dir or resolved.is_relative_to(tool_dir):
                raise InvalidRequestError(
                    f"{path} is one of the tool's own data folders; choose another folder"
                )
        if resolved.exists() and not resolved.is_dir():
            raise InvalidRequestError(f"{path} is a file, not a folder")
        ancestor = resolved
        while not ancestor.exists():
            ancestor = ancestor.parent
        if not ancestor.is_dir() or not os.access(ancestor, os.W_OK):
            raise InvalidRequestError(f"can't create or write the folder {path}")
        return resolved

    def recent_destinations(self) -> list[str]:
        try:
            data = json.loads((self._settings.workspace_dir / RECENT_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return [d for d in data if isinstance(d, str)][:RECENT_LIMIT] if isinstance(data, list) else []

    def _remember(self, destination: Path) -> None:
        recent = [
            d for d in self.recent_destinations() if os.path.normcase(d) != os.path.normcase(str(destination))
        ]
        data = json.dumps([str(destination), *recent][:RECENT_LIMIT], indent=1)
        self._guard.write_atomic(self._settings.workspace_dir / RECENT_FILE, data.encode("utf-8"))

    def was_exported(self, path: Path) -> bool:
        """True for files this process exported (the UI may reveal those in Explorer, nothing else)."""
        with self._lock:
            return Path(os.path.realpath(path)) in self._exported

    def reveal(self, path: Path) -> None:
        """Show an exported file in the system's file manager (only files this process exported)."""
        if not self.was_exported(path):
            raise InvalidRequestError(f"{path} isn't a file exported in this session")
        if not path.is_file():
            raise NotFoundError(f"{path} no longer exists")
        reveal_in_file_manager(path)

    # ---- plan + export

    def plan(
        self,
        photo_ids: Sequence[str],
        settings: ExportSettings,
        destination: str,
        preset_id: str | None = None,
    ) -> ExportPlan:
        """What ``export`` would write. Nothing is written."""
        return self._prepare(photo_ids, settings, destination, preset_id).plan()

    def export(
        self,
        photo_ids: Sequence[str],
        settings: ExportSettings,
        destination: str,
        preset_id: str | None = None,
    ) -> Job:
        prepared = self._prepare(photo_ids, settings, destination, preset_id)
        dest = prepared.destination
        self._remember(dest)
        with self._lock:
            self._writing[dest] += 1
            self._guard.allow_writes_to(dest)
        workers = min(self.workers, len(prepared.items))
        pool: list[Executor] = []
        pool_lock = threading.Lock()
        outcomes: Counter[str] = Counter()

        def render(task: ExportTask) -> RenderedExport:
            if workers == 1:
                return render_export(task)  # one at a time: no worker process needed
            with pool_lock:
                if not pool:
                    pool.append(self._executor_factory(workers))
                executor = pool[0]
            return executor.submit(render_export, task).result()

        def work(index: int) -> ItemResult:
            item = prepared.items[index]
            target = dest / item.name
            if item.collision == CollisionStatus.SKIP:
                with self._lock:
                    outcomes["skipped"] += 1
                return ItemResult(photo_id=item.photo.id, output_path=str(target), message="exists, skipped")
            try:
                if item.error:
                    raise InvalidRequestError(item.error)
                rendered = render(self._task(item, prepared.settings))
                written = self._guard.write_atomic(target, rendered.data)
            except Exception:
                with self._lock:
                    outcomes["failed"] += 1
                raise
            with self._lock:
                self._exported.add(Path(os.path.realpath(written)))
                outcomes["exported"] += 1
            return ItemResult(
                photo_id=item.photo.id,
                output_path=str(written),
                output_bytes=len(rendered.data),
                output_width=rendered.width,
                output_height=rendered.height,
                warnings=(*item.warnings, *rendered.warnings),
                message="overwritten" if item.collision == CollisionStatus.OVERWRITE else None,
            )

        def finish() -> str:
            parts = [f"{outcomes['exported']} exported"]
            parts += [f"{outcomes[k]} {k}" for k in ("skipped", "failed") if outcomes[k]]
            return f"{', '.join(parts)} → {dest}"

        def cleanup() -> None:
            with pool_lock:
                for executor in pool:
                    executor.shutdown(wait=True, cancel_futures=True)
            with self._lock:
                self._writing[dest] -= 1
                if self._writing[dest] <= 0:
                    del self._writing[dest]
                    self._guard.revoke(dest)

        count = len(prepared.items)
        noun = "photo" if count == 1 else "photos"
        label = preset_id or "custom settings"
        return self._jobs.submit(
            JobKind.EXPORT,
            f"Export {count} {noun} ({label})",
            [ItemSpec(filename=i.photo.path.name, photo_id=i.photo.id) for i in prepared.items],
            work,
            parallel=workers,
            finish=finish,
            cleanup=cleanup,
            queue=EXPORT_QUEUE,
            preset_id=preset_id,
            destination=str(dest),
        )

    # ---- internals

    def _prepare(
        self, photo_ids: Sequence[str], settings: ExportSettings, destination: str, preset_id: str | None
    ) -> _Prepared:
        if not photo_ids:
            raise InvalidRequestError("no photos to export")
        dest = self._destination(destination)
        photos = sorted(
            {pid: self._library.photo(pid) for pid in photo_ids}.values(),
            key=lambda p: (
                p.captured_at is None,
                p.captured_at.isoformat() if p.captured_at else "",
                p.path.name.lower(),
            ),
        )
        geometries = [export_geometry(p.width, p.height, settings, is_raw=is_raw(p.path)) for p in photos]
        existing = {p.name.lower() for p in dest.iterdir() if p.is_file()} if dest.is_dir() else set()
        fields = [
            NameFields(
                original=p.path.stem,
                captured_at=p.captured_at,
                camera=p.camera,
                style=p.style_id,
                preset=preset_id,
            )
            for p in photos
        ]
        names = plan_names(settings.naming, fields, EXTENSIONS[settings.file.format], existing)
        items: list[_Item] = []
        for photo, geometry, name in zip(photos, geometries, names, strict=True):
            warnings = geometry_warnings(geometry)
            copyright_, note = self._copyright(settings, photo)
            if note:
                warnings.append(note)
            error = None
            if not photo.path.is_file():
                error = f"the original is no longer at {photo.path}"
            items.append(_Item(photo, geometry, name.name, name.collision, copyright_, warnings, error))
        return _Prepared(dest, settings, items)

    def _copyright(self, settings: ExportSettings, photo: CatalogPhoto) -> tuple[str | None, str | None]:
        text = settings.metadata.copyright or self._settings.export_copyright
        if not text or "{year}" not in text:
            return text, None
        if photo.captured_at is not None:
            return text.replace("{year}", str(photo.captured_at.year)), None
        return re.sub(r"\s{2,}", " ", text.replace("{year}", "")).strip(), "no capture date: {year} left out"

    def _task(self, item: _Item, settings: ExportSettings) -> ExportTask:
        photo = item.photo
        edit = self._library.edit(photo.id)
        if edit.style_error is not None:
            raise InvalidRequestError(f"{edit.style_error}; fix the style or remove it from this photo")
        return ExportTask(
            path=photo.path,
            width=photo.width,
            height=photo.height,
            adjustments=edit.adjustments,
            profile=profile_of(photo),
            anchors=self._library.renderer.anchors(photo),
            settings=settings,
            geometry=item.geometry,
            copyright=item.copyright,
            creator=settings.metadata.creator or self._settings.export_creator,
        )


def reveal_in_file_manager(path: Path) -> None:
    """Open Explorer (Finder, or the file manager) showing ``path``. Starts a program; writes nothing."""
    if sys.platform == "win32":
        subprocess.Popen(["explorer", f"/select,{path}"])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent)])
