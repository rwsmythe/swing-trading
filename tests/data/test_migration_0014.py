"""Phase 7 migration 0014 smoke test.

Smoke-only at T2; full preservation invariant tests land in T9; in-flight
VIR/DHC/CC/YOU migration tests land in T10.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


def _seed_v13_db(path: Path) -> sqlite3.Connection:
    """Build a schema-version-13 DB. Uses the public run_migrations API."""
    from swing.data.db import run_migrations
    conn = sqlite3.connect(path)
    run_migrations(conn, target_version=13)
    return conn


def test_migration_0014_smoke(tmp_path):
    """0014 applies cleanly to an empty (no trades) v13 DB; schema_version → 14."""
    from swing.data.db import run_migrations

    db = tmp_path / "test.db"
    conn = _seed_v13_db(db)
    run_migrations(conn, target_version=14, backup_dir=tmp_path)

    # schema_version bumped.
    cur = conn.execute("SELECT version FROM schema_version")
    assert cur.fetchone()[0] == 14

    # New table fills exists.
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fills'"
    ).fetchall()
    assert len(rows) == 1, "fills table should exist post-0014"

    # Old table exits is dropped.
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='exits'"
    ).fetchall()
    assert len(rows) == 0, "exits table should be dropped post-0014"

    # status column dropped from trades; state + new cols added.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(trades)")}
    assert "status" not in cols, "status column should be dropped"
    assert "state" in cols
    assert "trade_origin" in cols
    assert "pre_trade_locked_at" in cols
    assert "current_size" in cols
    assert "current_avg_cost" in cols
    assert "last_fill_at" in cols
    # Sample of pre-trade decision fields:
    for f in ("thesis", "why_now", "invalidation_condition",
              "expected_scenario", "premortem_technical",
              "emotional_state_pre_trade", "catalyst"):
        assert f in cols, f"missing pre-trade field: {f}"

    # state CHECK enum enforced.
    with sqlite3.connect(db) as bad_conn:
        # Insert a trade with an invalid state — expect CHECK violation.
        try:
            bad_conn.execute(
                "INSERT INTO trades (ticker, entry_date, entry_price, "
                "initial_shares, initial_stop, current_stop, state, "
                "trade_origin, pre_trade_locked_at) "
                "VALUES ('AAA','2026-01-01',10.0,1,9.0,9.0,'bogus',"
                "'manual_off_pipeline','2026-01-01T16:00:00')"
            )
            bad_conn.commit()
            raise AssertionError("expected CHECK violation on state='bogus'")
        except sqlite3.IntegrityError:
            pass

    # trade_origin CHECK enum enforced.
    with sqlite3.connect(db) as bad_conn:
        try:
            bad_conn.execute(
                "INSERT INTO trades (ticker, entry_date, entry_price, "
                "initial_shares, initial_stop, current_stop, state, "
                "trade_origin, pre_trade_locked_at) "
                "VALUES ('BBB','2026-01-01',10.0,1,9.0,9.0,'entered',"
                "'bogus_origin','2026-01-01T16:00:00')"
            )
            bad_conn.commit()
            raise AssertionError("expected CHECK violation on trade_origin='bogus_origin'")
        except sqlite3.IntegrityError:
            pass

    # New event_type 'pre_trade_edit' is allowed in trade_events CHECK.
    with sqlite3.connect(db) as ev_conn:
        # Need a trade row first to satisfy FK.
        ev_conn.execute(
            "INSERT INTO trades (id, ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, "
            "trade_origin, pre_trade_locked_at) "
            "VALUES (1,'CCC','2026-01-01',10.0,1,9.0,9.0,'entered',"
            "'manual_off_pipeline','2026-01-01T16:00:00')"
        )
        ev_conn.execute(
            "INSERT INTO trade_events (trade_id, ts, event_type, payload_json) "
            "VALUES (1, '2026-01-01T17:00:00', 'pre_trade_edit', '{}')"
        )
        ev_conn.commit()
        # Verify it landed.
        row = ev_conn.execute(
            "SELECT event_type FROM trade_events WHERE trade_id = 1"
        ).fetchone()
        assert row[0] == "pre_trade_edit"


def test_migration_0014_idempotent(tmp_path):
    """Running run_migrations against an already-v14 DB is a no-op (returns
    without re-applying)."""
    from swing.data.db import run_migrations

    db = tmp_path / "test.db"
    conn = _seed_v13_db(db)
    run_migrations(conn, target_version=14, backup_dir=tmp_path)
    # Second invocation should not re-apply (no error; schema_version still 14).
    run_migrations(conn, target_version=14, backup_dir=tmp_path)
    cur = conn.execute("SELECT version FROM schema_version")
    assert cur.fetchone()[0] == 14
