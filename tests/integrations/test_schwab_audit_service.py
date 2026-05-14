"""Phase 11 T-A.9 — Schwab audit service-layer wrapper tests.

Per plan §B.1 (service signatures) + §H.4.1 (combined-tx2 algorithm) +
plan §Tasks-A T-A.9.

Tests cover:
  - Happy paths for the 4 service functions.
  - Caller-held-tx rejection for each (mirrors Phase 9 service-layer
    discipline + CLAUDE.md gotcha "in_transaction auto-detect").
  - PK preservation across update (locks UPDATE-in-place vs INSERT OR
    REPLACE per CLAUDE.md gotcha).
  - Combined-tx2 atomicity (R2 Major #3 fix): single BEGIN IMMEDIATE
    covers BOTH UPDATEs in link_snapshot_and_stamp_account_hash; on
    mid-tx failure, NEITHER side-effect persists (never one without the
    other).
  - End-to-end audit lifecycle (start → finish → link).
  - Concurrent serialization across two connections (BEGIN IMMEDIATE
    write-lock serializes; both eventually succeed with distinct
    call_ids).
"""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.integrations.schwab.audit_service import (
    CallerHeldTransactionError,
    link_reconciliation_run,
    link_snapshot_and_stamp_account_hash,
    record_call_finish,
    record_call_start,
)


# ============================================================================
# Fixtures + seed helpers
# ============================================================================


@pytest.fixture
def v18_conn(tmp_path: Path) -> sqlite3.Connection:
    """v18 DB with PRAGMA foreign_keys=ON (set by ensure_schema)."""
    return ensure_schema(tmp_path / "schwab-audit-svc-test.db")


@pytest.fixture
def v18_db_path(tmp_path: Path) -> Path:
    """Initialised DB file path (for multi-connection concurrency tests)."""
    path = tmp_path / "schwab-audit-svc-concurrency.db"
    ensure_schema(path).close()
    return path


def _seed_pipeline_run(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "INSERT INTO pipeline_runs ("
        "started_ts, trigger, data_asof_date, action_session_date, "
        "state, lease_token"
        ") VALUES (?, ?, ?, ?, ?, ?)",
        ("2026-05-13T08:00:00", "manual", "2026-05-12", "2026-05-13",
         "running", "test-token"),
    )
    conn.commit()  # Release implicit auto-tx so service can BEGIN IMMEDIATE.
    return int(cur.lastrowid)


def _seed_account_equity_snapshot(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "INSERT INTO account_equity_snapshots ("
        "snapshot_date, equity_dollars, source, source_artifact_path, "
        "recorded_at, recorded_by, notes"
        ") VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("2026-05-13", 2000.0, "manual", None, "2026-05-13T12:00:00",
         "operator", None),
    )
    conn.commit()
    return int(cur.lastrowid)


def _seed_reconciliation_run(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "INSERT INTO reconciliation_runs ("
        "started_ts, source, period_start, period_end, state"
        ") VALUES (?, ?, ?, ?, ?)",
        ("2026-05-13T12:00:00", "tos_csv", "2026-05-06", "2026-05-13",
         "completed"),
    )
    conn.commit()
    return int(cur.lastrowid)


def _common_start_kwargs(pipeline_run_id: int) -> dict:
    return dict(
        ts="2026-05-13T12:00:00",
        endpoint="oauth.refresh",
        pipeline_run_id=pipeline_run_id,
        surface="pipeline",
        environment="sandbox",
    )


# ============================================================================
# 1-2. record_call_start: happy path + caller-held-tx rejection
# ============================================================================


def test_record_call_start_happy_path_persists_in_flight_row(
    v18_conn: sqlite3.Connection,
) -> None:
    conn = v18_conn
    try:
        pr = _seed_pipeline_run(conn)
        call_id = record_call_start(conn, **_common_start_kwargs(pr))
        assert isinstance(call_id, int)
        assert call_id >= 1
        row = conn.execute(
            "SELECT status, ts, endpoint, pipeline_run_id, surface, environment "
            "FROM schwab_api_calls WHERE call_id = ?",
            (call_id,),
        ).fetchone()
        assert row is not None
        assert row[0] == "in_flight"
        assert row[1] == "2026-05-13T12:00:00"
        assert row[2] == "oauth.refresh"
        assert row[3] == pr
        assert row[4] == "pipeline"
        assert row[5] == "sandbox"
        # Service must have COMMITTED — conn.in_transaction is False post-call.
        assert conn.in_transaction is False
    finally:
        conn.close()


