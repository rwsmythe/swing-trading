"""Lease acquire/release + concurrent-rejection."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.pipeline import LeaseRevokedError, find_run
from swing.pipeline.lease import (
    acquire_lease, ConcurrentRunBlockedError, Lease,
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
    with pytest.raises(ConcurrentRunBlockedError):
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


def test_fenced_write_rolls_back_when_lease_revoked(tmp_path: Path):
    """Adversarial review Batch 4 Round 2 Critical: fenced_write must verify
    the lease token in the SAME transaction as the subsequent writes. A
    force_clear that lands before the fenced_write's BEGIN IMMEDIATE + SELECT
    must cause ROLLBACK, not silent commit."""
    from swing.data.repos.pipeline import LeaseRevokedError, force_clear
    import sqlite3

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    lease = acquire_lease(
        db_path=db, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    # Force_clear BEFORE entering fenced_write.
    conn = sqlite3.connect(db)
    try:
        with conn:
            force_clear(conn, run_id=lease.run_id, error_message="test-revoke")
    finally:
        conn.close()

    with pytest.raises(LeaseRevokedError):
        with lease.fenced_write() as conn:
            # Write something that would land if fencing were skipped.
            conn.execute(
                "INSERT INTO weather_runs (run_ts, asof_date, ticker, status, close) "
                "VALUES (?, ?, ?, ?, ?)",
                ("2026-04-15T21:49:00", "2026-04-15", "QQQ", "Bullish", 450.0),
            )

    # Weather row must NOT be committed — the fenced txn rolled back.
    conn = sqlite3.connect(db)
    try:
        n = conn.execute("SELECT COUNT(*) FROM weather_runs").fetchone()[0]
    finally:
        conn.close()
    assert n == 0


def test_verify_held_raises_when_revoked(tmp_path: Path):
    """verify_held is the cheap fail-fast preflight used before expensive work
    (e.g., chart rendering). It must raise LeaseRevokedError on a force-cleared run."""
    from swing.data.repos.pipeline import LeaseRevokedError, force_clear
    import sqlite3

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    lease = acquire_lease(
        db_path=db, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    conn = sqlite3.connect(db)
    try:
        with conn:
            force_clear(conn, run_id=lease.run_id, error_message="test-revoke")
    finally:
        conn.close()
    with pytest.raises(LeaseRevokedError):
        lease.verify_held()


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
