"""Repo helpers for pipeline_chart_targets and pipeline_runs.evaluation_run_id.

Tranche C T2 — repo layer. Verifies the small mutation primitives the pipeline
runner uses to persist (a) the eval-run linkage and (b) per-ticker chart-step
outcomes. These functions intentionally do NOT take lease tokens — they assume
the caller is already inside a `lease.fenced_write()` transaction (the
authoritative atomic fence).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema


def _seed_pipeline_run(conn: sqlite3.Connection, **overrides) -> int:
    base = dict(
        started_ts="2026-04-17T21:00:00",
        trigger="manual",
        data_asof_date="2026-04-17",
        action_session_date="2026-04-17",
        state="running",
        lease_token="t-1",
    )
    base.update(overrides)
    cols = ", ".join(base.keys())
    placeholders = ", ".join("?" for _ in base)
    cur = conn.execute(
        f"INSERT INTO pipeline_runs ({cols}) VALUES ({placeholders})",
        tuple(base.values()),
    )
    return int(cur.lastrowid)


def _seed_eval_run(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        """INSERT INTO evaluation_runs
           (run_ts, data_asof_date, action_session_date, finviz_csv_path,
            tickers_evaluated, aplus_count, watch_count, skip_count,
            excluded_count, error_count, rs_universe_version, rs_universe_hash)
           VALUES ('2026-04-17T21:30:00', '2026-04-17', '2026-04-17', NULL,
                   0, 0, 0, 0, 0, 0, 'v1', 'deadbeef')""",
    )
    return int(cur.lastrowid)


def test_set_evaluation_run_id_writes_fk(tmp_path: Path):
    from swing.data.repos.pipeline import set_evaluation_run_id

    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    try:
        run_id = _seed_pipeline_run(conn)
        eval_id = _seed_eval_run(conn)
        conn.commit()
        set_evaluation_run_id(
            conn, pipeline_run_id=run_id, evaluation_run_id=eval_id,
        )
        conn.commit()
        row = conn.execute(
            "SELECT evaluation_run_id FROM pipeline_runs WHERE id=?", (run_id,),
        ).fetchone()
        assert row[0] == eval_id
    finally:
        conn.close()


def test_set_evaluation_run_id_idempotent_overwrite(tmp_path: Path):
    """Calling twice with different values overwrites — pipeline only ever
    binds to one eval per run, but the repo function shouldn't impose a
    one-shot constraint."""
    from swing.data.repos.pipeline import set_evaluation_run_id

    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    try:
        run_id = _seed_pipeline_run(conn)
        e1 = _seed_eval_run(conn)
        e2 = _seed_eval_run(conn)
        conn.commit()
        set_evaluation_run_id(
            conn, pipeline_run_id=run_id, evaluation_run_id=e1,
        )
        set_evaluation_run_id(
            conn, pipeline_run_id=run_id, evaluation_run_id=e2,
        )
        conn.commit()
        row = conn.execute(
            "SELECT evaluation_run_id FROM pipeline_runs WHERE id=?", (run_id,),
        ).fetchone()
        assert row[0] == e2
    finally:
        conn.close()


def test_insert_chart_target_writes_row_with_pending_default(tmp_path: Path):
    from swing.data.repos.pipeline import insert_chart_target

    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    try:
        run_id = _seed_pipeline_run(conn)
        conn.commit()
        insert_chart_target(
            conn, pipeline_run_id=run_id, ticker="AAPL", source="aplus",
        )
        conn.commit()
        row = conn.execute(
            """SELECT ticker, source, chart_status FROM pipeline_chart_targets
               WHERE pipeline_run_id=?""", (run_id,),
        ).fetchone()
        assert row == ("AAPL", "aplus", "pending")
    finally:
        conn.close()


def test_insert_chart_target_accepts_explicit_status(tmp_path: Path):
    from swing.data.repos.pipeline import insert_chart_target

    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    try:
        run_id = _seed_pipeline_run(conn)
        conn.commit()
        insert_chart_target(
            conn, pipeline_run_id=run_id, ticker="MSFT",
            source="near_proximity", chart_status="ok",
        )
        conn.commit()
        row = conn.execute(
            """SELECT chart_status FROM pipeline_chart_targets
               WHERE pipeline_run_id=? AND ticker='MSFT'""", (run_id,),
        ).fetchone()
        assert row[0] == "ok"
    finally:
        conn.close()


def test_update_chart_target_status_transitions(tmp_path: Path):
    from swing.data.repos.pipeline import (
        insert_chart_target, update_chart_target_status,
    )

    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    try:
        run_id = _seed_pipeline_run(conn)
        conn.commit()
        insert_chart_target(
            conn, pipeline_run_id=run_id, ticker="AAPL", source="aplus",
        )
        conn.commit()
        update_chart_target_status(
            conn, pipeline_run_id=run_id, ticker="AAPL",
            chart_status="fetcher_failed",
        )
        conn.commit()
        row = conn.execute(
            """SELECT chart_status FROM pipeline_chart_targets
               WHERE pipeline_run_id=? AND ticker='AAPL'""", (run_id,),
        ).fetchone()
        assert row[0] == "fetcher_failed"
    finally:
        conn.close()


def test_update_chart_target_status_no_op_for_unknown_ticker(tmp_path: Path):
    """Updating a row that doesn't exist must NOT raise — the chart step never
    inserts before update, but a defensive call should be silent rather than
    surfacing as a fenced_write rollback. (Affects retry scenarios where a
    target was filtered out between insert and update phases.)"""
    from swing.data.repos.pipeline import update_chart_target_status

    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    try:
        run_id = _seed_pipeline_run(conn)
        conn.commit()
        update_chart_target_status(
            conn, pipeline_run_id=run_id, ticker="GHOST", chart_status="ok",
        )
        conn.commit()
        n = conn.execute(
            "SELECT COUNT(*) FROM pipeline_chart_targets"
        ).fetchone()[0]
        assert n == 0
    finally:
        conn.close()


def test_list_chart_targets_returns_tuples_for_run(tmp_path: Path):
    from swing.data.repos.pipeline import (
        insert_chart_target, list_chart_targets,
    )

    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    try:
        run_id = _seed_pipeline_run(conn)
        conn.commit()
        insert_chart_target(
            conn, pipeline_run_id=run_id, ticker="AAPL", source="aplus",
            chart_status="ok",
        )
        insert_chart_target(
            conn, pipeline_run_id=run_id, ticker="MSFT",
            source="near_proximity", chart_status="too_few_bars",
        )
        # An unrelated run's targets must NOT leak into the result. Use a
        # complete state so the running-row unique index doesn't reject.
        other_run = _seed_pipeline_run(conn, lease_token="t-2", state="complete")
        insert_chart_target(
            conn, pipeline_run_id=other_run, ticker="ZZZ", source="aplus",
        )
        conn.commit()
        targets = list_chart_targets(conn, pipeline_run_id=run_id)
        by_ticker = {t.ticker: t for t in targets}
        assert set(by_ticker.keys()) == {"AAPL", "MSFT"}
        assert by_ticker["AAPL"].source == "aplus"
        assert by_ticker["AAPL"].chart_status == "ok"
        assert by_ticker["MSFT"].source == "near_proximity"
        assert by_ticker["MSFT"].chart_status == "too_few_bars"
    finally:
        conn.close()


def test_insert_chart_target_duplicate_raises(tmp_path: Path):
    """The (pipeline_run_id, ticker) UNIQUE constraint must surface as
    IntegrityError — caller is expected to dedupe targets before insert."""
    from swing.data.repos.pipeline import insert_chart_target

    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    try:
        run_id = _seed_pipeline_run(conn)
        conn.commit()
        insert_chart_target(
            conn, pipeline_run_id=run_id, ticker="AAPL", source="aplus",
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            insert_chart_target(
                conn, pipeline_run_id=run_id, ticker="AAPL",
                source="near_proximity",
            )
            conn.commit()
    finally:
        conn.close()
