"""Style operations across the library on synthetic photos (P4.7): apply jobs, even out, live link, styles
from photos, samples, the consistency report. Everything is written into tmp_path; originals are only read."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from helpers import write_jpeg
from photoedit.core.cache import ImageCache
from photoedit.core.catalog import Catalog
from photoedit.core.errors import InvalidRequestError, NotFoundError
from photoedit.core.jobs import JobManager
from photoedit.core.library import Library
from photoedit.core.styles import StyleLibrary
from photoedit.core.styling import Styling
from photoedit.models import Job, JobKind, JobStatus, Page, Photo
from photoedit.models.style import (
    StyleCreate,
    StyleFromPhoto,
    StyleUpdate,
    StyleUpdateFromPhoto,
)
from photoedit.safety import PathGuard

TIMEOUT = 30
# Three grays one stop of light apart in the scene, shot in manual with three shutter speeds.
SERIES = (
    ("dark.jpg", 70, Fraction(1, 500)),
    ("mid.jpg", 100, Fraction(1, 250)),
    ("bright.jpg", 140, Fraction(1, 125)),
)


@dataclass
class Env:
    library: Library
    styling: Styling
    styles: StyleLibrary
    jobs: JobManager
    photos: Path
    workspace: Path

    def wait_all(self) -> None:
        for job in self.jobs.list():
            if job.finished_at is None:
                self.jobs.wait(job.id, TIMEOUT)

    def run(self, job: Job) -> Job:
        done = self.jobs.wait(job.id, TIMEOUT)
        self.wait_all()  # the thumbnail job it starts
        return done

    def ids(self) -> dict[str, str]:
        page: Page[Photo] = self.library.list_photos(limit=50)
        return {p.filename: p.id for p in page.items}

    def style(self, name: str = "Warm", **fields: Any) -> str:
        data = {"name": name, "values": {"tone.contrast": -10}, **fields}
        return self.styles.create(StyleCreate.model_validate(data)).id

    def photo_style(self, pid: str) -> str | None:
        return self.library.photo(pid).style_id


@pytest.fixture
def env(tmp_path: Path) -> Iterator[Env]:
    workspace, photos = tmp_path / "workspace", tmp_path / "photos"
    for name, level, shutter in SERIES:
        write_jpeg(photos / name, (level, level, level), exposure=(4.0, shutter, 400))
    guard = PathGuard(writable_roots=[workspace], protected_roots=[photos])
    jobs = JobManager()
    catalog = Catalog(workspace / "catalog.sqlite", guard)
    cache = ImageCache(workspace / "cache", guard, identity="test")
    styles = StyleLibrary(workspace / "styles", guard, clock=lambda: datetime(2026, 10, 9, tzinfo=UTC))
    library = Library(catalog, cache, jobs, guard, styles=styles)
    styling = Styling(library, styles, jobs, guard, group_ids=lambda: "g1")
    env = Env(library, styling, styles, jobs, photos, workspace)
    env.run(library.import_folder(photos))
    yield env
    jobs.shutdown()


def _tweak(env: Env, pid: str, values: dict[str, Any]) -> None:
    """Save the photo's current parameters with ``values`` changed, as the UI does."""
    env.library.save_edit(pid, env.library.edit(pid).adjustments.with_values(values))


def _hashes(folder: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}


# ----------------------------------------------------------------- applying


def test_apply_job_writes_edits_catalog_and_thumbnails(env: Env) -> None:
    originals = _hashes(env.photos)
    sid = env.style()
    ids = env.ids()
    job = env.run(env.styling.apply(list(ids.values()), sid))
    assert (job.kind, job.status, job.title, job.style_id) == (
        JobKind.APPLY_STYLE,
        JobStatus.DONE,
        "Apply Warm to 3 photos",
        sid,
    )
    for pid in ids.values():
        assert env.photo_style(pid) == sid
        assert env.library.edit(pid).adjustments.tone.contrast == -10
        assert env.library.renderer.has_thumbnail(env.library.photo(pid), env.library.edit(pid))
    assert (
        env.library.list_photos(style_id=sid).total == 3
        and env.library.list_photos(style_id="none").total == 0
    )
    assert [s.photo_count for s in env.styling.summaries()] == [3]
    assert _hashes(env.photos) == originals  # golden rule 1


