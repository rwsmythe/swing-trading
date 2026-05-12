"""Phase 9 T-A.3 — risk_policy repo CRUD + RiskPolicy dataclass validator."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.datetime_helpers import now_ms
from swing.data.db import ensure_schema
from swing.data.models import RiskPolicy
from swing.data.repos.risk_policy import (
    NoActivePolicyError,
    get_active_policy,
    get_policy_by_id,
    insert_policy,
    list_policy_history,
    update_policy_active_flag,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "phase9_repo.db")


def _full_kwargs(**overrides):
    base = dict(
        effective_from=now_ms(),
        effective_to=None,
        is_active=1,
        superseded_by_policy_id=None,
        created_at=now_ms(),
        policy_notes=None,
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
        low_sample_size_threshold_class_b_n=5,
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
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# §1 — repo CRUD
# ---------------------------------------------------------------------------


def test_get_active_policy_returns_seed(conn: sqlite3.Connection) -> None:
    p = get_active_policy(conn)
    assert p.policy_id == 1
    assert p.is_active == 1
    assert p.capital_floor_constant_dollars == 7500.0
    assert p.scratch_epsilon_R == 0.10
    assert p.mfe_mae_default_precision_level == "daily_approximate"


def test_get_active_policy_raises_when_no_active_row(
    conn: sqlite3.Connection,
) -> None:
    conn.execute("UPDATE risk_policy SET is_active = 0")
    with pytest.raises(NoActivePolicyError):
        get_active_policy(conn)


def test_get_policy_by_id_returns_specific_row(conn: sqlite3.Connection) -> None:
    p = get_policy_by_id(conn, policy_id=1)
    assert p is not None
    assert p.policy_id == 1


def test_get_policy_by_id_returns_none_for_unknown(
    conn: sqlite3.Connection,
) -> None:
    assert get_policy_by_id(conn, policy_id=99999) is None


def test_insert_policy_returns_new_id(conn: sqlite3.Connection) -> None:
    """Pure INSERT inside caller's transaction; returns new policy_id.

    Predecessor flagged is_active=0 first to free the partial-unique slot.
    """
    conn.execute("BEGIN IMMEDIATE")
    update_policy_active_flag(
        conn, policy_id=1, is_active=0, effective_to=now_ms(),
        superseded_by_policy_id=None,
    )
    new_id = insert_policy(
        conn,
        **_full_kwargs(max_account_risk_per_trade_pct=0.75),
    )
    conn.execute("COMMIT")
    assert new_id == 2
    p = get_policy_by_id(conn, policy_id=2)
    assert p is not None
    assert p.max_account_risk_per_trade_pct == 0.75


def test_repo_does_not_commit(conn: sqlite3.Connection) -> None:
    """Caller-controlled transaction scope (Finviz I1 lesson).

    Inserts inside an explicit BEGIN; assert the row is invisible from a
    second connection until the first connection COMMITs.
    """
    conn.execute("BEGIN IMMEDIATE")
    update_policy_active_flag(
        conn, policy_id=1, is_active=0, effective_to=now_ms(),
        superseded_by_policy_id=None,
    )
    new_id = insert_policy(conn, **_full_kwargs(max_account_risk_per_trade_pct=0.75))

    db_path = Path(conn.execute("PRAGMA database_list").fetchone()[2])
    other = sqlite3.connect(db_path, timeout=0.1)
    try:
        other.execute("PRAGMA foreign_keys=ON")
        # Other connection must NOT see the un-committed row.
        cur = other.execute(
            "SELECT COUNT(*) FROM risk_policy WHERE policy_id = ?",
            (new_id,),
        )
        # SQLite WAL allows reads but the row is still uncommitted from
        # the writing connection's perspective; in WAL mode the second
        # connection sees the *last committed* state, which excludes the
        # new row.
        assert cur.fetchone()[0] == 0
    finally:
        other.close()
    conn.execute("COMMIT")


def test_list_policy_history_tiebreaker_order(conn: sqlite3.Connection) -> None:
    """Spec §3.1: ORDER BY effective_from DESC, policy_id DESC."""
    same_ts = now_ms()
    conn.execute("BEGIN IMMEDIATE")
    update_policy_active_flag(
        conn, policy_id=1, is_active=0, effective_to=same_ts,
        superseded_by_policy_id=None,
    )
    id_2 = insert_policy(
        conn,
        **_full_kwargs(effective_from=same_ts, is_active=0, effective_to=same_ts),
    )
    id_3 = insert_policy(
        conn,
        **_full_kwargs(effective_from=same_ts, is_active=1),
    )
    conn.execute("COMMIT")
    rows = list_policy_history(conn)
    # Most recent comes first; same effective_from → higher policy_id wins.
    assert rows[0].policy_id == id_3
    assert rows[1].policy_id == id_2


def test_list_policy_history_limit(conn: sqlite3.Connection) -> None:
    rows = list_policy_history(conn, limit=1)
    assert len(rows) == 1


def test_update_policy_active_flag_sets_supersession_chain(
    conn: sqlite3.Connection,
) -> None:
    conn.execute("BEGIN IMMEDIATE")
    ts = now_ms()
    update_policy_active_flag(
        conn, policy_id=1, is_active=0, effective_to=ts,
        superseded_by_policy_id=None,
    )
    new_id = insert_policy(conn, **_full_kwargs(effective_from=ts))
    update_policy_active_flag(
        conn, policy_id=1, is_active=0, effective_to=ts,
        superseded_by_policy_id=new_id,
    )
    conn.execute("COMMIT")

    p1 = get_policy_by_id(conn, policy_id=1)
    assert p1 is not None
    assert p1.is_active == 0
    assert p1.effective_to == ts
    assert p1.superseded_by_policy_id == new_id


# ---------------------------------------------------------------------------
# §2 — RiskPolicy dataclass __post_init__ validator
# ---------------------------------------------------------------------------


def test_riskpolicy_constructs_with_valid_fields() -> None:
    p = RiskPolicy(policy_id=99, **_full_kwargs())
    assert p.policy_id == 99
    assert p.process_grade_weight_entry == 0.40


def test_riskpolicy_post_init_rejects_nan_real_field() -> None:
    with pytest.raises(ValueError, match="not finite"):
        RiskPolicy(
            policy_id=99,
            **_full_kwargs(max_account_risk_per_trade_pct=float("nan")),
        )


def test_riskpolicy_post_init_rejects_inf_real_field() -> None:
    with pytest.raises(ValueError, match="not finite"):
        RiskPolicy(
            policy_id=99,
            **_full_kwargs(capital_floor_constant_dollars=float("inf")),
        )


def test_riskpolicy_post_init_rejects_negative_capital_floor() -> None:
    with pytest.raises(ValueError, match="capital_floor_constant_dollars"):
        RiskPolicy(
            policy_id=99,
            **_full_kwargs(capital_floor_constant_dollars=-100.0),
        )


def test_riskpolicy_post_init_rejects_zero_capital_floor() -> None:
    with pytest.raises(ValueError, match="capital_floor_constant_dollars"):
        RiskPolicy(
            policy_id=99,
            **_full_kwargs(capital_floor_constant_dollars=0.0),
        )


def test_riskpolicy_post_init_rejects_drawdown_positive_threshold() -> None:
    """Phase 10 sign convention: drawdown thresholds < 0 (R1 Major #7)."""
    with pytest.raises(ValueError, match="drawdown_pause_threshold_R"):
        RiskPolicy(
            policy_id=99,
            **_full_kwargs(
                drawdown_circuit_breaker_enabled=1,
                drawdown_pause_threshold_R=2.0,
                drawdown_pause_action="halt_new_entries",
                drawdown_recovery_threshold_R=-0.5,
            ),
        )


def test_riskpolicy_post_init_rejects_drawdown_recovery_positive() -> None:
    with pytest.raises(ValueError, match="drawdown_recovery_threshold_R"):
        RiskPolicy(
            policy_id=99,
            **_full_kwargs(
                drawdown_circuit_breaker_enabled=1,
                drawdown_pause_threshold_R=-2.0,
                drawdown_pause_action="halt_new_entries",
                drawdown_recovery_threshold_R=0.5,
            ),
        )


def test_riskpolicy_post_init_requires_threshold_when_enabled() -> None:
    """When drawdown_circuit_breaker_enabled=1, threshold + action + recovery
    are all required (spec §3.1 cross-field validator path)."""
    with pytest.raises(ValueError, match="drawdown_circuit_breaker_enabled"):
        RiskPolicy(
            policy_id=99,
            **_full_kwargs(
                drawdown_circuit_breaker_enabled=1,
                drawdown_pause_threshold_R=None,
                drawdown_pause_action=None,
                drawdown_recovery_threshold_R=None,
            ),
        )


def test_riskpolicy_post_init_requires_size_reduction_pct_for_reduce_size() -> None:
    with pytest.raises(ValueError, match="drawdown_size_reduction_pct"):
        RiskPolicy(
            policy_id=99,
            **_full_kwargs(
                drawdown_circuit_breaker_enabled=1,
                drawdown_pause_threshold_R=-2.0,
                drawdown_pause_action="reduce_size",
                drawdown_size_reduction_pct=None,  # required for reduce_size
                drawdown_recovery_threshold_R=-0.5,
            ),
        )


def test_riskpolicy_post_init_rejects_invalid_mfe_mae_enum() -> None:
    with pytest.raises(ValueError, match="mfe_mae_default_precision_level"):
        RiskPolicy(
            policy_id=99,
            **_full_kwargs(mfe_mae_default_precision_level="invalid"),
        )


def test_riskpolicy_post_init_rejects_invalid_drawdown_action_enum() -> None:
    with pytest.raises(ValueError, match="drawdown_pause_action"):
        RiskPolicy(
            policy_id=99,
            **_full_kwargs(
                drawdown_circuit_breaker_enabled=1,
                drawdown_pause_threshold_R=-2.0,
                drawdown_pause_action="not_a_real_action",
                drawdown_recovery_threshold_R=-0.5,
            ),
        )


def test_riskpolicy_post_init_rejects_grade_weights_not_summing_to_1() -> None:
    with pytest.raises(ValueError, match="process_grade_weight"):
        RiskPolicy(
            policy_id=99,
            **_full_kwargs(
                process_grade_weight_entry=0.50,
                process_grade_weight_management=0.35,
                process_grade_weight_exit=0.25,
            ),
        )


def test_riskpolicy_post_init_accepts_alternative_valid_weights() -> None:
    p = RiskPolicy(
        policy_id=99,
        **_full_kwargs(
            process_grade_weight_entry=0.50,
            process_grade_weight_management=0.30,
            process_grade_weight_exit=0.20,
        ),
    )
    assert p.policy_id == 99


def test_riskpolicy_post_init_rejects_zero_grade_weight() -> None:
    with pytest.raises(ValueError, match="process_grade_weight_entry"):
        RiskPolicy(
            policy_id=99,
            **_full_kwargs(
                process_grade_weight_entry=0.0,
                process_grade_weight_management=0.5,
                process_grade_weight_exit=0.5,
            ),
        )


def test_riskpolicy_post_init_rejects_grade_weight_at_or_above_one() -> None:
    with pytest.raises(ValueError, match="process_grade_weight_entry"):
        RiskPolicy(
            policy_id=99,
            **_full_kwargs(
                process_grade_weight_entry=1.0,
                process_grade_weight_management=0.0,  # would fail too
                process_grade_weight_exit=0.0,
            ),
        )


def test_riskpolicy_post_init_rejects_invalid_size_reduction_pct() -> None:
    with pytest.raises(ValueError, match="drawdown_size_reduction_pct"):
        RiskPolicy(
            policy_id=99,
            **_full_kwargs(
                drawdown_circuit_breaker_enabled=1,
                drawdown_pause_threshold_R=-2.0,
                drawdown_pause_action="reduce_size",
                drawdown_size_reduction_pct=1.5,  # > 1.0 invalid
                drawdown_recovery_threshold_R=-0.5,
            ),
        )


def test_riskpolicy_post_init_rejects_negative_count_field() -> None:
    with pytest.raises(ValueError, match="max_concurrent_positions"):
        RiskPolicy(
            policy_id=99,
            **_full_kwargs(max_concurrent_positions=-1),
        )


def test_riskpolicy_post_init_rejects_invalid_consecutive_losses_action() -> None:
    with pytest.raises(ValueError, match="consecutive_losses_pause_action"):
        RiskPolicy(
            policy_id=99,
            **_full_kwargs(consecutive_losses_pause_action="not_review_required"),
        )
