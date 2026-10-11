"""Zoom view: decoded bases at 50 / 100 % (P6a.6) and tiles rendered from them (P6a.7)."""

from __future__ import annotations

import io
import threading
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from helpers import write_jpeg
from photoedit.core.catalog import CatalogPhoto
from photoedit.core.decode import LinearImage
from photoedit.core.errors import InvalidRequestError
from photoedit.core.geometry import largest_crop
from photoedit.core.render.anchors import measure_anchors
from photoedit.core.render.pipeline import geometry_stage, render, render_window
from photoedit.core.render.profile import GENERIC
from photoedit.core.render.stages import quantize
from photoedit.core.scan import SourceKind
from photoedit.core.zoom import ZoomBases
from photoedit.models import PhotoSort
from photoedit.models.adjustments import AdjustmentParams
from photoedit.models.photo import TILE_SIZE
from test_library import Env, env  # noqa: F401 (fixture)
from test_render_pipeline import params, raw_base


def _photo(name: str = "a.RAF", pid: str = "p1") -> CatalogPhoto:
    return CatalogPhoto(
        id=pid,
        sha256="0" * 64,
        path=Path("C:/photos") / name,
        kind=SourceKind.RAW,
        file_size=1,
        mtime_ns=0,
        width=64,
        height=48,
    )


