"""In-memory mock backend with fake data (Phase 1 UI skeleton).

It implements the same operations the real core will provide, so API routes and the UI are built against the
final contract. Later phases replace it piece by piece. Nothing here reads photos or writes files.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from photoedit.core.presets import BUILTIN_PRESETS
from photoedit.mock import images
from photoedit.models import (
    AdjustmentParams,
    ApplyAndExportRequest,
    ApplyStyleRequest,
    ExportPreset,
    ExportRequest,
    Job,
    JobItem,
    JobKind,
    JobStatus,
    LibraryInfo,
    Page,
    Photo,
    PhotoDetail,
    PhotoEdit,
    PhotoSort,
    SortOrder,
    Style,
    StyleSample,
    StyleSummary,
)

Clock = Callable[[], datetime]

MOCK_FOLDER = "C:/Users/ambro/Pictures/2026/2026-08-11"
PHOTO_COUNT = 24
SECONDS_PER_ITEM = 0.4  # fake processing time per photo in a job
_BASE_TIME = datetime(2026, 8, 11, 8, 30, tzinfo=UTC)
_LENSES = ("XF16-55mmF2.8 R LM WR", "XF35mmF1.4 R", "XF56mmF1.2 R", "XF10-24mmF4 R OIS")
_SHUTTERS = ("1/250", "1/1000", "1/60", "1/125", "1/500", "1/30", "1/2000")


class NotFoundError(LookupError):
    """Requested object doesn't exist."""


# ----------------------------------------------------------------- fake data


def _photo(i: int) -> Photo:
    portrait = i % 4 == 1
    width, height = (4160, 6240) if portrait else (6240, 4160)
    name = f"DSCF{5437 + i:04d}.RAF"
    style_cycle = (None, "warm-film", None, "moody-forest", "clean-bright", None)
    style_id = style_cycle[i % len(style_cycle)]
    return Photo(
        id=f"p{i + 1:03d}",
        path=f"{MOCK_FOLDER}/{name}",
        filename=name,
        folder=MOCK_FOLDER,
        file_size=26_000_000 + (i * 977_123) % 9_000_000,
        captured_at=_BASE_TIME + timedelta(minutes=17 * i),
        camera="FUJIFILM X-T3",
        lens=_LENSES[i % len(_LENSES)],
        iso=(160, 320, 640, 1600, 3200)[i % 5],
        shutter=_SHUTTERS[i % len(_SHUTTERS)],
        aperture=(2.8, 1.4, 4.0, 5.6, 8.0)[i % 5],
        focal_length=(16.0, 35.0, 56.0, 23.0, 10.0)[i % 5],
        width=width,
        height=height,
        rating=(i * 7) % 6,
        style_id=style_id,
        has_overrides=style_id is not None and i % 3 == 0,
    )


def _adjust(**groups: dict[str, object]) -> AdjustmentParams:
    return AdjustmentParams.model_validate(groups)


