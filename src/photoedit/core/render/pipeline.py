"""The render pipeline: stages in the fixed order of PLAN 4.3, plus the checks around them.

Golden rule 3: the same decoded image, parameters, profile and engine version always give identical pixels.
Anything that changes pixels for given inputs must bump ``ENGINE_VERSION``.
"""

from __future__ import annotations

import itertools
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version as package_version

import numpy as np
import numpy.typing as npt

from photoedit.core import color
from photoedit.core.cache import resize_linear
from photoedit.core.decode import LinearImage
from photoedit.core.decode import render_identity as decoder_identity
from photoedit.core.errors import InvalidRequestError
from photoedit.core.render import stages
from photoedit.core.render.anchors import ToneAnchors, measure_anchors
from photoedit.core.render.profile import IDENTITY, CameraProfile
from photoedit.core.render.stages import F32
from photoedit.models.adjustments import AdjustmentParams, Hsl
from photoedit.models.export import ColorSpace

ENGINE_VERSION = 2

# numpy releases the GIL in its array loops, so a few threads render strips of one image in parallel.
_STRIP_THREADS = 8
_MIN_STRIP_ROWS = 64
# Low-memory renders (full-size exports, several per machine): strips of at most this many rows, this many
# at a time, so the per-pixel stages' intermediates stay small. Same pixels, as strips always give.
_LOW_MEMORY_ROWS = 256
_LOW_MEMORY_THREADS = 2
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
    anchors: ToneAnchors | None = None,
    output: ColorSpace = ColorSpace.SRGB,
    low_memory: bool = False,
) -> F32:
    """Render to ``output``-encoded float pixels (0..1); sRGB unless an export asks for another space.

    ``profile`` is the camera profile for RAWs; None for JPEG/TIFF originals, which are already rendered
    (their "base curve" is the exact sRGB encoding, so an unedited render reproduces the original).
    ``original_width`` is the photo's full width, so sharpening means the same at every output size.
    ``anchors`` are the photo's tone anchors; the library passes the stored ones so every size of a photo gets
    the same tone curve. Without them they are measured on ``base``. ``low_memory`` renders in more, smaller
    strips, fewer at a time (for full-size exports in parallel worker processes); the pixels are the same.
    """
    check_supported(params)
    tone_params = params.tone
    tone_curve: npt.NDArray[np.float64] | None = None
    if (
        tone_params.contrast
        or tone_params.highlights
        or tone_params.shadows
        or tone_params.whites
        or (tone_params.blacks)
    ):
        black, white = (anchors or measure_anchors(base, profile)).shifted(tone_params.exposure)
        tone_curve = stages.tone_curve_stops(tone_params, black, white)
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
        if tone_curve is not None:
            rgb = stages.apply_tone_curve(rgb, tone_curve)
        if profile is not None:
            encoded = stages.base_curve(rgb, profile)
        else:
            encoded = color.srgb_encode(np.clip(rgb, 0, 1)).astype(np.float32, copy=False)
        encoded = stages.curves(encoded, params.tone_curve)
        display = stages.to_display_linear(encoded)
        display = stages.color_adjust(display, profile_hsl, params.hsl, params.color_grading, params.presence)
        display = stages.vignette(display, vignette, None if mask is None else mask[rows])
        return stages.output_encode(display, output)

    strips = _strips(height, max_rows=_LOW_MEMORY_ROWS if low_memory else None)
    out = np.empty((height, width, 3), dtype=np.float32)

    def into_out(rows: slice) -> None:
        out[rows] = pointwise(rows)

    if len(strips) == 1:
        into_out(strips[0])
    else:
        at_once = _LOW_MEMORY_THREADS if low_memory else _STRIP_THREADS
        for first in range(0, len(strips), at_once):
            list(_POOL.map(into_out, strips[first : first + at_once]))
    return stages.sharpen(out, params.detail.sharpening, out.shape[1] / original_width)


def _strips(height: int, *, max_rows: int | None = None) -> list[slice]:
    count = max(1, min(_STRIP_THREADS, height // _MIN_STRIP_ROWS))
    if max_rows is not None:
        count = max(count, -(-height // max_rows))
    edges = [round(i * height / count) for i in range(count + 1)]
    return [slice(a, b) for a, b in itertools.pairwise(edges)]
