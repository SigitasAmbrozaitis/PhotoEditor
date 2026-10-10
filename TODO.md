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
- **Phases 0–4 and 3b (deferred, at the end) are detailed.** Later phases are an outline and get detailed at the start of each phase. Writing that detail is the first item in each phase.
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
- [x] **P3.14** `core/edits.py`: per-photo edit JSON `workspace/edits/<photo-id>.json` (`schema_version`, `photo_id`,
  `style_id` (unused until Phase 4), sparse `overrides` such as `{"tone.exposure": 0.5}`); load/save/reset, effective
  parameters = defaults ← style ← overrides; atomic writes through the path guard. Catalog schema v2 (the migration hook's
  first use): `has_edits`, as-shot temperature/tint (filled lazily for photos imported before).
- [x] **P3.15** Previews and thumbnails through the pipeline: `before` = default look, `after` = the photo's edit; the cache
  key adds a hash of the edit; thumbnails per P3.1 (background job after import, re-render on edit).
- [x] **P3.16** Golden images (P3.1): committed synthetic references (`tests/golden/`: a color chart + ramps rendered
  with fixed edits under the generic and X-T3 profiles, compared bit-exactly; `scripts/update_golden.py` regenerates
  them), plus `photoedit golden update` writing local references for a few real RAFs into `output/golden/`
  (git-ignored, a tool-owned folder: `tests/` is not one), compared by `@pytest.mark.golden` tests within ΔE2000
  mean ≤ 0.5 / p99 ≤ 2.
