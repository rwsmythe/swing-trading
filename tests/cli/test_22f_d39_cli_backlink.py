"""22-F T-F2 -- D39 (S-D39) on `discrepancy resolve-ambiguity`'s
`linked_correction` back-link envelope (census C2-05: the rollback was
UNGUARDED -- a failing rollback escaped from inside the `except` with the
write error only as implicit `__context__`).

The proxy arrives through `patch_conn_opener` at `swing.data.db.connect`
(the command imports `connect` function-locally -- plan section 0.4), and the
back-link is its `UPDATE schwab_api_calls` (`update_call_linked_correction`).
The tier-2 resolution itself commits BEFORE the envelope, so its correction
row is durable in every case.
"""
from __future__ import annotations

import logging
import sqlite3

from swing.cli import main
from tests._22f_proxies import FailingVerbsConn, patch_conn_opener
from tests.cli.test_discrepancy_resolve_ambiguity_cli import (  # noqa: F401
    _plant_pending_ambiguity,
    _seed_reconciliation_run,
    _seed_trade_with_entry_fill,
    cli_workspace,
)

_UPDATE = "UPDATE schwab_api_calls"


def _world(db_path) -> tuple[int, int]:
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        trade_id, fill_id = _seed_trade_with_entry_fill(conn, ticker="DHC")
        did = _plant_pending_ambiguity(
            conn, run_id=run_id, ticker="DHC",
            ambiguity_kind="multi_partial_vs_consolidated",
            trade_id=trade_id, fill_id=fill_id)
        cur = conn.execute(
            "INSERT INTO schwab_api_calls (ts, endpoint, status, surface, "
            "environment, http_status) VALUES (?, ?, ?, ?, ?, ?)",
            ("2026-05-16T12:04:00", "accounts.orders.list", "success", "cli",
             "production", 200))
        conn.commit()
        return did, int(cur.lastrowid)
    finally:
        conn.close()


def _invoke(runner, cfg, did, call_id):
    return runner.invoke(main, [
        "--config", str(cfg), "journal", "discrepancy", "resolve-ambiguity",
        str(did), "--choice", "keep_journal_as_is", "--reason", "d39 probe",
        "--schwab-api-call-id", str(call_id)])


def _back_link(db_path, call_id):
    c = sqlite3.connect(db_path)
    try:
        return c.execute("SELECT linked_correction_id FROM schwab_api_calls "
                         "WHERE call_id = ?", (call_id,)).fetchone()[0]
    finally:
        c.close()


def _failed(proxies) -> int:
    return sum(p.calls["failed_sql"] for p in proxies)


def test_F2_both_verbs_fail_raises_cleanup_chained_with_one_record(
        cli_workspace, monkeypatch, caplog):
    """PRE-FIX: the CLEANUP error, `__cause__ is None`, no record.
    POST-FIX: the CLEANUP error chained from the write error, one
    `MUST BE DISCARDED` record."""
    runner, cfg, db_path = cli_workspace
    did, call_id = _world(db_path)
    built = patch_conn_opener(
        monkeypatch, "swing.data.db.connect",
        lambda real: FailingVerbsConn(real, fail_sql_prefix=_UPDATE,
                                      fail_rollback=True))
    with caplog.at_level(logging.ERROR):
        r = _invoke(runner, cfg, did, call_id)
    assert _failed(built) == 1  # did-it-fire (the back-link UPDATE)
    assert sum(p.calls["rollback"] for p in built) >= 1
    exc = r.exception
    assert isinstance(exc, sqlite3.OperationalError), (type(exc), r.output)
    assert "cannot rollback" in str(exc)
    assert isinstance(exc.__cause__, sqlite3.OperationalError)
    assert "planted on UPDATE" in str(exc.__cause__)
    recs = [x for x in caplog.records if "MUST BE DISCARDED" in x.getMessage()]
    assert len(recs) == 1
    assert _back_link(db_path, call_id) is None


def test_F2_twin_interrupt_rolls_back(cli_workspace, monkeypatch):
    """PRE-FIX: `except Exception` does not run on `KeyboardInterrupt` -- no
    rollback is attempted.  POST-FIX: the rollback runs and the interrupt is
    re-raised; nothing is back-linked."""
    runner, cfg, db_path = cli_workspace
    did, call_id = _world(db_path)
    built = patch_conn_opener(
        monkeypatch, "swing.data.db.connect",
        lambda real: FailingVerbsConn(real, fail_sql_prefix=_UPDATE,
                                      raise_on_sql=KeyboardInterrupt))
    r = _invoke(runner, cfg, did, call_id)
    assert _failed(built) == 1
    assert isinstance(r.exception, KeyboardInterrupt) or r.exit_code != 0
    assert sum(p.calls["rollback"] for p in built) >= 1
    assert _back_link(db_path, call_id) is None


def test_F2_single_failure_write_error_reraised(cli_workspace, monkeypatch,
                                                caplog):
    """PIN (both trees): the write fails, the rollback works -> the write
    error escapes, no record."""
    runner, cfg, db_path = cli_workspace
    did, call_id = _world(db_path)
    built = patch_conn_opener(
        monkeypatch, "swing.data.db.connect",
        lambda real: FailingVerbsConn(real, fail_sql_prefix=_UPDATE))
    with caplog.at_level(logging.ERROR):
        r = _invoke(runner, cfg, did, call_id)
    assert _failed(built) == 1
    assert "planted on UPDATE" in str(r.exception)
    assert not [x for x in caplog.records
                if "MUST BE DISCARDED" in x.getMessage()]
    assert _back_link(db_path, call_id) is None


def test_F2_control_backlink_commits(cli_workspace, monkeypatch):
    runner, cfg, db_path = cli_workspace
    did, call_id = _world(db_path)
    built = patch_conn_opener(monkeypatch, "swing.data.db.connect",
                              lambda real: FailingVerbsConn(real))
    r = _invoke(runner, cfg, did, call_id)
    assert r.exit_code == 0, r.output
    assert sum(p.calls["execute:UPDATE"] for p in built) >= 1
    assert _back_link(db_path, call_id) is not None
