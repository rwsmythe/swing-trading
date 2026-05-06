from pathlib import Path

from swing.data.db import connect, ensure_schema
from swing.data.models import FinvizApiCall
from swing.data.repos.finviz_api_calls import (
    get_latest_signature_hash,
    insert_call,
    list_recent_calls,
)


def _insert(conn, **overrides) -> FinvizApiCall:
    base = dict(
        call_id=None, ts="2026-05-05T12:00:00", screen_query="v=152&f=cap_largeover",
        status="ok", row_count=42, response_time_ms=180,
        rate_limit_remaining=99, signature_hash="abc123def456", error_message=None,
    )
    base.update(overrides)
    call = FinvizApiCall(**base)
    new_id = insert_call(conn, call)
    return FinvizApiCall(**{**base, "call_id": new_id})


def test_insert_call_assigns_autoincrement_id(tmp_path: Path) -> None:
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        call = _insert(conn)
        assert isinstance(call.call_id, int)
        assert call.call_id >= 1
    finally:
        conn.close()


def test_list_recent_calls_orders_by_ts_desc(tmp_path: Path) -> None:
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        _insert(conn, ts="2026-05-01T12:00:00", signature_hash="old")
        _insert(conn, ts="2026-05-05T12:00:00", signature_hash="new")
        _insert(conn, ts="2026-05-03T12:00:00", signature_hash="mid")
        calls = list_recent_calls(conn, limit=10)
        assert [c.signature_hash for c in calls] == ["new", "mid", "old"]
    finally:
        conn.close()


def test_get_latest_signature_hash_filters_by_screen_query(tmp_path: Path) -> None:
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        _insert(conn, ts="2026-05-05T10:00:00", screen_query="v=152", signature_hash="A")
        _insert(conn, ts="2026-05-05T11:00:00", screen_query="v=200", signature_hash="B")
        _insert(conn, ts="2026-05-05T12:00:00", screen_query="v=152", signature_hash="C")
        _insert(conn, ts="2026-05-05T13:00:00", screen_query="v=200", signature_hash="D")

        assert get_latest_signature_hash(conn, screen_query="v=152") == "C"
        assert get_latest_signature_hash(conn, screen_query="v=200") == "D"
        assert get_latest_signature_hash(conn, screen_query="v=999") is None
    finally:
        conn.close()


def test_get_latest_signature_hash_skips_error_rows(tmp_path: Path) -> None:
    """Discriminating: error rows have signature_hash=NULL; the helper must
    return the latest non-NULL hash, not the latest row irrespective of hash."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        _insert(conn, ts="2026-05-05T10:00:00", screen_query="v=152",
                status="ok", signature_hash="GOOD")
        _insert(conn, ts="2026-05-05T11:00:00", screen_query="v=152",
                status="error", signature_hash=None, error_message="boom")
        _insert(conn, ts="2026-05-05T12:00:00", screen_query="v=152",
                status="skipped_manual_override", signature_hash=None)
        assert get_latest_signature_hash(conn, screen_query="v=152") == "GOOD"
    finally:
        conn.close()


def test_list_recent_calls_tiebreaks_by_call_id_when_ts_equal(tmp_path: Path) -> None:
    """Codex R3 Major-1: audit ts is recorded with second precision; two rows
    inserted in the same second MUST be returned in deterministic order
    (newest insert first) so the CLI's just-inserted-row lookup is correct.

    Discriminating pre-fix (ORDER BY ts DESC alone): SQLite is free to return
    either ordering — the test would be flaky.
    Discriminating post-fix (ORDER BY ts DESC, call_id DESC): the AUTOINCREMENT
    call_id strictly increases, so the most-recently inserted row wins.
    """
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        a = _insert(conn, ts="2026-05-05T12:00:00", signature_hash="A_first")
        b = _insert(conn, ts="2026-05-05T12:00:00", signature_hash="B_second")
        c = _insert(conn, ts="2026-05-05T12:00:00", signature_hash="C_third")
        # Sanity: autoincrement strictly increases.
        assert a.call_id < b.call_id < c.call_id

        calls = list_recent_calls(conn, limit=10)
        # Discriminating: order is c -> b -> a (newest insert first).
        assert [c_.signature_hash for c_ in calls] == [
            "C_third", "B_second", "A_first",
        ]
    finally:
        conn.close()


def test_get_latest_signature_hash_tiebreaks_by_call_id_when_ts_equal(
    tmp_path: Path,
) -> None:
    """Codex R3 Major-1: drift-detection comparison must be against the
    most-recently inserted row when two rows share a second-precision ts.
    """
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        _insert(conn, ts="2026-05-05T12:00:00", screen_query="v=152",
                status="ok", signature_hash="OLD")
        _insert(conn, ts="2026-05-05T12:00:00", screen_query="v=152",
                status="ok", signature_hash="NEW")
        # Discriminating post-fix: returns the newer-inserted row's signature.
        assert get_latest_signature_hash(conn, screen_query="v=152") == "NEW"
    finally:
        conn.close()


def test_insert_call_does_not_commit_internally(tmp_path: Path) -> None:
    """Discriminating: insert_call must NOT call conn.commit() internally.

    The lease.fenced_write() context manager in swing/pipeline/lease.py owns
    explicit transaction control via BEGIN IMMEDIATE + COMMIT. If insert_call
    commits internally, the outer COMMIT raises sqlite3.OperationalError
    ("cannot commit - no transaction is active") and the subsequent ROLLBACK
    fails identically — operator-witnessed in S3 of the executing-plans gate
    (2026-05-06; code-review I1 fix).

    This test mirrors fenced_write's setup (isolation_level=None + explicit
    BEGIN IMMEDIATE) on a non-fenced path to isolate the repo-level contract.
    Pre-fix: insert_call's internal `conn.commit()` closes the transaction →
    the explicit COMMIT below raises. Post-fix: insert_call leaves the
    transaction open → the explicit COMMIT succeeds.
    """
    import sqlite3

    db_path = tmp_path / "swing.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    conn.isolation_level = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        _insert(conn)
        # Pre-fix raises sqlite3.OperationalError; post-fix succeeds.
        conn.execute("COMMIT")
        # Verify row persisted via fresh connection (rules out
        # read-your-own-writes false positive).
        with sqlite3.connect(db_path) as fresh:
            count = fresh.execute(
                "SELECT COUNT(*) FROM finviz_api_calls"
            ).fetchone()[0]
        assert count == 1
    finally:
        conn.close()
