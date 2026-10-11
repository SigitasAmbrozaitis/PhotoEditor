"""Geometry on a real X-T3 RAF (P6a.13). Local only: needs sample_photos_dir; nothing is written near the
photos.

A cropped, straightened and turned edit must frame the same picture in a preview (from the 2048 px working
base) and in an export (from the decode the export picks), and render the same twice.
"""

from __future__ import annotations

import io
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from photoedit.core.cache import LINEAR_LONG_EDGE, resize_linear
from photoedit.core.decode import decode_linear, read_raw_info
from photoedit.core.export.geometry import export_geometry
from photoedit.core.export.worker import ExportTask, render_export
from photoedit.core.geometry import apply_change, edited_size
from photoedit.core.golden import compare
from photoedit.core.metadata import read_metadata_from_bytes
from photoedit.core.render.anchors import measure_anchors
from photoedit.core.render.pipeline import render
from photoedit.core.render.profile import profile_for
from photoedit.core.render.stages import quantize
from photoedit.models.adjustments import AdjustmentParams, Geometry, GeometryChange
from photoedit.models.export import ExportSettings
from test_export_golden import _state

pytestmark = [pytest.mark.golden, pytest.mark.slow]

LONG_EDGE = 1024


def test_preview_and_export_frame_the_same_picture(sample_photos_dir: Path, sample_raw: Path) -> None:
    before = _state(sample_photos_dir, sample_raw)
    info = read_raw_info(sample_raw)
    camera = read_metadata_from_bytes(info.embedded_jpeg).camera if info.embedded_jpeg else None
    profile = profile_for(camera)
    geometry = apply_change(
        Geometry(), GeometryChange(rotate=270, angle=-4.5, aspect="4:5"), info.width, info.height
    )
    values = {"tone": {"contrast": 20}, "effects": {"vignette": {"amount": -30}}}
    edit = AdjustmentParams.model_validate({**values, "geometry": geometry.model_dump()})
    half = decode_linear(sample_raw, half_size=True)
    anchors = measure_anchors(half, profile)

    # The preview: the library's way (the 2048 px working base, limited to the long edge).
    base = resize_linear(half, LINEAR_LONG_EDGE)
    preview = render(base, edit, profile, original_width=info.width, long_edge=LONG_EDGE, anchors=anchors)
    again = render(base, edit, profile, original_width=info.width, long_edge=LONG_EDGE, anchors=anchors)
    np.testing.assert_array_equal(preview, again)

    # The export: the same long edge, no output sharpening, near-lossless JPEG.
    settings = ExportSettings.model_validate(
        {
            "size": {"mode": "long_edge", "long_edge": LONG_EDGE},
            "file": {"jpeg_quality": 100},
            "sharpening": {"target": "none"},
            "metadata": {"policy": "copyright_only"},
        }
    )
    width, height = edited_size(info.width, info.height, geometry)
    task = ExportTask(
        path=sample_raw,
        width=width,
        height=height,
        adjustments=edit,
        profile=profile,
        anchors=anchors,
        settings=settings,
        geometry=export_geometry(width, height, settings, is_raw=True),
        copyright=None,
        creator=None,
    )
    result = render_export(task)
    with Image.open(io.BytesIO(result.data)) as image:
        exported = np.asarray(image.convert("RGB"), dtype=np.uint8)
    shown = np.asarray(quantize(preview, 8), dtype=np.uint8)
    assert abs(exported.shape[0] - shown.shape[0]) <= 1 and abs(exported.shape[1] - shown.shape[1]) <= 1
    assert abs(exported.shape[1] / exported.shape[0] - 0.8) < 0.005  # the 4:5 crop
    if exported.shape != shown.shape:  # the sizes round at different resolutions
        exported = cv2.resize(exported, (shown.shape[1], shown.shape[0]), interpolation=cv2.INTER_AREA)
    # The two take different resampling chains (the working base vs. the export's own decode), so fine
    # detail differs (ΔE2000 mean ~1.5 unstraightened, ~3 straightened). Blurred, only the framing is
    # compared: measured 0.3-0.4 here, while the same images 2 px apart give ~2.5.
    blur = lambda pixels: cv2.GaussianBlur(pixels, (0, 0), 2)  # noqa: E731
    mean, p99 = compare(blur(shown), blur(exported))
    assert mean <= 0.8, f"ΔE2000 of the blurred images: mean {mean:.2f}, p99 {p99:.2f}"
    shifted, _ = compare(blur(shown[2:, 2:]), blur(exported[:-2, :-2]))
    assert shifted > 2 * mean  # the check would see a 2 px shift
    assert _state(sample_photos_dir, sample_raw) == before
