from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    MigrationBackupRequiredException,
    _current_version,
    _entry_intent_backup_gate,
    run_migrations,
)
from swing.data.models import ENTRY_INTENTS, Trade
from swing.data.repos.trades import (
    _row_to_trade,
    _trade_select_cols,
    insert_trade_with_event,
    update_entry_intent,
    update_trade_review_fields,
)


def _migrate(tmp_path: Path, version: int, backup_dir: Path | None = None):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=version, backup_dir=backup_dir or tmp_path)
    return conn


def _make_trade(**over) -> Trade:
    base = dict(
        id=None, ticker="AAA", entry_date="2026-05-01", entry_price=10.0,
        initial_shares=10, initial_stop=9.0, current_stop=9.0, state="entered",
        watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
        trade_origin="manual_off_pipeline", pre_trade_locked_at="2026-05-01T00:00:00",
        current_size=10.0,
    )
    base.update(over)
    return Trade(**base)


def test_expected_schema_version_is_27():
    assert EXPECTED_SCHEMA_VERSION == 29


def test_entry_intents_constant():
    assert ENTRY_INTENTS == frozenset({"standard", "hypothesis_test_by_design"})


def test_migrate_to_27_adds_nullable_checked_column(tmp_path):
    conn = _migrate(tmp_path, 27)
    assert _current_version(conn) == 27
    cols = {r[1] for r in conn.execute("PRAGMA table_info(trades)").fetchall()}
    assert "entry_intent" in cols
    # CHECK accepts NULL + the two enum members; rejects anything else.
    conn.execute("INSERT INTO trades (ticker, entry_date, entry_price, "
                 "initial_shares, initial_stop, current_stop, state, "
                 "trade_origin, pre_trade_locked_at, current_size, entry_intent) "
                 "VALUES ('A','2026-05-01',10,1,9,9,'entered',"
                 "'manual_off_pipeline','2026-05-01T00:00:00',1,'standard')")
    # NULL is accepted by the CHECK (the unclassified third facet).
    conn.execute("INSERT INTO trades (ticker, entry_date, entry_price, "
                 "initial_shares, initial_stop, current_stop, state, "
                 "trade_origin, pre_trade_locked_at, current_size, entry_intent) "
                 "VALUES ('B','2026-05-01',10,1,9,9,'entered',"
                 "'manual_off_pipeline','2026-05-01T00:00:00',1,NULL)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO trades (ticker, entry_date, entry_price, "
                     "initial_shares, initial_stop, current_stop, state, "
                     "trade_origin, pre_trade_locked_at, current_size, entry_intent) "
                     "VALUES ('C','2026-05-01',10,1,9,9,'entered',"
                     "'manual_off_pipeline','2026-05-01T00:00:00',1,'foo')")
    conn.close()


def test_trade_model_rejects_bad_entry_intent():
    with pytest.raises(ValueError, match="entry_intent"):
        _make_trade(entry_intent="foo")
    # valid values + None accepted.
    assert _make_trade(entry_intent="standard").entry_intent == "standard"
    assert _make_trade(entry_intent=None).entry_intent is None


def test_insert_and_read_round_trip_preserves_entry_intent(tmp_path):
    conn = _migrate(tmp_path, 27)
    with conn:
        tid = insert_trade_with_event(
            conn, _make_trade(entry_intent="hypothesis_test_by_design"),
            event_ts="2026-05-01T00:00:00", rationale="t")
    cols = _trade_select_cols(conn)
    row = conn.execute(f"SELECT {cols} FROM trades WHERE id = ?", (tid,)).fetchone()
    assert _row_to_trade(row).entry_intent == "hypothesis_test_by_design"
    conn.close()


def test_pre_v27_projection_yields_null_entry_intent(tmp_path):
    # A v26 DB: the projection must emit `NULL AS entry_intent` (merge-safe pin).
    conn = _migrate(tmp_path, 26)
    cols = _trade_select_cols(conn)
    assert "entry_intent" in cols  # as a NULL alias
    with conn:
        tid = insert_trade_with_event(
            conn, _make_trade(), event_ts="2026-05-01T00:00:00", rationale="t")
    row = conn.execute(f"SELECT {cols} FROM trades WHERE id = ?", (tid,)).fetchone()
    assert _row_to_trade(row).entry_intent is None
    conn.close()