def test_removing_the_style_with_a_job(env: Env) -> None:
    sid = env.style()
    ids = list(env.ids().values())
    env.run(env.styling.apply(ids, sid))
    job = env.run(env.styling.apply(ids[:2], None))
    assert job.title == "Remove the style from 2 photos"
    assert [env.photo_style(pid) for pid in ids] == [None, None, sid]


def test_unknown_style_or_photo_fails_before_the_job(env: Env) -> None:
    with pytest.raises(NotFoundError):
        env.styling.apply(list(env.ids().values()), "nope")
    with pytest.raises(NotFoundError):
        env.styling.apply(["nope"], None)


def test_set_photo_style(env: Env) -> None:
    sid = env.style()
    pid = env.ids()["mid.jpg"]
    env.styling.set_photo_style(pid, sid)
    assert env.photo_style(pid) == sid and env.library.photo(pid).has_edits
    env.styling.set_photo_style(pid, None)
    assert env.photo_style(pid) is None and not env.library.photo(pid).has_edits


def test_even_out_by_middle_brings_photos_to_the_groups_median(env: Env) -> None:
    sid = env.style(values={}, rules=[{"type": "exposure", "max_change": 3}])
    ids = env.ids()
    job = env.run(env.styling.apply(list(ids.values()), sid, even_out=True))
    assert job.summary == "3 photos, evened out as a group of 3" and job.title.endswith("(evened out)")
    results = {}
    for name, pid in ids.items():
        edit = env.library.edit(pid)
        stats = env.library.rule_inputs(env.library.photo(pid)).stats
        assert stats is not None and edit.group is not None and edit.group.id == "g1"
        results[name] = stats.middle + edit.adjustments.tone.exposure
    assert max(results.values()) - min(results.values()) < 1e-3  # all at the group's median
    assert results["mid.jpg"] == pytest.approx(env.library.edit(ids["mid.jpg"]).group.middle, abs=1e-3)  # type: ignore[union-attr]


def test_even_out_by_camera_settings_uses_the_shutter_difference(env: Env) -> None:
    sid = env.style(values={}, rules=[{"type": "exposure", "metering": "camera_settings"}])
    ids = env.ids()
    env.run(env.styling.apply(list(ids.values()), sid, even_out=True))
    exposure = {name: env.library.edit(pid).adjustments.tone.exposure for name, pid in ids.items()}
    # Group median is the 1/250 shot: 1/500 was a stop darker (+1), 1/125 a stop brighter (-1).
    assert exposure == pytest.approx({"dark.jpg": 1.0, "mid.jpg": 0.0, "bright.jpg": -1.0}, abs=1e-3)
    group = env.library.edit(ids["mid.jpg"]).group
    assert group is not None and group.camera_ev == pytest.approx(math.log2(16 * 250) - 2, abs=1e-3)


def test_applying_without_even_out_clears_the_group(env: Env) -> None:
    sid = env.style(values={}, rules=[{"type": "exposure"}])
    ids = list(env.ids().values())
    env.run(env.styling.apply(ids, sid, even_out=True))
    env.run(env.styling.apply(ids, sid))
    assert all(env.library.edit(pid).group is None for pid in ids)


# ----------------------------------------------------------------- live link


def test_changing_the_look_rerenders_its_photos_but_a_rename_does_not(env: Env) -> None:
    sid = env.style()
    ids = list(env.ids().values())
    env.run(env.styling.apply(ids, sid))
    before = [env.library.photo(pid).edit_revision for pid in ids]
    env.styling.update(sid, StyleUpdate(expected_version=1, name="Renamed"))
    assert [env.library.photo(pid).edit_revision for pid in ids] == before
    view = env.styling.update(sid, StyleUpdate(expected_version=2, values={"tone.contrast": -30}))
    env.wait_all()
    after = [env.library.photo(pid).edit_revision for pid in ids]
    assert all(a != b for a, b in zip(after, before, strict=True)) and view.version == 3
    for pid in ids:
        assert env.library.renderer.has_thumbnail(env.library.photo(pid), env.library.edit(pid))


