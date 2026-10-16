"""What every MCP tool shares: how it is registered (as the AI, core errors as tool errors), photo references,
and images."""

from __future__ import annotations

import functools
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

from mcp.server.mcpserver import Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import BaseModel, Field, ValidationError

from photoedit.core.decode import DecodeError
from photoedit.core.errors import InvalidRequestError, NotFoundError
from photoedit.core.events import origin
from photoedit.core.subject.model_files import ModelFileError
from photoedit.models import Job, JobStatus
from photoedit.models.events import Origin
from photoedit.safety import WriteNotAllowedError
from photoedit.services import Services

type Svc = Callable[[], Services]

# Hints for the client (Claude Code may treat read-only tools more lightly). Nothing here is open-world: every
# tool works on this machine's library only.
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)
CHANGES = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False
)

# Errors the core raises for a request it refuses, with a message meant for the caller.
_EXPECTED = (
    NotFoundError,
    InvalidRequestError,
    WriteNotAllowedError,
    ValidationError,
    DecodeError,
    ModelFileError,
)

PhotoRef = Annotated[
    str,
    Field(
        min_length=1,
        description="A photo: its id (or its first 8+ characters), its file name (DSCF5437 or DSCF5437.RAF), "
        "or folder/name when the name is in several folders.",
    ),
]
PhotoRefs = Annotated[
    list[PhotoRef], Field(max_length=2000, description="Photos, each as an id, a file name or folder/name.")
]
Folder = Annotated[
    str | None, Field(default=None, description="An imported folder (its full path): all its photos.")
]


def tool[F: Callable[..., Any]](
    server: MCPServer[Any], annotations: ToolAnnotations, *, title: str | None = None
) -> Callable[[F], F]:
    """Register a tool that runs as the AI (so the UI can say "Claude changed…") and turns core errors into
    tool errors carrying their message. Anything else is a crash, which the SDK reports to the model only as
    "Error executing tool" (its text stays in the server log)."""

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                with origin(Origin.AI):
                    return fn(*args, **kwargs)
            except _EXPECTED as exc:
                raise ToolError(str(exc)) from exc

        server.add_tool(wrapper, title=title, annotations=annotations)
        return fn

    return decorator


def photo_id(svc: Svc, ref: str) -> str:
    return svc().library.resolve(ref).id


def photo_ids(svc: Svc, refs: list[str], folder: str | None) -> list[str]:
    """The photos named, then all of ``folder``'s; each once. At least one is required."""
    found = svc().library.resolve_many(refs, folder=Path(folder) if folder else None)
    return [p.id for p in found]


class JobBrief(BaseModel):
    id: str
    title: str
    status: JobStatus
    progress: float = Field(ge=0, le=1)
    summary: str | None = None


def brief(job: Job) -> JobBrief:
    return JobBrief(id=job.id, title=job.title, status=job.status, progress=job.progress, summary=job.summary)


def jpeg(data: bytes) -> Image:
    return Image(data=data, format="jpeg")
