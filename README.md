# PhotoEditor

A tool for applying a style to photos without tweaking sliders by hand.

PhotoEditor is a non-destructive RAW photo editor meant to replace Lightroom for **global edits**: color balance, tone,
cropping, zooming and centering. An **AI agent** (Claude Code, through MCP) drives it. You describe the look you want, the AI
applies it, and the tool's code enforces the rules. A small web UI lets you browse, compare and approve.

> **Status: early development (Phase 3, edit engine).** Photos render through a deterministic pipeline with live sliders,
> per-photo edits and a camera profile fitted to the X-T3 camera JPEGs (see docs/default-look.md). Styles and export
> are still demo data / simulated (Phases 4–5).
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

Optional: copy `config.example.toml` to `config.local.toml` and set `sample_photos_dir` to a folder of your RAW photos.
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

Tests marked `golden` read the real photos in `sample_photos_dir` (read-only) and are skipped without it. Add
`-m "not slow"` for a quick run, or `-m golden` to run only the real-photo tests. The real-photo golden-image
test compares against `output/golden/` (run `photoedit golden update` once); the synthetic golden images in
`tests/golden/` are committed. After an intended change to the render engine, regenerate both
(`uv run python scripts/update_golden.py` and `photoedit golden update`).

End-to-end smoke test in a real browser (uses your installed Google Chrome with a temporary profile; build the UI
first). It runs on synthetic photos written to `output/e2e/` and never touches your real catalog. Screenshots of
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
docs/              benchmark results, how the default look (camera profile) was fitted
styles/            saved styles: style.json + README + sample images (from Phase 4)
export-presets/    export settings presets (from Phase 5)
workspace/         local catalog (catalog.sqlite), later edits (git-ignored)
cache/             previews and thumbnails (git-ignored)
output/            development test exports (git-ignored)
```

Photos and real exports live **outside** this folder. Photo folders are only ever read.

## License

[MIT](LICENSE) © 2026 Sigitas Ambrozaitis
