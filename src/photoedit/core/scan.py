"""Find the photos in a folder. Only directory listings are read here; no file is opened."""

from __future__ import annotations

import os
from collections import defaultdict
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

# RAW formats LibRaw decodes that we accept. Only RAF is tested against real files (the X-T3 samples).
RAW_EXTENSIONS = frozenset({".raf", ".cr2", ".cr3", ".nef", ".arw", ".orf", ".rw2", ".dng", ".pef", ".srw"})
JPEG_EXTENSIONS = frozenset({".jpg", ".jpeg"})
RASTER_EXTENSIONS = JPEG_EXTENSIONS | frozenset({".tif", ".tiff"})


class ScanError(ValueError):
    """The folder can't be scanned (missing, not a folder, not readable)."""


class SourceKind(StrEnum):
    RAW = "raw"
    RASTER = "raster"


class ScannedPhoto(BaseModel):
    """One photo: a master file plus, for a RAW, the camera JPEG saved next to it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    kind: SourceKind
    sidecar_jpeg: Path | None = None


class SkippedFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    reason: str


class ScanResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    folder: Path
    photos: list[ScannedPhoto]
    skipped: list[SkippedFile]


def scan_folder(folder: Path, *, recursive: bool = False) -> ScanResult:
    """List the photos in ``folder``.

    RAW + JPEG files with the same name become one photo with the RAW as master.
    """
    root = _checked_folder(folder)
    files: list[Path] = []
    if recursive:
        # followlinks=False: a symlinked folder pointing at an ancestor must not loop forever.
        for dirpath, dirnames, filenames in os.walk(root, onerror=_raise_scan_error, followlinks=False):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            files.extend(Path(dirpath) / name for name in filenames)
    else:
        files.extend(_list_files(root))

    photos: list[ScannedPhoto] = []
    skipped: list[SkippedFile] = []
    groups: dict[tuple[str, str], list[Path]] = defaultdict(list)
    for path in files:
        suffix = path.suffix.lower()
        if path.name.startswith("."):
            skipped.append(SkippedFile(path=path, reason="hidden file"))
        elif suffix in RAW_EXTENSIONS or suffix in RASTER_EXTENSIONS:
            # Windows file names are case-insensitive, so DSCF1.RAF and dscf1.jpg belong together.
            groups[(os.path.normcase(str(path.parent)), path.stem.casefold())].append(path)
        else:
            reason = f"unsupported file type ({suffix or 'no extension'})"
            skipped.append(SkippedFile(path=path, reason=reason))

    for members in groups.values():
        photos.extend(_pair(sorted(members, key=_sort_key)))

    photos.sort(key=lambda p: _sort_key(p.path))
    skipped.sort(key=lambda s: _sort_key(s.path))
    return ScanResult(folder=root, photos=photos, skipped=skipped)


def _pair(members: list[Path]) -> list[ScannedPhoto]:
    """Turn files sharing a name into photos.

    The first JPEG next to the first RAW is its sidecar; everything else stands alone.
    """
    raws = [p for p in members if p.suffix.lower() in RAW_EXTENSIONS]
    rasters = [p for p in members if p.suffix.lower() in RASTER_EXTENSIONS]
    sidecar = next((p for p in rasters if p.suffix.lower() in JPEG_EXTENSIONS), None) if raws else None
    photos = [
        ScannedPhoto(path=raw, kind=SourceKind.RAW, sidecar_jpeg=sidecar if i == 0 else None)
        for i, raw in enumerate(raws)
    ]
    photos.extend(ScannedPhoto(path=p, kind=SourceKind.RASTER) for p in rasters if p != sidecar)
    return photos


def _checked_folder(folder: Path) -> Path:
    root = folder.expanduser()
    if not root.is_absolute():
        raise ScanError(f"folder path must be absolute: {folder}")
    if not root.exists():
        raise ScanError(f"folder not found: {folder}")
    if not root.is_dir():
        raise ScanError(f"not a folder: {folder}")
    return root.resolve()


def _list_files(root: Path) -> list[Path]:
    try:
        with os.scandir(root) as entries:
            return [Path(e.path) for e in entries if e.is_file()]
    except OSError as exc:
        raise ScanError(f"cannot read folder {root}: {exc.strerror or exc}") from exc


def _raise_scan_error(exc: OSError) -> None:
    raise ScanError(f"cannot read folder {exc.filename}: {exc.strerror or exc}") from exc


def _sort_key(path: Path) -> str:
    return os.path.normcase(str(path))
