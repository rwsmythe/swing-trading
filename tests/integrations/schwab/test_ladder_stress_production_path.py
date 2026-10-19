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

D87 (load robustness): the holder is SYNCHRONISED, never slept on. It sets
``held`` only after its ``BEGIN IMMEDIATE`` has returned, and each test waits
on that event before the contended audit write runs. The old shape slept a
fixed 50 / 100 ms and hoped the holder had the lock by then; under xdist load
the holder thread had not reached RESERVED yet, the 1 ms audit write found no
contention, and ``pytest.raises`` reported DID NOT RAISE. For the same reason
the pre-fix holders hold until the test releases them (``_PRE_FIX_HOLD_BOUND``
is a hang guard, not a duration): a holder that times out on its own while a
loaded main thread is still on its way to the audit write is the same race
from the other side. The 1 ms ``busy_timeout`` is the tests' design (the
pre-fix shape) and is unchanged.
"""
import sqlite3
import threading
from pathlib import Path

import pytest

from swing.data.db import ensure_schema, open_connection
from swing.integrations.schwab import marketdata

# The holder's own wait for the test's release signal in the two pre-fix tests.
# Every test releases its holder in ``finally``; this bound only stops a broken
# test from leaving a thread holding the write lock forever.
_PRE_FIX_HOLD_BOUND = 30.0
# How long a test waits for the holder to report that it holds RESERVED.
_HELD_WAIT = 60.0


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


def _external_lock_holder(db: Path, hold_seconds: float, release_evt: threading.Event,
                          held_evt: threading.Event, errors: list[BaseException]):
    """Hold the SQLite write lock (simulating a candidates/archive/evaluate
    writer) until `release_evt` is set or `hold_seconds` pass, so an audit
    BEGIN IMMEDIATE must wait. `held_evt` is set only once BEGIN IMMEDIATE has
    RETURNED, i.e. once this connection owns RESERVED.

    Any exception raised in this thread is appended to `errors`, and the
    connection is closed in ``finally``. An exception escaping a thread is only
    a pytest warning, so each test asserts `errors` is empty after joining."""
    conn = None
    try:
        conn = open_connection(db, busy_timeout_ms=30000)
        conn.execute("BEGIN IMMEDIATE")  # RESERVED write lock; blocks other writers
        held_evt.set()
        release_evt.wait(timeout=hold_seconds)
        conn.commit()
    except BaseException as exc:  # noqa: BLE001 -- surfaced to the test via `errors`
        errors.append(exc)
    finally:
        if conn is not None:
            conn.close()


def _wait_held(held: threading.Event) -> None:
    assert held.wait(timeout=_HELD_WAIT), (
        f"the external holder did not report RESERVED within {_HELD_WAIT}s"
    )


def _assert_holder_clean(errors: list[BaseException]) -> None:
    assert errors == [], f"the external lock holder raised: {errors!r}"


def test_forced_start_lock_leaves_no_audit_row(tmp_path):
    # PRE-FIX shape: tiny busy_timeout + external holder during start ->
    # record_call_start's BEGIN IMMEDIATE times out BEFORE the insert commits.
    db = _db(tmp_path)
    release = threading.Event()
    held = threading.Event()
    holder_errors: list[BaseException] = []
    holder = threading.Thread(
        target=_external_lock_holder,
        args=(db, _PRE_FIX_HOLD_BOUND, release, held, holder_errors))
    holder.start()
    audit_conn = None
    try:
        _wait_held(held)  # the holder owns RESERVED before the 1 ms connection opens
        audit_conn = open_connection(db, busy_timeout_ms=1)  # 1ms -> times out
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
        if audit_conn is not None:
            audit_conn.close()
    _assert_holder_clean(holder_errors)


def test_forced_finish_lock_leaves_in_flight_row(tmp_path):
    # PRE-FIX shape: start commits (no contention), THEN an external holder grabs
    # the lock during the injected HTTP latency window so record_call_finish's
    # BEGIN IMMEDIATE times out -> the committed in_flight row REMAINS, unfinalized.
    db = _db(tmp_path)
    audit_conn = open_connection(db, busy_timeout_ms=1)
    release = threading.Event()
    held = threading.Event()
    holders: list[threading.Thread] = []
    holder_errors: list[BaseException] = []

    def _on_http():
        # spawn the lock holder mid-HTTP (record_call_start has committed), and
        # return only once it owns RESERVED, so finish contends
        holder = threading.Thread(
            target=_external_lock_holder,
            args=(db, _PRE_FIX_HOLD_BOUND, release, held, holder_errors))
        holders.append(holder)
        holder.start()
        _wait_held(held)

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
            "SELECT status, http_status FROM schwab_api_calls "
            "WHERE endpoint='marketdata.pricehistory'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "in_flight"
        assert rows[0][1] is None
    finally:
        release.set()
        for holder in holders:
            holder.join()
        audit_conn.close()
    _assert_holder_clean(holder_errors)


def test_post_fix_30s_all_attempts_complete(tmp_path):
    # POST-FIX: 30s busy_timeout + external holder that releases within budget ->
    # the audit writes drain and complete; no OperationalError.
    db = _db(tmp_path)
    audit_conn = open_connection(db, busy_timeout_ms=30000, check_same_thread=False)
    release = threading.Event()
    held = threading.Event()
    holder_errors: list[BaseException] = []
    holder = threading.Thread(
        target=_external_lock_holder, args=(db, 0.5, release, held, holder_errors))
    holder.start()
    try:
        _wait_held(held)  # the holder owns RESERVED before the audit write starts
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
    _assert_holder_clean(holder_errors)
