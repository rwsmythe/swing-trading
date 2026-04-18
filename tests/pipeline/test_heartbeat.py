"""Heartbeat thread — emits at interval, stops cleanly."""
from __future__ import annotations

import time
from pathlib import Path

from swing.data.db import ensure_schema
from swing.data.repos.pipeline import find_run
from swing.pipeline.heartbeat import Heartbeat
from swing.pipeline.lease import acquire_lease


def test_heartbeat_updates_at_interval(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    lease = acquire_lease(
        db_path=db, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    hb = Heartbeat(lease=lease, interval_seconds=0.2)
    hb.start()
    try:
        time.sleep(0.5)
    finally:
        hb.stop()

    import sqlite3
    conn = sqlite3.connect(db)
    try:
        run = find_run(conn, lease.run_id)
    finally:
        conn.close()
    assert run.lease_heartbeat_ts is not None
    lease.release(state="complete")


def test_heartbeat_stops_on_event(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    lease = acquire_lease(
        db_path=db, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    hb = Heartbeat(lease=lease, interval_seconds=0.1)
    hb.start()
    hb.stop()
    assert not hb.is_alive()
    lease.release(state="complete")
