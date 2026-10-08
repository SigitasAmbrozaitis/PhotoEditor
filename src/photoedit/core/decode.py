"""Decode source photos into pixels. The only module that touches LibRaw (via rawpy).

Files are opened ``"rb"`` by us and handed to LibRaw as an in-memory buffer, so an original can never
be opened for writing, and non-ASCII Windows paths work. The decode settings are fixed and versioned
(golden rule 3): change anything here that alters pixels → bump ``DECODER_VERSION`` so caches and golden
images are invalidated.

LibRaw runs single-threaded. Its OpenMP code is not deterministic on X-Trans files (measured 2026-10-07 on
the X-T3: two decodes of the same RAF differed by up to 184 levels in ~5 M pixels). Parallelism comes from
processes instead.
"""

from __future__ import annotations

import ctypes
import functools
import io
from dataclasses import dataclass
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Literal

import numpy as np
import numpy.typing as npt
import rawpy
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict

# rawpy re-exports these from its extension module in a way mypy can't see; import them from the source.
from rawpy._rawpy import (
    ColorSpace,
    LibRawError,
    LibRawNoThumbnailError,
    LibRawUnsupportedThumbnailError,
    RawPy,
    ThumbFormat,
    libraw_version,
)

from photoedit.core.scan import RAW_EXTENSIONS

DECODER_VERSION = 1

# LibRaw "flip" → the Pillow transpose that shows the image upright (0 = as stored).
_FLIP_TRANSPOSE = {
    3: Image.Transpose.ROTATE_180,
    5: Image.Transpose.ROTATE_90,
    6: Image.Transpose.ROTATE_270,
}
_EXIF_ORIENTATION = 0x0112

type RGBImage = npt.NDArray[np.uint8] | npt.NDArray[np.uint16]


class DecodeError(ValueError):
    """The file can't be decoded (unsupported, corrupt or unreadable)."""


class DecodeOptions(BaseModel):
    """Every LibRaw setting that affects pixels, spelled out instead of relying on library defaults."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    half_size: bool
    output_bps: Literal[8, 16]
    use_camera_wb: bool = True
    output_color: Literal["sRGB"] = "sRGB"
    # Fuji underexposes RAWs to protect highlights; LibRaw's auto-brightness brings them close to the camera
    # JPEG (decided 2026-10-07, temporary until the Phase 3 pipeline does exposure itself).
    auto_bright: bool = True
    auto_bright_threshold: float = 0.01


PREVIEW = DecodeOptions(half_size=True, output_bps=8)
FULL = DecodeOptions(half_size=False, output_bps=16)


@dataclass(frozen=True)
class RawInfo:
    width: int
    height: int
    flip: int
    embedded_jpeg: bytes | None


def render_identity() -> str:
    """The decoder build. Part of every cache key, so a library upgrade never serves stale pixels."""
    libraw = ".".join(str(part) for part in libraw_version)
    return f"dec{DECODER_VERSION}-libraw{libraw}-pillow{package_version('pillow')}"


def is_raw(path: Path) -> bool:
    return path.suffix.lower() in RAW_EXTENSIONS


def read_raw_info(path: Path) -> RawInfo:
    """Displayed size, orientation and the camera's embedded JPEG (if any), without demosaicing."""
    with _open_raw(path) as raw:
        sizes = raw.sizes
        width, height = (sizes.height, sizes.width) if sizes.flip in (5, 6) else (sizes.width, sizes.height)
        return RawInfo(width=width, height=height, flip=sizes.flip, embedded_jpeg=_embedded_jpeg(raw))


