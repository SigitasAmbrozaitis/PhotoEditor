"""Rendering photos for viewing: previews and thumbnails through the pipeline, cached on disk.

Cache files sit under ``cache/renders/<render identity>/<photo id>/`` and are named by edit revision and size,
so a new edit, a new engine/library version or a new size never serves stale pixels.
"""

from __future__ import annotations

import io
import math
import shutil
import threading
from collections.abc import Callable
from pathlib import Path

import numpy as np
from PIL import Image

from photoedit.core.cache import THUMBNAIL_LONG_EDGE, LinearCache, resize_linear
from photoedit.core.catalog import CatalogPhoto
from photoedit.core.decode import LinearImage, decode_linear, is_raw
from photoedit.core.edits import EffectiveEdit
from photoedit.core.render.anchors import PhotoStats, ToneAnchors, measure_stats
from photoedit.core.render.pipeline import render, render_identity
from photoedit.core.render.profile import CameraProfile, profile_for
from photoedit.core.render.stages import quantize
from photoedit.safety import PathGuard

PREVIEW_QUALITY = 90
THUMBNAIL_QUALITY = 85

# Stores a photo's measurements (photo id, PhotoStats fields, render identity), e.g. in the catalog.
type StatsSink = Callable[[str, dict[str, float], str], None]


def profile_of(photo: CatalogPhoto) -> CameraProfile | None:
    """The camera profile a photo renders with (None for JPEG/TIFF originals), DR compensation included.

    Fujifilm DR200/DR400 shots are underexposed by 1/2 EV on purpose; the camera's JPEG brings that back,
    and so do we.
    """
    if not is_raw(photo.path):
        return None
    profile = profile_for(photo.camera)
    if photo.dynamic_range and photo.dynamic_range > 100:
        boost = math.log2(photo.dynamic_range / 100)
        profile = profile.model_copy(update={"baseline_exposure": profile.baseline_exposure + boost})
    return profile


def stored_stats(photo: CatalogPhoto, identity: str) -> PhotoStats | None:
    """The catalog's measurements of ``photo`` if they are complete and from render identity ``identity``."""
    values = {
        "black": photo.tone_black,
        "white": photo.tone_white,
        "middle": photo.tone_middle,
        "neutral_temperature": photo.neutral_temperature,
        "neutral_tint": photo.neutral_tint,
    }
    if photo.tone_anchors_identity != identity or any(v is None for v in values.values()):
        return None
    return PhotoStats.model_validate(values)


class Renderer:
    def __init__(
        self,
        cache_dir: Path,
        guard: PathGuard,
        linear: LinearCache | None = None,
        *,
        remember_stats: StatsSink | None = None,
    ) -> None:
        self._guard = guard
        self.identity = render_identity()
        self._root = cache_dir / "renders" / self.identity
        self.linear = linear or LinearCache()
        self._remember_stats = remember_stats
        self._stats: dict[str, PhotoStats] = {}
        self._locks: dict[Path, threading.Lock] = {}
        self._locks_lock = threading.Lock()

    def anchors(self, photo: CatalogPhoto, base: LinearImage | None = None) -> ToneAnchors:
        return self.stats(photo, base).anchors

    def stats(self, photo: CatalogPhoto, base: LinearImage | None = None) -> PhotoStats:
        """The photo's measurements: the stored ones if this engine measured them, else measured now (on
        ``base``, the in-memory base, or a fresh decode) and handed to ``remember_stats``."""
        stored = stored_stats(photo, self.identity)
        if stored is not None:
            return stored
        with self._locks_lock:
            known = self._stats.get(photo.id)
        if known is not None:
            return known
        if base is None:
            base = self.linear.peek(photo.id) or decode_linear(photo.path, half_size=is_raw(photo.path))
        measured = measure_stats(base, profile_of(photo))
        with self._locks_lock:
            self._stats[photo.id] = measured
        if self._remember_stats is not None:
            self._remember_stats(photo.id, measured.model_dump(), self.identity)
        return measured

    def preview_path(self, photo: CatalogPhoto, edit: EffectiveEdit, long_edge: int) -> Path:
        return self._root / photo.id / f"{edit.revision}-{long_edge}.jpg"

    def thumbnail_path(self, photo: CatalogPhoto, edit: EffectiveEdit) -> Path:
        return self._root / photo.id / f"{edit.revision}-thumb.jpg"

    def preview(self, photo: CatalogPhoto, edit: EffectiveEdit, long_edge: int) -> bytes:
        """JPEG of ``photo`` with ``edit`` at ``long_edge`` px (never larger than the working size)."""
        path = self.preview_path(photo, edit, long_edge)
        with self._lock(path):
            if path.is_file():
                return path.read_bytes()
            base = self.linear.get(photo)
            data = self._encode(photo, edit, base, long_edge, PREVIEW_QUALITY, self.anchors(photo, base))
            self._guard.write_atomic(path, data)
            return data

    def has_thumbnail(self, photo: CatalogPhoto, edit: EffectiveEdit) -> bool:
        return self.thumbnail_path(photo, edit).is_file()

    def thumbnail(self, photo: CatalogPhoto, edit: EffectiveEdit) -> bytes:
        """Rendered thumbnail. Uses the in-memory base when the photo is open; otherwise decodes without
        caching, so a batch of thumbnails doesn't push the photo being edited out of memory."""
        path = self.thumbnail_path(photo, edit)
        with self._lock(path):
            if path.is_file():
                return path.read_bytes()
            base = self.linear.peek(photo.id)
            if base is None:
                decoded = decode_linear(photo.path, half_size=is_raw(photo.path))
                anchors = self.anchors(photo, decoded)
                base = resize_linear(decoded, 2 * THUMBNAIL_LONG_EDGE)
            else:
                anchors = self.anchors(photo, base)
            data = self._encode(photo, edit, base, THUMBNAIL_LONG_EDGE, THUMBNAIL_QUALITY, anchors)
            self._guard.write_atomic(path, data)
            return data

    def prune(self, photo_id: str, keep: set[str]) -> int:
        """Delete cached renders of ``photo_id`` whose edit revision isn't in ``keep``. Returns files
        removed."""
        folder = self._root / photo_id
        if not folder.is_dir():
            return 0
        removed = 0
        for file in folder.iterdir():
            if file.name.split("-", 1)[0] not in keep:
                self._guard.assert_writable(file)
                file.unlink(missing_ok=True)
                removed += 1
        return removed

    def clear(self) -> int:
        """Delete all cached renders (every render identity). Returns files removed."""
        root = self._root.parent
        if not root.is_dir():
            return 0
        self._guard.assert_writable(root)
        removed = sum(1 for p in root.rglob("*") if p.is_file())
        shutil.rmtree(root)
        self.linear.clear()
        return removed

    def _encode(
        self,
        photo: CatalogPhoto,
        edit: EffectiveEdit,
        base: LinearImage,
        long_edge: int,
        quality: int,
        anchors: ToneAnchors,
    ) -> bytes:
        pixels = render(
            base,
            edit.adjustments,
            profile_of(photo),
            original_width=photo.width,
            long_edge=long_edge,
            anchors=anchors,
        )
        buf = io.BytesIO()
        Image.fromarray(np.asarray(quantize(pixels, 8))).save(buf, "JPEG", quality=quality, optimize=True)
        return buf.getvalue()

    def _lock(self, path: Path) -> threading.Lock:
        with self._locks_lock:
            return self._locks.setdefault(path, threading.Lock())
