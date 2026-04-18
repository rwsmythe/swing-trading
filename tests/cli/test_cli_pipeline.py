"""CLI: swing pipeline run / list / force-clear."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    return runner, cfg_path, project


def test_pipeline_run_with_csv_arg(tmp_path: Path, monkeypatch):
    runner, cfg, project = _setup(tmp_path)
    csv = project / "data" / "finviz-inbox" / "finviz15Apr2026.csv"
    csv.parent.mkdir(parents=True, exist_ok=True)
    cols = "No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap"
    csv.write_text(cols + "\n1,AAPL,T,H,USA,180.0,2.5%,200000,1.5,5.0,200.0,150.0,3e9\n",
                   encoding="utf-8")

    closes = [100.0 + i * 0.5 for i in range(260)]
    idx = pd.bdate_range(end="2026-04-15", periods=260)
    df = pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1_000_000] * 260,
    }, index=idx)
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: df,
    )

    r = runner.invoke(main, ["--config", str(cfg), "pipeline", "run"])
    assert r.exit_code == 0, r.output
    assert "complete" in r.output.lower() or "run id" in r.output.lower()


def test_pipeline_list_shows_recent_runs(tmp_path: Path):
    runner, cfg, _ = _setup(tmp_path)
    r = runner.invoke(main, ["--config", str(cfg), "pipeline", "list"])
    assert r.exit_code == 0
    assert "no runs" in r.output.lower() or "id" in r.output.lower()


def test_force_clear_rejects_fresh_run(tmp_path: Path):
    """Spec §5.6: force-clear must refuse when run is not two-signal-stale."""
    from swing.pipeline.lease import acquire_lease

    runner, cfg_path, _ = _setup(tmp_path)
    from swing.config import load
    cfg = load(cfg_path)
    lease = acquire_lease(
        db_path=cfg.paths.db_path, trigger="scheduled",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    try:
        r = runner.invoke(main, [
            "--config", str(cfg_path), "pipeline", "force-clear", str(lease.run_id),
        ], input="y\n")
        assert r.exit_code != 0
        assert "staleness" in r.output.lower()
    finally:
        lease.release(state="complete")


def test_force_clear_bypass_works(tmp_path: Path):
    """--bypass-staleness-check allows clearing fresh run."""
    from swing.config import load
    from swing.pipeline.lease import acquire_lease

    runner, cfg_path, _ = _setup(tmp_path)
    cfg = load(cfg_path)
    lease = acquire_lease(
        db_path=cfg.paths.db_path, trigger="scheduled",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    r = runner.invoke(main, [
        "--config", str(cfg_path), "pipeline", "force-clear",
        str(lease.run_id), "--bypass-staleness-check",
    ], input="y\n")
    assert r.exit_code == 0, r.output
    assert "force-cleared" in r.output.lower()
