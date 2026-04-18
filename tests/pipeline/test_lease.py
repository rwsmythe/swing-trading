"""Lease acquire/release + concurrent-rejection."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.pipeline import LeaseRevoked, find_run
from swing.pipeline.lease import (
    acquire_lease, ConcurrentRunBlocked, Lease,
)


def test_acquire_inserts_and_returns_lease(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    lease = acquire_lease(
        db_path=db, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
        block_threshold_seconds=120,
    )
    assert isinstance(lease, Lease)
    assert lease.run_id > 0
    assert lease.token

    lease.release(state="complete")


def test_concurrent_blocked_within_threshold(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    first = acquire_lease(
        db_path=db, trigger="scheduled",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
        block_threshold_seconds=120,
    )
    with pytest.raises(ConcurrentRunBlocked):
        acquire_lease(
            db_path=db, trigger="manual",
            data_asof_date="2026-04-15", action_session_date="2026-04-16",
            block_threshold_seconds=120,
        )
    first.release(state="complete")


def test_release_marks_complete(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    lease = acquire_lease(
        db_path=db, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
        block_threshold_seconds=120,
    )
    lease.release(state="complete")
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        run = find_run(conn, lease.run_id)
    finally:
        conn.close()
    assert run.state == "complete"
    assert run.finished_ts is not None


def test_release_failed_with_error(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    lease = acquire_lease(
        db_path=db, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
        block_threshold_seconds=120,
    )
    lease.release(state="failed", error_message="boom")
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        run = find_run(conn, lease.run_id)
    finally:
        conn.close()
    assert run.state == "failed"
    assert run.error_message == "boom"
