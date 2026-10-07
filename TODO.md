# PhotoEditor: TODO

Derived from [PLAN.md](PLAN.md) v0.3. This checklist is written for an AI to follow, step by step.

## How to use this list

- Work **top to bottom**, one item at a time. Tick `[x]` only when the item is **done**:
  - the code is written,
  - its tests are written and **the whole test suite is green** (`uv run pytest`, plus `npm test` in `ui/` once it exists),
  - lint and types are clean (`uv run ruff check`, `uv run mypy`),
  - it is committed, with a message that references the item ID (e.g. `P0.3: ...`).
- ⛔ **STOP** = halt and wait for the user. Never continue past a STOP without the user's explicit go-ahead.
- 🧑 **Human test** = steps the user runs by hand at the end of a phase, with the expected result for each step.
- If something is ambiguous or the plan seems wrong, **ask**. Don't guess. Plan changes go into PLAN.md first.
- **Phases 0–1 are detailed.** Later phases are an outline and get detailed at the start of each phase. Writing that detail is the first item in each phase.
- Golden rules: originals are read-only; never write outside `C:\Work\PhotoEditing` (except export destinations the user
  chose); commit as `SigitasAmbrozaitis`.

---

## ⛔ STOP: wait for the user's confirmation before starting Phase 0

---

## Phase 0: Project setup + AI rules

Goal: an empty but complete project. The Python package, CLI, API server, web UI scaffold, tests and AI rules all work together.

### Python project
- [ ] **P0.1** `uv init` as a src-layout package `photoedit`. `.python-version` = 3.12. Fill in the `pyproject.toml` metadata
  (name, version 0.1.0, MIT, author).
- [ ] **P0.2** Add dependencies:
  - runtime: `typer`, `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`
  - dev group: `pytest`, `pytest-cov`, `hypothesis`, `httpx`, `ruff`, `mypy`

  Image libraries (rawpy, numpy, opencv…) come later in Phase 2. Commit `uv.lock`.
- [ ] **P0.3** Package skeleton:
  ```
  src/photoedit/
    __init__.py        (__version__)
    cli.py             Typer app
    config.py          settings
    safety.py          path guard
    api/app.py         FastAPI app factory
    core/__init__.py   (empty, for later phases)
    mcp/__init__.py    (empty, Phase 7)
  tests/
  ```
- [ ] **P0.4** Tool config in `pyproject.toml`:
  - ruff (lint + format, line length 110)
  - mypy (strict on `src/`)
  - pytest (testpaths, `--strict-markers`), plus markers `slow` and `golden` registered for later

### Core foundations
- [ ] **P0.5** `config.py`: a Pydantic-settings `Settings` with:
  - `project_root`, `workspace_dir`, `styles_dir`, `presets_dir`, `output_dir` (all default under the project root)
  - `sample_photos_dir` (optional)
  - `host` / `port` (127.0.0.1:8765)

  Values are loaded from defaults, then `config.local.toml` (git-ignored), then env vars `PHOTOEDIT_*`. Commit
  `config.example.toml` with `sample_photos_dir = "C:/Users/ambro/Pictures/2026/2026-08-11"`.
  Tests: defaults, local override, env override.
- [ ] **P0.6** `safety.py`: the path guard. `assert_writable(path)` allows writes only inside the allowed roots (project
  folders, plus export destinations registered at runtime). `assert_readonly_source(path)` marks photo folders as never-write.
  Tests: inside/outside a root, `..` traversal, symlinks, case-insensitive Windows paths, UNC paths.

### CLI + API
- [ ] **P0.7** CLI:
  - `photoedit --version`
  - `photoedit config show` (prints the effective settings)
  - `photoedit ui [--no-browser]` (starts uvicorn and opens the browser)

  Register the `photoedit` script entry point. Tests use Typer's `CliRunner`.
- [ ] **P0.8** FastAPI app factory:
  - `GET /api/health` returns `{status, version}`
  - serves the built UI from `ui/dist` when it exists, otherwise a plain "UI not built" page

  Tests use `TestClient`.

### Web UI scaffold
- [ ] **P0.9** `ui/`: Vite + React + TypeScript (strict). Dev server proxy `/api` → `127.0.0.1:8765`.
  Add `npm run build`, `npm run dev`, `npm test` (Vitest + React Testing Library) and `npm run lint` (ESLint).
- [ ] **P0.10** The UI shell shows "PhotoEditor" plus the backend version from `/api/health`. If the backend is down, it shows a red "backend offline" badge.
  Tests: renders the version, and shows the offline state (fetch mocked).
- [ ] **P0.11** Dev launch:
  - `.claude/launch.json` (backend + UI dev server), so Claude can preview the UI
  - `scripts/dev.ps1`, which starts both processes for the user

