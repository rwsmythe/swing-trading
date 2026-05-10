"""Operator-facing CLI help text MUST NOT leak internal phase/tranche nomenclature.

Internal milestone tags ("Phase 6", "Tranche B-ops T4") are useful in commit
history and source comments but should not surface in `--help` output, which
is the operator's primary contract with the CLI.
"""
from __future__ import annotations

import pytest
from click.testing import CliRunner

from swing.cli import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_trade_review_help_no_phase_leak(runner: CliRunner) -> None:
    result = runner.invoke(main, ["trade", "review", "--help"])
    assert result.exit_code == 0, result.output
    assert "Phase" not in result.output, (
        f"`swing trade review --help` leaks internal phase nomenclature:\n"
        f"{result.output}"
    )


def test_review_group_help_no_phase_leak(runner: CliRunner) -> None:
    result = runner.invoke(main, ["review", "--help"])
    assert result.exit_code == 0, result.output
    assert "Phase" not in result.output, (
        f"`swing review --help` leaks internal phase nomenclature:\n"
        f"{result.output}"
    )


def test_review_complete_help_no_phase_leak(runner: CliRunner) -> None:
    """Defense-in-depth: subcommand under `swing review` group."""
    result = runner.invoke(main, ["review", "complete", "--help"])
    assert result.exit_code == 0, result.output
    assert "Phase" not in result.output, (
        f"`swing review complete --help` leaks internal phase nomenclature:\n"
        f"{result.output}"
    )


def test_trade_entry_help_no_phase_or_tranche_leak(runner: CliRunner) -> None:
    """`swing trade entry --help` MUST NOT contain 'Phase N' or 'Tranche'."""
    result = runner.invoke(main, ["trade", "entry", "--help"])
    assert result.exit_code == 0, result.output
    assert "Phase " not in result.output, (
        f"`swing trade entry --help` leaks 'Phase ' nomenclature:\n{result.output}"
    )
    assert "Tranche" not in result.output, (
        f"`swing trade entry --help` leaks 'Tranche' nomenclature:\n{result.output}"
    )


def test_trade_exit_help_no_tranche_leak(runner: CliRunner) -> None:
    result = runner.invoke(main, ["trade", "exit", "--help"])
    assert result.exit_code == 0, result.output
    assert "Tranche" not in result.output, (
        f"`swing trade exit --help` leaks 'Tranche' nomenclature:\n{result.output}"
    )


def test_trade_stop_adjust_help_no_tranche_leak(runner: CliRunner) -> None:
    result = runner.invoke(main, ["trade", "stop-adjust", "--help"])
    assert result.exit_code == 0, result.output
    assert "Tranche" not in result.output, (
        f"`swing trade stop-adjust --help` leaks 'Tranche' nomenclature:\n"
        f"{result.output}"
    )
