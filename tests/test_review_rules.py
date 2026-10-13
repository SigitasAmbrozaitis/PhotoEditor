from __future__ import annotations

from typing import Any

import pytest

from photoedit.core.export.geometry import Box, ExportGeometry, ZoomPlan
from photoedit.core.export.service import Framing
from photoedit.core.review.rules import is_part, overlap, reasons, rivals, visible_candidates
from photoedit.models.export import DecodeUsed, ExportSettings
from photoedit.models.review import ReviewCandidate, ReviewRule, ReviewSettings
from photoedit.models.subject import SubjectBox, SubjectCandidate, SubjectKind, SubjectSource

SUBJECT = SubjectBox(left=0.4, top=0.4, right=0.6, bottom=0.6)
FAR = SubjectBox(left=0.0, top=0.0, right=0.1, bottom=0.1)
INSIDE = SubjectBox(left=0.45, top=0.45, right=0.5, bottom=0.5)
IG = ExportSettings.model_validate({"aspect": {"ratio": "4:5", "anchor": "subject", "zoom": "auto"}})


def _framing(**changes: Any) -> Framing:
    values: dict[str, Any] = {
        "geometry": ExportGeometry(crop=Box(0, 0, 100, 125), width=80, height=100, decode=DecodeUsed.HALF),
        "zoom": ZoomPlan(wanted=1.0, fast=1.5, quality=3.0),
        "box": SUBJECT,
        "source": SubjectSource.DETECTED,
        "kind": SubjectKind.CAR,
        "score": 0.8,
    }
    return Framing(**{**values, **changes})


def _candidate(
    box: SubjectBox, score: float, kind: SubjectKind = SubjectKind.CAR, index: int = 1
) -> ReviewCandidate:
    return ReviewCandidate(index=index, box=box, kind=kind, score=score)


def _codes(framing: Framing, *candidates: ReviewCandidate, **rules: Any) -> list[ReviewRule]:
    found = reasons(framing, list(candidates), IG, ReviewSettings(**rules))
    return [r.code for r in found]


def test_a_sure_subject_is_ready() -> None:
    assert _codes(_framing(), _candidate(SUBJECT, 0.8, index=0)) == []


@pytest.mark.parametrize(("score", "check"), [(0.49, True), (0.5, False), (0.51, False)])
def test_uncertain_at_the_threshold(score: float, check: bool) -> None:
    codes = _codes(_framing(score=score))
    assert (ReviewRule.UNCERTAIN in codes) is check
    text = reasons(_framing(score=0.42), [], IG, ReviewSettings())[0].text
    assert text == "the car is uncertain: score 0.42, below 0.50"


def test_min_score_setting_moves_the_threshold() -> None:
    assert _codes(_framing(score=0.6), min_score=0.7) == [ReviewRule.UNCERTAIN]
    assert _codes(_framing(score=0.3), min_score=0.2) == []


@pytest.mark.parametrize(("rival", "check"), [(0.59, False), (0.6, True), (0.79, True)])
def test_ambiguous_at_the_threshold(rival: float, check: bool) -> None:
    # 0.75 × 0.8 = 0.6
    codes = _codes(_framing(), _candidate(FAR, rival))
    assert (ReviewRule.AMBIGUOUS in codes) is check


def test_ambiguous_text_names_the_best_rival() -> None:
    found = reasons(
        _framing(),
        [_candidate(FAR, 0.7, SubjectKind.ANIMAL), _candidate(FAR, 0.65, index=2)],
        IG,
        ReviewSettings(),
    )
    assert found[0].text == "another animal scores 0.70 (the car: 0.80), and 1 more"


def test_parts_and_grouped_candidates_are_not_rivals() -> None:
    driver = _candidate(INSIDE, 0.9, SubjectKind.FACE)
    # The second car of a tandem: the chooser grouped it, so the subject's box holds it.
    tandem = _candidate(SubjectBox(left=0.5, top=0.42, right=0.6, bottom=0.58), 0.78)
    assert _codes(_framing(), driver, tandem) == []
    # Mostly outside: a rival.
    half_out = _candidate(SubjectBox(left=0.55, top=0.4, right=0.8, bottom=0.6), 0.78)
    assert _codes(_framing(), half_out) == [ReviewRule.AMBIGUOUS]


def test_unrecognized_cues_are_never_rivals() -> None:
    assert _codes(_framing(), _candidate(FAR, 0.95, SubjectKind.SALIENT)) == []


