"""Fit a camera profile from RAW + camera JPEG pairs: the "match the camera" default look (decided
2026-10-08).

Samples are rendered with the production ``render()`` (sharpening off), so a fitted profile looks in the app
exactly as it scored here. The parameter vector maps to a valid ``CameraProfile`` by construction: matrix rows
sum to 1 (grays stay gray), the tone curve is a cumulative softplus (monotone, inside 0..1), HSL is bounded.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt
from PIL import Image, ImageOps
from scipy.optimize import least_squares

from photoedit.core import color
from photoedit.core.cache import resize_linear
from photoedit.core.decode import LinearImage, decode_linear
from photoedit.core.render.pipeline import render
from photoedit.core.render.profile import GENERIC, CameraProfile, ProfileCurvePoint
from photoedit.models.adjustments import AdjustmentParams, Hsl

type F32 = npt.NDArray[np.float32]
type F64 = npt.NDArray[np.float64]

FIT_LONG_EDGE = 512
SAMPLES_PER_PHOTO = 2000
EVAL_SAMPLES_PER_PHOTO = 20000
HOLDOUT_EVERY = 4
CURVE_STOPS = (-10.0, -7.0, -5.0, -4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.5)
CURVE_BLACK = (-14.0, 0.0)  # fixed end points: true black and full white
CURVE_WHITE = (7.0, 1.0)
BANDS = ("red", "orange", "yellow", "green", "aqua", "blue", "purple", "magenta")
MATRIX_LIMIT = 0.6
HSL_LIMIT = 60.0
# Regularization, in ΔE-equivalents per sample for a parameter at its limit: small nudges toward neutral
# so the fit only uses matrix/HSL terms that clearly pay for themselves (and the profile stays editable).
_REGULARIZATION = (
    2.5  # tuned on the X-T3 samples: 0.4..2.5 all give held-out ΔE ≈ 2.3; stronger stays neutral
)
# Curve smoothness: penalizes bends (second differences of the knot values, in display %), so stretches of the
# curve with few unclipped samples follow their neighbours instead of collapsing into flat plateaus.
_SMOOTHNESS = 0.05  # 0.15+ flattens the highlight shoulder into a clip

_NO_SHARPENING = AdjustmentParams.model_validate({"detail": {"sharpening": {"amount": 0}}})
_N_CURVE = len(CURVE_STOPS)
_N_PARAMS = 1 + 6 + _N_CURVE + 3 * len(BANDS)


@dataclass(frozen=True)
class PairSamples:
    name: str
    scene: F32  # (N, 3) scene-linear Rec.2020, as-shot white balance
    target: F32  # (N, 3) camera JPEG, sRGB-encoded 0..1


@dataclass
class FitReport:
    profile: CameraProfile
    train: list[str]
    holdout: dict[str, tuple[float, float]] = field(default_factory=dict)  # name → (ΔE before, ΔE after)
    iterations: int = 0

    @property
    def mean_before(self) -> float:
        return float(np.mean([b for b, _ in self.holdout.values()]))

    @property
    def mean_after(self) -> float:
        return float(np.mean([a for _, a in self.holdout.values()]))


# ----------------------------------------------------------------- data


def load_pair(
    raw_path: Path, jpeg_path: Path, samples: int, seed: int, long_edge: int = FIT_LONG_EDGE
) -> PairSamples:
    """Aligned, downscaled pixel samples of one RAW and its camera JPEG. Both files are only read."""
    base = resize_linear(decode_linear(raw_path, half_size=True), long_edge)
    scene = color.apply_matrix(base.pixels, base.to_rec2020)
    height, width = scene.shape[:2]
    with Image.open(jpeg_path) as image:
        jpeg = np.asarray(ImageOps.exif_transpose(image).convert("RGB"), dtype=np.float32) / 255
    jpeg_linear = cv2.resize(color.srgb_decode(jpeg), (width, height), interpolation=cv2.INTER_AREA)
    target = color.srgb_encode(np.clip(jpeg_linear, 0, 1)).astype(np.float32)

    valid = np.ones((height, width), dtype=bool)
    # The JPEG has lens corrections (distortion, vignetting) the RAW lacks: use the center 90 % only.
    my, mx = round(height * 0.05), round(width * 0.05)
    valid[:my], valid[-my:], valid[:, :mx], valid[:, -mx:] = False, False, False, False
    valid &= base.pixels.max(axis=-1) < 0.99  # clipped in the RAW: no information to fit
    valid &= (target.max(axis=-1) < 0.98) & (target.max(axis=-1) > 0.02)  # clipped or crushed in the JPEG
    luma = target @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    gy, gx = np.gradient(luma)
    gradient = np.hypot(gx, gy)
    valid &= gradient < np.percentile(gradient, 80)  # edges: sharpening and tiny misalignment dominate there
    indices = np.flatnonzero(valid)
    rng = np.random.default_rng(seed)
    chosen = np.sort(rng.choice(indices, size=min(samples, indices.size), replace=False))
    return PairSamples(
        name=raw_path.stem,
        scene=scene.reshape(-1, 3)[chosen].astype(np.float32),
        target=target.reshape(-1, 3)[chosen],
    )


def load_pairs(
    pairs: Sequence[tuple[Path, Path]], samples: int, *, workers: int = 8, seed: int = 0
) -> list[PairSamples]:
    if workers <= 1:
        return [load_pair(r, j, samples, seed + i) for i, (r, j) in enumerate(pairs)]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(load_pair, r, j, samples, seed + i) for i, (r, j) in enumerate(pairs)]
        return [f.result() for f in futures]


# ----------------------------------------------------------------- parameters ↔ profile


def _softplus(x: F64) -> F64:
    out: F64 = np.logaddexp(0, x)
    return out


def _inverse_softplus(y: F64) -> F64:
    out: F64 = np.log(np.expm1(np.maximum(y, 1e-6)))
    return out


def unpack(theta: F64, template: CameraProfile) -> CameraProfile:
    """Parameter vector → profile (identity fields such as id and camera come from ``template``)."""
    baseline = float(theta[0])
    o = theta[1:7]
    matrix = (
        (1 - o[0] - o[1], float(o[0]), float(o[1])),
        (float(o[2]), 1 - o[2] - o[3], float(o[3])),
        (float(o[4]), float(o[5]), 1 - o[4] - o[5]),
    )
    cumulative = np.cumsum(_softplus(theta[7 : 7 + _N_CURVE]))
    values = 1 - np.exp(-cumulative)
    points = [CURVE_BLACK, *zip(CURVE_STOPS, values.tolist(), strict=True), CURVE_WHITE]
    # HSL parameters are stored ÷100 so every parameter is O(1) for the optimizer's finite differences.
    hsl_values = np.clip(theta[7 + _N_CURVE :] * 100, -100, 100).reshape(len(BANDS), 3)
    hsl = Hsl.model_validate(
        {
            band: {"hue": h, "saturation": s, "luminance": lum}
            for band, (h, s, lum) in zip(BANDS, hsl_values, strict=True)
        }
    )
    return template.model_copy(
        update={
            "baseline_exposure": baseline,
            "matrix": tuple(tuple(float(v) for v in row) for row in matrix),
            "tone_curve": [ProfileCurvePoint(stops=s, value=float(v)) for s, v in points],
            "hsl": hsl,
        }
    )


def initial_parameters(baseline: float) -> F64:
    """Start from the generic curve, an identity matrix and neutral HSL."""
    generic = {p.stops: p.value for p in GENERIC.tone_curve}
    stops = [p.stops for p in GENERIC.tone_curve]
    values = np.interp(CURVE_STOPS, stops, [generic[s] for s in stops])
    cumulative = -np.log(1 - np.clip(values, 1e-4, 0.999))
    increments = np.diff(np.concatenate([[0.0], cumulative]))
    theta = np.zeros(_N_PARAMS)
    theta[0] = baseline
    theta[7 : 7 + _N_CURVE] = _inverse_softplus(increments)
    return theta


def bounds() -> tuple[F64, F64]:
    low = np.full(_N_PARAMS, -np.inf)
    high = np.full(_N_PARAMS, np.inf)
    low[0], high[0] = -3, 4
    low[1:7], high[1:7] = -MATRIX_LIMIT, MATRIX_LIMIT
    low[7 + _N_CURVE :], high[7 + _N_CURVE :] = -HSL_LIMIT / 100, HSL_LIMIT / 100
    return low, high


# ----------------------------------------------------------------- rendering + scoring


def render_samples(scene: F32, profile: CameraProfile) -> F32:
    """Render scene-linear samples with the production pipeline (as an N×1 image, no sharpening)."""
    image = LinearImage(pixels=scene[:, None, :], to_rec2020=np.eye(3), is_raw=True)
    out: F32 = render(image, _NO_SHARPENING, profile, original_width=1)[:, 0, :]
    return out


def encoded_to_oklab(encoded: F32) -> F32:
    linear = color.apply_matrix(color.srgb_decode(encoded), color.REC2020_FROM_SRGB)
    return color.rec2020_to_oklab(linear)


def encoded_to_cielab(encoded: F32) -> F64:
    linear = color.srgb_decode(encoded.astype(np.float64))
    lab: F64 = color.xyz_to_cielab(color.apply_matrix(linear, color.XYZ_FROM_SRGB)).astype(np.float64)
    return lab


def mean_delta_e(samples: PairSamples, profile: CameraProfile) -> float:
    ours = encoded_to_cielab(render_samples(samples.scene, profile))
    return float(np.mean(color.delta_e_2000(ours, encoded_to_cielab(samples.target))))


def estimate_baseline(pairs: Sequence[PairSamples]) -> float:
    """Exposure that best matches mid-tone brightness under the generic curve (a starting point only)."""
    candidates = np.arange(-2, 3.01, 0.25)
    errors = []
    for ev in candidates:
        profile = GENERIC.model_copy(update={"baseline_exposure": float(ev)})
        errors.append(
            sum(
                abs(float(np.median(render_samples(p.scene, profile))) - float(np.median(p.target)))
                for p in pairs
            )
        )
    return float(candidates[int(np.argmin(errors))])


def fit_profile(
    train: Sequence[PairSamples],
    template: CameraProfile,
    *,
    max_evaluations: int = 4000,
    regularization: float = _REGULARIZATION,
    smoothness: float = _SMOOTHNESS,
    progress: Callable[[str], None] | None = None,
) -> tuple[CameraProfile, int]:
    """Least-squares fit of the profile parameters to the training samples (robust soft-L1 loss on OKLab)."""
    scene = np.concatenate([p.scene for p in train])
    target_lab = encoded_to_oklab(np.concatenate([p.target for p in train]))
    weight = regularization * math.sqrt(scene.shape[0])
    smooth = smoothness * math.sqrt(scene.shape[0])
    spacing = np.diff(CURVE_STOPS)
    scale = np.concatenate([np.full(6, 1 / MATRIX_LIMIT), np.full(3 * len(BANDS), 100 / HSL_LIMIT)])

    def residuals(theta: F64) -> F64:
        profile = unpack(theta, template)
        lab = encoded_to_oklab(render_samples(scene, profile))
        image_terms = ((lab - target_lab) * 100).ravel()  # OKLab × 100 ≈ ΔE-sized units
        prior = weight * np.concatenate([theta[1:7], theta[7 + _N_CURVE :]]) * scale
        values = 1 - np.exp(-np.cumsum(_softplus(theta[7 : 7 + _N_CURVE])))
        slopes = np.diff(values) / spacing
        bends = smooth * np.diff(slopes) * 100
        return np.concatenate([image_terms, prior, bends])

    baseline = estimate_baseline(train)
    if progress:
        progress(f"starting fit from baseline exposure {baseline:+.2f} EV on {scene.shape[0]} samples")
    low, high = bounds()
    start = np.clip(initial_parameters(baseline), low + 1e-9, high - 1e-9)
    result = least_squares(
        residuals,
        start,
        bounds=(low, high),
        loss="soft_l1",
        f_scale=3.0,
        x_scale="jac",
        # Renders are float32: the default step (~1e-8) is below what they resolve and every gradient reads 0.
        diff_step=np.full(_N_PARAMS, 1e-3),
        max_nfev=max_evaluations,
    )
    return unpack(result.x, template), int(result.nfev)


def fit_and_evaluate(
    pairs: Sequence[tuple[Path, Path]],
    template: CameraProfile,
    *,
    workers: int = 8,
    progress: Callable[[str], None] | None = None,
) -> FitReport:
    """Fit on 3 of every 4 pairs, report ΔE2000 before (generic) and after (fitted) on the 4th."""
    ordered = sorted(pairs)
    holdout_idx = set(range(HOLDOUT_EVERY - 1, len(ordered), HOLDOUT_EVERY))
    train_pairs = [p for i, p in enumerate(ordered) if i not in holdout_idx]
    holdout_pairs = [p for i, p in enumerate(ordered) if i in holdout_idx]
    if progress:
        progress(f"loading {len(train_pairs)} training and {len(holdout_pairs)} held-out pairs")
    train = load_pairs(train_pairs, SAMPLES_PER_PHOTO, workers=workers)
    holdout = load_pairs(holdout_pairs, EVAL_SAMPLES_PER_PHOTO, workers=workers, seed=1000)
    profile, evaluations = fit_profile(train, template, progress=progress)
    report = FitReport(profile=profile, train=[p.name for p in train], iterations=evaluations)
    for samples in holdout:
        report.holdout[samples.name] = (mean_delta_e(samples, GENERIC), mean_delta_e(samples, profile))
    return report


def format_report(report: FitReport) -> str:
    profile = report.profile
    lines = [
        f"# Camera profile fit: {profile.name}",
        "",
        f"- Trained on {len(report.train)} RAW + JPEG pairs, evaluated on {len(report.holdout)} others.",
        f"- Baseline exposure: {profile.baseline_exposure:+.3f} EV",
        f"- Matrix rows: {[[round(v, 4) for v in row] for row in profile.matrix]}",
        f"- Function evaluations: {report.iterations}",
        "",
        "| Held-out photo | ΔE2000 generic | ΔE2000 fitted |",
        "|---|---:|---:|",
    ]
    lines += [
        f"| {name} | {before:.2f} | {after:.2f} |" for name, (before, after) in sorted(report.holdout.items())
    ]
    lines += ["", f"**Mean ΔE2000: {report.mean_before:.2f} → {report.mean_after:.2f}** (target ≤ 3).", ""]
    return "\n".join(lines)
