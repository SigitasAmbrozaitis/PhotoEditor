"""Per-photo edits: small JSON files in ``workspace/edits/`` holding a style reference and the photo's tweaks.

Effective parameters = source defaults ← style values ← style rules (on the photo's measurements) ← per-photo
overrides. Overrides are sparse dotted names (``{"tone.exposure": 0.5}``) stored as differences from the
styled values, so a later change to the defaults or the style still reaches every value the user didn't
touch, and moving a slider back to the style's value makes it follow the style again. The style is linked by
id (live link).
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from photoedit.core.catalog import CatalogPhoto
from photoedit.core.errors import InvalidRequestError, NotFoundError
from photoedit.core.events import EventBus
from photoedit.core.geometry import check_geometry, is_identity
from photoedit.core.render.pipeline import check_supported
from photoedit.core.scan import SourceKind
from photoedit.core.style_rules import RuleInputs, resolve, rule_parameters
from photoedit.core.styles import StyleLibrary
from photoedit.models import AdjustmentParams, GroupReference, RuleResult, Style
from photoedit.models.adjustments import Geometry
from photoedit.models.events import EventKind
from photoedit.models.photo import PhotoNote
from photoedit.models.subject import SubjectBox
from photoedit.safety import PathGuard

EDIT_SCHEMA_VERSION = 1

# What the rules need to know about a photo (measurements, as-shot WB, camera EV); asked only when a style has
# rules, because measuring may decode the photo.
type InputsProvider = Callable[[CatalogPhoto], RuleInputs]


class PhotoEditFile(BaseModel):
    """What is stored on disk for one photo."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    photo_id: str
    style_id: str | None = None
    overrides: dict[str, Any] = Field(default_factory=dict)
    group: GroupReference | None = None
    # The main subject set by hand (upright coordinates). It frames crops but changes no pixels, so it is kept
    # out of the overrides and the revision.
    subject: SubjectBox | None = None
    # Claude's note (P7.7): text only, so it stays out of the overrides and the revision too.
    note: PhotoNote | None = None


class EffectiveEdit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    adjustments: AdjustmentParams
    overridden: list[str]
    style_id: str | None
    revision: str = Field(description="Changes whenever the edit changes; used for cache keys and URLs.")
    base: AdjustmentParams | None = Field(
        default=None, description="The parameters before the photo's own tweaks (defaults + style)."
    )
    style_values: list[str] = Field(default_factory=list)
    rules: list[RuleResult] = Field(default_factory=list)
    style_version: int | None = None
    style_error: str | None = None
    group: GroupReference | None = None


def source_defaults(kind: SourceKind) -> AdjustmentParams:
    """Defaults depend on the source: JPEG/TIFF originals are already sharpened, so they start at 0 (like
    Lightroom); RAWs get the default input sharpening."""
    if kind is SourceKind.RASTER:
        return AdjustmentParams.model_validate({"detail": {"sharpening": {"amount": 0}}})
    return AdjustmentParams()


