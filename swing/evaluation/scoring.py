"""Bucket classification: aplus / watch / skip / excluded / error.

NA results count as fails for bucket determination — insufficient data is a fail.
"""
from __future__ import annotations

from collections.abc import Sequence

from swing.config import Config
from swing.evaluation.criteria._base import Result


def bucket_for(
    trend_template_results: Sequence[Result],
    vcp_results: Sequence[Result],
    risk_results: Sequence[Result],
    config: Config,
) -> str:
    # Risk is a hard filter
    if any(r.result != "pass" for r in risk_results):
        return "skip"

    # Trend Template gate: (a) enough passes AND (b) every failing TT is in allowed_miss_names.
    # This matches spec §4.1 — the allowed fail is configurable, TT8 is the default.
    tt_passes = sum(1 for r in trend_template_results if r.result == "pass")
    tt_fails = [r.name for r in trend_template_results if r.result != "pass"]
    allowed = set(config.trend_template.allowed_miss_names)

    if tt_passes < config.trend_template.min_passes:
        return "skip"
    if not all(n in allowed for n in tt_fails):
        return "skip"

    vcp_fails = sum(1 for r in vcp_results if r.result in ("fail", "na"))
    if vcp_fails == 0:
        return "aplus"
    if vcp_fails <= 2:
        return "watch"
    return "skip"
