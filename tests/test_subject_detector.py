"""The object detector (P6b.5): tiling, decoding and merging on synthetic data; the real model on samples."""

from __future__ import annotations

import time
from itertools import pairwise
from pathlib import Path

import numpy as np
import pytest

from photoedit.core.subject.detector import (
    COCO_CLASSES,
    OVERLAP,
    TILE,
    Detections,
    ObjectDetector,
    _cut_by_tile,
    decode_output,
    merge,
    tile_origins,
)
from photoedit.models.subject import SubjectKind

CAR, TRUCK, CAT, PERSON, BENCH = (COCO_CLASSES.index(n) for n in ("car", "truck", "cat", "person", "bench"))


def dets(*rows: tuple[float, float, float, float, float, int]) -> Detections:
    """Detections from (x, y, w, h, score, class) rows."""
    if not rows:
        return Detections.empty()
    array = np.array(rows, dtype=np.float64)
    return Detections(
        array[:, :4].astype(np.float32), array[:, 4].astype(np.float32), array[:, 5].astype(np.int32)
    )


# ---- tiling


@pytest.mark.parametrize(
    ("length", "origins"),
    [(300, [0]), (640, [0]), (641, [0, 1]), (1365, [0, 512, 725]), (2048, [0, 512, 1024, 1408])],
)
def test_tile_origins(length: int, origins: list[int]) -> None:
    assert tile_origins(length) == origins


@pytest.mark.parametrize("length", range(641, 5000, 97))
def test_tiles_cover_with_overlap(length: int) -> None:
    origins = tile_origins(length)
    assert origins[0] == 0 and origins[-1] + TILE == length
    assert all(b - a <= TILE - OVERLAP for a, b in pairwise(origins))


def test_boxes_cut_by_inner_tile_edges() -> None:
    boxes = np.array(
        [[0, 100, 50, 50], [300, 300, 40, 40], [600, 100, 40, 40], [100, 610, 30, 30]], dtype=np.float32
    )
    # A middle tile of a large image: every edge is inside the image.
    assert _cut_by_tile(boxes, 512, 512, 3000, 3000).tolist() == [True, False, True, True]
    # The top-left tile of an image as small as the tile: its edges are the image's own.
    assert _cut_by_tile(boxes, 0, 0, 640, 640).tolist() == [False, False, False, False]


# ---- decoding


def _raw_output() -> np.ndarray:
    output = np.zeros((8400, 85), np.float32)
    output[:, 4] = 0.0  # no objectness anywhere
    return output


def test_decode_output_places_boxes_on_the_anchor_grid() -> None:
    output = _raw_output()
    # Anchor 0 of stride 8 is cell (0, 0); anchor 81 is cell (1, 1) of the 80 × 80 grid.
    output[81, :4] = [0.5, 0.25, np.log(4.0), np.log(2.0)]  # center (1.5, 1.25) cells, size 4 × 2 cells
    output[81, 4] = 0.9
    output[81, 5 + CAR] = 0.8
    output[0, 4] = 0.9
    output[0, 5 + BENCH] = 0.95  # not a subject class
    output[1, 4] = 0.5
    output[1, 5 + CAT] = 0.4  # 0.2: below the score
    found = decode_output(output)
    assert found.classes.tolist() == [CAR]
    assert found.scores.tolist() == pytest.approx([0.72])
    assert found.boxes.tolist() == [pytest.approx([12 - 16, 10 - 8, 32, 16])]


def test_decode_output_of_nothing() -> None:
    assert len(decode_output(_raw_output())) == 0


# ---- merging


def test_duplicates_across_passes_and_related_classes_merge() -> None:
    merged = merge(
        [
            dets((100, 100, 50, 30, 0.9, CAR), (400, 400, 40, 80, 0.7, PERSON)),
            dets((102, 101, 50, 30, 0.8, TRUCK)),  # the same vehicle, called a truck
        ]
    )
    assert merged.classes.tolist() == [CAR, PERSON]
    assert merged.scores.tolist() == pytest.approx([0.9, 0.7])


def test_parts_inside_a_better_box_of_the_same_kind_are_dropped() -> None:
    merged = merge(
        [
            dets((0, 0, 400, 300, 0.95, CAT)),
            dets((50, 50, 120, 100, 0.85, CAT), (60, 60, 100, 200, 0.8, PERSON)),
        ]
    )
    # The cat's head goes; the person in front of the cat is another kind and stays.
    assert merged.classes.tolist() == [CAT, PERSON]


def test_separate_objects_stay_best_first() -> None:
    merged = merge([dets((500, 0, 50, 50, 0.6, CAR), (0, 0, 50, 50, 0.6, CAR), (200, 0, 50, 50, 0.9, CAR))])
    assert merged.boxes[:, 0].tolist() == [200, 0, 500]  # by score, then position


def test_merge_of_nothing() -> None:
    assert len(merge([])) == 0 and len(merge([Detections.empty(), Detections.empty()])) == 0


# ---- the real model


@pytest.fixture(scope="module")
def detector() -> ObjectDetector:
    from photoedit.config import load_settings
    from photoedit.core.subject.model_files import MODEL_FILES, OBJECT_MODEL, verified_model_path

    path = verified_model_path(load_settings().cache_dir, MODEL_FILES[OBJECT_MODEL])
    if path is None:
        pytest.skip("the YOLOX model is not fetched (photoedit models fetch)")
    return ObjectDetector(path)


def test_no_detections_in_a_flat_image(detector: ObjectDetector) -> None:
    assert detector(np.full((1365, 2048, 3), 128, np.uint8)) == []


@pytest.mark.golden
def test_finds_the_rally_car_the_same_way_twice(
    detector: ObjectDetector, style_sample_dirs: dict[str, Path]
) -> None:
    from PIL import Image, ImageOps

    folder = style_sample_dirs.get("2026-08-16")
    if folder is None or not (folder / "DSCF6100.JPG").is_file():
        pytest.skip("the rally sample folder is missing")
    with Image.open(folder / "DSCF6100.JPG") as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    image.thumbnail((2048, 2048))
    pixels = np.asarray(image)
    start = time.perf_counter()
    found = detector(pixels)
    seconds = time.perf_counter() - start
    best = found[0]
    assert (best.kind, best.label) == (SubjectKind.CAR, "car") and best.score > 0.8
    # The car jumping over the crest, in the middle of the portrait frame.
    assert best.box.center == pytest.approx((0.48, 0.52), abs=0.05)
    assert detector(pixels.copy()) == found
    assert seconds < 20, f"detection took {seconds:.1f} s"
