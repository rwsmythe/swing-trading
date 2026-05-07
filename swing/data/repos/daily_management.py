"""Daily management records repo (Phase 8, migration 0016).

Two ``record_type`` values share the table:
  * ``daily_snapshot`` — pipeline-step-emitted (UPSERT keyed on
    ``(trade_id, data_asof_session, mfe_mae_precision_level)``); carries full
    position-state.
  * ``event_log`` — operator-discretionary (web POST); each emission is its
    own row; position-state OPTIONAL.

Public API split across multiple Phase 8 tasks:

  Task 2.0 (this file): ``insert_snapshot``, ``insert_event_log``
  Task 2.1: ``select_active_snapshot``
  Task 2.2: ``select_history``, ``list_for_trade_timeline``,
            ``list_open_position_active_snapshots``
  Task 2.3: ``upsert_snapshot``, ``tier_upgrade_snapshot``

CLAUDE.md gotcha (2026-05-06) — ``INSERT OR REPLACE`` is forbidden on this
table because REPLACE is ``DELETE old + INSERT new`` semantically and would
CASCADE-WIPE FK-linked rows + reissue the auto-increment PK. T2.0's INSERTs
are plain INSERTs; the UPSERT semantics live in T2.3 via SELECT-then-UPDATE-
or-INSERT against the ACTIVE row.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from swing.data.models import DailyManagementRecord

# Canonical 42-column SELECT list for daily_management_records, in the same
# field order as ``DailyManagementRecord`` so positional unpack into the
# dataclass remains stable. Mirrors Phase 7's ``_row_to_trade`` pattern.
_DMR_SELECT_COLS = (
    # Metadata (10):
    "management_record_id, trade_id, record_type, review_date, "
    "data_asof_session, created_at, mfe_mae_precision_level, "
    "pipeline_run_id, is_superseded, superseded_by_record_id, "
    # Position-state (14):
    "current_price, current_stop, current_size, current_avg_cost, "
    "open_R_effective, open_MFE_R_to_date, open_MAE_R_to_date, "
    "intraday_high, intraday_low, position_capital_utilization_pct, "
    "position_capital_denominator_dollars, "
    "position_portfolio_heat_contribution_dollars, "
    "maturity_stage, trail_MA_candidate_price, "
    # Trail-MA stamp/cache (2):
    "trail_MA_period_days, trail_MA_eligibility_flag, "
    # Operator-input (16):
    "thesis_status, prior_stop, new_stop, linked_trade_event_id, "
    "stop_changed, stop_change_reason, volume_behavior, "
    "relative_strength_status, market_regime_change, "
    "sector_condition_change, news_or_event_update, "
    "action_taken, action_reason, emotional_state, "
    "rule_violation_suspected, management_notes"
)


def _row_to_record(row: sqlite3.Row | tuple[Any, ...]) -> DailyManagementRecord:
    """Map a row selected via ``_DMR_SELECT_COLS`` to a ``DailyManagementRecord``."""
    return DailyManagementRecord(
        management_record_id=row[0],
        trade_id=row[1],
        record_type=row[2],
        review_date=row[3],
        data_asof_session=row[4],
        created_at=row[5],
        mfe_mae_precision_level=row[6],
        pipeline_run_id=row[7],
        is_superseded=row[8],
        superseded_by_record_id=row[9],
        current_price=row[10],
        current_stop=row[11],
        current_size=row[12],
        current_avg_cost=row[13],
        open_R_effective=row[14],
        open_MFE_R_to_date=row[15],
        open_MAE_R_to_date=row[16],
        intraday_high=row[17],
        intraday_low=row[18],
        position_capital_utilization_pct=row[19],
        position_capital_denominator_dollars=row[20],
        position_portfolio_heat_contribution_dollars=row[21],
        maturity_stage=row[22],
        trail_MA_candidate_price=row[23],
        trail_MA_period_days=row[24],
        trail_MA_eligibility_flag=row[25],
        thesis_status=row[26],
        prior_stop=row[27],
        new_stop=row[28],
        linked_trade_event_id=row[29],
        stop_changed=row[30],
        stop_change_reason=row[31],
        volume_behavior=row[32],
        relative_strength_status=row[33],
        market_regime_change=row[34],
        sector_condition_change=row[35],
        news_or_event_update=row[36],
        action_taken=row[37],
        action_reason=row[38],
        emotional_state=row[39],
        rule_violation_suspected=row[40],
        management_notes=row[41],
    )


def select_active_snapshot(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    data_asof_session: str,
) -> DailyManagementRecord | None:
    """Return the ACTIVE daily_snapshot row for ``(trade_id, data_asof_session)``.

    "Active" = ``record_type='daily_snapshot' AND is_superseded=0``. The
    partial unique index from migration 0016 guarantees at most one such row
    per ``(trade_id, data_asof_session, mfe_mae_precision_level)``; this
    function scopes to the snapshot discriminator and returns the single
    active row regardless of precision tier (callers needing tier-specific
    lookup should filter post-hoc, or use a more specific helper).

    Returns ``None`` if no active snapshot exists for the given key.
    """
    row = conn.execute(
        f"SELECT {_DMR_SELECT_COLS} FROM daily_management_records "
        f"WHERE trade_id = ? AND data_asof_session = ? "
        f"  AND record_type = 'daily_snapshot' AND is_superseded = 0",
        (trade_id, data_asof_session),
    ).fetchone()
    return _row_to_record(row) if row else None


def insert_snapshot(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    snapshot_fields: dict[str, Any],
) -> int:
    """Pure INSERT for ``record_type='daily_snapshot'``.

    Caller manages the outer transaction (``with conn:``).

    Caller MUST validate ``snapshot_fields`` per
    ``OPERATION_REQUIRED_FIELDS["snapshot_emit"]`` BEFORE calling this
    function — the repo layer trusts validated input. Optional keys default
    to NULL (``pipeline_run_id``, ``trail_MA_candidate_price``,
    ``trail_MA_period_days``).

    Returns the new ``management_record_id``.
    """
    cur = conn.execute(
        """
        INSERT INTO daily_management_records (
            trade_id, record_type, review_date, data_asof_session, created_at,
            mfe_mae_precision_level, pipeline_run_id, is_superseded,
            current_price, current_stop, current_size, current_avg_cost,
            open_R_effective, open_MFE_R_to_date, open_MAE_R_to_date,
            intraday_high, intraday_low,
            position_capital_utilization_pct,
            position_capital_denominator_dollars,
            position_portfolio_heat_contribution_dollars,
            maturity_stage, trail_MA_candidate_price,
            trail_MA_period_days, trail_MA_eligibility_flag
        ) VALUES (?, 'daily_snapshot', ?, ?, ?, ?, ?, 0,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade_id,
            snapshot_fields["review_date"],
            snapshot_fields["data_asof_session"],
            snapshot_fields["created_at"],
            snapshot_fields["mfe_mae_precision_level"],
            snapshot_fields.get("pipeline_run_id"),
            snapshot_fields["current_price"],
            snapshot_fields["current_stop"],
            snapshot_fields["current_size"],
            snapshot_fields["current_avg_cost"],
            snapshot_fields["open_R_effective"],
            snapshot_fields["open_MFE_R_to_date"],
            snapshot_fields["open_MAE_R_to_date"],
            snapshot_fields["intraday_high"],
            snapshot_fields["intraday_low"],
            snapshot_fields["position_capital_utilization_pct"],
            snapshot_fields["position_capital_denominator_dollars"],
            snapshot_fields["position_portfolio_heat_contribution_dollars"],
            snapshot_fields["maturity_stage"],
            snapshot_fields.get("trail_MA_candidate_price"),
            snapshot_fields.get("trail_MA_period_days"),
            snapshot_fields["trail_MA_eligibility_flag"],
        ),
    )
    return int(cur.lastrowid)


