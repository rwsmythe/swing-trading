"""Migration 0013 round-trip + column presence + CHECK enforcement + unique-index."""
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import Trade
from swing.data.repos.trades import (
    get_trade,
    insert_trade_with_event,
    update_trade_review_fields,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase6.db"
    conn = ensure_schema(db_path)
    yield conn
    conn.close()


def test_migration_0013_advances_schema_version(conn: sqlite3.Connection) -> None:
    # ensure_schema walks to HEAD; migration 0019 advanced schema_version to 19.
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    assert version == 19


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


# Phase 7 Sub-A migration 0014 rebuilt the trades table and DROPPED the
# entry/management/exit/process grade CHECK constraints (the new table at
# migrations/0014... has these columns as plain TEXT). The 0013-era CHECK
# is no longer present, so the test that asserted invalid grades raise
# IntegrityError was deleted in C.13. If grade validation is desired in the
# future it should be added at the application layer (review_log repo) since
# the data layer no longer enforces it.


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


def test_trade_dataclass_has_ten_review_fields_with_none_default() -> None:
    t = Trade(
        id=None, ticker="TEST", entry_date="2026-04-01", entry_price=10.0,
        initial_shares=10, initial_stop=9.0, current_stop=9.0,         state="closed",
        watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
    )
    # All 10 review fields default to None:
    assert t.reviewed_at is None
    assert t.mistake_tags is None
    assert t.entry_grade is None
    assert t.management_grade is None
    assert t.exit_grade is None
    assert t.process_grade is None
    assert t.disqualifying_process_violation is None
    assert t.realized_R_if_plan_followed is None
    assert t.mistake_cost_confidence is None
    assert t.lesson_learned is None


def test_update_trade_review_fields_raises_on_unknown_id(conn: sqlite3.Connection) -> None:
    """Silent no-op on missing trade_id is data loss; must raise."""
    with pytest.raises(ValueError, match="trade 99999 not found"), conn:
        update_trade_review_fields(
            conn, trade_id=99999,
            reviewed_at="2026-05-02T10:00:00",
            mistake_tags_json='["CHASED"]',
            entry_grade="C", management_grade="B", exit_grade="B",
            process_grade="C", disqualifying_process_violation=False,
            realized_R_if_plan_followed=2.0,
            mistake_cost_confidence="medium",
            lesson_learned="x",
        )


@pytest.mark.parametrize(
    ("disqualifying_process_violation", "expected_stored"),
    [(False, False), (True, True), (None, None)],
)
def test_update_trade_review_fields_round_trip(
    conn: sqlite3.Connection,
    disqualifying_process_violation: bool | None,
    expected_stored: bool | None,
) -> None:
    with conn:
        trade_id = insert_trade_with_event(
            conn,
            Trade(
                id=None, ticker="VIR", entry_date="2026-04-01", entry_price=10.0,
                initial_shares=10, initial_stop=9.0, current_stop=9.0,                 state="closed",
                watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
            ),
            event_ts="2026-04-01T09:30:00",
        )
    with conn:
        update_trade_review_fields(
            conn, trade_id=trade_id,
            reviewed_at="2026-05-02T10:00:00",
            mistake_tags_json='["CHASED"]',
            entry_grade="C", management_grade="B", exit_grade="B",
            process_grade="C",
            disqualifying_process_violation=disqualifying_process_violation,
            realized_R_if_plan_followed=2.0,
            mistake_cost_confidence="medium",
            lesson_learned="Wait for the breakout, not the build-up.",
        )
    t = get_trade(conn, trade_id)
    assert t is not None
    assert t.reviewed_at == "2026-05-02T10:00:00"
    assert t.mistake_tags == '["CHASED"]'
    assert t.entry_grade == "C"
    assert t.management_grade == "B"
    assert t.exit_grade == "B"
    assert t.process_grade == "C"
    assert t.disqualifying_process_violation is expected_stored
    assert t.realized_R_if_plan_followed == 2.0
    assert t.mistake_cost_confidence == "medium"
    assert t.lesson_learned == "Wait for the breakout, not the build-up."
