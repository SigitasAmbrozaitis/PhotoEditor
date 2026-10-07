"""Error types the front-ends translate to responses (HTTP 404 / 400, CLI messages, MCP errors)."""

from __future__ import annotations


class NotFoundError(LookupError):
    """The requested object doesn't exist."""


class InvalidRequestError(ValueError):
    """The request can't be done as asked; the message says why, in words a user understands."""
