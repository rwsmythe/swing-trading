"""cfg substitution helper for the V2 OHLCV harness.

Substitutes one cfg field at a time via dataclasses.replace + returns a NEW
Config (immutable; original unchanged). The vcp.watch_max_fails variable is
NOT routed through this helper -- see spec §E.3 / OQ-11 special-case at
sweep.py.
"""
from __future__ import annotations

import dataclasses
from typing import NamedTuple

from research.harness.aplus_v2_ohlcv_evaluator.exceptions import OutOfRangeSubstitutionError
from swing.config import Config

_KNOWN_SUBSECTIONS: frozenset[str] = frozenset(
    {"trend_template", "vcp", "risk", "rs"}
)

# Num TT criteria in swing/evaluation/criteria/trend_template.py CHECK_NAMES (8 items).
_NUM_TT_CRITERIA = 8

# Num VCP criteria evaluated by evaluator.py: prior_trend, stack_r, rising_r,
# proximity, adr, pullback, tightness, vcp, orderliness (9 items).
_NUM_VCP_CRITERIA = 9


class _Range(NamedTuple):
    lo: float  # inclusive lower bound
    hi: float  # inclusive upper bound


# Per-variable valid range table (Codex R1.M1 RESOLVED).
# Enforced by substitute_cfg to raise OutOfRangeSubstitutionError.
# vcp.watch_max_fails is intentionally ABSENT -- it is handled by the
# special-case branch in sweep.py and does NOT route through substitute_cfg.
#
# Semantics:
#   - Additive (int) variables: lo/hi are counts/integers; value must be int
#     in [lo, hi].
#   - Multiplicative (float/int) variables: lo/hi are real bounds; value must
#     be in [lo, hi].
#   - Positive-only floats (percentages, ratios): lo > 0 enforces positivity.
#
# Source annotations cite the production code that establishes the constraint.
_VARIABLE_RANGES: dict[str, _Range] = {
    # trend_template gates/thresholds
    # min_passes: [0, _NUM_TT_CRITERIA]; 0 = disable gate; max = all 8 criteria
    "trend_template.min_passes": _Range(0, _NUM_TT_CRITERIA),
    # rising_ma_period_days: must be >= 1 (< 1 breaks MA rolling window)
    "trend_template.rising_ma_period_days": _Range(1, 365),
    # Percentages: must be > 0 (0 would disable the gate in an uncontrolled way);
    # upper bounds set to 200% to catch runaway multiplicative sweep points.
    "trend_template.high_52w_margin_pct": _Range(0.1, 200.0),
    "trend_template.low_52w_min_pct": _Range(0.1, 200.0),
    # vcp thresholds
    "vcp.prior_trend_min_pct": _Range(0.1, 500.0),
    "vcp.adr_min_pct": _Range(0.1, 50.0),
    "vcp.pullback_max_pct": _Range(0.1, 200.0),
    "vcp.proximity_max_pct": _Range(0.1, 200.0),
    # tightness_days_required: >= 1 (0 would trivially pass any tightness check)
    "vcp.tightness_days_required": _Range(1, 60),
    "vcp.tightness_range_factor": _Range(0.01, 5.0),
    "vcp.orderliness_max_bar_ratio": _Range(0.1, 20.0),
    "vcp.orderliness_max_range_cv": _Range(0.01, 5.0),
    # risk threshold
    # max_risk_pct: > 0 (0 = zero risk budget; production uses 0.005 = 0.5%)
    "risk.max_risk_pct": _Range(0.0001, 0.5),
    # rs thresholds
    # horizon_weeks: >= 1 (0 would produce bars_needed=0, trivially include all)
    "rs.horizon_weeks": _Range(1, 52),
    # rs_rank_min_pass: [0, 100] (RS rank is a percentile 0-100)
    "rs.rs_rank_min_pass": _Range(0, 100),
    "rs.fallback_extreme_pct": _Range(0.1, 100.0),
}


def substitute_cfg(
    cfg: Config,
    variable_name: str,
    sweep_value: float | int,
) -> Config:
    """Return a NEW Config with `variable_name` = `sweep_value`; other
    fields unchanged.

    Args:
      cfg: production cfg from Config.from_defaults() or operator's cfg.
      variable_name: dotted-path form "<sub>.<field>" where <sub> is one of
        {trend_template, vcp, risk, rs}.
      sweep_value: numeric value to substitute. Must match the field's
        expected type (int for additive variables; float for multiplicative).

    Raises:
      ValueError: when <sub> is not in {trend_template, vcp, risk, rs}
        (per Expansion #11 taxonomy discipline + cumulative
        "Literal[...] type hints are NOT runtime-enforced" gotcha).
      OutOfRangeSubstitutionError: when sweep_value falls outside the
        documented valid range for the variable (Codex R1.M1 RESOLVED).
        Range table: _VARIABLE_RANGES at module level.
    """
    sub, field_name = variable_name.split(".", 1)
    if sub not in _KNOWN_SUBSECTIONS:
        raise ValueError(
            f"substitute_cfg: unknown cfg subsection {sub!r}; "
            f"expected one of {sorted(_KNOWN_SUBSECTIONS)}"
        )

    # Range validation (Codex R1.M1 RESOLVED)
    if variable_name in _VARIABLE_RANGES:
        r = _VARIABLE_RANGES[variable_name]
        if not (r.lo <= sweep_value <= r.hi):
            raise OutOfRangeSubstitutionError(
                f"substitute_cfg: {variable_name}={sweep_value!r} is out of "
                f"valid range [{r.lo}, {r.hi}]. "
                f"Sweep value must satisfy {r.lo} <= value <= {r.hi}."
            )

    sub_obj = getattr(cfg, sub)
    new_sub = dataclasses.replace(sub_obj, **{field_name: sweep_value})
    return dataclasses.replace(cfg, **{sub: new_sub})
