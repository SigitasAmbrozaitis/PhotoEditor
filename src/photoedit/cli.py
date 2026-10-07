"""Command-line interface: ``photoedit ...``."""

from __future__ import annotations

import json
import sys
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


@app.command()
def version() -> None:
    """Print the versions of PhotoEditor and the native libraries that decide how photos render."""
    import platform
    from importlib.metadata import version as package_version

    import numpy
    from rawpy._rawpy import libraw_version  # rawpy re-exports it untyped

    libraw = ".".join(str(part) for part in libraw_version)
    typer.echo(f"photoedit {__version__}")
    typer.echo(f"python    {platform.python_version()}")
    typer.echo(f"rawpy     {package_version('rawpy')} (LibRaw {libraw})")
    typer.echo(f"numpy     {numpy.__version__}")


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


@app.command()
def openapi() -> None:
    """Print the HTTP API's OpenAPI schema (UTF-8 JSON). Used to generate the UI's TypeScript types."""
    from photoedit.api import create_app

    schema = create_app().openapi()
    text = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
    # Write bytes: a redirected Windows console would otherwise use a legacy code page and mangle "×".
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.flush()


def main() -> None:
    app()
