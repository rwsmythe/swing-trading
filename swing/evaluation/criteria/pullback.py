"""Pullback from recent high < N% threshold."""
from __future__ import annotations

from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria._base import Result

NAME = "pullback"
LAYER = "vcp"
PEAK_LOOKBACK = 100


def evaluate(ctx: CandidateContext) -> Result:
    closes = ctx.ohlcv["Close"]
    if len(closes) < PEAK_LOOKBACK:
        return Result.na_(f"need {PEAK_LOOKBACK} bars, have {len(closes)}", name=NAME, layer=LAYER)

    recent = closes.iloc[-PEAK_LOOKBACK:]
    peak = float(recent.max())
    last = float(closes.iloc[-1])
    if peak <= 0:
        return Result.na_("peak non-positive", name=NAME, layer=LAYER)

    pullback_pct = (peak - last) / peak * 100
    threshold = ctx.config.vcp.pullback_max_pct
    rule = f"< {threshold}% from consolidation high"
    value = f"{pullback_pct:.1f}%"
    metrics = {"pullback_pct": round(pullback_pct, 2)}
    if pullback_pct < threshold:
        return Result.pass_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
    return Result.fail_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
