"""Review rules (P6c.3): why a prepared photo needs the user's look, as pure functions.

Each rule is switched on or off, with its threshold, in ``ReviewSettings``. A subject set by hand (by the
user, the AI or in a review) is a decision already made, so the rules about the subject itself (none,
uncertain, ambiguous) do not apply to it; the ones about the framing (cut off, too small) still do.

Boxes are normalized to the edited photo, the frame the review shows.
"""

from __future__ import annotations

from collections.abc import Sequence

from photoedit.core.export.service import Framing
from photoedit.core.subject.choose import UNRECOGNIZED
from photoedit.models.export import AspectZoom, ExportSettings
from photoedit.models.review import ReviewCandidate, ReviewReason, ReviewRule, ReviewSettings
from photoedit.models.subject import SubjectBox, SubjectCandidate, SubjectSource

# A candidate with at least this share of its area inside the subject's box is part of it (the driver in
# the car, the second car of a tandem the chooser grouped, a face of the person).
PART_OF = 0.5
# Scores are stored to 6 decimals; a threshold met to within this counts as met (0.75 × 0.8 is 0.6000…01).
_EPS = 1e-9


def overlap(box: SubjectBox, other: SubjectBox) -> float:
    """The share of ``box``'s area inside ``other``."""
    width = max(0.0, min(box.right, other.right) - max(box.left, other.left))
    height = max(0.0, min(box.bottom, other.bottom) - max(box.top, other.top))
    area = (box.right - box.left) * (box.bottom - box.top)
    return width * height / area if area > 0 else 0.0


def is_part(candidate: SubjectBox, subject: SubjectBox) -> bool:
    return overlap(candidate, subject) >= PART_OF


def rivals(
    subject: SubjectBox, score: float, candidates: Sequence[ReviewCandidate], ambiguity: float
) -> list[ReviewCandidate]:
    """Recognized candidates, not part of the subject, scoring at least ``ambiguity`` × its ``score``."""
    return [
        c
        for c in candidates
        if c.kind not in UNRECOGNIZED and not is_part(c.box, subject) and c.score >= ambiguity * score - _EPS
    ]


def visible_candidates(
    found: Sequence[SubjectCandidate], mapped: Sequence[SubjectBox | None], subject: SubjectBox | None
) -> list[ReviewCandidate]:
    """The recognized candidates (``found``, best first) that are inside the edited photo (``mapped``: each
    one's box in it, or None), marked when they are part of the ``subject``."""
    out = []
    for index, (candidate, box) in enumerate(zip(found, mapped, strict=True)):
        if box is None or candidate.kind in UNRECOGNIZED:
            continue
        out.append(
            ReviewCandidate(
                index=index,
                box=box,
                kind=candidate.kind,
                score=candidate.score,
                label=candidate.label,
                chosen=subject is not None and is_part(box, subject),
            )
        )
    return out


def reasons(
    framing: Framing,
    candidates: Sequence[ReviewCandidate],
    settings: ExportSettings,
    rules: ReviewSettings,
    *,
    unusable: str | None = None,
) -> list[ReviewReason]:
    """Why the photo framed as ``framing`` needs a look; empty when it is Ready.

    ``candidates`` are the photo's visible candidates (``visible_candidates``). ``unusable`` says why the
    photo can't be exported at all: then that is the only reason.
    """
    if unusable is not None:
        return [ReviewReason(code=ReviewRule.UNUSABLE, text=unusable)]
    if framing.source is None:
        return []  # the export doesn't frame subjects: nothing to doubt
    out: list[ReviewReason] = []
    box, source = framing.box, framing.source
    if source in (SubjectSource.NONE, SubjectSource.AF_POINT) or box is None:
        if rules.no_subject:
            text = "no subject recognized: framed on the camera's focus point"
            if source != SubjectSource.AF_POINT:
                text = framing.note or "no subject recognized: centered"
            out.append(ReviewReason(code=ReviewRule.NO_SUBJECT, text=text))
    elif source == SubjectSource.DETECTED:
        score = framing.score or 0.0
        kind = framing.kind.value if framing.kind else "subject"
        if rules.uncertain and score < rules.min_score - _EPS:
            text = f"the {kind} is uncertain: score {score:.2f}, below {rules.min_score:.2f}"
            out.append(ReviewReason(code=ReviewRule.UNCERTAIN, text=text))
        found = rivals(box, score, candidates, rules.ambiguity) if rules.ambiguous else []
        if found:
            best = max(found, key=lambda c: c.score)
            text = f"another {best.kind.value} scores {best.score:.2f} (the {kind}: {score:.2f})"
            if len(found) > 1:
                text += f", and {len(found) - 1} more"
            out.append(ReviewReason(code=ReviewRule.AMBIGUOUS, text=text))
    geometry = framing.geometry
    if rules.cut_off and geometry.subject_cut is not None:
        text = (
            f"the subject is cut off: it is {geometry.subject_cut} than a {settings.aspect.ratio} crop allows"
        )
        out.append(ReviewReason(code=ReviewRule.CUT_OFF, text=text))
    zooms = settings.aspect.zoom == AspectZoom.AUTO and not framing.own_crop
    if rules.zoom_limit and zooms and framing.zoom.limited:
        fill = settings.aspect.subject_fill
        text = (
            f"the subject stays small: filling {fill:.0%} of the crop needs {framing.zoom.wanted:.1f}×, "
            f"the most without enlarging is {framing.zoom.quality:.2f}×"
        )
        out.append(ReviewReason(code=ReviewRule.ZOOM_LIMIT, text=text))
    return out
