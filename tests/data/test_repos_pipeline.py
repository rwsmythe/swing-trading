"""Pipeline runs repo + lease enforcement."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.pipeline import (
    LeaseRevoked, insert_pipeline_run, update_step, update_status_columns,
    finalize_run, force_clear, find_active_run, find_run, list_recent_runs,
)


def _ts(n: int = 0) -> str:
    return f"2026-04-15T21:49:{n:02d}"


def test_insert_and_find_active(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            rid, token = insert_pipeline_run(
                conn, started_ts=_ts(0), trigger="scheduled",
                data_asof_date="2026-04-15", action_session_date="2026-04-16",
                lease_heartbeat_ts=_ts(1),
            )
        active = find_active_run(conn)
        assert active is not None
        assert active.id == rid
        assert active.lease_token == token
        assert active.state == "running"
    finally:
        conn.close()


def test_lease_fenced_step_update(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            rid, token = insert_pipeline_run(
                conn, started_ts=_ts(0), trigger="scheduled",
                data_asof_date="2026-04-15", action_session_date="2026-04-16",
                lease_heartbeat_ts=_ts(1),
            )
        with conn:
            update_step(conn, run_id=rid, lease_token=token,
                        step="weather", progress_ts=_ts(2))
        run = find_run(conn, rid)
        assert run.current_step == "weather"
        assert run.last_step_progress_ts == _ts(2)

        # Wrong token must raise
        with pytest.raises(LeaseRevoked):
            with conn:
                update_step(conn, run_id=rid, lease_token="wrong-token",
                            step="evaluate", progress_ts=_ts(3))
    finally:
        conn.close()


def test_force_clear_revokes_lease(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            rid, token = insert_pipeline_run(
                conn, started_ts=_ts(0), trigger="scheduled",
                data_asof_date="2026-04-15", action_session_date="2026-04-16",
                lease_heartbeat_ts=_ts(1),
            )
        with conn:
            force_clear(conn, run_id=rid, error_message="admin force at 22:00")

        # Original holder cannot continue
        with pytest.raises(LeaseRevoked):
            with conn:
                update_step(conn, run_id=rid, lease_token=token,
                            step="evaluate", progress_ts=_ts(5))

        run = find_run(conn, rid)
        assert run.state == "force_cleared"
        assert "admin" in (run.error_message or "")
    finally:
        conn.close()


def test_finalize_run_sets_finished(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            rid, token = insert_pipeline_run(
                conn, started_ts=_ts(0), trigger="scheduled",
                data_asof_date="2026-04-15", action_session_date="2026-04-16",
                lease_heartbeat_ts=_ts(1),
            )
        with conn:
            finalize_run(conn, run_id=rid, lease_token=token,
                         state="complete", finished_ts=_ts(30))
        run = find_run(conn, rid)
        assert run.state == "complete"
        assert run.finished_ts == _ts(30)
    finally:
        conn.close()


def test_list_recent_returns_descending(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        ids = []
        for i in range(3):
            with conn:
                rid, token = insert_pipeline_run(
                    conn, started_ts=f"2026-04-1{i+1}T21:49:00",
                    trigger="scheduled",
                    data_asof_date=f"2026-04-1{i+1}",
                    action_session_date=f"2026-04-1{i+2}",
                    lease_heartbeat_ts=f"2026-04-1{i+1}T21:49:30",
                )
            # Finalize each run so the next insert doesn't violate
            # the ux_pipeline_one_running partial unique index.
            with conn:
                finalize_run(conn, run_id=rid, lease_token=token,
                             state="complete",
                             finished_ts=f"2026-04-1{i+1}T22:00:00")
            ids.append(rid)
        recent = list_recent_runs(conn, limit=10)
        assert [r.id for r in recent] == list(reversed(ids))
    finally:
        conn.close()
