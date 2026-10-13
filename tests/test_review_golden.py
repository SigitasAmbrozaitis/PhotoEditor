"""The pre-export review on the labeled sample photos (P6c.13). Local only: needs the style sample folders and
the fetched models.

Everything runs in a temporary workspace (the photos are only read). The review must never let a wrong
subject through silently: every wrong detection and every photo without a recognized subject is in Check.
The Check share per folder is printed (run with -s) and kept as a test property. A few photos are exported
from a review, and each file must show what its framing preview showed. The photo folders are unchanged.
"""

from __future__ import annotations

import hashlib
import io
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from photoedit.config import load_settings
from photoedit.core.presets import BUILTIN_PRESETS
from photoedit.core.subject.evaluate import PhotoResult, evaluate, load_labels
from photoedit.core.subject.model_files import MODEL_FILES, verified_model_path
from photoedit.core.subject.service import Subjects
from photoedit.models import JobStatus
from photoedit.models.review import ExportReview, ReviewExportScope, ReviewStatus
from photoedit.models.subject import SubjectSource
from photoedit.services import Services

pytestmark = [pytest.mark.golden, pytest.mark.slow]

DATA = Path(__file__).parent / "data"
HASHED = ("2026-08-16/DSCF6019.RAF", "2026-07-26/DSCF5403.RAF", "2026-08-11/DSCF5600.RAF")
TIMEOUT = 900


def _state(folders: dict[str, Path]) -> dict[str, object]:
    files = {
        f"{name}/{p.name}": (p.stat().st_size, p.stat().st_mtime_ns)
        for name, folder in folders.items()
        for p in sorted(folder.iterdir())
        if p.is_file()
    }
    hashes = {
        key: hashlib.sha256((folders[key.split("/")[0]] / key.split("/")[1]).read_bytes()).hexdigest()
        for key in HASHED
        if key.split("/")[0] in folders
    }
    return {"files": files, "hashes": hashes}


def _pixels(data: bytes, size: tuple[int, int]) -> np.ndarray[Any, Any]:
    with Image.open(io.BytesIO(data)) as image:
        return np.asarray(image.convert("RGB").resize(size, Image.Resampling.BOX), dtype=np.float32)


@pytest.fixture(scope="module")
def run(style_sample_dirs: dict[str, Path], tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    labels = load_labels(DATA / "subject-labels.json").photos
    folders = {
        name: style_sample_dirs[name] for name in {p.folder for p in labels} if name in style_sample_dirs
    }
    if len(folders) < 4:
        pytest.skip("the four style sample folders are not all present")
    real_cache = load_settings().cache_dir
    if any(verified_model_path(real_cache, m) is None for m in MODEL_FILES.values()):
        pytest.skip("the detector models are not fetched (photoedit models fetch)")
    before = _state(folders)

    root = tmp_path_factory.mktemp("review-golden")
    settings = load_settings(
        root / "missing.toml", project_root=root, style_sample_dirs=list(folders.values())
    )
    services = Services(settings)
    try:
        # The pinned models from the real cache; detections and everything else go to the temp workspace.
        subjects = Subjects(services.library, real_cache)
        services.subjects = subjects
        services.exporter._subjects = subjects
        services.reviews._subjects = subjects
        for folder in folders.values():
            services.jobs.wait(services.library.import_folder(folder).id)
        photos = [services.catalog.get_by_path(folders[p.folder] / p.file) for p in labels]
        assert all(photos), "a labeled photo is missing from its folder"
        found = [p for p in photos if p is not None]
        results = evaluate(labels, found, subjects.detected)

        instagram = next(p for p in BUILTIN_PRESETS if p.id == "instagram-portrait")
        job = services.reviews.prepare(
            [p.id for p in found], instagram.settings, str(root / "exports"), preset_id=instagram.id
        )
        done = services.jobs.wait(job.id, TIMEOUT)
        assert done.status == JobStatus.DONE and done.review_id is not None, done
        review = services.reviews.get(done.review_id)

        # A small review exported for real: its files against its previews.
        sample = [r.photo.id for r in results if r.hit][:3]
        small_job = services.jobs.wait(
            services.reviews.prepare(
                sample, instagram.settings, str(root / "small"), preset_id=instagram.id
            ).id,
            TIMEOUT,
        )
        assert small_job.review_id is not None
        small = services.reviews.get(small_job.review_id)
        previews = {i.photo_id: services.reviews.preview(small.id, i.photo_id) for i in small.items}
        export = services.jobs.wait(services.reviews.export(small.id, ReviewExportScope.ALL).id, TIMEOUT)
        files = {item.photo_id: Path(item.output_path or "").read_bytes() for item in export.items}
    finally:
        services.close()
    return {
        "results": results,
        "review": review,
        "small": small,
        "previews": previews,
        "files": files,
        "before": before,
        "after": _state(folders),
    }


def test_wrong_or_missing_subjects_are_always_checked(run: dict[str, Any]) -> None:
    review: ExportReview = run["review"]
    items = {i.photo_id: i for i in review.items}
    results: list[PhotoResult] = run["results"]
    unchecked = []
    for r in results:
        item = items[r.photo.id]
        recognized = item.subject in (SubjectSource.DETECTED, SubjectSource.MANUAL)
        wrong = (r.label.subject is not None and not r.hit) or (r.label.subject is None and recognized)
        if (wrong or not recognized) and item.status != ReviewStatus.CHECK:
            unchecked.append(f"{r.label.folder}/{r.label.file} ({item.status}, {item.subject})")
    assert not unchecked, f"exported without a look: {unchecked}"


def test_check_share_per_folder(run: dict[str, Any], record_property: Any) -> None:
    review: ExportReview = run["review"]
    results: list[PhotoResult] = run["results"]
    folder_of = {r.photo.id: r.label.folder for r in results}
    total, checked = Counter[str](), Counter[str]()
    reasons = Counter[str]()
    for item in review.items:
        folder = folder_of[item.photo_id]
        total[folder] += 1
        if item.status == ReviewStatus.CHECK:
            checked[folder] += 1
            reasons.update(r.code.value for r in item.reasons)
    lines = [f"{f}: {checked[f]}/{total[f]} in Check ({checked[f] / total[f]:.0%})" for f in sorted(total)]
    share = sum(checked.values()) / sum(total.values())
    lines.append(
        f"all: {sum(checked.values())}/{sum(total.values())} ({share:.0%}); reasons: {dict(reasons)}"
    )
    print("\n".join(["", "Check share (instagram-portrait):", *lines]))
    record_property("check_share", lines)
    assert review.counts.unusable == 0
    # Strict on purpose, but not everything: the review is useless if it asks about every photo.
    assert share < 0.6


def test_exported_files_show_the_previews(run: dict[str, Any]) -> None:
    small: ExportReview = run["small"]
    assert len(run["files"]) == len(small.items) == 3
    for item in small.items:
        file, preview = run["files"][item.photo_id], run["previews"][item.photo_id]
        with Image.open(io.BytesIO(file)) as exported:
            assert exported.size == (item.width, item.height)
        difference = np.abs(_pixels(file, (108, 135)) - _pixels(preview, (108, 135))).mean()
        assert difference < 6, (
            f"{item.filename}: the file differs from its preview by {difference:.1f} levels"
        )


def test_the_photo_folders_are_unchanged(run: dict[str, Any]) -> None:
    assert run["after"] == run["before"]
