"""Golden images: fixed renders that later versions are compared against, to catch unintended changes.

Two kinds:
- synthetic: a generated color chart + ramps, rendered with fixed edits. Small, committed to the repository
  (``tests/golden/``), compared bit-exactly.
- real photos: a few sample RAWs rendered into ``output/golden/`` on this machine (they stay local, decided
  2026-10-08), compared within a small ΔE tolerance.

An intended change to the engine (``ENGINE_VERSION`` bump) means regenerating both.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import numpy.typing as npt
from PIL import Image

from photoedit.core import color
from photoedit.core.cache import resize_linear
from photoedit.core.decode import LinearImage, decode_linear
from photoedit.core.render.pipeline import render, render_identity
from photoedit.core.render.profile import GENERIC, CameraProfile, profile_for
from photoedit.core.render.stages import quantize
from photoedit.models import AdjustmentParams
from photoedit.safety import PathGuard

type U8 = npt.NDArray[np.uint8]

GOLDEN_LONG_EDGE = 512
# The 24 patches of the classic ColorChecker chart, sRGB-encoded (BabelColor averages).
CHART = [
    (115, 82, 68), (194, 150, 130), (98, 122, 157), (87, 108, 67), (133, 128, 177), (103, 189, 170),
    (214, 126, 44), (80, 91, 166), (193, 90, 99), (94, 60, 108), (157, 188, 64), (224, 163, 46),
    (56, 61, 150), (70, 148, 73), (175, 54, 60), (231, 199, 31), (187, 86, 149), (8, 133, 161),
    (243, 243, 242), (200, 200, 200), (160, 160, 160), (122, 122, 121), (85, 85, 85), (52, 52, 52),
]  # fmt: skip

GOLDEN_EDITS: dict[str, AdjustmentParams] = {
    "neutral": AdjustmentParams(),
    "busy": AdjustmentParams.model_validate(
        {
            "white_balance": {"temperature": 4300, "tint": 12},
            "tone": {
                "exposure": 0.6,
                "contrast": 35,
                "highlights": -40,
                "shadows": 30,
                "whites": 10,
                "blacks": -15,
            },
            "presence": {"vibrance": 25, "saturation": -10},
            "tone_curve": {
                "darks": -20,
                "lights": 15,
                "rgb": [{"x": 0, "y": 0.05}, {"x": 0.5, "y": 0.52}, {"x": 1, "y": 0.97}],
            },
            "hsl": {"blue": {"hue": -15, "saturation": 20}, "green": {"saturation": -30, "luminance": 10}},
            "color_grading": {
                "shadows": {"hue": 210, "saturation": 25},
                "highlights": {"hue": 40, "saturation": 20},
            },
            "effects": {"vignette": {"amount": -35}},
            "detail": {"sharpening": {"amount": 70}},
        }
    ),
}


def synthetic_scene() -> LinearImage:
    """96×64 scene-linear test image: the chart (6×4 patches of 16 px) over a gray ramp and a hue ramp."""
    height, width = 64, 96
    pixels = np.zeros((height, width, 3), dtype=np.float64)
    chart = color.apply_matrix(
        color.srgb_decode(np.array(CHART, dtype=np.float64) / 255), color.REC2020_FROM_SRGB
    )
    for index, rgb in enumerate(chart):
        row, col = divmod(index, 6)
        pixels[row * 12 : row * 12 + 12, col * 16 : col * 16 + 16] = rgb
    # Gray ramp from 12 stops under to 3 stops over mid gray: exercises the whole tone curve.
    stops = np.linspace(-12, 3, width)
    pixels[48:56] = (0.18 * 2.0**stops)[None, :, None]
    # Saturated hue ramp.
    hue = np.linspace(0, 1, width, endpoint=False)
    ramp = np.stack([np.abs(hue * 6 - 3) - 1, 2 - np.abs(hue * 6 - 2), 2 - np.abs(hue * 6 - 4)], axis=-1)
    pixels[56:64] = np.clip(ramp, 0, 1)[None] * 0.5
    # Pixels are camera RGB already balanced, with an identity "camera matrix": the RAW path without LibRaw.
    return LinearImage(pixels=pixels.astype(np.float32), to_rec2020=np.eye(3), is_raw=True)


def render_synthetic(profile: CameraProfile, edit: str) -> U8:
    out = render(synthetic_scene(), GOLDEN_EDITS[edit], profile, original_width=96)
    return np.asarray(quantize(out, 8), dtype=np.uint8)


def synthetic_cases() -> list[tuple[str, CameraProfile, str]]:
    """(file stem, profile, edit) for every committed synthetic golden image."""
    xt3 = profile_for("FUJIFILM X-T3")
    return [(f"synthetic-{p.id}-{e}", p, e) for p in (GENERIC, xt3) for e in GOLDEN_EDITS]


# ----------------------------------------------------------------- real photos (local only)


def render_photo(path: Path, camera: str | None, width: int, edit: str) -> U8:
    base = resize_linear(decode_linear(path, half_size=True), GOLDEN_LONG_EDGE * 2)
    out = render(
        base, GOLDEN_EDITS[edit], profile_for(camera), original_width=width, long_edge=GOLDEN_LONG_EDGE
    )
    return np.asarray(quantize(out, 8), dtype=np.uint8)


def write_png(guard: PathGuard, path: Path, pixels: U8) -> None:
    import io

    buf = io.BytesIO()
    Image.fromarray(pixels).save(buf, "PNG")
    guard.write_atomic(path, buf.getvalue())


def read_png(path: Path) -> U8:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def write_manifest(guard: PathGuard, folder: Path, entries: Sequence[dict[str, object]]) -> None:
    manifest = {"render_identity": render_identity(), "images": list(entries)}
    guard.write_atomic(folder / "manifest.json", json.dumps(manifest, indent=2).encode("utf-8"))


def compare(reference: U8, current: U8) -> tuple[float, float]:
    """Mean and 99th-percentile CIEDE2000 between two sRGB images of the same size."""
    if reference.shape != current.shape:
        raise ValueError(f"size changed: {reference.shape} → {current.shape}")

    def lab(pixels: U8) -> npt.NDArray[np.float64]:
        linear = color.srgb_decode(pixels.astype(np.float64) / 255)
        return color.xyz_to_cielab(color.apply_matrix(linear, color.XYZ_FROM_SRGB)).astype(np.float64)

    delta = color.delta_e_2000(lab(reference), lab(current))
    return float(delta.mean()), float(np.percentile(delta, 99))
