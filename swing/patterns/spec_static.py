"""Phase 13 T2.SB1 T-A.1.5b Defect 2 — static rule_criteria +
structural_evidence_schema for the 5 V1 detector pattern classes.

Encodes the canonical rule criteria tables + structural evidence dataclass
shapes from
`docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`
sections 5.2 through 5.6 VERBATIM (transliterated to ASCII per Windows
cp1252 stdout gotcha; +/- substituted for the +/- sign).

Consumed by `swing/cli.py:label_exemplars_cmd` at the dispatch-payload emit
path so the pattern-labeler subagent receives the actual rule criteria +
schema for the requested `pattern_class` (replaces the V1 placeholder dicts
that forced the operator-paired session at T-A.1.7 to manually paste spec
content into the dispatch payload).

LOCK (per T-A.1.5b brief section 1.2): this is V1 PATCH scope only. When
T2.SB3 + T2.SB4 land the actual rule-based detector modules, they MAY
rebase the criteria + schema onto compute-derived defaults; until then this
module is the source of truth for dev-time labeling dispatch payloads.

ASCII-only on every string per CLAUDE.md Windows cp1252 stdout gotcha
(non-ASCII glyphs flowing through stdout via `click.echo` crash PowerShell).
"""
from __future__ import annotations

import copy
from typing import Any

from swing.data.models import DETECTOR_PATTERN_CLASSES

# ---------------------------------------------------------------------------
# Rule criteria per pattern class (spec sections 5.2 through 5.6 verbatim,
# transliterated to ASCII).
# ---------------------------------------------------------------------------

_VCP_CRITERIA: list[dict[str, Any]] = [
    {
        "id": 1,
        "name": "stage_2_uptrend",
        "description": "In Stage 2 uptrend per trend template",
        "lock": "current_stage(ticker, asof_date) == 'stage_2'",
        "tolerance": "NONE - hard gate",
    },
    {
        "id": 2,
        "name": "prior_uptrend_leg",
        "description": "Prior uptrend leg of >= 30% over >= 8 weeks",
        "lock": "prior_uptrend_pct >= 0.30 AND prior_uptrend_weeks >= 8",
        "tolerance": "+/- 2% tolerance on uptrend pct",
    },
    {
        "id": 3,
        "name": "contractions_monotonic",
        "description": (
            "Sequence of N >= 2 contractions where each depth % decreases "
            "monotonically"
        ),
        "lock": (
            "len(contractions) >= 2 AND all(c[i].depth_pct < c[i-1].depth_pct "
            "for i in range(1, len(contractions)))"
        ),
        "tolerance": (
            "+/- 0.5% tolerance on monotonicity (per v2 brief section 5.1 "
            "weakness mitigation)"
        ),
    },
    {
        "id": 4,
        "name": "contraction_depth_bounds",
        "description": (
            "Typical depths: T1 ~15-30%, T2 ~10-15%, T3 ~5-10%; "
            "acceptance range T1 in [10%, 35%]; T2 in [5%, 20%]; "
            "T3 in [3%, 15%]"
        ),
        "lock": (
            "contractions[0].depth_pct in [0.10, 0.35] AND "
            "contractions[1].depth_pct in [0.05, 0.20] AND "
            "(len(contractions) < 3 OR contractions[2].depth_pct "
            "in [0.03, 0.15])"
        ),
        "tolerance": "NONE - these are bounds, not point thresholds",
    },
    {
        "id": 5,
        "name": "volume_decline_through_contractions",
        "description": "Volume declines through the contraction sequence",
        "lock": (
            "volume_segments[i].avg_volume < volume_segments[i-1].avg_volume "
            "for i in range(1, len(volume_segments))"
        ),
        "tolerance": "+/- 10% tolerance per pair",
    },
    {
        "id": 6,
        "name": "base_duration",
        "description": "Duration: 3-12 weeks total base",
        "lock": "(base_end - base_start).days in [21, 84]",
        "tolerance": "NONE - duration is the bound",
    },
    {
        "id": 7,
        "name": "pivot_at_base_top",
        "description": (
            "Pivot formed near top of base (within 1% of base top)"
        ),
        "lock": "pivot_price / base_top_price in [0.99, 1.01]",
        "tolerance": "+/- 0.5% tolerance",
    },
    {
        "id": 8,
        "name": "breakout_volume_optional",
        "description": (
            "Optional: breakout above pivot on volume >= 40% above 50d avg"
        ),
        "lock": "breakout_volume_ratio >= 1.40",
        "tolerance": "NONE - optional criterion",
    },
]

