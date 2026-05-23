"""Tests for V2 OHLCV harness cfg_substitution module."""
from __future__ import annotations

import pytest

from swing.config import Config


def test_substitute_cfg_replaces_trend_template_field_in_isolation():
    cfg = Config.from_defaults()
    from research.harness.aplus_v2_ohlcv_evaluator.cfg_substitution import substitute_cfg
    new_cfg = substitute_cfg(cfg, "trend_template.min_passes", 5)
    assert new_cfg.trend_template.min_passes == 5
    # All other fields unchanged
    assert new_cfg.trend_template.rising_ma_period_days == cfg.trend_template.rising_ma_period_days
    assert new_cfg.vcp == cfg.vcp
    assert new_cfg.risk == cfg.risk
    assert new_cfg.rs == cfg.rs
    # Original unchanged (immutability)
    assert cfg.trend_template.min_passes != 5


def test_substitute_cfg_replaces_vcp_field():
    cfg = Config.from_defaults()
    from research.harness.aplus_v2_ohlcv_evaluator.cfg_substitution import substitute_cfg
    new_cfg = substitute_cfg(cfg, "vcp.adr_min_pct", 6.0)
    assert new_cfg.vcp.adr_min_pct == 6.0
    assert new_cfg.trend_template == cfg.trend_template


def test_substitute_cfg_replaces_risk_field():
    cfg = Config.from_defaults()
    from research.harness.aplus_v2_ohlcv_evaluator.cfg_substitution import substitute_cfg
    new_cfg = substitute_cfg(cfg, "risk.max_risk_pct", 0.0075)
    assert new_cfg.risk.max_risk_pct == 0.0075
    assert new_cfg.vcp == cfg.vcp


def test_substitute_cfg_replaces_rs_field():
    cfg = Config.from_defaults()
    from research.harness.aplus_v2_ohlcv_evaluator.cfg_substitution import substitute_cfg
    new_cfg = substitute_cfg(cfg, "rs.rs_rank_min_pass", 60)
    assert new_cfg.rs.rs_rank_min_pass == 60
    assert new_cfg.trend_template == cfg.trend_template


def test_substitute_cfg_raises_ValueError_on_unknown_subsection():  # noqa: N802
    cfg = Config.from_defaults()
    from research.harness.aplus_v2_ohlcv_evaluator.cfg_substitution import substitute_cfg
    with pytest.raises(ValueError, match="unknown cfg subsection 'fake'"):
        substitute_cfg(cfg, "fake.field", 1.0)


def test_substitute_cfg_preserves_int_vs_float_types():
    cfg = Config.from_defaults()
    from research.harness.aplus_v2_ohlcv_evaluator.cfg_substitution import substitute_cfg
    # Additive (int) sweep_value preserves int
    new_cfg = substitute_cfg(cfg, "trend_template.min_passes", 6)
    assert isinstance(new_cfg.trend_template.min_passes, int)
    # Multiplicative (float) sweep_value preserves float
    new_cfg2 = substitute_cfg(cfg, "vcp.adr_min_pct", 4.5)
    assert isinstance(new_cfg2.vcp.adr_min_pct, float)


# ---------------------------------------------------------------------------
# Range validation tests (Codex R1.M1 RESOLVED)
# ---------------------------------------------------------------------------

def test_substitute_cfg_raises_OutOfRangeSubstitutionError_for_min_passes_above_8():  # noqa: N802
    """trend_template.min_passes > 8 must raise OutOfRangeSubstitutionError.
    8 = _NUM_TT_CRITERIA; asking for 9 passes from 8 criteria is nonsensical.
    This is a REAL range rejection (no monkeypatch) -- discriminating fixture
    per Codex R1.M1 resolution."""
    from research.harness.aplus_v2_ohlcv_evaluator.cfg_substitution import substitute_cfg
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import OutOfRangeSubstitutionError
    cfg = Config.from_defaults()
    with pytest.raises(OutOfRangeSubstitutionError, match="trend_template.min_passes"):
        substitute_cfg(cfg, "trend_template.min_passes", 9)  # 9 > 8 TT criteria


