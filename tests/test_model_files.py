"""Pinned model files (P6b.1): fetching, hash checks and the path guard, with a fake downloader."""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from photoedit import cli
from photoedit.core.subject import model_files
from photoedit.core.subject.model_files import (
    MODEL_FILES,
    FetchStatus,
    ModelFile,
    ModelFileError,
    detector_identity,
    fetch_model,
    model_path,
    verified_model_path,
)
from photoedit.safety import PathGuard, WriteNotAllowedError

BODY = b"fake onnx model " * 1000


def _model(body: bytes = BODY) -> ModelFile:
    return ModelFile(
        name="fake",
        file_name="fake.onnx",
        url="https://example.invalid/fake.onnx",
        size=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        description="test model",
    )


def _serve(body: bytes, calls: list[str] | None = None) -> model_files.Downloader:
    def download(url: str) -> Iterator[bytes]:
        if calls is not None:
            calls.append(url)
        for start in range(0, len(body), 4096):
            yield body[start : start + 4096]

    return download


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    return tmp_path / "cache"


@pytest.fixture
def guard(cache: Path) -> PathGuard:
    return PathGuard(writable_roots=[cache])


def test_downloads_once_then_leaves_a_good_file_alone(cache: Path, guard: PathGuard) -> None:
    calls: list[str] = []
    model = _model()
    assert fetch_model(cache, model, guard, _serve(BODY, calls)) is FetchStatus.DOWNLOADED
    path = model_path(cache, model)
    assert path == cache / "models" / "fake" / "fake.onnx"
    assert path.read_bytes() == BODY
    assert verified_model_path(cache, model) == path

    assert fetch_model(cache, model, guard, _serve(BODY, calls)) is FetchStatus.PRESENT
    assert calls == [model.url]
    assert [p.name for p in path.parent.iterdir()] == ["fake.onnx"]  # no temp files left


def test_wrong_existing_file_is_replaced(cache: Path, guard: PathGuard) -> None:
    model = _model()
    path = model_path(cache, model)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x" * len(BODY))  # right size, wrong hash
    assert verified_model_path(cache, model) is None
    assert fetch_model(cache, model, guard, _serve(BODY)) is FetchStatus.REPLACED
    assert path.read_bytes() == BODY


@pytest.mark.parametrize("served", [BODY[:-1] + b"!", BODY[:100], BODY + b"extra"])
def test_a_download_that_misses_the_pin_is_deleted(cache: Path, guard: PathGuard, served: bytes) -> None:
    model = _model()
    with pytest.raises(ModelFileError, match=r"fake\.onnx"):
        fetch_model(cache, model, guard, _serve(served))
    folder = model_path(cache, model).parent
    assert not any(folder.iterdir())
    assert verified_model_path(cache, model) is None


def test_a_wrong_existing_file_is_gone_even_if_the_download_fails(cache: Path, guard: PathGuard) -> None:
    model = _model()
    path = model_path(cache, model)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"corrupt")
    with pytest.raises(ModelFileError):
        fetch_model(cache, model, guard, _serve(b"also wrong"))
    assert not path.exists()


def test_writes_go_through_the_guard(cache: Path, tmp_path: Path) -> None:
    elsewhere = PathGuard(writable_roots=[tmp_path / "other"])
    with pytest.raises(WriteNotAllowedError):
        fetch_model(cache, _model(), elsewhere, _serve(BODY))
    assert not cache.exists()


def test_the_real_downloader_refuses_plain_http() -> None:
    with pytest.raises(ModelFileError, match="non-HTTPS"):
        next(model_files._download("http://example.invalid/model.onnx"))


def test_pins_and_identity() -> None:
    for model in MODEL_FILES.values():
        assert model.url.startswith("https://") and model.url.endswith(model.file_name)
        assert len(model.sha256) == 64 and model.size > 1_000_000
    assert model_files.DEFAULT_MODEL in MODEL_FILES
    identity = detector_identity(MODEL_FILES["yolox_s"])
    assert identity.startswith("yolox_s-c5c2d13e59ae-opencv")
    other = dataclasses.replace(MODEL_FILES["yolox_s"], sha256="0" * 64)
    assert detector_identity(other) != identity


# ---- CLI


@pytest.fixture
def fake_zoo(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Pins the CLI's models to two fake files served by a fake downloader."""
    calls: list[str] = []
    bodies = {"a": b"model a" * 500, "b": b"model b" * 700}
    fakes = {
        name: dataclasses.replace(_model(body), name=name, file_name=f"{name}.onnx", url=f"https://x/{name}")
        for name, body in bodies.items()
    }

    def download(url: str) -> Iterator[bytes]:
        calls.append(url)
        yield bodies[url.rsplit("/", 1)[1]]

    monkeypatch.setattr(model_files, "MODEL_FILES", fakes)
    monkeypatch.setattr(model_files, "DEFAULT_MODEL", "a")
    monkeypatch.setattr(model_files, "_download", download)
    return calls


def _config(tmp_path: Path) -> str:
    config = tmp_path / "c.toml"
    config.write_text(f'project_root = "{(tmp_path / "project").as_posix()}"\n', encoding="utf-8")
    return str(config)


def test_cli_fetch_and_list(tmp_path: Path, fake_zoo: list[str]) -> None:
    runner = CliRunner()
    config = _config(tmp_path)
    listed = runner.invoke(cli.app, ["models", "list", "--config", config])
    assert listed.exit_code == 0, listed.output
    assert "a (default): test model" in listed.output and "not fetched" in listed.output

    fetched = runner.invoke(cli.app, ["models", "fetch", "--config", config])
    assert fetched.exit_code == 0, fetched.output
    assert "downloaded" in fetched.output and fake_zoo == ["https://x/a"]
    assert (tmp_path / "project" / "cache" / "models" / "a" / "a.onnx").is_file()

    again = runner.invoke(cli.app, ["models", "fetch", "--all", "--config", config])
    assert again.exit_code == 0, again.output
    assert "present" in again.output and fake_zoo == ["https://x/a", "https://x/b"]
    listed = runner.invoke(cli.app, ["models", "list", "--config", config])
    assert "not fetched" not in listed.output


def test_cli_unknown_model_and_failure(
    tmp_path: Path, fake_zoo: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = CliRunner()
    config = _config(tmp_path)
    unknown = runner.invoke(cli.app, ["models", "fetch", "nope", "--config", config])
    assert unknown.exit_code != 0 and "unknown model nope" in unknown.output

    monkeypatch.setattr(model_files, "_download", _serve(b"tampered"))
    failed = runner.invoke(cli.app, ["models", "fetch", "a", "--config", config])
    assert failed.exit_code == 1 and "doesn't match the pinned file" in failed.output
