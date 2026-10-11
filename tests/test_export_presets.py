from __future__ import annotations

import json
from pathlib import Path

import pytest

from photoedit.core.errors import ConflictError, InvalidRequestError, NotFoundError
from photoedit.core.export.presets import PresetLibrary
from photoedit.core.presets import BUILTIN_PRESETS
from photoedit.models.export import ExportSettings, PresetCreate, PresetDuplicate, PresetUpdate
from photoedit.safety import PathGuard, WriteNotAllowedError


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    return tmp_path / "export-presets"


@pytest.fixture
def library(tmp_path: Path, folder: Path) -> PresetLibrary:
    return PresetLibrary(folder, PathGuard(writable_roots=[folder]))


def test_builtins_first_and_read_only(library: PresetLibrary) -> None:
    assert [p.id for p in library.all()] == [p.id for p in BUILTIN_PRESETS]
    assert library.get("web-full").builtin
    with pytest.raises(InvalidRequestError, match="built-in preset and can't be changed; duplicate it"):
        library.update("web-full", PresetUpdate(expected_version=1, name="x"))
    with pytest.raises(InvalidRequestError, match="built-in"):
        library.delete("web-full")


def test_create_get_and_file(library: PresetLibrary, folder: Path) -> None:
    preset = library.create(PresetCreate(name="My Instagram", settings=ExportSettings()))
    assert (preset.id, preset.version, preset.builtin) == ("my-instagram", 1, False)
    assert library.get("my-instagram") == preset
    data = json.loads((folder / "my-instagram.json").read_text(encoding="utf-8"))
    assert "builtin" not in data and "error" not in data and data["name"] == "My Instagram"
    assert [p.id for p in library.all()][-1] == "my-instagram"


def test_ids_never_collide(library: PresetLibrary) -> None:
    assert library.create(PresetCreate(name="Web full")).id == "web-full-2"  # a built-in has "web-full"
    assert library.create(PresetCreate(name="Web full")).id == "web-full-3"


def test_duplicate_builtin_and_custom(library: PresetLibrary) -> None:
    copy = library.duplicate("instagram-portrait")
    assert (copy.id, copy.name, copy.builtin) == (
        "instagram-portrait-4-5-copy",
        "Instagram portrait (4:5) copy",
        False,
    )
    assert copy.settings == library.get("instagram-portrait").settings
    named = library.duplicate(copy.id, PresetDuplicate(name="IG 95"))
    assert (named.id, named.name) == ("ig-95", "IG 95")


def test_update_with_version_check(library: PresetLibrary) -> None:
    preset = library.create(PresetCreate(name="Mine"))
    settings = ExportSettings.model_validate({"file": {"jpeg_quality": 95}})
    updated = library.update(preset.id, PresetUpdate(expected_version=1, settings=settings, description="hi"))
    assert (updated.version, updated.settings.file.jpeg_quality, updated.description, updated.name) == (
        2,
        95,
        "hi",
        "Mine",
    )
    assert library.get(preset.id) == updated
    with pytest.raises(ConflictError, match="version 2, not 1"):
        library.update(preset.id, PresetUpdate(expected_version=1, name="late"))


def test_delete(library: PresetLibrary, folder: Path) -> None:
    preset = library.create(PresetCreate(name="Mine"))
    library.delete(preset.id)
    assert not (folder / "mine.json").exists()
    with pytest.raises(NotFoundError):
        library.get("mine")
    with pytest.raises(NotFoundError):
        library.delete("mine")


def test_broken_file_is_listed_with_its_error(library: PresetLibrary, folder: Path) -> None:
    library.create(PresetCreate(name="Good"))
    (folder / "bad.json").write_text(
        '{"id": "bad", "name": "Bad", "settings": {"file": {"jpeg_quality": 500}}}'
    )
    (folder / "garbage.json").write_text("{not json")
    (folder / "Not A Slug.json").write_text("{}")  # not a preset file name: ignored
    listed = {p.id: p for p in library.all() if not p.builtin}
    assert set(listed) == {"good", "bad", "garbage"}
    assert listed["good"].error is None
    assert "settings.file.jpeg_quality" in (listed["bad"].error or "")
    assert listed["garbage"].error
    with pytest.raises(InvalidRequestError, match="can't be read"):
        library.duplicate("bad")
    library.delete("bad")  # a broken preset can still be deleted


def test_unknown_and_odd_ids(library: PresetLibrary) -> None:
    with pytest.raises(NotFoundError):
        library.get("nope")
    with pytest.raises(NotFoundError):
        library.get("../escape")


def test_writes_outside_the_folder_are_refused(tmp_path: Path, folder: Path) -> None:
    library = PresetLibrary(folder, PathGuard(writable_roots=[tmp_path / "elsewhere"]))
    with pytest.raises(WriteNotAllowedError):
        library.create(PresetCreate(name="Mine"))
