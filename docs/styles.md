# Styles (Phase 4)

A **style** is a reusable look: a few parameter values plus **adaptive rules** that fit it to each photo. Photos
reference their style by id, so changing a style changes every photo that uses it (decisions 2026-10-09, PLAN §0).

The hard part, as the user put it: photos are shot with manual exposure tweaked while shooting, of very different
subjects (rally/drift cars that are often small in the frame, an orange and a **black** cat, sunsets, cities). One
fixed set of values can't look the same on all of them. Phase 4 builds the tools to measure and iterate on that;
Phase 8 (style creation) and the AI (Phase 7) build on them.

## Files

```
styles/<id>/
  style.json        the style (source of truth; schema below)
  README.md         generated from style.json on every save; don't edit it
  history/v<N>.json every saved version (compare, revert)
  samples/          before/after JPEGs rendered from your photos (local only, git-ignored)
```

`style.json` (format version 1):

```json
{
  "schema_version": 1,
  "id": "test-warm-matte",
  "name": "Test · Warm Matte",
  "description": "…",
  "best_for": ["cats", "golden hour"],
  "avoid_on": ["night scenes with point lights"],
  "values": { "tone.contrast": -15, "hsl.green.saturation": -25 },
  "rules": [
    { "type": "exposure", "metering": "middle", "target": null, "use_group": true, "strength": 100, "max_change": 1.5 },
    { "type": "white_balance", "mode": "as_shot", "temperature_offset": 400, "tint_offset": 0 }
  ],
  "test_photo_ids": ["…"],
  "samples": [],
  "created_at": "2026-10-09T20:23:00Z",
  "updated_at": "2026-10-09T20:23:00Z",
  "version": 1,
  "change_note": ""
}
```

- **`values`** are sparse dotted parameter names (the same names as the Photo view's sliders, see
  `models/adjustments.py`). Setting a value equal to its default still counts as "the style sets it". Not allowed:
  `geometry.*` (per photo), `white_balance.*` (use a white balance rule), and parameters of later phases (grain,
  clarity, …). Invalid values are rejected with the parameter's name, never clamped.
- **`rules`**: at most one per type, run in a fixed order (exposure, then white balance). Each has a `rule_version`;
  a file from a newer tool is refused with a clear message.
- The **look** (what renders) is `values` + `rules`. Its hash (`look_hash`) is part of every styled photo's render
  key, so a renamed style or a new description never re-renders anything.

## How a photo's parameters come together

```
camera defaults  ←  style values  ←  style rules (on the photo's measurements)  ←  the photo's own tweaks
```

- The photo's own tweaks are stored as differences from the styled values, so a later change to the style still
  reaches every value you didn't touch, and moving a slider back to the style's value makes it follow the style.
- **Applying a style** drops your tweaks of what the style sets (its values, plus exposure / white balance when it has
  those rules) and keeps the rest (e.g. a crop). Removing a style keeps every tweak as it was.
- **Reset all** in the Photo view drops the photo's own tweaks; the style stays. Double-clicking a slider goes back to
  the style's value.
- A missing or broken style never breaks the Library: the photo renders unstyled and says why.

## Adaptive rules

Each photo is measured once (512 px, default render, stored in the catalog with the render identity):

| Measure | What it is |
|---|---|
| middle | median brightness, stops from mid gray at exposure 0 |
| white | white point (99.5th percentile), stops |
| neutral WB | the Kelvin/tint that makes the photo's near-gray midtones gray (gray world restricted to near-grays; falls back to as shot when it finds no plausible light, e.g. a frame filled by the orange cat) |
| camera EV | EV100 = log2(N²/t) − log2(ISO/100) from EXIF: the exposure you dialed in |

### Exposure: which metering when

| Metering | Moves | Good for | Fails on |
|---|---|---|---|
| `middle` | the median to the target | ordinary scenes, overcast drift | dark subjects (black cat → gray), sunsets (darkened), warm lamp light |
| `highlights` | the white point to the target | low-key subjects whose bright parts are normal: the black cat on a lit floor, night streets | scenes with no real highlights (a dark room), backlit sun (the sun is the white point) |
| `camera_settings` | by the EV100 difference to the group | a **series in the same light** where you changed shutter/aperture/ISO (drift session, cats indoors) | different light between shots (rally stages, sun vs. shade): use per run of shots, not a whole folder |

- Without a group, `camera_settings` meters like `middle` (and says so). Missing EXIF also falls back.
- **Default targets** (measured on all 369 style sample photos, so an average photo barely changes):
  middle **−2.7** stops, highlights **−0.1** stops. A rule's `target` overrides them.
- `strength` (0–100 %) moves only part of the way; `max_change` (0–3 EV) caps the change. Every limit or fallback is
  named in the rule's result (Photo view, report, contact sheet).

### Even out a group

"Apply style…" → **Even out these photos** (CLI: `--even-out`) measures the selection and stores the group's medians
(middle, white point, camera EV) with every photo of it. A rule with `use_group` then targets the group instead of a
fixed number: the photos match each other. The group is stored, so a photo's render never depends on what is selected
later, and switching the style's metering mode later still works.

### White balance

