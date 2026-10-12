"""Choosing a photo's main subject from everything found (P6b.6).

Every candidate gets a total score: what the detector or cue says × how likely its kind is to be the subject
× a size factor (not a speck, not the whole frame) × how sharp it is compared to the photo (a panned car is
sharp on a blurred background) × a bonus when the camera focused on it. The best recognized candidate (a
vehicle, animal, face or person) wins if its total is high enough. Sharpness and saliency alone never make a
subject: on a sunset or an empty track they only guess (user decision 2026-10-12). Without a recognized
subject the camera's focus point stands in, and failing that there is none (crops center).

The rules are plain arithmetic on the candidates, so the same candidates always give the same subject. Bump
``CHOOSER_VERSION`` when they change, so cached results are recomputed.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from photoedit.core.metadata import AfMode
from photoedit.models.subject import SubjectBox, SubjectCandidate, SubjectInfo, SubjectKind, SubjectSource

CHOOSER_VERSION = 2

VEHICLES = frozenset({SubjectKind.CAR, SubjectKind.MOTORCYCLE, SubjectKind.AIRCRAFT})
PRIORITY: dict[SubjectKind, float] = {
    SubjectKind.CAR: 1.0,
    SubjectKind.MOTORCYCLE: 1.0,
    SubjectKind.AIRCRAFT: 0.9,
    SubjectKind.ANIMAL: 1.0,
    SubjectKind.FACE: 0.7,
    SubjectKind.PERSON: 0.6,
    SubjectKind.SALIENT: 0.35,
    SubjectKind.AF_POINT: 0.3,
}
# Cues that find something without knowing what it is: they rank candidates but never become the subject.
UNRECOGNIZED = frozenset({SubjectKind.SALIENT, SubjectKind.AF_POINT})
# People and faces next to a vehicle are the crowd, the marshals or the driver: weak, one region at most.
CROWD = 0.3
# The camera focusing inside a box multiplies its total by 1 + this (zone and wide modes report the zone's
# center, so they say less).
AF_BONUS: dict[AfMode, float] = {
    AfMode.SINGLE: 0.3,
    AfMode.UNKNOWN: 0.2,
    AfMode.ZONE: 0.1,
    AfMode.WIDE: 0.1,
    AfMode.MANUAL: 0.1,
    AfMode.NONE: 0.0,
}
# The best total must reach this to be the main subject.
MIN_MAIN = 0.15
# Vehicles of the same kind this good compared to the best one, and this close (in widths of the best box),
# join it: a tandem drift is one subject.
GROUP_SHARE = 0.5
GROUP_GAP = 1.0
# The focus point stands in as a square this big (fraction of the short side) when nothing else does.
AF_BOX = 0.1

# Mean relative sharpness inside a box (0 = the photo's median, 1 = clearly sharp), or None if unknown.
type SharpnessOf = Callable[[SubjectBox], float | None]


def size_factor(box: SubjectBox) -> float:
    """1 for ordinary sizes, less for specks (< 0.3 % of the frame) and for boxes filling most of it."""
    area = (box.right - box.left) * (box.bottom - box.top)
    if area < 0.0005:
        return 0.3
    if area < 0.003:
        return 0.3 + 0.7 * (area - 0.0005) / 0.0025
    if area <= 0.5:
        return 1.0
    return 1.0 - 0.6 * (area - 0.5) / 0.5


def sharpness_factor(sharpness: float | None) -> float:
    """0.7 for a box no sharper than the photo's median, up to 1 for a clearly sharp one."""
    if sharpness is None:
        return 1.0
    return 0.7 + 0.3 * min(1.0, max(0.0, sharpness))


def af_factor(box: SubjectBox, af_point: tuple[float, float] | None, af_mode: AfMode) -> float:
    if af_point is None:
        return 1.0
    x, y = af_point
    inside = box.left <= x <= box.right and box.top <= y <= box.bottom
    return 1.0 + AF_BONUS[af_mode] if inside else 1.0


def af_box(point: tuple[float, float], aspect: float) -> SubjectBox:
    """A square around the focus point, ``AF_BOX`` of the short side; ``aspect`` = width ÷ height."""
    half_w = AF_BOX / 2 / max(1.0, aspect)
    half_h = AF_BOX / 2 * min(1.0, aspect)
    x = min(1 - half_w, max(half_w, point[0]))
    y = min(1 - half_h, max(half_h, point[1]))
    return SubjectBox(left=x - half_w, top=y - half_h, right=x + half_w, bottom=y + half_h)


def choose(
    candidates: Sequence[SubjectCandidate],
    *,
    af_point: tuple[float, float] | None = None,
    af_mode: AfMode = AfMode.NONE,
    sharpness: SharpnessOf | None = None,
    aspect: float = 1.5,
    detector: str | None = None,
    notes: Sequence[str] = (),
) -> SubjectInfo:
    """The main subject among ``candidates``: boxes normalized to the photo, whose width ÷ height is
    ``aspect``."""
    vehicle_present = any(c.kind in VEHICLES for c in candidates)
    scored: list[SubjectCandidate] = []
    for candidate in candidates:
        total = candidate.score * PRIORITY[candidate.kind]
        if vehicle_present and candidate.kind in (SubjectKind.PERSON, SubjectKind.FACE):
            total *= CROWD
        total *= size_factor(candidate.box)
        total *= sharpness_factor(sharpness(candidate.box) if sharpness is not None else None)
        total *= af_factor(candidate.box, af_point, af_mode)
        scored.append(candidate.model_copy(update={"score": round(min(1.0, total), 6)}))
    # Best first; ties by kind priority and position, so the order depends only on the candidates.
    scored.sort(key=lambda c: (-c.score, -PRIORITY[c.kind], c.box.left, c.box.top))
    common = {"candidates": scored, "detector": detector, "notes": list(notes)}
    recognized = [c for c in scored if c.kind not in UNRECOGNIZED]
    if recognized and recognized[0].score >= MIN_MAIN:
        best = recognized[0]
        box = _grouped(best, scored) if best.kind in VEHICLES else best.box
        return SubjectInfo(source=SubjectSource.DETECTED, box=box, kind=best.kind, score=best.score, **common)
    if af_point is not None and af_mode is not AfMode.NONE:
        box = af_box(af_point, aspect)
        return SubjectInfo(source=SubjectSource.AF_POINT, box=box, kind=SubjectKind.AF_POINT, **common)
    return SubjectInfo(source=SubjectSource.NONE, **common)


def _grouped(best: SubjectCandidate, scored: Sequence[SubjectCandidate]) -> SubjectBox:
    """``best``'s box joined with nearby, nearly as good vehicles of its kind (a tandem drift)."""
    box = best.box
    reach = GROUP_GAP * (best.box.right - best.box.left)
    for other in scored[1:]:
        if other.kind is not best.kind or other.score < GROUP_SHARE * best.score:
            continue
        gap_x = max(0.0, max(other.box.left, box.left) - min(other.box.right, box.right))
        gap_y = max(0.0, max(other.box.top, box.top) - min(other.box.bottom, box.bottom))
        if gap_x <= reach and gap_y <= reach:
            box = SubjectBox(
                left=min(box.left, other.box.left),
                top=min(box.top, other.box.top),
                right=max(box.right, other.box.right),
                bottom=max(box.bottom, other.box.bottom),
            )
    return box
