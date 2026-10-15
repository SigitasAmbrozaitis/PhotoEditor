"""``photoedit review ...`` (P6c.8) on synthetic photos in tmp_path. Without detector models nothing is
recognized on one-color photos, so every photo is in Check ("no subject recognized")."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
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
    cfg = tmp_path / "c.toml"
    cfg.write_text(
        f'project_root = "{(tmp_path / "project").as_posix()}"\nexport_workers = 1\n', encoding="utf-8"
    )
    assert runner.invoke(cli.app, ["import", str(photos), "--config", str(cfg)]).exit_code == 0
    return cfg


def invoke(cfg: Path, *args: str) -> Result:
    return runner.invoke(cli.app, [*args, "--config", str(cfg)])


def _prepare(cfg: Path, out: Path) -> str:
    result = invoke(cfg, "review", "prepare", "--preset", "instagram-square", "--dest", str(out))
    assert result.exit_code == 0, result.output
    found = re.search(r"Review ([a-z0-9]{12}): 2 photos", result.stdout)
    assert found, result.stdout
    return found.group(1)


def _hashes(folder: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}


def test_prepare_show_approve_export(project: Path, tmp_path: Path, photos: Path) -> None:
    before = _hashes(photos)
    out = tmp_path / "out"
    review = _prepare(project, out)
    shown = invoke(project, "review", "show", review)
    assert shown.exit_code == 0, shown.output
    assert "0 ready, 2 to check, 0 approved" in shown.stdout
    assert "[   check] a.jpg" in shown.stdout
    assert "- no subject found: centered" in shown.stdout
    assert review in invoke(project, "review", "list").stdout

    approved = invoke(project, "review", "approve", review, "a")
    assert approved.exit_code == 0, approved.output
    assert "[approved] a.jpg" in approved.stdout

    exported = invoke(project, "review", "export", review)
    assert exported.exit_code == 0, exported.output
    assert "1 exported" in exported.stdout and "1 photos left in the review." in exported.stdout
    assert [p.name for p in out.iterdir()] == ["a_ig.jpg"]

    rest = invoke(project, "review", "export", review, "--all")
    assert rest.exit_code == 0, rest.output
    assert "The review is done." in rest.stdout
    assert sorted(p.name for p in out.iterdir()) == ["a_ig.jpg", "b_ig.jpg"]
    assert _hashes(photos) == before
    assert "No open reviews." in invoke(project, "review", "list").stdout


def test_refusals(project: Path, tmp_path: Path, photos: Path) -> None:
    assert invoke(project, "review", "prepare").exit_code == 2  # no --dest
    inside = invoke(project, "review", "prepare", "--dest", str(photos / "x"))
    assert inside.exit_code == 2 and "inside the photo folder" in inside.output
    assert invoke(project, "review", "show", "abcdefabcdef").exit_code == 2
    review = _prepare(project, tmp_path / "out")
    nothing = invoke(project, "review", "export", review)
    assert nothing.exit_code == 2 and "nothing to export" in nothing.output
    assert invoke(project, "review", "approve", review, "missing").exit_code == 2


def test_settings(project: Path) -> None:
    shown = invoke(project, "review", "settings")
    assert shown.exit_code == 0, shown.output
    assert json.loads(shown.stdout)["min_score"] == 0.5
    changed = invoke(project, "review", "settings", "--min-score", "0.4", "--rule", "ambiguous=off")
    assert changed.exit_code == 0, changed.output
    data = json.loads(changed.stdout)
    assert (data["min_score"], data["ambiguous"]) == (0.4, False)
    assert json.loads(invoke(project, "review", "settings").stdout)["min_score"] == 0.4
    assert invoke(project, "review", "settings", "--rule", "strict=on").exit_code == 2
    assert invoke(project, "review", "settings", "--min-score", "2").exit_code == 2
