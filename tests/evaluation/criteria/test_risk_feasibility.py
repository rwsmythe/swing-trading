"""Tests for risk_feasibility criterion."""
from __future__ import annotations

import pandas as pd

from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.criteria.risk_feasibility import evaluate


def _ctx_priced(pivot, stop, config, equity=1000.0):
    highs = [pivot] * 30
    lows = [stop] * 30
    closes = [(pivot + stop) / 2] * 30
    idx = pd.bdate_range(end="2026-04-17", periods=30)
    df = pd.DataFrame(
        {"Open": closes, "High": highs, "Low": lows, "Close": closes,
         "Volume": [1_000_000] * 30},
        index=idx,
    )
    return CandidateContext(
        ticker="T", ohlcv=df, config=config,
        batch=BatchContext({}, (), "t", "h", 0.0),
        market=MarketContext(), current_equity=equity,
    )


def test_feasibility_pass_small_risk(sample_config):
    # equity 1000, max_risk_pct 0.005 → $5 budget
    # pivot 10, stop 9 → risk/share 1 → 5 shares affordable
    r = evaluate(_ctx_priced(pivot=10.0, stop=9.0, config=sample_config))
    assert r.result == "pass"


def test_feasibility_fail_when_risk_per_share_too_big(sample_config):
    # equity 1000 → $5 budget; pivot 100, stop 50 → risk/share 50 → 0 shares
    r = evaluate(_ctx_priced(pivot=100.0, stop=50.0, config=sample_config))
    assert r.result == "fail"
