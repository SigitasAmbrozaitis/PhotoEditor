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
- **Phases 0–3 are detailed.** Later phases are an outline and get detailed at the start of each phase. Writing that detail is the first item in each phase.
- Golden rules: originals are read-only; never write outside `C:\Work\PhotoEditing` (except export destinations the user
  chose); commit as `SigitasAmbrozaitis`.

- Git: follow the per-phase branch workflow in [PLAN.md §8.1](PLAN.md#81-git-workflow-per-phase).

---

## ⛔ STOP: wait for the user's confirmation before starting Phase 0

---

## Phase 0: Project setup + AI rules

Goal: an empty but complete project. The Python package, CLI, API server, web UI scaffold, tests and AI rules all work together.

### Python project
- [x] **P0.1** `uv init` as a src-layout package `photoedit`. `.python-version` = 3.12. Fill in the `pyproject.toml` metadata
  (name, version 0.1.0, MIT, author).
- [x] **P0.2** Add dependencies:
  - runtime: `typer`, `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`
  - dev group: `pytest`, `pytest-cov`, `hypothesis`, `httpx2`, `ruff`, `mypy`

  Image libraries (rawpy, numpy, opencv…) come later in Phase 2. Commit `uv.lock`.
- [x] **P0.3** Package skeleton:
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
- [x] **P0.4** Tool config in `pyproject.toml`:
  - ruff (lint + format, line length 110)
  - mypy (strict on `src/`)
  - pytest (testpaths, `--strict-markers`), plus markers `slow` and `golden` registered for later

### Core foundations
- [x] **P0.5** `config.py`: a Pydantic-settings `Settings` with:
  - `project_root`, `workspace_dir`, `styles_dir`, `presets_dir`, `output_dir` (all default under the project root)
  - `sample_photos_dir` (optional)
  - `host` / `port` (127.0.0.1:8765)

  Values are loaded from defaults, then `config.local.toml` (git-ignored), then env vars `PHOTOEDIT_*`. Commit
  `config.example.toml` with `sample_photos_dir = "C:/Users/ambro/Pictures/2026/2026-08-11"`.
  Tests: defaults, local override, env override.
- [x] **P0.6** `safety.py`: the path guard. `assert_writable(path)` allows writes only inside the allowed roots (project
  folders, plus export destinations registered at runtime). `protect(root)` marks photo folders as never-write (protected roots win over writable ones).
  Tests: inside/outside a root, `..` traversal, symlinks, case-insensitive Windows paths, UNC paths.

### CLI + API
- [x] **P0.7** CLI:
  - `photoedit --version`
  - `photoedit config show` (prints the effective settings)
  - `photoedit ui [--no-browser]` (starts uvicorn and opens the browser)

  Register the `photoedit` script entry point. Tests use Typer's `CliRunner`.
- [x] **P0.8** FastAPI app factory:
  - `GET /api/health` returns `{status, version}`
  - serves the built UI from `ui/dist` when it exists, otherwise a plain "UI not built" page

  Tests use `TestClient`.

### Web UI scaffold
- [x] **P0.9** `ui/`: Vite + React + TypeScript (strict). Dev server proxy `/api` → `127.0.0.1:8765`.
  Add `npm run build`, `npm run dev`, `npm test` (Vitest + React Testing Library) and `npm run lint` (oxlint, the Vite template default).
- [x] **P0.10** The UI shell shows "PhotoEditor" plus the backend version from `/api/health`. If the backend is down, it shows a red "backend offline" badge.
  Tests: renders the version, and shows the offline state (fetch mocked).
- [x] **P0.11** Dev launch:
  - `.claude/launch.json` (backend + UI dev server), so Claude can preview the UI
  - `scripts/dev.ps1`, which starts both processes for the user

### AI rules + docs
- [x] **P0.12** `CLAUDE.md`: project rules for AI.
  - golden rules (originals are read-only, write boundaries, deterministic rendering, one core with many front-ends, the code enforces ranges)
  - workflow (PLAN → TODO → phase → STOP gates; ask when in doubt)
  - commands (test, lint, type-check, run)
  - code conventions (typing, Pydantic models for all data, no logic in front-ends)
  - git rules (identity, commit message format with the item ID, the per-phase branch workflow from PLAN.md §8.1)
- [x] **P0.13** README "Getting started" section: clone, then `uv sync`, `cd ui && npm install`, `photoedit ui`, and how to run the tests.
- [x] **P0.14** Full check: `uv run pytest`, `uv run ruff check`, `uv run mypy src`, `npm test` and `npm run build` are all green.

### 🧑 Human test: Phase 0
1. Open a **new** terminal (so uv and node are on PATH): `cd C:\Work\PhotoEditing` → `uv sync` → expect no errors.
2. `uv run photoedit --version` → prints `0.1.0`.
3. `uv run photoedit config show` → the paths are under `C:\Work\PhotoEditing`, and `sample_photos_dir` is your
   `2026-08-11` folder (from `config.local.toml`).
4. `cd ui; npm install; npm run build; cd ..` → the build succeeds.
5. `uv run photoedit ui` → the browser opens and shows "PhotoEditor" with a green `backend v0.1.0` badge. Ctrl+C stops it.
6. `uv run pytest` → all tests pass (2 symlink tests are skipped unless Windows Developer Mode is on). `cd ui; npm test` → all pass.
7. `scripts\dev.cmd` → a backend window opens, and the browser opens http://localhost:5173 with a green badge.
   Close the backend window → within about 5 s the badge turns red "backend offline". Ctrl+C in the first terminal stops the dev server.

### ⛔ STOP: user approves Phase 0

---

## Phase 1: UI skeleton (no functionality, mock data)

Goal: every screen of the full use loop is clickable, so you can judge the look and feel. A mock API returns fake data.
The API **contract** (Pydantic models + OpenAPI) is defined here and kept in the later phases. Only the implementation behind it changes.

### Decisions to confirm at phase start (ask the user)
- [x] **P1.0** Confirm the UI basics (decided: dark neutral gray, Tailwind CSS, Radix primitives):
  - Visual style: dark neutral-gray theme (the standard for photo editors, because it doesn't bias color perception). Light theme optional.
  - Styling approach: Tailwind CSS (default) or plain CSS modules.
  - Component library: none / Radix primitives (default) / MUI.

### API contract + mock backend
- [x] **P1.1** Pydantic models in `photoedit/models/`:
  - `Photo` (id, path, filename, capture date, camera, lens, ISO/shutter/aperture, size, rating, assigned style)
  - `PhotoEdit` (style ref + overrides), `AdjustmentParams` (all groups from PLAN 4.2, with ranges)
  - `Style` (id, name, description, best_for, avoid_on, params, samples)
  - `ExportPreset` (all fields from PLAN 4.6)
  - `Job` (id, kind, status, progress, items)

  Tests: validation, ranges, JSON round-trip.
- [x] **P1.2** Mock data provider: ~24 fake photos, 4 styles, the built-in export presets (Instagram portrait, square,
  landscape, story; Print 4×6, 5×7, 8×10, A4, A3; Web full size) and 2 jobs. Placeholder images are generated in code as
  gradients/patterns with a label, and cached in memory (no real photos, no disk writes). The built-in presets are
  real data in `core/presets.py` and are kept for Phase 5.
- [x] **P1.3** Mock endpoints (`/api/...`):
  - photos list (filter, paging), photo detail, thumbnail, preview (`?before=true`)
  - styles list/detail
  - export presets list/detail
  - jobs list/detail
  - `POST` apply-style / export: these return a fake job that progresses over time

  Tests for each endpoint, including that responses match the schema.
- [x] **P1.4** Generate TypeScript types from OpenAPI (`openapi-typescript`) into `ui/src/api/schema.d.ts` via `npm run gen:api` (exports `ui/openapi.json` with `photoedit openapi`).
  A test fails if the generated types are out of date.

### Screens
- [x] **P1.5** App layout:
  - left navigation: Library, Styles, Export presets, Jobs
  - top bar: current folder, job indicator
  - routing (react-router), with a URL for each screen
- [x] **P1.6** **Library**: folder picker field (shows the folder path), thumbnail grid, single/multi/range select,
  sort/filter (date, style, rating), style badge on each thumbnail, selection count. Actions bar: "Apply style…", "Export…".
- [x] **P1.7** **Photo view**:
  - large preview, with before/after as a toggle *and* a split-slider mode, and a filmstrip
  - adjustment panel with every parameter group from PLAN 4.2, shown as **disabled** sliders with the current values
  - EXIF info panel
  - crop overlay placeholder
- [x] **P1.8** **Styles library**: a card grid (name, short description, after-sample thumbnail) and a "Create style…" button (it opens a "coming in Phase 8" dialog).
- [x] **P1.9** **Style detail**: description, best for / avoid on, before/after sample pairs, a parameter table, and an "Apply to selection" button.
- [x] **P1.10** **Export dialog**: preset dropdown plus every setting from PLAN 4.6 (file, color space, size, aspect/orientation,
  sharpening, metadata, naming, destination folder), and a live summary line ("1080×1350 JPEG q90 sRGB → C:\…").
- [x] **P1.11** **Apply + export flow** (the full use loop): select photos → pick a style → pick an export preset → pick a
  destination → confirm. A mock job then starts, and progress shows in the **Jobs** panel.
- [x] **P1.12** **Jobs** screen: list with progress bars and status, plus per-item status in the job detail.
- [x] **P1.13** UI tests (Vitest + RTL): each screen renders with mock data, plus key interactions (select photos, open the
  export dialog, change a preset → the summary updates, complete the apply flow → a job appears).
- [x] **P1.14** Playwright smoke test: start the backend and UI, click through the full use loop, and take screenshots into `/output/screenshots`. (`npm run test:e2e`; uses the installed Google Chrome, so no browser download.)
- [x] **P1.15** Full check (as in P0.14) and update the README.

### 🧑 Human test: Phase 1
0. Stop any `photoedit ui` still running from Phase 0 (Ctrl+C in its terminal), because it holds files that `uv sync` must
   update. Then, in a new terminal: `uv sync`, `npm --prefix ui install` and `npm --prefix ui run build`.
1. `uv run photoedit ui` → the browser opens on the **Library**: 24 placeholder thumbnails, a yellow `DEMO DATA` tag and a
   green backend badge.
2. Selecting: click one photo, **Shift+click** another (range), **Ctrl+click** to add/remove → "N selected" updates.
   Try sorting (date/name/rating, ↑↓), the Style filter and the Rating filter.
3. **Double-click** a photo (or Enter) → the **Photo view**. Check the **After / Before / Split** buttons (drag across the
   image in Split), the **Crop** overlay, the right panel (**Adjust**: read-only sliders per group; **Info**: EXIF), the
   filmstrip, and ←/→ keys for prev/next and Esc to go back.
4. **Styles** → 4 cards → open one → description, best for / avoid on, before/after samples and the parameter table.
   "Create style…" explains Phase 8.
5. Library → select several photos → **Apply style…** → pick a style → Next → keep "Instagram portrait (4:5)" → click a
   *Recent* destination or type one → Next → review → **Apply & export** → you land on **Jobs**, and the job's progress
   bar runs to 100%. The top bar shows "N running" while it runs.
6. Library → select photos → **Export…** → switch presets and change settings → the summary line at the bottom updates
   live, and the preset label says "(modified)".
7. **Export presets** → browse the 10 built-in presets (read-only).
8. **Give feedback on layout, look and feel** (colors, sizes, what's missing or in the wrong place). Changes are made on
   this branch before Phase 2.

Optional: `npm --prefix ui run test:e2e` clicks through the whole loop in Chrome and saves screenshots of every screen to
`output/screenshots/`.

### ⛔ STOP: user approves the UI skeleton (with any change requests applied)

---

## Phase 2: Import & decode + benchmark

Goal: the Library shows the **real** photos of a folder (thumbnails, EXIF, a neutral preview), backed by a SQLite catalog.
The originals are provably untouched. A benchmark decides go/no-go for the Python engine **before** more is built on it.
Styles, export presets and apply/export jobs stay mock until their phases.

Facts from a probe of `DSCF5437.RAF` (read-only, hash unchanged): 6246×4170 X-Trans, embedded JPEG 4416×2944 with full
EXIF (rotation via the EXIF `Orientation` tag; Fuji pads strings with NUL bytes); LibRaw 0.22 half-size decode ≈ 0.6 s,
full-size ≈ 5.2 s single-threaded; without auto-brightness the render is ~1.3 EV darker than the camera JPEG (Fuji
underexposes the RAW to protect highlights).

- [x] **P2.0** Detail this phase into items. ⛔ STOP for the user to review it.

### Decisions to confirm at phase start (ask the user)
- [x] **P2.1** Confirm (all defaults confirmed 2026-10-07 and recorded in PLAN.md §0):
  - **RAW + JPEG pairs** (`DSCF5437.RAF` + `DSCF5437.JPG`): one photo. The RAW is the master; the camera JPEG is
    remembered as a sidecar (test data for Phase 8). A JPEG/TIFF without a RAW is a photo of its own. Other files (`.MOV`…)
    are skipped and counted.
  - **Opening folders**: an in-app folder browser (read-only directory listing via the API), a paste-a-path field and a
    list of recent folders. The catalog keeps every imported folder; the Library shows one folder at a time. Subfolders
    are not included unless "Include subfolders" is ticked. Nothing is imported automatically on start.
  - **Photo identity**: the id comes from the file's content hash (SHA-256). A moved or renamed folder is recognized on
    re-import and keeps its edits; identical files in two places are one photo (the latest path wins).
  - **EXIF reading with Pillow** (from the RAW's embedded JPEG, or the JPEG itself). **ExifTool moves to Phase 5**, where it
    is first needed (copying metadata into exports). OpenCV moves to Phase 3 for the same reason.
  - **Phase 2 preview look**: LibRaw half-size decode, camera white balance, sRGB, LibRaw auto-brightness **on** (closest to
    the camera JPEG). It is temporary: Phase 3's pipeline replaces it, and exposure normalization becomes an adaptive rule
    in Phase 4.

### Dependencies
- [x] **P2.2** Add runtime deps `rawpy` and `numpy`, and `psutil` (for the benchmark's RAM measurement). Commit `uv.lock`.
  `photoedit version` prints the photoedit, Python, rawpy/LibRaw and numpy versions (LibRaw is part of the render identity).

### Reading files (read-only)
- [x] **P2.3** `core/scan.py`: list a folder's supported files (optionally recursive) and group RAW + JPEG pairs by
  file stem (case-insensitive). Supported: RAW extensions LibRaw handles (`.raf .cr2 .cr3 .nef .arw .orf .rw2 .dng .pef
  .srw`), plus `.jpg .jpeg .tif .tiff`. Result model: photos found + skipped files with a reason. Files are only ever
  opened `"rb"`.
  Tests (synthetic files in `tmp_path`): pairing, case variants, lone JPEG, lone RAW, skipped types, subfolders on/off,
  a missing folder and a file path instead of a folder → clear errors.
- [x] **P2.4** `core/metadata.py`: EXIF → a `PhotoMetadata` model. Strip NULs; camera `"FUJIFILM X-T3"` (no doubled
  make); shutter as displayed (`0.00025` → `"1/4000"`, `0.5` → `"0.5s"`, `2` → `"2s"`); `captured_at` from
  `DateTimeOriginal` (+ `OffsetTimeOriginal` when present); width/height after orientation; rating from EXIF/XMP if
  present, else 0. Missing or broken EXIF gives `None` fields, never an exception.
  Tests: synthetic JPEGs with EXIF written by Pillow (every orientation 1–8, odd shutter values, missing tags, garbage EXIF).
- [x] **P2.5** `core/decode.py`: the only module that touches LibRaw.
  - `embedded_jpeg(path)`: the RAW's embedded JPEG bytes (orientation applied when decoded to pixels).
  - `decode(path, size=PREVIEW|FULL)`: an RGB array, using fixed, explicit LibRaw options in a frozen `DecodeOptions`
    model (camera WB, sRGB, auto-bright on, half-size for previews). JPEG/TIFF originals decode via Pillow with EXIF
    orientation applied.
  - `DECODER_VERSION` + the LibRaw version form the **render identity** used in cache keys (determinism, golden rule 3).
  - LibRaw is pinned to **one OpenMP thread** in every calling thread: its multithreaded X-Trans decode is not
    deterministic (found while doing this item; see PLAN.md §0).

  Tests: JPEG/TIFF paths and options on synthetic files; real RAF decode is `@pytest.mark.golden` (a portrait shot comes
  out upright, output size, identical bytes on two decodes).

### Benchmark: go/no-go
- [x] **P2.6** `core/benchmark.py` + CLI `photoedit benchmark [FOLDER] [--count N] [--workers 1,2,4,6,8]` (FOLDER defaults to
  `sample_photos_dir`). Per photo: full-res decode + a basic float32 render (exposure gain, a tone curve, a saturation
  change, back to 8-bit) + JPEG q90 encode **in memory** (nothing is written near the photos). It runs sequentially and
  with a process pool for each worker count, and reports seconds per photo, **minutes per 100 photos** and **peak RAM**
  (sum over the process tree, sampled with psutil). The report goes to `output/benchmark/report-<timestamp>.md`.
  Tests: report math and formatting on a fake decoder (non-golden); a 2-photo real run is `@pytest.mark.golden` + `slow`.
- [x] **P2.7** Run the benchmark on all 67 RAFs. Copy the summary table into `docs/benchmark.md` (committed).
  ⛔ **Go/no-go**: if the best configuration takes more than 5 min per 100 photos, stop and discuss with the user.

### Catalog + cache
- [x] **P2.8** `core/catalog.py`: SQLite at `workspace/catalog.sqlite` (stdlib `sqlite3`, no ORM). Tables `folders` and
  `photos` (id from the content hash, path, folder, filename, size, mtime, sha256, kind raw/raster, sidecar JPEG path,
  metadata fields, rating, missing flag). Schema version in `PRAGMA user_version` with a migration hook. Queries back the
  existing filter/sort/paging contract. The DB file goes through `PathGuard.assert_writable`.
  Tests: CRUD, upsert on re-import, a moved file keeps its id, filter/sort/paging, schema version mismatch → clear error.
- [x] **P2.9** `core/cache.py`: disk cache in `cache/`, keyed by photo id + render identity:
  - thumbnails `cache/thumbs/…jpg` (400 px long edge, from the embedded JPEG for RAWs),
  - previews `cache/previews/…jpg` (half-size render, JPEG q92), resized per request with a small in-memory LRU.

  Atomic writes (temp file + rename), all through the path guard. CLI `photoedit cache clear`.
  Tests: hit/miss, a render-identity change invalidates, atomic write, a cache dir configured inside a protected photo
  folder is refused.

### Import
- [x] **P2.10** `core/jobs.py`: a real in-process job manager (thread pool, progress, cancel) behind the existing `Job`
  model; add `JobKind.IMPORT`, `Job.folder`, `Job.summary`, and make `JobItem.photo_id` optional (an import item has no
  id until its file is hashed). The mock apply/export jobs run on it too (each item just sleeps), so the Jobs screen
  shows both. Tests: progress, cancel, a failing item doesn't stop the job, list order.
- [x] **P2.11** `core/library.py`: `import_folder(folder, include_subfolders)` as a job. It protects the folder in the path
  guard **first**, then per photo: stat → hash (skipped when size + mtime are unchanged since the last import) → metadata →
  thumbnail. Re-import is incremental; files that disappeared are flagged missing and hidden. Also: list folders, current
  folder (remembered in the workspace), photo list/detail, thumbnail/preview bytes. CLI `photoedit import FOLDER`.
  Tests on synthetic JPEG folders in `tmp_path`: first import, incremental re-import, deleted file, renamed folder, cancel.
- [x] **P2.12** **Safety tests**:
  - synthetic (always runs): a protected folder in `tmp_path`; import + thumbnails + previews → every file's SHA-256, size,
    mtime and the folder listing are unchanged;
  - golden: the same check on the real `2026-08-11` folder, with workspace and cache in `tmp_path`.

### API + UI
- [x] **P2.13** Real endpoints replace the mock photo endpoints (same contract for photos/detail/thumbnail/preview;
  `before` returns the same image until Phase 3). New:
  - `GET /api/library/folders`, `PUT /api/library/current` (switch folder), `POST /api/library/import` → `Job`
  - `GET /api/fs/dirs?path=` for the folder browser: drives when `path` is empty, otherwise subfolders + the number of
    supported photos in each (read-only listing)

  Styles and export presets stay mock. Unknown folder / not a folder / unreadable → 4xx with a clear message.
  `photoedit/services.py` wires the core from settings (shared by API and CLI); the app builds it on the first request,
  so `photoedit openapi` never creates a catalog. Regenerate `openapi.json` + `schema.d.ts`. Tests for every new and
  changed endpoint.
- [x] **P2.14** UI:
  - **Library**: empty state ("Open a folder", sample folder pre-filled); editable folder field + **Browse…** dialog +
    recent folders + **Include subfolders**; **Open** starts the import, shows progress in the Library and in Jobs, and the
    grid fills in as thumbnails arrive. The `DEMO DATA` tag leaves the Library (it stays on Styles/Presets).
  - **Photo view**: the real preview with a loading state, real EXIF in **Info**, the sidecar camera JPEG named in Info.
    Sliders stay disabled.

  Vitest tests: empty state, folder browser navigation, import progress, the grid after import.
- [x] **P2.15** Playwright smoke test on generated photos: `scripts/e2e_setup.py` writes 8 synthetic JPEGs into
  `output/e2e/photos`, and the e2e server's workspace/cache/sample folder point at `output/e2e/` via `PHOTOEDIT_*`
  (tool-owned folders only); then open the folder → import → grid → photo view, plus the existing apply/export loop.
  Screenshots go to `output/screenshots/`.
- [x] **P2.16** Full check (pytest incl. `-m golden` locally, ruff, format, mypy, npm test/lint/build, e2e) and update README.

### 🧑 Human test: Phase 2
0. Stop any running `photoedit ui`. Then `uv sync`, `npm --prefix ui install`, `npm --prefix ui run build`.
1. `uv run photoedit ui` → the Library shows "Open a folder" with your `2026-08-11` path pre-filled. No `DEMO DATA` tag there.
2. **Browse…** → go to `C:\Users\ambro\Pictures\2026\2026-08-11` (each folder shows its photo count) → choose it →
   **Open** → an import job runs (progress in the Library and on Jobs) and thumbnails fill in. Expect **67 photos** (RAF +
   JPG pairs merged; the `.MOV` reported as skipped), with portrait shots upright.
3. Open `DSCF5437` → **Info** shows FUJIFILM X-T3, XF18-55mmF2.8-4 R LM OIS, ISO 6400, 1/4000, f/4.5, 55 mm,
   2026-08-11 06:02:51, and the camera JPEG as sidecar.
4. The preview shows within about 2 s the first time (a spinner shows meanwhile) and instantly afterwards. Compare a few
   photos with their camera JPEGs: natural colors and white balance, no strong color cast. Expected differences (fixed by
   the Phase 3 pipeline): flatter and less saturated (no film simulation); dark, low-key scenes come out **brighter**
   than the camera JPEG (LibRaw auto-brightness); blown-out lights can show a faint tint instead of pure white.
5. Sort/filter still work. ←/→ in the Photo view walks through the real photos.
6. Close and restart `photoedit ui` → the library is there at once. **Open** the folder again → it finishes within a
   few seconds with "Last import: 67 photos: 67 unchanged; 1 other file skipped".
7. In Explorer, the `2026-08-11` folder has no new or changed files (sort by Date modified). `uv run pytest -m golden` →
   the real-folder safety test passes.
8. `uv run photoedit benchmark` (takes about 6 minutes; the computer is busy meanwhile) → prints the table (minutes per
   100 photos, peak RAM) and the report path. Compare with `docs/benchmark.md`.

### ⛔ STOP: user approves Phase 2

## Phase 3: Edit engine, MVP parameters

Goal: real, deterministic rendering of every MVP parameter (PLAN 4.2/4.3), saved per photo as edit JSON, with live
sliders in the Photo view. Geometry (crop/rotate) stays in Phase 6; clarity/texture/dehaze, noise reduction, grain and
lens corrections stay in Phase 9. Styles stay mock (Phase 4).

Facts from a probe of 9 X-T3 RAFs (2026-10-08): LibRaw's linear camera-space decode + our own camera→sRGB matrix
(built from `rgb_xyz_matrix`, LibRaw's method) reproduces LibRaw's sRGB output exactly (mean diff 0.00001), so the
pipeline can own white balance and color conversion. "As shot" Kelvin + tint can be recovered from the camera
multipliers (fit residual < 0.01; these shots ≈ 4950–5025 K). There is **no constant exposure offset** to the camera
JPEGs (−1.2 to +1.1 EV depending on scene and tone range): the camera's tone curve differs, so matching it needs a
fitted curve, not just an exposure value (P3.13). Numpy
pipeline math at preview size runs in ~100–200 ms, so live sliders are feasible.

**Engine design** (fixed order, float32):
- Working space: **linear Rec.2020, D65**. Hue/saturation work (HSL, color grading, vibrance) uses **OKLab/OKLCh**
  (perceptually uniform, so a hue shift doesn't change brightness). Tone curves work on display-encoded values (0..1).
- White balance: RAWs are decoded once in camera space with the camera's WB; a new temperature/tint rescales the
  camera channels (`new / as-shot` multipliers from Kelvin via the camera matrix) before the camera→Rec.2020 matrix.
  JPEG/TIFF originals count as "as shot" = 6500 K, tint 0, and use a Bradford adaptation.
- Highlights/shadows/whites/blacks/contrast are **global** luminance curves (ratio-preserving, so colors don't shift).
  Local, Lightroom-style versions arrive with clarity in Phase 9.
- Sharpening default (amount 40) is applied, like Lightroom's default input sharpening; its radius scales with the
  output size, so previews and exports look alike.

- [x] **P3.0** Detail this phase into items. ⛔ STOP for the user to review it.

### Decisions to confirm at phase start (ask the user)
- [x] **P3.1** Confirmed 2026-10-08 (recorded in PLAN.md §0):
  - **Default look = match the camera JPEGs.** An unedited photo renders through a **camera profile** fitted from the
    RAF + camera JPEG pairs (P3.13). All 67 samples were shot with **Provia/Standard at DR100** (read from the Fuji maker
    notes), so the first profile is "FUJIFILM X-T3 · Provia". Cameras without a profile get a generic profile (gentle
    S-curve, no color change). JPEG/TIFF originals are already rendered and get no profile.
  - **Thumbnails** go through the same pipeline as the Photo view: after an import, a background job re-renders them
    (≈ 15 s per 67 photos with parallel workers), and a photo's thumbnail is re-rendered when its edit changes. Until
    then, the embedded JPEG thumbnail is shown.
  - **Golden images of your real photos stay local** (git-ignored, regenerated with a command); only synthetic golden
    images are committed.
  - **Parameters planned for later phases** (geometry, clarity, texture, dehaze, noise reduction, grain, lens) are
    **rejected with a clear error** when set to a non-default value, instead of being silently ignored (golden rule 5).

### Engine
- [x] **P3.2** Add `opencv-python-headless` (blur/resize for sharpening and previews) and `scipy` (least-squares fitting
  of the camera profile; reused for style fitting in Phase 8). Commit `uv.lock`.
- [x] **P3.3** `core/color.py`: the color math, all float64-exact and tested against published reference values:
  sRGB/Rec.2020/XYZ matrices and transfer functions; OKLab/OKLCh (Ottosson's reference values); Kelvin + tint ↔
  chromaticity (Planckian/daylight locus, tint perpendicular to it); Bradford adaptation; camera WB multipliers from
  Kelvin + tint (given the camera matrix) and the inverse "as shot" estimate.
- [x] **P3.4** `decode.decode_linear(path, size)`: RAW → demosaiced, camera-space, camera-WB, linear float data plus the
  camera matrix and as-shot multipliers; JPEG/TIFF → linear Rec.2020. `DECODER_VERSION` → 2. Golden test: our matrix
  path matches LibRaw's sRGB output within 1e-4.
- [x] **P3.5** Linear base cache: the decoded linear image at preview working size (long edge 2048) in an in-memory
  LRU (8 photos, ~33 MB each); no disk copy (~16 MB per photo even as float16): rendered previews are disk-cached
  instead (P3.15). Full resolution is decoded on demand (exports).
- [x] **P3.6** Render stages in `core/render/` (pure functions on arrays; exact-math tests on synthetic images, and each
  stage is the identity at its neutral value):
  - white balance + camera → Rec.2020; exposure (+1 EV doubles linear values); output transform (Rec.2020 → sRGB,
    gamut clip, sRGB encoding, 8/16-bit)
- [x] **P3.7** Tone stages: whites/blacks, highlights/shadows, contrast (18 % gray stays fixed; ratio-preserving).
- [x] **P3.8** Curves: base curve, parametric regions (highlights/lights/darks/shadows), point curves for RGB/R/G/B
  (monotone cubic, so curves never overshoot).
- [x] **P3.9** Color stages: HSL (8 overlapping hue bands in OKLCh), color grading (shadows/midtones/highlights/global
  wheels with blending and balance), vibrance (weighted toward muted colors) and saturation (−100 = gray with the same
  luminance).
- [x] **P3.10** Effects + detail: post-crop vignette (amount/midpoint/roundness/feather; the center stays unchanged) and
  sharpening (luminance unsharp mask: amount/radius/detail/masking).
- [x] **P3.11** `render.pipeline`: `render(base, params, size)` runs the stages in PLAN 4.3 order. `ENGINE_VERSION` joins
  the render identity. Determinism: the same input gives identical bytes (OpenCV thread count pinned; tested twice in a
  row and across threads). Rejects later-phase parameters (P3.1).
- [x] **P3.12** Property tests (hypothesis): any valid `AdjustmentParams` renders a small synthetic image with no NaN, no
  out-of-range values, and identical output on a second run; invalid parameters are rejected by the models.
- [x] **P3.13** Camera profile = the default look (P3.1). A profile is the first render stage after white balance, so
  user adjustments work on top of it, like Lightroom's camera profiles:
  - `CameraProfile` model (versioned JSON): camera make/model, film simulation, baseline exposure, a 3×3 color matrix
    (linear Rec.2020), a monotone tone curve, and 8-band hue/saturation/luminance tweaks (OKLCh). Shipped profiles live
    in the package (`src/photoedit/profiles/`); selection by camera, otherwise the generic profile.
  - Fujifilm DR200/DR400 shots are underexposed 1/2 EV by the camera on purpose; the profile adds that back (DR read from
    the maker notes at import). Only DR100 can be checked against the samples.
  - `photoedit profile fit FOLDER` fits a profile from RAF + camera JPEG pairs: both downscaled (~512 px, center 90 % to
    avoid the JPEG's lens corrections), clipped and near-black pixels excluded, least squares on OKLab differences, every
    4th pair held out. It writes `output/profiles/<camera>.json` plus a report; the result is reviewed and copied into the
    package by hand (the tool never writes into `src/`).
  - Acceptance: mean ΔE2000 on the held-out pairs ≤ 3 (≈ "barely noticeable side by side"). If the parametric model
    can't reach that, stop and discuss (fallback: a 3D LUT inside the profile, i.e. Phase 8's F3 pulled forward).
  - `docs/default-look.md`: method, the fitted numbers, and ΔE before/after per held-out photo.

### Edits, previews, golden images
- [ ] **P3.14** `core/edits.py`: per-photo edit JSON `workspace/edits/<photo-id>.json` (`schema_version`, `photo_id`,
  `style_id` (unused until Phase 4), sparse `overrides` such as `{"tone.exposure": 0.5}`); load/save/reset, effective
  parameters = defaults ← style ← overrides; atomic writes through the path guard. Catalog schema v2 (the migration hook's
  first use): `has_edits`, as-shot temperature/tint (filled lazily for photos imported before).
- [ ] **P3.15** Previews and thumbnails through the pipeline: `before` = default look, `after` = the photo's edit; the cache
  key adds a hash of the edit; thumbnails per P3.1 (background job after import, re-render on edit).
- [ ] **P3.16** Golden images (P3.1): a committed synthetic reference (color chart + gradients rendered with fixed
  parameters, compared exactly), plus `photoedit golden update` writing local references for a few real RAFs into
  `tests/golden-local/` (git-ignored), compared by `@pytest.mark.golden` tests within a small ΔE tolerance.
- [ ] **P3.17** Contact sheet: `photoedit contact-sheet PHOTO [--group tone]` → `output/contact-sheets/…jpg`, every
  implemented parameter at −/0/+ (min/neutral/max where that's more useful), labeled.
- [ ] **P3.18** Preview speed: time a full render at 1600 px from the cached base on a real RAF (target ≤ 0.5 s); add the
  result to `docs/benchmark.md`.

### API + UI
- [ ] **P3.19** API: `PUT /api/photos/{id}/edit` (full `AdjustmentParams`; validated, saved as overrides, returns
  `PhotoDetail` with an edit revision), `DELETE /api/photos/{id}/edit` (reset); preview URLs carry the revision for cache
  busting; `PhotoDetail` adds the as-shot WB and which parameters are live in this phase. Regenerate the TS types.
- [ ] **P3.20** Photo view: sliders enabled for live parameters (later-phase ones stay disabled, labeled "Phase 6/9");
  numeric entry; double-click a slider to reset it; reset group / reset all; WB shows the as-shot values; changes save
  automatically (debounced) and the preview updates, keeping the old image until the new one arrives; Before = default
  look; a **Camera JPEG** view mode (when the photo has a sidecar) to compare the default look with what the camera
  made; Ctrl+Z / Ctrl+Shift+Z undo/redo within the session.
- [ ] **P3.21** Tone curve editor: an SVG point editor for RGB/R/G/B (drag points, click to add, double-click to remove)
  next to the parametric sliders.
- [ ] **P3.22** Tests: Vitest for slider edit/reset/undo and the curve editor; Playwright: move a slider → the preview
  changes and the edit survives a reload; screenshots.
- [ ] **P3.23** Full check (pytest incl. `-m golden`, ruff, format, mypy, npm test/lint/build, e2e) and update README.

### 🧑 Human test: Phase 3
0. Stop any running `photoedit ui`. Then `uv sync`, `npm --prefix ui install`, `npm --prefix ui run build`.
1. `uv run photoedit ui` → the Library. Within a short while the thumbnails switch to the pipeline's default look
   (a background job on Jobs). They should look very close to the camera JPEGs (Provia).
1b. Open a few photos and switch between **After** and **Camera JPEG**: colors, contrast and brightness match closely
   (small differences in sharpening, noise and the very corners are expected; `docs/default-look.md` lists the measured
   difference per photo).
2. Open a photo → the Adjust panel's sliders are live (geometry and Phase 9 ones stay disabled, labeled). Move
   **Exposure** → the preview updates within about half a second. Try every group: white balance (temperature/tint start
   at the as-shot values), tone, presence, tone curve (drag a point), HSL, color grading, sharpening, vignette.
3. **Before/After/Split** compare against the default look. Double-click a slider → it resets. **Reset all** works.
   Ctrl+Z / Ctrl+Shift+Z undo and redo.
4. Go back to the Library → the edited photo's thumbnail shows the edit. Restart `photoedit ui` → the edit is still there.
5. Extreme values (every slider at its end) never produce broken colors, black frames or errors.
6. `uv run photoedit contact-sheet DSCF5437` → open the images in `output/contact-sheets/`: each parameter at −/0/+
   looks like what its name says.
7. The `2026-08-11` folder is still unchanged (Explorer, Date modified). `uv run pytest -m golden` passes.
8. **Give feedback on the default look and on how each slider feels** (too strong, too weak, wrong direction).

### ⛔ STOP: user approves Phase 3

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
