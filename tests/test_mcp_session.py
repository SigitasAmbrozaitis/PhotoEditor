"""Cross-cutting MCP checks (P7.18): a whole session as Claude would run it, through the SDK client.

Import a folder of synthetic photos → look → change → apply a style → plan → export. The originals stay
byte-identical, files appear only in the chosen destination, previews are deterministic, every change is
published as the AI's, and each tool's declared output schema is a valid JSON schema that its results meet.
"""

from __future__ import annotations

import base64
import hashlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import anyio
import jsonschema
import pytest
from mcp import Client
from mcp_types import CallToolResult, ImageContent

from helpers import fill_folder
from photoedit.config import load_settings
from photoedit.mcp.server import build_server
from photoedit.models.events import EventKind, Origin
from photoedit.services import Services

TIMEOUT = 30


def _tree(folder: Path) -> dict[str, str]:
    """Every file under ``folder`` with its SHA-256."""
    return {
        str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


@pytest.fixture
def services(tmp_path: Path) -> Iterator[Services]:
    settings = load_settings(tmp_path / "missing.toml", project_root=tmp_path / "project", export_workers=1)
    services = Services(settings)
    yield services
    services.close()


def test_a_whole_session_writes_only_where_it_should(services: Services, tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    fill_folder(photos)
    originals = _tree(photos)
    destination = tmp_path / "exports"
    listener = services.events.subscribe(limit=10_000)
    schemas: dict[str, dict[str, Any]] = {}
    results: list[tuple[str, Any]] = []

    async def session() -> None:
        async with Client(build_server(lambda: services)) as client:
            for tool in (await client.list_tools()).tools:
                if tool.output_schema is not None:
                    jsonschema.Draft202012Validator.check_schema(tool.output_schema)
                    schemas[tool.name] = tool.output_schema

            async def call(name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
                result = await client.call_tool(name, arguments or {})
                assert not result.is_error, (name, result.content)
                results.append((name, result.structured_content))
                return result

            async def wait(job: CallToolResult) -> None:
                assert job.structured_content is not None
                done = await call("get_job", {"job": job.structured_content["id"], "wait_seconds": TIMEOUT})
                assert done.structured_content is not None and done.structured_content["status"] == "done"

            await call("library_status")
            await wait(await call("import_folder", {"folder": str(photos)}))
            await call("list_photos")
            first = await call("render_preview", {"photo": "a", "size": 256})
            again = await call("render_preview", {"photo": "a", "size": 256})
            image = [b for b in first.content if isinstance(b, ImageContent)]
            assert image and image == [b for b in again.content if isinstance(b, ImageContent)]  # same bytes
            assert base64.b64decode(image[0].data)[:2] == b"\xff\xd8"
            await call("analyze_photo", {"photo": "a"})
            await call("update_adjustments", {"photos": ["a"], "changes": {"tone": {"exposure": 0.3}}})
            style = await call(
                "create_style", {"request": {"name": "Session", "values": {"tone.contrast": 10}}}
            )
            assert style.structured_content is not None
            await wait(
                await call("apply_style", {"style": style.structured_content["id"], "folder": str(photos)})
            )
            await call("contact_sheet", {"folder": str(photos), "size": 160})
            await call("set_note", {"photo": "b", "text": "Matches the others now."})
            plan = await call(
                "plan_export", {"destination": str(destination), "folder": str(photos), "preset": "web-full"}
            )
            assert plan.structured_content is not None and len(plan.structured_content["items"]) == 3
            await wait(
                await call(
                    "export_photos",
                    {"destination": str(destination), "folder": str(photos), "preset": "web-full"},
                )
            )

    anyio.run(session)

    # The originals are untouched; the export wrote only into its destination.
    assert _tree(photos) == originals
    assert sorted(_tree(destination)) == ["a_web.jpg", "b_web.jpg", "c_web.jpg"]
    project = tmp_path / "project"
    written = {p.relative_to(project).parts[0] for p in project.rglob("*") if p.is_file()}
    assert written <= {"workspace", "cache", "styles"}, written
    assert not [
        p for p in tmp_path.iterdir() if p.name not in ("photos", "project", "exports", "missing.toml")
    ]

    # Every structured result meets its tool's declared schema.
    for name, content in results:
        if name in schemas:
            jsonschema.validate(content, schemas[name])

    # Everything the session changed was published as the AI's (jobs included).
    events = listener.drain()
    changes = [e for e in events if e.kind is not EventKind.RESYNC]
    assert {e.kind for e in changes} >= {
        EventKind.PHOTO_EDIT,
        EventKind.STYLE,
        EventKind.JOB,
        EventKind.LIBRARY,
    }
    assert all(e.origin is Origin.AI for e in changes), {e.origin for e in changes}