_STYLE_DEFS: tuple[tuple[str, str, str, list[str], list[str], AdjustmentParams, images.Look], ...] = (
    (
        "warm-film",
        "Warm Film",
        "Soft, warm analog look with gentle contrast, lifted blacks and golden highlights. "
        "Inspired by Portra-style color negative film.",
        ["portraits", "golden hour", "travel"],
        ["night scenes", "cold winter scenes"],
        _adjust(
            white_balance={"temperature": 6200, "tint": 8},
            tone={"exposure": 0.15, "contrast": -12, "highlights": -30, "shadows": 20, "blacks": 15},
            presence={"vibrance": 10, "saturation": -8},
            color_grading={
                "shadows": {"hue": 200, "saturation": 8},
                "highlights": {"hue": 40, "saturation": 15},
            },
            effects={"grain": {"amount": 20}},
        ),
        images.Look(tint=(255, 170, 90), tint_strength=0.12, saturation=0.95, contrast=0.92, brightness=1.05),
    ),
    (
        "moody-forest",
        "Moody Forest",
        "Dark, desaturated greens and teal shadows with deep contrast. "
        "For forests, fog and overcast landscapes.",
        ["forests", "fog", "overcast landscapes"],
        ["portraits with skin tones", "beach"],
        _adjust(
            tone={"exposure": -0.4, "contrast": 25, "highlights": -40, "shadows": -10, "blacks": -15},
            presence={"vibrance": -15, "saturation": -20},
            hsl={"green": {"hue": 20, "saturation": -35, "luminance": -20}, "yellow": {"saturation": -25}},
            color_grading={"shadows": {"hue": 190, "saturation": 20}},
            effects={"vignette": {"amount": -25}},
        ),
        images.Look(tint=(40, 90, 85), tint_strength=0.18, saturation=0.7, contrast=1.25, brightness=0.85),
    ),
    (
        "clean-bright",
        "Clean & Bright",
        "Airy, bright and neutral. Lifted exposure, clean whites and accurate colors.",
        ["interiors", "product", "daylight portraits"],
        ["low-key scenes"],
        _adjust(
            tone={"exposure": 0.5, "contrast": -5, "highlights": -20, "shadows": 30, "whites": 15},
            presence={"vibrance": 15},
        ),
        images.Look(saturation=1.05, contrast=0.95, brightness=1.18),
    ),
    (
        "bw-classic",
        "Classic B&W",
        "Punchy black and white with strong contrast and deep blacks.",
        ["street", "architecture", "dramatic skies"],
        ["scenes that rely on color"],
        _adjust(
            tone={"contrast": 35, "highlights": -15, "shadows": 10, "whites": 20, "blacks": -25},
            presence={"saturation": -100},
            effects={"grain": {"amount": 30}},
        ),
        images.Look(saturation=0.0, contrast=1.35),
    ),
)


def _style_sample_url(style_id: str, n: int, which: str) -> str:
    return f"/api/styles/{style_id}/samples/{n}/{which}.jpg"


def _build_styles() -> dict[str, Style]:
    styles: dict[str, Style] = {}
    for idx, (sid, name, desc, best, avoid, adjustments, _look) in enumerate(_STYLE_DEFS):
        samples = [
            StyleSample(
                caption=f"Sample {n + 1}",
                before_url=_style_sample_url(sid, n, "before"),
                after_url=_style_sample_url(sid, n, "after"),
            )
            for n in range(3)
        ]
        created = _BASE_TIME - timedelta(days=30 - idx * 5)
        styles[sid] = Style(
            id=sid,
            name=name,
            description=desc,
            best_for=best,
            avoid_on=avoid,
            adjustments=adjustments,
            samples=samples,
            cover_url=samples[0].after_url,
            created_at=created,
            updated_at=created + timedelta(days=2),
            version=idx + 1,
        )
    return styles


_LOOKS: dict[str, images.Look] = {d[0]: d[6] for d in _STYLE_DEFS}


# ----------------------------------------------------------------- jobs


@dataclass
class _JobRecord:
    id: str
    kind: JobKind
    title: str
    created_at: datetime
    photos: list[Photo]
    style_id: str | None = None
    preset_id: str | None = None
    destination: str | None = None
    failing: frozenset[int] = field(default_factory=frozenset)  # item indexes that fail (demo of errors)
    cancelled_at: datetime | None = None


# ----------------------------------------------------------------- backend


