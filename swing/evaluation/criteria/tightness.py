"""Last N consecutive days have daily range <= factor * ADR."""
from __future__ import annotations

from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria._base import Result, adr_pct, daily_range_pct

NAME = "tightness"
LAYER = "vcp"


def evaluate(ctx: CandidateContext) -> Result:
    df = ctx.ohlcv
    if len(df) < 22:
        return Result.na_(f"need 22 bars, have {len(df)}", name=NAME, layer=LAYER)

    adr = adr_pct(df, lookback=20)
    ranges = daily_range_pct(df)
    factor = ctx.config.vcp.tightness_range_factor
    threshold = factor * adr
    required_days = ctx.config.vcp.tightness_days_required

    streak = 0
    for r in reversed(ranges.tolist()):
        if r <= threshold:
            streak += 1
        else:
            break

    rule = f">= {required_days} consec. days with range <= {factor:.2f} x ADR ({threshold:.2f}%)"
    value = f"{streak} day streak"
    metrics = {"tight_streak_days": streak}
    if streak >= required_days:
        return Result.pass_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
    return Result.fail_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
