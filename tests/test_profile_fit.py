from __future__ import annotations

import numpy as np
import pytest

from photoedit.core import profile_fit as pf
from photoedit.core.render.profile import (
    GENERIC,
    CameraProfile,
    ProfileCurvePoint,
    builtin_profiles,
    profile_for,
)
from photoedit.models.adjustments import Hsl, HslBand

TEMPLATE = GENERIC.model_copy(update={"id": "test", "name": "Test"})


def test_unpack_always_gives_a_valid_profile() -> None:
    rng = np.random.default_rng(0)
    low, high = pf.bounds()
    for _ in range(20):
        theta = rng.normal(0, 2, pf._N_PARAMS)
        theta = np.clip(theta, np.where(np.isfinite(low), low, -10), np.where(np.isfinite(high), high, 10))
        profile = pf.unpack(theta, TEMPLATE)  # validators run here: monotone curve, matrix in range, HSL ±100
        assert all(abs(sum(row) - 1) < 1e-12 for row in profile.matrix)  # grays stay gray
        assert profile.tone_curve[0].value == 0 and profile.tone_curve[-1].value == 1


def test_initial_parameters_start_from_the_generic_curve() -> None:
    profile = pf.unpack(pf.initial_parameters(0.3), TEMPLATE)
    assert profile.baseline_exposure == 0.3
    generic = dict((p.stops, p.value) for p in GENERIC.tone_curve)
    for point in profile.tone_curve[1:-1]:
        if point.stops in generic:
            assert point.value == pytest.approx(generic[point.stops], abs=1e-3)
    assert profile.matrix == ((1, 0, 0), (0, 1, 0), (0, 0, 1)) and profile.hsl == Hsl()


def test_fit_recovers_a_known_look() -> None:
    """Render random scene colors with a known profile, then fit: the result must reproduce those renders."""
    rng = np.random.default_rng(42)
    scene = (0.18 * 2.0 ** rng.uniform(-5, 2.5, (4000, 1)) * rng.uniform(0.3, 1.0, (4000, 3))).astype(
        np.float32
    )
    truth = TEMPLATE.model_copy(
        update={
            "baseline_exposure": 0.4,
            "matrix": ((0.9, 0.05, 0.05), (0.05, 0.85, 0.1), (0.0, 0.1, 0.9)),
            "tone_curve": [
                ProfileCurvePoint(stops=s, value=v)
                for s, v in [
                    (-12, 0),
                    (-6, 0.02),
                    (-3, 0.12),
                    (-1, 0.33),
                    (0, 0.45),
                    (1, 0.6),
                    (3, 0.88),
                    (6, 1),
                ]
            ],
            "hsl": Hsl(blue=HslBand(saturation=-20)),
        }
    )
    target = pf.render_samples(scene, truth)
    samples = pf.PairSamples(name="synthetic", scene=scene, target=target)
    before = pf.mean_delta_e(samples, GENERIC)
    fitted, _ = pf.fit_profile([samples], TEMPLATE, max_evaluations=400)
    after = pf.mean_delta_e(samples, fitted)
    assert before > 2  # the known look differs visibly from the generic one
    assert after < 1.0  # below "just noticeable"


def test_format_report_lists_holdout_and_means() -> None:
    report = pf.FitReport(
        profile=TEMPLATE, train=["a", "b"], holdout={"x": (4.0, 2.0), "y": (3.0, 1.0)}, iterations=12
    )
    text = pf.format_report(report)
    assert "| x | 4.00 | 2.00 |" in text and "**Mean ΔE2000: 3.50 → 1.50**" in text


def test_profile_selection_falls_back_to_generic() -> None:
    assert profile_for(None) is GENERIC
    assert profile_for("Some Camera 9000") is GENERIC
    for profile in builtin_profiles():
        assert isinstance(profile, CameraProfile)
        assert profile_for(f"{profile.make} {profile.model}".upper()).id == profile.id  # case-insensitive
