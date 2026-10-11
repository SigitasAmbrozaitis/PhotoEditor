"""Pinned model files for subject detection, fetched once into ``cache/models/`` (P6b.1).

Each file is pinned by URL, size and SHA-256, and the user OKed exactly these files (2026-10-11). A file is
used only when its hash matches, so a corrupted or swapped download can never reach detection. Nothing here
runs on import or during detection: downloading happens only on ``photoedit models fetch``.
"""

from __future__ import annotations

import hashlib
import os
import threading
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import cv2

from photoedit.safety import PathGuard

MODELS_SUBDIR = "models"
_CHUNK = 1 << 20
_TIMEOUT_S = 60

# OpenCV Model Zoo (Apache-2.0), pinned to one commit so the URL always serves the same bytes. YOLOX-S float32
# was chosen over its int8 version (2026-10-11): under OpenCV 5's dnn the int8 file found no vehicle in 12
# rally/drift samples where float32 found them at 3-47 % of the width, and it ran 1.8x slower.
_ZOO = (
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/"
    "0b263e423d012606b83d1f81238d11c177da2b9c/models/object_detection_yolox/"
)


@dataclass(frozen=True)
class ModelFile:
    name: str
    file_name: str
    url: str
    size: int
    sha256: str
    description: str


MODEL_FILES: dict[str, ModelFile] = {
    m.name: m
    for m in (
        ModelFile(
            name="yolox_s",
            file_name="object_detection_yolox_2022nov.onnx",
            url=_ZOO + "object_detection_yolox_2022nov.onnx",
            size=35_858_002,
            sha256="c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063",
            description="YOLOX-S, COCO 80 classes, 640 px input, float32",
        ),
    )
}

# The model detection uses. ``photoedit models fetch`` without names fetches only this one.
DEFAULT_MODEL = "yolox_s"

# Yields the body of a URL in chunks. Tests pass a fake one; there is no network in tests.
Downloader = Callable[[str], Iterator[bytes]]


class ModelFileError(RuntimeError):
    """A model file could not be fetched or failed its hash check."""


class FetchStatus(StrEnum):
    PRESENT = "present"  # already there with the right hash: left alone
    DOWNLOADED = "downloaded"
    REPLACED = "replaced"  # a file with the wrong hash was deleted and downloaded again


def models_dir(cache_dir: Path) -> Path:
    return cache_dir / MODELS_SUBDIR


def model_path(cache_dir: Path, model: ModelFile) -> Path:
    return models_dir(cache_dir) / model.name / model.file_name


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def verified_model_path(cache_dir: Path, model: ModelFile) -> Path | None:
    """The model's file if it is present with the pinned size and hash, else None."""
    path = model_path(cache_dir, model)
    if not path.is_file() or path.stat().st_size != model.size:
        return None
    return path if file_sha256(path) == model.sha256 else None


def detector_identity(model: ModelFile) -> str:
    """Names everything that decides the detector's boxes; cached detections are keyed by it."""
    return f"{model.name}-{model.sha256[:12]}-opencv{cv2.__version__}"


def fetch_model(
    cache_dir: Path, model: ModelFile, guard: PathGuard, downloader: Downloader | None = None
) -> FetchStatus:
    """Make sure ``model`` is in ``cache/models/`` with the pinned hash, downloading it if needed.

    A file already there with the right hash is left alone. One with the wrong hash is deleted first. A
    download that doesn't match the pin is deleted and reported, and nothing is kept.
    """
    target = guard.assert_writable(model_path(cache_dir, model))
    replaced = False
    if target.exists():
        if verified_model_path(cache_dir, model) is not None:
            return FetchStatus.PRESENT
        target.unlink()
        replaced = True
    target.parent.mkdir(parents=True, exist_ok=True)
    part_name = f".{target.name}.{os.getpid()}-{threading.get_ident()}.part"
    temp = guard.assert_writable(target.with_name(part_name))
    digest = hashlib.sha256()
    size = 0
    try:
        with temp.open("wb") as stream:
            for chunk in (downloader or _download)(model.url):
                size += len(chunk)
                if size > model.size:
                    raise ModelFileError(
                        f"{model.file_name}: the download is larger than the pinned {model.size} bytes"
                    )
                digest.update(chunk)
                stream.write(chunk)
        if size != model.size or digest.hexdigest() != model.sha256:
            raise ModelFileError(
                f"{model.file_name}: the download doesn't match the pinned file "
                f"({size} bytes, sha256 {digest.hexdigest()}; expected {model.size} bytes, "
                f"sha256 {model.sha256}). It was deleted."
            )
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
    return FetchStatus.REPLACED if replaced else FetchStatus.DOWNLOADED


def _download(url: str) -> Iterator[bytes]:
    if not url.startswith("https://"):
        raise ModelFileError(f"refusing a non-HTTPS model URL: {url}")
    try:
        with urllib.request.urlopen(url, timeout=_TIMEOUT_S) as response:
            while chunk := response.read(_CHUNK):
                yield chunk
    except OSError as exc:
        raise ModelFileError(f"download failed: {url} ({exc})") from exc
