"""Export presets: the built-in ones (read-only, in code) and the user's own in ``export-presets/<id>.json``.

All writes are atomic and go through the path guard. A custom preset file that can't be read is listed with
its error, so one bad file never hides the others.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from pydantic import ValidationError

from photoedit.core.errors import ConflictError, InvalidRequestError, NotFoundError
from photoedit.core.presets import BUILTIN_PRESETS
from photoedit.core.styles import slugify
from photoedit.models.export import ExportPreset, PresetCreate, PresetDuplicate, PresetUpdate
from photoedit.safety import PathGuard

_SUFFIX = ".json"


class PresetLibrary:
    def __init__(
        self, folder: Path, guard: PathGuard, builtins: tuple[ExportPreset, ...] = BUILTIN_PRESETS
    ) -> None:
        self._folder = folder
        self._guard = guard
        self._builtins = {p.id: p for p in builtins}
        self._lock = threading.Lock()

    def all(self) -> list[ExportPreset]:
        """Built-ins first (in their own order), then custom presets by name."""
        custom = sorted(self._custom(), key=lambda p: (p.name.lower(), p.id))
        return [*self._builtins.values(), *custom]

    def get(self, preset_id: str) -> ExportPreset:
        if preset_id in self._builtins:
            return self._builtins[preset_id]
        path = self._path(preset_id)
        if not path.is_file():
            raise NotFoundError(f"export preset '{preset_id}' not found")
        return self._read(path)

    def create(self, request: PresetCreate) -> ExportPreset:
        with self._lock:
            preset = ExportPreset(
                id=self._free_id(slugify(request.name)),
                name=request.name,
                description=request.description,
                target=request.target,
                settings=request.settings,
            )
            self._write(preset)
            return preset

    def duplicate(self, preset_id: str, request: PresetDuplicate | None = None) -> ExportPreset:
        source = self.get(preset_id)
        if source.error is not None:
            raise InvalidRequestError(f"export preset '{preset_id}' can't be read: {source.error}")
        name = request.name if request is not None and request.name else f"{source.name} copy"
        return self.create(
            PresetCreate(
                name=name, description=source.description, target=source.target, settings=source.settings
            )
        )

    def update(self, preset_id: str, update: PresetUpdate) -> ExportPreset:
        self._editable(preset_id)
        with self._lock:
            current = self.get(preset_id)
            if current.error is not None:
                raise InvalidRequestError(f"export preset '{preset_id}' can't be read: {current.error}")
            if current.version != update.expected_version:
                raise ConflictError(
                    f"export preset '{preset_id}' is at version {current.version}, not "
                    f"{update.expected_version}; reload it and try again"
                )
            changes = update.model_dump(exclude_unset=True, exclude={"expected_version"})
            changes = {k: v for k, v in changes.items() if v is not None}
            if "settings" in changes:
                changes["settings"] = update.settings
            preset = current.model_copy(update={**changes, "version": current.version + 1})
            self._write(ExportPreset.model_validate(preset.model_dump()))
            return preset

    def delete(self, preset_id: str) -> None:
        self._editable(preset_id)
        path = self._path(preset_id)
        if not path.is_file():
            raise NotFoundError(f"export preset '{preset_id}' not found")
        self._guard.assert_writable(path)
        path.unlink()

    # ---- internals

    def _editable(self, preset_id: str) -> None:
        if preset_id in self._builtins:
            raise InvalidRequestError(
                f"'{self._builtins[preset_id].name}' is a built-in preset and can't be changed; "
                "duplicate it first"
            )

    def _custom(self) -> list[ExportPreset]:
        if not self._folder.is_dir():
            return []
        paths = sorted(self._folder.glob(f"*{_SUFFIX}"))
        return [self._read(path) for path in paths if slugify(path.stem) == path.stem]

    def _path(self, preset_id: str) -> Path:
        if slugify(preset_id) != preset_id:
            raise NotFoundError(f"export preset '{preset_id}' not found")
        return self._folder / f"{preset_id}{_SUFFIX}"

    def _read(self, path: Path) -> ExportPreset:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            preset = ExportPreset.model_validate({**data, "builtin": False})
        except ValidationError as exc:
            problems = (f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:3])
            return self._broken(path, "; ".join(problems))
        except (OSError, ValueError) as exc:
            return self._broken(path, str(exc))
        if preset.id != path.stem:
            return preset.model_copy(
                update={"error": f"the file is named {path.name} but holds '{preset.id}'"}
            )
        return preset

    def _broken(self, path: Path, reason: str) -> ExportPreset:
        return ExportPreset(id=path.stem, name=path.stem, error=reason)

    def _write(self, preset: ExportPreset) -> None:
        data = preset.model_dump(mode="json", exclude={"builtin", "error"})
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        self._guard.write_atomic(self._path(preset.id), text.encode("utf-8"))

    def _free_id(self, base: str) -> str:
        taken = set(self._builtins)
        if self._folder.is_dir():
            taken |= {p.stem for p in self._folder.glob(f"*{_SUFFIX}")}
        candidate, n = base, 2
        while candidate in taken:
            candidate, n = f"{base}-{n}", n + 1
        return candidate
