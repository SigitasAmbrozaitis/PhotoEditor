"""Style contact sheets: one style across many photos, to judge consistency at a glance.

One row per photo: the unedited photo, then the style (or an older version of it next to the current one).
Each row is labeled with the photo's measurements and what the style's rules did there, so a photo that comes
out too dark or too warm can be traced to a number.
"""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

from photoedit.core.catalog import CatalogPhoto
from photoedit.core.edits import EffectiveEdit
from photoedit.core.library import Library
from photoedit.models import Style

TILE = 360
LABEL_HEIGHT = 30
GAP = 6
_BACKGROUND = (32, 32, 32)
_TITLE = (255, 220, 90)
_TEXT = (220, 220, 220)


def render_style_sheet(
    library: Library, style: Style, photos: list[CatalogPhoto], *, compare: Style | None = None
) -> bytes:
    """A JPEG with a row per photo: before | style (or before | ``compare`` | style)."""
    columns = ["before", *([f"version {compare.version}"] if compare else []), f"version {style.version}"]
    rows: list[tuple[str, list[Image.Image]]] = []
    for photo in photos:
        stored = library.edits.load(photo.id)
        group = stored.group if stored is not None and stored.style_id == style.id else None
        edits = [library.edits.default(photo)]
        if compare is not None:
            edits.append(library.edits.styled_edit(photo, compare, group=group))
        current = library.edits.styled_edit(photo, style, group=group)
        edits.append(current)
        images = [_tile(library, photo, edit) for edit in edits]
        rows.append((_label(library, photo, current), images))
    return _compose(f"{style.name} ({style.id})", columns, rows)


def _tile(library: Library, photo: CatalogPhoto, edit: EffectiveEdit) -> Image.Image:
    data = library.renderer.preview(photo, edit, TILE)
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        return image.convert("RGB")


def _label(library: Library, photo: CatalogPhoto, edit: EffectiveEdit) -> str:
    """Two lines: the photo and its middle brightness before -> after, then what each rule did."""
    stats = library.rule_inputs(photo).stats
    first = photo.path.name
    if stats is not None:
        exposure = edit.adjustments.tone.exposure
        first += f"   middle {stats.middle:+.1f} -> {stats.middle + exposure:+.1f} stops"
    rules = "  |  ".join(result.summary for result in edit.rules) or "no adaptive rules"
    return f"{first}\n{rules}"


def _compose(title: str, columns: list[str], rows: list[tuple[str, list[Image.Image]]]) -> bytes:
    width = len(columns) * (TILE + GAP) + GAP
    height = LABEL_HEIGHT + len(rows) * (TILE + LABEL_HEIGHT + GAP) + GAP
    sheet = Image.new("RGB", (width, height), _BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    draw.text((GAP, 4), f"{title}: {' / '.join(columns)}", fill=_TITLE)
    y = LABEL_HEIGHT
    for label, images in rows:
        draw.text((GAP, y + 2), label, fill=_TEXT)
        for column, image in enumerate(images):
            # Center each image in its square cell (portrait and landscape photos mix).
            x = GAP + column * (TILE + GAP) + (TILE - image.width) // 2
            sheet.paste(image, (x, y + LABEL_HEIGHT + (TILE - image.height) // 2))
        y += TILE + LABEL_HEIGHT + GAP
    buf = io.BytesIO()
    sheet.save(buf, "JPEG", quality=88)
    return buf.getvalue()
