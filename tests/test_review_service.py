"""The review service (P6c.4-P6c.6) on synthetic photos with a fake detector. Everything is written into
tmp_path; the photos are only read."""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from helpers import write_jpeg
from photoedit.config import Settings, load_settings
from photoedit.core.cache import ImageCache
from photoedit.core.catalog import Catalog
from photoedit.core.errors import InvalidRequestError, NotFoundError
from photoedit.core.export import service as export_service
from photoedit.core.export.service import Exporter
from photoedit.core.jobs import JobManager
from photoedit.core.library import Library
from photoedit.core.review.service import Reviews
from photoedit.core.styles import StyleLibrary
from photoedit.core.styling import Styling
from photoedit.core.subject.service import Subjects
from photoedit.models import Job, JobStatus
from photoedit.models.adjustments import CropRect, GeometryChange
from photoedit.models.export import ExportSettings
from photoedit.models.review import (
    ExportReview,
    ReviewExportScope,
    ReviewItem,
    ReviewItemUpdate,
    ReviewRule,
    ReviewSettings,
    ReviewStatus,
    ReviewSubjectUpdate,
)
from photoedit.models.style import StyleCreate
from photoedit.models.subject import SubjectBox, SubjectCandidate, SubjectKind, SubjectSource
from photoedit.safety import PathGuard

TIMEOUT = 60
NOW = datetime(2026, 10, 13, 12, tzinfo=UTC)


def _box(cx: float, cy: float, w: float, h: float) -> SubjectBox:
    return SubjectBox(left=cx - w / 2, top=cy - h / 2, right=cx + w / 2, bottom=cy + h / 2)


def _found(kind: SubjectKind, score: float, box: SubjectBox) -> SubjectCandidate:
    return SubjectCandidate(box=box, kind=kind, score=score, label=kind.value)


# Each photo's color tells the fake detector what it "finds" there.
PHOTOS: dict[str, tuple[tuple[int, int, int], list[SubjectCandidate]]] = {
    "a_sure.jpg": ((200, 40, 40), [_found(SubjectKind.CAR, 0.9, _box(0.4, 0.5, 0.3, 0.5))]),
    "b_uncertain.jpg": ((40, 200, 40), [_found(SubjectKind.CAR, 0.42, _box(0.5, 0.5, 0.3, 0.5))]),
    "c_two_cats.jpg": (
        (200, 200, 40),
        [
            _found(SubjectKind.ANIMAL, 0.9, _box(0.2, 0.5, 0.2, 0.4)),
            _found(SubjectKind.ANIMAL, 0.8, _box(0.8, 0.5, 0.2, 0.4)),
        ],
    ),
    "d_sunset.jpg": ((200, 40, 200), []),
    # Blue with a small red "car" (14 × 14 px of 320 × 200): it wants 5.6×, more than the 40 px output allows.
    "e_small.jpg": ((40, 40, 200), [_found(SubjectKind.CAR, 0.9, _box(0.5, 0.5, 0.045, 0.07))]),
}
COLORS = {name: color for name, (color, _) in PHOTOS.items()}


def _finder(image: np.ndarray[Any, Any]) -> list[SubjectCandidate]:
    mean = image.reshape(-1, 3).mean(axis=0)
    name = min(COLORS, key=lambda n: float(np.abs(mean - np.array(COLORS[n])).sum()))
    return list(PHOTOS[name][1])


