"""Tests for prior_trend criterion."""
from __future__ import annotations

import pandas as pd

from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.criteria.prior_trend import evaluate


def _ctx_from_closes(closes, config):
    """Build a minimal CandidateContext from a list of closes."""
    idx = pd.bdate_range(end="2026-04-17", periods=len(closes))
    df = pd.DataFrame(
        {
            "Open": closes,
            "High": [c * 1.01 for c in closes],
            "Low": [c * 0.99 for c in closes],
            "Close": closes,
            "Volume": [1_000_000] * len(closes),
        },
        index=idx,
    )
    return CandidateContext(
        ticker="TEST",
        ohlcv=df,
        config=config,
        batch=BatchContext(
            returns_12w_by_ticker={},
            universe_tickers=(),
            universe_version="test",
            universe_hash="x",
            spy_return_12w=0.0,
        ),
        market=MarketContext(),
        current_equity=1000.0,
    )


def test_prior_trend_passes_when_gain_exceeds_threshold(sample_config):
    # 250 bars: 20 flat @10, 210 rising to 40, 20 flat @40 (300% gain)
    closes = [10.0] * 20 + [10.0 + i * 0.14 for i in range(210)] + [40.0] * 20
    ctx = _ctx_from_closes(closes, sample_config)
    result = evaluate(ctx)
    assert result.result == "pass"
    assert "%" in result.value


def test_prior_trend_fails_when_no_trend(sample_config):
    closes = [10.0] * 250
    ctx = _ctx_from_closes(closes, sample_config)
    result = evaluate(ctx)
    assert result.result == "fail"


def test_prior_trend_na_when_not_enough_data(sample_config):
    closes = [10.0] * 50  # needs 250
    ctx = _ctx_from_closes(closes, sample_config)
    result = evaluate(ctx)
    assert result.result == "na"
