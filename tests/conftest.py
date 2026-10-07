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


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings rooted in a temporary project folder, ignoring any real config.local.toml."""
    return load_settings(tmp_path / "missing.toml", project_root=tmp_path)
