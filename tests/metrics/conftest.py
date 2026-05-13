"""Shared fixtures for tests/metrics/ — Phase 10 Sub-bundle A."""
from __future__ import annotations

import pytest

from swing.data.models import RiskPolicy


def _make_policy(**overrides) -> RiskPolicy:
    """Construct a RiskPolicy with all 34 fields at spec-default values.

    Per plan §A.7 T-A.1 watch item: "Use a fixed RiskPolicy fixture with
    `global_confidence_floor_n=20`, `bootstrap_resample_count=1000`, all
    class thresholds at spec defaults" — spec §5.1 Class A=3, §5.2 Class B=3,
    §5.3 Class C=5, §5.4 Class D (window N)=10. Overrides keyword-passed.
    """
    defaults = dict(
        policy_id=1,
        effective_from="2026-05-12T00:00:00.000",
        effective_to=None,
        is_active=1,
        superseded_by_policy_id=None,
        created_at="2026-05-12T00:00:00.000",
        policy_notes="test fixture",
        max_account_risk_per_trade_pct=0.50,
        max_concurrent_positions=6,
        max_portfolio_heat_pct=3.0,
        max_sector_concentration_positions=3,
        consecutive_losses_pause_threshold=3,
        consecutive_losses_pause_action="review_required",
        consecutive_losses_streak_reset="review_completed",
        drawdown_circuit_breaker_enabled=0,
        drawdown_pause_threshold_R=None,
        drawdown_pause_action=None,
        drawdown_size_reduction_pct=None,
        drawdown_recovery_threshold_R=None,
        capital_floor_constant_dollars=7500.0,
        scratch_epsilon_R=0.10,
        review_lag_threshold_days=7,
        low_sample_size_threshold_class_a_n=3,
        low_sample_size_threshold_class_b_n=3,
        low_sample_size_threshold_class_c_n=5,
        low_sample_size_threshold_class_d_n=10,
        global_confidence_floor_n=20,
        bootstrap_resample_count=1000,
        process_grade_weight_entry=0.40,
        process_grade_weight_management=0.35,
        process_grade_weight_exit=0.25,
        mfe_mae_default_precision_level="daily_approximate",
        trail_MA_period_days=21,
        trail_MA_post_2R_period_days=None,
    )
    defaults.update(overrides)
    return RiskPolicy(**defaults)


@pytest.fixture
def spec_default_policy() -> RiskPolicy:
    """The spec-default RiskPolicy fixture for Phase 10 metric tests."""
    return _make_policy()


@pytest.fixture
def policy_factory():
    """Factory for overriding individual policy fields (e.g., suppression
    thresholds, confidence floor) per-test without re-typing all 34 fields."""
    return _make_policy
