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


def test_fetch_daily_bars_strips_in_progress_bar_via_as_of_date(monkeypatch):
    """Spec §3.1: the last bar whose date == current exchange session is
    treated as in-progress and dropped before .tail(n_bars)."""
    from datetime import date
    import pandas as pd
    from swing.pipeline import ohlcv as mod

    idx = pd.date_range("2026-04-15", periods=10, freq="B")  # Wed Apr 15 → Tue Apr 28
    closes = [100.0 + i for i in range(10)]
    df = pd.DataFrame({"Close": closes}, index=idx)

    class FakeTicker:
        def history(self, **kwargs):
            return df

    monkeypatch.setattr(mod, "yf", type("Y", (), {"Ticker": lambda self=None, t=None: FakeTicker()}))
    # Treat the last bar's date as the in-progress session.
    as_of = idx[-1].date()
    result = mod.fetch_daily_bars("AAPL", n_bars=5, as_of_date=as_of)
    assert result is not None
    # Last bar stripped → max 9 remaining, tail(5) → 5 rows.
    assert len(result) == 5
    # Last retained bar is idx[-2], not idx[-1].
    assert result.index[-1].date() == idx[-2].date()


def test_fetch_daily_bars_retains_last_bar_when_complete(monkeypatch):
    """Reverse case: if the last bar's date is strictly BEFORE the session,
    it is retained (the session has rolled over; the bar is complete)."""
    from datetime import date, timedelta
    import pandas as pd
    from swing.pipeline import ohlcv as mod

    idx = pd.date_range("2026-04-15", periods=10, freq="B")
    closes = [100.0 + i for i in range(10)]
    df = pd.DataFrame({"Close": closes}, index=idx)

    class FakeTicker:
        def history(self, **kwargs):
            return df

    monkeypatch.setattr(mod, "yf", type("Y", (), {"Ticker": lambda self=None, t=None: FakeTicker()}))
    # Session is AFTER the last bar — nothing to strip.
    as_of = idx[-1].date() + timedelta(days=5)
    result = mod.fetch_daily_bars("AAPL", n_bars=5, as_of_date=as_of)
    assert result is not None
    assert len(result) == 5
    # Last bar retained.
    assert result.index[-1].date() == idx[-1].date()


def test_fetch_daily_bars_propagates_exception(monkeypatch):
    """yfinance raising → exception propagates to caller. The cache layer
    catches this to distinguish source failure from per-ticker data absence."""
    import pytest
    from swing.pipeline import ohlcv as mod

    class FakeTicker:
        def history(self, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr(mod, "yf", type("Y", (), {"Ticker": lambda self=None, t=None: FakeTicker()}))
    with pytest.raises(RuntimeError, match="network down"):
        mod.fetch_daily_bars("AAPL")


def test_fetch_daily_bars_returns_none_on_empty_result(monkeypatch):
    """yfinance returning empty DataFrame → None."""
    import pandas as pd
    from swing.pipeline import ohlcv as mod

    class FakeTicker:
        def history(self, **kwargs):
            return pd.DataFrame()

    monkeypatch.setattr(mod, "yf", type("Y", (), {"Ticker": lambda self=None, t=None: FakeTicker()}))
    assert mod.fetch_daily_bars("AAPL") is None
