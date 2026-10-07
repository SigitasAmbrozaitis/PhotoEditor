from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from photoedit import __version__, cli

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(cli.app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_version_command_lists_native_libraries() -> None:
    result = runner.invoke(cli.app, ["version"])
    assert result.exit_code == 0, result.output
    assert f"photoedit {__version__}" in result.stdout
    assert "LibRaw 0." in result.stdout
    assert "numpy" in result.stdout


def test_version_is_semver() -> None:
    assert __version__.count(".") == 2


def test_no_args_shows_help() -> None:
    result = runner.invoke(cli.app, [])
    assert "Usage" in result.output


def test_config_show_prints_json(tmp_path: Path) -> None:
    cfg = tmp_path / "c.toml"
    cfg.write_text(f'project_root = "{tmp_path.as_posix()}"\nport = 9001\n', encoding="utf-8")
    result = runner.invoke(cli.app, ["config", "show", "--config", str(cfg)])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["port"] == 9001
    assert Path(data["workspace_dir"]) == tmp_path.resolve() / "workspace"


def test_ui_starts_server_without_browser(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def fake_run(app: object, host: str, port: int, log_level: str) -> None:
        calls.update(app=app, host=host, port=port)

    def fail_open(*args: object, **kwargs: object) -> None:
        raise AssertionError("browser must not open with --no-browser")

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", fake_run)
    monkeypatch.setattr(cli.webbrowser, "open", fail_open)
    cfg = tmp_path / "c.toml"
    cfg.write_text(f'project_root = "{tmp_path.as_posix()}"\n', encoding="utf-8")
    result = runner.invoke(cli.app, ["ui", "--no-browser", "--port", "9123", "--config", str(cfg)])
    assert result.exit_code == 0, result.output
    assert calls["host"] == "127.0.0.1"
    assert calls["port"] == 9123
    assert "http://127.0.0.1:9123/" in result.stdout


def test_openapi_prints_schema() -> None:
    result = runner.invoke(cli.app, ["openapi"])
    assert result.exit_code == 0, result.output
    schema = json.loads(result.stdout)
    assert "/api/health" in schema["paths"]
    assert "/api/jobs" in schema["paths"]


def _config(tmp_path: Path) -> Path:
    cfg = tmp_path / "c.toml"
    cfg.write_text(f'project_root = "{(tmp_path / "project").as_posix()}"\n', encoding="utf-8")
    return cfg


def test_import_command(tmp_path: Path) -> None:
    from helpers import fill_folder

    photos = tmp_path / "photos"
    fill_folder(photos)
    cfg = _config(tmp_path)
    result = runner.invoke(cli.app, ["import", str(photos), "--config", str(cfg)])
    assert result.exit_code == 0, result.output
    assert "3 photos: 3 new; 1 other file skipped" in result.stdout
    assert (tmp_path / "project" / "workspace" / "catalog.sqlite").is_file()
    again = runner.invoke(cli.app, ["import", str(photos), "--config", str(cfg)])
    assert "3 unchanged" in again.stdout

    cleared = runner.invoke(cli.app, ["cache", "clear", "--config", str(cfg)])
    assert cleared.exit_code == 0 and "Removed 3 cached files" in cleared.stdout


def test_import_command_rejects_missing_folder(tmp_path: Path) -> None:
    result = runner.invoke(cli.app, ["import", str(tmp_path / "nope"), "--config", str(_config(tmp_path))])
    assert result.exit_code != 0 and "folder not found" in result.output
