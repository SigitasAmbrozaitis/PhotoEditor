from __future__ import annotations

import contextlib
import hashlib
import io
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
import rawpy
from PIL import Image

from photoedit.core import decode
from photoedit.core.decode import FULL, PREVIEW, DecodeError, DecodeOptions


def _gradient(width: int, height: int) -> Image.Image:
    x = np.linspace(0, 255, width, dtype=np.uint8)
    y = np.linspace(0, 255, height, dtype=np.uint8)
    channels = [np.tile(x, (height, 1)), np.tile(y[:, None], (1, width)), np.full((height, width), 90)]
    return Image.fromarray(np.stack(channels, -1).astype(np.uint8))


def _jpeg_bytes(image: Image.Image, orientation: int | None = None) -> bytes:
    exif = Image.Exif()
    if orientation is not None:
        exif[0x0112] = orientation
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=95, exif=exif.tobytes())
    return buf.getvalue()


# ----------------------------------------------------------------- options + identity


def test_preview_and_full_options_are_explicit() -> None:
    assert PREVIEW.half_size and PREVIEW.output_bps == 8
    assert not FULL.half_size and FULL.output_bps == 16
    assert PREVIEW.use_camera_wb and PREVIEW.auto_bright and PREVIEW.output_color == "sRGB"


def test_options_are_frozen_and_strict() -> None:
    with pytest.raises(ValueError):
        DecodeOptions(half_size=True, output_bps=12)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        PREVIEW.half_size = False  # type: ignore[misc]


def test_render_identity_names_decoder_and_libraries() -> None:
    identity = decode.render_identity()
    assert identity.startswith(f"dec{decode.DECODER_VERSION}-libraw0.")
    assert "-pillow" in identity
    assert identity == decode.render_identity()


# ----------------------------------------------------------------- JPEG / TIFF originals


def test_jpeg_full_decode_is_upright_uint8(tmp_path: Path) -> None:
    path = tmp_path / "a.jpg"
    path.write_bytes(_jpeg_bytes(_gradient(60, 40), orientation=6))
    pixels = decode.decode(path, FULL)
    assert pixels.dtype == np.uint8
    assert pixels.shape == (60, 40, 3)  # orientation 6 → displayed portrait


def test_jpeg_preview_is_half_size(tmp_path: Path) -> None:
    path = tmp_path / "b.jpg"
    path.write_bytes(_jpeg_bytes(_gradient(200, 100)))
    assert decode.decode(path, PREVIEW).shape == (50, 100, 3)


def test_tiff_decode(tmp_path: Path) -> None:
    path = tmp_path / "c.tif"
    _gradient(30, 20).save(path, "TIFF")
    full = decode.decode(path, FULL)
    assert full.shape == (20, 30, 3)
    assert decode.decode(path, PREVIEW).shape == (10, 15, 3)
    assert int(full[0, -1, 0]) == 255  # lossless: the right edge of the red ramp is exactly 255


def test_raster_decode_is_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "d.jpg"
    path.write_bytes(_jpeg_bytes(_gradient(64, 48)))
    assert np.array_equal(decode.decode(path, PREVIEW), decode.decode(path, PREVIEW))


def test_corrupt_raster_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.jpg"
    path.write_bytes(b"not an image")
    with pytest.raises(DecodeError, match=r"bad\.jpg"):
        decode.decode(path, PREVIEW)


def test_corrupt_raw_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.RAF"
    path.write_bytes(b"not a raw file at all")
    with pytest.raises(DecodeError, match=r"bad\.RAF"):
        decode.decode(path, PREVIEW)
    with pytest.raises(DecodeError):
        decode.read_raw_info(path)


def test_missing_raw_raises(tmp_path: Path) -> None:
    with pytest.raises(DecodeError, match=r"missing\.RAF"):
        decode.read_raw_info(tmp_path / "missing.RAF")


# ----------------------------------------------------------------- orientation of embedded JPEGs


def test_oriented_image_uses_exif_orientation() -> None:
    image = decode.oriented_image(_jpeg_bytes(_gradient(60, 40), orientation=8))
    assert image.size == (40, 60)
    assert image.mode == "RGB"


