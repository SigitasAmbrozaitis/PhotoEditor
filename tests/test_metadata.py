from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from PIL.TiffImagePlugin import IFDRational

from photoedit.core.metadata import (
    MetadataError,
    format_shutter,
    read_metadata,
    read_metadata_from_bytes,
)


def _jpeg(
    size: tuple[int, int] = (60, 40),
    ifd0: dict[int, Any] | None = None,
    exif_ifd: dict[int, Any] | None = None,
    xmp: bytes | None = None,
) -> bytes:
    exif = Image.Exif()
    for key, value in (ifd0 or {}).items():
        exif[key] = value
    if exif_ifd:
        sub = exif.get_ifd(0x8769)
        for key, value in exif_ifd.items():
            sub[key] = value
    buf = io.BytesIO()
    extra = {"xmp": xmp} if xmp is not None else {}
    Image.new("RGB", size, (120, 80, 40)).save(buf, "JPEG", exif=exif.tobytes(), **extra)
    return buf.getvalue()


FUJI_IFD0 = {0x010F: "FUJIFILM", 0x0110: "X-T3", 0x0112: 1}
FUJI_EXIF = {
    0x9003: "2026:08:11 06:02:51",
    0xA434: "XF18-55mmF2.8-4 R LM OIS\x00\x00\x00\x00",
    0x8827: 6400,
    0x829A: IFDRational(1, 4000),
    0x829D: IFDRational(45, 10),
    0x920A: IFDRational(55, 1),
}


def test_reads_the_fuji_fields() -> None:
    meta = read_metadata_from_bytes(_jpeg(ifd0=FUJI_IFD0, exif_ifd=FUJI_EXIF))
    assert meta.camera == "FUJIFILM X-T3"
    assert meta.lens == "XF18-55mmF2.8-4 R LM OIS"
    assert meta.iso == 6400
    assert meta.shutter == "1/4000"
    assert meta.aperture == 4.5
    assert meta.focal_length == 55.0
    assert meta.captured_at == datetime(2026, 8, 11, 6, 2, 51)
    assert meta.captured_at.tzinfo is None
    assert (meta.width, meta.height) == (60, 40)
    assert meta.rating == 0


def test_offset_time_makes_the_date_timezone_aware() -> None:
    meta = read_metadata_from_bytes(_jpeg(exif_ifd={0x9003: "2026:08:11 06:02:51", 0x9011: "+03:00"}))
    assert meta.captured_at == datetime(2026, 8, 11, 6, 2, 51, tzinfo=timezone(timedelta(hours=3)))


def test_falls_back_to_the_file_date_when_capture_date_is_missing() -> None:
    meta = read_metadata_from_bytes(_jpeg(ifd0={0x0132: "2025:01:02 03:04:05"}))
    assert meta.captured_at == datetime(2025, 1, 2, 3, 4, 5)


@pytest.mark.parametrize("orientation", range(1, 9))
def test_size_follows_orientation(orientation: int) -> None:
    meta = read_metadata_from_bytes(_jpeg(size=(60, 40), ifd0={0x0112: orientation}))
    assert meta.orientation == orientation
    expected = (40, 60) if orientation >= 5 else (60, 40)
    assert (meta.width, meta.height) == expected


@pytest.mark.parametrize(
    ("seconds", "shown"),
    [
        (0.00025, "1/4000"),
        (1 / 250, "1/250"),
        (1 / 8, "1/8"),
        (0.4, "1/2.5"),
        (0.5, "0.5s"),
        (1.0, "1s"),
        (2.0, "2s"),
        (2.5, "2.5s"),
        (30.0, "30s"),
    ],
)
def test_format_shutter(seconds: float, shown: str) -> None:
    assert format_shutter(seconds) == shown


@pytest.mark.parametrize(
    ("make", "model", "camera"),
    [
        ("Canon", "Canon EOS R5", "Canon EOS R5"),
        ("NIKON CORPORATION", "NIKON Z 6", "NIKON Z 6"),
        ("SONY", "ILCE-7M4", "SONY ILCE-7M4"),
        (None, "X100V", "X100V"),
        ("FUJIFILM", None, "FUJIFILM"),
    ],
)
def test_camera_name_does_not_repeat_the_make(make: str | None, model: str | None, camera: str) -> None:
    ifd0 = {k: v for k, v in ((0x010F, make), (0x0110, model)) if v is not None}
    assert read_metadata_from_bytes(_jpeg(ifd0=ifd0)).camera == camera


def test_missing_exif_gives_empty_fields() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (10, 20)).save(buf, "JPEG")
    meta = read_metadata_from_bytes(buf.getvalue())
    assert meta.model_dump(exclude={"width", "height", "orientation", "rating"}) == {
        "captured_at": None,
        "camera": None,
        "lens": None,
        "iso": None,
        "shutter": None,
        "aperture": None,
        "focal_length": None,
        "film_simulation": None,
        "dynamic_range": None,
    }
    assert (meta.width, meta.height, meta.orientation, meta.rating) == (10, 20, 1, 0)


