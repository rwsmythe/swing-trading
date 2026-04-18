"""Tests for vcp (volume contraction) criterion."""
from __future__ import annotations

import pandas as pd

from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.criteria.vcp import evaluate


def _ctx_volumes(vols, config):
    n = len(vols)
    idx = pd.bdate_range(end="2026-04-17", periods=n)
    df = pd.DataFrame(
        {"Open": [100.0] * n, "High": [101.0] * n, "Low": [99.0] * n,
         "Close": [100.0] * n, "Volume": vols},
        index=idx,
    )
    return CandidateContext(
        ticker="T", ohlcv=df, config=config,
        batch=BatchContext({}, (), "t", "h", 0.0),
        market=MarketContext(), current_equity=1000.0,
    )


def test_vcp_pass_volume_contracting(sample_config):
    # 100 prior bars with 2M avg, 20 consolidation bars with 500k avg
    vols = [2_000_000] * 100 + [500_000] * 20
    ctx = _ctx_volumes(vols, sample_config)
    r = evaluate(ctx)
    assert r.result == "pass"


def test_vcp_fail_volume_expanding(sample_config):
    vols = [500_000] * 100 + [2_000_000] * 20
    ctx = _ctx_volumes(vols, sample_config)
    r = evaluate(ctx)
    assert r.result == "fail"
