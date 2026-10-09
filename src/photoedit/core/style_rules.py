"""Resolving a style for one photo: its values, then its adaptive rules on the photo's own measurements.

Pure functions: the same style, measurements and group reference always give the same parameters (golden
rule 3). Each rule type is one function from (rule, parameters so far, inputs) to (parameter changes, result),
so a new rule type or metering mode is a new function, not a change to the others. Rule outputs are limited by
design (``max_change``, the parameter ranges), and every limit says so in the rule's result.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from photoedit.core.render.anchors import PhotoStats
from photoedit.core.render.pipeline import check_supported
from photoedit.models import AdjustmentParams, GroupReference, Style
from photoedit.models.style import (
    DEFAULT_EXPOSURE_TARGETS,
    ExposureMetering,
    ExposureRule,
    RuleResult,
    WhiteBalanceMode,
    WhiteBalanceRule,
)

EXPOSURE_RANGE = (-5.0, 5.0)  # AdjustmentParams.tone.exposure
TEMPERATURE_RANGE = (2000.0, 50000.0)
TINT_RANGE = (-150.0, 150.0)
OFFSET_REFERENCE_KELVIN = 5500.0  # temperature offsets are given in Kelvin at this temperature


@dataclass(frozen=True)
class RuleInputs:
    """What the rules know about the photo."""

    stats: PhotoStats | None
    as_shot: tuple[float, float] | None
    camera_ev: float | None = None
    group: GroupReference | None = None


@dataclass(frozen=True)
class ResolvedStyle:
    adjustments: AdjustmentParams
    results: list[RuleResult]
    style_values: list[str]  # dotted names whose value comes from the style or its rules


type RuleChanges = dict[str, float]
type RuleFunction = Callable[[Any, AdjustmentParams, RuleInputs], tuple[RuleChanges, RuleResult]]


def resolve(defaults: AdjustmentParams, style: Style, inputs: RuleInputs) -> ResolvedStyle:
    """``defaults`` with the style's values and its rules' results applied (overrides come after this)."""
    params = defaults.with_values(style.values)
    check_supported(params)
    results: list[RuleResult] = []
    names = set(style.values)
    for rule in style.rules:  # already in RULE_ORDER
        changes, result = RULES[rule.type](rule, params, inputs)
        params = params.with_values(changes)
        names |= set(changes)
        results.append(result)
    return ResolvedStyle(adjustments=params, results=results, style_values=sorted(names))


def rule_parameters(style: Style) -> set[str]:
    """Dotted names the style sets, including what its rules set (what applying it replaces)."""
    names = set(style.values)
    for rule in style.rules:
        names |= RULE_PARAMETERS[rule.type]
    return names


# ----------------------------------------------------------------- exposure


def exposure_rule(
    rule: ExposureRule, params: AdjustmentParams, inputs: RuleInputs
) -> tuple[RuleChanges, RuleResult]:
    base = params.tone.exposure
    group = inputs.group if rule.use_group else None
    notes: list[str] = []
    metering = rule.metering
    if metering is ExposureMetering.CAMERA_SETTINGS:
        if inputs.camera_ev is None:
            notes.append("no exposure settings in EXIF, metered like 'middle'")
            metering = ExposureMetering.MIDDLE
        elif group is None or group.camera_ev is None:
            notes.append("camera_settings needs 'even out' (a group), metered like 'middle'")
            metering = ExposureMetering.MIDDLE
        else:
            # A faster shutter or a smaller aperture (higher EV100) made the photo darker by exactly that.
            measured, target = inputs.camera_ev, group.camera_ev
            label = f"camera EV {measured:.1f} vs group {target:.1f}"
            return _exposure_change(rule, base, measured - target, label, measured, target, notes)

    if inputs.stats is None:
        return {}, RuleResult(
            type="exposure", summary="not measured yet: no change", note="photo not measured"
        )
    if metering is ExposureMetering.MIDDLE:
        measured, from_group = inputs.stats.middle, group.middle if group else None
    else:
        measured, from_group = inputs.stats.white, group.white if group else None
    if from_group is not None:
        target, where = from_group, "group"
    elif rule.target is not None:
        target, where = rule.target, "target"
    else:
        target, where = DEFAULT_EXPOSURE_TARGETS[metering.value], "default target"
    label = f"{metering.value} {measured:+.2f} -> {where} {target:+.2f} stops"
    return _exposure_change(rule, base, target - measured, label, measured, target, notes)


def _exposure_change(
    rule: ExposureRule,
    base: float,
    wanted: float,
    label: str,
    measured: float,
    target: float,
    notes: list[str],
) -> tuple[RuleChanges, RuleResult]:
    delta = wanted * rule.strength / 100
    if abs(delta) > rule.max_change:
        notes.append(f"limited to {rule.max_change:g} EV (wanted {delta:+.2f})")
        delta = float(np.sign(delta)) * rule.max_change
    final = base + delta
    low, high = EXPOSURE_RANGE
    if not low <= final <= high:
        notes.append(f"exposure kept within {low:g}…{high:g} EV")
        final = min(max(final, low), high)
    final = round(final, 4)
    applied = final - base
    strength = f" at {rule.strength:g} %" if rule.strength != 100 else ""
    summary = f"{label}{strength}: {applied:+.2f} EV"
    return {"tone.exposure": final}, RuleResult(
        type="exposure",
        summary=summary,
        measured=round(measured, 4),
        target=round(target, 4),
        values={"tone.exposure": final},
        note="; ".join(notes) or None,
    )


# ----------------------------------------------------------------- white balance


def white_balance_rule(
    rule: WhiteBalanceRule, params: AdjustmentParams, inputs: RuleInputs
) -> tuple[RuleChanges, RuleResult]:
    notes: list[str] = []
    if rule.mode is WhiteBalanceMode.FIXED:
        if rule.temperature is None or rule.tint is None:  # the model guarantees both in fixed mode
            raise ValueError("white_balance rule: fixed mode needs temperature and tint")
        temperature, tint, label = rule.temperature, rule.tint, "fixed"
        measured: float | None = None
    else:
        if inputs.as_shot is None:
            return {}, RuleResult(
                type="white_balance", summary="no white balance recorded: no change", note="no as-shot WB"
            )
        start = inputs.as_shot
        label = "as shot"
        if rule.mode is WhiteBalanceMode.AUTO:
            if inputs.stats is None:
                notes.append("photo not measured yet, used as shot")
            else:
                start = (inputs.stats.neutral_temperature, inputs.stats.neutral_tint)
                label = "auto (neutral estimate)"
        measured = start[0]
        temperature = shift_temperature(start[0], rule.temperature_offset)
        tint = start[1] + rule.tint_offset
        label += f" {start[0]:.0f} K / {start[1]:+.1f}"
    t_low, t_high = TEMPERATURE_RANGE
    if not t_low <= temperature <= t_high or not TINT_RANGE[0] <= tint <= TINT_RANGE[1]:
        notes.append("kept within the white balance ranges")
    temperature = round(min(max(temperature, t_low), t_high), 1)
    tint = round(min(max(tint, TINT_RANGE[0]), TINT_RANGE[1]), 2)
    offsets = ""
    if rule.temperature_offset or rule.tint_offset:
        offsets = f" {rule.temperature_offset:+g} K / {rule.tint_offset:+g} tint"
    summary = f"{label}{offsets}: {temperature:.0f} K, tint {tint:+.1f}"
    values = {"white_balance.temperature": temperature, "white_balance.tint": tint}
    return values, RuleResult(
        type="white_balance",
        summary=summary,
        measured=measured,
        target=None,
        values=values,
        note="; ".join(notes) or None,
    )


def shift_temperature(kelvin: float, offset_at_reference: float) -> float:
    """``kelvin`` moved by the mired shift that ``offset_at_reference`` K is at 5500 K, so an offset looks
    alike under any light (+400 K at 5500 K is about +130 K at 3200 K)."""
    mired_shift = 1e6 / (OFFSET_REFERENCE_KELVIN + offset_at_reference) - 1e6 / OFFSET_REFERENCE_KELVIN
    return 1e6 / (1e6 / kelvin + mired_shift)


RULES: dict[str, RuleFunction] = {"exposure": exposure_rule, "white_balance": white_balance_rule}
RULE_PARAMETERS: dict[str, set[str]] = {
    "exposure": {"tone.exposure"},
    "white_balance": {"white_balance.temperature", "white_balance.tint"},
}
