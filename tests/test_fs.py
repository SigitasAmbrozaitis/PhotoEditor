from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from helpers import write_jpeg
from photoedit.core.errors import InvalidRequestError, NotFoundError
from photoedit.core.fs import list_dirs


def test_lists_subfolders_sorted_with_photo_counts(tmp_path: Path) -> None:
    write_jpeg(tmp_path / "Beta" / "a.jpg", (1, 1, 1))
    (tmp_path / "Beta" / "a.RAF").write_bytes(b"raw")  # pairs with a.jpg: still one photo
    (tmp_path / "alpha").mkdir()
    (tmp_path / "loose.jpg").write_bytes(b"x")
    listing = list_dirs(tmp_path)
    assert [(e.name, e.photo_count) for e in listing.entries] == [("alpha", 0), ("Beta", 1)]
    assert listing.photo_count == 1
    assert listing.entries[1].path == (tmp_path / "Beta").resolve().as_posix()


def test_dot_and_dollar_folders_are_hidden(tmp_path: Path) -> None:
    for name in (".git", "$RECYCLE.BIN", "visible"):
        (tmp_path / name).mkdir()
    assert [e.name for e in list_dirs(tmp_path).entries] == ["visible"]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows hidden attribute")
def test_windows_hidden_folders_are_hidden(tmp_path: Path) -> None:
    (tmp_path / "secret").mkdir()
    (tmp_path / "shown").mkdir()
    subprocess.run(["attrib", "+h", str(tmp_path / "secret")], check=True)
    assert [e.name for e in list_dirs(tmp_path).entries] == ["shown"]


def test_parent_of_a_drive_root_is_none() -> None:
    root = Path(Path.cwd().anchor)
    listing = list_dirs(root)
    assert listing.parent is None


def test_roots() -> None:
    listing = list_dirs(None)
    assert listing.path is None and listing.parent is None and listing.entries
    if sys.platform == "win32":
        assert any(e.name.upper().startswith("C:") for e in listing.entries)


def test_errors(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError):
        list_dirs(tmp_path / "missing")
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    with pytest.raises(InvalidRequestError, match="not a folder"):
        list_dirs(tmp_path / "f.txt")
    with pytest.raises(InvalidRequestError, match="absolute"):
        list_dirs(Path("relative"))
