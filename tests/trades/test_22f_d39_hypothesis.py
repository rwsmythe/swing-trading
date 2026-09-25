"""22-F T-F7 (C2-13) -- D39 (S-D39) on `hypothesis.py`'s one BEGIN site,
`update_hypothesis_status_with_audit` (`:187/:284`), plus its three in-try
refusal-branch ROLLBACKs (SS-4): `:199` not-found, `:205` no-op identity,
`:211` illegal transition.

The proxy is the `conn` argument.

* The BEGIN/cleanup site is driven down two write verbs (read from
  `swing/data/repos/hypothesis_status_history.py` and the service body): the
  body's FIRST write, `UPDATE hypothesis_status_history`
  (`update_close_open_interval`), and its LAST, `UPDATE hypothesis_registry`
  (issued after the history rows already changed in-tx).  Four cases each.
* The SS-4 sites: each is driven by its OWN refusal input with the proxy
  failing `rollback()` once (the in-try ROLLBACK fails, the handler's cleanup
  works -> that failure re-raised, a PIN on both trees) and twice (both
  fail -> pre: the cleanup error, `__cause__` None, no record; post: the
  cleanup error chained from the in-try failure, one record).  A CONTROL per
  refusal input (rollback works) pins each refusal's own outcome and that the
  branch was reached (one `rollback()` recorded).

Every case asserts the proxy recorded its failing verb (did-it-fire).  The
clock the service reads (`swing.trades.hypothesis.now_ms`, a module global
resolved at call time) is FROZEN at a value after any wall-clock seed stamp
the migrations write, so an interval close can never precede its open.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from tests._22f_proxies import FailingVerbsConn

_FROZEN_NOW = "2099-01-01T00:00:00.000"


@pytest.fixture(autouse=True)
def _frozen_clock(monkeypatch):
    import swing.trades.hypothesis as mod
    monkeypatch.setattr(mod, "now_ms", lambda: _FROZEN_NOW)


@pytest.fixture
def db(tmp_path: Path) -> dict:
    """A fresh DB with two seeded hypotheses: ``active_id`` (status
    'active') and ``paused_id`` (moved to 'paused' through the service, so
    'closed-target-met' is an ILLEGAL target for it)."""
    from swing.trades.hypothesis import update_hypothesis_status_with_audit
    path = tmp_path / "t.db"
    conn = ensure_schema(path)
    try:
        ids = [r[0] for r in conn.execute(
            "SELECT id FROM hypothesis_registry WHERE status = 'active' "
            "ORDER BY id").fetchall()]
        assert len(ids) >= 2, ids
        update_hypothesis_status_with_audit(
            conn, hypothesis_id=ids[1], new_status="paused",
            change_reason="seed")
    finally:
        conn.close()
    return {"path": path, "active_id": ids[0], "paused_id": ids[1]}


def _state(db: dict, hyp_id: int) -> tuple[int, str]:
    c = sqlite3.connect(str(db["path"]))
    try:
        n = c.execute("SELECT COUNT(*) FROM hypothesis_status_history "
                      "WHERE hypothesis_id = ?", (hyp_id,)).fetchone()[0]
        st = c.execute("SELECT status FROM hypothesis_registry WHERE id = ?",
                       (hyp_id,)).fetchone()[0]
        return n, st
    finally:
        c.close()


def _update(conn, hyp_id: int, new_status: str):
    from swing.trades.hypothesis import update_hypothesis_status_with_audit
    return update_hypothesis_status_with_audit(
        conn, hypothesis_id=hyp_id, new_status=new_status,
        change_reason="22-F probe")


def _records(caplog):
    return [r for r in caplog.records if "MUST BE DISCARDED" in r.getMessage()]


# --- the BEGIN/cleanup site (:187/:284) -------------------------------------

_VERBS = ("UPDATE hypothesis_status_history", "UPDATE hypothesis_registry")


@pytest.mark.parametrize("verb", _VERBS)
def test_both_verbs_fail_raises_cleanup_chained(verb, db, caplog):
    """PRE-FIX: the CLEANUP error with `__cause__` None, no record.
    POST-FIX: the CLEANUP error, `__cause__` the write error, one record."""
    hyp = db["active_id"]
    before = _state(db, hyp)
    proxy = FailingVerbsConn(sqlite3.connect(str(db["path"])),
                             fail_sql_prefix=verb, fail_rollback=True)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError) as info:
                _update(proxy, hyp, "paused")
    finally:
        proxy._real.close()
    assert proxy.calls["failed_sql"] == 1
    assert proxy.calls["rollback"] >= 1
    assert "cannot rollback" in str(info.value)
    assert "planted on" in str(info.value.__cause__)
    assert len(_records(caplog)) == 1
    assert _state(db, hyp) == before


@pytest.mark.parametrize("verb", _VERBS)
def test_f2_twin_interrupt_rolls_back(verb, db):
    hyp = db["active_id"]
    before = _state(db, hyp)
    proxy = FailingVerbsConn(sqlite3.connect(str(db["path"])),
                             fail_sql_prefix=verb,
                             raise_on_sql=KeyboardInterrupt)
    try:
        with pytest.raises(KeyboardInterrupt):
            _update(proxy, hyp, "paused")
        assert proxy.calls["failed_sql"] == 1
        assert proxy.in_transaction is False
    finally:
        proxy._real.close()
    assert _state(db, hyp) == before


@pytest.mark.parametrize("verb", _VERBS)
def test_single_failure_write_error_reraised_pin(verb, db, caplog):
    """PIN (both trees): the write fails, the rollback works."""
    hyp = db["active_id"]
    before = _state(db, hyp)
    proxy = FailingVerbsConn(sqlite3.connect(str(db["path"])),
                             fail_sql_prefix=verb)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError, match="planted on"):
                _update(proxy, hyp, "paused")
        assert proxy.calls["failed_sql"] == 1
        assert proxy.in_transaction is False
    finally:
        proxy._real.close()
    assert _records(caplog) == []
    assert _state(db, hyp) == before


@pytest.mark.parametrize("verb", _VERBS)
def test_control_commits(verb, db):
    hyp = db["active_id"]
    n0, _ = _state(db, hyp)
    proxy = FailingVerbsConn(sqlite3.connect(str(db["path"])))
    try:
        assert _update(proxy, hyp, "paused") == "transition"
        assert proxy.calls["commit"] >= 1
        assert proxy.calls["execute:UPDATE"] >= 2
    finally:
        proxy._real.close()
    assert _state(db, hyp) == (n0 + 1, "paused")


# --- the SS-4 in-try refusal-branch ROLLBACKs (:199, :205, :211) ------------

def _not_found(db):
    return 999_999, "paused"


def _noop(db):
    return db["active_id"], "active"


def _illegal(db):
    return db["paused_id"], "closed-target-met"


_REFUSALS = {"199_not_found": _not_found, "205_noop_identity": _noop,
             "211_illegal_transition": _illegal}


@pytest.mark.parametrize("site", sorted(_REFUSALS))
def test_ss4_refusal_control(site, db):
    """CONTROL (both trees): the rollback works; the refusal's own outcome,
    reached through its in-try ROLLBACK (one `rollback()` recorded)."""
    from swing.trades.hypothesis import HypothesisStatusTransitionError
    hyp, new = _REFUSALS[site](db)
    proxy = FailingVerbsConn(sqlite3.connect(str(db["path"])))
    try:
        if site == "199_not_found":
            with pytest.raises(ValueError, match="not found"):
                _update(proxy, hyp, new)
        elif site == "205_noop_identity":
            assert _update(proxy, hyp, new) == "noop_identity"
        else:
            with pytest.raises(HypothesisStatusTransitionError):
                _update(proxy, hyp, new)
        assert proxy.calls["rollback"] == 1
        assert proxy.in_transaction is False
    finally:
        proxy._real.close()


@pytest.mark.parametrize("site", sorted(_REFUSALS))
def test_ss4_single_failure_in_try_rollback_reraised_pin(site, db, caplog):
    """PIN (both trees): the in-try ROLLBACK fails (E1), the handler's
    cleanup ROLLBACK works -> E1 re-raised, no record, transaction closed."""
    hyp, new = _REFUSALS[site](db)
    proxy = FailingVerbsConn(sqlite3.connect(str(db["path"])),
                             fail_rollback=1)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError,
                               match="planted on rollback") as info:
                _update(proxy, hyp, new)
        assert proxy.calls["rollback"] == 2
        assert proxy.in_transaction is False
    finally:
        proxy._real.close()
    assert info.value.__cause__ is None
    assert _records(caplog) == []


@pytest.mark.parametrize("site", sorted(_REFUSALS))
def test_ss4_double_failure_raises_cleanup_chained(site, db, caplog):
    """PRE-FIX: the handler's cleanup error E2, `__cause__` None, no record.
    POST-FIX: E2 raised FROM the in-try failure E1, one record."""
    hyp, new = _REFUSALS[site](db)
    proxy = FailingVerbsConn(sqlite3.connect(str(db["path"])),
                             fail_rollback=2)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError) as info:
                _update(proxy, hyp, new)
        assert proxy.calls["rollback"] == 2
    finally:
        proxy._real.close()
    e1 = info.value.__cause__
    assert isinstance(e1, sqlite3.OperationalError)
    assert e1 is not info.value
    assert "planted on rollback" in str(e1)
    assert len(_records(caplog)) == 1