@pytest.mark.parametrize(("flip", "size"), [(0, (60, 40)), (3, (60, 40)), (5, (40, 60)), (6, (40, 60))])
def test_oriented_image_falls_back_to_raw_flip(flip: int, size: tuple[int, int]) -> None:
    assert decode.oriented_image(_jpeg_bytes(_gradient(60, 40)), fallback_flip=flip).size == size


def test_exif_orientation_wins_over_raw_flip() -> None:
    image = decode.oriented_image(_jpeg_bytes(_gradient(60, 40), orientation=1), fallback_flip=6)
    assert image.size == (60, 40)
    image = decode.oriented_image(_jpeg_bytes(_gradient(60, 40), orientation=6), fallback_flip=6)
    assert image.size == (40, 60)  # rotated once, not twice


def test_oriented_image_rejects_garbage() -> None:
    with pytest.raises(DecodeError):
        decode.oriented_image(b"nope")


# ----------------------------------------------------------------- RAW branching with a fake LibRaw


class _FakeRaw:
    def __init__(self, flip: int, thumb: Any) -> None:
        self.sizes = SimpleNamespace(width=600, height=400, flip=flip)
        self.camera_whitebalance = [0.0, 0.0, 0.0, 0.0]  # no as-shot data recorded
        self.rgb_xyz_matrix = np.zeros((4, 3))
        self._thumb = thumb

    def __enter__(self) -> _FakeRaw:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def extract_thumb(self) -> Any:
        if isinstance(self._thumb, Exception):
            raise self._thumb
        return self._thumb


def _fake_imread(monkeypatch: pytest.MonkeyPatch, raw: _FakeRaw) -> None:
    def imread(handle: io.BufferedReader) -> _FakeRaw:
        assert handle.mode == "rb"  # originals are only ever opened read-only
        handle.read()
        return raw

    monkeypatch.setattr(decode.rawpy, "imread", imread)


@pytest.mark.parametrize(
    ("flip", "size"), [(0, (600, 400)), (3, (600, 400)), (5, (400, 600)), (6, (400, 600))]
)
def test_raw_info_size_follows_flip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flip: int, size: tuple[int, int]
) -> None:
    path = tmp_path / "x.RAF"
    path.write_bytes(b"raw")
    thumb = SimpleNamespace(format=rawpy.ThumbFormat.JPEG, data=b"\xff\xd8jpeg")
    _fake_imread(monkeypatch, _FakeRaw(flip, thumb))
    info = decode.read_raw_info(path)
    assert (info.width, info.height, info.flip) == (*size, flip)
    assert info.embedded_jpeg == b"\xff\xd8jpeg"


def test_bitmap_thumbnail_is_reencoded_as_jpeg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "y.NEF"
    path.write_bytes(b"raw")
    bitmap = np.zeros((8, 12, 3), dtype=np.uint8)
    _fake_imread(monkeypatch, _FakeRaw(0, SimpleNamespace(format=rawpy.ThumbFormat.BITMAP, data=bitmap)))
    jpeg = decode.read_raw_info(path).embedded_jpeg
    assert jpeg is not None and jpeg[:2] == b"\xff\xd8"
    assert Image.open(io.BytesIO(jpeg)).size == (12, 8)


def test_missing_thumbnail_gives_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "z.DNG"
    path.write_bytes(b"raw")
    _fake_imread(monkeypatch, _FakeRaw(0, rawpy.LibRawNoThumbnailError()))
    assert decode.read_raw_info(path).embedded_jpeg is None


# ----------------------------------------------------------------- LibRaw threading


@pytest.mark.skipif(sys.platform != "win32", reason="the bundled OpenMP runtime is vcomp on Windows")
def test_libraw_openmp_is_limited_to_one_thread(tmp_path: Path) -> None:
    runtime = decode.openmp_runtime()
    assert runtime is not None
    result: dict[str, int] = {}

    def worker() -> None:
        with contextlib.suppress(DecodeError):
            path = tmp_path / "w.RAF"
            path.write_bytes(b"x")
            decode._single_threaded_libraw()
        result["threads"] = runtime.omp_get_max_threads()

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    assert result["threads"] == 1


