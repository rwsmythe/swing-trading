"""ADR >= N% (Average Daily Range over 20 bars)."""
from __future__ import annotations

from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria._base import Result, adr_pct

NAME = "adr"
LAYER = "vcp"


def evaluate(ctx: CandidateContext) -> Result:
    if len(ctx.ohlcv) < 20:
        return Result.na_(f"need 20 bars, have {len(ctx.ohlcv)}", name=NAME, layer=LAYER)

    adr = adr_pct(ctx.ohlcv, lookback=20)
    threshold = ctx.config.vcp.adr_min_pct
    rule = f">= {threshold}% required for sufficient volatility"
    value = f"{adr:.2f}%"
    metrics = {"adr_pct": round(adr, 4)}
    if adr >= threshold:
        return Result.pass_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
    return Result.fail_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
