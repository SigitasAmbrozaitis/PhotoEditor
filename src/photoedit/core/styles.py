"""The style library: one folder per style under ``styles/``.

``styles/<id>/style.json`` is the source of truth. ``README.md`` is regenerated from it on every save.
Every saved version is kept in ``history/v<N>.json``, so trying a change costs nothing (compare, then keep or
revert). ``samples/`` holds rendered before/after pairs. All writes are atomic and go through the path guard.
"""

from __future__ import annotations

import json
import re
import shutil
import threading
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from photoedit.core.errors import ConflictError, InvalidRequestError, NotFoundError
from photoedit.core.render.pipeline import check_supported
from photoedit.models import AdjustmentParams, Style
from photoedit.models.style import (
    STYLE_ID_PATTERN,
    STYLE_SCHEMA_VERSION,
    RuleChange,
    StyleCreate,
    StyleDiff,
    StyleSample,
    StyleUpdate,
    StyleVersionInfo,
    ValueChange,
)
from photoedit.safety import PathGuard

STYLE_FILE = "style.json"
README_FILE = "README.md"
HISTORY_DIR = "history"
SAMPLES_DIR = "samples"
_MAX_SLUG = 40
_VERSION_FILE = re.compile(r"^v(\d+)\.json$")

type Clock = Callable[[], datetime]
# schema_version N → N + 1, applied in order to files written by older versions of the tool.
type Migration = Callable[[dict[str, Any]], dict[str, Any]]
MIGRATIONS: dict[int, Migration] = {}


@dataclass(frozen=True)
class StyleListing:
    """One folder in the library: the style, or why it can't be read."""

    id: str
    style: Style | None
    error: str | None


