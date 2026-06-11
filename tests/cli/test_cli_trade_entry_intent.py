"""Task 3 (tuition-vs-error): `swing trade entry --entry-intent`.

The CLI flag is the operator's explicit design-intent choice, persisted
AS-IS (server-stamped via record_entry/Trade). The advisory suggestion
shown in the WEB form is NOT auto-applied on the CLI: omitting the flag
persists NULL. click.Choice rejects a bad value (exit 2).
"""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from swing.data.db import connect
from tests.cli.test_cli_eval import _minimal_config
from tests.conftest import cli_entry_pre_trade_args


def _setup(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    return runner, cfg


def _read_entry_intent(cfg_path: Path, ticker: str) -> str | None:
    import tomllib

    from swing.data.repos.trades import find_any_open_trade
    cfg_data = tomllib.loads(cfg_path.read_text())
    db_path = Path(cfg_data["paths"]["db_path"])
    conn = connect(db_path)
    try:
        t = find_any_open_trade(conn, ticker=ticker)
        return t.entry_intent if t is not None else None
    finally:
        conn.close()


def test_cli_entry_intent_flag_persists(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        "--entry-intent", "standard",
        *cli_entry_pre_trade_args(),
    ])
    assert result.exit_code == 0, result.output
    assert _read_entry_intent(cfg, "AAPL") == "standard"


def test_cli_entry_intent_by_design_persists(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        "--entry-intent", "hypothesis_test_by_design",
        *cli_entry_pre_trade_args(),
    ])
    assert result.exit_code == 0, result.output
    assert _read_entry_intent(cfg, "AAPL") == "hypothesis_test_by_design"


def test_cli_entry_omitted_intent_is_null(tmp_path: Path):
    """No --entry-intent -> NULL (advisory suggestion NOT auto-applied)."""
    runner, cfg = _setup(tmp_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        *cli_entry_pre_trade_args(),
    ])
    assert result.exit_code == 0, result.output
    assert _read_entry_intent(cfg, "AAPL") is None


def test_cli_entry_bad_intent_raises(tmp_path: Path):
    """click.Choice rejects an invalid value with exit code 2."""
    runner, cfg = _setup(tmp_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        "--entry-intent", "foo",
        *cli_entry_pre_trade_args(),
    ])
    assert result.exit_code == 2, result.output
    assert "entry-intent" in result.output.lower()
