"""CLI: swing trade entry / exit / list / stop-adjust / advisory."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path: Path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    return runner, cfg


def test_trade_entry_then_list(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "VCP",
    ])
    assert result.exit_code == 0, result.output
    assert "trade id" in result.output.lower() or "entered" in result.output.lower()

    result2 = runner.invoke(main, ["--config", str(cfg), "trade", "list"])
    assert result2.exit_code == 0
    assert "AAPL" in result2.output


def test_trade_exit(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "x",
    ])
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "exit",
        "--trade-id", "1", "--exit-date", "2026-04-22",
        "--exit-price", "200.0", "--shares", "5",
        "--reason", "target", "--rationale", "hit",
    ])
    assert result.exit_code == 0, result.output
    assert "R" in result.output


def test_trade_stop_adjust_blocked_when_lowering(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "x",
    ])
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "stop-adjust",
        "--trade-id", "1", "--new-stop", "165.0", "--rationale", "loosen",
    ])
    assert result.exit_code != 0
    assert "regression" in result.output.lower() or "force" in result.output.lower()
