import numpy as np
import pandas as pd
import pytest
from swing.pipeline.temporal_metadata import (
    compute_atr_pct, compute_return_pct, compute_52w_high_proximity_pct,
)


def _bars(n: int, last_date="2026-05-28") -> pd.DataFrame:
    idx = pd.bdate_range(end=last_date, periods=n)
    close = np.linspace(10.0, 20.0, n)
    return pd.DataFrame(
        {"Open": close * 0.99, "High": close * 1.02,
         "Low": close * 0.98, "Close": close, "Volume": 1_000_000},
        index=idx,
    )


def test_atr_pct_positive_for_normal_bars():
    out = compute_atr_pct(_bars(60), asof="2026-05-28")
    assert out is not None and out > 0


def test_return_pct_90_sessions():
    bars = _bars(120)
    out = compute_return_pct(bars, asof="2026-05-28", lookback_sessions=90)
    assert out is not None
    # close rises monotonically -> positive 90-session return
    assert out > 0


def test_return_pct_short_history_returns_none():
    out = compute_return_pct(_bars(30), asof="2026-05-28", lookback_sessions=90)
    assert out is None  # < 90 bars -> None, NOT an exception


def test_52w_proximity_near_high():
    bars = _bars(300)  # > 252
    out = compute_52w_high_proximity_pct(bars, asof="2026-05-28")
    assert out is not None and out >= 0  # close near the rising high


def test_helpers_strip_in_progress_partial_bar():
    # A bar dated AFTER asof (in-progress) must be ignored.
    bars = _bars(60, last_date="2026-05-29")  # last bar 2026-05-29 > asof
    out = compute_atr_pct(bars, asof="2026-05-28")
    assert out is not None  # did not crash; used <= asof slice


def test_helpers_return_none_on_empty_or_columnless_frame():
    # The Major-#1 empty-frame degrade path: an empty DataFrame (passed when
    # bars are unexpectedly absent for an emitted verdict) returns None for
    # every computed field rather than raising KeyError.
    empty = pd.DataFrame()
    assert compute_atr_pct(empty, asof="2026-05-28") is None
    assert compute_return_pct(empty, asof="2026-05-28", lookback_sessions=90) is None
    assert compute_52w_high_proximity_pct(empty, asof="2026-05-28") is None


def test_build_ohlc_today_json_validates_shape_and_provider():
    # Codex chain #2 Major #6: the observation JSON construction barrier.
    import json as _j
    from swing.pipeline.temporal_metadata import build_ohlc_today_json
    good = {"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5,
            "volume": 1e6, "provider": "yfinance"}
    out = _j.loads(build_ohlc_today_json(good))
    assert out["provider"] == "yfinance"
    assert set(out) == {"open", "high", "low", "close", "volume", "provider"}
    with pytest.raises(ValueError, match="provider"):
        build_ohlc_today_json({**good, "provider": "bogus"})
    with pytest.raises(ValueError, match="missing keys"):
        build_ohlc_today_json({"open": 1.0})  # incomplete
