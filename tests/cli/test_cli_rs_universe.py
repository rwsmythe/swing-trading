"""CLI: swing rs-universe refresh — versioned regen + prior snapshot."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


def test_refresh_creates_versioned_file(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])

    monkeypatch.setattr(
        "swing.evaluation.rs_refresh.fetch_source_tickers",
        lambda source: ["AAPL", "MSFT", "NVDA", "GOOG"],
    )

    r = runner.invoke(main, [
        "--config", str(cfg), "rs-universe", "refresh", "--source", "spx_ndx",
    ])
    assert r.exit_code == 0, r.output

    universe_path = project / "reference" / "rs-universe.csv"
    assert universe_path.exists()
    content = universe_path.read_text(encoding="utf-8")
    assert "# version: 2026-04-18-" in content
    assert "AAPL" in content


def test_refresh_snapshots_prior(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)

    monkeypatch.setattr(
        "swing.evaluation.rs_refresh.fetch_source_tickers",
        lambda source: ["AAPL", "MSFT"],
    )
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])

    runner.invoke(main, ["--config", str(cfg), "rs-universe", "refresh", "--source", "spx_ndx"])

    snapshots = list((project / "reference").glob("rs-universe-*.csv"))
    assert len(snapshots) >= 1
