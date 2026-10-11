"""``photoedit crop ...`` commands (P6a.9) on a synthetic photo in tmp_path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from helpers import write_jpeg
from photoedit import cli

runner = CliRunner()


@pytest.fixture
def cfg(tmp_path: Path) -> Path:
    photos = tmp_path / "photos"
    write_jpeg(photos / "wide.jpg", (120, 90, 60), size=(400, 200))
    config = tmp_path / "c.toml"
    config.write_text(f'project_root = "{(tmp_path / "project").as_posix()}"\n', encoding="utf-8")
    assert runner.invoke(cli.app, ["import", str(photos), "--config", str(config)]).exit_code == 0
    return config


def _geometry(output: str) -> dict[str, object]:
    first, _, rest = output.partition("\n")
    data: dict[str, object] = json.loads(rest)
    data["size"] = first.split(": ")[1]
    return data


def test_show_set_and_reset(cfg: Path) -> None:
    shown = runner.invoke(cli.app, ["crop", "show", "wide", "--config", str(cfg)])
    assert shown.exit_code == 0, shown.output
    assert _geometry(shown.output)["size"] == "400×200 px"

    turned = runner.invoke(
        cli.app, ["crop", "set", "wide", "--rotate", "90", "--aspect", "1:1", "--flip-h", "--config", str(cfg)]
    )
    assert turned.exit_code == 0, turned.output
    geometry = _geometry(turned.output)
    assert geometry["rotate"] == 90 and geometry["aspect"] == "1:1" and geometry["flip_horizontal"] is True
    assert geometry["size"] == "200×200 px"

    straightened = runner.invoke(cli.app, ["crop", "set", "wide", "--angle", "3", "--config", str(cfg)])
    assert straightened.exit_code == 0 and _geometry(straightened.output)["angle"] == 3

    free = runner.invoke(cli.app, ["crop", "set", "wide", "--aspect", "free", "--config", str(cfg)])
    assert _geometry(free.output)["aspect"] is None

    reset = runner.invoke(cli.app, ["crop", "reset", "wide", "--config", str(cfg)])
    assert reset.exit_code == 0 and _geometry(reset.output)["size"] == "400×200 px"


def test_explicit_crop_and_errors(cfg: Path) -> None:
    ok = runner.invoke(cli.app, ["crop", "set", "wide", "--crop", "0.1,0,0.6,1", "--config", str(cfg)])
    assert ok.exit_code == 0 and _geometry(ok.output)["size"] == "200×200 px"
    runner.invoke(cli.app, ["crop", "set", "wide", "--angle", "8", "--config", str(cfg)])
    outside = runner.invoke(cli.app, ["crop", "set", "wide", "--crop", "0,0,1,1", "--config", str(cfg)])
    assert outside.exit_code == 1 and "blank corners" in outside.output
    bad = runner.invoke(cli.app, ["crop", "set", "wide", "--crop", "0,0,1", "--config", str(cfg)])
    assert bad.exit_code == 2 and "LEFT,TOP,RIGHT,BOTTOM" in bad.output
    out_of_range = runner.invoke(cli.app, ["crop", "set", "wide", "--rotate", "45", "--config", str(cfg)])
    assert out_of_range.exit_code == 2 and "rotate" in out_of_range.output
    nothing = runner.invoke(cli.app, ["crop", "set", "wide", "--config", str(cfg)])
    assert nothing.exit_code == 2 and "nothing to change" in nothing.output
    unknown = runner.invoke(cli.app, ["crop", "show", "nope", "--config", str(cfg)])
    assert unknown.exit_code == 2 and "no imported photo" in unknown.output