# ----------------------------------------------------------------- real X-T3 RAFs (read-only)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.golden
def test_real_raf_info_and_embedded_jpeg(sample_raw: Path) -> None:
    before = _sha256(sample_raw)
    info = decode.read_raw_info(sample_raw)
    assert sorted((info.width, info.height)) == [4170, 6246]
    assert info.as_shot is not None and 4000 < info.as_shot[0] < 7000
    assert info.embedded_jpeg is not None
    thumb = decode.oriented_image(info.embedded_jpeg, info.flip)
    # The embedded JPEG has the same orientation as the RAW's displayed size.
    assert (thumb.width > thumb.height) == (info.width > info.height)
    assert _sha256(sample_raw) == before


@pytest.mark.golden
def test_real_raf_preview_is_upright_and_deterministic(sample_raw: Path) -> None:
    info = decode.read_raw_info(sample_raw)
    first = decode.decode(sample_raw, PREVIEW)
    second = decode.decode(sample_raw, PREVIEW)
    assert first.dtype == np.uint8
    height, width = first.shape[:2]
    assert (width > height) == (info.width > info.height)
    assert abs(width - info.width // 2) <= 4 and abs(height - info.height // 2) <= 4
    assert np.array_equal(first, second)
    # Auto-brightness keeps the preview in a sane range (the probe measured a mean of ~52 for DSCF5437).
    assert 20 < float(first.mean()) < 200


@pytest.mark.golden
def test_real_raf_decode_is_identical_across_threads(sample_raw: Path) -> None:
    """LibRaw's OpenMP code is not deterministic on X-Trans; decode pins it to one thread in every thread."""
    main = decode.decode(sample_raw, PREVIEW)
    result: dict[str, np.ndarray] = {}
    thread = threading.Thread(target=lambda: result.setdefault("pixels", decode.decode(sample_raw, PREVIEW)))
    thread.start()
    thread.join()
    assert np.array_equal(main, result["pixels"])


# ----------------------------------------------------------------- linear decode (Phase 3)


def test_linear_decode_of_a_tiff_is_linear_rec2020(tmp_path: Path) -> None:
    from photoedit.core import color

    path = tmp_path / "patches.tif"
    patches = np.zeros((2, 2, 3), dtype=np.uint8)
    patches[0, 0] = (128, 128, 128)
    patches[0, 1] = (255, 0, 0)
    Image.fromarray(patches).save(path, "TIFF")
    image = decode.decode_linear(path, half_size=False)
    assert not image.is_raw and image.pixels.dtype == np.float32
    np.testing.assert_allclose(image.to_rec2020, np.eye(3))
    gray = float(color.srgb_decode(np.array([128 / 255]))[0])
    np.testing.assert_allclose(image.pixels[0, 0], [gray] * 3, atol=1e-6)
    np.testing.assert_allclose(image.pixels[0, 1], color.REC2020_FROM_SRGB @ [1, 0, 0], atol=1e-6)
    temperature, _ = image.as_shot
    assert temperature == pytest.approx(6504, abs=10)  # JPEG/TIFF count as D65


def test_linear_decode_half_size(tmp_path: Path) -> None:
    path = tmp_path / "h.jpg"
    path.write_bytes(_jpeg_bytes(_gradient(64, 40)))
    assert decode.decode_linear(path, half_size=True).pixels.shape == (20, 32, 3)


@pytest.mark.golden
def test_real_raf_linear_decode_matches_libraw_srgb(sample_raw: Path) -> None:
    """Our camera→Rec.2020 matrix, taken on to sRGB, must reproduce LibRaw's own sRGB conversion."""
    import io as io_module

    import rawpy as rawpy_module

    from photoedit.core import color

    image = decode.decode_linear(sample_raw, half_size=True)
    assert image.is_raw and image.cam_from_xyz is not None
    ours = np.clip(
        color.apply_matrix(image.pixels.astype(np.float64), color.SRGB_FROM_REC2020 @ image.to_rec2020), 0, 1
    )
    with rawpy_module.imread(io_module.BytesIO(sample_raw.read_bytes())) as raw:
        decode._single_threaded_libraw()
        libraw = (
            raw.postprocess(
                half_size=True,
                output_bps=16,
                gamma=(1, 1),
                use_camera_wb=True,
                no_auto_bright=True,
                output_color=rawpy_module.ColorSpace.sRGB,
            ).astype(np.float64)
            / 65535
        )
    assert np.abs(ours - libraw).mean() < 1e-4
    temperature, tint = image.as_shot
    assert 4000 < temperature < 7000 and abs(tint) < 50  # the probe measured ~5000 K for these shots