def test_update_entry_intent_writes_only_the_column(tmp_path):
    conn = _migrate(tmp_path, 27)
    with conn:
        tid = insert_trade_with_event(
            conn, _make_trade(), event_ts="2026-05-01T00:00:00", rationale="t")
    # Persist real review fields via the dedicated writer (insert_trade_with_event
    # does NOT write review-grade columns) so the "untouched" assertions below are
    # meaningful -- they prove update_entry_intent does not clobber a reviewed row.
    with conn:
        update_trade_review_fields(
            conn, trade_id=tid, reviewed_at="2026-05-10",
            mistake_tags_json="[]", entry_grade="A", management_grade="A",
            exit_grade="A", process_grade="A",
            disqualifying_process_violation=False,
            realized_R_if_plan_followed=None, mistake_cost_confidence="high",
            lesson_learned="x")
        conn.execute("UPDATE trades SET state='reviewed' WHERE id=?", (tid,))
    with conn:
        update_entry_intent(conn, trade_id=tid, entry_intent="standard")
    row = conn.execute(
        "SELECT entry_intent, state, process_grade, reviewed_at "
        "FROM trades WHERE id = ?", (tid,)).fetchone()
    assert row[0] == "standard"
    assert row[1] == "reviewed"      # state untouched
    assert row[2] == "A"             # review fields untouched
    assert row[3] == "2026-05-10"
    # NULL round-trips (the skip path).
    with conn:
        update_entry_intent(conn, trade_id=tid, entry_intent=None)
    assert conn.execute("SELECT entry_intent FROM trades WHERE id=?",
                        (tid,)).fetchone()[0] is None
    conn.close()


def test_update_entry_intent_rejects_bad_value(tmp_path):
    conn = _migrate(tmp_path, 27)
    with conn:
        tid = insert_trade_with_event(
            conn, _make_trade(), event_ts="2026-05-01T00:00:00", rationale="t")
    with pytest.raises(ValueError, match="entry_intent"):
        with conn:
            update_entry_intent(conn, trade_id=tid, entry_intent="foo")
    conn.close()


def test_update_entry_intent_missing_trade_raises(tmp_path):
    conn = _migrate(tmp_path, 27)
    with pytest.raises(ValueError, match="not found"):
        with conn:
            update_entry_intent(conn, trade_id=9999, entry_intent="standard")
    conn.close()


def test_backup_gate_fires_strict_on_v26(tmp_path):
    conn = sqlite3.connect(":memory:")
    inert = tmp_path / "inert"; fire = tmp_path / "fire"; naive = tmp_path / "naive"
    # current==27 -> already past, inert.
    _entry_intent_backup_gate(conn, current_version=27, target_version=27, backup_dir=inert)
    # current==25, target==27 -> multi-version jump bypasses the v26-strict gate.
    _entry_intent_backup_gate(conn, current_version=25, target_version=27, backup_dir=naive)
    assert not inert.exists() and not naive.exists()
    # current==26, target>=27 -> fires; in-memory source -> raises.
    with pytest.raises(MigrationBackupRequiredException):
        _entry_intent_backup_gate(conn, current_version=26, target_version=27, backup_dir=fire)


def test_run_migrations_wires_entry_intent_gate(tmp_path):
    backups = tmp_path / "v26_backups"; backups.mkdir()
    conn = _migrate(tmp_path, 26); conn.close()
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=27, backup_dir=backups)
    assert _current_version(conn) == 27
    snaps = list(backups.glob("swing-pre-entry-intent-migration-*.db"))
    assert len(snaps) == 1
    conn.close()


def test_migrate_twice_is_noop(tmp_path):
    conn = _migrate(tmp_path, 27)
    run_migrations(conn, target_version=27)  # current >= target -> early return
    assert _current_version(conn) == 27
    cols = [r[1] for r in conn.execute("PRAGMA table_info(trades)").fetchall()]
    assert cols.count("entry_intent") == 1  # not double-added
    conn.close()
