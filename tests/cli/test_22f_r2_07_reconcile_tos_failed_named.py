"""22-F R2-07 (Reviewer A round 2; CHARC-ruled, group 4, option (a): NAME
IT with a NEW type, granted under F-F2's new-type clause).

`run_tos_reconciliation` COMMITS a `state='failed'` run row when
`reconcile_tos` raises, then re-raises.  PRE-FIX it re-raised the bare
cause, so `swing journal reconcile-tos` ended in a traceback that never
named the failed run it had recorded -- and with `durable` False, a failing
close REPLACED the reconciliation error entirely (the LOST CAUSE, the D68
shape in the exit path).  POST-FIX the service raises
`TosReconciliationFailedError(RuntimeError)` carrying `run_id`, `from` the
cause, AFTER `update_run_failed` commits; the CLI translates it into a
`ClickException` naming "reconciliation run <id> IS recorded as failed;
cause: <ascii_safe cause>" and holds it as the pending refusal, so a close
failure is named in it and chained (S-R8) -- it can never replace it.

The failure is planted at `swing.trades.reconciliation.reconcile_tos` (the
module global the service resolves at call time), a counting wrapper
asserted called.  The failing close is `swing.data.db.connect` (the name
the command's function-local import resolves), asserted fired.
"""
from __future__ import annotations

import sqlite3

import click

from swing.cli import main
from tests._22f_proxies import raising
from tests.cli.test_22f_close_after_durable import (
    _ALSO,
    _PLANTED,
    ROOTS,
    _closes,
    _failing_close,
)

_BY_ID = {r.id: r for r in ROOTS}
_ROOT = _BY_ID["journal-reconcile-tos"]
_CAUSE = "planted reconcile failure at row 17"


def _runs(db) -> list[tuple]:
    c = sqlite3.connect(str(db))
    try:
        return c.execute("SELECT run_id, state, error_message FROM "
                         "reconciliation_runs ORDER BY run_id").fetchall()
    finally:
        c.close()


def _plant(monkeypatch):
    planted = raising(ValueError(_CAUSE))
    monkeypatch.setattr("swing.trades.reconciliation.reconcile_tos", planted)
    return planted


def test_r2_07_service_raises_the_typed_failure_naming_the_run(
        tmp_path, monkeypatch):
    import swing.trades.reconciliation as svc
    w = _ROOT.world(tmp_path, monkeypatch)
    planted = _plant(monkeypatch)
    err_type = getattr(svc, "TosReconciliationFailedError", None)
    assert err_type is not None
    assert issubclass(err_type, RuntimeError)
    conn = sqlite3.connect(str(w.db))
    try:
        try:
            svc.run_tos_reconciliation(conn, csv_path=w.extra["csv"])
        except BaseException as exc:  # noqa: BLE001 -- inspected below
            raised = exc
        else:
            raised = None
        assert conn.in_transaction is False
    finally:
        conn.close()
    assert planted.calls == 1  # did-it-fire
    assert isinstance(raised, err_type), repr(raised)
    runs = _runs(w.db)
    assert len(runs) == 1 and runs[0][1] == "failed"
    assert raised.run_id == runs[0][0]
    assert isinstance(raised.__cause__, ValueError)
    assert _CAUSE in str(raised.__cause__)


def test_r2_07_cli_names_the_failed_run_and_the_cause(tmp_path, monkeypatch):
    w = _ROOT.world(tmp_path, monkeypatch)
    planted = _plant(monkeypatch)
    result = w.runner.invoke(main, _ROOT.argv(w), standalone_mode=False)
    assert planted.calls == 1  # did-it-fire
    runs = _runs(w.db)
    assert len(runs) == 1 and runs[0][1] == "failed"  # a FRESH read
    exc = result.exception
    assert isinstance(exc, click.ClickException), repr(exc)
    text = exc.format_message()
    assert f"reconciliation run {runs[0][0]} IS recorded as failed" in text
    assert _CAUSE in text
    assert text.isascii()
    assert isinstance(exc.__cause__, RuntimeError)  # the typed failure
    assert isinstance(exc.__cause__.__cause__, ValueError)


def test_r2_07_cli_exit_code_and_output_standalone(tmp_path, monkeypatch):
    w = _ROOT.world(tmp_path, monkeypatch)
    _plant(monkeypatch)
    result = w.runner.invoke(main, _ROOT.argv(w))
    run_id = _runs(w.db)[0][0]
    assert result.exit_code == 1, (result.output, repr(result.exception))
    assert isinstance(result.exception, SystemExit)
    assert "Traceback" not in result.output
    assert f"reconciliation run {run_id} IS recorded as failed" in (
        result.output)
    assert _CAUSE in result.output


def test_r2_07_cli_failing_close_carries_both(tmp_path, monkeypatch):
    w = _ROOT.world(tmp_path, monkeypatch)
    planted = _plant(monkeypatch)
    built = _failing_close(monkeypatch, _ROOT.target, _ROOT.nth)
    result = w.runner.invoke(main, _ROOT.argv(w), standalone_mode=False)
    assert planted.calls == 1  # did-it-fire (the failure)
    assert _closes(built, _ROOT.nth) >= 1  # did-it-fire (the close)
    runs = _runs(w.db)
    assert len(runs) == 1 and runs[0][1] == "failed"
    exc = result.exception
    assert isinstance(exc, click.ClickException), repr(exc)
    text = exc.format_message()
    assert f"reconciliation run {runs[0][0]} IS recorded as failed" in text
    assert _CAUSE in text
    assert _ALSO in text and _PLANTED in text
    assert isinstance(exc.__cause__, sqlite3.OperationalError)  # S-R8


def test_r2_07_success_path_unchanged_control(tmp_path, monkeypatch):
    """CONTROL (both trees): the unplanted run completes, exit 0."""
    w = _ROOT.world(tmp_path, monkeypatch)
    result = w.runner.invoke(main, _ROOT.argv(w))
    assert result.exit_code == 0, (result.output, repr(result.exception))
    assert "Reconciliation run #" in result.output
    assert "IS recorded as failed" not in result.output
    assert _runs(w.db)[0][1] == "completed"
