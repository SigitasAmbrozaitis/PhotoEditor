# Default look: camera profiles

An unedited photo renders through a **camera profile**, PhotoEditor's equivalent of a Lightroom camera profile.
It is the default look; every adjustment works on top of it. Decided 2026-10-08: the default look should **match the
camera's own JPEGs** (PLAN.md §0).

## What a profile contains

| Part | What it does |
|---|---|
| Baseline exposure | EV added before everything else |
| 3×3 matrix | Linear Rec.2020 → linear Rec.2020; each row sums to 1, so grays stay gray |
| Tone curve | Scene brightness (stops relative to 18 % gray) → display value, per channel, monotone |
| HSL | Small per-hue tweaks (8 bands), the same controls the user has |

Cameras without a shipped profile use the generic one (gentle S-curve, no color change). JPEG/TIFF originals are
already rendered, so they get no profile and an unedited render reproduces them.

Shipped profiles live in `src/photoedit/profiles/`; `profile_for(camera)` picks one by camera make and model.

## How the X-T3 profile was made

`uv run photoedit profile fit C:\Users\ambro\Pictures\2026\2026-08-11` (2026-10-08), on the 67 RAF + camera JPEG
pairs. All 67 were shot with **Provia/Standard at DR100** (read from the Fuji maker notes).

1. Each RAF is decoded (LibRaw half-size, as-shot white balance, linear Rec.2020) and the camera JPEG brought to the
   same size, both at 512 px.
2. Only the center 90 % is used (the JPEG has lens corrections the RAW doesn't). Pixels clipped in the RAW, clipped
   or crushed in the JPEG, and the 20 % with the strongest edges (sharpening, tiny misalignment) are left out;
   2000 random pixels per training photo remain.
3. Every 4th pair (16) is held out; the other 51 train the profile.
4. Robust least squares (soft-L1) minimizes the OKLab difference between **the production renderer's output** and
   the camera JPEG. Light priors keep the matrix and HSL near neutral unless they clearly help, and a small
   smoothness prior stops thinly sampled curve regions (very bright areas) from collapsing into flat plateaus.
   Tuning on the held-out set: matrix/HSL prior 0.4–2.5 all gave ≈ 2.3 ΔE (2.5 chosen: closest to neutral);
   smoothness above 0.1 flattened the highlight shoulder into a hard clip (0.05 chosen).
5. Score: **CIEDE2000** (ΔE00), the standard perceptual color difference: about 1 is just noticeable side by side,
   2–3 is close, above 5 is clearly different.

## Result

Mean ΔE2000 on the 16 held-out photos: **3.69 with the generic profile → 2.34 with the fitted profile** (target ≤ 3).

| Held-out photo | Generic | Fitted |
|---|---:|---:|
| DSCF5523 | 2.05 | 1.69 |
| DSCF5527 | 2.63 | 2.02 |
| DSCF5531 | 2.51 | 1.91 |
| DSCF5535 | 2.65 | 2.05 |
| DSCF5539 | 2.09 | 1.22 |
| DSCF5543 | 2.80 | 2.18 |
| DSCF5547 | 3.04 | 1.61 |
| DSCF5551 | 2.15 | 1.23 |
| DSCF5555 | 2.48 | 1.89 |
| DSCF5559 | 5.67 | 3.43 |
| DSCF5563 | 7.14 | 4.15 |
| DSCF5567 | 1.71 | 1.73 |
| DSCF5573 | 6.49 | 3.66 |
| DSCF5577 | 7.14 | 3.52 |
| DSCF5581 | 4.09 | 2.73 |
| DSCF5600 | 4.46 | 2.48 |

Fitted values: baseline exposure 0 EV (the tone curve absorbed Fuji's deliberate RAW underexposure: mid gray maps to
0.649, where plain sRGB encoding gives 0.461), matrix rows `[0.94, 0, 0.06] [0.18, 0.61, 0.22] [-0.08, 0.15, 0.93]`,
HSL practically neutral (yellow luminance +7).

**Known differences.** The four photos still above 3 are the close-up cat portraits: the camera renders bright fur
a little lighter than the profile. Sharpening, noise reduction and the image corners (lens corrections) differ by
design. Matching more closely would need a 3D LUT inside the profile (Phase 8's fallback F3), which wasn't needed to
meet the target.

**Dynamic range.** Fujifilm DR200/DR400 shots are underexposed by 1/2 EV on purpose; the renderer adds that back
from the DR value in the maker notes. Only DR100 could be checked against these samples.
