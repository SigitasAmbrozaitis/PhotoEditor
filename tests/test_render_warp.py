from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from photoedit.core.decode import LinearImage
from photoedit.core.geometry import largest_crop, source_map, turned_size
from photoedit.core.render import pipeline
from photoedit.core.render.anchors import measure_anchors
from photoedit.core.render.pipeline import render
from photoedit.core.render.profile import GENERIC
from photoedit.core.render.warp import apply_geometry, crop_size, output_size
from photoedit.models.adjustments import AdjustmentParams, CropRect, Geometry
from test_render_pipeline import params, raw_base


def _image(pixels: np.ndarray) -> LinearImage:
    return dataclasses.replace(raw_base(), pixels=np.ascontiguousarray(pixels, dtype=np.float32))


def _random(height: int = 40, width: int = 60, seed: int = 1) -> np.ndarray:
    return np.random.default_rng(seed).uniform(0, 1, (height, width, 3)).astype(np.float32)


@pytest.mark.parametrize(
    ("geometry", "expected"),
    [
        (Geometry(rotate=90), lambda a: np.rot90(a, -1)),
        (Geometry(rotate=180), lambda a: a[::-1, ::-1]),
        (Geometry(rotate=270), lambda a: np.rot90(a, 1)),
        (Geometry(flip_horizontal=True), lambda a: a[:, ::-1]),
        (Geometry(flip_vertical=True), lambda a: a[::-1]),
        (Geometry(flip_horizontal=True, rotate=90), lambda a: np.rot90(a[:, ::-1], -1)),
    ],
)
def test_flips_and_quarter_turns_are_exact_permutations(geometry: Geometry, expected: object) -> None:
    pixels = _random()
    out = apply_geometry(_image(pixels), geometry).pixels
    np.testing.assert_array_equal(out, expected(pixels))  # type: ignore[operator]


def test_an_axis_aligned_crop_is_the_exact_sub_array() -> None:
    pixels = _random()
    crop = CropRect(left=0.25, top=0.1, right=0.75, bottom=0.6)
    out = apply_geometry(_image(pixels), Geometry(crop=crop)).pixels
    np.testing.assert_array_equal(out, pixels[4:24, 15:45])


def test_the_warp_samples_where_the_math_says() -> None:
    # Cubic interpolation reproduces a linear ramp, so each output pixel holds its source coordinates.
    height, width = 80, 120
    ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
    ramp = np.dstack([xs, ys, np.zeros_like(xs)])
    geometry = Geometry(angle=12, rotate=90, flip_vertical=True)
    frame_w, frame_h = turned_size(width, height, 90)
    crop = largest_crop(None, 12, frame_w, frame_h)
    out = apply_geometry(_image(ramp), geometry.model_copy(update={"crop": crop})).pixels
    matrix = source_map(geometry, crop, width, height, out.shape[1], out.shape[0])
    for v, u in [(0, 0), (5, 17), (out.shape[0] - 1, out.shape[1] - 1), (30, 2)]:
        x, y, _ = matrix @ np.array([u, v, 1.0])
        # OpenCV places samples on a 1/32 pixel grid, and its cubic (a = -0.75) bends ramps slightly.
        assert out[v, u, 0] == pytest.approx(x, abs=0.1)
        assert out[v, u, 1] == pytest.approx(y, abs=0.1)


def test_a_straightened_crop_samples_only_inside_the_photo() -> None:
    crop = largest_crop(4 / 5, -9, 140, 90)
    geometry = Geometry(angle=-9, crop=crop, aspect="4:5")
    out_w, out_h = output_size(geometry, crop, 140, 90, None)
    matrix = source_map(geometry, crop, 140, 90, out_w, out_h)
    vs, us = np.mgrid[0:out_h, 0:out_w]
    points = matrix @ np.stack([us.ravel(), vs.ravel(), np.ones(us.size)])
    # Every output pixel's center comes from within the photo's pixel area (no blank corners).
    assert points[0].min() >= -0.5 and points[0].max() <= 139.5
    assert points[1].min() >= -0.5 and points[1].max() <= 89.5
    # The whole frame at that angle would not.
    frame = source_map(geometry, CropRect(), 140, 90, 140, 90)
    assert (frame @ np.array([0, 0, 1.0]))[1] < -0.5


