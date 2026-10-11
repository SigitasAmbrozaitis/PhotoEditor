"""Command-line interface: ``photoedit ...``."""

from __future__ import annotations

import json
import sys
import threading
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from photoedit import __version__
from photoedit.config import load_settings

if TYPE_CHECKING:
    from photoedit.core.catalog import CatalogPhoto
    from photoedit.models import Job
    from photoedit.models.export import ExportSettings
    from photoedit.services import Services

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
style_app = typer.Typer(
    help="Styles: list, apply, samples, contact sheets, reports, history.", no_args_is_help=True
)
app.add_typer(style_app, name="style")
preset_app = typer.Typer(help="Export presets: list, show, duplicate, delete, check.", no_args_is_help=True)
app.add_typer(preset_app, name="preset")

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
    export: Annotated[
        str | None,
        typer.Option(help="Time real exports instead: 'full' (original size) or 'instagram' (1080×1350)."),
    ] = None,
    config: ConfigOption = None,
) -> None:
    """Time full-resolution decode + render per worker count (the Phase 2 go/no-go), or real exports.

    Only the report is written (to output/benchmark/); nothing is written near the photos, and exports are
    encoded in memory only.
    """
    from photoedit.core.benchmark import EXPORT_TASKS, format_report, process_photo, run_benchmark
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
    if export is not None and export not in EXPORT_TASKS:
        raise typer.BadParameter(f"choose one of: {', '.join(EXPORT_TASKS)}", param_hint="--export")
    task_name, task = EXPORT_TASKS[export] if export is not None else (None, process_photo)
    report = run_benchmark(source, raws, worker_counts, task=task, task_name=task_name, progress=typer.echo)
    text = format_report(report)
    kind = f"export-{export}-" if export else ""
    path = settings.output_dir / "benchmark" / f"report-{kind}{report.started_at:%Y%m%d-%H%M%S}.md"
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


# ----------------------------------------------------------------- styles

StyleArg = Annotated[str, typer.Argument(help="Style id (its folder name under styles/).")]
PhotosArg = Annotated[
    list[str] | None,
    typer.Argument(help="Imported photos (file names like DSCF5437, or ids). Default: the current folder."),
]


def _open_services(config: Path | None) -> Services:
    from photoedit.services import Services

    return Services(load_settings(config))


def _find_photos(services: Services, names: list[str] | None) -> list[CatalogPhoto]:
    """The named photos, or every photo of the Library's current folder."""
    if not names:
        page = services.library.list_photos(limit=500)
        return [services.library.photo(p.id) for p in page.items]
    found = []
    for name in names:
        photo = services.catalog.find(name)
        if photo is None:
            raise typer.BadParameter(
                f"no imported photo called '{name}' (import its folder first)", param_hint="PHOTO"
            )
        found.append(photo)
    return found


def _run_job(services: Services, job: Job) -> Job:
    from photoedit.models import JobStatus

    typer.echo(f"{job.title}...")
    done = services.jobs.wait(job.id)
    for item in done.items:
        if item.status is JobStatus.FAILED:
            typer.echo(f"  failed: {item.filename}: {item.message}", err=True)
    typer.echo(done.summary or done.status.value)
    if done.status is JobStatus.FAILED:
        raise typer.Exit(1)
    return done


@style_app.command("list")
def style_list(config: ConfigOption = None) -> None:
    """List the styles with their version and how many photos use them."""
    services = _open_services(config)
    try:
        for s in services.styling.summaries():
            status = f"ERROR: {s.error}" if s.error else f"v{s.version}, {s.photo_count} photos"
            typer.echo(f"{s.id:<28} {s.name:<28} {status}")
    finally:
        services.close()


@style_app.command("show")
def style_show(style: StyleArg, config: ConfigOption = None) -> None:
    """Print a style as JSON (with derived fields: look hash, photo count, samples)."""
    services = _open_services(config)
    try:
        typer.echo(services.styling.view(style).model_dump_json(indent=2))
    finally:
        services.close()


@style_app.command("check")
def style_check(config: ConfigOption = None) -> None:
    """Validate every style file. Exits with 1 if any is invalid."""
    services = _open_services(config)
    try:
        listings = services.styles.listings()
    finally:
        services.close()
    for entry in listings:
        typer.echo(f"{entry.id}: {'ok' if entry.style else entry.error}")
    if any(entry.style is None for entry in listings):
        raise typer.Exit(1)
    typer.echo(f"{len(listings)} style{'s' if len(listings) != 1 else ''} valid")


