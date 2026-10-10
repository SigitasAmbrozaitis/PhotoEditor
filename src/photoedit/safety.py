"""Write-boundary enforcement.

Golden rule: original photos are read-only, and the tool writes only into folders it owns or into export
destinations the user explicitly chose.
Every write in the codebase must go through ``PathGuard.assert_writable``.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Iterable
from pathlib import Path

from photoedit.config import Settings


class WriteNotAllowedError(PermissionError):
    """Raised when code tries to write to a path outside the allowed roots or inside a protected one."""


def _normalize(path: Path) -> Path:
    """Absolute, symlink-resolved path (works for paths that don't exist yet).

    Raises ``WriteNotAllowedError`` if the path can't be resolved (e.g. an unreachable network share under
    load): a path whose real location is unknown is never writable.
    """
    try:
        real = os.path.realpath(path.expanduser())
    except OSError as exc:
        raise WriteNotAllowedError(
            f"Refusing to write to a path that can't be resolved: {path} ({exc})"
        ) from exc
    # On Windows, realpath sometimes keeps the extended-length prefix (seen while another thread creates the
    # same folder at that moment). Strip it so the path compares equal to the roots.
    if real.startswith("\\\\?\\UNC\\"):
        real = "\\\\" + real[len("\\\\?\\UNC\\") :]
    elif real.startswith("\\\\?\\"):
        real = real[len("\\\\?\\") :]
    return Path(real)


def _is_within(path: Path, root: Path) -> bool:
    # normcase: case-insensitive comparison and unified separators on Windows.
    p = os.path.normcase(str(path))
    r = os.path.normcase(str(root))
    try:
        return os.path.commonpath([p, r]) == r
    except ValueError:  # different drives / UNC vs local
        return False


class PathGuard:
    """Decides whether a path may be written to.

    A path is writable when it lies inside at least one writable root and inside no protected root.
    Protected roots always win, so a photo folder stays read-only even if it sits inside a writable root.
    """

    def __init__(self, writable_roots: Iterable[Path] = (), protected_roots: Iterable[Path] = ()) -> None:
        self._writable: list[Path] = []
        self._protected: list[Path] = []
        for root in writable_roots:
            self.allow_writes_to(root)
        for root in protected_roots:
            self.protect(root)

    @property
    def writable_roots(self) -> tuple[Path, ...]:
        return tuple(self._writable)

    @property
    def protected_roots(self) -> tuple[Path, ...]:
        return tuple(self._protected)

    def allow_writes_to(self, root: Path) -> None:
        """Register a writable root (e.g. an export destination chosen by the user)."""
        normalized = _normalize(root)
        if normalized not in self._writable:
            self._writable.append(normalized)

    def revoke(self, root: Path) -> None:
        """Remove a writable root registered with ``allow_writes_to`` (e.g. after an export finished)."""
        normalized = _normalize(root)
        if normalized in self._writable:
            self._writable.remove(normalized)

    def protected_root_of(self, path: Path) -> Path | None:
        """The protected folder ``path`` lies in, if any (None also for a path that can't be resolved)."""
        try:
            target = _normalize(path)
        except WriteNotAllowedError:
            return None
        return next((root for root in self._protected if _is_within(target, root)), None)

    def protect(self, root: Path) -> None:
        """Mark a folder (e.g. a source photo folder) as never writable."""
        normalized = _normalize(root)
        if normalized not in self._protected:
            self._protected.append(normalized)

    def is_writable(self, path: Path) -> bool:
        try:
            target = _normalize(path)
        except WriteNotAllowedError:
            return False
        if any(_is_within(target, root) for root in self._protected):
            return False
        return any(_is_within(target, root) for root in self._writable)

    def assert_writable(self, path: Path) -> Path:
        """Return the normalized path if writing is allowed, otherwise raise ``WriteNotAllowedError``."""
        target = _normalize(path)
        if any(_is_within(target, root) for root in self._protected):
            raise WriteNotAllowedError(f"Refusing to write into a protected (read-only) folder: {target}")
        if not any(_is_within(target, root) for root in self._writable):
            raise WriteNotAllowedError(f"Refusing to write outside the allowed folders: {target}")
        return target

    def write_atomic(self, path: Path, data: bytes) -> Path:
        """Write ``data`` to ``path`` via a temp file + rename, so readers never see a half-written file."""
        target = self.assert_writable(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Unique per process and thread: parallel writers of the same file must not share a temp file.
        temp = target.with_name(f".{target.name}.{os.getpid()}-{threading.get_ident()}.tmp")
        try:
            temp.write_bytes(data)
            temp.replace(target)
        finally:
            temp.unlink(missing_ok=True)
        return target


def guard_from_settings(settings: Settings) -> PathGuard:
    """Guard for the tool-owned folders, with the configured photo folders protected."""
    return PathGuard(writable_roots=settings.writable_dirs, protected_roots=settings.photo_dirs)
