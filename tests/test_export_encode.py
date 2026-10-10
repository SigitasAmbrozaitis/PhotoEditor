from __future__ import annotations

import io
import re
from fractions import Fraction
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
import tifffile
from PIL import Image
from PIL.TiffImagePlugin import IFDRational

from helpers import write_jpeg
from photoedit.core.export import metadata as md
from photoedit.core.export.encode import encode, export_identity
from photoedit.core.export.icc import icc_profile
from photoedit.core.render.pipeline import render_identity
from photoedit.models.export import ColorSpace, FileSettings, MetadataSettings

_ICC_TAG = 34675


def test_tifffile_writes_16_bit_lzw_with_icc(tmp_path: Path) -> None:
    pixels = (np.arange(4 * 6 * 3, dtype=np.uint16).reshape(4, 6, 3) * 900).astype(np.uint16)
    icc = b"fake-icc-profile"
    path = tmp_path / "out.tif"
    tifffile.imwrite(
        path, pixels, photometric="rgb", compression="lzw", extratags=[(_ICC_TAG, "B", len(icc), icc, True)]
    )
    with tifffile.TiffFile(path) as tif:
        page = tif.pages.first
        assert page.compression == tifffile.COMPRESSION.LZW
        assert page.tags[_ICC_TAG].value == icc
        np.testing.assert_array_equal(page.asarray(), pixels)


def test_export_identity_extends_render_identity() -> None:
    identity = export_identity()
    assert identity.startswith(render_identity())
    assert "tifffile" in identity and "imagecodecs" in identity


# ----------------------------------------------------------------- encoders + metadata


def _source(tmp_path: Path) -> md.SourceExif:
    """An original with camera, lens, serial, dates, exposure, GPS, a maker note and its own copyright."""
    path = write_jpeg(
        tmp_path / "orig.jpg",
        (120, 80, 40),
        date="2026:08:11 09:30:15",
        camera="X-T3",
        exposure=(5.6, Fraction(1, 250), 400),
    )
    with Image.open(path) as image:
        exif = image.getexif()
    exif[md.MAKE] = "FUJIFILM\x00\x00"
    exif[md.COPYRIGHT] = "Original owner"
    sub = exif.get_ifd(md.EXIF_IFD)
    sub[md.LENS_MODEL] = "XF70-300mmF4-5.6 R LM OIS WR"
    sub[md.BODY_SERIAL] = "SN12345"
    sub[md.OFFSET_TIME_ORIGINAL] = "+03:00"
    sub[0x927C] = b"FUJIFILM maker note" * 10
    gps = exif.get_ifd(md.GPS_IFD)
    gps[1] = "N"
    gps[2] = (IFDRational(54, 1), IFDRational(41, 1), IFDRational(0, 1))
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (120, 80, 40)).save(buf, "JPEG", exif=exif.tobytes())
    path.write_bytes(buf.getvalue())
    return md.read_source_exif(path)


def _meta(source: md.SourceExif, **settings: Any) -> md.ExportMetadata:
    copyright_ = settings.pop("copyright", None)
    creator = settings.pop("creator", None)
    return md.build_metadata(
        source,
        MetadataSettings.model_validate(settings),
        copyright=copyright_,
        creator=creator,
        width=64,
        height=48,
        ppi=300,
        color_space=ColorSpace.SRGB,
    )


def _pixels() -> np.ndarray:
    x = np.linspace(0, 1, 64, dtype=np.float32)[None, :].repeat(48, axis=0)
    y = np.linspace(0, 0.5, 48, dtype=np.float32)[:, None].repeat(64, axis=1)
    return np.ascontiguousarray(np.stack([x, y, np.full_like(x, 0.3)], axis=-1))


def _encode(fmt: str, meta: md.ExportMetadata, **file: Any) -> bytes:
    settings = FileSettings.model_validate({"format": fmt, **file})
    return encode(_pixels(), settings, icc=icc_profile(ColorSpace.SRGB), meta=meta, ppi=300).data


def _read_exif(data: bytes) -> tuple[dict[int, Any], dict[int, Any], dict[int, Any]]:
    with Image.open(io.BytesIO(data)) as image:
        exif = image.getexif()
        return dict(exif), dict(exif.get_ifd(md.EXIF_IFD)), dict(exif.get_ifd(md.GPS_IFD))


