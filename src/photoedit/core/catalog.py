"""The photo catalog: a SQLite index of imported photos (path, content hash, metadata).

Only paths and facts about the originals are stored, never the originals themselves. The catalog is a cache of
what the files say plus a few user facts (rating); it can always be rebuilt by importing again.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from photoedit.core.metadata import camera_ev, parse_shutter
from photoedit.core.scan import SourceKind
from photoedit.models import Photo, PhotoSort, SortOrder
from photoedit.safety import PathGuard

SCHEMA_VERSION = 4
ID_LENGTH = 16  # hex digits of the SHA-256 used as photo id: 64 bits, collisions are not a practical concern

_SCHEMA = """
CREATE TABLE folders (
    path_key TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    include_subfolders INTEGER NOT NULL,
    last_imported_at TEXT
);
CREATE TABLE photos (
    id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL UNIQUE,
    path TEXT NOT NULL,
    path_key TEXT NOT NULL UNIQUE,
    parent_key TEXT NOT NULL,
    filename TEXT NOT NULL,
    kind TEXT NOT NULL,
    sidecar_jpeg TEXT,
    file_size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    captured_at TEXT,
    camera TEXT,
    lens TEXT,
    iso INTEGER,
    shutter TEXT,
    aperture REAL,
    focal_length REAL,
    orientation INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    rating INTEGER NOT NULL DEFAULT 0,
    style_id TEXT,
    missing INTEGER NOT NULL DEFAULT 0,
    has_edits INTEGER NOT NULL DEFAULT 0,
    edit_revision TEXT,
    as_shot_temperature REAL,
    as_shot_tint REAL,
    film_simulation TEXT,
    dynamic_range INTEGER,
    tone_black REAL,
    tone_white REAL,
    tone_anchors_identity TEXT,
    tone_middle REAL,
    neutral_temperature REAL,
    neutral_tint REAL,
    exposure_time REAL
);
CREATE INDEX photos_parent ON photos (parent_key);
CREATE TABLE state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def _v1_to_v2(db: sqlite3.Connection) -> None:
    # Phase 3: edit flag, as-shot white balance and Fujifilm look settings. Photos imported before get the
    # new facts on their next (incremental) re-import; until then they read as unknown.
    for column in (
        "has_edits INTEGER NOT NULL DEFAULT 0",
        "edit_revision TEXT",
        "as_shot_temperature REAL",
        "as_shot_tint REAL",
        "film_simulation TEXT",
        "dynamic_range INTEGER",
    ):
        db.execute(f"ALTER TABLE photos ADD COLUMN {column}")


def _v2_to_v3(db: sqlite3.Connection) -> None:
    # P3.24: each photo's tone anchors (black/white point), measured lazily on the first render.
    for column in ("tone_black REAL", "tone_white REAL", "tone_anchors_identity TEXT"):
        db.execute(f"ALTER TABLE photos ADD COLUMN {column}")


def _v3_to_v4(db: sqlite3.Connection) -> None:
    # P4.4: the measurements styles' adaptive rules use (filled lazily with the anchors, which are measured
    # again once so all of them come from the same pass), and the exact exposure time for the camera EV, read
    # back from the stored shutter text for photos imported before (accurate to < 0.01 EV).
    for column in ("tone_middle REAL", "neutral_temperature REAL", "neutral_tint REAL", "exposure_time REAL"):
        db.execute(f"ALTER TABLE photos ADD COLUMN {column}")
    rows = db.execute("SELECT id, shutter FROM photos WHERE shutter IS NOT NULL").fetchall()
    db.executemany(
        "UPDATE photos SET exposure_time = ? WHERE id = ?", [(parse_shutter(r[1]), r[0]) for r in rows]
    )


# Migrations from version N to N + 1, applied in order when an older catalog is opened.
_MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {1: _v1_to_v2, 2: _v2_to_v3, 3: _v3_to_v4}

# Measured from the pixels, so they stay valid for the same id across re-imports.
_MEASURED_COLUMNS = (
    "tone_black",
    "tone_white",
    "tone_middle",
    "neutral_temperature",
    "neutral_tint",
    "tone_anchors_identity",
)

_SORT_SQL = {
    # NULL dates sort last in ascending order; filename breaks ties so the order is stable.
    PhotoSort.DATE: "captured_at IS NULL {order}, captured_at {order}, filename COLLATE NOCASE {order}",
    PhotoSort.NAME: "filename COLLATE NOCASE {order}",
    PhotoSort.RATING: "rating {order}, filename COLLATE NOCASE {order}",
}


class CatalogError(RuntimeError):
    """The catalog file can't be used (e.g. written by a newer version of the tool)."""


