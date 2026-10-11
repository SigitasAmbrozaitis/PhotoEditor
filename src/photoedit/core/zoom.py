"""Decoded bases for the zoom view: 50 % (LibRaw half-size, unresized) and 100 % (the full decode), in RAM.

The full decode of an X-T3 RAF takes ~13 to 25 s single-threaded (the same deterministic decode as full-size
exports, PLAN §7.1), so it runs in a background thread when first asked for; the UI shows the 50 % view
enlarged meanwhile (decided 2026-10-11). Each level decodes one photo at a time on its own thread, so a quick
50 % decode never waits behind a long 100 % one. Bases are dropped least-recently-used: two at 50 % (~80 MB
each), one at 100 % (~310 MB), plus the geometry-applied image of the photo being viewed at each level.
"""

from __future__ import annotations

import math
import threading
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Literal

from photoedit.core.cache import resize_linear
from photoedit.core.catalog import CatalogPhoto
from photoedit.core.decode import LinearImage, decode_linear, is_raw
from photoedit.models.photo import ZoomLevel

type ZoomState = Literal["idle", "decoding", "ready"]

_ITEMS: dict[int, int] = {50: 2, 100: 1}


class ZoomBases:
    def __init__(self, decoder: Callable[..., LinearImage] = decode_linear) -> None:
        self._decoder = decoder
        self._lock = threading.Lock()
        self._bases: dict[int, OrderedDict[str, LinearImage]] = {50: OrderedDict(), 100: OrderedDict()}
        self._pending: dict[tuple[str, int], Future[LinearImage]] = {}
        self._errors: dict[tuple[str, int], BaseException] = {}
        self._executors = {
            level: ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"zoom{level}") for level in (50, 100)
        }
        # (photo id, level) → (key of what was applied, the image), for the photo being viewed.
        self._derived: dict[tuple[str, int], tuple[str, LinearImage]] = {}

    def state(self, photo: CatalogPhoto, level: ZoomLevel) -> ZoomState:
        with self._lock:
            if photo.id in self._bases[level]:
                return "ready"
            return "decoding" if (photo.id, level) in self._pending else "idle"

    def request(self, photo: CatalogPhoto, level: ZoomLevel) -> ZoomState:
        """Start decoding ``photo`` for ``level`` unless it is ready or already decoding. Raises the error of
        a decode that failed since the last request (and forgets it, so the one after tries again)."""
        key = (photo.id, level)
        with self._lock:
            error = self._errors.pop(key, None)
            if error is not None:
                raise error
            if photo.id in self._bases[level]:
                self._bases[level].move_to_end(photo.id)
                return "ready"
            if key not in self._pending:
                self._pending[key] = self._executors[level].submit(self._run, photo, level)
            return "decoding"

    def get(self, photo: CatalogPhoto, level: ZoomLevel, timeout: float | None = None) -> LinearImage:
        """The base, waiting for its decode (started if needed)."""
        self.request(photo, level)
        with self._lock:
            ready = self._bases[level].get(photo.id)
            future = self._pending.get((photo.id, level))
        if ready is not None:
            return ready
        if future is None:  # it finished between the two looks: the next request reports how
            return self.get(photo, level, timeout)
        return future.result(timeout)

    def peek(self, photo: CatalogPhoto, level: ZoomLevel) -> LinearImage | None:
        with self._lock:
            return self._bases[level].get(photo.id)

    def derived(
        self, photo: CatalogPhoto, level: ZoomLevel, key: str, make: Callable[[LinearImage], LinearImage]
    ) -> LinearImage | None:
        """``make(base)`` for the ready base, kept while ``key`` (what ``make`` applies) stays the same.
        None while the base isn't ready."""
        base = self.peek(photo, level)
        if base is None:
            return None
        with self._lock:
            known = self._derived.get((photo.id, level))
        if known is not None and known[0] == key:
            return known[1]
        image = make(base)
        with self._lock:
            # Only the photo being viewed keeps its derived images.
            for other in [k for k in self._derived if k[0] != photo.id]:
                del self._derived[other]
            self._derived[(photo.id, level)] = (key, image)
        return image

    def clear(self) -> None:
        with self._lock:
            for bases in self._bases.values():
                bases.clear()
            self._derived.clear()
            self._errors.clear()

    def shutdown(self) -> None:
        for executor in self._executors.values():
            executor.shutdown(wait=False, cancel_futures=True)

    def _run(self, photo: CatalogPhoto, level: ZoomLevel) -> LinearImage:
        """The decode, recording its outcome before the future completes (so a waiter sees it)."""
        key = (photo.id, level)
        try:
            image = self._decode(photo, level)
        except BaseException as error:
            with self._lock:
                self._errors[key] = error
                self._pending.pop(key, None)
            raise
        with self._lock:
            bases = self._bases[level]
            bases[photo.id] = image
            while len(bases) > _ITEMS[level]:
                evicted, _ = bases.popitem(last=False)
                self._derived.pop((evicted, level), None)
            self._pending.pop(key, None)
        return image

    def _decode(self, photo: CatalogPhoto, level: ZoomLevel) -> LinearImage:
        if level == 100:
            return self._decoder(photo.path, half_size=False)
        if is_raw(photo.path):
            return self._decoder(photo.path, half_size=True)
        # JPEG/TIFF originals decode fully anyway; halve them for 50 %.
        full = self._decoder(photo.path, half_size=False)
        height, width = full.pixels.shape[:2]
        return resize_linear(full, math.ceil(max(width, height) / 2))
