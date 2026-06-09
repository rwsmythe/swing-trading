"""Lease — wraps pipeline_runs repo with token-bound mutations."""
from __future__ import annotations

import logging
import sqlite3
import time
from collections.abc import Iterator
from contextlib import closing, contextmanager, suppress
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from swing.data.db import connect
from swing.data.repos.pipeline import (
    LeaseRevokedError,
    finalize_run,
    find_active_run,
    find_run,
    insert_pipeline_run,
    update_heartbeat,
    update_status_columns,
    update_step,
)
from swing.data.repos.pipeline_step_timings import StepTiming, insert_step_timings

log = logging.getLogger(__name__)

# Advisory soft budget (spec §5.4) -- WARN only, never a control-flow gate.
# Defaults to the existing charts 60s shape; a constant, so per-step budgets can
# be tuned later without schema churn.
STEP_SOFT_BUDGET_MS = 60_000


class ConcurrentRunBlockedError(Exception):
    """Another pipeline_runs row has state='running' with a fresh heartbeat."""


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _monotonic() -> float:
    """Indirection so tests can stub a deterministic clock (mirrors _now_iso)."""
    return time.monotonic()


@dataclass(frozen=True)
class _PendingStep:
    ordinal: int
    step_name: str
    started_ts: str
    monotonic_start: float


def _aggregate_by_name(timings) -> dict[str, int]:
    """In-memory SUM(duration_ms) GROUP BY step_name, first-appearance order.
    Mirrors the repo's step_durations_by_name for the flush summary line (the
    ledger is summarized BEFORE the DB write)."""
    totals: dict[str, int] = {}
    for t in timings:
        totals[t.step_name] = totals.get(t.step_name, 0) + t.duration_ms
    return totals


def _emit_step_line(t: StepTiming) -> None:
    log.info("step ordinal=%d name=%s took %d ms", t.ordinal, t.step_name, t.duration_ms)
    if t.duration_ms > STEP_SOFT_BUDGET_MS:
        log.warning(
            "step ordinal=%d name=%s exceeded soft budget: %d ms > %d ms",
            t.ordinal, t.step_name, t.duration_ms, STEP_SOFT_BUDGET_MS,
        )


def _emit_totals_line(totals: dict[str, int]) -> None:
    parts = " ".join(f"{name}={ms}ms" for name, ms in totals.items())
    log.info("step totals: %s", parts)


def _heartbeat_age_seconds(now: datetime, ts: str) -> float:
    return (now - datetime.fromisoformat(ts)).total_seconds()


@dataclass
class Lease:
    db_path: Path
    run_id: int
    token: str
    _timings: list[StepTiming] = field(default_factory=list, init=False, repr=False)
    _pending: _PendingStep | None = field(default=None, init=False, repr=False)
    _next_ordinal: int = field(default=0, init=False, repr=False)
    _timings_flushed: bool = field(default=False, init=False, repr=False)

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
        self._record_step_boundary(name)

    def _record_step_boundary(self, name: str) -> None:
        now_mono = _monotonic()
        if self._pending is not None:
            closed = self._close_pending(now_mono)
            _emit_step_line(closed)
        self._pending = _PendingStep(
            ordinal=self._next_ordinal, step_name=name,
            started_ts=_now_iso(), monotonic_start=now_mono,
        )
        self._next_ordinal += 1

    def _close_pending(self, now_mono: float) -> StepTiming:
        p = self._pending
        timing = StepTiming(
            ordinal=p.ordinal, step_name=p.step_name,
            started_ts=p.started_ts, finished_ts=_now_iso(),
            duration_ms=int((now_mono - p.monotonic_start) * 1000),  # truncate, not round
        )
        self._timings.append(timing)
        self._pending = None
        return timing

    def flush_step_timings(self) -> None:
        """Flush the ledger ONCE, from run()'s finally. Sequence is load-bearing:
        (1) close the final pending; (2) emit the final per-step line + the
        aggregate-by-name summary BEFORE any DB write (so both survive a DB
        failure); (3) one batch transaction on a fresh connect(). The flush-once
        guard is set True ONLY after commit, so a transient failure does not
        disable a later retry while the in-memory ledger still holds the data."""
        if self._timings_flushed:
            return
        if self._pending is not None:
            _emit_step_line(self._close_pending(_monotonic()))
        if not self._timings:
            return  # empty ledger (run never called step()) -> no-op
        _emit_totals_line(_aggregate_by_name(self._timings))
        with closing(connect(self.db_path)) as conn, conn:
            insert_step_timings(conn, self.run_id, self._timings)
        self._timings_flushed = True

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
        """Preflight check: re-read pipeline_runs and raise LeaseRevokedError if our
        token no longer matches a 'running' row. Cheap fail-fast; the
        authoritative protection for write transactions is `fenced_write`."""
        conn = connect(self.db_path)
        try:
            run = find_run(conn, self.run_id)
        finally:
            conn.close()
        if run is None or run.lease_token != self.token or run.state != "running":
            raise LeaseRevokedError(
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
        SELECT sees `state != 'running'` and we ROLLBACK + raise LeaseRevokedError.
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
                    raise LeaseRevokedError(
                        f"lease revoked mid-txn for run_id={self.run_id} "
                        f"(state={row[0] if row else 'missing'})"
                    )
                yield conn
                conn.execute("COMMIT")
            except LeaseRevokedError:
                # ROLLBACK explicitly so the write lock is released
                # immediately rather than at conn.close() (R4 minor).
                with suppress(sqlite3.OperationalError):
                    conn.execute("ROLLBACK")
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
    surfaces as ConcurrentRunBlockedError.
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
                    raise ConcurrentRunBlockedError(
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
                raise ConcurrentRunBlockedError(
                    f"another run inserted concurrently: {exc}"
                ) from exc
            conn.execute("COMMIT")
        except ConcurrentRunBlockedError:
            raise
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    return Lease(db_path=db_path, run_id=run_id, token=token)
