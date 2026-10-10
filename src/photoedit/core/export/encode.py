"""Encoding rendered pixels into JPEG, TIFF and PNG files, in memory."""

from __future__ import annotations

from importlib.metadata import version as package_version

from photoedit.core.render.pipeline import render_identity

# Bump when anything changes the bytes of an exported file for the same render (encoders, metadata, ICC).
EXPORT_VERSION = 1


def export_identity() -> str:
    """Everything that decides an exported file's bytes: the render plus the encoders."""
    return (
        f"{render_identity()}-exp{EXPORT_VERSION}"
        f"-tifffile{package_version('tifffile')}-imagecodecs{package_version('imagecodecs')}"
    )