class StyleLibrary:
    def __init__(self, root: Path, guard: PathGuard, *, clock: Clock | None = None) -> None:
        self.root = root
        self._guard = guard
        self._clock: Clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.RLock()

    # ---- reading

    def listings(self) -> list[StyleListing]:
        """Every style folder, sorted by name; a broken file is listed with its error instead of failing."""
        listings: list[StyleListing] = []
        if not self.root.is_dir():
            return listings
        for folder in self.root.iterdir():
            if not (folder / STYLE_FILE).is_file() or not re.match(STYLE_ID_PATTERN, folder.name):
                continue
            try:
                listings.append(StyleListing(folder.name, self.get(folder.name), None))
            except InvalidRequestError as exc:
                listings.append(StyleListing(folder.name, None, str(exc)))
        return sorted(listings, key=lambda e: (e.style.name.lower() if e.style else e.id, e.id))

    def get(self, style_id: str) -> Style:
        path = self._style_file(style_id)
        if not path.is_file():
            raise NotFoundError(f"style '{style_id}' not found")
        style = _parse(path.read_text(encoding="utf-8"), f"style '{style_id}'")
        if style.id != style_id:
            raise InvalidRequestError(
                f"style '{style_id}': its file says id '{style.id}' (the folder name wins)"
            )
        return style

    def exists(self, style_id: str) -> bool:
        return self._style_file(style_id).is_file()

    def folder(self, style_id: str) -> Path:
        if not re.match(STYLE_ID_PATTERN, style_id):
            raise NotFoundError(f"style '{style_id}' not found")
        return self.root / style_id

    def sample_path(self, style_id: str, name: str, which: Literal["before", "after"]) -> Path:
        return self.folder(style_id) / SAMPLES_DIR / f"{name}-{which}.jpg"

    # ---- writing

    def create(self, request: StyleCreate, *, change_note: str = "created") -> Style:
        with self._lock:
            now = self._clock()
            style = _build(
                {
                    **request.model_dump(mode="json"),
                    "id": self._free_id(slugify(request.name)),
                    "created_at": now,
                    "updated_at": now,
                    "version": 1,
                    "change_note": change_note,
                },
                "new style",
            )
            self._write(style)
            return style

    def update(self, style_id: str, update: StyleUpdate) -> Style:
        """Apply ``update`` if the style is still at ``update.expected_version`` (else ``ConflictError``)."""
        with self._lock:
            current = self.get(style_id)
            if current.version != update.expected_version:
                raise ConflictError(
                    f"style '{style_id}' is at version {current.version}, but the change was made on version "
                    f"{update.expected_version}; reload it and try again"
                )
            changes = update.model_dump(
                mode="json", exclude_unset=True, exclude={"expected_version", "change_note"}
            )
            return self._save_new_version(current, changes, update.change_note)

    def set_samples(self, style_id: str, samples: list[StyleSample]) -> Style:
        """Record rendered samples. Not a new version: samples are derived from the look, not part of it."""
        with self._lock:
            style = self.get(style_id).model_copy(update={"samples": samples})
            self._write_files(style, history=False)
            return style

    def duplicate(self, style_id: str, name: str | None = None) -> Style:
        source = self.get(style_id)
        request = StyleCreate.model_validate(
            {
                **source.model_dump(mode="json", include=set(StyleCreate.model_fields)),
                "name": name or f"{source.name} (copy)"[:80],
            }
        )
        return self.create(request, change_note=f"duplicated from '{source.id}' version {source.version}")

    def delete(self, style_id: str) -> None:
        with self._lock:
            folder = self.folder(style_id)
            if not (folder / STYLE_FILE).is_file():
                raise NotFoundError(f"style '{style_id}' not found")
            self._guard.assert_writable(folder)
            shutil.rmtree(folder)

    # ---- history

    def history(self, style_id: str) -> list[StyleVersionInfo]:
        """Saved versions, newest first."""
        self.get(style_id)
        folder = self.folder(style_id) / HISTORY_DIR
        versions: list[StyleVersionInfo] = []
        for path in folder.glob("v*.json") if folder.is_dir() else ():
            if _VERSION_FILE.match(path.name):
                old = _parse(path.read_text(encoding="utf-8"), f"style '{style_id}' {path.name}")
                versions.append(
                    StyleVersionInfo(
                        version=old.version,
                        updated_at=old.updated_at,
                        change_note=old.change_note,
                        look_hash=old.look_hash(),
                    )
                )
        return sorted(versions, key=lambda v: v.version, reverse=True)

    def version(self, style_id: str, version: int) -> Style:
        current = self.get(style_id)
        if version == current.version:
            return current
        path = self.folder(style_id) / HISTORY_DIR / f"v{version}.json"
        if not path.is_file():
            raise NotFoundError(f"style '{style_id}' has no version {version}")
        return _parse(path.read_text(encoding="utf-8"), f"style '{style_id}' version {version}")

    def diff(self, style_id: str, a: int, b: int) -> StyleDiff:
        return diff_styles(self.version(style_id, a), self.version(style_id, b))

    def revert(self, style_id: str, version: int, *, expected_version: int) -> Style:
        """Bring back an older version's look and text as a new version (nothing is lost)."""
        with self._lock:
            old = self.version(style_id, version)
            fields = {"name", "description", "best_for", "avoid_on", "values", "rules", "test_photo_ids"}
            update = StyleUpdate.model_validate(
                {
                    **old.model_dump(mode="json", include=fields),
                    "expected_version": expected_version,
                    "change_note": f"reverted to version {version}",
                }
            )
            return self.update(style_id, update)

    # ---- internals

    def _style_file(self, style_id: str) -> Path:
        return self.folder(style_id) / STYLE_FILE

    def _free_id(self, slug: str) -> str:
        candidate, n = slug, 1
        while self.folder(candidate).exists():
            n += 1
            suffix = f"-{n}"
            candidate = slug[: _MAX_SLUG - len(suffix)].rstrip("-") + suffix
        return candidate

    def _save_new_version(self, current: Style, changes: dict[str, Any], note: str) -> Style:
        data = {
            **current.model_dump(mode="json"),
            **changes,
            "version": current.version + 1,
            "updated_at": self._clock(),
            "change_note": note,
        }
        style = _build(data, f"style '{current.id}'")
        self._write(style)
        return style

    def _write(self, style: Style) -> None:
        check_supported(AdjustmentParams().with_values(style.values))
        self._write_files(style, history=True)

    def _write_files(self, style: Style, *, history: bool) -> None:
        folder = self.folder(style.id)
        data = (style.model_dump_json(indent=2) + "\n").encode("utf-8")
        if history:
            self._guard.write_atomic(folder / HISTORY_DIR / f"v{style.version}.json", data)
        self._guard.write_atomic(folder / STYLE_FILE, data)
        self._guard.write_atomic(folder / README_FILE, readme(style).encode("utf-8"))


