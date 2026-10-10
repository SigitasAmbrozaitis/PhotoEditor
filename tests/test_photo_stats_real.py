"""Per-photo measurements on real photos from the style sample folders (P4.4). Read-only."""

from __future__ import annotations

import statistics
from pathlib import Path

import pytest

from photoedit.core.decode import decode_linear
from photoedit.core.render.anchors import measure_stats
from photoedit.core.render.profile import profile_for

RALLY = "2026-08-16"  # daylight, camera auto white balance
SAMPLE_EVERY = 15  # every 15th photo: 13 of 183, spread over the day


@pytest.mark.golden
@pytest.mark.slow
def test_neutral_estimate_agrees_with_the_camera_in_daylight(style_sample_dirs: dict[str, Path]) -> None:
    if RALLY not in style_sample_dirs:
        pytest.skip(f"style sample folder {RALLY} is not configured")
    raws = sorted(style_sample_dirs[RALLY].glob("*.RAF"))[::SAMPLE_EVERY]
    differences = []
    for path in raws:
        base = decode_linear(path, half_size=True)
        stats = measure_stats(base, profile_for("FUJIFILM X-T3"))
        differences.append(stats.neutral_temperature - base.as_shot[0])
        assert -8 < stats.middle < 2 and stats.black <= stats.middle <= stats.white
    # Measured 2026-10-09 on all 183: median -251 K, 80 % between -582 K and +137 K.
    assert abs(statistics.median(differences)) < 500
    assert sum(abs(d) < 1000 for d in differences) >= 0.8 * len(differences)