_FLAT_BASE_CRITERIA: list[dict[str, Any]] = [
    {
        "id": 1,
        "name": "stage_2_uptrend",
        "description": "In Stage 2 uptrend",
        "lock": "current_stage == 'stage_2'",
        "tolerance": "NONE - hard gate",
    },
    {
        "id": 2,
        "name": "prior_uptrend_leg",
        "description": "Prior uptrend leg (similar to VCP)",
        "lock": "prior_uptrend_pct >= 0.20 AND prior_uptrend_weeks >= 5",
        "tolerance": "+/- 2%",
    },
    {
        "id": 3,
        "name": "bounded_range",
        "description": "Bounded range: top - bottom in [3%, 12%]",
        "lock": (
            "(range_top - range_bottom) / range_bottom in [0.03, 0.12]"
        ),
        "tolerance": "+/- 0.5%",
    },
    {
        "id": 4,
        "name": "low_slope",
        "description": (
            "Low slope: linear regression slope of mid-range / range_bottom "
            "<= 0.005/week"
        ),
        "lock": "regression_slope_pct_per_week <= 0.005",
        "tolerance": "NONE",
    },
    {
        "id": 5,
        "name": "tight_atr",
        "description": "Tight ATR: avg(ATR_5d) / mid_range <= 0.025",
        "lock": "mean_atr_pct <= 0.025",
        "tolerance": "NONE",
    },
    {
        "id": 6,
        "name": "base_duration",
        "description": "Duration >= 5-7 weeks",
        "lock": "(base_end - base_start).days >= 35",
        "tolerance": "NONE - duration is the bound",
    },
    {
        "id": 7,
        "name": "pivot_at_range_top",
        "description": "Pivot at top of range",
        "lock": "pivot_price / range_top in [0.99, 1.01]",
        "tolerance": "+/- 0.5%",
    },
]

_CUP_WITH_HANDLE_CRITERIA: list[dict[str, Any]] = [
    {
        "id": 1,
        "name": "stage_2_uptrend",
        "description": "Stage 2 uptrend",
        "lock": "current_stage == 'stage_2'",
        "tolerance": "NONE",
    },
    {
        "id": 2,
        "name": "cup_left_to_bottom",
        "description": (
            "Cup left edge to bottom: smooth decline of >= 12% over "
            ">= 4 weeks; <= 35%"
        ),
        "lock": (
            "cup_depth_pct in [0.12, 0.35] AND "
            "cup_left_to_bottom_days >= 28"
        ),
        "tolerance": "+/- 0.5%",
    },
    {
        "id": 3,
        "name": "cup_right_edge_recovery",
        "description": (
            "Cup bottom to right edge: rounded recovery (NOT sharp V); "
            "cup right edge >= 95% of cup left edge"
        ),
        "lock": (
            "cup_right_edge_price >= 0.95 * cup_left_edge_price"
        ),
        "tolerance": "+/- 1%",
    },
    {
        "id": 4,
        "name": "cup_duration",
        "description": "Cup duration: 6-26 weeks (per O'Neil bounds)",
        "lock": "cup_duration_days in [42, 182]",
        "tolerance": "NONE",
    },
    {
        "id": 5,
        "name": "handle_shape",
        "description": (
            "Handle: shallow pullback from cup right edge of <= 15% AND "
            ">= 5d duration"
        ),
        "lock": (
            "handle_depth_pct <= 0.15 AND handle_duration_days >= 5"
        ),
        "tolerance": "+/- 1% on depth",
    },
    {
        "id": 6,
        "name": "handle_above_cup_midpoint",
        "description": "Handle low above cup midpoint",
        "lock": (
            "handle_low_price > "
            "(cup_left_edge_price + cup_bottom_price) / 2"
        ),
        "tolerance": "NONE",
    },
    {
        "id": 7,
        "name": "pivot_at_cup_right_edge",
        "description": (
            "Pivot at cup right edge (above the resistance level)"
        ),
        "lock": "pivot_price / cup_right_edge_price in [0.99, 1.01]",
        "tolerance": "+/- 0.5%",
    },
    {
        "id": 8,
        "name": "volume_dries_during_handle",
        "description": "Volume drying up during handle",
        "lock": "handle_avg_volume / cup_avg_volume <= 0.85",
        "tolerance": "+/- 5%",
    },
]

