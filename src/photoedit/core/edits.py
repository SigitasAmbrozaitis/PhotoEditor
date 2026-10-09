"""Per-photo edits: small JSON files in ``workspace/edits/`` holding only what differs from the defaults.

Effective parameters = source defaults ← style (Phase 4) ← per-photo overrides. Overrides are sparse dotted
names (``{"tone.exposure": 0.5}``), so a later change to the defaults or the style still reaches every
value the user didn't touch.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from photoedit.core.catalog import CatalogPhoto
from photoedit.core.errors import InvalidRequestError
from photoedit.core.render.pipeline import check_supported
from photoedit.core.scan import SourceKind
from photoedit.models import AdjustmentParams
from photoedit.safety import PathGuard

EDIT_SCHEMA_VERSION = 1


class PhotoEditFile(BaseModel):
    """What is stored on disk for one photo."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    photo_id: str
    style_id: str | None = None
    overrides: dict[str, Any] = Field(default_factory=dict)


class EffectiveEdit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    adjustments: AdjustmentParams
    overridden: list[str]
    style_id: str | None
    revision: str = Field(description="Changes whenever the edit changes; used for cache keys and URLs.")


def source_defaults(kind: SourceKind) -> AdjustmentParams:
    """Defaults depend on the source: JPEG/TIFF originals are already sharpened, so they start at 0 (like
    Lightroom); RAWs get the default input sharpening."""
    if kind is SourceKind.RASTER:
        return AdjustmentParams.model_validate({"detail": {"sharpening": {"amount": 0}}})
    return AdjustmentParams()


class EditStore:
    def __init__(self, edits_dir: Path, guard: PathGuard) -> None:
        self._dir = edits_dir
        self._guard = guard

    def path(self, photo_id: str) -> Path:
        return self._dir / f"{photo_id}.json"

    def load(self, photo_id: str) -> PhotoEditFile | None:
        path = self.path(photo_id)
        if not path.is_file():
            return None
        try:
            return PhotoEditFile.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError as exc:
            raise InvalidRequestError(f"edit file {path.name} is invalid: {exc.errors()[0]['msg']}") from exc

    def effective(self, photo: CatalogPhoto) -> EffectiveEdit:
        stored = self.load(photo.id)
        base = source_defaults(photo.kind)
        overrides = stored.overrides if stored else {}
        adjustments = apply_overrides(base, overrides)
        style_id = stored.style_id if stored else None
        return EffectiveEdit(
            adjustments=adjustments,
            overridden=sorted(overrides),
            style_id=style_id,
            revision=revision(style_id, overrides),
        )

    def default(self, photo: CatalogPhoto) -> EffectiveEdit:
        """The unedited state ("before")."""
        return EffectiveEdit(
            adjustments=source_defaults(photo.kind), overridden=[], style_id=None, revision=revision(None, {})
        )

    def save(self, photo: CatalogPhoto, adjustments: AdjustmentParams) -> EffectiveEdit:
        """Store ``adjustments`` as overrides against the defaults. Rejects parameters later phases render."""
        check_supported(adjustments)
        overrides = differences(source_defaults(photo.kind), adjustments)
        stored = self.load(photo.id)
        style_id = stored.style_id if stored else None
        if not overrides and style_id is None:
            self.reset(photo.id)
        else:
            record = PhotoEditFile(photo_id=photo.id, style_id=style_id, overrides=overrides)
            self._guard.write_atomic(self.path(photo.id), record.model_dump_json(indent=2).encode("utf-8"))
        return self.effective(photo)

    def reset(self, photo_id: str) -> None:
        path = self.path(photo_id)
        if path.exists():
            self._guard.assert_writable(path)
            path.unlink()


def differences(base: AdjustmentParams, edited: AdjustmentParams) -> dict[str, Any]:
    """Dotted names and values where ``edited`` differs from ``base`` (lists such as curves are leaf
    values)."""
    out: dict[str, Any] = {}
    _diff(base.model_dump(by_alias=True, mode="json"), edited.model_dump(by_alias=True, mode="json"), "", out)
    return out


def apply_overrides(base: AdjustmentParams, overrides: dict[str, Any]) -> AdjustmentParams:
    """``base`` with dotted overrides applied, validated (unknown names or bad values raise)."""
    data = copy.deepcopy(base.model_dump(by_alias=True, mode="json"))
    for name, value in overrides.items():
        node = data
        *parents, leaf = name.split(".")
        for part in parents:
            if not isinstance(node.get(part), dict):
                raise InvalidRequestError(f"unknown parameter '{name}'")
            node = node[part]
        if leaf not in node:
            raise InvalidRequestError(f"unknown parameter '{name}'")
        node[leaf] = value
    try:
        return AdjustmentParams.model_validate(data)
    except ValidationError as exc:
        error = exc.errors()[0]
        where = ".".join(str(p) for p in error["loc"])
        raise InvalidRequestError(f"invalid edit at {where}: {error['msg']}") from exc


def revision(style_id: str | None, overrides: dict[str, Any]) -> str:
    canonical = json.dumps({"style": style_id, "overrides": overrides}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def _diff(base: Any, edited: Any, prefix: str, out: dict[str, Any]) -> None:
    if isinstance(base, dict) and isinstance(edited, dict):
        for key, value in edited.items():
            _diff(base.get(key), value, f"{prefix}{key}.", out)
    elif base != edited:
        out[prefix.rstrip(".")] = edited
