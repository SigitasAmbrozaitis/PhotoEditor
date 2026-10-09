"""Property tests: any valid edit renders finite, in-range, deterministic pixels; invalid edits never get
that far."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from photoedit.core import color
from photoedit.core.decode import LinearImage
from photoedit.core.render.pipeline import render
from photoedit.core.render.profile import GENERIC
from photoedit.models.adjustments import MIN_CURVE_POINT_GAP, AdjustmentParams

XT3 = np.array([[1.6393, -0.7740, -0.1436], [-0.4140, 1.1745, 0.2632], [-0.0536, 0.1413, 0.6614]])
BANDS = ("red", "orange", "yellow", "green", "aqua", "blue", "purple", "magenta")

signed = st.floats(min_value=-100, max_value=100, allow_nan=False)
unsigned = st.floats(min_value=0, max_value=100, allow_nan=False)
unit = st.floats(min_value=0, max_value=1, allow_nan=False)


@st.composite
def point_curves(draw: st.DrawFn) -> list[dict[str, float]]:
    inner = draw(st.lists(st.floats(min_value=0.01, max_value=0.99), min_size=0, max_size=5))
    xs = [0.0]
    for x in [*sorted(inner), 1.0]:
        if x - xs[-1] >= MIN_CURVE_POINT_GAP:
            xs.append(x)
    if xs[-1] != 1.0:
        xs[-1] = 1.0
    return [{"x": x, "y": draw(unit)} for x in xs]


@st.composite
def edits(draw: st.DrawFn) -> AdjustmentParams:
    """Valid edits over every parameter this phase renders (later-phase ones stay at their defaults)."""
    data: dict[str, Any] = {
        "white_balance": {
            "temperature": draw(st.none() | st.floats(min_value=2000, max_value=50000)),
            "tint": draw(st.none() | st.floats(min_value=-150, max_value=150)),
        },
        "tone": {"exposure": draw(st.floats(min_value=-5, max_value=5))}
        | {name: draw(signed) for name in ("contrast", "highlights", "shadows", "whites", "blacks")},
        "presence": {"vibrance": draw(signed), "saturation": draw(signed)},
        "tone_curve": {name: draw(signed) for name in ("highlights", "lights", "darks", "shadows")}
        | {name: draw(point_curves()) for name in ("rgb", "red", "green", "blue")},
        "hsl": {
            band: {"hue": draw(signed), "saturation": draw(signed), "luminance": draw(signed)}
            for band in BANDS
        },
        "color_grading": {
            wheel: {
                "hue": draw(st.floats(min_value=0, max_value=359.9)),
                "saturation": draw(unsigned),
                "luminance": draw(signed),
            }
            for wheel in ("shadows", "midtones", "highlights", "global")
        }
        | {"blending": draw(unsigned), "balance": draw(signed)},
        "detail": {
            "sharpening": {
                "amount": draw(st.floats(min_value=0, max_value=150)),
                "radius": draw(st.floats(min_value=0.5, max_value=3)),
                "detail": draw(unsigned),
                "masking": draw(unsigned),
            }
        },
        "effects": {
            "vignette": {
                "amount": draw(signed),
                "midpoint": draw(unsigned),
                "roundness": draw(signed),
                "feather": draw(unsigned),
            }
        },
    }
    return AdjustmentParams.model_validate(data)


def _bases() -> list[tuple[LinearImage, bool]]:
    rng = np.random.default_rng(11)
    pixels = rng.uniform(0, 1, (16, 24, 3)).astype(np.float32)
    pixels[0, 0] = 0  # pure black
    pixels[0, 1] = 1  # clipped white
    raw = LinearImage(
        pixels=pixels,
        to_rec2020=color.camera_to_rec2020(XT3),
        is_raw=True,
        cam_from_xyz=XT3,
        as_shot_multipliers=color.camera_multipliers(XT3, 5000, 0),
    )
    raster = LinearImage(pixels=pixels, to_rec2020=np.eye(3), is_raw=False)
    return [(raw, True), (raster, False)]


BASES = _bases()


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(edits())
def test_every_valid_edit_renders_finite_in_range_and_deterministic(edit: AdjustmentParams) -> None:
    for base, is_raw in BASES:
        profile = GENERIC if is_raw else None
        out = render(base, edit, profile, original_width=24)
        assert np.isfinite(out).all()
        assert float(out.min()) >= 0 and float(out.max()) <= 1
        np.testing.assert_array_equal(out, render(base, edit, profile, original_width=24))


@pytest.mark.parametrize(
    "bad",
    [
        {"tone": {"exposure": 5.5}},
        {"tone": {"contrast": 101}},
        {"white_balance": {"temperature": 1500}},
        {"white_balance": {"tint": -151}},
        {"presence": {"saturation": float("nan")}},
        {"tone_curve": {"rgb": [{"x": 0, "y": 0}, {"x": 0, "y": 1}]}},
        {"tone_curve": {"rgb": [{"x": 0, "y": 0}, {"x": 1e-300, "y": 1}, {"x": 1, "y": 1}]}},
        {"tone_curve": {"rgb": [{"x": 0, "y": 1.2}, {"x": 1, "y": 1}]}},
        {"color_grading": {"shadows": {"hue": 360}}},
        {"detail": {"sharpening": {"radius": 0.2}}},
        {"effects": {"vignette": {"feather": -1}}},
        {"tone": {"brightness": 10}},
    ],
)
def test_invalid_edits_are_rejected_by_the_model(bad: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        AdjustmentParams.model_validate(bad)
