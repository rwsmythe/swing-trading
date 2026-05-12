"""Phase 9 T-B.7 — CLI rename + alias deprecation contract pin.

The main coverage for the discrepancy + reconcile-tos CLI surface lives
at ``tests/cli/test_discrepancy_cli.py``. This thin module pins the
plan §A.2.2 binding (``swing journal import-tos`` is a deprecation alias
of ``swing journal reconcile-tos`` for one phase; alias prints stderr
WARNING + dispatches to the new service) in the journal-tests folder
per plan §B file map.
"""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


_TOS_CSV = """\
Account Trade History
Exec Time,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,Price,Net Price,Order Type
2026-05-12 10:00:00,STOCK,BUY,+10,OPENING,ABC,,,,10.0500,10.0500,MKT
"""


def _setup_cli(tmp_path: Path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    r = runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    assert r.exit_code == 0, r.output
    return runner, cfg, home / "swing-data" / "swing.db"


def test_reconcile_tos_command_exists_and_runs(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup_cli(tmp_path)
    csv = tmp_path / "tos.csv"
    csv.write_text(_TOS_CSV, encoding="utf-8")
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "reconcile-tos",
        "--csv-path", str(csv),
    ])
    assert r.exit_code == 0
    assert "Reconciliation run" in r.output


def test_import_tos_alias_prints_deprecation_warning_and_runs(
    tmp_path: Path,
) -> None:
    runner, cfg, db_path = _setup_cli(tmp_path)
    csv = tmp_path / "tos.csv"
    csv.write_text(_TOS_CSV, encoding="utf-8")
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "import-tos",
        "--csv-path", str(csv),
    ])
    assert r.exit_code == 0
    assert "deprecated" in r.output.lower()
    assert "reconcile-tos" in r.output


def test_legacy_top_level_tos_import_still_works(tmp_path: Path) -> None:
    """The top-level ``swing tos-import`` command was the V0 surface.

    Bundle B does NOT touch it (plan T-B.7 scopes to `journal import-tos`
    alias). This test ensures introducing the journal group commands
    did not regress the unrelated top-level command.
    """
    runner, cfg, db_path = _setup_cli(tmp_path)
    csv = tmp_path / "tos.csv"
    csv.write_text(_TOS_CSV, encoding="utf-8")
    r = runner.invoke(main, [
        "--config", str(cfg), "tos-import",
        "--csv", str(csv), "--dry-run",
    ])
    assert r.exit_code == 0
