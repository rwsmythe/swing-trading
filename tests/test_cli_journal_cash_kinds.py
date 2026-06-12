"""CLI: swing journal cash -- the 5-kind vocabulary + ISO date validation (Arc 4b Task 5)."""
from __future__ import annotations

import pytest
from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    return runner, cfg


@pytest.mark.parametrize("flag", ["--interest", "--dividend", "--fee"])
def test_journal_cash_accepts_new_kinds(flag, tmp_path):
    # Pre-fix: --interest/--dividend/--fee are unknown options (exit!=0 for the
    # WRONG reason: "no such option"). Post-fix: the kind is accepted and the
    # row inserts (exit_code == 0) -- the test distinguishes by asserting ==0.
    runner, cfg = _setup(tmp_path)
    res = runner.invoke(main, [
        "--config", str(cfg), "journal", "cash", flag, "5", "--date", "2026-06-01",
    ])
    assert res.exit_code == 0, res.output


@pytest.mark.parametrize("bad", ["6/1/26", "2026-6-01", "abcd-ef-gh", "2026-13-40"])
def test_journal_cash_rejects_non_iso_date(bad, tmp_path):
    runner, cfg = _setup(tmp_path)
    res = runner.invoke(main, [
        "--config", str(cfg), "journal", "cash", "--deposit", "5", "--date", bad,
    ])
    assert res.exit_code != 0
    assert "YYYY-MM-DD" in res.output


def test_journal_cash_rejects_two_kinds(tmp_path):
    runner, cfg = _setup(tmp_path)
    res = runner.invoke(main, [
        "--config", str(cfg), "journal", "cash",
        "--deposit", "5", "--interest", "5", "--date", "2026-06-01",
    ])
    assert res.exit_code != 0
    assert "exactly one" in res.output.lower()
