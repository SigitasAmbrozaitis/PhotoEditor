"""Placeholder images for the mock backend (Phase 1 only).

Images are synthetic scenes drawn with Pillow: no real photos are read. They are generated in memory and
cached, so the mock never writes to disk.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from functools import lru_cache

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class Scene:
    sky_top: RGB
    sky_bottom: RGB
    ground_top: RGB
    ground_bottom: RGB
    horizon: float  # 0..1 from the top
    sun: RGB
    sun_xy: tuple[float, float]  # normalized center


SCENES: tuple[Scene, ...] = (
    Scene(
        (40, 70, 140), (240, 150, 90), (60, 50, 45), (25, 20, 20), 0.62, (255, 210, 120), (0.7, 0.55)
    ),  # sunset
    Scene(
        (120, 170, 210), (200, 225, 235), (50, 90, 50), (25, 50, 30), 0.45, (250, 250, 230), (0.2, 0.2)
    ),  # forest
    Scene(
        (90, 150, 210), (190, 220, 240), (30, 90, 140), (10, 40, 80), 0.5, (255, 255, 240), (0.5, 0.25)
    ),  # sea
    Scene(
        (30, 30, 50), (90, 80, 110), (40, 40, 45), (15, 15, 20), 0.7, (255, 200, 90), (0.3, 0.6)
    ),  # city night
    Scene((200, 190, 180), (160, 150, 140), (120, 100, 90), (80, 65, 60), 0.8, (230, 180, 160), (0.5, 0.45)),
    Scene((140, 180, 200), (230, 230, 220), (150, 130, 90), (100, 80, 50), 0.55, (255, 245, 220), (0.8, 0.3)),
)


@dataclass(frozen=True)
class Look:
    """Rough imitation of a style for placeholder 'after' images."""

    tint: RGB = (128, 128, 128)
    tint_strength: float = 0.0
    saturation: float = 1.0
    contrast: float = 1.0
    brightness: float = 1.0


NEUTRAL_LOOK = Look(saturation=1.08, contrast=1.08)
FLAT_LOOK = Look(saturation=0.75, contrast=0.8, brightness=0.95)  # "before": unedited RAW look


def _gradient(top: RGB, bottom: RGB, width: int, height: int) -> Image.Image:
    column = Image.new("RGB", (1, 256))
    column.putdata(
        [tuple(round(t + (b - t) * i / 255) for t, b in zip(top, bottom, strict=True)) for i in range(256)]
    )
    return column.resize((width, height), Image.Resampling.BICUBIC)


@lru_cache(maxsize=64)
def _base_scene(scene_index: int, width: int, height: int, label: str) -> Image.Image:
    scene = SCENES[scene_index % len(SCENES)]
    horizon = round(height * scene.horizon)
    img = Image.new("RGB", (width, height))
    img.paste(_gradient(scene.sky_top, scene.sky_bottom, width, horizon), (0, 0))
    img.paste(_gradient(scene.ground_top, scene.ground_bottom, width, height - horizon), (0, horizon))

    draw = ImageDraw.Draw(img)
    r = min(width, height) * 0.09
    cx, cy = scene.sun_xy[0] * width, scene.sun_xy[1] * height
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=scene.sun)
    # A simple "subject" silhouette on the ground for crop/centering demos.
    sx = width * (0.35 + 0.3 * ((scene_index * 37) % 10) / 10)
    sw, sh = width * 0.06, height * 0.28
    draw.rounded_rectangle(
        (sx - sw / 2, horizon - sh * 0.6, sx + sw / 2, horizon + sh * 0.4), radius=sw / 2, fill=(20, 20, 24)
    )
    img = img.filter(ImageFilter.GaussianBlur(radius=max(1, min(width, height) / 400)))

    font = ImageFont.load_default(size=max(12, round(min(width, height) / 18)))
    draw = ImageDraw.Draw(img)
    draw.text(
        (width * 0.04, height * 0.9),
        label,
        font=font,
        fill=(255, 255, 255),
        anchor="ls",
        stroke_width=2,
        stroke_fill=(0, 0, 0),
    )
    return img


def _apply_look(img: Image.Image, look: Look) -> Image.Image:
    out = ImageEnhance.Color(img).enhance(look.saturation)
    out = ImageEnhance.Contrast(out).enhance(look.contrast)
    out = ImageEnhance.Brightness(out).enhance(look.brightness)
    if look.tint_strength > 0:
        out = Image.blend(out, Image.new("RGB", out.size, look.tint), look.tint_strength)
    return out


@lru_cache(maxsize=256)
def render_placeholder(scene_index: int, width: int, height: int, label: str, look: Look) -> bytes:
    """JPEG bytes of a synthetic scene of the given size, with ``look`` applied."""
    img = _apply_look(_base_scene(scene_index, width, height, label), look)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def fit_size(width: int, height: int, long_edge: int) -> tuple[int, int]:
    """Scale (width, height) so the longer side equals ``long_edge``."""
    scale = long_edge / max(width, height)
    return max(1, round(width * scale)), max(1, round(height * scale))
