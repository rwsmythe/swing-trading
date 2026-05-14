"""Phase 11 T-A.8 — schwab_api_calls repo + SchwabApiCall dataclass tests.

Per plan §B.1 (repo signatures) + §H.7 (dataclass shape) + plan §Tasks-A T-A.8.

Validators tests assert __post_init__ rejects invalid values + accepts every
valid value of each CHECK-constrained field (endpoint, status, surface,
environment) plus the range-constrained / regex-constrained fields
(http_status, response_time_ms, signature_hash).

Repo function tests verify the 7 functions in §B.1. The discriminating
PK-preservation test (test_update_call_outcome_preserves_pk) locks the
"NEVER INSERT OR REPLACE" gotcha — a naive REPLACE-based update would
reassign the AUTOINCREMENT PK and the assertion would fail.

FK ON DELETE SET NULL test verifies CASCADE-style nullification with
PRAGMA foreign_keys=ON (already enabled by ensure_schema).

Caller-controlled tx discipline (mirror Phase 9 account_equity_snapshots
+ Finviz I1 lesson): repo functions DO NOT commit/rollback/BEGIN. The
test_no_internal_commit test pins the contract by attempting an explicit
COMMIT after the repo call — pre-fix (internal commit) the explicit
COMMIT would raise sqlite3.OperationalError.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import connect, ensure_schema
from swing.data.models import SchwabApiCall
from swing.data.repos.schwab_api_calls import (
    count_calls_by_status,
    get_call,
    insert_in_flight,
    list_recent_calls,
    update_call_linked_reconciliation_run,
    update_call_linked_snapshot,
    update_call_outcome,
)


# ============================================================================
# A. SchwabApiCall.__post_init__ validators (8 tests; 1 per field + sanity)
# ============================================================================


_VALID_ENDPOINTS = (
    "oauth.code_exchange", "oauth.refresh", "oauth.revoke",
    "accounts.linked", "accounts.details",
    "accounts.orders.list", "accounts.transactions.list",
    "marketdata.quotes", "marketdata.pricehistory",
)
_VALID_STATUSES = (
    "in_flight", "success", "error",
    "auth_failed", "rate_limited", "concurrent_refresh",
)


def _valid_kwargs(**overrides) -> dict:
    base = dict(
        call_id=None,
        ts="2026-05-13T12:00:00",
        endpoint="oauth.refresh",
        http_status=None,
        response_time_ms=None,
        rate_limit_remaining=None,
        signature_hash=None,
        status="in_flight",
        error_message=None,
        linked_snapshot_id=None,
        linked_reconciliation_run_id=None,
        pipeline_run_id=None,
        surface="pipeline",
        environment="sandbox",
    )
    base.update(overrides)
    return base


def test_endpoint_rejects_invalid_and_accepts_all_valid() -> None:
    """Discriminating: every CHECK-enum value works; one off-list rejected."""
    with pytest.raises(ValueError, match="endpoint"):
        SchwabApiCall(**_valid_kwargs(endpoint="bogus.endpoint"))
    for endpoint in _VALID_ENDPOINTS:
        # Should not raise.
        SchwabApiCall(**_valid_kwargs(endpoint=endpoint))


def test_status_rejects_invalid_and_accepts_all_valid() -> None:
    with pytest.raises(ValueError, match="status"):
        SchwabApiCall(**_valid_kwargs(status="completed"))
    for status in _VALID_STATUSES:
        SchwabApiCall(**_valid_kwargs(status=status))


def test_surface_rejects_invalid_and_accepts_pipeline_and_cli() -> None:
    with pytest.raises(ValueError, match="surface"):
        SchwabApiCall(**_valid_kwargs(surface="web"))
    SchwabApiCall(**_valid_kwargs(surface="pipeline"))
    SchwabApiCall(**_valid_kwargs(surface="cli"))


def test_environment_rejects_invalid_and_accepts_sandbox_and_production() -> None:
    with pytest.raises(ValueError, match="environment"):
        SchwabApiCall(**_valid_kwargs(environment="staging"))
    SchwabApiCall(**_valid_kwargs(environment="sandbox"))
    SchwabApiCall(**_valid_kwargs(environment="production"))


def test_http_status_range_validator() -> None:
    # Rejected:
    with pytest.raises(ValueError, match="http_status"):
        SchwabApiCall(**_valid_kwargs(http_status=99))
    with pytest.raises(ValueError, match="http_status"):
        SchwabApiCall(**_valid_kwargs(http_status=600))
    with pytest.raises(ValueError, match="http_status"):
        SchwabApiCall(**_valid_kwargs(http_status=-1))
    # Accepted:
    SchwabApiCall(**_valid_kwargs(http_status=None))
    SchwabApiCall(**_valid_kwargs(http_status=100))
    SchwabApiCall(**_valid_kwargs(http_status=599))
    SchwabApiCall(**_valid_kwargs(http_status=200))


def test_response_time_ms_non_negative_validator() -> None:
    with pytest.raises(ValueError, match="response_time_ms"):
        SchwabApiCall(**_valid_kwargs(response_time_ms=-1))
    SchwabApiCall(**_valid_kwargs(response_time_ms=None))
    SchwabApiCall(**_valid_kwargs(response_time_ms=0))
    SchwabApiCall(**_valid_kwargs(response_time_ms=1000))


def test_signature_hash_64char_lowercase_hex_validator() -> None:
    # Too short:
    with pytest.raises(ValueError, match="signature_hash"):
        SchwabApiCall(**_valid_kwargs(signature_hash="abc"))
    # Uppercase rejected (lowercase hex only):
    with pytest.raises(ValueError, match="signature_hash"):
        SchwabApiCall(**_valid_kwargs(signature_hash="A" * 64))
    # Non-hex character:
    with pytest.raises(ValueError, match="signature_hash"):
        SchwabApiCall(**_valid_kwargs(signature_hash="g" * 64))
    # Wrong length (63 chars, all hex):
    with pytest.raises(ValueError, match="signature_hash"):
        SchwabApiCall(**_valid_kwargs(signature_hash="a" * 63))
    # Accepted:
    SchwabApiCall(**_valid_kwargs(signature_hash=None))
    SchwabApiCall(**_valid_kwargs(signature_hash="a" * 64))
    SchwabApiCall(**_valid_kwargs(signature_hash="0123456789abcdef" * 4))


def test_full_valid_instance_constructs() -> None:
    """Sanity: every field populated with valid values does NOT raise."""
    call = SchwabApiCall(
        call_id=1,
        ts="2026-05-13T12:00:00",
        endpoint="marketdata.quotes",
        http_status=200,
        response_time_ms=145,
        rate_limit_remaining=99,
        signature_hash="0" * 64,
        status="success",
        error_message=None,
        linked_snapshot_id=42,
        linked_reconciliation_run_id=7,
        pipeline_run_id=11,
        surface="pipeline",
        environment="production",
    )
    assert call.endpoint == "marketdata.quotes"
    assert call.status == "success"


# ============================================================================
# Codex R1 Major #4 — close validator-coverage gap on 7 remaining fields
# ============================================================================


def test_call_id_validator_rejects_zero_negative_and_non_int_accepts_none_and_positive() -> None:
    """call_id: None pre-INSERT (accepted); positive int post-INSERT (accepted).
    Zero / negative / non-int (e.g. str) rejected.
    """
    # Rejected.
    with pytest.raises(ValueError, match="call_id"):
        SchwabApiCall(**_valid_kwargs(call_id=0))
    with pytest.raises(ValueError, match="call_id"):
        SchwabApiCall(**_valid_kwargs(call_id=-1))
    with pytest.raises(ValueError, match="call_id"):
        SchwabApiCall(**_valid_kwargs(call_id="1"))
    # Booleans are int subclasses in Python; we reject them explicitly.
    with pytest.raises(ValueError, match="call_id"):
        SchwabApiCall(**_valid_kwargs(call_id=True))
    # Accepted.
    SchwabApiCall(**_valid_kwargs(call_id=None))
    SchwabApiCall(**_valid_kwargs(call_id=1))
    SchwabApiCall(**_valid_kwargs(call_id=12345))


def test_ts_validator_rejects_empty_and_unparseable_accepts_iso8601() -> None:
    """ts: non-empty ISO 8601 parseable string. Empty string + None +
    free-text rejected.
    """
    # Rejected.
    with pytest.raises(ValueError, match="ts"):
        SchwabApiCall(**_valid_kwargs(ts=""))
    with pytest.raises(ValueError, match="ts"):
        SchwabApiCall(**_valid_kwargs(ts=None))
    with pytest.raises(ValueError, match="ts"):
        SchwabApiCall(**_valid_kwargs(ts="not-a-timestamp"))
    # Accepted: naked ISO; with microseconds; with offset.
    SchwabApiCall(**_valid_kwargs(ts="2026-05-13T12:00:00"))
    SchwabApiCall(**_valid_kwargs(ts="2026-05-13T12:00:00.123456"))
    SchwabApiCall(**_valid_kwargs(ts="2026-05-13T12:00:00+00:00"))


def test_rate_limit_remaining_validator_rejects_negative_accepts_none_and_zero_plus() -> None:
    """rate_limit_remaining: None or >= 0; no upper bound."""
    with pytest.raises(ValueError, match="rate_limit_remaining"):
        SchwabApiCall(**_valid_kwargs(rate_limit_remaining=-1))
    SchwabApiCall(**_valid_kwargs(rate_limit_remaining=None))
    SchwabApiCall(**_valid_kwargs(rate_limit_remaining=0))
    SchwabApiCall(**_valid_kwargs(rate_limit_remaining=120))
    SchwabApiCall(**_valid_kwargs(rate_limit_remaining=999_999))


def test_rate_limit_remaining_validator_rejects_bool_and_non_int() -> None:
    """Codex R2 Minor #1: bool is an int subclass; reject explicitly.
    Non-int values (str, float) must raise controlled ValueError, NOT
    TypeError on the `< 0` comparison.

    Discriminating: pre-fix the validator only checked `< 0`. `True`
    passed (bool < 0 is False); `"5"` and `1.5` would either be accepted
    (when comparable to 0) or raise TypeError. Post-fix all three raise
    ValueError with "rate_limit_remaining" in the message.
    """
    # Rejected: bool is int subclass.
    with pytest.raises(ValueError, match="rate_limit_remaining"):
        SchwabApiCall(**_valid_kwargs(rate_limit_remaining=True))
    with pytest.raises(ValueError, match="rate_limit_remaining"):
        SchwabApiCall(**_valid_kwargs(rate_limit_remaining=False))
    # Rejected: str / float — controlled ValueError, not TypeError.
    with pytest.raises(ValueError, match="rate_limit_remaining"):
        SchwabApiCall(**_valid_kwargs(rate_limit_remaining="5"))
    with pytest.raises(ValueError, match="rate_limit_remaining"):
        SchwabApiCall(**_valid_kwargs(rate_limit_remaining=1.5))
    # Accepted: None / 0 / positive int.
    SchwabApiCall(**_valid_kwargs(rate_limit_remaining=None))
    SchwabApiCall(**_valid_kwargs(rate_limit_remaining=0))
    SchwabApiCall(**_valid_kwargs(rate_limit_remaining=100))


def test_error_message_validator_rejects_non_string_accepts_none_and_string() -> None:
    """error_message: None or str. No length cap (redaction layer truncates)."""
    with pytest.raises(ValueError, match="error_message"):
        SchwabApiCall(**_valid_kwargs(error_message=123))
    with pytest.raises(ValueError, match="error_message"):
        SchwabApiCall(**_valid_kwargs(error_message=["list", "rejected"]))
    SchwabApiCall(**_valid_kwargs(error_message=None))
    SchwabApiCall(**_valid_kwargs(error_message=""))
    SchwabApiCall(**_valid_kwargs(error_message="<redacted body of 84 bytes>"))


def test_linked_snapshot_id_validator() -> None:
    """linked_snapshot_id: None or positive int. Zero / negative rejected."""
    with pytest.raises(ValueError, match="linked_snapshot_id"):
        SchwabApiCall(**_valid_kwargs(linked_snapshot_id=0))
    with pytest.raises(ValueError, match="linked_snapshot_id"):
        SchwabApiCall(**_valid_kwargs(linked_snapshot_id=-5))
    with pytest.raises(ValueError, match="linked_snapshot_id"):
        SchwabApiCall(**_valid_kwargs(linked_snapshot_id="1"))
    with pytest.raises(ValueError, match="linked_snapshot_id"):
        SchwabApiCall(**_valid_kwargs(linked_snapshot_id=True))
    SchwabApiCall(**_valid_kwargs(linked_snapshot_id=None))
    SchwabApiCall(**_valid_kwargs(linked_snapshot_id=1))


def test_linked_reconciliation_run_id_validator() -> None:
    """linked_reconciliation_run_id: None or positive int."""
    with pytest.raises(ValueError, match="linked_reconciliation_run_id"):
        SchwabApiCall(**_valid_kwargs(linked_reconciliation_run_id=0))
    with pytest.raises(ValueError, match="linked_reconciliation_run_id"):
        SchwabApiCall(**_valid_kwargs(linked_reconciliation_run_id=-1))
    with pytest.raises(ValueError, match="linked_reconciliation_run_id"):
        SchwabApiCall(**_valid_kwargs(linked_reconciliation_run_id=1.5))
    SchwabApiCall(**_valid_kwargs(linked_reconciliation_run_id=None))
    SchwabApiCall(**_valid_kwargs(linked_reconciliation_run_id=7))


def test_pipeline_run_id_validator() -> None:
    """pipeline_run_id: None or positive int."""
    with pytest.raises(ValueError, match="pipeline_run_id"):
        SchwabApiCall(**_valid_kwargs(pipeline_run_id=0))
    with pytest.raises(ValueError, match="pipeline_run_id"):
        SchwabApiCall(**_valid_kwargs(pipeline_run_id=-2))
    with pytest.raises(ValueError, match="pipeline_run_id"):
        SchwabApiCall(**_valid_kwargs(pipeline_run_id="abc"))
    SchwabApiCall(**_valid_kwargs(pipeline_run_id=None))
    SchwabApiCall(**_valid_kwargs(pipeline_run_id=42))


# ============================================================================
# B. Repo function tests (10 tests)
# ============================================================================


@pytest.fixture
def v18_conn(tmp_path: Path) -> sqlite3.Connection:
    """v18 DB with PRAGMA foreign_keys=ON (set by ensure_schema)."""
    return ensure_schema(tmp_path / "schwab-test.db")


def _seed_pipeline_run(conn: sqlite3.Connection, *, run_id: int | None = None) -> int:
    """Insert a minimal pipeline_runs row for FK satisfaction; return id."""
    if run_id is None:
        cur = conn.execute(
            "INSERT INTO pipeline_runs ("
            "started_ts, trigger, data_asof_date, action_session_date, "
            "state, lease_token"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            ("2026-05-13T08:00:00", "manual", "2026-05-12", "2026-05-13",
             "running", "test-token"),
        )
        return int(cur.lastrowid)
    cur = conn.execute(
        "INSERT INTO pipeline_runs ("
        "id, started_ts, trigger, data_asof_date, action_session_date, "
        "state, lease_token"
        ") VALUES (?, ?, ?, ?, ?, ?, ?)",
        (run_id, "2026-05-13T08:00:00", "manual", "2026-05-12", "2026-05-13",
         "running", "test-token-fixed"),
    )
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
    return int(cur.lastrowid)


def _seed_reconciliation_run(conn: sqlite3.Connection) -> int:
    """Insert a minimal reconciliation_runs row; return run_id."""
    cur = conn.execute(
        "INSERT INTO reconciliation_runs ("
        "started_ts, source, period_start, period_end, state"
        ") VALUES (?, ?, ?, ?, ?)",
        ("2026-05-13T12:00:00", "tos_csv", "2026-05-06", "2026-05-13", "completed"),
    )
    return int(cur.lastrowid)


def test_insert_in_flight_returns_int_and_persists_row(
    v18_conn: sqlite3.Connection,
) -> None:
    """insert_in_flight returns positive int call_id + row exists with status='in_flight'."""
    conn = v18_conn
    try:
        pipeline_run_id = _seed_pipeline_run(conn)
        call_id = insert_in_flight(
            conn,
            ts="2026-05-13T12:00:00",
            endpoint="oauth.refresh",
            pipeline_run_id=pipeline_run_id,
            surface="pipeline",
            environment="sandbox",
        )
        assert isinstance(call_id, int)
        assert call_id >= 1
        row = conn.execute(
            "SELECT call_id, ts, endpoint, status, pipeline_run_id, surface, environment "
            "FROM schwab_api_calls WHERE call_id = ?",
            (call_id,),
        ).fetchone()
        assert row is not None
        assert row[0] == call_id
        assert row[1] == "2026-05-13T12:00:00"
        assert row[2] == "oauth.refresh"
        assert row[3] == "in_flight"
        assert row[4] == pipeline_run_id
        assert row[5] == "pipeline"
        assert row[6] == "sandbox"
    finally:
        conn.close()


def test_update_call_outcome_preserves_pk(v18_conn: sqlite3.Connection) -> None:
    """DISCRIMINATING per plan §Tasks-A T-A.8 + CLAUDE.md INSERT-OR-REPLACE gotcha:
    update_call_outcome must UPDATE in place — the PK after update equals the
    call_id returned by INSERT. A REPLACE-based implementation would reassign
    the AUTOINCREMENT PK on update; this test would fail.
    """
    conn = v18_conn
    try:
        pipeline_run_id = _seed_pipeline_run(conn)
        original_call_id = insert_in_flight(
            conn,
            ts="2026-05-13T12:00:00",
            endpoint="oauth.refresh",
            pipeline_run_id=pipeline_run_id,
            surface="pipeline",
            environment="sandbox",
        )
        update_call_outcome(
            conn,
            call_id=original_call_id,
            http_status=200,
            response_time_ms=145,
            rate_limit_remaining=99,
            signature_hash="a" * 64,
            status="success",
            error_message=None,
        )
        # PK MUST be preserved — pre-fix REPLACE would yield a different ID.
        row = conn.execute(
            "SELECT call_id, status, http_status, response_time_ms, "
            "rate_limit_remaining, signature_hash "
            "FROM schwab_api_calls"
        ).fetchall()
        assert len(row) == 1, (
            "REPLACE would leave duplicate rows or reissue PK; UPDATE preserves single row."
        )
        assert row[0][0] == original_call_id, (
            "PK MUST be preserved across update — INSERT OR REPLACE forbidden."
        )
        assert row[0][1] == "success"
        assert row[0][2] == 200
        assert row[0][3] == 145
        assert row[0][4] == 99
        assert row[0][5] == "a" * 64
    finally:
        conn.close()


def test_update_call_linked_snapshot_only_changes_that_field(
    v18_conn: sqlite3.Connection,
) -> None:
    """update_call_linked_snapshot updates only linked_snapshot_id; preserves rest."""
    conn = v18_conn
    try:
        pipeline_run_id = _seed_pipeline_run(conn)
        call_id = insert_in_flight(
            conn,
            ts="2026-05-13T12:00:00",
            endpoint="accounts.details",
            pipeline_run_id=pipeline_run_id,
            surface="cli",
            environment="production",
        )
        update_call_outcome(
            conn,
            call_id=call_id,
            http_status=200,
            response_time_ms=200,
            rate_limit_remaining=50,
            signature_hash=None,
            status="success",
            error_message=None,
        )
        snapshot_id = _seed_account_equity_snapshot(conn)
        update_call_linked_snapshot(
            conn, call_id=call_id, snapshot_id=snapshot_id,
        )
        row = conn.execute(
            "SELECT call_id, ts, endpoint, http_status, response_time_ms, "
            "status, surface, environment, linked_snapshot_id "
            "FROM schwab_api_calls WHERE call_id = ?",
            (call_id,),
        ).fetchone()
        assert row[0] == call_id
        assert row[1] == "2026-05-13T12:00:00"
        assert row[2] == "accounts.details"
        assert row[3] == 200  # http_status preserved
        assert row[4] == 200  # response_time_ms preserved
        assert row[5] == "success"  # status preserved
        assert row[6] == "cli"  # surface preserved
        assert row[7] == "production"  # environment preserved
        assert row[8] == snapshot_id  # linked_snapshot_id updated
    finally:
        conn.close()


def test_update_call_linked_reconciliation_run_only_changes_that_field(
    v18_conn: sqlite3.Connection,
) -> None:
    conn = v18_conn
    try:
        pipeline_run_id = _seed_pipeline_run(conn)
        call_id = insert_in_flight(
            conn,
            ts="2026-05-13T12:00:00",
            endpoint="accounts.transactions.list",
            pipeline_run_id=pipeline_run_id,
            surface="pipeline",
            environment="sandbox",
        )
        update_call_outcome(
            conn,
            call_id=call_id,
            http_status=200,
            response_time_ms=300,
            rate_limit_remaining=42,
            signature_hash=None,
            status="success",
            error_message=None,
        )
        run_id = _seed_reconciliation_run(conn)
        update_call_linked_reconciliation_run(
            conn, call_id=call_id, reconciliation_run_id=run_id,
        )
        row = conn.execute(
            "SELECT status, linked_reconciliation_run_id, linked_snapshot_id "
            "FROM schwab_api_calls WHERE call_id = ?",
            (call_id,),
        ).fetchone()
        assert row[0] == "success"
        assert row[1] == run_id
        assert row[2] is None  # unchanged
    finally:
        conn.close()


def test_list_recent_calls_orders_by_ts_desc_and_honors_limit(
    v18_conn: sqlite3.Connection,
) -> None:
    conn = v18_conn
    try:
        pr = _seed_pipeline_run(conn)
        for ts in ("2026-05-10T12:00:00", "2026-05-12T12:00:00",
                   "2026-05-11T12:00:00", "2026-05-13T12:00:00",
                   "2026-05-09T12:00:00"):
            insert_in_flight(
                conn, ts=ts, endpoint="oauth.refresh",
                pipeline_run_id=pr, surface="pipeline", environment="sandbox",
            )
        results = list_recent_calls(
            conn, since_ts="2026-05-01T00:00:00",
            surface_filter=None, environment_filter=None, limit=3,
        )
        assert len(results) == 3
        timestamps = [c.ts for c in results]
        assert timestamps == [
            "2026-05-13T12:00:00",
            "2026-05-12T12:00:00",
            "2026-05-11T12:00:00",
        ]
        # since_ts filter works:
        recent = list_recent_calls(
            conn, since_ts="2026-05-12T00:00:00",
            surface_filter=None, environment_filter=None, limit=10,
        )
        assert len(recent) == 2
    finally:
        conn.close()


def test_list_recent_calls_surface_filter(v18_conn: sqlite3.Connection) -> None:
    conn = v18_conn
    try:
        pr = _seed_pipeline_run(conn)
        for surface in ("cli", "cli", "cli", "pipeline", "pipeline"):
            insert_in_flight(
                conn, ts="2026-05-13T12:00:00",
                endpoint="oauth.refresh", pipeline_run_id=pr,
                surface=surface, environment="sandbox",
            )
        cli_results = list_recent_calls(
            conn, since_ts="2026-05-01T00:00:00",
            surface_filter="cli", environment_filter=None, limit=10,
        )
        assert len(cli_results) == 3
        assert all(c.surface == "cli" for c in cli_results)
        pipeline_results = list_recent_calls(
            conn, since_ts="2026-05-01T00:00:00",
            surface_filter="pipeline", environment_filter=None, limit=10,
        )
        assert len(pipeline_results) == 2
    finally:
        conn.close()


def test_list_recent_calls_environment_filter(v18_conn: sqlite3.Connection) -> None:
    conn = v18_conn
    try:
        pr = _seed_pipeline_run(conn)
        for env in ("sandbox", "sandbox", "production", "production", "production"):
            insert_in_flight(
                conn, ts="2026-05-13T12:00:00",
                endpoint="oauth.refresh", pipeline_run_id=pr,
                surface="pipeline", environment=env,
            )
        sandbox_results = list_recent_calls(
            conn, since_ts="2026-05-01T00:00:00",
            surface_filter=None, environment_filter="sandbox", limit=10,
        )
        assert len(sandbox_results) == 2
        prod_results = list_recent_calls(
            conn, since_ts="2026-05-01T00:00:00",
            surface_filter=None, environment_filter="production", limit=10,
        )
        assert len(prod_results) == 3
    finally:
        conn.close()


def test_get_call_returns_none_for_unknown_id(v18_conn: sqlite3.Connection) -> None:
    conn = v18_conn
    try:
        assert get_call(conn, call_id=999) is None
        # Round-trip: insert + read = same row.
        pr = _seed_pipeline_run(conn)
        call_id = insert_in_flight(
            conn, ts="2026-05-13T12:00:00",
            endpoint="marketdata.quotes", pipeline_run_id=pr,
            surface="pipeline", environment="sandbox",
        )
        result = get_call(conn, call_id=call_id)
        assert result is not None
        assert result.call_id == call_id
        assert result.endpoint == "marketdata.quotes"
        assert result.status == "in_flight"
    finally:
        conn.close()


def test_count_calls_by_status(v18_conn: sqlite3.Connection) -> None:
    conn = v18_conn
    try:
        pr = _seed_pipeline_run(conn)
        # 2 in-flight, 3 success, 1 error.
        for _ in range(2):
            insert_in_flight(
                conn, ts="2026-05-13T12:00:00",
                endpoint="oauth.refresh", pipeline_run_id=pr,
                surface="pipeline", environment="sandbox",
            )
        for _ in range(3):
            cid = insert_in_flight(
                conn, ts="2026-05-13T12:00:00",
                endpoint="oauth.refresh", pipeline_run_id=pr,
                surface="pipeline", environment="sandbox",
            )
            update_call_outcome(
                conn, call_id=cid, http_status=200, response_time_ms=100,
                rate_limit_remaining=99, signature_hash=None,
                status="success", error_message=None,
            )
        cid_err = insert_in_flight(
            conn, ts="2026-05-13T12:00:00",
            endpoint="oauth.refresh", pipeline_run_id=pr,
            surface="pipeline", environment="sandbox",
        )
        update_call_outcome(
            conn, call_id=cid_err, http_status=500, response_time_ms=100,
            rate_limit_remaining=99, signature_hash=None,
            status="error", error_message="boom",
        )
        assert count_calls_by_status(
            conn, status_filter="in_flight", since_ts="2026-05-01T00:00:00",
        ) == 2
        assert count_calls_by_status(
            conn, status_filter="success", since_ts="2026-05-01T00:00:00",
        ) == 3
        assert count_calls_by_status(
            conn, status_filter="error", since_ts="2026-05-01T00:00:00",
        ) == 1
        # since_ts excludes earlier rows:
        assert count_calls_by_status(
            conn, status_filter="success", since_ts="2026-06-01T00:00:00",
        ) == 0
    finally:
        conn.close()


def test_fk_on_delete_set_null_for_pipeline_run(
    v18_conn: sqlite3.Connection,
) -> None:
    """FK ON DELETE SET NULL: when the referenced pipeline_run is deleted, the
    schwab_api_calls.pipeline_run_id column nullifies (does NOT cascade-delete
    the audit row). Requires PRAGMA foreign_keys=ON — set by ensure_schema."""
    conn = v18_conn
    try:
        # Verify FK PRAGMA is ON.
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        pr_id = _seed_pipeline_run(conn)
        call_id = insert_in_flight(
            conn, ts="2026-05-13T12:00:00",
            endpoint="oauth.refresh", pipeline_run_id=pr_id,
            surface="pipeline", environment="sandbox",
        )
        # Sanity: FK populated.
        assert conn.execute(
            "SELECT pipeline_run_id FROM schwab_api_calls WHERE call_id = ?",
            (call_id,),
        ).fetchone()[0] == pr_id
        # Delete the pipeline_runs row; FK should nullify the column.
        conn.execute("DELETE FROM pipeline_runs WHERE id = ?", (pr_id,))
        # Row still exists; column nullified.
        row = conn.execute(
            "SELECT call_id, pipeline_run_id FROM schwab_api_calls WHERE call_id = ?",
            (call_id,),
        ).fetchone()
        assert row is not None
        assert row[0] == call_id
        assert row[1] is None
    finally:
        conn.close()


# ============================================================================
# C. Caller-controlled tx discipline (bonus — Finviz I1 lesson family)
# ============================================================================


def test_insert_in_flight_does_not_commit_internally(tmp_path: Path) -> None:
    """Discriminating: repo must NOT call conn.commit() internally.

    Mirror Finviz `test_insert_call_does_not_commit_internally` precedent —
    repo writes inside an outer BEGIN IMMEDIATE / COMMIT context (per future
    T-A.9 service layer using lease.fenced_write or direct BEGIN IMMEDIATE).
    Pre-fix (internal commit): explicit COMMIT raises OperationalError.
    Post-fix: explicit COMMIT succeeds.
    """
    db_path = tmp_path / "schwab-test.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    conn.isolation_level = None
    try:
        # Seed a pipeline_runs row first so FK satisfied.
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO pipeline_runs ("
            "started_ts, trigger, data_asof_date, action_session_date, "
            "state, lease_token"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            ("2026-05-13T08:00:00", "manual", "2026-05-12", "2026-05-13",
             "running", "test-token"),
        )
        pipeline_run_id = int(conn.execute(
            "SELECT id FROM pipeline_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()[0])
        insert_in_flight(
            conn, ts="2026-05-13T12:00:00",
            endpoint="oauth.refresh",
            pipeline_run_id=pipeline_run_id,
            surface="pipeline", environment="sandbox",
        )
        # Pre-fix: internal commit closes the transaction → COMMIT raises.
        # Post-fix: succeeds.
        conn.execute("COMMIT")
        # Verify row persisted via fresh connection.
        with sqlite3.connect(db_path) as fresh:
            count = fresh.execute(
                "SELECT COUNT(*) FROM schwab_api_calls"
            ).fetchone()[0]
        assert count == 1
    finally:
        conn.close()
