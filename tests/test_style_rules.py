from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from photoedit.core.errors import InvalidRequestError
from photoedit.core.render.anchors import PhotoStats
from photoedit.core.style_rules import RuleInputs, resolve, rule_parameters, shift_temperature
from photoedit.models import AdjustmentParams, GroupReference, Style
from photoedit.models.style import DEFAULT_EXPOSURE_TARGETS

NOW = datetime(2026, 10, 9, tzinfo=UTC)
STATS = PhotoStats(black=-7.0, white=0.5, middle=-3.5, neutral_temperature=4600, neutral_tint=4)
AS_SHOT = (5000.0, 2.0)


def _style(values: dict[str, Any] | None = None, rules: list[dict[str, Any]] | None = None) -> Style:
    return Style.model_validate(
        {
            "id": "s",
            "name": "S",
            "created_at": NOW,
            "updated_at": NOW,
            "values": values or {},
            "rules": rules or [],
        }
    )


def _resolve(style: Style, **inputs: Any) -> tuple[AdjustmentParams, list[Any]]:
    data: dict[str, Any] = {"stats": STATS, "as_shot": AS_SHOT, **inputs}
    resolved = resolve(AdjustmentParams(), style, RuleInputs(**data))
    return resolved.adjustments, resolved.results


# ----------------------------------------------------------------- values


def test_values_only() -> None:
    style = _style({"tone.contrast": -10, "hsl.green.saturation": -30})
    resolved = resolve(AdjustmentParams(), style, RuleInputs(stats=None, as_shot=None))
    assert resolved.adjustments.tone.contrast == -10
    assert resolved.adjustments.hsl.green.saturation == -30
    assert resolved.results == [] and resolved.style_values == ["hsl.green.saturation", "tone.contrast"]


def test_values_apply_over_the_photos_defaults() -> None:
    jpeg_defaults = AdjustmentParams.model_validate({"detail": {"sharpening": {"amount": 0}}})
    resolved = resolve(jpeg_defaults, _style({"tone.contrast": 5}), RuleInputs(stats=None, as_shot=None))
    assert resolved.adjustments.detail.sharpening.amount == 0  # untouched by the style


def test_later_phase_values_are_rejected() -> None:
    # A style file edited by hand can carry them; using it must fail clearly, not render something else.
    style = Style.model_construct(**{**_style().model_dump(), "values": {"effects.grain.amount": 20.0}})
    with pytest.raises(InvalidRequestError, match="Phase 9"):
        resolve(AdjustmentParams(), style, RuleInputs(stats=None, as_shot=None))


# ----------------------------------------------------------------- exposure


@pytest.mark.parametrize(("strength", "expected"), [(100, 1.0), (50, 0.5), (0, 0.0)])
def test_middle_metering_moves_the_median_to_the_target(strength: float, expected: float) -> None:
    style = _style(rules=[{"type": "exposure", "target": -2.5, "strength": strength}])
    params, (result,) = _resolve(style)
    assert params.tone.exposure == pytest.approx(expected)  # -2.5 - (-3.5) = +1 EV at full strength
    assert (result.measured, result.target, result.note) == (-3.5, -2.5, None)
    assert result.values == {"tone.exposure": pytest.approx(expected)}


def test_default_target_and_the_styles_own_exposure_on_top() -> None:
    style = _style({"tone.exposure": 0.3}, [{"type": "exposure"}])
    params, (result,) = _resolve(style)
    delta = DEFAULT_EXPOSURE_TARGETS["middle"] - STATS.middle
    assert params.tone.exposure == pytest.approx(0.3 + delta)
    assert "default target" in result.summary


def test_max_change_limits_and_says_so() -> None:
    style = _style(rules=[{"type": "exposure", "target": 2, "max_change": 1.5}])
    params, (result,) = _resolve(style)
    assert params.tone.exposure == 1.5
    assert result.note is not None and "limited to 1.5 EV (wanted +5.50)" in result.note
    down = _style(rules=[{"type": "exposure", "target": -4, "max_change": 0.25}])
    assert _resolve(down)[0].tone.exposure == -0.25


def test_exposure_stays_within_its_range() -> None:
    style = _style({"tone.exposure": 4.5}, [{"type": "exposure", "target": 2, "max_change": 3}])
    params, (result,) = _resolve(style)
    assert params.tone.exposure == 5.0
    assert result.note is not None and "within -5…5 EV" in result.note


