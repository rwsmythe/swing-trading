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


def test_pipeline_run_blocked_default_exits_2(tmp_path: Path):
    """Task 1 (19-C) characterization fence: bare `pipeline run` maps a
    concurrent-run collision (ConcurrentRunBlockedError -> RunResult
    state='blocked') to exit code 2. This is the DEFAULT (no --skip-if-running)
    path; Task 2 must leave it unchanged.
    """
    from swing.config import load
    from swing.pipeline.lease import acquire_lease

    runner, cfg_path, _ = _setup(tmp_path)
    cfg = load(cfg_path)
    lease = acquire_lease(
        db_path=cfg.paths.db_path, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    try:
        r = runner.invoke(main, ["--config", str(cfg_path), "pipeline", "run"])
        assert r.exit_code == 2, r.output
        assert "blocked" in r.output.lower(), r.output
    finally:
        lease.release(state="complete")


def _align_code_tree(monkeypatch, project: Path) -> None:
    """Point the imported swing.config module's __file__ at the test project so
    the Task-2b unattended code-tree guard (exit 78) sees running-root ==
    cfg.project_root and does NOT fire — letting the --skip-if-running collision /
    completion paths run under a tmp config.
    """
    import swing.config as _swing_config
    monkeypatch.setattr(_swing_config, "__file__", str(project / "swing" / "config.py"))


def _seed_completable_run(project: Path, monkeypatch) -> None:
    """Finviz CSV + fake prices so a real `pipeline run` completes (mirrors
    test_pipeline_run_with_csv_arg)."""
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


def test_skip_if_running_blocked_exits_75(tmp_path: Path, monkeypatch):
    """Task 2 (19-C): WITH --skip-if-running, a collision maps to exit 75
    (EX_TEMPFAIL) + an ASCII 'skipped' message. Pre-fix: the flag does not exist
    so click UsageError exits 2; post-fix: exit 75. Distinguishes."""
    from swing.config import load
    from swing.pipeline.lease import acquire_lease

    runner, cfg_path, project = _setup(tmp_path)
    _align_code_tree(monkeypatch, project)
    cfg = load(cfg_path)
    lease = acquire_lease(
        db_path=cfg.paths.db_path, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    try:
        r = runner.invoke(main, [
            "--config", str(cfg_path), "pipeline", "run", "--skip-if-running",
        ])
        assert r.exit_code == 75, r.output
        assert "skipped" in r.output.lower(), r.output
    finally:
        lease.release(state="complete")


def test_skip_if_running_completed_exits_0(tmp_path: Path, monkeypatch):
    """Task 2 (19-C): WITH --skip-if-running, a normal completed run still exits
    0 (the flag only changes the collision mapping)."""
    runner, cfg_path, project = _setup(tmp_path)
    _align_code_tree(monkeypatch, project)
    _seed_completable_run(project, monkeypatch)
    r = runner.invoke(main, [
        "--config", str(cfg_path), "pipeline", "run", "--skip-if-running",
    ])
    assert r.exit_code == 0, r.output


def test_skip_if_running_flag_absent_still_exits_2(tmp_path: Path):
    """Task 2 (19-C) backward-compat fence: WITHOUT the flag, a collision still
    exits 2 (co-located with the flag tests)."""
    from swing.config import load
    from swing.pipeline.lease import acquire_lease

    runner, cfg_path, _ = _setup(tmp_path)
    cfg = load(cfg_path)
    lease = acquire_lease(
        db_path=cfg.paths.db_path, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    try:
        r = runner.invoke(main, ["--config", str(cfg_path), "pipeline", "run"])
        assert r.exit_code == 2, r.output
    finally:
        lease.release(state="complete")


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
