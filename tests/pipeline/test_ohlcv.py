"""Pure SMA helpers — canned DataFrame tests. No yfinance round-trip."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _bars(closes: list[float]) -> pd.DataFrame:
    """Build a synthetic DataFrame matching yfinance's shape (Close column)."""
    idx = pd.date_range("2026-01-02", periods=len(closes), freq="B")
    return pd.DataFrame({"Close": closes}, index=idx)


def test_compute_smas_returns_float_when_enough_bars():
    from swing.pipeline.ohlcv import compute_smas
    bars = _bars([100.0] * 50)
    out = compute_smas(bars, [10, 20, 50])
    assert out[10] == pytest.approx(100.0)
    assert out[20] == pytest.approx(100.0)
    assert out[50] == pytest.approx(100.0)


def test_compute_smas_returns_none_for_period_exceeding_bars():
    from swing.pipeline.ohlcv import compute_smas
    bars = _bars([100.0] * 10)
    out = compute_smas(bars, [10, 20, 50])
    assert out[10] is not None
    assert out[20] is None
    assert out[50] is None


def test_compute_smas_returns_all_none_on_empty_dataframe():
    from swing.pipeline.ohlcv import compute_smas
    bars = pd.DataFrame({"Close": []})
    out = compute_smas(bars, [10, 20, 50])
    assert out == {10: None, 20: None, 50: None}


def test_compute_smas_handles_all_nan_close_column():
    from swing.pipeline.ohlcv import compute_smas
    bars = _bars([np.nan] * 50)
    out = compute_smas(bars, [10, 20, 50])
    assert out == {10: None, 20: None, 50: None}


def test_compute_smas_returns_none_when_close_column_missing():
    from swing.pipeline.ohlcv import compute_smas
    bars = pd.DataFrame({"Open": [100.0] * 50})
    out = compute_smas(bars, [10])
    assert out == {10: None}


def test_previous_close_returns_last_close():
    from swing.pipeline.ohlcv import previous_close
    bars = _bars([100.0, 101.0, 102.5])
    assert previous_close(bars) == pytest.approx(102.5)


def test_previous_close_returns_none_on_empty_or_all_nan():
    from swing.pipeline.ohlcv import previous_close
    assert previous_close(pd.DataFrame({"Close": []})) is None
    assert previous_close(_bars([np.nan, np.nan])) is None


def test_previous_close_returns_none_when_close_column_missing():
    from swing.pipeline.ohlcv import previous_close
    bars = pd.DataFrame({"Open": [100.0, 101.0]})
    assert previous_close(bars) is None
