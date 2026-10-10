"""Metadata for exported files: the EXIF tags each policy keeps, plus copyright, creator and keywords (XMP).

The original's EXIF is read with Pillow (for RAWs from the camera's embedded JPEG). Only known standard tags
are copied, chosen per policy; maker notes, thumbnails and anything unknown are never copied. Nothing here
reads the clock, so the same photo and settings always give the same bytes.
"""

from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from PIL import Image, UnidentifiedImageError
from PIL.TiffImagePlugin import IFDRational

from photoedit import __version__
from photoedit.core.decode import DecodeError, embedded_jpeg, is_raw
from photoedit.models.export import ColorSpace, MetadataPolicy, MetadataSettings

SOFTWARE = f"PhotoEditor {__version__}"

EXIF_IFD, GPS_IFD = 0x8769, 0x8825
# IFD0
IMAGE_DESCRIPTION, MAKE, MODEL, ORIENTATION = 0x010E, 0x010F, 0x0110, 0x0112
X_RESOLUTION, Y_RESOLUTION, RESOLUTION_UNIT = 0x011A, 0x011B, 0x0128
SOFTWARE_TAG, DATE_TIME, ARTIST, COPYRIGHT = 0x0131, 0x0132, 0x013B, 0x8298
# Exif sub-IFD
EXPOSURE_TIME, F_NUMBER, ISO = 0x829A, 0x829D, 0x8827
EXIF_VERSION, DATE_TIME_ORIGINAL, DATE_TIME_DIGITIZED = 0x9000, 0x9003, 0x9004
OFFSET_TIME, OFFSET_TIME_ORIGINAL, OFFSET_TIME_DIGITIZED = 0x9010, 0x9011, 0x9012
EXPOSURE_BIAS, FOCAL_LENGTH = 0x9204, 0x920A
COLOR_SPACE, PIXEL_X, PIXEL_Y = 0xA001, 0xA002, 0xA003
FOCAL_LENGTH_35MM = 0xA405
BODY_SERIAL, LENS_MODEL = 0xA431, 0xA434

_IFD0_DESCRIPTION = frozenset({IMAGE_DESCRIPTION, DATE_TIME})
_IFD0_CAMERA = frozenset({MAKE, MODEL})
_EXIF_DATES = frozenset(
    {DATE_TIME_ORIGINAL, DATE_TIME_DIGITIZED, OFFSET_TIME, OFFSET_TIME_ORIGINAL, OFFSET_TIME_DIGITIZED}
    | {0x9290, 0x9291, 0x9292}  # sub-second times
)
_EXIF_EXPOSURE = frozenset(
    {EXPOSURE_TIME, F_NUMBER, ISO, EXPOSURE_BIAS, FOCAL_LENGTH, FOCAL_LENGTH_35MM}
    | {0x8822, 0x8830, 0x8832}  # exposure program, sensitivity type, recommended exposure index
    | {0x9201, 0x9202, 0x9203, 0x9205}  # shutter speed, aperture, brightness, max aperture (APEX)
    | {0x9207, 0x9208, 0x9209}  # metering mode, light source, flash
    | {0xA402, 0xA403, 0xA406}  # exposure mode, white balance, scene type
)
_EXIF_CAMERA = frozenset({0xA430, BODY_SERIAL, 0xA432, 0xA433, LENS_MODEL, 0xA435})  # owner, serials, lens

# XMP names for the Exif tags a TIFF carries in XMP (tifffile can't write an Exif sub-IFD).
_XMP_EXIF: dict[int, str] = {
    EXPOSURE_TIME: "exif:ExposureTime",
    F_NUMBER: "exif:FNumber",
    EXPOSURE_BIAS: "exif:ExposureBiasValue",
    FOCAL_LENGTH: "exif:FocalLength",
    FOCAL_LENGTH_35MM: "exif:FocalLengthIn35mmFilm",
    LENS_MODEL: "exifEX:LensModel",
    BODY_SERIAL: "exifEX:BodySerialNumber",
}
_EXIF_DATE = re.compile(r"^(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})$")


