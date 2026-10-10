"""The photo library: importing folders (read-only) and serving photos, thumbnails and previews."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from PIL import Image

from photoedit.core import color
from photoedit.core.cache import ImageCache
from photoedit.core.catalog import Catalog, CatalogPhoto, FolderRecord, photo_id
from photoedit.core.decode import is_raw, oriented_image, read_raw_info
from photoedit.core.edits import EditStore, EffectiveEdit
from photoedit.core.errors import NotFoundError
from photoedit.core.jobs import ItemResult, ItemSpec, JobManager
from photoedit.core.metadata import MetadataError, PhotoMetadata, read_metadata, read_metadata_from_bytes
from photoedit.core.renderer import Renderer, stored_stats
from photoedit.core.scan import ScannedPhoto, SourceKind, scan_folder
from photoedit.core.style_rules import RuleInputs
from photoedit.core.styles import StyleLibrary
from photoedit.models import (
    AdjustmentParams,
    AsShot,
    Job,
    JobKind,
    LibraryFolder,
    LibraryInfo,
    Page,
    Photo,
    PhotoDetail,
    PhotoEdit,
    PhotoSort,
    SortOrder,
)
from photoedit.safety import PathGuard

CURRENT_FOLDER = "current_folder"
IMPORT_THREADS = 4  # hashing and JPEG decoding release the GIL, so a few threads overlap disk and CPU
RENDER_THREADS = 4  # LibRaw and the numpy stages also release the GIL for most of their work
_HASH_CHUNK = 1 << 20

type Clock = Callable[[], datetime]


class ImportOutcome(StrEnum):
    NEW = "new"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


class Library:
    def __init__(
        self,
        catalog: Catalog,
        cache: ImageCache,
        jobs: JobManager,
        guard: PathGuard,
        *,
        suggested_folder: Path | None = None,
        clock: Clock | None = None,
        edits: EditStore | None = None,
        renderer: Renderer | None = None,
        styles: StyleLibrary | None = None,
    ) -> None:
        self.catalog = catalog
        self.styles = styles
        # Edits live next to the catalog in the workspace unless told otherwise.
        self.edits = edits or EditStore(
            catalog.path.parent / "edits", guard, styles=styles, inputs=self.rule_inputs
        )
        self.renderer = renderer or Renderer(cache.root, guard, remember_stats=catalog.set_photo_stats)
        self.cache = cache
        self.jobs = jobs
        self._guard = guard
        self._suggested = suggested_folder
        self._clock: Clock = clock or (lambda: datetime.now(UTC))
        # Every folder ever imported stays read-only for the life of the process (golden rule 1).
        for record in catalog.folders():
            guard.protect(record.path)

    # ---- import

    def import_folder(self, folder: Path, *, include_subfolders: bool = False) -> Job:
        """Start importing ``folder`` as a background job and make it the Library's current folder.

        Only reads the photos. Raises ``ScanError`` right away if the folder can't be listed.
        """
        self._guard.protect(folder)  # before anything else touches the folder
        scan = scan_folder(folder, recursive=include_subfolders)
        root = scan.folder
        self._guard.protect(root)
        previous = self.catalog.get_folder(root)
        self.catalog.save_folder(
            FolderRecord(
                path=root,
                include_subfolders=include_subfolders,
                last_imported_at=previous.last_imported_at if previous else None,
            )
        )
        self.catalog.set_state(CURRENT_FOLDER, str(root))

        outcomes: dict[int, tuple[str, ImportOutcome]] = {}

        def work(index: int) -> ItemResult:
            photo, outcome = self._import_one(scan.photos[index])
            outcomes[index] = (photo.id, outcome)
            return ItemResult(photo_id=photo.id, message=outcome.value)

        def finish() -> str:
            present = {pid for pid, _ in outcomes.values()}
            missing = self.catalog.mark_missing(root, recursive=include_subfolders, present_ids=present)
            self.catalog.save_folder(
                FolderRecord(path=root, include_subfolders=include_subfolders, last_imported_at=self._clock())
            )
            self.render_thumbnails([pid for pid, _ in outcomes.values()])
            return _summary(
                Counter(o for _, o in outcomes.values()), len(scan.photos), len(scan.skipped), missing
            )

        noun = "photo" if len(scan.photos) == 1 else "photos"
        return self.jobs.submit(
            JobKind.IMPORT,
            f"Import {len(scan.photos)} {noun} from {root.name or root}",
            [ItemSpec(filename=p.path.name) for p in scan.photos],
            work,
            parallel=IMPORT_THREADS,
            finish=finish,
            folder=root.as_posix(),
        )

    def _import_one(self, scanned: ScannedPhoto) -> tuple[CatalogPhoto, ImportOutcome]:
        path = scanned.path
        stat = path.stat()
        existing = self.catalog.get_by_path(path)
        if (
            existing is not None
            and existing.file_size == stat.st_size
            and existing.mtime_ns == stat.st_mtime_ns
            and existing.sidecar_jpeg == scanned.sidecar_jpeg
            and self.cache.has_thumbnail(existing.id)
        ):
            if existing.missing:
                existing = existing.model_copy(update={"missing": False})
                self.catalog.upsert(existing)
            return existing, ImportOutcome.UNCHANGED

        sha256 = _sha256(path)
        meta, thumbnail, as_shot = _read_metadata_and_thumbnail(path)
        previous = self.catalog.get(photo_id(sha256))
        photo = CatalogPhoto(
            id=photo_id(sha256),
            sha256=sha256,
            path=path,
            kind=scanned.kind,
            sidecar_jpeg=scanned.sidecar_jpeg,
            file_size=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
            captured_at=meta.captured_at,
            camera=meta.camera,
            lens=meta.lens,
            iso=meta.iso,
            shutter=meta.shutter,
            exposure_time=meta.exposure_time,
            aperture=meta.aperture,
            focal_length=meta.focal_length,
            orientation=meta.orientation,
            width=meta.width,
            height=meta.height,
            rating=meta.rating,
            film_simulation=meta.film_simulation,
            dynamic_range=meta.dynamic_range,
            as_shot_temperature=as_shot[0] if as_shot else None,
            as_shot_tint=as_shot[1] if as_shot else None,
        )
        # Thumbnail first: a file that can't be decoded fails here and never enters the catalog half-done.
        if thumbnail is not None:
            self.cache.put_thumbnail(photo.id, thumbnail)
        else:
            self.cache.thumbnail(photo)
        self.catalog.upsert(photo)
        outcome = ImportOutcome.NEW if existing is None and previous is None else ImportOutcome.UPDATED
        return photo, outcome

    # ---- folders

    def info(self) -> LibraryInfo:
        current = self._current()
        suggested = self._suggested.as_posix() if self._suggested else None
        if current is None:
            return LibraryInfo(folder=None, photo_count=0, suggested_folder=suggested)
        return LibraryInfo(
            folder=current.path.as_posix(),
            include_subfolders=current.include_subfolders,
            photo_count=self.catalog.count(current.path, recursive=current.include_subfolders),
            suggested_folder=suggested,
        )

    def folders(self) -> list[LibraryFolder]:
        return [
            LibraryFolder(
                path=record.path.as_posix(),
                include_subfolders=record.include_subfolders,
                photo_count=self.catalog.count(record.path, recursive=record.include_subfolders),
                last_imported_at=record.last_imported_at,
            )
            for record in self.catalog.folders()
        ]

    def open_folder(self, folder: Path) -> LibraryInfo:
        """Show an already imported folder in the Library (no disk access)."""
        record = self.catalog.get_folder(folder)
        if record is None:
            raise NotFoundError(f"folder '{folder}' has not been imported yet")
        self.catalog.set_state(CURRENT_FOLDER, str(record.path))
        return self.info()

    def _current(self) -> FolderRecord | None:
        value = self.catalog.get_state(CURRENT_FOLDER)
        return self.catalog.get_folder(Path(value)) if value else None

    # ---- photos

    def list_photos(
        self,
        *,
        style_id: str | None = None,
        min_rating: int = 0,
        sort: PhotoSort = PhotoSort.DATE,
        order: SortOrder = SortOrder.ASC,
        offset: int = 0,
        limit: int = 100,
    ) -> Page[Photo]:
        current = self._current()
        if current is None:
            return Page[Photo](items=[], total=0, offset=offset, limit=limit)
        items, total = self.catalog.page(
            current.path,
            recursive=current.include_subfolders,
            style_id=style_id,
            min_rating=min_rating,
            sort=sort,
            order=order,
            offset=offset,
            limit=limit,
        )
        photos = [p.to_photo(self.image_version(p)) for p in items]
        return Page[Photo](items=photos, total=total, offset=offset, limit=limit)

    def photo(self, photo_id: str) -> CatalogPhoto:
        photo = self.catalog.get(photo_id)
        if photo is None:
            raise NotFoundError(f"photo '{photo_id}' not found")
        return photo

    def photo_detail(self, photo_id: str) -> PhotoDetail:
        photo = self.photo(photo_id)
        edit = self.edits.effective(photo)
        unedited = self.edits.default(photo).adjustments
        as_shot = self.as_shot(photo)
        return PhotoDetail(
            photo=photo.to_photo(self.image_version(photo)),
            edit=PhotoEdit(
                photo_id=photo.id,
                style_id=edit.style_id,
                adjustments=edit.adjustments,
                overridden=edit.overridden,
                revision=edit.revision,
                defaults=edit.base or unedited,
                unedited=unedited,
                style_values=edit.style_values,
                rules=edit.rules,
                style_version=edit.style_version,
                style_error=edit.style_error,
                group=edit.group,
            ),
            as_shot=AsShot(temperature=as_shot[0], tint=as_shot[1]) if as_shot else None,
        )

    def rule_inputs(self, photo: CatalogPhoto) -> RuleInputs:
        """What a style's rules know about ``photo`` (measured once and stored; may decode the photo the first
        time)."""
        stats = None
        if stored_stats(photo, self.renderer.identity) is not None or photo.path.is_file():
            stats = self.renderer.stats(photo)
        return RuleInputs(stats=stats, as_shot=self.as_shot(photo), camera_ev=photo.camera_ev)

    def as_shot(self, photo: CatalogPhoto) -> tuple[float, float] | None:
        """The recorded white balance; read from the RAW (and remembered) for photos imported before
        Phase 3. JPEG/TIFF originals count as balanced for D65."""
        if photo.as_shot_temperature is not None and photo.as_shot_tint is not None:
            return photo.as_shot_temperature, photo.as_shot_tint
        if not is_raw(photo.path):
            return color.xy_to_temperature_tint(color.D65)
        if not photo.path.is_file():
            return None
        found = read_raw_info(photo.path).as_shot
        if found is not None:
            self.catalog.set_as_shot(photo.id, *found)
        return found

    # ---- edits

    def edit(self, photo_id: str) -> EffectiveEdit:
        return self.edits.effective(self.photo(photo_id))

    def save_edit(self, photo_id: str, adjustments: AdjustmentParams) -> EffectiveEdit:
        photo = self.photo(photo_id)
        result = self.edits.save(photo, adjustments)
        self.record_edit(photo, result)
        return result

    def reset_edit(self, photo_id: str) -> EffectiveEdit:
        """Drop the photo's own tweaks; its style stays (``set_photo_style(id, None)`` removes the style)."""
        photo = self.photo(photo_id)
        result = self.edits.reset_overrides(photo)
        self.record_edit(photo, result)
        return result

    def record_edit(self, photo: CatalogPhoto, edit: EffectiveEdit) -> None:
        """Bring the catalog (edit revision, style) and the render cache in line with a changed edit."""
        default = self.edits.default(photo).revision
        self.catalog.set_edit(photo.id, edit.revision if edit.revision != default else None)
        if photo.style_id != edit.style_id:
            self.catalog.set_style(photo.id, edit.style_id)
        # Renders of older edits are dead weight now; keep the current edit and the unedited "before".
        self.renderer.prune(photo.id, keep={edit.revision, default})

    def image_version(self, photo: CatalogPhoto) -> str:
        """Changes whenever the photo renders differently (new edit, new engine or library version)."""
        key = f"{self.renderer.identity}|{photo.edit_revision or 'unedited'}"
        return hashlib.sha256(key.encode()).hexdigest()[:10]

    # ---- images

    def thumbnail(self, photo_id: str) -> bytes:
        """The rendered thumbnail; for an unedited photo not rendered yet, the camera's embedded one meanwhile
        (the thumbnail job renders them after an import)."""
        photo = self.photo(photo_id)
        edit = self.edits.effective(photo)
        if self.renderer.has_thumbnail(photo, edit):
            return self.renderer.thumbnail(photo, edit)
        if photo.edit_revision is None and self.cache.has_thumbnail(photo.id):
            return self.cache.thumbnail(photo)
        self._require_original(photo)
        return self.renderer.thumbnail(photo, edit)

    def preview(self, photo_id: str, long_edge: int, *, before: bool = False) -> bytes:
        """The photo with its edit (``before`` = unedited) at ``long_edge`` px."""
        photo = self.photo(photo_id)
        edit = self.edits.default(photo) if before else self.edits.effective(photo)
        if not self.renderer.preview_path(photo, edit, long_edge).is_file():
            self._require_original(photo)
        return self.renderer.preview(photo, edit, long_edge)

    def sidecar(self, photo_id: str, long_edge: int) -> bytes:
        """The camera's own JPEG saved next to a RAW (read-only), scaled to ``long_edge``, for comparison."""
        photo = self.photo(photo_id)
        if photo.sidecar_jpeg is None:
            raise NotFoundError(f"'{photo.path.name}' has no camera JPEG next to it")
        if not photo.sidecar_jpeg.is_file():
            raise NotFoundError(f"the camera JPEG is no longer at {photo.sidecar_jpeg}")
        return self.cache.sidecar(photo, long_edge)

    def render_thumbnails(self, photo_ids: list[str]) -> Job | None:
        """Background job rendering the thumbnails that aren't rendered yet. None if nothing to do."""
        todo: list[CatalogPhoto] = []
        for pid in photo_ids:
            photo = self.catalog.get(pid)
            if photo is not None and not self.renderer.has_thumbnail(photo, self.edits.effective(photo)):
                todo.append(photo)
        if not todo:
            return None

        def work(index: int) -> ItemResult:
            photo = todo[index]
            self.renderer.thumbnail(photo, self.edits.effective(photo))
            return ItemResult(photo_id=photo.id)

        noun = "photo" if len(todo) == 1 else "photos"
        return self.jobs.submit(
            JobKind.RENDER,
            f"Render thumbnails for {len(todo)} {noun}",
            [ItemSpec(filename=p.path.name, photo_id=p.id) for p in todo],
            work,
            parallel=RENDER_THREADS,
        )

    def _require_original(self, photo: CatalogPhoto) -> None:
        if not photo.path.is_file():
            raise NotFoundError(f"the original of '{photo.path.name}' is no longer at {photo.path}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _read_metadata_and_thumbnail(
    path: Path,
) -> tuple[PhotoMetadata, Image.Image | None, tuple[float, float] | None]:
    """Metadata, an upright thumbnail source when it comes for free (a RAW's embedded JPEG), and the as-shot
    white balance (RAWs only)."""
    if not is_raw(path):
        return read_metadata(path), None, None
    info = read_raw_info(path)
    if info.embedded_jpeg is None:
        return PhotoMetadata(width=info.width, height=info.height), None, info.as_shot
    try:
        meta = read_metadata_from_bytes(info.embedded_jpeg)
    except MetadataError:
        meta = PhotoMetadata(width=info.width, height=info.height)
    # The embedded JPEG is smaller than the sensor; the RAW knows the real size.
    meta = meta.model_copy(update={"width": info.width, "height": info.height})
    return meta, oriented_image(info.embedded_jpeg, info.flip), info.as_shot


def _summary(outcomes: Counter[ImportOutcome], photos: int, skipped: int, missing: int) -> str:
    noun = "photo" if photos == 1 else "photos"
    parts = [f"{outcomes[o]} {o.value}" for o in ImportOutcome if outcomes[o]]
    failed = photos - sum(outcomes.values())
    if failed:
        parts.append(f"{failed} failed")
    text = f"{photos} {noun}" + (f": {', '.join(parts)}" if parts else "")
    if skipped:
        text += f"; {skipped} other file{'s' if skipped != 1 else ''} skipped"
    if missing:
        text += f"; {missing} no longer in the folder"
    return text


__all__ = ["ImportOutcome", "Library", "SourceKind"]
