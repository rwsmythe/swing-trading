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
    from datetime import date
    assert f"# version: {date.today().isoformat()}-" in content
    assert "AAPL" in content


def test_same_day_refresh_increments_n_suffix(tmp_path: Path, monkeypatch):
    """Adversarial review Batch 5 Round 1 Minor 3: running refresh twice on
    the same calendar day must increment the `-N` suffix (per spec §4.1's
    `YYYY-MM-DD-<n>`)."""
    from swing.evaluation.rs_refresh import refresh_rs_universe

    dest = tmp_path / "reference" / "rs-universe.csv"
    monkeypatch.setattr(
        "swing.evaluation.rs_refresh.fetch_source_tickers",
        lambda source: ["AAPL", "MSFT"],
    )
    from datetime import date
    fixed = date(2026, 4, 18)
    v1 = refresh_rs_universe(dest=dest, source="spx_ndx", today=fixed)
    v2 = refresh_rs_universe(dest=dest, source="spx_ndx", today=fixed)
    assert v1 == "2026-04-18-1"
    assert v2 == "2026-04-18-2"
    # Prior snapshot from the v1→v2 refresh exists
    assert (tmp_path / "reference" / "rs-universe-2026-04-18-1.csv").exists()


def test_refresh_rejects_unsafe_prior_version(tmp_path: Path, monkeypatch):
    """Adversarial review Batch 5 Round 1 Major 2: if the prior rs-universe.csv
    has a version string with filesystem-unsafe characters, the refresh must
    refuse to snapshot rather than silently produce a corrupt filename."""
    from swing.evaluation.rs_refresh import refresh_rs_universe
    import pytest as _pt

    dest = tmp_path / "reference" / "rs-universe.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        "# version: ../evil/../../../etc\n"
        "# source: test\n# columns: ticker\nticker\nAAPL\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "swing.evaluation.rs_refresh.fetch_source_tickers",
        lambda source: ["AAPL"],
    )
    from datetime import date
    with _pt.raises(ValueError, match="unsafe version string"):
        refresh_rs_universe(dest=dest, source="spx_ndx", today=date(2026, 4, 18))


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