@dataclass
class Env:
    settings: Settings
    library: Library
    jobs: JobManager
    guard: PathGuard
    styles: StyleLibrary
    styling: Styling
    subjects: Subjects
    exporter: Exporter
    reviews: Reviews
    photos: Path
    out: Path
    clock: list[datetime]

    def run(self, job: Job) -> Job:
        done = self.jobs.wait(job.id, TIMEOUT)
        for other in self.jobs.list():  # and the jobs it started (thumbnails)
            if other.finished_at is None:
                self.jobs.wait(other.id, TIMEOUT)
        return done

    def ids(self) -> dict[str, str]:
        return {p.filename: p.id for p in self.library.list_photos(limit=50).items}

    def new_reviews(self) -> Reviews:
        return Reviews(
            self.library,
            self.exporter,
            self.subjects,
            self.styling,
            self.jobs,
            self.guard,
            self.settings.workspace_dir,
            clock=lambda: self.clock[0],
        )

    def prepare(self, settings: ExportSettings | None = None, **kwargs: Any) -> ExportReview:
        job = self.run(
            self.reviews.prepare(list(self.ids().values()), settings or IG, str(self.out), **kwargs)
        )
        assert job.status == JobStatus.DONE, job
        assert job.review_id is not None
        return self.reviews.get(job.review_id)


IG = ExportSettings.model_validate(
    {
        "size": {"mode": "long_edge", "long_edge": 40},
        "aspect": {"ratio": "1:1", "anchor": "subject", "zoom": "auto"},
        "naming": {"template": "{original}"},
    }
)


@pytest.fixture
def env(tmp_path: Path) -> Iterator[Env]:
    photos = tmp_path / "photos"
    for name, (color, _) in PHOTOS.items():
        write_jpeg(photos / name, color)
    small = Image.new("RGB", (320, 200), COLORS["e_small.jpg"])
    small.paste((220, 30, 30), (153, 93, 167, 107))
    small.save(photos / "e_small.jpg", quality=95)
    settings = load_settings(tmp_path / "missing.toml", project_root=tmp_path, export_workers=1)
    guard = PathGuard(writable_roots=settings.writable_dirs, protected_roots=[photos])
    jobs = JobManager()
    catalog = Catalog(settings.workspace_dir / "catalog.sqlite", guard)
    cache = ImageCache(settings.cache_dir, guard, identity="test")
    styles = StyleLibrary(settings.styles_dir, guard)
    library = Library(catalog, cache, jobs, guard, styles=styles)
    styling = Styling(library, styles, jobs, guard)
    subjects = Subjects(library, settings.cache_dir, objects=(_finder, "fake"), faces=(lambda _: [], "none"))
    exporter = Exporter(library, jobs, guard, settings, subjects=subjects)
    clock = [NOW]
    reviews = Reviews(
        library, exporter, subjects, styling, jobs, guard, settings.workspace_dir, clock=lambda: clock[0]
    )
    env = Env(
        settings,
        library,
        jobs,
        guard,
        styles,
        styling,
        subjects,
        exporter,
        reviews,
        photos,
        tmp_path / "out",
        clock,
    )
    env.run(library.import_folder(photos))
    yield env
    jobs.shutdown()


def _item(review: ExportReview, filename: str) -> ReviewItem:
    return next(i for i in review.items if i.filename == filename)


def _codes(review: ExportReview) -> dict[str, list[ReviewRule]]:
    return {i.filename: [r.code for r in i.reasons] for i in review.items}


def _hashes(folder: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}


def test_prepare_sorts_ready_and_check(env: Env) -> None:
    before = _hashes(env.photos)
    review = env.prepare(preset_id="instagram-square")
    assert _codes(review) == {
        "a_sure.jpg": [],
        "b_uncertain.jpg": [ReviewRule.UNCERTAIN],
        "c_two_cats.jpg": [ReviewRule.AMBIGUOUS],
        "d_sunset.jpg": [ReviewRule.NO_SUBJECT],
        "e_small.jpg": [ReviewRule.ZOOM_LIMIT],
    }
    assert review.counts.model_dump() == {"total": 5, "ready": 1, "check": 4, "approved": 0, "unusable": 0}
    sure = _item(review, "a_sure.jpg")
    assert (sure.status, sure.subject, sure.subject_kind, sure.zoom) == ("ready", "detected", "car", 1.0)
    assert [c.chosen for c in sure.candidates] == [True]
    # The small car is zoomed as far as the quality limit goes: 200 px / 40 px = 5×.
    small = _item(review, "e_small.jpg")
    assert small.zoom == pytest.approx(5.0)
    assert (small.limits.fast, small.limits.quality) == (pytest.approx(5.0), pytest.approx(5.0))
    assert small.crop.right - small.crop.left == pytest.approx(40 / 320)
    cats = _item(review, "c_two_cats.jpg")
    assert [(c.index, c.kind, c.chosen) for c in cats.candidates] == [
        (0, "animal", True),
        (1, "animal", False),
    ]
    # Stored in the workspace; the photos are untouched.
    assert (env.settings.workspace_dir / "reviews" / f"{review.id}.json").is_file()
    assert _hashes(env.photos) == before
    assert [s.id for s in env.reviews.summaries()] == [review.id]


