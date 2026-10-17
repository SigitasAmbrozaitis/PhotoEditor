"""MCP server skeleton (P7.2): tools listed with schemas, structured output, images, core errors as tool
errors, and the endpoint mounted in the ``photoedit ui`` app over real HTTP."""

from __future__ import annotations

import base64
import io
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path
from typing import Any

import anyio
import httpx2
import pytest
from mcp import Client
from mcp_types import CallToolResult, ImageContent, TextContent
from PIL import Image

from helpers import fill_folder, free_port, serve
from photoedit import __version__
from photoedit.api import create_app
from photoedit.config import Settings, load_settings
from photoedit.mcp.server import build_server
from photoedit.services import Services


@pytest.fixture
def photo_settings(tmp_path: Path) -> Settings:
    photos = tmp_path / "photos"
    fill_folder(photos)
    return load_settings(
        tmp_path / "missing.toml", project_root=tmp_path / "project", sample_photos_dir=photos
    )


@pytest.fixture
def services(photo_settings: Settings) -> Iterator[Services]:
    services = Services(photo_settings)
    assert photo_settings.sample_photos_dir is not None
    job = services.library.import_folder(photo_settings.sample_photos_dir)
    services.jobs.wait(job.id, timeout=30)
    yield services
    services.close()


def _run[T](fn: Callable[[], Awaitable[T]]) -> T:
    return anyio.run(fn)


def _call(target: Any, tool: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
    async def go() -> CallToolResult:
        async with Client(target) as client:
            return await client.call_tool(tool, arguments or {})

    return _run(go)


def _text(result: CallToolResult) -> str:
    return " ".join(block.text for block in result.content if isinstance(block, TextContent))


def _first_photo(services: Services) -> str:
    return services.library.list_photos(limit=1).items[0].id


def test_tools_have_descriptions_and_schemas(services: Services) -> None:
    async def go() -> list[Any]:
        async with Client(build_server(lambda: services)) as client:
            return (await client.list_tools()).tools

    tools = {tool.name: tool for tool in _run(go)}
    assert {"ping", "render_preview", "library_status", "export_photos"} <= tools.keys()
    for tool in tools.values():
        assert tool.description, tool.name
        assert tool.input_schema["type"] == "object"
    size = tools["render_preview"].input_schema["properties"]["size"]
    assert (size["minimum"], size["maximum"]) == (256, 1600)


def test_ping_returns_structured_output(services: Services) -> None:
    result = _call(build_server(lambda: services), "ping")
    assert not result.is_error
    assert result.structured_content == {"status": "ok", "version": __version__, "photos": 3}


def test_render_preview_returns_a_jpeg_of_the_asked_size(services: Services) -> None:
    result = _call(
        build_server(lambda: services), "render_preview", {"photo": _first_photo(services), "size": 256}
    )
    assert not result.is_error
    block = result.content[0]
    assert isinstance(block, ImageContent)
    assert block.mime_type == "image/jpeg"
    with Image.open(io.BytesIO(base64.b64decode(block.data))) as image:
        assert image.format == "JPEG"
        assert max(image.size) == 256


def test_core_errors_reach_the_model_with_their_message(services: Services) -> None:
    result = _call(build_server(lambda: services), "render_preview", {"photo": "nope"})
    assert result.is_error
    assert "no imported photo called 'nope'" in _text(result)


def test_invalid_arguments_are_rejected_with_the_reason(services: Services) -> None:
    result = _call(build_server(lambda: services), "render_preview", {"photo": "x", "size": 5000})
    assert result.is_error
    assert "less than or equal to 1600" in _text(result)


# ----------------------------------------------------------------- over HTTP, inside the ui server


@pytest.fixture
def server_url(photo_settings: Settings, services: Services) -> Iterator[str]:
    with serve(create_app(photo_settings, services=services)) as url:
        yield url


def test_mcp_over_http_in_the_ui_server(server_url: str, services: Services) -> None:
    ping = _call(f"{server_url}/mcp", "ping")
    assert ping.structured_content is not None and ping.structured_content["status"] == "ok"
    preview = _call(f"{server_url}/mcp", "render_preview", {"photo": _first_photo(services), "size": 300})
    assert isinstance(preview.content[0], ImageContent)
    # The UI and the API are still served next to it.
    assert httpx2.get(f"{server_url}/api/health").json()["status"] == "ok"


def test_mcp_refuses_cross_origin_requests(server_url: str) -> None:
    response = httpx2.post(
        f"{server_url}/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
        headers={"Origin": "http://evil.example", "Accept": "application/json, text/event-stream"},
    )
    assert response.status_code == 403


def test_cli_mcp_check(server_url: str, tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from photoedit.cli import app

    port = server_url.rsplit(":", 1)[1]
    config = ["--config", str(tmp_path / "missing.toml")]
    up = CliRunner().invoke(app, ["mcp", "check", *config, "--port", port])
    assert up.exit_code == 0, up.output
    assert f"MCP server at {server_url}/mcp: 49 tools" in up.output
    assert "render_preview" in up.output and f'"url": "{server_url}/mcp"' in up.output
    down = CliRunner().invoke(app, ["mcp", "check", *config, "--port", str(free_port())])
    assert down.exit_code == 1 and "Start it with: photoedit ui" in down.output
