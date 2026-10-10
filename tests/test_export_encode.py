from __future__ import annotations

from pathlib import Path

import numpy as np
import tifffile

from photoedit.core.export.encode import export_identity
from photoedit.core.render.pipeline import render_identity

_ICC_TAG = 34675


def test_tifffile_writes_16_bit_lzw_with_icc(tmp_path: Path) -> None:
    pixels = (np.arange(4 * 6 * 3, dtype=np.uint16).reshape(4, 6, 3) * 900).astype(np.uint16)
    icc = b"fake-icc-profile"
    path = tmp_path / "out.tif"
    tifffile.imwrite(
        path, pixels, photometric="rgb", compression="lzw", extratags=[(_ICC_TAG, "B", len(icc), icc, True)]
    )
    with tifffile.TiffFile(path) as tif:
        page = tif.pages.first
        assert page.compression == tifffile.COMPRESSION.LZW
        assert page.tags[_ICC_TAG].value == icc
        np.testing.assert_array_equal(page.asarray(), pixels)


def test_export_identity_extends_render_identity() -> None:
    identity = export_identity()
    assert identity.startswith(render_identity())
    assert "tifffile" in identity and "imagecodecs" in identity
