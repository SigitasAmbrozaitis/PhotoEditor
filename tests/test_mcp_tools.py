"""MCP tools (P7.10 to P7.13): valid and invalid input for every tool, through the SDK's in-process client.

The library holds three synthetic JPEGs (a.jpg red, b.jpg green, c.jpg blue portrait); subject detection is
faked with two cars per photo, so reviews have candidates without the real model files."""

from __future__ import annotations

import base64
import hashlib
import io
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp_types import CallToolResult, ImageContent, TextContent
from PIL import Image

from helpers import fill_folder
from photoedit.config import load_settings
from photoedit.core.jobs import ItemSpec
from photoedit.core.subject.service import Subjects
from photoedit.mcp.server import build_server
from photoedit.models import JobKind
from photoedit.models.subject import SubjectBox, SubjectCandidate, SubjectKind
from photoedit.services import Services

TIMEOUT = 30
CARS = [
    SubjectCandidate(
        box=SubjectBox(left=0.1, top=0.4, right=0.3, bottom=0.7), kind=SubjectKind.CAR, score=0.9
    ),
    SubjectCandidate(
        box=SubjectBox(left=0.7, top=0.4, right=0.9, bottom=0.7), kind=SubjectKind.CAR, score=0.8
    ),
]
SMALL_SQUARE: dict[str, Any] = {
    "size": {"mode": "long_edge", "long_edge": 64},
    "aspect": {"ratio": "1:1", "anchor": "subject", "zoom": "auto"},
}


@dataclass
class Env:
    services: Services
    server: MCPServer[Any]
    photos: Path
    tmp: Path

    def call(self, tool: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        async def go() -> CallToolResult:
            async with Client(self.server) as client:
                return await client.call_tool(tool, arguments or {})

        return anyio.run(go)

    def ok(self, tool: str, arguments: dict[str, Any] | None = None) -> Any:
        """The tool's structured result (lists unwrapped); fails the test on a tool error."""
        result = self.call(tool, arguments)
        assert not result.is_error, _text(result)
        data = result.structured_content
        if isinstance(data, dict) and set(data) == {"result"}:
            return data["result"]
        return data

    def error(self, tool: str, arguments: dict[str, Any] | None = None) -> str:
        result = self.call(tool, arguments)
        assert result.is_error, f"{tool} should have failed"
        return _text(result)

    def wait(self, job_id: str) -> dict[str, Any]:
        job = self.ok("get_job", {"job": job_id, "wait_seconds": TIMEOUT})
        assert job["finished_at"] is not None, job
        return job

    def id(self, name: str) -> str:
        return self.services.library.resolve(name).id


def _text(result: CallToolResult) -> str:
    return " ".join(block.text for block in result.content if isinstance(block, TextContent))


def _image(result: CallToolResult) -> Image.Image:
    block = next(b for b in result.content if isinstance(b, ImageContent))
    assert block.mime_type == "image/jpeg"
    return Image.open(io.BytesIO(base64.b64decode(block.data)))


def _hashes(folder: Path) -> dict[str, str]:
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir()) if p.is_file()
    }


@pytest.fixture
def env(tmp_path: Path) -> Iterator[Env]:
    photos = tmp_path / "photos"
    fill_folder(photos)
    settings = load_settings(
        tmp_path / "missing.toml",
        project_root=tmp_path / "project",
        sample_photos_dir=photos,
        export_workers=1,
    )
    services = Services(settings)
    subjects = Subjects(
        services.library, settings.cache_dir, objects=(lambda _: CARS, "fake"), faces=(lambda _: [], "f")
    )
    services.subjects = subjects
    services.exporter._subjects = subjects
    services.reviews._subjects = subjects
    services.jobs.wait(services.library.import_folder(photos).id, timeout=TIMEOUT)
    for job in services.jobs.list():
        services.jobs.wait(job.id, timeout=TIMEOUT)
    yield Env(services, build_server(lambda: services), photos, tmp_path)
    services.close()


