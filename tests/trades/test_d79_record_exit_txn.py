"""D79 T1 -- ``record_exit`` owns ONE ``BEGIN IMMEDIATE`` and rejects a
caller-held transaction (CHARC K1 (1); the D73 shape, CHARC P1).

Plan: ``docs/superpowers/plans/2026-10-19-d79-exit-identity.plan.md`` T1.

The BARRIER HARNESS (``run_race``) is shared with T2-a
(``tests/trades/test_d79_record_exit_identity.py``). It orders the race by
EVENTS, never by sleeps:

* call 1's ``insert_fill_with_event`` runs the REAL insert first, so call 1
  holds the write lock under BOTH the pre-fix (deferred ``with conn:``) and
  the post-fix (``BEGIN IMMEDIATE``) shape; it then starts call 2 on a thread
  and waits up to 2.0 s on ``read_done`` before returning (and committing);
* call 2's FIRST ``get_trade`` / ``recorded_exit_identities`` appends
  ``"read"`` and sets ``read_done``;
* call 1's commit appends ``"commit1"`` (a connection proxy).

Pre-fix the read is outside any transaction, so ``"read"`` precedes
``"commit1"``; post-fix call 2 blocks at ``BEGIN IMMEDIATE``, the wait times
out, and ``"commit1"`` precedes ``"read"``.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

import pytest

from swing.data.db import connect, ensure_schema
from swing.trades import exit as exit_mod
from swing.trades.exit import ExitReason, ExitRequest
from tests.trades.test_exit import _seed_active_trade


# ------------------------------------------------------------------ helpers
class ConnProxy:
    """Delegates to a real ``sqlite3.Connection`` (whose C attributes cannot
    be monkeypatched) so a test can observe commits, record statements and
    make ``rollback`` raise."""

    def __init__(self, conn, *, on_commit=None, rollback_exc=None,
                 statements=None):
        self._conn = conn
        self._on_commit = on_commit
        self._rollback_exc = rollback_exc
        self._statements = statements

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def execute(self, sql, *args, **kwargs):
        if self._statements is not None:
            self._statements.append(sql)
        return self._conn.execute(sql, *args, **kwargs)

    def commit(self):
        self._conn.commit()
        if self._on_commit is not None:
            self._on_commit()

    def rollback(self):
        if self._rollback_exc is not None:
            raise self._rollback_exc
        self._conn.rollback()

    def __enter__(self):
        return self._conn.__enter__()

    def __exit__(self, exc_type, exc, tb):
        result = self._conn.__exit__(exc_type, exc, tb)
        if exc_type is None and self._on_commit is not None:
            self._on_commit()
        return result


def make_db(tmp_path: Path) -> Path:
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    return db


def seed_trade(db: Path, *, state: str = "entered",
               current_size: float = 10.0, ticker: str = "TST") -> int:
    conn = connect(db)
    try:
        return _seed_active_trade(conn, ticker=ticker, state=state,
                                  current_size=current_size)
    finally:
        conn.close()


def exit_req(trade_id: int, *, shares: int = 10,
             exit_date: str = "2026-05-21", exit_price: float = 131.0,
             envelope: str | None = None,
             fill_origin: str = "operator_typed") -> ExitRequest:
    return ExitRequest(
        trade_id=trade_id, exit_date=exit_date, exit_price=exit_price,
        shares=shares, reason=ExitReason.MANUAL, notes=None,
        rationale="manual", event_ts="2026-05-21T16:00:00",
        fill_origin=fill_origin, schwab_source_value_json=envelope,
    )


def count_exit_fills(db: Path) -> int:
    c = sqlite3.connect(str(db))
    try:
        return c.execute(
            "SELECT COUNT(*) FROM fills WHERE action != 'entry'").fetchone()[0]
    finally:
        c.close()


def run_race(db: Path, monkeypatch, req1: ExitRequest, req2: ExitRequest):
    """THE BARRIER HARNESS. Returns ``(events, result1, out2)`` where
    ``out2`` holds ``result`` or ``exc`` for call 2."""
    events: list[str] = []
    read_done = threading.Event()
    caller_ident = threading.get_ident()
    out2: dict = {}
    started = {"flag": False}
    real_insert = exit_mod.insert_fill_with_event

    def _call2():
        c2 = connect(db, busy_timeout_ms=5000)
        try:
            out2["result"] = exit_mod.record_exit(c2, req2)
        except BaseException as exc:  # noqa: BLE001 -- captured for asserts
            out2["exc"] = exc
        finally:
            c2.close()

    worker = threading.Thread(target=_call2, daemon=True)

    def hooked_insert(conn, fill, **kwargs):
        fill_id = real_insert(conn, fill, **kwargs)
        if threading.get_ident() == caller_ident and not started["flag"]:
            started["flag"] = True
            worker.start()
            read_done.wait(2.0)
        return fill_id

    def _spy(real):
        def spy(*args, **kwargs):
            if threading.get_ident() != caller_ident and not read_done.is_set():
                events.append("read")
                read_done.set()
            return real(*args, **kwargs)
        return spy

    monkeypatch.setattr(exit_mod, "insert_fill_with_event", hooked_insert)
    monkeypatch.setattr(exit_mod, "get_trade", _spy(exit_mod.get_trade))
    real_ident = getattr(exit_mod, "recorded_exit_identities", None)
    if real_ident is not None:
        monkeypatch.setattr(exit_mod, "recorded_exit_identities",
                            _spy(real_ident))

    c1 = ConnProxy(connect(db, busy_timeout_ms=5000),
                   on_commit=lambda: events.append("commit1"))
    try:
        result1 = exit_mod.record_exit(c1, req1)
    finally:
        worker.join(15.0)
        c1.close()
    assert not worker.is_alive()
    return events, result1, out2


# ----------------------------------------------------------------- T1-a
def test_t1a_caller_held_transaction_rejected_before_any_read(
        tmp_path, monkeypatch):
    """CHARC K1 (iii). PRE-FIX: no raise -- the inner ``with conn:`` COMMITS
    the caller's transaction and a fill is written. NULL killed: a guard
    placed after ``get_trade`` (the spy would record a call)."""
    db = make_db(tmp_path)
    tid = seed_trade(db)
    calls: list = []
    real_get = exit_mod.get_trade
    monkeypatch.setattr(exit_mod, "get_trade",
                        lambda *a, **k: calls.append(1) or real_get(*a, **k))
    conn = connect(db)
    try:
        conn.execute("BEGIN")
        conn.execute("SELECT COUNT(*) FROM trades").fetchone()
        assert conn.in_transaction
        with pytest.raises(exit_mod.CallerHeldTransactionError):
            exit_mod.record_exit(conn, exit_req(tid))
        assert calls == []
        assert conn.in_transaction  # the caller's transaction is untouched
        conn.rollback()
    finally:
        conn.close()
    assert count_exit_fills(db) == 0


# ----------------------------------------------------------------- T1-b
def test_t1b_both_verbs_fail_rollback_error_raised_chained_and_logged(
        tmp_path, monkeypatch, caplog):
    """CHARC K1 (iv), the both-verbs-fail proxy. The INSERT raises, then the
    ROLLBACK raises: the ROLLBACK error propagates, ``__cause__`` the insert
    error, with ONE ERROR record naming the discard. NULLS killed: a bare
    ``conn.rollback()`` (loses the original), a try/except that swallows the
    rollback error."""
    db = make_db(tmp_path)
    tid = seed_trade(db)
    insert_error = RuntimeError("insert")
    rollback_error = RuntimeError("rollback")

    def boom(*a, **k):
        raise insert_error

    monkeypatch.setattr(exit_mod, "insert_fill_with_event", boom)
    real = connect(db)
    proxy = ConnProxy(real, rollback_exc=rollback_error)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(RuntimeError) as info:
                exit_mod.record_exit(proxy, exit_req(tid))
        assert info.value is rollback_error
        assert info.value.__cause__ is insert_error
        records = [r for r in caplog.records
                   if r.levelno >= logging.ERROR
                   and "MUST BE DISCARDED" in r.getMessage()]
        assert len(records) == 1
    finally:
        if real.in_transaction:
            real.rollback()
        real.close()
    assert count_exit_fills(db) == 0


# ----------------------------------------------------------------- T1-e
def test_t1e_interrupt_in_flight_and_failed_rollback_the_interrupt_propagates(
        tmp_path, monkeypatch, caplog):
    """D73 (2026-10-18), CHARC P1. ``KeyboardInterrupt`` at the insert seam,
    the rollback raises ``OperationalError``: the raised object IS the
    interrupt, its ``__cause__`` the ``OperationalError``, ONE ERROR record
    names both and the discard -- and an outer ``except Exception`` does NOT
    contain it. PRE-FIX (the copied pre-D73 template): the OperationalError
    propagates and the outer ``except Exception`` swallows it."""
    db = make_db(tmp_path)
    tid = seed_trade(db)
    interrupt = KeyboardInterrupt("operator stop")
    cleanup = sqlite3.OperationalError("disk I/O error on rollback")

    def boom(*a, **k):
        raise interrupt

    monkeypatch.setattr(exit_mod, "insert_fill_with_event", boom)

    def call(conn):
        try:
            exit_mod.record_exit(conn, exit_req(tid))
        except Exception:  # noqa: BLE001 -- the containment under test
            pass

    real = connect(db)
    proxy = ConnProxy(real, rollback_exc=cleanup)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(KeyboardInterrupt) as info:
                call(proxy)
        assert info.value is interrupt
        assert info.value.__cause__ is cleanup
        records = [r for r in caplog.records
                   if r.levelno >= logging.ERROR
                   and "MUST BE DISCARDED" in r.getMessage()]
        assert len(records) == 1
        text = records[0].getMessage()
        assert "operator stop" in text
        assert "disk I/O error on rollback" in text
    finally:
        if real.in_transaction:
            real.rollback()
        real.close()


# ----------------------------------------------------------------- T1-c
# The ROUTE half lives in tests/web/test_routes/test_d79_exit_identity.py
# (it needs the web conftest fixtures).
def test_t1c_cli_calls_record_exit_with_no_open_transaction(
        tmp_path, monkeypatch):
    """CHARC K1 (1) precondition, the CLI half (a PIN, green pre-fix).
    ``cli.py`` imports ``record_exit`` locally at call time, so the module
    attribute is the bound name."""
    from swing.cli import main
    from tests.cli.test_22f_cli_typed_refusals import _db, _entry, _exit_args
    from tests.cli.test_cli_trade import _setup

    seen: list[bool] = []
    real = exit_mod.record_exit

    def spy(conn, req):
        seen.append(conn.in_transaction)
        return real(conn, req)

    runner, cfg = _setup(tmp_path)
    _entry(runner, cfg)
    monkeypatch.setattr(exit_mod, "record_exit", spy)
    result = runner.invoke(main, _exit_args(cfg, trade_id=1, shares=2))
    assert result.exit_code == 0, result.output
    assert seen == [False]
    assert count_exit_fills(_db(tmp_path)) == 1


# ----------------------------------------------------------------- T1-d
def test_t1d_concurrent_size_check_runs_under_the_lock(tmp_path, monkeypatch):
    """The race the lock closes, size half. Two 10-share exits of a 10-share
    trade on two connections. POST-FIX: call 2 blocks at ``BEGIN
    IMMEDIATE``, reads AFTER call 1's commit, and is refused. NULL killed:
    ``BEGIN IMMEDIATE`` with ``get_trade`` still before it (events
    ``["read", "commit1"]``, 2 fills)."""
    db = make_db(tmp_path)
    tid = seed_trade(db, state="entered", current_size=10.0)
    events, result1, out2 = run_race(
        db, monkeypatch, exit_req(tid, shares=10), exit_req(tid, shares=10))
    assert result1.fully_closed
    assert count_exit_fills(db) == 1
    assert "exc" in out2, out2
    assert isinstance(out2["exc"], ValueError)
    assert ("not active" in str(out2["exc"])
            or "exceeds" in str(out2["exc"])), out2["exc"]
    assert events == ["commit1", "read"]



# ----------------------------------------------------------------- A-F01
def test_af01_metric_failure_rolls_the_exit_back(tmp_path):
    """D79 executing Fork A-F01 (branch A). The realized P&L, risk-per-share
    and R-multiple are computed INSIDE the owned transaction, before COMMIT,
    so a failure there rolls the exit back: a raise from ``record_exit``
    means nothing was recorded (the contract the route's 22-F guard and the
    CLI both read). ``trades.entry_price`` is planted as TEXT by raw UPDATE
    (the column is ``REAL NOT NULL`` with no type CHECK, so SQLite stores an
    unconvertible string as TEXT). PRE-FIX: the metrics ran after
    ``conn.commit()``, so the call raised ``TypeError`` with ONE exit fill
    durable. POST-FIX: it raises with ZERO exit fills and the trade's size
    and state unchanged; the escaping error is the math's own ``TypeError``,
    never a ``ValueError`` (CHARC, 2026-10-19). NULLS killed: the post-commit
    metric block; a wrapper translating the failure into a ``ValueError``."""
    db = make_db(tmp_path)
    tid = seed_trade(db, state="managing", current_size=10.0)
    raw = sqlite3.connect(str(db))
    try:
        raw.execute("UPDATE trades SET entry_price = 'bad' WHERE id = ?",
                    (tid,))
        raw.commit()
        assert raw.execute("SELECT typeof(entry_price) FROM trades "
                           "WHERE id = ?", (tid,)).fetchone()[0] == "text"
    finally:
        raw.close()
    conn = connect(db)
    try:
        with pytest.raises(TypeError) as info:
            exit_mod.record_exit(conn, exit_req(tid, shares=4))
        # CHARC (2026-10-19): the math's own error escapes, NOT re-dressed as
        # a ValueError -- a corrupt row is a programming fault, not an
        # operator refusal, so no caller's ``except ValueError`` re-renders it.
        assert type(info.value) is TypeError
        assert not isinstance(info.value, ValueError)
        assert not conn.in_transaction
    finally:
        conn.close()
    assert count_exit_fills(db) == 0
    c = sqlite3.connect(str(db))
    try:
        assert c.execute("SELECT state, current_size FROM trades WHERE id = ?",
                         (tid,)).fetchone() == ("managing", 10.0)
    finally:
        c.close()


# ----------------------------------------------------------------- A-F04
def test_af04_caller_held_check_precedes_the_envelope_authority(
        tmp_path, monkeypatch):
    """A-F04 (Reviewer A R4). T1-a passes no envelope and spies only
    ``get_trade``, so a caller-held check moved AFTER the date normalisation
    and the envelope read (``canonical_envelope_identity``) but before
    ``get_trade`` would still pass it. This call CARRIES an envelope with the
    authority spied: ``CallerHeldTransactionError`` and ZERO authority calls,
    the caller's transaction untouched, no fill. A PIN (green before and
    after): discrimination measured by mutation -- the check placed after
    the envelope read fails the zero-calls assertion. NULL killed: the
    caller-held check anywhere after the authority call."""
    db = make_db(tmp_path)
    tid = seed_trade(db)
    calls: list = []
    real_authority = exit_mod.canonical_envelope_identity
    monkeypatch.setattr(
        exit_mod, "canonical_envelope_identity",
        lambda *a, **k: calls.append(1) or real_authority(*a, **k))
    envelope = ('{"closed_shares": 10, "exit_date": "2026-05-21", '
                '"exit_price": 131.0, "schwab_order_id": "o1"}')
    conn = connect(db)
    try:
        conn.execute("BEGIN")
        conn.execute("SELECT COUNT(*) FROM trades").fetchone()
        assert conn.in_transaction
        with pytest.raises(exit_mod.CallerHeldTransactionError):
            exit_mod.record_exit(conn, exit_req(
                tid, envelope=envelope, fill_origin="schwab_auto"))
        assert calls == []
        assert conn.in_transaction
        conn.rollback()
    finally:
        conn.close()
    assert count_exit_fills(db) == 0


# ----------------------------------------------------------------- R6-02
# D79 executing Fork R6-02 (CHARC, branch C): a raise FROM ``conn.commit()``
# with no transaction open is INDETERMINATE on the writer's connection (the
# commit may have been durable). The contract is restated at that width
# (``record_exit``'s docstring, plan AL-10) and PINNED here; settlement is a
# per-attempt token co-durable with the fill (D85, banked), and the first
# leg below is the red a D85 arc turns green.
_R602_ENVELOPE = ('{"closed_shares": 4, "exit_date": "2026-05-21", '
                  '"exit_price": 131.0, "schwab_order_id": "o1"}')


def _indeterminate_records(caplog) -> list:
    return [r for r in caplog.records
            if r.name == "swing.trades.exit" and r.levelno >= logging.ERROR
            and "INDETERMINATE" in r.getMessage()]


def _lost_commit(db: Path, tid: int, raised: BaseException, caplog):
    """Run one linked 4-share exit through a proxy whose ``commit()``
    performs the REAL commit and THEN raises ``raised``. Returns the raised
    exception and the writer's ``in_transaction`` after it."""
    def lost():
        raise raised

    real = connect(db)
    proxy = ConnProxy(real, on_commit=lost)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(BaseException) as info:
                exit_mod.record_exit(proxy, exit_req(
                    tid, shares=4, envelope=_R602_ENVELOPE,
                    fill_origin="schwab_auto"))
        return info.value, real.in_transaction
    finally:
        real.close()