def test_fixes_approve(env: Env) -> None:
    review = env.prepare()
    ids = env.ids()
    # The other cat: one click makes it the subject (saved to the photo's edit) and approves the photo.
    review = env.reviews.set_subject(review.id, ids["c_two_cats.jpg"], ReviewSubjectUpdate(candidate=1))
    cats = _item(review, "c_two_cats.jpg")
    assert (cats.subject, cats.approved, cats.status, cats.reasons) == ("manual", True, "ready", [])
    assert cats.subject_box is not None and cats.subject_box.left > 0.5
    assert env.library.edits.subject(ids["c_two_cats.jpg"]) == PHOTOS["c_two_cats.jpg"][1][1].box
    # A box drawn on the sunset.
    box = SubjectBox(left=0.1, top=0.1, right=0.3, bottom=0.4)
    review = env.reviews.set_subject(review.id, ids["d_sunset.jpg"], ReviewSubjectUpdate(box=box))
    sunset = _item(review, "d_sunset.jpg")
    assert (sunset.subject, sunset.approved, sunset.status) == ("manual", True, "ready")
    # A zoom approves; it is capped at the quality limit.
    with pytest.raises(InvalidRequestError, match=r"can zoom up to 5.00×"):
        env.reviews.update_item(review.id, ids["e_small.jpg"], ReviewItemUpdate(zoom=6))
    review = env.reviews.update_item(review.id, ids["e_small.jpg"], ReviewItemUpdate(zoom=2))
    small = _item(review, "e_small.jpg")
    assert (small.zoom, small.zoom_override, small.approved, small.status) == (2.0, 2.0, True, "check")
    # Back to the automatic zoom: still a decision.
    review = env.reviews.update_item(
        review.id, ids["e_small.jpg"], ReviewItemUpdate.model_validate({"zoom": None})
    )
    assert (_item(review, "e_small.jpg").zoom_override, _item(review, "e_small.jpg").zoom) == (
        None,
        pytest.approx(5),
    )
    # Approve as it is, and take it back.
    review = env.reviews.update_item(review.id, ids["b_uncertain.jpg"], ReviewItemUpdate(approved=True))
    assert _item(review, "b_uncertain.jpg").approved
    review = env.reviews.update_item(review.id, ids["b_uncertain.jpg"], ReviewItemUpdate(approved=False))
    assert not _item(review, "b_uncertain.jpg").approved
    assert review.counts.check == 1  # b only; e is approved, c and d are fixed
    # Use detected again: the sunset goes back to no subject, still approved (a decision).
    review = env.reviews.set_subject(
        review.id, ids["d_sunset.jpg"], ReviewSubjectUpdate.model_validate({"box": None})
    )
    sunset = _item(review, "d_sunset.jpg")
    assert (sunset.subject, sunset.approved, sunset.status) == ("none", True, "check")


def test_bad_decisions_are_rejected(env: Env) -> None:
    review = env.prepare()
    ids = env.ids()
    with pytest.raises(InvalidRequestError, match="no candidate 5"):
        env.reviews.set_subject(review.id, ids["c_two_cats.jpg"], ReviewSubjectUpdate(candidate=5))
    with pytest.raises(NotFoundError, match="not in review"):
        env.reviews.update_item(review.id, "nope", ReviewItemUpdate(approved=True))
    with pytest.raises(NotFoundError, match="not found"):
        env.reviews.get("../../etc")
    with pytest.raises(NotFoundError, match="not found"):
        env.reviews.get("abcdefabcdef")


