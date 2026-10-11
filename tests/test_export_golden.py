"""Exports of a real X-T3 RAF with every built-in preset (P5.18). Local only: needs sample_photos_dir.

Files are encoded in memory (``render_export`` never writes); nothing is written near the photos.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import numpy as np
import pytest
import tifffile
from PIL import Image, ImageCms

from photoedit.config import load_settings
from photoedit.core.decode import decode_linear, read_raw_info
from photoedit.core.export import metadata as md
from photoedit.core.export.geometry import export_geometry
from photoedit.core.export.icc import description
from photoedit.core.export.service import Exporter
from photoedit.core.export.worker import ExportTask, RenderedExport, render_export
from photoedit.core.metadata import read_metadata_from_bytes
from photoedit.core.presets import BUILTIN_PRESETS
from photoedit.core.render.anchors import measure_anchors
from photoedit.core.render.profile import profile_for
from photoedit.models.adjustments import AdjustmentParams
from photoedit.models.export import ExportPreset, FileFormat
from photoedit.safety import PathGuard

pytestmark = [pytest.mark.golden, pytest.mark.slow]


def _state(folder: Path, read: Path) -> dict[str, object]:
    """Size and modification time of every file, plus the content hash of the one the exports read."""
    files = {
        p.name: (p.stat().st_size, p.stat().st_mtime_ns) for p in sorted(folder.iterdir()) if p.is_file()
    }
    return {"files": files, "read": hashlib.sha256(read.read_bytes()).hexdigest()}


@pytest.fixture(scope="module")
def sample_state(sample_photos_dir: Path, sample_raw: Path) -> dict[str, object]:
    return _state(sample_photos_dir, sample_raw)


@pytest.fixture(scope="module")
def tasks(sample_raw: Path, sample_state: dict[str, object]) -> dict[str, ExportTask]:
    # Depends on sample_state so the folder's state is taken before the first export.
    info = read_raw_info(sample_raw)
    camera = read_metadata_from_bytes(info.embedded_jpeg).camera if info.embedded_jpeg else None
    profile = profile_for(camera)
    anchors = measure_anchors(decode_linear(sample_raw, half_size=True), profile)
    return {
        p.id: ExportTask(
            path=sample_raw,
            width=info.width,
            height=info.height,
            adjustments=AdjustmentParams(),
            profile=profile,
            anchors=anchors,
            settings=p.settings,
            geometry=export_geometry(info.width, info.height, p.settings, is_raw=True),
            copyright="(c) 2026 Golden",
            creator="Golden",
        )
        for p in BUILTIN_PRESETS
    }


def _preset(preset_id: str) -> ExportPreset:
    return next(p for p in BUILTIN_PRESETS if p.id == preset_id)


@pytest.mark.parametrize("preset_id", [p.id for p in BUILTIN_PRESETS])
def test_builtin_preset_export(preset_id: str, tasks: dict[str, ExportTask]) -> None:
    preset = _preset(preset_id)
    task = tasks[preset_id]
    result: RenderedExport = render_export(task)
    settings = preset.settings
    portrait = task.height > task.width
    if settings.size.width and settings.size.height:
        given = [settings.size.width, settings.size.height]
        # Instagram presets force their orientation; print presets follow the photo.
        forced = settings.aspect.orientation != "auto"
        expected = given if forced else sorted(given, reverse=not portrait)
        assert [result.width, result.height] == expected
    if settings.file.format == FileFormat.TIFF:
        with tifffile.TiffFile(io.BytesIO(result.data)) as tif:
            page = tif.pages.first
            assert page.shape == (result.height, result.width, 3)
            assert page.dtype == np.uint16
            assert page.tags["XResolution"].value == (settings.size.ppi, 1)
            icc = bytes(page.tags[34675].value)
            assert page.tags["Copyright"].value == "(c) 2026 Golden"
    else:
        with Image.open(io.BytesIO(result.data)) as image:
            assert image.size == (result.width, result.height)
            assert image.info["dpi"] == pytest.approx((settings.size.ppi, settings.size.ppi), abs=0.01)
            icc = image.info["icc_profile"]
            exif = image.getexif()
            assert exif[md.COPYRIGHT] == "(c) 2026 Golden"
            assert md.GPS_IFD not in exif or not exif.get_ifd(md.GPS_IFD)  # every built-in strips GPS
            assert exif[md.ORIENTATION] == 1
    profile = ImageCms.ImageCmsProfile(io.BytesIO(icc))
    assert ImageCms.getProfileDescription(profile).strip() == description(settings.color_space)


def test_export_is_deterministic(tasks: dict[str, ExportTask]) -> None:
    task = tasks["web-full"]
    assert render_export(task).data == render_export(task).data


def test_sample_folder_is_refused_and_unchanged(
    sample_photos_dir: Path, sample_raw: Path, sample_state: dict[str, object], tmp_path: Path
) -> None:
    settings = load_settings(tmp_path / "missing.toml", project_root=tmp_path)
    guard = PathGuard(writable_roots=settings.writable_dirs, protected_roots=[sample_photos_dir])
    exporter = Exporter(None, None, guard, settings)  # type: ignore[arg-type]  # destination checks only
    for folder in (sample_photos_dir, sample_photos_dir / "exports"):
        check = exporter.check_destination(str(folder))
        assert not check.ok and "inside the photo folder" in (check.reason or "")
    assert not (sample_photos_dir / "exports").exists()
    # Last in the module: every export above only read the photos.
    assert _state(sample_photos_dir, sample_raw) == sample_state
