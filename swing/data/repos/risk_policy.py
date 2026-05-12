"""risk_policy repository (migration 0017).

Phase 9 spec §3.1 / §4.1 / §A.0.1. Pure CRUD inside the caller's
transaction scope — repo functions DO NOT call ``conn.commit()`` (Finviz I1
lesson + caller-controlled transaction discipline; the service layer
``swing/trades/risk_policy.py`` owns BEGIN IMMEDIATE / COMMIT / ROLLBACK).

Public API:
  - ``insert_policy(conn, **fields) -> int`` — pure INSERT; returns new policy_id.
  - ``update_policy_active_flag(conn, *, policy_id, is_active, effective_to,
    superseded_by_policy_id)`` — pure UPDATE on the supersession metadata
    columns; called twice during the §4.1 6-step sequence (first to flag
    predecessor inactive freeing the unique slot, then to set the FK pointer
    after successor INSERT).
  - ``get_active_policy(conn) -> RiskPolicy`` — raises NoActivePolicyError if
    zero rows match ``is_active = 1``.
  - ``get_policy_by_id(conn, policy_id) -> RiskPolicy | None``.
  - ``list_policy_history(conn, *, limit=None) -> list[RiskPolicy]`` —
    ORDER BY ``effective_from DESC, policy_id DESC`` per spec §3.1 tiebreaker.
"""
from __future__ import annotations

import sqlite3

from swing.data.models import RiskPolicy


class NoActivePolicyError(RuntimeError):
    """Raised when ``get_active_policy`` finds zero rows with ``is_active = 1``.

    Pre-Phase-9 / pre-seed DB state OR a manual UPDATE that flipped every
    row inactive. Service-layer callers handle this distinct from generic
    sqlite3 errors so startup hooks can fall back gracefully (per Codex R3
    M#1 architectural fix in plan §A.5.1: TOML divergence helper returns
    ``(cfg, None)`` when this exception fires on a v17 DB pre-seed fixture).
    """


_SELECT_COLUMNS = (
    "policy_id, effective_from, effective_to, is_active, "
    "superseded_by_policy_id, created_at, policy_notes, "
    "max_account_risk_per_trade_pct, max_concurrent_positions, "
    "max_portfolio_heat_pct, max_sector_concentration_positions, "
    "consecutive_losses_pause_threshold, consecutive_losses_pause_action, "
    "consecutive_losses_streak_reset, drawdown_circuit_breaker_enabled, "
    "drawdown_pause_threshold_R, drawdown_pause_action, "
    "drawdown_size_reduction_pct, drawdown_recovery_threshold_R, "
    "capital_floor_constant_dollars, scratch_epsilon_R, "
    "review_lag_threshold_days, low_sample_size_threshold_class_a_n, "
    "low_sample_size_threshold_class_b_n, low_sample_size_threshold_class_c_n, "
    "low_sample_size_threshold_class_d_n, global_confidence_floor_n, "
    "bootstrap_resample_count, process_grade_weight_entry, "
    "process_grade_weight_management, process_grade_weight_exit, "
    "mfe_mae_default_precision_level, trail_MA_period_days, "
    "trail_MA_post_2R_period_days"
)


