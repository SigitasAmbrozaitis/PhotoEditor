"""MCP server skeleton (P7.2): tools listed with schemas, structured output, images, core errors as tool
errors, and the endpoint mounted in the ``photoedit ui`` app over real HTTP."""

from __future__ import annotations

import base64
import io
import socket
import threading
import time
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path
from typing import Any

import anyio
import httpx2
import pytest
import uvicorn
from mcp import Client
from mcp_types import CallToolResult, ImageContent, TextContent
from PIL import Image

from helpers import fill_folder
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


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


@pytest.fixture
def server_url(photo_settings: Settings, services: Services) -> Iterator[str]:
    port = _free_port()
    config = uvicorn.Config(
        create_app(photo_settings, services=services), host="127.0.0.1", port=port, log_level="warning"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "server did not start"
        time.sleep(0.02)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


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
