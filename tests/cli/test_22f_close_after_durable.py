"""22-F T-G1 -- F4 close-after-durable on the CLI operator-record roots
(plan section 8; S-B02 via `swing/cli.py::_close_after_writes`).

Per root, three tests over the ROOT TABLE below (each row carries its opener
`target`, the name the root resolves AT CALL TIME, read from its source):

* G1-a -- the root's SUCCESS path with `conn.close()` failing
  (`FailingVerbsConn(fail_close=True)`: the real close runs, then the error).
  PRE-FIX: the close error escapes the `finally` -> exit != 0, a traceback,
  over a DURABLE write.  POST-FIX: exit 0, `WARN: the write IS recorded`,
  and a FRESH read shows the write.
* G1-b -- the root's typed REFUSAL path with the close failing (roots that
  have one).  PRE-FIX: the close error REPLACES the refusal text.
  POST-FIX: the refusal text + `the connection close also failed`, exit 1,
  nothing written.
* G1-c -- CONTROL: nothing durable, no refusal (the root's writer is
  replaced by a counting wrapper raising a planted error no root translates
  into a refusal), close fails.  BOTH TREES: the close error replaces the in-flight error, exactly
  as it always has (the byte-unchanged bare-close branch).

Did-it-fire (R3-01): every case asserts the proxies recorded >= 1 `close()`;
every G1-c asserts its writer wrapper was called once.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pytest

# `swing.journal.tos_import` binds `connect` at MODULE level; imported here,
# at collection, it binds the REAL opener. Imported lazily for the first time
# INSIDE a test that has patched `swing.data.db.connect`, it would bind that
# test's patched opener for the rest of the process (`reconcile_tos`'s own
# read connection would then be proxied by whichever test ran first).
import swing.journal.tos_import  # noqa: F401
from swing.cli import main
from tests._22f_proxies import FailingVerbsConn, patch_conn_opener, raising
from tests.cli.test_cli_trade import _PRE_TRADE_OK_FLAGS, _setup

class _PlantedWriterFailure(Exception):
    """G1-c's planted writer error: a class NO root translates into a typed
    refusal (a `RuntimeError` would be -- `schwab logout` maps its
    rename-failure `RuntimeError` to a `ClickException`)."""


_WARN = "WARN: the write IS recorded; the connection close failed: "
_ALSO = "the connection close also failed"
_PLANTED = "planted on close"
_DB_CONNECT = "swing.data.db.connect"


def _db(tmp_path: Path) -> Path:
    return tmp_path / "home" / "swing-data" / "swing.db"


def _scalar(db_path: Path, sql: str, *params: Any) -> Any:
    c = sqlite3.connect(str(db_path))
    try:
        return c.execute(sql, params).fetchone()[0]
    finally:
        c.close()


@dataclass
class World:
    runner: Any
    cfg: Path
    db: Path
    extra: dict


@dataclass
class Root:
    id: str
    target: str
    world: Callable[[Path, Any], World]
    argv: Callable[[World], list]
    # a FRESH read that changes when the root's write lands
    probe: Callable[[World], Any]
    # the dotted name the root's writer is resolved by at call time (G1-c)
    writer: str
    refusal_argv: Callable[[World], list] | None = None
    refusal_text: str | None = None
    # the world the refusal runs in (default: `world`)
    refusal_world: Callable[[Path, Any], World] | None = None
    # stdin for a root that confirms (default: none)
    input: str | None = None
    # False where the root has NO nothing-durable path while its connection
    # is open (G1-c is then not constructible; the reason is in the row)
    control: bool = True


# ---------------------------------------------------------------- worlds ---

def _trade_world(tmp_path: Path, _mp: Any) -> World:
    runner, cfg = _setup(tmp_path)
    r = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        *_PRE_TRADE_OK_FLAGS,
    ])
    assert r.exit_code == 0, r.output
    return World(runner, cfg, _db(tmp_path), {})


def _fills(w: World) -> int:
    return _scalar(w.db, "SELECT COUNT(*) FROM fills")


def _current_stop(w: World) -> float:
    return _scalar(w.db, "SELECT current_stop FROM trades WHERE id = 1")


def _plain_world(tmp_path: Path, _mp: Any) -> World:
    runner, cfg = _setup(tmp_path)
    return World(runner, cfg, _db(tmp_path), {})


def _cash_rows(w: World) -> int:
    return _scalar(w.db, "SELECT COUNT(*) FROM cash_movements")


def _oof_world(tmp_path: Path, mp: Any) -> World:
    from tests.cli.test_oof_buy_command import _SPCX_OVERRIDES
    from tests.cli.test_oof_buy_command import _setup as _oof_setup
    runner, cfg, db = _oof_setup(tmp_path, mp, overrides=_SPCX_OVERRIDES)
    return World(runner, cfg, db, {})


def _oof_argv(w: World) -> list:
    return ["--config", str(w.cfg), "journal", "oof-buy", "--ticker", "SPCX",
            "--cost", "500", "--date", "2026-06-18"]


def _oof_collision_world(tmp_path: Path, mp: Any) -> World:
    w = _oof_world(tmp_path, mp)
    r = w.runner.invoke(main, _oof_argv(w))
    assert r.exit_code == 0, r.output
    return w


def _cash_void_world(tmp_path: Path, _mp: Any) -> World:
    w = _plain_world(tmp_path, _mp)
    r = w.runner.invoke(main, ["--config", str(w.cfg), "journal", "cash",
                               "--withdraw", "100", "--date", "2026-06-18"])
    assert r.exit_code == 0, r.output
    return w


def _entry_date_world(tmp_path: Path, mp: Any) -> World:
    from tests.cli.test_correct_entry_date_command import _seed
    from tests.cli.test_correct_entry_date_command import _setup as _ed_setup
    runner, cfg, db = _ed_setup(tmp_path, mp)
    return World(runner, cfg, db, _seed(db))


def _entry_date_argv(w: World) -> list:
    from tests.cli.test_correct_entry_date_command import _args
    return _args(w.cfg, w.extra)


def _entry_date(w: World) -> str:
    return _scalar(w.db, "SELECT entry_date FROM trades WHERE id = ?",
                   w.extra["trade_id"])


def _provenance_world(tmp_path: Path, mp: Any) -> World:
    from tests.cli.test_correct_cohort_provenance_command import _seed
    from tests.cli.test_correct_cohort_provenance_command import (
        _setup as _cp_setup,
    )
    runner, cfg, db = _cp_setup(tmp_path, mp)
    return World(runner, cfg, db, _seed(db))


def _provenance_argv(w: World) -> list:
    from tests.cli.test_correct_cohort_provenance_command import _cmd
    return _cmd(w.cfg, w.extra)


def _provenance_rows(w: World) -> int:
    return _scalar(w.db, "SELECT COUNT(*) FROM provenance_corrections")


def _tos_world(tmp_path: Path, _mp: Any) -> World:
    from tests.cli.test_discrepancy_cli import (
        SYNTHETIC_TOS_TEXT,
        _seed_open_trade,
    )
    w = _plain_world(tmp_path, _mp)
    _seed_open_trade(w.db)
    csv = tmp_path / "tos.csv"
    csv.write_text(SYNTHETIC_TOS_TEXT, encoding="utf-8")
    w.extra["csv"] = csv
    return w


def _recon_runs(w: World) -> int:
    return _scalar(w.db, "SELECT COUNT(*) FROM reconciliation_runs")


def _pending_world(tmp_path: Path, _mp: Any) -> World:
    from tests.cli.test_22f_d39_cli_backlink import _world as _bl_world
    w = _plain_world(tmp_path, _mp)
    did, _call_id = _bl_world(w.db)
    w.extra["did"] = did
    return w


def _resolution(w: World) -> str:
    return _scalar(w.db, "SELECT resolution FROM reconciliation_discrepancies "
                   "WHERE discrepancy_id = ?", w.extra["did"])


def _tier1_world(tmp_path: Path, _mp: Any) -> World:
    from tests.cli.test_discrepancy_override_correction_cli import (
        _seed_cvgi_with_tier1_correction,
    )
    w = _plain_world(tmp_path, _mp)
    w.extra.update(_seed_cvgi_with_tier1_correction(w.db))
    return w


def _override_argv(truth: str) -> Callable[[World], list]:
    def _argv(w: World) -> list:
        return ["--config", str(w.cfg), "journal", "discrepancy",
                "override-correction", str(w.extra["tier1_correction_id"]),
                "--truth-value", truth, "--reason", "broker statement",
                "--force"]
    return _argv


def _corrections(w: World) -> int:
    return _scalar(w.db, "SELECT COUNT(*) FROM reconciliation_corrections")


def _tos_import_world(tmp_path: Path, _mp: Any) -> World:
    from tests.cli.test_cli_tos import SYNTHETIC_FIXTURE
    w = _plain_world(tmp_path, _mp)
    w.extra["csv"] = SYNTHETIC_FIXTURE
    return w


def _running_run_world(tmp_path: Path, _mp: Any) -> World:
    w = _plain_world(tmp_path, _mp)
    c = sqlite3.connect(str(w.db))
    try:
        cur = c.execute(
            "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
            "action_session_date, state, lease_token, lease_heartbeat_ts) "
            "VALUES ('2026-06-15T09:00:00', 'manual', '2026-06-12', "
            "'2026-06-15', 'running', 'tok', '2026-06-15T09:00:00')")
        c.commit()
        w.extra["run_id"] = int(cur.lastrowid)
    finally:
        c.close()
    return w


def _run_state(w: World) -> str:
    return _scalar(w.db, "SELECT state FROM pipeline_runs WHERE id = ?",
                   w.extra["run_id"])


def _hypothesis_world(tmp_path: Path, mp: Any) -> World:
    from tests.cli.test_cli_hypothesis import _setup as _hyp_setup
    runner, cfg = _hyp_setup(tmp_path, mp)
    w = World(runner, cfg, _db(tmp_path), {})
    w.extra["hid"] = _scalar(
        w.db, "SELECT id FROM hypothesis_registry WHERE status = 'active' "
        "ORDER BY id LIMIT 1")
    return w


def _status_history(w: World) -> int:
    return _scalar(w.db, "SELECT COUNT(*) FROM hypothesis_status_history")


def _snapshots(w: World) -> int:
    return _scalar(w.db, "SELECT COUNT(*) FROM account_equity_snapshots")


def _home_world(tmp_path: Path, mp: Any) -> World:
    """USERPROFILE and HOME point into tmp_path: these roots WRITE the
    user-config file (`write_user_overrides` / `delete_user_override`)."""
    from click.testing import CliRunner

    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    mp.setenv("USERPROFILE", str(home))
    mp.setenv("HOME", str(home))
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    r = runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    assert r.exit_code == 0, r.output
    return World(runner, cfg, _db(tmp_path), {})


def _reset_world(tmp_path: Path, mp: Any) -> World:
    w = _home_world(tmp_path, mp)
    r = w.runner.invoke(main, ["--config", str(w.cfg), "config", "set",
                               "account.risk_equity_floor", "8500.0",
                               "--force"])
    assert r.exit_code == 0, r.output
    return w


def _no_active_policy_world(tmp_path: Path, mp: Any) -> World:
    w = _home_world(tmp_path, mp)
    c = sqlite3.connect(str(w.db))
    try:
        c.execute("UPDATE risk_policy SET is_active = 0")
        c.commit()
    finally:
        c.close()
    return w


def _policy_rows(w: World) -> int:
    return _scalar(w.db, "SELECT COUNT(*) FROM risk_policy")


_CLI_SCHWAB_CONNECT = "swing.cli_schwab.connect"


def _audit_row(conn: Any) -> None:
    """A durable `schwab_api_calls` row on the ROOT's connection -- the audit
    row the real (network-bound) Schwab service would have committed."""
    conn.execute(
        "INSERT INTO schwab_api_calls (ts, endpoint, status, surface, "
        "environment, http_status) VALUES (?, ?, ?, ?, ?, ?)",
        ("2026-06-18T12:00:00", "accounts.linked", "success", "cli",
         "production", 200))
    conn.commit()


def _schwab_calls(w: World) -> int:
    return _scalar(w.db, "SELECT COUNT(*) FROM schwab_api_calls")


def _schwab_world(tmp_path: Path, mp: Any) -> World:
    """Credentials come from the env tier (no prompt); USERPROFILE and HOME
    point into tmp_path (these roots read and write user-config)."""
    w = _home_world(tmp_path, mp)
    mp.setenv("SCHWAB_CLIENT_ID", "cid-sentinel")
    mp.setenv("SCHWAB_CLIENT_SECRET", "csecret-sentinel")
    return w


def _stub_service(mp: Any, name: str, result: dict) -> Any:
    from tests._22f_proxies import CountingWrapper

    def _fn(**kw: Any) -> dict:
        _audit_row(kw["conn"])
        return result
    stub = CountingWrapper(_fn)
    mp.setattr(f"swing.cli_schwab.{name}", stub)
    return stub


def _refusing_service(mp: Any, name: str, exc: BaseException) -> None:
    mp.setattr(f"swing.cli_schwab.{name}", raising(exc))


def _setup_world(tmp_path: Path, mp: Any) -> World:
    w = _schwab_world(tmp_path, mp)
    _stub_service(mp, "setup_paste_flow", {
        "account_hash": "ABCDEF1234567890", "num_accounts": 1,
        "tokens_path": "tokens.db"})
    return w


def _setup_refusal_world(tmp_path: Path, mp: Any) -> World:
    from swing.integrations.schwab.client import SchwabAuthError
    w = _schwab_world(tmp_path, mp)
    _refusing_service(mp, "setup_paste_flow", SchwabAuthError(401, "bad grant"))
    return w


def _refresh_world(tmp_path: Path, mp: Any) -> World:
    w = _schwab_world(tmp_path, mp)
    _stub_service(mp, "force_refresh", {"tokens_path": "tokens.db"})
    return w


def _refresh_refusal_world(tmp_path: Path, mp: Any) -> World:
    from swing.integrations.schwab.client import SchwabAuthError
    w = _schwab_world(tmp_path, mp)
    _refusing_service(mp, "force_refresh", SchwabAuthError(401, "bad grant"))
    return w


def _logout_world(tmp_path: Path, mp: Any) -> World:
    w = _schwab_world(tmp_path, mp)
    _stub_service(mp, "revoke_and_delete", {
        "revoke_status": "success", "deleted_path": "tokens.db.deleted"})
    return w


def _logout_refusal_world(tmp_path: Path, mp: Any) -> World:
    w = _schwab_world(tmp_path, mp)
    _refusing_service(mp, "revoke_and_delete",
                      RuntimeError("could not rename the tokens DB"))
    return w


def _oof_orphan_world(tmp_path: Path, mp: Any) -> World:
    """The real `resolve_out_of_framework_orphans` over one planted SPCX
    orphan (the declared set comes from a stubbed `apply_overrides`, as
    `test_resolve_out_of_framework_cli` does)."""
    import swing.config_overrides as _config_overrides
    from tests.cli.test_resolve_out_of_framework_cli import (
        _plant_orphan,
        _stub_cfg,
    )
    w = _schwab_world(tmp_path, mp)
    c = sqlite3.connect(str(w.db))
    try:
        _plant_orphan(c, "SPCX")
    finally:
        c.close()
    stub = _stub_cfg(w.db, tickers=("SPCX",))
    mp.setattr(_config_overrides, "apply_overrides", lambda _c: stub)
    return w


def _oof_running_world(tmp_path: Path, mp: Any) -> World:
    w = _oof_orphan_world(tmp_path, mp)
    c = sqlite3.connect(str(w.db))
    try:
        c.execute(
            "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
            "action_session_date, state, lease_token) VALUES "
            "('2026-06-15T09:00:00', 'manual', '2026-06-12', '2026-06-15', "
            "'running', 'tok')")
        c.commit()
    finally:
        c.close()
    return w


def _oof_resolution(w: World) -> str:
    return _scalar(w.db, "SELECT resolution FROM reconciliation_discrepancies "
                   "WHERE ticker = 'SPCX'")


def _fetch_world(tmp_path: Path, mp: Any) -> World:
    """`account_hash` configured through user-config; the schwabdev client
    builder and the snapshot step (both network-bound) are stubbed; the
    step writes its audit row on the ROOT's connection."""
    from tests._22f_proxies import CountingWrapper
    w = _schwab_world(tmp_path, mp)
    (tmp_path / "home" / "swing-data" / "user-config.toml").write_text(
        '[integrations.schwab]\naccount_hash = "ABCDEF1234567890"\n',
        encoding="utf-8")
    mp.setattr("swing.cli_schwab._build_schwabdev_client_for_fetch",
               lambda *a, **k: object())

    def _step(conn: Any, cfg: Any, **kw: Any) -> dict:
        _audit_row(conn)
        return {"status": "ok", "call_id": 1}
    mp.setattr("swing.integrations.schwab.pipeline_steps._step_schwab_snapshot",
               CountingWrapper(_step))
    return w


