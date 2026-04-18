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

    tt_passes = sum(1 for r in trend_template_results if r.result == "pass")
    vcp_fails = sum(1 for r in vcp_results if r.result in ("fail", "na"))

    tt_gate_ok = tt_passes >= config.trend_template.min_passes
    if not tt_gate_ok:
        return "skip"
    if vcp_fails == 0:
        return "aplus"
    if vcp_fails <= 2:
        return "watch"
    return "skip"
