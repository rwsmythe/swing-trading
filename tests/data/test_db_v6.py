"""Schema migration 0006 — pipeline_runs.evaluation_run_id FK + pipeline_chart_targets table.

Tranche C pipeline-linkage bundle T1. Verifies the structural linkage that
replaces the heuristic `data_asof_date + run_ts <= finished_ts` query in
chart_scope resolver, and the per-run chart-target persistence that
distinguishes `fetcher_failed` from `too_few_bars` (T5).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import EXPECTED_SCHEMA_VERSION, ensure_schema


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,),
    ).fetchone()
    return row is not None


def test_migration_0006_adds_evaluation_run_id_column(tmp_path: Path):
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    try:
        cols = _columns(conn, "pipeline_runs")
        assert "evaluation_run_id" in cols
        # Should be nullable for legacy backfill.
        info = {
            r[1]: (r[2], r[3])  # name -> (type, notnull)
            for r in conn.execute("PRAGMA table_info(pipeline_runs)").fetchall()
        }
        assert info["evaluation_run_id"][1] == 0, "evaluation_run_id must be nullable"
    finally:
        conn.close()


def test_migration_0006_creates_pipeline_chart_targets_table(tmp_path: Path):
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    try:
        assert _table_exists(conn, "pipeline_chart_targets")
        cols = _columns(conn, "pipeline_chart_targets")
        for c in ("id", "pipeline_run_id", "ticker", "source", "chart_status"):
            assert c in cols, f"missing column: {c}"
    finally:
        conn.close()


def test_migration_0006_bumps_schema_version(tmp_path: Path):
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    try:
        v = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert v == EXPECTED_SCHEMA_VERSION
        assert v >= 6, f"EXPECTED_SCHEMA_VERSION must be at least 6 after 0006, got {v}"
    finally:
        conn.close()


def _insert_minimal_pipeline_run(conn: sqlite3.Connection, **overrides) -> int:
    base = dict(
        started_ts="2026-04-17T21:00:00",
        finished_ts="2026-04-17T21:55:00",
        trigger="manual",
        data_asof_date="2026-04-17",
        action_session_date="2026-04-17",
        state="complete",
        lease_token="t-x",
    )
    base.update(overrides)
    cols = ", ".join(base.keys())
    placeholders = ", ".join("?" for _ in base)
    cur = conn.execute(
        f"INSERT INTO pipeline_runs ({cols}) VALUES ({placeholders})",
        tuple(base.values()),
    )
    return int(cur.lastrowid)


def _insert_minimal_eval_run(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        """INSERT INTO evaluation_runs
           (run_ts, data_asof_date, action_session_date, finviz_csv_path,
            tickers_evaluated, aplus_count, watch_count, skip_count,
            excluded_count, error_count, rs_universe_version, rs_universe_hash)
           VALUES ('2026-04-17T21:30:00', '2026-04-17', '2026-04-17', NULL,
                   0, 0, 0, 0, 0, 0, 'v1', 'deadbeef')""",
    )
    return int(cur.lastrowid)


def test_migration_0006_pipeline_run_with_null_evaluation_run_id_allowed(tmp_path: Path):
    """Legacy rows must still insert (no NOT NULL on evaluation_run_id)."""
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    try:
        run_id = _insert_minimal_pipeline_run(conn)
        conn.commit()
        row = conn.execute(
            "SELECT evaluation_run_id FROM pipeline_runs WHERE id=?", (run_id,),
        ).fetchone()
        assert row[0] is None
    finally:
        conn.close()


def test_migration_0006_pipeline_run_with_evaluation_run_id_works(tmp_path: Path):
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    try:
        eval_id = _insert_minimal_eval_run(conn)
        run_id = _insert_minimal_pipeline_run(conn, evaluation_run_id=eval_id)
        conn.commit()
        row = conn.execute(
            "SELECT evaluation_run_id FROM pipeline_runs WHERE id=?", (run_id,),
        ).fetchone()
        assert row[0] == eval_id
    finally:
        conn.close()


def test_migration_0006_pipeline_chart_targets_insert_and_uniqueness(tmp_path: Path):
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    try:
        run_id = _insert_minimal_pipeline_run(conn)
        conn.commit()
        # Valid insert.
        conn.execute(
            """INSERT INTO pipeline_chart_targets
               (pipeline_run_id, ticker, source, chart_status)
               VALUES (?, ?, 'aplus', 'pending')""",
            (run_id, "AAPL"),
        )
        conn.execute(
            """INSERT INTO pipeline_chart_targets
               (pipeline_run_id, ticker, source, chart_status)
               VALUES (?, ?, 'near_proximity', 'ok')""",
            (run_id, "MSFT"),
        )
        conn.commit()

        # Duplicate (run_id, ticker) must fail.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO pipeline_chart_targets
                   (pipeline_run_id, ticker, source, chart_status)
                   VALUES (?, ?, 'aplus', 'fetcher_failed')""",
                (run_id, "AAPL"),
            )
            conn.commit()
    finally:
        conn.close()


def test_migration_0006_pipeline_chart_targets_check_constraints(tmp_path: Path):
    """source must be 'aplus' or 'near_proximity'; chart_status must be one of
    'ok' | 'fetcher_failed' | 'too_few_bars' | 'pending'."""
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    try:
        run_id = _insert_minimal_pipeline_run(conn)
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO pipeline_chart_targets
                   (pipeline_run_id, ticker, source, chart_status)
                   VALUES (?, ?, 'bogus', 'pending')""",
                (run_id, "AAPL"),
            )
            conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO pipeline_chart_targets
                   (pipeline_run_id, ticker, source, chart_status)
                   VALUES (?, ?, 'aplus', 'unknown_status')""",
                (run_id, "MSFT"),
            )
            conn.commit()
    finally:
        conn.close()


def test_migration_0006_idempotent_apply(tmp_path: Path):
    """Running ensure_schema twice on a fresh DB lands at the new EXPECTED."""
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    conn = ensure_schema(db)
    try:
        v = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert v == EXPECTED_SCHEMA_VERSION
    finally:
        conn.close()


def test_migration_0006_applies_on_top_of_v5_with_existing_pipeline_runs(tmp_path: Path):
    """Backfill semantics: existing pipeline_runs rows get evaluation_run_id=NULL
    when 0006 applies on a populated DB."""
    from swing.data.db import _MIGRATIONS_DIR, _apply_migration

    db = tmp_path / "swing.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        # Apply migrations 0001..0005 only.
        for mig in sorted(_MIGRATIONS_DIR.glob("*.sql")):
            try:
                version = int(mig.stem.split("_", 1)[0])
            except ValueError:
                continue
            if version <= 5:
                _apply_migration(conn, mig)
        # Insert a v5-era pipeline_runs row (no evaluation_run_id column yet).
        _insert_minimal_pipeline_run(conn)
        conn.commit()
    finally:
        conn.close()

    # Now upgrade to current.
    conn = ensure_schema(db)
    try:
        # Existing legacy row picks up evaluation_run_id = NULL.
        rows = conn.execute(
            "SELECT id, evaluation_run_id FROM pipeline_runs"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][1] is None
        # And the new table is queryable (empty).
        n = conn.execute("SELECT COUNT(*) FROM pipeline_chart_targets").fetchone()[0]
        assert n == 0
    finally:
        conn.close()
