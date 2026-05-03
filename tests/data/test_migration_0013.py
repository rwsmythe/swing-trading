"""Migration 0013 round-trip + column presence + CHECK enforcement + unique-index."""
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase6.db"
    conn = ensure_schema(db_path)
    yield conn
    conn.close()


def test_migration_0013_advances_schema_version(conn: sqlite3.Connection) -> None:
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    assert version == 13


def test_migration_0013_adds_ten_trade_columns(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(trades)").fetchall()}
    expected_new = {
        "reviewed_at", "mistake_tags",
        "entry_grade", "management_grade", "exit_grade", "process_grade",
        "disqualifying_process_violation",
        "realized_R_if_plan_followed",
        "mistake_cost_confidence", "lesson_learned",
    }
    assert expected_new.issubset(cols)


def test_migration_0013_creates_review_log_table(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(review_log)").fetchall()}
    expected = {
        "review_id", "review_type", "period_start", "period_end",
        "scheduled_date", "completed_date", "skipped",
        "duration_minutes", "n_trades_reviewed",
        "total_mistake_cost_R", "total_lucky_violation_R",
        "primary_lesson", "next_period_focus", "created_at",
        "net_R_effective", "expectancy_R_effective", "win_rate",
        "avg_win_R", "avg_loss_R", "profit_factor", "max_drawdown_R",
    }
    assert expected.issubset(cols)


def test_migration_0013_grade_check_constraint_rejects_invalid(conn: sqlite3.Connection) -> None:
    # Insert a minimal trade row first to satisfy NOT NULLs:
    conn.execute(
        """INSERT INTO trades
           (ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, status)
           VALUES ('TEST', '2026-01-01', 10.0, 1, 9.0, 9.0, 'closed')"""
    )
    trade_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute(
            "UPDATE trades SET entry_grade='Z' WHERE id=?", (trade_id,),
        )


def test_migration_0013_review_type_check_rejects_invalid(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute(
            """INSERT INTO review_log
               (review_type, period_start, period_end, scheduled_date)
               VALUES ('yearly', '2026-01-01', '2026-12-31', '2027-01-01')"""
        )


def test_migration_0013_unique_index_blocks_duplicate_cadence(conn: sqlite3.Connection) -> None:
    conn.execute(
        """INSERT INTO review_log
           (review_type, period_start, period_end, scheduled_date)
           VALUES ('daily', '2026-04-30', '2026-04-30', '2026-05-01')"""
    )
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        conn.execute(
            """INSERT INTO review_log
               (review_type, period_start, period_end, scheduled_date)
               VALUES ('daily', '2026-04-30', '2026-04-30', '2026-05-01')"""
        )
