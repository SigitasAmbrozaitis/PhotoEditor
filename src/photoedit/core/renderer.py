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
from photoedit.core.errors import InvalidRequestError
from photoedit.core.render.anchors import PhotoStats, ToneAnchors, measure_stats
from photoedit.core.render.pipeline import geometry_stage, render, render_identity, render_window, shown_width
from photoedit.core.render.profile import CameraProfile, profile_for
from photoedit.core.render.stages import quantize
from photoedit.core.zoom import ZoomBases
from photoedit.models.adjustments import AdjustmentParams, Geometry
from photoedit.models.photo import TILE_SIZE, ZoomInfo, ZoomLevel
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
        zoom: ZoomBases | None = None,
        remember_stats: StatsSink | None = None,
    ) -> None:
        self._guard = guard
        self.identity = render_identity()
        self._root = cache_dir / "renders" / self.identity
        self.linear = linear or LinearCache()
        self.zoom = zoom or ZoomBases()
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

    def preview_path(
        self, photo: CatalogPhoto, edit: EffectiveEdit, long_edge: int, *, upright: bool = False
    ) -> Path:
        suffix = "-upright" if upright else ""
        return self._root / photo.id / f"{edit.revision}-{long_edge}{suffix}.jpg"

    def thumbnail_path(self, photo: CatalogPhoto, edit: EffectiveEdit) -> Path:
        return self._root / photo.id / f"{edit.revision}-thumb.jpg"

    def preview(
        self, photo: CatalogPhoto, edit: EffectiveEdit, long_edge: int, *, upright: bool = False
    ) -> bytes:
        """JPEG of ``photo`` with ``edit`` at ``long_edge`` px (never larger than the working size).

        ``upright`` leaves out the geometry: the whole photo as shot, with the edit's colors (the crop tool
        turns, straightens and crops it on screen).
        """
        path = self.preview_path(photo, edit, long_edge, upright=upright)
        with self._lock(path):
            if path.is_file():
                return path.read_bytes()
            base = self.linear.get(photo)
            anchors = self.anchors(photo, base)
            data = self._encode(
                photo, edit.adjustments, base, long_edge, PREVIEW_QUALITY, anchors, upright=upright
            )
            self._guard.write_atomic(path, data)
            return data

    def draft(self, photo: CatalogPhoto, adjustments: AdjustmentParams, long_edge: int) -> bytes:
        """JPEG of ``photo`` with ``adjustments`` that may never be saved: rendered like a preview, written
        nowhere (the in-memory base is shared with previews)."""
        base = self.linear.get(photo)
        return self._encode(photo, adjustments, base, long_edge, PREVIEW_QUALITY, self.anchors(photo, base))

    def zoom_info(self, photo: CatalogPhoto, edit: EffectiveEdit, level: ZoomLevel) -> ZoomInfo:
        """Start the decode for ``level`` if needed; once ready, the edited image's size at that level."""
        if self.zoom.request(photo, level) != "ready":
            return ZoomInfo(level=level, state="decoding")
        image = self._zoom_image(photo, edit, level)
        if image is None:  # dropped by another photo's decode just now
            return ZoomInfo(level=level, state="decoding")
        height, width = image.pixels.shape[:2]
        return ZoomInfo(level=level, state="ready", width=width, height=height)

    def tile_path(self, photo: CatalogPhoto, edit: EffectiveEdit, level: ZoomLevel, tx: int, ty: int) -> Path:
        return self._root / photo.id / f"{edit.revision}-z{level}-{tx}-{ty}.jpg"

    def tile(
        self, photo: CatalogPhoto, edit: EffectiveEdit, level: ZoomLevel, tx: int, ty: int
    ) -> bytes | None:
        """JPEG of one ``TILE_SIZE`` tile of the edited image at ``level`` (the same pixels as that part of a
        whole render at that size); None while the base is still decoding."""
        path = self.tile_path(photo, edit, level, tx, ty)
        with self._lock(path):
            if path.is_file():
                return path.read_bytes()
            self.zoom.request(photo, level)
            image = self._zoom_image(photo, edit, level)
            if image is None:
                return None
            height, width = image.pixels.shape[:2]
            left, top = tx * TILE_SIZE, ty * TILE_SIZE
            if tx < 0 or ty < 0 or left >= width or top >= height:
                raise InvalidRequestError(
                    f"tile {tx},{ty} is outside the {width}×{height} image at {level} %"
                )
            base = self.zoom.peek(photo, level)
            assert base is not None
            pixels = render_window(
                image,
                edit.adjustments,
                profile_of(photo),
                anchors=self.anchors(photo),
                full_width=shown_width(base, edit.adjustments.geometry, photo.width),
                window=(left, top, min(width, left + TILE_SIZE), min(height, top + TILE_SIZE)),
            )
            buf = io.BytesIO()
            Image.fromarray(np.asarray(quantize(pixels, 8))).save(buf, "JPEG", quality=PREVIEW_QUALITY)
            data = buf.getvalue()
            self._guard.write_atomic(path, data)
            return data

    def _zoom_image(self, photo: CatalogPhoto, edit: EffectiveEdit, level: ZoomLevel) -> LinearImage | None:
        """The zoom base with the edit's geometry applied (kept while the geometry stays the same)."""
        geometry = edit.adjustments.geometry
        return self.zoom.derived(
            photo,
            level,
            geometry.model_dump_json(),
            lambda base: geometry_stage(base, edit.adjustments, original_width=photo.width)[0],
        )

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
            data = self._encode(
                photo, edit.adjustments, base, THUMBNAIL_LONG_EDGE, THUMBNAIL_QUALITY, anchors
            )
            self._guard.write_atomic(path, data)
            return data

    def prune(self, photo_id: str, keep: set[str]) -> int:
        """Delete cached renders of ``photo_id`` whose edit revision isn't in ``keep``. Returns files
        removed.

        A render still open elsewhere (Windows refuses to delete a file the browser is being sent) is left
        for a later prune: stale renders are only clutter, and the edit that made them stale must not fail.
        """
        folder = self._root / photo_id
        if not folder.is_dir():
            return 0
        removed = 0
        for file in folder.iterdir():
            if file.name.split("-", 1)[0] not in keep:
                self._guard.assert_writable(file)
                try:
                    file.unlink(missing_ok=True)
                except PermissionError:
                    continue
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
        self.zoom.clear()
        return removed

    def _encode(
        self,
        photo: CatalogPhoto,
        adjustments: AdjustmentParams,
        base: LinearImage,
        long_edge: int,
        quality: int,
        anchors: ToneAnchors,
        *,
        upright: bool = False,
    ) -> bytes:
        if upright:
            adjustments = adjustments.model_copy(update={"geometry": Geometry()})
        pixels = render(
            base,
            adjustments,
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
