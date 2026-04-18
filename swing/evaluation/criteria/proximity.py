"""Price within N% of 20MA."""
from __future__ import annotations

from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria._base import Result, sma

NAME = "proximity_20ma"
LAYER = "vcp"


def evaluate(ctx: CandidateContext) -> Result:
    closes = ctx.ohlcv["Close"]
    if len(closes) < 20:
        return Result.na_(f"need 20 bars, have {len(closes)}", name=NAME, layer=LAYER)

    ma20 = float(sma(closes, 20).iloc[-1])
    last = float(closes.iloc[-1])
    pct = (last - ma20) / ma20 * 100
    threshold = ctx.config.vcp.proximity_max_pct
    value = f"{pct:+.2f}%"
    rule = f"|price - 20MA| <= {threshold}% of 20MA"
    metrics = {"proximity_pct": round(pct, 2)}
    if abs(pct) <= threshold:
        return Result.pass_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
    return Result.fail_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