def test_record_call_start_rejects_caller_held_tx(
    v18_conn: sqlite3.Connection,
) -> None:
    """Discriminating: caller holds an open transaction → CallerHeldTransactionError.
    Commit; retry; succeeds."""
    conn = v18_conn
    try:
        pr = _seed_pipeline_run(conn)
        conn.execute("BEGIN")
        with pytest.raises(CallerHeldTransactionError, match="record_call_start"):
            record_call_start(conn, **_common_start_kwargs(pr))
        conn.commit()  # release caller tx
        # Retry succeeds.
        call_id = record_call_start(conn, **_common_start_kwargs(pr))
        assert call_id >= 1
    finally:
        conn.close()


# ============================================================================
# 3-5. record_call_finish: happy path + caller-held-tx rejection + PK preserved
# ============================================================================


def test_record_call_finish_happy_path_updates_outcome_fields(
    v18_conn: sqlite3.Connection,
) -> None:
    conn = v18_conn
    try:
        pr = _seed_pipeline_run(conn)
        call_id = record_call_start(conn, **_common_start_kwargs(pr))
        record_call_finish(
            conn,
            call_id=call_id,
            http_status=200,
            response_time_ms=145,
            rate_limit_remaining=99,
            signature_hash="a" * 64,
            status="success",
            error_message=None,
        )
        row = conn.execute(
            "SELECT status, http_status, response_time_ms, "
            "rate_limit_remaining, signature_hash, error_message "
            "FROM schwab_api_calls WHERE call_id = ?",
            (call_id,),
        ).fetchone()
        assert row[0] == "success"
        assert row[1] == 200
        assert row[2] == 145
        assert row[3] == 99
        assert row[4] == "a" * 64
        assert row[5] is None
    finally:
        conn.close()


def test_record_call_finish_rejects_caller_held_tx(
    v18_conn: sqlite3.Connection,
) -> None:
    conn = v18_conn
    try:
        pr = _seed_pipeline_run(conn)
        call_id = record_call_start(conn, **_common_start_kwargs(pr))
        conn.execute("BEGIN")
        with pytest.raises(CallerHeldTransactionError, match="record_call_finish"):
            record_call_finish(
                conn,
                call_id=call_id,
                http_status=200,
                response_time_ms=100,
                rate_limit_remaining=99,
                signature_hash=None,
                status="success",
                error_message=None,
            )
        conn.commit()
        # Retry succeeds:
        record_call_finish(
            conn,
            call_id=call_id,
            http_status=200,
            response_time_ms=100,
            rate_limit_remaining=99,
            signature_hash=None,
            status="success",
            error_message=None,
        )
    finally:
        conn.close()


def test_record_call_finish_preserves_pk_across_update(
    v18_conn: sqlite3.Connection,
) -> None:
    """DISCRIMINATING: PK preserved across UPDATE — would fail if any
    INSERT OR REPLACE were introduced in the chain."""
    conn = v18_conn
    try:
        pr = _seed_pipeline_run(conn)
        call_id = record_call_start(conn, **_common_start_kwargs(pr))
        record_call_finish(
            conn,
            call_id=call_id,
            http_status=200,
            response_time_ms=145,
            rate_limit_remaining=99,
            signature_hash=None,
            status="success",
            error_message=None,
        )
        rows = conn.execute(
            "SELECT call_id FROM schwab_api_calls"
        ).fetchall()
        assert len(rows) == 1, (
            "REPLACE would yield duplicate row or reissue PK; UPDATE preserves single row."
        )
        assert rows[0][0] == call_id
    finally:
        conn.close()


def test_record_call_finish_does_not_mutate_unchanged_fields(
    v18_conn: sqlite3.Connection,
) -> None:
    """Capture initial state; finish; assert ts/endpoint/surface/etc unchanged."""
    conn = v18_conn
    try:
        pr = _seed_pipeline_run(conn)
        call_id = record_call_start(conn, **_common_start_kwargs(pr))
        before = conn.execute(
            "SELECT ts, endpoint, pipeline_run_id, surface, environment "
            "FROM schwab_api_calls WHERE call_id = ?",
            (call_id,),
        ).fetchone()
        record_call_finish(
            conn,
            call_id=call_id,
            http_status=500,
            response_time_ms=2000,
            rate_limit_remaining=10,
            signature_hash=None,
            status="error",
            error_message="upstream 5xx",
        )
        after = conn.execute(
            "SELECT ts, endpoint, pipeline_run_id, surface, environment, "
            "status, error_message "
            "FROM schwab_api_calls WHERE call_id = ?",
            (call_id,),
        ).fetchone()
        assert before == after[:5]
        assert after[5] == "error"
        assert after[6] == "upstream 5xx"
    finally:
        conn.close()


