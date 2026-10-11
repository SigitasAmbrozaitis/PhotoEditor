# Export

How a photo becomes an output file (Phase 5). The code is in `src/photoedit/core/export/`; the settings model is
`ExportSettings` in `src/photoedit/models/export.py`.

## Rules that never change

- **Originals are only read.** A destination inside a photo folder (one the catalog knows or one in the config), or
  any of its subfolders, is refused. So are the tool's own data folders (workspace, cache, styles, export-presets).
- **Only the chosen folder is written.** It becomes writable when its export starts and stops being writable when
  the export ends. Every file is written atomically (a temporary file, then a rename), so a cancelled or failed
  export never leaves a half-written file.
- **Same input, same bytes.** The same photo, edit, settings and engine version give a byte-identical file. Nothing
  depends on the clock: EXIF dates come from the original, and the ICC profiles have a fixed creation date.

## Pipeline

1. **Geometry** (`geometry.py`): the aspect crop (centered; `subject` arrives with Phase 6), the output size and
   whether the half-size decode is enough. All of this is in the photo's upright full-size pixels.
2. **Decode** (`worker.py`): LibRaw full size, or half size when its pixels still cover the output without
   enlarging (RAWs only; JPEG/TIFF originals always decode fully). `decode: full` in a preset forces full size.
   The print presets do that.
3. **Crop, then resize** in linear light: area averaging when shrinking, bicubic when enlarging.
4. **Render** with the same pipeline as previews, with the photo's stored tone anchors, so an export looks like
   the Photo view. The post-crop vignette is relative to the crop. Full-size exports render in small strips
   (`low_memory`) with the same pixels; this keeps a worker under ~1.6 GiB.
5. **Output color space** (part of the render's last stage): sRGB, Display P3 or Adobe RGB (1998). Colors outside
   the space are pulled toward their own luminance until they fit, so hues don't shift.
6. **Output sharpening** (`sharpen.py`, table below).
7. **Encode** (`encode.py`) with the ICC profile and metadata.

## Sizes

| Mode | Result |
|---|---|
| Original | the crop's size |
| Long edge / short edge | that edge in pixels, the other in proportion |
| Width × height | fits inside the box. The box is turned to match the crop's orientation, so a 3000×2400 print box gives 2400×3000 for a portrait photo |
| Megapixels | width × height ≈ the number given |
| Percentage | of the crop's size |

**Don't enlarge** caps the scale at 1. An enlarged export gets a warning ("enlarged 1.40×").

In width × height mode, an aspect ratio within 1 % of the box's own ratio counts as the box's ratio. Named ratios
are rounded (1.91:1 is really 1080×566, and A-series 1.414:1 is 3508×2480), and the box is what was meant, so the
output is exactly the box. Otherwise the crop takes the output's exact ratio, so resizing never stretches. The
difference is under one pixel.

**Orientation**: *Follow photo* turns the ratio to the photo's orientation (a 3:2 print preset gives 3:2 for
landscape photos and 2:3 for portrait ones). *Force portrait/landscape* always uses that orientation. The Instagram
presets force theirs, so a landscape photo becomes a centered 4:5 portrait crop.

## Formats

| Format | Bits | Notes |
|---|---|---|
| JPEG | 8 | Pillow. 4:4:4 color at quality ≥ 90, 4:2:0 below. Baseline (not progressive). *Limit file size* finds the highest quality that fits, by bisection; if even quality 1 is too big, the file is written at quality 1 with a warning |
| TIFF | 8 / 16 | tifffile. No compression, LZW or ZIP (with a horizontal predictor) |
| PNG | 8 / 16 | OpenCV, plus our `pHYs`, `iCCP`, `eXIf` and XMP chunks |

Every file carries its **ICC profile** (built in code: `icc.py`, ICC v2 matrix/curve profiles, checked against
LittleCMS in the tests) and its **resolution** (PPI). The EXIF orientation is always 1, because the pixels are
already upright.

## Output sharpening

An unsharp mask on luminance, applied after resizing, using the pipeline's own sharpening stage. For paper, the
radius is given for 300 PPI and scales with the preset's PPI, so it covers the same distance on the page.

| Sharpen for | Radius (output px) | Detail | Low | Standard | High |
|---|---:|---:|---:|---:|---:|
| Screen | 0.6 | 25 | 25 | 45 | 70 |
| Glossy paper | 0.8 × PPI / 300 | 25 | 35 | 60 | 90 |
| Matte paper | 1.1 × PPI / 300 | 30 | 45 | 75 | 110 |

Matte paper gets more because ink spreads on it. *None* leaves the pixels as rendered. The amounts are on the
same 0–150 scale as the Detail panel's sharpening.

## Metadata

The original's EXIF is read with Pillow (for a RAW, from the camera's embedded JPEG). Only known standard tags are
copied, chosen per policy. Maker notes (e.g. Fujifilm's film simulation), embedded thumbnails and unknown tags are
never copied.

| Policy | Copied from the original |
|---|---|
| All metadata | dates, exposure (shutter, aperture, ISO, focal length, metering, flash…), camera make/model, lens, serial numbers; GPS unless *Remove location* is on |
| All except camera & location info | dates and exposure only |
| Copyright & contact info | nothing; copyright and creator are written |
| Copyright only | nothing; copyright is written |

Always written: Software (`PhotoEditor <version>`), resolution, orientation 1, the color space tag and the pixel
size.

**Copyright and creator** come from the preset, or else from `export_copyright` / `export_creator` in
`config.local.toml`, or else from the original's own tags (when the policy keeps them). `{year}` in the copyright
is the photo's capture year, so the file doesn't depend on when it was exported. EXIF text is ASCII by
definition, so "©" is written there as "(c)" and accents are dropped. The exact text goes into **XMP**
(`dc:rights`, `dc:creator`), along with the **keywords** (`dc:subject`); Lightroom, Windows and Instagram read XMP.

TIFF files carry make, model, date, artist and copyright as TIFF tags, and the dates, exposure and lens in XMP
(tifffile can't write an EXIF sub-block). GPS is written only to JPEG and PNG files; a TIFF export with GPS on gets
a warning instead.

## Names

The name template uses these tokens:

| Token | Expands to |
|---|---|
| `{original}` | the original's file name without its extension |
| `{date}` / `{time}` | capture date `2026-08-11` / time `093015` (`nodate` / `notime` if unknown) |
| `{seq}`, `{seq:03}` | 1, 2, 3… in export order (capture time, then file name); `:03` pads to 3 digits |
| `{style}` | the photo's style id, or `nostyle` |
| `{preset}` | the preset id, or `custom` |
| `{camera}` | e.g. `FUJIFILM X-T3`, or `nocamera` |

The extension comes from the format. Characters Windows doesn't allow are refused in the template and replaced by
`_` in the expanded values. Names are at most 150 characters.

Two photos of one export never get the same name: the later one gets `_2`, `_3`… Against files already in the
folder (compared without case, as Windows does), the **If file exists** setting decides:

- *Add a number* (default): `name_2.jpg`, `name_3.jpg`…
- *Overwrite*: replaces the file in the destination.
- *Skip*: leaves it, and the job reports "exists, skipped".

The Export dialog shows the plan (names, sizes, decode, collisions, warnings) before anything is written. The CLI
has `--dry-run` for the same.

## Speed

Exports run in worker processes (`export_workers`, default automatic: at most 10, two cores left free, and only as
many as fit in free memory at ~1.7 GiB each). One export job runs at a time; others wait in the queue. Measured
numbers are in [benchmark.md](benchmark.md).
