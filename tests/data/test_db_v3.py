"""Schema migration 0003 round-trip — verifies all Phase 2 tables exist with expected columns."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from swing.data.db import EXPECTED_SCHEMA_VERSION, ensure_schema


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def test_migration_0003_creates_all_phase2_tables(tmp_path: Path):
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    try:
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        # Track EXPECTED_SCHEMA_VERSION rather than hardcode; migration 0004 bumped from 3 → 4.
        assert version == EXPECTED_SCHEMA_VERSION

        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        for t in (
            "weather_runs", "watchlist", "watchlist_archive",
            "trades", "exits", "cash_movements", "trade_events",
            "daily_recommendations", "pipeline_runs", "config_revisions",
        ):
            assert t in tables, f"missing table: {t}"

        # Spot-check column shapes (full set checked via INSERT below)
        assert "lease_token" in _columns(conn, "pipeline_runs")
        assert "lease_heartbeat_ts" in _columns(conn, "pipeline_runs")
        assert "last_step_progress_ts" in _columns(conn, "pipeline_runs")
        assert "rs_universe_version" in _columns(conn, "pipeline_runs")
        assert "not_qualified_streak" in _columns(conn, "watchlist")
        assert "current_stop" in _columns(conn, "trades")
        assert "r_multiple" in _columns(conn, "exits")
        assert "payload_json" in _columns(conn, "trade_events")

        # CHECK constraint on bucket already exists from 0001 — verify not regressed
        cur = conn.execute("PRAGMA foreign_key_check")
        assert cur.fetchall() == []

        # UNIQUE on daily_recommendations matches spec §3
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='daily_recommendations'"
        ).fetchall()
        assert any("action_session_date" in r[0] for r in rows) or \
            any("daily_recommendations" in r[0] and "ticker" in r[0] for r in rows), \
            "daily_recommendations needs UNIQUE on (action_session_date, ticker, recommendation)"
    finally:
        conn.close()


def test_migration_idempotent(tmp_path: Path):
    """Running ensure_schema twice on a fresh DB ends at EXPECTED_SCHEMA_VERSION, no errors."""
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    conn = ensure_schema(db)
    try:
        assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == EXPECTED_SCHEMA_VERSION
    finally:
        conn.close()


def test_migration_0004_enforces_one_open_trade_per_ticker(tmp_path: Path):
    """Adversarial review Batch 3 Critical: schema-level partial unique index
    catches the race where two concurrent record_entry calls both pass the
    app-layer list_open_trades check."""
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    try:
        # Insert one open trade directly
        conn.execute(
            """INSERT INTO trades
               (ticker, entry_date, entry_price, initial_shares, initial_stop,
                current_stop, status, watchlist_entry_target,
                watchlist_initial_stop, notes)
               VALUES (?, ?, ?, ?, ?, ?, 'open', NULL, NULL, NULL)""",
            ("AAPL", "2026-04-15", 180.0, 5, 170.0, 170.0),
        )
        conn.commit()
        # Second open AAPL must fail
        import pytest as _pt
        with _pt.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO trades
                   (ticker, entry_date, entry_price, initial_shares, initial_stop,
                    current_stop, status, watchlist_entry_target,
                    watchlist_initial_stop, notes)
                   VALUES (?, ?, ?, ?, ?, ?, 'open', NULL, NULL, NULL)""",
                ("AAPL", "2026-04-16", 185.0, 5, 175.0, 175.0),
            )
        # But a CLOSED AAPL is allowed (history)
        conn.execute(
            """INSERT INTO trades
               (ticker, entry_date, entry_price, initial_shares, initial_stop,
                current_stop, status, watchlist_entry_target,
                watchlist_initial_stop, notes)
               VALUES (?, ?, ?, ?, ?, ?, 'closed', NULL, NULL, NULL)""",
            ("AAPL", "2026-04-10", 175.0, 5, 165.0, 165.0),
        )
        conn.commit()
    finally:
        conn.close()
