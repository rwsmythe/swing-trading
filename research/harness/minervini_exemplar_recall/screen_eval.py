# research/harness/minervini_exemplar_recall/screen_eval.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from swing.config import Config
from swing.data.models import CriterionResult
from swing.evaluation.context import CandidateContext, MarketContext
from swing.evaluation.evaluator import evaluate_one

from . import rs_proxy
from .constants import EQUITY_FLOOR_SURROGATE, screenable_floor
from .ohlcv_reader import slice_to

H1_OUTCOMES = (
    "no_data",
    "skip_insufficient_history",
    "surfaced_aplus",
    "surfaced_watch",
    "skip_gate_rejection",
)


@dataclass(frozen=True)
class GateAttribution:
    first_rejecting_gate: str  # risk_feasibility|trend_template_min_passes|trend_template|vcp
    failing_gates: tuple[str, ...]


@dataclass(frozen=True)
class ScreenResult:
    outcome: str
    bucket: str | None
    n_sliced: int
    rs_path: str | None
    tt_criteria: tuple[CriterionResult, ...]  # the 8 trend_template results (for stage seeding)
    gate_attribution: GateAttribution | None
    gate_passes: dict[str, bool] | None = None  # per-gate pass over the SCREENABLE subset (else None)


# The 8 trend_template criterion names (mirrors swing.evaluation.criteria.trend_template.CHECK_NAMES).
# A test (test_screen_eval.py::test_tt_names_match_production) asserts parity so this never drifts.
_TT_NAMES = (
    "TT1_above_150_200",
    "TT2_150_above_200",
    "TT3_200_rising",
    "TT4_50_above_150_200",
    "TT5_above_50",
    "TT6_above_52w_low_30pct",
    "TT7_within_52w_high_25pct",
    "TT8_rs_rank",
)


def _na_tt_criteria() -> tuple[CriterionResult, ...]:
    """8 distinct trend_template NA rows -> faithful stage seeds to pass_count 0 -> undefined
    stage (NOT coverage_skip). Used when evaluate_one raises on a tiny below-floor slice so H1
    ALWAYS yields 8 TT rows (spec section 5)."""
    return tuple(CriterionResult(n, "trend_template", "na") for n in _TT_NAMES)


def compute_gate_passes(
    criteria: tuple[CriterionResult, ...] | list[CriterionResult], config: Config
) -> dict[str, bool]:
    """Per-gate pass status mirroring bucket_for's layer gates (spec section 9 per-gate pass rate).
    risk: all risk pass. trend_template: tt_passes >= min_passes AND every TT fail in allowed.
    vcp: vcp_fails (fail|na) <= 2 (i.e. watch-or-better)."""
    tt = [c for c in criteria if c.layer == "trend_template"]
    vcp = [c for c in criteria if c.layer == "vcp"]
    risk = [c for c in criteria if c.layer == "risk"]
    risk_pass = all(c.result == "pass" for c in risk)
    tt_passes = sum(1 for c in tt if c.result == "pass")
    tt_fails = [c.criterion_name for c in tt if c.result != "pass"]
    allowed = set(config.trend_template.allowed_miss_names)
    tt_gate = tt_passes >= config.trend_template.min_passes and all(n in allowed for n in tt_fails)
    vcp_gate = sum(1 for c in vcp if c.result in ("fail", "na")) <= 2
    return {"risk_feasibility": risk_pass, "trend_template": tt_gate, "vcp": vcp_gate}


def classify_h1_outcome(*, has_bars: bool, n_sliced: int, bucket: str | None, floor: int) -> str:
    if not has_bars or n_sliced == 0:
        return "no_data"
    if n_sliced < floor:
        return "skip_insufficient_history"
    if bucket == "aplus":
        return "surfaced_aplus"
    if bucket == "watch":
        return "surfaced_watch"
    return "skip_gate_rejection"


def attribute_first_rejecting_gate(
    criteria: tuple[CriterionResult, ...] | list[CriterionResult], config: Config
) -> GateAttribution:
    tt = [c for c in criteria if c.layer == "trend_template"]
    vcp = [c for c in criteria if c.layer == "vcp"]
    risk = [c for c in criteria if c.layer == "risk"]

    risk_fails = [c.criterion_name for c in risk if c.result != "pass"]
    if risk_fails:
        return GateAttribution("risk_feasibility", tuple(risk_fails))

    tt_passes = sum(1 for c in tt if c.result == "pass")
    tt_fails = [c.criterion_name for c in tt if c.result != "pass"]
    allowed = set(config.trend_template.allowed_miss_names)

    if tt_passes < config.trend_template.min_passes:
        return GateAttribution("trend_template_min_passes", tuple(tt_fails))
    unallowed = [n for n in tt_fails if n not in allowed]
    if unallowed:
        return GateAttribution("trend_template", tuple(tt_fails))

    vcp_fails = [c.criterion_name for c in vcp if c.result in ("fail", "na")]
    if len(vcp_fails) > 2:
        return GateAttribution("vcp", tuple(vcp_fails))

    # Reached only if the caller mis-routed a non-skip candidate; name it explicitly.
    return GateAttribution("none", ())


def evaluate_h1(
    *,
    ticker: str,
    exemplar_full: pd.DataFrame,
    spy_full: pd.DataFrame | None,
    session: date,
    config: Config,
) -> ScreenResult:
    floor = screenable_floor(config)
    sliced = slice_to(exemplar_full, session)
    n = len(sliced)
    if n == 0:
        return ScreenResult("no_data", None, 0, None, (), None)

    proxy = rs_proxy.build_batch(
        ticker=ticker, exemplar_sliced=sliced, spy_full=spy_full, session=session, config=config
    )
    ctx = CandidateContext(
        ticker=ticker,
        ohlcv=sliced,
        config=config,
        batch=proxy.batch,
        market=MarketContext(),
        current_equity=EQUITY_FLOOR_SURROGATE,
    )
    try:
        candidate = evaluate_one(ctx)
    except Exception:  # noqa: BLE001
        # The youngest names' earliest sweep sessions slice to a handful of bars; evaluate_one is
        # hardened for liquid finviz candidates, not 1-bar input. Below the screenable floor an
        # exception is invariably too-few-bars -> classify insufficient_history, but STILL return 8
        # synthetic NA TT rows so the faithful H2 stage seeds to undefined (not coverage_skip), per
        # spec section 5 ("ALWAYS returns the 8 trend_template criteria"). At/above the floor a raise
        # is a genuine bug and must NOT be swallowed.
        if n < floor:
            return ScreenResult(
                "skip_insufficient_history", None, n, proxy.rs_path, _na_tt_criteria(), None, None
            )
        raise
    tt = tuple(c for c in candidate.criteria if c.layer == "trend_template")
    outcome = classify_h1_outcome(has_bars=True, n_sliced=n, bucket=candidate.bucket, floor=floor)
    attrib = (
        attribute_first_rejecting_gate(candidate.criteria, config)
        if outcome == "skip_gate_rejection"
        else None
    )
    gate_passes = (
        compute_gate_passes(candidate.criteria, config)
        if outcome in ("surfaced_aplus", "surfaced_watch", "skip_gate_rejection")
        else None
    )
    return ScreenResult(outcome, candidate.bucket, n, proxy.rs_path, tt, attrib, gate_passes)
