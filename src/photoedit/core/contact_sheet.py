"""Contact sheets: every live parameter of a group at its low / neutral / high value, side by side.

A quick visual check that each slider does what its name says, in the right direction and with a sensible
strength. Rendered with the production pipeline from the photo's unedited state.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw

from photoedit.core.cache import resize_linear
from photoedit.core.catalog import CatalogPhoto
from photoedit.core.decode import LinearImage, decode_linear, is_raw
from photoedit.core.edits import apply_overrides, source_defaults
from photoedit.core.errors import InvalidRequestError
from photoedit.core.render.anchors import ToneAnchors, measure_anchors
from photoedit.core.render.pipeline import render
from photoedit.core.render.stages import quantize
from photoedit.core.renderer import profile_of

TILE = 320
LABEL_HEIGHT = 18
_BANDS = ("red", "orange", "yellow", "green", "aqua", "blue", "purple", "magenta")


@dataclass(frozen=True)
class Row:
    label: str
    values: tuple[dict[str, object], dict[str, object], dict[str, object]]  # low, neutral, high overrides
    captions: tuple[str, str, str]


def _row(name: str, low: float, high: float, neutral: float = 0, unit: str = "") -> Row:
    return Row(
        label=name,
        values=({name: low}, {name: neutral} if neutral else {}, {name: high}),
        captions=(f"{low:+g}{unit}", f"{neutral:g}{unit}", f"{high:+g}{unit}"),
    )


def groups(as_shot: tuple[float, float]) -> dict[str, list[Row]]:
    temperature, tint = as_shot
    wb = [
        Row(
            "white_balance.temperature",
            ({"white_balance.temperature": 3000}, {}, {"white_balance.temperature": 9000}),
            ("3000 K", f"as shot {temperature:.0f} K", "9000 K"),
        ),
        Row(
            "white_balance.tint",
            ({"white_balance.tint": -60}, {}, {"white_balance.tint": 60}),
            ("-60", f"as shot {tint:+.0f}", "+60"),
        ),
    ]
    tone = [_row("tone.exposure", -2, 2, unit=" EV")] + [
        _row(f"tone.{name}", -100, 100) for name in ("contrast", "highlights", "shadows", "whites", "blacks")
    ]
    presence = [_row(f"presence.{name}", -100, 100) for name in ("vibrance", "saturation")]
    curve = [_row(f"tone_curve.{name}", -100, 100) for name in ("highlights", "lights", "darks", "shadows")]
    hsl = [
        _row(f"hsl.{band}.{part}", -100, 100)
        for band in _BANDS
        for part in ("hue", "saturation", "luminance")
    ]
    grading = [
        Row(
            f"color_grading.{wheel}",
            (
                {f"color_grading.{wheel}.hue": 220, f"color_grading.{wheel}.saturation": 60},
                {},
                {
                    f"color_grading.{wheel}.hue": 40,
                    f"color_grading.{wheel}.saturation": 60,
                },
            ),
            ("blue 60", "none", "orange 60"),
        )
        for wheel in ("shadows", "midtones", "highlights", "global")
    ] + [
        _row(f"color_grading.{wheel}.luminance", -100, 100) for wheel in ("shadows", "midtones", "highlights")
    ]
    effects = [_row("effects.vignette.amount", -100, 100)] + [
        Row(
            f"effects.vignette.{name}",
            (
                {"effects.vignette.amount": -80, f"effects.vignette.{name}": low},
                {"effects.vignette.amount": -80},
                {
                    "effects.vignette.amount": -80,
                    f"effects.vignette.{name}": high,
                },
            ),
            (f"{low:g}", "default", f"{high:g}"),
        )
        for name, low, high in (("midpoint", 0, 100), ("roundness", -100, 100), ("feather", 0, 100))
    ]
    detail = [
        Row(
            "detail.sharpening.amount",
            (
                {"detail.sharpening.amount": 0},
                {"detail.sharpening.amount": 40},
                {"detail.sharpening.amount": 150},
            ),
            ("0", "40", "150"),
        ),
        Row(
            "detail.sharpening.radius",
            (
                {"detail.sharpening.amount": 120, "detail.sharpening.radius": 0.5},
                {"detail.sharpening.amount": 120},
                {
                    "detail.sharpening.amount": 120,
                    "detail.sharpening.radius": 3.0,
                },
            ),
            ("0.5", "1.0", "3.0"),
        ),
        Row(
            "detail.sharpening.masking",
            (
                {"detail.sharpening.amount": 120},
                {"detail.sharpening.amount": 120, "detail.sharpening.masking": 50},
                {
                    "detail.sharpening.amount": 120,
                    "detail.sharpening.masking": 100,
                },
            ),
            ("0", "50", "100"),
        ),
    ]
    return {
        "white_balance": wb,
        "tone": tone,
        "presence": presence,
        "tone_curve": curve,
        "hsl": hsl,
        "color_grading": grading,
        "effects": effects,
        "detail": detail,
    }


def render_sheet(
    photo: CatalogPhoto, group: str, base: LinearImage | None = None, anchors: ToneAnchors | None = None
) -> bytes:
    """One JPEG with a row per parameter of ``group`` (low / neutral / high).

    ``anchors`` are the photo's stored tone anchors; without them they are measured on the decoded image.
    """
    full = base or decode_linear(photo.path, half_size=is_raw(photo.path))
    rows = groups(_as_shot(photo, full)).get(group)
    if rows is None:
        raise InvalidRequestError(f"unknown group '{group}'; choose from: {', '.join(groups((0, 0)))}")
    defaults = source_defaults(photo.kind)
    profile = profile_of(photo)
    anchors = anchors or measure_anchors(full, profile)
    # Detail is judged at 1:1 (a center crop of the working image); everything else on the whole frame.
    working = resize_linear(full, 2048 if group == "detail" else TILE * 2)
    tiles: list[list[Image.Image]] = []
    for row in rows:
        rendered = []
        for overrides in row.values:
            params = apply_overrides(defaults, overrides)
            if group == "detail":
                pixels = render(working, params, profile, original_width=photo.width, anchors=anchors)
                height, width = pixels.shape[:2]
                top, left = (height - TILE) // 2, (width - TILE) // 2
                pixels = pixels[max(top, 0) : top + TILE, max(left, 0) : left + TILE]
            else:
                pixels = render(
                    working, params, profile, original_width=photo.width, long_edge=TILE, anchors=anchors
                )
            rendered.append(Image.fromarray(np.asarray(quantize(pixels, 8))))
        tiles.append(rendered)
    return _compose(photo.path.name, group, rows, tiles)


def _compose(name: str, group: str, rows: Sequence[Row], tiles: list[list[Image.Image]]) -> bytes:
    tile_w = max(t.width for row in tiles for t in row)
    tile_h = max(t.height for row in tiles for t in row)
    gap = 6
    width = 3 * (tile_w + gap) + gap
    height = LABEL_HEIGHT + len(rows) * (tile_h + LABEL_HEIGHT + gap) + gap
    sheet = Image.new("RGB", (width, height), (32, 32, 32))
    draw = ImageDraw.Draw(sheet)
    draw.text((gap, 3), f"{name}: {group} (low / neutral / high)", fill=(255, 220, 90))
    y = LABEL_HEIGHT
    for row, images in zip(rows, tiles, strict=True):
        for column, (image, caption) in enumerate(zip(images, row.captions, strict=True)):
            x = gap + column * (tile_w + gap)
            draw.text((x, y + 2), f"{row.label} {caption}" if column == 0 else caption, fill=(220, 220, 220))
            sheet.paste(image, (x, y + LABEL_HEIGHT))
        y += tile_h + LABEL_HEIGHT + gap
    buf = io.BytesIO()
    sheet.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def _as_shot(photo: CatalogPhoto, image: LinearImage) -> tuple[float, float]:
    if photo.as_shot_temperature is not None and photo.as_shot_tint is not None:
        return photo.as_shot_temperature, photo.as_shot_tint
    return image.as_shot
