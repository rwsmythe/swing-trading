"""Phase 18 Arc 18-B — GAP closure: the Schwab market-data ladder write path.

`_persist_window_to_archive` is the SECOND OHLC-bar ingest writer (the first
being the legacy `_yf_download_window` / `_warm_one_window` paths). It persists
a freshly-fetched window into the Shape-A archive `{TICKER}.{provider}.parquet`
that `resolve_ohlcv_window` reads. Before 18-B it applied NO trailing-ragged
finiteness barrier, unlike its sibling legacy writer. These tests lock the
barrier: a trailing non-finite OHLC bar (the 06-10 yfinance Close=NaN artifact)
is trimmed BEFORE write, via the ONE shared `is_finite_ohlc` predicate (reused
through `_trim_trailing_ragged`; C1). Volume-only-NaN is EXEMPT; a fully-valid
window persists unchanged (no over-rejection).
"""
from __future__ import annotations

import math

import pandas as pd

from swing.data.ohlcv_archive import resolve_ohlcv_window
from swing.integrations.schwab.marketdata_ladder import _persist_window_to_archive


def test_ladder_persist_trims_trailing_nan_before_write_phase18b(tmp_path):
    """GAP closure: a fetched window with a TRAILING Close=NaN (O/H/L/V finite --
    the 06-10 artifact) must be trimmed BEFORE write_window, so the Shape-A
    archive never persists a non-finite bar.

    PRE-FIX arithmetic: _persist_window_to_archive builds df with the NaN row and
    calls write_window -> the parquet contains 2 rows incl. close=NaN; a later
    resolve_ohlcv_window read returns the NaN bar (assert all(isfinite) fails).
    POST-FIX: the trailing NaN row is trimmed -> 1 clean row persisted;
    resolve_ohlcv_window returns only the finite bar."""
    df = pd.DataFrame({
        "asof_date": ["2026-06-09", "2026-06-10"],
        "open": [10.0, 10.5], "high": [11.0, 11.5], "low": [9.0, 10.0],
        "close": [10.5, float("nan")], "volume": [1000.0, 1200.0],
    })
    _persist_window_to_archive("AAA", df, "yfinance", tmp_path)
    out, _prov = resolve_ohlcv_window(
        "AAA", start="2026-06-01", end="2026-06-30", cache_dir=tmp_path)
    closes = [float(c) for c in out["close"]]
    assert all(math.isfinite(c) for c in closes)        # no NaN persisted
    assert "2026-06-10" not in list(out["asof_date"])   # the NaN row was trimmed
    assert "2026-06-09" in list(out["asof_date"])        # the finite row survived


def test_ladder_persist_keeps_fully_valid_window_phase18b(tmp_path):
    """No over-rejection: a fully-finite window persists unchanged (both rows)."""
    df = pd.DataFrame({
        "asof_date": ["2026-06-09", "2026-06-10"],
        "open": [10.0, 10.5], "high": [11.0, 11.5], "low": [9.0, 10.0],
        "close": [10.5, 10.7], "volume": [1000.0, 1200.0],
    })
    _persist_window_to_archive("BBB", df, "yfinance", tmp_path)
    out, _ = resolve_ohlcv_window(
        "BBB", start="2026-06-01", end="2026-06-30", cache_dir=tmp_path)
    assert sorted(out["asof_date"]) == ["2026-06-09", "2026-06-10"]


def test_ladder_persist_volume_only_nan_not_trimmed_phase18b(tmp_path):
    """Volume-only-NaN trailing row is EXEMPT (finite OHLC) -> persisted."""
    df = pd.DataFrame({
        "asof_date": ["2026-06-09", "2026-06-10"],
        "open": [10.0, 10.5], "high": [11.0, 11.5], "low": [9.0, 10.0],
        "close": [10.5, 10.7], "volume": [1000.0, float("nan")],
    })
    _persist_window_to_archive("CCC", df, "yfinance", tmp_path)
    out, _ = resolve_ohlcv_window(
        "CCC", start="2026-06-01", end="2026-06-30", cache_dir=tmp_path)
    assert sorted(out["asof_date"]) == ["2026-06-09", "2026-06-10"]