def _fetch_running_world(tmp_path: Path, mp: Any) -> World:
    w = _fetch_world(tmp_path, mp)
    c = sqlite3.connect(str(w.db))
    try:
        c.execute(
            "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
            "action_session_date, state, lease_token) VALUES "
            "('2026-06-15T09:00:00', 'manual', '2026-06-12', '2026-06-15', "
            "'running', 'tok')")
        c.commit()
    finally:
        c.close()
    return w


# ------------------------------------------------------------ root table ---

ROOTS: list[Root] = [
    Root(
        id="trade-exit", target=_DB_CONNECT, world=_trade_world,
        argv=lambda w: ["--config", str(w.cfg), "trade", "exit",
                        "--trade-id", "1", "--exit-date", "2026-04-22",
                        "--exit-price", "200.0", "--shares", "2",
                        "--reason", "partial"],
        probe=_fills, writer="swing.trades.exit.record_exit",
        refusal_argv=lambda w: ["--config", str(w.cfg), "trade", "exit",
                                "--trade-id", "1", "--exit-date",
                                "2026-04-22", "--exit-price", "200.0",
                                "--shares", "50", "--reason", "target"],
        refusal_text="exceeds remaining",
    ),
    Root(
        id="trade-stop-adjust", target=_DB_CONNECT, world=_trade_world,
        argv=lambda w: ["--config", str(w.cfg), "trade", "stop-adjust",
                        "--trade-id", "1", "--new-stop", "175.0",
                        "--rationale", "manual-trail"],
        probe=_current_stop, writer="swing.trades.stop_adjust.adjust_stop",
        refusal_argv=lambda w: ["--config", str(w.cfg), "trade",
                                "stop-adjust", "--trade-id", "1",
                                "--new-stop", "165.0", "--rationale",
                                "manual-trail"],
        refusal_text="force",
    ),
    Root(
        id="journal-cash", target=_DB_CONNECT, world=_plain_world,
        argv=lambda w: ["--config", str(w.cfg), "journal", "cash",
                        "--deposit", "100", "--date", "2026-06-18"],
        probe=_cash_rows, writer="swing.data.repos.cash.insert_cash",
    ),
    Root(
        id="journal-oof-buy", target=_DB_CONNECT, world=_oof_world,
        argv=_oof_argv, probe=_cash_rows,
        writer="swing.data.repos.cash.insert_cash",
        refusal_world=_oof_collision_world, refusal_argv=_oof_argv,
        refusal_text="--force",
    ),
    Root(
        id="journal-cash-void", target=_DB_CONNECT, world=_cash_void_world,
        argv=lambda w: ["--config", str(w.cfg), "journal", "cash-void", "1",
                        "--reason", "entered twice"],
        probe=_cash_rows, writer="swing.data.repos.cash.insert_cash",
        refusal_argv=lambda w: ["--config", str(w.cfg), "journal",
                                "cash-void", "99", "--reason", "x"],
        refusal_text="no cash_movement with id 99",
    ),
    Root(
        id="journal-correct-entry-date", target=_DB_CONNECT,
        world=_entry_date_world,
        argv=_entry_date_argv,
        probe=_entry_date,
        writer="swing.trades.entry_date_correction.correct_entry_date",
        refusal_argv=lambda w: [
            "--config", str(w.cfg), "journal", "correct-entry-date",
            str(w.extra["trade_id"]), "--to", "2026-08-03",
            "--discrepancy", str(w.extra["discrepancy_id"]),
            "--reason", "typo"],
        refusal_text="SERVER-DERIVED",
    ),
    Root(
        id="journal-correct-cohort-provenance", target=_DB_CONNECT,
        world=_provenance_world,
        argv=lambda w: _provenance_argv(w) + [
            "--reason", "the framework's own contemporaneous record"],
        probe=_provenance_rows,
        writer=("swing.trades.cohort_provenance_correction."
                "correct_cohort_provenance"),
        refusal_argv=_provenance_argv,
        refusal_text="--reason must be a non-empty string",
    ),
    Root(
        id="journal-reconcile-tos", target=_DB_CONNECT, world=_tos_world,
        argv=lambda w: ["--config", str(w.cfg), "journal", "reconcile-tos",
                        "--csv-path", str(w.extra["csv"]),
                        "--period-end", "2026-05-12"],
        probe=_recon_runs,
        writer="swing.trades.reconciliation.run_tos_reconciliation",
    ),
    Root(
        id="discrepancy-resolve-ambiguity", target=_DB_CONNECT,
        world=_pending_world,
        argv=lambda w: ["--config", str(w.cfg), "journal", "discrepancy",
                        "resolve-ambiguity", str(w.extra["did"]), "--choice",
                        "keep_journal_as_is", "--reason", "g1 probe"],
        probe=_resolution,
        writer=("swing.trades.reconciliation_auto_correct."
                "apply_tier2_resolution"),
        refusal_argv=lambda w: ["--config", str(w.cfg), "journal",
                                "discrepancy", "resolve-ambiguity", "9999",
                                "--choice", "keep_journal_as_is",
                                "--reason", "g1 probe"],
        refusal_text="discrepancy 9999 not found",
    ),
    Root(
        id="discrepancy-override-correction", target=_DB_CONNECT,
        world=_tier1_world, argv=_override_argv('{"price": 5.25}'),
        probe=_corrections,
        writer="swing.trades.reconciliation_auto_correct.apply_tier3_override",
        refusal_argv=_override_argv('{"price": 1e500}'),
        refusal_text="validator rejected",
    ),
    Root(
        id="discrepancy-resolve", target=_DB_CONNECT, world=_pending_world,
        argv=lambda w: ["--config", str(w.cfg), "journal", "discrepancy",
                        "resolve", str(w.extra["did"]), "--resolution",
                        "acknowledged_immaterial", "--force"],
        probe=_resolution, writer="swing.trades.reconciliation.resolve_discrepancy",
        refusal_argv=lambda w: ["--config", str(w.cfg), "journal",
                                "discrepancy", "resolve", str(w.extra["did"]),
                                "--resolution", "acknowledged_immaterial"],
        refusal_text="would bypass the choice menu",
    ),
    Root(
        id="tos-import", target=_DB_CONNECT, world=_tos_import_world,
        argv=lambda w: ["--config", str(w.cfg), "tos-import", "--csv",
                        str(w.extra["csv"]), "--auto-confirm"],
        probe=_cash_rows, writer="swing.data.repos.cash.insert_cash",
    ),
    Root(
        id="pipeline-force-clear", target="swing.cli.connect",
        world=_running_run_world,
        argv=lambda w: ["--config", str(w.cfg), "pipeline", "force-clear",
                        str(w.extra["run_id"]), "--bypass-staleness-check"],
        probe=_run_state, writer="swing.data.repos.pipeline.force_clear",
        refusal_argv=lambda w: ["--config", str(w.cfg), "pipeline",
                                "force-clear", "9999"],
        refusal_text="run 9999 not found", input="y\n",
    ),
    Root(
        id="hypothesis-update", target=_DB_CONNECT, world=_hypothesis_world,
        argv=lambda w: ["--config", str(w.cfg), "hypothesis", "update",
                        str(w.extra["hid"]), "--status", "paused",
                        "--reason", "g1 probe"],
        probe=_status_history,
        writer="swing.trades.hypothesis.update_hypothesis_status_with_audit",
        refusal_argv=lambda w: ["--config", str(w.cfg), "hypothesis",
                                "update", "9999", "--status", "paused",
                                "--reason", "g1 probe"],
        refusal_text="hypothesis 9999 not found",
    ),
    Root(
        id="account-snapshot", target=_DB_CONNECT, world=_plain_world,
        argv=lambda w: ["--config", str(w.cfg), "account", "snapshot",
                        "--equity", "1300", "--date", "2026-06-18"],
        probe=_snapshots,
        writer="swing.trades.account_equity_snapshots.record_snapshot",
        refusal_argv=lambda w: ["--config", str(w.cfg), "account",
                                "snapshot", "--equity", "0", "--date",
                                "2026-06-18"],
        refusal_text="equity_dollars",
    ),
    Root(
        id="config-set", target=_DB_CONNECT, world=_home_world,
        argv=lambda w: ["--config", str(w.cfg), "config", "set",
                        "account.risk_equity_floor", "8500.0", "--force"],
        probe=_policy_rows,
        writer="swing.trades.risk_policy.supersede_active_policy",
        # No G1-c: the override is written BEFORE the cascade connection
        # opens, so the connection never lives with nothing durable, and
        # every cascade failure is contained as a WARNING (no refusal).
        control=False,
    ),
    Root(
        id="config-reset", target=_DB_CONNECT, world=_reset_world,
        argv=lambda w: ["--config", str(w.cfg), "config", "reset",
                        "account.risk_equity_floor"],
        probe=_policy_rows,
        writer="swing.trades.risk_policy.supersede_active_policy",
        # No G1-c: as `config set` (the override is deleted first).
        control=False,
    ),
    Root(
        id="config-policy-set", target=_DB_CONNECT, world=_home_world,
        argv=lambda w: ["--config", str(w.cfg), "config", "policy", "set",
                        "--field", "capital_floor_constant_dollars",
                        "--value", "8500"],
        probe=_policy_rows,
        writer="swing.trades.risk_policy.supersede_active_policy",
        refusal_world=_no_active_policy_world,
        refusal_argv=lambda w: ["--config", str(w.cfg), "config", "policy",
                                "set", "--field",
                                "capital_floor_constant_dollars",
                                "--value", "8500"],
        refusal_text="No swing command creates a policy",
    ),
    Root(
        id="config-policy-import-from-toml", target=_DB_CONNECT,
        world=_home_world,
        argv=lambda w: ["--config", str(w.cfg), "config", "policy",
                        "import-from-toml", "--field",
                        "capital_floor_constant_dollars"],
        probe=_policy_rows,
        writer="swing.trades.risk_policy.supersede_active_policy",
        refusal_world=_no_active_policy_world,
        refusal_argv=lambda w: ["--config", str(w.cfg), "config", "policy",
                                "import-from-toml", "--field",
                                "capital_floor_constant_dollars"],
        refusal_text="No swing command creates a policy",
    ),
    Root(
        id="schwab-resolve-out-of-framework", target=_CLI_SCHWAB_CONNECT,
        world=_oof_orphan_world,
        argv=lambda w: ["schwab", "resolve-out-of-framework"],
        probe=_oof_resolution,
        writer=("swing.trades.schwab_reconciliation."
                "resolve_out_of_framework_orphans"),
        refusal_world=_oof_running_world,
        refusal_argv=lambda w: ["schwab", "resolve-out-of-framework"],
        refusal_text="currently in flight",
    ),
    Root(
        id="schwab-fetch", target=_CLI_SCHWAB_CONNECT, world=_fetch_world,
        argv=lambda w: ["--config", str(w.cfg), "schwab", "fetch",
                        "--snapshot"],
        probe=_schwab_calls,
        writer="swing.integrations.schwab.pipeline_steps._step_schwab_snapshot",
        refusal_world=_fetch_running_world,
        refusal_argv=lambda w: ["--config", str(w.cfg), "schwab", "fetch",
                                "--snapshot"],
        refusal_text="currently in flight",
    ),
    Root(
        id="schwab-setup", target=_CLI_SCHWAB_CONNECT, world=_setup_world,
        argv=lambda w: ["--config", str(w.cfg), "schwab", "setup"],
        probe=_schwab_calls, writer="swing.cli_schwab.setup_paste_flow",
        refusal_world=_setup_refusal_world,
        refusal_argv=lambda w: ["--config", str(w.cfg), "schwab", "setup"],
        refusal_text="Authentication failed: ",
    ),
    Root(
        id="schwab-refresh", target=_CLI_SCHWAB_CONNECT, world=_refresh_world,
        argv=lambda w: ["--config", str(w.cfg), "schwab", "refresh"],
        probe=_schwab_calls, writer="swing.cli_schwab.force_refresh",
        refusal_world=_refresh_refusal_world,
        refusal_argv=lambda w: ["--config", str(w.cfg), "schwab", "refresh"],
        refusal_text="Authentication failed during refresh",
    ),
    Root(
        id="schwab-logout", target=_CLI_SCHWAB_CONNECT, world=_logout_world,
        argv=lambda w: ["--config", str(w.cfg), "schwab", "logout"],
        probe=_schwab_calls, writer="swing.cli_schwab.revoke_and_delete",
        refusal_world=_logout_refusal_world,
        refusal_argv=lambda w: ["--config", str(w.cfg), "schwab", "logout"],
        refusal_text="could not rename the tokens DB",
    ),
]

