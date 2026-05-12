"""reconciliation_runs + reconciliation_discrepancies repository (migration 0017).

Phase 9 spec §3.2 / §3.3 / §3.3.3 + plan §A.2 + §B file map (T-B.1). Pure
CRUD inside the caller's transaction scope — repo functions DO NOT call
``conn.commit()`` (Finviz I1 lesson + caller-controlled transaction
discipline; the service layer ``swing/trades/reconciliation.py`` owns
BEGIN IMMEDIATE / COMMIT / ROLLBACK per spec §3.3.3).

Two-read pattern on ``list_recent_runs`` per CLAUDE.md gotcha "Queries
ordered by ``started_ts DESC`` on ``pipeline_runs`` mask prior completes
mid-run": separate query for most-recent-COMPLETED (for "when did we last
reconcile?") + most-recent-STARTED (for "what's running now?").
"""
from __future__ import annotations

import sqlite3

from swing.data.models import (
    ReconciliationDiscrepancy,
    ReconciliationRun,
)

_RUN_SELECT_COLUMNS = (
    "run_id, source, source_artifact_path, source_artifact_sha256, "
    "period_start, period_end, started_ts, finished_ts, state, "
    "account_equity_journal_dollars, account_equity_source_dollars, "
    "equity_delta_dollars, trades_reconciled_count, fills_reconciled_count, "
    "discrepancies_count, unresolved_discrepancies_count, summary_json, "
    "error_message, notes"
)


_DISCREPANCY_SELECT_COLUMNS = (
    "discrepancy_id, run_id, discrepancy_type, trade_id, fill_id, "
    "cash_movement_id, linked_daily_management_record_id, ticker, "
    "field_name, expected_value_json, actual_value_json, delta_text, "
    "material_to_review, resolution, resolution_reason, resolved_at, "
    "resolved_by, mistake_tag_assigned, created_at"
)


_DISCREPANCY_SELECT_COLUMNS_D_ALIAS = (
    "d.discrepancy_id, d.run_id, d.discrepancy_type, d.trade_id, d.fill_id, "
    "d.cash_movement_id, d.linked_daily_management_record_id, d.ticker, "
    "d.field_name, d.expected_value_json, d.actual_value_json, d.delta_text, "
    "d.material_to_review, d.resolution, d.resolution_reason, d.resolved_at, "
    "d.resolved_by, d.mistake_tag_assigned, d.created_at"
)


def _row_to_run(row: tuple) -> ReconciliationRun:
    return ReconciliationRun(
        run_id=row[0],
        source=row[1],
        source_artifact_path=row[2],
        source_artifact_sha256=row[3],
        period_start=row[4],
        period_end=row[5],
        started_ts=row[6],
        finished_ts=row[7],
        state=row[8],
        account_equity_journal_dollars=row[9],
        account_equity_source_dollars=row[10],
        equity_delta_dollars=row[11],
        trades_reconciled_count=row[12],
        fills_reconciled_count=row[13],
        discrepancies_count=row[14],
        unresolved_discrepancies_count=row[15],
        summary_json=row[16],
        error_message=row[17],
        notes=row[18],
    )


def _row_to_discrepancy(row: tuple) -> ReconciliationDiscrepancy:
    return ReconciliationDiscrepancy(
        discrepancy_id=row[0],
        run_id=row[1],
        discrepancy_type=row[2],
        trade_id=row[3],
        fill_id=row[4],
        cash_movement_id=row[5],
        linked_daily_management_record_id=row[6],
        ticker=row[7],
        field_name=row[8],
        expected_value_json=row[9],
        actual_value_json=row[10],
        delta_text=row[11],
        material_to_review=row[12],
        resolution=row[13],
        resolution_reason=row[14],
        resolved_at=row[15],
        resolved_by=row[16],
        mistake_tag_assigned=row[17],
        created_at=row[18],
    )


# ============================================================================
# reconciliation_runs CRUD
# ============================================================================


