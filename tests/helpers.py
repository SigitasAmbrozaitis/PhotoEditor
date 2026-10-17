"""Shared test helpers (synthetic photos). Everything is written into the caller's tmp_path."""

from __future__ import annotations

import io
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path
from typing import Any

from PIL import Image
from PIL.TiffImagePlugin import IFDRational


def write_jpeg(
    path: Path,
    color: tuple[int, int, int],
    size: tuple[int, int] = (320, 200),
    *,
    date: str | None = None,
    camera: str | None = None,
    exposure: tuple[float, Fraction, int] | None = None,
) -> Path:
    """A one-color JPEG. ``exposure`` = (f-number, exposure time in seconds, ISO) written to EXIF."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tags = Image.Exif()
    if date is not None:
        tags.get_ifd(0x8769)[0x9003] = date
    if exposure is not None:
        aperture, seconds, iso = exposure
        exif = tags.get_ifd(0x8769)
        exif[0x829D] = IFDRational(int(aperture * 10), 10)
        exif[0x829A] = IFDRational(seconds.numerator, seconds.denominator)
        exif[0x8827] = iso
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


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


@contextmanager
def serve(app: Any) -> Iterator[str]:
    """Run ``app`` under uvicorn on a free local port (for streams and real HTTP clients); yields its URL."""
    import uvicorn

    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "server did not start"
        time.sleep(0.02)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