def test_revert_restyles(env: Env) -> None:
    sid = env.style()
    pid = env.ids()["mid.jpg"]
    env.styling.set_photo_style(pid, sid)
    env.styling.update(sid, StyleUpdate(expected_version=1, values={"tone.contrast": -30}))
    env.styling.revert(sid, 1, expected_version=2)
    assert env.library.edit(pid).adjustments.tone.contrast == -10


def test_delete_drops_photos_back_to_no_style_and_keeps_tweaks(env: Env) -> None:
    sid = env.style()
    ids = env.ids()
    env.run(env.styling.apply(list(ids.values()), sid))
    _tweak(env, ids["mid.jpg"], {"presence.vibrance": 25})
    assert env.styling.delete(sid) == 3
    env.wait_all()
    assert all(env.photo_style(pid) is None for pid in ids.values())
    kept = env.library.edit(ids["mid.jpg"]).adjustments
    assert kept.presence.vibrance == 25 and kept.tone.contrast == 0
    assert env.styling.summaries() == []
    with pytest.raises(NotFoundError):
        env.styling.delete(sid)


def test_test_photos_must_exist(env: Env) -> None:
    with pytest.raises(InvalidRequestError, match="unknown photo id"):
        env.styling.create(StyleCreate(name="X", test_photo_ids=["nope"]))
    sid = env.style()
    with pytest.raises(InvalidRequestError, match="unknown photo id"):
        env.styling.update(sid, StyleUpdate(expected_version=1, test_photo_ids=["nope"]))


# ----------------------------------------------------------------- from a photo


def _edit_mid(env: Env) -> str:
    pid = env.ids()["mid.jpg"]
    _tweak(
        env,
        pid,
        {
            "white_balance.temperature": 7000,
            "white_balance.tint": 5,
            "tone.exposure": 0.5,
            "tone.contrast": 20,
            "hsl.green.saturation": -40,
            "presence.vibrance": 15,
        },
    )
    return pid


def test_create_from_photo_matches_brightness_and_white_balance(env: Env) -> None:
    pid = _edit_mid(env)
    view = env.styling.create_from_photo(
        StyleFromPhoto(photo_id=pid, name="From mid", groups=["tone", "hsl"])
    )
    assert view.values == {"hsl.green.saturation": -40.0, "tone.contrast": 20.0}  # no presence, no exposure
    stats = env.library.rule_inputs(env.library.photo(pid)).stats
    assert stats is not None
    exposure, wb = view.rules
    assert exposure.type == "exposure" and exposure.target == pytest.approx(round(stats.middle + 0.5, 2))
    # JPEGs count as shot at D65 (6504 K): 7000 K is the mired shift that +350 K is at 5500 K.
    as_shot = env.library.as_shot(env.library.photo(pid))
    assert as_shot is not None
    assert wb.type == "white_balance" and wb.mode == "as_shot"
    assert wb.temperature_offset == pytest.approx(350, abs=2)
    assert wb.tint_offset == pytest.approx(5 - as_shot[1], abs=0.1)
    assert view.test_photo_ids == [pid] and view.change_note == "created from mid.jpg"
    # On another photo shot under the same light, the style gives the same white balance and brightness
    # (the bright one: the dark one is 1.56 EV away, past the rule's default 1.5 EV limit).
    other = env.ids()["bright.jpg"]
    env.styling.set_photo_style(other, view.id)
    edit = env.library.edit(other)
    assert edit.adjustments.white_balance.temperature == pytest.approx(7000, abs=3)
    assert edit.adjustments.white_balance.tint == pytest.approx(5, abs=0.1)
    dark = env.library.rule_inputs(env.library.photo(other)).stats
    assert dark is not None
    assert dark.middle + edit.adjustments.tone.exposure == pytest.approx(stats.middle + 0.5, abs=0.01)