def insert_run(
    conn: sqlite3.Connection,
    *,
    source: str,
    started_ts: str,
    state: str = "running",
    source_artifact_path: str | None = None,
    source_artifact_sha256: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    finished_ts: str | None = None,
    account_equity_journal_dollars: float | None = None,
    account_equity_source_dollars: float | None = None,
    equity_delta_dollars: float | None = None,
    trades_reconciled_count: int | None = None,
    fills_reconciled_count: int | None = None,
    discrepancies_count: int | None = None,
    unresolved_discrepancies_count: int | None = None,
    summary_json: str | None = None,
    error_message: str | None = None,
    notes: str | None = None,
) -> int:
    """Pure INSERT inside the caller's transaction scope.

    Caller owns the surrounding BEGIN IMMEDIATE → COMMIT (service layer
    ``swing/trades/reconciliation.py:run_tos_reconciliation``).

    Returns:
        Newly-assigned ``run_id`` (autoincrement).
    """
    cur = conn.execute(
        "INSERT INTO reconciliation_runs ("
        "source, source_artifact_path, source_artifact_sha256, "
        "period_start, period_end, started_ts, finished_ts, state, "
        "account_equity_journal_dollars, account_equity_source_dollars, "
        "equity_delta_dollars, trades_reconciled_count, "
        "fills_reconciled_count, discrepancies_count, "
        "unresolved_discrepancies_count, summary_json, error_message, notes"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            source, source_artifact_path, source_artifact_sha256,
            period_start, period_end, started_ts, finished_ts, state,
            account_equity_journal_dollars, account_equity_source_dollars,
            equity_delta_dollars, trades_reconciled_count,
            fills_reconciled_count, discrepancies_count,
            unresolved_discrepancies_count, summary_json, error_message, notes,
        ),
    )
    return cur.lastrowid


def update_run_completed(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    finished_ts: str,
    account_equity_journal_dollars: float | None = None,
    account_equity_source_dollars: float | None = None,
    equity_delta_dollars: float | None = None,
    trades_reconciled_count: int | None = None,
    fills_reconciled_count: int | None = None,
    discrepancies_count: int | None = None,
    unresolved_discrepancies_count: int | None = None,
    summary_json: str | None = None,
    notes: str | None = None,
) -> None:
    """Transition a running run to ``state='completed'`` with summary fields.

    UPDATE only — no REPLACE. Caller controls transaction (the service
    layer's BEGIN IMMEDIATE owns it per spec §3.3.3).
    """
    conn.execute(
        "UPDATE reconciliation_runs SET "
        "state = 'completed', finished_ts = ?, "
        "account_equity_journal_dollars = ?, "
        "account_equity_source_dollars = ?, "
        "equity_delta_dollars = ?, "
        "trades_reconciled_count = ?, "
        "fills_reconciled_count = ?, "
        "discrepancies_count = ?, "
        "unresolved_discrepancies_count = ?, "
        "summary_json = COALESCE(?, summary_json), "
        "notes = COALESCE(?, notes) "
        "WHERE run_id = ?",
        (
            finished_ts,
            account_equity_journal_dollars,
            account_equity_source_dollars,
            equity_delta_dollars,
            trades_reconciled_count,
            fills_reconciled_count,
            discrepancies_count,
            unresolved_discrepancies_count,
            summary_json,
            notes,
            run_id,
        ),
    )


def update_run_failed(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    finished_ts: str,
    error_message: str,
) -> None:
    """Transition a running run to ``state='failed'`` with error_message.

    Per spec §3.3.3 + plan §A.2.1: failure-path PRESERVES the existing run
    row + UPDATEs ``state='failed'`` (NOT a rollback-new-row pattern). Any
    discrepancies / cash_movements / fills emitted prior to the failure are
    PRESERVED alongside the failed-state UPDATE within the same outer
    transaction (audit-trail integrity prioritized over rollback purity).
    """
    conn.execute(
        "UPDATE reconciliation_runs SET "
        "state = 'failed', finished_ts = ?, error_message = ? "
        "WHERE run_id = ?",
        (finished_ts, error_message, run_id),
    )