def test_read_source_exif(tmp_path: Path) -> None:
    source = _source(tmp_path)
    assert source.ifd0[md.MODEL] == "X-T3"
    assert source.exif[md.ISO] == 400
    assert source.gps[1] == "N"
    assert md.read_source_exif(tmp_path / "missing.jpg") == md.SourceExif()


def test_policy_all_keeps_camera_and_drops_maker_notes(tmp_path: Path) -> None:
    meta = _meta(_source(tmp_path), policy="all", strip_gps=False)
    ifd0, exif, gps = _read_exif(_encode("jpeg", meta))
    assert ifd0[md.MAKE] == "FUJIFILM" and ifd0[md.MODEL] == "X-T3"
    assert ifd0[md.COPYRIGHT] == "Original owner"  # nothing configured: the original's is kept
    assert exif[md.BODY_SERIAL] == "SN12345" and exif[md.LENS_MODEL].startswith("XF70-300")
    assert exif[md.ISO] == 400 and exif[md.DATE_TIME_ORIGINAL] == "2026:08:11 09:30:15"
    assert 0x927C not in exif
    assert gps[1] == "N"
    assert ifd0[md.ORIENTATION] == 1 and ifd0[md.SOFTWARE_TAG] == md.SOFTWARE
    assert (exif[md.PIXEL_X], exif[md.PIXEL_Y], exif[md.COLOR_SPACE]) == (64, 48, 1)


def test_policy_all_strips_gps(tmp_path: Path) -> None:
    _, _, gps = _read_exif(_encode("jpeg", _meta(_source(tmp_path), policy="all")))
    assert gps == {}


def test_policy_all_except_camera_and_gps(tmp_path: Path) -> None:
    meta = _meta(_source(tmp_path), policy="all_except_camera_and_gps", copyright="© 2026 Me", creator="Me")
    ifd0, exif, gps = _read_exif(_encode("jpeg", meta))
    assert md.MAKE not in ifd0 and md.MODEL not in ifd0
    assert md.BODY_SERIAL not in exif and md.LENS_MODEL not in exif
    assert gps == {}
    assert exif[md.ISO] == 400 and exif[md.EXPOSURE_TIME] == Fraction(1, 250)
    assert (ifd0[md.COPYRIGHT], ifd0[md.ARTIST]) == ("(c) 2026 Me", "Me")


def test_policy_copyright_only(tmp_path: Path) -> None:
    meta = _meta(_source(tmp_path), policy="copyright_only", copyright="© 2026 Me", creator="Me")
    ifd0, exif, _ = _read_exif(_encode("jpeg", meta))
    assert ifd0[md.COPYRIGHT] == "(c) 2026 Me"
    assert md.ARTIST not in ifd0 and md.MAKE not in ifd0
    assert set(exif) == {md.EXIF_VERSION, md.COLOR_SPACE, md.PIXEL_X, md.PIXEL_Y}


def test_policy_copyright_and_contact(tmp_path: Path) -> None:
    meta = _meta(_source(tmp_path), policy="copyright_and_contact", creator="Me")
    ifd0, exif, _ = _read_exif(_encode("jpeg", meta))
    assert (ifd0[md.COPYRIGHT], ifd0[md.ARTIST]) == ("Original owner", "Me")
    assert md.ISO not in exif


def test_xmp_has_rights_creator_keywords(tmp_path: Path) -> None:
    meta = _meta(_source(tmp_path), copyright="© <Me> & co", creator="Me", keywords=["rally", "cat"])
    with Image.open(io.BytesIO(_encode("jpeg", meta))) as image:
        xmp = image.info["xmp"].decode("utf-8")
    assert "© &lt;Me&gt; &amp; co" in xmp
    assert "<rdf:li>Me</rdf:li>" in xmp
    assert re.search(r"<dc:subject><rdf:Bag><rdf:li>rally</rdf:li><rdf:li>cat</rdf:li></rdf:Bag>", xmp)


