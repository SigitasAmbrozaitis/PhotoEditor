"""The render pipeline: stages in the fixed order of PLAN 4.3, plus the checks around them.

Golden rule 3: the same decoded image, parameters, profile and engine version always give identical pixels.
Anything that changes pixels for given inputs must bump ``ENGINE_VERSION``.
"""

from __future__ import annotations

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
    rgb = stages.white_balance(image, params.white_balance)
    baseline = 0.0
    if profile is not None:
        if profile.matrix != IDENTITY:
            rgb = color.apply_matrix(rgb, np.array(profile.matrix, dtype=np.float64))
        baseline = profile.baseline_exposure
    rgb = stages.exposure(rgb, params.tone.exposure + baseline)
    rgb = stages.tone(rgb, params.tone)
    if profile is not None:
        encoded = stages.base_curve(rgb, profile)
    else:
        encoded = color.srgb_encode(np.clip(rgb, 0, 1)).astype(np.float32, copy=False)
    encoded = stages.curves(encoded, params.tone_curve)
    display = stages.to_display_linear(encoded)
    display = stages.color_adjust(
        display,
        profile.hsl if profile is not None else Hsl(),
        params.hsl,
        params.color_grading,
        params.presence,
    )
    display = stages.vignette(display, params.effects.vignette)
    out = stages.output_srgb(display)
    return stages.sharpen(out, params.detail.sharpening, out.shape[1] / original_width)