def test_no_tool_deletes(env: Env) -> None:
    async def go() -> list[str]:
        async with Client(env.server) as client:
            return [t.name for t in (await client.list_tools()).tools]

    names = anyio.run(go)
    assert len(names) == 49
    assert not [n for n in names if n.startswith(("delete", "discard", "remove"))]


# ----------------------------------------------------------------- library + seeing (P7.10)


def test_library_status_import_and_open_folder(env: Env) -> None:
    status = env.ok("library_status")
    assert status["open"]["photo_count"] == 3 and len(status["folders"]) == 1
    assert status["active_jobs"] == [] and status["engine"]
    job = env.ok("import_folder", {"folder": str(env.photos)})
    assert env.wait(job["id"])["status"] == "done"
    assert env.ok("open_folder", {"folder": str(env.photos)})["photo_count"] == 3
    assert str(env.tmp / "nope") in env.error("import_folder", {"folder": str(env.tmp / "nope")})
    assert "not been imported" in env.error("open_folder", {"folder": str(env.tmp)})


def test_list_and_get_photos(env: Env) -> None:
    page = env.ok("list_photos", {"sort": "name"})
    assert [p["filename"] for p in page["items"]] == ["a.jpg", "b.jpg", "c.jpg"]
    assert env.ok("list_photos", {"folder": str(env.photos), "limit": 1})["total"] == 3
    assert "less than or equal to 200" in env.error("list_photos", {"limit": 500})
    assert "isn't imported yet" in env.error("list_photos", {"folder": str(env.tmp)})
    detail = env.ok("get_photo", {"photo": "a"})
    assert detail["photo"]["filename"] == "a.jpg" and detail["note"] is None
    assert "no imported photo called 'zzz'" in env.error("get_photo", {"photo": "zzz"})


def test_render_preview_of_the_edit_and_of_unsaved_changes(env: Env) -> None:
    saved = env.call("render_preview", {"photo": "a", "size": 256})
    assert not saved.is_error and max(_image(saved).size) == 256 and "current edit" in _text(saved)
    revision = env.services.library.edit(env.id("a")).revision
    draft = env.call(
        "render_preview", {"photo": "a", "size": 256, "changes": {"presence": {"saturation": -100}}}
    )
    assert "unsaved changes" in _text(draft)
    red, gray = _image(saved).convert("RGB").getpixel((5, 5)), _image(draft).convert("RGB").getpixel((5, 5))
    assert isinstance(red, tuple) and isinstance(gray, tuple) and red != gray
    assert env.services.library.edit(env.id("a")).revision == revision  # nothing saved
    assert "tone.exposure" in env.error(
        "render_preview", {"photo": "a", "changes": {"tone": {"exposure": 9}}}
    )
    assert "greater than or equal to 256" in env.error("render_preview", {"photo": "a", "size": 10})


def test_contact_sheet(env: Env) -> None:
    sheet = env.call("contact_sheet", {"folder": str(env.photos), "size": 160})
    assert not sheet.is_error and _text(sheet) == "3 of 3 photos"
    assert _image(sheet).width > 3 * 160
    two = env.call("contact_sheet", {"photos": ["a", "b", "c"], "limit": 2, "size": 160})
    assert _text(two) == "2 of 3 photos; 1 more after these (use offset 2)"
    assert "past the 3 photos" in env.error("contact_sheet", {"folder": str(env.photos), "offset": 5})
    assert "no photos given" in env.error("contact_sheet", {})


def test_analyze_photo(env: Env) -> None:
    saved = env.ok("analyze_photo", {"photo": "a"})
    assert saved["draft"] is False and saved["measures"]["colorful_share"] > 90
    draft = env.ok("analyze_photo", {"photo": "a", "changes": {"presence": {"saturation": -100}}})
    assert draft["draft"] is True and draft["measures"]["colorful_share"] == 0
    assert "unknown parameter 'tone.exposur'" in env.error(
        "analyze_photo", {"photo": "a", "changes": {"tone": {"exposur": 1}}}
    )


