"""Migration 0016 round-trip + 42-column presence + indexes + CHECK + FK behavior.

Phase 8 Task 1.0 (per docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md
§Task 1.0). Discriminating regression tests for:
  - schema_version → 16
  - daily_management_records table created with all 42 columns (spec §3.1)
  - trades.planned_target_R column exists
  - record_type CHECK rejects values outside {'daily_snapshot','event_log'}
  - active-snapshot partial-unique-index predicate (§A.6)
  - superseded rows excluded from active-snapshot uniqueness predicate
  - pipeline_run_id FK has ON DELETE SET NULL (spec §4.3 + §A.4)
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from swing.data.db import ensure_schema


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    db_path = tmp_path / "phase8.db"
    conn = ensure_schema(db_path)
    conn.execute("PRAGMA foreign_keys=ON")  # mirror production runtime
    try:
        yield conn
    finally:
        conn.close()


def test_migration_0016_advances_schema_version(conn: sqlite3.Connection) -> None:
    # ensure_schema walks to HEAD; migration 0023 advanced schema_version to 23.
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    assert version == 29


def test_migration_0016_creates_daily_management_records_table(
    conn: sqlite3.Connection,
) -> None:
    cols = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(daily_management_records)"
        ).fetchall()
    }
    expected = {
        "management_record_id",
        "trade_id",
        "record_type",
        "review_date",
        "data_asof_session",
        "created_at",
        "mfe_mae_precision_level",
        "pipeline_run_id",
        "is_superseded",
        "superseded_by_record_id",
        "current_price",
        "current_stop",
        "current_size",
        "current_avg_cost",
        "open_R_effective",
        "open_MFE_R_to_date",
        "open_MAE_R_to_date",
        "intraday_high",
        "intraday_low",
        "position_capital_utilization_pct",
        "position_capital_denominator_dollars",
        "position_portfolio_heat_contribution_dollars",
        "maturity_stage",
        "trail_MA_candidate_price",
        "trail_MA_period_days",
        "trail_MA_eligibility_flag",
        "thesis_status",
        "prior_stop",
        "new_stop",
        "linked_trade_event_id",
        "stop_changed",
        "stop_change_reason",
        "volume_behavior",
        "relative_strength_status",
        "market_regime_change",
        "sector_condition_change",
        "news_or_event_update",
        "action_taken",
        "action_reason",
        "emotional_state",
        "rule_violation_suspected",
        "management_notes",
    }
    assert expected == cols
    assert len(expected) == 42  # spec §3.1 binding count


def test_migration_0016_adds_planned_target_R_to_trades(
    conn: sqlite3.Connection,
) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(trades)").fetchall()}
    assert "planned_target_R" in cols


def test_migration_0016_record_type_check_rejects_invalid(
    conn: sqlite3.Connection,
) -> None:
    _seed_minimal_trade(conn, trade_id=1)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint"):
        conn.execute(
            "INSERT INTO daily_management_records "
            "(trade_id, record_type, review_date, data_asof_session, created_at, "
            " mfe_mae_precision_level) "
            "VALUES (1, 'INVALID', '2026-05-07', '2026-05-07', '2026-05-07T00:00:00', "
            " 'daily_approximate')"
        )


def test_migration_0016_active_snapshot_unique_index_predicate(
    conn: sqlite3.Connection,
) -> None:
    """Two non-superseded snapshot rows for same (trade, session) → IntegrityError."""
    _seed_minimal_trade(conn, trade_id=1)
    conn.execute(
        "INSERT INTO daily_management_records "
        "(trade_id, record_type, review_date, data_asof_session, created_at, "
        " mfe_mae_precision_level, is_superseded) "
        "VALUES (1, 'daily_snapshot', '2026-05-07', '2026-05-07', "
        "        '2026-05-07T00:00:00', 'daily_approximate', 0)"
    )
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        conn.execute(
            "INSERT INTO daily_management_records "
            "(trade_id, record_type, review_date, data_asof_session, created_at, "
            " mfe_mae_precision_level, is_superseded) "
            "VALUES (1, 'daily_snapshot', '2026-05-07', '2026-05-07', "
            "        '2026-05-07T00:00:00', 'intraday_estimated', 0)"
        )


def test_migration_0016_superseded_row_does_not_block_active(
    conn: sqlite3.Connection,
) -> None:
    """Predicate excludes superseded rows from the active-snapshot uniqueness constraint."""
    _seed_minimal_trade(conn, trade_id=1)
    conn.execute(
        "INSERT INTO daily_management_records "
        "(trade_id, record_type, review_date, data_asof_session, created_at, "
        " mfe_mae_precision_level, is_superseded) "
        "VALUES (1, 'daily_snapshot', '2026-05-07', '2026-05-07', "
        "        '2026-05-07T00:00:00', 'daily_approximate', 1)"
    )
    # Should succeed: predicate excludes the superseded row.
    conn.execute(
        "INSERT INTO daily_management_records "
        "(trade_id, record_type, review_date, data_asof_session, created_at, "
        " mfe_mae_precision_level, is_superseded) "
        "VALUES (1, 'daily_snapshot', '2026-05-07', '2026-05-07', "
        "        '2026-05-07T00:00:00', 'intraday_estimated', 0)"
    )


def test_migration_0016_pipeline_run_id_set_null_on_delete(
    conn: sqlite3.Connection,
) -> None:
    """pipeline_run_id FK has ON DELETE SET NULL per spec §4.3 + §A.4."""
    _seed_minimal_trade(conn, trade_id=1)
    _seed_pipeline_run(conn, run_id=99)
    conn.execute(
        "INSERT INTO daily_management_records "
        "(trade_id, record_type, review_date, data_asof_session, created_at, "
        " mfe_mae_precision_level, pipeline_run_id) "
        "VALUES (1, 'daily_snapshot', '2026-05-07', '2026-05-07', "
        "        '2026-05-07T00:00:00', 'daily_approximate', 99)"
    )
    conn.execute("DELETE FROM pipeline_runs WHERE id = 99")
    row = conn.execute(
        "SELECT pipeline_run_id FROM daily_management_records LIMIT 1"
    ).fetchone()
    assert row[0] is None  # SET NULL fired


def _seed_minimal_trade(conn: sqlite3.Connection, *, trade_id: int) -> None:
    """Insert a minimal trade row sufficient to satisfy NOT NULL + CHECK constraints.

    Mirrors Phase 7 trades schema as of HEAD 1441109 (migration 0014 table-rebuild).
    """
    conn.execute(
        "INSERT INTO trades "
        "(id, ticker, entry_date, entry_price, initial_shares, initial_stop, "
        " current_stop, state, trade_origin, pre_trade_locked_at, current_size) "
        "VALUES (?, 'TST', '2026-05-01', 100.0, 10, 90.0, 90.0, "
        "        'managing', 'manual_off_pipeline', '2026-05-01T16:00:00', 10.0)",
        (trade_id,),
    )


def _seed_pipeline_run(conn: sqlite3.Connection, *, run_id: int) -> None:
    """Insert minimal pipeline_runs row matching schema at migration 0003+."""
    conn.execute(
        "INSERT INTO pipeline_runs "
        "(id, started_ts, trigger, data_asof_date, action_session_date, "
        " state, lease_token) "
        "VALUES (?, '2026-05-07T00:00:00', 'manual', '2026-05-06', '2026-05-07', "
        "        'complete', 'test-token')",
        (run_id,),
    )
