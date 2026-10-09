"""Style operations across the library.

Applying styles to photos (as jobs, optionally evening a selection out), keeping every photo that uses a style
in step when the style changes (live link), creating or updating a style from a photo's look, rendering sample
pairs and the consistency report. The style files themselves are ``StyleLibrary``'s; the photos and their
edits are the ``Library``'s.
"""

from __future__ import annotations

import statistics
import uuid
from collections.abc import Callable, Iterable
from typing import Literal

from photoedit.core.catalog import CatalogPhoto
from photoedit.core.edits import differences, source_defaults
from photoedit.core.errors import InvalidRequestError, NotFoundError
from photoedit.core.jobs import ItemResult, ItemSpec, JobManager
from photoedit.core.library import Library
from photoedit.core.style_rules import OFFSET_REFERENCE_KELVIN
from photoedit.core.styles import SAMPLES_DIR, StyleLibrary
from photoedit.models import (
    ConsistencyReport,
    ExposureRule,
    GroupReference,
    Job,
    JobKind,
    PhotoMeasurements,
    ReportPhoto,
    Spread,
    Style,
    StyleSample,
    StyleSummary,
    StyleView,
    WhiteBalanceRule,
    style_summary,
    style_view,
)
from photoedit.models.adjustments import WhiteBalance
from photoedit.models.style import (
    ExposureFromPhoto,
    StyleCreate,
    StyleFromPhoto,
    StyleUpdate,
    StyleUpdateFromPhoto,
    WhiteBalanceFromPhoto,
)
from photoedit.safety import PathGuard

SAMPLE_LONG_EDGE = 1200
APPLY_THREADS = 4
TARGET_RANGE = (-4.0, 4.0)  # ExposureRule.target
OFFSET_RANGE = (-3000.0, 3000.0)  # WhiteBalanceRule.temperature_offset
TINT_OFFSET_RANGE = (-50.0, 50.0)
# Parameters a style never takes from a photo: white balance and exposure have their own choices (rules).
_NEVER_FROM_PHOTO = ("white_balance.", "geometry.", "lens.")

type GroupIds = Callable[[], str]


