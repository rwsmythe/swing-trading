"""Tests for swing.evaluation.context + criteria._base."""
from __future__ import annotations

import pandas as pd
import pytest

from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.criteria._base import Result, adr_pct, sma


def test_sma_rolling_mean():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    result = sma(s, 3)
    assert result.iloc[-1] == pytest.approx(4.0)
    assert pd.isna(result.iloc[0])


def test_adr_pct_calculation(ohlcv_factory):
    # ohlcv_factory creates High=close*1.01, Low=close*0.99 → range = 2% of close
    df = ohlcv_factory([100.0, 100.0, 100.0, 100.0, 100.0])
    result = adr_pct(df, lookback=5)
    assert result == pytest.approx(2.0)


def test_result_pass_fail_constructors():
    r = Result.pass_("1.5x", "must be >= 1.0x", name="test", layer="vcp")
    assert r.result == "pass"
    assert r.value == "1.5x"

    r = Result.fail_("0.5x", "must be >= 1.0x", name="test", layer="vcp")
    assert r.result == "fail"


def test_result_metrics_get_metric():
    r = Result.pass_(
        "ok", "rule", name="test", layer="vcp",
        metrics={"streak_days": 3, "adr_pct": 4.66},
    )
    assert r.get_metric("streak_days") == 3
    assert r.get_metric("adr_pct") == pytest.approx(4.66)
    assert r.get_metric("nonexistent") is None


def test_candidate_context_constructs():
    """Smoke test — ensures imports and construction work."""
    assert CandidateContext is not None
    assert BatchContext is not None
    assert MarketContext is not None
