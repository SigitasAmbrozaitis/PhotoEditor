# PhotoEditing Tool: Implementation Plan (v0.3)

> Status: **All decisions made (section 0). Waiting for final approval.**
> After the plan is approved, it gets split into an AI-followable `TODO.md`, one block per phase.

## 0. Decisions so far

| Topic | Decision | Date |
|---|---|---|
| AI mode | **MCP server used from Claude Code** (no API key) | 2026-10-07 |
| Style input | **Both**: finished photos (approximate look) and RAW + edited pairs (numerical fit). Fallbacks in section 4.5.1 | 2026-10-07 |
| Backend language | **Python 3.12** (stack as in section 3) | 2026-10-07 |
| Engine | **Own pipeline on LibRaw (rawpy). No RawTherapee.** | 2026-10-07 |
| UI | **Python backend (FastAPI) + web UI (React/TS)** | 2026-10-07 |
| Phase order | **UI skeleton early** (clickable, mock data, no functionality); each later phase wires its part of the UI | 2026-10-07 |
| Sample photos | `C:\Users\ambro\Pictures\2026\2026-08-11`: 67 × Fujifilm **X-T3** `.RAF` (26 MP X-Trans), each with a camera `.JPG`. **Read-only.** | 2026-10-07 |
| Style samples | **No style yet. At the style-creation phase, STOP and ask the user for style samples.** | 2026-10-07 |
| Lightroom import | **Not needed** (fallback F4 dropped) | 2026-10-07 |
| Folder layout | **Tool + its data (workspace, styles, presets) live in `C:\Work\PhotoEditing`. Photos and exports live in other folders.** During development, test exports go to `C:\Work\PhotoEditing\output\` (git-ignored). | 2026-10-07 |
| UI look & build | **Dark neutral-gray theme, Tailwind CSS, Radix primitives** (plus react-router, TanStack Query, lucide icons) | 2026-10-07 |
| RAW + JPEG pairs | **One photo**: the RAW is the master, the camera JPEG is kept as a sidecar (Phase 8 test data). Lone JPEG/TIFF = own photo | 2026-10-07 |
| Opening folders | **In-app folder browser + paste a path + recent folders.** Catalog keeps all imported folders; Library shows one at a time | 2026-10-07 |
| Photo identity | **Content hash (SHA-256).** Moved/renamed folders keep their edits; identical copies are one photo | 2026-10-07 |
| Phase 2 preview | **LibRaw half-size, camera WB, sRGB, auto-brightness on** (temporary until the Phase 3 pipeline) | 2026-10-07 |
| LibRaw threading | **Single-threaded LibRaw; parallelism via worker processes.** LibRaw's OpenMP decode of X-T3 RAFs is not deterministic (two decodes differed by up to 184 levels); 1 thread is bit-identical but ~5× slower per photo (full-size ≈ 13 s) | 2026-10-07 |
| Default look (Phase 3) | **Match the camera JPEGs**: a per-camera profile (baseline EV, 3×3 matrix, tone curve, 8-band HSL) fitted from RAF + camera JPEG pairs; first profile "X-T3 · Provia" (all samples: Provia, DR100). Generic profile for other cameras; none for JPEG/TIFF originals | 2026-10-08 |
| Thumbnails (Phase 3) | **Rendered by the pipeline** (background job after import; re-render on edit), embedded JPEG only until then | 2026-10-08 |
| Golden images | **Real-photo references stay local** (git-ignored); only synthetic references are committed | 2026-10-08 |
| Later-phase parameters | **Rejected with a clear error** when set to non-default values before their phase | 2026-10-08 |
| ExifTool / OpenCV timing | ~~ExifTool joins in Phase 5~~ (replaced 2026-10-10, see "Export metadata"); Phase 2 reads EXIF with Pillow. **OpenCV joins in Phase 3** | 2026-10-07 |
| Tone sliders (Phase 3 feedback) | **Highlights/shadows/whites/blacks are relative to each photo's own white and black points** (Lightroom-like), not fixed scene stops. Measured once per photo, stored in the catalog, so previews and exports agree. Reason: with fixed stops, Whites ±100 changed nothing on DSCF5437 (its brightest pixel is +2.4 stops; the band started at +2) | 2026-10-09 |
| Contrast pivot (P3.24) | **Contrast and the four tone bands pivot on the middle of the photo's own range** (between its black and white points), not on scene mid gray, which lies above the median pixel of every sample (Contrast +100 turned a night shot almost black) | 2026-10-09 |
| Phase 3b timing | **Deferred** after the Phase 3 human test (preview speed is better but still has a delay; fine for now, since the AI drives edits and the user won't move sliders by hand yet). **Phase 4 (Styles) comes next**; 3b moves after Phase 9 or folds into its performance work | 2026-10-09 |
| Live preview speed | **New Phase 3b** after Phase 3: (A) draft renders while dragging, latest-wins, save on release; (B) **instant GPU preview in the browser via a 3D LUT built by `core`**. Reason: a slider change took ~0.6 s after the mouse stopped and showed nothing while dragging | 2026-10-09 |
| Sharpening preview | Sharpening is invisible at fit-to-screen size (radius 1 px → 0.26 px); it needs a **1:1 zoom view, deferred to Phase 6** | 2026-10-09 |
| Style ↔ photo link (Phase 4) | **Live link**: a photo's edit references its style by id, so changing a style updates every photo that uses it (thumbnails re-render). The edit's revision includes a hash of the style's look, so renders stay deterministic | 2026-10-09 |
| Applying a style over tweaks (Phase 4) | **Lightroom-like**: per-photo tweaks of parameters the style sets are dropped, so the style's value shows. Tweaks of other parameters (e.g. a crop) are kept | 2026-10-09 |
| Adaptive rules (Phase 4) | **Auto exposure** (bring the photo's middle brightness to a target, with strength and a max ±EV), **white balance relative to as shot** (style offsets instead of fixed Kelvin) and an optional **auto-neutral white balance** + offset. Inputs are measured once per photo, like the tone anchors | 2026-10-09 |
| Inconsistent photos (user input) | The user shoots **rally/drift, two cats (one black, one orange) and varied travel**, with **manual exposure tweaked while shooting**, so series are often inconsistent, which is expected to be the hardest problem. Phase 4 prepares for it without solving it fully: extensible typed rules, exposure metering modes (`middle`, `highlights` for low-key subjects such as the black cat, `camera_settings` from EXIF EV), an optional "even out this selection" group reference, a test set per style, a measured consistency report, and style version history with compare/revert | 2026-10-09 |
| Style editing UI (Phase 4) | **Managed in the UI**: save a photo's edit as a style (choose groups), edit text and rules, update a style from a photo, duplicate, delete (photos drop back to no style and keep their tweaks), render sample images from library photos | 2026-10-09 |
| Export metadata (Phase 5) | **Pillow, no ExifTool**: the tool should not depend on other programs. EXIF copied from the original and filtered by policy, XMP for copyright/creator/keywords, ICC in every file. Fujifilm maker notes and IPTC-IIM are not written | 2026-10-10 |
| Export (Phase 5) | **Automatic decode size** (half-size when it covers the output, else full; `decode: full` forces it); aspect crops **centered** until Phase 6 (`subject` rejected); **ICC profiles generated in code**; `tifffile` + `imagecodecs` for 16-bit TIFF; **custom presets committed** in `export-presets/`; default copyright from `export_copyright` in `config.local.toml`; `export_workers=auto`, one export job at a time; collisions default to `suffix`. Watermark, WebP/AVIF, original passthrough and ProPhoto ⏭ Phase 9 | 2026-10-10 |
| Full-size export speed (Phase 5) | **Accepted for now, decide later** (open concern, see §7.1). Full-size exports take ~31 s per photo (~1 min for 4 photos, ~23 min per 100); screen exports (Instagram, web) take ~1.2 min per 100. Fine for prints of a few photos. Solutions are listed in §7.1 and get decided at the start of Phase 9 | 2026-10-10 |

**Target machine**: i7-12700H (14 cores / 20 threads), 16 GB RAM, RTX 3060 Laptop (6 GB), Windows 11.
.NET 9 SDK is installed. Python and uv are not installed yet.

**Camera notes (X-T3)**:
- X-Trans sensors need a special demosaic. LibRaw supports it, but it is slower than for standard (Bayer) sensors, so the
  Phase 2 benchmark must use these files.
- The camera JPEGs (film simulations) that sit next to each RAF are useful test data. They give RAW + "edited" pairs, which
  can be used to test the style-fitting code without waiting for a real style.

---

## 1. Goal

A RAW photo editor that replaces Lightroom for **global, non-destructive edits** (color, tone, crop, zoom, centering).
An **AI agent** drives it instead of a human moving sliders. The human says what they want ("make these look like my
*Moody Forest* style, export for Instagram"), and the AI calls the tool's API. The tool's **code enforces** what is allowed:
valid parameter ranges, never touching originals, a deterministic render. A small **UI** lets the human browse, compare
and approve.

Out of scope: local or spot edits (healing, cloning, masks, brushes), generative fill, and anything that invents pixels.

---

## 2. Core principles (also become the AI rules in `CLAUDE.md`)

1. **Originals are read-only.** The tool never writes to or next to a RAW file unless the user asks for it. A test checks
   that file hashes are unchanged after every operation.
2. **Everything is data.** Styles, per-photo edits and export presets are versioned, human-readable JSON files that are
   validated against a schema.
3. **Deterministic rendering.** The same RAW, edit and engine version always give the same output, which makes golden-image tests possible.
4. **One core, many front-ends.** The CLI, the AI interface (MCP) and the UI all call the same Python core API. None of them contains its own logic.
5. **The code enforces the rules.** The AI can only set parameters that exist, inside their allowed ranges. Invalid input gets a clear error back.
6. **Plan → TODO → phases → each phase human-testable + unit-tested.** When in doubt, ask.

---

## 3. Recommended tech stack (needs your decision, see section 9)

| Layer | Recommendation | Why |
|---|---|---|
| Language | **Python 3.12** | Best ecosystem for image processing and AI tooling. Claude writes and tests it well. |
| Env / packaging | **uv** | Fast, reproducible environments on Windows. |
| RAW decoding | **rawpy** (LibRaw) | Supports nearly every camera RAW (CR2/CR3, NEF, ARW, RAF, ORF, RW2, DNG…). |
| Image math | **NumPy** (+ **OpenCV** for resize, sharpen, geometry, face detection) | Fast vectorised pipeline in float32 linear light. |
| Color management | **Pillow ImageCms** (LittleCMS) + **colour-science** | ICC profiles for sRGB, Display P3 and AdobeRGB output, plus white balance math. |
| Metadata | **Pillow** (EXIF + XMP; decided 2026-10-10, no ExifTool) | Copy EXIF, write copyright/keywords as XMP, strip GPS on request. |
| Lens corrections (later) | **lensfunpy** | Distortion and vignetting profiles. |
| Data models / validation | **Pydantic v2** | Schema, ranges and JSON (de)serialization for styles, edits and presets. |
| CLI | **Typer** | `photoedit style apply ...` and similar commands. Also used for manual testing. |
| AI interface | **MCP server** (official `mcp` Python SDK) | Claude Code / Claude Desktop calls the tool's functions directly and gets preview images back to "see" results. |
| UI | **Local web UI**: FastAPI backend + **React + TypeScript + Vite** frontend, opened in the browser | Same core API, easy to test, Claude can also drive and check it in a browser. |
| Tests | **pytest** (+ golden-image comparisons with tolerance, hypothesis for parameter fuzzing) | |
| Lint / types | **ruff**, **mypy** | |

Alternatives are listed in section 9.

### 3.1 Performance: can Python handle 50–100 photos?

Yes. Two things matter:

- **Applying a style is instant.** It only writes small edit JSON files. Pixels are processed only for previews and for export.
- **The heavy work is not Python.** RAW decoding and demosaicing happen in LibRaw (C++). The pixel math runs in NumPy/OpenCV
  (C, vectorised). A C# or Rust backend would call the same kind of native code, so it would not be meaningfully faster.

Estimates for this machine (to be confirmed by a benchmark in Phase 1):

| Job | 24 MP RAWs | 45 MP RAWs |
|---|---|---|
| Full-res render + export, single photo | ~3–5 s | ~6–9 s |
| **100 photos, parallel** (6 workers for 24 MP, 3–4 for 45 MP, limited by 16 GB RAM) | **~1–2 min** | **~3–4 min** |
| 100 previews (half-size, cached) | ~10–20 s | ~20–40 s |

For comparison, a Lightroom export takes roughly 1–2 s per photo on similar hardware, so this is in the same range.
If it's too slow, the next steps are, in order:
1. Process in float16 or tiles to fit more workers in RAM.
2. Move pipeline stages to the GPU (CuPy/PyTorch on the RTX 3060). That leaves decoding as the only real cost.
3. Use Numba-compiled kernels for the hottest stages.

Your X-T3 files are 26 MP, so the 24 MP column applies. X-Trans demosaicing adds roughly 30–50 %, so expect **about 1.5–3 min
per 100 photos**.

**Phase 2 includes a go/no-go benchmark.** If 100 photos take more than 5 minutes, we stop and rethink before building further.

### 3.2 Splitting UI and backend (e.g. C# UI + Python backend)

The architecture (section 4) already separates them, so it is possible. The Python backend runs as a **local HTTP service**
(FastAPI on `127.0.0.1`). Any UI talks to it: web, C# or something else.

| UI option | Pros | Cons |
|---|---|---|
| **Web UI** (React/TS in the browser, served by the backend) | One process; fastest to build; Claude can test it in a browser; easy to restyle | Feels like a web page, not a native app |
| **C# WPF / WinUI 3** (.NET 9 is already installed) | Native Windows feel, good image controls, fast scrolling of thumbnails | Two languages and two builds. The C# app has to start and supervise the Python process. Harder for Claude to test the UI automatically. |
| **Avalonia (C#)** | Like WPF, but cross-platform | Same costs as WPF |
| **PySide6 (Qt, Python)** | Single language, native window | Qt is verbose; less pleasant for a rich gallery UI |

Recommendation: start with the **web UI**, because it gets you to a testable full loop fastest. The HTTP API contract is defined in
OpenAPI, so a C# UI can be added or swapped in later without changing the backend.
If a native feel matters to you from day one, C# WPF + Python backend is a solid choice. It just costs more time per phase.

### 3.3 RawTherapee: licensing and permissions

- **License: GPLv3.** For your **personal use** there are no obligations at all. The GPL only applies when software is
  **distributed** to others.
- If we **call `rawtherapee-cli` as a separate program** (no code copied or linked), our tool can keep any license. That
  holds even if it is shared later. We would just have to say that RawTherapee must be installed, or follow GPL rules if we
  bundle its binaries in a download.
- **Permissions**: a normal free Windows install with no account, no network and no telemetry. Our tool would only need read
  access to the RAWs and write access to the output folder, the same as our own engine. (To verify before choosing it: whether
  a portable/no-admin install works.)
- The other libraries in the plan are fine for personal and commercial use: rawpy (MIT), LibRaw (LGPL/CDDL), OpenCV
  (Apache 2), NumPy (BSD), Pillow (MIT-like), lensfun (LGPL), ExifTool (Perl Artistic/GPL, called as a program).
- **Trade-off reminder**: RawTherapee gives better image quality on day one (noise reduction, highlight recovery, lens
  corrections, local contrast). In exchange, there is an external dependency, rendering is slower to iterate on, and only
  what `.pp3` files expose can be controlled.

---

## 4. Architecture

```
            ┌────────────┐   ┌──────────────┐   ┌──────────────────┐
  Human ──▶ │  Web UI    │   │  CLI (Typer) │   │ MCP server (AI)  │ ◀── Claude
            └─────┬──────┘   └──────┬───────┘   └────────┬─────────┘
                  │ HTTP            │                    │
                  ▼                 ▼                    ▼
            ┌───────────────────────────────────────────────────────┐
            │                 Core API  (photoedit.core)            │
            │  library · styles · edits · render · analyze · export │
            └───┬──────────────┬───────────────┬──────────────┬─────┘
                ▼              ▼               ▼              ▼
          RAW decode     Render pipeline   Analysis       Export
          (rawpy)        (NumPy/OpenCV)    (stats, faces) (resize, ICC,
                                                           sharpen, EXIF)
