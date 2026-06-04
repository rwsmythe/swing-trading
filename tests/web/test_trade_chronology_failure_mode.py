import sqlite3
from pathlib import Path  # noqa: F401  # retained for parity with sibling tests

from swing.data.db import run_migrations
from swing.web.view_models.trade_chronology import _review_entry


def _seed_reviewed(conn, *, failure_mode_sql: str, fm_value):
    conn.execute(
        "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares, "
        "initial_stop, current_stop, state, trade_origin, pre_trade_locked_at, "
        f"current_size, reviewed_at, process_grade, lesson_learned, mistake_tags"
        f"{failure_mode_sql}) VALUES ('CH','2026-05-01',10.0,1,9.0,9.0,'reviewed',"
        "'manual_off_pipeline','2026-05-01T09:30:00',1.0,'2026-05-05T16:00:00',"
        f"'A','learned','[]'{', ?' if fm_value is not None else ''})",
        ((fm_value,) if fm_value is not None else ()))
    return conn.execute("SELECT id FROM trades WHERE ticker='CH'").fetchone()[0]


def test_v24_reviewed_trade_shows_failure_mode_label(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "swing.db"))
    run_migrations(conn, target_version=24, backup_dir=tmp_path)
    tid = _seed_reviewed(conn, failure_mode_sql=", failure_mode",
                         fm_value="execution_error")
    entries = _review_entry(conn, tid)
    assert entries and "Execution error" in (entries[0].detail or "")


def test_pre_v24_chronology_renders_without_no_such_column(tmp_path):
    # PRE-FIX: a literal "SELECT ... failure_mode" raises OperationalError on a
    # pre-v24 DB. POST-FIX: PRAGMA fallback selects NULL AS failure_mode -> renders.
    conn = sqlite3.connect(str(tmp_path / "swing.db"))
    run_migrations(conn, target_version=16, backup_dir=tmp_path)
    tid = _seed_reviewed(conn, failure_mode_sql="", fm_value=None)
    entries = _review_entry(conn, tid)  # must NOT raise
    assert entries  # the review entry still renders