# ============================================================================
# 6-9. link_snapshot_and_stamp_account_hash: happy / reject / rollback / single-tx
# ============================================================================


def test_link_snapshot_and_stamp_account_hash_both_updates_land_atomically(
    v18_conn: sqlite3.Connection,
) -> None:
    """Both schwab_api_calls.linked_snapshot_id AND
    account_equity_snapshots.schwab_account_hash populated after one call."""
    conn = v18_conn
    try:
        pr = _seed_pipeline_run(conn)
        call_id = record_call_start(conn, **_common_start_kwargs(pr))
        record_call_finish(
            conn,
            call_id=call_id,
            http_status=200,
            response_time_ms=145,
            rate_limit_remaining=99,
            signature_hash=None,
            status="success",
            error_message=None,
        )
        snapshot_id = _seed_account_equity_snapshot(conn)
        link_snapshot_and_stamp_account_hash(
            conn,
            call_id=call_id,
            snapshot_id=snapshot_id,
            account_hash="ABCDEF1234567890",
        )
        audit_row = conn.execute(
            "SELECT linked_snapshot_id FROM schwab_api_calls WHERE call_id = ?",
            (call_id,),
        ).fetchone()
        snap_row = conn.execute(
            "SELECT schwab_account_hash FROM account_equity_snapshots "
            "WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
        assert audit_row[0] == snapshot_id
        assert snap_row[0] == "ABCDEF1234567890"
    finally:
        conn.close()


def test_link_snapshot_and_stamp_account_hash_rejects_caller_held_tx(
    v18_conn: sqlite3.Connection,
) -> None:
    conn = v18_conn
    try:
        pr = _seed_pipeline_run(conn)
        call_id = record_call_start(conn, **_common_start_kwargs(pr))
        snapshot_id = _seed_account_equity_snapshot(conn)
        conn.execute("BEGIN")
        with pytest.raises(
            CallerHeldTransactionError,
            match="link_snapshot_and_stamp_account_hash",
        ):
            link_snapshot_and_stamp_account_hash(
                conn,
                call_id=call_id,
                snapshot_id=snapshot_id,
                account_hash="HASH",
            )
        conn.commit()
        # Retry succeeds:
        link_snapshot_and_stamp_account_hash(
            conn,
            call_id=call_id,
            snapshot_id=snapshot_id,
            account_hash="HASH",
        )
    finally:
        conn.close()


def test_link_snapshot_and_stamp_account_hash_rollback_on_mid_tx_failure(
    v18_conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DISCRIMINATING / R2 Major #3 + plan T-A.9 crash-window simulation:
    if the second UPDATE raises mid-tx2, NEITHER side-effect persists
    (linked_snapshot_id stays NULL AND schwab_account_hash stays NULL).

    Implementation: patch the service's ``_stamp_account_hash_on_snapshot``
    helper (the second leg of the combined tx2) to raise. The first leg
    runs normally through repo.update_call_linked_snapshot. The
    discriminating shape: combined-tx2 rolls BOTH back; if the service
    had two separate transactions, only the second would roll back and
    `linked_snapshot_id` would remain set (the failure-mode the R2 fix
    closes)."""
    import swing.integrations.schwab.audit_service as svc

    conn = v18_conn
    try:
        pr = _seed_pipeline_run(conn)
        call_id = record_call_start(conn, **_common_start_kwargs(pr))
        snapshot_id = _seed_account_equity_snapshot(conn)

        def _raising_stamp(_conn, *, snapshot_id, account_hash):
            raise RuntimeError("simulated process kill")

        monkeypatch.setattr(
            svc, "_stamp_account_hash_on_snapshot", _raising_stamp,
        )
        with pytest.raises(RuntimeError, match="simulated process kill"):
            link_snapshot_and_stamp_account_hash(
                conn,
                call_id=call_id,
                snapshot_id=snapshot_id,
                account_hash="WILL_NOT_LAND",
            )
        # Both side-effects MUST be NULL — combined-tx2 atomicity.
        audit_row = conn.execute(
            "SELECT linked_snapshot_id FROM schwab_api_calls WHERE call_id = ?",
            (call_id,),
        ).fetchone()
        snap_row = conn.execute(
            "SELECT schwab_account_hash FROM account_equity_snapshots "
            "WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
        assert audit_row[0] is None, (
            "linked_snapshot_id must roll back when account_hash UPDATE fails "
            "— combined-tx2 atomicity per R2 Major #3 fix."
        )
        assert snap_row[0] is None
    finally:
        conn.close()


def test_link_snapshot_and_stamp_account_hash_uses_single_begin_immediate(
    v18_conn: sqlite3.Connection,
) -> None:
    """DISCRIMINATING / R2 Major #3: assert ONE ``BEGIN IMMEDIATE`` —
    confirms single-tx2 design (NOT two separate transactions per leg).
    Uses ``set_trace_callback`` to count BEGIN IMMEDIATE statements
    issued during the link call only. A two-tx design would call BEGIN
    IMMEDIATE twice; the test would fail."""
    conn = v18_conn
    try:
        pr = _seed_pipeline_run(conn)
        call_id = record_call_start(conn, **_common_start_kwargs(pr))
        snapshot_id = _seed_account_equity_snapshot(conn)

        observed: list[str] = []

        def _trace(stmt: str) -> None:
            if "BEGIN IMMEDIATE" in stmt.upper():
                observed.append(stmt)

        conn.set_trace_callback(_trace)
        try:
            link_snapshot_and_stamp_account_hash(
                conn,
                call_id=call_id,
                snapshot_id=snapshot_id,
                account_hash="HASH",
            )
        finally:
            conn.set_trace_callback(None)
        assert len(observed) == 1, (
            "link_snapshot_and_stamp_account_hash MUST use ONE BEGIN IMMEDIATE "
            "covering both UPDATEs per plan §H.4.1 + R2 Major #3 fix. "
            f"Observed BEGIN IMMEDIATE statements: {observed!r}"
        )
    finally:
        conn.close()


# ============================================================================
# 10-11. link_reconciliation_run: happy + caller-held-tx rejection
# ============================================================================


def test_link_reconciliation_run_happy_path(
    v18_conn: sqlite3.Connection,
) -> None:
    conn = v18_conn
    try:
        pr = _seed_pipeline_run(conn)
        call_id = record_call_start(conn, **_common_start_kwargs(pr))
        run_id = _seed_reconciliation_run(conn)
        link_reconciliation_run(
            conn, call_id=call_id, reconciliation_run_id=run_id,
        )
        row = conn.execute(
            "SELECT linked_reconciliation_run_id FROM schwab_api_calls "
            "WHERE call_id = ?",
            (call_id,),
        ).fetchone()
        assert row[0] == run_id
    finally:
        conn.close()


def test_link_reconciliation_run_rejects_caller_held_tx(
    v18_conn: sqlite3.Connection,
) -> None:
    conn = v18_conn
    try:
        pr = _seed_pipeline_run(conn)
        call_id = record_call_start(conn, **_common_start_kwargs(pr))
        run_id = _seed_reconciliation_run(conn)
        conn.execute("BEGIN")
        with pytest.raises(
            CallerHeldTransactionError, match="link_reconciliation_run",
        ):
            link_reconciliation_run(
                conn, call_id=call_id, reconciliation_run_id=run_id,
            )
        conn.commit()
        # Retry succeeds:
        link_reconciliation_run(
            conn, call_id=call_id, reconciliation_run_id=run_id,
        )
    finally:
        conn.close()


# ============================================================================
# 12. End-to-end audit lifecycle
# ============================================================================


def test_end_to_end_audit_lifecycle_round_trip(
    v18_conn: sqlite3.Connection,
) -> None:
    """start → finish(success) → link_snapshot_and_stamp_account_hash;
    verify final state across audit row + snapshot row."""
    conn = v18_conn
    try:
        pr = _seed_pipeline_run(conn)
        call_id = record_call_start(
            conn,
            ts="2026-05-13T12:00:00",
            endpoint="accounts.details",
            pipeline_run_id=pr,
            surface="cli",
            environment="production",
        )
        record_call_finish(
            conn,
            call_id=call_id,
            http_status=200,
            response_time_ms=180,
            rate_limit_remaining=42,
            signature_hash="0123456789abcdef" * 4,
            status="success",
            error_message=None,
        )
        snapshot_id = _seed_account_equity_snapshot(conn)
        link_snapshot_and_stamp_account_hash(
            conn,
            call_id=call_id,
            snapshot_id=snapshot_id,
            account_hash="DEADBEEF",
        )
        audit = conn.execute(
            "SELECT ts, endpoint, status, http_status, response_time_ms, "
            "rate_limit_remaining, signature_hash, surface, environment, "
            "linked_snapshot_id, pipeline_run_id "
            "FROM schwab_api_calls WHERE call_id = ?",
            (call_id,),
        ).fetchone()
        assert audit[0] == "2026-05-13T12:00:00"
        assert audit[1] == "accounts.details"
        assert audit[2] == "success"
        assert audit[3] == 200
        assert audit[4] == 180
        assert audit[5] == 42
        assert audit[6] == "0123456789abcdef" * 4
        assert audit[7] == "cli"
        assert audit[8] == "production"
        assert audit[9] == snapshot_id
        assert audit[10] == pr
        snap = conn.execute(
            "SELECT schwab_account_hash FROM account_equity_snapshots "
            "WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
        assert snap[0] == "DEADBEEF"
    finally:
        conn.close()


# ============================================================================
# 13. Concurrent serialization (two connections; BEGIN IMMEDIATE serializes)
# ============================================================================


def test_record_call_start_serializes_concurrent_writers(
    v18_db_path: Path,
) -> None:
    """Two writers concurrently call record_call_start through distinct
    sqlite3 connections to the same DB file. BEGIN IMMEDIATE acquires the
    write lock; second writer waits; both eventually succeed with
    DISTINCT call_ids. Discriminating contract: no SQLITE_BUSY raised at
    the service layer + both call_ids land + they differ."""
    db_path = v18_db_path

    # Seed a pipeline_run shared by both writers.
    with sqlite3.connect(db_path) as seed_conn:
        seed_conn.execute("PRAGMA foreign_keys = ON")
        cur = seed_conn.execute(
            "INSERT INTO pipeline_runs ("
            "started_ts, trigger, data_asof_date, action_session_date, "
            "state, lease_token"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            ("2026-05-13T08:00:00", "manual", "2026-05-12", "2026-05-13",
             "running", "concurrency-test-token"),
        )
        seed_conn.commit()
        pipeline_run_id = int(cur.lastrowid)

    results: list[int] = []
    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def _writer(tag: str) -> None:
        try:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                barrier.wait()
                # Tiny stagger to encourage observable lock contention.
                if tag == "B":
                    time.sleep(0.005)
                call_id = record_call_start(
                    conn,
                    ts=f"2026-05-13T12:00:0{tag}",
                    endpoint="oauth.refresh",
                    pipeline_run_id=pipeline_run_id,
                    surface="pipeline",
                    environment="sandbox",
                )
                results.append(call_id)
            finally:
                conn.close()
        except BaseException as exc:  # pragma: no cover - surfaced via errors
            errors.append(exc)

    threads = [threading.Thread(target=_writer, args=(t,)) for t in ("A", "B")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15.0)

    assert not errors, f"Concurrent writers should both succeed; got {errors!r}"
    assert len(results) == 2
    assert results[0] != results[1], (
        "Distinct call_ids — AUTOINCREMENT PK + serialized BEGIN IMMEDIATE."
    )
    # Both rows actually persisted with status='in_flight'.
    with sqlite3.connect(db_path) as verify_conn:
        count = verify_conn.execute(
            "SELECT COUNT(*) FROM schwab_api_calls WHERE status = 'in_flight'"
        ).fetchone()[0]
    assert count == 2


# ============================================================================
# 14. record_call_start writes all required fields
# ============================================================================


def test_record_call_start_writes_all_required_fields(
    v18_conn: sqlite3.Connection,
) -> None:
    conn = v18_conn
    try:
        pr = _seed_pipeline_run(conn)
        call_id = record_call_start(
            conn,
            ts="2026-05-13T12:34:56",
            endpoint="marketdata.pricehistory",
            pipeline_run_id=pr,
            surface="cli",
            environment="production",
        )
        row = conn.execute(
            "SELECT ts, endpoint, pipeline_run_id, surface, environment, status "
            "FROM schwab_api_calls WHERE call_id = ?",
            (call_id,),
        ).fetchone()
        assert row[0] == "2026-05-13T12:34:56"
        assert row[1] == "marketdata.pricehistory"
        assert row[2] == pr
        assert row[3] == "cli"
        assert row[4] == "production"
        assert row[5] == "in_flight"
    finally:
        conn.close()


# ============================================================================
# 15. record_call_start without pipeline_run (None FK)
# ============================================================================


def test_record_call_start_accepts_null_pipeline_run_id(
    v18_conn: sqlite3.Connection,
) -> None:
    """The pipeline_run_id FK is nullable — CLI surfaces invoke outside
    pipeline runs (e.g., manual `swing schwab refresh-token`)."""
    conn = v18_conn
    try:
        call_id = record_call_start(
            conn,
            ts="2026-05-13T12:00:00",
            endpoint="oauth.refresh",
            pipeline_run_id=None,
            surface="cli",
            environment="sandbox",
        )
        row = conn.execute(
            "SELECT status, pipeline_run_id FROM schwab_api_calls "
            "WHERE call_id = ?",
            (call_id,),
        ).fetchone()
        assert row[0] == "in_flight"
        assert row[1] is None
    finally:
        conn.close()