@dataclass(frozen=True)
class SourceExif:
    """The original's EXIF, split into its IFDs (empty when it has none)."""

    ifd0: dict[int, Any] = field(default_factory=dict)
    exif: dict[int, Any] = field(default_factory=dict)
    gps: dict[int, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExportMetadata:
    """Everything written into an exported file besides the pixels and the ICC profile."""

    ifd0: dict[int, Any]
    exif: dict[int, Any]
    gps: dict[int, Any]
    copyright: str | None
    creator: str | None
    keywords: tuple[str, ...]


def read_source_exif(path: Path) -> SourceExif:
    """The EXIF of an original (read-only). A file without readable EXIF gives an empty one."""
    try:
        if is_raw(path):
            jpeg = embedded_jpeg(path)
            if jpeg is None:
                return SourceExif()
            with Image.open(io.BytesIO(jpeg)) as image:
                return _split(image.getexif())
        with Image.open(path) as image:
            return _split(image.getexif())
    except (UnidentifiedImageError, OSError, ValueError, DecodeError):
        return SourceExif()


def _split(exif: Image.Exif) -> SourceExif:
    try:
        return SourceExif(ifd0=dict(exif), exif=dict(exif.get_ifd(EXIF_IFD)), gps=dict(exif.get_ifd(GPS_IFD)))
    except Exception:  # Pillow raises many types on corrupt EXIF; treat it all as "no EXIF"
        return SourceExif()


def build_metadata(
    source: SourceExif,
    settings: MetadataSettings,
    *,
    copyright: str | None,
    creator: str | None,
    width: int,
    height: int,
    ppi: int,
    color_space: ColorSpace,
) -> ExportMetadata:
    """The metadata an export writes under ``settings.policy``.

    ``copyright`` and ``creator`` are the resolved texts (preset, else configuration); when they are None, the
    original's own Copyright / Artist tags are kept if the policy keeps them.
    """
    policy = settings.policy
    ifd0_keep: set[int] = set()
    exif_keep: set[int] = set()
    if policy == MetadataPolicy.ALL:
        ifd0_keep |= _IFD0_DESCRIPTION | _IFD0_CAMERA
        exif_keep |= _EXIF_DATES | _EXIF_EXPOSURE | _EXIF_CAMERA
    elif policy == MetadataPolicy.ALL_EXCEPT_CAMERA_AND_GPS:
        ifd0_keep |= _IFD0_DESCRIPTION
        exif_keep |= _EXIF_DATES | _EXIF_EXPOSURE
    rights = {COPYRIGHT} if policy == MetadataPolicy.COPYRIGHT_ONLY else {COPYRIGHT, ARTIST}

    ifd0 = {tag: value for tag in sorted(ifd0_keep) if (value := _clean(source.ifd0.get(tag))) is not None}
    exif = {tag: value for tag in sorted(exif_keep) if (value := _clean(source.exif.get(tag))) is not None}
    copyright = copyright or _text(source.ifd0.get(COPYRIGHT))
    creator = (creator or _text(source.ifd0.get(ARTIST))) if ARTIST in rights else None
    if copyright:
        ifd0[COPYRIGHT] = ascii_text(copyright)
    if creator:
        ifd0[ARTIST] = ascii_text(creator)
    ifd0 |= {
        ORIENTATION: 1,  # the pixels are already upright
        X_RESOLUTION: IFDRational(ppi, 1),
        Y_RESOLUTION: IFDRational(ppi, 1),
        RESOLUTION_UNIT: 2,  # inches
        SOFTWARE_TAG: SOFTWARE,
    }
    exif |= {
        EXIF_VERSION: b"0232",
        COLOR_SPACE: 1 if color_space == ColorSpace.SRGB else 0xFFFF,  # 0xFFFF = "uncalibrated": see the ICC
        PIXEL_X: width,
        PIXEL_Y: height,
    }
    gps: dict[int, Any] = {}
    if policy == MetadataPolicy.ALL and not settings.strip_gps:
        gps = {
            tag: cleaned for tag, raw in sorted(source.gps.items()) if (cleaned := _clean(raw)) is not None
        }
    return ExportMetadata(
        ifd0=dict(sorted(ifd0.items())),
        exif=dict(sorted(exif.items())),
        gps=gps,
        copyright=copyright or None,
        creator=creator or None,
        keywords=tuple(settings.keywords),
    )


def exif_bytes(meta: ExportMetadata) -> bytes:
    """The EXIF block for JPEG (APP1) and PNG (eXIf), as Pillow serializes it."""
    exif = Image.Exif()
    for tag, value in meta.ifd0.items():
        exif[tag] = value
    sub = exif.get_ifd(EXIF_IFD)
    sub.update(meta.exif)
    if meta.gps:
        exif.get_ifd(GPS_IFD).update(meta.gps)
    return exif.tobytes()


def xmp_packet(meta: ExportMetadata, *, include_exif: bool = False) -> bytes:
    """An XMP packet with copyright, creator, keywords and the software; with ``include_exif`` also the dates,
    exposure and camera details (for TIFF, which has no Exif sub-IFD here)."""
    props: list[str] = [f"<xmp:CreatorTool>{escape(SOFTWARE)}</xmp:CreatorTool>"]
    if meta.copyright:
        props.append(
            '<dc:rights><rdf:Alt><rdf:li xml:lang="x-default">'
            f"{escape(meta.copyright)}</rdf:li></rdf:Alt></dc:rights>"
        )
    if meta.creator:
        props.append(f"<dc:creator><rdf:Seq><rdf:li>{escape(meta.creator)}</rdf:li></rdf:Seq></dc:creator>")
    if meta.keywords:
        items = "".join(f"<rdf:li>{escape(k)}</rdf:li>" for k in meta.keywords)
        props.append(f"<dc:subject><rdf:Bag>{items}</rdf:Bag></dc:subject>")
    if include_exif:
        props.extend(_xmp_exif(meta))
    body = "".join(props)
    packet = (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about=""'
        ' xmlns:dc="http://purl.org/dc/elements/1.1/"'
        ' xmlns:xmp="http://ns.adobe.com/xap/1.0/"'
        ' xmlns:exif="http://ns.adobe.com/exif/1.0/"'
        ' xmlns:exifEX="http://cipa.jp/exif/1.0/">'
        f"{body}"
        "</rdf:Description></rdf:RDF></x:xmpmeta>"
        '<?xpacket end="w"?>'
    )
    return packet.encode("utf-8")


def _xmp_exif(meta: ExportMetadata) -> list[str]:
    props: list[str] = []
    original = meta.exif.get(DATE_TIME_ORIGINAL)
    if isinstance(original, str) and (date := _xmp_date(original, meta.exif.get(OFFSET_TIME_ORIGINAL))):
        props.append(f"<exif:DateTimeOriginal>{date}</exif:DateTimeOriginal>")
    if (iso := meta.exif.get(ISO)) is not None:
        props.append(
            f"<exif:ISOSpeedRatings><rdf:Seq><rdf:li>{int(iso)}</rdf:li></rdf:Seq></exif:ISOSpeedRatings>"
        )
    for tag, name in _XMP_EXIF.items():
        value = meta.exif.get(tag)
        if isinstance(value, IFDRational):
            props.append(f"<{name}>{value.numerator}/{value.denominator}</{name}>")
        elif isinstance(value, int):
            props.append(f"<{name}>{value}</{name}>")
        elif isinstance(value, str):
            props.append(f"<{name}>{escape(value)}</{name}>")
    return props


def _xmp_date(value: str, offset: Any) -> str | None:
    match = _EXIF_DATE.match(value)
    if match is None:
        return None
    y, mo, d, h, mi, s = match.groups()
    zone = offset if isinstance(offset, str) and re.fullmatch(r"[+-]\d{2}:\d{2}", offset) else ""
    return f"{y}-{mo}-{d}T{h}:{mi}:{s}{zone}"


_ASCII_SIGNS = {"©": "(c)", "®": "(R)", "™": "(TM)"}


def ascii_text(text: str) -> str:
    """EXIF and TIFF text tags are ASCII: "©" → "(c)", accents dropped ("ė" → "e"), anything else → "?".

    The exact text goes into XMP, which is Unicode.
    """
    for sign, spelled in _ASCII_SIGNS.items():
        text = text.replace(sign, spelled)
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.encode("ascii", errors="replace").decode("ascii")


def _text(value: Any) -> str | None:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if not isinstance(value, str):
        return None
    cleaned = value.replace("\x00", "").strip()  # Fuji pads fixed-size strings with NUL bytes
    return cleaned or None


def _clean(value: Any) -> Any:
    """Copyable tag values only: ASCII text without padding, numbers, rationals and short byte strings."""
    if isinstance(value, str):
        text = _text(value)
        return ascii_text(text) if text is not None else None
    if isinstance(value, (int, IFDRational, float)):
        return value
    if isinstance(value, bytes) and len(value) <= 64:
        return value
    if isinstance(value, tuple) and all(isinstance(v, (int, IFDRational, float)) for v in value):
        return value
    return None
