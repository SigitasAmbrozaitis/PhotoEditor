"""Read-only folder browsing for the "Open folder" dialog. Lists names only; never opens a file."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

from photoedit.core.errors import InvalidRequestError, NotFoundError
from photoedit.core.scan import ScanError, scan_folder
from photoedit.models.fs import DirEntry, DirListing

_HIDDEN_ATTRIBUTES = getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0) | getattr(stat, "FILE_ATTRIBUTE_SYSTEM", 0)


def list_dirs(path: Path | None) -> DirListing:
    """Subfolders of ``path`` with their photo counts; the drives (or ``/``) when ``path`` is None."""
    if path is None:
        return _roots()
    if not path.is_absolute():
        raise InvalidRequestError(f"folder path must be absolute: {path}")
    if not path.exists():
        raise NotFoundError(f"folder not found: {path}")
    if not path.is_dir():
        raise InvalidRequestError(f"not a folder: {path}")
    folder = path.resolve()
    try:
        with os.scandir(folder) as found:
            subfolders = sorted(
                (Path(e.path) for e in found if _is_visible_dir(e)), key=lambda p: p.name.casefold()
            )
    except OSError as exc:
        raise InvalidRequestError(f"cannot read folder {folder}: {exc.strerror or exc}") from exc
    parent = folder.parent if folder.parent != folder else None
    return DirListing(
        path=folder.as_posix(),
        parent=parent.as_posix() if parent else None,
        photo_count=_photo_count(folder) or 0,
        entries=[DirEntry(name=p.name, path=p.as_posix(), photo_count=_photo_count(p)) for p in subfolders],
    )


def _roots() -> DirListing:
    if sys.platform == "win32":
        drives = [Path(d) for d in os.listdrives()]
        entries = [DirEntry(name=str(d).rstrip("\\"), path=d.as_posix(), photo_count=None) for d in drives]
    else:
        entries = [DirEntry(name="/", path="/", photo_count=None)]
    return DirListing(path=None, parent=None, photo_count=0, entries=entries)


def _is_visible_dir(entry: os.DirEntry[str]) -> bool:
    try:
        if not entry.is_dir() or entry.name.startswith((".", "$")):
            return False
        attributes = getattr(entry.stat(), "st_file_attributes", 0)
    except OSError:
        return False
    return not attributes & _HIDDEN_ATTRIBUTES


def _photo_count(folder: Path) -> int | None:
    try:
        return len(scan_folder(folder).photos)
    except ScanError:
        return None
