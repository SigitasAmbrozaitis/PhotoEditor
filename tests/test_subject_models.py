"""Subject models, the manual box in the edit file, and mapping upright boxes into a frame (P6b.2)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from photoedit.core.catalog import CatalogPhoto
from photoedit.core.edits import EditStore, PhotoEditFile
from photoedit.core.geometry import source_map, subject_in_frame, upright_to_frame
from photoedit.core.scan import SourceKind
from photoedit.core.styles import StyleLibrary
from photoedit.models import AdjustmentParams
from photoedit.models.adjustments import CropRect, Geometry
from photoedit.models.crop import CropSuggestionRequest
from photoedit.models.style import StyleCreate
from photoedit.models.subject import (
    SubjectBox,
    SubjectCandidate,
    SubjectInfo,
    SubjectKind,
    SubjectSource,
)
from photoedit.safety import PathGuard

W, H = 600.0, 400.0


def box(left: float, top: float, right: float, bottom: float) -> SubjectBox:
    return SubjectBox(left=left, top=top, right=right, bottom=bottom)


def close(a: SubjectBox | None, b: SubjectBox) -> bool:
    assert a is not None
    return bool(
        np.allclose([a.left, a.top, a.right, a.bottom], [b.left, b.top, b.right, b.bottom], atol=1e-9)
    )


# ---- models


@pytest.mark.parametrize(
    "values",
    [
        {"left": 0.5, "top": 0.1, "right": 0.4, "bottom": 0.2},  # left > right
        {"left": 0.1, "top": 0.1, "right": 0.101, "bottom": 0.2},  # too narrow
        {"left": -0.1, "top": 0.1, "right": 0.4, "bottom": 0.2},
        {"left": 0.1, "top": 0.1, "right": 0.4, "bottom": 1.2},
    ],
)
def test_bad_boxes_are_rejected(values: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        SubjectBox.model_validate(values)


def test_info_round_trip_and_box_rule() -> None:
    found = box(0.1, 0.2, 0.3, 0.5)
    info = SubjectInfo(
        source=SubjectSource.DETECTED,
        box=found,
        kind=SubjectKind.CAR,
        score=0.9,
        candidates=[SubjectCandidate(box=found, kind=SubjectKind.CAR, score=0.9, label="truck")],
        detector="yolox_s-c5c2d13e59ae-opencv5.0.0",
    )
    assert SubjectInfo.model_validate_json(info.model_dump_json()) == info
    assert found.center == pytest.approx((0.2, 0.35))
    with pytest.raises(ValidationError, match="exactly when"):
        SubjectInfo(source=SubjectSource.NONE, box=found)
    with pytest.raises(ValidationError, match="exactly when"):
        SubjectInfo(source=SubjectSource.MANUAL)
    assert SubjectInfo(source=SubjectSource.NONE).box is None


def test_suggestion_request_validation() -> None:
    assert CropSuggestionRequest(aspect="4:5").zoom == 1
    for bad in ({"aspect": "4/5"}, {"aspect": "4:5", "zoom": 0.5}):
        with pytest.raises(ValidationError):
            CropSuggestionRequest.model_validate(bad)


# ---- upright → frame


@pytest.mark.parametrize(
    ("geometry", "expected"),
    [
        (Geometry(), box(0.1, 0.2, 0.3, 0.6)),
        (Geometry(flip_horizontal=True), box(0.7, 0.2, 0.9, 0.6)),
        (Geometry(flip_vertical=True), box(0.1, 0.4, 0.3, 0.8)),
        # Clockwise quarter turn: normalized (x, y) → (1 - y, x).
        (Geometry(rotate=90), box(0.4, 0.1, 0.8, 0.3)),
        (Geometry(rotate=180), box(0.7, 0.4, 0.9, 0.8)),
        (Geometry(rotate=270), box(0.2, 0.7, 0.6, 0.9)),
        # The flip comes first, in upright coordinates.
        (Geometry(flip_horizontal=True, rotate=90), box(0.4, 0.7, 0.8, 0.9)),
    ],
)
def test_flips_and_turns_are_exact(geometry: Geometry, expected: SubjectBox) -> None:
    assert close(subject_in_frame(box(0.1, 0.2, 0.3, 0.6), geometry, W, H), expected)


def test_the_crop_doesnt_move_the_box() -> None:
    cropped = Geometry(crop=CropRect(left=0.2, top=0.1, right=0.7, bottom=0.9))
    assert close(subject_in_frame(box(0.1, 0.2, 0.3, 0.6), cropped, W, H), box(0.1, 0.2, 0.3, 0.6))


@pytest.mark.parametrize(
    "geometry", [Geometry(angle=45), Geometry(angle=-45, rotate=270, flip_vertical=True)]
)
def test_straightened_box_is_the_bounding_box_of_its_turned_corners(geometry: Geometry) -> None:
    centered = box(0.45, 0.45, 0.55, 0.55)  # 60 × 40 px around the center
    mapped = subject_in_frame(centered, geometry, W, H)
    assert mapped is not None
    frame_w, frame_h = (H, W) if geometry.rotate in (90, 270) else (W, H)
    # A 60 × 40 rectangle turned by 45° spans (60 + 40) / √2 px both ways.
    span = 100 / np.sqrt(2)
    assert (mapped.right - mapped.left) * frame_w == pytest.approx(span)
    assert (mapped.bottom - mapped.top) * frame_h == pytest.approx(span)
    assert mapped.center == pytest.approx((0.5, 0.5))


def test_a_box_turned_out_of_the_frame_is_cut_or_gone() -> None:
    corner = box(0.0, 0.0, 0.02, 0.02)
    assert subject_in_frame(corner, Geometry(angle=45), W, H) is None
    edge = subject_in_frame(box(0.0, 0.1, 0.2, 0.9), Geometry(angle=30), W, H)
    assert edge is not None and edge.left == 0


@pytest.mark.parametrize(
    "geometry",
    [Geometry(), Geometry(rotate=90, angle=7.5), Geometry(flip_horizontal=True, rotate=180, angle=-30)],
)
def test_mapping_is_the_inverse_of_the_render_source_map(geometry: Geometry) -> None:
    frame_w, frame_h = (H, W) if geometry.rotate in (90, 270) else (W, H)
    to_source = source_map(geometry, CropRect(), int(W), int(H), int(frame_w), int(frame_h))
    points = np.random.default_rng(1).uniform(0, 1, (2, 20))
    upright = np.vstack([points, np.ones(20)])
    frame = upright_to_frame(geometry, W, H) @ upright
    # source_map works on pixel centers; shift edge coordinates by half a pixel both ways.
    back = to_source @ np.vstack([frame[:2] - 0.5, np.ones(20)])
    assert np.allclose(back[:2] + 0.5, points * np.array([[W], [H]]))


# ---- the manual box in the edit file


def photo(pid: str = "abc123") -> CatalogPhoto:
    return CatalogPhoto(
        id=pid,
        sha256="0" * 64,
        path=Path("C:/photos/DSCF0001.RAF"),
        kind=SourceKind.RAW,
        file_size=1,
        mtime_ns=1,
        width=600,
        height=400,
    )


@pytest.fixture
def styles(tmp_path: Path) -> StyleLibrary:
    root = tmp_path / "styles"
    return StyleLibrary(
        root, PathGuard(writable_roots=[root]), clock=lambda: datetime(2026, 10, 11, tzinfo=UTC)
    )


@pytest.fixture
def store(tmp_path: Path, styles: StyleLibrary) -> EditStore:
    edits = tmp_path / "edits"
    return EditStore(edits, PathGuard(writable_roots=[edits]), styles=styles)


def test_manual_box_is_stored_without_changing_the_revision(store: EditStore) -> None:
    before = store.effective(photo()).revision
    manual = box(0.2, 0.3, 0.4, 0.6)
    store.set_subject(photo(), manual)
    assert store.subject("abc123") == manual
    assert store.effective(photo()).revision == before
    on_disk = json.loads(store.path("abc123").read_text(encoding="utf-8"))
    assert on_disk["subject"] == {"left": 0.2, "top": 0.3, "right": 0.4, "bottom": 0.6}
    assert "group" not in on_disk

    store.set_subject(photo(), None)
    assert store.subject("abc123") is None
    assert not store.path("abc123").exists()  # nothing else was stored


def test_manual_box_survives_tweaks_resets_and_styles(store: EditStore, styles: StyleLibrary) -> None:
    manual = box(0.2, 0.3, 0.4, 0.6)
    store.set_subject(photo(), manual)
    edited = AdjustmentParams.model_validate({"tone": {"exposure": 0.5}})
    tweaked = store.save(photo(), edited)
    assert store.subject("abc123") == manual
    store.reset_overrides(photo())
    assert store.subject("abc123") == manual
    style = styles.create(StyleCreate.model_validate({"name": "Warm", "values": {"tone.contrast": 10}}))
    store.apply_style(photo(), style.id)
    assert store.subject("abc123") == manual
    store.apply_style(photo(), None)
    assert store.subject("abc123") == manual
    # Same tweaks, same revision, with or without a subject.
    assert store.save(photo(), edited).revision == tweaked.revision


def test_old_edit_files_load(store: EditStore) -> None:
    store.path("abc123").parent.mkdir(parents=True)
    old = {"schema_version": 1, "photo_id": "abc123", "style_id": None, "overrides": {"tone.exposure": 1}}
    store.path("abc123").write_text(json.dumps(old), encoding="utf-8")
    loaded = store.load("abc123")
    assert loaded == PhotoEditFile(photo_id="abc123", overrides={"tone.exposure": 1})
    assert store.subject("abc123") is None


def test_subject_in_crop_is_normalized_to_the_edited_photo() -> None:
    from photoedit.core.geometry import subject_in_crop

    cropped = Geometry(crop=CropRect(left=0.2, top=0.1, right=0.7, bottom=0.9))
    inside = subject_in_crop(box(0.3, 0.3, 0.4, 0.5), cropped, W, H)
    assert close(inside, box(0.2, 0.25, 0.4, 0.5))
    partly = subject_in_crop(box(0.6, 0.3, 0.8, 0.5), cropped, W, H)  # cut at the crop's right edge
    assert close(partly, box(0.8, 0.25, 1.0, 0.5))
    assert subject_in_crop(box(0.75, 0.3, 0.9, 0.5), cropped, W, H) is None  # outside the crop
    turned = subject_in_crop(box(0.1, 0.2, 0.3, 0.6), Geometry(rotate=90), W, H)
    assert close(turned, box(0.4, 0.1, 0.8, 0.3))
