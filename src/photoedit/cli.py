"""Command-line interface: ``photoedit ...``."""

from __future__ import annotations

import json
import threading
import webbrowser
from pathlib import Path
from typing import Annotated

import typer

from photoedit import __version__
from photoedit.config import load_settings

app = typer.Typer(
    name="photoedit", help="Agent-driven, non-destructive RAW photo editor.", no_args_is_help=True
)
config_app = typer.Typer(help="Inspect configuration.", no_args_is_help=True)
app.add_typer(config_app, name="config")

ConfigOption = Annotated[
    Path | None,
    typer.Option("--config", help="Settings file (default: config.local.toml in the project root)."),
]


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def _root(
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_version_callback, is_eager=True, help="Print the version and exit."
        ),
    ] = False,
) -> None:
    """PhotoEditor command-line interface."""


@config_app.command("show")
def config_show(config: ConfigOption = None) -> None:
    """Print the effective settings as JSON."""
    settings = load_settings(config)
    typer.echo(json.dumps(settings.model_dump(mode="json"), indent=2))


@app.command()
def ui(
    config: ConfigOption = None,
    no_browser: Annotated[bool, typer.Option("--no-browser", help="Don't open the browser.")] = False,
    port: Annotated[int | None, typer.Option(help="Override the configured port.")] = None,
) -> None:
    """Start the local web UI and API server."""
    import uvicorn

    from photoedit.api import create_app

    overrides: dict[str, object] = {"port": port} if port is not None else {}
    settings = load_settings(config, **overrides)
    url = f"http://{settings.host}:{settings.port}/"
    typer.echo(f"PhotoEditor {__version__} running at {url}  (Ctrl+C to stop)")
    if not no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, log_level="info")


def main() -> None:
    app()
