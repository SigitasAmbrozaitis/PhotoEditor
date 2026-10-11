"""The render pipeline: stages in the fixed order of PLAN 4.3, plus the checks around them.

Golden rule 3: the same decoded image, parameters, profile and engine version always give identical pixels.
Anything that changes pixels for given inputs must bump ``ENGINE_VERSION``.
"""

from __future__ import annotations

import itertools
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from importlib.metadata import version as package_version

import numpy as np
import numpy.typing as npt

from photoedit.core import color
from photoedit.core.cache import resize_linear
from photoedit.core.decode import LinearImage
from photoedit.core.decode import render_identity as decoder_identity
from photoedit.core.errors import InvalidRequestError
from photoedit.core.geometry import is_identity, turned_size
from photoedit.core.render import stages
from photoedit.core.render.anchors import ToneAnchors, measure_anchors
from photoedit.core.render.profile import IDENTITY, CameraProfile
from photoedit.core.render.stages import F32
from photoedit.core.render.warp import apply_geometry
from photoedit.models.adjustments import AdjustmentParams, Geometry, Hsl
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
    ``original_width`` is the photo's full (upright) width, so sharpening means the same at every output size.
    The geometry (flips, quarter turn, straighten, crop) is applied to ``base`` first; ``long_edge`` then
    limits the cropped image.
    ``anchors`` are the photo's tone anchors; the library passes the stored ones so every size of a photo gets
    the same tone curve. Without them they are measured on ``base``. ``low_memory`` renders in more, smaller
    strips, fewer at a time (for full-size exports in parallel worker processes); the pixels are the same.
    """
    check_supported(params)
    if anchors is None and _needs_anchors(params):
        anchors = measure_anchors(base, profile)
    image, full_width = geometry_stage(base, params, original_width=original_width, long_edge=long_edge)
    pointwise = _Pointwise.prepare(image, params, profile, anchors, output)
    height, width = image.pixels.shape[:2]
    vignette = params.effects.vignette
    mask = stages.vignette_mask(height, width, vignette) if vignette.amount else None
    strips = _strips(height, max_rows=_LOW_MEMORY_ROWS if low_memory else None)
    out = np.empty((height, width, 3), dtype=np.float32)

    def into_out(rows: slice) -> None:
        # Every stage here works pixel by pixel, so rendering in strips gives exactly the full-frame result.
        out[rows] = pointwise.apply(image.pixels[rows], None if mask is None else mask[rows])

    if len(strips) == 1:
        into_out(strips[0])
    else:
        at_once = _LOW_MEMORY_THREADS if low_memory else _STRIP_THREADS
        for first in range(0, len(strips), at_once):
            list(_POOL.map(into_out, strips[first : first + at_once]))
    return stages.sharpen(out, params.detail.sharpening, out.shape[1] / full_width)


def geometry_stage(
    base: LinearImage,
    params: AdjustmentParams,
    *,
    original_width: int,
    long_edge: int | None = None,
) -> tuple[LinearImage, float]:
    """``base`` with the edit's geometry applied (and limited to ``long_edge``), plus the width of what it
    shows in the photo's full-size pixels (for sharpening)."""
    geometry = params.geometry
    full_width = shown_width(base, geometry, original_width)
    if is_identity(geometry):
        return (resize_linear(base, long_edge) if long_edge is not None else base), full_width
    return apply_geometry(base, geometry, long_edge=long_edge), full_width


def shown_width(base: LinearImage, geometry: Geometry, original_width: int) -> float:
    """The width of what ``geometry`` shows, in the photo's full-size pixels (``base`` may be any size)."""
    if is_identity(geometry):
        return float(original_width)
    base_h, base_w = base.pixels.shape[:2]
    frame_w = turned_size(base_w, base_h, geometry.rotate)[0]
    crop = geometry.crop
    return float((crop.right - crop.left) * frame_w * original_width / base_w)


