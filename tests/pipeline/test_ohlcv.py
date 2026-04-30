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


def test_fetch_daily_bars_strips_in_progress_bar_via_as_of_date(tmp_path, monkeypatch):
    """When the helper returns a frame whose last bar is the in-progress
    session, fetch_daily_bars strips it (CLAUDE.md yfinance gotcha)."""
    from datetime import date, timedelta
    import pandas as pd
    from swing.pipeline import ohlcv as mod

    as_of = date(2026, 4, 28)
    helper_dates = [as_of - timedelta(days=4), as_of - timedelta(days=3),
                    as_of - timedelta(days=2), as_of - timedelta(days=1), as_of]
    helper_frame = pd.DataFrame(
        {"Open": [1.0]*5, "High": [1.0]*5, "Low": [1.0]*5,
         "Close": [1.0]*5, "Volume": [1]*5},
        index=pd.to_datetime(helper_dates),
    )

    def fake_helper(ticker, *, end_date, cache_dir, archive_history_days):
        assert end_date == as_of
        assert cache_dir == tmp_path
        return helper_frame

    monkeypatch.setattr(mod, "read_or_fetch_archive", fake_helper)

    result = mod.fetch_daily_bars(
        "AAPL", n_bars=5, as_of_date=as_of, cache_dir=tmp_path, archive_history_days=1260,
    )
    assert result is not None
    assert result.index[-1].date() < as_of, (
        f"strip rule failed; last bar {result.index[-1].date()} >= session {as_of}"
    )


def test_fetch_daily_bars_retains_last_bar_when_complete(tmp_path, monkeypatch):
    """Last bar date strictly before session → no strip."""
    from datetime import date, timedelta
    import pandas as pd
    from swing.pipeline import ohlcv as mod

    as_of = date(2026, 4, 28)
    helper_dates = [as_of - timedelta(days=i) for i in range(1, 6)]
    helper_dates.reverse()
    helper_frame = pd.DataFrame(
        {"Open": [1.0]*5, "High": [1.0]*5, "Low": [1.0]*5,
         "Close": [1.0]*5, "Volume": [1]*5},
        index=pd.to_datetime(helper_dates),
    )

    monkeypatch.setattr(mod, "read_or_fetch_archive",
                        lambda *a, **kw: helper_frame)

    result = mod.fetch_daily_bars(
        "AAPL", n_bars=5, as_of_date=as_of, cache_dir=tmp_path, archive_history_days=1260,
    )
    assert result is not None
    assert len(result) == 5
    assert result.index[-1].date() == as_of - timedelta(days=1)


def test_fetch_daily_bars_propagates_exception(tmp_path, monkeypatch):
    """Helper raises → fetch_daily_bars propagates (caller's circuit breaker
    distinguishes source-level failure from per-ticker absence)."""
    from datetime import date
    from swing.pipeline import ohlcv as mod

    def boom(*args, **kwargs):
        raise RuntimeError("yfinance down")

    monkeypatch.setattr(mod, "read_or_fetch_archive", boom)

    with pytest.raises(RuntimeError, match="yfinance down"):
        mod.fetch_daily_bars(
            "AAPL", as_of_date=date(2026, 4, 28),
            cache_dir=tmp_path, archive_history_days=1260,
        )


def test_fetch_daily_bars_returns_none_on_empty_helper_result(tmp_path, monkeypatch):
    """Helper returns None → fetch_daily_bars returns None (per-ticker
    absence; not breaker-relevant)."""
    from datetime import date
    from swing.pipeline import ohlcv as mod

    monkeypatch.setattr(mod, "read_or_fetch_archive", lambda *a, **kw: None)

    result = mod.fetch_daily_bars(
        "AAPL", as_of_date=date(2026, 4, 28),
        cache_dir=tmp_path, archive_history_days=1260,
    )
    assert result is None


def test_fetch_daily_bars_passes_resolved_session_as_end_date(tmp_path, monkeypatch):
    """When `as_of_date=None`, fetch_daily_bars resolves to action_session_for_run
    (NOT date.today()) per CLAUDE.md exchange-session gotcha (HST lags ET 5h)."""
    from swing.pipeline import ohlcv as mod
    from swing.evaluation.dates import action_session_for_run
    from datetime import datetime
    import pandas as pd

    recorded: dict = {}

    def fake_helper(ticker, *, end_date, cache_dir, archive_history_days):
        recorded["end_date"] = end_date
        return pd.DataFrame()

    monkeypatch.setattr(mod, "read_or_fetch_archive", fake_helper)

    mod.fetch_daily_bars("AAPL", cache_dir=tmp_path, archive_history_days=1260)

    expected_session = action_session_for_run(datetime.now())
    assert recorded["end_date"] == expected_session, (
        f"as_of_date=None should resolve to action_session_for_run; "
        f"got {recorded['end_date']}, expected {expected_session}"
    )
