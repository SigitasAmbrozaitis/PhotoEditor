# Geometry and the zoom view

How a photo's crop, straighten angle, quarter turn and flips work (Phase 6a), and how the zoom view shows
50 % and 100 %. The math is in `src/photoedit/core/geometry.py`, the pixels in `core/render/warp.py`, and the
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

## CLI

```
photoedit crop show DSCF5437
photoedit crop set DSCF5437 --aspect 4:5 --angle -2.5
photoedit crop set DSCF5437 --rotate 90 --flip-h
photoedit crop set DSCF5437 --crop 0.1,0,0.9,1
photoedit crop reset DSCF5437
```

`--aspect free` unlocks the ratio. An angle or aspect change fits the crop; an explicit `--crop` that doesn't fit
is refused with the reason (exit code 1).
