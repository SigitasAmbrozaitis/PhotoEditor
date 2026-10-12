"""Choosing the main subject (P6b.6): the scoring rules on constructed candidate sets."""

from __future__ import annotations

import pytest

from photoedit.core.metadata import AfMode
from photoedit.core.subject.choose import MIN_MAIN, af_box, choose, sharpness_factor, size_factor
from photoedit.models.subject import SubjectBox, SubjectCandidate, SubjectKind, SubjectSource


def box(left: float, top: float, right: float, bottom: float) -> SubjectBox:
    return SubjectBox(left=left, top=top, right=right, bottom=bottom)


def cand(kind: SubjectKind, score: float, b: SubjectBox, label: str | None = None) -> SubjectCandidate:
    return SubjectCandidate(box=b, kind=kind, score=score, label=label or kind.value)


CAR = SubjectKind.CAR
PERSON = SubjectKind.PERSON
FACE = SubjectKind.FACE
ANIMAL = SubjectKind.ANIMAL
SALIENT = SubjectKind.SALIENT


def test_a_small_car_beats_a_confident_crowd() -> None:
    crowd = [cand(PERSON, 0.92, box(0.05 * i, 0.7, 0.05 * i + 0.04, 0.85)) for i in range(10)]
    car = cand(CAR, 0.8, box(0.6, 0.4, 0.65, 0.43))  # ~3 % of the width
    info = choose([*crowd, car, cand(FACE, 0.9, box(0.1, 0.7, 0.12, 0.73))])
    assert info.source is SubjectSource.DETECTED and info.kind is CAR and info.box == car.box
    assert info.candidates[0].label == "car"
    # The crowd still counts, but weakly.
    people = [c for c in info.candidates if c.kind is PERSON]
    assert people and all(c.score < info.score for c in people)


def test_people_are_the_subject_when_there_is_no_vehicle() -> None:
    info = choose([cand(PERSON, 0.9, box(0.3, 0.2, 0.5, 0.9)), cand(SALIENT, 0.9, box(0.7, 0.1, 0.9, 0.3))])
    assert info.kind is PERSON


def test_a_cat_beats_saliency_and_a_face_beats_its_person() -> None:
    cat = cand(ANIMAL, 0.85, box(0.2, 0.3, 0.7, 0.9), "cat")
    bright = cand(SALIENT, 1.0, box(0.8, 0.05, 0.95, 0.2), "saliency")
    assert choose([bright, cat]).box == cat.box
    face = cand(FACE, 0.95, box(0.4, 0.2, 0.5, 0.3))
    person = cand(PERSON, 0.9, box(0.3, 0.15, 0.6, 0.95))
    assert choose([person, face]).kind is FACE


def test_nothing_found_falls_back_to_the_focus_point_then_none() -> None:
    weak = [cand(SALIENT, 0.2, box(0.1, 0.1, 0.2, 0.2))]
    assert weak[0].score * 0.35 < MIN_MAIN
    info = choose(weak, af_point=(0.3, 0.6), af_mode=AfMode.SINGLE, aspect=1.5)
    assert info.source is SubjectSource.AF_POINT and info.kind is SubjectKind.AF_POINT
    assert info.box is not None and info.box.center == pytest.approx((0.3, 0.6))
    assert info.candidates == [weak[0].model_copy(update={"score": pytest.approx(0.07)})]
    nothing = choose(weak)
    assert nothing.source is SubjectSource.NONE and nothing.box is None
    assert choose([], af_point=(0.5, 0.5), af_mode=AfMode.NONE).source is SubjectSource.NONE


def test_the_focus_point_picks_between_two_cars() -> None:
    left = cand(CAR, 0.8, box(0.1, 0.4, 0.25, 0.5))
    right = cand(CAR, 0.8, box(0.7, 0.4, 0.85, 0.5))
    assert choose([left, right], af_point=(0.75, 0.45), af_mode=AfMode.ZONE).box == right.box
    assert choose([left, right]).box == left.box  # a tie goes to the left one, always the same


def test_a_tandem_drift_is_one_subject() -> None:
    lead = cand(CAR, 0.9, box(0.30, 0.50, 0.40, 0.56))
    chaser = cand(CAR, 0.8, box(0.45, 0.52, 0.55, 0.58))  # half a car length behind
    parked = cand(CAR, 0.9, box(0.85, 0.1, 0.95, 0.15))  # far away: not part of it
    spectator_car = cand(CAR, 0.3, box(0.41, 0.5, 0.44, 0.52))  # close but much weaker
    info = choose([lead, chaser, parked, spectator_car])
    assert info.box == box(0.30, 0.50, 0.55, 0.58)


def test_sharp_boxes_beat_blurred_ones() -> None:
    panned = cand(CAR, 0.7, box(0.1, 0.4, 0.3, 0.5))
    parked = cand(CAR, 0.75, box(0.6, 0.4, 0.8, 0.5))

    def sharpness(b: SubjectBox) -> float:
        return 1.5 if b == panned.box else 0.0

    assert choose([panned, parked], sharpness=sharpness).box == panned.box
    assert choose([panned, parked]).box == parked.box


@pytest.mark.parametrize(
    ("area_box", "factor"),
    [
        (box(0, 0, 0.01, 0.01), 0.3),  # a speck
        (box(0, 0, 0.1, 0.1), 1.0),
        (box(0, 0, 0.7, 0.7), 1.0),
        (box(0, 0, 1, 1), 0.4),  # the whole frame
    ],
)
def test_size_factor(area_box: SubjectBox, factor: float) -> None:
    assert size_factor(area_box) == pytest.approx(factor)


def test_sharpness_factor() -> None:
    assert sharpness_factor(None) == 1
    assert sharpness_factor(-2) == pytest.approx(0.7)
    assert sharpness_factor(0.5) == pytest.approx(0.85)
    assert sharpness_factor(3) == pytest.approx(1.0)


def test_af_box_is_square_and_inside() -> None:
    square = af_box((0.5, 0.5), aspect=1.5)
    assert (square.right - square.left) * 1.5 == pytest.approx(square.bottom - square.top)
    corner = af_box((0.0, 1.0), aspect=2 / 3)
    assert corner.left == 0 and corner.bottom == pytest.approx(1)


def test_same_candidates_same_choice() -> None:
    candidates = [cand(CAR, 0.6, box(0.1 * i, 0.4, 0.1 * i + 0.05, 0.45)) for i in range(8)]
    assert choose(candidates) == choose(list(reversed(candidates)))


def test_saliency_and_sharpness_alone_never_make_a_subject() -> None:
    sun = cand(SALIENT, 1.0, box(0.4, 0.5, 0.6, 0.7), "saliency")
    assert sun.score * 0.35 >= MIN_MAIN  # strong enough by score, but it doesn't know what it found
    info = choose([sun, cand(SALIENT, 0.9, box(0.1, 0.1, 0.3, 0.3), "sharp")])
    assert info.source is SubjectSource.NONE and info.candidates[0].label == "saliency"
    focused = choose([sun], af_point=(0.5, 0.6), af_mode=AfMode.SINGLE)
    assert focused.source is SubjectSource.AF_POINT
    # A recognized subject still wins, even if it scores lower than the cue.
    car = cand(CAR, 0.5, box(0.7, 0.4, 0.8, 0.45))
    assert choose([sun, car]).box == car.box
