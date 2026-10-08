from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from helpers import write_jpeg
from photoedit.core.catalog import CatalogPhoto
from photoedit.core.contact_sheet import TILE, groups, render_sheet
from photoedit.core.edits import apply_overrides, source_defaults
from photoedit.core.errors import InvalidRequestError
from photoedit.core.scan import SourceKind


def photo(tmp_path: Path) -> CatalogPhoto:
    path = write_jpeg(tmp_path / "a.jpg", (150, 110, 80), size=(480, 320))
    return CatalogPhoto(
        id="p",
        sha256="a" * 64,
        path=path,
        kind=SourceKind.RASTER,
        file_size=1,
        mtime_ns=1,
        width=480,
        height=320,
    )


def test_every_row_is_a_valid_edit() -> None:
    for rows in groups((5000, 10)).values():
        for row in rows:
            for overrides in row.values:
                apply_overrides(source_defaults(SourceKind.RAW), overrides)  # raises on a bad name or value


def test_sheet_layout_and_direction(tmp_path: Path) -> None:
    data = render_sheet(photo(tmp_path), "tone")
    sheet = np.asarray(Image.open(io.BytesIO(data)).convert("L"), dtype=np.float32)
    rows = len(groups((0, 0))["tone"])
    assert sheet.shape[1] > 3 * TILE
    # First row is exposure: the -2 EV tile is darker than the +2 EV tile.
    tile_h = (sheet.shape[0] - 18) // rows
    low, high = sheet[40 : tile_h - 10, 10 : TILE - 10], sheet[40 : tile_h - 10, 2 * TILE + 30 : 3 * TILE]
    assert float(low.mean()) + 30 < float(high.mean())


def test_unknown_group(tmp_path: Path) -> None:
    with pytest.raises(InvalidRequestError, match="unknown group 'colour'"):
        render_sheet(photo(tmp_path), "colour")
