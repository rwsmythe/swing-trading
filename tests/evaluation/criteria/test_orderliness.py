"""Tests for orderliness criterion."""
from __future__ import annotations

import pandas as pd

from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.criteria.orderliness import evaluate


def _ctx(highs, lows, config):
    n = len(highs)
    idx = pd.bdate_range(end="2026-04-17", periods=n)
    df = pd.DataFrame(
        {"Open": [100.0] * n, "High": highs, "Low": lows,
         "Close": [100.0] * n, "Volume": [1_000_000] * n},
        index=idx,
    )
    return CandidateContext(
        ticker="T", ohlcv=df, config=config,
        batch=BatchContext({}, (), "t", "h", 0.0),
        market=MarketContext(), current_equity=1000.0,
    )


def test_orderliness_pass_consistent_ranges(sample_config):
    highs = [101.0] * 25
    lows = [99.0] * 25
    r = evaluate(_ctx(highs, lows, sample_config))
    assert r.result == "pass"


def test_orderliness_fail_one_big_range(sample_config):
    highs = [101.0] * 24 + [130.0]
    lows = [99.0] * 24 + [70.0]
    r = evaluate(_ctx(highs, lows, sample_config))
    assert r.result == "fail"
