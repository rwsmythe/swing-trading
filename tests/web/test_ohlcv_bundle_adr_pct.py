"""3e.8 Bundle 2 — OhlcvBundle gains adr_pct field; computed from same bars
as sma10/20/50 (no new yfinance fetches)."""
from __future__ import annotations

import time

import pandas as pd

from swing.pipeline.ohlcv import compute_adr_pct
from swing.web.ohlcv_cache import OhlcvBundle


def test_ohlcv_bundle_has_adr_pct_field():
    b = OhlcvBundle(
        sma10=1.0, sma20=2.0, sma50=3.0,
        previous_close=4.0, fetched_at=time.monotonic(),
        adr_pct=5.0,
    )
    assert b.adr_pct == 5.0


def test_ohlcv_bundle_adr_pct_defaults_to_none_for_backward_compat():
    b = OhlcvBundle(
        sma10=1.0, sma20=2.0, sma50=3.0,
        previous_close=4.0, fetched_at=time.monotonic(),
    )
    assert b.adr_pct is None


def test_ohlcv_bundle_empty_has_none_adr_pct():
    b = OhlcvBundle.empty(fetched_at=time.monotonic())
    assert b.adr_pct is None


def test_compute_adr_pct_returns_none_when_bars_empty():
    assert compute_adr_pct(pd.DataFrame(), lookback=20) is None


def test_compute_adr_pct_returns_none_when_bars_none():
    assert compute_adr_pct(None, lookback=20) is None


def test_compute_adr_pct_returns_none_when_insufficient_bars():
    # 19 bars but lookback=20 → None.
    df = pd.DataFrame({
        "High": [101.0] * 19,
        "Low": [99.0] * 19,
        "Close": [100.0] * 19,
    })
    assert compute_adr_pct(df, lookback=20) is None


def test_compute_adr_pct_computes_correctly_when_sufficient_bars():
    # Each bar: range = (101 - 99) / 100 * 100 = 2.0% → mean 2.0.
    df = pd.DataFrame({
        "High": [101.0] * 20,
        "Low": [99.0] * 20,
        "Close": [100.0] * 20,
    })
    result = compute_adr_pct(df, lookback=20)
    assert result is not None
    assert abs(result - 2.0) < 1e-9


def test_compute_adr_pct_only_uses_trailing_lookback_bars():
    # 30 bars total but adr_pct should only consider trailing 20.
    # First 10 have huge range; last 20 have small range.
    highs = [200.0] * 10 + [101.0] * 20
    lows = [50.0] * 10 + [99.0] * 20
    closes = [100.0] * 30
    df = pd.DataFrame({"High": highs, "Low": lows, "Close": closes})
    result = compute_adr_pct(df, lookback=20)
    assert result is not None
    # Trailing 20 bars: (101-99)/100*100 = 2.0%.
    assert abs(result - 2.0) < 1e-9