# Cup-with-handle rounded-vs-V test (spec section 5.4 supplementary note,
# inlined per source-of-truth fidelity).
_CUP_WITH_HANDLE_ROUNDED_TEST: dict[str, str] = {
    "method": (
        "Cup-bottom curvature: compute 5-day window centered on "
        "cup_midpoint_date = cup_start_date + "
        "(cup_bottom_date - cup_start_date) / 2."
    ),
    "rounded_predicate": (
        "min(window_lows) < cup_bottom_price * 1.02 -> cup is rounded"
    ),
    "v_shape_reject_predicate": (
        "min(window_lows) > cup_bottom_price * 1.05 -> cup is V-shaped, reject"
    ),
}

_HIGH_TIGHT_FLAG_CRITERIA: list[dict[str, Any]] = [
    {
        "id": 1,
        "name": "stage_2_uptrend",
        "description": "Stage 2 uptrend",
        "lock": "current_stage == 'stage_2'",
        "tolerance": "NONE",
    },
    {
        "id": 2,
        "name": "prior_advance_pole",
        "description": (
            "Prior advance (pole): >= 90% gain over 4-8 weeks"
        ),
        "lock": (
            "pole_pct >= 0.90 AND pole_duration_days in [28, 56]"
        ),
        "tolerance": "+/- 5% on pct",
    },
    {
        "id": 3,
        "name": "consolidation_pullback",
        "description": (
            "Consolidation: tight; <= 25% pullback from pole top over "
            "3-5 weeks"
        ),
        "lock": (
            "consolidation_pullback_pct <= 0.25 AND "
            "consolidation_duration_days in [21, 35]"
        ),
        "tolerance": "+/- 2%",
    },
    {
        "id": 4,
        "name": "consolidation_width",
        "description": "Consolidation range: <= 15% width (top to bottom)",
        "lock": "consolidation_width_pct <= 0.15",
        "tolerance": "NONE",
    },
    {
        "id": 5,
        "name": "consolidation_volume_contracts",
        "description": "Volume contracts during consolidation",
        "lock": (
            "consolidation_avg_volume / pole_avg_volume <= 0.65"
        ),
        "tolerance": "+/- 10%",
    },
    {
        "id": 6,
        "name": "pivot_at_consolidation_top",
        "description": "Pivot at consolidation top",
        "lock": (
            "pivot_price / consolidation_top_price in [0.99, 1.01]"
        ),
        "tolerance": "+/- 0.5%",
    },
]