def _row_to_policy(row: tuple) -> RiskPolicy:
    return RiskPolicy(
        policy_id=row[0],
        effective_from=row[1],
        effective_to=row[2],
        is_active=row[3],
        superseded_by_policy_id=row[4],
        created_at=row[5],
        policy_notes=row[6],
        max_account_risk_per_trade_pct=row[7],
        max_concurrent_positions=row[8],
        max_portfolio_heat_pct=row[9],
        max_sector_concentration_positions=row[10],
        consecutive_losses_pause_threshold=row[11],
        consecutive_losses_pause_action=row[12],
        consecutive_losses_streak_reset=row[13],
        drawdown_circuit_breaker_enabled=row[14],
        drawdown_pause_threshold_R=row[15],
        drawdown_pause_action=row[16],
        drawdown_size_reduction_pct=row[17],
        drawdown_recovery_threshold_R=row[18],
        capital_floor_constant_dollars=row[19],
        scratch_epsilon_R=row[20],
        review_lag_threshold_days=row[21],
        low_sample_size_threshold_class_a_n=row[22],
        low_sample_size_threshold_class_b_n=row[23],
        low_sample_size_threshold_class_c_n=row[24],
        low_sample_size_threshold_class_d_n=row[25],
        global_confidence_floor_n=row[26],
        bootstrap_resample_count=row[27],
        process_grade_weight_entry=row[28],
        process_grade_weight_management=row[29],
        process_grade_weight_exit=row[30],
        mfe_mae_default_precision_level=row[31],
        trail_MA_period_days=row[32],
        trail_MA_post_2R_period_days=row[33],
    )


def get_active_policy(conn: sqlite3.Connection) -> RiskPolicy:
    """Return the row with ``is_active = 1``.

    Raises:
        NoActivePolicyError: when zero rows match.
    """
    row = conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM risk_policy WHERE is_active = 1"
    ).fetchone()
    if row is None:
        raise NoActivePolicyError(
            "No risk_policy row has is_active = 1; schema corrupted or "
            "seed missing (was migration 0017 applied?)."
        )
    return _row_to_policy(row)


def get_policy_by_id(
    conn: sqlite3.Connection, policy_id: int,
) -> RiskPolicy | None:
    row = conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM risk_policy WHERE policy_id = ?",
        (policy_id,),
    ).fetchone()
    return _row_to_policy(row) if row else None


def list_policy_history(
    conn: sqlite3.Connection, *, limit: int | None = None,
) -> list[RiskPolicy]:
    """Return policy rows ordered by ``effective_from DESC, policy_id DESC``.

    Spec §3.1 tiebreaker: identical-microsecond ties (rare but possible)
    resolve deterministically by PK monotonicity (newer PK wins).
    """
    base = (
        f"SELECT {_SELECT_COLUMNS} FROM risk_policy "
        "ORDER BY effective_from DESC, policy_id DESC"
    )
    if limit is not None:
        rows = conn.execute(base + " LIMIT ?", (limit,)).fetchall()
    else:
        rows = conn.execute(base).fetchall()
    return [_row_to_policy(r) for r in rows]


_INSERT_COLUMNS = (
    # All columns EXCEPT auto-PK policy_id.
    "effective_from, effective_to, is_active, superseded_by_policy_id, "
    "created_at, policy_notes, "
    "max_account_risk_per_trade_pct, max_concurrent_positions, "
    "max_portfolio_heat_pct, max_sector_concentration_positions, "
    "consecutive_losses_pause_threshold, consecutive_losses_pause_action, "
    "consecutive_losses_streak_reset, drawdown_circuit_breaker_enabled, "
    "drawdown_pause_threshold_R, drawdown_pause_action, "
    "drawdown_size_reduction_pct, drawdown_recovery_threshold_R, "
    "capital_floor_constant_dollars, scratch_epsilon_R, "
    "review_lag_threshold_days, low_sample_size_threshold_class_a_n, "
    "low_sample_size_threshold_class_b_n, low_sample_size_threshold_class_c_n, "
    "low_sample_size_threshold_class_d_n, global_confidence_floor_n, "
    "bootstrap_resample_count, process_grade_weight_entry, "
    "process_grade_weight_management, process_grade_weight_exit, "
    "mfe_mae_default_precision_level, trail_MA_period_days, "
    "trail_MA_post_2R_period_days"
)


