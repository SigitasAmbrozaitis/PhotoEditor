"""Evaluating subject detection against hand-labeled boxes (P6b.9).

For each labeled photo: is the detected subject the labeled one (its center inside the found box, or IoU ≥
``HIT_IOU``), and does the suggested 4:5 crop keep at least ``CROP_KEEP`` of the labeled box (of what any crop
of that size could keep, for a subject bigger than the crop, like a cat filling a 2:3 frame)? A photo labeled
"no subject" is a hit when nothing is found or the suggested crop is centered anyway. Results are grouped by
folder, each with its own targets, because each kind of shooting fails in its own way.
"""

from __future__ import annotations

import io
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw
from pydantic import BaseModel, ConfigDict, Field

from photoedit.core.catalog import CatalogPhoto
from photoedit.core.subject.suggest import suggest
from photoedit.models.adjustments import CropRect
from photoedit.models.subject import SubjectBox, SubjectInfo, SubjectSource

HIT_IOU = 0.3
CROP_KEEP = 0.95
CROP_RATIO = 4 / 5
# A crop whose center is this close (fraction of the photo) to the centered crop's counts as centered.
CENTERED = 0.02
TARGET_HITS = 0.8
TARGET_CROPS = 0.9
_TILE = 300


class LabeledPhoto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    folder: str = Field(description="The sample folder's name, e.g. '2026-08-16'.")
    file: str
    box: tuple[float, float, float, float] | None = Field(description="left, top, right, bottom; null = none")
    note: str = ""

    @property
    def subject(self) -> SubjectBox | None:
        if self.box is None:
            return None
        left, top, right, bottom = self.box
        return SubjectBox(left=left, top=top, right=right, bottom=bottom)


