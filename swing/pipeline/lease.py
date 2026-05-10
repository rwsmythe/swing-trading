"""Lease — wraps pipeline_runs repo with token-bound mutations."""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from swing.data.db import connect
from swing.data.repos.pipeline import (
    LeaseRevoked,
    finalize_run,
    find_active_run,
    find_run,
    insert_pipeline_run,
    update_heartbeat,
    update_status_columns,
    update_step,
)


class ConcurrentRunBlocked(Exception):
    """Another pipeline_runs row has state='running' with a fresh heartbeat."""


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _heartbeat_age_seconds(now: datetime, ts: str) -> float:
    return (now - datetime.fromisoformat(ts)).total_seconds()


@dataclass
class Lease:
    db_path: Path
    run_id: int
    token: str

    def heartbeat(self) -> None:
        conn = connect(self.db_path)
        try:
            with conn:
                update_heartbeat(
                    conn, run_id=self.run_id, lease_token=self.token,
                    heartbeat_ts=_now_iso(),
                )
        finally:
            conn.close()

    def step(self, name: str) -> None:
        conn = connect(self.db_path)
        try:
            with conn:
                update_step(
                    conn, run_id=self.run_id, lease_token=self.token,
                    step=name, progress_ts=_now_iso(),
                )
        finally:
            conn.close()

    def status(self, **cols: str) -> None:
        conn = connect(self.db_path)
        try:
            with conn:
                update_status_columns(
                    conn, run_id=self.run_id, lease_token=self.token, **cols,
                )
        finally:
            conn.close()

    def release(
        self, *, state: str, error_message: str | None = None,
        warnings_json: str | None = None,
    ) -> None:
        conn = connect(self.db_path)
        try:
            with conn:
                finalize_run(
                    conn, run_id=self.run_id, lease_token=self.token,
                    state=state, finished_ts=_now_iso(),
                    error_message=error_message, warnings_json=warnings_json,
                )
        finally:
            conn.close()

    def verify_held(self) -> None:
        """Preflight check: re-read pipeline_runs and raise LeaseRevoked if our
        token no longer matches a 'running' row. Cheap fail-fast; the
        authoritative protection for write transactions is `fenced_write`."""
        conn = connect(self.db_path)
        try:
            run = find_run(conn, self.run_id)
        finally:
            conn.close()
        if run is None or run.lease_token != self.token or run.state != "running":
            raise LeaseRevoked(
                f"lease revoked for run_id={self.run_id} "
                f"(state={run.state if run else 'missing'})"
            )

    @contextmanager
    def fenced_write(self) -> Iterator[sqlite3.Connection]:
        """Yield a connection inside a BEGIN IMMEDIATE transaction whose lease
        is verified in the SAME transaction as the subsequent writes. This is
        the authoritative atomic fencing for canonical DB mutations outside of
        the `pipeline_runs` table (candidates, watchlist, recommendations,
        weather_runs). If a concurrent `force_clear` committed before us, our
        SELECT sees `state != 'running'` and we ROLLBACK + raise LeaseRevoked.
        If a concurrent `force_clear` tries after we hold the RESERVED lock,
        it waits until we COMMIT; our writes land atomically then force_clear
        proceeds. Callers must do all their writes inside the `with` block;
        COMMIT happens automatically on clean exit, ROLLBACK on exception."""
        conn = connect(self.db_path)
        # Autocommit so our explicit BEGIN/COMMIT/ROLLBACK are the authoritative
        # transaction control — the sqlite3 module's default `isolation_level=""`
        # injects implicit BEGIN before DML which can conflict with our manual
        # BEGIN IMMEDIATE (adversarial review Batch 4 Round 3 Minor 1).
        conn.isolation_level = None
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    "SELECT state, lease_token FROM pipeline_runs WHERE id = ?",
                    (self.run_id,),
                ).fetchone()
                if row is None or row[0] != "running" or row[1] != self.token:
                    conn.execute("ROLLBACK")
                    raise LeaseRevoked(
                        f"lease revoked mid-txn for run_id={self.run_id} "
                        f"(state={row[0] if row else 'missing'})"
                    )
                yield conn
                conn.execute("COMMIT")
            except LeaseRevoked:
                # ROLLBACK explicitly so the write lock is released
                # immediately rather than at conn.close() (R4 minor).
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.OperationalError:
                    pass
                raise
            except Exception:
                conn.execute("ROLLBACK")
                raise
        finally:
            conn.close()


def acquire_lease(
    *, db_path: Path, trigger: str, data_asof_date: str,
    action_session_date: str, block_threshold_seconds: int = 120,
    finviz_csv_path: str | None = None,
    rs_universe_version: str | None = None,
    rs_universe_hash: str | None = None,
) -> Lease:
    """Insert a fresh pipeline_runs row + return Lease.

    Race-safe: BEGIN IMMEDIATE acquires the SQLite reserved lock up front, and
    the partial unique index ux_pipeline_one_running (migration 0003) is the
    second line of defense. The race-winner gets the lease; every loser
    surfaces as ConcurrentRunBlocked.
    """
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            active = find_active_run(conn)
            if active is not None and active.lease_heartbeat_ts is not None:
                age = _heartbeat_age_seconds(datetime.now(), active.lease_heartbeat_ts)
                if age <= block_threshold_seconds:
                    conn.execute("ROLLBACK")
                    raise ConcurrentRunBlocked(
                        f"run {active.id} state=running, heartbeat {age:.0f}s ago"
                    )
            try:
                run_id, token = insert_pipeline_run(
                    conn, started_ts=_now_iso(), trigger=trigger,
                    data_asof_date=data_asof_date,
                    action_session_date=action_session_date,
                    lease_heartbeat_ts=_now_iso(),
                    finviz_csv_path=finviz_csv_path,
                    rs_universe_version=rs_universe_version,
                    rs_universe_hash=rs_universe_hash,
                )
            except sqlite3.IntegrityError as exc:
                conn.execute("ROLLBACK")
                raise ConcurrentRunBlocked(
                    f"another run inserted concurrently: {exc}"
                ) from exc
            conn.execute("COMMIT")
        except ConcurrentRunBlocked:
            raise
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    return Lease(db_path=db_path, run_id=run_id, token=token)