class Styling:
    def __init__(
        self,
        library: Library,
        styles: StyleLibrary,
        jobs: JobManager,
        guard: PathGuard,
        *,
        group_ids: GroupIds | None = None,
    ) -> None:
        self.library = library
        self.styles = styles
        self.jobs = jobs
        self._guard = guard
        self._group_ids: GroupIds = group_ids or (lambda: uuid.uuid4().hex[:8])

    # ---- reading

    def summaries(self) -> list[StyleSummary]:
        counts = self.library.catalog.style_counts()
        out: list[StyleSummary] = []
        for entry in self.styles.listings():
            count = counts.get(entry.id, 0)
            if entry.style is not None:
                out.append(style_summary(entry.style, photo_count=count))
            else:
                out.append(StyleSummary(id=entry.id, name=entry.id, photo_count=count, error=entry.error))
        return out

    def view(self, style_id: str) -> StyleView:
        return self._view(self.styles.get(style_id))

    def _view(self, style: Style) -> StyleView:
        return style_view(style, photo_count=len(self.library.catalog.photo_ids_with_style(style.id)))

    # ---- changing styles (every photo using the style follows: live link)

    def create(self, request: StyleCreate) -> StyleView:
        self._check_photos(request.test_photo_ids)
        return self._view(self.styles.create(request))

    def update(self, style_id: str, update: StyleUpdate) -> StyleView:
        if update.test_photo_ids is not None:
            self._check_photos(update.test_photo_ids)
        before = self.styles.get(style_id).look_hash()
        style = self.styles.update(style_id, update)
        if style.look_hash() != before:
            self._restyle(style_id)
        return self._view(style)

    def duplicate(self, style_id: str, name: str | None = None) -> StyleView:
        return self._view(self.styles.duplicate(style_id, name))

    def revert(self, style_id: str, version: int, *, expected_version: int) -> StyleView:
        style = self.styles.revert(style_id, version, expected_version=expected_version)
        self._restyle(style_id)
        return self._view(style)

    def delete(self, style_id: str) -> int:
        """Delete the style. Photos using it drop back to no style and keep their tweaks. Returns how many."""
        self.styles.get(style_id)  # NotFoundError before touching any photo
        ids = self.library.catalog.photo_ids_with_style(style_id)
        for pid in ids:
            photo = self.library.photo(pid)
            self.library.record_edit(photo, self.library.edits.apply_style(photo, None))
        self.styles.delete(style_id)
        self.library.render_thumbnails(ids)
        return len(ids)

    def _restyle(self, style_id: str) -> None:
        """The style's look changed: new revisions for its photos, and their thumbnails again."""
        ids = self.library.catalog.photo_ids_with_style(style_id)
        for pid in ids:
            photo = self.library.photo(pid)
            self.library.record_edit(photo, self.library.edits.effective(photo))
        self.library.render_thumbnails(ids)

    # ---- applying

    def set_photo_style(self, photo_id: str, style_id: str | None) -> None:
        """Give one photo a style (None removes it) right away, e.g. from the Photo view."""
        photo = self.library.photo(photo_id)
        self.library.record_edit(photo, self.library.edits.apply_style(photo, style_id))
        self.library.render_thumbnails([photo.id])

    def apply(
        self,
        photo_ids: list[str],
        style_id: str | None,
        *,
        even_out: bool = False,
        then: Callable[[], None] | None = None,
    ) -> Job:
        """Apply ``style_id`` (None removes the style) to the photos as a job; it writes edit files only.

        With ``even_out``, every photo is measured first, then the group's medians are stored with each photo,
        so the style's exposure rule evens the photos out against each other. ``then`` runs after the job.
        """
        photos = [self.library.photo(pid) for pid in photo_ids]
        style = self.styles.get(style_id) if style_id is not None else None
        noun = "photo" if len(photos) == 1 else "photos"
        if style is None:
            title = f"Remove the style from {len(photos)} {noun}"
        else:
            title = f"Apply {style.name} to {len(photos)} {noun}" + (" (evened out)" if even_out else "")
        items = [ItemSpec(filename=p.path.name, photo_id=p.id) for p in photos]
        grouped = even_out and style is not None

        def apply_one(index: int, group: GroupReference | None) -> None:
            photo = photos[index]
            self.library.record_edit(photo, self.library.edits.apply_style(photo, style_id, group=group))

        def work(index: int) -> ItemResult:
            if grouped:
                self.library.rule_inputs(photos[index])  # measure now; applied together in finish()
                return ItemResult(photo_id=photos[index].id, message="measured")
            apply_one(index, None)
            return ItemResult(photo_id=photos[index].id)

        def finish() -> str:
            summary = f"{len(photos)} {noun}"
            if grouped:
                group = self._group(photos)
                failed = 0
                for index in range(len(photos)):
                    try:
                        apply_one(index, group)
                    except (
                        Exception
                    ):  # a photo that can't be measured or read: the others still get the style
                        failed += 1
                summary += f", evened out as a group of {group.size}" + (
                    f"; {failed} failed" if failed else ""
                )
            self.library.render_thumbnails([p.id for p in photos])
            if then is not None:
                then()
            return summary

        return self.jobs.submit(
            JobKind.APPLY_STYLE, title, items, work, parallel=APPLY_THREADS, finish=finish, style_id=style_id
        )

    def _group(self, photos: list[CatalogPhoto]) -> GroupReference:
        middles, whites, evs = [], [], []
        for photo in photos:
            try:
                inputs = self.library.rule_inputs(photo)
            except Exception:  # unreadable: not part of the group's reference
                continue
            if inputs.stats is not None:
                middles.append(inputs.stats.middle)
                whites.append(inputs.stats.white)
            if inputs.camera_ev is not None:
                evs.append(inputs.camera_ev)
        return GroupReference(
            id=self._group_ids(),
            size=len(photos),
            middle=_median(middles),
            white=_median(whites),
            camera_ev=_median(evs),
        )

    # ---- from a photo

    def create_from_photo(self, request: StyleFromPhoto) -> StyleView:
        photo = self.library.photo(request.photo_id)
        edit = self.library.edits.effective(photo)
        groups = {g.value for g in request.groups}
        values = {
            name: value
            for name, value in differences(source_defaults(photo.kind), edit.adjustments).items()
            if name.split(".", 1)[0] in groups
            and not name.startswith(_NEVER_FROM_PHOTO)
            and name != "tone.exposure"
        }
        rules: list[ExposureRule | WhiteBalanceRule] = []
        exposure = edit.adjustments.tone.exposure
        if request.exposure is ExposureFromPhoto.VALUE and exposure != 0:
            values["tone.exposure"] = exposure
        elif request.exposure is ExposureFromPhoto.MATCH:
            stats = self.library.rule_inputs(photo).stats
            if stats is None:
                raise InvalidRequestError(
                    f"'{photo.path.name}' can't be measured, so its brightness can't be matched"
                )
            target = min(max(stats.middle + exposure, TARGET_RANGE[0]), TARGET_RANGE[1])
            rules.append(ExposureRule(target=round(target, 2)))
        if request.white_balance is WhiteBalanceFromPhoto.OFFSET:
            offset = self._white_balance_offset(photo, edit.adjustments.white_balance)
            if offset is not None:
                rules.append(offset)
        create = StyleCreate(
            name=request.name,
            description=request.description,
            values=values,
            rules=rules,
            test_photo_ids=[photo.id],
        )
        return self._view(self.styles.create(create, change_note=f"created from {photo.path.name}"))

    def update_from_photo(self, style_id: str, request: StyleUpdateFromPhoto) -> StyleView:
        """Replace the chosen groups of the style with the photo's values. The photo then keeps only the
        tweaks that differ from the updated style."""
        style = self.styles.get(style_id)
        photo = self.library.photo(request.photo_id)
        edit = self.library.edits.effective(photo)
        groups = {g.value for g in request.groups}
        has_exposure_rule = style.rule(ExposureRule) is not None
        values = {n: v for n, v in style.values.items() if n.split(".", 1)[0] not in groups}
        for name, value in differences(source_defaults(photo.kind), edit.adjustments).items():
            if name.split(".", 1)[0] not in groups or name.startswith(_NEVER_FROM_PHOTO):
                continue
            if name == "tone.exposure" and has_exposure_rule:
                continue  # the rule sets exposure per photo
            values[name] = value
        note = request.change_note or f"updated {', '.join(sorted(groups))} from {photo.path.name}"
        updated = self.update(
            style_id, StyleUpdate(expected_version=request.expected_version, values=values, change_note=note)
        )
        if photo.style_id == style_id:
            fresh = self.library.photo(photo.id)
            self.library.record_edit(fresh, self.library.edits.save(fresh, edit.adjustments))
            self.library.render_thumbnails([photo.id])
        return updated

    def _white_balance_offset(self, photo: CatalogPhoto, wb: WhiteBalance) -> WhiteBalanceRule | None:
        """The photo's white balance as an as-shot-relative rule (None if it's as shot)."""
        temperature, tint = wb.temperature, wb.tint
        as_shot = self.library.as_shot(photo)
        if as_shot is None or (temperature is None and tint is None):
            return None
        t = temperature if temperature is not None else as_shot[0]
        # The inverse of style_rules.shift_temperature: the same mired shift, expressed at 5500 K.
        mired_shift = 1e6 / t - 1e6 / as_shot[0]
        offset = 1e6 / (1e6 / OFFSET_REFERENCE_KELVIN + mired_shift) - OFFSET_REFERENCE_KELVIN
        tint_offset = (tint if tint is not None else as_shot[1]) - as_shot[1]
        return WhiteBalanceRule(
            temperature_offset=round(min(max(offset, OFFSET_RANGE[0]), OFFSET_RANGE[1]), 0),
            tint_offset=round(min(max(tint_offset, TINT_OFFSET_RANGE[0]), TINT_OFFSET_RANGE[1]), 1),
        )

    # ---- samples

    def render_samples(self, style_id: str, photo_ids: list[str]) -> Job:
        """Render before (default look) / after (the style, no per-photo tweaks) pairs into ``samples/``."""
        style = self.styles.get(style_id)
        photos = [self.library.photo(pid) for pid in photo_ids]
        names = [f"{i + 1:02d}" for i in range(len(photos))]
        rendered: dict[int, StyleSample] = {}

        def work(index: int) -> ItemResult:
            photo = photos[index]
            before = self.library.renderer.preview(photo, self.library.edits.default(photo), SAMPLE_LONG_EDGE)
            styled = self.library.edits.styled_edit(photo, style)
            after = self.library.renderer.preview(photo, styled, SAMPLE_LONG_EDGE)
            self._guard.write_atomic(self.styles.sample_path(style_id, names[index], "before"), before)
            self._guard.write_atomic(self.styles.sample_path(style_id, names[index], "after"), after)
            rendered[index] = StyleSample(
                photo_id=photo.id, caption=photo.path.stem, name=names[index], look_hash=style.look_hash()
            )
            return ItemResult(photo_id=photo.id)

        def finish() -> str:
            samples = [rendered[i] for i in sorted(rendered)]
            self._remove_sample_files(style_id, keep={s.name for s in samples})
            self.styles.set_samples(style_id, samples)
            return f"{len(samples)} sample{'s' if len(samples) != 1 else ''} rendered"

        noun = "sample" if len(photos) == 1 else "samples"
        return self.jobs.submit(
            JobKind.RENDER,
            f"Render {len(photos)} {noun} of {style.name}",
            [ItemSpec(filename=p.path.name, photo_id=p.id) for p in photos],
            work,
            parallel=APPLY_THREADS,
            finish=finish,
            style_id=style_id,
        )

    def render_version(self, style_id: str, version: int, photo_id: str, long_edge: int) -> bytes:
        """``photo`` with ``version`` of the style and none of its own tweaks (to compare versions)."""
        style = self.styles.version(style_id, version)
        photo = self.library.photo(photo_id)
        stored = self.library.edits.load(photo.id)
        group = stored.group if stored is not None and stored.style_id == style_id else None
        edit = self.library.edits.styled_edit(photo, style, group=group)
        return self.library.renderer.preview(photo, edit, long_edge)

    def sample_image(self, style_id: str, name: str, which: Literal["before", "after"]) -> bytes:
        style = self.styles.get(style_id)
        if not any(s.name == name for s in style.samples):
            raise NotFoundError(f"style '{style_id}' has no sample '{name}'")
        path = self.styles.sample_path(style_id, name, which)
        if not path.is_file():
            raise NotFoundError(
                f"sample '{name}' of style '{style_id}' is missing (render the samples again)"
            )
        return path.read_bytes()

    def _remove_sample_files(self, style_id: str, keep: set[str]) -> None:
        folder = self.styles.folder(style_id) / SAMPLES_DIR
        for file in folder.glob("*.jpg") if folder.is_dir() else ():
            if file.stem.rsplit("-", 1)[0] not in keep:
                self._guard.assert_writable(file)
                file.unlink(missing_ok=True)

    # ---- consistency report

    def report(self, style_id: str | None, photo_ids: list[str] | None = None) -> ConsistencyReport:
        """How consistent the photos come out: measurements before and after the style, and their spread.

        "After" is in scene terms (the photo's measurements moved by its exposure and white balance), before
        tone curves and color, so it shows what the adaptive rules did. With a style, each photo gets the
        style without its own tweaks (and with its group if it was evened out with this style); without one,
        each photo's current edit.
        """
        style = self.styles.get(style_id) if style_id is not None else None
        if photo_ids is None:
            if style is None:
                raise InvalidRequestError("name the photos to report on, or a style")
            photo_ids = style.test_photo_ids or self.library.catalog.photo_ids_with_style(style.id)
        if not photo_ids:
            raise InvalidRequestError("no photos to report on: give the style a test set or apply it first")
        rows: list[tuple[ReportPhoto, float | None]] = []
        for pid in photo_ids:
            photo = self.library.photo(pid)
            inputs = self.library.rule_inputs(photo)
            if style is not None:
                stored = self.library.edits.load(photo.id)
                group = stored.group if stored is not None and stored.style_id == style.id else None
                edit = self.library.edits.styled_edit(photo, style, group=group)
            else:
                edit = self.library.edits.effective(photo)
            stats, as_shot = inputs.stats, inputs.as_shot
            exposure = edit.adjustments.tone.exposure
            wb = edit.adjustments.white_balance
            before = PhotoMeasurements(
                middle=stats.middle if stats else None,
                white=stats.white if stats else None,
                temperature=as_shot[0] if as_shot else None,
                tint=as_shot[1] if as_shot else None,
            )
            after = PhotoMeasurements(
                middle=round(stats.middle + exposure, 4) if stats else None,
                white=round(stats.white + exposure, 4) if stats else None,
                temperature=wb.temperature if wb.temperature is not None else before.temperature,
                tint=wb.tint if wb.tint is not None else before.tint,
            )
            row = ReportPhoto(
                photo_id=photo.id,
                filename=photo.path.name,
                camera_ev=inputs.camera_ev,
                before=before,
                after=after,
                rules=edit.rules,
                deviation=0.0,
            )
            rows.append((row, after.middle))
        center = _median([m for _, m in rows if m is not None])
        photos = [row.model_copy(update={"deviation": _deviation(m, center)}) for row, m in rows]
        return ConsistencyReport(
            style_id=style.id if style else None,
            look_hash=style.look_hash() if style else None,
            photos=photos,
            spread=[_spread(name, photos) for name in ("middle", "white", "temperature", "tint")],
        )

    def _check_photos(self, photo_ids: Iterable[str]) -> None:
        unknown = [pid for pid in photo_ids if self.library.catalog.get(pid) is None]
        if unknown:
            raise InvalidRequestError(f"unknown photo id(s) in the test set: {', '.join(unknown)}")


def _deviation(value: float | None, center: float | None) -> float:
    return round(value - center, 4) if value is not None and center is not None else 0.0


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 4) if values else None


def _spread(measure: str, photos: list[ReportPhoto]) -> Spread:
    def values(which: str) -> list[float]:
        found = [getattr(getattr(p, which), measure) for p in photos]
        return [v for v in found if v is not None]

    def mad(xs: list[float]) -> float:
        if not xs:
            return 0.0
        center = statistics.median(xs)
        return round(statistics.median(abs(x - center) for x in xs), 4)

    before, after = values("before"), values("after")
    return Spread(
        measure=measure,
        before_mad=mad(before),
        after_mad=mad(after),
        before_range=round(max(before) - min(before), 4) if before else 0.0,
        after_range=round(max(after) - min(after), 4) if after else 0.0,
    )
