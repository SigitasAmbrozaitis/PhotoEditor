from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from photoedit.models import (
    AdjustmentParams,
    ApplyStyleRequest,
    ExposureMetering,
    ExposureRule,
    JobRequest,
    PhotoEdit,
    Style,
    StyleSample,
    WhiteBalanceMode,
    WhiteBalanceRule,
    style_summary,
    style_view,
)

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


def _style(**fields: Any) -> Style:
    data: dict[str, Any] = {"id": "warm", "name": "Warm", "created_at": NOW, "updated_at": NOW}
    data.update(fields)
    return Style.model_validate(data)


# ----------------------------------------------------------------- identity + values


def test_style_id_must_be_slug() -> None:
    assert _style(id="moody-forest").id == "moody-forest"
    for bad in ("Moody Forest", "moody_forest", "-moody", ""):
        with pytest.raises(ValidationError):
            _style(id=bad)


def test_values_are_validated_and_normalized() -> None:
    style = _style(values={"tone.contrast": -10, "hsl.green.saturation": -30, "color_grading.global.hue": 40})
    # Sorted, in the parameters' own JSON form (ints become floats), aliases kept ("global").
    assert style.values == {
        "color_grading.global.hue": 40.0,
        "hsl.green.saturation": -30.0,
        "tone.contrast": -10.0,
    }
    assert (
        _style(values={"tone.contrast": -10.0}).look_hash()
        == _style(values={"tone.contrast": -10}).look_hash()
    )


