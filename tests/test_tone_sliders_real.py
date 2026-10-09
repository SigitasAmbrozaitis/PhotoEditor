"""P3.24 acceptance on the real sample photos: every tone slider visibly changes its part of each photo."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pytest

from photoedit.core import color
from photoedit.core.cache import LINEAR_LONG_EDGE, resize_linear
from photoedit.core.decode import decode_linear
from photoedit.core.render import stages
from photoedit.core.render.anchors import measure_anchors
from photoedit.core.render.pipeline import render
from photoedit.core.render.profile import profile_for
from photoedit.models import AdjustmentParams
from photoedit.models.adjustments import WhiteBalance

PREVIEW = 1600
SLIDERS = ("whites", "highlights", "shadows", "blacks")
MIN_CHANGED = 0.25  # share of a slider's own visible pixels that must change by >= 2 levels at ±100
# Pixels this dark in the unedited preview are black on screen: they can't get 2 levels darker, and a lift in
# stops leaves (near) zero at (near) zero. They don't count toward "visibly changes".
BLACK_LEVEL = 3


def _check(path: Path) -> list[str]:
    """Problems found on one photo (empty = every slider passes)."""
    profile = profile_for("FUJIFILM X-T3")
    decoded = decode_linear(path, half_size=True)
    anchors = measure_anchors(decoded, profile)
    base = resize_linear(decoded, LINEAR_LONG_EDGE)

    def preview(params: AdjustmentParams) -> npt.NDArray[np.int16]:
        out = render(base, params, profile, original_width=6240, long_edge=PREVIEW, anchors=anchors)
        return np.asarray(stages.quantize(out), dtype=np.int16)

    # Each pixel's place in the photo's range: scene stops of the unedited render, as the anchors measure it.
    small = resize_linear(base, PREVIEW)
    matrix = np.array(profile.matrix) @ stages.white_balance_matrix(small, WhiteBalance())
    luminance = stages.luminance(color.apply_matrix(small.pixels, matrix)).astype(np.float64)
    stops = np.log2(np.maximum(luminance, 1e-9) / stages.MID_GRAY) + profile.baseline_exposure
    pivot, bands = stages.tone_bands(anchors.black, anchors.white)
    unedited = preview(AdjustmentParams())
    visible = unedited.max(axis=-1) >= BLACK_LEVEL
    problems = []
    for name in SLIDERS:
        center, half_width = bands[name]
        # A slider's own pixels: the core of its band and everything it moves beyond it.
        mine = stops >= center - half_width / 2 if center > pivot else stops <= center + half_width / 2
        mine &= visible
        for value in (-100, 100):
            edited = preview(AdjustmentParams.model_validate({"tone": {name: value}}))
            changed = (np.abs(edited - unedited).max(axis=-1) >= 2)[mine]
            if changed.mean() < MIN_CHANGED:
                problems.append(f"{path.name} {name} {value:+d}: {changed.mean():.0%} of its pixels changed")
    return problems


@pytest.mark.golden
@pytest.mark.slow
def test_every_tone_slider_visibly_changes_its_part_of_every_sample(sample_photos_dir: Path) -> None:
    raws = sorted(sample_photos_dir.glob("*.RAF"))
    if not raws:
        pytest.skip("no .RAF files in sample_photos_dir")
    # LibRaw and the numpy stages release the GIL, so a few photos at a time keep this to a few minutes.
    with ThreadPoolExecutor(max_workers=4) as pool:
        problems = [p for found in pool.map(_check, raws) for p in found]
    assert not problems, "\n".join(problems)
