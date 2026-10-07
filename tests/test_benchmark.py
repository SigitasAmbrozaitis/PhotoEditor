from __future__ import annotations

import io
from concurrent.futures import Executor, ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from typer.testing import CliRunner

from photoedit import cli
from photoedit.core import benchmark
from photoedit.core.benchmark import BenchmarkReport, BenchmarkRun, basic_render, format_report, run_benchmark


def _report(*runs: BenchmarkRun) -> BenchmarkReport:
    return BenchmarkReport(
        folder=Path("C:/photos"),
        started_at=datetime(2026, 10, 7, 12, 0, tzinfo=UTC),
        machine="test machine",
        render_identity="dec1-libraw0.22.1-pillow12",
        runs=list(runs),
    )


def test_run_math() -> None:
    run = BenchmarkRun(workers=4, photos=20, seconds=30.0, peak_ram_bytes=3 * 2**30)
    assert run.seconds_per_photo == 1.5
    assert run.minutes_per_100 == 2.5


def test_best_run_and_go_verdict() -> None:
    slow = BenchmarkRun(workers=1, photos=10, seconds=130.0, peak_ram_bytes=1)  # 21.7 min / 100
    fast = BenchmarkRun(workers=6, photos=10, seconds=24.0, peak_ram_bytes=1)  # 4.0 min / 100
    report = _report(slow, fast)
    assert report.best is fast
    assert report.go
    assert not _report(slow).go


def test_go_limit_is_inclusive() -> None:
    exactly = BenchmarkRun(workers=2, photos=100, seconds=300.0, peak_ram_bytes=1)
    assert exactly.minutes_per_100 == 5.0
    assert _report(exactly).go


def test_format_report_table_and_verdict() -> None:
    text = format_report(
        _report(
            BenchmarkRun(workers=1, photos=12, seconds=156.0, peak_ram_bytes=2 * 2**30),
            BenchmarkRun(workers=8, photos=12, seconds=24.0, peak_ram_bytes=9 * 2**30),
        )
    )
    assert "| 1 | 12 | 156.0 | 13.00 | 21.67 | 2.0 GiB |" in text
    assert "| 8 | 12 | 24.0 | 2.00 | 3.33 | 9.0 GiB |" in text
    assert "**GO**: best is 8 workers at 3.33 min per 100 photos (limit 5 min)." in text
    assert "dec1-libraw0.22.1" in text


def test_format_report_no_go() -> None:
    text = format_report(_report(BenchmarkRun(workers=1, photos=1, seconds=10.0, peak_ram_bytes=0)))
    assert "**NO-GO**: best is 1 worker at 16.67 min" in text


def _threads(workers: int) -> Executor:
    return ThreadPoolExecutor(max_workers=workers)


def test_run_benchmark_runs_every_photo_once_per_worker_count(tmp_path: Path) -> None:
    seen: list[str] = []

    def task(path: Path) -> int:
        seen.append(path.name)
        return 1

    paths = [tmp_path / f"{i}.RAF" for i in range(3)]
    messages: list[str] = []
    report = run_benchmark(
        tmp_path, paths, [1, 2], task=task, executor_factory=_threads, progress=messages.append
    )
    assert [r.workers for r in report.runs] == [1, 2]
    assert all(r.photos == 3 for r in report.runs)
    assert sorted(seen) == sorted([p.name for p in paths] * 2)
    assert all(r.peak_ram_bytes > 0 for r in report.runs)
    assert report.render_identity.startswith("dec")
    assert any("2 workers" in m for m in messages)


def test_run_benchmark_needs_photos(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no photos"):
        run_benchmark(tmp_path, [], [1])


def test_basic_render_shape_range_and_determinism() -> None:
    ramp = np.linspace(0, 65535, 4 * 6 * 3).reshape(4, 6, 3).astype(np.uint16)
    out = basic_render(ramp)
    assert out.shape == ramp.shape and out.dtype == np.uint8
    assert out.min() == 0 and out.max() <= 255
    assert np.array_equal(out, basic_render(ramp))
    gray = np.full((2, 2, 3), 32768, dtype=np.uint16)
    pixel = basic_render(gray)[0, 0]
    assert pixel[0] == pixel[1] == pixel[2]  # saturation leaves neutral gray neutral


def test_process_photo_handles_jpeg_originals(tmp_path: Path) -> None:
    path = tmp_path / "a.jpg"
    buf = io.BytesIO()
    Image.new("RGB", (32, 24), (100, 150, 200)).save(buf, "JPEG")
    path.write_bytes(buf.getvalue())
    assert benchmark.process_photo(path) > 0


def test_cli_rejects_bad_input(tmp_path: Path) -> None:
    runner = CliRunner()
    cfg = tmp_path / "c.toml"
    cfg.write_text(f'project_root = "{tmp_path.as_posix()}"\n', encoding="utf-8")
    result = runner.invoke(cli.app, ["benchmark", str(tmp_path), "--config", str(cfg)])
    assert result.exit_code != 0 and "no RAW files" in result.output
    result = runner.invoke(cli.app, ["benchmark", str(tmp_path), "--workers", "a,b", "--config", str(cfg)])
    assert result.exit_code != 0 and "not a list of numbers" in result.output
    result = runner.invoke(cli.app, ["benchmark", "--config", str(cfg)])
    assert result.exit_code != 0 and "sample_photos_dir" in result.output


@pytest.mark.golden
@pytest.mark.slow
def test_cli_benchmark_on_real_rafs(sample_photos_dir: Path, tmp_path: Path) -> None:
    cfg = tmp_path / "c.toml"
    cfg.write_text(f'project_root = "{tmp_path.as_posix()}"\n', encoding="utf-8")
    before = sorted((p.name, p.stat().st_mtime_ns) for p in sample_photos_dir.iterdir())
    result = CliRunner().invoke(
        cli.app,
        ["benchmark", str(sample_photos_dir), "--count", "2", "--workers", "1,2", "--config", str(cfg)],
    )
    assert result.exit_code == 0, result.output
    reports = list((tmp_path / "output" / "benchmark").glob("report-*.md"))
    assert len(reports) == 1
    assert "| 2 | 2 |" in reports[0].read_text(encoding="utf-8")
    assert sorted((p.name, p.stat().st_mtime_ns) for p in sample_photos_dir.iterdir()) == before
