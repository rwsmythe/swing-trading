import pandas as pd
import numpy as np
from swing.evaluation.patterns.flag_classifier import classify_flag


def _flat_bars(n: int, start_close: float = 100.0) -> pd.DataFrame:
    """Build n bars with constant OHLCV — used as a no-detect baseline."""
    idx = pd.date_range("2026-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"Open": start_close, "High": start_close, "Low": start_close,
         "Close": start_close, "Volume": 1_000_000.0}, index=idx,
    )


def test_module_imports():
    from swing.evaluation.patterns.flag_classifier import (
        FlagClassificationResult,
        classify_flag,
    )

    assert callable(classify_flag)
    assert FlagClassificationResult is not None


def test_data_window_gate_below_threshold_returns_none():
    res = classify_flag(_flat_bars(35))
    assert res.detected is False
    assert res.pattern == "none"


def test_data_window_gate_at_threshold_enters_search():
    # 36 bars — minimum. Flat bars still fail later gates, but classify_flag
    # MUST run the search instead of short-circuiting.
    res = classify_flag(_flat_bars(36))
    assert res.detected is False
    # components_json must populate (best-attempted baseline) — proof the
    # search ran and was not short-circuited by data_window.
    assert "pole_M" in res.components