_DOUBLE_BOTTOM_W_CRITERIA: list[dict[str, Any]] = [
    {
        "id": 1,
        "name": "stage_context",
        "description": (
            "Stage 2 uptrend OR coming OUT of Stage 4 toward 2"
        ),
        "lock": (
            "current_stage in ('stage_2',) OR (recent_stage == 'stage_4' "
            "AND current_stage in ('stage_2',))"
        ),
        "tolerance": "NONE",
    },
    {
        "id": 2,
        "name": "trough_1_drawdown",
        "description": (
            "Trough 1: low point with >= 15% drawdown from prior peak"
        ),
        "lock": "trough_1_drawdown_pct >= 0.15",
        "tolerance": "+/- 1%",
    },
    {
        "id": 3,
        "name": "center_peak_retracement",
        "description": "Center peak: recovery >= 50% retracement",
        "lock": "center_peak_retracement_pct >= 0.50",
        "tolerance": "+/- 2%",
    },
    {
        "id": 4,
        "name": "trough_2_alignment",
        "description": (
            "Trough 2: at approximately same level as trough 1 (+/- 5%) "
            "OR undercut by <= 5%"
        ),
        "lock": (
            "abs(trough_2 - trough_1) / trough_1 <= 0.05 OR "
            "(trough_2 < trough_1 AND "
            "(trough_1 - trough_2) / trough_1 <= 0.05)"
        ),
        "tolerance": "+/- 0.5%",
    },
    {
        "id": 5,
        "name": "symmetric_durations",
        "description": (
            "Symmetric structure: trough_1 -> center_peak duration in "
            "[5d, 35d]; center_peak -> trough_2 duration in [5d, 35d]"
        ),
        "lock": "both durations in [5, 35]",
        "tolerance": "NONE",
    },
    {
        "id": 6,
        "name": "pivot_at_center_peak",
        "description": "Pivot at center peak height",
        "lock": "pivot_price / center_peak_price in [0.99, 1.01]",
        "tolerance": "+/- 0.5%",
    },
    {
        "id": 7,
        "name": "trough_2_volume_rises",
        "description": (
            "Volume rises into trough_2 (optional; shakeout signal)"
        ),
        "lock": (
            "trough_2_avg_volume / trough_1_avg_volume in [1.0, 2.0]"
        ),
        "tolerance": "OPTIONAL",
    },
    {
        "id": 8,
        "name": "trough_2_undercut_bonus",
        "description": (
            "Trough_2 undercut adds geometric_score bonus (composite "
            "formula caps at 1.0)"
        ),
        "lock": "geometric_score += 0.10 if undercut else 0",
        "tolerance": "LOCK",
    },
]

# Pack everything per pattern_class.

_RULE_CRITERIA_BY_CLASS: dict[str, dict[str, Any]] = {
    "vcp": {
        "pattern_class": "vcp",
        "pattern_name": "Volatility Contraction Pattern",
        "spec_section": "section 5.2",
        "criteria": _VCP_CRITERIA,
        "composite_scoring_note": (
            "Weighted sum of criteria pass/fail with #1 (stage_2_uptrend) "
            "and #6 (base_duration) as hard gates - no partial credit; "
            "pattern rejected if either hard gate fails."
        ),
    },
    "flat_base": {
        "pattern_class": "flat_base",
        "pattern_name": "Flat-base consolidation",
        "spec_section": "section 5.3",
        "criteria": _FLAT_BASE_CRITERIA,
        "composite_scoring_note": (
            "Weighted sum of criteria pass/fail with #1 (stage_2_uptrend) "
            "as hard gate."
        ),
    },
    "cup_with_handle": {
        "pattern_class": "cup_with_handle",
        "pattern_name": "Cup-with-handle (O'Neil / CANSLIM)",
        "spec_section": "section 5.4",
        "criteria": _CUP_WITH_HANDLE_CRITERIA,
        "rounded_vs_v_test": _CUP_WITH_HANDLE_ROUNDED_TEST,
        "composite_scoring_note": (
            "Weighted sum of criteria pass/fail; rounded-vs-V test is a "
            "hard reject gate when cup is V-shaped."
        ),
    },
    "high_tight_flag": {
        "pattern_class": "high_tight_flag",
        "pattern_name": "High-tight flag (Minervini / O'Neil)",
        "spec_section": "section 5.5",
        "criteria": _HIGH_TIGHT_FLAG_CRITERIA,
        "composite_scoring_note": (
            "Weighted sum of criteria pass/fail with #1 (stage_2_uptrend) "
            "as hard gate."
        ),
    },
    "double_bottom_w": {
        "pattern_class": "double_bottom_w",
        "pattern_name": "Double-bottom W (Minervini / O'Neil)",
        "spec_section": "section 5.6",
        "criteria": _DOUBLE_BOTTOM_W_CRITERIA,
        "composite_scoring_note": (
            "Weighted sum of criteria pass/fail; trough_2 undercut adds "
            "+0.10 bonus capping at 1.0 via min(1.0, ...)."
        ),
    },
}

