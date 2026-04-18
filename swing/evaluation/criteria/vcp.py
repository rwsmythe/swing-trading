"""Volume contraction: 20-bar consolidation avg volume < 100-bar prior trend avg volume."""
from __future__ import annotations

from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria._base import Result

NAME = "vcp_volume_contraction"
LAYER = "vcp"


def evaluate(ctx: CandidateContext) -> Result:
    df = ctx.ohlcv
    if len(df) < 120:
        return Result.na_(f"need 120 bars, have {len(df)}", name=NAME, layer=LAYER)

    prior = df["Volume"].iloc[-120:-20]
    consolidation = df["Volume"].iloc[-20:]
    prior_avg = float(prior.mean())
    cons_avg = float(consolidation.mean())

    rule = "consolidation avg volume < prior trend avg volume"
    value = f"cons:{cons_avg:,.0f} vs trend:{prior_avg:,.0f}"
    metrics = {"consolidation_avg_volume": cons_avg, "prior_avg_volume": prior_avg}
    if cons_avg < prior_avg:
        return Result.pass_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
    return Result.fail_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
