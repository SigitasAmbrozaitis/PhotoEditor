from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from photoedit.config import DEFAULT_PROJECT_ROOT, load_settings


def test_defaults_resolve_under_project_root(tmp_path: Path) -> None:
    s = load_settings(tmp_path / "missing.toml", project_root=tmp_path)
    root = tmp_path.resolve()
    assert s.project_root == root
    assert s.workspace_dir == root / "workspace"
    assert s.styles_dir == root / "styles"
    assert s.presets_dir == root / "export-presets"
    assert s.output_dir == root / "output"
    assert s.cache_dir == root / "cache"
    assert s.ui_dist_dir == root / "ui" / "dist"
    assert s.sample_photos_dir is None
    assert (s.host, s.port) == ("127.0.0.1", 8765)


def test_default_project_root_is_repo_root() -> None:
    assert (DEFAULT_PROJECT_ROOT / "pyproject.toml").is_file()


def test_local_toml_overrides_defaults(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    cfg = tmp_path / "config.local.toml"
    cfg.write_text(
        f'sample_photos_dir = "{photos.as_posix()}"\nport = 9000\noutput_dir = "out"\n', encoding="utf-8"
    )
    s = load_settings(cfg, project_root=tmp_path)
    assert s.sample_photos_dir == photos.resolve()
    assert s.port == 9000
    assert s.output_dir == tmp_path.resolve() / "out"


def test_env_overrides_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "config.local.toml"
    cfg.write_text("port = 9000\n", encoding="utf-8")
    monkeypatch.setenv("PHOTOEDIT_PORT", "9100")
    s = load_settings(cfg, project_root=tmp_path)
    assert s.port == 9100


def test_explicit_override_wins_over_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHOTOEDIT_PORT", "9100")
    s = load_settings(tmp_path / "missing.toml", project_root=tmp_path, port=9200)
    assert s.port == 9200


def test_absolute_paths_are_kept(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere" / "ws"
    s = load_settings(tmp_path / "missing.toml", project_root=tmp_path / "proj", workspace_dir=elsewhere)
    assert s.workspace_dir == elsewhere.resolve()


@pytest.mark.parametrize("port", [0, 70000])
def test_invalid_port_rejected(tmp_path: Path, port: int) -> None:
    with pytest.raises(ValidationError):
        load_settings(tmp_path / "missing.toml", project_root=tmp_path, port=port)


def test_unknown_key_rejected(tmp_path: Path) -> None:
    cfg = tmp_path / "config.local.toml"
    cfg.write_text("no_such_setting = 1\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_settings(cfg, project_root=tmp_path)


def test_writable_dirs_excludes_sample_photos(tmp_path: Path) -> None:
    s = load_settings(tmp_path / "missing.toml", project_root=tmp_path, sample_photos_dir=tmp_path / "photos")
    assert s.sample_photos_dir not in s.writable_dirs
    assert s.workspace_dir in s.writable_dirs


def test_style_sample_dirs_resolve_and_are_protected(tmp_path: Path) -> None:
    from photoedit.safety import WriteNotAllowedError, guard_from_settings

    cfg = tmp_path / "config.local.toml"
    cfg.write_text('style_sample_dirs = ["cats", "C:/rally"]\n', encoding="utf-8")
    s = load_settings(cfg, project_root=tmp_path, sample_photos_dir=tmp_path / "photos")
    assert s.style_sample_dirs == [(tmp_path / "cats").resolve(), Path("C:/rally").resolve()]
    assert s.photo_dirs == ((tmp_path / "photos").resolve(), *s.style_sample_dirs)
    guard = guard_from_settings(s)
    for folder in s.photo_dirs:
        with pytest.raises(WriteNotAllowedError, match="protected"):
            guard.assert_writable(folder / "x.jpg")
    assert load_settings(tmp_path / "missing.toml", project_root=tmp_path).style_sample_dirs == []
