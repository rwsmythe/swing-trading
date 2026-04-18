"""Evaluate one ticker (runs all criteria) and a batch."""
from __future__ import annotations

from collections.abc import Sequence

from swing.data.models import Candidate, CriterionResult
from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria import (
    adr,
    ma_stack_short,
    orderliness,
    prior_trend,
    proximity,
    pullback,
    risk_feasibility,
    tightness,
    trend_template,
    vcp,
)
from swing.evaluation.criteria._base import Result, adr_pct
from swing.evaluation.scoring import bucket_for


def _to_model(r: Result) -> CriterionResult:
    return CriterionResult(
        criterion_name=r.name,
        layer=r.layer,
        result=r.result,
        value=r.value or None,
        rule=r.rule or None,
    )


def evaluate_one(ctx: CandidateContext) -> Candidate:
    """Run all criteria on one ticker, determine bucket, return a Candidate."""
    tt_results = list(trend_template.evaluate(ctx))

    stack_r, rising_r = ma_stack_short.evaluate(ctx)
    vcp_results = [
        prior_trend.evaluate(ctx),
        stack_r,
        rising_r,
        proximity.evaluate(ctx),
        adr.evaluate(ctx),
        pullback.evaluate(ctx),
        tightness.evaluate(ctx),
        vcp.evaluate(ctx),
        orderliness.evaluate(ctx),
    ]
    risk_results = [risk_feasibility.evaluate(ctx)]

    bucket = bucket_for(tt_results, vcp_results, risk_results, ctx.config)

    closes = ctx.ohlcv["Close"]
    last_close = float(closes.iloc[-1])

    tail = ctx.ohlcv.iloc[-20:] if len(ctx.ohlcv) >= 20 else ctx.ohlcv
    pivot = float(tail["High"].max())
    initial_stop = float(tail["Low"].min())
    adr_value = adr_pct(ctx.ohlcv, lookback=20) if len(ctx.ohlcv) >= 20 else None

    # Structured metrics read from Results (never parse display strings)
    def _find(results, name):
        return next((r for r in results if r.name == name), None)

    tight_r = _find(vcp_results, "tightness")
    tight_streak = (
        int(tight_r.get_metric("tight_streak_days"))
        if tight_r and tight_r.get_metric("tight_streak_days") is not None
        else None
    )
    pullback_r = _find(vcp_results, "pullback")
    pullback_value = pullback_r.get_metric("pullback_pct") if pullback_r else None
    prior_r = _find(vcp_results, "prior_trend")
    prior_trend_value = prior_r.get_metric("prior_trend_pct") if prior_r else None

    # RS: extract via batch, same logic as TT8
    rs_rank = None
    rs_return_vs_spy = None
    rs_method = "unavailable"
    ticker_ret = ctx.batch.returns_12w_by_ticker.get(ctx.ticker)
    if ticker_ret is not None:
        rs_return_vs_spy = ticker_ret - ctx.batch.spy_return_12w
        if ctx.ticker in ctx.batch.universe_tickers:
            rs_method = "universe"
            universe_returns = sorted(
                r for t, r in ctx.batch.returns_12w_by_ticker.items()
                if t in ctx.batch.universe_tickers
            )
            if universe_returns:
                leq = sum(1 for r in universe_returns if r <= ticker_ret)
                rs_rank = max(
                    0,
                    min(99, int((leq - 1) / max(1, len(universe_returns) - 1) * 99)),
                )
        else:
            rs_method = "fallback_spy"

    criteria_models = tuple(_to_model(r) for r in tt_results + vcp_results + risk_results)

    return Candidate(
        ticker=ctx.ticker,
        bucket=bucket,
        close=last_close,
        pivot=pivot,
        initial_stop=initial_stop,
        adr_pct=adr_value,
        tight_streak=tight_streak,
        pullback_pct=pullback_value,
        prior_trend_pct=prior_trend_value,
        rs_rank=rs_rank,
        rs_return_12w_vs_spy=rs_return_vs_spy,
        rs_method=rs_method,
        pattern_tag=None,
        notes=None,
        criteria=criteria_models,
    )


def evaluate_batch(contexts: Sequence[CandidateContext]) -> list[Candidate]:
    """Evaluate a batch of tickers."""
    return [evaluate_one(ctx) for ctx in contexts]
