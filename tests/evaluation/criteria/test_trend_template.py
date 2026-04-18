"""Tests for Minervini Trend Template (8 checks)."""
from __future__ import annotations

import pandas as pd

from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.criteria.trend_template import CHECK_NAMES, evaluate


def _long_ctx(closes, config, ticker="T", universe=("T",), returns_12w=None, spy_return=0.0):
    idx = pd.bdate_range(end="2026-04-17", periods=len(closes))
    df = pd.DataFrame(
        {"Open": closes, "High": [c * 1.01 for c in closes],
         "Low": [c * 0.99 for c in closes], "Close": closes,
         "Volume": [1_000_000] * len(closes)},
        index=idx,
    )
    return CandidateContext(
        ticker=ticker, ohlcv=df, config=config,
        batch=BatchContext(
            returns_12w_by_ticker=returns_12w or {ticker: 0.50},
            universe_tickers=universe,
            universe_version="test-v1",
            universe_hash="deadbeef",
            spy_return_12w=spy_return,
        ),
        market=MarketContext(),
        current_equity=1000.0,
    )


def test_all_8_checks_returned(sample_config):
    closes = [10.0 + i * 0.2 for i in range(250)]
    ctx = _long_ctx(closes, sample_config)
    results = evaluate(ctx)
    assert len(results) == 8
    assert {r.name for r in results} == set(CHECK_NAMES)
    for r in results:
        assert r.layer == "trend_template"


def test_strong_uptrend_passes_majority(sample_config):
    closes = [10.0 + i * 0.15 for i in range(260)]
    ctx = _long_ctx(closes, sample_config)
    results = evaluate(ctx)
    passes = sum(1 for r in results if r.result == "pass")
    assert passes >= 6


def test_flat_data_fails_most(sample_config):
    closes = [50.0] * 260
    ctx = _long_ctx(closes, sample_config)
    results = evaluate(ctx)
    fails = sum(1 for r in results if r.result == "fail")
    assert fails >= 3


def test_na_when_not_enough_bars(sample_config):
    closes = [10.0] * 100
    ctx = _long_ctx(closes, sample_config)
    results = evaluate(ctx)
    nas = sum(1 for r in results if r.result == "na")
    assert nas >= 4
