"""Golden rule 1: import, thumbnails and previews never change, add or remove a file in a photo folder."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path

import pytest

from helpers import fill_folder, write_jpeg
from photoedit.config import load_settings
from photoedit.models import JobStatus
from photoedit.services import Services

type Snapshot = dict[str, tuple[str, int, int]]


def snapshot(folder: Path) -> Snapshot:
    """sha256, size and mtime of every file under ``folder`` (the listing is the dict's keys)."""
    result: Snapshot = {}
    for path in sorted(folder.rglob("*")):
        if path.is_file():
            stat = path.stat()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result[path.relative_to(folder).as_posix()] = (digest, stat.st_size, stat.st_mtime_ns)
    return result


@pytest.fixture
def services(tmp_path: Path) -> Iterator[Services]:
    settings = load_settings(tmp_path / "missing.toml", project_root=tmp_path / "project")
    svc = Services(settings)
    yield svc
    svc.close()


def _exercise(
    services: Services, folder: Path, *, previews: int | None = None, subfolders: bool = False
) -> None:
    job = services.library.import_folder(folder, include_subfolders=subfolders)
    done = services.jobs.wait(job.id, timeout=600)
    assert done.status == JobStatus.DONE and done.failed == 0, done.summary
    photos = services.library.list_photos(limit=500).items
    for photo in photos:
        services.library.thumbnail(photo.id)
    for photo in photos[:previews]:
        services.library.preview(photo.id, 1600)
    services.library.photo_detail(photos[0].id)


def test_synthetic_folder_is_untouched(services: Services, tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    fill_folder(photos)
    write_jpeg(photos / "sub" / "d.jpg", (9, 9, 9))
    (photos / "e.RAF").write_bytes(b"not really a raw")  # fails to decode: must still leave no trace
    before = snapshot(photos)

    job = services.library.import_folder(photos, include_subfolders=True)
    services.jobs.wait(job.id, timeout=60)
    for photo in services.library.list_photos().items:
        services.library.thumbnail(photo.id)
        services.library.preview(photo.id, 512)
    services.library.import_folder(photos, include_subfolders=True)  # re-import too
    services.jobs.wait(services.jobs.list()[0].id, timeout=60)

    assert snapshot(photos) == before
    assert not services.guard.is_writable(photos / "anything.jpg")
    assert not services.guard.is_writable(photos / "sub" / "anything.jpg")


@pytest.mark.golden
@pytest.mark.slow
def test_real_sample_folder_is_untouched(services: Services, sample_photos_dir: Path) -> None:
    before = snapshot(sample_photos_dir)
    _exercise(services, sample_photos_dir, previews=3)
    assert snapshot(sample_photos_dir) == before
