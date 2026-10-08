"""Shared test helpers (synthetic photos). Everything is written into the caller's tmp_path."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image


def write_jpeg(
    path: Path,
    color: tuple[int, int, int],
    size: tuple[int, int] = (320, 200),
    *,
    date: str | None = None,
    camera: str | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tags = Image.Exif()
    if date is not None:
        tags.get_ifd(0x8769)[0x9003] = date
    if camera is not None:
        tags[0x0110] = camera
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG", quality=90, exif=tags.tobytes())
    path.write_bytes(buf.getvalue())
    return path


def fill_folder(folder: Path) -> None:
    """Three JPEGs (two dated, one portrait) and a movie file that must be skipped."""
    write_jpeg(folder / "a.jpg", (255, 0, 0), date="2026:08:11 09:00:00", camera="Cam A")
    write_jpeg(folder / "b.jpg", (0, 255, 0), date="2026:08:11 07:00:00")
    write_jpeg(folder / "c.jpg", (0, 0, 255), size=(200, 320))
    (folder / "clip.mov").write_bytes(b"movie")
