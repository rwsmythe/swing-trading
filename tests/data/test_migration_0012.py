"""Migration 0012 — sector + industry columns on candidates + trades.

Incremental v11→v12 pattern: applies migrations 0001-0011 from disk to
bring an empty conn to schema_version=11, then applies ONLY 0012 to
exercise the transition. Mirrors test_migration_0011.py's _migrate_to_v10.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from swing.data.db import EXPECTED_SCHEMA_VERSION


def _migrate_to_v11(conn: sqlite3.Connection) -> None:
    """Apply migrations 0001-0011 sequentially from disk."""
    from swing.data import migrations
    migs_dir = Path(migrations.__file__).parent
    for n in range(1, 12):
        sql_files = sorted(migs_dir.glob(f"{n:04d}_*.sql"))
        assert len(sql_files) == 1, f"expected exactly one migration {n:04d}, got {sql_files}"
        conn.executescript(sql_files[0].read_text(encoding="utf-8"))
    conn.commit()


def _apply_migration_0012(conn: sqlite3.Connection) -> None:
    """Apply ONLY migration 0012 (the v11 → v12 transition under test)."""
    from swing.data import migrations
    migs_dir = Path(migrations.__file__).parent
    sql_files = sorted(migs_dir.glob("0012_*.sql"))
    assert len(sql_files) == 1, f"expected one 0012 migration, got {sql_files}"
    conn.executescript(sql_files[0].read_text(encoding="utf-8"))
    conn.commit()


def test_expected_schema_version_is_19():
    """Code-side constant matches the current HEAD migration's UPDATE schema_version."""
    assert EXPECTED_SCHEMA_VERSION == 29


def test_migration_0012_advances_schema_version_from_11_to_12(tmp_path: Path):
    """The standalone 0012 SQL transitions a v11 database to v12."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        _migrate_to_v11(conn)
        v_before = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert v_before == 11

        _apply_migration_0012(conn)
        v_after = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert v_after == 12
    finally:
        conn.close()


def test_migration_0012_adds_sector_industry_to_candidates_and_trades(tmp_path: Path):
    """Migration 0012 adds NOT NULL DEFAULT '' sector + industry columns to
    BOTH candidates and trades. Default values apply on INSERTs that omit
    the columns, preserving backfill behavior on historical rows."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        _migrate_to_v11(conn)
        _apply_migration_0012(conn)

        # Both tables have the new columns with the right shape.
        for table in ("candidates", "trades"):
            cols = {
                row[1]: row for row in conn.execute(f"PRAGMA table_info({table})")
            }
            assert "sector" in cols, f"{table}.sector missing"
            assert "industry" in cols, f"{table}.industry missing"
            # PRAGMA table_info row: (cid, name, type, notnull, dflt_value, pk)
            assert cols["sector"][2].upper() == "TEXT"
            assert cols["industry"][2].upper() == "TEXT"
            assert cols["sector"][3] == 1, f"{table}.sector must be NOT NULL"
            assert cols["industry"][3] == 1, f"{table}.industry must be NOT NULL"
            # SQLite renders TEXT default as "''".
            assert cols["sector"][4] == "''", f"{table}.sector default must be ''"
            assert cols["industry"][4] == "''", f"{table}.industry default must be ''"

        # Functional check: INSERT omitting sector/industry must succeed and
        # persist empty strings (not NULL — NOT NULL violation would surface here).
        conn.execute(
            """INSERT INTO evaluation_runs
               (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                tickers_evaluated, aplus_count, watch_count, skip_count,
                excluded_count, error_count)
               VALUES ('2026-04-28T00:00:00','2026-04-25','2026-04-28',
                       NULL,0,0,0,0,0,0)"""
        )
        eval_run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """INSERT INTO candidates
               (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                adr_pct, tight_streak, pullback_pct, prior_trend_pct, rs_rank,
                rs_return_12w_vs_spy, rs_method, pattern_tag, notes)
               VALUES (?, 'TEST', 'watch', 100.0, 105.0, 95.0,
                       2.0, 5, NULL, NULL, NULL, NULL, 'fallback_spy',
                       NULL, NULL)""",
            (eval_run_id,),
        )
        row = conn.execute(
            "SELECT sector, industry FROM candidates WHERE ticker='TEST'"
        ).fetchone()
        assert row == ("", "")

        conn.execute(
            """INSERT INTO trades
               (ticker, entry_date, entry_price, initial_shares, initial_stop,
                current_stop, status)
               VALUES ('TEST','2026-04-28',100.0,10,95.0,95.0,'open')"""
        )
        row = conn.execute(
            "SELECT sector, industry FROM trades WHERE ticker='TEST'"
        ).fetchone()
        assert row == ("", "")
    finally:
        conn.close()