def test_substitute_cfg_raises_OutOfRangeSubstitutionError_for_min_passes_below_0():  # noqa: N802
    """trend_template.min_passes < 0 must raise OutOfRangeSubstitutionError."""
    from research.harness.aplus_v2_ohlcv_evaluator.cfg_substitution import substitute_cfg
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import OutOfRangeSubstitutionError
    cfg = Config.from_defaults()
    with pytest.raises(OutOfRangeSubstitutionError, match="trend_template.min_passes"):
        substitute_cfg(cfg, "trend_template.min_passes", -1)


def test_substitute_cfg_accepts_min_passes_boundary_values():
    """trend_template.min_passes = 0 and 8 (boundary values) must be accepted."""
    from research.harness.aplus_v2_ohlcv_evaluator.cfg_substitution import substitute_cfg
    cfg = Config.from_defaults()
    # lo boundary
    new_cfg_lo = substitute_cfg(cfg, "trend_template.min_passes", 0)
    assert new_cfg_lo.trend_template.min_passes == 0
    # hi boundary
    new_cfg_hi = substitute_cfg(cfg, "trend_template.min_passes", 8)
    assert new_cfg_hi.trend_template.min_passes == 8


def test_substitute_cfg_raises_OutOfRangeSubstitutionError_for_rs_rank_above_100():  # noqa: N802
    """rs.rs_rank_min_pass > 100 must raise OutOfRangeSubstitutionError.
    RS rank is a 0-100 percentile; values > 100 are semantically invalid."""
    from research.harness.aplus_v2_ohlcv_evaluator.cfg_substitution import substitute_cfg
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import OutOfRangeSubstitutionError
    cfg = Config.from_defaults()
    with pytest.raises(OutOfRangeSubstitutionError, match="rs.rs_rank_min_pass"):
        substitute_cfg(cfg, "rs.rs_rank_min_pass", 101)


def test_substitute_cfg_raises_OutOfRangeSubstitutionError_for_negative_max_risk_pct():  # noqa: N802
    """risk.max_risk_pct <= 0 must raise OutOfRangeSubstitutionError.
    Zero risk budget means no position can be taken."""
    from research.harness.aplus_v2_ohlcv_evaluator.cfg_substitution import substitute_cfg
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import OutOfRangeSubstitutionError
    cfg = Config.from_defaults()
    with pytest.raises(OutOfRangeSubstitutionError, match="risk.max_risk_pct"):
        substitute_cfg(cfg, "risk.max_risk_pct", 0.0)


def test_substitute_cfg_range_validation_covers_all_17_enumerated_variables():
    """Smoke-check: all 16 non-watch_max_fails variables have range table entries.
    vcp.watch_max_fails is intentionally absent (handled by sweep.py special-case).
    """
    from research.harness.aplus_v2_ohlcv_evaluator.cfg_substitution import _VARIABLE_RANGES
    expected_variables = {
        "trend_template.min_passes",
        "trend_template.rising_ma_period_days",
        "trend_template.high_52w_margin_pct",
        "trend_template.low_52w_min_pct",
        "vcp.prior_trend_min_pct",
        "vcp.adr_min_pct",
        "vcp.pullback_max_pct",
        "vcp.proximity_max_pct",
        "vcp.tightness_days_required",
        "vcp.tightness_range_factor",
        "vcp.orderliness_max_bar_ratio",
        "vcp.orderliness_max_range_cv",
        "risk.max_risk_pct",
        "rs.horizon_weeks",
        "rs.rs_rank_min_pass",
        "rs.fallback_extreme_pct",
    }
    missing = expected_variables - set(_VARIABLE_RANGES.keys())
    assert not missing, (
        f"Range table missing entries for variables: {sorted(missing)}. "
        "Each enumerated sweep variable (except vcp.watch_max_fails) must have "
        "a range table entry in _VARIABLE_RANGES."
    )
    # vcp.watch_max_fails must NOT be in the range table (handled by sweep.py special-case)
    assert "vcp.watch_max_fails" not in _VARIABLE_RANGES, (
        "vcp.watch_max_fails must NOT be in _VARIABLE_RANGES; it is handled by "
        "the special-case branch in sweep.py and does NOT route through substitute_cfg."
    )
