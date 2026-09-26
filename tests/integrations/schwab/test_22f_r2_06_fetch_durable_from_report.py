"""22-F R2-06 (Reviewer A round 2; orchestrator-authorized FIX) -- `swing
schwab fetch` binds `durable` from EACH step's own report, never from the
step having returned normally.

A step that returns `status='sandbox_audit_only'` (or `'failed'`) has
written only a `schwab_api_calls` AUDIT row; per the STOP-4 rule an
audit-only write is not durable, so a failing close must take the
nothing-durable branch (the pre-arc bare close: the close error
propagates, and NO "the write IS recorded" WARN is printed).  PRE-FIX the
command set `durable = True` after any normally-returned step, so an
audit-only run with a failing close printed the false WARN and exited 0.

POST-FIX: the snapshot step is durable iff it reports a `snapshot_id`;
the orders step iff it reports a `reconciliation_run_id`.  The steps here
are the REAL steps over a stubbed schwabdev client; the failing close is
patched at `swing.cli_schwab.connect` (the name `schwab fetch` resolves at
call time) and asserted fired.
"""
from __future__ import annotations

import sqlite3

import pytest

from tests._22f_proxies import FailingVerbsConn, patch_conn_opener
from tests.integrations.test_schwab_fetch_cli import (  # noqa: F401
    _make_cfg,
    _stub_schwabdev_client,
    invoke_cli,
    isolated_db,
    isolated_home,
)

_WARN = "WARN: the write IS recorded; the connection close failed: "
_PLANTED = "planted on close"


def _count(db, sql: str) -> int:
    c = sqlite3.connect(db)
    try:
        return c.execute(sql).fetchone()[0]
    finally:
        c.close()


def _snapshots(db) -> int:
    return _count(db, "SELECT COUNT(*) FROM account_equity_snapshots")


def _runs(db) -> int:
    return _count(db, "SELECT COUNT(*) FROM reconciliation_runs")


def _calls(db) -> int:
    return _count(db, "SELECT COUNT(*) FROM schwab_api_calls")


def _failing_close(monkeypatch) -> list:
    return patch_conn_opener(
        monkeypatch, "swing.cli_schwab.connect",
        lambda real: FailingVerbsConn(real, fail_close=True))


@pytest.mark.parametrize("flag", ["--snapshot", "--orders", "--all"])
def test_r2_06_audit_only_run_with_failing_close_is_not_durable(
        flag, isolated_db, invoke_cli, monkeypatch):
    """Sandbox: every step returns `sandbox_audit_only` -- audit rows only.
    The close error propagates (nothing durable); no WARN."""
    _stub_schwabdev_client(monkeypatch)
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    built = _failing_close(monkeypatch)
    result = invoke_cli(cfg, "fetch", flag, "--environment", "sandbox")
    assert sum(p.calls["close"] for p in built) >= 1  # did-it-fire
    assert _calls(isolated_db) >= 1  # the audit rows ARE written
    assert _snapshots(isolated_db) == 0
    assert _runs(isolated_db) == 0
    assert _WARN not in result.output, result.output
    assert isinstance(result.exception, sqlite3.OperationalError), (
        result.output, repr(result.exception))
    assert _PLANTED in str(result.exception)


@pytest.mark.parametrize("flag,probe", [
    ("--snapshot", _snapshots), ("--orders", _runs), ("--all", _runs)])
def test_r2_06_domain_write_with_failing_close_warns_control(
        flag, probe, isolated_db, invoke_cli, monkeypatch):
    """CONTROL (both trees): production -- the step reports its domain row
    (`snapshot_id` / `reconciliation_run_id`), so a failing close is the
    durable branch: exit 0 with the WARN, the row durable on a fresh read."""
    _stub_schwabdev_client(monkeypatch)
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    built = _failing_close(monkeypatch)
    result = invoke_cli(cfg, "fetch", flag)
    assert sum(p.calls["close"] for p in built) >= 1  # did-it-fire
    assert result.exit_code == 0, (result.output, repr(result.exception))
    assert _WARN in result.output
    assert _PLANTED in result.output
    assert probe(isolated_db) == 1


def test_r2_06_snapshot_failed_report_then_orders_domain_write_is_durable(
        isolated_db, invoke_cli, monkeypatch):
    """`--all` where the snapshot step reports `failed` (no snapshot_id) and
    the orders step records its run: durable comes from the ORDERS report,
    so the failing close still WARNs (the binding is per-step, OR-ed)."""
    _stub_schwabdev_client(monkeypatch)
    from swing.integrations.schwab import pipeline_steps as ps
    from tests._22f_proxies import CountingWrapper

    def _failed_snapshot(conn, cfg, **kw):
        return {"status": "failed", "call_id": None, "snapshot_id": None,
                "error": "planted"}
    stub = CountingWrapper(_failed_snapshot)
    monkeypatch.setattr(ps, "_step_schwab_snapshot", stub)
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    built = _failing_close(monkeypatch)
    result = invoke_cli(cfg, "fetch", "--all")
    assert stub.calls == 1  # did-it-fire
    assert sum(p.calls["close"] for p in built) >= 1
    assert result.exit_code == 0, (result.output, repr(result.exception))
    assert _WARN in result.output
    assert _snapshots(isolated_db) == 0
    assert _runs(isolated_db) == 1
