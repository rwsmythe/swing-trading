"""22-F T-F8 (C2-17) -- D39 (S-D39) on
`diagnostics/backfill_trades_sector_industry.py`'s one BEGIN site:
`run_backfill`'s apply path (`:115/:130`).

`run_backfill` opens its own connection through the MODULE-LEVEL
`from swing.data.db import connect`, so the proxy arrives through
`patch_conn_opener` at `swing.diagnostics.backfill_trades_sector_industry.
connect` (the name resolved at call time).  The failing verb is the apply
path's first write, `UPDATE trades SET sector` (`_apply_updates`; read).  The
cleanup is `conn.execute("ROLLBACK")` (plan 1.2 row 3); the proxy fails that
verb too.  The row is F1 (BEGIN outside the try), F2 (`except Exception`)
and F3 (the cleanup UNGUARDED).  SS-4, by reading: no in-try ROLLBACK.
Every case asserts the proxy was built and recorded its verb (did-it-fire),
and every failure case asserts on a fresh read that the trade's sector and
industry are still empty.  The module's clock (`datetime`, a module global
resolved at call time; it names the restore artifact) is frozen.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import Candidate, EvaluationRun
from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
from tests._22f_proxies import FailingVerbsConn, patch_conn_opener
from tests.cli.test_diagnose_backfill_trades_sector_industry import (
    _build_candidate_fixture,
    _insert_trade,
    _read_back_sector_industry,
)

_MOD = "swing.diagnostics.backfill_trades_sector_industry"
_VERB = "UPDATE trades SET sector"


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: D401
        return cls(2026, 9, 25, 12, 0, 0, tzinfo=tz)


@pytest.fixture(autouse=True)
def _frozen_clock(monkeypatch):
    import importlib
    monkeypatch.setattr(importlib.import_module(_MOD), "datetime",
                        _FrozenDatetime)


@pytest.fixture
def world(tmp_path: Path) -> tuple[Path, int]:
    db_path = tmp_path / "swing.db"
    conn = ensure_schema(db_path)
    try:
        with conn:
            run_id = insert_evaluation_run(conn, EvaluationRun(
                id=None, run_ts="2026-05-27T20:00:00",
                data_asof_date="2026-05-26", action_session_date="2026-05-27",
                finviz_csv_path=None, tickers_evaluated=1, aplus_count=0,
                watch_count=1, skip_count=0, excluded_count=0, error_count=0))
            insert_candidates(conn, run_id, [Candidate(
                ticker="VSAT", sector="Technology",
                industry="Communications Equipment",
                **_build_candidate_fixture("VSAT"))])
    finally:
        conn.close()
    trade_id = _insert_trade(db_path, ticker="VSAT", sector="", industry="")
    return db_path, trade_id


def _run(db_path: Path, out: Path):
    from swing.diagnostics.backfill_trades_sector_industry import run_backfill
    return run_backfill(db_path=db_path, apply=True, output_dir=out,
                        allowlist=None, include_closed=False)


def _records(caplog):
    return [r for r in caplog.records if "MUST BE DISCARDED" in r.getMessage()]


def test_both_verbs_fail_raises_cleanup_chained(world, tmp_path, monkeypatch,
                                                caplog):
    """PRE-FIX: the CLEANUP error with `__cause__` None, no record.
    POST-FIX: the CLEANUP error, `__cause__` the write error, one record."""
    db_path, tid = world
    built = patch_conn_opener(monkeypatch, f"{_MOD}.connect",
                              lambda real: FailingVerbsConn(
                                  real, fail_sql_prefix=_VERB,
                                  fail_rollback=True))
    with caplog.at_level(logging.ERROR):
        with pytest.raises(sqlite3.OperationalError) as info:
            _run(db_path, tmp_path / "out")
    assert len(built) == 1
    assert built[0].calls["failed_sql"] == 1
    assert built[0].calls["rollback"] >= 1
    assert "cannot rollback" in str(info.value)
    assert "planted on" in str(info.value.__cause__)
    assert len(_records(caplog)) == 1
    assert _read_back_sector_industry(db_path, tid) == ("", "")


def test_f2_twin_interrupt_rolls_back(world, tmp_path, monkeypatch):
    db_path, tid = world
    seen: list[bool] = []

    def factory(real):
        proxy = FailingVerbsConn(real, fail_sql_prefix=_VERB,
                                 raise_on_sql=KeyboardInterrupt)
        orig_close = proxy._real.close

        def close_spy():
            seen.append(proxy._real.in_transaction)
            orig_close()
        object.__setattr__(proxy, "close", close_spy)
        return proxy

    built = patch_conn_opener(monkeypatch, f"{_MOD}.connect", factory)
    with pytest.raises(KeyboardInterrupt):
        _run(db_path, tmp_path / "out")
    assert built[0].calls["failed_sql"] == 1
    # `run_backfill` closes its connection in a `finally`; the transaction
    # state AT that close is the discriminator (pre: still open, the
    # `except Exception` never ran; post: rolled back).
    assert seen == [False]
    assert _read_back_sector_industry(db_path, tid) == ("", "")


def test_single_failure_write_error_reraised_pin(world, tmp_path, monkeypatch,
                                                 caplog):
    """PIN (both trees): the write fails, the ROLLBACK works."""
    db_path, tid = world
    built = patch_conn_opener(monkeypatch, f"{_MOD}.connect",
                              lambda real: FailingVerbsConn(
                                  real, fail_sql_prefix=_VERB))
    with caplog.at_level(logging.ERROR):
        with pytest.raises(sqlite3.OperationalError, match="planted on"):
            _run(db_path, tmp_path / "out")
    assert built[0].calls["failed_sql"] == 1
    assert built[0].calls["rollback"] == 1
    assert _records(caplog) == []
    assert _read_back_sector_industry(db_path, tid) == ("", "")


def test_control_commits(world, tmp_path, monkeypatch):
    db_path, tid = world
    built = patch_conn_opener(monkeypatch, f"{_MOD}.connect",
                              lambda real: FailingVerbsConn(real))
    summary = _run(db_path, tmp_path / "out")
    assert built[0].calls["execute:UPDATE"] == 1
    assert built[0].calls["execute:COMMIT"] == 1
    assert summary.applied is True and summary.update_count == 1
    assert _read_back_sector_industry(db_path, tid) == (
        "Technology", "Communications Equipment")