# ----------------------------------------------------------------- edits (P7.11)


def test_update_and_set_and_reset_adjustments(env: Env) -> None:
    results = env.ok("update_adjustments", {"photos": ["a", "b"], "changes": {"tone": {"exposure": 0.4}}})
    assert [r["filename"] for r in results] == ["a.jpg", "b.jpg"]
    assert all(r["own_tweaks"] == ["tone.exposure"] for r in results)
    before = {n: env.services.library.edit(env.id(n)).revision for n in "abc"}
    error = env.error(
        "update_adjustments",
        {"folder": str(env.photos), "changes": {"tone": {"contrast": 20, "whites": 900}}},
    )
    assert "tone.whites" in error
    assert {n: env.services.library.edit(env.id(n)).revision for n in "abc"} == before  # none saved
    full = env.services.library.edit(env.id("c")).adjustments.model_dump(mode="json")
    full["presence"]["vibrance"] = 25
    assert env.ok("set_adjustments", {"photo": "c", "adjustments": full})["own_tweaks"] == [
        "presence.vibrance"
    ]
    full["presence"]["clarity"] = 10
    assert "Phase 9" in env.error("set_adjustments", {"photo": "c", "adjustments": full})
    assert all(r["own_tweaks"] == [] for r in env.ok("reset_adjustments", {"folder": str(env.photos)}))
    assert "no photos given" in env.error("reset_adjustments", {})


def test_set_geometry_and_suggest_crop(env: Env) -> None:
    result = env.ok("set_geometry", {"photo": "a", "change": {"aspect": "1:1"}})
    assert result["geometry"]["aspect"] == "1:1"
    assert "less than or equal to 45" in env.error("set_geometry", {"photo": "a", "change": {"angle": 60}})
    crop = env.ok("suggest_crop", {"photo": "b", "aspect": "4:5"})
    assert crop["aspect"] in ("4:5", "5:4") and crop["crop"]["right"] > crop["crop"]["left"]
    assert "pattern" in env.error("suggest_crop", {"photo": "b", "aspect": "square"})


def test_subjects_and_notes(env: Env) -> None:
    detected = env.ok("get_subject", {"photo": "a"})
    assert detected["kind"] == "car"
    box = {"left": 0.4, "top": 0.4, "right": 0.6, "bottom": 0.6}
    assert env.ok("set_subject", {"photo": "a", "box": box})["source"] == "manual"
    assert env.ok("set_subject", {"photo": "a", "box": None})["source"] != "manual"
    assert env.error(
        "set_subject", {"photo": "a", "box": {"left": 0.6, "top": 0.1, "right": 0.2, "bottom": 0.5}}
    )
    job = env.ok("detect_subjects", {"folder": str(env.photos)})
    assert env.wait(job["id"])["status"] == "done"
    assert "no photos given" in env.error("detect_subjects", {"photos": []})
    note = env.ok("set_note", {"photo": "a", "text": "Red all over; left as is."})
    assert note["text"] == "Red all over; left as is."
    assert env.ok("get_photo", {"photo": "a"})["note"]["text"] == note["text"]
    assert "at most 2000 characters" in env.error("set_note", {"photo": "a", "text": "x" * 2001})
    assert env.ok("set_note", {"photo": "a", "text": None}) is None


# ----------------------------------------------------------------- styles (P7.12)


