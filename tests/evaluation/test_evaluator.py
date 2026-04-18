"""Tests for the evaluator orchestrator."""
from __future__ import annotations

import pandas as pd

from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.evaluator import evaluate_batch, evaluate_one


def _long_ctx(closes, config, ticker="TEST", universe=("TEST",), spy_return=0.0):
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
            returns_12w_by_ticker={ticker: 0.50},
            universe_tickers=universe,
            universe_version="t", universe_hash="h", spy_return_12w=spy_return,
        ),
        market=MarketContext(),
        current_equity=10000.0,
    )


def test_evaluate_one_returns_candidate_with_all_criteria(sample_config):
    closes = [10.0 + i * 0.15 for i in range(260)]
    ctx = _long_ctx(closes, sample_config)
    candidate = evaluate_one(ctx)

    assert candidate.ticker == "TEST"
    assert candidate.bucket in ("aplus", "watch", "skip")

    layers = {c.layer for c in candidate.criteria}
    assert "trend_template" in layers
    assert "vcp" in layers
    assert "risk" in layers
    # 8 TT + 9 VCP (ma_stack_short contributes 2) + 1 risk = 18
    assert len(candidate.criteria) >= 18


def test_evaluate_batch_processes_multiple_tickers(sample_config):
    closes_up = [10.0 + i * 0.15 for i in range(260)]
    closes_flat = [10.0] * 260
    idx = pd.bdate_range(end="2026-04-17", periods=260)

    def _mk_df(cs):
        return pd.DataFrame(
            {"Open": cs, "High": [c * 1.01 for c in cs], "Low": [c * 0.99 for c in cs],
             "Close": cs, "Volume": [1_000_000] * 260},
            index=idx,
        )

    batch = BatchContext(
        returns_12w_by_ticker={"UP": 0.50, "FLAT": 0.0},
        universe_tickers=("UP", "FLAT"),
        universe_version="t", universe_hash="h", spy_return_12w=0.05,
    )
    ctx_up = CandidateContext(
        ticker="UP", ohlcv=_mk_df(closes_up), config=sample_config, batch=batch,
        market=MarketContext(), current_equity=10000.0,
    )
    ctx_flat = CandidateContext(
        ticker="FLAT", ohlcv=_mk_df(closes_flat), config=sample_config, batch=batch,
        market=MarketContext(), current_equity=10000.0,
    )
    candidates = evaluate_batch([ctx_up, ctx_flat])
    assert len(candidates) == 2
    by_ticker = {c.ticker: c for c in candidates}
    assert by_ticker["FLAT"].bucket == "skip"
