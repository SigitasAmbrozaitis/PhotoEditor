"""Classical subject cues (P6b.4): what is sharp, what stands out, and human faces.

Both work on an upright RGB image of about ``CUE_SIZE`` px and return candidate boxes normalized to it, so
they fit any size of the same photo. They are weak hints next to the object detector: they find *something*
(a panned car is the only sharp thing; a lone bright subject stands out) but can't say what it is.
Everything is plain array math, so the same image always gives the same boxes.
"""

from __future__ import annotations

import threading
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt

from photoedit.models.subject import SubjectBox, SubjectCandidate, SubjectKind

type RGB8 = npt.NDArray[np.uint8]
type Gray = npt.NDArray[np.float32]

CUE_SIZE = 1024
# Below this standard deviation (of 0..1 luminance) an image is flat: nothing can stand out.
_FLAT = 1e-3
# Regions smaller than this share of the image are noise, not subjects.
_MIN_AREA = 0.002
_MAX_CANDIDATES = 5

# Sharpness: a region is sharp when its local Laplacian energy is this many robust standard deviations (in log
# energy) above the photo's median, and at least _SHARP_MIN_RATIO times the median. Relative to the photo's
# own spread, so an all-sharp photo has no outstanding region and a panned car on a blurred background does;
# the ratio keeps the small wobbles of an evenly sharp photo from counting.
_SHARP_Z = 2.0
_SHARP_MIN_RATIO = 8.0
_SHARP_SIGMA = 0.012  # smoothing of the energy map, fraction of the long edge
_SHARP_CLOSE = 0.02  # gaps closed between sharp bits of one subject, fraction of the long edge

# Spectral residual saliency (Hou & Zhang, CVPR 2007): computed at this width, thresholded at this multiple
# of the mean saliency, as in the paper.
_SALIENCY_WIDTH = 64
_SALIENCY_THRESHOLD = 3.0


# Faces: YuNet (OpenCV 5 dropped the Haar cascades). It finds faces of about 10-300 px, so it runs on the
# 2048 px detection input, where a spectator's face is still ~30 px.
_FACE_SCORE = 0.6
_FACE_NMS = 0.3


def luminance(image: RGB8) -> Gray:
    """0..1 luminance (Rec. 709 weights on the encoded values: plenty for finding structure)."""
    weights = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    gray: Gray = (image.astype(np.float32) @ weights) / np.float32(255)
    return gray


def relative_sharpness(image: RGB8) -> npt.NDArray[np.float64] | None:
    """Local sharpness relative to the photo: 0 at its median, 1 at the threshold of a sharp region. None for
    a photo without structure (flat, or evenly textured with no spread)."""
    gray = luminance(image)
    if float(gray.std()) < _FLAT:
        return None
    laplacian = cv2.Laplacian(gray, cv2.CV_32F, ksize=3)
    energy = cv2.GaussianBlur(laplacian * laplacian, (0, 0), _SHARP_SIGMA * max(gray.shape))
    log_energy = np.log(energy.astype(np.float64) + 1e-10)
    median = float(np.median(log_energy))
    spread = 1.4826 * float(np.median(np.abs(log_energy - median)))
    if spread < 1e-6:
        return None
    threshold = max(_SHARP_Z * spread, float(np.log(_SHARP_MIN_RATIO)))
    ratio: npt.NDArray[np.float64] = (log_energy - median) / threshold
    return ratio


