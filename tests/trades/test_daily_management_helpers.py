"""Pure-helper tests for Phase 8 daily_management service module.

Plan: docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md §T3.0.
Spec: §1.5 maturity-stage thresholds, §3.1 column definitions, §3.1.1
OPERATION_REQUIRED_FIELDS, §5.6 R3 Major #4 thesis-status resolution rule,
§6.6 trail-MA period stamp, §E pure-helper formulas (verbatim).

These helpers are pure (no DB, no I/O) so unit tests assert input → output.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from swing.trades.daily_management import (
    DAILY_MGMT_PRECISION_RANK,
    DAILY_MGMT_THESIS_UNRECORDED_SENTINEL,
    OPERATION_REQUIRED_FIELDS,
    compute_maturity_stage,
    compute_open_R_effective,
    compute_position_capital_utilization,
    compute_position_portfolio_heat,
    compute_running_extrema_R,
    compute_trail_MA_eligibility_flag,
    resolve_thesis_status,
    validate_for_operation,
)

# -- compute_maturity_stage --------------------------------------------------


@pytest.mark.parametrize("mfe_r,expected", [
    (None, None),
    (0.0, "pre_+1.5R"),
    (1.49, "pre_+1.5R"),
    (1.5, "+1.5R_to_+2R"),
    (1.99, "+1.5R_to_+2R"),
    (2.0, ">=+2R_trail_eligible"),
    (5.0, ">=+2R_trail_eligible"),
])
def test_compute_maturity_stage_boundaries(mfe_r: float | None, expected: str | None) -> None:
    assert compute_maturity_stage(mfe_r) == expected


# -- compute_trail_MA_eligibility_flag --------------------------------------


@pytest.mark.parametrize("stage,trail_price,stop,expected", [
    (None, 100.0, 90.0, None),
    (">=+2R_trail_eligible", None, 90.0, None),
    (">=+2R_trail_eligible", 100.0, None, None),
    ("pre_+1.5R", 100.0, 90.0, 0),
    ("+1.5R_to_+2R", 100.0, 90.0, 0),
    (">=+2R_trail_eligible", 100.0, 90.0, 1),  # stop < trail → flag=1
    (">=+2R_trail_eligible", 100.0, 100.0, 0),  # stop == trail → flag=0
    (">=+2R_trail_eligible", 100.0, 110.0, 0),  # stop > trail → flag=0
])
def test_compute_trail_MA_eligibility_flag(
    stage: str | None,
    trail_price: float | None,
    stop: float | None,
    expected: int | None,
) -> None:
    assert compute_trail_MA_eligibility_flag(
        maturity_stage=stage,
        trail_MA_candidate_price=trail_price,
        current_stop=stop,
    ) == expected


# -- compute_open_R_effective ------------------------------------------------


def test_compute_open_R_effective_basic() -> None:
    # Entry at 100, stop at 90 → risk_per_share = 10. Position 50 shares.
    # planned_risk_budget = 10 * 50 = 500.
    # Current price 110 → unrealized = (110 - 100) * 50 = 500 → R = 500/500 = 1.0
    assert compute_open_R_effective(
        current_price=110.0, current_avg_cost=100.0,
        current_size=50.0, planned_risk_budget_dollars=500.0,
    ) == 1.0


def test_compute_open_R_effective_zero_budget_raises() -> None:
    with pytest.raises(ValueError, match="planned_risk_budget_dollars"):
        compute_open_R_effective(
            current_price=110.0, current_avg_cost=100.0,
            current_size=50.0, planned_risk_budget_dollars=0.0,
        )


# -- compute_position_capital_utilization -----------------------------------


def test_compute_position_capital_utilization_basic() -> None:
    # 50 shares * 108 / 7500 = 0.72
    result = compute_position_capital_utilization(
        current_size=50.0, current_price=108.0, denominator_dollars=7500.0,
    )
    assert result == pytest.approx(0.72)


def test_compute_position_capital_utilization_zero_denominator_raises() -> None:
    with pytest.raises(ValueError, match="denominator_dollars"):
        compute_position_capital_utilization(
            current_size=50.0, current_price=108.0, denominator_dollars=0.0,
        )


# -- compute_position_portfolio_heat ----------------------------------------


def test_compute_position_portfolio_heat_basic() -> None:
    # max(0, (100 - 92) * 50) = 400
    assert compute_position_portfolio_heat(
        current_avg_cost=100.0, current_stop=92.0, current_size=50.0,
    ) == 400.0


def test_compute_position_portfolio_heat_clamps_to_zero_when_stop_above_avg_cost() -> None:
    # max(0, (100 - 110) * 50) = max(0, -500) = 0  (slippage convention)
    assert compute_position_portfolio_heat(
        current_avg_cost=100.0, current_stop=110.0, current_size=50.0,
    ) == 0.0


# -- compute_running_extrema_R ----------------------------------------------


def test_compute_running_extrema_R_basic() -> None:
    df = pd.DataFrame({
        "High": [105.0, 115.0, 110.0],
        "Low":  [98.0,  102.0, 100.0],
    }, index=pd.to_datetime(["2026-05-05", "2026-05-06", "2026-05-07"]))
    mfe, mae = compute_running_extrema_R(
        df,
        anchor_session=date(2026, 5, 5),
        asof_session=date(2026, 5, 7),
        entry_price=100.0,
        initial_stop=90.0,  # risk_per_share = 10
    )
    # MFE = (max(High) - 100) / 10 = (115 - 100) / 10 = 1.5
    # MAE = (100 - min(Low)) / 10 = (100 - 98) / 10 = 0.2
    assert mfe == 1.5
    assert mae == 0.2


def test_compute_running_extrema_R_returns_zero_on_empty_window() -> None:
    df = pd.DataFrame({"High": [105.0], "Low": [98.0]},
                      index=pd.to_datetime(["2026-05-05"]))
    mfe, mae = compute_running_extrema_R(
        df, anchor_session=date(2026, 6, 1), asof_session=date(2026, 6, 30),
        entry_price=100.0, initial_stop=90.0,
    )
    assert (mfe, mae) == (0.0, 0.0)


def test_compute_running_extrema_R_clamps_to_zero_when_price_never_moves() -> None:
    """Adverse-positive convention: MAE non-negative even when entry > all lows
    is reversed. Both MFE and MAE clamp to >= 0 per spec §2."""
    df = pd.DataFrame({
        "High": [105.0, 105.0],
        "Low":  [102.0, 101.0],
    }, index=pd.to_datetime(["2026-05-05", "2026-05-06"]))
    mfe, mae = compute_running_extrema_R(
        df,
        anchor_session=date(2026, 5, 5),
        asof_session=date(2026, 5, 6),
        entry_price=100.0, initial_stop=90.0,  # risk = 10
    )
    # MFE = (105 - 100) / 10 = 0.5 (positive)
    # MAE = (100 - 101) / 10 = -0.1 → clamped to 0.0
    assert mfe == 0.5
    assert mae == 0.0


def test_compute_running_extrema_R_zero_risk_per_share_raises() -> None:
    df = pd.DataFrame({"High": [105.0], "Low": [98.0]},
                      index=pd.to_datetime(["2026-05-05"]))
    with pytest.raises(ValueError, match="risk_per_share"):
        compute_running_extrema_R(
            df, anchor_session=date(2026, 5, 5), asof_session=date(2026, 5, 5),
            entry_price=100.0, initial_stop=100.0,
        )


# -- validate_for_operation -------------------------------------------------


def test_validate_for_operation_snapshot_emit_missing_fields() -> None:
    incomplete = {"current_price": 100.0}  # missing 13 others
    missing = validate_for_operation(incomplete, op="snapshot_emit")
    assert "current_stop" in missing
    assert "current_size" in missing
    # CHECK at least 13 missing reported:
    assert len(missing) >= 13


def test_validate_for_operation_snapshot_emit_complete_returns_empty() -> None:
    complete = {f: 0.0 for f in OPERATION_REQUIRED_FIELDS["snapshot_emit"]}
    # Provide non-zero/non-empty so None check passes (we use 0.0 throughout):
    complete["maturity_stage"] = "pre_+1.5R"
    assert validate_for_operation(complete, op="snapshot_emit") == []


def test_validate_for_operation_event_log_emit_minimal() -> None:
    minimal = {
        "stop_changed": 0,
        "action_taken": "no_action",
        "rule_violation_suspected": 0,
        "emotional_state": '["calm"]',
    }
    assert validate_for_operation(minimal, op="event_log_emit") == []


def test_validate_for_operation_event_log_emit_missing_returns_list() -> None:
    missing = validate_for_operation({}, op="event_log_emit")
    assert "stop_changed" in missing
    assert "action_taken" in missing
    assert "rule_violation_suspected" in missing
    assert "emotional_state" in missing


def test_validate_for_operation_tier_upgrade_uses_snapshot_emit_fields() -> None:
    """Tier-upgrade replaces an existing snapshot row at a higher precision tier;
    the same 14 position-state fields are required (spec §3.1.1)."""
    incomplete = {"current_price": 100.0}
    missing = validate_for_operation(incomplete, op="tier_upgrade")
    assert len(missing) >= 13


def test_validate_for_operation_unknown_op_raises() -> None:
    with pytest.raises((ValueError, KeyError)):
        validate_for_operation({}, op="bogus")  # type: ignore[arg-type]


def test_validate_for_operation_treats_None_as_missing_but_keeps_zero() -> None:
    """A snapshot field with value None is reported missing; value 0.0 is NOT
    missing (legitimate position-state value, e.g. open_MFE_R_to_date == 0.0)."""
    fields: dict[str, object] = {
        f: 0.0 for f in OPERATION_REQUIRED_FIELDS["snapshot_emit"]
    }
    fields["maturity_stage"] = "pre_+1.5R"
    fields["open_MFE_R_to_date"] = 0.0  # legitimately zero
    fields["current_price"] = None  # explicitly None — should be missing
    missing = validate_for_operation(fields, op="snapshot_emit")
    assert "current_price" in missing
    assert "open_MFE_R_to_date" not in missing


# -- resolve_thesis_status --------------------------------------------------


def test_resolve_thesis_status_open_default_intact() -> None:
    """Open trades, no event_log thesis update → 'intact'."""
    assert resolve_thesis_status(
        trade_state="managing", latest_thesis_in_event_log=None,
    ) == "intact"


def test_resolve_thesis_status_closed_default_unrecorded() -> None:
    """Closed trades, no event_log thesis update → sentinel 'unrecorded' (NOT 'intact')."""
    assert resolve_thesis_status(
        trade_state="closed", latest_thesis_in_event_log=None,
    ) == DAILY_MGMT_THESIS_UNRECORDED_SENTINEL
    assert DAILY_MGMT_THESIS_UNRECORDED_SENTINEL == "unrecorded"


def test_resolve_thesis_status_reviewed_default_unrecorded() -> None:
    """Reviewed trades behave like closed for thesis-default purposes."""
    assert resolve_thesis_status(
        trade_state="reviewed", latest_thesis_in_event_log=None,
    ) == DAILY_MGMT_THESIS_UNRECORDED_SENTINEL


def test_resolve_thesis_status_event_log_value_overrides_default() -> None:
    """If event_log has non-NULL thesis_status, that value is returned regardless of state."""
    assert resolve_thesis_status(
        trade_state="closed", latest_thesis_in_event_log="invalidated",
    ) == "invalidated"
    assert resolve_thesis_status(
        trade_state="managing", latest_thesis_in_event_log="weakening",
    ) == "weakening"


# -- re-export sanity -------------------------------------------------------


def test_DAILY_MGMT_PRECISION_RANK_reexported_from_trades_namespace() -> None:
    """T2.3 carry-forward: trades.daily_management re-exports the rank dict."""
    assert DAILY_MGMT_PRECISION_RANK == {
        "daily_approximate": 1,
        "intraday_estimated": 2,
        "intraday_exact": 3,
    }
