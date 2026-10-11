"""``photoedit export`` and ``photoedit preset ...`` (P5.13) on synthetic photos in tmp_path."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image
from typer.testing import CliRunner, Result

from helpers import write_jpeg
from photoedit import cli

runner = CliRunner()


@pytest.fixture
def photos(tmp_path: Path) -> Path:
    folder = tmp_path / "photos"
    write_jpeg(folder / "a.jpg", (200, 100, 50), date="2026:08:11 09:00:00")
    write_jpeg(folder / "b.jpg", (50, 100, 200), (200, 320), date="2026:08:11 10:00:00")
    return folder


@pytest.fixture
def project(tmp_path: Path, photos: Path) -> Path:
    """An imported folder of two photos. Returns the config file."""
    cfg = tmp_path / "c.toml"
    cfg.write_text(
        f'project_root = "{(tmp_path / "project").as_posix()}"\nexport_workers = 1\n'
        'export_copyright = "© {year} Me"\n',
        encoding="utf-8",
    )
    assert runner.invoke(cli.app, ["import", str(photos), "--config", str(cfg)]).exit_code == 0
    return cfg


def invoke(cfg: Path, *args: str) -> Result:
    return runner.invoke(cli.app, [*args, "--config", str(cfg)])


def test_dry_run_prints_the_plan_and_writes_nothing(project: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = invoke(project, "export", "--preset", "instagram-square", "--dest", str(out), "--dry-run")
    assert result.exit_code == 0, result.output
    assert f"2 photos → {out}" in result.stdout
    assert "a.jpg                → a_ig.jpg  1080×1080  (new, full decode, enlarged" in result.stdout
    assert not out.exists()


def test_export_folder_with_overrides(project: Path, photos: Path, tmp_path: Path) -> None:
    originals = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in photos.iterdir()}
    out = tmp_path / "out"
    result = invoke(
        project,
        "export",
        "--folder",
        str(photos),
        "--dest",
        str(out),
        "--set",
        "size.long_edge=100",
        "--set",
        "naming.template={seq:02}_{original}",
        "--set",
        "file.format=png",
    )
    assert result.exit_code == 0, result.output
    assert "[1/2] a.jpg → 01_a.png 100×63" in result.stdout
    assert f"2 exported → {out}" in result.stdout
    assert sorted(p.name for p in out.iterdir()) == ["01_a.png", "02_b.png"]
    with Image.open(out / "02_b.png") as image:
        assert image.size == (63, 100)
    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in photos.iterdir()} == originals


def test_export_named_photos(project: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = invoke(project, "export", "b", "--set", "size.long_edge=50", "--dest", str(out))
    assert result.exit_code == 0, result.output
    assert [p.name for p in out.iterdir()] == ["b_web.jpg"]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--set", "file.nope=1"], "unknown setting 'file.nope'"),
        (["--set", "file.jpeg_quality=500"], "file.jpeg_quality"),
        (["--set", "oops"], "expected group.field=value"),
        (["--preset", "nope"], "export preset 'nope' not found"),
    ],
)
def test_bad_options(project: Path, tmp_path: Path, args: list[str], message: str) -> None:
    result = invoke(project, "export", "a", "--dest", str(tmp_path / "out"), *args)
    assert result.exit_code == 2 and message in result.output


def test_refused_destination_and_unimported_folder(project: Path, photos: Path, tmp_path: Path) -> None:
    result = invoke(project, "export", "a", "--dest", str(photos / "exports"))
    assert result.exit_code == 2 and "inside the photo folder" in result.output
    result = invoke(project, "export", "--folder", str(tmp_path), "--dest", str(tmp_path / "out"))
    assert result.exit_code == 2 and "isn't imported yet" in result.output
    assert not (photos / "exports").exists()


def test_preset_commands(project: Path, tmp_path: Path) -> None:
    listed = invoke(project, "preset", "list")
    assert listed.exit_code == 0 and "instagram-portrait" in listed.stdout and "built-in" in listed.stdout
    shown = json.loads(invoke(project, "preset", "show", "web-full").stdout)
    assert shown["settings"]["size"]["long_edge"] == 2048
    created = invoke(project, "preset", "duplicate", "web-full", "--name", "My web")
    assert created.exit_code == 0 and "created my-web (My web)" in created.stdout
    assert "1 custom preset valid" in invoke(project, "preset", "check").stdout
    (tmp_path / "project" / "export-presets" / "bad.json").write_text("{}", encoding="utf-8")
    check = invoke(project, "preset", "check")
    assert check.exit_code == 1 and "bad:" in check.stdout
    assert invoke(project, "preset", "delete", "my-web").exit_code == 0
    assert invoke(project, "preset", "delete", "web-full").exit_code != 0