@pytest.mark.parametrize(
    ("fmt", "file", "dtype"),
    [
        ("jpeg", {}, np.uint8),
        ("png", {}, np.uint8),
        ("png", {"bit_depth": 16}, np.uint16),
        ("tiff", {}, np.uint8),
        ("tiff", {"bit_depth": 16, "tiff_compression": "zip"}, np.uint16),
        ("tiff", {"tiff_compression": "none"}, np.uint8),
    ],
)
def test_formats_round_trip(tmp_path: Path, fmt: str, file: dict[str, Any], dtype: type) -> None:
    meta = _meta(_source(tmp_path), copyright="© Me")
    data = _encode(fmt, meta, **file)
    assert data == _encode(fmt, meta, **file)  # deterministic
    decoded = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
    assert decoded.shape == (48, 64, 3) and decoded.dtype == dtype
    top = 255 if dtype == np.uint8 else 65535
    expected = np.floor(_pixels() * top + 0.5).astype(np.int64)[..., ::-1]
    if fmt == "jpeg":
        assert np.abs(decoded.astype(np.int64) - expected).mean() < 2
    else:
        np.testing.assert_array_equal(decoded, expected)
    if fmt != "tiff" or dtype == np.uint8:  # Pillow can't open 16-bit RGB TIFFs
        with Image.open(io.BytesIO(data)) as image:
            assert image.info.get("icc_profile") == icc_profile(ColorSpace.SRGB)
            assert image.info.get("dpi") == pytest.approx((300, 300), abs=0.01)


def test_tiff_tags_and_xmp(tmp_path: Path) -> None:
    meta = _meta(_source(tmp_path), policy="all", copyright="(c) Me", creator="Me")
    data = _encode("tiff", meta, bit_depth=16)
    with tifffile.TiffFile(io.BytesIO(data)) as tif:
        tags = tif.pages.first.tags
        assert tags["Copyright"].value == "(c) Me"
        assert tags["Artist"].value == "Me"
        assert tags["Model"].value == "X-T3"
        assert tags["Software"].value == md.SOFTWARE
        assert tags[_ICC_TAG].value == icc_profile(ColorSpace.SRGB)
        assert "ImageDescription" not in tags  # tifffile writes no description of its own
        xmp = bytes(tags["XMP"].value).decode("utf-8")
    assert "<exif:DateTimeOriginal>2026-08-11T09:30:15+03:00</exif:DateTimeOriginal>" in xmp
    assert "<exif:ExposureTime>1/250</exif:ExposureTime>" in xmp
    assert "<rdf:li>400</rdf:li>" in xmp


def test_png_chunks(tmp_path: Path) -> None:
    meta = _meta(_source(tmp_path), policy="all", copyright="© Me")
    data = _encode("png", meta, bit_depth=16)
    ifd0, exif, _ = _read_exif(data)
    assert ifd0[md.COPYRIGHT] == "(c) Me" and exif[md.ISO] == 400
    with Image.open(io.BytesIO(data)) as image:
        assert "© Me" in image.info["XML:com.adobe.xmp"]


def test_max_file_size(tmp_path: Path) -> None:
    noisy = np.random.default_rng(1).uniform(0, 1, (256, 256, 3)).astype(np.float32)
    meta = _meta(_source(tmp_path))
    icc = icc_profile(ColorSpace.SRGB)
    full = encode(noisy, FileSettings(jpeg_quality=95), icc=icc, meta=meta, ppi=72)
    limited = encode(noisy, FileSettings(jpeg_quality=95, max_file_size_kb=60), icc=icc, meta=meta, ppi=72)
    assert len(full.data) > 60 * 1024 >= len(limited.data)
    assert limited.warnings[0].startswith("quality lowered to")
    big = np.random.default_rng(2).uniform(0, 1, (2048, 2048, 3)).astype(np.float32)
    impossible = encode(big, FileSettings(max_file_size_kb=50), icc=icc, meta=meta, ppi=72)
    assert "even at quality 1" in impossible.warnings[0]


def test_ascii_text() -> None:
    assert md.ascii_text("© 2026 Sigitas Ambrozaitis") == "(c) 2026 Sigitas Ambrozaitis"
    assert md.ascii_text("Žemaitė® ™") == "Zemaite(R) (TM)"
    assert md.ascii_text("猫") == "?"
