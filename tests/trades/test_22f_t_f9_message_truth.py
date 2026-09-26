"""22-F T-F9 (S8 item 8; A-2 GRANTED, R43) -- MESSAGE TRUTH at the two
cohort-provenance cleanup messages that said "STILL OPEN" unconditionally
after a rollback raised:

* site P, `preview_cohort_provenance_correction`'s owned-transaction
  savepoint handler (`cohort_provenance_correction.py:2388-2419`);
* site R, `read_provenance_corrections`'s `finally` unwind (`:3547-3560`).

No control-flow change: site P still raises the cleanup error chained from
the savepoint error; site R's bare `raise` stays (on the reader's success
path no other exception is in flight, so there is no original to chain).
Each message now RE-READS `conn.in_transaction` after the failed rollback
and reports that value.

Two postures per site, both on a REAL connection (the proxy is the `conn`
argument; `in_transaction` delegates to the real connection):

* still-open -- `rollback()` raises WITHOUT rolling back (the transaction
  really is open) -> the message says `in_transaction reads True`;
* took-effect -- `rollback()` performs the REAL rollback and then raises
  (modeled on `_RollbackAfterEffect`,
  `tests/trades/test_22a_task9_entry_wiring.py:3082`) -> pre: the message
  says "STILL OPEN" (false); post: `in_transaction reads False`.

Both postures: the message contains `MUST BE DISCARDED`, and the cleanup
error is what escapes.  Every case asserts the proxy recorded the
`rollback()` (did-it-fire) and, on site P, the failing SAVEPOINT.  No clock
is read.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from tests._22f_proxies import FailingVerbsConn


class _RollbackTakesEffectThenRaises(FailingVerbsConn):
    """The real rollback runs, THEN the error is raised (after-effect)."""

    def rollback(self) -> None:
        self.calls["rollback"] += 1
        self._real.rollback()
        raise sqlite3.OperationalError("rollback took effect, then raised")


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "t.db"
    ensure_schema(path).close()
    return path


def _proxy(db: Path, posture: str, **kw):
    real = sqlite3.connect(str(db))
    if posture == "still_open":
        return FailingVerbsConn(real, fail_rollback=True, **kw)
    return _RollbackTakesEffectThenRaises(real, **kw)


_EXPECTED = {"still_open": True, "took_effect": False}


def _messages(caplog, needle: str) -> list[str]:
    return [r.getMessage() for r in caplog.records if needle in r.getMessage()]


@pytest.mark.parametrize("posture", sorted(_EXPECTED))
def test_preview_savepoint_handler_reports_the_reread_state(posture, db,
                                                            caplog):
    import swing.trades.cohort_provenance_correction as mod
    proxy = _proxy(db, posture, fail_sql_prefix="SAVEPOINT")
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError) as info:
                mod.preview_cohort_provenance_correction(
                    proxy, trade_id=1, cited_candidate_id=2,
                    cited_recommendation_id=3)
        assert proxy.in_transaction is _EXPECTED[posture]
    finally:
        proxy._real.close()
    assert proxy.calls["failed_sql"] == 1
    assert proxy.calls["rollback"] == 1
    assert "planted on SAVEPOINT" in str(info.value.__cause__)
    msgs = _messages(caplog, "could not create its savepoint")
    assert len(msgs) == 1, msgs
    assert "MUST BE DISCARDED" in msgs[0]
    assert f"in_transaction reads {_EXPECTED[posture]}" in msgs[0]
    if posture == "took_effect":
        assert "STILL OPEN" not in msgs[0]


@pytest.mark.parametrize("posture", sorted(_EXPECTED))
def test_reader_unwind_reports_the_reread_state(posture, db, caplog,
                                               monkeypatch):
    import swing.trades.cohort_provenance_correction as mod
    monkeypatch.setattr(mod, "_read_provenance_corrections_inner",
                        lambda conn, **kw: [])
    proxy = _proxy(db, posture)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError) as info:
                mod.read_provenance_corrections(proxy, trade_id=1)
        assert proxy.in_transaction is _EXPECTED[posture]
    finally:
        proxy._real.close()
    assert proxy.calls["execute:BEGIN"] == 1
    assert proxy.calls["rollback"] == 1
    assert info.value.__cause__ is None
    msgs = _messages(caplog, "READER could not roll back")
    assert len(msgs) == 1, msgs
    assert "MUST BE DISCARDED" in msgs[0]
    assert f"in_transaction reads {_EXPECTED[posture]}" in msgs[0]
    if posture == "took_effect":
        assert "STILL OPEN" not in msgs[0]
