"""Suggested crops (P6b.7): the largest crop of a ratio that keeps the subject, placed centered or on thirds.

Pure math in the frame of a geometry (after flips and the quarter turn, in pixels of any size). For a crop of
half size (k·W₁, k·H₁), where W₁ × H₁ is the largest axis-aligned crop of the ratio, every condition on its
center is linear:

- it lies inside the frame,
- it lies inside the straightened image (each corner, turned back by the angle, inside the frame's bounds),
- it contains the subject box plus a margin of ``MARGIN`` of the crop on each side (or up to the frame's edge
  where that is closer: a subject at the edge of the photo can't have more).

The centers that satisfy them form a convex polygon. A crop that keeps the subject can always shrink down to
the subject's own size and still keep it, so the largest k with a non-empty polygon is found by bisection.
The crop's center is then the point of the polygon closest to where the placement wants it.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

from photoedit.core.geometry import Rect, crop_inside
from photoedit.models.adjustments import CropRect
from photoedit.models.crop import CropPlacement
from photoedit.models.subject import SubjectBox

MARGIN = 0.05
# The smallest crop (fraction of the largest one) a zoom can ask for: well above CropRect's 1 % minimum.
_MIN_K = 0.02
_BISECTIONS = 40
_TOLERANCE = 1e-9
# Crops are shrunk by this factor around their center if rounding put a corner a hair outside.
_SAFETY = 1 - 1e-9

type Constraint = tuple[float, float, float]  # a·x + b·y ≤ c


@dataclass(frozen=True)
class Suggestion:
    crop: CropRect
    zoom: float
    cut_off: str | None = None  # "wider" or "taller" when the subject doesn't fit in the crop


def suggest(
    subject: SubjectBox | None,
    *,
    ratio: float,
    angle: float,
    width: float,
    height: float,
    placement: CropPlacement = CropPlacement.CENTERED,
    zoom: float = 1.0,
) -> Suggestion:
    """The suggested crop of ``ratio`` (width ÷ height) in a ``width`` × ``height`` frame straightened by
    ``angle``, framing ``subject`` (normalized to the frame; None = center the crop)."""
    if width / height > ratio:
        base_hw, base_hh = height * ratio / 2, height / 2
    else:
        base_hw, base_hh = width / 2, width / ratio / 2
    frame = _Frame(width, height, angle, base_hw, base_hh)
    center = (width / 2, height / 2)

    if subject is None:
        k = frame.largest(None) / zoom
        return Suggestion(frame.crop(k, frame.closest(k, None, center)), zoom)

    box = (subject.left * width, subject.top * height, subject.right * width, subject.bottom * height)
    need_w = _needed(box[0], box[2], width) / (2 * base_hw)
    need_h = _needed(box[1], box[3], height) / (2 * base_hh)
    k_subject = max(need_w, need_h, _MIN_K)
    k_best = frame.largest(box) if frame.feasible(k_subject, box) else None
    if k_best is None:
        # The subject (plus margin) doesn't fit any crop: the largest crop, centered on it as far as it goes.
        k = frame.largest(None) / zoom
        target = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        cut = "wider" if need_w >= need_h else "taller"
        return Suggestion(frame.crop(k, frame.closest(k, None, target)), zoom, cut_off=cut)
    k = max(k_subject, k_best / zoom)
    target = _target(box, k * base_hw, k * base_hh, placement, width, height)
    return Suggestion(frame.crop(k, frame.closest(k, box, target)), k_best / k)


def _needed(start: float, end: float, length: float) -> float:
    """The smallest crop side that holds [start, end] plus the margin, where the margin stops at the frame's
    edges (0 and ``length``). The span grows with the crop by at most 2 × MARGIN of it, so the shortfall is
    increasing and bisection finds where it turns positive."""

    def holds(side: float) -> bool:
        margin = MARGIN * side
        return side >= min(length, end + margin) - max(0.0, start - margin)

    low, high = 0.0, max(length, (end - start) / (1 - 2 * MARGIN))
    for _ in range(_BISECTIONS):
        middle = (low + high) / 2
        if holds(middle):
            high = middle
        else:
            low = middle
    return high


def _target(
    box: tuple[float, float, float, float],
    hw: float,
    hh: float,
    placement: CropPlacement,
    width: float,
    height: float,
) -> tuple[float, float]:
    """Where the crop's center should be: on the subject's center, or so that the subject's center lands on
    the thirds intersection on the side of the frame the subject is on."""
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    if placement is CropPlacement.CENTERED:
        return cx, cy
    # A subject left of the middle goes on the left third line (the crop's center is to its right).
    dx = hw / 3 if cx < width / 2 else -hw / 3
    dy = hh / 3 if cy < height / 2 else -hh / 3
    return cx + dx, cy + dy


@dataclass(frozen=True)
class _Frame:
    width: float
    height: float
    angle: float
    base_hw: float
    base_hh: float

    def constraints(self, k: float, box: tuple[float, float, float, float] | None) -> list[Constraint]:
        hw, hh = k * self.base_hw, k * self.base_hh
        out: list[Constraint] = [
            (1, 0, self.width - hw),
            (-1, 0, -hw),
            (0, 1, self.height - hh),
            (0, -1, -hh),
        ]
        if self.angle:
            a = math.radians(-self.angle)  # turned back by the angle: rows of the inverse rotation
            rows = ((math.cos(a), -math.sin(a)), (math.sin(a), math.cos(a)))
            limits = (self.width / 2, self.height / 2)
            fx, fy = self.width / 2, self.height / 2
            for (rx, ry), limit in zip(rows, limits, strict=True):
                for ox, oy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
                    offset = rx * (ox - fx) + ry * (oy - fy)
                    out.append((rx, ry, limit - offset))
                    out.append((-rx, -ry, limit + offset))
        if box is not None:
            # The crop's edges reach past the subject by the margin, or to the frame's edge if that's closer.
            mw, mh = 2 * MARGIN * hw, 2 * MARGIN * hh
            left, top = max(0.0, box[0] - mw), max(0.0, box[1] - mh)
            right, bottom = min(self.width, box[2] + mw), min(self.height, box[3] + mh)
            out += [(1, 0, left + hw), (-1, 0, hw - right), (0, 1, top + hh), (0, -1, hh - bottom)]
        return out

    def feasible(self, k: float, box: tuple[float, float, float, float] | None) -> bool:
        return _closest(self.constraints(k, box), (self.width / 2, self.height / 2)) is not None

    def largest(self, box: tuple[float, float, float, float] | None) -> float:
        """The largest k (≤ 1) with a valid center; ``box`` must fit at ``_MIN_K`` or above when given."""
        if self.feasible(1.0, box):
            return 1.0
        low, high = _MIN_K, 1.0
        for _ in range(_BISECTIONS):
            middle = (low + high) / 2
            if self.feasible(middle, box):
                low = middle
            else:
                high = middle
        return low

    def closest(
        self, k: float, box: tuple[float, float, float, float] | None, target: tuple[float, float]
    ) -> tuple[float, float]:
        point = _closest(self.constraints(k, box), target)
        if point is None:  # only through float noise at the edge of feasibility
            point = _closest(self.constraints(k, None), target) or (self.width / 2, self.height / 2)
        return point

    def crop(self, k: float, center: tuple[float, float]) -> CropRect:
        rect = Rect(center[0], center[1], k * self.base_hw, k * self.base_hh)
        crop = rect.to_crop(self.width, self.height)
        while not crop_inside(crop, self.angle, self.width, self.height):
            rect = Rect(rect.cx, rect.cy, rect.hw * _SAFETY, rect.hh * _SAFETY)
            crop = rect.to_crop(self.width, self.height)
        return crop


def _satisfies(constraints: list[Constraint], point: tuple[float, float], scale: float) -> bool:
    x, y = point
    return all(a * x + b * y <= c + _TOLERANCE * scale for a, b, c in constraints)


def _closest(constraints: list[Constraint], target: tuple[float, float]) -> tuple[float, float] | None:
    """The point satisfying every constraint that is closest to ``target``; None if there is none.

    In 2-D the closest point is the target itself, its projection onto one constraint's line, or a corner
    where two lines meet; checking them all is exact and cheap for a few dozen constraints.
    """
    scale = max(1.0, *(abs(c) for _, _, c in constraints))
    if _satisfies(constraints, target, scale):
        return target
    tx, ty = target
    candidates: list[tuple[float, float]] = []
    for a, b, c in constraints:
        norm = a * a + b * b
        if norm > 0:
            excess = (a * tx + b * ty - c) / norm
            candidates.append((tx - excess * a, ty - excess * b))
    for (a1, b1, c1), (a2, b2, c2) in itertools.combinations(constraints, 2):
        det = a1 * b2 - a2 * b1
        if abs(det) > 1e-12:
            candidates.append(((c1 * b2 - c2 * b1) / det, (a1 * c2 - a2 * c1) / det))
    feasible = [p for p in candidates if _satisfies(constraints, p, scale)]
    if not feasible:
        return None
    # Closest first; ties by position, so the result depends only on the inputs.
    return min(feasible, key=lambda p: (round((p[0] - tx) ** 2 + (p[1] - ty) ** 2, 9), p[0], p[1]))
