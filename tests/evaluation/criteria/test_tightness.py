"""Tests for tightness criterion."""
from __future__ import annotations

import pandas as pd

from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.criteria.tightness import evaluate


def _ctx_with_custom_rows(row_specs, config):
    """row_specs: list of (open, high, low, close) tuples."""
    idx = pd.bdate_range(end="2026-04-17", periods=len(row_specs))
    df = pd.DataFrame(
        {
            "Open": [r[0] for r in row_specs],
            "High": [r[1] for r in row_specs],
            "Low": [r[2] for r in row_specs],
            "Close": [r[3] for r in row_specs],
            "Volume": [1_000_000] * len(row_specs),
        },
        index=idx,
    )
    return CandidateContext(
        ticker="T", ohlcv=df, config=config,
        batch=BatchContext({}, (), "t", "h", 0.0),
        market=MarketContext(), current_equity=1000.0,
    )


def test_tightness_pass_two_consecutive_tight_days(sample_config):
    # 20 bars with 10% range (ADR=10%), then 2 bars with 3% range (<2/3*10%=6.67%)
    row_specs = [(100, 105, 95, 100)] * 20 + [(100, 101.5, 98.5, 100), (100, 101.5, 98.5, 100)]
    ctx = _ctx_with_custom_rows(row_specs, sample_config)
    r = evaluate(ctx)
    assert r.result == "pass"


def test_tightness_fail_zero_streak(sample_config):
    # Big-range days throughout
    row_specs = [(100, 110, 90, 100)] * 25
    ctx = _ctx_with_custom_rows(row_specs, sample_config)
    r = evaluate(ctx)
    assert r.result == "fail"