```

### 4.1 Data on disk (inside this folder by default; location configurable)

```
workspace/
  catalog.sqlite              # photo index: path, hash, EXIF, thumbnails cache keys
  edits/<photo-id>.json       # per-photo edit = style ref + per-photo overrides (crop, exposure tweak…)
  cache/previews/...          # rendered previews (disposable)
styles/
  <style-slug>/
    style.json                # parameters (schema-validated, versioned)
    README.md                 # human description: intent, "best for", "avoid on"
    samples/                  # before/after JPEGs showing expected result
    analysis.json             # stats of reference photos it was derived from
export-presets/
  instagram-portrait.json
  print-8x10-glossy.json
  ...
```

Originals stay where they are. The catalog only stores their path and hash.

### 4.2 Edit parameter model (Lightroom-like, global only)

The MVP set comes first. Later items are marked ⏭.

- **White balance**: temperature (K), tint
- **Tone**: exposure (EV), contrast, highlights, shadows, whites, blacks
- **Presence**: vibrance, saturation, ⏭ clarity, ⏭ texture, ⏭ dehaze
- **Tone curve**: parametric curve, plus point curves for RGB, R, G and B
- **HSL / color mixer**: 8 hue bands × (hue, saturation, luminance)
- **Color grading**: shadows / midtones / highlights (hue, sat, lum), blending, balance
- **Detail**: sharpening (amount, radius, detail, masking), ⏭ noise reduction
- **Effects**: post-crop vignette, ⏭ grain
- **Geometry** (usually per photo, not per style): crop rectangle, aspect lock, rotate/straighten, flip, zoom/center
- ⏭ **Lens**: profile distortion and vignetting correction

A **Style** holds a subset of these parameters, plus *adaptive rules* that the code applies per photo. Example:
"auto-exposure to target mid-gray, then apply the style". Without these, one style would only look right on photos that were
shot the same way. A **per-photo edit** = style + overrides. Overrides always win.

### 4.3 Render pipeline (fixed order, float32 linear working space)

1. Decode RAW → demosaic → camera RGB to linear wide gamut (ProPhoto / Rec.2020 linear), with white balance applied
2. Exposure → highlights/shadows/whites/blacks → contrast
3. Tone curve → HSL → color grading → vibrance/saturation
4. Geometry (crop / rotate / zoom)
5. Vignette → sharpening
6. Output transform: gamut-map to the target color space, encode the gamma, embed the ICC profile

Previews use LibRaw's half-size decode and are cached, so the AI and the UI get fast feedback (~0.5 s). Exports use full resolution.

**Live preview while editing (Phase 3b, decided 2026-10-09; deferred).** Every stage except vignette and sharpening is a per-pixel
color function: a pixel's output depends only on its own input color. So `core` evaluates the exact pipeline on a 3D grid
of input colors (a 3D LUT, e.g. 33³–65³ colors instead of ~1.7 M pixels: milliseconds), and the browser applies that LUT
to the photo's linear base image in a WebGL shader at screen refresh rate. The browser only interpolates numbers made by
`core`, so the editing logic stays in one place (principle 4). The GPU image is a draft: after the slider is released,
the exact CPU render replaces it, and exports never use the LUT. Vignette and sharpening (not per-pixel) use fast
server-side draft renders while dragging instead.

### 4.4 AI interface (MCP tools, first draft)

| Tool | Purpose |
|---|---|
| `import_photos(paths/folder)` | Add photos to the catalog (read-only scan). |
| `list_photos(filter)` / `get_photo_info(id)` | EXIF, current edit, thumbnails. |
| `render_preview(id, edit?, size)` | Returns a JPEG so the AI can **see** the result. |
| `analyze_photo(id)` | Histogram, clipping, mean luminance, color cast, saturation per hue, faces/subject box. |
| `list_styles` / `get_style` | Read the style library. |
| `create_style` / `update_style` | Write a style (validated). |
| `apply_style(style, photos)` | Bulk-assign a style to photos (writes edit JSON only). |
| `set_adjustments(photo, params)` | Per-photo overrides (crop, exposure tweak…). |
| `suggest_crop(photo, aspect)` | Code-computed crop centered on the detected subject. The AI can accept it or adjust. |
| `list/create_export_preset` | Export settings. |
| `export(photos, preset, dest)` | Render and write output files. |

### 4.5 Style creation workflow (the AI-heavy feature)

1. The user points at sample photos (see open question Q4 about what kind of samples).
2. The code runs `analyze_photo` on each sample: tone statistics, color cast in shadows and highlights, saturation per hue,
   contrast, and so on.
3. The AI looks at the samples and the statistics and proposes style parameters.
4. If **RAW + edited pairs** exist, the code also **fits** parameters numerically. It optimizes them to minimize the color
   difference (ΔE) between our render and the user's edit. This gives the most accurate result.
5. The code renders before/after on the samples. The AI compares and iterates a few rounds.
6. The style is saved with a README (description, intent, "best for"), sample before/after images and the analysis.
7. The human reviews it in the UI and approves it, or asks for changes.

Both input types are supported. **Finished photos** go through steps 2–3 and 5–7 and give an approximate look.
**RAW + edited pairs** also go through step 4 and give an exact fit.

#### 4.5.1 Fallbacks if style creation doesn't give the desired result

Try these in order. Each is a self-contained addition, so we can switch to one without redesigning the tool.

| # | Approach | When to use | Cost |
|---|---|---|---|
| F1 | **Human-in-the-loop A/B**: the AI renders 3–4 variants and you pick one; repeat 2–3 rounds | The AI proposal is "close but not it" | Low; only UI and MCP work |
| F2 | **Statistical color transfer**: Lab mean/variance transfer (Reinhard), per-channel histogram matching, tone-curve fit from luminance histograms | Finished photos only, and the AI's parameter guesses are off | Low–medium |
| F3 | **Learned 3D LUT** (e.g. 33³) fitted from RAW + edited pairs, stored inside the style next to the parameters | Pairs exist, but the slider model can't express the look (complex color shifts) | Medium. Very accurate for global color, but less tweakable |
| F4 | **Import Lightroom develop settings / presets (`.xmp`)** and map them onto our parameters | You already have the look as a Lightroom preset or edits | Medium; the mapping is approximate for Adobe-specific processing |
| F5 | **ML enhancement model** (image-adaptive 3D LUT / HDRNet-style), trained on your pairs | Look depends heavily on scene content and needs many pairs (50+) | High. GPU training, the most complex option |

### 4.6 Export settings (Lightroom export parity, staged)

- **File**: JPEG (quality, optional max file size), TIFF 8/16-bit (compression), PNG, ⏭ WebP/AVIF, DNG passthrough copy
- **Color space**: sRGB, Display P3, AdobeRGB, ⏭ ProPhoto
- **Size**: original, long edge, short edge, width × height (fit), megapixels, percentage; don't enlarge; DPI/PPI
- **Aspect / orientation**: crop-to-aspect (1:1, 4:5, 1.91:1, 9:16, 2:3, 4:3, 5:7, 8:10, A-series…) with subject-centered
  auto crop; force portrait/landscape
- **Output sharpening**: screen / matte / glossy × low / standard / high
- **Metadata**: all, copyright only, copyright + contact, all except camera & GPS; strip GPS; add copyright/keywords
- **Naming**: template (`{date}_{seq:03}_{orig}`), collision handling
- **Watermark** (⏭ simple text/PNG)
- **Built-in presets**: Instagram feed portrait (1080×1350 4:5 sRGB), square, landscape, story (1080×1920); print
  4×6 / 5×7 / 8×10 / A4 / A3 at 300 PPI (AdobeRGB or sRGB, TIFF/JPEG max quality); web full-size

---

## 5. Phases (each one ends with something you can test by hand)

| # | Phase | Backend | UI part | You can check it by… |
|---|---|---|---|---|
| 0 | **Project setup + AI rules** | uv project, folder structure, `CLAUDE.md` rules, ruff/mypy/pytest, `.gitignore` (RAWs, output, cache) | Vite + React + TS scaffold, served by FastAPI | `uv run pytest` is green; `uv run photoedit --version` works; `photoedit ui` opens an empty page |
| 1 | **UI skeleton (no functionality)** | Mock API that returns fake data | All screens, clickable with placeholder images: Library grid, Photo view (before/after, adjustment panel), Style library (card with description + samples), Style detail, Export dialog (all settings), Jobs/progress | Click through the full use loop and judge the look and feel. Give feedback, and the layout gets adjusted before real work starts |
| 2 | **Import & decode + benchmark** | Catalog, EXIF read, thumbnails, half-size preview render, **go/no-go speed benchmark on the X-T3 RAFs** | Library grid shows real thumbnails and EXIF | Import `2026-08-11` → real thumbnails in UI; previews look neutral and correct; originals' hashes unchanged; benchmark report |
| 3 | **Edit engine (MVP params)** | Parameter model + render pipeline + per-photo edit JSON | Adjustment panel works (sliders for testing, even though AI is the main user); before/after toggle | Move sliders → preview updates; contact sheet of each slider at −/0/+ |
| 3b | **Live preview speed** (added 2026-10-09; **deferred** 2026-10-09, after Phase 9) | Draft render endpoint, faster CPU render, 3D LUT of the per-pixel pipeline, linear base for the browser | Drafts while dragging (latest-wins, save on release); WebGL preview applying the LUT; exact render swaps in after release | Drag any color/tone slider → the image follows the mouse with no visible delay; the final image settles within about half a second of release |
| 4 | **Styles** | Style file format, library, apply to one/many, adaptive rules, overrides | Style library and detail screens are live; "apply style to selection" | Apply a hand-written test style to the folder → before/after looks consistent |
| 5 | **Export** | Presets, resize, color space + ICC, output sharpening, metadata, naming, aspect crop | Export dialog is live; job progress | Instagram preset → 1080×1350, sRGB tagged, EXIF as configured; print preset → correct PPI/size |
| 6 | **Geometry & centering** | Crop/rotate/straighten/zoom, subject detection, `suggest_crop`, full-resolution crops for a 1:1 view | Crop overlay in the Photo view; 1:1 zoom view (where sharpening can be judged) | Auto 4:5 crop keeps subjects well framed; sharpening is visible at 1:1 |
| 7 | **MCP server (agentic workflow)** | Exposes the core API to Claude Code | UI auto-refreshes when the AI changes something | In Claude Code: "apply style X to folder Y and export for Instagram to Z" works end to end |
| 8 | **AI style creation**. ⛔ **STOP at the start and ask the user for style samples** | Analysis tools, parameter fitting from pairs (developed and tested first on the camera JPEG + RAF pairs), README + samples generation, fallbacks F1–F3, F5 | "Create style" flow; A/B variant picker (F1) | Give sample photos → style created, saved, and its samples look like the references |
| 9 | **Polish** | Parallel batch tuning, caching, clarity/texture/dehaze, noise reduction, lens corrections, more formats | UI refinements from your feedback | 100 RAFs export in acceptable time; extra sliders behave |

---

## 6. Testing strategy

- **Unit tests** for every pipeline stage. They run on small synthetic images (gradients, color patches) with exact
  expected math: exposure +1 EV doubles linear values, zero parameters give an identity result, and so on.
- **Property tests** (hypothesis). Every valid parameter combination renders without NaN or out-of-range values.
  Invalid values are rejected.
- **Golden-image tests** on a small set of real RAWs. The render must match the stored reference within ΔE tolerance, which catches regressions.
- **Safety tests**. Originals' hashes stay unchanged after import, edit and export, and nothing is written outside the configured folders.
- **Export tests**: output dimensions, color profile, metadata and file naming.
- **MCP tests**. Each tool is called with valid and invalid input and returns schema-correct responses.
- **UI**: API tests via FastAPI TestClient, plus a few Playwright smoke tests in a later phase.

---

## 7. Risks / hard parts (to be honest up front)

- **Color science quality.** Matching Lightroom's look (Adobe camera profiles, highlight recovery, noise reduction) is hard.
  The plan is to start with LibRaw's standard pipeline and improve it. It will look *good*, but not identical to Lightroom.
- **One style on very different photos.** Adaptive rules (auto-exposure and WB normalization before the style) are key here. These need iteration with your real photos.
- **Speed.** Python/NumPy on 24–60 MP files takes about 2–5 s per photo at full size. Running in parallel across CPU cores is planned. A GPU path is possible later if needed.
- **Style-from-finished-JPEGs** (no RAW pairs) can only approximate a look. RAW + edited pairs give much better results.

### 7.1 Open concern: full-size export speed (to decide in Phase 9)

**The problem** (measured 2026-10-10, docs/benchmark.md). A full-size X-T3 export takes ~31 s of one core per
photo: decode ~25 s (LibRaw's 3-pass X-Trans demosaic), render ~6 s, sharpening ~2.5 s, encode ~1 s. The decode
runs single-threaded on purpose: LibRaw's multithreaded decode isn't deterministic (golden rule 3). Parallel
exports help, but each needs ~1.6 GiB, so only 3–4 fit when ~5 GiB RAM is free. Result: ~1 min for 4 photos, ~23
min per 100 (target was 5). Even with unlimited RAM, the cores (6 performance + 8 efficiency) would give ~9 min
per 100. Screen exports use the half-size decode and are fine (~1.2 min per 100).

**Possible solutions** (estimates for 100 full-size photos; they combine):

| # | Solution | Estimate | Trade-off |
|---|---|---:|---|
| S1 | **Accept** (current choice): full size is mainly for prints, a few photos at a time | 23 min | None |
| S2 | **Less memory per export**: sharpening (pipeline + output) in tiles with overlap instead of full-frame planes, ~1.6 → ~0.8 GiB, so 6–8 exports fit | ~10–12 min | ~1 day of work; output stays bit-identical |
| S3 | **1-pass X-Trans demosaic** for full-size exports: decode 25 → 14 s | ~15 min (4 exports) | Slightly softer fine detail / more color artifacts (mean difference 0.03 %, worst pixels 1.75 %); full-size references regenerated once |
| S4 | **S2 + S3** | ~6–7 min | Both trade-offs |
| S5 | **GPU render** (RTX 3060, CuPy/PyTorch): render + sharpening 8 s → <1 s | decode-bound | Large job; the decode stays the limit; GPU results must be checked for determinism |
| S6 | **Re-measure on an idle, plugged-in machine** first: Phase 2 measured ~13 s for the same full decode that took ~25 s now | ? | None; may change every estimate above |
| S7 | **Faster deterministic demosaic** of our own (e.g. a vectorized/Numba X-Trans demosaic in tiles, multi-core but deterministic) | could reach the 5-min target | Biggest job; must match LibRaw's quality |
| S8 | **Pre-decode in the background** (full-size linear cache on disk while the user edits) | export time drops, work moves earlier | ~150 MB per photo on disk (float16); only helps if it ran before the export |

Not an option: LibRaw's multithreaded decode (breaks deterministic rendering).

---

## 8. Workflow rules for building it (AI rules)

- Each phase: plan section → `TODO.md` checklist → implement → unit tests → **human test script** (exact steps + expected
  result) → you approve → next phase.
- Never modify files outside `C:\Work\PhotoEditing`. Photo folders are read-only. Exports outside this folder only go to a
  destination the user explicitly chose.
- Ask when requirements are ambiguous. Don't guess.

### 8.1 Git workflow (per phase)

1. At the start of each phase that writes code, create a branch from an up-to-date `main`: `phase-<N>-<short-name>`
   (e.g. `phase-0-setup`, `phase-1-ui-skeleton`).
2. Commit on that branch as often as is useful. Each commit message references the TODO item ID (e.g. `P0.3: ...`).
3. At the end of the phase, the user runs the 🧑 human test. Requested tweaks are made **on the same branch**.
4. Only after the user **confirms the phase**: merge the branch into `main` with `--no-ff` (so each phase stays one visible
   unit in history), then create the next phase's branch from `main`.
5. Never merge into `main` before the user's confirmation. Never commit phase code directly to `main`.
6. Pushing: the phase branch is pushed as work progresses (as a backup). `main` is pushed right after each confirmed merge.
7. Commits use the user's identity `SigitasAmbrozaitis <ambrozaitis.sigitas@gmail.com>`, set in the repo-local config. Never
   use the global `cyam` identity.

---

## 9. Open decisions (please answer)

All decided. See section 0.
