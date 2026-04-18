"""Concurrent run rejection."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.pipeline.lease import ConcurrentRunBlocked, acquire_lease


def test_second_acquire_blocked(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    first = acquire_lease(
        db_path=db, trigger="scheduled",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
        block_threshold_seconds=120,
    )
    try:
        with pytest.raises(ConcurrentRunBlocked):
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
        except ConcurrentRunBlocked:
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
