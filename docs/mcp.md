# MCP server (Claude)

How Claude drives PhotoEditor (Phase 7). The code is in `src/photoedit/mcp/`: `server.py` (instructions, `ping`),
`common.py` (registration, photo references, errors) and one module per group of tools. The tools are thin: each
one turns its arguments into a core call and the result into structured output, an image or a short text, like the
HTTP routes. Every rule (ranges, read-only originals, write boundaries) is enforced by the core, so the AI can't get
around one; it gets the error message instead.

## Setup

The server runs **inside `photoedit ui`**, at **`http://127.0.0.1:8765/mcp`** (MCP Streamable HTTP; decided
2026-10-15, PLAN.md §0). The AI and the web UI share one set of services: the catalog, the caches, the job queue
(one export at a time) and the change events the UI follows.

1. Start the server: `uv run photoedit ui` (or `--no-browser`). Leave it running.
2. Check it: `uv run photoedit mcp check` lists the tools (exit 1 and "Start it with: photoedit ui" if nothing
   answers; `--port` for another port, with the `.mcp.json` entry to use).
3. Start Claude Code in this folder. `.mcp.json` registers the server (`photoedit`, type `http`); approve it when
   Claude Code asks. `/mcp` shows it connected.

If `photoedit ui` wasn't running when the Claude Code session started, Claude Code lists the server as failed:
start it, then reconnect it in `/mcp`. To call a tool by hand (the way Claude does, so the UI shows a toast):

```bash
uv run python scripts/mcp_call.py set_note '{"photo": "DSCF5437", "text": "checked"}'
```

## How Claude is meant to work

The server sends these instructions on connect (`INSTRUCTIONS` in `server.py`):

- Start with `library_status`. Photos are named by file name (`DSCF5437` or `DSCF5437.RAF`), `folder/name` when a
  name is in several folders, or id (or its first 8+ characters). Tools that take several photos also take a
  `folder` (all its photos). An ambiguous or unknown name is an error listing the matches.
- Look before and after a change: `render_preview` (an image) and `analyze_photo` (numbers). Both can show unsaved
  `changes` first; `update_adjustments` saves only the values given.
- A series: `apply_style` (or `update_adjustments` on a folder) → `get_job` → `contact_sheet`.
- Export: `plan_export`, then `export_photos`. When subjects decide the framing (Instagram crops), `prepare_export`
  so doubtful photos go to the user's review (Check) instead of guessing.
- Long work returns a job: `get_job` with `wait_seconds` (≤ 120) returns when it ends.
- `set_note` explains a change or a judgment to the user (AI Analysis tab).

## Tools (49)

Read-only tools carry the MCP `readOnlyHint`; nothing is open-world (everything happens on this machine).

**Library and seeing** (`tools_library.py`)

| Tool | What it does |
|---|---|
| `ping` | Version and the open folder's photo count. |
| `library_status` | Imported folders, the one the user has open, running jobs, the render engine. |
| `import_folder(folder, include_subfolders)` | Import (read-only) and open a folder; a job. |
| `open_folder(folder)` | Show an imported folder in the user's Library. |
| `list_photos(folder?, style?, min_rating, sort, order, offset, limit ≤ 200)` | A page of photos. |
| `get_photo(photo)` | EXIF, style, adjustments (own tweaks marked), values before them, rule results, note. |
| `render_preview(photo, size 256–1600, changes?, before)` | JPEG of the edit, of unsaved `changes`, or the default look. |
| `contact_sheet(photos/folder, offset, limit ≤ 24, size 160–480)` | One labeled image of several photos. |
| `analyze_photo(photo, changes?)` | Lightness histogram and percentiles, clipping, color cast, HSL bands, tone stats, subject. |

**Edits** (`tools_edit.py`)

| Tool | What it does |
|---|---|
| `update_adjustments(changes, photos/folder)` | Change only the given values (nested patch; `null` = back to the style or default). All photos are checked before any is saved. |
| `set_adjustments(photo, adjustments)` | Replace the whole set. |
| `reset_adjustments(photos/folder)` | Drop the photos' own tweaks (the style stays). |
| `set_geometry(photo, change)` | Crop, straighten, aspect lock, quarter turn, flips. |
| `suggest_crop(photo, aspect, orientation, placement, zoom)` | A subject-framing crop in the current framing; nothing saved. |
| `get_subject(photo)` / `set_subject(photo, box?)` | The main subject (detected now if needed) / set by hand or back to detected. |
| `detect_subjects(photos/folder)` | Detection as a job. |
| `set_note(photo, text?)` | Claude's note for the user (≤ 2000 characters); `null` removes it. |

**Styles** (`tools_styles.py`)