def test_highlights_metering_keeps_a_dark_subject_dark() -> None:
    # A black cat on a dark sofa: the median is very low, but the few bright pixels sit near the usual white.
    black_cat = PhotoStats(black=-9, white=-0.3, middle=-6.5, neutral_temperature=5000, neutral_tint=0)
    middle = _resolve(_style(rules=[{"type": "exposure", "max_change": 3}]), stats=black_cat)[0]
    highlights = _resolve(_style(rules=[{"type": "exposure", "metering": "highlights"}]), stats=black_cat)[0]
    assert middle.tone.exposure == 3.0  # pulled toward gray as far as allowed
    assert highlights.tone.exposure == pytest.approx(DEFAULT_EXPOSURE_TARGETS["highlights"] - (-0.3))


def test_group_reference_is_the_target_when_used() -> None:
    group = GroupReference(id="g", size=5, middle=-3.0, white=0.0, camera_ev=11.0)
    style = _style(rules=[{"type": "exposure", "target": -1}])
    params, (result,) = _resolve(style, group=group)
    assert params.tone.exposure == pytest.approx(0.5)  # group middle -3.0 vs this photo's -3.5
    assert "group" in result.summary
    ignore = _style(rules=[{"type": "exposure", "target": -1, "use_group": False, "max_change": 3}])
    assert _resolve(ignore, group=group)[0].tone.exposure == pytest.approx(2.5)


def test_camera_settings_even_out_a_manual_series_exactly() -> None:
    group = GroupReference(id="g", size=8, middle=-3.0, white=0.0, camera_ev=math.log2(4.5**2 * 250) - 3)
    style = _style(rules=[{"type": "exposure", "metering": "camera_settings"}])
    # Shot at 1/500 instead of the group's 1/250 (same aperture and ISO): one stop darker, so +1 EV.
    ev_500 = math.log2(4.5**2 * 500) - 3
    params, (result,) = _resolve(style, group=group, camera_ev=ev_500)
    assert params.tone.exposure == pytest.approx(1.0)
    assert result.measured == pytest.approx(ev_500, abs=1e-4) and result.note is None
    # Whatever the photo shows (a black cat filling the frame) doesn't matter.
    dark = PhotoStats(black=-12, white=-4, middle=-9, neutral_temperature=5000, neutral_tint=0)
    assert _resolve(style, group=group, camera_ev=ev_500, stats=dark)[0].tone.exposure == pytest.approx(1.0)


def test_camera_settings_fall_back_to_middle_and_say_why() -> None:
    style = _style(rules=[{"type": "exposure", "metering": "camera_settings", "target": -2.5}])
    params, (result,) = _resolve(style, camera_ev=11.0)  # no group
    assert params.tone.exposure == pytest.approx(1.0) and "needs 'even out'" in (result.note or "")
    group = GroupReference(id="g", size=3, middle=-3.5, white=0.0, camera_ev=None)
    params, (result,) = _resolve(style, group=group, camera_ev=None)
    assert params.tone.exposure == pytest.approx(0.0)  # metered like middle against the group's middle
    assert "no exposure settings in EXIF" in (result.note or "")


def test_unmeasured_photo_gets_no_exposure_change() -> None:
    params, (result,) = _resolve(_style(rules=[{"type": "exposure"}]), stats=None)
    assert params.tone.exposure == 0 and result.note == "photo not measured"


# ----------------------------------------------------------------- white balance


def test_offsets_are_the_same_mired_shift_under_any_light() -> None:
    assert shift_temperature(5500, 400) == pytest.approx(5900)
    tungsten = shift_temperature(3200, 400)
    assert 1e6 / 3200 - 1e6 / tungsten == pytest.approx(1e6 / 5500 - 1e6 / 5900)
    assert tungsten == pytest.approx(3331, abs=1)
    assert shift_temperature(4000, 0) == pytest.approx(4000)


def test_as_shot_mode_with_offsets() -> None:
    style = _style(rules=[{"type": "white_balance", "temperature_offset": 400, "tint_offset": -3}])
    params, (result,) = _resolve(style)
    assert params.white_balance.temperature == pytest.approx(shift_temperature(5000, 400), abs=0.1)
    assert params.white_balance.tint == pytest.approx(-1.0)
    assert result.summary.startswith("as shot 5000 K / +2.0 +400 K / -3 tint")


