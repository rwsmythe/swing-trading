"""22-F T-F8 (C2-16; A-3 CONFIRMED, R44; plan 1.2 row 12) -- F3 on every
ROLLBACK of `entry_intent_assignment.assign`'s one try.

BEGIN is already inside the try and the trigger is already `BaseException`
(F1/F2 hold); the defect is F3: the cleanup `conn.execute("ROLLBACK")`
(`:667-668`) is unguarded, so a failing cleanup replaces the original error
with `__cause__` None and no record.  The in-try ROLLBACKs at `:644` (the
`EnvelopeIdentityDriftError` branch) and `:654` (`dry_run` / not admitted)
are NOT wrapped one by one: a failure there IS the original error, it enters
the same handler, which re-reads `in_transaction` and attempts the cleanup.

Drives (the proxy is the `conn` argument; it wraps the committed trade-20
world of `tests/trades/test_22b_assignment_service.py`):

* `:644` -- identity drift planted RAW, exactly as `b22_209` plants it;
* `:654` -- a `dry_run=True` call;
* the cleanup path -- a planted write error on
  `INSERT INTO entry_intent_attestations` (read from
  `swing/data/repos/entry_intent_attestations.py:insert_attestation`).

The proxy fails `execute("ROLLBACK")` on its FIRST call only (single failure)
and on BOTH calls (double failure).  On `:644`/`:654` the single failure is
the in-try ROLLBACK (E1) with the cleanup working -> E1 re-raised (a PIN on
both trees); the double failure is E1 then the cleanup (E2) -> pre: E2,
`__cause__` None, no record; post: E2 from E1, one `MUST BE DISCARDED`
record.  On the cleanup path there is ONE ROLLBACK: the write error (E0)
with a working ROLLBACK is the PIN; with the ROLLBACK failing -> pre: E1,
`__cause__` None; post: E1 from E0, one record.  A CONTROL per drive
(ROLLBACK works) pins each branch's own outcome on both trees, including the
success path's `assign` result.  Every case asserts the proxy recorded its
ROLLBACK count (did-it-fire), and every case asserts nothing was written.
The clock `preflight` and `ensure_entry_fill_identities` read is frozen.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from tests._22b_fixtures import insert_row
from tests._22f_proxies import FailingVerbsConn
from tests.trades.test_22b_assignment_service import (
    _assign,
    _fresh,
    _nothing_written,
    _world,
)

_WRITE = "INSERT INTO entry_intent_attestations"


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: D401
        return cls(2026, 9, 25, 12, 0, 0, tzinfo=tz)


@pytest.fixture(autouse=True)
def _frozen_clock(monkeypatch):
    import swing.data.repos.fill_envelope_identity as fei
    import swing.trades.entry_intent_assignment as svc
    monkeypatch.setattr(svc, "datetime", _FrozenDatetime)
    monkeypatch.setattr(fei, "datetime", _FrozenDatetime)


def _plant_drift(c) -> None:
    doc = c.execute("SELECT schwab_source_value_json FROM fills "
                    "WHERE fill_id = 41").fetchone()[0]
    insert_row(c, "fill_envelope_identity", {
        "fill_id": 41, "envelope_raw": doc, "envelope_state": "canonical",
        "broker_order_id": "999", "instrument_symbol": "AMN",
        "canonicalizer_version": "planted",
        "recorded_ts": "2026-09-23T00:00:00Z"})
    c.commit()


def _run(tmp_path: Path, drive: str, **proxy_kw):
    """Build the world, wrap its connection, call `assign` down ``drive``.
    Returns (outcome, proxy, path); ``outcome`` is the result or the raised
    exception."""
    c, cfg, path = _world(tmp_path)
    if drive == "644_identity_drift":
        _plant_drift(c)
    if drive == "cleanup_write_error":
        proxy_kw.setdefault("fail_sql_prefix", _WRITE)
    proxy = FailingVerbsConn(c, **proxy_kw)
    try:
        try:
            out = _assign(proxy, cfg, dry_run=(drive == "654_dry_run"))
        except BaseException as exc:  # noqa: BLE001
            out = exc
    finally:
        c.close()
    return out, proxy, path


_IN_TRY = ("644_identity_drift", "654_dry_run")
_ALL = _IN_TRY + ("cleanup_write_error",)
_DRIFT_ROWS = {"644_identity_drift": 1, "654_dry_run": 0,
               "cleanup_write_error": 0}


def _records(caplog):
    return [r for r in caplog.records if "MUST BE DISCARDED" in r.getMessage()]


def _assert_nothing_written(path: Path, drive: str) -> None:
    _nothing_written(path)
    # The readings `ensure` appended are rolled back with the rest; the only
    # stored reading is the one planted (and committed) before the call.
    assert _fresh(path, "SELECT COUNT(*) FROM fill_envelope_identity") == [
        (_DRIFT_ROWS[drive],)]


@pytest.mark.parametrize("drive", _ALL)
def test_control_rollback_works(drive, tmp_path):
    """CONTROL (both trees): each branch's own outcome."""
    out, proxy, path = _run(tmp_path, drive)
    if drive == "644_identity_drift":
        assert (out.admitted, out.refusal_code) == (False, "identity_drift")
        assert proxy.calls["rollback"] == 1
    elif drive == "654_dry_run":
        assert out.admitted is True and out.attestation_id is None
        assert proxy.calls["rollback"] == 1
    else:
        assert isinstance(out, sqlite3.OperationalError), out
        assert "planted on" in str(out)
        assert proxy.calls["failed_sql"] == 1
        assert proxy.calls["rollback"] == 1
    _assert_nothing_written(path, drive)