def oriented_image(jpeg: bytes, fallback_flip: int = 0) -> Image.Image:
    """Decode JPEG bytes to an upright RGB image.

    ``fallback_flip`` (a LibRaw flip) applies only when the JPEG has no orientation tag of its own.
    """
    try:
        image = Image.open(io.BytesIO(jpeg))
        has_orientation = _EXIF_ORIENTATION in image.getexif()
        upright = ImageOps.exif_transpose(image)
    except (UnidentifiedImageError, OSError) as exc:
        raise DecodeError(f"cannot decode JPEG: {exc}") from exc
    if not has_orientation and fallback_flip in _FLIP_TRANSPOSE:
        upright = upright.transpose(_FLIP_TRANSPOSE[fallback_flip])
    return upright.convert("RGB")


def decode(path: Path, options: DecodeOptions) -> RGBImage:
    """Decode a photo to an upright RGB array (H, W, 3).

    RAWs go through LibRaw with ``options``. JPEG/TIFF originals go through Pillow and always come back as
    uint8; ``half_size`` halves them too, so previews of both kinds have comparable sizes.
    """
    if is_raw(path):
        return _decode_raw(path, options)
    return _decode_raster(path, half_size=options.half_size)


def _decode_raw(path: Path, options: DecodeOptions) -> RGBImage:
    with _open_raw(path) as raw:
        _single_threaded_libraw()
        try:
            pixels: RGBImage = raw.postprocess(
                half_size=options.half_size,
                output_bps=options.output_bps,
                use_camera_wb=options.use_camera_wb,
                use_auto_wb=False,
                output_color=ColorSpace.sRGB,
                no_auto_bright=not options.auto_bright,
                auto_bright_thr=options.auto_bright_threshold,
            )
        except LibRawError as exc:
            raise DecodeError(f"cannot decode {path.name}: {exc}") from exc
    return pixels


def _decode_raster(path: Path, *, half_size: bool) -> npt.NDArray[np.uint8]:
    try:
        with Image.open(path) as image:
            width, height = image.size
            if image.getexif().get(_EXIF_ORIENTATION, 1) in (5, 6, 7, 8):
                width, height = height, width
            if half_size and image.format == "JPEG":
                # draft() lets libjpeg decode at a reduced scale directly, which is much faster.
                image.draft("RGB", (image.width // 2, image.height // 2))
            upright = ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise DecodeError(f"cannot decode {path.name}: {exc}") from exc
    if half_size:
        target = (max(1, width // 2), max(1, height // 2))
        if upright.size != target:
            upright = upright.resize(target, Image.Resampling.LANCZOS)
    return np.asarray(upright, dtype=np.uint8)


def _open_raw(path: Path) -> RawPy:
    try:
        with path.open("rb") as handle:
            return rawpy.imread(handle)
    except OSError as exc:
        raise DecodeError(f"cannot read {path.name}: {exc.strerror or exc}") from exc
    except LibRawError as exc:
        raise DecodeError(f"cannot decode {path.name}: {exc}") from exc


def _embedded_jpeg(raw: RawPy) -> bytes | None:
    try:
        thumb = raw.extract_thumb()
    except (LibRawNoThumbnailError, LibRawUnsupportedThumbnailError):
        return None
    if thumb.format == ThumbFormat.JPEG:
        return bytes(thumb.data)
    # Some cameras store an uncompressed bitmap; re-encode it so callers always get JPEG bytes.
    buf = io.BytesIO()
    Image.fromarray(np.asarray(thumb.data)).convert("RGB").save(buf, "JPEG", quality=92)
    return buf.getvalue()


@functools.cache
def openmp_runtime() -> ctypes.CDLL | None:
    """The OpenMP runtime bundled with rawpy (vcomp on Windows, libgomp elsewhere), if there is one."""
    package = Path(rawpy.__file__).parent
    for candidate in [*package.glob("vcomp*.dll"), *package.parent.glob("rawpy.libs/libgomp*")]:
        try:
            return ctypes.CDLL(str(candidate))
        except OSError:
            continue
    return None


def _single_threaded_libraw() -> None:
    """Limit LibRaw's OpenMP to one thread for the calling thread (see the module docstring for why)."""
    runtime = openmp_runtime()
    if runtime is not None:
        runtime.omp_set_num_threads(1)
