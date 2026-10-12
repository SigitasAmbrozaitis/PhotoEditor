# Geometry and the zoom view

How a photo's crop, straighten angle, quarter turn and flips work (Phase 6a), how the zoom view shows
50 % and 100 %, and how subjects are found and framed (Phase 6b). The math is in `src/photoedit/core/geometry.py`, the pixels in `core/render/warp.py`, and the
model is `Geometry` in `src/photoedit/models/adjustments.py`. Geometry is per photo: styles never set it, and
applying a style keeps it.

## Order and coordinates

1. **Flips** (`flip_horizontal`, `flip_vertical`), on the upright photo.
2. **Quarter turn** (`rotate`: 0, 90, 180 or 270, clockwise). The photo after the flips and the turn is the
   **frame**.
3. **Straighten** (`angle`, −45…45°, clockwise positive) turns the image inside the frame around its center.
4. **Crop** (`crop`: left, top, right, bottom, 0..1 of the frame). Because the crop is in frame coordinates, it
   stays put while the angle changes.

`aspect` locks the crop's width:height as shown (e.g. `4:5`); `null` is a free crop. The edited photo's size in
full-size pixels (the crop's width and height in the frame) is stored in the catalog, so the Library and the
Photo view lay out cropped photos without reading every edit (`Photo.edited_width/edited_height`).

## No blank corners

A crop must lie inside the straightened image. Core checks it whenever an edit is saved, and refuses a crop that
reaches into the blank corners, or one whose ratio is off the aspect lock by more than a pixel (golden rule 5:
rejected, not silently fixed).

Changing the geometry goes through `apply_change` (the `GeometryChange` model; `POST /api/photos/{id}/geometry`
saves it, `POST .../geometry/preview` only computes it). The fields given are applied in this order:

| Change | What happens to the crop |
|---|---|
| `reset` | Back to the original framing. |
| a flip | Mirrored with the image, so it frames the same content; the angle changes sign. |
| a quarter turn | Turned with the frame; a locked aspect swaps (4:5 ↔ 5:4). |
| `angle` | **Shrunk around its center until it fits** (`constrain_crop`, Lightroom's "constrain to image"). If the center is outside the straightened image, or so near its edge that the crop would be tiny, it moves toward the middle just far enough. |
| `aspect` | The largest crop of that ratio around the same center, shrunk to fit. |
| `crop` | Checked as given; refused if it doesn't fit. |

## Rendering

Geometry is applied to the linear base **before** the per-pixel stages. That gives the same result as the order
in PLAN §4.3 (everything before the vignette works pixel by pixel), and only the pixels the crop keeps are
rendered. Without an angle, flips, turns and the crop are exact array operations. With an angle, one cubic
`warpAffine` in linear light maps the crop from the source at the source's resolution, then it is resized like
any other image (area averaging down). A photo without geometry skips all of it, so its pixels are what they were
before Phase 6 (the golden images didn't change).

- **Tone stays put**: tone anchors and auto exposure measure the whole photo, so cropping never changes the
  brightness.
- **Vignette** is relative to the crop (post-crop vignette).
- **Sharpening** scales with the crop's width in full-size pixels, so it means the same at every size.
- **Before** (Photo view) is the photo's default look with the edit's geometry, so Before and Split line up.

**Exports** work inside the photo's own crop: the export's aspect crop, output size and decode choice
([export.md](export.md)) are computed in the edited photo's pixels, and the worker maps that part of the crop
from the decode in one step. A straightened full-size export peaks at ~1.76 GiB per worker (1.67 GiB
unstraightened), so `WORKER_PEAK_BYTES` is 1.8 GiB.

Previews and exports of the same edit frame the same picture (checked by `tests/test_geometry_golden.py`). Fine
detail differs a little, since a preview resamples the 2048 px working base and an export its own decode.

## The crop tool

The **Crop** button (key **R**) opens it in the Photo view. It shows the photo as shot (`preview?upright=true`)
and turns, flips and straightens it on screen, so the straighten slider moves instantly; the crop rectangle sits
on top. Turning, flipping, straightening and the aspect menu ask core for the fitted crop (`geometry/preview`,
nothing saved); dragging the corners, edges or the middle uses the same "inside the straightened image" rule in
the browser, so a drag stops at the photo's edge. **Done** (Enter) checks the crop with core once more and saves
it through the photo's edit session: one undo step, like a slider. **Cancel** (Esc) drops the draft.

## Zoom view

**Fit / 50% / 100%** in the Photo view's header; **Z** toggles Fit ↔ 100 %, a click on the photo zooms in
there, and a click without dragging (or Esc) goes back. Drag to pan. The view shows tiles of 512 px of the
edited photo, rendered by the exact pipeline with the edit's own sharpening (an export preset's output sharpening
isn't shown: it depends on the output size). Tiles are cached on disk by edit revision, like previews.

| Level | Comes from | First time (DSCF5437, this machine) | RAM |
|---|---|---|---|
| 50 % | LibRaw's half-size decode, kept unresized | 0.4 s | 75 MiB per photo, 2 kept |
| 100 % | the full decode (single-threaded, deterministic, as for full-size exports) | 12.5 s (up to ~25 s on a busy machine) | 298 MiB, 1 kept |

While the full decode runs, the 50 % tiles are shown enlarged with "Loading full size…". A straightened photo
also needs its geometry applied once per level (0.65 s and ~260 MiB at 100 %). After that, a tile takes ~0.15 s.
Stitched tiles equal a whole render within float rounding (identical 8-bit pixels): a margin is rendered for
sharpening and cut off, and the vignette is placed relative to the whole photo.

## Subjects and suggested crops (Phase 6b)

The code finds each photo's **main subject** so a crop can frame it: in the crop tool's **Suggest crop** and in
exports whose aspect crop is set to **Frame the crop on: the photo's subject** (the built-in Instagram presets).
The code is in `src/photoedit/core/subject/`.

**Coordinates.** Subject boxes are in *upright* photo coordinates (0..1 of the photo as shot, before any flip,
turn, straighten or crop). Detection never depends on the edit, and a turn never moves a box; core maps a box
into an edited frame when it needs to (`subject_in_frame`, `subject_in_crop` in `core/geometry.py`).

**What is found** (on the photo's default look at the 2048 px working size):

| Finder | What it gives | Notes |
|---|---|---|
| YOLOX-S (OpenCV Model Zoo, Apache-2.0) | cars (car/truck/bus), motorcycles, aircraft (a helicopter too), animals (cat, dog, bird…), people | 12 overlapping 640 px tiles + the whole frame, merged per kind; a box inside a better one of its kind is a part and dropped. ~4 s per photo |
| YuNet (OpenCV Model Zoo, MIT) | human faces | OpenCV 5 dropped the Haar cascades; ~0.1 s |
| Sharpness | regions much sharper than the photo's own spread (a panned car) | only ranks; never the subject alone |
| Spectral-residual saliency | what stands out | only ranks; never the subject alone |
| Camera focus point | Fujifilm FocusPixel + AF mode from the maker note | stands in when nothing is recognized |

Both models are fetched once by `photoedit models fetch` into `cache/models/` and checked by SHA-256 (the user
approved the exact files). Without them, detection uses the other cues and says so.

**Choosing the main subject** (`choose.py`): each candidate's score × its kind's priority (vehicles and animals
first, then faces, then people) × a size factor (not a speck, not the whole frame) × how sharp it is compared to
the photo × a bonus when the camera focused inside it. People and faces next to a vehicle count weakly (the
crowd, the marshals). Close vehicles of the same kind become one subject (a tandem drift). Only a *recognized*
candidate can be the subject: on a sunset or an empty track the tool doesn't guess (decided 2026-10-12), and the
crop follows the camera's focus point, or centers. A box **set by hand** (crop tool → Set subject) always wins;
it is saved in the photo's edit file and changes no pixels. Results are stored in the catalog per detection
identity (models, OpenCV, the render engine, `CHOOSER_VERSION`), so the first look at a photo takes ~6 s and
later ones are instant, and an export of the same photo always frames the same subject.

**Suggested crop** (`suggest.py`): the largest crop of the ratio inside the straightened photo that keeps the
subject plus a 5 % margin (the margin stops at the photo's edge). It is exact geometry: for each size, the
possible centers form a convex polygon; the size comes from bisection, and the center is the point of the
polygon closest to the placement's target, either the subject's center (**Centered**) or the thirds
intersection on the subject's side of the frame (**On the thirds**; the 3×3 grid, key **G**, shows it).
**Zoom** makes it tighter, up to where the subject plus margin fills the crop. In the crop tool, the locked
ratio keeps its orientation (4:5 stays portrait on a landscape photo; **Swap** turns it).

**Export anchor `subject`.** The export's aspect crop keeps the size of a centered one and moves to frame the
subject (mapped into the edited photo: through its geometry and cut to its crop). Photos without a subject are
centered and say so in the plan. Missing detections run when the plan is made (several photos at once) and are
stored, so the export reuses them. The plan shows each photo's subject and its score.

**Evaluation** (`photoedit subject eval`): 44 photos labeled by hand across the four sample folders
(`tests/data/subject-labels.json`). A hit is the labeled box's center inside the found box (or IoU ≥ 0.3); a crop
is right when the 4:5 suggestion keeps ≥ 95 % of the labeled box (of what a crop that size could keep). Photos
labeled "no subject" are right when nothing is framed or the crop stays centered. Results (2026-10-12):

| Folder | Photos | Subject found | 4:5 crop keeps it |
|---|---|---|---|
| 2026-07-26 drift | 12 | 92 % | 92 % |
| 2026-08-11 both cats | 12 | 83 % | 92 % |
| 2026-08-16 rally | 14 | 100 % | 100 % |
| 2026-08-17 orange cat + sunsets | 6 | 83 % | 83 % |

The targets were 80 % / 90 % per folder. The last folder misses by its one sunset (DSCF6288), whose crop follows
the camera's focus point onto the TV tower; the user accepted this. The other misses: the empty drift track (a
spectator is framed), a shop test shot (a face on a TV screen) and the black cat on its back (only part of it is
boxed; its crop is still right). Uncertain photos are meant to be reviewed before export: Phase 6c. The contact
sheet (`output/contact-sheets/subject-eval.jpg`) shows each labeled box, the found one with its score, and the
suggested crop. `--results FILE` writes what was found per photo; `tests/data/subject-golden.json` holds the
stored results the golden test compares a fresh detection against.

## CLI

```
photoedit crop show DSCF5437
photoedit crop set DSCF5437 --aspect 4:5 --angle -2.5
photoedit crop set DSCF5437 --rotate 90 --flip-h
photoedit crop set DSCF5437 --crop 0.1,0,0.9,1
photoedit crop reset DSCF5437
```

```
photoedit crop suggest DSCF5437 --aspect 4:5 [--orientation portrait] [--placement thirds] [--zoom 1.5] [--apply]
photoedit subject show DSCF5437
photoedit subject detect --folder "C:/Users/you/Pictures/2026/2026-08-16"
photoedit subject eval
photoedit models fetch
```

`--aspect free` unlocks the ratio. An angle or aspect change fits the crop; an explicit `--crop` that doesn't fit
is refused with the reason (exit code 1).