def test_refresh_drops_an_approval_whose_framing_changed(env: Env) -> None:
    review = env.prepare()
    pid = env.ids()["b_uncertain.jpg"]
    env.reviews.update_item(review.id, pid, ReviewItemUpdate(approved=True))
    # A color change elsewhere keeps the approval; a new crop changes the framing.
    env.library.save_edit(pid, env.library.edit(pid).adjustments.with_values({"tone.contrast": 20}))
    assert _item(env.reviews.get(review.id), "b_uncertain.jpg").approved
    env.library.set_geometry(pid, GeometryChange(crop=CropRect(left=0.3, right=1)))
    item = _item(env.reviews.get(review.id), "b_uncertain.jpg")
    assert not item.approved
    assert [r.code for r in item.reasons] == [ReviewRule.UNCERTAIN, ReviewRule.CHANGED]
    assert item.reasons[-1].text == "the framing changed since you approved it"
    # Approving again clears it.
    review = env.reviews.update_item(review.id, pid, ReviewItemUpdate(approved=True))
    assert [r.code for r in _item(review, "b_uncertain.jpg").reasons] == [ReviewRule.UNCERTAIN]


def test_decisions_survive_a_restart(env: Env) -> None:
    review = env.prepare()
    ids = env.ids()
    env.reviews.update_item(review.id, ids["e_small.jpg"], ReviewItemUpdate(zoom=3))
    env.reviews.update_item(review.id, ids["d_sunset.jpg"], ReviewItemUpdate(approved=True))
    again = env.new_reviews().get(review.id)
    assert _item(again, "e_small.jpg").zoom_override == 3
    assert _item(again, "d_sunset.jpg").approved


