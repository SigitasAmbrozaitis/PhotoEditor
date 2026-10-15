"""Change events (P7.8): the bus, bounded subscriptions, origins, and one event per write in every store."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from helpers import fill_folder
from photoedit.config import load_settings
from photoedit.core.events import EventBus, current_origin, origin
from photoedit.models import PhotoSort
from photoedit.models.events import ChangeEvent, EventKind, Origin
from photoedit.models.export import PresetCreate
from photoedit.models.review import ReviewSettings
from photoedit.models.style import StyleCreate
from photoedit.models.subject import SubjectBox
from photoedit.services import Services

# ----------------------------------------------------------------- the bus


def test_events_reach_every_subscriber_in_order_with_the_current_origin() -> None:
    bus = EventBus()
    first, second = bus.subscribe(), bus.subscribe()
    bus.publish(EventKind.STYLE, ["warm"])
    with origin(Origin.AI):
        assert current_origin() is Origin.AI
        bus.publish(EventKind.PHOTO_EDIT, ["p1", "p2"], summary="two photos")
    assert current_origin() is Origin.UI
    bus.publish(EventKind.JOB, ["j0001"], source=Origin.CLI)
    events = first.drain()
    assert [(e.seq, e.kind, e.ids, e.origin) for e in events] == [
        (1, EventKind.STYLE, ["warm"], Origin.UI),
        (2, EventKind.PHOTO_EDIT, ["p1", "p2"], Origin.AI),
        (3, EventKind.JOB, ["j0001"], Origin.CLI),
    ]
    assert events[1].summary == "two photos"
    assert second.drain() == events
    assert first.drain() == []
    second.close()
    bus.publish(EventKind.PRESET)
    assert len(first.drain()) == 1 and second.drain() == []


def test_a_listener_that_falls_behind_loses_old_events_and_gets_a_resync() -> None:
    bus = EventBus()
    slow = bus.subscribe(limit=3)
    for i in range(10):
        bus.publish(EventKind.PHOTO_EDIT, [f"p{i}"])  # never blocks, although nobody drains
    events = slow.drain()
    assert events[0].kind is EventKind.RESYNC
    assert [e.ids for e in events[1:]] == [["p7"], ["p8"], ["p9"]]
    bus.publish(EventKind.STYLE)
    assert [e.kind for e in slow.drain()] == [EventKind.STYLE]  # caught up: no second resync


def test_notify_runs_after_each_event_and_wait_wakes_up() -> None:
    bus = EventBus()
    calls: list[int] = []
    bus.subscribe(notify=lambda: calls.append(1))
    waiting = bus.subscribe()
    assert waiting.wait(0.01) == []
    threading.Timer(0.05, lambda: bus.publish(EventKind.LIBRARY)).start()
    started = time.monotonic()
    events = waiting.wait(5)
    assert [e.kind for e in events] == [EventKind.LIBRARY] and time.monotonic() - started < 4
    assert calls == [1]


# ----------------------------------------------------------------- every write publishes


@pytest.fixture
def services(tmp_path: Path) -> Iterator[Services]:
    photos = tmp_path / "photos"
    fill_folder(photos)
    settings = load_settings(
        tmp_path / "missing.toml", project_root=tmp_path / "project", sample_photos_dir=photos
    )
    services = Services(settings)
    services.jobs.wait(services.library.import_folder(photos).id, timeout=30)
    for job in services.jobs.list():  # the thumbnails job the import started
        services.jobs.wait(job.id, timeout=30)
    yield services
    services.close()


def _changes(events: list[ChangeEvent]) -> list[tuple[EventKind, list[str]]]:
    return [(e.kind, e.ids) for e in events if e.kind is not EventKind.JOB]


def test_each_write_publishes_once_with_its_ids(services: Services) -> None:
    listener = services.events.subscribe()
    pid = services.library.list_photos(sort=PhotoSort.NAME).items[0].id

    services.library.update_edit(pid, {"tone": {"exposure": 0.3}})
    assert _changes(listener.drain()) == [(EventKind.PHOTO_EDIT, [pid])]
    services.library.set_note(pid, "looks fine")
    services.library.reset_edit(pid)
    services.subjects.set_manual(
        services.library.photo(pid), SubjectBox(left=0.1, top=0.1, right=0.5, bottom=0.5)
    )
    assert _changes(listener.drain()) == [(EventKind.PHOTO_EDIT, [pid])] * 3

    style = services.styling.create(StyleCreate(name="Warm", values={"tone.exposure": 0.2}))
    assert _changes(listener.drain()) == [(EventKind.STYLE, [style.id])]
    services.styling.delete(style.id)
    assert (EventKind.STYLE, [style.id]) in _changes(listener.drain())

    preset = services.presets.create(PresetCreate(name="Mine"))
    services.presets.delete(preset.id)
    assert _changes(listener.drain()) == [(EventKind.PRESET, [preset.id])] * 2

    services.reviews.set_settings(ReviewSettings())
    assert _changes(listener.drain()) == [(EventKind.REVIEW, [])]

    folder = services.library.info().folder
    assert folder is not None
    services.library.open_folder(Path(folder))
    assert _changes(listener.drain()) == [(EventKind.LIBRARY, [folder])]

    # Reading writes nothing, so it publishes nothing.
    services.library.photo_detail(pid)
    services.library.preview(pid, 256)
    services.reviews.summaries()
    assert listener.drain() == []


def test_jobs_publish_their_progress_and_carry_their_starters_origin(services: Services) -> None:
    ids = [p.id for p in services.library.list_photos().items]
    style = services.styling.create(StyleCreate(name="Cool", values={"tone.exposure": -0.2}))
    listener = services.events.subscribe()
    with origin(Origin.AI):
        job = services.styling.apply(ids, style.id)
    services.jobs.wait(job.id, timeout=30)
    events = listener.drain()
    job_events = [e for e in events if e.kind is EventKind.JOB and e.ids == [job.id]]
    assert len(job_events) >= 2 and all(e.origin is Origin.AI for e in job_events)
    assert job_events[-1].summary is not None and "done" in job_events[-1].summary.lower()
    # The edits the job wrote in its own threads are the AI's too.
    edits = [e for e in events if e.kind is EventKind.PHOTO_EDIT]
    assert sorted(i for e in edits for i in e.ids) == sorted(ids)
    assert all(e.origin is Origin.AI for e in edits)
