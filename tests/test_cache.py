from __future__ import annotations

import hashlib
import io
import threading
from pathlib import Path

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


def test_preview_base_is_half_size_and_resized_on_request(setup: tuple[ImageCache, Path, Path]) -> None:
    cache, _, photos = setup
    photo = _jpeg_photo(photos, size=(1200, 800))
    assert _size(cache.preview(photo)) == (600, 400)
    assert cache.preview_path(photo.id).is_file()
    assert _size(cache.preview(photo, 300)) == (300, 200)
    assert cache.preview(photo, 300) == cache.preview(photo, 300)  # served from memory
    assert _size(cache.preview(photo, 4096)) == (600, 400)  # never enlarged


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
    cache.preview(photo, 200)
    assert (photo.path.read_bytes(), photo.path.stat().st_mtime_ns) == before
    assert [p.name for p in photos.iterdir()] == ["a.jpg"]


def test_concurrent_requests_decode_once(
    setup: tuple[ImageCache, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    cache, _, photos = setup
    photo = _jpeg_photo(photos)
    calls: list[int] = []
    real_decode = cache_module.decode

    def counting_decode(path: Path, options: object) -> object:
        calls.append(1)
        return real_decode(path, options)  # type: ignore[arg-type]

    monkeypatch.setattr(cache_module, "decode", counting_decode)
    threads = [threading.Thread(target=cache.preview, args=(photo,)) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(calls) == 1


def test_clear_removes_everything(setup: tuple[ImageCache, Path, Path]) -> None:
    cache, cache_dir, photos = setup
    photo = _jpeg_photo(photos)
    cache.thumbnail(photo)
    cache.preview(photo, 100)
    assert cache.clear() == 2
    assert not (cache_dir / "thumbs").exists() and not (cache_dir / "previews").exists()
    assert cache.clear() == 0


@pytest.mark.golden
def test_real_raf_thumbnail_and_preview(sample_raw: Path, tmp_path: Path) -> None:
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
    preview = _size(cache.preview(photo, 1600))
    assert max(thumb) == THUMBNAIL_LONG_EDGE and max(preview) == 1600
    assert (thumb[0] < thumb[1]) == (preview[0] < preview[1])  # both upright the same way
    assert hashlib.sha256(sample_raw.read_bytes()).hexdigest() == sha
