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
cache_app = typer.Typer(help="Manage the thumbnail/preview cache.", no_args_is_help=True)
app.add_typer(cache_app, name="cache")
profile_app = typer.Typer(help="Camera profiles (the default look of unedited photos).", no_args_is_help=True)
app.add_typer(profile_app, name="profile")
golden_app = typer.Typer(
    help="Golden reference renders of your sample photos (kept local).", no_args_is_help=True
)
app.add_typer(golden_app, name="golden")

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
def benchmark(
    folder: Annotated[
        Path | None, typer.Argument(help="Folder with RAW files (default: sample_photos_dir).")
    ] = None,
    count: Annotated[int, typer.Option(min=1, help="Photos per run (the same ones for every run).")] = 12,
    workers: Annotated[str, typer.Option(help="Comma-separated worker counts to try.")] = "1,2,4,6,8",
    config: ConfigOption = None,
) -> None:
    """Time full-resolution decode + render per worker count (the Phase 2 go/no-go).

    Only the report is written (to output/benchmark/); nothing is written near the photos.
    """
    from photoedit.core.benchmark import format_report, run_benchmark
    from photoedit.core.scan import ScanError, SourceKind, scan_folder
    from photoedit.safety import guard_from_settings

    settings = load_settings(config)
    source = folder or settings.sample_photos_dir
    if source is None:
        message = "give a FOLDER or set sample_photos_dir in config.local.toml"
        raise typer.BadParameter(message, param_hint="FOLDER")
    try:
        worker_counts = [int(part) for part in workers.split(",") if part.strip()]
    except ValueError:
        raise typer.BadParameter(f"not a list of numbers: {workers!r}", param_hint="--workers") from None
    if not worker_counts or min(worker_counts) < 1:
        raise typer.BadParameter("worker counts must be 1 or more", param_hint="--workers")
    try:
        raws = [p.path for p in scan_folder(source.resolve()).photos if p.kind is SourceKind.RAW][:count]
    except ScanError as exc:
        raise typer.BadParameter(str(exc), param_hint="FOLDER") from None
    if not raws:
        raise typer.BadParameter(f"no RAW files in {source}", param_hint="FOLDER")

    guard = guard_from_settings(settings)
    guard.protect(source)
    report = run_benchmark(source, raws, worker_counts, progress=typer.echo)
    text = format_report(report)
    path = settings.output_dir / "benchmark" / f"report-{report.started_at:%Y%m%d-%H%M%S}.md"
    guard.write_atomic(path, text.encode("utf-8"))
    typer.echo("")
    typer.echo(text)
    typer.echo(f"Report written to {path}")


@app.command("import")
def import_(
    folder: Annotated[Path, typer.Argument(help="Photo folder to import (read-only).")],
    subfolders: Annotated[bool, typer.Option("--subfolders", help="Include photos in subfolders.")] = False,
    config: ConfigOption = None,
) -> None:
    """Import a folder into the catalog: hashes, EXIF and thumbnails. The photos are only read."""
    from photoedit.core.errors import InvalidRequestError
    from photoedit.models import JobStatus
    from photoedit.services import Services

    services = Services(load_settings(config))
    try:
        job = services.library.import_folder(folder.expanduser().absolute(), include_subfolders=subfolders)
        typer.echo(f"{job.title}...")
        done = services.jobs.wait(job.id)
    except InvalidRequestError as exc:
        raise typer.BadParameter(str(exc), param_hint="FOLDER") from None
    finally:
        services.close()
    for item in done.items:
        if item.status is JobStatus.FAILED:
            typer.echo(f"  failed: {item.filename}: {item.message}", err=True)
    typer.echo(done.summary or done.status.value)
    if done.status is JobStatus.FAILED:
        raise typer.Exit(1)


@cache_app.command("clear")
def cache_clear(config: ConfigOption = None) -> None:
    """Delete all cached thumbnails and previews (they are rebuilt on demand)."""
    from photoedit.core.cache import ImageCache
    from photoedit.core.renderer import Renderer
    from photoedit.safety import guard_from_settings

    settings = load_settings(config)
    guard = guard_from_settings(settings)
    removed = ImageCache(settings.cache_dir, guard).clear() + Renderer(settings.cache_dir, guard).clear()
    typer.echo(f"Removed {removed} cached file{'s' if removed != 1 else ''} from {settings.cache_dir}")