def test_r602_ii_a_lost_commit_is_indeterminate_and_a_retry_is_refused(
        tmp_path, caplog):
    """R6-02 condition (ii), the WIDTH PINNED (a PIN: green before and
    after). Leg 1: the commit is durable and ``commit()`` then raises; the
    ORIGINAL propagates (not swallowed, not re-typed), ``in_transaction``
    reads False, and exactly ONE exit fill is durable, read on a FRESH
    connection (never the writer's own -- the writer quoting itself). Leg 2:
    the retry of that same LINKED exit is refused by the (a) guard under the
    lock, naming the durable fill. A D85 arc (settlement) turns leg 1's
    "the original propagates" red."""
    db = make_db(tmp_path)
    tid = seed_trade(db, state="managing", current_size=10.0)
    lost = sqlite3.OperationalError("commit acknowledgement lost")
    raised, in_tx = _lost_commit(db, tid, lost, caplog)
    assert raised is lost
    assert type(raised) is sqlite3.OperationalError
    assert in_tx is False
    fresh = sqlite3.connect(str(db))
    try:
        rows = fresh.execute(
            "SELECT fill_id, quantity FROM fills WHERE action != 'entry'"
        ).fetchall()
    finally:
        fresh.close()
    assert len(rows) == 1
    [(fill_id, quantity)] = rows
    assert quantity == 4.0
    retry = connect(db)
    try:
        with pytest.raises(exit_mod.ExitOrderAlreadyRecordedError) as info:
            exit_mod.record_exit(retry, exit_req(
                tid, shares=4, envelope=_R602_ENVELOPE,
                fill_origin="schwab_auto"))
        assert not retry.in_transaction
    finally:
        retry.close()
    assert f"#{fill_id}" in str(info.value)
    assert "o1" in str(info.value)
    assert count_exit_fills(db) == 1


