# PhotoEditor

A tool for applying a style to photos without tweaking sliders by hand.

PhotoEditor is a non-destructive RAW photo editor meant to replace Lightroom for **global edits**: color balance, tone,
cropping, zooming and centering. An **AI agent** (Claude Code, through MCP) drives it. You describe the look you want, the AI
applies it, and the tool's code enforces the rules. A small web UI lets you browse, compare and approve.

> **Status: early development (Phase 5, export).** Photos render through a deterministic pipeline with live
> sliders, per-photo edits and a camera profile fitted to the X-T3 camera JPEGs (see docs/default-look.md). Styles
> are real: made by hand from an edited photo, applied to many photos, adapted to each one by rules (see
> docs/styles.md). Export writes real files: presets, sizes and crops, color spaces with ICC profiles, output
> sharpening, metadata and names (see docs/export.md).
> See [PLAN.md](PLAN.md) for the full plan and [TODO.md](TODO.md) for progress.

---

## Planned features

- **Styles**: give the tool sample photos, and the AI builds a reusable style from them. Each style is saved with a
  description and before/after samples.
- **Bulk editing**: apply a style to one photo, a folder or a selection (50–100+ photos at a time).
- **Export**: Lightroom-style export settings (size, aspect, orientation, format, color space, sharpening, metadata,
  naming), with presets such as *Instagram 4:5* or *Print 8×10*.
- **Non-destructive**: originals are never modified. Edits are stored as small JSON files, and exports are written as new files.
- **RAW support**: through LibRaw (Fujifilm RAF, Canon CR2/CR3, Nikon NEF, Sony ARW, DNG, and more).
- **Agent-first**: every operation can be called by an AI through MCP, and it can render previews so the AI can *see* the result.

Out of scope: local or spot edits (healing, cloning, masks) and generative edits.

## Typical workflow

1. Set up the style you want.
2. Import photos.
3. Pick the style.
4. Pick export settings and a destination folder.
5. Apply and export.

## Tech stack

| Part | Technology |
|---|---|
| Core / backend | Python 3.12, rawpy (LibRaw), NumPy, Pillow, SQLite, Pydantic (OpenCV from Phase 3) |
| AI interface | MCP server (used from Claude Code) |
| Web UI | FastAPI + React + TypeScript + Vite |
| CLI | Typer |
| Tests | pytest, hypothesis |

## Requirements

- Windows 11
- Python 3.12
- Node.js 24 LTS
- [uv](https://docs.astral.sh/uv/) (Python package manager)

## Getting started

### Install the tools (once per machine)

```bash
winget install Python.Python.3.12
```
```bash
winget install OpenJS.NodeJS.LTS
```
```bash
winget install astral-sh.uv
```

Open a **new** terminal afterwards so the tools are on `PATH`.

### Set up the project

```bash
git clone https://github.com/SigitasAmbrozaitis/PhotoEditor.git
```
```bash
cd PhotoEditor
```
```bash
uv sync
```
```bash
npm --prefix ui install
```
```bash
npm --prefix ui run build
```

Optional: copy `config.example.toml` to `config.local.toml` and set `sample_photos_dir` to a folder of your RAW photos
(and `style_sample_dirs` to folders of varied photos for developing styles).
`uv run photoedit config show` prints the effective settings.

### Run

```bash
uv run photoedit ui
```

This opens http://127.0.0.1:8765 in the browser (backend plus built UI). Stop it with Ctrl+C.

In the Library, type or paste a folder path (or use **Browse…**) and press **Open**. The folder is imported read-only:
RAW + JPEG pairs become one photo, and opening a folder again only re-reads files that changed. After an import,
a background job renders every thumbnail with the photo's default look.

**Editing.** Double-click a photo (or press Enter) to open it. Every slider in the **Adjust** panel edits the
photo and saves automatically; the preview follows. Double-click a slider to reset it, click its value to type
one, use the ↺ button on a group to reset that group, **Reset all** to start over, and Ctrl+Z / Ctrl+Shift+Z to
undo and redo. Compare with **Before**, **Split**, or **Camera JPEG** (the camera's own JPEG next to a RAW).
Sliders labeled *Phase 6* / *Phase 9* (crop, clarity, noise reduction, …) arrive later. Edits are small JSON
files in `workspace/edits/`; the original photos are never changed.

**Highlights, Shadows, Whites, Blacks** and **Contrast** work on each photo's own tonal range, like Lightroom:
the tool measures a photo's black and white points once (stored in the catalog), places the four bands between
them, and pivots Contrast on the middle of that range, so a dark night shot and a bright beach shot both respond.
See [docs/tone-sliders.md](docs/tone-sliders.md).

**Styles.** A style is a reusable look (`styles/<id>/style.json`): a few parameter values plus **adaptive
rules** that fit it to each photo. Auto exposure meters the photo's middle brightness, its highlights (so a black
cat stays dark), or the exposure you dialed in (shutter, aperture, ISO); white balance stays the camera's, shifted
by an offset. Make one from an edited photo with **Save as style…** in the Adjust panel, apply it with **Apply
style…** (tick **Even out these photos** for a series shot in the same light with changing settings), and change
it on its Styles page: every photo using it follows. Each style keeps a **test set** of hard photos, a
**consistency** report (how far apart the photos come out, before vs. after), its **history** (compare versions
side by side, bring one back) and before/after samples. Your own tweaks on a photo stay on top of its style. See
[docs/styles.md](docs/styles.md) for the format, the rules and how to iterate on a style.

**Export.** **Export…** (Library selection or Photo view) or **Apply style…** with export: pick a preset
(Instagram, print, web, or your own), a destination folder (**Browse…**; photo folders are refused, because
originals are read-only), and check the plan table (file names, pixel sizes, collisions, warnings) before
exporting. The job page lists every file with its size and a **Show in folder** button. On the **Export presets**
page, **Duplicate** a built-in preset to make an editable copy (saved in `export-presets/`). Copyright text goes
into `config.local.toml` (`export_copyright = "© {year} Your Name"`). Exports run in parallel worker processes;
RAWs are decoded at half size when that's enough for the output (Instagram, web), which is much faster. See
[docs/export.md](docs/export.md).

An unedited RAW renders through a **camera profile** fitted to that camera's own JPEGs (FUJIFILM X-T3 · Provia
ships with the tool; other cameras get a neutral generic profile). See [docs/default-look.md](docs/default-look.md).

