"""The MCP server: Claude's way into the core (PLAN 4.4). Thin like the HTTP routes: tools translate arguments
into core calls and results into structured output, images or short text. Mounted inside the ``photoedit ui``
server at ``/mcp`` (decided 2026-10-15), so the AI and the UI share one set of services."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Annotated, Any

from mcp.server.mcpserver import Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field, ValidationError

from photoedit import __version__
from photoedit.core.errors import InvalidRequestError, NotFoundError
from photoedit.safety import WriteNotAllowedError
from photoedit.services import Services

MCP_PATH = "/mcp"

INSTRUCTIONS = """\
PhotoEditor: a non-destructive RAW photo editor driven by you. The user browses, compares and approves in its
web UI, which follows your changes live.

Rules the tool enforces (you can't break them, so don't work around an error; report it):
- Originals are read-only. Edits are small JSON files; pixels are only made for previews and exports.
- Every value has a range; out-of-range or unknown values are rejected with the reason.
- Rendering is deterministic: the same photo, edit and engine give the same image.

Look before and after you change something: render_preview shows you the photo."""


class Pong(BaseModel):
    status: str
    version: str
    photos: int = Field(description="Photos in the folder open in the Library.")


def _core_errors[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Core errors become tool errors carrying their message. Anything else is a crash, which the SDK reports
    to the model only as "Error executing tool" (its text stays in the server log)."""

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return fn(*args, **kwargs)
        except (NotFoundError, InvalidRequestError, WriteNotAllowedError, ValidationError) as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


def build_server(services: Callable[[], Services]) -> MCPServer[Any]:
    """The MCP server over ``services``, called per tool call (the app builds the services on first use)."""
    server: MCPServer[Any] = MCPServer(
        "photoedit", title="PhotoEditor", version=__version__, instructions=INSTRUCTIONS
    )

    @server.tool()
    @_core_errors
    def ping() -> Pong:
        """Check that PhotoEditor is running; returns its version and the open folder's photo count."""
        return Pong(status="ok", version=__version__, photos=services().library.info().photo_count)

    @server.tool()
    @_core_errors
    def render_preview(
        photo_id: Annotated[str, Field(description="The photo's id.")],
        size: Annotated[int, Field(ge=256, le=1600, description="Long edge in pixels.")] = 1024,
    ) -> Image:
        """The photo with its current edit, as a JPEG for you to look at."""
        return Image(data=services().library.preview(photo_id, size), format="jpeg")

    return server
