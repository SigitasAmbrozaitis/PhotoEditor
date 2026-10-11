"""Rendering one export: decode → geometry + aspect crop → resize → pipeline → output sharpening → encode.

``render_export`` runs in a worker process (it gets everything it needs in a picklable ``ExportTask`` and
returns the file's bytes), so a batch uses every core. It never writes anything: the parent process writes
the bytes through the path guard.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from photoedit.core.decode import decode_linear
from photoedit.core.export.encode import encode
from photoedit.core.export.geometry import ExportGeometry
from photoedit.core.export.icc import icc_profile
from photoedit.core.export.metadata import build_metadata, read_source_exif
from photoedit.core.export.sharpen import output_sharpen
from photoedit.core.geometry import sub_crop
from photoedit.core.render.anchors import ToneAnchors
from photoedit.core.render.pipeline import render
from photoedit.core.render.profile import CameraProfile
from photoedit.core.render.warp import apply_geometry
from photoedit.models.adjustments import AdjustmentParams, Geometry
from photoedit.models.export import DecodeUsed, ExportSettings


@dataclass(frozen=True)
class ExportTask:
    path: Path
    width: (
        int  # the photo's full size after its own geometry (crop, quarter turn), which ``geometry`` refers to
    )
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
    # The export's aspect crop is in pixels of the photo after its own geometry: as a part of the photo's crop
    # it maps onto the decode at any size (half or full, or a pixel off LibRaw's nominal size).
    box, photo_geometry = geometry.crop, task.adjustments.geometry
    crop = sub_crop(
        photo_geometry.crop,
        box.left / task.width,
        box.top / task.height,
        (box.left + box.width) / task.width,
        (box.top + box.height) / task.height,
    )
    cropped = apply_geometry(base, photo_geometry, crop=crop, size=(geometry.width, geometry.height))
    encoded = render(
        cropped,
        task.adjustments.model_copy(update={"geometry": Geometry()}),  # already applied
        task.profile,
        original_width=box.width,
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
