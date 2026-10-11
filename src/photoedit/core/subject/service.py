"""A photo's subject (P6b.6): the box set by hand, or detection on the photo's default look, cached in the
catalog per detection identity.

Detection never depends on the edit: it runs on the photo as shot (default look, no geometry) at the 2048 px
working size previews use, so the result is the same whatever the photo's edit, and a re-edit never redoes it.
The identity names everything that decides the result (models, OpenCV, the render engine, the chooser), so a
change to any of them recomputes it, and an export of the same photo always frames the same subject.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np

from photoedit.core.cache import LINEAR_LONG_EDGE, resize_linear
from photoedit.core.catalog import CatalogPhoto
from photoedit.core.decode import decode_linear, is_raw
from photoedit.core.edits import source_defaults
from photoedit.core.errors import NotFoundError
from photoedit.core.geometry import check_geometry, oriented_ratio, parse_ratio, subject_in_frame, turned_size
from photoedit.core.library import Library
from photoedit.core.metadata import AfMode
from photoedit.core.render.pipeline import render
from photoedit.core.render.stages import quantize
from photoedit.core.renderer import profile_of
from photoedit.core.subject.choose import CHOOSER_VERSION, choose
from photoedit.core.subject.cues import (
    CUE_SIZE,
    RGB8,
    FaceFinder,
    relative_sharpness,
    salient_regions,
    sharp_regions,
)
from photoedit.core.subject.detector import ObjectDetector
from photoedit.core.subject.model_files import (
    FACE_MODEL,
    MODEL_FILES,
    OBJECT_MODEL,
    detector_identity,
    verified_model_path,
)
from photoedit.core.subject.suggest import suggest
from photoedit.models.crop import CropSuggestion, CropSuggestionRequest
from photoedit.models.subject import (
    SubjectBox,
    SubjectCandidate,
    SubjectInfo,
    SubjectSource,
)

# Finds candidates on the detection input; given with the identity of whatever decides its boxes.
type Finder = Callable[[RGB8], list[SubjectCandidate]]

NO_OBJECT_MODEL = (
    "No object detector model, so cars, animals and people were not looked for (only faces, sharpness, "
    "saliency and the focus point). Run `photoedit models fetch`."
)
NO_FACE_MODEL = "No face model, so faces were not looked for. Run `photoedit models fetch`."


class Subjects:
    def __init__(
        self,
        library: Library,
        cache_dir: Path,
        *,
        objects: tuple[Finder, str] | None = None,
        faces: tuple[Finder, str] | None = None,
    ) -> None:
        """``objects`` and ``faces`` replace the pinned models (tests); otherwise those are loaded from
        ``cache_dir`` when present."""
        self._library = library
        self._cache_dir = cache_dir
        self._lock = threading.Lock()
        self._photo_locks: dict[str, threading.Lock] = {}
        self._objects: Finder | None = None
        self._faces: Finder | None = None
        self._model_ids: dict[str, str] = {}
        if objects is not None:
            self._objects, self._model_ids[OBJECT_MODEL] = objects
        if faces is not None:
            self._faces, self._model_ids[FACE_MODEL] = faces

    def identity(self) -> str:
        """Everything that decides a detection; cached results from another identity are recomputed."""
        self._load_models()
        objects = self._model_ids.get(OBJECT_MODEL, "no-objects")
        faces = self._model_ids.get(FACE_MODEL, "no-faces")
        return f"subject{CHOOSER_VERSION}|{objects}|{faces}|{self._library.renderer.identity}"

    def subject(self, photo: CatalogPhoto, *, detect: bool = True) -> SubjectInfo:
        """The photo's subject: the manual box if one is set, else the detected one (detected now if needed
        and ``detect``; else ``none`` with a note until it is)."""
        manual = self._library.edits.subject(photo.id)
        found = self.detected(photo) if detect and manual is None else self.cached(photo)
        if manual is not None:
            known = found or SubjectInfo(source=SubjectSource.NONE)
            return SubjectInfo(
                source=SubjectSource.MANUAL,
                box=manual,
                candidates=known.candidates,
                detector=known.detector,
                notes=known.notes,
            )
        return found or SubjectInfo(source=SubjectSource.NONE, notes=["Not detected yet."])

    def set_manual(self, photo: CatalogPhoto, box: SubjectBox | None) -> SubjectInfo:
        """Set the subject by hand (upright coordinates), or clear it with None to use the detected one."""
        self._library.edits.set_subject(photo, box)
        return self.subject(photo, detect=box is None)

    def suggest_crop(self, photo: CatalogPhoto, request: CropSuggestionRequest) -> CropSuggestion:
        """A crop of ``request.aspect`` framing the photo's subject, in the frame of ``request.geometry`` (the
        crop tool's draft: its flips, turn and angle are kept). Nothing is saved."""
        geometry = request.geometry
        check_geometry(geometry, photo.width, photo.height)
        frame_w, frame_h = turned_size(photo.width, photo.height, geometry.rotate)
        ratio = oriented_ratio(parse_ratio(request.aspect), request.orientation, frame_w, frame_h)
        aspect = request.aspect
        if (ratio > 1) != (parse_ratio(aspect) > 1):
            width, height = aspect.split(":")
            aspect = f"{height}:{width}"
        info = self.subject(photo)
        framed = (
            subject_in_frame(info.box, geometry, photo.width, photo.height) if info.box is not None else None
        )
        warnings = []
        if info.box is None:
            warnings.append("no subject found: centered")
        elif framed is None:
            warnings.append("the subject is outside the straightened photo: centered")
        result = suggest(
            framed,
            ratio=ratio,
            angle=geometry.angle,
            width=frame_w,
            height=frame_h,
            placement=request.placement,
            zoom=request.zoom,
        )
        if result.cut_off is not None:
            warnings.append(f"the subject is cut off: it is {result.cut_off} than a {aspect} crop allows")
        if result.zoom < request.zoom - 1e-6 and framed is not None and result.cut_off is None:
            warnings.append(f"zoom stopped at {result.zoom:.2f}×, where the subject fills the crop")
        return CropSuggestion(
            crop=result.crop,
            aspect=aspect,
            placement=request.placement,
            zoom=round(result.zoom, 4),
            source=info.source if framed is not None else SubjectSource.NONE,
            kind=info.kind if framed is not None else None,
            subject=framed,
            warnings=warnings,
        )

    def cached(self, photo: CatalogPhoto) -> SubjectInfo | None:
        return self._library.catalog.subject(photo.id, self.identity())

    def detected(self, photo: CatalogPhoto) -> SubjectInfo:
        """The detected subject, from the catalog or found now (once per photo at a time)."""
        with self._lock:
            photo_lock = self._photo_locks.setdefault(photo.id, threading.Lock())
        with photo_lock:
            identity = self.identity()
            stored = self._library.catalog.subject(photo.id, identity)
            if stored is not None:
                return stored
            found = self.detect(photo)
            self._library.catalog.set_subject(photo.id, identity, found)
            return found

    def detect(self, photo: CatalogPhoto) -> SubjectInfo:
        """Run detection now, without the cache."""
        image = self.detection_input(photo)
        height, width = image.shape[:2]
        scale = CUE_SIZE / max(height, width)
        size = (max(1, round(width * scale)), max(1, round(height * scale)))
        small = np.asarray(cv2.resize(image, size, interpolation=cv2.INTER_AREA), dtype=np.uint8)
        sharpness = relative_sharpness(small)
        candidates = [*sharp_regions(small, sharpness), *salient_regions(small)]
        notes = []
        self._load_models()
        if self._objects is not None:
            candidates.extend(self._objects(image))
        else:
            notes.append(NO_OBJECT_MODEL)
        if self._faces is not None:
            candidates.extend(self._faces(image))
        else:
            notes.append(NO_FACE_MODEL)
        photo = self._library.with_af_point(photo)

        def sharpness_of(box: SubjectBox) -> float | None:
            if sharpness is None:
                return None
            rows, cols = sharpness.shape
            top, left = min(rows - 1, int(box.top * rows)), min(cols - 1, int(box.left * cols))
            bottom, right = max(top + 1, round(box.bottom * rows)), max(left + 1, round(box.right * cols))
            return float(sharpness[top:bottom, left:right].mean())

        return choose(
            candidates,
            af_point=photo.af_point,
            af_mode=photo.af_mode or AfMode.NONE,
            sharpness=sharpness_of,
            aspect=width / height,
            detector=self.identity(),
            notes=notes,
        )

    def detection_input(self, photo: CatalogPhoto) -> RGB8:
        """The photo's default look (no edit, no geometry) at the working size, as 8-bit RGB.

        Uses the in-memory working base when the photo is open; otherwise decodes without caching it, so a
        batch of detections doesn't push the photo being edited out of memory.
        """
        if not photo.path.is_file():
            raise NotFoundError(f"{photo.path.name} is not at {photo.path.parent} any more")
        renderer = self._library.renderer
        base = renderer.linear.peek(photo.id)
        if base is None:
            decoded = decode_linear(photo.path, half_size=is_raw(photo.path))
            anchors = renderer.anchors(photo, decoded)
            base = resize_linear(decoded, LINEAR_LONG_EDGE)
        else:
            anchors = renderer.anchors(photo, base)
        pixels = render(
            base,
            source_defaults(photo.kind),
            profile_of(photo),
            original_width=photo.width,
            long_edge=LINEAR_LONG_EDGE,
            anchors=anchors,
        )
        return np.asarray(quantize(pixels, 8), dtype=np.uint8)

    def _load_models(self) -> None:
        """Load the detectors whose pinned files are present (once each; a model fetched later is picked up
        on the next call)."""
        with self._lock:
            if self._objects is None:
                model = MODEL_FILES[OBJECT_MODEL]
                path = verified_model_path(self._cache_dir, model)
                if path is not None:
                    self._objects = ObjectDetector(path)
                    self._model_ids[OBJECT_MODEL] = detector_identity(model)
            if self._faces is None:
                model = MODEL_FILES[FACE_MODEL]
                path = verified_model_path(self._cache_dir, model)
                if path is not None:
                    self._faces = FaceFinder(path)
                    self._model_ids[FACE_MODEL] = detector_identity(model)