def test_odd_values_become_none() -> None:
    meta = read_metadata_from_bytes(
        _jpeg(
            ifd0={0x0112: 9, 0x010F: "\x00\x00"},
            exif_ifd={
                0x9003: "not a date",
                0x8827: 0,
                0x829A: IFDRational(1, 0),
                0x829D: IFDRational(0, 1),
                0xA434: "   ",
            },
        )
    )
    assert meta.orientation == 1
    assert meta.camera is None
    assert meta.captured_at is None
    assert meta.iso is None
    assert meta.shutter is None
    assert meta.aperture is None
    assert meta.lens is None


@pytest.mark.filterwarnings("ignore:Corrupt EXIF data")
def test_garbage_exif_block_does_not_raise() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, "JPEG", exif=b"Exif\x00\x00II*\x00\xff\xff\xff\xff garbage")
    meta = read_metadata_from_bytes(buf.getvalue())
    assert (meta.width, meta.height, meta.camera) == (8, 8, None)


@pytest.mark.parametrize(
    ("ifd0", "xmp", "rating"),
    [
        ({0x4746: 4}, None, 4),
        ({}, b'<x:xmpmeta><rdf:Description xmp:Rating="3"/></x:xmpmeta>', 3),
        ({}, b"<x:xmpmeta><xmp:Rating>5</xmp:Rating></x:xmpmeta>", 5),
        ({}, b'<rdf:Description xmp:Rating="-1"/>', 0),
        ({0x4746: 9}, None, 0),
    ],
)
def test_rating(ifd0: dict[int, Any], xmp: bytes | None, rating: int) -> None:
    assert read_metadata_from_bytes(_jpeg(ifd0=ifd0, xmp=xmp)).rating == rating


def test_reads_jpeg_and_tiff_files(tmp_path: Path) -> None:
    jpg = tmp_path / "a.jpg"
    jpg.write_bytes(_jpeg(size=(30, 20), ifd0=FUJI_IFD0, exif_ifd=FUJI_EXIF))
    assert read_metadata(jpg).camera == "FUJIFILM X-T3"

    tif = tmp_path / "b.tif"
    exif = Image.Exif()
    exif[0x0110] = "TIFF Cam"
    Image.new("RGB", (12, 34)).save(tif, "TIFF", exif=exif)
    meta = read_metadata(tif)
    assert (meta.width, meta.height, meta.camera) == (12, 34, "TIFF Cam")


def test_not_an_image_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"definitely not a jpeg")
    with pytest.raises(MetadataError, match=r"bad\.jpg"):
        read_metadata(bad)
    with pytest.raises(MetadataError):
        read_metadata_from_bytes(b"nope")


# ----------------------------------------------------------------- Fujifilm maker notes


def fuji_maker_note(tags: dict[int, int]) -> bytes:
    import struct

    entries = b"".join(struct.pack("<HHII", tag, 3, 1, value) for tag, value in sorted(tags.items()))
    return b"FUJIFILM" + struct.pack("<I", 12) + struct.pack("<H", len(tags)) + entries + b"\0\0\0\0"


@pytest.mark.parametrize(
    ("tags", "film", "dr"),
    [
        ({0x1401: 0x000, 0x1403: 100}, "Provia", 100),
        ({0x1401: 0x600, 0x1403: 400}, "Classic Chrome", 400),
        ({0x1003: 0x500, 0x1401: 0x000, 0x1403: 200}, "Acros", 200),  # monochrome wins over film mode
        ({0x1401: 0x7777, 0x1403: 300}, None, None),  # unknown values stay unknown
    ],
)
def test_fujifilm_film_simulation_and_dynamic_range(
    tags: dict[int, int], film: str | None, dr: int | None
) -> None:
    meta = read_metadata_from_bytes(_jpeg(ifd0=FUJI_IFD0, exif_ifd={0x927C: fuji_maker_note(tags)}))
    assert (meta.film_simulation, meta.dynamic_range) == (film, dr)


@pytest.mark.parametrize(
    "note", [b"Nikon\0\x02\x10\0\0", b"FUJIFILM\xff\xff", b"FUJIFILM" + b"\x0c\0\0\0" + b"\xff\xff"]
)
def test_other_or_broken_maker_notes_are_ignored(note: bytes) -> None:
    meta = read_metadata_from_bytes(_jpeg(exif_ifd={0x927C: note}))
    assert meta.film_simulation is None and meta.dynamic_range is None


@pytest.mark.golden
def test_real_xt3_maker_note(sample_raw: Path) -> None:
    from photoedit.core.decode import read_raw_info

    jpeg = read_raw_info(sample_raw).embedded_jpeg
    assert jpeg is not None
    meta = read_metadata_from_bytes(jpeg)
    assert (meta.film_simulation, meta.dynamic_range) == ("Provia", 100)
