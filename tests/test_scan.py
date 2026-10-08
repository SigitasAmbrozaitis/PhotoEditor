from __future__ import annotations

from pathlib import Path

import pytest

from photoedit.core.scan import ScanError, SourceKind, scan_folder


def _touch(folder: Path, *names: str) -> None:
    for name in names:
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")


def _names(paths: list[Path]) -> list[str]:
    return [p.name for p in paths]


def test_raw_and_jpeg_with_same_name_are_one_photo(tmp_path: Path) -> None:
    _touch(tmp_path, "DSCF0001.RAF", "DSCF0001.JPG")
    result = scan_folder(tmp_path)
    assert len(result.photos) == 1
    photo = result.photos[0]
    assert photo.kind is SourceKind.RAW
    assert photo.path.name == "DSCF0001.RAF"
    assert photo.sidecar_jpeg is not None and photo.sidecar_jpeg.name == "DSCF0001.JPG"


def test_pairing_ignores_case(tmp_path: Path) -> None:
    _touch(tmp_path, "dscf0002.raf", "DSCF0002.jpeg")
    (photo,) = scan_folder(tmp_path).photos
    assert photo.sidecar_jpeg is not None and photo.sidecar_jpeg.name == "DSCF0002.jpeg"


def test_lone_files_stand_alone(tmp_path: Path) -> None:
    _touch(tmp_path, "a.RAF", "b.jpg", "c.tif", "d.TIFF")
    result = scan_folder(tmp_path)
    assert [(p.path.name, p.kind) for p in result.photos] == [
        ("a.RAF", SourceKind.RAW),
        ("b.jpg", SourceKind.RASTER),
        ("c.tif", SourceKind.RASTER),
        ("d.TIFF", SourceKind.RASTER),
    ]
    assert all(p.sidecar_jpeg is None for p in result.photos)


def test_tiff_next_to_raw_is_its_own_photo(tmp_path: Path) -> None:
    _touch(tmp_path, "e.RAF", "e.tif")
    result = scan_folder(tmp_path)
    assert _names([p.path for p in result.photos]) == ["e.RAF", "e.tif"]
    assert result.photos[0].sidecar_jpeg is None


def test_only_first_raw_gets_the_sidecar(tmp_path: Path) -> None:
    _touch(tmp_path, "f.DNG", "f.RAF", "f.JPG", "f.jpeg")
    result = scan_folder(tmp_path)
    by_name = {p.path.name: p for p in result.photos}
    # Sorted case-insensitively, f.jpeg comes before f.JPG.
    assert set(by_name) == {"f.DNG", "f.RAF", "f.JPG"}
    assert by_name["f.DNG"].sidecar_jpeg is not None and by_name["f.DNG"].sidecar_jpeg.name == "f.jpeg"
    assert by_name["f.RAF"].sidecar_jpeg is None


def test_unsupported_and_hidden_files_are_skipped_with_reason(tmp_path: Path) -> None:
    _touch(tmp_path, "clip.MOV", "notes", ".hidden.jpg", "g.RAF")
    result = scan_folder(tmp_path)
    assert _names([p.path for p in result.photos]) == ["g.RAF"]
    reasons = {s.path.name: s.reason for s in result.skipped}
    assert reasons == {
        "clip.MOV": "unsupported file type (.mov)",
        "notes": "unsupported file type (no extension)",
        ".hidden.jpg": "hidden file",
    }


def test_subfolders_only_when_recursive(tmp_path: Path) -> None:
    _touch(tmp_path, "top.jpg", "day2/inner.RAF", "day2/inner.JPG", "day2/deeper/x.jpg", ".git/y.jpg")
    assert _names([p.path for p in scan_folder(tmp_path).photos]) == ["top.jpg"]
    recursive = scan_folder(tmp_path, recursive=True)
    assert sorted(_names([p.path for p in recursive.photos])) == ["inner.RAF", "top.jpg", "x.jpg"]


def test_same_name_in_different_folders_is_not_paired(tmp_path: Path) -> None:
    _touch(tmp_path, "a/h.RAF", "b/h.JPG")
    result = scan_folder(tmp_path, recursive=True)
    assert [(p.path.name, p.sidecar_jpeg) for p in result.photos] == [("h.RAF", None), ("h.JPG", None)]


def test_results_are_absolute_and_sorted(tmp_path: Path) -> None:
    _touch(tmp_path, "b.jpg", "A.jpg", "c.jpg")
    result = scan_folder(tmp_path)
    assert _names([p.path for p in result.photos]) == ["A.jpg", "b.jpg", "c.jpg"]
    assert all(p.path.is_absolute() for p in result.photos)
    assert result.folder == tmp_path.resolve()


def test_empty_folder(tmp_path: Path) -> None:
    result = scan_folder(tmp_path)
    assert result.photos == [] and result.skipped == []


def test_scanning_does_not_change_the_folder(tmp_path: Path) -> None:
    _touch(tmp_path, "i.RAF", "i.JPG", "j.mov")
    before = {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in tmp_path.iterdir()}
    scan_folder(tmp_path, recursive=True)
    after = {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in tmp_path.iterdir()}
    assert after == before


@pytest.mark.parametrize(
    ("make_path", "message"),
    [
        (lambda tmp: tmp / "missing", "folder not found"),
        (lambda tmp: tmp / "file.jpg", "not a folder"),
        (lambda tmp: Path("relative/folder"), "must be absolute"),
    ],
)
def test_bad_folders_raise_clear_errors(tmp_path: Path, make_path: object, message: str) -> None:
    _touch(tmp_path, "file.jpg")
    path = make_path(tmp_path)  # type: ignore[operator]
    with pytest.raises(ScanError, match=message):
        scan_folder(path)
