# PhotoEditor

A tool for applying a style to photos without tweaking sliders by hand.

PhotoEditor is a non-destructive RAW photo editor meant to replace Lightroom for **global edits**: color balance, tone,
cropping, zooming and centering. An **AI agent** (Claude Code, through MCP) drives it. You describe the look you want, the AI
applies it, and the tool's code enforces the rules. A small web UI lets you browse, compare and approve.

> **Status: early development (Phase 0, project scaffold).** None of the editing features work yet.
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
| Core / backend | Python 3.12, rawpy (LibRaw), NumPy, OpenCV, Pydantic |
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

Lint and type checks: `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `npm --prefix ui run lint`.

## Project layout

```
PLAN.md            implementation plan and decisions
TODO.md            step-by-step checklist per phase
CLAUDE.md          rules for AI agents working on this repo
src/photoedit/     Python package: CLI, config, safety (write guard), API, core, MCP server
ui/                web UI (React + TypeScript + Vite)
tests/             Python tests
scripts/           dev helpers (dev.cmd starts backend + UI dev server)
styles/            saved styles: style.json + README + sample images (from Phase 4)
export-presets/    export settings presets (from Phase 5)
workspace/         local catalog, edits (git-ignored)
cache/             previews and thumbnails (git-ignored)
output/            development test exports (git-ignored)
```

Photos and real exports live **outside** this folder. Photo folders are only ever read.

## License

[MIT](LICENSE) © 2026 Sigitas Ambrozaitis
