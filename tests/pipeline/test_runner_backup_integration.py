"""Pipeline runner triggers a weekly DB backup before any lease/DB writes."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from swing.data.backup import compute_backup_destination
from swing.data.db import ensure_schema


def _ohlcv(closes=None, end="2026-04-15"):
    closes = closes or [100.0 + i * 0.5 for i in range(260)]
    idx = pd.bdate_range(end=end, periods=len(closes))
    return pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1_000_000] * len(closes),
    }, index=idx)


def _setup_cfg(tmp_path: Path):
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    from swing.config import load
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()

    inbox = cfg.paths.finviz_inbox_dir
    inbox.mkdir(parents=True, exist_ok=True)
    csv = inbox / "finviz15Apr2026.csv"
    cols = ["No.", "Ticker", "Sector", "Industry", "Country", "Price", "Change",
            "Average Volume", "Relative Volume", "Average True Range",
            "52-Week High", "52-Week Low", "Market Cap"]
    csv.write_text(
        ",".join(cols) + "\n"
        "1,AAPL,Tech,Hardware,USA,180.0,2.5%,200000,1.5,5.0,200.0,150.0,3000000000\n",
        encoding="utf-8",
    )
    return cfg


def test_runner_creates_weekly_backup_on_first_run_of_week(tmp_path: Path, monkeypatch):
    """Happy path — backup file present at canonical name after a complete run."""
    cfg = _setup_cfg(tmp_path)
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )
    from swing.pipeline.runner import run_pipeline_internal
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    expected = compute_backup_destination(datetime.now(), cfg.paths.backups_dir)
    assert expected.exists(), f"missing backup at {expected}"


def test_runner_skips_backup_when_current_week_already_present(tmp_path: Path, monkeypatch):
    """Pre-existing backup for the current ISO week → should_backup False → no
    re-copy. We assert the existing file's bytes are NOT overwritten."""
    cfg = _setup_cfg(tmp_path)
    cfg.paths.backups_dir.mkdir(parents=True, exist_ok=True)
    placeholder = compute_backup_destination(datetime.now(), cfg.paths.backups_dir)
    placeholder.write_bytes(b"sentinel-bytes-not-a-real-db")

    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )
    from swing.pipeline.runner import run_pipeline_internal
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    assert placeholder.read_bytes() == b"sentinel-bytes-not-a-real-db"


def test_runner_continues_when_backup_raises(tmp_path: Path, monkeypatch):
    """Backup failure (e.g., disk full, OSError) MUST NOT abort the pipeline.
    Operator visibility is via the pipeline log, not a failed run state."""
    cfg = _setup_cfg(tmp_path)

    def boom(*a, **kw):
        raise OSError("simulated disk full")

    monkeypatch.setattr("swing.pipeline.runner.do_backup", boom)
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )
    from swing.pipeline.runner import run_pipeline_internal
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete", (
        f"pipeline must remain operational on backup failure, got {result.state}"
    )


def test_runner_invokes_prune_after_successful_backup(tmp_path: Path, monkeypatch):
    """After a successful do_backup, prune_old_backups runs with keep=12."""
    cfg = _setup_cfg(tmp_path)
    calls: list[tuple] = []

    real_do = __import__("swing.data.backup", fromlist=["do_backup"]).do_backup
    real_prune = __import__("swing.data.backup", fromlist=["prune_old_backups"]).prune_old_backups

    def spy_do(db_path, dest_dir, **kw):
        calls.append(("do", db_path, dest_dir))
        return real_do(db_path, dest_dir, **kw)

    def spy_prune(dest_dir, keep):
        calls.append(("prune", dest_dir, keep))
        return real_prune(dest_dir, keep)

    monkeypatch.setattr("swing.pipeline.runner.do_backup", spy_do)
    monkeypatch.setattr("swing.pipeline.runner.prune_old_backups", spy_prune)
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )
    from swing.pipeline.runner import run_pipeline_internal
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    kinds = [c[0] for c in calls]
    assert kinds == ["do", "prune"], f"expected do→prune sequence, got {kinds}"
    prune_call = next(c for c in calls if c[0] == "prune")
    assert prune_call[2] == 12, f"keep should be 12, got {prune_call[2]}"


def test_runner_continues_when_prune_raises(tmp_path: Path, monkeypatch):
    """Prune failure (e.g., permissions) MUST NOT abort the pipeline either —
    the backup itself already succeeded, so the run is healthy."""
    cfg = _setup_cfg(tmp_path)

    def boom(*a, **kw):
        raise OSError("simulated permission denied on prune")

    monkeypatch.setattr("swing.pipeline.runner.prune_old_backups", boom)
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )
    from swing.pipeline.runner import run_pipeline_internal
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"
