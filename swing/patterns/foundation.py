"""Phase 13 T2.SB2 - foundation pattern primitives (spec section 5.1).

Pure-logic primitives consumed by T2.SB3 (VCP + flat base + cup-with-handle)
and T2.SB4 (high-tight-flag + double-bottom-W) detectors. ZERO DB writes
in this module other than the explicitly read-only ``current_stage``
wrapper at section 5.1.5 which queries shipped Phase 4 surfaces.

LOCKs (per dispatch brief section 6):
- L1: pure functions only; no I/O, no globals, no logging from inside
  primitive functions.
- L2: ZERO DB writes (current_stage may READ).
- L3: frozen dataclasses for Swing + CandidateWindow + VolumeSegment.
- L4: Literal type hints are not runtime-enforced; data-integrity-path
  fields validate in ``__post_init__``.
- L5: ASCII-only output paths; no non-ASCII glyphs in strings/docstrings.

T-A.2.1 ships smoothing primitives. Later tasks extend in-place.
"""
from __future__ import annotations

import numpy as np

# ============================================================================
# Section 5.1.1 - Smoothing primitives (T-A.2.1)
# ============================================================================


def smooth_ema(prices: np.ndarray, window: int) -> np.ndarray:
    """Exponential Moving Average with smoothing factor alpha = 2/(window+1).

    Implements the standard EMA recursion ``y[i] = alpha*x[i] + (1-alpha)*y[i-1]``
    seeded with ``y[0] = x[0]``. Output length matches input length.

    Matches ``pandas.Series.ewm(span=window, adjust=False).mean()`` semantics
    element-wise. Window must be >= 1.
    """
    if window < 1:
        raise ValueError(f"window must be >= 1, got {window}")
    arr = np.asarray(prices, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"prices must be 1-D, got shape {arr.shape}")
    n = arr.shape[0]
    if n == 0:
        return arr.copy()
    alpha = 2.0 / (window + 1)
    out = np.empty(n, dtype=float)
    out[0] = arr[0]
    for i in range(1, n):
        out[i] = alpha * arr[i] + (1.0 - alpha) * out[i - 1]
    return out


def smooth_kernel_regression(prices: np.ndarray, bandwidth: float) -> np.ndarray:
    """Nadaraya-Watson kernel regression with Gaussian kernel.

    For each bar index ``i``, output is the kernel-weighted mean of all
    input prices, with weight ``K((i-j)/bandwidth)`` where ``K`` is the
    standard Gaussian. Bandwidth is in bar-index units.

    Spec section 5.1.1 LOCK: "historical only, no recent-bar". This
    centered kernel introduces no lag at interior points but blends
    future bars into the smoothed estimate; callers MUST NOT consume the
    output of this function for recent-bar trading decisions. Reserved
    for stable historical-exemplar curation and template-matching
    reference computation.
    """
    if bandwidth <= 0:
        raise ValueError(f"bandwidth must be > 0, got {bandwidth}")
    arr = np.asarray(prices, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"prices must be 1-D, got shape {arr.shape}")
    n = arr.shape[0]
    if n == 0:
        return arr.copy()
    idx = np.arange(n, dtype=float)
    out = np.empty(n, dtype=float)
    for i in range(n):
        diffs = (i - idx) / bandwidth
        weights = np.exp(-0.5 * diffs * diffs)
        total = float(np.sum(weights))
        out[i] = float(np.sum(weights * arr)) / total
    return out
