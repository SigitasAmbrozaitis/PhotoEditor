"""GET /api/events (P7.15): changes arrive as server-sent events, in order, with their origin."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import anyio
import httpx2
import pytest
from mcp import Client

from helpers import fill_folder, serve
from photoedit.api import create_app
from photoedit.config import load_settings
from photoedit.models.events import ChangeEvent, EventKind, Origin
from photoedit.services import Services


@pytest.fixture
def server(tmp_path: Path) -> Iterator[tuple[str, Services]]:
    photos = tmp_path / "photos"
    fill_folder(photos)
    settings = load_settings(tmp_path / "missing.toml", project_root=tmp_path / "project")
    services = Services(settings)
    services.jobs.wait(services.library.import_folder(photos).id, timeout=30)
    for job in services.jobs.list():
        services.jobs.wait(job.id, timeout=30)
    with serve(create_app(settings, services=services)) as url:
        yield url, services


def _changes(url: str, wanted: int, act: Any) -> list[ChangeEvent]:
    """Open the stream, run ``act`` once it is open, and collect ``wanted`` non-job change events."""
    found: list[ChangeEvent] = []
    with httpx2.stream("GET", f"{url}/api/events", timeout=15) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        acting = threading.Timer(0.3, act)
        acting.start()
        event_name = None
        for line in response.iter_lines():
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and event_name == "change":
                event = ChangeEvent.model_validate(json.loads(line.split(":", 1)[1]))
                if event.kind is not EventKind.JOB:
                    found.append(event)
                if len(found) == wanted:
                    break
    acting.join(10)  # let it finish (e.g. close its MCP session) before the server stops
    return found


def test_changes_from_the_api_and_from_claude_arrive_in_order(server: tuple[str, Services]) -> None:
    url, services = server
    pid = services.library.list_photos().items[0].id

    def act() -> None:
        httpx2.put(f"{url}/api/photos/{pid}/style", json={"style_id": None}, timeout=10)  # the UI's way

        async def as_claude() -> None:
            async with Client(f"{url}/mcp") as client:
                await client.call_tool("set_note", {"photo": pid, "text": "checked"})

        anyio.run(as_claude)

    events = _changes(url, 2, act)
    assert [(e.kind, e.ids, e.origin) for e in events] == [
        (EventKind.PHOTO_EDIT, [pid], Origin.UI),
        (EventKind.PHOTO_EDIT, [pid], Origin.AI),
    ]
    assert events[0].seq < events[1].seq


def test_a_closed_stream_stops_listening(server: tuple[str, Services]) -> None:
    url, services = server
    before = len(services.events._subscriptions)
    _changes(url, 1, lambda: services.events.publish(EventKind.STYLE, ["warm"]))
    # The server notices the closed connection and drops its subscription.
    deadline = time.monotonic() + 5
    while len(services.events._subscriptions) != before and time.monotonic() < deadline:
        time.sleep(0.05)
    assert len(services.events._subscriptions) == before