def get_run(
    conn: sqlite3.Connection, run_id: int,
) -> ReconciliationRun | None:
    row = conn.execute(
        f"SELECT {_RUN_SELECT_COLUMNS} FROM reconciliation_runs "
        "WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    return _row_to_run(row) if row else None


def list_recent_runs(
    conn: sqlite3.Connection, *, limit: int = 10,
) -> list[ReconciliationRun]:
    """List recent runs in started_ts DESC, run_id DESC tiebreak order.

    See ``most_recent_completed_run`` + ``most_recent_started_run`` for the
    two-read pattern that callers needing "last good data" timestamps MUST
    use to avoid the CLAUDE.md gotcha "Queries ordered by ``started_ts
    DESC`` on ``pipeline_runs`` mask prior completes mid-run".
    """
    rows = conn.execute(
        f"SELECT {_RUN_SELECT_COLUMNS} FROM reconciliation_runs "
        "ORDER BY started_ts DESC, run_id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [_row_to_run(r) for r in rows]


def most_recent_completed_run(
    conn: sqlite3.Connection,
) -> ReconciliationRun | None:
    """Return the most-recent run with ``state='completed'`` (two-read pattern).

    Use this for "when did we last successfully reconcile?" — does NOT get
    masked by a currently-running new run. Companion to
    ``most_recent_started_run`` for the "what's happening now?" surface.
    """
    row = conn.execute(
        f"SELECT {_RUN_SELECT_COLUMNS} FROM reconciliation_runs "
        "WHERE state = 'completed' "
        "ORDER BY finished_ts DESC, run_id DESC LIMIT 1"
    ).fetchone()
    return _row_to_run(row) if row else None


def most_recent_started_run(
    conn: sqlite3.Connection,
) -> ReconciliationRun | None:
    """Return the most-recent run regardless of state (two-read pattern).

    Use this for "what's running now?" surface. Caller pairs with
    ``most_recent_completed_run`` per CLAUDE.md gotcha discipline.
    """
    row = conn.execute(
        f"SELECT {_RUN_SELECT_COLUMNS} FROM reconciliation_runs "
        "ORDER BY started_ts DESC, run_id DESC LIMIT 1"
    ).fetchone()
    return _row_to_run(row) if row else None


def count_runs_for_artifact_sha256(
    conn: sqlite3.Connection, sha256: str,
) -> int:
    """Count prior runs with the same ``source_artifact_sha256`` (advisory).

    Drives a CLI advisory "this CSV has been reconciled N times already"
    surface per spec §5.1 R3 Major #4 "source_artifact_rerun_signal". Does
    NOT block re-runs — operator decides whether to proceed.
    """
    row = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_runs "
        "WHERE source_artifact_sha256 = ?",
        (sha256,),
    ).fetchone()
    return int(row[0])


# ============================================================================
# reconciliation_discrepancies CRUD
# ============================================================================


def insert_discrepancy(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    discrepancy_type: str,
    field_name: str,
    material_to_review: int,
    created_at: str,
    trade_id: int | None = None,
    fill_id: int | None = None,
    cash_movement_id: int | None = None,
    linked_daily_management_record_id: int | None = None,
    ticker: str | None = None,
    expected_value_json: str | None = None,
    actual_value_json: str | None = None,
    delta_text: str | None = None,
    resolution: str = "unresolved",
    resolution_reason: str | None = None,
    resolved_at: str | None = None,
    resolved_by: str | None = None,
    mistake_tag_assigned: str | None = None,
) -> int:
    """Pure INSERT inside the caller's transaction scope.

    Returns:
        Newly-assigned ``discrepancy_id`` (autoincrement).
    """
    cur = conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "run_id, discrepancy_type, trade_id, fill_id, cash_movement_id, "
        "linked_daily_management_record_id, ticker, field_name, "
        "expected_value_json, actual_value_json, delta_text, "
        "material_to_review, resolution, resolution_reason, "
        "resolved_at, resolved_by, mistake_tag_assigned, created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id, discrepancy_type, trade_id, fill_id, cash_movement_id,
            linked_daily_management_record_id, ticker, field_name,
            expected_value_json, actual_value_json, delta_text,
            material_to_review, resolution, resolution_reason,
            resolved_at, resolved_by, mistake_tag_assigned, created_at,
        ),
    )
    return cur.lastrowid


def update_discrepancy_resolution(
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    resolution: str,
    resolution_reason: str | None,
    resolved_by: str,
    resolved_at: str,
    mistake_tag_assigned: str | None = None,
) -> None:
    """UPDATE the resolution-lifecycle columns on an existing row.

    UPDATE only — NO ``INSERT OR REPLACE`` per CLAUDE.md gotcha (FK
    references would CASCADE-wipe; resolution UPDATE preserves PK).
    """
    conn.execute(
        "UPDATE reconciliation_discrepancies SET "
        "resolution = ?, resolution_reason = ?, "
        "resolved_at = ?, resolved_by = ?, "
        "mistake_tag_assigned = COALESCE(?, mistake_tag_assigned) "
        "WHERE discrepancy_id = ?",
        (
            resolution, resolution_reason, resolved_at, resolved_by,
            mistake_tag_assigned, discrepancy_id,
        ),
    )


