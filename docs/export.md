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

1. **Geometry** (`geometry.py`): the aspect crop (centered, or framed on the photo's subject with the `subject` anchor, as in
   the Instagram presets: [geometry.md](geometry.md#subjects-and-suggested-crops-phase-6b)), its zoom
   ([below](#pre-export-review-phase-6c)), the output size and whether the half-size decode is enough. All of this is in the full-size pixels of the photo after its
   own geometry (crop, straighten, turn: [geometry.md](geometry.md)), so the aspect crop is taken inside the
   photo's crop.
2. **Decode** (`worker.py`): LibRaw full size, or half size when its pixels still cover the output without
   enlarging (RAWs only; JPEG/TIFF originals always decode fully). `decode: full` in a preset forces full size.
   The print presets do that.
3. **Geometry, crop, then resize** in linear light: the photo's flips, turn and straighten plus both crops
   in one step (`core/render/warp.py`), then area averaging when shrinking, bicubic when enlarging.
4. **Render** with the same pipeline as previews, with the photo's stored tone anchors, so an export looks like
   the Photo view. The post-crop vignette is relative to the crop. Full-size exports render in small strips
   (`low_memory`) with the same pixels; this keeps a worker under ~1.7 GiB (~1.8 GiB with a straightened crop).
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

## Pre-export review (Phase 6c)

For a batch, **Library → Prepare export…** (or **Apply style…**, whose last step is now *Apply & prepare for
review*) instead of **Export…**: the tool frames every photo as the export will and asks only about the ones it
isn't sure of. **Frame the crop on the subject** is on by default in both dialogs (it sets the export's `subject`
anchor, also for presets that center, such as the print presets); switched off, crops are centered, subjects
aren't looked at and every photo is Ready. The code is in `src/photoedit/core/review/`; the models are
in `src/photoedit/models/review.py`.

1. **Prepare** (a job): an optional style is applied first (its own job; Prepare waits for it, so the previews
   show it). Then each photo's subject is found (stored detections are reused), it is framed through the same
   code as a plain export (`Exporter.frame`), the review rules sort it, and its **framing preview** is rendered:
   the photo's edit cut to the export's crop, 800 px long edge, cached like previews. The review opens at
   once and shows the job's progress until it is ready.
2. **Ready / Check.** A Check photo carries one or more reasons. Ready photos need nothing. A photo that can't be
   exported at all (original gone, broken style) is listed apart and never exported.
3. **Fix or approve.** The panel shows the whole photo with the export's frame and **what detection found**:
   the subject, every other candidate and the guesses (what stands out, sharp areas), each with its kind and
   confidence, and the camera's focus point (**Hide details**, key `D`, remembered per browser). The subject's
   confidence also shows next to the Ready/Check tag and on each card. On a photo: click another candidate's
   box, **Set subject** (drag a box), **drag the frame** to move it, move the **Zoom**, or **Approve** (key `A`)
   the tool's framing as it is. A fix is a decision, so it approves the photo. A chosen subject is saved to the
   photo's edit (as the crop tool's Set subject) and places the frame on it again; the zoom and the frame's
   position belong to this review only (**Re-center on subject** forgets the position). While the zoom slider
   or the frame moves, the frame and the preview follow at once: core sends the crop for every 0.01× zoom step,
   and the browser shows the loaded photo cut to the frame until the real preview has rendered.
4. **Export.** **Export Approved** writes the Ready and approved photos. **Force Export All** also writes the
   ones not approved, with the tool's framing, after a confirmation that names them. Once nothing is left to
   approve there is one **Export All**. Exported photos leave the review; an empty review is deleted.

A review is stored as `workspace/reviews/<id>.json`, so a reload or a restart keeps the decisions. Opening one
frames every photo again against its current edit and subject. An approval stores the framing it approved
(the crop and the output size); when that changed since (the photo was re-edited elsewhere), the approval is
dropped and the photo is back in Check with "the framing changed since you approved it". Exports use those
refreshed framings and each photo's zoom and position, so the files show what the previews showed. A photo already in an
export job isn't sent again. Reviews older than 30 days are deleted when the tool starts.

**Rules** (`review-settings.json` in the workspace; **Rules…** on the review screen, or
`photoedit review settings`). Saving them sorts every open review again.

| Rule | A photo is in Check when | Default |
|---|---|---|
| `no_subject` | nothing is recognized: the crop is centered or follows the camera's focus point | on |
| `uncertain` | the detected subject scores below `min_score` | 0.5 |
| `ambiguous` | another recognized candidate, not part of the subject (less than half of it inside the subject's box; a tandem the chooser grouped is inside), scores at least `ambiguity` × the subject's score | 0.75 |
| `cut_off` | the aspect crop can't hold the whole subject | on |
| `zoom_limit` | with automatic zoom, the subject stays smaller than `subject_fill` even at the quality limit | on |
| `changed` | the framing changed after it was approved | always |
| `unusable` | the export can't be made | always |

A subject set by hand (in the crop tool, by the AI or in a review) is a decision already made: `no_subject`,
`uncertain` and `ambiguous` don't apply to it. The starting thresholds come from the labeled photos: every wrong
detection scored 0.36–0.48, and rivals on good photos reached 0.85–0.94 of the subject. On the 44 labeled photos
(instagram-portrait, 2026-10-13) 13 land in Check (30 %): drift 1/12, rally 2/14, both cats 6/12, orange cat
and sunsets 4/6; no wrong subject is exported without a look (`tests/test_review_golden.py`).

**Automatic zoom** (`aspect.zoom: auto`, on in the Instagram presets; **Zoom in on small subjects** in the
export form) tightens the subject crop until the subject fills `aspect.subject_fill` (default 40 %) of the
crop's width or height. It needs the `subject` anchor and a ratio. It stops at the **fast limit**, where a RAW's
half-size decode still covers the output (1.54× for a landscape X-T3 photo in a 4:5 1080×1350 crop): automatic
zoom never makes an export slower. In the review the zoom slider goes up to the **quality limit**, where the
crop has as many pixels as the output (3.08× there); past the fast limit the review says the photo needs the
full decode (~30 s instead of ~1 s, see Speed). Photos the user cropped themselves, and photos framed on the
camera's focus point (a guess, not a subject), are never zoomed automatically. Plain exports use automatic zoom
too, so an Instagram export from the Export dialog frames small subjects the same way.

## Speed

Exports run in worker processes (`export_workers`, default automatic: at most 10, two cores left free, and only as
many as fit in free memory at ~1.8 GiB each). One export job runs at a time; others wait in the queue. Measured
numbers are in [benchmark.md](benchmark.md).