| Mode | Result |
|---|---|
| `as_shot` + offsets | the camera's white balance, shifted. "+400 K" is given at 5500 K and applied as the same mired shift, so it looks alike under tungsten (+130 K at 3200 K) and daylight |
| `auto` + offsets | the neutral estimate, shifted. Can remove intentional warm light (on the 06:00 sunrise shots it wanted −1800 K) |
| `fixed` | the same Kelvin/tint everywhere (studio) |

No white balance rule = the style doesn't touch white balance.

## Writing a style by hand

1. Easiest: edit a photo, then **Save as style…** in its Adjust panel (choose groups; exposure as "match this photo's
   brightness"; white balance as an offset from as shot). The photo becomes the first test photo.
2. Or write `styles/<id>/style.json` as above (`id` = folder name, lowercase with hyphens), then
   `uv run photoedit style check`. The first change made through the tool keeps your version in `history/`.

## Iterating on a style

1. Give the style a **test set** of hard photos (Style detail → Test set → "Add N selected").
2. Change something (rules, a value, or **Update style from this photo**), with a change note.
3. Check: **Consistency** (Style detail, or `photoedit style report ID`): the spread of middle brightness and white
   point before → after; photos more than 0.5 stop from the rest are flagged. And look:
   `photoedit style contact-sheet ID --test-set` (each row labeled with what the rules did).
4. Compare with the previous version: History → Compare (side by side on the test set), or
   `photoedit style contact-sheet ID --test-set --version N` / `photoedit style diff ID N M`.
5. Keep it, or **Bring back** the old version (`photoedit style revert ID N`; saved as a new version, nothing lost).

## The two test styles (P4.12)

Both have the same test set of 10 hard photos from the four style sample folders: the black cat on a lit floor
(DSCF5580) and in a dark room (DSCF5601), the orange cat close up (DSCF5574), under a warm lamp (DSCF5598) and at
night (DSCF6283), a red sunset silhouette (DSCF6286), drift at 1/2000 ISO 1000 (DSCF5323) and 1/4000 ISO 4000
(DSCF5414), rally dust (DSCF6033) and a tree against the sun (DSCF6278).

- **Test · Warm Matte** (`test-warm-matte`): middle metering (uses the group), as shot +400 K, lower contrast,
  lifted blacks (tone curve), highlights −30, greens down, warm highlights / cool shadows, vignette −15.
- **Test · Classic B&W** (`test-classic-bw`): highlights metering, saturation −100, contrast +35, blacks −25.

Test set report (2026-10-09; spread = median absolute deviation / range, stops):

| Style | middle before → after | white before → after |
|---|---|---|
| Warm Matte | 0.70 / 5.36 → **0.00 / 2.36** | 1.01 / 3.27 → 0.37 / 2.95 |
| Classic B&W | 0.70 / 5.36 → 0.60 / 4.09 | 1.01 / 3.27 → **0.00 / 0.37** |

What remains for Warm Matte is the 1.5 EV limit on the two darkest photos (the black cat in the dark room, the tree
against the sun). The contact sheet also shows the known weak spots of `middle` metering: the warm lamp shot loses its
glow (−1.3 EV) and the sunset is pulled down 1.5 EV. These are the cases to tune in the Phase 4 human test.

Whole folders (each style on every photo of a folder, without "even out"):

| Folder | Photos | Style | middle: typical deviation | middle: range | white point: typical deviation |
|---|---|---|---|---|---|
| 2026-08-17 | 6 | test-warm-matte | 0.51 → 0.00 | 2.86 → 0.14 | 0.38 → 0.07 |
| 2026-08-17 | 6 | test-classic-bw | 0.51 → 0.26 | 2.86 → 0.63 | 0.38 → 0.00 |
| 2026-08-11 | 67 | test-warm-matte | 0.49 → 0.49 | 4.98 → 1.98 | 0.41 → 0.49 |
| 2026-08-11 | 67 | test-classic-bw | 0.49 → 0.30 | 4.98 → 6.04 | 0.41 → 0.00 |
| 2026-07-26 | 113 | test-warm-matte | 0.42 → 0.00 | 3.60 → 0.84 | 0.52 → 0.43 |
| 2026-07-26 | 113 | test-classic-bw | 0.42 → 0.40 | 3.60 → 2.45 | 0.52 → 0.00 |
| 2026-08-16 | 183 | test-warm-matte | 0.17 → 0.00 | 6.83 → 3.83 | 0.07 → 0.24 |
| 2026-08-16 | 183 | test-classic-bw | 0.17 → 0.24 | 6.83 → 4.46 | 0.07 → 0.00 |

Reading it: **middle metering** (Warm Matte) brings the middle brightness of the drift, rally and sunset folders to
the same value; **highlights metering** (Classic B&W) lines up the white points instead and leaves the middles where
the scenes put them. In the cats folder (2026-08-11) the 40 very dark indoor shots (median −5.4 stops) all hit the
1.5 EV limit, so the spread doesn't shrink: a larger `max_change`, "even out" per series, or highlights metering are
the knobs to try there. Measuring all 369 photos took 2.7 minutes with 6 threads (once; the numbers are stored).
