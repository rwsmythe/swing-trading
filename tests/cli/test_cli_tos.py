"""CLI: swing tos-import."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


def test_tos_import_dry_run(tmp_path: Path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])

    fixture = Path(__file__).parent.parent / "fixtures" / "tos" / "synthetic-tos.csv"
    r = runner.invoke(main, [
        "--config", str(cfg), "tos-import",
        "--csv", str(fixture), "--dry-run",
    ])
    assert r.exit_code == 0, r.output
    assert "deposit" in r.output.lower() or "DEP-001" in r.output
    assert "unmatched" in r.output.lower()
