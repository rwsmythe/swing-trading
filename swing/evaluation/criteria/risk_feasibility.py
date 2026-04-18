"""At least 1 share fits within max_risk_pct * equity."""
from __future__ import annotations

from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria._base import Result

NAME = "risk_feasibility"
LAYER = "risk"


def evaluate(ctx: CandidateContext) -> Result:
    df = ctx.ohlcv
    if len(df) < 20:
        return Result.na_(f"need 20 bars, have {len(df)}", name=NAME, layer=LAYER)

    tail = df.iloc[-20:]
    pivot = float(tail["High"].max())
    stop = float(tail["Low"].min())
    risk_per_share = pivot - stop
    if risk_per_share <= 0:
        return Result.na_("non-positive risk/share", name=NAME, layer=LAYER)

    budget = ctx.current_equity * ctx.config.risk.max_risk_pct
    shares = int(budget // risk_per_share)
    risk_dollars = shares * risk_per_share

    rule = f">= 1 share fits in {ctx.config.risk.max_risk_pct:.1%} of equity (${budget:.2f})"
    value = f"{shares} sh, ${risk_dollars:.2f} risk"
    metrics = {
        "pivot": round(pivot, 4),
        "stop": round(stop, 4),
        "shares": shares,
        "risk_dollars": round(risk_dollars, 2),
    }
    if shares >= 1:
        return Result.pass_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
    return Result.fail_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