### AI rules + docs
- [ ] **P0.12** `CLAUDE.md`: project rules for AI.
  - golden rules (originals are read-only, write boundaries, deterministic rendering, one core with many front-ends, the code enforces ranges)
  - workflow (PLAN → TODO → phase → STOP gates; ask when in doubt)
  - commands (test, lint, type-check, run)
  - code conventions (typing, Pydantic models for all data, no logic in front-ends)
  - git rules (identity, commit message format with the item ID, never push without the user's instruction)
- [ ] **P0.13** README "Getting started" section: clone, then `uv sync`, `cd ui && npm install`, `photoedit ui`, and how to run the tests.
- [ ] **P0.14** Full check: `uv run pytest`, `uv run ruff check`, `uv run mypy src`, `npm test` and `npm run build` are all green.

### 🧑 Human test: Phase 0
1. In a new terminal: `cd C:\Work\PhotoEditing` → `uv sync` → expect no errors.
2. `uv run photoedit --version` → prints `0.1.0`.
3. `uv run photoedit config show` → shows the paths under `C:\Work\PhotoEditing`.
4. `cd ui; npm install; npm run build; cd ..` → the build succeeds.
5. `uv run photoedit ui` → the browser opens and shows "PhotoEditor" with the version. Stop the server, and the page shows "backend offline" after a refresh.
6. `uv run pytest` → all tests pass.

### ⛔ STOP: user approves Phase 0

---

## Phase 1: UI skeleton (no functionality, mock data)

Goal: every screen of the full use loop is clickable, so you can judge the look and feel. A mock API returns fake data.
The API **contract** (Pydantic models + OpenAPI) is defined here and kept in the later phases. Only the implementation behind it changes.

### Decisions to confirm at phase start (ask the user)
- [ ] **P1.0** Confirm the UI basics:
  - Visual style: dark neutral-gray theme (the standard for photo editors, because it doesn't bias color perception). Light theme optional.
  - Styling approach: Tailwind CSS (default) or plain CSS modules.
  - Component library: none / Radix primitives (default) / MUI.

### API contract + mock backend
- [ ] **P1.1** Pydantic models in `photoedit/models/`:
  - `Photo` (id, path, filename, capture date, camera, lens, ISO/shutter/aperture, size, rating, assigned style)
  - `PhotoEdit` (style ref + overrides), `AdjustmentParams` (all groups from PLAN 4.2, with ranges)
  - `Style` (id, name, description, best_for, avoid_on, params, samples)
  - `ExportPreset` (all fields from PLAN 4.6)
  - `Job` (id, kind, status, progress, items)

  Tests: validation, ranges, JSON round-trip.
- [ ] **P1.2** Mock data provider: ~24 fake photos, 4 styles, the built-in export presets (Instagram portrait, square,
  landscape, story; Print 4×6, 5×7, 8×10, A4, A3; Web full size) and 2 jobs. Placeholder images are generated in code as
  gradients/patterns with a label, and cached in `/cache` (no real photos).
- [ ] **P1.3** Mock endpoints (`/api/...`):
  - photos list (filter, paging), photo detail, thumbnail, preview (`?before=true`)
  - styles list/detail
  - export presets list/detail
  - jobs list/detail
  - `POST` apply-style / export: these return a fake job that progresses over time

  Tests for each endpoint, including that responses match the schema.
- [ ] **P1.4** Generate TypeScript types from OpenAPI (`openapi-typescript`) into `ui/src/api/types.ts`, plus an npm script.
  A test fails if the generated types are out of date.

### Screens
- [ ] **P1.5** App layout:
  - left navigation: Library, Styles, Export presets, Jobs
  - top bar: current folder, job indicator
  - routing (react-router), with a URL for each screen
- [ ] **P1.6** **Library**: folder picker field (shows the folder path), thumbnail grid, single/multi/range select,
  sort/filter (date, style, rating), style badge on each thumbnail, selection count. Actions bar: "Apply style…", "Export…".
- [ ] **P1.7** **Photo view**:
  - large preview, with before/after as a toggle *and* a split-slider mode, and a filmstrip
  - adjustment panel with every parameter group from PLAN 4.2, shown as **disabled** sliders with the current values
  - EXIF info panel
  - crop overlay placeholder
- [ ] **P1.8** **Styles library**: a card grid (name, short description, after-sample thumbnail) and a "Create style…" button (it opens a "coming in Phase 8" dialog).
- [ ] **P1.9** **Style detail**: description, best for / avoid on, before/after sample pairs, a parameter table, and an "Apply to selection" button.
- [ ] **P1.10** **Export dialog**: preset dropdown plus every setting from PLAN 4.6 (file, color space, size, aspect/orientation,
  sharpening, metadata, naming, destination folder), and a live summary line ("1080×1350 JPEG q90 sRGB → C:\…").
- [ ] **P1.11** **Apply + export flow** (the full use loop): select photos → pick a style → pick an export preset → pick a
  destination → confirm. A mock job then starts, and progress shows in the **Jobs** panel.
- [ ] **P1.12** **Jobs** screen: list with progress bars and status, plus per-item status in the job detail.
- [ ] **P1.13** UI tests (Vitest + RTL): each screen renders with mock data, plus key interactions (select photos, open the
  export dialog, change a preset → the summary updates, complete the apply flow → a job appears).
- [ ] **P1.14** Playwright smoke test: start the backend and UI, click through the full use loop, and take screenshots into `/output/screenshots`.
- [ ] **P1.15** Full check (as in P0.14) and update the README.

### 🧑 Human test: Phase 1
1. `uv run photoedit ui` → the browser opens on the Library with ~24 placeholder thumbnails.
2. Select a few photos → the selection count updates. Open one → the Photo view shows the preview and the before/after toggle and split work.
3. Styles → 4 cards → open one → the detail page shows samples and the parameter table.
4. Library → select photos → "Apply style…" → choose a style → choose "Instagram portrait" → choose a destination → confirm →
   Jobs shows a progressing job.
5. Open the Export dialog → switch presets → the summary line updates.
6. **Give feedback on layout, look and feel.** Changes are made before Phase 2.

### ⛔ STOP: user approves the UI skeleton (with any change requests applied)

---

## Phase 2: Import & decode + benchmark (outline)
- [ ] **P2.0** Detail this phase into items. ⛔ STOP for the user to review it.
- [ ] Add the image deps (rawpy, numpy, opencv-python-headless, pillow, PyExifTool + a bundled ExifTool).
- [ ] Catalog (SQLite): import a folder read-only, store path + content hash + EXIF.
- [ ] Thumbnails (from the RAF's embedded JPEG) and half-size previews (LibRaw), cached in `/cache`.
- [ ] Safety test: hashes of the originals are unchanged after import/preview.
- [ ] **Benchmark**: full-res decode + basic render of the X-T3 RAFs, sequential vs. parallel. Report the time per 100 photos and peak RAM.
  ⛔ **Go/no-go**: more than 5 min per 100 → stop and discuss.
- [ ] Replace the mock photo endpoints with real ones. The Library shows the real `2026-08-11` photos.
- 🧑 Human test + ⛔ STOP.

## Phase 3: Edit engine, MVP parameters (outline)
- [ ] **P3.0** Detail this phase. ⛔ STOP for review.
- [ ] Render pipeline stages (PLAN 4.3), each with exact-math unit tests on synthetic images.
- [ ] Per-photo edit JSON in the workspace. Deterministic render plus a golden-image test setup.
- [ ] Property tests: every valid parameter combination renders with no NaN and no out-of-range values.
- [ ] Enable the UI sliders and the live preview. Generate a slider contact sheet (−/0/+ for each parameter).
- 🧑 Human test + ⛔ STOP.

## Phase 4: Styles (outline)
- [ ] **P4.0** Detail this phase. ⛔ STOP for review.
- [ ] Style file format (`style.json` + README + samples). Library CRUD, schema versioning.
- [ ] Apply to one or many photos (writes edit JSON only). Per-photo overrides. Adaptive rules (auto exposure/WB normalization).
- [ ] The UI style screens go live with real data. A hand-written test style is applied to the sample folder.
- 🧑 Human test + ⛔ STOP.

## Phase 5: Export (outline)
- [ ] **P5.0** Detail this phase. ⛔ STOP for review.
- [ ] Resize modes, aspect crop, color space + embedded ICC, output sharpening, metadata policies, naming templates, collision handling.
- [ ] Parallel batch export job with progress, cancellation, and the path guard for destinations.
- [ ] Export tests: dimensions, ICC, EXIF, names. The UI Export dialog goes live.
- 🧑 Human test + ⛔ STOP.

## Phase 6: Geometry & centering (outline)
- [ ] **P6.0** Detail this phase. ⛔ STOP for review.
- [ ] Crop / rotate / straighten / flip / zoom in the pipeline. Subject detection (faces + saliency). `suggest_crop(aspect)`.
- [ ] Crop overlay in the Photo view.
- 🧑 Human test + ⛔ STOP.

## Phase 7: MCP server (outline)
- [ ] **P7.0** Detail this phase. ⛔ STOP for review.
- [ ] MCP server exposing the core API (PLAN 4.4), including `render_preview` returning images.
- [ ] Register it with Claude Code. The UI auto-refreshes when the AI changes something.
- [ ] MCP tests: valid and invalid input for every tool.
- 🧑 Human test (end-to-end via Claude Code) + ⛔ STOP.

## Phase 8: AI style creation (outline)
- [ ] ⛔ **STOP FIRST: ask the user for style samples** (finished photos and/or RAW + edited pairs).
- [ ] **P8.0** Detail this phase. ⛔ STOP for review.
- [ ] Analysis tools; parameter fitting from pairs (developed first on the X-T3 camera JPEG + RAF pairs).
- [ ] Style creation flow: AI proposal → render → compare → iterate → save with README + samples.
- [ ] Fallbacks as needed: F1 A/B picker, F2 statistical transfer, F3 learned 3D LUT, F5 ML (only with the user's approval).
- 🧑 Human test + ⛔ STOP.

## Phase 9: Polish (outline)
- [ ] **P9.0** Detail this phase together with the user's feedback list. ⛔ STOP for review.
- [ ] Performance tuning, clarity/texture/dehaze, noise reduction, lens corrections, more formats, UI refinements.
- 🧑 Human test + ⛔ STOP.