@style_app.command("apply")
def style_apply(
    style: StyleArg,
    photos: PhotosArg = None,
    even_out: Annotated[
        bool, typer.Option("--even-out", help="Even the photos out as a group (the style's exposure rule).")
    ] = False,
    config: ConfigOption = None,
) -> None:
    """Apply a style to photos (writes edit files only; the originals are never touched)."""
    services = _open_services(config)
    try:
        found = _find_photos(services, photos)
        _run_job(services, services.styling.apply([p.id for p in found], style, even_out=even_out))
    finally:
        services.close()


@style_app.command("remove")
def style_remove(photos: PhotosArg = None, config: ConfigOption = None) -> None:
    """Remove the style from photos (their own tweaks are kept)."""
    services = _open_services(config)
    try:
        found = _find_photos(services, photos)
        _run_job(services, services.styling.apply([p.id for p in found], None))
    finally:
        services.close()


@style_app.command("samples")
def style_samples(
    style: StyleArg,
    photos: Annotated[
        list[str], typer.Argument(help="1-12 imported photos to render as before/after pairs.")
    ],
    config: ConfigOption = None,
) -> None:
    """Render the style's sample pairs into styles/<id>/samples/."""
    services = _open_services(config)
    try:
        found = _find_photos(services, photos)
        _run_job(services, services.styling.render_samples(style, [p.id for p in found]))
    finally:
        services.close()


@style_app.command("contact-sheet")
def style_contact_sheet(
    style: StyleArg,
    test_set: Annotated[bool, typer.Option("--test-set", help="Use the style's test set.")] = False,
    count: Annotated[int, typer.Option(min=1, max=60, help="Photos of the current folder.")] = 12,
    version: Annotated[
        int | None, typer.Option(help="Also render this older version, next to the current one.")
    ] = None,
    config: ConfigOption = None,
) -> None:
    """Before/after of one style across many photos into output/contact-sheets/, labeled with what the rules
    did on each photo."""
    from photoedit.core.style_sheet import render_style_sheet

    services = _open_services(config)
    try:
        current = services.styles.get(style)
        if test_set:
            if not current.test_photo_ids:
                raise typer.BadParameter("the style has no test set", param_hint="--test-set")
            found = [services.library.photo(pid) for pid in current.test_photo_ids]
        else:
            found = _find_photos(services, None)[:count]
        if not found:
            raise typer.BadParameter("no photos: open a folder in the Library first, or use --test-set")
        compare = services.styles.version(style, version) if version is not None else None
        data = render_style_sheet(services.library, current, found, compare=compare)
        suffix = f"-v{version}-v{current.version}" if version is not None else f"-v{current.version}"
        out = services.settings.output_dir / "contact-sheets" / f"style-{style}{suffix}.jpg"
        typer.echo(f"wrote {services.guard.write_atomic(out, data)}")
    finally:
        services.close()