def render_window(
    image: LinearImage,
    params: AdjustmentParams,
    profile: CameraProfile | None,
    *,
    anchors: ToneAnchors,
    full_width: float,
    window: tuple[int, int, int, int],
    output: ColorSpace = ColorSpace.SRGB,
) -> F32:
    """The part ``window`` = (left, top, right, bottom) of ``render``'s result, for an ``image`` that already
    has the geometry applied (``geometry_stage``, which also gives ``full_width``).

    The same pixels as that region of the whole render: the vignette is placed relative to the whole image,
    and sharpening sees a margin of real neighbors that is cut off afterwards.
    """
    check_supported(params)
    height, width = image.pixels.shape[:2]
    left, top, right, bottom = window
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise InvalidRequestError(f"window {window} is outside the {width}×{height} image")
    scale = width / full_width
    sharpening = params.detail.sharpening
    # OpenCV's Gaussian reaches ~4 sigma; the masking gradient needs one more pixel, and one for rounding.
    margin = math.ceil(4 * sharpening.radius * scale) + 3
    x0, y0 = max(0, left - margin), max(0, top - margin)
    x1, y1 = min(width, right + margin), min(height, bottom + margin)
    vignette = params.effects.vignette
    mask = stages.vignette_mask(height, width, vignette, window=(x0, y0, x1, y1)) if vignette.amount else None
    pointwise = _Pointwise.prepare(image, params, profile, anchors, output)
    out = pointwise.apply(image.pixels[y0:y1, x0:x1], mask)
    out = stages.sharpen(out, sharpening, scale)
    return np.ascontiguousarray(out[top - y0 : bottom - y0, left - x0 : right - x0])


def _needs_anchors(params: AdjustmentParams) -> bool:
    tone = params.tone
    return bool(tone.contrast or tone.highlights or tone.shadows or tone.whites or tone.blacks)


@dataclass(frozen=True)
class _Pointwise:
    """The per-pixel stages, prepared once per render."""

    params: AdjustmentParams
    profile: CameraProfile | None
    matrix: npt.NDArray[np.float64]
    skip_matrix: bool
    exposure: float
    tone_curve: npt.NDArray[np.float64] | None
    profile_hsl: Hsl
    output: ColorSpace

    @classmethod
    def prepare(
        cls,
        image: LinearImage,
        params: AdjustmentParams,
        profile: CameraProfile | None,
        anchors: ToneAnchors | None,
        output: ColorSpace,
    ) -> _Pointwise:
        tone_curve = None
        if _needs_anchors(params):
            assert anchors is not None
            black, white = anchors.shifted(params.tone.exposure)
            tone_curve = stages.tone_curve_stops(params.tone, black, white)
        matrix = stages.white_balance_matrix(image, params.white_balance)
        baseline = 0.0
        if profile is not None:
            if profile.matrix != IDENTITY:
                matrix = np.array(profile.matrix, dtype=np.float64) @ matrix
            baseline = profile.baseline_exposure
        return cls(
            params=params,
            profile=profile,
            matrix=matrix,
            skip_matrix=not image.is_raw and np.array_equal(matrix, np.eye(3)),
            exposure=params.tone.exposure + baseline,
            tone_curve=tone_curve,
            profile_hsl=profile.hsl if profile is not None else Hsl(),
            output=output,
        )

    def apply(self, rgb: F32, mask: F32 | None) -> F32:
        params = self.params
        if not self.skip_matrix:
            rgb = color.apply_matrix(rgb, self.matrix)
        rgb = stages.exposure(rgb, self.exposure)
        if self.tone_curve is not None:
            rgb = stages.apply_tone_curve(rgb, self.tone_curve)
        if self.profile is not None:
            encoded = stages.base_curve(rgb, self.profile)
        else:
            encoded = color.srgb_encode(np.clip(rgb, 0, 1)).astype(np.float32, copy=False)
        encoded = stages.curves(encoded, params.tone_curve)
        display = stages.to_display_linear(encoded)
        display = stages.color_adjust(
            display, self.profile_hsl, params.hsl, params.color_grading, params.presence
        )
        display = stages.vignette(display, params.effects.vignette, mask)
        return stages.output_encode(display, self.output)


def _strips(height: int, *, max_rows: int | None = None) -> list[slice]:
    count = max(1, min(_STRIP_THREADS, height // _MIN_STRIP_ROWS))
    if max_rows is not None:
        count = max(count, -(-height // max_rows))
    edges = [round(i * height / count) for i in range(count + 1)]
    return [slice(a, b) for a, b in itertools.pairwise(edges)]
