# PhotoEditor

A tool for applying a style to photos without tweaking sliders by hand.

PhotoEditor is a non-destructive RAW photo editor meant to replace Lightroom for **global edits**: color balance, tone,
cropping, zooming and centering. An **AI agent** (Claude Code, through MCP) drives it. You describe the look you want, the AI
applies it, and the tool's code enforces the rules. A small web UI lets you browse, compare and approve.

> **Status: early development.** Nothing below works yet. See [PLAN.md](PLAN.md) for the full plan and phases.

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

_Setup instructions will be added in Phase 0 (project scaffold)._

## Project layout (planned)

```
PLAN.md            implementation plan and decisions
src/photoedit/     Python core, CLI, API, MCP server
ui/                web UI (React + TS)
tests/             unit, golden-image and safety tests
styles/            saved styles (style.json + README + sample images)
export-presets/    export settings presets
workspace/         local catalog, edits and preview cache (git-ignored)
output/            development test exports (git-ignored)
```

Photos and real exports live **outside** this folder. Photo folders are only ever read.

## License

[MIT](LICENSE) © 2026 Sigitas Ambrozaitis