# ---------------------------------------------------------------------------
# Structural evidence schemas per pattern class (frozen dataclass shapes
# from spec sections 5.2 through 5.6, serialized as JSON-friendly dicts).
# ---------------------------------------------------------------------------

#
# T-A.1.5b Codex R1 M#5 closure: schemas mirror the VERBATIM field lists
# enumerated in spec sections 5.3 through 5.6. The spec section 5.2
# VCPEvidence dataclass is the only class that explicitly lists `stage`
# and `criteria_pass`; section 5.3-5.6 use abbreviated `/ ... /` field
# enumerations and DO NOT enumerate `stage` or `criteria_pass`. We mirror
# the spec literally per class; the spec section 5.6 criterion #1 lock
# does reference `current_stage` + `recent_stage` but the structural
# evidence dataclass for DBW per spec section 5.6 only enumerates
# `trough_1_*` / `center_peak_*` / `trough_2_*` / `undercut` / `pivot_*`
# / `geometric_score`.
#
_STRUCTURAL_EVIDENCE_SCHEMA_BY_CLASS: dict[str, dict[str, Any]] = {
    "vcp": {
        "pattern_class": "vcp",
        "spec_section": "section 5.2",
        "evidence_dataclass": "VCPEvidence",
        "fields": {
            "stage": "Literal['stage_2', ...]",
            "prior_uptrend_pct": "float",
            "prior_uptrend_weeks": "int",
            "base_start_date": "date (ISO YYYY-MM-DD)",
            "base_end_date": "date (ISO YYYY-MM-DD)",
            "contractions": "tuple[Contraction, ...] (see nested shape)",
            "pivot_price": "float",
            "base_top_price": "float",
            "pivot_within_top_pct": "float",
            "volume_decline_passes": "bool",
            "breakout_observed": "bool (optional criterion)",
            "breakout_volume_ratio": (
                "float | None (populated if breakout_observed)"
            ),
            "criteria_pass": "dict[str, bool] (per-criterion granular)",
            "geometric_score": "float in [0.0, 1.0]",
        },
        "nested_shapes": {
            "Contraction": {
                "start_date": "date (ISO YYYY-MM-DD)",
                "end_date": "date (ISO YYYY-MM-DD)",
                "peak_price": "float",
                "trough_price": "float",
                "depth_pct": "float",
                "duration_days": "int",
                "avg_volume": "float",
            },
        },
    },
    "flat_base": {
        "pattern_class": "flat_base",
        "spec_section": "section 5.3",
        "evidence_dataclass": "FlatBaseEvidence",
        "fields": {
            "range_top": "float",
            "range_bottom": "float",
            "regression_slope_pct_per_week": "float",
            "mean_atr_pct": "float",
            "duration_days": "int",
            "pivot_price": "float",
            "geometric_score": "float in [0.0, 1.0]",
        },
    },
    "cup_with_handle": {
        "pattern_class": "cup_with_handle",
        "spec_section": "section 5.4",
        "evidence_dataclass": "CupWithHandleEvidence",
        "fields": {
            "cup_left_edge_date": "date (ISO YYYY-MM-DD)",
            "cup_left_edge_price": "float",
            "cup_bottom_date": "date (ISO YYYY-MM-DD)",
            "cup_bottom_price": "float",
            "cup_right_edge_date": "date (ISO YYYY-MM-DD)",
            "cup_right_edge_price": "float",
            "cup_duration_days": "int",
            "cup_depth_pct": "float",
            "handle_start_date": "date (ISO YYYY-MM-DD)",
            "handle_end_date": "date (ISO YYYY-MM-DD)",
            "handle_low_price": "float",
            "handle_depth_pct": "float",
            "handle_duration_days": "int",
            "handle_avg_volume": "float",
            "cup_avg_volume": "float",
            "pivot_price": "float",
            "is_rounded": "bool (per rounded-vs-V test in spec section 5.4)",
            "geometric_score": "float in [0.0, 1.0]",
        },
    },
    "high_tight_flag": {
        "pattern_class": "high_tight_flag",
        "spec_section": "section 5.5",
        "evidence_dataclass": "HighTightFlagEvidence",
        "fields": {
            "pole_start_date": "date (ISO YYYY-MM-DD)",
            "pole_start_price": "float",
            "pole_end_date": "date (ISO YYYY-MM-DD)",
            "pole_end_price": "float",
            "pole_pct": "float",
            "pole_duration_days": "int",
            "pole_avg_volume": "float",
            "consolidation_start_date": "date (ISO YYYY-MM-DD)",
            "consolidation_end_date": "date (ISO YYYY-MM-DD)",
            "consolidation_top_price": "float",
            "consolidation_bottom_price": "float",
            "consolidation_pullback_pct": "float",
            "consolidation_width_pct": "float",
            "consolidation_duration_days": "int",
            "consolidation_avg_volume": "float",
            "pivot_price": "float",
            "geometric_score": "float in [0.0, 1.0]",
        },
    },
    "double_bottom_w": {
        "pattern_class": "double_bottom_w",
        "spec_section": "section 5.6",
        "evidence_dataclass": "DoubleBottomWEvidence",
        "fields": {
            "trough_1_date": "date (ISO YYYY-MM-DD)",
            "trough_1_price": "float",
            "trough_1_drawdown_pct": "float",
            "trough_1_avg_volume": "float",
            "center_peak_date": "date (ISO YYYY-MM-DD)",
            "center_peak_price": "float",
            "center_peak_retracement_pct": "float",
            "trough_2_date": "date (ISO YYYY-MM-DD)",
            "trough_2_price": "float",
            "trough_2_avg_volume": "float",
            "undercut": "bool (true if trough_2 < trough_1)",
            "pivot_price": "float",
            "geometric_score": (
                "float in [0.0, 1.0] (+0.10 if undercut bonus applied, "
                "capped at 1.0)"
            ),
        },
    },
}


