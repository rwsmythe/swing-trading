"""T-T4.SB.1 §B.1 Sub-task 1A — sensitivity-sweep variable enumeration."""
from __future__ import annotations

from research.harness.aplus_sensitivity.variables import (
    SweepVariable,
    enumerate_variables,
)
from swing.config import Config


def test_enumerate_sweep_variables_from_config():
    cfg = Config.from_defaults()
    variables = enumerate_variables(cfg)
    # Per spec §1.5.1 + R2 LOCK: 2 gate + 15 threshold = 17 variables.
    assert len(variables) == 17
    names = {v.name for v in variables}
    expected_names = {
        # 2 gate
        "trend_template.min_passes",
        "vcp.watch_max_fails",
        # 3 trend_template threshold (allowed_miss_names + min_passes excluded)
        "trend_template.rising_ma_period_days",
        "trend_template.high_52w_margin_pct",
        "trend_template.low_52w_min_pct",
        # 8 vcp threshold
        "vcp.prior_trend_min_pct",
        "vcp.adr_min_pct",
        "vcp.pullback_max_pct",
        "vcp.proximity_max_pct",
        "vcp.tightness_days_required",
        "vcp.tightness_range_factor",
        "vcp.orderliness_max_bar_ratio",
        "vcp.orderliness_max_range_cv",
        # 1 risk threshold
        "risk.max_risk_pct",
        # 3 rs threshold
        "rs.horizon_weeks",
        "rs.rs_rank_min_pass",
        "rs.fallback_extreme_pct",
    }
    assert names == expected_names, (
        f"missing: {expected_names - names}; extra: {names - expected_names}"
    )
    # Each variable carries valid kind + sweep anchor present.
    gate_count = 0
    for v in variables:
        assert isinstance(v, SweepVariable)
        assert v.kind in {"gate", "threshold_additive", "threshold_multiplicative"}
        if v.kind == "gate":
            gate_count += 1
        assert v.current_value is not None
        assert len(v.sweep_points) >= 3
        assert v.current_value in v.sweep_points
    assert gate_count == 2  # invariant from R2 LOCK


def test_sweep_variable_kind_rejects_invalid_value():
    import pytest

    with pytest.raises(ValueError, match="kind must be one of"):
        SweepVariable(
            name="bogus", kind="additive", current_value=5, sweep_points=(1, 2, 3, 5, 10),
        )
