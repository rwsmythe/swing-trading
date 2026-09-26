"""22-F Part A (CLI half) -- typed service refusals reach the operator as a
`click.ClickException` (S-CLICK: exit 1, `Error: <message>`), never a traceback.

T-A4 -- C1-02 `trade exit` (`ValueError` / `InvalidStateTransition` from
`record_exit`), C1-03 `trade stop-adjust` (`ValueError` from `adjust_stop`,
beside the existing `StopRegressionError` clause), C1-04
`schwab purge-marketdata-archive` / `schwab resolve-out-of-framework`
(`SchwabPipelineActiveError`, mirroring the siblings in `cli_schwab.py`).

A traceback shows in CliRunner as `result.exception` being the service's own
exception (not `SystemExit`) with the traceback in `result.exc_info`; the
S-CLICK shape is `SystemExit(1)` with the message on the output.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import swing.config_overrides as _config_overrides
from click.testing import CliRunner

from swing.cli import main
from swing.data.db import ensure_schema
from tests.cli.test_cli_trade import _PRE_TRADE_OK_FLAGS, _setup


def _db(tmp_path: Path) -> Path:
    return tmp_path / "home" / "swing-data" / "swing.db"


def _counts(db_path: Path) -> dict:
    c = sqlite3.connect(str(db_path))
    try:
        return {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("trades", "fills", "trade_events")}
    finally:
        c.close()


def _entry(runner, cfg) -> None:
    r = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        *_PRE_TRADE_OK_FLAGS,
    ])
    assert r.exit_code == 0, r.output


def _exit_args(cfg, *, trade_id: int, shares: int) -> list[str]:
    return ["--config", str(cfg), "trade", "exit", "--trade-id", str(trade_id),
            "--exit-date", "2026-04-22", "--exit-price", "200.0",
            "--shares", str(shares), "--reason", "target"]


def _assert_typed(result, *needle: str) -> None:
    assert isinstance(result.exception, SystemExit), (
        type(result.exception), result.output)
    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert result.output.startswith("Error: "), result.output
    for n in needle:
        assert n in result.output, result.output


def test_A4a_A4c_trade_exit_unknown_trade_is_typed_and_writes_nothing(
        tmp_path):
    """A4-a / A4-c. PRE-FIX: `record_exit` raises `ValueError("trade 9999
    not found")` through the command -> a traceback.  POST-FIX: exit 1,
    `Error: trade 9999 not found`; a FRESH read shows nothing written."""
    runner, cfg = _setup(tmp_path)
    before = _counts(_db(tmp_path))
    result = runner.invoke(main, _exit_args(cfg, trade_id=9999, shares=1))
    _assert_typed(result, "trade 9999 not found")
    assert _counts(_db(tmp_path)) == before


def test_A4b_trade_exit_shares_over_remaining_is_typed(tmp_path):
    """A4-b. PRE-FIX: `ValueError` ("exceeds remaining") traceback.
    POST-FIX: typed; nothing written by the refused exit."""
    runner, cfg = _setup(tmp_path)
    _entry(runner, cfg)
    before = _counts(_db(tmp_path))
    result = runner.invoke(main, _exit_args(cfg, trade_id=1, shares=50))
    _assert_typed(result, "exceeds remaining")
    assert _counts(_db(tmp_path)) == before


def test_A4d_stop_adjust_unknown_trade_is_typed(tmp_path):
    """A4-d. PRE-FIX: `adjust_stop` raises `ValueError("trade 9999 not
    found")`, which the `except StopRegressionError` clause does not catch
    (`StopRegressionError` is an `Exception`, not a `ValueError`) ->
    traceback.  POST-FIX: typed."""
    runner, cfg = _setup(tmp_path)
    before = _counts(_db(tmp_path))
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "stop-adjust", "--trade-id", "9999",
        "--new-stop", "165.0", "--rationale", "manual-trail",
    ])
    _assert_typed(result, "trade 9999 not found")
    assert _counts(_db(tmp_path)) == before


def test_A4d_control_stop_regression_still_typed(tmp_path):
    """CONTROL: the existing `StopRegressionError` clause is unchanged
    (lowering without --force -> typed, both trees)."""
    runner, cfg = _setup(tmp_path)
    _entry(runner, cfg)
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "stop-adjust", "--trade-id", "1",
        "--new-stop", "165.0", "--rationale", "manual-trail",
    ])
    _assert_typed(result)
    assert "force" in result.output.lower()


def _running_pipeline_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "swing.db"
    conn = ensure_schema(db_path)
    try:
        conn.execute(
            "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
            "action_session_date, state, lease_token) VALUES "
            "('2026-06-15T09:00:00', 'manual', '2026-06-12', '2026-06-15', "
            "'running', 'tok')")
        conn.commit()
    finally:
        conn.close()
    return db_path


def test_A4e_purge_marketdata_archive_pipeline_active_is_typed(
        tmp_path, monkeypatch):
    """A4-e. PRE-FIX: `_check_pipeline_not_running` raises
    `SchwabPipelineActiveError` with no handler -> traceback.  POST-FIX:
    typed, exit 1, the check's own text; nothing purged."""
    db_path = _running_pipeline_db(tmp_path)
    cache = tmp_path / "prices"
    cache.mkdir()
    (cache / "AAPL.schwab_api.parquet").write_bytes(b"x")
    stub = SimpleNamespace(
        paths=SimpleNamespace(prices_cache_dir=cache, db_path=db_path))
    monkeypatch.setattr(_config_overrides, "apply_overrides",
                        lambda _cfg: stub)
    result = CliRunner().invoke(
        main, ["schwab", "purge-marketdata-archive", "--yes"])
    _assert_typed(result, "currently in flight")
    assert (cache / "AAPL.schwab_api.parquet").exists()