@style_app.command("report")
def style_report(
    style: StyleArg,
    photos: Annotated[
        list[str] | None, typer.Argument(help="Photos to report on. Default: the test set, else its photos.")
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print the full report as JSON.")] = False,
    config: ConfigOption = None,
) -> None:
    """How consistent the style makes the photos: each photo's brightness before -> after, and the spread."""
    services = _open_services(config)
    try:
        ids = [p.id for p in _find_photos(services, photos)] if photos else None
        report = services.styling.report(style, ids)
    finally:
        services.close()
    if as_json:
        typer.echo(report.model_dump_json(indent=2))
        return
    for p in report.photos:
        before, after = p.before.middle, p.after.middle
        middle = (
            f"{before:+.2f} -> {after:+.2f}" if before is not None and after is not None else "not measured"
        )
        rules = " | ".join(r.summary for r in p.rules)
        typer.echo(f"{p.filename:<16} middle {middle}  dev {p.deviation:+.2f}  {rules}")
    typer.echo("")
    typer.echo(
        f"{'spread':<12} {'MAD before':>10} {'MAD after':>10} {'range before':>13} {'range after':>12}"
    )
    for s in report.spread:
        mads = f"{s.before_mad:>10.2f} {s.after_mad:>10.2f}"
        typer.echo(f"{s.measure:<12} {mads} {s.before_range:>13.2f} {s.after_range:>12.2f}")


@style_app.command("history")
def style_history(style: StyleArg, config: ConfigOption = None) -> None:
    """The style's saved versions, newest first."""
    services = _open_services(config)
    try:
        for v in services.styles.history(style):
            typer.echo(f"v{v.version:<4} {v.updated_at:%Y-%m-%d %H:%M}  look {v.look_hash}  {v.change_note}")
    finally:
        services.close()


@style_app.command("diff")
def style_diff(
    style: StyleArg,
    a: Annotated[int, typer.Argument(help="Older version.")],
    b: Annotated[int, typer.Argument(help="Newer version.")],
    config: ConfigOption = None,
) -> None:
    """What changed between two versions of a style."""
    services = _open_services(config)
    try:
        diff = services.styles.diff(style, a, b)
    finally:
        services.close()
    for change in diff.values:
        typer.echo(f"{change.name}: {change.before} -> {change.after}")
    for rule in diff.rules:
        typer.echo(f"rule {rule.type}: {rule.before} -> {rule.after}")
    if diff.fields:
        typer.echo(f"also changed: {', '.join(diff.fields)}")
    if diff.same_look:
        typer.echo("same look")


@style_app.command("revert")
def style_revert(
    style: StyleArg,
    version: Annotated[int, typer.Argument(help="The version to bring back (saved as a new version).")],
    config: ConfigOption = None,
) -> None:
    """Bring back an older version of a style; every photo using it follows."""
    services = _open_services(config)
    try:
        current = services.styles.get(style)
        reverted = services.styling.revert(style, version, expected_version=current.version)
        typer.echo(f"{style}: version {reverted.version} = version {version}")
    finally:
        services.close()


# ----------------------------------------------------------------- export


def _with_overrides(settings: ExportSettings, overrides: list[str]) -> ExportSettings:
    """Apply ``--set group.field=value`` overrides (values are JSON when they parse, else text)."""
    from pydantic import ValidationError

    from photoedit.models.export import ExportSettings

    data = settings.model_dump(mode="json")
    for override in overrides:
        name, sep, raw = override.partition("=")
        parts = name.strip().split(".")
        if not sep or not all(parts):
            raise typer.BadParameter(f"expected group.field=value, got {override!r}", param_hint="--set")
        try:
            value = json.loads(raw)
        except ValueError:
            value = raw
        target = data
        for part in parts[:-1]:
            if not isinstance(target.get(part), dict):
                raise typer.BadParameter(f"unknown setting {name!r}", param_hint="--set")
            target = target[part]
        if parts[-1] not in target:
            raise typer.BadParameter(f"unknown setting {name!r}", param_hint="--set")
        target[parts[-1]] = value
    try:
        return ExportSettings.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
        raise typer.BadParameter(problems, param_hint="--set") from None


def _folder_photos(services: Services, folder: Path) -> list[CatalogPhoto]:
    from photoedit.models import PhotoSort, SortOrder

    record = services.catalog.get_folder(folder)
    if record is None:
        hint = f'{folder} isn\'t imported yet; run: photoedit import "{folder}"'
        raise typer.BadParameter(hint, param_hint="--folder")
    items, _ = services.catalog.page(
        record.path,
        recursive=record.include_subfolders,
        style_id=None,
        min_rating=0,
        sort=PhotoSort.DATE,
        order=SortOrder.ASC,
        offset=0,
        limit=100_000,
    )
    return list(items)


@app.command("export")
def export(
    photos: PhotosArg = None,
    preset: Annotated[str, typer.Option(help="Export preset id (see: photoedit preset list).")] = "web-full",
    dest: Annotated[Path | None, typer.Option(help="Destination folder (created if needed).")] = None,
    folder: Annotated[
        Path | None, typer.Option(help="Export every photo of this imported folder instead of PHOTO….")
    ] = None,
    set_: Annotated[
        list[str] | None,
        typer.Option("--set", help="Change a preset setting, e.g. --set file.jpeg_quality=95 (repeatable)."),
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Only print what would be written.")] = False,
    config: ConfigOption = None,
) -> None:
    """Export photos with a preset into a folder. Originals are only read; nothing is written next to them."""
    from photoedit.core.errors import InvalidRequestError, NotFoundError
    from photoedit.models import JobStatus

    if dest is None:
        raise typer.BadParameter("give the destination folder", param_hint="--dest")
    services = _open_services(config)
    try:
        if folder is not None and photos:
            raise typer.BadParameter("give PHOTO… or --folder, not both", param_hint="--folder")
        found = (
            _folder_photos(services, folder.expanduser().absolute())
            if folder is not None
            else _find_photos(services, photos)
        )
        if not found:
            raise typer.BadParameter("no photos to export", param_hint="PHOTO")
        try:
            base = services.presets.get(preset)
        except NotFoundError as exc:
            raise typer.BadParameter(f"{exc} (see: photoedit preset list)", param_hint="--preset") from None
        settings = _with_overrides(base.settings, set_ or [])
        ids = [p.id for p in found]
        destination = str(dest.expanduser().absolute())
        try:
            plan = services.exporter.plan(ids, settings, destination, preset)
        except InvalidRequestError as exc:
            raise typer.BadParameter(str(exc), param_hint="--dest") from None
        typer.echo(f"{len(plan.items)} photo{'s' if len(plan.items) != 1 else ''} → {plan.destination}")
        for item in plan.items:
            notes = ", ".join([item.collision.value, f"{item.decode.value} decode", *item.warnings])
            typer.echo(f"  {item.filename:<20} → {item.output_name}  {item.width}×{item.height}  ({notes})")
        if dry_run:
            return
        job = services.exporter.export(ids, settings, destination, preset)
        typer.echo(f"{job.title}... ({min(services.exporter.workers, len(ids))} workers)")
        _follow(services, job.id)
        done = services.jobs.get(job.id)
        typer.echo(done.summary or done.status.value)
        if done.failed or done.status is JobStatus.FAILED:
            raise typer.Exit(1)
    finally:
        services.close()


def _follow(services: Services, job_id: str) -> None:
    """Print one line per photo as it finishes."""
    from photoedit.models import JobStatus

    shown: set[int] = set()
    finished = False
    while not finished:
        try:
            services.jobs.wait(job_id, timeout=0.3)
            finished = True
        except TimeoutError:
            pass
        job = services.jobs.get(job_id)
        for index, item in enumerate(job.items):
            if index in shown or item.status not in (JobStatus.DONE, JobStatus.FAILED):
                continue
            shown.add(index)
            count = f"[{len(shown)}/{job.total}]"
            if item.status is JobStatus.FAILED:
                typer.echo(f"  {count} failed: {item.filename}: {item.message}", err=True)
                continue
            name = Path(item.output_path).name if item.output_path else ""
            pixels = f" {item.output_width}×{item.output_height}" if item.output_width else ""
            size = f", {item.output_bytes // 1024} KB" if item.output_bytes else ""
            extra = "; ".join([*([item.message] if item.message else []), *item.warnings])
            typer.echo(f"  {count} {item.filename} → {name}{pixels}{size}" + (f" ({extra})" if extra else ""))


PresetArg = Annotated[str, typer.Argument(help="Export preset id.")]


@preset_app.command("list")
def preset_list(config: ConfigOption = None) -> None:
    """List the export presets (built-in ones first)."""
    services = _open_services(config)
    try:
        for p in services.presets.all():
            kind = "built-in" if p.builtin else f"custom v{p.version}"
            typer.echo(f"{p.id:<28} {p.name:<36} {f'ERROR: {p.error}' if p.error else kind}")
    finally:
        services.close()


@preset_app.command("show")
def preset_show(preset: PresetArg, config: ConfigOption = None) -> None:
    """Print a preset as JSON."""
    services = _open_services(config)
    try:
        typer.echo(services.presets.get(preset).model_dump_json(indent=2))
    finally:
        services.close()


@preset_app.command("duplicate")
def preset_duplicate(
    preset: PresetArg,
    name: Annotated[str | None, typer.Option(help="Name of the copy (default: the name + ' copy').")] = None,
    config: ConfigOption = None,
) -> None:
    """Copy a preset into export-presets/ so it can be edited."""
    from photoedit.models.export import PresetDuplicate

    services = _open_services(config)
    try:
        copy = services.presets.duplicate(preset, PresetDuplicate(name=name) if name else None)
        typer.echo(f"created {copy.id} ({copy.name})")
    finally:
        services.close()


@preset_app.command("delete")
def preset_delete(preset: PresetArg, config: ConfigOption = None) -> None:
    """Delete a custom preset (built-in presets can't be deleted)."""
    services = _open_services(config)
    try:
        services.presets.delete(preset)
        typer.echo(f"deleted {preset}")
    finally:
        services.close()


@preset_app.command("check")
def preset_check(config: ConfigOption = None) -> None:
    """Validate every custom preset file. Exits with 1 if any is invalid."""
    services = _open_services(config)
    try:
        custom = [p for p in services.presets.all() if not p.builtin]
    finally:
        services.close()
    for p in custom:
        typer.echo(f"{p.id}: {p.error or 'ok'}")
    if any(p.error for p in custom):
        raise typer.Exit(1)
    typer.echo(f"{len(custom)} custom preset{'s' if len(custom) != 1 else ''} valid")


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
