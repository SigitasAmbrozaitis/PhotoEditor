"""The photo library: importing folders (read-only) and serving photos, thumbnails and previews."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
from PIL import Image
from pydantic import ValidationError

from photoedit.core import color
from photoedit.core.cache import ImageCache
from photoedit.core.catalog import Catalog, CatalogPhoto, FolderRecord, path_key, photo_id
from photoedit.core.decode import DecodeError, embedded_jpeg, is_raw, oriented_image, read_raw_info
from photoedit.core.edits import EditStore, EffectiveEdit, merge_patch
from photoedit.core.errors import InvalidRequestError, NotFoundError
from photoedit.core.geometry import apply_change, check_geometry, edited_size, is_identity, sub_crop
from photoedit.core.jobs import ItemResult, ItemSpec, JobManager
from photoedit.core.metadata import (
    AfMode,
    MetadataError,
    PhotoMetadata,
    read_metadata,
    read_metadata_from_bytes,
)
from photoedit.core.render.pipeline import check_supported
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
from photoedit.models.adjustments import CropRect, Geometry, GeometryChange
from photoedit.models.photo import PhotoNote, ZoomInfo, ZoomLevel
from photoedit.safety import PathGuard

CURRENT_FOLDER = "current_folder"
IMPORT_THREADS = 4  # hashing and JPEG decoding release the GIL, so a few threads overlap disk and CPU
RENDER_THREADS = 4  # LibRaw and the numpy stages also release the GIL for most of their work
_HASH_CHUNK = 1 << 20
MAX_LISTED = 10  # matches named in an ambiguous-reference error

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
            if existing.af_mode is None:
                existing = self.with_af_point(existing)
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
            af_x=meta.af_point[0] if meta.af_point else None,
            af_y=meta.af_point[1] if meta.af_point else None,
            af_mode=meta.af_mode,
        )
        # Thumbnail first: a file that can't be decoded fails here and never enters the catalog half-done.
        if thumbnail is not None:
            self.cache.put_thumbnail(photo.id, thumbnail)
        else:
            self.cache.thumbnail(photo)
        self.catalog.upsert(photo)
        outcome = ImportOutcome.NEW if existing is None and previous is None else ImportOutcome.UPDATED
        return photo, outcome

    def with_af_point(self, photo: CatalogPhoto) -> CatalogPhoto:
        """``photo`` with its focus point read from the file if the catalog doesn't have it yet (photos
        imported before P6b.3). Reads only the header (a RAW's embedded JPEG), never the raw data. A file that
        can't be read counts as having no point."""
        if photo.af_mode is not None:
            return photo
        try:
            meta = _read_metadata(photo.path)
        except (MetadataError, DecodeError, OSError):
            meta = None
        point, mode = (meta.af_point, meta.af_mode) if meta is not None else (None, AfMode.NONE)
        self.catalog.set_af_point(photo.id, point, mode)
        x, y = point if point is not None else (None, None)
        return photo.model_copy(update={"af_x": x, "af_y": y, "af_mode": mode})

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

    def resolve(self, ref: str) -> CatalogPhoto:
        """The one photo ``ref`` names: an id, an id prefix (8+ characters), a file name with or without its
        extension, or ``folder/name`` (any trailing part of the folder's path) when a name is in several
        folders. Unknown and ambiguous references are errors that list what matched."""
        ref = ref.strip()
        if not ref:
            raise InvalidRequestError("empty photo reference")
        exact = self.catalog.get(ref)
        if exact is not None and not exact.missing:
            return exact
        folder, sep, name = ref.replace("\\", "/").rpartition("/")
        found = self.catalog.matches(name if sep else ref)
        if sep:
            found = [p for p in found if _in_folder(p.path.parent, folder)]
        if not found:
            raise NotFoundError(f"no imported photo called '{ref}' (import its folder first)")
        if len(found) > 1:
            listed = "; ".join(f"{p.path} (id {p.id})" for p in found[:MAX_LISTED])
            more = f"; and {len(found) - MAX_LISTED} more" if len(found) > MAX_LISTED else ""
            raise InvalidRequestError(
                f"'{ref}' matches {len(found)} photos: {listed}{more}. Use folder/name or the id."
            )
        return found[0]

    def resolve_many(self, refs: Sequence[str] = (), *, folder: Path | None = None) -> list[CatalogPhoto]:
        """The photos ``refs`` name, then every photo of ``folder`` (an imported folder), each once, in
        order."""
        photos = [self.resolve(ref) for ref in refs]
        if folder is not None:
            photos += self.folder_photos(folder)
        if not photos:
            raise InvalidRequestError("no photos given")
        return list({p.id: p for p in photos}.values())

    def folder_photos(self, folder: Path) -> list[CatalogPhoto]:
        """Every present photo of an imported folder (with its subfolders if it was imported with them), by
        capture date."""
        record = self.catalog.get_folder(folder)
        if record is None:
            raise NotFoundError(f"{folder} isn't imported yet; import it first")
        items, _ = self.catalog.page(
            record.path,
            recursive=record.include_subfolders,
            sort=PhotoSort.DATE,
            order=SortOrder.ASC,
            limit=1_000_000,
        )
        return items

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
            note=self.edits.note(photo.id),
        )

    def set_note(self, photo_id: str, text: str | None) -> PhotoNote | None:
        """Write Claude's note about the photo (replacing the old one), or remove it with None. No pixels
        change, so previews and the edit's revision stay."""
        photo = self.photo(photo_id)
        note = None
        if text is not None:
            try:
                note = PhotoNote(text=text.strip(), written_at=self._clock())
            except ValidationError as exc:
                raise InvalidRequestError(f"invalid note: {exc.errors()[0]['msg']}") from exc
        self.edits.set_note(photo, note)
        return note

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

    def update_edit(self, photo_id: str, patch: Mapping[str, Any]) -> EffectiveEdit:
        """Change only the values in ``patch`` (nested, e.g. ``{"tone": {"exposure": 0.3}}``; ``None`` = back
        to the style's or default value) and save. Nothing is written when any value is rejected."""
        current = self.edit(photo_id)
        base = current.base or self.edits.default(self.photo(photo_id)).adjustments
        return self.save_edit(photo_id, merge_patch(current.adjustments, base, patch))

    def set_geometry(self, photo_id: str, change: GeometryChange) -> EffectiveEdit:
        """Apply a geometry change (flips and turns carry the crop along; angle and aspect changes shrink the
        crop to fit) and save it."""
        photo = self.photo(photo_id)
        current = self.edits.effective(photo).adjustments
        geometry = apply_change(current.geometry, change, photo.width, photo.height)
        return self.save_edit(photo_id, current.model_copy(update={"geometry": geometry}))

    def preview_geometry(self, photo_id: str, geometry: Geometry, change: GeometryChange) -> Geometry:
        """``geometry`` with ``change`` applied for this photo, without saving (the crop tool's draft)."""
        photo = self.photo(photo_id)
        return apply_change(geometry, change, photo.width, photo.height)

    def reset_edit(self, photo_id: str) -> EffectiveEdit:
        """Drop the photo's own tweaks; its style stays (``set_photo_style(id, None)`` removes the style)."""
        photo = self.photo(photo_id)
        result = self.edits.reset_overrides(photo)
        self.record_edit(photo, result)
        return result

    def record_edit(self, photo: CatalogPhoto, edit: EffectiveEdit) -> None:
        """Bring the catalog (edit revision, style) and the render cache in line with a changed edit."""
        default = self.edits.default(photo).revision
        geometry = edit.adjustments.geometry
        size = None if is_identity(geometry) else edited_size(photo.width, photo.height, geometry)
        self.catalog.set_edit(photo.id, edit.revision if edit.revision != default else None, size)
        if photo.style_id != edit.style_id:
            self.catalog.set_style(photo.id, edit.style_id)
        # Renders of older edits are dead weight now; keep the current edit and its "before" views.
        before = self.edits.before(photo, geometry).revision
        self.renderer.prune(photo.id, keep={edit.revision, default, before})

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

    def preview(self, photo_id: str, long_edge: int, *, before: bool = False, upright: bool = False) -> bytes:
        """The photo with its edit at ``long_edge`` px. ``before`` = unedited colors with the edit's geometry,
        so before and after line up; ``upright`` = without any geometry (the crop tool's view)."""
        photo = self.photo(photo_id)
        edit = self.edits.effective(photo)
        if before:
            edit = self.edits.before(photo, edit.adjustments.geometry)
        if not self.renderer.preview_path(photo, edit, long_edge, upright=upright).is_file():
            self._require_original(photo)
        return self.renderer.preview(photo, edit, long_edge, upright=upright)

    def render_draft(
        self, photo_id: str, adjustments: AdjustmentParams, long_edge: int, *, before: bool = False
    ) -> bytes:
        """The photo with ``adjustments`` that aren't saved (a look at a change before making it). Validated
        like a save; nothing is written. ``before`` = the photo's defaults with the draft's geometry."""
        photo = self._draft_photo(photo_id, adjustments)
        if before:
            adjustments = self.edits.before(photo, adjustments.geometry).adjustments
        return self.renderer.draft(photo, adjustments, long_edge)

    def render_pixels(
        self, photo_id: str, adjustments: AdjustmentParams | None, long_edge: int
    ) -> npt.NDArray[np.uint8]:
        """The 8-bit sRGB pixels of the photo with its saved edit, or with unsaved ``adjustments`` (validated
        like a save), as a preview shows them. Nothing is written."""
        if adjustments is None:
            photo = self._draft_photo(photo_id, None)
            adjustments = self.edits.effective(photo).adjustments
        else:
            photo = self._draft_photo(photo_id, adjustments)
        return self.renderer.pixels(photo, adjustments, long_edge)

    def _draft_photo(self, photo_id: str, adjustments: AdjustmentParams | None) -> CatalogPhoto:
        photo = self.photo(photo_id)
        if adjustments is not None:
            check_supported(adjustments)
            check_geometry(adjustments.geometry, photo.width, photo.height)
        if self.renderer.linear.peek(photo.id) is None:
            self._require_original(photo)
        return photo

    def framing_preview(self, photo_id: str, crop: CropRect, long_edge: int) -> bytes:
        """The photo with its edit, cut to ``crop`` (normalized to the edited photo) on top of its own crop:
        what an export with that aspect crop shows (P6c.5). Cached like previews, under the edit's revision,
        so a new edit prunes it."""
        photo = self.photo(photo_id)
        edit = self.edits.effective(photo)
        geometry = edit.adjustments.geometry
        framed = geometry.model_copy(
            update={"crop": sub_crop(geometry.crop, crop.left, crop.top, crop.right, crop.bottom)}
        )
        key = hashlib.sha256(framed.crop.model_dump_json().encode()).hexdigest()[:10]
        view = edit.model_copy(
            update={
                "adjustments": edit.adjustments.model_copy(update={"geometry": framed}),
                "revision": f"{edit.revision}-f{key}",
            }
        )
        if not self.renderer.preview_path(photo, view, long_edge).is_file():
            self._require_original(photo)
        return self.renderer.preview(photo, view, long_edge)

    def zoom_info(self, photo_id: str, level: ZoomLevel) -> ZoomInfo:
        """The zoom view at ``level`` (50 or 100 %): starts its decode if needed."""
        photo = self.photo(photo_id)
        self._require_original(photo)
        return self.renderer.zoom_info(photo, self.edits.effective(photo), level)

    def tile(
        self, photo_id: str, level: ZoomLevel, tx: int, ty: int, *, before: bool = False
    ) -> bytes | None:
        """One tile of the zoom view (``before`` = the photo's defaults with the edit's geometry); None while
        the decode for ``level`` is still running."""
        photo = self.photo(photo_id)
        edit = self.edits.effective(photo)
        if before:
            edit = self.edits.before(photo, edit.adjustments.geometry)
        if not self.renderer.tile_path(photo, edit, level, tx, ty).is_file():
            self._require_original(photo)
        return self.renderer.tile(photo, edit, level, tx, ty)

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


def _read_metadata(path: Path) -> PhotoMetadata:
    if not is_raw(path):
        return read_metadata(path)
    jpeg = embedded_jpeg(path)
    if jpeg is None:
        raise MetadataError(f"{path.name} has no embedded JPEG")
    return read_metadata_from_bytes(jpeg)


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


def _in_folder(parent: Path, folder: str) -> bool:
    """Whether ``parent`` is ``folder`` or ends with it at a path boundary (``2026-08-11`` matches
    ``C:/Pictures/2026/2026-08-11``)."""
    have = path_key(parent).replace("\\", "/").rstrip("/")
    want = path_key(Path(folder)).replace("\\", "/").rstrip("/")
    return bool(want) and (have == want or have.endswith("/" + want))