class CatalogPhoto(BaseModel):
    """One catalog row."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    sha256: str = Field(min_length=64, max_length=64)
    path: Path
    kind: SourceKind
    sidecar_jpeg: Path | None = None
    file_size: int = Field(ge=0)
    mtime_ns: int
    captured_at: datetime | None = None
    camera: str | None = None
    lens: str | None = None
    iso: int | None = None
    shutter: str | None = None
    aperture: float | None = None
    focal_length: float | None = None
    orientation: int = Field(default=1, ge=1, le=8)
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    rating: int = Field(default=0, ge=0, le=5)
    style_id: str | None = None
    missing: bool = False
    has_edits: bool = False
    edit_revision: str | None = None
    as_shot_temperature: float | None = None
    as_shot_tint: float | None = None
    film_simulation: str | None = None
    dynamic_range: int | None = None
    # Per-photo measurements in stops / Kelvin (see core.render.anchors.PhotoStats) and the render identity
    # they were measured with.
    tone_black: float | None = None
    tone_white: float | None = None
    tone_middle: float | None = None
    neutral_temperature: float | None = None
    neutral_tint: float | None = None
    tone_anchors_identity: str | None = None
    exposure_time: float | None = Field(default=None, gt=0, description="Seconds.")

    @property
    def camera_ev(self) -> float | None:
        """The exposure dialed in (EV100), from EXIF; None if a setting is unknown."""
        return camera_ev(self.aperture, self.exposure_time, self.iso)

    def to_photo(self, image_version: str = "") -> Photo:
        return Photo(
            id=self.id,
            path=self.path.as_posix(),
            filename=self.path.name,
            folder=self.path.parent.as_posix(),
            file_size=self.file_size,
            captured_at=self.captured_at,
            camera=self.camera,
            lens=self.lens,
            iso=self.iso,
            shutter=self.shutter,
            aperture=self.aperture,
            focal_length=self.focal_length,
            width=self.width,
            height=self.height,
            rating=self.rating,
            style_id=self.style_id,
            has_overrides=self.has_edits,
            image_version=image_version,
            sidecar_jpeg=self.sidecar_jpeg.as_posix() if self.sidecar_jpeg else None,
        )


class FolderRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    include_subfolders: bool
    last_imported_at: datetime | None = None


def photo_id(sha256: str) -> str:
    return sha256[:ID_LENGTH]


def path_key(path: Path) -> str:
    """Comparison key for a path: case-insensitive with unified separators on Windows."""
    return os.path.normcase(str(path))


class Catalog:
    """Thread-safe access to ``catalog.sqlite``: one connection behind a lock (imports use threads)."""

    def __init__(self, db_path: Path, guard: PathGuard) -> None:
        target = guard.assert_writable(db_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.path = target
        self._lock = threading.Lock()
        self._db = sqlite3.connect(target, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # ---- photos

    def get(self, photo_id: str) -> CatalogPhoto | None:
        row = self._one("SELECT * FROM photos WHERE id = ?", (photo_id,))
        return _photo(row) if row else None

    def find(self, name: str) -> CatalogPhoto | None:
        """A photo by id, file name or file name without extension (case-insensitive); newest import first."""
        row = self._one(
            "SELECT * FROM photos WHERE missing = 0 AND (id = ? OR filename = ? COLLATE NOCASE OR "
            "filename LIKE ? ESCAPE '!' COLLATE NOCASE) ORDER BY rowid DESC LIMIT 1",
            (name, name, name.replace("!", "!!").replace("%", "!%").replace("_", "!_") + ".%"),
        )
        return _photo(row) if row else None

    def get_by_path(self, path: Path) -> CatalogPhoto | None:
        row = self._one("SELECT * FROM photos WHERE path_key = ?", (path_key(path),))
        return _photo(row) if row else None

    def upsert(self, photo: CatalogPhoto) -> None:
        """Insert or update by id. A photo found at a new path (moved, or a copy) takes that path."""
        values = _row_values(photo)
        columns = ", ".join(values)
        placeholders = ", ".join(f":{name}" for name in values)
        updates = ", ".join(
            f"{name} = excluded.{name}"
            for name in values
            # The id is the content hash, so facts measured from the pixels stay valid for the same id.
            if name not in ("id", "rating", "style_id", "has_edits", "edit_revision", *_MEASURED_COLUMNS)
        )
        with self._transaction() as db:
            # Another row may hold this path with older content (the file was edited elsewhere): replace it.
            db.execute("DELETE FROM photos WHERE path_key = :path_key AND id != :id", values)
            db.execute(
                f"INSERT INTO photos ({columns}) VALUES ({placeholders}) "
                f"ON CONFLICT(id) DO UPDATE SET {updates}",
                values,
            )

    def set_as_shot(self, photo_id: str, temperature: float, tint: float) -> None:
        with self._transaction() as db:
            db.execute(
                "UPDATE photos SET as_shot_temperature = ?, as_shot_tint = ? WHERE id = ?",
                (temperature, tint, photo_id),
            )

    def set_photo_stats(self, photo_id: str, stats: Mapping[str, float], identity: str) -> None:
        """Store a photo's measurements (``PhotoStats`` fields: black, white, middle, neutral_temperature,
        neutral_tint) with the render identity they were measured with."""
        with self._transaction() as db:
            db.execute(
                "UPDATE photos SET tone_black = ?, tone_white = ?, tone_middle = ?, neutral_temperature = ?,"
                " neutral_tint = ?, tone_anchors_identity = ? WHERE id = ?",
                (
                    stats["black"],
                    stats["white"],
                    stats["middle"],
                    stats["neutral_temperature"],
                    stats["neutral_tint"],
                    identity,
                    photo_id,
                ),
            )

    def photo_ids_with_style(self, style_id: str) -> list[str]:
        """Every (present) photo that uses ``style_id``, in any folder."""
        with self._lock:
            rows = self._db.execute(
                "SELECT id FROM photos WHERE style_id = ? AND missing = 0 ORDER BY captured_at, filename",
                (style_id,),
            ).fetchall()
        return [row["id"] for row in rows]

    def style_counts(self) -> dict[str, int]:
        """Number of (present) photos per style id."""
        with self._lock:
            rows = self._db.execute(
                "SELECT style_id, COUNT(*) AS n FROM photos WHERE style_id IS NOT NULL AND missing = 0"
                " GROUP BY style_id"
            ).fetchall()
        return {row["style_id"]: row["n"] for row in rows}

    def set_style(self, photo_id: str, style_id: str | None) -> None:
        with self._transaction() as db:
            db.execute("UPDATE photos SET style_id = ? WHERE id = ?", (style_id, photo_id))

    def set_edit(self, photo_id: str, revision: str | None) -> None:
        """Record a photo's current edit revision (None = unedited)."""
        with self._transaction() as db:
            db.execute(
                "UPDATE photos SET has_edits = ?, edit_revision = ? WHERE id = ?",
                (int(revision is not None), revision, photo_id),
            )

    def mark_missing(self, folder: Path, *, recursive: bool, present_ids: set[str]) -> int:
        """Flag photos in ``folder`` that weren't seen by the last import. Returns how many were flagged."""
        where, params = _scope(folder, recursive)
        with self._transaction() as db:
            rows = db.execute(f"SELECT id FROM photos WHERE missing = 0 AND {where}", params).fetchall()
            gone = [row["id"] for row in rows if row["id"] not in present_ids]
            db.executemany("UPDATE photos SET missing = 1 WHERE id = ?", [(i,) for i in gone])
        return len(gone)

    def page(
        self,
        folder: Path,
        *,
        recursive: bool = False,
        style_id: str | None = None,
        min_rating: int = 0,
        sort: PhotoSort = PhotoSort.DATE,
        order: SortOrder = SortOrder.ASC,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[CatalogPhoto], int]:
        """One page of the (non-missing) photos in ``folder``, plus the total count of matches."""
        where, params = _scope(folder, recursive)
        clauses = ["missing = 0", where, "rating >= ?"]
        params = [*params, min_rating]
        if style_id == "none":
            clauses.append("style_id IS NULL")
        elif style_id is not None:
            clauses.append("style_id = ?")
            params.append(style_id)
        condition = " AND ".join(clauses)
        order_by = _SORT_SQL[sort].format(order="DESC" if order is SortOrder.DESC else "ASC")
        with self._lock:
            total = self._db.execute(f"SELECT COUNT(*) FROM photos WHERE {condition}", params).fetchone()[0]
            rows = self._db.execute(
                f"SELECT * FROM photos WHERE {condition} ORDER BY {order_by} LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
        return [_photo(row) for row in rows], int(total)

    def count(self, folder: Path, *, recursive: bool = False) -> int:
        return self.page(folder, recursive=recursive, limit=1)[1]

    # ---- folders

    def folders(self) -> list[FolderRecord]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM folders ORDER BY last_imported_at DESC, path").fetchall()
        return [_folder(row) for row in rows]

    def get_folder(self, folder: Path) -> FolderRecord | None:
        row = self._one("SELECT * FROM folders WHERE path_key = ?", (path_key(folder),))
        return _folder(row) if row else None

    def save_folder(self, record: FolderRecord) -> None:
        with self._transaction() as db:
            db.execute(
                "INSERT INTO folders (path_key, path, include_subfolders, last_imported_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(path_key) DO UPDATE SET path = excluded.path, "
                "include_subfolders = excluded.include_subfolders, "
                "last_imported_at = excluded.last_imported_at",
                (
                    path_key(record.path),
                    str(record.path),
                    int(record.include_subfolders),
                    record.last_imported_at.isoformat() if record.last_imported_at else None,
                ),
            )

    # ---- small key/value state (e.g. the folder shown in the Library)

    def get_state(self, key: str) -> str | None:
        row = self._one("SELECT value FROM state WHERE key = ?", (key,))
        return str(row["value"]) if row else None

    def set_state(self, key: str, value: str) -> None:
        with self._transaction() as db:
            db.execute(
                "INSERT INTO state (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    # ---- internals

    def _one(self, sql: str, params: tuple[Any, ...]) -> sqlite3.Row | None:
        with self._lock:
            row: sqlite3.Row | None = self._db.execute(sql, params).fetchone()
        return row

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield self._db
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            self._db.execute("COMMIT")

    def _migrate(self) -> None:
        version = int(self._db.execute("PRAGMA user_version").fetchone()[0])
        if version > SCHEMA_VERSION:
            raise CatalogError(
                f"{self.path} was written by a newer PhotoEditor (catalog schema {version}, this build reads "
                f"up to {SCHEMA_VERSION}). Update PhotoEditor, or move the catalog away to start a new one."
            )
        with self._transaction() as db:
            if version == 0:
                _execute_script(db, _SCHEMA)
            else:
                for step in range(version, SCHEMA_VERSION):
                    _MIGRATIONS[step](db)
            db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _execute_script(db: sqlite3.Connection, script: str) -> None:
    # executescript() would COMMIT the surrounding transaction, so run the statements one by one.
    for statement in script.split(";"):
        if statement.strip():
            db.execute(statement)


def _scope(folder: Path, recursive: bool) -> tuple[str, list[Any]]:
    key = path_key(folder)
    if not recursive:
        return "parent_key = ?", [key]
    prefix = key.rstrip("\\/") + os.sep
    escaped = prefix.replace("!", "!!").replace("%", "!%").replace("_", "!_")
    return "(parent_key = ? OR path_key LIKE ? ESCAPE '!')", [key, escaped + "%"]


def _row_values(photo: CatalogPhoto) -> dict[str, Any]:
    return {
        "id": photo.id,
        "sha256": photo.sha256,
        "path": str(photo.path),
        "path_key": path_key(photo.path),
        "parent_key": path_key(photo.path.parent),
        "filename": photo.path.name,
        "kind": photo.kind.value,
        "sidecar_jpeg": str(photo.sidecar_jpeg) if photo.sidecar_jpeg else None,
        "file_size": photo.file_size,
        "mtime_ns": photo.mtime_ns,
        "captured_at": photo.captured_at.isoformat() if photo.captured_at else None,
        "camera": photo.camera,
        "lens": photo.lens,
        "iso": photo.iso,
        "shutter": photo.shutter,
        "aperture": photo.aperture,
        "focal_length": photo.focal_length,
        "orientation": photo.orientation,
        "width": photo.width,
        "height": photo.height,
        "rating": photo.rating,
        "style_id": photo.style_id,
        "missing": int(photo.missing),
        "has_edits": int(photo.has_edits),
        "edit_revision": photo.edit_revision,
        "as_shot_temperature": photo.as_shot_temperature,
        "as_shot_tint": photo.as_shot_tint,
        "film_simulation": photo.film_simulation,
        "dynamic_range": photo.dynamic_range,
        "tone_black": photo.tone_black,
        "tone_white": photo.tone_white,
        "tone_anchors_identity": photo.tone_anchors_identity,
        "tone_middle": photo.tone_middle,
        "neutral_temperature": photo.neutral_temperature,
        "neutral_tint": photo.neutral_tint,
        "exposure_time": photo.exposure_time,
    }


def _photo(row: sqlite3.Row) -> CatalogPhoto:
    data = dict(row)
    for name in ("path_key", "parent_key", "filename"):
        data.pop(name)
    data["missing"] = bool(data["missing"])
    data["has_edits"] = bool(data["has_edits"])
    return CatalogPhoto.model_validate(data)


def _folder(row: sqlite3.Row) -> FolderRecord:
    return FolderRecord(
        path=Path(row["path"]),
        include_subfolders=bool(row["include_subfolders"]),
        last_imported_at=row["last_imported_at"],
    )