class SubjectLabels(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    about: str = ""
    photos: list[LabeledPhoto]


@dataclass(frozen=True)
class PhotoResult:
    label: LabeledPhoto
    photo: CatalogPhoto
    info: SubjectInfo
    crop: CropRect
    hit: bool
    crop_ok: bool


@dataclass(frozen=True)
class FolderScore:
    folder: str
    photos: int
    hits: int
    crops: int

    @property
    def hit_rate(self) -> float:
        return self.hits / self.photos if self.photos else 0.0

    @property
    def crop_rate(self) -> float:
        return self.crops / self.photos if self.photos else 0.0

    @property
    def passed(self) -> bool:
        return self.hit_rate >= TARGET_HITS and self.crop_rate >= TARGET_CROPS


def load_labels(path: Path) -> SubjectLabels:
    return SubjectLabels.model_validate_json(path.read_text(encoding="utf-8"))


def iou(a: SubjectBox, b: SubjectBox) -> float:
    inter = _overlap(a, b)
    union = _area(a) + _area(b) - inter
    return inter / union if union > 0 else 0.0


def kept_share(box: SubjectBox, crop: CropRect) -> float:
    """The share of ``box``'s area inside ``crop``."""
    as_box = SubjectBox(left=crop.left, top=crop.top, right=crop.right, bottom=crop.bottom)
    return _overlap(box, as_box) / _area(box)


def judge(
    label: SubjectBox | None, info: SubjectInfo, crop: CropRect, centered: CropRect
) -> tuple[bool, bool]:
    """(hit, crop kept) for one photo."""
    if label is None:
        is_centered = (
            abs((crop.left + crop.right) / 2 - (centered.left + centered.right) / 2) <= CENTERED
            and abs((crop.top + crop.bottom) / 2 - (centered.top + centered.bottom) / 2) <= CENTERED
        )
        ok = info.source is SubjectSource.NONE or is_centered
        return ok, ok
    found = info.box
    hit = found is not None and (_contains(found, label.center) or iou(found, label) >= HIT_IOU)
    possible = min(1.0, (crop.right - crop.left) / (label.right - label.left)) * min(
        1.0, (crop.bottom - crop.top) / (label.bottom - label.top)
    )
    return hit, kept_share(label, crop) >= CROP_KEEP * possible


def evaluate(
    labels: Sequence[LabeledPhoto],
    photos: Sequence[CatalogPhoto],
    detect: Callable[[CatalogPhoto], SubjectInfo],
    *,
    workers: int = 8,
) -> list[PhotoResult]:
    """Detect (``detect`` may be cached) and judge each labeled photo, a few at a time."""
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        infos = list(pool.map(detect, photos))
    results = []
    for label, photo, info in zip(labels, photos, infos, strict=True):
        width, height = float(photo.width), float(photo.height)
        crop = suggest(info.box, ratio=CROP_RATIO, angle=0, width=width, height=height).crop
        centered = suggest(None, ratio=CROP_RATIO, angle=0, width=width, height=height).crop
        hit, crop_ok = judge(label.subject, info, crop, centered)
        results.append(PhotoResult(label, photo, info, crop, hit, crop_ok))
    return results


def scores(results: Sequence[PhotoResult]) -> list[FolderScore]:
    folders = sorted({r.label.folder for r in results})
    return [
        FolderScore(
            folder,
            sum(1 for r in results if r.label.folder == folder),
            sum(1 for r in results if r.label.folder == folder and r.hit),
            sum(1 for r in results if r.label.folder == folder and r.crop_ok),
        )
        for folder in folders
    ]


def report(results: Sequence[PhotoResult]) -> str:
    """A plain-text report: one line per folder, then each miss with what was found instead."""
    lines = [
        f"{'folder':<12} {'photos':>6} {'hits':>10} {'4:5 crops':>10}  targets: hits ≥ 80 %, crops ≥ 90 %"
    ]
    for s in scores(results):
        mark = "ok" if s.passed else "MISSED"
        lines.append(f"{s.folder:<12} {s.photos:>6} {s.hit_rate:>9.0%} {s.crop_rate:>10.0%}  {mark}")
    misses = [r for r in results if not (r.hit and r.crop_ok)]
    if misses:
        lines.append("")
        lines.append("misses:")
        for r in misses:
            found = (
                f"{r.info.source.value} {r.info.kind.value if r.info.kind else ''}".strip()
                if r.info.box is not None
                else "none"
            )
            what = [] if r.hit else ["detection"]
            what += [] if r.crop_ok else ["crop"]
            note = f" ({r.label.note})" if r.label.note else ""
            lines.append(f"  {r.label.folder}/{r.label.file}{note}: {' + '.join(what)} missed; found {found}")
    return "\n".join(lines)


def contact_sheet(results: Sequence[PhotoResult], thumbnail: Callable[[CatalogPhoto], bytes]) -> bytes:
    """Each photo with the labeled box (green), the found one (yellow when right, red when wrong), and the
    suggested 4:5 crop (cyan)."""
    columns = 8
    rows = (len(results) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * _TILE, rows * (_TILE + 16)), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    for index, r in enumerate(results):
        image = Image.open(io.BytesIO(thumbnail(r.photo))).convert("RGB")
        image.thumbnail((_TILE, _TILE))
        x0 = (index % columns) * _TILE + (_TILE - image.width) // 2
        y0 = (index // columns) * (_TILE + 16) + (_TILE - image.height) // 2
        sheet.paste(image, (x0, y0))
        place = (x0, y0, image.width, image.height)
        _outline(draw, place, r.crop, (0, 200, 255), 1)
        if r.label.subject is not None:
            _outline(draw, place, r.label.subject, (0, 230, 0), 2)
        if r.info.box is not None:
            _outline(draw, place, r.info.box, (255, 220, 0) if r.hit else (255, 40, 40), 2)
        verdict = ("hit" if r.hit else "MISS") + (" crop ok" if r.crop_ok else " CROP")
        text_at = ((index % columns) * _TILE + 4, (index // columns) * (_TILE + 16) + _TILE + 2)
        draw.text(text_at, f"{r.label.file[:8]} {verdict}", fill=(230, 230, 230))
    buffer = io.BytesIO()
    sheet.save(buffer, "JPEG", quality=88)
    return buffer.getvalue()


def _outline(
    draw: ImageDraw.ImageDraw,
    place: tuple[int, int, int, int],
    box: SubjectBox | CropRect,
    color: tuple[int, int, int],
    width: int,
) -> None:
    """``box`` (normalized) drawn on an image pasted at ``place`` (x, y, width, height)."""
    x, y, w, h = place
    corners = (x + box.left * w, y + box.top * h, x + box.right * w, y + box.bottom * h)
    draw.rectangle(corners, outline=color, width=width)


def _area(box: SubjectBox) -> float:
    return (box.right - box.left) * (box.bottom - box.top)


def _overlap(a: SubjectBox, b: SubjectBox) -> float:
    width = min(a.right, b.right) - max(a.left, b.left)
    height = min(a.bottom, b.bottom) - max(a.top, b.top)
    return max(0.0, width) * max(0.0, height)


def _contains(box: SubjectBox, point: tuple[float, float]) -> bool:
    return box.left <= point[0] <= box.right and box.top <= point[1] <= box.bottom
