"""Prepare a clean, self-contained data set for the Playwright smoke test (run before the server starts).

Everything lives under output/e2e/ (tool-owned, git-ignored): synthetic photos, plus the workspace, cache
and styles folder the e2e server is pointed at via PHOTOEDIT_* variables. Real photos, the real catalog and
the real styles are never touched.
"""

from __future__ import annotations

import io
import json
import shutil
import sys

import numpy as np
from PIL import Image
from PIL.TiffImagePlugin import IFDRational

from photoedit.config import load_settings
from photoedit.safety import PathGuard

# (filename, size, top-left color, bottom-right color, capture time)
PHOTOS = [
    ("E2E_0001.JPG", (1800, 1200), (30, 60, 110), (230, 180, 90), "2026:08:11 06:10:00"),
    ("E2E_0002.JPG", (1800, 1200), (20, 90, 40), (200, 220, 120), "2026:08:11 06:20:00"),
    ("E2E_0003.JPG", (1200, 1800), (120, 40, 60), (250, 200, 210), "2026:08:11 06:30:00"),
    ("E2E_0004.JPG", (1800, 1200), (10, 10, 30), (90, 120, 200), "2026:08:11 06:40:00"),
    ("E2E_0005.JPG", (1800, 1200), (80, 70, 50), (240, 230, 200), "2026:08:11 06:50:00"),
    ("E2E_0006.JPG", (1200, 1800), (40, 40, 40), (220, 220, 220), "2026:08:11 07:00:00"),
    ("E2E_0007.JPG", (1800, 1200), (150, 60, 20), (255, 210, 120), "2026:08:11 07:10:00"),
    ("E2E_0008.JPG", (1800, 1200), (20, 70, 90), (160, 230, 230), "2026:08:11 07:20:00"),
]
SHUTTER = 250  # every photo: f/4, 1/250 s, ISO 400 ...
# ... except a manual series: E2E_0001's scene again, shot 2 stops darker (1/1000) and 1 stop brighter
# (1/125), so "even out" has something to even out.
SERIES = [("E2E_0010.JPG", -2, 1000, "2026:08:11 06:11:00"), ("E2E_0011.JPG", 1, 125, "2026:08:11 06:12:00")]
# A style to apply in the use-loop test (the real styles/ folder is never used by e2e runs).
SEED_STYLE = {
    "id": "e2e-moody",
    "name": "E2E Moody",
    "description": "Darker, desaturated, teal shadows. Seeded by scripts/e2e_setup.py.",
    "best_for": ["forests"],
    "avoid_on": ["portraits"],
    "values": {"tone.contrast": 25, "presence.saturation": -20, "color_grading.shadows.hue": 190},
    "rules": [],
    "created_at": "2026-10-09T12:00:00Z",
    "updated_at": "2026-10-09T12:00:00Z",
}


def gradient(size: tuple[int, int], start: tuple[int, int, int], end: tuple[int, int, int]) -> Image.Image:
    width, height = size
    t = (np.linspace(0, 1, width)[None, :] + np.linspace(0, 1, height)[:, None]) / 2
    rgb = np.array(start) + (np.array(end) - np.array(start)) * t[..., None]
    return Image.fromarray(rgb.astype(np.uint8))


def exposed(image: Image.Image, stops: float) -> Image.Image:
    """The same scene ``stops`` brighter (in linear light, as a camera would record it)."""
    srgb = np.asarray(image, dtype=np.float64) / 255
    linear = np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4) * 2.0**stops
    out = np.where(linear <= 0.0031308, linear * 12.92, 1.055 * np.clip(linear, 0, 1) ** (1 / 2.4) - 0.055)
    return Image.fromarray((np.clip(out, 0, 1) * 255).round().astype(np.uint8))


def jpeg(image: Image.Image, captured: str, shutter: int = SHUTTER) -> bytes:
    exif = Image.Exif()
    exif[0x010F], exif[0x0110] = "FUJIFILM", "X-T3"
    sub = exif.get_ifd(0x8769)
    sub[0x9003] = captured
    sub[0xA434] = "XF35mmF1.4 R"
    sub[0x829D] = IFDRational(4, 1)  # f/4
    sub[0x829A] = IFDRational(1, shutter)
    sub[0x8827] = 400
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=90, exif=exif.tobytes())
    return buf.getvalue()


def main() -> None:
    settings = load_settings()
    root = settings.output_dir / "e2e"
    # Not guard_from_settings: during e2e runs the sample folder *is* output/e2e/photos, which it protects.
    guard = PathGuard(writable_roots=[root])
    if root.exists():
        guard.assert_writable(root)
        shutil.rmtree(root)
    photos = root / "photos"
    for name, size, start, end, captured in PHOTOS:
        guard.write_atomic(photos / name, jpeg(gradient(size, start, end), captured))
    first = gradient(*PHOTOS[0][1:4])
    for name, stops, shutter, captured in SERIES:
        guard.write_atomic(photos / name, jpeg(exposed(first, stops), captured, shutter))
    guard.write_atomic(photos / "E2E_0009.MOV", b"not a photo")  # must be reported as skipped
    seed = root / "styles" / SEED_STYLE["id"] / "style.json"
    guard.write_atomic(seed, json.dumps(SEED_STYLE, indent=2).encode("utf-8"))
    print(f"e2e data ready in {root}", file=sys.stderr)


if __name__ == "__main__":
    main()