- [x] **P3.17** Contact sheet: `photoedit contact-sheet PHOTO [--group tone]` → `output/contact-sheets/…jpg`, every
  implemented parameter at −/0/+ (min/neutral/max where that's more useful), labeled.
- [x] **P3.18** Preview speed: time a full render at 1600 px from the cached base on a real RAF (target ≤ 0.5 s); add the
  result to `docs/benchmark.md`.

### API + UI
- [x] **P3.19** API: `PUT /api/photos/{id}/edit` (full `AdjustmentParams`; validated, saved as overrides, returns
  `PhotoDetail` with an edit revision), `DELETE /api/photos/{id}/edit` (reset); preview URLs carry the revision for cache
  busting; `PhotoDetail` adds the as-shot WB and which parameters are live in this phase. Regenerate the TS types.
- [x] **P3.20** Photo view: sliders enabled for live parameters (later-phase ones stay disabled, labeled "Phase 6/9");
  numeric entry; double-click a slider to reset it; reset group / reset all; WB shows the as-shot values; changes save
  automatically (debounced) and the preview updates, keeping the old image until the new one arrives; Before = default
  look; a **Camera JPEG** view mode (when the photo has a sidecar) to compare the default look with what the camera
  made; Ctrl+Z / Ctrl+Shift+Z undo/redo within the session.
- [x] **P3.21** Tone curve editor: an SVG point editor for RGB/R/G/B (drag points, click to add, double-click to remove)
  next to the parametric sliders.
- [x] **P3.22** Tests: Vitest for slider edit/reset/undo and the curve editor; Playwright: move a slider → the preview
  changes and the edit survives a reload; screenshots.
- [x] **P3.23** Full check (pytest incl. `-m golden`, ruff, format, mypy, npm test/lint/build, e2e) and update README.

### Human test feedback (2026-10-09)
Measured on DSCF5437 at 1600 px, each slider at ±100 vs. unedited: Whites changed 0 % of pixels (max 1/255), Blacks
14 % (weak), Highlights −100 only 2 %; Shadows/Contrast/Exposure 93–100 %. Cause: the four bands sit at fixed scene
stops (whites +2…+5 stops above mid gray, blacks −4…−9), but this photo's brightest pixel is +2.4 stops and the X-T3
curve's shoulder starts at +2. Speed → Phase 3b. Sharpening → needs the 1:1 view (Phase 6). HSL: not changed for now.

- [x] **P3.24** Relative tone sliders (PLAN §0, 2026-10-09). Highlights/shadows/whites/blacks act relative to the photo's
  own tonal range, like Lightroom ([docs/tone-sliders.md](docs/tone-sliders.md)):
  - **Anchors**: a black and a white point per photo (0.5 % / 99.5 % luminance percentiles), measured once on the
    default render's scene luminance (as-shot WB, camera profile, exposure 0) at a fixed 512 px size, so the numbers
    don't depend on preview or export size. Stored in the catalog (schema v3, filled lazily on the first render)
    together with the render identity; measured again when that changes.
  - **Bands** sit between the anchors and move with the exposure slider. The pivot is the **middle of the photo's
    range**, not mid gray (changed while implementing: on ~50 of the 67 samples the white point is below mid gray, so
    "between mid gray and the white point" would have been empty). Highlights/whites move only pixels above the
    pivot, shadows/blacks only below it. The curve stays slope-based and monotone.
  - **Contrast** pivots on the same middle (user decision 2026-10-09; it was "unchanged" in the plan): around mid
    gray, which is above the median pixel of every sample, Contrast +100 turned a night shot almost black.
  - Strengths at ±100 (everything past the band moves by): whites 1, highlights 1, shadows 2, blacks 2.5 stops; local
    slope limited to ×1/8…×8. Checked on contact sheets of bright, dark, night and backlit samples.
  - `ENGINE_VERSION` → 2; synthetic golden images and the local real ones regenerated (unedited renders unchanged).
  - Tests: exact-math tests on synthetic ramps with known anchors (shift past each band, pivot fixed, untouched side,
    bands follow exposure, minimum range, slope limit), hypothesis (monotone, pivot fixed for any values and
    anchors), anchor measurement, catalog v3, renderer/library storage. The `@pytest.mark.golden` acceptance test
    changed from "≥ 5 % of the whole image" to **"≥ 25 % of the slider's own pixels change by ≥ 2 levels, leaving out
    pixels already black on screen"**: on night shots (≈ 97 % deep darks plus lights) only ~1 % of the frame is above
    the pivot, so a whole-image share can't measure Whites/Highlights; the deepest shadows of the darkest photos sit in
    the profile's toe, where one stop is a few levels. All 67 samples pass.
  - Full check re-run (pytest incl. golden, ruff, format, mypy, npm test/lint/build, e2e); README and docs updated.

### 🧑 Human test: Phase 3
0. Stop any running `photoedit ui`. Then `uv sync`, `npm --prefix ui install`, `npm --prefix ui run build`.
1. `uv run photoedit ui` → the Library (your catalog is upgraded automatically). Press **Open** on the `2026-08-11`
   folder (quick: nothing changed) → a "Render thumbnails" job runs (top bar / Jobs, about half a minute) and the
   thumbnails switch to the pipeline's default look. They should look very close to the camera JPEGs (Provia).
1b. Open a few photos and switch between **After** and **Camera JPEG**: colors, contrast and brightness match closely
   (small differences in sharpening, noise and the very corners are expected; `docs/default-look.md` lists the measured
   difference per photo).
2. Open a photo → the Adjust panel's sliders are live (geometry and Phase 9 ones stay disabled, labeled). Move
   **Exposure** → the preview updates within about half a second after you stop moving it (instant updates while
   dragging come in Phase 3b). Try every group: white balance (temperature/tint start at the as-shot values), tone,
   presence, tone curve (drag a point), HSL, color grading, vignette. Sharpening is only visible at 1:1 (Phase 6).
2b. (P3.24) On a few different photos (bright, dark, backlit, and a night shot such as DSCF5523), set **Whites**,
   **Blacks**, **Highlights**, **Shadows** each to −100 and +100 → every one visibly changes its part of the tonal range
   on every photo (on a night shot, Whites/Highlights act on the lights). **Contrast** ±100 adds or removes contrast
   without making the whole photo much darker or brighter. (The engine changed, so step 1's "Render thumbnails"
   job re-renders every thumbnail once; it also measures each photo's black/white points.)
3. **Before/After/Split** compare against the default look. Double-click a slider → it resets. **Reset all** works.
   Ctrl+Z / Ctrl+Shift+Z undo and redo.
4. Go back to the Library → the edited photo's thumbnail shows the edit. Restart `photoedit ui` → the edit is still there.
5. Extreme values (every slider at its end) never produce broken colors, black frames or errors.
6. `uv run photoedit contact-sheet DSCF5437` → open the images in `output/contact-sheets/`: each parameter at −/0/+
   looks like what its name says.
7. The `2026-08-11` folder is still unchanged (Explorer, Date modified). `uv run pytest -m golden` passes.
8. **Give feedback on the default look and on how each slider feels** (too strong, too weak, wrong direction).

### ⛔ STOP: user approves Phase 3

**Approved 2026-10-09.** Feedback from the human test: the tone sliders and the other groups work. Preview speed is
better but still has a delay; acceptable for now, because the user isn't planning to move sliders by hand yet, so
**Phase 3b is deferred** (moved below Phase 9, PLAN §0) and Phase 4 comes next.

## Phase 4: Styles

Goal: real styles. A style is a reusable look stored as data in `styles/<id>/`. It can be applied to one or many
photos (that writes edit JSON only), it adapts to each photo through adaptive rules, and per-photo tweaks stay on
top. The Styles screens, "Apply style…" and the Photo view's style controls work on real data. A hand-written test
style applied to the `2026-08-11` folder gives a consistent look. Export stays mock (Phase 5): "Apply & export"
applies for real and simulates the export.

Starting point (Phase 3): `PhotoEditFile` already has `style_id` (always `None` so far) and sparse dotted
`overrides`, stored as differences from the source defaults. The catalog has a `style_id` column, and the Library's
style filter uses it. Styles, sample images and apply jobs come from `mock/backend.py`. The `Style` model holds a full
`AdjustmentParams`, so it can't tell "sets contrast to 0" apart from "leaves contrast alone".

**Design** (decisions 2026-10-09, PLAN §0):
- **Effective parameters** = source defaults ← style values ← adaptive rule results ← per-photo overrides.
  Overrides are stored as differences from the styled values (defaults ← style ← rules), so moving a slider back to
  the style's value makes it follow the style again.
- **Live link**: a photo stores only `style_id`. The edit revision hashes the style's *look* (its values and rules,
  not its name or description), the rule results and the overrides. Changing a style re-revisions every photo that
  uses it and re-renders their thumbnails. Renaming a style doesn't.
- **Applying over tweaks**: overrides of parameters the style sets are dropped, and others (e.g. a crop) are kept.
  If the style's exposure or white-balance rule is active, it counts as setting `tone.exposure` or
  `white_balance.*`.
- **A style is sparse**: `values` is a dotted dict (`{"tone.contrast": -10, "hsl.green.saturation": -30}`). Setting a
  value equal to the default still counts as "sets it". Geometry is never part of a style (it's per photo), and
  later-phase parameters are rejected as in P3.1.
- **Adaptive rules** run per photo on numbers measured once per photo (like the tone anchors: 512 px, default
  render, stored in the catalog with the render identity), so renders stay deterministic:
  - `exposure`: `off` | `auto`. Auto adds `strength × (target − photo middle)` EV, limited to ±`max_change`. The
    "photo middle" is the median scene luminance in stops relative to mid gray, at exposure 0 with the profile
    baseline. The style's own `tone.exposure` is added on top.
  - `white_balance`: `as_shot` + offsets | `auto` (neutral estimate + offsets) | `fixed` (temperature/tint given in
    the rule). A style without a white_balance rule doesn't touch WB. `values` never holds `white_balance.*`
    (rejected: WB goes through the rule). Temperature offsets are given in Kelvin at 5500 K and applied as the
    equivalent mired shift, so "+400 K" looks alike under tungsten and daylight. (Changed in P4.2: `as_shot`
    takes the offsets, so a separate `as_shot_offset` mode wasn't needed.)
  - Rule outputs are limited by design (`max_change`, the parameter ranges) and the limits are documented. That isn't
    silent clamping of input (golden rule 5): invalid rule settings are still rejected.

**Inconsistent photos are the hard part** (the user's shooting, 2026-10-09; PLAN §0). The user exposes manually and
tweaks settings while shooting, so a series from one place can vary by a stop or more. The subjects vary widely:
rally/drift (fast, mixed light), a **black cat** (low-key: any "make the middle gray" metering turns it gray) and an
orange cat, and travel (cities, mountains, night). Phase 4 doesn't solve this fully, but it builds the ground for
iterating on it, in Phase 8 and with the AI in Phase 7:
- **Rules are an extensible list**: each rule is a typed, versioned entry (a discriminated union), run in a fixed
  order. A new rule or metering mode later = one model + one function + tests, with no format redesign.
- **Exposure metering modes**: `middle` (the median), `highlights` (puts the photo's white point at a target, so a
  low-key subject such as the black cat or a night street isn't pulled up to gray) and `camera_settings` (see the
  next point).
- **Even out a group**: applying a style to a selection can store a **group reference** in each photo's edit (the
  group's median of the chosen measure). The exposure rule then targets the group instead of a fixed number.
  With `camera_settings` metering, the measure is the photo's own exposure from EXIF (shutter, aperture, ISO → EV),
  so a series shot in steady light with changing settings is evened out exactly, and the picture content (a black
  cat filling the frame) can't fool it. The reference is stored, so renders stay deterministic and don't depend on
  what else is selected later.
- **A test set per style**: a style keeps a list of hard test photos (e.g. the black cat, a night street, a backlit
  rally shot). Samples, contact sheets and reports use it, so every iteration is checked on the same hard cases.
- **Measured consistency**: a report gives numbers for "consistent". It shows the spread of the output's middle
  brightness, white point and WB across a set, before vs. after the style, with each photo's measurements and rule
  results. Phase 7's AI and Phase 8's fitting can optimize against the same numbers.
- **Version history**: every saved style version is kept (`styles/<id>/history/v<N>.json`). The UI and CLI can diff
  two versions, compare them on the test set and revert, so trying a change costs nothing.

- [x] **P4.0** Detail this phase into items. ⛔ STOP for the user to review it. Reviewed and approved 2026-10-09.

### Decisions to confirm at phase start (ask the user)
- [x] **P4.1** Confirmed 2026-10-09 (recorded in PLAN.md §0): live link; applying replaces only the parameters the
  style sets; adaptive rules = auto exposure + WB relative to as shot + auto-neutral WB; styles managed in the UI.
  Still open, with defaults to confirm in the P4.0 review:
  - **Sample images rendered from your real photos stay local** (`styles/*/samples/` git-ignored, the same as the
    golden-image decision), and only `style.json` + `README.md` are committed. Say if they should be committed (the
    repo is pushed to GitHub).
  - **The 4 mock styles are removed.** Phase 4 ships two hand-written test styles (P4.12). Your real styles come in
    Phase 8.
  - **Auto exposure's default target** = the median "photo middle" of the 67 samples, so an average photo barely
    changes. It's measured in P4.4 and written into `docs/styles.md`.
  - **Even out a group** is a checkbox in "Apply style…", **off by default**. When it's on, the exposure rule targets
    the group's reference instead of the style's fixed target.
  - **Style sample folders** (given 2026-10-09, read-only; all X-T3 · Provia · DR100, so the existing profile fits).
    They're configured as `style_sample_dirs` in `config.local.toml` (a new list setting, also used by the
    `@pytest.mark.golden` tests) and imported into the catalog in P4.12 (where the test sets are chosen):
    - `2026-08-17`: orange cat + sunsets (6 photos; ISO 800, 1/60, EV spread 0.7 stops)
    - `2026-08-11`: both cats, orange and **black** (67; the existing sample folder; EV spread 6.9 stops)
    - `2026-07-26`: drift (113; old XF18-55 lens; 1/500–1/4000, ISO 1000/4000; EV spread 2.3 stops in one
      session, a good "even out" test).
    - `2026-08-16`: rally (183; new XF70-300 lens; f/9–14, **1/60–1/3195**: panning and freeze shots mixed, light
      changes between stages; EV spread 4.7 stops).
    - At car events the user can't get close, even with the longer lens, so **cars are often small in the frame**
      and the framing varies. Whole-frame metering then mostly measures the background, so nothing in Phase 4 may
      rely on the framing or on the subject filling the frame. Subject-weighted metering and subject-centered
      crops (Phase 6) matter here. Camera-settings evening-out only holds within a run of shots in the same
      light, so whole-folder grouping is left to later (see Phase 8).

    The test styles' test sets (P4.12) pick hard cases from all four folders: the black cat, the orange cat, a
    sunset, a backlit or night shot, drift shots at different settings, and rally panning vs. freeze shots.

### Core
- [x] **P4.2** Models (`models/style.py`, the API contract):
  - `rules`: a list of typed rules (discriminated by `type`, each with its own `rule_version`), at most one per
    type, evaluated in a fixed order:
    - `exposure`: metering `middle` | `highlights` | `camera_settings`; target −4…+4 stops (for `middle` /
      `highlights`); `use_group` (target the photo's stored group reference when it has one); strength 0…100;
      max_change 0…3 EV.
    - `white_balance`: mode, temperature_offset −3000…+3000 K, tint_offset −50…+50, temperature/tint (`fixed`
      only).
  - `RuleResults`: per rule, what it measured, its target and what it changed (e.g. "highlights metering: white
    point +1.8 → target +2.2, +0.4 EV"), for display and reports.
  - `Style`: `schema_version`, id (slug = folder name, fixed at creation), name, description, best_for, avoid_on,
    `values` (sparse dotted dict, validated by applying it to `AdjustmentParams`), `rules`, `test_photo_ids`
    (the style's hard cases), `samples` (photo id, caption, file names, the style `look_hash` they were rendered
    with), created_at/updated_at, `version` (+1 on every saved change), `change_note` (optional, one line per
    version), and `look_hash` (computed: values + rules).
  - `StyleSummary` adds `photo_count` and `cover_url`. `StyleView` adds `changed_parameters` (= `values`) and
    `samples_stale`.
  - `PhotoEdit` adds `style_values` (the dotted names the style sets, so the UI can mark them), `rules` (the photo's
    `RuleResults`) and `style_version`.
  - `ApplyStyleRequest.style_id` becomes nullable (`null` removes the style), and it adds `even_out` (bool, default
    off).
  - `ConsistencyReport`: per photo, its measurements (middle, white point, WB, camera EV) before and after, plus the
    rule results; per set, the spread (median absolute deviation and range) of each measurement, before vs. after.

  Tests: validation and ranges, WB values only in `fixed` mode, a duplicate rule type rejected, an unknown rule
  type or newer rule version → a clear error, geometry and later-phase names rejected, unknown names rejected, JSON
  round-trip, and `look_hash` ignores name, description, test set and timestamps.
  Done: `StyleView` is a flat API model (not a subclass of the stored `Style`) with sample URLs and `stale` flags;
  `PhotoEdit` also has `style_error` and `group` (`GroupReference`); `AdjustmentParams.with_values()` / `dotted()`
  handle dotted names. Later-phase names are rejected by core when a style is saved or used (P4.3/P4.5), because
  the list lives in the engine. The mock styles were adapted to the new format until P4.7 removes them.
- [x] **P4.3** `core/styles.py` `StyleLibrary` over `styles/` (all writes atomic and through the path guard):
  - list (a broken `style.json` is listed as broken with its error, so it doesn't break the list), get, create (id
    from the name; slug collision → `-2`, `-3`…), update (optimistic: `expected_version` mismatch → conflict error),
    duplicate, delete (removes the folder).
  - `schema_version` with a migration hook. A file from a newer version → clear error.
  - `README.md` is regenerated from `style.json` on every save (description, best for / avoid on, rules,
    parameter table). `style.json` is the source of truth.
  - **History**: every save also writes `history/v<N>.json`. Also `history(id)`, `version(id, n)`, `diff(id, a, b)`
    (changed values and rules) and `revert(id, n)` (saved as a new version, so nothing is lost).
  - A clock is injected for timestamps (not in the render path).

  Tests in `tmp_path`: CRUD, slug collisions, version conflict, a broken file, a newer schema, README content,
  history/diff/revert, and writes outside `styles/` refused.
  Done: saving samples (`set_samples`) is not a new version (samples are derived from the look). Duplicates copy
  the look, text and test set but not the samples. `ConflictError` maps to HTTP 409. Request models
  `StyleCreate`, `StyleUpdate`, `StyleDiff` and `StyleVersionInfo` live in `models/style.py`.
- [x] **P4.4** Photo measurements for the rules: extend the anchor measurement into `PhotoStats` (black, white,
  **middle** = median, and the **neutral WB estimate**: the temperature/tint that makes the photo's near-neutral
  midtone pixels gray, found in camera space and converted with `color.as_shot_temperature_tint`). One pass, the same
  512 px input. Catalog schema v4 adds `tone_middle`, `neutral_temperature`, `neutral_tint`, filled lazily and
  measured again when missing or when the render identity changes. Stored anchors keep their values (unedited renders
  don't change).
  Also the **camera exposure** of each photo: `EV100 = log2(N² / t) − log2(ISO / 100)` from EXIF aperture, exposure
  time and ISO (catalog v4 stores the exposure time as a number; existing rows are filled from the stored shutter
  text). `None` when EXIF is missing; `camera_settings` metering then falls back to `middle` and says so in the rule
  results.
  Tests: synthetic images with a known median and a known color cast (estimate within 100 K / 3 tint), EV100 math
  (known settings → known EV), catalog v4 migration, lazy fill. Golden: on the samples, the daylight shots' neutral
  estimate is near as-shot. Print the median-of-middles over all four style sample folders (369 photos) for P4.1's
  default target.
  Config: a `style_sample_dirs: list[Path]` setting (`config.example.toml` lists the four folders, commented).
  Golden tests skip a folder that isn't configured or present.
  Done. Neutral estimate: a gray world over midtones near gray, starting from the median color with a radius
  shrinking from 1.0 to 0.35 (log2 channel ratio), so a strong cast (tungsten on daylight balance) is found while
  saturated subjects drop out. It falls back to as shot when fewer than 2 % of midtones qualify or the result is
  no plausible light (outside 2500–12000 K or tint ±50: a frame filled by one colored subject).
  Measured on all 369 sample RAFs (half size, 5 min): middle median **−2.7** (p10 −5.2, p90 −2.0), white point
  median **−0.1** → `DEFAULT_EXPOSURE_TARGETS` (middle −2.7, highlights −0.1). Neutral − as shot: rally (daylight)
  median −251 K (80 % within −582…+137 K); drift +834 K (asphalt and smoke read bluish); 2026-08-11 down to
  −1800 K on the 06:00 sunrise shots (auto WB would remove the golden light, as expected: it's opt-in). As-shot
  fallbacks: 18/67, 28/183, 4/6. Measurements are filled lazily (every stored photo is measured again once, in
  one pass with the anchors, which keep their values).
  `Settings.photo_dirs` = sample + style sample folders, all protected by the path guard.
- [x] **P4.5** Resolving a style for a photo (`core/style_rules.py`, pure functions): `resolve(defaults, style, stats,
  as_shot) → (AdjustmentParams, RuleResults)`.
  - Exposure: style exposure + the auto delta, per metering mode: `middle` moves the median to the target;
    `highlights` moves the white point to the target; `camera_settings` (with a group reference) adds
    `photo EV100 − group EV100`, the exposure difference the photographer dialed in. With `use_group` and a stored
    group reference, the target is the reference.
  - White balance per mode. Offsets go through mireds, and the result is limited to the WB ranges.
  - Each rule is a function from (rule, stats, group reference) to (parameter changes, result). Adding one later
    doesn't touch the others.
  - Exact-math tests per rule and mode: strength 0/50/100, max_change limits, each metering mode (a dark-subject
    image: `middle` brightens it, `highlights` doesn't), camera EV differences (1/250 vs 1/500 at the same
    aperture/ISO → exactly 1 EV), the missing-EXIF fallback, offsets at 3200 K vs 5500 K, fixed mode, as_shot
    leaves WB `None`.
  - Hypothesis: any valid style + any stats → valid `AdjustmentParams`, deterministic.
  Done in `core/style_rules.py` (`resolve`, `RuleInputs`, `rule_parameters`): every limit or fallback is named in
  the rule result's `note`. Changed while implementing: `GroupReference` stores the group's medians of **all**
  measures (middle, white point, camera EV), so switching a style's metering mode later doesn't invalidate photos
  already evened out. Values and outputs are rounded (exposure 4 decimals, Kelvin 0.1, tint 0.01) so stored
  numbers and revisions don't carry float noise.
- [x] **P4.6** Edits with styles (`core/edits.py`):
  - `PhotoEditFile` adds an optional `group` (`GroupReference`: id, size, middle, white, camera_ev; written by
    "even out"), still schema v1
    (the field is optional and new).
  - `effective()` = defaults ← resolved style ← overrides. A missing or broken style → the photo renders as if
    unstyled, and `PhotoDetail` says why (it never crashes the Library).
  - `save()` stores overrides as differences from the styled values.
  - `apply_style(photo, style_id | None)` drops overrides of parameters the style sets (plus `tone.exposure` /
    `white_balance.*` when a rule covers them) and keeps the rest.
  - The revision hashes `look_hash` + rule results + overrides. Unstyled photos keep their Phase 3 revisions, so no
    cache churn.
  - The catalog's `style_id` is kept in sync.

  Tests: precedence, sparse overrides relative to the style, apply/replace/remove, slider back to the style value,
  revision changes on a look change but not on a rename, a missing style.
  Done. The revision of a styled edit hashes the resolved style parameters (look + rule results), so unstyled
  photos keep their Phase 3 revisions and nothing re-renders. Measurements are asked for only when the style has
  rules (measuring may decode). **Reset (DELETE /edit) now drops only the per-photo tweaks and keeps the style**;
  removing a style is its own action (P4.7). The catalog keeps `style_id` across re-imports (like the rating).
  When an applied style is switched, kept tweaks keep the value the photo showed.
- [x] **P4.7** Library operations (`core/styling.py`, next to `core/library.py`):
  - `apply_style(photo_ids, style_id | None, even_out=False)` as a real `APPLY_STYLE` job (each item writes one edit
    JSON), followed by the thumbnail job. With `even_out`, it first measures the selection, then stores the group's
    medians (middle, white point, camera EV) in each photo's edit. Applying without it clears the group.
  - `consistency_report(style_id | None, photo_ids)` → `ConsistencyReport`. The default set is the style's test
    set, otherwise the photos that use it.
  - `set_photo_style(photo_id, style_id | None)` (instant, for the Photo view).
  - Style changes (update / delete) re-revision the photos using the style and re-render their thumbnails. Delete
    sets them to no style and keeps their tweaks as absolute values.
  - `style_from_photo(photo_id, name, groups, exposure_mode, wb_mode)` creates a style from a photo's effective
    values (only what differs from the source defaults, never geometry). WB can be saved as an offset from the
    photo's as-shot. Exposure can be saved as "match this photo's brightness" (auto, target = this photo's resulting
    middle).
  - `update_style_from_photo(style_id, photo_id, groups)`, then re-saves that photo so overrides now equal to the
    style vanish.
  - `render_samples(style_id, photo_ids)` job: before = default look, after = with the style (no per-photo tweaks),
    1200 px JPEG q88, into `styles/<id>/samples/`.

  The mock styles leave `mock/backend.py`. Apply & export = a real apply + the simulated export.
  Tests on synthetic photos: every operation, jobs and their progress, thumbnails re-rendered, originals untouched.
  Done in a new `core/styling.py` (`Styling`; `library.py` was already 400+ lines). With "even out", items measure
  the photos and the edits are written together once the group is known. Apply & export returns the apply job;
  the simulated export job is submitted when it finishes. Samples are 1200 px previews (JPEG q90, the preview
  quality) rendered as a `render` job; a new rendering removes sample files no longer listed. The report measures
  "after" in scene terms (measurements moved by exposure and WB, before tone curves), so it shows what the rules
  did. `mock/images.py` is gone; the mock backend only serves presets and simulated exports. The existing GET
  style routes and `POST /api/jobs` already use the real code (the rest of the API follows in P4.8).

### API + CLI
- [x] **P4.8** Real style endpoints (replace the mock ones; `409` on a version conflict, `404`/`422` with clear
  messages):
  - `GET /api/styles`, `GET /api/styles/{id}`, `POST /api/styles` (create: blank, or from a photo with groups and
    modes), `PUT /api/styles/{id}` (text, values, rules; with `expected_version`), `POST /api/styles/{id}/duplicate`,
    `DELETE /api/styles/{id}`.
  - `POST /api/styles/{id}/from-photo` (update from a photo), `POST /api/styles/{id}/samples` (`photo_ids` → job),
    and `GET` sample images.
  - `GET /api/styles/{id}/history`, `GET /api/styles/{id}/versions/{n}`, `GET /api/styles/{id}/diff?a=&b=`,
    `POST /api/styles/{id}/revert`.
  - `POST /api/styles/{id}/report` (`photo_ids` optional → `ConsistencyReport`).
  - `PUT /api/photos/{id}/style` (`{style_id | null}` → `PhotoDetail`).
  - `POST /api/jobs` `apply_style` / `apply_and_export` become real.

  Regenerate `openapi.json` + `schema.d.ts`. Tests for every endpoint.
  Done: creating from a photo is `POST /api/styles/from-photo` (a separate path). Also `GET /versions/{n}` (a
  version as a `StyleView`), `POST /duplicate` (`{name?}`) and `DELETE` returns `{id, photos}`. Invalid style values
  are 400 with the reason (checked when the style is built); malformed bodies are 422. `DELETE /photos/{id}/edit`
  keeps the style (P4.6).
- [x] **P4.9** CLI:
  - `photoedit style list | show ID | check` (validates every style file)
  - `photoedit style apply ID [PHOTO…|--folder] [--even-out]` and `--remove`
  - `photoedit style samples ID PHOTO…`
  - `photoedit style contact-sheet ID [--test-set | --count 12] [--version N]`: a before/after grid (the test set,
    or photos of the current folder) into `output/contact-sheets/`, each tile labeled with its measurements and rule
    results. `--version` renders an older version, so two versions can be compared side by side.
  - `photoedit style report ID [PHOTO…]`: the consistency report as a table (and `--json`).
  - `photoedit style history ID`, `diff ID A B`, `revert ID N`.

  Tests with `CliRunner`.
  Done: removing is `photoedit style remove [PHOTO…]` (not `apply --remove`); photos default to the Library's
  current folder. The contact sheet (`core/style_sheet.py`) is one row per photo, labeled with its middle
  brightness before → after and every rule's result; `--version N` adds a column with version N. Found while
  testing: a hand-written `style.json` has no history, so the first change now saves the replaced version to
  `history/` too.

### UI
- [x] **P4.10** Styles screens on real data (the `DEMO DATA` tag leaves them):
  - Library cards: cover = the first "after" sample, else a placeholder; photo count.
  - Detail: inline editing of name, description, best for, avoid on; a rules editor (exposure auto: target,
    strength, max; WB mode and offsets); the parameter table with "remove from style"; samples with "Render from
    selection" and a "samples are from an older version" badge; Duplicate; Delete (the confirmation names the number
    of photos that drop back to no style); Apply to N selected; Show photos (opens the Library filtered to the
    style).
  - Rules editor: metering mode (with a one-line hint each, e.g. "highlights: for dark subjects such as a black
    cat or night streets"), "use group reference".
  - **Test set**: add/remove photos ("add selection"), shown as a before/after strip with each photo's rule results.
  - **Consistency** panel: the report for the test set (or the photos using the style), with spread before → after
    per measurement, and the photos furthest from the group highlighted (they need attention).
  - **History**: a version list with change notes, a diff of two versions, "compare on test set" (old vs. new
    renders side by side), and revert.
  - Saving asks for an optional change note and shows conflicts (another change came first) with a reload.
  Done: the detail page is split into sections (`features/styles/Style*.tsx`), each with its own edit/save, all
  through one save path (`useStyleSave`: `expected_version`, 409 → a "changed somewhere else" banner with Reload).
  Added `GET /api/styles/{id}/versions/{n}/photos/{photo_id}.jpg` (a photo with any version, no tweaks) for the
  test-set strips and "compare on the test set". "Show photos" opens `/library?style=<id>`. The Create style dialog
  now explains Save as style… (by hand) next to Phase 8's AI flow. Vite's chunk warning limit is 800 kB (local app,
  one bundle; 515 kB now).
- [x] **P4.11** Library + Photo view:
  - Library: "Apply style…" uses real styles and a real job (the export step is labeled "simulated until Phase 5"),
    plus the **Even out these photos** checkbox (off by default; its hint explains when it helps, e.g. "a series shot
    in the same light with changing settings"). A "Remove style" action. Real style badges and filter.
  - Photo view Adjust panel: a style picker at the top (applies immediately); sliders whose value comes from the
    style get a marker; a line showing the rule results ("Auto exposure +0.62 EV · WB as shot +400 K");
    "Save as style…" (name, groups with the number of changed values in each, exposure and WB modes);
    "Update style from this photo" (choose groups, confirm "changes N photos").
  Done. Also: double-clicking a slider (or a group reset) on a styled photo goes back to the **style's** value
  (`PhotoEdit.defaults` is now "what a reset goes back to": the styled values; new `PhotoEdit.unedited` is the
  Before look, used to count changed values per group). Save as style… can use the new style for the photo right
  away (on by default). The panel restarts its edit session when the photo's style or style version changes. When
  an apply job finishes, photos and styles refresh app-wide (`useRefreshAfterJobs` in the layout). "Remove style"
  is enabled when the selection has a styled photo.
- [x] **P4.12** Two hand-written test styles, committed in `styles/` (only `style.json` + generated `README.md`):
  - `test-warm-matte`: auto exposure (`middle` metering, use group); WB as shot +400 K; lower contrast, lifted
    blacks (tone curve), highlights −30; greens toned down; warm highlight / cool shadow grading; a light vignette.
  - `test-classic-bw`: auto exposure (`highlights` metering), saturation −100, strong contrast, deep blacks.

  Their test sets are 8–10 photos chosen across the four style sample folders (P4.1): black cat, orange cat,
  sunset, backlit/night, drift at two settings, rally panning and freeze. Render their samples locally,
  run the report and the contact sheet over the whole folder, and record the before → after spread in
  `docs/styles.md`. That file documents the format, precedence, rules and metering modes (when to use which, with
  the black-cat and manual-series cases), the measured default target, how to write a style by hand, and **how to
  iterate on a style**: edit → contact sheet / report on the test set → compare versions → keep or revert.
  Done 2026-10-09. The four folders are imported (369 photos) and measured. Test set: DSCF5580/5601 (black cat lit /
  dark), 5574/5598/6283 (orange cat close / lamp / night), 6286 (sunset), 5323/5414 (drift 1/2000 ISO 1000 vs.
  1/4000 ISO 4000), 6033 (rally dust), 6278 (tree against the sun). The rally folder has no panning shots (its
  1/60–1/125 frames are a parked car), so the into-the-sun shot stands in as the hard rally-day case. Results are in
  `docs/styles.md`: middle metering takes the middle spread to 0 on the drift, rally and sunset folders; the cats
  folder's 40 very dark indoor shots hit the 1.5 EV limit (a case to tune). The styles were created through the
  library (README + history) from hand-chosen values. Slugs now join "&" and apostrophes ("B&W" → `bw`).
  `styles/*/samples/` is git-ignored.
- [x] **P4.13** Tests:
  - Vitest: style detail editing, the rules editor, test set, consistency panel, history/diff/revert, delete
    confirmation, conflict handling, the Photo view style picker, Save as style, update-from-photo, the apply wizard
    with a real job and "even out".
  - Playwright on the e2e photos (the generator adds a deliberately under- and overexposed copy of one scene, to
    stand in for a manual series): create a style from an edited photo → apply it to the folder with "even out" →
    the thumbnails change and the report's spread shrinks → edit the style → the thumbnails change again → revert →
    delete. Screenshots.
  Done: 85 Vitest tests (Styles screens, Photo view style controls, Library remove/filter, wizard even out) and 5
  Playwright tests. The e2e server now also uses `output/e2e/styles` (seeded with "E2E Moody"), so it never touches
  the real `styles/`; e2e photos carry exposure EXIF, plus a 2-stop-darker and a 1-stop-brighter shot of scene 1.
  Fixed from the screenshots: the Photo view's style picker was squeezed by its buttons (now its own row); a rule
  summary showed "-0.00 EV".
- [x] **P4.14** Full check (pytest incl. `-m golden`, ruff, format, mypy, npm test/lint/build, e2e) and update README.
  Done 2026-10-09: pytest 565 passed (+ 13 golden, 8 min), ruff, format, mypy clean; Vitest 85 passed, oxlint
  clean, build OK; Playwright 5 passed. README: status, Styles section, style CLI, config, layout.

### 🧑 Human test: Phase 4
0. Stop any running `photoedit ui`. Then `uv sync`, `npm --prefix ui install`, `npm --prefix ui run build`.
1. `uv run photoedit ui` → **Styles** shows the two test styles (no `DEMO DATA` tag), each with sample before/after
   images and a parameter table. The catalog upgrades on its own, and the first render of each photo measures its
   middle brightness and neutral WB.
2. Library (`2026-08-11`) → select all → **Apply style…** → **Test · Warm Matte** → apply without export → a job
   runs and the thumbnails switch to the style. They look **consistent** across bright, dark and backlit shots
   (auto exposure evens them out). Night shots get brighter only within the style's max change.
2b. Open the drift folder (`2026-07-26`) → select a run of shots in the same light with different settings → apply
   with **Even out these photos** → their brightness matches more closely than without it. In `2026-08-11`, on the
   black cat, **highlights** metering keeps it black, while **middle** pulls it toward gray (switch the rule in
   the style and compare). In the rally folder, a panning shot and a freeze shot of the same stage come out alike.
2c. Style detail → **Consistency** → the spread after the style is smaller than before, and the photos furthest
   from the group are highlighted. Change a rule, save with a note, then **History** → compare the two versions on
   the test set → **revert**.
3. Open a styled photo → the Adjust panel shows the style, marks the style's sliders, and shows "Auto exposure …".
   Move **Exposure** → it becomes a per-photo tweak. Re-apply the style → that tweak is replaced (the style sets
   exposure), but any other tweak remains.
4. Styles → Warm Matte → change contrast or a rule (e.g. WB offset +800 K) → save → every photo using it updates
   (thumbnails re-render). Renaming the style doesn't re-render anything.
5. Edit a photo by hand → **Save as style…** (pick groups, "match this photo's brightness") → apply the new style to
   other photos → they take on its look and brightness. **Update style from this photo** works and says how many
   photos change.
6. Style detail → **Render from selection** → new samples appear. Change the style → the "older version" badge shows.
   **Duplicate** then **Delete** the copy → the confirmation says how many photos it affects, and those photos fall
   back to no style with their own tweaks kept.
7. Library filter **Style: Warm Matte** shows exactly the styled photos. Restart `photoedit ui` → everything is
   still there.
8. `uv run photoedit style contact-sheet test-warm-matte --test-set` → `output/contact-sheets/` shows labeled
   before/after pairs. `uv run photoedit style report test-warm-matte` prints the spread table.
   `uv run photoedit style check` → all styles valid.
9. The `2026-08-11` folder is unchanged (Explorer, Date modified). `uv run pytest -m golden` passes.
10. **Give feedback** on the rules (does auto exposure feel right? WB offsets?) and on the style screens.

### ⛔ STOP: user approves Phase 4

**Approved 2026-10-10.** The user inspected and applied styles in the human test; no change requests.

## Phase 5: Export (outline)
- [ ] **P5.0** Detail this phase. ⛔ STOP for review.
- [ ] Resize modes, aspect crop, color space + embedded ICC, output sharpening, metadata policies, naming templates, collision handling.
- [ ] Parallel batch export job with progress, cancellation, and the path guard for destinations.
- [ ] Export tests: dimensions, ICC, EXIF, names. The UI Export dialog goes live.
- 🧑 Human test + ⛔ STOP.

## Phase 6: Geometry & centering (outline)
- [ ] **P6.0** Detail this phase. ⛔ STOP for review.
- [ ] Crop / rotate / straighten / flip / zoom in the pipeline. Subject detection (faces + saliency). `suggest_crop(aspect)`.
  Must handle small, off-center subjects (rally/drift cars shot from far away, often with panning blur) and cats
  (incl. a black cat on dark backgrounds); test on the style sample folders.
- [ ] Crop overlay in the Photo view.
- [ ] 1:1 zoom view (full-resolution crops of the visible area) so sharpening can be judged (deferred from Phase 3,
  2026-10-09).
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
- [ ] Series detection for inconsistent shoots (from Phase 4's preparation): split a folder into runs of shots in
  the same light (capture-time gaps + scene similarity), so "even out" works per series on a whole folder (e.g. a
  rally day with panning and freeze shots across stages). Subject-weighted metering once Phase 6 detects subjects
  (cars are often small in the frame: the user can't get close at rally/drift events).
- 🧑 Human test + ⛔ STOP.

## Phase 9: Polish (outline)
- [ ] **P9.0** Detail this phase together with the user's feedback list. ⛔ STOP for review.
- [ ] Performance tuning, clarity/texture/dehaze, noise reduction, lens corrections, more formats, UI refinements.
- 🧑 Human test + ⛔ STOP.

---

## Phase 3b: Live preview speed (deferred 2026-10-09)

Deferred after the Phase 3 human test: the AI drives the edits, and manual slider use can wait (PLAN §0). The
detail below stays as written; when resumed, re-measure first (the engine changed in P3.24), update it, and start
with P3b.0's review. It may be folded into Phase 9 (performance tuning).

Goal: slider changes show **instantly**, like Lightroom: the image follows the mouse while dragging, and the exact image
settles within about half a second of release. Added 2026-10-09 after the Phase 3 human test (PLAN §0, §4.3).
Branch `phase-3b-live-preview` from `main` when resumed.

Measured 2026-10-09 (DSCF5437, 1600 px, this machine):
- A 2 s drag in the UI: **nothing renders while the slider moves**. The edit is saved only after 200 ms without motion,
  and only then is a new preview requested. Final image 0.6 s after release. Every pause also refreshes the photo list
  and re-renders the filmstrip thumbnail. Superseded previews keep rendering on the server (they can't be cancelled),
  so a stop-and-go drag piles up work.
- The first edit of a freshly opened photo also waits for the RAW decode (2.6 s).
- Render 0.38–0.45 s at 1600 px. CPU time per stage (single thread): color_adjust 460 ms (always runs, because the
  X-T3 profile has HSL tweaks), output_srgb 224 ms, base_curve 149 ms, to_display 81 ms, sharpen 52 ms. JPEG
  `optimize=True` costs +30 ms (q90: 43 ms vs 12 ms).

Approach: **A** = make the server path responsive (drafts while dragging, latest-wins, save on release). **B** = the
instant path: `core` turns the per-pixel part of the pipeline into a 3D LUT, and the browser applies it to the photo's
linear base in WebGL. Vignette and sharpening aren't per-pixel color functions, so they stay on A's drafts. The exact
CPU render stays the source of truth; exports never use the LUT.

- [ ] **P3b.0** Review this detail. ⛔ STOP for the user.

### A: responsive server path
- [ ] **P3b.1** Benchmark first: `photoedit benchmark preview PHOTO` times the render per stage at 1600/800 px, the JPEG
  encode, and (after P3b.6) the LUT build. Record the baseline in `docs/benchmark.md` so every later item is measured
  against it.
- [ ] **P3b.2** Draft renders: `POST /api/photos/{id}/render` takes the full `AdjustmentParams` and a size, validates
  them like a save (later-phase parameters still rejected), and returns a JPEG. Nothing is saved, nothing is written to
  disk, `optimize` is off. Core: `Library.render_draft()`. Regenerate the TS types.
- [ ] **P3b.3** UI drafts: while a slider or curve point moves, request drafts continuously at a draft size (~800 px,
  chosen from P3b.1), **at most one request in flight**: when it returns, send the newest parameters if they changed
  (latest-wins, so nothing piles up on the server). Show each draft as soon as it arrives. On release: one save (PUT),
  then the full 1600 px preview replaces the draft without flicker. Refresh the photo list and filmstrip thumbnail only
  after the save. Undo/redo and keyboard/numeric entry behave as before.
- [ ] **P3b.4** First open: show the cached preview at once, decode the linear base in the background when a photo
  opens (not on the first slider move), and prefetch the previous/next photo's base (the LRU holds 8).
- [ ] **P3b.5** Faster CPU render (this helps the release render, thumbnails and exports too). Target ≤ 0.2 s at 1600 px
  for a busy edit. Candidates: fuse the OKLab conversions and matrices in `color_adjust`, a cube-root and sRGB-encode
  via lookup tables, skip passes for neutral groups, fewer float temporaries. Keep the strip-parallel result
  bit-identical; any pixel change bumps `ENGINE_VERSION` and regenerates the golden images.

### B: instant GPU preview (3D LUT)
- [ ] **P3b.6** `core/render/lut.py`: `build_lut(base, params, profile, size)` runs the **same stage functions** as
  `render` (white balance → profile → exposure → tone → base curve → curves → color → output encoding) on an N³ grid
  of input colors. Inputs are the base's camera-space linear RGB through a log2 shaper (range chosen to cover the base
  images, below-range values clamp). N = 33 or 65, chosen by measurement (accuracy vs. build time; target ≤ 30 ms).
  Deterministic. Tests: at grid points the LUT equals `render` of those colors exactly; neutral grays stay neutral;
  `@pytest.mark.golden`: LUT preview vs. exact render on the sample RAFs (vignette and sharpening off) within ΔE2000
  mean ≤ 1, p99 ≤ 3.
- [ ] **P3b.7** API for the browser (binary, documented in OpenAPI, metadata as Pydantic models):
  - `GET /api/photos/{id}/base?size=1600`: the linear base, shaper-encoded, as float16 RGB with a small header (size,
    shaper range, render identity). In-memory cache; cacheable by the browser per render identity.
  - `POST /api/photos/{id}/lut`: `AdjustmentParams` → the LUT (float16 RGB, N³) plus its header. Validated like a save.
- [ ] **P3b.8** UI `GpuPreview` (WebGL2): upload the base once per photo as a texture and each LUT as a 3D texture with
  linear filtering. The shader does only the lookup (no editing math in TypeScript). Before/Split use the default
  edit's LUT. While dragging a per-pixel slider: request LUTs with the same latest-wins rule as P3b.3; vignette and
  sharpening sliders use P3b.3's drafts. After release, the exact render swaps in. Without WebGL2 (or if a LUT
  request fails): fall back to drafts and say so once.
- [ ] **P3b.9** Tests: Python (LUT exactness, binary formats, validation errors, render identity in the headers);
  Vitest (latest-wins scheduler, draft/LUT/exact swapping, the WebGL2 fallback, with WebGL mocked); Playwright: drag
  Exposure → the canvas changes while the mouse is still moving, and the exact image arrives after release
  (screenshots).
- [ ] **P3b.10** Measure in the real UI and document in `docs/benchmark.md` ("Live preview"): time from a slider move to
  new pixels (GPU path target ≤ 50 ms; draft path), time from release to the exact image (target ≤ 0.6 s), first open
  of a photo. If a target is missed, ⛔ STOP and discuss before going on.
- [ ] **P3b.11** Full check (pytest incl. `-m golden`, ruff, format, mypy, npm test/lint/build, e2e) and update README.

### 🧑 Human test: Phase 3b
0. Stop any running `photoedit ui`. Then `uv sync`, `npm --prefix ui install`, `npm --prefix ui run build`, and
   `uv run photoedit ui`.
1. Open a photo you haven't opened in this session → its preview shows at once (no long spinner).
2. Drag **Exposure** slowly, then fast, back and forth → the image follows the mouse with no visible delay. Release →
   within about half a second the image may sharpen slightly (the exact render), but the colors don't jump.
3. Same for temperature/tint, contrast, highlights/shadows/whites/blacks, saturation/vibrance, an HSL band, a color
   grading wheel, and a tone curve point.
4. Drag **Vignette** amount → updates several times per second while dragging (server drafts), exact after release.
5. Before / Split while editing work and stay fast. Ctrl+Z / Ctrl+Shift+Z still undo and redo whole drags.
6. Next/previous photo, then edit right away → no 2–3 s wait on the first slider move.
7. Library → the edited photo's thumbnail shows the edit. Restart `photoedit ui` → the edits are still there.
8. `docs/benchmark.md` "Live preview" numbers look plausible to you.

### ⛔ STOP: user approves Phase 3b