def update_discrepancy_material(
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    material_to_review: int,
) -> None:
    """UPDATE the ``material_to_review`` override flag on a discrepancy row.

    Per spec §3.3.2 operator-override semantics: the classification flag
    starts at INSERT-time per ``MATERIAL_BY_TYPE`` lookup; operator may
    flip it post-INSERT via the CLI ``swing journal discrepancy resolve``
    ``--material`` flag (writing-plans T-B.7).
    """
    if material_to_review not in (0, 1):
        raise ValueError(
            f"material_to_review must be 0 or 1; got {material_to_review}"
        )
    conn.execute(
        "UPDATE reconciliation_discrepancies SET material_to_review = ? "
        "WHERE discrepancy_id = ?",
        (material_to_review, discrepancy_id),
    )


def get_discrepancy(
    conn: sqlite3.Connection, discrepancy_id: int,
) -> ReconciliationDiscrepancy | None:
    row = conn.execute(
        f"SELECT {_DISCREPANCY_SELECT_COLUMNS} FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (discrepancy_id,),
    ).fetchone()
    return _row_to_discrepancy(row) if row else None


def list_discrepancies_for_run(
    conn: sqlite3.Connection, run_id: int,
) -> list[ReconciliationDiscrepancy]:
    rows = conn.execute(
        f"SELECT {_DISCREPANCY_SELECT_COLUMNS} FROM reconciliation_discrepancies "
        "WHERE run_id = ? ORDER BY discrepancy_id ASC",
        (run_id,),
    ).fetchall()
    return [_row_to_discrepancy(r) for r in rows]


# ============================================================================
# Canonical queries (spec §5.1)
# ============================================================================


def list_unresolved_material_for_active_trades(
    conn: sqlite3.Connection,
) -> list[ReconciliationDiscrepancy]:
    """Return unresolved material discrepancies attributed to active trades.

    Spec §5.1 CANONICAL #1: "Active-trade reconciliation alerts" — trade
    states 'entered' / 'managing' / 'partial_exited'. position_qty_mismatch
    + stop_mismatch are MOST URGENT on live positions (broker/journal
    divergence; operator may be flying blind).

    Returns rows ordered by discrepancy.created_at DESC, discrepancy_id DESC
    (newest first; deterministic tiebreak via PK monotonicity).
    """
    rows = conn.execute(
        f"SELECT {_DISCREPANCY_SELECT_COLUMNS_D_ALIAS} "
        "FROM reconciliation_discrepancies d "
        "JOIN trades t ON d.trade_id = t.id "
        "WHERE d.material_to_review = 1 "
        "  AND d.resolution = 'unresolved' "
        "  AND t.state IN ('entered', 'managing', 'partial_exited') "
        "ORDER BY d.created_at DESC, d.discrepancy_id DESC"
    ).fetchall()
    return [_row_to_discrepancy(r) for r in rows]


def list_unresolved_material_for_closed_trades(
    conn: sqlite3.Connection,
) -> list[ReconciliationDiscrepancy]:
    """Return unresolved material discrepancies on closed/reviewed trades.

    Spec §5.1 CANONICAL #2: "Closed/reviewed-trade re-review attention" —
    trade states 'closed' / 'reviewed'. Lower urgency than CANONICAL #1;
    operator dispositions at next reconciliation review cadence.

    Returns rows ordered by discrepancy.created_at DESC, discrepancy_id DESC.
    """
    rows = conn.execute(
        f"SELECT {_DISCREPANCY_SELECT_COLUMNS_D_ALIAS} "
        "FROM reconciliation_discrepancies d "
        "JOIN trades t ON d.trade_id = t.id "
        "WHERE d.material_to_review = 1 "
        "  AND d.resolution = 'unresolved' "
        "  AND t.state IN ('closed', 'reviewed') "
        "ORDER BY d.created_at DESC, d.discrepancy_id DESC"
    ).fetchall()
    return [_row_to_discrepancy(r) for r in rows]