def test_values_may_set_defaults_and_curves() -> None:
    curve = [{"x": 0, "y": 0.05}, {"x": 1, "y": 1}]
    style = _style(values={"tone.contrast": 0, "tone_curve.rgb": curve})
    assert style.values["tone.contrast"] == 0  # setting a default value still counts as "sets it"
    assert style.values["tone_curve.rgb"] == [{"x": 0.0, "y": 0.05}, {"x": 1.0, "y": 1.0}]


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"tone.exposre": 1}, "unknown parameter 'tone.exposre'"),
        ({"tone": {"exposure": 1}}, "unknown parameter 'tone'"),
        ({"tone.contrast": 150}, "tone.contrast"),
        ({"geometry.angle": 3}, "per photo"),
        ({"white_balance.temperature": 6000}, "white_balance rule"),
        ({"tone_curve.rgb": [{"x": 0.5, "y": 0.5}]}, "tone_curve.rgb"),
    ],
)
def test_invalid_values_are_rejected(values: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        _style(values=values)


# ----------------------------------------------------------------- rules


def test_rules_parse_by_type_and_are_ordered() -> None:
    style = _style(
        rules=[
            {"type": "white_balance", "mode": "as_shot", "temperature_offset": 400},
            {"type": "exposure", "metering": "highlights", "target": 2},
        ]
    )
    assert [r.type for r in style.rules] == ["exposure", "white_balance"]
    exposure = style.rule(ExposureRule)
    assert exposure is not None and exposure.metering is ExposureMetering.HIGHLIGHTS
    wb = style.rule(WhiteBalanceRule)
    assert wb is not None and wb.temperature_offset == 400


def test_rule_defaults() -> None:
    rule = ExposureRule()
    assert (rule.metering, rule.target, rule.use_group, rule.strength, rule.max_change) == (
        ExposureMetering.MIDDLE,
        None,
        True,
        100,
        1.5,
    )
    assert WhiteBalanceRule().mode is WhiteBalanceMode.AS_SHOT


def test_duplicate_rule_type_rejected() -> None:
    with pytest.raises(ValidationError, match="repeated: exposure"):
        _style(rules=[{"type": "exposure"}, {"type": "exposure", "strength": 50}])


def test_unknown_rule_type_and_newer_version_rejected() -> None:
    with pytest.raises(ValidationError, match="does not match any of the expected tags"):
        _style(rules=[{"type": "dehaze"}])
    with pytest.raises(ValidationError, match="version 2 is newer than this tool supports"):
        _style(rules=[{"type": "exposure", "rule_version": 2}])


@pytest.mark.parametrize(
    ("rule", "message"),
    [
        ({"strength": 101}, "strength"),
        ({"max_change": 3.5}, "max_change"),
        ({"target": -5}, "target"),
        ({"metering": "spot"}, "metering"),
    ],
)
def test_exposure_rule_ranges(rule: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        ExposureRule.model_validate(rule)


def test_white_balance_fields_depend_on_mode() -> None:
    WhiteBalanceRule(mode=WhiteBalanceMode.FIXED, temperature=5200, tint=5)
    with pytest.raises(ValidationError, match="fixed mode needs temperature and tint"):
        WhiteBalanceRule(mode=WhiteBalanceMode.FIXED, temperature=5200)
    with pytest.raises(ValidationError, match="offsets don't apply in fixed mode"):
        WhiteBalanceRule(mode=WhiteBalanceMode.FIXED, temperature=5200, tint=0, temperature_offset=100)
    with pytest.raises(ValidationError, match="only for fixed mode"):
        WhiteBalanceRule(mode=WhiteBalanceMode.AUTO, temperature=5200)
    with pytest.raises(ValidationError, match="temperature_offset"):
        WhiteBalanceRule(temperature_offset=3500)


# ----------------------------------------------------------------- look hash, round trip, views


def test_look_hash_covers_only_the_look() -> None:
    base = _style(values={"tone.contrast": -10}, rules=[{"type": "exposure"}])
    same_look = base.model_copy(
        update={
            "name": "Other",
            "description": "x",
            "test_photo_ids": ["p1"],
            "updated_at": datetime(2027, 1, 1, tzinfo=UTC),
            "version": 7,
            "change_note": "renamed",
        }
    )
    assert same_look.look_hash() == base.look_hash()
    assert _style(values={"tone.contrast": -11}, rules=[{"type": "exposure"}]).look_hash() != base.look_hash()
    assert _style(
        values={"tone.contrast": -10}, rules=[{"type": "exposure", "strength": 50}]
    ).look_hash() != (base.look_hash())


def test_style_json_round_trip() -> None:
    style = _style(
        values={"tone.contrast": -10, "tone_curve.rgb": [{"x": 0, "y": 0.05}, {"x": 1, "y": 1}]},
        rules=[
            {"type": "exposure", "metering": "camera_settings"},
            {"type": "white_balance", "mode": "auto"},
        ],
        test_photo_ids=["a", "b"],
        samples=[{"photo_id": "a", "name": "01", "look_hash": "abc"}],
        best_for=["cats"],
    )
    assert Style.model_validate_json(style.model_dump_json()) == style
    assert "look_hash" not in style.model_dump()  # derived, so a stored file round-trips with extra="forbid"


def test_style_view_and_summary() -> None:
    style = _style(values={"tone.exposure": 0.3})
    look = style.look_hash()
    style = style.model_copy(
        update={
            "samples": [
                StyleSample(photo_id="a", name="01", look_hash=look),
                StyleSample(photo_id="b", name="02", look_hash="old"),
            ]
        }
    )
    view = style_view(style, photo_count=5)
    assert view.changed_parameters == view.values == {"tone.exposure": 0.3}
    assert view.look_hash == look and view.photo_count == 5
    assert [s.stale for s in view.samples] == [False, True] and view.samples_stale
    assert view.samples[0].after_url == f"/api/styles/warm/samples/01/after.jpg?v={look}"
    assert view.cover_url == view.samples[0].after_url
    summary = style_summary(style, photo_count=5)
    assert (summary.cover_url, summary.photo_count, summary.error) == (view.cover_url, 5, None)


# ----------------------------------------------------------------- requests + photo edit


def test_apply_style_request_can_remove_and_even_out() -> None:
    adapter: TypeAdapter[object] = TypeAdapter(JobRequest)
    remove = adapter.validate_python({"kind": "apply_style", "photo_ids": ["a"], "style_id": None})
    assert isinstance(remove, ApplyStyleRequest) and remove.style_id is None and not remove.even_out
    even = adapter.validate_python(
        {"kind": "apply_style", "photo_ids": ["a"], "style_id": "w", "even_out": True}
    )
    assert isinstance(even, ApplyStyleRequest) and even.even_out
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "apply_style", "photo_ids": ["a"]})  # style_id must be given


def test_photo_edit_style_fields_round_trip() -> None:
    edit = PhotoEdit.model_validate(
        {
            "photo_id": "p",
            "style_id": "warm",
            "adjustments": AdjustmentParams().model_dump(by_alias=True),
            "style_values": ["tone.exposure"],
            "rules": [{"type": "exposure", "summary": "+0.4 EV", "values": {"tone.exposure": 0.4}}],
            "style_version": 3,
            "group": {"id": "g1", "size": 8, "middle": -2.5, "white": 0.3, "camera_ev": 11.2},
        }
    )
    assert PhotoEdit.model_validate_json(edit.model_dump_json(by_alias=True)) == edit
    assert edit.group is not None and edit.group.camera_ev == 11.2
