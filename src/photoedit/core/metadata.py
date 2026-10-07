"""Read photo metadata (EXIF) with Pillow.

For RAW files the EXIF comes from the camera's embedded JPEG (see ``decode.embedded_jpeg``).
Broken or missing tags give ``None`` fields: one odd tag must never stop an import.
"""

from __future__ import annotations

import io
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field

# EXIF tag ids (IFD0 and the Exif sub-IFD).
_EXIF_IFD = 0x8769
_MAKE, _MODEL, _ORIENTATION, _DATETIME, _RATING = 0x010F, 0x0110, 0x0112, 0x0132, 0x4746
_EXPOSURE_TIME, _FNUMBER, _ISO = 0x829A, 0x829D, 0x8827
_DATETIME_ORIGINAL, _OFFSET_TIME_ORIGINAL = 0x9003, 0x9011
_FOCAL_LENGTH, _LENS_MODEL = 0x920A, 0xA434

_XMP_RATING = re.compile(rb"xmp:Rating(?:=\"|>)\s*(-?\d+)")
_OFFSET = re.compile(r"^([+-])(\d{2}):(\d{2})$")
# Orientations 5-8 rotate by 90°, so the displayed image is the stored one with width and height swapped.
_SWAPS_AXES = frozenset({5, 6, 7, 8})


class MetadataError(ValueError):
    """The file is not an image Pillow can read."""


class PhotoMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    captured_at: datetime | None = None
    camera: str | None = None
    lens: str | None = None
    iso: int | None = Field(default=None, ge=1)
    shutter: str | None = None
    aperture: float | None = Field(default=None, gt=0)
    focal_length: float | None = Field(default=None, gt=0)
    orientation: int = Field(default=1, ge=1, le=8, description="EXIF orientation of the stored pixels.")
    rating: int = Field(default=0, ge=0, le=5)
    width: int = Field(ge=1, description="Displayed width (after orientation).")
    height: int = Field(ge=1, description="Displayed height (after orientation).")


def read_metadata(path: Path) -> PhotoMetadata:
    """Metadata of a JPEG/TIFF file. Only the header is read; the pixels are not decoded."""
    try:
        with Image.open(path) as image:
            return _from_image(image)
    except (UnidentifiedImageError, OSError) as exc:
        raise MetadataError(f"cannot read image {path.name}: {exc}") from exc


def read_metadata_from_bytes(data: bytes) -> PhotoMetadata:
    """Metadata of an in-memory JPEG, e.g. the one embedded in a RAW file."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            return _from_image(image)
    except (UnidentifiedImageError, OSError) as exc:
        raise MetadataError(f"cannot read embedded image: {exc}") from exc


def format_shutter(seconds: float) -> str:
    """Exposure time as cameras display it: ``1/4000``, ``1/2.5``, ``0.5s``, ``2s``."""
    if seconds >= 0.5:
        return f"{seconds:.1f}".rstrip("0").rstrip(".") + "s"
    denominator = 1 / seconds
    if denominator >= 10:
        return f"1/{round(denominator)}"
    return "1/" + f"{denominator:.1f}".rstrip("0").rstrip(".")


def _from_image(image: Image.Image) -> PhotoMetadata:
    try:
        exif = image.getexif()
        exif_ifd: dict[int, Any] = dict(exif.get_ifd(_EXIF_IFD))
        ifd0: dict[int, Any] = dict(exif)
    except Exception:  # Pillow raises many types on corrupt EXIF; treat it all as "no EXIF"
        exif_ifd, ifd0 = {}, {}

    def tag(tag_id: int) -> Any:
        return exif_ifd.get(tag_id, ifd0.get(tag_id))

    orientation = _int(ifd0.get(_ORIENTATION))
    orientation = orientation if orientation is not None and 1 <= orientation <= 8 else 1
    width, height = image.size
    if orientation in _SWAPS_AXES:
        width, height = height, width

    exposure = _positive_float(tag(_EXPOSURE_TIME))
    captured_at = _datetime(tag(_DATETIME_ORIGINAL), tag(_OFFSET_TIME_ORIGINAL)) or _datetime(tag(_DATETIME))
    return PhotoMetadata(
        captured_at=captured_at,
        camera=_camera(_text(ifd0.get(_MAKE)), _text(ifd0.get(_MODEL))),
        lens=_text(tag(_LENS_MODEL)),
        iso=_iso(tag(_ISO)),
        shutter=format_shutter(exposure) if exposure is not None else None,
        aperture=_positive_float(tag(_FNUMBER)),
        focal_length=_positive_float(tag(_FOCAL_LENGTH)),
        orientation=orientation,
        rating=_rating(ifd0.get(_RATING), image.info.get("xmp")),
        width=width,
        height=height,
    )


def _text(value: Any) -> str | None:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if not isinstance(value, str):
        return None
    # Fuji pads fixed-size string tags with NUL bytes.
    cleaned = value.replace("\x00", "").strip()
    return cleaned or None


def _camera(make: str | None, model: str | None) -> str | None:
    if model is None:
        return make
    if make is None:
        return model
    # "Canon" + "Canon EOS R5" and "NIKON CORPORATION" + "NIKON Z 6" already contain the make.
    if model.casefold().startswith(make.split()[0].casefold()):
        return model
    return f"{make} {model}"


def _positive_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return round(number, 6) if math.isfinite(number) and number > 0 else None


def _int(value: Any) -> int | None:
    if isinstance(value, tuple | list):
        value = value[0] if value else None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _iso(value: Any) -> int | None:
    iso = _int(value)
    return iso if iso is not None and iso >= 1 else None


def _datetime(value: Any, offset: Any = None) -> datetime | None:
    text = _text(value)
    if text is None:
        return None
    try:
        moment = datetime.strptime(text, "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None
    match = _OFFSET.match(_text(offset) or "")
    if match:
        sign = 1 if match[1] == "+" else -1
        delta = timedelta(hours=int(match[2]), minutes=int(match[3]))
        moment = moment.replace(tzinfo=timezone(sign * delta))
    return moment


def _rating(exif_rating: Any, xmp: Any) -> int:
    rating = _int(exif_rating)
    if rating is None and isinstance(xmp, bytes | str):
        found = _XMP_RATING.search(xmp.encode() if isinstance(xmp, str) else xmp)
        rating = int(found[1]) if found else None
    # XMP uses -1 for "rejected"; we have no reject flag yet, so anything outside 1-5 reads as unrated.
    return rating if rating is not None and 1 <= rating <= 5 else 0
