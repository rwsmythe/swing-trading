"""CLI: swing pipeline run / list / force-clear."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
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


def test_skip_if_running_code_tree_mismatch_exits_78(tmp_path: Path, monkeypatch):
    """Task 2b (19-C): under --skip-if-running, a running code tree that diverges
    from cfg.project_root (worktree drift / wrong --config) fails closed with exit
    78 (EX_CONFIG) BEFORE any lease is acquired. Pre-fix: no guard -> the run
    proceeds (not 78); post-fix: deterministic 78. Distinguishes."""
    import swing.config as _swing_config

    runner, cfg_path, _ = _setup(tmp_path)
    # Force running-root != cfg.project_root deterministically (independent of
    # where pytest runs).
    monkeypatch.setattr(
        _swing_config, "__file__",
        str(tmp_path / "elsewhere" / "swing" / "config.py"),
    )
    r = runner.invoke(main, [
        "--config", str(cfg_path), "pipeline", "run", "--skip-if-running",
    ])
    assert r.exit_code == 78, r.output
    assert "config root" in r.output.lower() or "code tree" in r.output.lower()


def test_skip_if_running_code_tree_match_proceeds(tmp_path: Path, monkeypatch):
    """Task 2b (19-C) companion fence: with running-root == cfg.project_root the
    guard does NOT fire (it must not exit 78 on a legitimate MAIN-tree launch);
    the run proceeds to the collision path (exit 75 here)."""
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
        assert r.exit_code != 78, r.output
        assert r.exit_code == 75, r.output
    finally:
        lease.release(state="complete")


def test_unattended_schwab_construction_wired_non_interactive(monkeypatch):
    """C3 (19-C) static wiring: the non-setup Schwab construction site
    (_construct_v3_client_with_guard, the path construct_authenticated_client ->
    the market-data ladder uses under the scheduled task) passes
    open_browser_for_auth=False AND the raising call_on_auth=_raise_on_auth.
    A regression flipping either param FAILS -- no interactive/browser auth is
    reachable in the unattended launch context."""
    import schwabdev

    from swing.integrations.schwab import auth as schwab_auth

    captured: dict = {}

    class _FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(schwabdev, "Client", _FakeClient)
    schwab_auth._construct_v3_client_with_guard(
        tokens_path="tok.db", app_key="k", app_secret="s",
        callback_url="https://cb.example", encryption=None, timeout=5,
    )
    assert captured["open_browser_for_auth"] is False
    assert captured["call_on_auth"] is schwab_auth._raise_on_auth


def test_unattended_schwab_construction_never_prompts(monkeypatch):
    """C3 (19-C) behavioral guard (broader than the wiring check): if schwabdev's
    construction attempts to prompt (invokes the injected call_on_auth), the
    unattended path raises SchwabAuthError and NEVER touches input()/webbrowser."""
    import builtins
    import webbrowser

    import schwabdev

    from swing.integrations.schwab import auth as schwab_auth
    from swing.integrations.schwab.client import SchwabAuthError

    class _PromptingClient:
        def __init__(self, *, call_on_auth, open_browser_for_auth, **kwargs):
            # mimic schwabdev's missing/stale-token construction path invoking
            # the injected callback (v3 would otherwise prompt interactively).
            call_on_auth("https://consent.example/auth")

    monkeypatch.setattr(schwabdev, "Client", _PromptingClient)

    def _boom(*args, **kwargs):
        raise AssertionError("interactive primitive reached in unattended path")

    monkeypatch.setattr(builtins, "input", _boom)
    monkeypatch.setattr(webbrowser, "open", _boom)

    with pytest.raises(SchwabAuthError):
        schwab_auth._construct_v3_client_with_guard(
            tokens_path="tok.db", app_key="k", app_secret="s",
            callback_url="https://cb.example", encryption=None, timeout=5,
        )


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
