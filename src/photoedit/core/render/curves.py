"""Monotone cubic curves (Fritsch-Carlson PCHIP) and the lookup tables built from them.

PCHIP never overshoots its points: where the points rise, the curve rises; where they flatten, it flattens.
That keeps tone curves free of the bumps an ordinary spline adds between points.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

type F64 = npt.NDArray[np.float64]


def pchip(xs: Sequence[float], ys: Sequence[float], x: npt.ArrayLike) -> F64:
    """Evaluate the shape-preserving cubic through ``(xs, ys)`` at ``x`` (constant beyond the end points)."""
    px = np.asarray(xs, dtype=np.float64)
    py = np.asarray(ys, dtype=np.float64)
    if px.size < 2 or np.any(np.diff(px) <= 0):
        raise ValueError("curve points need at least two strictly increasing x values")
    slopes = _slopes(px, py)
    q = np.clip(np.asarray(x, dtype=np.float64), px[0], px[-1])
    k = np.clip(np.searchsorted(px, q, side="right") - 1, 0, px.size - 2)
    h = px[k + 1] - px[k]
    t = (q - px[k]) / h
    t2, t3 = t * t, t * t * t
    out: F64 = (
        (2 * t3 - 3 * t2 + 1) * py[k]
        + (t3 - 2 * t2 + t) * h * slopes[k]
        + (-2 * t3 + 3 * t2) * py[k + 1]
        + (t3 - t2) * h * slopes[k + 1]
    )
    return out


def _slopes(x: F64, y: F64) -> F64:
    h = np.diff(x)
    delta = np.diff(y) / h
    m = np.zeros_like(x)
    if x.size == 2:
        m[:] = delta[0]
        return m
    # Interior: weighted harmonic mean of the neighbouring secants, 0 at a local extremum (Fritsch-Butland).
    for k in range(1, x.size - 1):
        if delta[k - 1] * delta[k] > 0:
            w1 = 2 * h[k] + h[k - 1]
            w2 = h[k] + 2 * h[k - 1]
            # (w1 + w2) / (w1 / d0 + w2 / d1), multiplied out so tiny secants can't overflow.
            denominator = w1 * delta[k] + w2 * delta[k - 1]
            if denominator != 0:
                m[k] = (w1 + w2) * delta[k - 1] * delta[k] / denominator
    m[0] = _end_slope(h[0], h[1], delta[0], delta[1])
    m[-1] = _end_slope(h[-1], h[-2], delta[-1], delta[-2])
    return m


def _end_slope(h0: float, h1: float, d0: float, d1: float) -> float:
    """One-sided three-point estimate, limited so the end interval stays monotone (as in SciPy's PCHIP)."""
    m = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)
    if np.sign(m) != np.sign(d0):
        return 0.0
    if np.sign(d0) != np.sign(d1) and abs(m) > abs(3 * d0):
        return 3 * d0
    return float(m)