def insert_event_log(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    event_log_fields: dict[str, Any],
) -> int:
    """Pure INSERT for ``record_type='event_log'``. Position-state OPTIONAL.

    Caller manages the outer transaction (``with conn:``).

    Caller MUST validate per ``OPERATION_REQUIRED_FIELDS["event_log_emit"]``.
    Position-state fields (``current_price``, ``current_stop``, etc.) are
    OPTIONAL on event_log per spec §3.1.1 R1 Critical 1 — the operator can
    log a free-form event without committing to a fresh price/stop snapshot.

    Returns the new ``management_record_id``.
    """
    cur = conn.execute(
        """
        INSERT INTO daily_management_records (
            trade_id, record_type, review_date, data_asof_session, created_at,
            mfe_mae_precision_level, pipeline_run_id, is_superseded,
            current_price, current_stop, current_size, current_avg_cost,
            open_R_effective, open_MFE_R_to_date, open_MAE_R_to_date,
            intraday_high, intraday_low,
            position_capital_utilization_pct,
            position_capital_denominator_dollars,
            position_portfolio_heat_contribution_dollars,
            maturity_stage, trail_MA_candidate_price,
            trail_MA_period_days, trail_MA_eligibility_flag,
            thesis_status, prior_stop, new_stop, linked_trade_event_id,
            stop_changed, stop_change_reason,
            volume_behavior, relative_strength_status,
            market_regime_change, sector_condition_change,
            news_or_event_update,
            action_taken, action_reason, emotional_state,
            rule_violation_suspected, management_notes
        ) VALUES (?, 'event_log', ?, ?, ?, ?, ?, 0,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade_id,
            event_log_fields["review_date"],
            event_log_fields["data_asof_session"],
            event_log_fields["created_at"],
            event_log_fields["mfe_mae_precision_level"],
            event_log_fields.get("pipeline_run_id"),
            # Position-state — all optional on event_log:
            event_log_fields.get("current_price"),
            event_log_fields.get("current_stop"),
            event_log_fields.get("current_size"),
            event_log_fields.get("current_avg_cost"),
            event_log_fields.get("open_R_effective"),
            event_log_fields.get("open_MFE_R_to_date"),
            event_log_fields.get("open_MAE_R_to_date"),
            event_log_fields.get("intraday_high"),
            event_log_fields.get("intraday_low"),
            event_log_fields.get("position_capital_utilization_pct"),
            event_log_fields.get("position_capital_denominator_dollars"),
            event_log_fields.get(
                "position_portfolio_heat_contribution_dollars"
            ),
            event_log_fields.get("maturity_stage"),
            event_log_fields.get("trail_MA_candidate_price"),
            event_log_fields.get("trail_MA_period_days"),
            event_log_fields.get("trail_MA_eligibility_flag"),
            # Operator-input fields:
            event_log_fields.get("thesis_status"),
            event_log_fields.get("prior_stop"),
            event_log_fields.get("new_stop"),
            event_log_fields.get("linked_trade_event_id"),
            event_log_fields.get("stop_changed"),
            event_log_fields.get("stop_change_reason"),
            event_log_fields.get("volume_behavior"),
            event_log_fields.get("relative_strength_status"),
            event_log_fields.get("market_regime_change"),
            event_log_fields.get("sector_condition_change"),
            event_log_fields.get("news_or_event_update"),
            event_log_fields.get("action_taken"),
            event_log_fields.get("action_reason"),
            event_log_fields.get("emotional_state"),
            event_log_fields.get("rule_violation_suspected"),
            event_log_fields.get("management_notes"),
        ),
    )
    return int(cur.lastrowid)
