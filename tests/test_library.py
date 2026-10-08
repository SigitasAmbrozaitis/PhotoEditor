from __future__ import annotations

import io
import itertools
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from PIL import Image

from helpers import fill_folder, write_jpeg
from photoedit.core.cache import ImageCache
from photoedit.core.catalog import Catalog
from photoedit.core.errors import NotFoundError
from photoedit.core.jobs import JobManager
from photoedit.core.library import Library
from photoedit.core.scan import ScanError
from photoedit.models import JobStatus, PhotoSort
from photoedit.safety import PathGuard

TIMEOUT = 30


def _ticking_clock() -> Callable[[], datetime]:
    """A clock that moves one minute per call, so import times are distinct and ordered."""
    ticks = itertools.count()
    return lambda: datetime(2026, 10, 7, tzinfo=UTC) + timedelta(minutes=next(ticks))


@dataclass
class Env:
    library: Library
    guard: PathGuard
    photos: Path
    workspace: Path

    def run_import(self, folder: Path | None = None, **kwargs: bool) -> object:
        """Import and wait, including the thumbnail job it starts (which reads the photos)."""
        job = self.library.import_folder(folder or self.photos, **kwargs)
        done = self.library.jobs.wait(job.id, TIMEOUT)
        for other in self.library.jobs.list():
            if other.kind == "render" and other.finished_at is None:
                self.library.jobs.wait(other.id, TIMEOUT)
        return done

    def reopen(self) -> Library:
        catalog = Catalog(self.workspace / "catalog.sqlite", self.guard)
        cache = ImageCache(self.workspace / "cache", self.guard, identity="test")
        return Library(catalog, cache, self.library.jobs, self.guard)


@pytest.fixture
def env(tmp_path: Path) -> Iterator[Env]:
    workspace, photos = tmp_path / "workspace", tmp_path / "photos"
    photos.mkdir()
    guard = PathGuard(writable_roots=[workspace])
    jobs = JobManager()
    catalog = Catalog(workspace / "catalog.sqlite", guard)
    cache = ImageCache(workspace / "cache", guard, identity="test")
    library = Library(catalog, cache, jobs, guard, suggested_folder=photos, clock=_ticking_clock())
    yield Env(library, guard, photos, workspace)
    jobs.shutdown()


def test_empty_library_suggests_the_sample_folder(env: Env) -> None:
    info = env.library.info()
    assert info.folder is None and info.photo_count == 0
    assert info.suggested_folder == env.photos.as_posix()
    assert env.library.list_photos().items == []


def test_first_import(env: Env) -> None:
    fill_folder(env.photos)
    job = env.run_import()
    assert job.status == JobStatus.DONE  # type: ignore[attr-defined]
    assert job.summary == "3 photos: 3 new; 1 other file skipped"  # type: ignore[attr-defined]
    assert all(item.photo_id for item in job.items)  # type: ignore[attr-defined]

    info = env.library.info()
    assert info.folder == env.photos.resolve().as_posix() and info.photo_count == 3
    page = env.library.list_photos()
    assert [p.filename for p in page.items] == ["b.jpg", "a.jpg", "c.jpg"]  # by capture date, undated last
    first = env.library.list_photos(sort=PhotoSort.NAME).items[0]
    assert first.camera == "Cam A" and (first.width, first.height) == (320, 200)

    thumb = Image.open(io.BytesIO(env.library.thumbnail(first.id)))
    assert thumb.size == (320, 200)  # small originals are not enlarged
    preview = Image.open(io.BytesIO(env.library.preview(first.id, 1600)))
    assert preview.size == (320, 200)  # rendered at its own size: never enlarged
    assert env.library.photo_detail(first.id).edit.style_id is None


def test_folder_is_protected_and_untouched(env: Env) -> None:
    fill_folder(env.photos)
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in env.photos.iterdir()}
    env.run_import()
    for photo in env.library.list_photos().items:
        env.library.preview(photo.id, 256)
    assert {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in env.photos.iterdir()} == before
    assert not env.guard.is_writable(env.photos / "anything.jpg")


