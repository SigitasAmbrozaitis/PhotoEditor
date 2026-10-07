from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

import pytest

from photoedit.core.catalog import (
    SCHEMA_VERSION,
    Catalog,
    CatalogError,
    CatalogPhoto,
    FolderRecord,
    photo_id,
)
from photoedit.core.scan import SourceKind
from photoedit.models import PhotoSort, SortOrder
from photoedit.safety import PathGuard, WriteNotAllowedError


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path / "workspace"


@pytest.fixture
def catalog(workspace: Path) -> Catalog:
    return Catalog(workspace / "catalog.sqlite", PathGuard(writable_roots=[workspace]))


PHOTOS = Path("C:/photos/day1") if Path("C:/").exists() else Path("/photos/day1")


def _sha(n: int) -> str:
    return f"{n:016x}" + "ab" * 24  # the id is the first 16 hex digits, so n must be there


def _photo(n: int, path: Path | None = None, **fields: object) -> CatalogPhoto:
    sha = _sha(n)
    data: dict[str, object] = {
        "id": photo_id(sha),
        "sha256": sha,
        "path": path or PHOTOS / f"DSCF{n:04d}.RAF",
        "kind": SourceKind.RAW,
        "file_size": 1000 + n,
        "mtime_ns": 10**18 + n,
        "width": 6240,
        "height": 4160,
    }
    data.update(fields)
    return CatalogPhoto.model_validate(data)