class _Styled(BaseModel):
    """The photo's parameters before its overrides: defaults, or defaults + its style."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    adjustments: AdjustmentParams
    style_values: list[str] = Field(default_factory=list)
    rules: list[RuleResult] = Field(default_factory=list)
    style_version: int | None = None
    style_error: str | None = None


class EditStore:
    def __init__(
        self,
        edits_dir: Path,
        guard: PathGuard,
        *,
        styles: StyleLibrary | None = None,
        inputs: InputsProvider | None = None,
        events: EventBus | None = None,
    ) -> None:
        self._events = events or EventBus()
        self._dir = edits_dir
        self._guard = guard
        self._styles = styles
        self._inputs = inputs

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
        stored = self.load(photo.id) or PhotoEditFile(photo_id=photo.id)
        styled = self._styled(photo, stored.style_id, stored.group)
        adjustments = apply_overrides(styled.adjustments, stored.overrides)
        resolved = styled.adjustments if stored.style_id and styled.style_error is None else None
        return EffectiveEdit(
            adjustments=adjustments,
            overridden=sorted(stored.overrides),
            style_id=stored.style_id,
            revision=revision(stored.style_id, stored.overrides, resolved),
            base=styled.adjustments,
            style_values=styled.style_values,
            rules=styled.rules,
            style_version=styled.style_version,
            style_error=styled.style_error,
            group=stored.group,
        )

    def default(self, photo: CatalogPhoto) -> EffectiveEdit:
        """The unedited state ("before"): no style, no overrides."""
        return EffectiveEdit(
            adjustments=source_defaults(photo.kind), overridden=[], style_id=None, revision=revision(None, {})
        )

    def before(self, photo: CatalogPhoto, geometry: Geometry) -> EffectiveEdit:
        """The "before" view of an edit: the photo's defaults with the edit's geometry, so before and after
        frame the same picture."""
        default = self.default(photo)
        if is_identity(geometry):
            return default
        adjustments = default.adjustments.model_copy(update={"geometry": geometry})
        overrides = differences(default.adjustments, adjustments)
        return EffectiveEdit(
            adjustments=adjustments, overridden=[], style_id=None, revision=revision(None, overrides)
        )

    def save(self, photo: CatalogPhoto, adjustments: AdjustmentParams) -> EffectiveEdit:
        """Store ``adjustments`` as overrides against the styled values. Rejects later-phase parameters and
        geometry that doesn't fit the photo."""
        check_supported(adjustments)
        check_geometry(adjustments.geometry, photo.width, photo.height)
        stored = self.load(photo.id) or PhotoEditFile(photo_id=photo.id)
        styled = self._styled(photo, stored.style_id, stored.group)
        overrides = differences(styled.adjustments, adjustments)
        self._store(stored.model_copy(update={"overrides": overrides}))
        return self.effective(photo)

    def reset_overrides(self, photo: CatalogPhoto) -> EffectiveEdit:
        """Drop the per-photo tweaks; the style (and its group) and a manual subject stay."""
        stored = self.load(photo.id) or PhotoEditFile(photo_id=photo.id)
        self._store(stored.model_copy(update={"overrides": {}}))
        return self.effective(photo)

    def apply_style(
        self, photo: CatalogPhoto, style_id: str | None, *, group: GroupReference | None = None
    ) -> EffectiveEdit:
        """Give the photo ``style_id`` (None removes its style) and the ``group`` it was evened out with.

        Tweaks of parameters the new style sets (its values, plus what its rules set) are dropped so the
        style's value shows; other tweaks keep their values. Removing a style keeps every tweak as it is.
        """
        stored = self.load(photo.id) or PhotoEditFile(photo_id=photo.id)
        current = self.effective(photo)
        kept = dict(stored.overrides)
        if style_id is not None:
            style = self._library().get(style_id)  # NotFoundError for an unknown style
            replaced = rule_parameters(style)
            kept = {n: v for n, v in kept.items() if n not in replaced}
        new = PhotoEditFile(
            photo_id=photo.id, style_id=style_id, group=group if style_id else None, subject=stored.subject
        )
        styled = self._styled(photo, new.style_id, new.group)
        if styled.style_error is not None:
            raise InvalidRequestError(styled.style_error)
        # Kept tweaks keep the value the photo showed; drop the ones the new base already has.
        shown = current.adjustments.dotted(kept)
        base = styled.adjustments.dotted(kept)
        self._store(new.model_copy(update={"overrides": {n: v for n, v in shown.items() if base[n] != v}}))
        return self.effective(photo)

    def styled_edit(
        self, photo: CatalogPhoto, style: Style, *, group: GroupReference | None = None
    ) -> EffectiveEdit:
        """``style`` (any version, applied or not) on ``photo`` without its tweaks: for samples, reports and
        comparing versions. Raises if the style can't be used."""
        styled = self._styled_with(photo, style, group)
        return EffectiveEdit(
            adjustments=styled.adjustments,
            overridden=[],
            style_id=style.id,
            revision=revision(style.id, {}, styled.adjustments),
            style_values=styled.style_values,
            rules=styled.rules,
            style_version=style.version,
            group=group,
        )

    def subject(self, photo_id: str) -> SubjectBox | None:
        """The subject box set by hand, if any."""
        stored = self.load(photo_id)
        return stored.subject if stored is not None else None

    def set_subject(self, photo: CatalogPhoto, box: SubjectBox | None) -> None:
        """Set the photo's subject by hand (None = use the detected one). The revision stays the same."""
        stored = self.load(photo.id) or PhotoEditFile(photo_id=photo.id)
        self._store(stored.model_copy(update={"subject": box}))

    def note(self, photo_id: str) -> PhotoNote | None:
        stored = self.load(photo_id)
        return stored.note if stored is not None else None

    def set_note(self, photo: CatalogPhoto, note: PhotoNote | None) -> None:
        """Set or (None) remove Claude's note. The revision stays the same."""
        stored = self.load(photo.id) or PhotoEditFile(photo_id=photo.id)
        self._store(stored.model_copy(update={"note": note}))

    def reset(self, photo_id: str) -> None:
        """Forget the photo's edit entirely (style, group, tweaks, subject and note)."""
        self._delete(photo_id)
        self._events.publish(EventKind.PHOTO_EDIT, [photo_id])

    # ---- internals

    def _store(self, record: PhotoEditFile) -> None:
        if (
            not record.overrides
            and record.style_id is None
            and record.subject is None
            and record.note is None
        ):
            self._delete(record.photo_id)
        else:
            # Leave out keys that are unset, so files look as they did before groups, subjects and notes.
            unset = {name for name in ("group", "subject", "note") if getattr(record, name) is None}
            data = record.model_dump_json(indent=2, exclude=unset or None)
            self._guard.write_atomic(self.path(record.photo_id), data.encode("utf-8"))
        self._events.publish(EventKind.PHOTO_EDIT, [record.photo_id])

    def _delete(self, photo_id: str) -> None:
        path = self.path(photo_id)
        if path.exists():
            self._guard.assert_writable(path)
            path.unlink()

    def _library(self) -> StyleLibrary:
        if self._styles is None:
            raise InvalidRequestError("styles are not available here (no style library configured)")
        return self._styles

    def _styled(self, photo: CatalogPhoto, style_id: str | None, group: GroupReference | None) -> _Styled:
        defaults = source_defaults(photo.kind)
        if style_id is None:
            return _Styled(adjustments=defaults)
        try:
            return self._styled_with(photo, self._library().get(style_id), group)
        except (NotFoundError, InvalidRequestError, ValueError) as exc:
            # A missing or broken style must never break the Library: render unstyled and say why.
            return _Styled(adjustments=defaults, style_error=f"style '{style_id}' is not applied: {exc}")

    def _styled_with(self, photo: CatalogPhoto, style: Style, group: GroupReference | None) -> _Styled:
        if style.rules and self._inputs is not None:
            inputs = replace(self._inputs(photo), group=group)
        else:
            inputs = RuleInputs(stats=None, as_shot=None, group=group)
        resolved = resolve(source_defaults(photo.kind), style, inputs)
        return _Styled(
            adjustments=resolved.adjustments,
            style_values=resolved.style_values,
            rules=resolved.results,
            style_version=style.version,
        )


