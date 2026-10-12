"""A photo's subject (P6b.6): detection input, caching per identity, manual boxes, missing models."""

from __future__ import annotations

import struct
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from helpers import write_jpeg
from photoedit.core.cache import ImageCache
from photoedit.core.catalog import Catalog, CatalogPhoto
from photoedit.core.errors import NotFoundError
from photoedit.core.jobs import JobManager
from photoedit.core.library import Library
from photoedit.core.subject.cues import RGB8
from photoedit.core.subject.service import NO_FACE_MODEL, NO_OBJECT_MODEL, Subjects
from photoedit.models.adjustments import Geometry
from photoedit.models.crop import CropPlacement, CropSuggestionRequest
from photoedit.models.export import Orientation
from photoedit.models.subject import (
    SubjectBox,
    SubjectCandidate,
    SubjectKind,
    SubjectSource,
)
from photoedit.safety import PathGuard

CAR_BOX = SubjectBox(left=0.6, top=0.4, right=0.8, bottom=0.6)


class FakeFinder:
    """Returns fixed candidates and counts its calls."""

    def __init__(self, *candidates: SubjectCandidate) -> None:
        self.candidates = list(candidates)
        self.calls = 0
        self.sizes: list[tuple[int, int]] = []

    def __call__(self, image: RGB8) -> list[SubjectCandidate]:
        self.calls += 1
        self.sizes.append((image.shape[1], image.shape[0]))
        return list(self.candidates)


@pytest.fixture
def library(tmp_path: Path) -> Iterator[Library]:
    workspace, photos = tmp_path / "workspace", tmp_path / "photos"
    write_jpeg(photos / "wide.jpg", (90, 120, 150), size=(400, 200))
    _fuji_jpeg(photos / "focused.jpg", (300, 50))
    guard = PathGuard(writable_roots=[workspace])
    jobs = JobManager()
    library = Library(
        Catalog(workspace / "catalog.sqlite", guard), ImageCache(workspace / "cache", guard), jobs, guard
    )
    jobs.wait(library.import_folder(photos).id, 60)
    yield library
    jobs.shutdown()
    library.catalog.close()


def _fuji_jpeg(path: Path, focus: tuple[int, int], size: tuple[int, int] = (400, 200)) -> None:
    entries = struct.pack("<HHII", 0x1022, 3, 1, 1) + struct.pack("<HHIHH", 0x1023, 3, 2, *focus)
    exif = Image.Exif()
    exif[0x010F] = "FUJIFILM"
    exif.get_ifd(0x8769)[0x927C] = b"FUJIFILM" + struct.pack("<IH", 12, 2) + entries + b"\0\0\0\0"
    # Mostly flat with soft noise, so no cue stands out and the focus point decides.
    pixels = np.random.default_rng(0).normal(128, 2, (size[1], size[0], 3)).clip(0, 255).astype(np.uint8)
    Image.fromarray(pixels).save(path, "JPEG", exif=exif.tobytes())


def _photo(library: Library, name: str) -> CatalogPhoto:
    photo = library.catalog.find(name)
    assert photo is not None
    return photo


def subjects(library: Library, tmp_path: Path, objects: FakeFinder, identity: str = "fake-1") -> Subjects:
    return Subjects(
        library, tmp_path / "no-models", objects=(objects, identity), faces=(FakeFinder(), "faces-1")
    )


def test_detects_once_and_reuses_the_stored_result(library: Library, tmp_path: Path) -> None:
    finder = FakeFinder(SubjectCandidate(box=CAR_BOX, kind=SubjectKind.CAR, score=0.9, label="car"))
    service = subjects(library, tmp_path, finder)
    photo = _photo(library, "wide")
    info = service.subject(photo)
    assert info.source is SubjectSource.DETECTED and info.kind is SubjectKind.CAR and info.box == CAR_BOX
    assert info.detector == service.identity() and info.notes == []
    assert finder.sizes == [(400, 200)]  # the photo's default look, never enlarged
    assert service.subject(photo) == info and finder.calls == 1
    assert library.catalog.subject(photo.id, service.identity()) == info

    # Another detection identity (a new model, engine or chooser) finds it again.
    other = subjects(library, tmp_path, finder, identity="fake-2")
    assert other.cached(photo) is None
    other.subject(photo)
    assert finder.calls == 2


def test_manual_box_wins_without_detecting(library: Library, tmp_path: Path) -> None:
    finder = FakeFinder(SubjectCandidate(box=CAR_BOX, kind=SubjectKind.CAR, score=0.9))
    service = subjects(library, tmp_path, finder)
    photo = _photo(library, "wide")
    manual = SubjectBox(left=0.1, top=0.1, right=0.3, bottom=0.5)
    info = service.set_manual(photo, manual)
    assert (info.source, info.box, info.kind) == (SubjectSource.MANUAL, manual, None)
    assert finder.calls == 0 and service.subject(photo).box == manual
    revision = library.edits.effective(photo).revision

    cleared = service.set_manual(photo, None)
    assert cleared.source is SubjectSource.DETECTED and cleared.box == CAR_BOX and finder.calls == 1
    assert library.edits.effective(photo).revision == revision
    # With a detection stored, a manual subject still lists what was found.
    assert service.set_manual(photo, manual).candidates == cleared.candidates


