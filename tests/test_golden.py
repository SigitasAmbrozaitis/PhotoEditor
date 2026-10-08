"""Golden images: renders must not change unless the engine is changed on purpose."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from photoedit.config import load_settings
from photoedit.core.golden import compare, read_png, render_photo, render_synthetic, synthetic_cases

GOLDEN_DIR = Path(__file__).parent / "golden"
CHANGED = "engine output changed; if intended, bump ENGINE_VERSION and run scripts/update_golden.py"


@pytest.mark.parametrize(
    ("stem", "profile", "edit"), synthetic_cases(), ids=[c[0] for c in synthetic_cases()]
)
def test_synthetic_golden_images_are_bit_identical(stem: str, profile: object, edit: str) -> None:
    reference = GOLDEN_DIR / f"{stem}.png"
    assert reference.is_file(), f"missing {reference.name}: run scripts/update_golden.py"
    current = render_synthetic(profile, edit)  # type: ignore[arg-type]
    expected = read_png(reference)
    if not np.array_equal(current, expected):
        mean, p99 = compare(expected, current)
        pytest.fail(f"{stem}: {CHANGED} (ΔE2000 mean {mean:.3f}, p99 {p99:.3f})")


def _local_manifest() -> tuple[Path, dict[str, object]]:
    folder = load_settings().output_dir / "golden"
    manifest = folder / "manifest.json"
    if not manifest.is_file():
        pytest.skip("no local golden references yet: run `photoedit golden update`")
    return folder, json.loads(manifest.read_text(encoding="utf-8"))


@pytest.mark.golden
@pytest.mark.slow
def test_real_photo_renders_match_local_references() -> None:
    folder, manifest = _local_manifest()
    images = manifest["images"]
    assert isinstance(images, list) and images
    for entry in images:
        source = Path(entry["source"])
        if not source.is_file():
            pytest.skip(f"sample photo moved: {source}")
        current = render_photo(source, entry["camera"], entry["width"], entry["edit"])
        mean, p99 = compare(read_png(folder / entry["file"]), current)
        # Small numeric differences (e.g. a numpy/OpenCV upgrade) are fine; a visible change is not.
        assert mean <= 0.5 and p99 <= 2.0, (
            f"{entry['file']}: ΔE2000 mean {mean:.2f}, p99 {p99:.2f}: {CHANGED}"
        )