From the command line:

```bash
uv run photoedit import "C:\Users\you\Pictures\2026\2026-08-11"
```
```bash
uv run photoedit benchmark
```

`photoedit benchmark` times full-resolution decoding of a RAW folder (default: `sample_photos_dir`) with several
worker counts and writes a report to `output/benchmark/`. Results for the X-T3 sample folder are in
[docs/benchmark.md](docs/benchmark.md). `photoedit cache clear` deletes cached thumbnails and previews, and
`photoedit version` shows the library versions that decide how photos render.

```bash
uv run photoedit contact-sheet DSCF5437
```

`photoedit contact-sheet PHOTO [--group tone]` renders every slider of an imported photo at its low / neutral /
high value into `output/contact-sheets/` (one image per group): a quick check that each slider does what it says.
`photoedit profile fit FOLDER` fits a camera profile from RAW + camera JPEG pairs (report and JSON in
`output/profiles/`), and `photoedit golden update` renders local reference images of a few sample photos into
`output/golden/` for the golden-image tests.

Styles from the command line (photos default to the Library's current folder):

```bash
uv run photoedit style list
```
```bash
uv run photoedit style apply test-warm-matte --even-out
```
```bash
uv run photoedit style contact-sheet test-warm-matte --test-set
```

Also `style show | check | remove | samples | report | history | diff | revert` (`--help` on each). The contact
sheet goes to `output/contact-sheets/`, one row per photo labeled with what the rules did there; `--version N`
adds a column with an older version.

Export from the command line (`--dry-run` only prints the plan; `--set` changes one setting of the preset):

```bash
uv run photoedit export --folder "C:\Users\you\Pictures\2026\2026-08-17" --preset web-full --dest "C:\Users\you\Pictures\Exports\web" --dry-run
```
```bash
uv run photoedit export DSCF5437 --preset instagram-portrait --dest output\exports --set file.jpeg_quality=95
```

Presets: `photoedit preset list | show ID | duplicate ID --name "My preset" | delete ID | check`.
`photoedit benchmark --export full|instagram` times real exports per worker count.

For UI development with hot reload (backend plus Vite dev server on http://localhost:5173):

```bash
scripts\dev.cmd
```

### Test

```bash
uv run pytest
```
```bash
npm --prefix ui test
```

Tests marked `golden` read the real photos in `sample_photos_dir` and `style_sample_dirs` (read-only) and are
skipped without them. Add
`-m "not slow"` for a quick run, or `-m golden` to run only the real-photo tests. The real-photo golden-image
test compares against `output/golden/` (run `photoedit golden update` once); the synthetic golden images in
`tests/golden/` are committed. After an intended change to the render engine, regenerate both
(`uv run python scripts/update_golden.py` and `photoedit golden update`).

End-to-end smoke test in a real browser (uses your installed Google Chrome with a temporary profile; build the UI
first). It runs on synthetic photos written to `output/e2e/` (exports go to `output/e2e/exports`) and never touches
your real catalog, styles or presets. Screenshots of
every screen are saved to `output/screenshots/`:

```bash
npm --prefix ui run test:e2e
```

Lint and type checks: `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `npm --prefix ui run lint`.

## Project layout

```
PLAN.md            implementation plan and decisions
TODO.md            step-by-step checklist per phase
CLAUDE.md          rules for AI agents working on this repo
src/photoedit/     Python package: CLI, config, safety (write guard), API, core, MCP server
ui/                web UI (React + TypeScript + Vite)
tests/             Python tests
scripts/           dev helpers (dev.cmd, e2e_setup.py for e2e test photos, update_golden.py)
docs/              benchmark results, the default look (camera profile), tone sliders, styles
styles/            saved styles: style.json + README + history (sample images stay local)
export-presets/    your own export presets (one JSON file each; the built-in ones are in code)
workspace/         local catalog (catalog.sqlite) and per-photo edits (git-ignored)
cache/             previews and thumbnails (git-ignored)
output/            development test exports (git-ignored)
```

Photos and real exports live **outside** this folder. Photo folders are only ever read.

## License

[MIT](LICENSE) © 2026 Sigitas Ambrozaitis
