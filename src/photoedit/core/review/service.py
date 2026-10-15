"""The review service (P6c.4): prepares an export, keeps the user's decisions, and exports from it.

**Prepare** is a job: it detects missing subjects, frames every photo exactly as the export will (through
``Exporter.frame``), sorts it into Ready, Check or unusable by the review rules, and renders its framing
preview. A style asked for is applied first, by its own job on the same queue, so the previews show it.

A review is stored as ``workspace/reviews/<id>.json`` (through the path guard): a reload or a restart keeps
the decisions. Every read **refreshes** it: each photo is framed again against its current edit and subject,
and an approval whose framing changed since is dropped (the photo goes back to Check). Exports use the
refreshed framing and each photo's zoom, so the files show what the previews showed. Exported photos leave the
review; an empty review is deleted, and reviews older than ``KEEP_DAYS`` are pruned at start.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import secrets
import threading
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

from photoedit.core.catalog import CatalogPhoto
from photoedit.core.errors import InvalidRequestError, NotFoundError
from photoedit.core.export.geometry import ZOOM_TOLERANCE, Box
from photoedit.core.export.geometry import warnings as geometry_warnings
from photoedit.core.export.service import Exporter, Framing, frames_subjects, in_export_order
from photoedit.core.geometry import crop_box_to_upright
from photoedit.core.jobs import ItemResult, ItemSpec, JobManager
from photoedit.core.library import Library
from photoedit.core.review.rules import reasons
from photoedit.core.styling import Styling
from photoedit.core.subject.analysis import focus_box, found_candidates
from photoedit.core.subject.service import Subjects
from photoedit.models import Job, JobKind
from photoedit.models.adjustments import CropRect
from photoedit.models.export import ExportSettings
from photoedit.models.review import (
    ExportReview,
    FramePosition,
    ReviewCandidate,
    ReviewExportScope,
    ReviewFrames,
    ReviewItem,
    ReviewItemUpdate,
    ReviewReason,
    ReviewRule,
    ReviewSettings,
    ReviewStatus,
    ReviewSubjectUpdate,
    ReviewSummary,
    ZoomFrame,
    ZoomLimits,
)
from photoedit.models.subject import SubjectInfo, SubjectSource
from photoedit.safety import PathGuard

REVIEWS_DIR = "reviews"
SETTINGS_FILE = "review-settings.json"
KEEP_DAYS = 30
PREVIEW_LONG_EDGE = 800
# Photos prepared at once: like a detection job (each holds a half-size decode at its peak).
PREPARE_THREADS = 6
# Zoom steps sent for the slider: about 0.01× apart, at most this many.
FRAME_STEP = 0.01
MAX_FRAMES = 400
_ID = re.compile(r"^[a-z0-9]{12}$")
_ID_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"

type Clock = Callable[[], datetime]
type Found = tuple[SubjectInfo | None, str | None]


def _now() -> datetime:
    return datetime.now(UTC)


class Reviews:
    def __init__(
        self,
        library: Library,
        exporter: Exporter,
        subjects: Subjects,
        styling: Styling,
        jobs: JobManager,
        guard: PathGuard,
        workspace_dir: Path,
        *,
        clock: Clock = _now,
    ) -> None:
        self._library = library
        self._exporter = exporter
        self._subjects = subjects
        self._styling = styling
        self._jobs = jobs
        self._guard = guard
        self._dir = workspace_dir / REVIEWS_DIR
        self._settings_path = workspace_dir / SETTINGS_FILE
        self._clock = clock
        self._lock = threading.RLock()
        self._exporting: dict[str, set[str]] = {}  # review id → photos in an export job right now
        self.prune()

    # ---- settings

    def settings(self) -> ReviewSettings:
        if not self._settings_path.is_file():
            return ReviewSettings()
        try:
            return ReviewSettings.model_validate_json(self._settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise InvalidRequestError(
                f"the review settings in {self._settings_path} can't be read ({exc}); save them again or "
                "delete the file to go back to the defaults"
            ) from None

    def set_settings(self, settings: ReviewSettings) -> ReviewSettings:
        """Save the rules; open reviews are sorted again by them."""
        with self._lock:
            text = settings.model_dump_json(indent=2) + "\n"
            self._guard.write_atomic(self._settings_path, text.encode("utf-8"))
            for review_id in self._ids():
                try:
                    self.get(review_id)
                except (NotFoundError, InvalidRequestError):
                    continue  # a broken review file stays as it is
        return settings

    # ---- prepare

    def prepare(
        self,
        photo_ids: Sequence[str],
        settings: ExportSettings,
        destination: str,
        *,
        preset_id: str | None = None,
        style_id: str | None = None,
        even_out: bool = False,
    ) -> Job:
        """Prepare an export for review as a job; the job's ``review_id`` names the review it creates.

        Everything that can fail early does, before anything is written: the photos, the destination, the
        style, the review settings.
        """
        if not photo_ids:
            raise InvalidRequestError("no photos to prepare")
        if even_out and style_id is None:
            raise InvalidRequestError("even out needs a style")
        photos = in_export_order({pid: self._library.photo(pid) for pid in photo_ids}.values())
        check = self._exporter.check_destination(destination)
        if not check.ok:
            raise InvalidRequestError(check.reason or f"{destination} can't take exports")
        rules = self.settings()
        review_id = "".join(secrets.choice(_ID_ALPHABET) for _ in range(12))
        queue = None
        if style_id is not None:
            queue = f"prepare-{review_id}"
            self._styling.apply([p.id for p in photos], style_id, even_out=even_out, queue=queue)
        prepared: dict[int, ReviewItem] = {}

        def work(index: int) -> ItemResult:
            photo = self._library.photo(photos[index].id)  # again: the style job changed its edit
            found = self._found(photo, settings, detect=True)
            item = self._build(photo, settings, rules, found)
            warnings: list[str] = []
            if item.status != ReviewStatus.UNUSABLE:
                try:
                    self._library.framing_preview(photo.id, item.crop, PREVIEW_LONG_EDGE)
                except Exception as exc:  # the review still works; the preview renders when asked
                    warnings.append(f"the framing preview failed: {exc}")
            prepared[index] = item
            message = item.status.value
            if item.reasons:
                message += ": " + "; ".join(r.text for r in item.reasons)
            return ItemResult(photo_id=photo.id, message=message, warnings=tuple(warnings))

        def finish() -> str:
            now = self._clock()
            review = ExportReview(
                id=review_id,
                created_at=now,
                updated_at=now,
                preset_id=preset_id,
                style_id=style_id,
                settings=settings,
                destination=check.path,
                items=[prepared[i] for i in range(len(photos)) if i in prepared],
            )
            with self._lock:
                self._save(review)
            return _summary(review)

        noun = "photo" if len(photos) == 1 else "photos"
        return self._jobs.submit(
            JobKind.PREPARE_EXPORT,
            f"Prepare {len(photos)} {noun} for export ({preset_id or 'custom settings'})",
            [ItemSpec(filename=p.path.name, photo_id=p.id) for p in photos],
            work,
            parallel=PREPARE_THREADS,
            finish=finish,
            queue=queue,
            style_id=style_id,
            preset_id=preset_id,
            destination=check.path,
            review_id=review_id,
        )

    # ---- reading

    def get(self, review_id: str) -> ExportReview:
        """The review, refreshed against the photos' current edits and subjects."""
        with self._lock:
            review = self._load(review_id)
            fresh = self._refresh(review)
            if fresh.items != review.items:
                fresh = fresh.model_copy(update={"updated_at": self._clock()})
                self._save(fresh)
            return fresh

    def summaries(self) -> list[ReviewSummary]:
        """Open reviews, newest first (as last stored; opening one refreshes it)."""
        out = []
        with self._lock:
            for review_id in self._ids():
                try:
                    review = self._load(review_id)
                except (NotFoundError, InvalidRequestError):
                    continue
                out.append(
                    ReviewSummary(
                        id=review.id,
                        created_at=review.created_at,
                        updated_at=review.updated_at,
                        preset_id=review.preset_id,
                        destination=review.destination,
                        counts=review.counts,
                    )
                )
        return sorted(out, key=lambda r: (r.created_at, r.id), reverse=True)

    def discard(self, review_id: str) -> None:
        with self._lock:
            path = self._path(review_id)
            if not path.is_file():
                raise NotFoundError(f"review '{review_id}' not found")
            self._guard.assert_writable(path)
            path.unlink()

    def preview(self, review_id: str, photo_id: str) -> bytes:
        """The photo's framing preview: its edit cut to the export's crop."""
        item = self._item(self.get(review_id), photo_id)
        if item.status == ReviewStatus.UNUSABLE:
            raise InvalidRequestError(f"{item.filename} can't be exported: {item.reasons[0].text}")
        return self._library.framing_preview(photo_id, item.crop, PREVIEW_LONG_EDGE)

    # ---- decisions

    def update_item(self, review_id: str, photo_id: str, update: ReviewItemUpdate) -> ExportReview:
        """Change a photo's zoom (``None`` = automatic), the crop's position (``None`` = placed by the rules)
        or approval. A zoom or a position is a decision, so it approves the photo."""
        with self._lock:
            review = self.get(review_id)
            item = self._item(review, photo_id)
            if item.status == ReviewStatus.UNUSABLE:
                raise InvalidRequestError(f"{item.filename} can't be exported: {item.reasons[0].text}")
            approve = update.approved
            given = update.model_fields_set
            if "zoom" in given or "position" in given:
                zoom = update.zoom if "zoom" in given else item.zoom_override
                position = update.position if "position" in given else item.position
                if zoom is not None and zoom > item.limits.quality + ZOOM_TOLERANCE:
                    raise InvalidRequestError(
                        f"{item.filename} can zoom up to {item.limits.quality:.2f}×: past that the crop has "
                        "fewer pixels than the output"
                    )
                photo = self._library.photo(photo_id)
                found = self._found(photo, review.settings, detect=False)
                item = self._build(
                    photo,
                    review.settings,
                    self.settings(),
                    found,
                    zoom_override=zoom,
                    position=position,
                    previous=item,
                )
                approve = True if approve is None else approve
            if approve is not None:
                item = _approved(item, approve)
            return self._replace(review, item)

    def set_subject(self, review_id: str, photo_id: str, update: ReviewSubjectUpdate) -> ExportReview:
        """Choose a detected candidate, draw a box (normalized to the edited photo), or go back to the
        detected subject. It is saved to the photo's edit (like the crop tool's Set subject) and approves the
        photo. The crop is placed on the new subject again (a position dragged before is dropped)."""
        with self._lock:
            review = self.get(review_id)
            item = self._item(review, photo_id)
            if item.status == ReviewStatus.UNUSABLE:
                raise InvalidRequestError(f"{item.filename} can't be exported: {item.reasons[0].text}")
            photo = self._library.photo(photo_id)
            geometry = self._library.edit(photo_id).adjustments.geometry
            if "candidate" in update.model_fields_set:
                assert update.candidate is not None
                info = self._subjects.subject(photo, detect=False)
                if update.candidate not in {c.index for c in item.candidates}:
                    raise InvalidRequestError(
                        f"{item.filename} has no candidate {update.candidate} inside the photo's crop"
                    )
                self._subjects.set_manual(photo, info.candidates[update.candidate].box)
            elif update.box is not None:
                upright = crop_box_to_upright(update.box, geometry, photo.width, photo.height)
                if upright is None:
                    raise InvalidRequestError("the box is outside the photo")
                self._subjects.set_manual(photo, upright)
            else:
                self._subjects.set_manual(photo, None)
            photo = self._library.photo(photo_id)
            found = self._found(photo, review.settings, detect=True)
            fresh = self._build(
                photo,
                review.settings,
                self.settings(),
                found,
                zoom_override=item.zoom_override,
                previous=item,
            )
            return self._replace(review, _approved(fresh, True))

    def frames(self, review_id: str, photo_id: str) -> ReviewFrames:
        """The photo's crop at each zoom step from 1 to its quality limit (about 0.01× apart), for its current
        subject and position: what the review shows while the zoom slider is dragged."""
        review = self.get(review_id)
        item = self._item(review, photo_id)
        if item.status == ReviewStatus.UNUSABLE:
            raise InvalidRequestError(f"{item.filename} can't be exported: {item.reasons[0].text}")
        photo = self._library.photo(photo_id)
        found = self._found(photo, review.settings, detect=False)
        quality = item.limits.quality
        steps = max(1, min(MAX_FRAMES, math.ceil((quality - 1) / FRAME_STEP)))
        zooms = [1 + (quality - 1) * i / steps for i in range(steps + 1)]
        position = (item.position.x, item.position.y) if item.position else None
        geometries = self._exporter.zoom_frames(photo, review.settings, found, zooms, position=position)
        width, height = photo.edited_width or photo.width, photo.edited_height or photo.height
        return ReviewFrames(
            photo_id=photo_id,
            frames=[
                ZoomFrame(zoom=round(zoom, 4), crop=_normalized(g.crop, width, height))
                for zoom, g in zip(zooms, geometries, strict=True)
            ],
        )

    # ---- export

    def export(self, review_id: str, scope: ReviewExportScope) -> Job:
        """Export the approved photos (Ready + approved Check), or all of them (``all``: Check photos with the
        tool's framing). Unusable photos are never sent; photos already in an export job aren't sent again.
        Exported photos leave the review."""
        with self._lock:
            review = self.get(review_id)
            busy = self._exporting.get(review_id, set())
            chosen = [
                i
                for i in review.items
                if i.status != ReviewStatus.UNUSABLE
                and (scope == ReviewExportScope.ALL or i.exportable)
                and i.photo_id not in busy
            ]
            if not chosen:
                if busy:
                    raise InvalidRequestError("these photos are being exported already")
                raise InvalidRequestError("nothing to export: approve the photos to check first")
            ids = [i.photo_id for i in chosen]

            def finished(done: list[str]) -> None:
                with self._lock:
                    self._exporting.get(review_id, set()).difference_update(ids)
                    self._remove(review_id, done)

            job = self._exporter.export(
                ids,
                review.settings,
                review.destination,
                review.preset_id,
                zooms={i.photo_id: i.zoom for i in chosen},
                positions={i.photo_id: (i.position.x, i.position.y) for i in chosen if i.position},
                finished=finished,
            )
            self._exporting.setdefault(review_id, set()).update(ids)
            return job

    # ---- housekeeping

    def prune(self) -> int:
        """Delete reviews created more than ``KEEP_DAYS`` ago. Returns how many."""
        cutoff = self._clock() - timedelta(days=KEEP_DAYS)
        removed = 0
        with self._lock:
            for review_id in self._ids():
                path = self._path(review_id)
                try:
                    created = self._load(review_id).created_at
                except (NotFoundError, InvalidRequestError):
                    created = datetime.fromtimestamp(path.stat().st_mtime, UTC)
                if created < cutoff:
                    self._guard.assert_writable(path)
                    path.unlink(missing_ok=True)
                    removed += 1
        return removed

    # ---- internals

    def _found(self, photo: CatalogPhoto, settings: ExportSettings, *, detect: bool) -> Found | None:
        if not frames_subjects(settings):
            return None
        return self._exporter.subjects_of([photo], detect=detect)[photo.id]

    def _build(
        self,
        photo: CatalogPhoto,
        settings: ExportSettings,
        rules: ReviewSettings,
        found: Found | None,
        *,
        zoom_override: float | None = None,
        position: FramePosition | None = None,
        previous: ReviewItem | None = None,
    ) -> ReviewItem:
        """The photo framed by ``settings`` (with the review's zoom and position, if any), sorted by
        ``rules``. An approval in ``previous`` holds while the framing is the one approved."""
        unusable = None
        edit = self._library.edit(photo.id)
        if not photo.path.is_file():
            unusable = f"the original is no longer at {photo.path}"
        elif edit.style_error is not None:
            unusable = f"{edit.style_error}; fix the style or remove it from this photo"
        framing = self._exporter.frame(
            photo,
            settings,
            found,
            zoom=zoom_override,
            position=(position.x, position.y) if position is not None else None,
        )
        info = found[0] if found is not None else None
        candidates: list[ReviewCandidate] = []
        focus = None
        if info is not None and framing.source is not None:
            geometry = edit.adjustments.geometry
            candidates = found_candidates(
                info, geometry, photo.width, photo.height, framing.box, framing.kind
            )
            focus = focus_box(
                self._library.with_af_point(photo).af_point, geometry, photo.width, photo.height
            )
        why = reasons(framing, candidates, settings, rules, unusable=unusable)
        key = _framing_key(framing)
        approved_framing = previous.approved_framing if previous is not None else None
        approved = previous is not None and previous.approved and approved_framing == key
        if unusable is None and approved_framing is not None and approved_framing != key:
            why.append(
                ReviewReason(code=ReviewRule.CHANGED, text="the framing changed since you approved it")
            )
        status = ReviewStatus.UNUSABLE if unusable else ReviewStatus.CHECK if why else ReviewStatus.READY
        geometry_ = framing.geometry
        width, height = photo.edited_width or photo.width, photo.edited_height or photo.height
        warnings = geometry_warnings(geometry_)
        if framing.note and all(r.text != framing.note for r in why):
            warnings.append(framing.note)
        return ReviewItem(
            photo_id=photo.id,
            filename=photo.path.name,
            status=status,
            reasons=why,
            approved=approved and status != ReviewStatus.UNUSABLE,
            approved_framing=approved_framing,
            framing=key,
            subject=framing.source or SubjectSource.NONE,
            subject_kind=framing.kind,
            subject_score=framing.score,
            subject_box=framing.box,
            candidates=candidates,
            focus=focus,
            position=position,
            crop=_normalized(geometry_.crop, width, height),
            zoom=geometry_.zoom,
            auto_zoom=framing.auto_zoom,
            zoom_override=zoom_override,
            limits=ZoomLimits(fast=framing.zoom.fast, quality=framing.zoom.quality),
            decode=geometry_.decode,
            width=geometry_.width,
            height=geometry_.height,
            warnings=warnings,
            revision=hashlib.sha256(f"{key}|{self._library.image_version(photo)}".encode()).hexdigest()[:12],
        )

    def _refresh(self, review: ExportReview) -> ExportReview:
        rules = self.settings()
        items = []
        for item in review.items:
            try:
                photo = self._library.photo(item.photo_id)
            except NotFoundError:
                gone = ReviewReason(code=ReviewRule.UNUSABLE, text="the photo is no longer in the library")
                items.append(
                    item.model_copy(
                        update={"status": ReviewStatus.UNUSABLE, "reasons": [gone], "approved": False}
                    )
                )
                continue
            found = self._found(photo, review.settings, detect=False)
            items.append(
                self._build(
                    photo,
                    review.settings,
                    rules,
                    found,
                    zoom_override=item.zoom_override,
                    position=item.position,
                    previous=item,
                )
            )
        return review.model_copy(update={"items": items})

    def _replace(self, review: ExportReview, item: ReviewItem) -> ExportReview:
        items = [item if i.photo_id == item.photo_id else i for i in review.items]
        updated = review.model_copy(update={"items": items, "updated_at": self._clock()})
        self._save(updated)
        return updated

    def _remove(self, review_id: str, photo_ids: Sequence[str]) -> None:
        """Take exported photos out of the review; delete it when none are left."""
        if not photo_ids:
            return
        try:
            review = self._load(review_id)
        except (NotFoundError, InvalidRequestError):
            return  # discarded meanwhile
        done = set(photo_ids)
        items = [i for i in review.items if i.photo_id not in done]
        if not items:
            path = self._path(review_id)
            self._guard.assert_writable(path)
            path.unlink(missing_ok=True)
            return
        self._save(review.model_copy(update={"items": items, "updated_at": self._clock()}))

    def _item(self, review: ExportReview, photo_id: str) -> ReviewItem:
        for item in review.items:
            if item.photo_id == photo_id:
                return item
        raise NotFoundError(f"photo '{photo_id}' is not in review '{review.id}'")

    def _ids(self) -> list[str]:
        if not self._dir.is_dir():
            return []
        return sorted(p.stem for p in self._dir.glob("*.json") if _ID.match(p.stem))

    def _path(self, review_id: str) -> Path:
        if not _ID.match(review_id):
            raise NotFoundError(f"review '{review_id}' not found")
        return self._dir / f"{review_id}.json"

    def _load(self, review_id: str) -> ExportReview:
        path = self._path(review_id)
        if not path.is_file():
            raise NotFoundError(f"review '{review_id}' not found")
        try:
            return ExportReview.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError, ValueError) as exc:
            raise InvalidRequestError(f"review '{review_id}' can't be read: {exc}") from None

    def _save(self, review: ExportReview) -> None:
        data = json.loads(review.model_dump_json(exclude={"counts"}))
        text = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
        self._guard.write_atomic(self._path(review.id), text.encode("utf-8"))


def _normalized(box: Box, width: int, height: int) -> CropRect:
    return CropRect(
        left=box.left / width,
        top=box.top / height,
        right=(box.left + box.width) / width,
        bottom=(box.top + box.height) / height,
    )


def _framing_key(framing: Framing) -> str:
    """What the export shows: the crop and the output size."""
    g = framing.geometry
    text = f"{g.crop.left},{g.crop.top},{g.crop.width},{g.crop.height},{g.width},{g.height}"
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _approved(item: ReviewItem, on: bool) -> ReviewItem:
    """``item`` approved (for its current framing) or not; approving clears "changed since"."""
    reasons_ = [r for r in item.reasons if r.code != ReviewRule.CHANGED] if on else item.reasons
    status = item.status
    if status == ReviewStatus.CHECK and not reasons_:
        status = ReviewStatus.READY
    return item.model_copy(
        update={
            "approved": on,
            "approved_framing": item.framing if on else None,
            "reasons": reasons_,
            "status": status,
        }
    )


def _summary(review: ExportReview) -> str:
    counts = review.counts
    parts = [f"{counts.ready} ready", f"{counts.check} to check"]
    if counts.unusable:
        parts.append(f"{counts.unusable} can't be exported")
    return ", ".join(parts)
