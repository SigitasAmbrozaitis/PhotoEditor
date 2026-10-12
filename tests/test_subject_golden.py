"""Subject detection on the labeled sample photos (P6b.16). Local only: needs the style sample folders and the
fetched models.

Detection runs fresh in a temporary workspace (the photos are only read) and must match the stored results
exactly (tests/data/subject-golden.json, from ``photoedit subject eval --results``). The Instagram crops of
those detections must keep the labeled subjects, and the photo folders must be unchanged afterwards.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from photoedit.config import load_settings
from photoedit.core.export.geometry import export_geometry
from photoedit.core.presets import BUILTIN_PRESETS
from photoedit.core.subject.evaluate import evaluate, judge, load_labels, results_json
from photoedit.core.subject.model_files import MODEL_FILES, verified_model_path
from photoedit.core.subject.service import Subjects
from photoedit.models.adjustments import CropRect
from photoedit.services import Services

pytestmark = [pytest.mark.golden, pytest.mark.slow]

DATA = Path(__file__).parent / "data"
# Hashed before and after (the RAWs are ~50 MB each, so a few; the rest are checked by size and date).
HASHED = ("2026-08-16/DSCF6019.RAF", "2026-07-26/DSCF5403.RAF", "2026-08-11/DSCF5600.RAF")


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


@pytest.fixture(scope="module")
def run(style_sample_dirs: dict[str, Path], tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
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

    root = tmp_path_factory.mktemp("subject-golden")
    settings = load_settings(
        root / "missing.toml", project_root=root, style_sample_dirs=list(folders.values())
    )
    services = Services(settings)
    try:
        for folder in folders.values():
            services.jobs.wait(services.library.import_folder(folder).id)
        photos = [services.catalog.get_by_path(folders[p.folder] / p.file) for p in labels]
        assert all(photos), "a labeled photo is missing from its folder"
        subjects = Subjects(
            services.library, real_cache
        )  # the models; detection results go to the temp catalog
        results = evaluate(labels, [p for p in photos if p is not None], subjects.detected)
        found = results_json(results, subjects.identity())
    finally:
        services.close()
    return {"results": results, "found": found, "before": before, "after": _state(folders)}


def test_detection_matches_the_stored_results(run: dict[str, object]) -> None:
    stored = json.loads((DATA / "subject-golden.json").read_text(encoding="utf-8"))
    found = run["found"]
    assert isinstance(found, dict)
    if found["identity"] != stored["identity"]:
        pytest.skip(
            f"detection changed identity ({found['identity']} vs stored {stored['identity']}): check the "
            "eval report, then regenerate with `photoedit subject eval --results output/subject-golden.json`"
        )
    assert found["photos"] == stored["photos"]


def test_instagram_crops_keep_the_labeled_subjects(run: dict[str, object]) -> None:
    preset = next(p for p in BUILTIN_PRESETS if p.id == "instagram-portrait")
    assert preset.settings.aspect.anchor == "subject"
    results = run["results"]
    assert isinstance(results, list)
    checked = 0
    for r in results:
        label = r.label.subject
        if label is None or not r.hit:
            continue  # known misses are reported by the evaluation, not here
        width, height = r.photo.width, r.photo.height
        geometry = export_geometry(width, height, preset.settings, is_raw=True, subject=r.info.box)
        box = geometry.crop
        crop = CropRect(
            left=box.left / width,
            top=box.top / height,
            right=(box.left + box.width) / width,
            bottom=(box.top + box.height) / height,
        )
        assert judge(label, r.info, crop, crop)[1], (
            f"{r.label.folder}/{r.label.file}: the export cuts the subject"
        )
        checked += 1
    assert checked >= 30


def test_the_photo_folders_are_unchanged(run: dict[str, object]) -> None:
    assert run["after"] == run["before"]
