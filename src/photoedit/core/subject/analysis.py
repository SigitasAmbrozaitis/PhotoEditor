"""What detection found, as the user sees it (Phase 6c feedback): the subject, every candidate and the
camera's focus point, mapped into the edited photo (through its flips, turn, straighten and crop).

The Photo view's AI Analysis tab and the pre-export review both show this, so boxes drawn on the edited photo
line up with it. Nothing here detects anything; it only maps what is stored.
"""

from __future__ import annotations

from photoedit.core.geometry import subject_in_crop
from photoedit.core.subject.choose import UNRECOGNIZED, af_box
from photoedit.models.adjustments import Geometry
from photoedit.models.subject import FoundCandidate, SubjectAnalysis, SubjectBox, SubjectInfo, SubjectKind

# Candidates shown at most (best first); detection keeps more, mostly weak guesses.
MAX_SHOWN = 12
# A candidate with at least this share of its area inside the subject's box is part of it (the driver in
# the car, the second car of a tandem the chooser grouped, a face of the person).
PART_OF = 0.5


def overlap(box: SubjectBox, other: SubjectBox) -> float:
    """The share of ``box``'s area inside ``other``."""
    width = max(0.0, min(box.right, other.right) - max(box.left, other.left))
    height = max(0.0, min(box.bottom, other.bottom) - max(box.top, other.top))
    area = (box.right - box.left) * (box.bottom - box.top)
    return width * height / area if area > 0 else 0.0


def is_part(candidate: SubjectBox, subject: SubjectBox) -> bool:
    return overlap(candidate, subject) >= PART_OF


def found_candidates(
    info: SubjectInfo,
    geometry: Geometry,
    width: int,
    height: int,
    subject: SubjectBox | None,
    kind: SubjectKind | None = None,
) -> list[FoundCandidate]:
    """``info``'s candidates inside the edited photo (best first, at most ``MAX_SHOWN``), each marked when it
    is the ``subject`` (normalized to the edited photo): inside its box and, for a detected subject, of its
    ``kind`` (a person inside a car's box is the driver, not the subject)."""
    out: list[FoundCandidate] = []
    for index, candidate in enumerate(info.candidates):
        box = subject_in_crop(candidate.box, geometry, width, height)
        if box is None:
            continue
        recognized = candidate.kind not in UNRECOGNIZED
        out.append(
            FoundCandidate(
                index=index,
                box=box,
                kind=candidate.kind,
                score=candidate.score,
                label=candidate.label,
                recognized=recognized,
                chosen=recognized
                and subject is not None
                and is_part(box, subject)
                and (kind is None or candidate.kind is kind),
            )
        )
        if len(out) == MAX_SHOWN:
            break
    return out


def focus_box(
    af_point: tuple[float, float] | None, geometry: Geometry, width: int, height: int
) -> SubjectBox | None:
    """The camera's focus point (upright, normalized) as a small box in the edited photo."""
    if af_point is None:
        return None
    return subject_in_crop(af_box(af_point, width / height), geometry, width, height)


def analysis(
    info: SubjectInfo,
    geometry: Geometry,
    width: int,
    height: int,
    *,
    af_point: tuple[float, float] | None,
    detected: bool,
) -> SubjectAnalysis:
    """``info`` (upright boxes) mapped into the photo edited by ``geometry``; ``width`` × ``height`` is the
    upright photo."""
    box = subject_in_crop(info.box, geometry, width, height) if info.box is not None else None
    return SubjectAnalysis(
        detected=detected,
        source=info.source,
        kind=info.kind,
        score=info.score,
        box=box,
        candidates=found_candidates(info, geometry, width, height, box, info.kind),
        focus=focus_box(af_point, geometry, width, height),
        detector=info.detector,
        notes=info.notes,
    )