def test_no_subject_texts() -> None:
    centered = reasons(
        _framing(box=None, source=SubjectSource.NONE, kind=None, score=None), [], IG, ReviewSettings()
    )
    assert [(r.code, r.text) for r in centered] == [
        (ReviewRule.NO_SUBJECT, "no subject recognized: centered")
    ]
    noted = _framing(
        box=None, source=SubjectSource.NONE, note="the subject is outside the photo's crop: centered"
    )
    assert (
        reasons(noted, [], IG, ReviewSettings())[0].text
        == "the subject is outside the photo's crop: centered"
    )
    af = _framing(source=SubjectSource.AF_POINT, kind=SubjectKind.AF_POINT, score=None)
    assert reasons(af, [], IG, ReviewSettings())[0].text == (
        "no subject recognized: framed on the camera's focus point"
    )


def test_manual_subjects_skip_the_subject_rules() -> None:
    manual = _framing(source=SubjectSource.MANUAL, kind=None, score=None)
    assert _codes(manual, _candidate(FAR, 0.99)) == []
    cut = _framing(source=SubjectSource.MANUAL, geometry=_cut_geometry())
    assert _codes(cut) == [ReviewRule.CUT_OFF]


def _cut_geometry() -> ExportGeometry:
    return ExportGeometry(
        crop=Box(0, 0, 100, 125), width=80, height=100, decode=DecodeUsed.HALF, subject_cut="wider"
    )


def test_cut_off() -> None:
    found = reasons(_framing(geometry=_cut_geometry()), [], IG, ReviewSettings())
    assert [(r.code, r.text) for r in found] == [
        (ReviewRule.CUT_OFF, "the subject is cut off: it is wider than a 4:5 crop allows")
    ]


def test_zoom_limit() -> None:
    limited = _framing(zoom=ZoomPlan(wanted=4.7, fast=1.54, quality=3.08))
    found = reasons(limited, [], IG, ReviewSettings())
    assert [(r.code, r.text) for r in found] == [
        (
            ReviewRule.ZOOM_LIMIT,
            "the subject stays small: filling 40% of the crop needs 4.7×, "
            "the most without enlarging is 3.08×",
        )
    ]
    # At the limit exactly: fine. Without automatic zoom, or with the user's own crop: not a reason.
    assert _codes(_framing(zoom=ZoomPlan(wanted=3.08, fast=1.54, quality=3.08))) == []
    off = IG.model_copy(update={"aspect": IG.aspect.model_copy(update={"zoom": "off"})})
    assert reasons(limited, [], off, ReviewSettings()) == []
    assert _codes(_framing(zoom=limited.zoom, own_crop=True)) == []


def test_rules_switched_off() -> None:
    everything = _framing(score=0.1, geometry=_cut_geometry(), zoom=ZoomPlan(wanted=9, fast=1.5, quality=3))
    rival = _candidate(FAR, 0.1)
    assert _codes(everything, rival) == [
        ReviewRule.UNCERTAIN,
        ReviewRule.AMBIGUOUS,
        ReviewRule.CUT_OFF,
        ReviewRule.ZOOM_LIMIT,
    ]
    off = {"uncertain": False, "ambiguous": False, "cut_off": False, "zoom_limit": False}
    assert _codes(everything, rival, **off) == []
    assert _codes(_framing(box=None, source=SubjectSource.NONE), no_subject=False) == []


def test_unusable_is_the_only_reason() -> None:
    found = reasons(_framing(score=0.1), [], IG, ReviewSettings(), unusable="the original is gone")
    assert [(r.code, r.text) for r in found] == [(ReviewRule.UNUSABLE, "the original is gone")]


def test_exports_without_subject_framing_are_always_ready() -> None:
    assert _codes(_framing(box=None, source=None, kind=None, score=None)) == []


def test_overlap_and_parts() -> None:
    assert overlap(INSIDE, SUBJECT) == 1.0
    assert overlap(FAR, SUBJECT) == 0.0
    assert overlap(SubjectBox(left=0.5, top=0.4, right=0.7, bottom=0.6), SUBJECT) == pytest.approx(0.5)
    assert is_part(SubjectBox(left=0.5, top=0.4, right=0.7, bottom=0.6), SUBJECT)
    assert rivals(SUBJECT, 0.8, [_candidate(FAR, 0.6)], 0.75) == [_candidate(FAR, 0.6)]


def test_visible_candidates() -> None:
    found = [
        SubjectCandidate(box=SUBJECT, kind=SubjectKind.CAR, score=0.8, label="car"),
        SubjectCandidate(box=FAR, kind=SubjectKind.SALIENT, score=0.5),
        SubjectCandidate(box=FAR, kind=SubjectKind.PERSON, score=0.3, label="person"),
        SubjectCandidate(box=FAR, kind=SubjectKind.ANIMAL, score=0.2),
    ]
    mapped = [SUBJECT, FAR, FAR, None]  # the animal is outside the photo's crop
    shown = visible_candidates(found, mapped, SUBJECT)
    assert [(c.index, c.kind, c.chosen) for c in shown] == [
        (0, SubjectKind.CAR, True),
        (2, SubjectKind.PERSON, False),
    ]