def insert_policy(
    conn: sqlite3.Connection,
    *,
    effective_from: str,
    effective_to: str | None,
    is_active: int,
    superseded_by_policy_id: int | None,
    created_at: str,
    policy_notes: str | None,
    max_account_risk_per_trade_pct: float,
    max_concurrent_positions: int,
    max_portfolio_heat_pct: float,
    max_sector_concentration_positions: int,
    consecutive_losses_pause_threshold: int,
    consecutive_losses_pause_action: str,
    consecutive_losses_streak_reset: str,
    drawdown_circuit_breaker_enabled: int,
    drawdown_pause_threshold_R: float | None,
    drawdown_pause_action: str | None,
    drawdown_size_reduction_pct: float | None,
    drawdown_recovery_threshold_R: float | None,
    capital_floor_constant_dollars: float,
    scratch_epsilon_R: float,
    review_lag_threshold_days: int,
    low_sample_size_threshold_class_a_n: int,
    low_sample_size_threshold_class_b_n: int,
    low_sample_size_threshold_class_c_n: int,
    low_sample_size_threshold_class_d_n: int,
    global_confidence_floor_n: int,
    bootstrap_resample_count: int,
    process_grade_weight_entry: float,
    process_grade_weight_management: float,
    process_grade_weight_exit: float,
    mfe_mae_default_precision_level: str,
    trail_MA_period_days: int,
    trail_MA_post_2R_period_days: int | None,
) -> int:
    """Pure INSERT inside the caller's transaction scope.

    Caller MUST own the surrounding BEGIN IMMEDIATE → COMMIT (the service
    layer ``swing/trades/risk_policy.py:supersede_active_policy`` is the
    canonical owner; direct repo callers in tests use explicit ``BEGIN``).

    Returns:
        Newly assigned ``policy_id`` (autoincrement).
    """
    cur = conn.execute(
        f"INSERT INTO risk_policy ({_INSERT_COLUMNS}) VALUES "
        "(?, ?, ?, ?, ?, ?, "
        "?, ?, ?, ?, ?, ?, ?, ?, "
        "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            effective_from, effective_to, is_active, superseded_by_policy_id,
            created_at, policy_notes,
            max_account_risk_per_trade_pct, max_concurrent_positions,
            max_portfolio_heat_pct, max_sector_concentration_positions,
            consecutive_losses_pause_threshold,
            consecutive_losses_pause_action,
            consecutive_losses_streak_reset,
            drawdown_circuit_breaker_enabled,
            drawdown_pause_threshold_R, drawdown_pause_action,
            drawdown_size_reduction_pct, drawdown_recovery_threshold_R,
            capital_floor_constant_dollars,
            scratch_epsilon_R, review_lag_threshold_days,
            low_sample_size_threshold_class_a_n,
            low_sample_size_threshold_class_b_n,
            low_sample_size_threshold_class_c_n,
            low_sample_size_threshold_class_d_n,
            global_confidence_floor_n, bootstrap_resample_count,
            process_grade_weight_entry, process_grade_weight_management,
            process_grade_weight_exit,
            mfe_mae_default_precision_level,
            trail_MA_period_days, trail_MA_post_2R_period_days,
        ),
    )
    return cur.lastrowid


def update_policy_active_flag(
    conn: sqlite3.Connection,
    *,
    policy_id: int,
    is_active: int,
    effective_to: str | None,
    superseded_by_policy_id: int | None,
) -> None:
    """Pure UPDATE on supersession metadata columns inside caller's transaction.

    Called TWICE during the §4.1 6-step supersession sequence:
      - Step 2: predecessor flagged ``is_active=0`` + ``effective_to=now`` +
        ``superseded_by_policy_id=None`` (frees the partial-unique slot
        before successor INSERT).
      - Step 5: predecessor's ``superseded_by_policy_id`` set to the
        successor's ``policy_id`` (audit-chain pointer; allowed to set
        AFTER successor INSERT because the partial-unique slot is already
        free from step 2).
    """
    conn.execute(
        "UPDATE risk_policy "
        "SET is_active = ?, effective_to = ?, superseded_by_policy_id = ? "
        "WHERE policy_id = ?",
        (is_active, effective_to, superseded_by_policy_id, policy_id),
    )