def test_new_catalog_has_current_schema(catalog: Catalog) -> None:
    with sqlite3.connect(catalog.path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_catalog_file_must_be_writable(tmp_path: Path) -> None:
    with pytest.raises(WriteNotAllowedError):
        Catalog(tmp_path / "elsewhere" / "catalog.sqlite", PathGuard(writable_roots=[tmp_path / "workspace"]))


def test_newer_schema_is_refused(catalog: Catalog, workspace: Path) -> None:
    catalog.close()
    with sqlite3.connect(workspace / "catalog.sqlite") as db:
        db.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    with pytest.raises(CatalogError, match="newer PhotoEditor"):
        Catalog(workspace / "catalog.sqlite", PathGuard(writable_roots=[workspace]))


def test_reopening_keeps_data(catalog: Catalog, workspace: Path) -> None:
    catalog.upsert(_photo(1))
    catalog.close()
    again = Catalog(workspace / "catalog.sqlite", PathGuard(writable_roots=[workspace]))
    assert again.get(photo_id(_sha(1))) == _photo(1)


def test_insert_and_get(catalog: Catalog) -> None:
    photo = _photo(
        1,
        sidecar_jpeg=PHOTOS / "DSCF0001.JPG",
        captured_at=datetime(2026, 8, 11, 6, 2, 51),
        camera="FUJIFILM X-T3",
        iso=6400,
        aperture=4.5,
        rating=3,
    )
    catalog.upsert(photo)
    assert catalog.get(photo.id) == photo
    assert catalog.get_by_path(photo.path) == photo
    assert catalog.get("nope") is None


def test_lookup_by_path_ignores_case_on_windows(catalog: Catalog) -> None:
    catalog.upsert(_photo(1))
    found = catalog.get_by_path(Path(str(PHOTOS / "DSCF0001.RAF").upper()))
    assert (found is not None) == (Path("A") == Path("a"))  # case-insensitive only where the OS is


def test_reimport_updates_facts_but_keeps_rating(catalog: Catalog) -> None:
    catalog.upsert(_photo(1, rating=4, camera="old"))
    catalog.upsert(_photo(1, rating=0, camera="new", mtime_ns=5))
    stored = catalog.get(photo_id(_sha(1)))
    assert stored is not None
    assert (stored.camera, stored.mtime_ns, stored.rating) == ("new", 5, 4)


def test_moved_file_keeps_its_id(catalog: Catalog) -> None:
    catalog.upsert(_photo(1))
    moved = PHOTOS.parent / "renamed" / "DSCF0001.RAF"
    catalog.upsert(_photo(1, path=moved))
    stored = catalog.get(photo_id(_sha(1)))
    assert stored is not None and stored.path == moved
    assert catalog.get_by_path(PHOTOS / "DSCF0001.RAF") is None


def test_changed_content_at_same_path_replaces_the_old_row(catalog: Catalog) -> None:
    path = PHOTOS / "edited.jpg"
    catalog.upsert(_photo(1, path=path))
    catalog.upsert(_photo(2, path=path))
    assert catalog.get(photo_id(_sha(1))) is None
    assert catalog.get_by_path(path) == _photo(2, path=path)


def test_list_scope_recursive_and_not(catalog: Catalog) -> None:
    catalog.upsert(_photo(1))
    catalog.upsert(_photo(2, path=PHOTOS / "sub" / "a.RAF"))
    catalog.upsert(_photo(3, path=PHOTOS.parent / "day1_extra" / "b.RAF"))  # shares the name prefix only
    ids = lambda page: [p.id for p in page[0]]  # noqa: E731
    assert ids(catalog.page(PHOTOS)) == [photo_id(_sha(1))]
    assert sorted(ids(catalog.page(PHOTOS, recursive=True))) == sorted([photo_id(_sha(1)), photo_id(_sha(2))])
    assert catalog.count(PHOTOS, recursive=True) == 2


def test_list_filters_sorts_and_pages(catalog: Catalog) -> None:
    catalog.upsert(_photo(1, path=PHOTOS / "c.RAF", rating=1, captured_at=datetime(2026, 8, 11, 9)))
    catalog.upsert(_photo(2, path=PHOTOS / "a.RAF", rating=5, captured_at=datetime(2026, 8, 11, 7)))
    catalog.upsert(_photo(3, path=PHOTOS / "B.RAF", rating=3, captured_at=None))
    catalog.upsert(
        _photo(4, path=PHOTOS / "d.RAF", rating=3, captured_at=datetime(2026, 8, 11, 8), style_id="s1")
    )

    def names(**kwargs: object) -> list[str]:
        return [p.path.name for p in catalog.page(PHOTOS, **kwargs)[0]]  # type: ignore[arg-type]

    assert names() == ["a.RAF", "d.RAF", "c.RAF", "B.RAF"]  # by date, undated last
    assert names(order=SortOrder.DESC) == ["B.RAF", "c.RAF", "d.RAF", "a.RAF"]
    assert names(sort=PhotoSort.NAME) == ["a.RAF", "B.RAF", "c.RAF", "d.RAF"]
    assert names(sort=PhotoSort.RATING, order=SortOrder.DESC) == ["a.RAF", "d.RAF", "B.RAF", "c.RAF"]
    assert names(min_rating=3) == ["a.RAF", "d.RAF", "B.RAF"]
    assert names(style_id="s1") == ["d.RAF"]
    assert names(style_id="none", sort=PhotoSort.NAME) == ["a.RAF", "B.RAF", "c.RAF"]
    items, total = catalog.page(PHOTOS, sort=PhotoSort.NAME, offset=1, limit=2)
    assert [p.path.name for p in items] == ["B.RAF", "c.RAF"] and total == 4


def test_mark_missing_hides_unseen_photos(catalog: Catalog) -> None:
    for n in (1, 2, 3):
        catalog.upsert(_photo(n))
    catalog.upsert(_photo(4, path=PHOTOS / "sub" / "x.RAF"))
    flagged = catalog.mark_missing(
        PHOTOS, recursive=False, present_ids={photo_id(_sha(1)), photo_id(_sha(3))}
    )
    assert flagged == 1
    assert catalog.count(PHOTOS) == 2
    assert catalog.count(PHOTOS, recursive=True) == 3  # the subfolder photo was out of scope
    hidden = catalog.get(photo_id(_sha(2)))
    assert hidden is not None and hidden.missing
    catalog.upsert(_photo(2))  # found again on a later import
    assert catalog.count(PHOTOS) == 3


def test_folders_and_state(catalog: Catalog) -> None:
    assert catalog.folders() == []
    first = FolderRecord(path=PHOTOS, include_subfolders=False, last_imported_at=datetime(2026, 10, 7, 9))
    second = FolderRecord(
        path=PHOTOS.parent / "b", include_subfolders=True, last_imported_at=datetime(2026, 10, 7, 10)
    )
    catalog.save_folder(first)
    catalog.save_folder(second)
    assert catalog.folders() == [second, first]  # most recent first
    catalog.save_folder(first.model_copy(update={"include_subfolders": True}))
    stored = catalog.get_folder(PHOTOS)
    assert stored is not None and stored.include_subfolders
    assert catalog.get_state("current_folder") is None
    catalog.set_state("current_folder", str(PHOTOS))
    catalog.set_state("current_folder", str(PHOTOS.parent / "b"))
    assert catalog.get_state("current_folder") == str(PHOTOS.parent / "b")


def test_failed_write_rolls_back(catalog: Catalog) -> None:
    catalog.upsert(_photo(1))
    with pytest.raises(sqlite3.IntegrityError):
        # Same sha256, different id: violates the UNIQUE constraint, nothing must be half-written.
        catalog.upsert(_photo(1).model_copy(update={"id": "different", "path": PHOTOS / "other.RAF"}))
    assert catalog.get_by_path(PHOTOS / "other.RAF") is None
    assert catalog.count(PHOTOS) == 1


def test_parallel_writers(catalog: Catalog) -> None:
    def write(start: int) -> None:
        for n in range(start, start + 25):
            catalog.upsert(_photo(n))

    threads = [threading.Thread(target=write, args=(i * 100,)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert catalog.count(PHOTOS) == 100


def test_to_photo_maps_to_the_api_model(catalog: Catalog) -> None:
    photo = _photo(7, sidecar_jpeg=PHOTOS / "DSCF0007.JPG", rating=2).to_photo()
    assert photo.id == photo_id(_sha(7))
    assert photo.filename == "DSCF0007.RAF"
    assert photo.folder == PHOTOS.as_posix()
    assert photo.sidecar_jpeg == (PHOTOS / "DSCF0007.JPG").as_posix()
    assert (photo.width, photo.height, photo.rating, photo.style_id) == (6240, 4160, 2, None)
