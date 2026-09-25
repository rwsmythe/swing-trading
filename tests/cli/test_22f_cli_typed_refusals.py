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