def test_create_from_photo_with_fixed_or_no_exposure(env: Env) -> None:
    pid = _edit_mid(env)
    fixed = env.styling.create_from_photo(
        StyleFromPhoto(photo_id=pid, name="Fixed", exposure="value", white_balance="none")
    )
    assert fixed.values["tone.exposure"] == 0.5 and fixed.rules == []
    assert "presence.vibrance" in fixed.values  # all style groups by default
    plain = env.styling.create_from_photo(
        StyleFromPhoto(photo_id=pid, name="Plain", exposure="none", white_balance="none")
    )
    assert "tone.exposure" not in plain.values and plain.rules == []
    with pytest.raises(ValueError, match="geometry"):
        StyleFromPhoto(photo_id=pid, name="x", groups=["geometry"])


def test_update_from_photo_replaces_groups_and_absorbs_the_photos_tweaks(env: Env) -> None:
    sid = env.style(values={"tone.contrast": -10, "presence.saturation": -20})
    ids = env.ids()
    env.run(env.styling.apply(list(ids.values()), sid))
    pid = ids["mid.jpg"]
    _tweak(env, pid, {"tone.contrast": 30})
    view = env.styling.update_from_photo(
        sid, StyleUpdateFromPhoto(photo_id=pid, groups=["tone"], expected_version=1)
    )
    assert view.values == {"presence.saturation": -20.0, "tone.contrast": 30.0}
    assert view.change_note == "updated tone from mid.jpg"
    assert env.library.edit(pid).overridden == []  # its tweak is now the style's value
    assert env.library.edit(ids["dark.jpg"]).adjustments.tone.contrast == 30  # every photo follows


# ----------------------------------------------------------------- samples


def test_render_samples(env: Env) -> None:
    sid = env.style()
    ids = env.ids()
    job = env.run(env.styling.render_samples(sid, [ids["dark.jpg"], ids["bright.jpg"]]))
    assert job.status == JobStatus.DONE and job.summary == "2 samples rendered"
    view = env.styling.view(sid)
    assert [(s.photo_id, s.caption, s.stale) for s in view.samples] == [
        (ids["dark.jpg"], "dark", False),
        (ids["bright.jpg"], "bright", False),
    ]
    folder = env.workspace / "styles" / sid / "samples"
    assert sorted(p.name for p in folder.iterdir()) == [
        "01-after.jpg",
        "01-before.jpg",
        "02-after.jpg",
        "02-before.jpg",
    ]
    assert env.styling.sample_image(sid, "02", "after")[:2] == b"\xff\xd8"
    env.run(env.styling.render_samples(sid, [ids["mid.jpg"]]))
    assert sorted(p.name for p in folder.iterdir()) == ["01-after.jpg", "01-before.jpg"]
    with pytest.raises(NotFoundError):
        env.styling.sample_image(sid, "02", "after")
    env.styling.update(sid, StyleUpdate(expected_version=1, values={"tone.contrast": 5}))
    assert env.styling.view(sid).samples_stale


# ----------------------------------------------------------------- consistency report


def test_report_shows_the_spread_shrinking(env: Env) -> None:
    ids = env.ids()
    rules = [{"type": "exposure", "target": -0.5, "max_change": 3}]
    sid = env.style(values={}, rules=rules, test_photo_ids=list(ids.values()))
    report = env.styling.report(sid)
    assert report.style_id == sid and len(report.photos) == 3
    middle = next(s for s in report.spread if s.measure == "middle")
    assert middle.before_range > 1 and middle.after_range < 1e-3  # all moved to the same target
    assert all(abs(p.deviation) < 1e-3 for p in report.photos)
    assert all(p.rules and p.rules[0].type == "exposure" for p in report.photos)
    camera = {p.filename: p.camera_ev for p in report.photos}
    assert camera["dark.jpg"] - camera["mid.jpg"] == pytest.approx(1, abs=1e-3)  # type: ignore[operator]


def test_report_without_style_uses_current_edits_and_needs_photos(env: Env) -> None:
    ids = env.ids()
    report = env.styling.report(None, [ids["mid.jpg"]])
    assert report.style_id is None and report.photos[0].after == report.photos[0].before
    with pytest.raises(InvalidRequestError, match="name the photos"):
        env.styling.report(None)
    sid = env.style()
    with pytest.raises(InvalidRequestError, match="no photos to report on"):
        env.styling.report(sid)
