# CLAUDE.md: rules for AI working on PhotoEditor

Read [PLAN.md](PLAN.md) (what and why) and [TODO.md](TODO.md) (what's next) before doing anything.

## Golden rules (never break these)

1. **Originals are read-only.** Never write to, rename, move or delete a source photo, and never write next to it.
2. **Write boundaries.** Write only inside the tool-owned folders (`workspace/`, `styles/`, `export-presets/`, `output/`,
   `cache/`) or into an export destination the user chose explicitly. Every file write in `src/` goes through
   `photoedit.safety.PathGuard.assert_writable()`.
3. **Deterministic rendering.** The same input, edit and engine version must always produce the same output. No randomness
   without a fixed seed, and no wall-clock or environment-dependent behavior in the render path.
4. **One core, many front-ends.** Logic lives in `photoedit.core` (and `config`, `safety`, `models`). The CLI, HTTP API, MCP
   server and UI only translate requests and responses. They never re-implement rules.
5. **The code enforces the rules.** All data (styles, edits, presets, API payloads) is a Pydantic model with explicit ranges.
   Invalid input is rejected with a clear message. It is never silently clamped or guessed.

## Workflow

- Work **phase by phase** following TODO.md. Do items in order, and tick `[x]` only when the code, its tests and every check are green.
- ⛔ **STOP** markers in TODO.md mean: halt and wait for the user's explicit go-ahead.
- Each phase ends with a 🧑 human test script. The user runs it and confirms. Requested tweaks are made before merging.
- **When in doubt, ask.** Don't guess at requirements. Plan changes go into PLAN.md first (with a decision date in section 0).
- Each later phase starts by expanding its outline in TODO.md into detailed items, then stops for the user to review them.

## Git (PLAN.md §8.1)

- One branch per phase: `phase-<N>-<short-name>`, created from an up-to-date `main`. Commit on it freely.
- Commit messages start with the TODO item ID(s): `P1.6: Library grid with multi-select`.
- Merge into `main` with `--no-ff` **only after the user confirms the phase**. Never commit phase code directly to `main`.
- Push the phase branch as a backup while working. Push `main` right after each confirmed merge.
- Identity: `SigitasAmbrozaitis <ambrozaitis.sigitas@gmail.com>` (repo-local config). Never the global `cyam` identity.
- End commit messages with `Co-Authored-By: Claude <noreply@anthropic.com>` (adjust the model name).

## Commands

```bash
# Python (from the repo root)
uv sync                       # install / update the environment
uv run pytest                 # tests (add -m "not slow" to skip long ones)
uv run ruff check             # lint
uv run ruff format            # format
uv run mypy                   # strict type check of src/
uv run photoedit --version
uv run photoedit config show
uv run photoedit ui           # backend + built UI on http://127.0.0.1:8765

# UI (from ui/)
npm install
npm test                      # Vitest
npm run lint                  # oxlint
npm run build                 # type-check + production build into ui/dist
npm run dev                   # dev server http://localhost:5173 (proxies /api to :8765)
npm run gen:api               # after any API/model change: regenerate openapi.json + src/api/schema.d.ts
npm run test:e2e              # Playwright smoke test (installed Chrome; needs `npm run build` first);
                              # screenshots of every screen go to output/screenshots/

# Both at once with hot reload
scripts\dev.cmd
```

All of these must be green before an item is ticked: `pytest`, `ruff check`, `ruff format --check`, `mypy`, `npm test`,
`npm run lint`, `npm run build` (and `npm run test:e2e` at the end of a phase that touches the UI).

API contract: Python models in `photoedit.models` are the source of truth. After changing them or any route, run
`npm run gen:api`; tests fail if `ui/openapi.json` or `ui/src/api/schema.d.ts` are stale.

Claude's browser previews (`.claude/launch.json`) use ports 8766/5174 so they never clash with the user's own
`photoedit ui` on 8765.

## Layout

```
src/photoedit/
  cli.py        Typer CLI (thin)
  config.py     Settings: defaults < config.local.toml < PHOTOEDIT_* env < explicit overrides
  safety.py     PathGuard: write-boundary enforcement
  models/       Pydantic data models = the API contract (photos, adjustments, styles, export, jobs)
  api/          FastAPI app + routes (thin); serves ui/dist
  core/         all real logic (library, edits, render, styles, export); core/presets.py = built-in presets
  mock/         Phase 1 fake backend (replaced piece by piece from Phase 2)
  mcp/          MCP server for Claude (Phase 7)
tests/          pytest; mirrors src/
ui/             React + TypeScript web UI (src/features/<screen>/, src/api/ generated types + query hooks,
                src/components/ shared UI, src/test/ fake API + fixtures, e2e/ Playwright)
scripts/        dev helpers
```

## Code conventions

- Python 3.12, full type hints, `mypy --strict` clean. Use `pathlib.Path`, never string paths.
- Pydantic v2 models for all data crossing a boundary (files, API, MCP).
- Tests: unit tests for every module. Image math is tested on small synthetic arrays with exact expected values. Tests that
  need real RAW files are marked `@pytest.mark.golden`, and long ones `@pytest.mark.slow`.
- Tests write only into `tmp_path`, never into the real project folders or photo folders.
- UI: function components and hooks, strict TS, no `any`. Every screen gets a Vitest + Testing Library test.
- Match the surrounding code's style and comment density. Comments explain *why*, not *what*.

## Local machine notes

- Sample photos: `C:\Users\ambro\Pictures\2026\2026-08-11` (Fujifilm X-T3 `.RAF` files plus camera `.JPG`s). **Read-only.**
  The path is configured in `config.local.toml` (git-ignored; copy it from `config.example.toml`).
- Style sample folders (Phase 4+, all X-T3 RAF + JPG, **read-only**), under `C:\Users\ambro\Pictures\2026\`:
  `2026-08-17` orange cat + sunsets, `2026-08-11` both cats (orange and black), `2026-07-26` drift, `2026-08-16` rally.
- Large files (RAWs, exports, caches) are git-ignored and must never be committed.