def test_settings_resort_open_reviews(env: Env) -> None:
    review = env.prepare()
    assert env.reviews.settings() == ReviewSettings()
    env.reviews.set_settings(ReviewSettings(min_score=0.4, ambiguous=False))
    assert env.reviews.summaries()[0].counts.check == 2  # the sunset and the small car
    assert _item(env.reviews.get(review.id), "b_uncertain.jpg").status == ReviewStatus.READY
    assert env.new_reviews().settings().min_score == 0.4
    (env.settings.workspace_dir / "review-settings.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(InvalidRequestError, match="can't be read"):
        env.reviews.settings()


def test_prune_and_discard(env: Env) -> None:
    old = env.prepare()
    env.clock[0] = NOW + timedelta(days=20)
    newer = env.prepare()
    env.clock[0] = NOW + timedelta(days=31)
    assert env.new_reviews().summaries() == env.reviews.summaries()
    assert [s.id for s in env.reviews.summaries()] == [newer.id]
    env.reviews.discard(newer.id)
    assert env.reviews.summaries() == []
    with pytest.raises(NotFoundError):
        env.reviews.get(old.id)


def test_unusable_photos(env: Env) -> None:
    review = env.prepare()
    (env.photos / "a_sure.jpg").unlink()  # the test's own synthetic file
    sure = _item(env.reviews.get(review.id), "a_sure.jpg")
    assert sure.status == ReviewStatus.UNUSABLE
    assert sure.reasons[0].text.startswith("the original is no longer at")
    with pytest.raises(InvalidRequestError, match="can't be exported"):
        env.reviews.update_item(review.id, sure.photo_id, ReviewItemUpdate(approved=True))
    job = env.run(env.reviews.export(review.id, ReviewExportScope.ALL))
    assert job.status == JobStatus.DONE
    assert "a_sure.jpg" not in {i.filename for i in job.items}
    assert [i.filename for i in env.reviews.get(review.id).items] == ["a_sure.jpg"]


def test_prepare_validates_first(env: Env) -> None:
    ids = list(env.ids().values())
    with pytest.raises(InvalidRequestError, match="inside the photo folder"):
        env.reviews.prepare(ids, IG, str(env.photos / "out"))
    with pytest.raises(NotFoundError):
        env.reviews.prepare(["nope"], IG, str(env.out))
    with pytest.raises(NotFoundError):
        env.reviews.prepare(ids, IG, str(env.out), style_id="missing")
    with pytest.raises(InvalidRequestError, match="even out needs a style"):
        env.reviews.prepare(ids, IG, str(env.out), even_out=True)
    assert env.reviews.summaries() == []


def test_prepare_with_a_style_applies_it_first(env: Env) -> None:
    style = env.styles.create(StyleCreate.model_validate({"name": "Warm", "values": {"tone.contrast": -10}}))
    review = env.prepare(style_id=style.id)
    assert review.style_id == style.id
    assert {env.library.photo(i.photo_id).style_id for i in review.items} == {style.id}


def test_without_subject_framing_everything_is_ready(env: Env) -> None:
    centered = ExportSettings.model_validate(
        {"size": {"mode": "long_edge", "long_edge": 40}, "aspect": {"ratio": "1:1"}}
    )
    review = env.prepare(centered)
    assert review.counts.ready == 5
    assert {i.subject for i in review.items} == {SubjectSource.NONE}


# ---- framing previews (P6c.5) and export (P6c.6)


def _pixels(data: bytes | Path, size: tuple[int, int]) -> np.ndarray[Any, Any]:
    image = Image.open(data if isinstance(data, Path) else __import__("io").BytesIO(data))
    return np.asarray(image.convert("RGB").resize(size, Image.Resampling.BOX), dtype=np.float32)


def test_framing_preview_matches_the_exported_file(env: Env) -> None:
    review = env.prepare()
    ids = env.ids()
    env.reviews.update_item(review.id, ids["e_small.jpg"], ReviewItemUpdate(zoom=2.5))
    review = env.reviews.get(review.id)
    preview = env.reviews.preview(review.id, ids["e_small.jpg"])
    job = env.run(env.reviews.export(review.id, ReviewExportScope.APPROVED))
    assert job.status == JobStatus.DONE, job
    exported = env.out / "e_small.jpg"
    # 2.5×: an 80 px crop with the 14 × 14 px car in its middle (a 200 px crop would show it 2.5× smaller).
    file, shown = _pixels(exported, (40, 40)), _pixels(preview, (40, 40))
    assert np.abs(file - shown).mean() < 6
    red = file[..., 0] > 128
    assert 0.02 < red.mean() < 0.045  # 14·14 / 80² = 3.1 %


def test_export_approved_then_all(env: Env) -> None:
    review = env.prepare()
    ids = env.ids()
    env.reviews.update_item(review.id, ids["b_uncertain.jpg"], ReviewItemUpdate(approved=True))
    job = env.run(env.reviews.export(review.id, ReviewExportScope.APPROVED))
    assert job.status == JobStatus.DONE, job
    assert sorted(p.name for p in env.out.iterdir()) == ["a_sure.jpg", "b_uncertain.jpg"]
    left = env.reviews.get(review.id)
    assert sorted(i.filename for i in left.items) == ["c_two_cats.jpg", "d_sunset.jpg", "e_small.jpg"]
    with pytest.raises(InvalidRequestError, match="nothing to export"):
        env.reviews.export(review.id, ReviewExportScope.APPROVED)
    job = env.run(env.reviews.export(review.id, ReviewExportScope.ALL))
    assert job.status == JobStatus.DONE, job
    assert len(list(env.out.iterdir())) == 5
    with pytest.raises(NotFoundError):
        env.reviews.get(review.id)  # empty: deleted


def test_nothing_is_exported_twice(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    review = env.prepare()
    gate, started = threading.Event(), threading.Event()
    real: Callable[..., Any] = export_service.render_export

    def slow(task: Any) -> Any:
        started.set()
        assert gate.wait(TIMEOUT)
        return real(task)

    monkeypatch.setattr(export_service, "render_export", slow)
    first = env.reviews.export(review.id, ReviewExportScope.APPROVED)
    assert started.wait(TIMEOUT)
    with pytest.raises(InvalidRequestError, match="being exported already"):
        env.reviews.export(review.id, ReviewExportScope.APPROVED)
    # The others can still go.
    second = env.reviews.export(review.id, ReviewExportScope.ALL)
    assert {i.filename for i in second.items} == {
        "b_uncertain.jpg",
        "c_two_cats.jpg",
        "d_sunset.jpg",
        "e_small.jpg",
    }
    gate.set()
    assert env.run(first).status == JobStatus.DONE
    assert env.run(second).status == JobStatus.DONE
    assert len(list(env.out.iterdir())) == 5


# ---- moving the frame and live zoom (P6c.17, P6c.19)


def test_a_dragged_position_moves_the_crop_and_approves(env: Env) -> None:
    from photoedit.models.review import FramePosition

    review = env.prepare()
    pid = env.ids()["e_small.jpg"]
    review = env.reviews.update_item(
        review.id, pid, ReviewItemUpdate(zoom=2, position=FramePosition(x=0.2, y=0.3))
    )
    item = _item(review, "e_small.jpg")
    assert item.approved and item.position == FramePosition(x=0.2, y=0.3)
    # A 100 px square (200 / 2) centered on (64, 60) of the 320 × 200 photo.
    assert (item.crop.left, item.crop.top) == (pytest.approx(14 / 320), pytest.approx(10 / 200))
    assert item.crop.right - item.crop.left == pytest.approx(100 / 320)
    # The zoom changes around the position; too far toward an edge, the crop stops there.
    review = env.reviews.update_item(review.id, pid, ReviewItemUpdate(zoom=1))
    assert _item(review, "e_small.jpg").crop.left == 0.0
    # Survives a refresh, and back to the rules with null.
    assert _item(env.reviews.get(review.id), "e_small.jpg").position == FramePosition(x=0.2, y=0.3)
    review = env.reviews.update_item(review.id, pid, ReviewItemUpdate.model_validate({"position": None}))
    assert _item(review, "e_small.jpg").position is None


def test_choosing_a_subject_drops_a_dragged_position(env: Env) -> None:
    from photoedit.models.review import FramePosition

    review = env.prepare()
    pid = env.ids()["c_two_cats.jpg"]
    env.reviews.update_item(review.id, pid, ReviewItemUpdate(position=FramePosition(x=0.5, y=0.5)))
    review = env.reviews.set_subject(review.id, pid, ReviewSubjectUpdate(candidate=1))
    assert _item(review, "c_two_cats.jpg").position is None


def test_the_export_uses_the_dragged_position(env: Env) -> None:
    from photoedit.models.review import FramePosition

    review = env.prepare()
    pid = env.ids()["e_small.jpg"]
    # Zoom 2 on the top-left corner: blue only, the red car (in the middle) is outside.
    env.reviews.update_item(review.id, pid, ReviewItemUpdate(zoom=2, position=FramePosition(x=0, y=0)))
    job = env.run(env.reviews.export(review.id, ReviewExportScope.APPROVED))
    assert job.status == JobStatus.DONE, job
    with Image.open(env.out / "e_small.jpg") as exported:
        pixels = np.asarray(exported.convert("RGB"), dtype=np.float32)
    assert pixels[..., 2].mean() > 150 and pixels[..., 0].mean() < 80


def test_zoom_frames_follow_the_slider(env: Env) -> None:
    review = env.prepare()
    pid = env.ids()["e_small.jpg"]
    frames = env.reviews.frames(review.id, pid).frames
    # 1× to the quality limit (5×), about 0.01× apart, and each is what the export would use at that zoom.
    assert (frames[0].zoom, frames[-1].zoom) == (1.0, 5.0)
    assert len(frames) == 401
    widths = [f.crop.right - f.crop.left for f in frames]
    assert widths == sorted(widths, reverse=True)
    at_two = next(f for f in frames if f.zoom == 2.0)
    review = env.reviews.update_item(review.id, pid, ReviewItemUpdate(zoom=2))
    assert _item(review, "e_small.jpg").crop == at_two.crop
