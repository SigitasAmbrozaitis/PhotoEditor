from __future__ import annotations

import hashlib
import io
import threading
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from photoedit.core import cache as cache_module
from photoedit.core.cache import THUMBNAIL_LONG_EDGE, ImageCache
from photoedit.core.catalog import CatalogPhoto, photo_id
from photoedit.core.scan import SourceKind
from photoedit.safety import PathGuard, WriteNotAllowedError


def _jpeg_photo(folder: Path, name: str = "a.jpg", size: tuple[int, int] = (1200, 800)) -> CatalogPhoto:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    Image.new("RGB", size, (200, 120, 40)).save(path, "JPEG", quality=90)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    return CatalogPhoto(
        id=photo_id(sha),
        sha256=sha,
        path=path,
        kind=SourceKind.RASTER,
        file_size=path.stat().st_size,
        mtime_ns=path.stat().st_mtime_ns,
        width=size[0],
        height=size[1],
    )


@pytest.fixture
def setup(tmp_path: Path) -> tuple[ImageCache, Path, Path]:
    cache_dir, photos = tmp_path / "cache", tmp_path / "photos"
    guard = PathGuard(writable_roots=[cache_dir], protected_roots=[photos])
    return ImageCache(cache_dir, guard, identity="test-id"), cache_dir, photos


def _size(data: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(data)).size