def test_sizes() -> None:
    crop = CropRect(left=0.1, top=0, right=0.6, bottom=0.5)
    assert crop_size(Geometry(rotate=90), crop, 600, 400) == (200, 300)
    assert output_size(Geometry(), crop, 600, 400, None) == (300, 200)
    assert output_size(Geometry(), crop, 600, 400, 150) == (150, 100)
    assert output_size(Geometry(), crop, 600, 400, 1000) == (300, 200)  # never enlarged
    image = apply_geometry(_image(_random(400, 600)), Geometry(crop=crop), size=(90, 60))
    assert image.pixels.shape == (60, 90, 3)


def test_warp_is_deterministic() -> None:
    geometry = Geometry(angle=3.3, crop=largest_crop(None, 3.3, 60, 40))
    first = apply_geometry(_image(_random()), geometry, long_edge=33).pixels
    np.testing.assert_array_equal(first, apply_geometry(_image(_random()), geometry, long_edge=33).pixels)


# ------------------------------------------------------------------ in the pipeline


def _geometry_edit(**extra: dict[str, object]) -> AdjustmentParams:
    crop = largest_crop(None, 6, 200, 300)
    crop = CropRect(left=crop.left + 0.1, top=crop.top + 0.05, right=crop.right - 0.05, bottom=crop.bottom)
    return params(
        geometry={"angle": 6, "crop": crop.model_dump()},
        effects={"vignette": {"amount": -60}},
        detail={"sharpening": {"amount": 90}},
        **extra,
    )


def test_render_applies_the_geometry_first() -> None:
    # The same as rendering the cropped base without geometry: the vignette and sharpening follow the crop.
    base = raw_base(height=300, width=200, seed=3)
    edit = _geometry_edit(tone={"contrast": 20})
    anchors = measure_anchors(base, GENERIC)
    out = render(base, edit, GENERIC, original_width=400, anchors=anchors)
    cropped = apply_geometry(base, edit.geometry)
    crop_full_width = crop_size(edit.geometry, edit.geometry.crop, 400, 600)[0]
    without = edit.model_copy(update={"geometry": Geometry()})
    expected = render(cropped, without, GENERIC, original_width=crop_full_width, anchors=anchors)  # type: ignore[arg-type]
    np.testing.assert_array_equal(out, expected)


def test_geometry_renders_measure_tone_on_the_whole_photo() -> None:
    # Without stored anchors they come from the uncropped base, so cropping keeps the tone curve.
    base = raw_base(height=300, width=200, seed=3)
    edit = _geometry_edit(tone={"contrast": 40, "shadows": 30})
    anchors = measure_anchors(base, GENERIC)
    np.testing.assert_array_equal(
        render(base, edit, GENERIC, original_width=200),
        render(base, edit, GENERIC, original_width=200, anchors=anchors),
    )


def test_geometry_render_strips_and_long_edge(monkeypatch: pytest.MonkeyPatch) -> None:
    base = raw_base(height=300, width=200, seed=4)
    edit = _geometry_edit()
    full = render(base, edit, GENERIC, original_width=200)
    np.testing.assert_array_equal(full, render(base, edit, GENERIC, original_width=200, low_memory=True))
    monkeypatch.setattr(pipeline, "_STRIP_THREADS", 1)
    np.testing.assert_array_equal(full, render(base, edit, GENERIC, original_width=200))
    small = render(base, edit, GENERIC, original_width=200, long_edge=100)
    assert max(small.shape[:2]) == 100


def test_default_geometry_renders_as_before() -> None:
    # No geometry = no warp: the pixels are those of the Phase 5 pipeline (no golden image changes).
    base = raw_base(seed=8)
    plain = params(tone={"exposure": 0.3}, detail={"sharpening": {"amount": 50}})
    locked = plain.model_copy(update={"geometry": Geometry(aspect="3:2")})
    np.testing.assert_array_equal(
        render(base, plain, GENERIC, original_width=90, long_edge=45),
        render(base, locked, GENERIC, original_width=90, long_edge=45),
    )