def sharp_regions(image: RGB8, sharpness: npt.NDArray[np.float64] | None = None) -> list[SubjectCandidate]:
    """Regions much sharper than the rest of the photo, best first. ``sharpness`` is ``relative_sharpness``
    of ``image`` when the caller already has it."""
    ratio = relative_sharpness(image) if sharpness is None else sharpness
    if ratio is None:
        return []
    size = max(3, round(_SHARP_CLOSE * max(ratio.shape)) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    closed = cv2.morphologyEx((ratio > 1).astype(np.uint8), cv2.MORPH_CLOSE, kernel)
    mask = np.asarray(closed, dtype=np.uint8)
    # Score: how far above the median the region is on average (three times the threshold or more = 1).
    strength: npt.NDArray[np.float64] = np.clip(ratio / 3, 0, 1)
    return _regions(mask, strength, "sharp")


def salient_regions(image: RGB8) -> list[SubjectCandidate]:
    """Regions that stand out by spectral-residual saliency, best first."""
    gray = luminance(image)
    if float(gray.std()) < _FLAT:
        return []
    height, width = gray.shape
    small_h = max(1, round(height * _SALIENCY_WIDTH / width))
    small = cv2.resize(gray, (_SALIENCY_WIDTH, small_h), interpolation=cv2.INTER_AREA).astype(np.float64)
    spectrum = np.fft.fft2(small)
    log_amplitude = np.log(np.abs(spectrum) + 1e-9)
    residual = log_amplitude - cv2.blur(log_amplitude, (3, 3), borderType=cv2.BORDER_REPLICATE)
    raw = np.abs(np.fft.ifft2(np.exp(residual + 1j * np.angle(spectrum)))) ** 2
    blurred = cv2.GaussianBlur(raw, (0, 0), 2.5)
    peak = float(blurred.max())
    if peak <= 0:
        return []
    saliency = np.asarray(blurred, dtype=np.float64) / peak
    small_mask = (saliency > _SALIENCY_THRESHOLD * float(saliency.mean())).astype(np.uint8)
    mask = np.asarray(
        cv2.resize(small_mask, (width, height), interpolation=cv2.INTER_NEAREST), dtype=np.uint8
    )
    strength = cv2.resize(saliency, (width, height), interpolation=cv2.INTER_LINEAR)
    return _regions(mask, np.asarray(strength, dtype=np.float64), "saliency")


def _regions(
    mask: npt.NDArray[np.uint8], strength: npt.NDArray[np.float64], label: str
) -> list[SubjectCandidate]:
    """Connected regions of ``mask`` as candidates scored by their mean ``strength``, the strongest (score ×
    area) first."""
    height, width = mask.shape
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    found: list[tuple[float, SubjectCandidate]] = []
    for index in range(1, count):
        left, top, box_w, box_h, area = (int(v) for v in stats[index])
        if area < _MIN_AREA * height * width:
            continue
        score = float(strength[labels == index].mean())
        box = SubjectBox(
            left=left / width, top=top / height, right=(left + box_w) / width, bottom=(top + box_h) / height
        )
        candidate = SubjectCandidate(box=box, kind=SubjectKind.SALIENT, score=round(score, 6), label=label)
        found.append((score * area, candidate))
    # Ties broken by position, so the order never depends on anything but the pixels.
    found.sort(key=lambda item: (-item[0], item[1].box.left, item[1].box.top))
    return [candidate for _, candidate in found[:_MAX_CANDIDATES]]


class FaceFinder:
    """Human faces with YuNet (``cv2.FaceDetectorYN``). Each thread gets its own detector: OpenCV's isn't
    thread-safe."""

    def __init__(self, model: Path) -> None:
        self._model = model
        self._local = threading.local()

    def __call__(self, image: RGB8) -> list[SubjectCandidate]:
        height, width = image.shape[:2]
        detector = self._detector()
        detector.setInputSize((width, height))
        _, faces = detector.detect(np.ascontiguousarray(image[:, :, ::-1]))
        if faces is None:
            return []
        found = []
        for face in faces:
            x, y, w, h = (float(v) for v in face[:4])
            left, top = max(0.0, x / width), max(0.0, y / height)
            right, bottom = min(1.0, (x + w) / width), min(1.0, (y + h) / height)
            if right - left < 2 / width or bottom - top < 2 / height:
                continue
            box = SubjectBox(left=left, top=top, right=right, bottom=bottom)
            score = round(float(face[14]), 6)
            found.append(SubjectCandidate(box=box, kind=SubjectKind.FACE, score=score, label="face"))
        found.sort(key=lambda c: (-c.score, c.box.left, c.box.top))
        return found

    def _detector(self) -> cv2.FaceDetectorYN:
        detector: cv2.FaceDetectorYN | None = getattr(self._local, "detector", None)
        if detector is None:
            # Creating it logs that OpenCV 5's engine ignores compute targets: true, and only noise here.
            previous = cv2.utils.logging.getLogLevel()
            cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
            try:
                detector = cv2.FaceDetectorYN.create(str(self._model), "", (320, 320), _FACE_SCORE, _FACE_NMS)
            finally:
                cv2.utils.logging.setLogLevel(previous)
            self._local.detector = detector
        return detector