@profile_app.command("fit")
def profile_fit(
    folder: Annotated[Path, typer.Argument(help="Folder with RAW files and their camera JPEGs (read-only).")],
    profile_id: Annotated[
        str | None, typer.Option("--id", help="Profile id (default: from the camera).")
    ] = None,
    workers: Annotated[int, typer.Option(min=1, help="Processes for decoding.")] = 8,
    config: ConfigOption = None,
) -> None:
    """Fit a camera profile from RAW + camera JPEG pairs. Writes output/profiles/<id>.json and a report."""
    from photoedit.core.decode import read_raw_info
    from photoedit.core.metadata import read_metadata_from_bytes
    from photoedit.core.profile_fit import fit_and_evaluate, format_report
    from photoedit.core.render.profile import GENERIC
    from photoedit.core.scan import ScanError, SourceKind, scan_folder
    from photoedit.safety import guard_from_settings

    settings = load_settings(config)
    try:
        scanned = scan_folder(folder.expanduser().absolute())
    except ScanError as exc:
        raise typer.BadParameter(str(exc), param_hint="FOLDER") from None
    pairs = [(p.path, p.sidecar_jpeg) for p in scanned.photos if p.kind is SourceKind.RAW and p.sidecar_jpeg]
    if len(pairs) < 8:
        raise typer.BadParameter(f"need at least 8 RAW + JPEG pairs, found {len(pairs)}", param_hint="FOLDER")
    embedded = read_raw_info(pairs[0][0]).embedded_jpeg
    meta = read_metadata_from_bytes(embedded) if embedded else None
    camera = meta.camera if meta and meta.camera else "Unknown camera"
    make, _, model = camera.partition(" ")
    film = meta.film_simulation if meta else None
    name = f"{camera} · {film}" if film else camera
    slug = profile_id or "-".join(part for part in (camera, film) if part).lower().replace(" ", "-").replace(
        ".", ""
    )
    template = GENERIC.model_copy(
        update={
            "id": slug,
            "name": name,
            "make": make or None,
            "model": model or None,
            "film_simulation": film,
        }
    )
    typer.echo(f"Fitting '{name}' from {len(pairs)} pairs...")
    report = fit_and_evaluate(pairs, template, workers=workers, progress=typer.echo)
    guard = guard_from_settings(settings)
    guard.protect(scanned.folder)
    out_dir = settings.output_dir / "profiles"
    json_path = guard.write_atomic(
        out_dir / f"{slug}.json", report.profile.model_dump_json(indent=2).encode()
    )
    text = format_report(report)
    guard.write_atomic(out_dir / f"{slug}.md", text.encode("utf-8"))
    typer.echo(text)
    typer.echo(f"Profile written to {json_path}")


@golden_app.command("update")
def golden_update(
    folder: Annotated[
        Path | None, typer.Argument(help="Folder with sample RAWs (default: sample_photos_dir).")
    ] = None,
    count: Annotated[int, typer.Option(min=1, help="How many photos (spread across the folder).")] = 4,
    config: ConfigOption = None,
) -> None:
    """Render reference images of a few sample RAWs into output/golden/ (git-ignored).

    The golden tests compare later renders against them; run again after an intended engine change.
    """
    from photoedit.core.decode import read_raw_info
    from photoedit.core.golden import GOLDEN_EDITS, render_photo, write_manifest, write_png
    from photoedit.core.metadata import read_metadata_from_bytes
    from photoedit.core.scan import ScanError, SourceKind, scan_folder
    from photoedit.safety import guard_from_settings

    settings = load_settings(config)
    source = folder or settings.sample_photos_dir
    if source is None:
        raise typer.BadParameter("give a FOLDER or set sample_photos_dir", param_hint="FOLDER")
    try:
        raws = [p.path for p in scan_folder(source.resolve()).photos if p.kind is SourceKind.RAW]
    except ScanError as exc:
        raise typer.BadParameter(str(exc), param_hint="FOLDER") from None
    if not raws:
        raise typer.BadParameter(f"no RAW files in {source}", param_hint="FOLDER")
    picked = [raws[round(i * (len(raws) - 1) / max(count - 1, 1))] for i in range(min(count, len(raws)))]
    guard = guard_from_settings(settings)
    guard.protect(source)
    out_dir = settings.output_dir / "golden"
    entries: list[dict[str, object]] = []
    for path in dict.fromkeys(picked):
        info = read_raw_info(path)
        camera = read_metadata_from_bytes(info.embedded_jpeg).camera if info.embedded_jpeg else None
        for edit in GOLDEN_EDITS:
            name = f"{path.stem}-{edit}.png"
            write_png(guard, out_dir / name, render_photo(path, camera, info.width, edit))
            entries.append(
                {"file": name, "source": str(path), "camera": camera, "width": info.width, "edit": edit}
            )
            typer.echo(f"wrote {name}")
    write_manifest(guard, out_dir, entries)
    typer.echo(f"{len(entries)} references in {out_dir}")


@app.command("contact-sheet")
def contact_sheet(
    photo: Annotated[str, typer.Argument(help="An imported photo (file name like DSCF5437, or its id).")],
    group: Annotated[
        str | None, typer.Option(help="Only this group (e.g. tone); default: all groups.")
    ] = None,
    config: ConfigOption = None,
) -> None:
    """Render every parameter at low / neutral / high into output/contact-sheets/ (one image per group)."""
    from photoedit.core.contact_sheet import groups, render_sheet
    from photoedit.core.decode import decode_linear, is_raw
    from photoedit.core.errors import InvalidRequestError
    from photoedit.services import Services

    services = Services(load_settings(config))
    try:
        found = services.catalog.find(photo)
        if found is None:
            raise typer.BadParameter(
                f"no imported photo called '{photo}' (import its folder first)", param_hint="PHOTO"
            )
        names = [group] if group else list(groups((0, 0)))
        base = decode_linear(found.path, half_size=is_raw(found.path))
        anchors = services.library.renderer.anchors(found, base)
        out_dir = services.settings.output_dir / "contact-sheets"
        for name in names:
            try:
                data = render_sheet(found, name, base, anchors)
            except InvalidRequestError as exc:
                raise typer.BadParameter(str(exc), param_hint="--group") from None
            path = services.guard.write_atomic(out_dir / f"{found.path.stem}-{name}.jpg", data)
            typer.echo(f"wrote {path}")
    finally:
        services.close()


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
    # Redirected output on Windows defaults to the ANSI code page, which can't encode "ΔE", "…" or "·".
    for stream in (sys.stdout, sys.stderr):
        if not stream.isatty() and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    app()