def get_rule_criteria(pattern_class: str) -> dict[str, Any]:
    """Return the rule_criteria dict for the given V1 pattern class.

    The returned shape carries `pattern_class`, `pattern_name`,
    `spec_section`, `criteria` (list of {id, name, description, lock,
    tolerance}), `composite_scoring_note`, and (for cup_with_handle) the
    `rounded_vs_v_test` supplementary method.

    Returns a deep copy so caller mutations do NOT poison subsequent
    dispatch payloads in-process (Codex R1 Minor #2 closure).

    Raises ValueError on an unknown pattern_class - the CLI separately
    validates pattern_class against DETECTOR_PATTERN_CLASSES, so reaching
    this raise indicates a callsite bug.
    """
    if pattern_class not in DETECTOR_PATTERN_CLASSES:
        raise ValueError(
            "pattern_class must be one of "
            f"{DETECTOR_PATTERN_CLASSES}, got {pattern_class!r}"
        )
    return copy.deepcopy(_RULE_CRITERIA_BY_CLASS[pattern_class])


def get_structural_evidence_schema(pattern_class: str) -> dict[str, Any]:
    """Return the structural_evidence_schema dict for the given V1 class.

    The returned shape carries `pattern_class`, `spec_section`,
    `evidence_dataclass` (name of the dataclass per spec sections 5.2
    through 5.6), `fields` (dict of field-name -> type/semantics string),
    and (for vcp) `nested_shapes` for the Contraction sub-dataclass.

    Returns a deep copy so caller mutations do NOT poison subsequent
    dispatch payloads in-process (Codex R1 Minor #2 closure).

    Raises ValueError on an unknown pattern_class.
    """
    if pattern_class not in DETECTOR_PATTERN_CLASSES:
        raise ValueError(
            "pattern_class must be one of "
            f"{DETECTOR_PATTERN_CLASSES}, got {pattern_class!r}"
        )
    return copy.deepcopy(_STRUCTURAL_EVIDENCE_SCHEMA_BY_CLASS[pattern_class])


__all__ = [
    "get_rule_criteria",
    "get_structural_evidence_schema",
]
