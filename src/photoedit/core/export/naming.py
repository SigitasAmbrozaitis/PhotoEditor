"""Output file names: the naming template per photo, unique within the batch, then the collision policy.

Names are compared case-insensitively, as Windows does.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from photoedit.models.export import (
    WINDOWS_RESERVED,
    CollisionPolicy,
    CollisionStatus,
    NamingSettings,
    parse_template,
)

MAX_NAME_LENGTH = 150  # characters, extension included; leaves room for long destination folders
_FORBIDDEN = set('<>:"/\\|?*') | {chr(c) for c in range(32)}


@dataclass(frozen=True)
class NameFields:
    """What the template tokens of one photo expand to."""

    original: str  # the original's file name without its extension
    captured_at: datetime | None = None
    camera: str | None = None
    style: str | None = None
    preset: str | None = None


@dataclass(frozen=True)
class PlannedName:
    name: str
    collision: CollisionStatus


def expand(template: str, fields: NameFields, seq: int) -> str:
    """The file name stem for one photo (no extension), safe to use on Windows."""
    out: list[str] = []
    for part in parse_template(template):
        if isinstance(part, str):
            out.append(part)
            continue
        token, width = part
        match token:
            case "original":
                out.append(fields.original)
            case "date":
                out.append(fields.captured_at.strftime("%Y-%m-%d") if fields.captured_at else "nodate")
            case "time":
                out.append(fields.captured_at.strftime("%H%M%S") if fields.captured_at else "notime")
            case "seq":
                out.append(str(seq).zfill(width))
            case "style":
                out.append(fields.style or "nostyle")
            case "preset":
                out.append(fields.preset or "custom")
            case "camera":
                out.append(fields.camera or "nocamera")
    return _safe("".join(out))


def _safe(stem: str) -> str:
    cleaned = "".join("_" if c in _FORBIDDEN else c for c in stem).rstrip(". ").strip()
    if not cleaned:
        cleaned = "export"
    if cleaned.lower() in WINDOWS_RESERVED:
        cleaned += "_"
    return cleaned


def plan_names(
    settings: NamingSettings,
    photos: Sequence[NameFields],
    extension: str,
    existing: set[str],
) -> list[PlannedName]:
    """Names for ``photos`` in export order (``seq`` = 1, 2, …).

    ``existing`` are the file names already in the destination, in lower case. Two photos of the batch never
    get the same name (the later one gets ``_2``, ``_3``…), whatever the collision policy.
    """
    used: set[str] = set()
    planned: list[PlannedName] = []
    policy = settings.on_collision
    for seq, fields in enumerate(photos, start=1):
        stem = _fit(expand(settings.template, fields, seq), extension, suffix_room=0)
        name = stem + extension
        renamed = False
        if name.lower() in used or (policy == CollisionPolicy.SUFFIX and name.lower() in existing):
            name = _suffixed(stem, extension, used | existing if policy == CollisionPolicy.SUFFIX else used)
            renamed = True
        if name.lower() in existing:  # only with overwrite / skip: suffix always picks a free name
            status = (
                CollisionStatus.OVERWRITE if policy == CollisionPolicy.OVERWRITE else CollisionStatus.SKIP
            )
        else:
            status = CollisionStatus.RENAMED if renamed else CollisionStatus.NEW
        used.add(name.lower())
        planned.append(PlannedName(name, status))
    return planned


def _suffixed(stem: str, extension: str, taken: set[str]) -> str:
    n = 2
    while True:
        candidate = f"{_fit(stem, extension, suffix_room=len(f'_{n}'))}_{n}{extension}"
        if candidate.lower() not in taken:
            return candidate
        n += 1


def _fit(stem: str, extension: str, *, suffix_room: int) -> str:
    """Shorten the stem so the whole name stays within ``MAX_NAME_LENGTH``."""
    room = MAX_NAME_LENGTH - len(extension) - suffix_room
    return stem if len(stem) <= room else stem[:room].rstrip(". ") or "export"