@pytest.mark.parametrize("drive", _IN_TRY)
def test_in_try_single_failure_reraised_pin(drive, tmp_path, caplog):
    """PIN (both trees): the in-try ROLLBACK fails (E1), the cleanup works
    -> E1 re-raised, `__cause__` None, no record."""
    with caplog.at_level(logging.ERROR):
        out, proxy, path = _run(tmp_path, drive, fail_rollback=1)
    assert isinstance(out, sqlite3.OperationalError), out
    assert "planted on execute ROLLBACK" in str(out)
    assert out.__cause__ is None
    assert proxy.calls["rollback"] == 2
    assert _records(caplog) == []
    _assert_nothing_written(path, drive)


@pytest.mark.parametrize("drive", _IN_TRY)
def test_in_try_double_failure_raises_cleanup_chained(drive, tmp_path, caplog):
    """PRE-FIX: the cleanup error E2, `__cause__` None, no record.
    POST-FIX: E2 raised FROM the in-try failure E1, one record."""
    with caplog.at_level(logging.ERROR):
        out, proxy, path = _run(tmp_path, drive, fail_rollback=2)
    assert isinstance(out, sqlite3.OperationalError), out
    assert proxy.calls["rollback"] == 2
    e1 = out.__cause__
    assert isinstance(e1, sqlite3.OperationalError)
    assert e1 is not out
    assert "planted on execute ROLLBACK" in str(e1)
    assert len(_records(caplog)) == 1
    _assert_nothing_written(path, drive)


def test_cleanup_path_write_and_rollback_fail_raises_chained(tmp_path, caplog):
    """PRE-FIX: the ROLLBACK error, `__cause__` None, no record.
    POST-FIX: the ROLLBACK error FROM the write error, one record."""
    with caplog.at_level(logging.ERROR):
        out, proxy, path = _run(tmp_path, "cleanup_write_error",
                                fail_rollback=1)
    assert isinstance(out, sqlite3.OperationalError), out
    assert "cannot rollback" in str(out)
    assert proxy.calls["failed_sql"] == 1
    assert proxy.calls["rollback"] == 1
    assert "planted on" in str(out.__cause__)
    assert "cannot rollback" not in str(out.__cause__)
    assert len(_records(caplog)) == 1
    _assert_nothing_written(path, "cleanup_write_error")


def test_success_path_control(tmp_path):
    """CONTROL (both trees): the admitted `assign` result, committed."""
    c, cfg, path = _world(tmp_path)
    proxy = FailingVerbsConn(c)
    try:
        r = _assign(proxy, cfg)
        assert not proxy.in_transaction
    finally:
        c.close()
    assert r.admitted, r.message
    assert (r.tier, r.admitted_leg, r.placement_session, r.outcome_known_at) == (
        "contemporaneous_record", "deployment", "2026-08-01",
        "2026-08-11T16:00:00")
    assert r.attestation_id is not None
    assert proxy.calls["execute:COMMIT"] == 1
    assert proxy.calls["rollback"] == 0
    assert _fresh(path, "SELECT COUNT(*) FROM entry_intent_attestations") == [(1,)]
