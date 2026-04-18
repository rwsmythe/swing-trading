"""CLI: swing journal review / cash."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    return runner, cfg


def test_journal_review_empty(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    r = runner.invoke(main, ["--config", str(cfg), "journal", "review"])
    assert r.exit_code == 0
    assert "0 trades" in r.output or "no trades" in r.output.lower()


def test_journal_cash_deposit(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "cash",
        "--deposit", "200.0", "--date", "2026-04-01",
        "--ref", "DEP-X", "--note", "test deposit",
    ])
    assert r.exit_code == 0, r.output
    assert "DEP-X" in r.output or "deposit" in r.output.lower()