| Tool | What it does |
|---|---|
| `list_styles`, `get_style(style, version?)` | The style library; one style (or an older version). |
| `create_style(request)`, `create_style_from_photo(request)` | A new style from values and rules, or from a photo's look. |
| `update_style(style, update)`, `update_style_from_photo(style, request)` | Change a style (`expected_version` guards against overwriting a newer one). Its photos follow. |
| `duplicate_style(style, name?)`, `revert_style(style, version, expected_version)` | A copy; an older version back as a new one. |
| `apply_style(style?, photos/folder, even_out)` | Give photos a style (`null` removes it); a job. |
| `style_report(style, photos/folder?)`, `style_history`, `style_diff(style, a, b)` | Consistency, versions, changes. |
| `render_style_samples(style, photos ≤ 12)` | Before/after samples; a job. |

**Export, review, jobs** (`tools_export.py`)

| Tool | What it does |
|---|---|
| `list_export_presets`, `get_export_preset(preset)` | Presets with their settings. |
| `create_export_preset(request)`, `update_export_preset(preset, update)` | Custom presets (built-ins stay read-only). |
| `plan_export(destination, photos/folder, preset?, settings?)` | What an export would write; nothing is written. |
| `export_photos(...)` | The export job. |
| `prepare_export(..., style?, even_out)` | A pre-export review (job → `review_id`), shown under Reviews. |
| `list_reviews`, `get_review(review)` | Open reviews; one review with every photo's status and reasons. |
| `update_review_item(review, photo, update)`, `set_review_subject(review, photo, update)` | Zoom, position, approve; choose the subject. |
| `review_preview(review, photo)` | The photo as the export will frame it. |
| `export_review(review, scope)` | Export approved (or all) photos of a review. |
| `get_review_settings`, `set_review_settings(settings)` | The review rules. |
| `list_jobs`, `get_job(job, wait_seconds ≤ 120)`, `cancel_job(job)` | Jobs. |

**Not available to the AI** (decided 2026-10-15): deleting styles or presets and discarding reviews; the user does
that in the UI or the CLI. Exports go only to the folder the call names, checked like the UI's: never inside a photo
folder or the tool's own folders. Claude Code's permission prompt shows the destination.

## Live updates in the UI

Every write in the core publishes a change event (P7.8) tagged with its origin: `ui` (HTTP), `ai` (MCP tools) or
`cli`; jobs carry the origin of whoever started them. `GET /api/events` streams them as server-sent events. The UI
(`useLiveUpdates`) refetches what each event touches, once per burst, reconnects after a dropped stream and
refetches everything after missed events. Changes with origin `ai` show a toast ("Claude edited DSCF5437.RAF",
"Claude edited 24 photos · changed style Warm film") with a link. The Photo view's sliders take over an edit saved
elsewhere as an undo step, so Ctrl+Z takes Claude's change back (while the Adjust tab stays open).

## SDK notes (`mcp` 2.3.0)

- `FastMCP` from SDK 1.x is **`MCPServer`** in 2.x (`from mcp.server.mcpserver import MCPServer, Image`).
- **Mounting**: `server.streamable_http_app(streamable_http_path="/mcp", host=...)` returns a Starlette app with a
  single route; its routes are added to the FastAPI app **before** the UI's catch-all `GET /{path}` route (the MCP
  stream's `GET` would otherwise get the UI's HTML). The route isn't an `APIRoute`, so it stays out of OpenAPI.
  `server.session_manager.run()` wraps the app's lifespan; a session manager runs once, so every app builds its own
  server.
- **Transport security**: for host `127.0.0.1`/`localhost`/`::1` the SDK checks the `Host` and `Origin` headers
  (allowed: those hosts on any port). A request from a web page on another origin gets **403**, so a page can't
  reach the tools through DNS rebinding. (A non-local `host` in the config turns the check off.)
- **Tools** are typed Python functions; the input schema comes from the signature (Pydantic `Field` ranges are in
  it), the description from the docstring. A Pydantic return type gives an output schema and `structuredContent`.
  `Image(data=..., format="jpeg")` gives an image block. Sync functions run in a worker thread.
- **Output schemas** are generated in validation mode and clients check results against them, so a model with a
  computed field needs `json_schema_mode_override="serialization"` (`ExportReview.counts`).
- **Errors**: arguments that fail the input schema come back as a tool error with Pydantic's message. Inside a
  tool, only `ToolError` keeps its message; any other exception reaches the model as just "Error executing tool".
  So every tool is registered through `common.tool()`, which turns the core's expected errors (not found, invalid,
  conflict, write refused, decode and model-file errors, validation) into `ToolError`s.
- **Testing**: `mcp.Client(server)` connects in-process, `mcp.Client("http://…/mcp")` over HTTP
  (`tests/helpers.serve` runs the app under uvicorn on a free port). `tests/test_mcp_tools.py` covers every tool
  with valid and invalid input, `tests/test_mcp_session.py` a whole session.
