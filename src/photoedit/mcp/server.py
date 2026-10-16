"""The MCP server: Claude's way into the core (PLAN 4.4). Thin like the HTTP routes: tools translate arguments
into core calls and results into structured output, images or short text. Mounted inside the ``photoedit ui``
server at ``/mcp`` (decided 2026-10-15), so the AI and the UI share one set of services."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

from photoedit import __version__
from photoedit.mcp import tools_edit, tools_export, tools_library, tools_styles
from photoedit.mcp.common import READ_ONLY, Svc, tool

MCP_PATH = "/mcp"

INSTRUCTIONS = """\
PhotoEditor: a non-destructive RAW photo editor that you drive for the user. They browse, compare and approve
in its web UI, which follows your changes live (and tells them "Claude changed…").

Rules the tool enforces (you can't break them, so don't work around an error: report it):
- Originals are read-only. Edits, styles and presets are small JSON files; pixels are only made for previews
  and exports.
- Every value has a range; out-of-range or unknown values are rejected with the reason, and nothing changes.
- Rendering is deterministic: the same photo, edit and engine always give the same image.
- Exports go only to the folder you name, never into a photo folder. Deleting styles or presets and
  discarding reviews is left to the user.

How to work:
- Start with library_status. Photos can be named by file name (DSCF5437), folder/name, or id.
- Look before and after changing something: render_preview (an image) and analyze_photo (numbers). Both can
  show unsaved `changes` first; update_adjustments saves only the values you give.
- A series: apply_style (or update_adjustments on a folder), wait with get_job, then contact_sheet.
- Export: plan_export first, then export_photos. When subjects decide the framing (Instagram crops), use
  prepare_export so doubtful photos go to the user's review (Check) instead of guessing.
- Long work returns a job: get_job with wait_seconds until it ends.
- Leave a note with set_note when you change or judge a photo, so the user sees why in its AI Analysis tab."""


class Pong(BaseModel):
    status: str
    version: str
    photos: int = Field(description="Photos in the folder open in the Library.")


def build_server(services: Svc) -> MCPServer[Any]:
    """The MCP server over ``services``, called per tool call (the app builds the services on first use)."""
    server: MCPServer[Any] = MCPServer(
        "photoedit", title="PhotoEditor", version=__version__, instructions=INSTRUCTIONS
    )

    @tool(server, READ_ONLY)
    def ping() -> Pong:
        """Check that PhotoEditor is running; returns its version and the open folder's photo count."""
        return Pong(status="ok", version=__version__, photos=services().library.info().photo_count)

    for module in (tools_library, tools_edit, tools_styles, tools_export):
        module.register(server, services)
    return server
