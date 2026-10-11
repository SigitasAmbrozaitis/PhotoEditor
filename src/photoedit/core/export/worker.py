"""Rendering one export: decode → crop → resize → pipeline → output sharpening → encode.

``render_export`` runs in a worker process (it gets everything it needs in a picklable ``ExportTask`` and
returns the file's bytes), so a batch uses every core. It never writes anything: the parent process writes
the bytes through the path guard.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from photoedit.core.decode import decode_linear
from photoedit.core.export.encode import encode
from photoedit.core.export.geometry import ExportGeometry
from photoedit.core.export.icc import icc_profile
from photoedit.core.export.metadata import build_metadata, read_source_exif
from photoedit.core.export.sharpen import output_sharpen
from photoedit.core.render.anchors import ToneAnchors
from photoedit.core.render.pipeline import render
from photoedit.core.render.profile import CameraProfile
from photoedit.models.adjustments import AdjustmentParams
from photoedit.models.export import DecodeUsed, ExportSettings


@dataclass(frozen=True)
class ExportTask:
    path: Path
    width: int  # the photo's upright full size, which ``geometry`` refers to
    height: int
    adjustments: AdjustmentParams
    profile: CameraProfile | None
    anchors: ToneAnchors
    settings: ExportSettings
    geometry: ExportGeometry
    copyright: str | None
    creator: str | None


@dataclass(frozen=True)
class RenderedExport:
    data: bytes
    width: int
    height: int
    warnings: tuple[str, ...] = ()


def render_export(task: ExportTask) -> RenderedExport:
    settings, geometry = task.settings, task.geometry
    base = decode_linear(task.path, half_size=geometry.decode == DecodeUsed.HALF)
    height, width = base.pixels.shape[:2]
    # The crop is in full-size pixels; the decode may be half size (or a pixel off LibRaw's nominal size).
    sx, sy = width / task.width, height / task.height
    crop = geometry.crop
    x0, x1 = round(crop.left * sx), round((crop.left + crop.width) * sx)
    y0, y1 = round(crop.top * sy), round((crop.top + crop.height) * sy)
    pixels = _resize(base.pixels[max(0, y0) : min(height, y1), max(0, x0) : min(width, x1)], geometry)
    cropped = dataclasses.replace(base, pixels=pixels)
    encoded = render(
        cropped,
        task.adjustments,
        task.profile,
        original_width=crop.width,
        anchors=task.anchors,
        output=settings.color_space,
        low_memory=True,  # exports run several at a time; previews keep the faster default
    )
    encoded = output_sharpen(encoded, settings.sharpening, settings.size.ppi)
    meta = build_metadata(
        read_source_exif(task.path),
        settings.metadata,
        copyright=task.copyright,
        creator=task.creator,
        width=geometry.width,
        height=geometry.height,
        ppi=settings.size.ppi,
        color_space=settings.color_space,
    )
    result = encode(
        encoded, settings.file, icc=icc_profile(settings.color_space), meta=meta, ppi=settings.size.ppi
    )
    return RenderedExport(result.data, geometry.width, geometry.height, tuple(result.warnings))


def _resize(pixels: np.ndarray, geometry: ExportGeometry) -> np.ndarray:
    """Scale linear pixels to exactly the output size: area averaging down, bicubic up."""
    size = (geometry.width, geometry.height)
    if pixels.shape[1::-1] == size:
        return np.ascontiguousarray(pixels, dtype=np.float32)
    shrinking = pixels.shape[1] >= geometry.width and pixels.shape[0] >= geometry.height
    resized = cv2.resize(pixels, size, interpolation=cv2.INTER_AREA if shrinking else cv2.INTER_CUBIC)
    if not shrinking:
        resized = np.maximum(resized, 0)  # bicubic overshoots below black at hard edges
    return np.ascontiguousarray(resized, dtype=np.float32)