def slugify(name: str) -> str:
    """'Warm Matte (v2)' → 'warm-matte-v2'; accents folded, at most 40 characters, never empty."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:_MAX_SLUG].rstrip("-")
    return slug or "style"


def diff_styles(a: Style, b: Style) -> StyleDiff:
    names = sorted(set(a.values) | set(b.values))
    values = [
        ValueChange(name=n, before=a.values.get(n), after=b.values.get(n))
        for n in names
        if a.values.get(n) != b.values.get(n)
    ]
    rules_a = {r.type: r.model_dump(mode="json") for r in a.rules}
    rules_b = {r.type: r.model_dump(mode="json") for r in b.rules}
    rules = [
        RuleChange(type=t, before=rules_a.get(t), after=rules_b.get(t))
        for t in sorted(set(rules_a) | set(rules_b))
        if rules_a.get(t) != rules_b.get(t)
    ]
    text_fields = ("name", "description", "best_for", "avoid_on", "test_photo_ids")
    fields = [f for f in text_fields if getattr(a, f) != getattr(b, f)]
    return StyleDiff(
        style_id=b.id,
        a=a.version,
        b=b.version,
        values=values,
        rules=rules,
        fields=fields,
        same_look=a.look_hash() == b.look_hash(),
    )


def readme(style: Style) -> str:
    """The human description next to ``style.json`` (generated; edit the style, not this file)."""
    lines = [
        f"# {style.name}",
        "",
        f"<!-- Generated from style.json (version {style.version}). Edit the style, not this file. -->",
        "",
    ]
    if style.description:
        lines += [style.description, ""]
    lines += _bullets("Best for", style.best_for) + _bullets("Avoid on", style.avoid_on)
    lines += ["## Adaptive rules", ""]
    lines += [f"- {_describe_rule(r.model_dump(mode='json'))}" for r in style.rules] or ["- none"]
    lines += ["", "## Parameters", ""]
    if style.values:
        lines += ["| Parameter | Value |", "|---|---|"]
        lines += [f"| `{name}` | {_format_value(value)} |" for name, value in style.values.items()]
    else:
        lines.append("The style sets no parameters directly.")
    lines += ["", f"Version {style.version}, updated {style.updated_at:%Y-%m-%d %H:%M} UTC.", ""]
    return "\n".join(lines)


def _bullets(title: str, items: Iterable[str]) -> list[str]:
    items = list(items)
    return [f"## {title}", "", *(f"- {i}" for i in items), ""] if items else []


def _describe_rule(rule: dict[str, Any]) -> str:
    settings = ", ".join(
        f"{k} {v}" for k, v in rule.items() if k not in {"type", "rule_version"} and v is not None
    )
    return f"**{rule['type']}**: {settings}"


def _format_value(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(f"({p['x']:g}, {p['y']:g})" for p in value)
    return f"{value:g}" if isinstance(value, float) else str(value)


def _parse(text: str, what: str) -> Style:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidRequestError(
            f"{what}: style.json is not valid JSON ({exc.msg}, line {exc.lineno})"
        ) from exc
    if not isinstance(data, dict):
        raise InvalidRequestError(f"{what}: style.json must hold an object")
    return _build(_migrate(data, what), what)


def _migrate(data: dict[str, Any], what: str) -> dict[str, Any]:
    version = data.get("schema_version", 1)
    if not isinstance(version, int) or version < 1:
        raise InvalidRequestError(f"{what}: schema_version must be a positive whole number")
    if version > STYLE_SCHEMA_VERSION:
        raise InvalidRequestError(
            f"{what} was written by a newer version of the tool (style format {version}; this one reads "
            f"up to {STYLE_SCHEMA_VERSION})"
        )
    while version < STYLE_SCHEMA_VERSION:
        data = MIGRATIONS[version](data)
        version += 1
        data["schema_version"] = version
    return data


def _build(data: dict[str, Any], what: str) -> Style:
    try:
        return Style.model_validate(data)
    except ValidationError as exc:
        error = exc.errors()[0]
        where = ".".join(str(p) for p in error["loc"])
        message = error["msg"].removeprefix("Value error, ")
        raise InvalidRequestError(f"{what}: {where + ': ' if where else ''}{message}") from exc
