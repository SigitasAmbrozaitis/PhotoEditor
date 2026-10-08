from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from photoedit.config import Settings, load_settings


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Tests must not pick up PHOTOEDIT_* variables from the developer's shell."""
    for key in list(os.environ):
        if key.startswith("PHOTOEDIT_"):
            monkeypatch.delenv(key)
    yield


@pytest.fixture(scope="session")
def sample_photos_dir() -> Path:
    """The real sample photo folder (read-only!) from config.local.toml. Golden tests skip without it."""
    folder = load_settings().sample_photos_dir
    if folder is None or not folder.is_dir():
        pytest.skip("sample_photos_dir is not configured or missing (see config.example.toml)")
    return folder


@pytest.fixture(scope="session")
def sample_raw(sample_photos_dir: Path) -> Path:
    """A portrait-orientation X-T3 RAF when available (it exercises rotation), else the first RAF."""
    preferred = sample_photos_dir / "DSCF5437.RAF"
    if preferred.is_file():
        return preferred
    raws = sorted(sample_photos_dir.glob("*.RAF"))
    if not raws:
        pytest.skip("no .RAF files in sample_photos_dir")
    return raws[0]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings rooted in a temporary project folder, ignoring any real config.local.toml."""
    return load_settings(tmp_path / "missing.toml", project_root=tmp_path)
