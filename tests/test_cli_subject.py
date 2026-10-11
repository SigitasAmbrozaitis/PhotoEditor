"""``photoedit subject detect|show`` and ``photoedit crop suggest`` (P6b.11) on synthetic photos in tmp_path.

No models are fetched here, so detection uses the cues and says so.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from typer.testing import CliRunner

from helpers import write_jpeg
from photoedit import cli

runner = CliRunner()


@pytest.fixture
def cfg(tmp_path: Path) -> Path:
    photos = tmp_path / "photos"
    write_jpeg(photos / "wide.jpg", (120, 90, 60), size=(400, 200))
    # A bright square on a dark, softly noisy field: the saliency cue finds it.
    pixels = np.random.default_rng(0).normal(30, 3, (200, 400, 3)).clip(0, 255).astype(np.uint8)
    pixels[80:120, 320:360] = 240
    Image.fromarray(pixels).save(photos / "spot.jpg", quality=95)
    config = tmp_path / "c.toml"
    config.write_text(f'project_root = "{(tmp_path / "project").as_posix()}"\n', encoding="utf-8")
    assert runner.invoke(cli.app, ["import", str(photos), "--config", str(config)]).exit_code == 0
    return config


def test_detect_and_show(cfg: Path) -> None:
    detected = runner.invoke(cli.app, ["subject", "detect", "wide", "spot", "--config", str(cfg)])
    assert detected.exit_code == 0, detected.output
    assert "wide.jpg: none" in detected.output and "photoedit models fetch" in detected.output
    shown = runner.invoke(cli.app, ["subject", "show", "spot", "--config", str(cfg)])
    assert shown.exit_code == 0, shown.output
    info = json.loads(shown.output)
    assert info["source"] == "detected" and info["kind"] == "salient"
    assert 0.75 <= (info["box"]["left"] + info["box"]["right"]) / 2 <= 0.9


def test_crop_suggest_and_apply(cfg: Path) -> None:
    suggested = runner.invoke(cli.app, ["crop", "suggest", "spot", "--aspect", "1:1", "--config", str(cfg)])
    assert suggested.exit_code == 0, suggested.output
    suggestion = json.loads(suggested.output)
    assert suggestion["aspect"] == "1:1" and suggestion["crop"]["right"] == pytest.approx(1)

    args = ["crop", "suggest", "spot", "--aspect", "1:1", "--apply", "--config", str(cfg)]
    applied = runner.invoke(cli.app, args)
    assert applied.exit_code == 0, applied.output
    assert "spot.jpg: 200×200 px" in applied.output and '"aspect": "1:1"' in applied.output

    bad = runner.invoke(
        cli.app, ["crop", "suggest", "spot", "--aspect", "1:1", "--placement", "x", "--config", str(cfg)]
    )
    assert bad.exit_code != 0 and "placement" in bad.output
