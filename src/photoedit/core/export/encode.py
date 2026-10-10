"""Encoding rendered pixels into JPEG, TIFF and PNG files, in memory.

Every encoder is deterministic: the same pixels, settings and metadata give the same bytes (no timestamps, no
random ids, fixed compression settings).
"""

from __future__ import annotations

import io
import struct
import zlib
from dataclasses import dataclass, field
from importlib.metadata import version as package_version

import cv2
import numpy as np
import tifffile
from PIL import Image

from photoedit.core.export import metadata as md
from photoedit.core.render.pipeline import render_identity
from photoedit.core.render.stages import F32, quantize
from photoedit.models.export import FileFormat, FileSettings, TiffCompression

# Bump when anything changes the bytes of an exported file for the same render (encoders, metadata, ICC).
EXPORT_VERSION = 1

EXTENSIONS = {FileFormat.JPEG: ".jpg", FileFormat.TIFF: ".tif", FileFormat.PNG: ".png"}

_HIGH_QUALITY_444 = 90  # from this JPEG quality on, color isn't subsampled (4:4:4)
_PNG_COMPRESSION = 6
_TIFF_COMPRESSION = {TiffCompression.NONE: None, TiffCompression.LZW: "lzw", TiffCompression.ZIP: "zlib"}
# TIFF tag ids written into IFD0 (all ASCII).
_TIFF_TEXT_TAGS = (
    md.IMAGE_DESCRIPTION,
    md.MAKE,
    md.MODEL,
    md.SOFTWARE_TAG,
    md.DATE_TIME,
    md.ARTIST,
    md.COPYRIGHT,
)
_TIFF_XMP, _TIFF_ICC = 700, 34675


@dataclass(frozen=True)
class Encoded:
    data: bytes
    warnings: list[str] = field(default_factory=list)


def export_identity() -> str:
    """Everything that decides an exported file's bytes: the render plus the encoders."""
    return (
        f"{render_identity()}-exp{EXPORT_VERSION}"
        f"-tifffile{package_version('tifffile')}-imagecodecs{package_version('imagecodecs')}"
    )


def encode(pixels: F32, settings: FileSettings, *, icc: bytes, meta: md.ExportMetadata, ppi: int) -> Encoded:
    """Encode ``pixels`` (encoded 0..1, height × width × 3) as ``settings.format``."""
    match settings.format:
        case FileFormat.JPEG:
            return _jpeg(pixels, settings, icc, meta, ppi)
        case FileFormat.TIFF:
            return _tiff(pixels, settings, icc, meta, ppi)
        case FileFormat.PNG:
            return _png(pixels, settings, icc, meta, ppi)


# ----------------------------------------------------------------- JPEG


def _jpeg(pixels: F32, settings: FileSettings, icc: bytes, meta: md.ExportMetadata, ppi: int) -> Encoded:
    image = Image.fromarray(quantize(pixels, 8), "RGB")
    exif = md.exif_bytes(meta)
    xmp = md.xmp_packet(meta)

    def at(quality: int) -> bytes:
        buf = io.BytesIO()
        image.save(
            buf,
            "JPEG",
            quality=quality,
            subsampling=0 if quality >= _HIGH_QUALITY_444 else 2,
            optimize=False,
            progressive=False,
            icc_profile=icc,
            exif=exif,
            xmp=xmp,
            dpi=(ppi, ppi),
        )
        return buf.getvalue()

    data = at(settings.jpeg_quality)
    limit = settings.max_file_size_kb
    if limit is None or len(data) <= limit * 1024:
        return Encoded(data)
    # The highest quality that fits, by bisection: deterministic, about 7 encodes.
    low, high = 1, settings.jpeg_quality - 1
    best: bytes | None = None
    best_quality = 0
    while low <= high:
        middle = (low + high) // 2
        candidate = at(middle)
        if len(candidate) <= limit * 1024:
            best, best_quality, low = candidate, middle, middle + 1
        else:
            high = middle - 1
    if best is None:
        smallest = at(1)
        return Encoded(smallest, [f"larger than {limit} KB even at quality 1 ({len(smallest) // 1024} KB)"])
    return Encoded(best, [f"quality lowered to {best_quality} to stay under {limit} KB"])


# ----------------------------------------------------------------- TIFF


def _tiff(pixels: F32, settings: FileSettings, icc: bytes, meta: md.ExportMetadata, ppi: int) -> Encoded:
    data = quantize(pixels, settings.bit_depth)
    xmp = md.xmp_packet(meta, include_exif=True)
    extratags: list[tuple[int, str, int, object, bool]] = []
    for tag in _TIFF_TEXT_TAGS:
        value = meta.ifd0.get(tag)
        if isinstance(value, str) and value:
            extratags.append((tag, "s", 0, md.ascii_text(value), True))
    extratags.append((_TIFF_XMP, "B", len(xmp), xmp, True))
    extratags.append((_TIFF_ICC, "B", len(icc), icc, True))
    compression = _TIFF_COMPRESSION[settings.tiff_compression]
    description = meta.ifd0.get(md.IMAGE_DESCRIPTION)
    buf = io.BytesIO()
    tifffile.imwrite(
        buf,
        data,
        photometric="rgb",
        planarconfig="contig",
        compression=compression,
        predictor=compression is not None,
        resolution=(ppi, ppi),
        resolutionunit="INCH",
        metadata=None,  # no JSON description of tifffile's own
        description=md.ascii_text(description) if isinstance(description, str) else None,
        software=md.SOFTWARE,
        extratags=extratags,
    )
    warnings = ["GPS is only written to JPEG and PNG files"] if meta.gps else []
    return Encoded(buf.getvalue(), warnings)


# ----------------------------------------------------------------- PNG


def _png(pixels: F32, settings: FileSettings, icc: bytes, meta: md.ExportMetadata, ppi: int) -> Encoded:
    data = quantize(pixels, settings.bit_depth)
    ok, encoded = cv2.imencode(
        ".png", np.ascontiguousarray(data[..., ::-1]), [cv2.IMWRITE_PNG_COMPRESSION, _PNG_COMPRESSION]
    )
    if not ok:  # pragma: no cover - OpenCV only fails on invalid input
        raise RuntimeError("PNG encoding failed")
    png = encoded.tobytes()
    pixels_per_metre = round(ppi / 0.0254)
    exif = md.exif_bytes(meta)
    chunks = [
        _chunk(b"pHYs", struct.pack(">IIB", pixels_per_metre, pixels_per_metre, 1)),
        _chunk(b"iCCP", b"ICC Profile\0\0" + zlib.compress(icc, 9)),
        _chunk(b"eXIf", exif.removeprefix(b"Exif\x00\x00")),
        _chunk(b"iTXt", b"XML:com.adobe.xmp\0\0\0\0\0" + md.xmp_packet(meta)),
    ]
    # Ancillary chunks go right after IHDR (8-byte signature + 25-byte IHDR chunk), before any image data.
    ihdr_end = 8 + 25
    return Encoded(png[:ihdr_end] + b"".join(chunks) + png[ihdr_end:])


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
