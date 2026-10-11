"""ICC v2 display profiles for the export color spaces, built in code (no profile files are bundled).

A matrix/curve profile is small: the D50-adapted colorants of the space, its white point and one tone curve
shared by the three channels. The bytes are fixed (including the creation date in the header), so exported
files stay deterministic.
"""

from __future__ import annotations

import functools
import struct

import numpy as np
import numpy.typing as npt

from photoedit.core import color
from photoedit.models.export import ColorSpace

_HEADER_SIZE = 128
_CREATED = (2026, 10, 10, 0, 0, 0)  # fixed, so the bytes never change
_SRGB_CURVE_POINTS = 1024
_COPYRIGHT = "No copyright, use freely"

# (description, linear RGB → XYZ (D65), gamma or None for the sRGB curve)
_SPACES: dict[ColorSpace, tuple[str, npt.NDArray[np.float64], float | None]] = {
    ColorSpace.SRGB: ("sRGB IEC61966-2.1", color.XYZ_FROM_SRGB, None),
    ColorSpace.DISPLAY_P3: ("Display P3", color.XYZ_FROM_DISPLAY_P3, None),
    ColorSpace.ADOBE_RGB: ("Adobe RGB (1998) compatible", color.XYZ_FROM_ADOBE_RGB, color.ADOBE_RGB_GAMMA),
}

_D50_PCS = (0.9642, 1.0, 0.8249)  # the ICC profile connection space white, as the spec writes it


def description(space: ColorSpace) -> str:
    return _SPACES[space][0]


@functools.cache
def icc_profile(space: ColorSpace) -> bytes:
    """The ICC profile bytes for ``space``."""
    name, xyz_from_rgb, gamma = _SPACES[space]
    colorants = color.bradford(color.D65, color.D50) @ xyz_from_rgb
    trc = _curve_gamma(gamma) if gamma is not None else _curve_srgb()
    tags: list[tuple[bytes, bytes]] = [
        (b"desc", _desc(name)),
        (b"cprt", _text(_COPYRIGHT)),
        (b"wtpt", _xyz(color.xy_to_xyz(color.D65))),
        (b"rXYZ", _xyz(colorants[:, 0])),
        (b"gXYZ", _xyz(colorants[:, 1])),
        (b"bXYZ", _xyz(colorants[:, 2])),
        (b"rTRC", trc),
        (b"gTRC", trc),
        (b"bTRC", trc),
    ]
    return _assemble(tags)


def _assemble(tags: list[tuple[bytes, bytes]]) -> bytes:
    table_size = 4 + 12 * len(tags)
    offset = _HEADER_SIZE + table_size
    entries: list[bytes] = []
    data: list[bytes] = []
    placed: dict[bytes, int] = {}  # identical tag data (the three curves) is stored once
    for signature, body in tags:
        if body not in placed:
            placed[body] = offset
            padded = body + b"\0" * (-len(body) % 4)
            data.append(padded)
            offset += len(padded)
        entries.append(struct.pack(">4sII", signature, placed[body], len(body)))
    size = offset
    header = struct.pack(
        ">I4sI4s4s4s6H4s4sI4s4s8sI12s4s16s28s",
        size,
        b"\0\0\0\0",  # preferred CMM: none
        0x02100000,  # version 2.1
        b"mntr",
        b"RGB ",
        b"XYZ ",
        *_CREATED,
        b"acsp",
        b"\0\0\0\0",  # platform: none
        0,  # flags
        b"\0\0\0\0",  # device manufacturer
        b"\0\0\0\0",  # device model
        b"\0" * 8,  # device attributes
        0,  # rendering intent: perceptual
        b"".join(struct.pack(">i", _s15f16(v)) for v in _D50_PCS),
        b"\0\0\0\0",  # creator
        b"\0" * 16,  # profile id (v4 only)
        b"\0" * 28,
    )
    assert len(header) == _HEADER_SIZE
    return header + struct.pack(">I", len(tags)) + b"".join(entries) + b"".join(data)


def _s15f16(value: float) -> int:
    return round(value * 65536)


def _xyz(values: npt.ArrayLike) -> bytes:
    x, y, z = (float(v) for v in np.asarray(values, dtype=np.float64))
    return b"XYZ \0\0\0\0" + struct.pack(">3i", _s15f16(x), _s15f16(y), _s15f16(z))


def _text(text: str) -> bytes:
    return b"text\0\0\0\0" + text.encode("ascii") + b"\0"


def _desc(text: str) -> bytes:
    ascii_ = text.encode("ascii") + b"\0"
    return (
        b"desc\0\0\0\0"
        + struct.pack(">I", len(ascii_))
        + ascii_
        + struct.pack(">II", 0, 0)  # no Unicode description
        + struct.pack(">HB", 0, 0)  # no ScriptCode description
        + b"\0" * 67
    )


def _curve_gamma(gamma: float) -> bytes:
    # A one-entry curve is a pure gamma in u8Fixed8 (Adobe RGB's 563/256 is exact).
    return b"curv\0\0\0\0" + struct.pack(">IH", 1, round(gamma * 256))


def _curve_srgb() -> bytes:
    encoded = np.linspace(0, 1, _SRGB_CURVE_POINTS)
    linear = np.rint(color.srgb_decode(encoded) * 65535).astype(">u2")
    return b"curv\0\0\0\0" + struct.pack(">I", _SRGB_CURVE_POINTS) + linear.tobytes()
