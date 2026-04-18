"""Prior trend: consolidation area >= N% above the pre-trend low."""
from __future__ import annotations

from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria._base import Result

NAME = "prior_trend"
LAYER = "vcp"

CONSOLIDATION_LOOKBACK = 20
PRIOR_TREND_LOOKBACK = 230


def evaluate(ctx: CandidateContext) -> Result:
    df = ctx.ohlcv
    min_bars = CONSOLIDATION_LOOKBACK + PRIOR_TREND_LOOKBACK
    if len(df) < min_bars:
        return Result.na_(f"need {min_bars} bars, have {len(df)}", name=NAME, layer=LAYER)

    closes = df["Close"]
    consolidation = closes.iloc[-CONSOLIDATION_LOOKBACK:]
    prior = closes.iloc[-(CONSOLIDATION_LOOKBACK + PRIOR_TREND_LOOKBACK):-CONSOLIDATION_LOOKBACK]

    consolidation_low = float(consolidation.min())
    prior_low = float(prior.min())
    if prior_low <= 0:
        return Result.na_("prior_low non-positive", name=NAME, layer=LAYER)

    gain_pct = (consolidation_low - prior_low) / prior_low * 100
    threshold = ctx.config.vcp.prior_trend_min_pct
    rule = f">= {threshold}% required"
    value = f"{gain_pct:.1f}%"
    metrics = {"prior_trend_pct": round(gain_pct, 2)}
    if gain_pct >= threshold:
        return Result.pass_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
    return Result.fail_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