def test_style_lifecycle(env: Env) -> None:
    created = env.ok("create_style", {"request": {"name": "Warm", "values": {"tone.exposure": 0.2}}})
    sid = created["id"]
    assert "tone.exposure" in env.error(
        "create_style", {"request": {"name": "Bad", "values": {"tone.exposure": 9}}}
    )
    assert [s["id"] for s in env.ok("list_styles")] == [sid]
    assert env.ok("get_style", {"style": sid})["values"] == {"tone.exposure": 0.2}
    assert "not found" in env.error("get_style", {"style": "nope"})

    from_photo = env.ok("create_style_from_photo", {"request": {"photo_id": "a", "name": "From A"}})
    assert from_photo["name"] == "From A"
    assert "no imported photo" in env.error(
        "create_style_from_photo", {"request": {"photo_id": "z", "name": "Z"}}
    )

    updated = env.ok(
        "update_style", {"style": sid, "update": {"expected_version": 1, "values": {"tone.exposure": 0.3}}}
    )
    assert updated["version"] == 2
    conflict = env.error("update_style", {"style": sid, "update": {"expected_version": 1, "name": "X"}})
    assert "version" in conflict
    from_a = env.ok(
        "update_style_from_photo",
        {"style": sid, "request": {"photo_id": "a", "groups": ["tone"], "expected_version": 2}},
    )
    assert from_a["version"] == 3
    assert env.error(
        "update_style_from_photo",
        {"style": sid, "request": {"photo_id": "a", "groups": [], "expected_version": 3}},
    )
    copy = env.ok("duplicate_style", {"style": sid})
    assert copy["name"] == "Warm (copy)"
    assert "at most 80 characters" in env.error("duplicate_style", {"style": sid, "name": "x" * 81})

    assert [v["version"] for v in env.ok("style_history", {"style": sid})][:2] == [3, 2]
    assert env.ok("style_diff", {"style": sid, "a": 1, "b": 2})["values"]
    assert env.error("style_diff", {"style": sid, "a": 1, "b": 9})
    reverted = env.ok("revert_style", {"style": sid, "version": 1, "expected_version": 3})
    assert reverted["version"] == 4 and reverted["values"] == {"tone.exposure": 0.2}
    assert env.error("revert_style", {"style": sid, "version": 1, "expected_version": 3})


def test_apply_style_report_and_samples(env: Env) -> None:
    sid = env.ok("create_style", {"request": {"name": "Cool", "values": {"tone.exposure": -0.2}}})["id"]
    job = env.ok("apply_style", {"style": sid, "folder": str(env.photos)})
    assert env.wait(job["id"])["status"] == "done"
    assert env.services.library.photo(env.id("b")).style_id == sid
    assert "not found" in env.error("apply_style", {"style": "nope", "photos": ["a"]})
    report = env.ok("style_report", {"style": sid})
    assert report is not None
    assert env.error("style_report", {"style": "nope"})
    samples = env.ok("render_style_samples", {"style": sid, "photos": ["a"]})
    assert env.wait(samples["id"])["status"] == "done"
    assert "at least 1 item" in env.error("render_style_samples", {"style": sid, "photos": []})
    removed = env.ok("apply_style", {"style": None, "photos": ["a"]})
    env.wait(removed["id"])
    assert env.services.library.photo(env.id("a")).style_id is None


# ----------------------------------------------------------------- export, review, jobs (P7.13)


def test_presets(env: Env) -> None:
    assert "web-full" in [p["id"] for p in env.ok("list_export_presets")]
    assert env.ok("get_export_preset", {"preset": "web-full"})["builtin"] is True
    assert "not found" in env.error("get_export_preset", {"preset": "nope"})
    custom = env.ok("create_export_preset", {"request": {"name": "Tiny"}})
    changed = env.ok(
        "update_export_preset", {"preset": custom["id"], "update": {"expected_version": 1, "name": "Tinier"}}
    )
    assert changed["name"] == "Tinier"
    assert env.error(
        "update_export_preset", {"preset": "web-full", "update": {"expected_version": 1, "name": "X"}}
    )


