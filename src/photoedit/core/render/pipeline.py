"""The render pipeline: stages in the fixed order of PLAN 4.3, plus the checks around them.

Golden rule 3: the same decoded image, parameters, profile and engine version always give identical pixels.
Anything that changes pixels for given inputs must bump ``ENGINE_VERSION``.
"""

from __future__ import annotations

import itertools
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version as package_version

import numpy as np

from photoedit.core import color
from photoedit.core.cache import resize_linear
from photoedit.core.decode import LinearImage
from photoedit.core.decode import render_identity as decoder_identity
from photoedit.core.errors import InvalidRequestError
from photoedit.core.render import stages
from photoedit.core.render.profile import IDENTITY, CameraProfile
from photoedit.core.render.stages import F32
from photoedit.models.adjustments import AdjustmentParams, Hsl

ENGINE_VERSION = 1

# numpy releases the GIL in its array loops, so a few threads render strips of one image in parallel.
_STRIP_THREADS = 8
_MIN_STRIP_ROWS = 64
_POOL = ThreadPoolExecutor(max_workers=_STRIP_THREADS, thread_name_prefix="render")

# Parameters that exist in the model but whose rendering arrives in a later phase (decided 2026-10-08: setting
# them is an error, not a silent no-op).
LATER_PHASE_PARAMETERS = {
    "geometry": 6,
    "presence.clarity": 9,
    "presence.texture": 9,
    "presence.dehaze": 9,
    "detail.noise_reduction": 9,
    "effects.grain": 9,
    "lens": 9,
}


class UnsupportedParameterError(InvalidRequestError):
    """A parameter was set that this version can't render yet."""


def unsupported_parameters(params: AdjustmentParams) -> dict[str, int]:
    """Changed parameters that belong to a later phase, with that phase number."""
    found: dict[str, int] = {}
    for name in params.changed_fields():
        for prefix, phase in LATER_PHASE_PARAMETERS.items():
            if name == prefix or name.startswith(prefix + "."):
                found[name] = phase
    return found


def check_supported(params: AdjustmentParams) -> None:
    found = unsupported_parameters(params)
    if found:
        listed = ", ".join(f"{name} (Phase {phase})" for name, phase in sorted(found.items()))
        raise UnsupportedParameterError(f"not supported yet, leave at the default: {listed}")


def render_identity() -> str:
    """Everything that decides the pixels of a render, for cache keys and golden images."""
    return (
        f"{decoder_identity()}-eng{ENGINE_VERSION}"
        f"-numpy{package_version('numpy')}-opencv{package_version('opencv-python-headless')}"
    )


def render(
    base: LinearImage,
    params: AdjustmentParams,
    profile: CameraProfile | None,
    *,
    original_width: int,
    long_edge: int | None = None,
) -> F32:
    """Render to sRGB-encoded float pixels (0..1).

    ``profile`` is the camera profile for RAWs; None for JPEG/TIFF originals, which are already rendered
    (their "base curve" is the exact sRGB encoding, so an unedited render reproduces the original).
    ``original_width`` is the photo's full width, so sharpening means the same at every output size.
    """
    check_supported(params)
    image = resize_linear(base, long_edge) if long_edge is not None else base
    matrix = stages.white_balance_matrix(image, params.white_balance)
    baseline = 0.0
    if profile is not None:
        if profile.matrix != IDENTITY:
            matrix = np.array(profile.matrix, dtype=np.float64) @ matrix
        baseline = profile.baseline_exposure
    skip_matrix = not image.is_raw and np.array_equal(matrix, np.eye(3))
    exposure = params.tone.exposure + baseline
    profile_hsl = profile.hsl if profile is not None else Hsl()
    height, width = image.pixels.shape[:2]
    vignette = params.effects.vignette
    mask = stages.vignette_mask(height, width, vignette) if vignette.amount else None

    def pointwise(rows: slice) -> F32:
        # Every stage here works pixel by pixel, so rendering in strips gives exactly the full-frame result.
        rgb = image.pixels[rows]
        if not skip_matrix:
            rgb = color.apply_matrix(rgb, matrix)
        rgb = stages.exposure(rgb, exposure)
        rgb = stages.tone(rgb, params.tone)
        if profile is not None:
            encoded = stages.base_curve(rgb, profile)
        else:
            encoded = color.srgb_encode(np.clip(rgb, 0, 1)).astype(np.float32, copy=False)
        encoded = stages.curves(encoded, params.tone_curve)
        display = stages.to_display_linear(encoded)
        display = stages.color_adjust(display, profile_hsl, params.hsl, params.color_grading, params.presence)
        display = stages.vignette(display, vignette, None if mask is None else mask[rows])
        return stages.output_srgb(display)

    strips = _strips(height)
    parts = list(_POOL.map(pointwise, strips)) if len(strips) > 1 else [pointwise(strips[0])]
    out = np.concatenate(parts, axis=0) if len(parts) > 1 else parts[0]
    return stages.sharpen(out, params.detail.sharpening, out.shape[1] / original_width)


def _strips(height: int) -> list[slice]:
    count = max(1, min(_STRIP_THREADS, height // _MIN_STRIP_ROWS))
    edges = [round(i * height / count) for i in range(count + 1)]
    return [slice(a, b) for a, b in itertools.pairwise(edges)]