def test_reimport_is_incremental(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    fill_folder(env.photos)
    env.run_import()
    hashed: list[Path] = []
    from photoedit.core import library as library_module

    real = library_module._sha256

    def counting(path: Path) -> str:
        hashed.append(path)
        return real(path)

    monkeypatch.setattr(library_module, "_sha256", counting)
    job = env.run_import()
    assert job.summary == "3 photos: 3 unchanged; 1 other file skipped"  # type: ignore[attr-defined]
    assert hashed == []

    write_jpeg(env.photos / "a.jpg", (10, 10, 10))  # edited elsewhere
    os.utime(env.photos / "a.jpg", ns=(1, 1))
    write_jpeg(env.photos / "d.jpg", (1, 2, 3))
    job = env.run_import()
    assert job.summary == "4 photos: 1 new, 1 updated, 2 unchanged; 1 other file skipped"  # type: ignore[attr-defined]
    assert sorted(p.name for p in hashed) == ["a.jpg", "d.jpg"]


def test_deleted_file_is_hidden(env: Env) -> None:
    fill_folder(env.photos)
    env.run_import()
    (env.photos / "b.jpg").unlink()
    job = env.run_import()
    assert job.summary == "2 photos: 2 unchanged; 1 other file skipped; 1 no longer in the folder"  # type: ignore[attr-defined]
    assert [p.filename for p in env.library.list_photos(sort=PhotoSort.NAME).items] == ["a.jpg", "c.jpg"]


def test_renamed_folder_keeps_photo_ids(env: Env) -> None:
    fill_folder(env.photos)
    env.run_import()
    ids = {p.filename: p.id for p in env.library.list_photos().items}
    renamed = env.photos.with_name("photos-renamed")
    env.photos.rename(renamed)
    job = env.run_import(renamed)
    assert job.summary == "3 photos: 3 updated; 1 other file skipped"  # type: ignore[attr-defined]
    assert {p.filename: p.id for p in env.library.list_photos().items} == ids
    assert env.library.info().folder == renamed.resolve().as_posix()


def test_subfolders(env: Env) -> None:
    write_jpeg(env.photos / "top.jpg", (1, 1, 1))
    write_jpeg(env.photos / "day2" / "inner.jpg", (2, 2, 2))
    env.run_import()
    assert env.library.info().photo_count == 1
    env.run_import(include_subfolders=True)
    info = env.library.info()
    assert info.include_subfolders and info.photo_count == 2


def test_raw_pairs_record_the_sidecar(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    from photoedit.core import library as library_module
    from photoedit.core.metadata import PhotoMetadata

    (env.photos / "DSCF1.RAF").write_bytes(b"raw bytes")
    write_jpeg(env.photos / "DSCF1.JPG", (5, 5, 5))
    fake_thumb = Image.new("RGB", (60, 40))
    monkeypatch.setattr(
        library_module,
        "_read_metadata_and_thumbnail",
        lambda path: (
            PhotoMetadata(width=6240, height=4160, camera="FUJIFILM X-T3"),
            fake_thumb,
            (5000.0, -5.0),
        ),
    )
    env.run_import()
    (photo,) = env.library.list_photos().items
    assert photo.filename == "DSCF1.RAF"
    assert photo.sidecar_jpeg == (env.photos / "DSCF1.JPG").resolve().as_posix()
    assert (photo.width, photo.camera) == (6240, "FUJIFILM X-T3")
    stored = env.library.photo(photo.id)
    assert (stored.as_shot_temperature, stored.as_shot_tint) == (5000.0, -5.0)


def test_unreadable_photo_fails_its_item_only(env: Env) -> None:
    fill_folder(env.photos)
    (env.photos / "broken.jpg").write_bytes(b"not a jpeg")
    job = env.run_import()
    assert job.status == JobStatus.DONE  # type: ignore[attr-defined]
    assert job.failed == 1  # type: ignore[attr-defined]
    assert "1 failed" in job.summary  # type: ignore[attr-defined]
    assert env.library.info().photo_count == 3


def test_bad_folder_raises_before_any_job(env: Env, tmp_path: Path) -> None:
    with pytest.raises(ScanError, match="not found"):
        env.library.import_folder(tmp_path / "nope")
    assert env.library.jobs.list() == []


def test_open_folder_switches_between_imported_folders(env: Env, tmp_path: Path) -> None:
    other = tmp_path / "other"
    write_jpeg(other / "x.jpg", (9, 9, 9))
    fill_folder(env.photos)
    env.run_import()
    env.run_import(other)
    assert env.library.info().photo_count == 1
    info = env.library.open_folder(env.photos.resolve())
    assert info.photo_count == 3
    assert [f.path for f in env.library.folders()] == [
        other.resolve().as_posix(),
        env.photos.resolve().as_posix(),
    ]
    with pytest.raises(NotFoundError, match="not been imported"):
        env.library.open_folder(tmp_path / "never")


def test_state_survives_a_restart(env: Env) -> None:
    fill_folder(env.photos)
    env.run_import()
    reopened = env.reopen()
    assert reopened.info().photo_count == 3
    assert not env.guard.is_writable(env.photos / "x")


def test_missing_original_gives_a_clear_error(env: Env) -> None:
    fill_folder(env.photos)
    env.run_import()
    photo = env.library.list_photos(sort=PhotoSort.NAME).items[0]
    (env.photos / "a.jpg").unlink()
    assert env.library.thumbnail(photo.id)  # still cached
    with pytest.raises(NotFoundError, match="no longer at"):
        env.library.preview(photo.id, 800)
    with pytest.raises(NotFoundError):
        env.library.photo("unknown")


def test_cancelled_import_keeps_what_was_done(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    import threading

    from photoedit.core import library as library_module

    fill_folder(env.photos)
    gate, started = threading.Event(), threading.Event()
    real = library_module._sha256

    def slow_hash(path: Path) -> str:
        started.set()
        gate.wait(TIMEOUT)
        return real(path)

    monkeypatch.setattr(library_module, "IMPORT_THREADS", 1)
    monkeypatch.setattr(library_module, "_sha256", slow_hash)
    job = env.library.import_folder(env.photos)
    assert started.wait(TIMEOUT)
    env.library.jobs.cancel(job.id)
    gate.set()
    done = env.library.jobs.wait(job.id, TIMEOUT)
    assert done.status == JobStatus.CANCELLED
    assert done.summary is None  # finish() doesn't run, so nothing is flagged missing
    assert env.library.info().photo_count == 1  # the photo in progress was finished


# ----------------------------------------------------------------- edits (Phase 3)


def test_edits_save_show_and_reset(env: Env) -> None:
    from photoedit.core.render.pipeline import UnsupportedParameterError
    from photoedit.models import AdjustmentParams

    fill_folder(env.photos)
    env.run_import()
    pid = env.library.list_photos(sort=PhotoSort.NAME).items[0].id
    # Like the UI: start from the photo's current parameters (JPEGs default to no sharpening) and change two.
    edited = env.library.edit(pid).adjustments.model_copy(deep=True)
    edited.tone.exposure = 0.7
    edited.presence.vibrance = 20
    result = env.library.save_edit(pid, edited)
    assert result.overridden == ["presence.vibrance", "tone.exposure"]
    detail = env.library.photo_detail(pid)
    assert detail.edit.adjustments.tone.exposure == 0.7 and detail.edit.overridden == result.overridden
    assert detail.photo.has_overrides
    assert env.library.list_photos(sort=PhotoSort.NAME).items[0].has_overrides
    assert env.reopen().edit(pid).adjustments.tone.exposure == 0.7  # survives a restart

    with pytest.raises(UnsupportedParameterError):
        env.library.save_edit(pid, AdjustmentParams.model_validate({"lens": {"profile_corrections": True}}))
    assert env.library.edit(pid).adjustments.tone.exposure == 0.7  # the rejected save changed nothing

    reset = env.library.reset_edit(pid)
    assert reset.overridden == [] and not env.library.photo_detail(pid).photo.has_overrides


def test_jpeg_originals_default_to_no_sharpening(env: Env) -> None:
    fill_folder(env.photos)
    env.run_import()
    pid = env.library.list_photos().items[0].id
    assert env.library.edit(pid).adjustments.detail.sharpening.amount == 0


def test_image_version_changes_with_the_edit(env: Env) -> None:
    fill_folder(env.photos)
    env.run_import()
    first = env.library.list_photos(sort=PhotoSort.NAME).items[0]
    edited = env.library.edit(first.id).adjustments.model_copy(deep=True)
    edited.tone.exposure = 0.5
    env.library.save_edit(first.id, edited)
    after = env.library.list_photos(sort=PhotoSort.NAME).items[0]
    assert after.image_version != first.image_version
    env.library.reset_edit(first.id)
    assert env.library.list_photos(sort=PhotoSort.NAME).items[0].image_version == first.image_version


def test_import_renders_thumbnails_in_the_background(env: Env) -> None:
    fill_folder(env.photos)
    env.run_import()
    render_job = next(j for j in env.library.jobs.list() if j.kind == "render")
    done = env.library.jobs.wait(render_job.id, TIMEOUT)
    assert done.status == JobStatus.DONE and done.total == 3
    for photo in env.library.list_photos().items:
        stored = env.library.photo(photo.id)
        assert env.library.renderer.has_thumbnail(stored, env.library.edit(photo.id))
    env.run_import()  # nothing left to render: no new render job
    assert sum(1 for j in env.library.jobs.list() if j.kind == "render") == 1


def test_before_and_after_previews(env: Env) -> None:
    fill_folder(env.photos)
    env.run_import()
    pid = env.library.list_photos(sort=PhotoSort.NAME).items[0].id
    assert env.library.preview(pid, 256) == env.library.preview(pid, 256, before=True)
    edited = env.library.edit(pid).adjustments.model_copy(deep=True)
    edited.presence.saturation = -100
    env.library.save_edit(pid, edited)
    assert env.library.preview(pid, 256) != env.library.preview(pid, 256, before=True)