def test_A4f_resolve_out_of_framework_pipeline_active_is_typed(
        tmp_path, monkeypatch):
    """A4-f. PRE-FIX: `SchwabPipelineActiveError` traceback.  POST-FIX:
    typed, exit 1."""
    db_path = _running_pipeline_db(tmp_path)
    stub = SimpleNamespace(
        paths=SimpleNamespace(db_path=db_path),
        reconciliation=SimpleNamespace(out_of_framework_tickers=("SPCX",)))
    monkeypatch.setattr(_config_overrides, "apply_overrides",
                        lambda _cfg: stub)
    result = CliRunner().invoke(main, ["schwab", "resolve-out-of-framework"])
    _assert_typed(result, "currently in flight")


# ---------------------------------------------------------------------------
# T-A5 -- C1-05 `ReservedJournalFieldError`, C1-06
# `MultiRowCorrectionOverrideError` at `discrepancy resolve-ambiguity` and
# `discrepancy override-correction` (CHARC F-F2 RJFE: per-site, NO re-base --
# both stay bare-`Exception` subclasses).  The world is 22-A4's CLI world
# (`tests/cli/test_22a4_corrector_refusal_cli.py`: a trade with a minted token
# and a TRADES-anchored `stop_mismatch` discrepancy).
# ---------------------------------------------------------------------------

def _recon_world(tmp_path: Path, *, tier2: bool):
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    r = runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    assert r.exit_code == 0, r.output
    db_path = home / "swing-data" / "swing.db"
    from tests.trades.test_22a4_corrector_refusal import (
        _seed_trade_anchored_world,
    )
    conn = sqlite3.connect(db_path)
    try:
        world = _seed_trade_anchored_world(conn, tier2=tier2)
    finally:
        conn.close()
    return runner, cfg, db_path, world


def _seed_head(db_path: Path, world: dict, *, choice: str = "operator_truth",
               field: str = "current_stop") -> int:
    from swing.data.db import connect
    from swing.data.models import ReconciliationCorrection
    from swing.data.repos.reconciliation_corrections import insert_correction
    conn = connect(db_path)
    try:
        head = ReconciliationCorrection(
            correction_id=0, discrepancy_id=world["discrepancy_id"],
            correction_action="operator_resolved_ambiguity",
            correction_choice=choice, affected_table="trades",
            affected_row_id=world["trade_id"], field_name=field,
            pre_correction_value_json='{"current_stop": 4.0}',
            source_canonical_value_json='{"current_stop": 4.5}',
            applied_value_json='{"current_stop": 4.5}',
            operator_truth_value_json=None,
            applied_at="2026-09-07T12:05:00.000Z", applied_by="operator",
            correction_set_id=None, superseded_by_correction_id=None,
            risk_policy_id_at_correction=None, schwab_api_call_id=None,
            reconciliation_run_id=world["run_id"],
            correction_reason="seed head", notes=None,
        )
        cid = insert_correction(conn, head)
        conn.commit()
        return int(cid)
    finally:
        conn.close()


def _correction_count(db_path: Path) -> int:
    c = sqlite3.connect(str(db_path))
    try:
        return c.execute(
            "SELECT COUNT(*) FROM reconciliation_corrections").fetchone()[0]
    finally:
        c.close()