class FakeDecoder:
    """Records decodes; each one waits until released, so tests see the "decoding" state."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []
        self.release = threading.Event()
        self.release.set()
        self.fail: set[str] = set()

    def __call__(self, path: Path, *, half_size: bool) -> LinearImage:
        self.calls.append((path.name, half_size))
        self.release.wait(10)
        if path.name in self.fail:
            raise ValueError(f"cannot decode {path.name}")
        size = (24, 32) if half_size else (48, 64)
        return raw_base(*size)


@pytest.fixture
def decoder() -> FakeDecoder:
    return FakeDecoder()


@pytest.fixture
def bases(decoder: FakeDecoder) -> ZoomBases:
    zoom = ZoomBases(decoder)
    yield zoom
    zoom.shutdown()


def test_decodes_in_the_background_once(bases: ZoomBases, decoder: FakeDecoder) -> None:
    decoder.release.clear()
    photo = _photo()
    assert bases.state(photo, 100) == "idle"
    assert bases.request(photo, 100) == "decoding"
    assert bases.request(photo, 100) == "decoding"  # already running: not started again
    assert bases.peek(photo, 100) is None
    decoder.release.set()
    image = bases.get(photo, 100, timeout=10)
    assert image.pixels.shape == (48, 64, 3)
    assert bases.state(photo, 100) == "ready" and bases.request(photo, 100) == "ready"
    assert decoder.calls == [("a.RAF", False)]


def test_levels_use_their_own_decodes(bases: ZoomBases, decoder: FakeDecoder) -> None:
    photo = _photo()
    assert bases.get(photo, 50, timeout=10).pixels.shape == (24, 32, 3)
    assert bases.get(photo, 100, timeout=10).pixels.shape == (48, 64, 3)
    assert decoder.calls == [("a.RAF", True), ("a.RAF", False)]


def test_jpeg_originals_are_halved_for_50(bases: ZoomBases, decoder: FakeDecoder) -> None:
    jpeg = _photo("b.jpg")
    assert bases.get(jpeg, 50, timeout=10).pixels.shape == (24, 32, 3)
    assert decoder.calls == [("b.jpg", False)]


def test_least_recently_used_bases_are_dropped(bases: ZoomBases, decoder: FakeDecoder) -> None:
    a, b, c = _photo("a.RAF", "a"), _photo("b.RAF", "b"), _photo("c.RAF", "c")
    for photo in (a, b):
        bases.get(photo, 50, timeout=10)
    bases.request(a, 50)  # a was used last: b goes first
    bases.get(c, 50, timeout=10)
    assert [bases.state(p, 50) for p in (a, b, c)] == ["ready", "idle", "ready"]
    bases.get(a, 100, timeout=10)
    bases.get(b, 100, timeout=10)
    assert bases.state(a, 100) == "idle" and bases.state(b, 100) == "ready"  # one at 100 %


def test_a_failed_decode_is_reported_once(bases: ZoomBases, decoder: FakeDecoder) -> None:
    decoder.fail.add("a.RAF")
    photo = _photo()
    with pytest.raises(ValueError, match="cannot decode"):
        bases.get(photo, 100, timeout=10)
    with pytest.raises(ValueError, match="cannot decode"):
        bases.request(photo, 100)
    decoder.fail.clear()
    assert bases.request(photo, 100) == "decoding"  # tried again


def test_derived_images_follow_their_key(bases: ZoomBases) -> None:
    photo = _photo()
    made: list[str] = []

    def make(key: str) -> object:
        def run(base: LinearImage) -> LinearImage:
            made.append(key)
            return base

        return run

    assert bases.derived(photo, 50, "k1", make("k1")) is None  # not decoded yet
    bases.get(photo, 50, timeout=10)
    bases.derived(photo, 50, "k1", make("k1"))  # type: ignore[arg-type]
    bases.derived(photo, 50, "k1", make("k1"))  # type: ignore[arg-type]
    bases.derived(photo, 50, "k2", make("k2"))  # type: ignore[arg-type]
    assert made == ["k1", "k2"]


# ------------------------------------------------------------------ tiles


@pytest.mark.parametrize("with_geometry", [False, True])
def test_tiles_stitch_into_the_whole_render(with_geometry: bool) -> None:
    base = raw_base(height=300, width=440, seed=12)
    geometry: dict[str, object] = {}
    if with_geometry:
        geometry = {"angle": -4, "rotate": 90, "crop": largest_crop(None, -4, 300, 440).model_dump()}
    edit = params(
        geometry=geometry,
        tone={"contrast": 30, "shadows": 20},
        effects={"vignette": {"amount": -50, "roundness": 30}},
        detail={"sharpening": {"amount": 120, "radius": 2.0, "masking": 40}},
    )
    anchors = measure_anchors(base, GENERIC)
    whole = render(base, edit, GENERIC, original_width=880, anchors=anchors)
    image, full_width = geometry_stage(base, edit, original_width=880)
    height, width = image.pixels.shape[:2]
    tile = 128
    stitched = np.zeros_like(whole)
    for top in range(0, height, tile):
        for left in range(0, width, tile):
            window = (left, top, min(width, left + tile), min(height, top + tile))
            part = render_window(image, edit, GENERIC, anchors=anchors, full_width=full_width, window=window)
            stitched[top : window[3], left : window[2]] = part
    # Equal up to float rounding: vectorized loops round a row's last elements differently, so a pixel can
    # differ in the last bit depending on where its row segment ends. Far below one 8-bit level.
    np.testing.assert_allclose(stitched, whole, rtol=0, atol=1e-6)
    np.testing.assert_array_equal(quantize(stitched, 8), quantize(whole, 8))


def test_render_window_rejects_a_window_outside() -> None:
    base = raw_base()
    anchors = measure_anchors(base, GENERIC)
    with pytest.raises(InvalidRequestError, match="outside"):
        render_window(
            base, AdjustmentParams(), GENERIC, anchors=anchors, full_width=90, window=(80, 0, 100, 10)
        )


def test_library_tiles(env: Env) -> None:  # noqa: F811 (fixture)
    write_jpeg(env.photos / "big.jpg", (180, 90, 40), size=(1200, 700))
    env.run_import()
    pid = env.library.list_photos(sort=PhotoSort.NAME).items[0].id
    info = env.library.zoom_info(pid, 100)
    if info.state == "decoding":
        env.library.renderer.zoom.get(env.library.photo(pid), 100, timeout=30)
        info = env.library.zoom_info(pid, 100)
    assert (info.state, info.width, info.height, info.tile_size) == ("ready", 1200, 700, TILE_SIZE)
    first = env.library.tile(pid, 100, 0, 0)
    assert first is not None
    with Image.open(io.BytesIO(first)) as tile:
        assert tile.size == (TILE_SIZE, TILE_SIZE)
    edge = env.library.tile(pid, 100, 2, 1)
    assert edge is not None
    with Image.open(io.BytesIO(edge)) as tile:
        assert tile.size == (1200 - 2 * TILE_SIZE, 700 - TILE_SIZE)
    with pytest.raises(InvalidRequestError, match="outside"):
        env.library.tile(pid, 100, 3, 0)
    # A new edit renders new tiles; the before view keeps the old look.
    edited = env.library.edit(pid).adjustments.model_copy(deep=True)
    edited.presence.saturation = -100
    env.library.save_edit(pid, edited)
    assert env.library.tile(pid, 100, 0, 0) != first
    assert env.library.tile(pid, 100, 0, 0, before=True) == first
