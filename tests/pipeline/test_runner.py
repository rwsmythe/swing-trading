"""Pipeline runner: orchestrates 9 steps, records per-step status, aborts on evaluation fail."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from swing.data.db import ensure_schema
from swing.data.repos.pipeline import find_run
from swing.pipeline.runner import run_pipeline_internal, RunResult


def _ohlcv(closes=None, end="2026-04-15"):
    closes = closes or [100.0 + i * 0.5 for i in range(260)]
    idx = pd.bdate_range(end=end, periods=len(closes))
    return pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1_000_000] * len(closes),
    }, index=idx)


def test_runner_completes_all_steps(tmp_path: Path, monkeypatch):
    """End-to-end happy path with mocked PriceFetcher + finviz CSV."""
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
        "1,AAPL,Tech,Hardware,USA,180.0,2.5%,200000,1.5,5.0,200.0,150.0,3000000000\n"
        "2,MSFT,Tech,Software,USA,420.0,1.5%,250000,1.2,4.5,440.0,330.0,3500000000\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )

    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert isinstance(result, RunResult)
    assert result.state == "complete"

    import sqlite3
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        run = find_run(conn, result.run_id)
        assert run.state == "complete"
        assert run.weather_status == "ok"
        assert run.evaluation_status == "ok"
        assert run.watchlist_status == "ok"
        assert run.recommendations_status == "ok"
        assert run.export_status == "ok"
    finally:
        conn.close()


def test_runner_aborts_on_evaluation_fail(tmp_path: Path, monkeypatch):
    """Spec §5.3: evaluation failure => abort. Watchlist/recommendations/charts/export skipped."""
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    from swing.config import load
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()

    csv = cfg.paths.finviz_inbox_dir / "finviz15Apr2026.csv"
    csv.parent.mkdir(parents=True, exist_ok=True)
    cols = "No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap"
    csv.write_text(cols + "\n1,AAPL,T,H,USA,180.0,2.5%,200000,1.5,5.0,200.0,150.0,3e9\n",
                   encoding="utf-8")

    def fail_get(self, ticker, lookback_days, *, as_of_date=None):
        if ticker == "QQQ":
            return _ohlcv()
        raise RuntimeError("simulated yfinance outage")

    monkeypatch.setattr("swing.prices.PriceFetcher.get", fail_get)

    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "failed"

    import sqlite3
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        run = find_run(conn, result.run_id)
        assert run.state == "failed"
        assert run.evaluation_status == "failed"
        assert run.watchlist_status in (None, "skipped")
        assert run.recommendations_status in (None, "skipped")
        assert run.export_status in (None, "skipped")
    finally:
        conn.close()