def _trade_row(db_path: Path, trade_id: int) -> tuple:
    c = sqlite3.connect(str(db_path))
    try:
        return c.execute(
            "SELECT entry_date, current_stop, attempt_id FROM trades "
            "WHERE id = ?", (trade_id,)).fetchone()
    finally:
        c.close()


def test_A5a_A5d_resolve_ambiguity_reserved_field_is_typed(tmp_path):
    """A5-a / A5-d. `--choice operator_truth` with a RESERVED field
    (`trades.entry_date`, coupled to `correct-entry-date`).  PRE-FIX:
    `ReservedJournalFieldError` (a bare `Exception`) passes the command's
    `CallerHeld` / `AlreadySuperseded` / `ValidatorRejected` / `ValueError`
    ladder -> a traceback.  POST-FIX: exit 1, the service's own text, no
    traceback; a FRESH read shows no correction row and the trade row
    unchanged."""
    runner, cfg, db_path, world = _recon_world(tmp_path, tier2=True)
    before_trade = _trade_row(db_path, world["trade_id"])
    before = _correction_count(db_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "journal", "discrepancy", "resolve-ambiguity",
        str(world["discrepancy_id"]), "--choice", "operator_truth",
        "--custom-value", '{"entry_date": "2026-04-28"}',
        "--reason", "broker says a different entry date",
    ])
    _assert_typed(result, "cannot be written through the generic correction")
    assert _correction_count(db_path) == before
    assert _trade_row(db_path, world["trade_id"]) == before_trade


def test_A5b_A5d_override_correction_reserved_field_is_typed(tmp_path):
    """A5-b / A5-d. `override-correction` on a single-row head with a
    RESERVED field in the truth value.  PRE-FIX: `ReservedJournalFieldError`
    traceback.  POST-FIX: typed; nothing written (the head is still the only
    correction row, the trade row unchanged)."""
    runner, cfg, db_path, world = _recon_world(tmp_path, tier2=False)
    head_id = _seed_head(db_path, world)
    before_trade = _trade_row(db_path, world["trade_id"])
    before = _correction_count(db_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "journal", "discrepancy", "override-correction",
        str(head_id), "--truth-value", '{"entry_date": "2026-04-28"}',
        "--reason", "override onto a reserved column", "--force",
    ])
    _assert_typed(result, "cannot be written through the generic correction")
    assert _correction_count(db_path) == before
    assert _trade_row(db_path, world["trade_id"]) == before_trade


def test_A5c_A5d_override_correction_multi_row_head_is_typed(tmp_path):
    """A5-c / A5-d. `override-correction` aimed at a MULTI-ROW head
    (`correction_choice='correct_entry_date'`).  PRE-FIX:
    `MultiRowCorrectionOverrideError` traceback.  POST-FIX: typed, the
    service's text names the MULTI-ROW correction; nothing written."""
    runner, cfg, db_path, world = _recon_world(tmp_path, tier2=False)
    head_id = _seed_head(db_path, world, choice="correct_entry_date",
                         field="entry_date")
    before_trade = _trade_row(db_path, world["trade_id"])
    before = _correction_count(db_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "journal", "discrepancy", "override-correction",
        str(head_id), "--truth-value", '{"current_stop": 4.6}',
        "--reason", "override a multi-row head", "--force",
    ])
    _assert_typed(result, "MULTI-ROW")
    assert _correction_count(db_path) == before
    assert _trade_row(db_path, world["trade_id"]) == before_trade


# ---------------------------------------------------------------------------
# T-A6 -- C1-24 CLI half: `trade exit --exit-price 0`.
# ---------------------------------------------------------------------------

def test_A6b_A6c_trade_exit_price_zero_is_typed_and_writes_nothing(tmp_path):
    """A6-b / A6-c. PRE-FIX: `record_exit` INSERTs `price=0` and the
    `fills.price` CHECK raises `sqlite3.IntegrityError` -- not a
    `ValueError`, so T-A4's clause does not catch it -> a traceback.
    POST-FIX: `ExitPriceRefusedError(ValueError)` rides T-A4's clause:
    exit 1, typed; a FRESH read shows nothing written."""
    runner, cfg = _setup(tmp_path)
    _entry(runner, cfg)
    before = _counts(_db(tmp_path))
    args = _exit_args(cfg, trade_id=1, shares=1)
    args[args.index("--exit-price") + 1] = "0"
    result = runner.invoke(main, args)
    _assert_typed(result, "exit price must be > 0")
    assert _counts(_db(tmp_path)) == before
