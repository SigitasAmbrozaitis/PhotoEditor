"""``photoedit style ...`` commands (P4.9) on synthetic photos in tmp_path."""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import pytest
from PIL import Image
from typer.testing import CliRunner

from helpers import write_jpeg
from photoedit import cli

runner = CliRunner()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project with three imported grays (a manual series) and one style. Returns the config file."""
    photos = tmp_path / "photos"
    for name, level, shutter in (("a.jpg", 70, 500), ("b.jpg", 100, 250), ("c.jpg", 140, 125)):
        write_jpeg(photos / name, (level, level, level), exposure=(4.0, Fraction(1, shutter), 400))
    cfg = tmp_path / "c.toml"
    cfg.write_text(f'project_root = "{(tmp_path / "project").as_posix()}"\n', encoding="utf-8")
    assert runner.invoke(cli.app, ["import", str(photos), "--config", str(cfg)]).exit_code == 0
    style = tmp_path / "project" / "styles" / "even"
    style.mkdir(parents=True)
    (style / "style.json").write_text(
        json.dumps(
            {
                "id": "even",
                "name": "Even",
                "values": {"tone.contrast": -10},
                "rules": [{"type": "exposure", "metering": "camera_settings"}],
                "test_photo_ids": [],
                "created_at": "2026-10-09T12:00:00Z",
                "updated_at": "2026-10-09T12:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    return cfg


def run(cfg: Path, *args: str) -> str:
    result = runner.invoke(cli.app, ["style", *args, "--config", str(cfg)])
    assert result.exit_code == 0, result.output
    return result.stdout


def test_list_show_check(project: Path, tmp_path: Path) -> None:
    assert "even" in run(project, "list") and "v1, 0 photos" in run(project, "list")
    shown = json.loads(run(project, "show", "even"))
    assert shown["values"] == {"tone.contrast": -10.0} and shown["look_hash"]
    assert "1 style valid" in run(project, "check")
    broken = tmp_path / "project" / "styles" / "broken"
    broken.mkdir()
    (broken / "style.json").write_text("{}", encoding="utf-8")
    result = runner.invoke(cli.app, ["style", "check", "--config", str(project)])
    assert result.exit_code == 1 and "broken: " in result.stdout


def test_apply_with_even_out_report_and_remove(project: Path) -> None:
    out = run(project, "apply", "even", "--even-out")
    assert "Apply Even to 3 photos (evened out)" in out and "evened out as a group of 3" in out
    assert "3 photos" in run(project, "list")
    report = run(project, "report", "even", "a", "b", "c")
    assert "a.jpg" in report and "camera EV" in report and "spread" in report
    data = json.loads(run(project, "report", "even", "a", "b", "c", "--json"))
    middle = next(s for s in data["spread"] if s["measure"] == "middle")
    assert middle["after_range"] < middle["before_range"]
    assert "Remove the style from 1 photo" in run(project, "remove", "a")
    assert "2 photos" in run(project, "list")


def test_unknown_photo_and_style(project: Path) -> None:
    result = runner.invoke(cli.app, ["style", "apply", "even", "nope", "--config", str(project)])
    assert result.exit_code == 2 and "no imported photo called 'nope'" in result.output
    result = runner.invoke(cli.app, ["style", "show", "nope", "--config", str(project)])
    assert result.exit_code != 0


def test_samples_and_contact_sheets(project: Path, tmp_path: Path) -> None:
    assert "2 samples rendered" in run(project, "samples", "even", "a", "c")
    samples = tmp_path / "project" / "styles" / "even" / "samples"
    assert sorted(p.name for p in samples.iterdir())[:2] == ["01-after.jpg", "01-before.jpg"]
    out = run(project, "contact-sheet", "even", "--count", "3")
    sheet = tmp_path / "project" / "output" / "contact-sheets" / "style-even-v1.jpg"
    assert str(sheet) in out
    with Image.open(sheet) as image:
        assert image.width == 2 * (360 + 6) + 6  # before | after
    result = runner.invoke(
        cli.app, ["style", "contact-sheet", "even", "--test-set", "--config", str(project)]
    )
    assert result.exit_code == 2 and "no test set" in result.output


def test_history_diff_revert_and_versioned_sheet(project: Path, tmp_path: Path) -> None:
    from photoedit.config import load_settings
    from photoedit.models.style import StyleUpdate
    from photoedit.services import Services

    services = Services(load_settings(project))
    try:
        services.styling.update("even", StyleUpdate(expected_version=1, change_note="flat", values={}))
    finally:
        services.close()
    history = run(project, "history", "even")
    assert history.index("v2") < history.index("v1") and "flat" in history
    assert "tone.contrast: -10.0 -> None" in run(project, "diff", "even", "1", "2")
    run(project, "contact-sheet", "even", "--count", "2", "--version", "1")
    sheet = tmp_path / "project" / "output" / "contact-sheets" / "style-even-v1-v2.jpg"
    with Image.open(sheet) as image:
        assert image.width == 3 * (360 + 6) + 6  # before | version 1 | version 2
    assert "even: version 3 = version 1" in run(project, "revert", "even", "1")
    assert "same look" in run(project, "diff", "even", "1", "3")