def test_without_detection_a_subject_says_so(library: Library, tmp_path: Path) -> None:
    service = subjects(library, tmp_path, FakeFinder())
    info = service.subject(_photo(library, "wide"), detect=False)
    assert info.source is SubjectSource.NONE and info.notes == ["Not detected yet."]


def test_the_focus_point_stands_in_when_nothing_is_found(library: Library, tmp_path: Path) -> None:
    service = subjects(library, tmp_path, FakeFinder())
    info = service.subject(_photo(library, "focused"))
    assert info.source is SubjectSource.AF_POINT and info.box is not None
    assert info.box.center == pytest.approx((0.75, 0.25), abs=0.01)


def test_missing_models_use_the_cues_and_say_so(library: Library, tmp_path: Path) -> None:
    service = Subjects(library, tmp_path / "no-models")
    info = service.subject(_photo(library, "wide"))
    assert info.notes == [NO_OBJECT_MODEL, NO_FACE_MODEL]
    assert "no-objects" in service.identity() and "no-faces" in service.identity()
    assert info.source is SubjectSource.NONE  # a flat photo: nothing stands out, no focus point


def test_a_missing_file_cant_be_detected(library: Library, tmp_path: Path) -> None:
    photo = _photo(library, "wide").model_copy(update={"path": tmp_path / "photos" / "gone.jpg"})
    with pytest.raises(NotFoundError, match=r"gone\.jpg"):
        subjects(library, tmp_path, FakeFinder()).subject(photo)


def test_detection_input_is_deterministic(library: Library, tmp_path: Path) -> None:
    service = subjects(library, tmp_path, FakeFinder())
    photo = _photo(library, "focused")
    first = service.detection_input(photo)
    assert first.dtype == np.uint8 and first.shape == (200, 400, 3)
    assert np.array_equal(first, service.detection_input(photo))


# ---- suggested crops (P6b.7)


def test_suggest_crop_frames_the_subject_in_the_drafts_frame(library: Library, tmp_path: Path) -> None:
    finder = FakeFinder(SubjectCandidate(box=CAR_BOX, kind=SubjectKind.CAR, score=0.9, label="car"))
    service = subjects(library, tmp_path, finder)
    photo = _photo(library, "wide")  # 400 × 200, the car at x 0.6-0.8, y 0.4-0.6
    square = service.suggest_crop(photo, CropSuggestionRequest(aspect="1:1"))
    assert (square.source, square.kind, square.aspect, square.warnings) == (
        SubjectSource.DETECTED,
        SubjectKind.CAR,
        "1:1",
        [],
    )
    assert square.subject == CAR_BOX and square.crop.top == 0 and square.crop.bottom == 1
    assert (square.crop.left + square.crop.right) / 2 == pytest.approx(0.7)
    assert square.crop.right - square.crop.left == pytest.approx(0.5)

    # The draft is turned 90° clockwise: the frame is 200 × 400 and the car is at x 0.4-0.6, y 0.6-0.8.
    turned = service.suggest_crop(photo, CropSuggestionRequest(aspect="1:1", geometry=Geometry(rotate=90)))
    assert turned.subject == SubjectBox(left=0.4, top=0.6, right=0.6, bottom=0.8)
    assert turned.crop.left == 0 and turned.crop.right == 1
    assert (turned.crop.top + turned.crop.bottom) / 2 == pytest.approx(0.7)
    assert finder.calls == 1  # the draft geometry never re-detects


@pytest.mark.parametrize(
    ("aspect", "orientation", "shown"),
    [
        ("4:5", Orientation.AUTO, "5:4"),  # a landscape frame turns the ratio landscape
        ("4:5", Orientation.PORTRAIT, "4:5"),
        ("5:4", Orientation.PORTRAIT, "4:5"),
        ("16:9", Orientation.LANDSCAPE, "16:9"),
    ],
)
def test_suggest_crop_orientation(
    library: Library, tmp_path: Path, aspect: str, orientation: Orientation, shown: str
) -> None:
    service = subjects(library, tmp_path, FakeFinder())
    result = service.suggest_crop(
        _photo(library, "wide"), CropSuggestionRequest(aspect=aspect, orientation=orientation)
    )
    assert result.aspect == shown


def test_suggest_crop_without_a_subject_centers_and_says_so(library: Library, tmp_path: Path) -> None:
    service = subjects(library, tmp_path, FakeFinder())
    result = service.suggest_crop(_photo(library, "wide"), CropSuggestionRequest(aspect="1:1", zoom=2))
    assert result.source is SubjectSource.NONE and result.warnings == ["no subject found: centered"]
    assert (result.crop.left, result.crop.right) == pytest.approx((0.375, 0.625))
    assert result.zoom == 2


def test_suggest_crop_reports_capped_zoom_and_uses_the_manual_box(library: Library, tmp_path: Path) -> None:
    service = subjects(library, tmp_path, FakeFinder())
    photo = _photo(library, "wide")
    manual = SubjectBox(left=0.1, top=0.2, right=0.3, bottom=0.8)
    service.set_manual(photo, manual)
    result = service.suggest_crop(
        photo, CropSuggestionRequest(aspect="1:1", zoom=10, placement=CropPlacement.THIRDS)
    )
    assert result.source is SubjectSource.MANUAL and result.subject == manual
    assert result.zoom < 10 and result.warnings == [
        f"zoom stopped at {result.zoom:.2f}×, where the subject fills the crop"
    ]