def test_r602_iii_a_lost_commit_writes_one_error_record(tmp_path, caplog):
    """R6-02 condition (iii): ONE ERROR record through ``log_contained_note``
    naming the indeterminate outcome, the trade id and the order id.
    PRE-FIX: no record (the original propagated silently)."""
    db = make_db(tmp_path)
    tid = seed_trade(db, state="managing", current_size=10.0)
    lost = sqlite3.OperationalError("commit acknowledgement lost")
    raised, _ = _lost_commit(db, tid, lost, caplog)
    assert raised is lost
    records = _indeterminate_records(caplog)
    assert len(records) == 1
    text = records[0].getMessage()
    assert "commit raised with no transaction open" in text
    assert "check the trade's fills before re-entering" in text
    assert f"trade {tid}" in text
    assert "order o1" in text
    assert "commit acknowledgement lost" in text
    assert count_exit_fills(db) == 1


def test_r602_iii_an_interrupt_from_the_commit_writes_the_record_then_propagates(
        tmp_path, caplog):
    """R6-02 (iii), the D73 shape: an INTERRUPT raised from the commit (the
    commit durable) writes the ONE record first, then the interrupt itself
    propagates, unchained and untranslated. PRE-FIX: no record."""
    db = make_db(tmp_path)
    tid = seed_trade(db, state="managing", current_size=10.0)
    interrupt = KeyboardInterrupt("operator stop at the commit")
    raised, in_tx = _lost_commit(db, tid, interrupt, caplog)
    assert raised is interrupt
    assert in_tx is False
    assert len(_indeterminate_records(caplog)) == 1
    assert count_exit_fills(db) == 1


def test_r602_iii_a_failure_before_the_commit_statement_writes_no_record(
        tmp_path, caplog):
    """Cell 7's intake correction, the record's own condition: ``BEGIN
    IMMEDIATE`` failing leaves ``in_transaction`` False in the same except,
    but nothing was attempted, so the outcome is NOT indeterminate and no
    INDETERMINATE record is written; the original propagates and nothing is
    recorded. NULL killed: a record keyed on ``in_transaction`` alone (it
    would name a commit that never ran)."""
    db = make_db(tmp_path)
    tid = seed_trade(db, state="managing", current_size=10.0)
    busy = sqlite3.OperationalError("database is locked")

    class BusyAtBegin(ConnProxy):
        def execute(self, sql, *args, **kwargs):
            if sql.strip().upper().startswith("BEGIN"):
                raise busy
            return super().execute(sql, *args, **kwargs)

    real = connect(db)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError) as info:
                exit_mod.record_exit(BusyAtBegin(real), exit_req(
                    tid, shares=4, envelope=_R602_ENVELOPE,
                    fill_origin="schwab_auto"))
        assert info.value is busy
        assert not real.in_transaction
    finally:
        real.close()
    assert _indeterminate_records(caplog) == []
    assert count_exit_fills(db) == 0
