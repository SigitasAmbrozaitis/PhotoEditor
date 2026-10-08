"""Disk cache of thumbnails and previews (disposable: deleting ``cache/`` only costs time).

Files live under a folder named after the decoder's render identity, so a LibRaw/Pillow upgrade or a
``DECODER_VERSION`` bump never serves pixels made by an older decoder.
"""

from __future__ import annotations

import dataclasses
import io
import shutil
import threading
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from photoedit.core.catalog import CatalogPhoto
from photoedit.core.decode import (
    PREVIEW,
    LinearImage,
    decode,
    decode_linear,
    is_raw,
    oriented_image,
    read_raw_info,
    render_identity,
)
from photoedit.safety import PathGuard

THUMBNAIL_LONG_EDGE = 400
THUMBNAIL_QUALITY = 85
PREVIEW_QUALITY = 92
RESIZED_QUALITY = 90
_MEMORY_ITEMS = 64  # resized previews kept in RAM (about 0.2 to 0.5 MB each)


class ImageCache:
    def __init__(self, cache_dir: Path, guard: PathGuard, identity: str | None = None) -> None:
        self._root = cache_dir
        self._guard = guard
        self.identity = identity or render_identity()
        self._memory: OrderedDict[tuple[str, int], bytes] = OrderedDict()
        self._memory_lock = threading.Lock()
        self._build_locks: dict[Path, threading.Lock] = {}
        self._build_locks_lock = threading.Lock()

    # ---- thumbnails

    def thumbnail_path(self, photo_id: str) -> Path:
        return self._root / "thumbs" / self.identity / f"{photo_id}.jpg"

    def has_thumbnail(self, photo_id: str) -> bool:
        return self.thumbnail_path(photo_id).is_file()

    def put_thumbnail(self, photo_id: str, image: Image.Image) -> bytes:
        """Store a thumbnail made from a decoded upright image (import has the embedded JPEG at hand)."""
        data = _encode(_fit(image, THUMBNAIL_LONG_EDGE), THUMBNAIL_QUALITY)
        self._guard.write_atomic(self.thumbnail_path(photo_id), data)
        return data

    def thumbnail(self, photo: CatalogPhoto) -> bytes:
        path = self.thumbnail_path(photo.id)
        with self._build_lock(path):
            if path.is_file():
                return path.read_bytes()
            return self.put_thumbnail(photo.id, _thumbnail_source(photo.path))

    # ---- previews

    def preview_path(self, photo_id: str) -> Path:
        return self._root / "previews" / self.identity / f"{photo_id}.jpg"

    def preview(self, photo: CatalogPhoto, long_edge: int | None = None) -> bytes:
        """The half-size preview, scaled down to ``long_edge`` when that is smaller."""
        base = self._base_preview(photo)
        if long_edge is None:
            return base
        key = (photo.id, long_edge)
        with self._memory_lock:
            if key in self._memory:
                self._memory.move_to_end(key)
                return self._memory[key]
        with Image.open(io.BytesIO(base)) as image:
            if max(image.size) <= long_edge:
                return base
            data = _encode(_fit(image, long_edge), RESIZED_QUALITY)
        with self._memory_lock:
            self._memory[key] = data
            while len(self._memory) > _MEMORY_ITEMS:
                self._memory.popitem(last=False)
        return data

    def _base_preview(self, photo: CatalogPhoto) -> bytes:
        path = self.preview_path(photo.id)
        with self._build_lock(path):
            if path.is_file():
                return path.read_bytes()
            data = _encode(Image.fromarray(decode(photo.path, PREVIEW)), PREVIEW_QUALITY)
            self._guard.write_atomic(path, data)
            return data

    # ---- maintenance

    def clear(self) -> int:
        """Delete every cached file. Returns how many were removed."""
        removed = 0
        for sub in ("thumbs", "previews"):
            folder = self._root / sub
            if folder.is_dir():
                self._guard.assert_writable(folder)
                removed += sum(1 for p in folder.rglob("*") if p.is_file())
                shutil.rmtree(folder)
        with self._memory_lock:
            self._memory.clear()
        return removed

    def _build_lock(self, path: Path) -> threading.Lock:
        """One lock per file, so two requests for the same preview decode the RAW once, not twice."""
        with self._build_locks_lock:
            return self._build_locks.setdefault(path, threading.Lock())


def _thumbnail_source(path: Path) -> Image.Image:
    if is_raw(path):
        info = read_raw_info(path)
        if info.embedded_jpeg is not None:
            return oriented_image(info.embedded_jpeg, info.flip)
        return Image.fromarray(decode(path, PREVIEW))
    with Image.open(path) as image:
        image.draft("RGB", (THUMBNAIL_LONG_EDGE * 2, THUMBNAIL_LONG_EDGE * 2))
        return ImageOps.exif_transpose(image).convert("RGB")


def _fit(image: Image.Image, long_edge: int) -> Image.Image:
    scale = long_edge / max(image.size)
    if scale >= 1:
        return image
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(size, Image.Resampling.LANCZOS)


def _encode(image: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, "JPEG", quality=quality, optimize=True)
    return buf.getvalue()


# ----------------------------------------------------------------- linear bases (render input)

LINEAR_LONG_EDGE = 2048
_LINEAR_ITEMS = 8  # ≈ 33 MB each at 2048 px: the open photo and its neighbours


class LinearCache:
    """Decoded scene-linear images at preview working size, kept in RAM only.

    A disk copy would cost ~16 MB per photo even as float16; rendered previews are cached on disk instead, so
    reopening a photo is instant and only editing it needs this base (decoded once, ~1.3 s for an X-T3 RAF).
    """

    def __init__(
        self, items: int = _LINEAR_ITEMS, decoder: Callable[..., LinearImage] = decode_linear
    ) -> None:
        self._items = items
        self._decoder = decoder
        self._memory: OrderedDict[str, LinearImage] = OrderedDict()
        self._lock = threading.Lock()
        self._build_locks: dict[str, threading.Lock] = {}

    def get(self, photo: CatalogPhoto) -> LinearImage:
        with self._lock:
            build_lock = self._build_locks.setdefault(photo.id, threading.Lock())
        with build_lock:
            with self._lock:
                if photo.id in self._memory:
                    self._memory.move_to_end(photo.id)
                    return self._memory[photo.id]
            # RAWs: LibRaw's half-size decode (no demosaic interpolation) is already larger than the base.
            image = resize_linear(self._decoder(photo.path, half_size=is_raw(photo.path)), LINEAR_LONG_EDGE)
            with self._lock:
                self._memory[photo.id] = image
                while len(self._memory) > self._items:
                    self._memory.popitem(last=False)
            return image

    def clear(self) -> None:
        with self._lock:
            self._memory.clear()


def resize_linear(image: LinearImage, long_edge: int) -> LinearImage:
    """Scale down so the long edge is at most ``long_edge`` (area averaging: correct on linear data)."""
    height, width = image.pixels.shape[:2]
    scale = long_edge / max(height, width)
    if scale >= 1:
        return image
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    pixels = cv2.resize(image.pixels, size, interpolation=cv2.INTER_AREA)
    return dataclasses.replace(image, pixels=np.ascontiguousarray(pixels, dtype=np.float32))
