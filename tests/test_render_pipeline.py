from __future__ import annotations

import threading

import numpy as np
import pytest

from photoedit.core import color
from photoedit.core.decode import LinearImage
from photoedit.core.render import pipeline
from photoedit.core.render.pipeline import UnsupportedParameterError, render
from photoedit.core.render.profile import GENERIC
from photoedit.models.adjustments import AdjustmentParams

XT3 = np.array([[1.6393, -0.7740, -0.1436], [-0.4140, 1.1745, 0.2632], [-0.0536, 0.1413, 0.6614]])


def raw_base(height: int = 60, width: int = 90, seed: int = 0) -> LinearImage:
    rng = np.random.default_rng(seed)
    pixels = rng.uniform(0, 0.6, (height, width, 3)).astype(np.float32)
    return LinearImage(
        pixels=pixels,
        to_rec2020=color.camera_to_rec2020(XT3),
        is_raw=True,
        cam_from_xyz=XT3,
        as_shot_multipliers=color.camera_multipliers(XT3, 5200, 3),
    )


def params(**groups: dict[str, object]) -> AdjustmentParams:
    return AdjustmentParams.model_validate(groups)


def test_neutral_raw_render_is_in_range() -> None:
    out = render(raw_base(), AdjustmentParams(), GENERIC, original_width=90)
    assert out.shape == (60, 90, 3) and out.dtype == np.float32
    assert float(out.min()) >= 0 and float(out.max()) <= 1 and np.isfinite(out).all()


def test_long_edge_scales_the_output() -> None:
    assert render(raw_base(), AdjustmentParams(), GENERIC, original_width=90, long_edge=45).shape == (
        30,
        45,
        3,
    )


def test_profile_baseline_equals_exposure() -> None:
    base = raw_base()
    lifted = GENERIC.model_copy(update={"baseline_exposure": 1.0})
    a = render(base, AdjustmentParams(), lifted, original_width=90)
    b = render(base, params(tone={"exposure": 1.0}), GENERIC, original_width=90)
    np.testing.assert_array_equal(a, b)


def test_exposure_brightens() -> None:
    base = raw_base()
    dark = render(base, params(tone={"exposure": -1}), GENERIC, original_width=90)
    bright = render(base, params(tone={"exposure": 1}), GENERIC, original_width=90)
    assert float(bright.mean()) > float(dark.mean()) + 0.1


def test_raster_neutral_render_reproduces_the_original() -> None:
    rng = np.random.default_rng(5)
    encoded = rng.uniform(0, 1, (20, 30, 3))
    linear = color.apply_matrix(color.srgb_decode(encoded), color.REC2020_FROM_SRGB)
    base = LinearImage(pixels=linear.astype(np.float32), to_rec2020=np.eye(3), is_raw=False)
    no_sharpening = params(detail={"sharpening": {"amount": 0}})
    out = render(base, no_sharpening, None, original_width=30)
    np.testing.assert_allclose(out, encoded, atol=1 / 512)


def test_later_phase_parameters_are_rejected_with_their_phase() -> None:
    edit = params(
        geometry={"angle": 3}, presence={"clarity": 20, "saturation": 10}, effects={"grain": {"amount": 5}}
    )
    assert pipeline.unsupported_parameters(edit) == {
        "geometry.angle": 6,
        "presence.clarity": 9,
        "effects.grain.amount": 9,
    }
    with pytest.raises(
        UnsupportedParameterError, match=r"geometry\.angle \(Phase 6\).*presence\.clarity \(Phase 9\)"
    ):
        render(raw_base(), edit, GENERIC, original_width=90)
    assert pipeline.unsupported_parameters(params(presence={"saturation": 10})) == {}


def test_render_is_bit_identical_across_runs_and_threads() -> None:
    base = raw_base(seed=7)
    edit = params(
        tone={"exposure": 0.4, "contrast": 30, "shadows": 40, "highlights": -30},
        presence={"vibrance": 25},
        hsl={"blue": {"hue": -20, "saturation": 30}},
        color_grading={"shadows": {"hue": 210, "saturation": 30}},
        effects={"vignette": {"amount": -30}},
        detail={"sharpening": {"amount": 60}},
    )
    first = render(base, edit, GENERIC, original_width=45)
    np.testing.assert_array_equal(first, render(base, edit, GENERIC, original_width=45))
    result: dict[str, np.ndarray] = {}
    thread = threading.Thread(
        target=lambda: result.setdefault("out", render(base, edit, GENERIC, original_width=45))
    )
    thread.start()
    thread.join()
    np.testing.assert_array_equal(first, result["out"])


def test_render_identity_names_engine_and_libraries() -> None:
    identity = pipeline.render_identity()
    assert f"-eng{pipeline.ENGINE_VERSION}-" in identity and "numpy" in identity and "opencv" in identity


def test_strip_rendering_equals_one_strip(monkeypatch: pytest.MonkeyPatch) -> None:
    base = raw_base(height=300, width=200, seed=9)
    edit = params(
        tone={"contrast": 25},
        hsl={"red": {"saturation": 30}},
        effects={"vignette": {"amount": -50}},
        detail={"sharpening": {"amount": 80}},
    )
    strips = render(base, edit, GENERIC, original_width=200)
    assert len(pipeline._strips(300)) > 1
    monkeypatch.setattr(pipeline, "_LOW_MEMORY_ROWS", 40)
    assert len(pipeline._strips(300, max_rows=40)) == 8
    np.testing.assert_array_equal(strips, render(base, edit, GENERIC, original_width=200, low_memory=True))
    monkeypatch.setattr(pipeline, "_STRIP_THREADS", 1)
    assert len(pipeline._strips(300)) == 1
    np.testing.assert_array_equal(strips, render(base, edit, GENERIC, original_width=200))