def test_plan_and_export_write_only_the_destination(env: Env) -> None:
    originals = _hashes(env.photos)
    out = env.tmp / "out"
    plan = env.ok("plan_export", {"destination": str(out), "folder": str(env.photos), "preset": "web-full"})
    assert len(plan["items"]) == 3 and not out.exists()
    assert "give a preset" in env.error("plan_export", {"destination": str(out), "photos": ["a"]})
    refused = env.error(
        "plan_export", {"destination": str(env.photos / "x"), "photos": ["a"], "preset": "web-full"}
    )
    assert "photo" in refused.lower()
    job = env.ok("export_photos", {"destination": str(out), "photos": ["a", "c"], "preset": "web-full"})
    done = env.wait(job["id"])
    assert done["status"] == "done" and sorted(p.name for p in out.iterdir()) == ["a_web.jpg", "c_web.jpg"]
    assert _hashes(env.photos) == originals
    assert env.error(
        "export_photos", {"destination": str(out), "photos": ["a"], "settings": {"file": {"format": "gif"}}}
    )


def test_review_flow(env: Env) -> None:
    out = env.tmp / "review-out"
    job = env.ok(
        "prepare_export", {"destination": str(out), "folder": str(env.photos), "settings": SMALL_SQUARE}
    )
    review_id = env.wait(job["id"])["review_id"]
    assert [r["id"] for r in env.ok("list_reviews")] == [review_id]
    review = env.ok("get_review", {"review": review_id})
    assert {item["status"] for item in review["items"]} == {"check"}  # two cars: ambiguous everywhere
    assert "not found" in env.error("get_review", {"review": "nope"})

    approved = env.ok("update_review_item", {"review": review_id, "photo": "a", "update": {"approved": True}})
    assert next(i for i in approved["items"] if i["photo_id"] == env.id("a"))["approved"] is not None
    assert env.error("update_review_item", {"review": review_id, "photo": "a", "update": {}})
    chosen = env.ok("set_review_subject", {"review": review_id, "photo": "b", "update": {"candidate": 0}})
    assert next(i for i in chosen["items"] if i["photo_id"] == env.id("b"))["approved"] is not None
    assert env.error("set_review_subject", {"review": review_id, "photo": "b", "update": {"candidate": -1}})

    preview = env.call("review_preview", {"review": review_id, "photo": "a"})
    assert not preview.is_error and max(_image(preview).size) <= 800
    assert env.error("review_preview", {"review": review_id, "photo": "zzz"})

    exported = env.ok("export_review", {"review": review_id})
    assert env.wait(exported["id"])["status"] == "done"
    assert sorted(p.name for p in out.iterdir()) == ["a.jpg", "b.jpg"]
    assert env.error("export_review", {"review": review_id, "scope": "everything"})

    settings = env.ok("get_review_settings")
    settings["min_score"] = 0.6
    assert env.ok("set_review_settings", {"settings": settings})["min_score"] == 0.6
    settings["min_score"] = 2
    assert "less than or equal to 1" in env.error("set_review_settings", {"settings": settings})


def test_jobs_wait_time_out_and_cancel(env: Env) -> None:
    release = threading.Event()
    slow = env.services.jobs.submit(
        JobKind.IMPORT, "Slow", [ItemSpec("x"), ItemSpec("y")], lambda _: release.wait(TIMEOUT) and None
    )
    waited = env.ok("get_job", {"job": slow.id, "wait_seconds": 1})
    assert waited["finished_at"] is None and waited["status"] in ("queued", "running")
    assert slow.id in [j["id"] for j in env.ok("list_jobs")]
    cancelled = env.ok("cancel_job", {"job": slow.id})
    assert cancelled["id"] == slow.id
    release.set()
    assert env.wait(slow.id)["status"] in ("cancelled", "done")
    assert "not found" in env.error("get_job", {"job": "j9999"})
    assert "less than or equal to 120" in env.error("get_job", {"job": slow.id, "wait_seconds": 500})
    assert env.error("cancel_job", {"job": "j9999"})
