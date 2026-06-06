"""Task 7 -- production-path concurrency stress, split by failure point.

Drives the REAL record_call_start -> HTTP -> record_call_finish sequence through
``marketdata.get_price_history`` under concurrency, splitting the pre-fix
assertion by WHERE the audit BEGIN IMMEDIATE loses the write lock (Codex R2
major #4: record_call_start commits before the HTTP, so "no audit row" is only
correct for a START-lock; a FINISH-lock leaves a committed in_flight row).

ARITHMETIC (feedback_regression_test_arithmetic): the discriminator is
``busy_timeout_ms``. At 1 ms the audit BEGIN IMMEDIATE times out while the
external holder (>=0.5 s) owns the write lock -> OperationalError (pre-fix shape).
At 30000 ms the same holder releases at 0.5 s -> the audit write drains and
succeeds (post-fix). The two regimes flip the outcome on the timeout value alone.

Note vs the plan draft: the external holder grabs the write lock with a bare
``BEGIN IMMEDIATE`` (no INSERT) -- a RESERVED lock blocks another BEGIN IMMEDIATE
regardless, and avoids both the schwab_api_calls.endpoint CHECK constraint and
contaminating the ``marketdata.pricehistory`` row count.
"""
import sqlite3
import threading
import time
import pytest
from pathlib import Path
from swing.data.db import ensure_schema, open_connection
from swing.integrations.schwab import marketdata


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    return db


_VALID_PAYLOAD = {
    "symbol": "AAPL",
    "empty": False,
    "candles": [
        {
            "open": 149.0, "high": 151.0, "low": 148.5,
            "close": 150.0, "volume": 50_000_000,
            "datetime": 1715520000000,
        },
    ],
}


class _StubClient:
    """Minimal schwabdev stand-in. ``price_history`` absorbs the camelCase
    kwargs the wrapper passes and returns a valid raw-dict candles payload.

    ``on_http`` (optional) is invoked INSIDE the simulated HTTP call so a test
    can interleave an external lock holder between record_call_start (already
    committed) and record_call_finish (the finish-lock case).
    """

    def __init__(self, on_http=None):
        self._on_http = on_http

    def price_history(self, symbol, **kwargs):
        if self._on_http is not None:
            self._on_http()
        return dict(_VALID_PAYLOAD, symbol=symbol)


def _external_lock_holder(db: Path, hold_seconds: float, release_evt: threading.Event):
    """Hold the SQLite write lock for `hold_seconds` (simulating a candidates/
    archive/evaluate writer) so an audit BEGIN IMMEDIATE must wait."""
    conn = open_connection(db, busy_timeout_ms=30000)
    conn.execute("BEGIN IMMEDIATE")  # RESERVED write lock; blocks other writers
    release_evt.wait(timeout=hold_seconds)
    conn.commit()
    conn.close()


def test_forced_start_lock_leaves_no_audit_row(tmp_path):
    # PRE-FIX shape: tiny busy_timeout + external holder during start ->
    # record_call_start's BEGIN IMMEDIATE times out BEFORE the insert commits.
    db = _db(tmp_path)
    audit_conn = open_connection(db, busy_timeout_ms=1)  # 1ms -> times out
    release = threading.Event()
    holder = threading.Thread(target=_external_lock_holder, args=(db, 2.0, release))
    holder.start()
    time.sleep(0.05)  # ensure the holder owns the lock first
    try:
        with pytest.raises(sqlite3.OperationalError):
            marketdata.get_price_history(
                _StubClient(), audit_conn, "AAPL",
                period_type="year", period=5, frequency_type="daily", frequency=1,
                start_dt=None, end_dt=None, surface="pipeline",
                environment="production", pipeline_run_id=None,
            )
        # start never committed -> no audit row
        count = audit_conn.execute(
            "SELECT COUNT(*) FROM schwab_api_calls WHERE endpoint='marketdata.pricehistory'"
        ).fetchone()[0]
        assert count == 0
    finally:
        release.set()
        holder.join()
        audit_conn.close()


def test_forced_finish_lock_leaves_in_flight_row(tmp_path):
    # PRE-FIX shape: start commits (no contention), THEN an external holder grabs
    # the lock during the injected HTTP latency window so record_call_finish's
    # BEGIN IMMEDIATE times out -> the committed in_flight row REMAINS, unfinalized.
    db = _db(tmp_path)
    audit_conn = open_connection(db, busy_timeout_ms=1)
    release = threading.Event()

    def _on_http():
        # spawn the lock holder mid-HTTP, then let finish contend
        holder = threading.Thread(target=_external_lock_holder, args=(db, 2.0, release))
        holder.start()
        time.sleep(0.1)
        return holder

    client = _StubClient(on_http=_on_http)
    try:
        with pytest.raises(sqlite3.OperationalError):
            marketdata.get_price_history(
                client, audit_conn, "MSFT",
                period_type="year", period=5, frequency_type="daily", frequency=1,
                start_dt=None, end_dt=None, surface="pipeline",
                environment="production", pipeline_run_id=None,
            )
        # start committed -> exactly one in_flight row, terminal fields NULL
        rows = audit_conn.execute(
            "SELECT status, http_status FROM schwab_api_calls WHERE endpoint='marketdata.pricehistory'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "in_flight"
        assert rows[0][1] is None
    finally:
        release.set()
        audit_conn.close()


def test_post_fix_30s_all_attempts_complete(tmp_path):
    # POST-FIX: 30s busy_timeout + external holder that releases within budget ->
    # the audit writes drain and complete; no OperationalError.
    db = _db(tmp_path)
    audit_conn = open_connection(db, busy_timeout_ms=30000, check_same_thread=False)
    release = threading.Event()
    holder = threading.Thread(target=_external_lock_holder, args=(db, 0.5, release))
    holder.start()
    time.sleep(0.05)
    try:
        # Should NOT raise -- waits up to 30s, holder releases at 0.5s.
        result = marketdata.get_price_history(
            _StubClient(), audit_conn, "NVDA",
            period_type="year", period=5, frequency_type="daily", frequency=1,
            start_dt=None, end_dt=None, surface="pipeline",
            environment="production", pipeline_run_id=None,
        )
        assert result is not None
        rows = audit_conn.execute(
            "SELECT status FROM schwab_api_calls WHERE endpoint='marketdata.pricehistory'"
        ).fetchall()
        assert len(rows) == 1 and rows[0][0] == "success"
    finally:
        release.set()
        holder.join()
        audit_conn.close()