class MockBackend:
    """Fake implementation of the backend operations used by the API."""

    def __init__(self, clock: Clock | None = None, folder: str = MOCK_FOLDER) -> None:
        self._clock: Clock = clock or (lambda: datetime.now(UTC))
        self._folder = folder
        self._photos: dict[str, Photo] = {}
        for i in range(PHOTO_COUNT):
            p = _photo(i)
            p = p.model_copy(update={"folder": folder, "path": f"{folder}/{p.filename}"})
            self._photos[p.id] = p
        self._styles = _build_styles()
        self._presets: dict[str, ExportPreset] = {p.id: p for p in BUILTIN_PRESETS}
        self._jobs: dict[str, _JobRecord] = {}
        self._job_seq = itertools.count(1)
        self._seed_jobs()

    # ---- library / photos

    def library(self) -> LibraryInfo:
        return LibraryInfo(folder=self._folder, photo_count=len(self._photos))

    def list_photos(
        self,
        *,
        style_id: str | None = None,
        min_rating: int = 0,
        sort: PhotoSort = PhotoSort.DATE,
        order: SortOrder = SortOrder.ASC,
        offset: int = 0,
        limit: int = 100,
    ) -> Page[Photo]:
        photos = [p for p in self._photos.values() if p.rating >= min_rating]
        if style_id == "none":
            photos = [p for p in photos if p.style_id is None]
        elif style_id is not None:
            photos = [p for p in photos if p.style_id == style_id]
        keys: dict[PhotoSort, Callable[[Photo], object]] = {
            PhotoSort.DATE: lambda p: (p.captured_at, p.filename),
            PhotoSort.NAME: lambda p: p.filename,
            PhotoSort.RATING: lambda p: (p.rating, p.filename),
        }
        photos.sort(key=keys[sort], reverse=order == SortOrder.DESC)  # type: ignore[arg-type]
        return Page[Photo](
            items=photos[offset : offset + limit], total=len(photos), offset=offset, limit=limit
        )

    def photo(self, photo_id: str) -> Photo:
        try:
            return self._photos[photo_id]
        except KeyError:
            raise NotFoundError(f"photo '{photo_id}' not found") from None

    def photo_detail(self, photo_id: str) -> PhotoDetail:
        photo = self.photo(photo_id)
        adjustments = (
            self._styles[photo.style_id].adjustments.model_copy(deep=True)
            if photo.style_id
            else AdjustmentParams()
        )
        overridden: list[str] = []
        if photo.has_overrides:
            adjustments.tone.exposure = round(adjustments.tone.exposure + 0.3, 2)
            adjustments.geometry.crop.left = 0.05
            adjustments.geometry.crop.right = 0.95
            overridden = ["tone.exposure", "geometry.crop.left", "geometry.crop.right"]
        return PhotoDetail(
            photo=photo,
            edit=PhotoEdit(
                photo_id=photo.id, style_id=photo.style_id, adjustments=adjustments, overridden=overridden
            ),
        )

    def photo_image(self, photo_id: str, *, long_edge: int, before: bool = False) -> bytes:
        photo = self.photo(photo_id)
        index = int(photo.id[1:]) - 1
        width, height = images.fit_size(photo.width, photo.height, long_edge)
        if before:
            look = images.FLAT_LOOK
        elif photo.style_id:
            look = _LOOKS[photo.style_id]
        else:
            look = images.NEUTRAL_LOOK
        return images.render_placeholder(index, width, height, photo.filename, look)

    # ---- styles

    def list_styles(self) -> list[StyleSummary]:
        return [
            StyleSummary.model_validate(s.model_dump(include=set(StyleSummary.model_fields)))
            for s in sorted(self._styles.values(), key=lambda s: s.name)
        ]

    def style(self, style_id: str) -> Style:
        try:
            return self._styles[style_id]
        except KeyError:
            raise NotFoundError(f"style '{style_id}' not found") from None

    def style_sample_image(self, style_id: str, n: int, *, before: bool) -> bytes:
        style = self.style(style_id)
        if not 0 <= n < len(style.samples):
            raise NotFoundError(f"style '{style_id}' has no sample {n}")
        scene = (list(self._styles).index(style_id) * 3 + n) % len(images.SCENES)
        look = images.FLAT_LOOK if before else _LOOKS[style_id]
        return images.render_placeholder(scene, 800, 533, f"{style.name} #{n + 1}", look)

    # ---- export presets

    def list_presets(self) -> list[ExportPreset]:
        return list(self._presets.values())

    def preset(self, preset_id: str) -> ExportPreset:
        try:
            return self._presets[preset_id]
        except KeyError:
            raise NotFoundError(f"export preset '{preset_id}' not found") from None

    # ---- jobs

    def create_job(self, request: ApplyStyleRequest | ExportRequest | ApplyAndExportRequest) -> Job:
        photos = [self.photo(pid) for pid in request.photo_ids]
        style_id = getattr(request, "style_id", None)
        preset_id = getattr(request, "preset_id", None)
        destination = getattr(request, "destination", None)
        style_name = self.style(style_id).name if style_id else None
        preset_name = self.preset(preset_id).name if preset_id else "custom settings"
        n = len(photos)
        noun = "photo" if n == 1 else "photos"
        titles = {
            JobKind.APPLY_STYLE: f"Apply {style_name} to {n} {noun}",
            JobKind.EXPORT: f"Export {n} {noun} ({preset_name})",
            JobKind.APPLY_AND_EXPORT: f"Apply {style_name} and export {n} {noun} ({preset_name})",
        }
        record = _JobRecord(
            id=f"j{next(self._job_seq):04d}",
            kind=request.kind,
            title=titles[request.kind],
            created_at=self._clock(),
            photos=photos,
            style_id=style_id,
            preset_id=preset_id,
            destination=destination,
        )
        self._jobs[record.id] = record
        return self._job_view(record)

    def list_jobs(self) -> list[Job]:
        return [
            self._job_view(r) for r in sorted(self._jobs.values(), key=lambda r: r.created_at, reverse=True)
        ]

    def job(self, job_id: str) -> Job:
        try:
            return self._job_view(self._jobs[job_id])
        except KeyError:
            raise NotFoundError(f"job '{job_id}' not found") from None

    def cancel_job(self, job_id: str) -> Job:
        job = self.job(job_id)
        record = self._jobs[job_id]
        if job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
            record.cancelled_at = self._clock()
        return self._job_view(record)

    def _job_view(self, record: _JobRecord) -> Job:
        """Derive the job's state from elapsed time: item i finishes after (i + 1) * SECONDS_PER_ITEM."""
        now = record.cancelled_at or self._clock()
        elapsed = (now - record.created_at).total_seconds()
        total = len(record.photos)
        finished = min(total, max(0, int(elapsed / SECONDS_PER_ITEM)))
        items: list[JobItem] = []
        failed = 0
        for i, photo in enumerate(record.photos):
            if i < finished:
                if i in record.failing:
                    failed += 1
                    items.append(
                        JobItem(
                            photo_id=photo.id,
                            filename=photo.filename,
                            status=JobStatus.FAILED,
                            message="Mock failure: file could not be decoded",
                        )
                    )
                else:
                    out = (
                        f"{record.destination}/{photo.filename.rsplit('.', 1)[0]}.jpg"
                        if record.destination and record.kind != JobKind.APPLY_STYLE
                        else None
                    )
                    items.append(
                        JobItem(
                            photo_id=photo.id, filename=photo.filename, status=JobStatus.DONE, output_path=out
                        )
                    )
            elif i == finished and record.cancelled_at is None:
                items.append(JobItem(photo_id=photo.id, filename=photo.filename, status=JobStatus.RUNNING))
            else:
                status = JobStatus.CANCELLED if record.cancelled_at else JobStatus.QUEUED
                items.append(JobItem(photo_id=photo.id, filename=photo.filename, status=status))

        if record.cancelled_at is not None and finished < total:
            status, finished_at = JobStatus.CANCELLED, record.cancelled_at
        elif finished >= total:
            status = JobStatus.FAILED if failed == total else JobStatus.DONE
            finished_at = record.created_at + timedelta(seconds=total * SECONDS_PER_ITEM)
        else:
            status, finished_at = JobStatus.RUNNING, None
        return Job(
            id=record.id,
            kind=record.kind,
            status=status,
            title=record.title,
            created_at=record.created_at,
            finished_at=finished_at,
            progress=finished / total if total else 1.0,
            total=total,
            completed=finished,
            failed=failed,
            style_id=record.style_id,
            preset_id=record.preset_id,
            destination=record.destination,
            items=items,
        )

    def _seed_jobs(self) -> None:
        """Two finished jobs so the Jobs screen isn't empty: one clean, one with a failed item."""
        photos = list(self._photos.values())
        start = self._clock() - timedelta(hours=2)
        self._jobs["j0001"] = _JobRecord(
            id="j0001",
            kind=JobKind.APPLY_AND_EXPORT,
            title="Apply Warm Film and export 6 photos (Instagram portrait (4:5))",
            created_at=start,
            photos=photos[:6],
            style_id="warm-film",
            preset_id="instagram-portrait",
            destination="C:/Users/ambro/Pictures/Exports/instagram",
        )
        self._jobs["j0002"] = _JobRecord(
            id="j0002",
            kind=JobKind.EXPORT,
            title="Export 4 photos (Print 8×10 in (20×25 cm))",
            created_at=start + timedelta(minutes=30),
            photos=photos[6:10],
            preset_id="print-8x10",
            destination="C:/Users/ambro/Pictures/Exports/print",
            failing=frozenset({2}),
        )
        self._job_seq = itertools.count(3)