def test_auto_mode_starts_from_the_neutral_estimate() -> None:
    style = _style(rules=[{"type": "white_balance", "mode": "auto", "temperature_offset": 300}])
    params, _ = _resolve(style)
    assert params.white_balance.temperature == pytest.approx(shift_temperature(4600, 300), abs=0.1)
    assert params.white_balance.tint == 4
    unmeasured, (fallback,) = _resolve(style, stats=None)
    assert unmeasured.white_balance.temperature == pytest.approx(shift_temperature(5000, 300), abs=0.1)
    assert "used as shot" in (fallback.note or "")


def test_fixed_mode() -> None:
    style = _style(rules=[{"type": "white_balance", "mode": "fixed", "temperature": 3400, "tint": 10}])
    params, _ = _resolve(style, as_shot=None)
    assert (params.white_balance.temperature, params.white_balance.tint) == (3400, 10)


def test_white_balance_is_limited_to_its_ranges() -> None:
    style = _style(rules=[{"type": "white_balance", "temperature_offset": -3000, "tint_offset": -50}])
    params, (result,) = _resolve(style, as_shot=(2100.0, -140.0))
    assert params.white_balance.temperature == 2000 and params.white_balance.tint == -150
    assert "ranges" in (result.note or "")


def test_no_white_balance_rule_leaves_as_shot() -> None:
    params, _ = _resolve(_style({"tone.contrast": 5}))
    assert params.white_balance.temperature is None and params.white_balance.tint is None


def test_rule_parameters_name_what_applying_replaces() -> None:
    style = _style({"tone.contrast": 5}, [{"type": "exposure"}, {"type": "white_balance"}])
    assert rule_parameters(style) == {
        "tone.contrast",
        "tone.exposure",
        "white_balance.temperature",
        "white_balance.tint",
    }
    resolved = resolve(AdjustmentParams(), style, RuleInputs(stats=STATS, as_shot=AS_SHOT))
    assert set(resolved.style_values) == rule_parameters(style)


# ----------------------------------------------------------------- properties

stops = st.floats(-12, 4)
exposure_rules = st.fixed_dictionaries(
    {
        "type": st.just("exposure"),
        "metering": st.sampled_from(["middle", "highlights", "camera_settings"]),
        "target": st.none() | st.floats(-4, 4),
        "use_group": st.booleans(),
        "strength": st.floats(0, 100),
        "max_change": st.floats(0, 3),
    }
)
wb_rules = st.fixed_dictionaries(
    {
        "type": st.just("white_balance"),
        "mode": st.sampled_from(["as_shot", "auto"]),
        "temperature_offset": st.floats(-3000, 3000),
        "tint_offset": st.floats(-50, 50),
    }
)


@settings(max_examples=150, deadline=None)
@given(
    exposure=st.none() | exposure_rules,
    wb=st.none() | wb_rules,
    own_exposure=st.floats(-5, 5),
    middle=stops,
    spread=st.floats(0, 8),
    neutral=st.floats(2500, 12000),
    as_shot=st.floats(2000, 50000),
    camera_ev=st.none() | st.floats(-5, 25),
    group_ev=st.none() | st.floats(-5, 25),
)
def test_any_valid_style_resolves_to_valid_parameters(
    exposure: dict[str, Any] | None,
    wb: dict[str, Any] | None,
    own_exposure: float,
    middle: float,
    spread: float,
    neutral: float,
    as_shot: float,
    camera_ev: float | None,
    group_ev: float | None,
) -> None:
    rules = [r for r in (exposure, wb) if r is not None]
    style = _style({"tone.exposure": own_exposure}, rules)
    stats = PhotoStats(
        black=max(middle - spread, -16),
        white=min(middle + spread, 16),
        middle=middle,
        neutral_temperature=neutral,
        neutral_tint=0,
    )
    group = GroupReference(id="g", size=3, middle=-3, white=0, camera_ev=group_ev)
    inputs = RuleInputs(stats=stats, as_shot=(as_shot, 0.0), camera_ev=camera_ev, group=group)
    first = resolve(AdjustmentParams(), style, inputs)
    AdjustmentParams.model_validate(first.adjustments.model_dump(by_alias=True))  # within every range
    assert resolve(AdjustmentParams(), style, inputs) == first  # deterministic
    if exposure is not None:
        assert (
            abs(first.adjustments.tone.exposure - own_exposure) <= exposure["max_change"] + 1e-4
        )  # rounding


def test_no_change_reads_as_plus_zero() -> None:
    _, (result,) = _resolve(_style(rules=[{"type": "exposure", "target": STATS.middle}]))
    assert result.summary.endswith(": +0.00 EV")
