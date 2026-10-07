"""PhotoEditor: agent-driven, non-destructive RAW photo editor."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("photoedit")
except PackageNotFoundError:  # pragma: no cover - only when running from an uninstalled source tree
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