_REFUSING = [r for r in ROOTS if r.refusal_argv is not None]
_CONTROLLED = [r for r in ROOTS if r.control]


def _failing_close(monkeypatch, target: str) -> list:
    return patch_conn_opener(monkeypatch, target,
                             lambda real: FailingVerbsConn(real,
                                                           fail_close=True))


def _closes(built: list) -> int:
    return sum(p.calls["close"] for p in built)


@pytest.mark.parametrize("root", ROOTS, ids=[r.id for r in ROOTS])
def test_G1a_success_with_close_failure_exits_zero_and_warns(
        root: Root, tmp_path, monkeypatch):
    w = root.world(tmp_path, monkeypatch)
    before = root.probe(w)
    built = _failing_close(monkeypatch, root.target)
    result = w.runner.invoke(main, root.argv(w), input=root.input)
    assert _closes(built) >= 1
    assert result.exit_code == 0, (result.output, repr(result.exception))
    assert _WARN in result.output
    assert _PLANTED in result.output
    assert root.probe(w) != before  # the write is durable (fresh read)


@pytest.mark.parametrize("root", _REFUSING, ids=[r.id for r in _REFUSING])
def test_G1b_refusal_with_close_failure_keeps_the_refusal(
        root: Root, tmp_path, monkeypatch):
    w = (root.refusal_world or root.world)(tmp_path, monkeypatch)
    before = root.probe(w)
    built = _failing_close(monkeypatch, root.target)
    result = w.runner.invoke(main, root.refusal_argv(w), input=root.input)
    assert _closes(built) >= 1
    assert result.exit_code == 1, (result.output, repr(result.exception))
    assert isinstance(result.exception, SystemExit)
    assert root.refusal_text in result.output
    assert _ALSO in result.output
    assert _PLANTED in result.output
    assert root.probe(w) == before  # nothing written


@pytest.mark.parametrize("root", _CONTROLLED,
                         ids=[r.id for r in _CONTROLLED])
def test_G1c_control_nothing_durable_close_error_replaces_as_before(
        root: Root, tmp_path, monkeypatch):
    w = root.world(tmp_path, monkeypatch)
    before = root.probe(w)
    module_name, _, attr = root.writer.rpartition(".")
    wrapper = raising(_PlantedWriterFailure("planted writer failure"))
    monkeypatch.setattr(module_name + "." + attr, wrapper)
    built = _failing_close(monkeypatch, root.target)
    result = w.runner.invoke(main, root.argv(w), input=root.input)
    assert wrapper.calls == 1
    assert _closes(built) >= 1
    assert isinstance(result.exception, sqlite3.OperationalError), (
        result.output, repr(result.exception))
    assert _PLANTED in str(result.exception)
    assert _WARN not in result.output
    assert root.probe(w) == before
