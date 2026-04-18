"""Tests for adr criterion."""
from __future__ import annotations

import pandas as pd

from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.criteria.adr import evaluate


def _ctx(df, config):
    return CandidateContext(
        ticker="T", ohlcv=df, config=config,
        batch=BatchContext({}, (), "t", "h", 0.0),
        market=MarketContext(), current_equity=1000.0,
    )


def test_adr_pass(sample_config):
    # Range = 10% of close
    closes = [100.0] * 25
    idx = pd.bdate_range(end="2026-04-17", periods=25)
    df = pd.DataFrame(
        {"Open": closes, "High": [105.0] * 25, "Low": [95.0] * 25,
         "Close": closes, "Volume": [1_000_000] * 25},
        index=idx,
    )
    r = evaluate(_ctx(df, sample_config))
    assert r.result == "pass"


def test_adr_fail(sample_config):
    # Range = 2% of close (below 4% threshold)
    closes = [100.0] * 25
    idx = pd.bdate_range(end="2026-04-17", periods=25)
    df = pd.DataFrame(
        {"Open": closes, "High": [101.0] * 25, "Low": [99.0] * 25,
         "Close": closes, "Volume": [1_000_000] * 25},
        index=idx,
    )
    r = evaluate(_ctx(df, sample_config))
    assert r.result == "fail"