def differences(base: AdjustmentParams, edited: AdjustmentParams) -> dict[str, Any]:
    """Dotted names and values where ``edited`` differs from ``base`` (lists such as curves are leaf
    values)."""
    out: dict[str, Any] = {}
    _diff(base.model_dump(by_alias=True, mode="json"), edited.model_dump(by_alias=True, mode="json"), "", out)
    return out


def apply_overrides(base: AdjustmentParams, overrides: dict[str, Any]) -> AdjustmentParams:
    """``base`` with dotted overrides applied, validated (unknown names or bad values raise)."""
    try:
        return base.with_values(overrides)
    except ValidationError as exc:
        error = exc.errors()[0]
        where = ".".join(str(p) for p in error["loc"])
        raise InvalidRequestError(f"invalid edit at {where}: {error['msg']}") from exc
    except ValueError as exc:
        raise InvalidRequestError(str(exc)) from exc


def merge_patch(
    current: AdjustmentParams, base: AdjustmentParams, patch: Mapping[str, Any]
) -> AdjustmentParams:
    """``current`` with a nested patch of only the values to change (``{"tone": {"exposure": 0.3}}``),
    validated as a whole. ``None`` puts a value back to ``base`` (the photo's values before its own tweaks:
    the defaults, or its style's). Unknown names and bad values raise naming the parameter."""
    if not patch:
        raise InvalidRequestError("nothing to change: the patch is empty")
    data = current.model_dump(by_alias=True, mode="json")
    _merge(data, base.model_dump(by_alias=True, mode="json"), patch, "")
    try:
        return AdjustmentParams.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in error['loc'])}: {error['msg']}" for error in exc.errors()[:5]
        )
        raise InvalidRequestError(f"invalid edit: {problems}") from exc


def _merge(node: dict[str, Any], base: dict[str, Any], patch: Mapping[str, Any], prefix: str) -> None:
    for key, value in patch.items():
        name = f"{prefix}{key}"
        if key not in node:
            raise InvalidRequestError(f"unknown parameter '{name}'")
        if value is None:
            node[key] = copy.deepcopy(base[key])
        elif isinstance(value, Mapping) and isinstance(node[key], dict):
            _merge(node[key], base[key], value, f"{name}.")
        else:
            node[key] = copy.deepcopy(value)


def revision(style_id: str | None, overrides: dict[str, Any], styled: AdjustmentParams | None = None) -> str:
    """Changes whenever the rendered edit changes. A styled edit hashes the resolved style parameters, so a
    new look or a different rule result re-renders and a renamed style doesn't. Unstyled edits hash as
    before."""
    content: dict[str, Any] = {"style": style_id, "overrides": overrides}
    if styled is not None:
        content["styled"] = styled.model_dump(by_alias=True, mode="json")
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def _diff(base: Any, edited: Any, prefix: str, out: dict[str, Any]) -> None:
    if isinstance(base, dict) and isinstance(edited, dict):
        for key, value in edited.items():
            _diff(base.get(key), value, f"{prefix}{key}.", out)
    elif base != edited:
        out[prefix.rstrip(".")] = copy.deepcopy(edited)
