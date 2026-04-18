"""Last 20 bars are orderly: no outlier range, low coefficient of variation."""
from __future__ import annotations

from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria._base import Result, daily_range_pct

NAME = "orderliness"
LAYER = "vcp"


def evaluate(ctx: CandidateContext) -> Result:
    df = ctx.ohlcv
    if len(df) < 20:
        return Result.na_(f"need 20 bars, have {len(df)}", name=NAME, layer=LAYER)

    ranges = daily_range_pct(df).iloc[-20:]
    median_range = float(ranges.median())
    max_range = float(ranges.max())
    mean_range = float(ranges.mean())

    if median_range <= 0:
        return Result.na_("median range non-positive", name=NAME, layer=LAYER)

    max_ratio = max_range / median_range
    cv = float(ranges.std() / mean_range) if mean_range > 0 else 0.0

    max_ratio_limit = ctx.config.vcp.orderliness_max_bar_ratio
    cv_limit = ctx.config.vcp.orderliness_max_range_cv

    rule = f"max bar <= {max_ratio_limit:.1f}x median AND range CV <= {cv_limit:.2f}"
    value = f"max {max_ratio:.2f}x, CV {cv:.2f}"
    metrics = {"max_bar_ratio": round(max_ratio, 3), "range_cv": round(cv, 3)}
    if max_ratio <= max_ratio_limit and cv <= cv_limit:
        return Result.pass_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
    return Result.fail_(value, rule, name=NAME, layer=LAYER, metrics=metrics)
