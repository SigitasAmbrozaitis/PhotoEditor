"""The object detector (P6b.5): YOLOX-S (COCO classes) through OpenCV's ``cv2.dnn`` on the CPU.

Small subjects are the hard part: a drift car can be ~3 % of the frame width, ~60 px of the 2048 px detection
input but only ~19 px if the whole frame were squeezed into the model's 640 px input. So the detector runs on
overlapping 640 px tiles at full detection size, plus one pass over the whole frame for subjects larger than a
tile, and merges the results kind by kind (a car also called a truck is one vehicle).

A box that a tile cut off at an inner edge is dropped: the same object is whole in a neighboring tile (if it's
smaller than the overlap) or in the whole-frame pass. A box lying mostly inside a better one of the same kind
is a part (a tile that sees only a cat's head still says "cat") and is dropped too. The result is
bit-identical for the same image whatever OpenCV's thread count (measured 2026-10-11).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt

from photoedit.models.subject import SubjectBox, SubjectCandidate, SubjectKind

type RGB8 = npt.NDArray[np.uint8]
type F32 = npt.NDArray[np.float32]

TILE = 640
OVERLAP = 128
_STRIDES = (8, 16, 32)
_PAD_VALUE = 114.0  # YOLOX's letterbox gray
_SCORE = 0.3
_NMS_IOU = 0.45
# A box with at least this share of its area inside a better box of the same kind is a part of it.
_PART_OF = 0.7
_MAX_CANDIDATES = 40
# A tile box within this many pixels of an inner tile edge was cut off by the tile.
_EDGE = 2.0

COCO_CLASSES = (
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light",
    "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard",
    "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors",
    "teddy bear", "hair drier", "toothbrush",
)  # fmt: skip

# The classes that can be a photo's subject. Everything else (benches, bottles, traffic lights...) is ignored.
KIND_OF_CLASS: dict[str, SubjectKind] = {
    "car": SubjectKind.CAR,
    "truck": SubjectKind.CAR,
    "bus": SubjectKind.CAR,
    "motorcycle": SubjectKind.MOTORCYCLE,
    "bicycle": SubjectKind.MOTORCYCLE,
    "airplane": SubjectKind.AIRCRAFT,  # helicopters too
    "person": SubjectKind.PERSON,
    **{
        name: SubjectKind.ANIMAL
        for name in ("bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe")
    },
}
_CLASS_IDS = {COCO_CLASSES.index(name) for name in KIND_OF_CLASS}
_KINDS = list(SubjectKind)
_KIND_INDEX = {COCO_CLASSES.index(name): _KINDS.index(kind) for name, kind in KIND_OF_CLASS.items()}


@dataclass(frozen=True)
class Detections:
    """Boxes in pixels of the detection input: x, y, width, height."""

    boxes: F32
    scores: F32
    classes: npt.NDArray[np.int32]

    @classmethod
    def empty(cls) -> Detections:
        return cls(np.zeros((0, 4), np.float32), np.zeros(0, np.float32), np.zeros(0, np.int32))

    def __len__(self) -> int:
        return len(self.scores)


def tile_origins(length: int, tile: int = TILE, overlap: int = OVERLAP) -> list[int]:
    """Where tiles start along one side so they cover it with at least ``overlap`` px between neighbors."""
    if length <= tile:
        return [0]
    step = tile - overlap
    origins = list(range(0, length - tile + 1, step))
    if origins[-1] + tile < length:
        origins.append(length - tile)
    return origins


def _anchors() -> tuple[F32, F32]:
    grids, strides = [], []
    for stride in _STRIDES:
        cells = TILE // stride
        xs, ys = np.meshgrid(np.arange(cells), np.arange(cells))
        grids.append(np.stack((xs, ys), 2).reshape(-1, 2))
        strides.append(np.full((cells * cells, 1), stride))
    return np.concatenate(grids).astype(np.float32), np.concatenate(strides).astype(np.float32)


_GRID, _STRIDE = _anchors()


def decode_output(output: F32, score: float = _SCORE) -> Detections:
    """YOLOX's raw output (anchors × 85) as boxes of the classes of interest scoring at least ``score``."""
    rows = output.reshape(-1, 85)
    centers = (rows[:, :2] + _GRID) * _STRIDE
    sizes = np.exp(np.minimum(rows[:, 2:4], 20)) * _STRIDE
    class_scores = rows[:, 4:5] * rows[:, 5:]
    classes = class_scores.argmax(axis=1).astype(np.int32)
    scores = class_scores.max(axis=1)
    keep = (scores >= score) & np.isin(classes, list(_CLASS_IDS))
    boxes = np.concatenate([centers[keep] - sizes[keep] / 2, sizes[keep]], axis=1)
    return Detections(boxes.astype(np.float32), scores[keep].astype(np.float32), classes[keep])


