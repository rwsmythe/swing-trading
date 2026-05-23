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
