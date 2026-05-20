"""Phase 13 T2.SB2 T-A.2.1 — discriminating tests for smoothing primitives.

Per plan §G.3 T-A.2.1 Step 1: 4 failing tests covering
``smooth_ema`` and ``smooth_kernel_regression`` per spec §5.1.1 LOCK.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing.patterns.foundation import smooth_ema, smooth_kernel_regression


def test_smooth_ema_matches_pandas_ewm_reference() -> None:
    """``smooth_ema(prices, window=5)`` matches the pandas
    ``ewm(span=5, adjust=False).mean()`` reference output element-wise.
    """
    rng = np.random.default_rng(seed=42)
    prices = rng.normal(loc=100.0, scale=2.0, size=50).astype(float)
    reference = pd.Series(prices).ewm(span=5, adjust=False).mean().to_numpy()
    out = smooth_ema(prices, window=5)
    assert out.shape == prices.shape
    np.testing.assert_allclose(out, reference, rtol=1e-12, atol=1e-12)


def test_smooth_ema_step_impulse_response_at_step_is_approximately_one_third() -> None:
    """EMA lag verified via input-step impulse response: constant 100 for N
    steps, then step to 200. At the step bar, EMA(window=5) value is
    100 + alpha*(200-100) where alpha=2/(5+1)=1/3 → ~133.33. After several
    bars, EMA approaches 200 smoothly.
    """
    prices = np.concatenate(
        [np.full(20, 100.0), np.full(20, 200.0)]
    ).astype(float)
    out = smooth_ema(prices, window=5)
    alpha = 2.0 / (5 + 1)
    # At the FIRST step bar (index 20), EMA = 100 + alpha*(200-100)
    expected_at_step = 100.0 + alpha * (200.0 - 100.0)
    assert out[20] == pytest.approx(expected_at_step, rel=1e-9)
    # Several bars later, EMA should be much closer to 200 than to 100.
    assert out[35] > 195.0
    # Pre-step values stay at 100 (no leakage).
    assert out[19] == pytest.approx(100.0, rel=1e-12)


def test_smooth_kernel_regression_matches_nadaraya_watson_reference() -> None:
    """``smooth_kernel_regression`` matches a Nadaraya-Watson Gaussian-kernel
    weighted-mean reference computed in-test.
    """
    rng = np.random.default_rng(seed=7)
    prices = rng.normal(loc=50.0, scale=1.5, size=30).astype(float)
    bandwidth = 10.0
    n = len(prices)
    expected = np.empty(n, dtype=float)
    for i in range(n):
        diffs = (i - np.arange(n)) / bandwidth
        weights = np.exp(-0.5 * diffs * diffs)
        expected[i] = float(np.sum(weights * prices) / np.sum(weights))
    out = smooth_kernel_regression(prices, bandwidth=bandwidth)
    assert out.shape == prices.shape
    np.testing.assert_allclose(out, expected, rtol=1e-12, atol=1e-12)


def test_smooth_kernel_regression_constant_input_returns_constant_output() -> None:
    """Centered-on-mean property: input constant -> output equals input
    (no edge artifacts in the middle).
    """
    prices = np.full(40, 75.0, dtype=float)
    out = smooth_kernel_regression(prices, bandwidth=5.0)
    np.testing.assert_allclose(out, prices, rtol=1e-12, atol=1e-12)
