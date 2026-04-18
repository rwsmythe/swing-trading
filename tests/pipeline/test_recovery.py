"""Startup recovery sweep."""
from __future__ import annotations

import json
import time
from pathlib import Path

from swing.data.db import ensure_schema
from swing.data.repos.pipeline import insert_pipeline_run
from swing.pipeline.recovery import sweep_stale_artifacts


def test_deletes_staging_for_dead_run(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        with conn:
            rid, token = insert_pipeline_run(
                conn, started_ts="2026-04-15T10:00:00", trigger="scheduled",
                data_asof_date="2026-04-15", action_session_date="2026-04-16",
                lease_heartbeat_ts="2026-04-15T10:00:00",
            )
            conn.execute("UPDATE pipeline_runs SET state='failed' WHERE id=?", (rid,))
    finally:
        conn.close()

    base = tmp_path / "charts"
    staging = base / ".staging" / str(rid)
    staging.mkdir(parents=True)
    (staging / "MANIFEST.json").write_text(json.dumps({"run_id": rid}), encoding="utf-8")

    result = sweep_stale_artifacts(
        db_path=db, artifact_dirs=[base],
        prev_retention_days=7, orphan_age_seconds=3600,
    )
    assert not staging.exists()
    assert rid in result.deleted_staging_run_ids


def test_keeps_staging_for_active_run(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        with conn:
            rid, token = insert_pipeline_run(
                conn, started_ts="2026-04-15T10:00:00", trigger="scheduled",
                data_asof_date="2026-04-15", action_session_date="2026-04-16",
                lease_heartbeat_ts="2026-04-15T10:00:00",
            )
    finally:
        conn.close()
    base = tmp_path / "charts"
    staging = base / ".staging" / str(rid)
    staging.mkdir(parents=True)
    (staging / "MANIFEST.json").write_text(json.dumps({"run_id": rid}), encoding="utf-8")

    sweep_stale_artifacts(
        db_path=db, artifact_dirs=[base],
        prev_retention_days=7, orphan_age_seconds=3600,
    )
    assert staging.exists()


def test_deletes_old_prev(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    base = tmp_path / "charts"
    prev = base / ".prev" / "2026-01-01-000000"
    prev.mkdir(parents=True)
    old_ts = time.time() - 8 * 86400
    import os
    os.utime(prev, (old_ts, old_ts))

    sweep_stale_artifacts(
        db_path=db, artifact_dirs=[base],
        prev_retention_days=7, orphan_age_seconds=3600,
    )
    assert not prev.exists()


def test_deletes_manifestless_staging_when_old(tmp_path: Path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    base = tmp_path / "charts"
    staging = base / ".staging" / "999"
    staging.mkdir(parents=True)
    import os
    old_ts = time.time() - 7200
    os.utime(staging, (old_ts, old_ts))

    sweep_stale_artifacts(
        db_path=db, artifact_dirs=[base],
        prev_retention_days=7, orphan_age_seconds=3600,
    )
    assert not staging.exists()


def test_flags_stale_running_heartbeat(tmp_path: Path):
    """Spec §5.6: running runs with old heartbeats must be FLAGGED for operator
    review (not auto-deleted — only force-clear can revoke a lease)."""
    from datetime import datetime, timedelta

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        with conn:
            rid, _ = insert_pipeline_run(
                conn, started_ts="2026-04-15T10:00:00", trigger="scheduled",
                data_asof_date="2026-04-15", action_session_date="2026-04-16",
                lease_heartbeat_ts=(datetime.now() - timedelta(seconds=600)).isoformat(
                    timespec="seconds"
                ),
            )
    finally:
        conn.close()
    base = tmp_path / "charts"
    staging = base / ".staging" / str(rid)
    staging.mkdir(parents=True)
    (staging / "MANIFEST.json").write_text(json.dumps({"run_id": rid}), encoding="utf-8")

    result = sweep_stale_artifacts(
        db_path=db, artifact_dirs=[base],
        prev_retention_days=7, orphan_age_seconds=3600,
        stale_heartbeat_seconds=300,
    )
    assert staging.exists()
    assert rid in result.flagged_stale_running_runs
