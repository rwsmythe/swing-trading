"""Concurrent run rejection."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.pipeline.lease import ConcurrentRunBlockedError, acquire_lease


def test_second_acquire_blocked(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    first = acquire_lease(
        db_path=db, trigger="scheduled",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
        block_threshold_seconds=120,
    )
    try:
        with pytest.raises(ConcurrentRunBlockedError):
            acquire_lease(
                db_path=db, trigger="manual",
                data_asof_date="2026-04-15", action_session_date="2026-04-16",
                block_threshold_seconds=120,
            )
    finally:
        first.release(state="complete")


def test_acquire_succeeds_after_release(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    first = acquire_lease(
        db_path=db, trigger="scheduled",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    first.release(state="complete")
    second = acquire_lease(
        db_path=db, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    second.release(state="complete")


def test_stale_heartbeat_still_blocks_without_force_clear(tmp_path: Path):
    """Spec §5.1 step 1: when the prior run's heartbeat is older than the
    block threshold it becomes eligible for admin force-clear — but it does
    NOT auto-takeover. A concurrent attempt with a stale predecessor still
    raises ConcurrentRunBlockedError (via ux_pipeline_one_running partial unique
    index) until force_clear moves state out of 'running'. Completes the
    H3 coverage of the two lease-gate branches (adversarial review Batch 5
    Round 1 Major 3)."""
    import sqlite3
    from datetime import datetime, timedelta

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    # Seed a 'running' row with a stale heartbeat (10 minutes ago > 120s).
    stale_hb = (datetime.now() - timedelta(seconds=600)).isoformat(timespec="seconds")
    conn = sqlite3.connect(db)
    try:
        from swing.data.repos.pipeline import insert_pipeline_run
        with conn:
            insert_pipeline_run(
                conn, started_ts=stale_hb, trigger="scheduled",
                data_asof_date="2026-04-15", action_session_date="2026-04-16",
                lease_heartbeat_ts=stale_hb,
            )
    finally:
        conn.close()

    # A new acquire MUST still block — stale heartbeat skips the explicit
    # ConcurrentRunBlockedError raise, but the partial unique index refuses the
    # INSERT (state='running' already), surfaced via sqlite3.IntegrityError
    # → remapped to ConcurrentRunBlockedError.
    with pytest.raises(ConcurrentRunBlockedError):
        acquire_lease(
            db_path=db, trigger="manual",
            data_asof_date="2026-04-15", action_session_date="2026-04-16",
            block_threshold_seconds=120,
        )

    # After force_clear (state moves to 'force_cleared'), a new acquire
    # succeeds — the partial unique index only guards against state='running'.
    from swing.data.repos.pipeline import find_run, force_clear, list_recent_runs
    conn = sqlite3.connect(db)
    try:
        runs = list_recent_runs(conn, limit=1)
        assert runs[0].state == "running"
        stale_run_id = runs[0].id
        with conn:
            force_clear(conn, run_id=stale_run_id, error_message="test force-clear")
    finally:
        conn.close()
    new_lease = acquire_lease(
        db_path=db, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    # Audit assertions (adversarial review Batch 5 Round 2 Minor 2): the
    # stale row must transition to 'force_cleared' with its error_message
    # preserved, and the new acquire must create a DISTINCT pipeline_runs
    # row rather than mutating the old one. This proves force_clear is an
    # audit event, not an in-place takeover.
    assert new_lease.run_id != stale_run_id
    conn = sqlite3.connect(db)
    try:
        stale_run = find_run(conn, stale_run_id)
        new_run = find_run(conn, new_lease.run_id)
    finally:
        conn.close()
    assert stale_run.state == "force_cleared"
    assert stale_run.error_message == "test force-clear"
    assert new_run.state == "running"
    assert new_run.lease_token == new_lease.token
    new_lease.release(state="complete")


def test_concurrent_acquire_exactly_one_wins(tmp_path: Path):
    """True-contention test: N threads race acquire_lease against the same DB.
    Each thread HOLDS the lease (doesn't release) so the invariant "exactly one
    winner among simultaneous attempters" can actually be observed. Validates
    BEGIN IMMEDIATE + ux_pipeline_one_running partial unique index (0003)."""
    import threading

    db = tmp_path / "swing.db"
    ensure_schema(db).close()

    winners: list = []
    blocked_count = [0]
    results_lock = threading.Lock()
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()
        try:
            lease = acquire_lease(
                db_path=db, trigger="manual",
                data_asof_date="2026-04-15", action_session_date="2026-04-16",
            )
            with results_lock:
                winners.append(lease)
        except ConcurrentRunBlockedError:
            with results_lock:
                blocked_count[0] += 1

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(winners) == 1, (
        f"expected exactly one winner, got {len(winners)}"
    )
    assert blocked_count[0] == 7, (
        f"expected 7 blocked, got {blocked_count[0]}"
    )
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT COUNT(*) FROM pipeline_runs WHERE state='running'"
        ).fetchone()[0]
        assert rows == 1
    finally:
        conn.close()
    winners[0].release(state="complete")