def _cut_by_tile(boxes: F32, left: int, top: int, width: int, height: int) -> npt.NDArray[np.bool_]:
    """Boxes (tile pixels) touching a tile edge that is inside the image (not the image's own edge)."""
    x0, y0 = boxes[:, 0], boxes[:, 1]
    x1, y1 = x0 + boxes[:, 2], y0 + boxes[:, 3]
    cut = np.zeros(len(boxes), bool)
    if left > 0:
        cut |= x0 <= _EDGE
    if top > 0:
        cut |= y0 <= _EDGE
    if left + TILE < width:
        cut |= x1 >= TILE - _EDGE
    if top + TILE < height:
        cut |= y1 >= TILE - _EDGE
    return cut


def merge(found: list[Detections], iou: float = _NMS_IOU) -> Detections:
    """Non-maximum suppression per subject kind over all passes, then parts dropped; the best first."""
    boxes = np.concatenate([d.boxes for d in found]) if found else np.zeros((0, 4), np.float32)
    if not len(boxes):
        return Detections.empty()
    scores = np.concatenate([d.scores for d in found])
    classes = np.concatenate([d.classes for d in found])
    kinds = [_KIND_INDEX[int(c)] for c in classes]
    kept = cv2.dnn.NMSBoxesBatched(boxes.tolist(), scores.tolist(), kinds, _SCORE, iou)
    index = np.asarray(kept, dtype=np.int64).reshape(-1)
    # Best first; ties by position, so the order depends only on the boxes.
    order = sorted(index.tolist(), key=lambda i: (-float(scores[i]), float(boxes[i, 0]), float(boxes[i, 1])))
    whole: list[int] = []
    for i in order:
        if not any(kinds[j] == kinds[i] and _inside_share(boxes[i], boxes[j]) >= _PART_OF for j in whole):
            whole.append(i)
    whole = whole[:_MAX_CANDIDATES]
    return Detections(boxes[whole], scores[whole], classes[whole])


def _inside_share(box: F32, other: F32) -> float:
    """The share of ``box``'s area (x, y, w, h) that lies inside ``other``."""
    width = min(box[0] + box[2], other[0] + other[2]) - max(box[0], other[0])
    height = min(box[1] + box[3], other[1] + other[3]) - max(box[1], other[1])
    area = float(box[2] * box[3])
    return float(max(0.0, width) * max(0.0, height)) / area if area > 0 else 0.0


class ObjectDetector:
    """YOLOX on tiles + the whole frame. One network per thread: OpenCV's isn't thread-safe."""

    def __init__(self, model: Path) -> None:
        self._model = model
        self._local = threading.local()

    def detect(self, image: RGB8) -> Detections:
        """Merged detections in pixels of ``image`` (upright RGB)."""
        height, width = image.shape[:2]
        bgr = np.ascontiguousarray(image[:, :, ::-1], dtype=np.float32)
        found = [self._whole_frame(bgr)]
        for top in tile_origins(height):
            for left in tile_origins(width):
                tile = np.full((TILE, TILE, 3), _PAD_VALUE, np.float32)
                part = bgr[top : top + TILE, left : left + TILE]
                tile[: part.shape[0], : part.shape[1]] = part
                d = self._run(tile)
                keep = ~_cut_by_tile(d.boxes, left, top, width, height)
                boxes = d.boxes[keep] + np.array([left, top, 0, 0], np.float32)
                found.append(Detections(boxes, d.scores[keep], d.classes[keep]))
        return merge(found)

    def __call__(self, image: RGB8) -> list[SubjectCandidate]:
        height, width = image.shape[:2]
        found = self.detect(image)
        candidates = []
        for (x, y, w, h), score, cls in zip(found.boxes, found.scores, found.classes, strict=True):
            left, top = max(0.0, float(x) / width), max(0.0, float(y) / height)
            right, bottom = min(1.0, float(x + w) / width), min(1.0, float(y + h) / height)
            if right - left < 2 / width or bottom - top < 2 / height:
                continue
            name = COCO_CLASSES[int(cls)]
            candidates.append(
                SubjectCandidate(
                    box=SubjectBox(left=left, top=top, right=right, bottom=bottom),
                    kind=KIND_OF_CLASS[name],
                    score=round(float(score), 6),
                    label=name,
                )
            )
        return candidates

    def _whole_frame(self, bgr: F32) -> Detections:
        height, width = bgr.shape[:2]
        scale = min(TILE / height, TILE / width)
        size = (max(1, int(width * scale)), max(1, int(height * scale)))
        letterbox = np.full((TILE, TILE, 3), _PAD_VALUE, np.float32)
        letterbox[: size[1], : size[0]] = cv2.resize(bgr, size, interpolation=cv2.INTER_LINEAR)
        d = self._run(letterbox)
        return Detections(d.boxes / np.float32(scale), d.scores, d.classes)

    def _run(self, tile: F32) -> Detections:
        net = self._net()
        net.setInput(np.transpose(tile, (2, 0, 1))[np.newaxis])
        return decode_output(np.asarray(net.forward(), dtype=np.float32))

    def _net(self) -> cv2.dnn.Net:
        net: cv2.dnn.Net | None = getattr(self._local, "net", None)
        if net is None:
            net = cv2.dnn.readNet(str(self._model))
            self._local.net = net
        return net