def test_thumbnail_is_built_once_then_read_from_disk(
    setup: tuple[ImageCache, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    cache, cache_dir, photos = setup
    photo = _jpeg_photo(photos)
    first = cache.thumbnail(photo)
    assert max(_size(first)) == THUMBNAIL_LONG_EDGE
    assert cache.thumbnail_path(photo.id) == cache_dir / "thumbs" / "test-id" / f"{photo.id}.jpg"
    assert cache.has_thumbnail(photo.id)

    def fail(path: Path) -> Image.Image:
        raise AssertionError("must not rebuild a cached thumbnail")

    monkeypatch.setattr(cache_module, "_thumbnail_source", fail)
    assert cache.thumbnail(photo) == first


def test_put_thumbnail_from_decoded_image(setup: tuple[ImageCache, Path, Path]) -> None:
    cache, _, _ = setup
    data = cache.put_thumbnail("abc", Image.new("RGB", (300, 900)))
    assert _size(data) == (133, 400)
    assert cache.thumbnail_path("abc").read_bytes() == data


def test_small_images_are_not_enlarged(setup: tuple[ImageCache, Path, Path]) -> None:
    cache, _, photos = setup
    photo = _jpeg_photo(photos, size=(120, 90))
    assert _size(cache.thumbnail(photo)) == (120, 90)


def test_render_identity_change_invalidates(tmp_path: Path) -> None:
    cache_dir, photos = tmp_path / "cache", tmp_path / "photos"
    guard = PathGuard(writable_roots=[cache_dir])
    photo = _jpeg_photo(photos)
    old = ImageCache(cache_dir, guard, identity="dec1")
    old.thumbnail(photo)
    new = ImageCache(cache_dir, guard, identity="dec2")
    assert not new.has_thumbnail(photo.id)
    new.thumbnail(photo)
    assert old.thumbnail_path(photo.id) != new.thumbnail_path(photo.id)


def test_default_identity_is_the_decoders(tmp_path: Path) -> None:
    from photoedit.core.decode import render_identity

    assert ImageCache(tmp_path, PathGuard(writable_roots=[tmp_path])).identity == render_identity()


def test_cache_inside_a_protected_photo_folder_is_refused(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    photo = _jpeg_photo(photos)
    guard = PathGuard(writable_roots=[tmp_path], protected_roots=[photos])
    cache = ImageCache(photos / "cache", guard, identity="x")  # misconfigured: cache inside the photo folder
    with pytest.raises(WriteNotAllowedError):
        cache.thumbnail(photo)
    assert sorted(p.name for p in photos.iterdir()) == ["a.jpg"]


def test_originals_are_untouched(setup: tuple[ImageCache, Path, Path]) -> None:
    cache, _, photos = setup
    photo = _jpeg_photo(photos)
    before = (photo.path.read_bytes(), photo.path.stat().st_mtime_ns)
    cache.thumbnail(photo)
    assert (photo.path.read_bytes(), photo.path.stat().st_mtime_ns) == before
    assert [p.name for p in photos.iterdir()] == ["a.jpg"]


def test_concurrent_requests_decode_once(
    setup: tuple[ImageCache, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    cache, _, photos = setup
    photo = _jpeg_photo(photos)
    calls: list[int] = []
    real_source = cache_module._thumbnail_source

    def counting(path: Path) -> Image.Image:
        calls.append(1)
        return real_source(path)

    monkeypatch.setattr(cache_module, "_thumbnail_source", counting)
    threads = [threading.Thread(target=cache.thumbnail, args=(photo,)) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(calls) == 1


def test_clear_removes_everything(setup: tuple[ImageCache, Path, Path]) -> None:
    cache, cache_dir, photos = setup
    photo = _jpeg_photo(photos)
    cache.thumbnail(photo)
    assert cache.clear() == 1
    assert not (cache_dir / "thumbs").exists()
    assert cache.clear() == 0


@pytest.mark.golden
def test_real_raf_embedded_thumbnail(sample_raw: Path, tmp_path: Path) -> None:
    sha = hashlib.sha256(sample_raw.read_bytes()).hexdigest()
    photo = CatalogPhoto(
        id=photo_id(sha),
        sha256=sha,
        path=sample_raw,
        kind=SourceKind.RAW,
        file_size=sample_raw.stat().st_size,
        mtime_ns=sample_raw.stat().st_mtime_ns,
        width=4170,
        height=6246,
    )
    guard = PathGuard(writable_roots=[tmp_path], protected_roots=[sample_raw.parent])
    cache = ImageCache(tmp_path / "cache", guard)
    thumb = _size(cache.thumbnail(photo))
    assert max(thumb) == THUMBNAIL_LONG_EDGE and thumb[0] < thumb[1]  # the portrait shot is upright
    assert hashlib.sha256(sample_raw.read_bytes()).hexdigest() == sha


# ----------------------------------------------------------------- linear bases


def _linear(height: int, width: int, value: float = 0.25) -> object:
    from photoedit.core.decode import LinearImage

    return LinearImage(
        pixels=np.full((height, width, 3), value, dtype=np.float32), to_rec2020=np.eye(3), is_raw=False
    )


def test_linear_cache_decodes_once_and_resizes(tmp_path: Path) -> None:
    from photoedit.core.cache import LINEAR_LONG_EDGE, LinearCache

    photo = _jpeg_photo(tmp_path / "photos")
    calls: list[tuple[Path, bool]] = []

    def decoder(path: Path, *, half_size: bool) -> object:
        calls.append((path, half_size))
        return _linear(3000, 4500)

    cache = LinearCache(decoder=decoder)  # type: ignore[arg-type]
    first = cache.get(photo)
    assert first.pixels.shape == (1365, LINEAR_LONG_EDGE, 3)
    np.testing.assert_allclose(first.pixels, 0.25, atol=1e-6)  # area averaging keeps flat areas exact
    assert cache.get(photo) is first
    assert calls == [(photo.path, False)]  # JPEG originals decode at full size, then scale down


def test_linear_cache_evicts_least_recently_used(tmp_path: Path) -> None:
    from photoedit.core.cache import LinearCache

    photos = [_jpeg_photo(tmp_path / "photos", f"{i}.jpg", size=(64 + i, 48)) for i in range(3)]
    decoded: list[str] = []

    def decoder(path: Path, *, half_size: bool) -> object:
        decoded.append(path.name)
        return _linear(10, 10)

    cache = LinearCache(items=2, decoder=decoder)  # type: ignore[arg-type]
    cache.get(photos[0])
    cache.get(photos[1])
    cache.get(photos[0])  # 0 is now the most recent
    cache.get(photos[2])  # evicts 1
    cache.get(photos[0])
    cache.get(photos[1])
    assert decoded == ["0.jpg", "1.jpg", "2.jpg", "1.jpg"]


def test_resize_linear_keeps_mean_and_never_enlarges() -> None:
    from photoedit.core.cache import resize_linear

    rng = np.random.default_rng(1)
    image = _linear(400, 600)
    image = type(image)(
        pixels=rng.uniform(0, 1, (400, 600, 3)).astype(np.float32), to_rec2020=np.eye(3), is_raw=False
    )  # type: ignore[call-arg, attr-defined]
    small = resize_linear(image, 300)  # type: ignore[arg-type]
    assert small.pixels.shape == (200, 300, 3) and small.pixels.dtype == np.float32
    assert float(small.pixels.mean()) == pytest.approx(float(image.pixels.mean()), abs=1e-4)  # type: ignore[attr-defined]
    assert resize_linear(image, 5000) is image  # type: ignore[arg-type]


@pytest.mark.golden
def test_real_raf_linear_base(sample_raw: Path) -> None:
    from photoedit.core.cache import LINEAR_LONG_EDGE, LinearCache

    photo = CatalogPhoto(
        id="x",
        sha256="0" * 64,
        path=sample_raw,
        kind=SourceKind.RAW,
        file_size=1,
        mtime_ns=1,
        width=4170,
        height=6246,
    )
    base = LinearCache().get(photo)
    height, width = base.pixels.shape[:2]
    assert max(height, width) == LINEAR_LONG_EDGE and height > width  # portrait shot stays upright
    assert base.is_raw and float(base.pixels.min()) >= 0 and float(base.pixels.max()) <= 1


def test_sidecar_is_scaled_upright_and_cached(setup: tuple[ImageCache, Path, Path]) -> None:
    cache, _, photos = setup
    raw_like = _jpeg_photo(photos, "x.jpg", size=(1200, 800))
    sidecar = photos / "x-camera.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6  # rotated: the camera JPEG is stored sideways
    Image.new("RGB", (1200, 800), (90, 120, 150)).save(sidecar, "JPEG", exif=exif.tobytes())
    photo = raw_like.model_copy(update={"sidecar_jpeg": sidecar})
    data = cache.sidecar(photo, 600)
    assert _size(data) == (400, 600)  # upright portrait
    assert cache.sidecar_path(photo.id, 600).is_file()
    assert sorted(p.name for p in photos.iterdir()) == [
        "x-camera.jpg",
        "x.jpg",
    ]  # nothing written next to photos
