"""Classical subject cues (P6b.4) on synthetic images."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt
import pytest

from photoedit.core.subject.cues import FaceFinder, salient_regions, sharp_regions
from photoedit.models.subject import SubjectBox, SubjectKind

type Image = npt.NDArray[np.uint8]


def _texture(height: int, width: int, seed: int) -> npt.NDArray[np.float64]:
    return np.random.default_rng(seed).uniform(40, 215, (height, width))


def _rgb(gray: npt.NDArray[np.float64]) -> Image:
    return np.repeat(np.clip(gray, 0, 255).astype(np.uint8)[..., None], 3, axis=2)


def _contains(box: SubjectBox, left: float, top: float, right: float, bottom: float, slack: float) -> bool:
    return (
        box.left <= left + slack
        and box.top <= top + slack
        and box.right >= right - slack
        and box.bottom >= bottom - slack
        and box.left >= left - 3 * slack
        and box.top >= top - 3 * slack
        and box.right <= right + 3 * slack
        and box.bottom <= bottom + 3 * slack
    )


def sharp_square() -> Image:
    """A sharp textured square (x 0.55-0.75, y 0.3-0.6) on the same texture blurred: a panned car."""
    height, width = 600, 900
    sharp = _texture(height, width, 1)
    image = cv2.GaussianBlur(sharp, (0, 0), 6)
    image[180:360, 495:675] = sharp[180:360, 495:675]
    return _rgb(image)


def test_a_sharp_square_on_a_blurred_background_is_found() -> None:
    found = sharp_regions(sharp_square())
    assert found, "nothing found"
    best = found[0]
    assert best.kind is SubjectKind.SALIENT and best.label == "sharp" and 0 < best.score <= 1
    assert _contains(best.box, 0.55, 0.3, 0.75, 0.6, slack=0.03)


def test_an_evenly_sharp_photo_has_no_sharp_region() -> None:
    assert sharp_regions(_rgb(_texture(400, 600, 2))) == []


def test_a_bright_blob_on_noise_is_salient() -> None:
    height, width = 512, 768
    gray = np.random.default_rng(3).normal(90, 12, (height, width))
    cv2.circle(gray, (200, 300), 40, 245, thickness=-1)
    found = salient_regions(_rgb(gray))
    assert found and found[0].label == "saliency"
    cx, cy = found[0].box.center
    assert cx == pytest.approx(200 / width, abs=0.04) and cy == pytest.approx(300 / height, abs=0.04)


@pytest.mark.parametrize("cue", [sharp_regions, salient_regions])
@pytest.mark.parametrize("value", [0, 128, 255])
def test_flat_images_give_nothing(cue: object, value: int) -> None:
    assert callable(cue)
    assert cue(np.full((300, 400, 3), value, np.uint8)) == []


@pytest.mark.parametrize("cue", [sharp_regions, salient_regions])
def test_same_image_same_boxes(cue: object) -> None:
    assert callable(cue)
    image = sharp_square()
    assert cue(image) == cue(image.copy())


# ---- faces (YuNet; needs the model from `photoedit models fetch`)


@pytest.fixture(scope="module")
def faces() -> FaceFinder:
    from photoedit.config import load_settings
    from photoedit.core.subject.model_files import FACE_MODEL, MODEL_FILES, verified_model_path

    path = verified_model_path(load_settings().cache_dir, MODEL_FILES[FACE_MODEL])
    if path is None:
        pytest.skip("the YuNet model is not fetched (photoedit models fetch)")
    return FaceFinder(path)


def test_no_faces_in_flat_or_noisy_images(faces: FaceFinder) -> None:
    assert faces(np.full((480, 640, 3), 128, np.uint8)) == []
    assert faces(_rgb(_texture(480, 640, 4))) == []


@pytest.mark.golden
def test_faces_in_a_drift_crowd(faces: FaceFinder, style_sample_dirs: dict[str, Path]) -> None:
    from PIL import Image, ImageOps

    folder = style_sample_dirs.get("2026-07-26")
    if folder is None or not (folder / "DSCF5413.JPG").is_file():
        pytest.skip("the drift sample folder is missing")
    with Image.open(folder / "DSCF5413.JPG") as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    image.thumbnail((2048, 2048))
    pixels = np.asarray(image)
    found = faces(pixels)
    assert len(found) >= 5 and all(c.kind is SubjectKind.FACE and c.score >= 0.6 for c in found)
    assert all(c.box.top > 0.5 for c in found)  # the crowd fills the lower half
    assert faces(pixels.copy()) == found
