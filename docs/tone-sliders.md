# Tone sliders (P3.24)

Highlights, Shadows, Whites, Blacks and Contrast act on **each photo's own tonal range** (decided 2026-10-09 after the
Phase 3 human test), not at fixed scene brightness.

## Why

The first version placed the four bands at fixed stops above and below scene mid gray (whites +2…+5 stops, blacks
−4…−9). Measured on the 67 X-T3 samples (scene luminance of the default render, in stops from mid gray):

| | 0.5 % (black point) | median | 99.5 % (white point) |
|---|---|---|---|
| darkest photo | −9.1 | −5.8 | −2.6 |
| brightest photo | −4.7 | −0.8 | +2.4 |

Most photos never get near mid gray +2, so Whites changed nothing on DSCF5437 and Highlights barely acted. Mid gray
also sits **above the median pixel of every sample** (by 0.8–5.8 stops), so Contrast, which pivoted on it, mostly
darkened (+) or brightened (−) the whole photo.

## How it works

1. **Anchors.** The black and white points are the 0.5 % and 99.5 % luminance percentiles of the default render's
   scene luminance (as-shot white balance, camera profile, exposure 0), measured on a 512 px copy of the decoded
   image (`core/render/anchors.py`). Every size of a photo uses the same numbers: they are measured once and stored in
   the catalog (schema v3) with the render identity, and measured again after an engine change.
2. **Bands.** The middle of the range is the **pivot**. Each band is a quarter of the range wide on either side of its
   center: Shadows and Highlights halfway between the pivot and the ends, Blacks and Whites so that their full effect
   is reached at the black / white point. Photos narrower than 4 stops get bands as if they spanned 4 stops. The bands
   move with the Exposure slider.
3. **Curve.** Each slider changes the slope of a luminance curve (in stops) inside its band. The slope is integrated
   from the pivot, so Highlights/Whites only move pixels above the pivot and Shadows/Blacks only below it, and the
   curve is monotone for any values. At ±100 everything past a band moves by: Whites 1, Highlights 1, Shadows 2,
   Blacks 2.5 stops. The local slope stays within ×1/8…×8, so a very narrow photo gets a smaller shift instead of a
   flattened or posterized band. Contrast then scales the curve around the pivot (±100 → slope ×1.52 / ×0.66).
   Colors keep their ratios (the curve scales each pixel's RGB by one gain).

`ENGINE_VERSION` 2. Unedited renders are unchanged (the curve only runs when a tone slider is set).

## Acceptance (all 67 samples)

`tests/test_tone_sliders_real.py` (`-m golden`) renders each sample at 1600 px with each of the four sliders at −100
and +100. Among the slider's own pixels (the core of its band plus everything it moves beyond it, leaving out pixels
already black on screen, below 3/255), at least 25 % must change by 2 levels or more. All 67 pass.

Whites, Highlights and Shadows reach ~100 % on most photos. The lowest values are Shadows and Blacks on the four
darkest photos (black point −8 to −9 stops), where the shadows sit in the camera profile's toe and one stop is only
a few display levels. On the contact sheets they still visibly lift or deepen the shadows.

On night shots (about half the samples: deep darks plus a few bright lights) the range above the pivot holds only the
lights, ~1 % of the frame. Whites and Highlights then act on the lights, as they would in Lightroom.

Try it: `uv run photoedit contact-sheet DSCF5523 --group tone` (night), `DSCF5438` (dark), `DSCF5437` (backlit).
