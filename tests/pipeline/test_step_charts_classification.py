"""Pipeline tests for `_step_charts` classification persistence."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from swing.data.db import ensure_schema
from swing.data.repos.pattern_classifications import list_classifications_for_run
from swing.pipeline.runner import run_pipeline_internal


def _flag_bars(periods: int = 200) -> pd.DataFrame:
    from tests.evaluation.patterns._synthetic import make_flag_bars

    flag = make_flag_bars(pre_run_bars=50, pole_bars=10, flag_bars=8)
    pad_n = max(0, periods - len(flag))
    if pad_n == 0:
        return flag
    pad_start = flag.index[0] - pd.tseries.offsets.BDay(pad_n)
    pad_idx = pd.bdate_range(pad_start, periods=pad_n)
    pad = pd.DataFrame({
        "Open": 100.0,
        "High": 100.0,
        "Low": 100.0,
        "Close": 100.0,
        "Volume": 1_400_000.0,
    }, index=pad_idx)
    combined = pd.concat([pad, flag])
    return combined[~combined.index.duplicated(keep="last")]


def _flat_bars(periods: int) -> pd.DataFrame:
    idx = pd.bdate_range(end="2026-04-15", periods=periods)
    closes = [100.0] * periods
    return pd.DataFrame({
        "Open": closes,
        "High": closes,
        "Low": closes,
        "Close": closes,
        "Volume": [1_000_000.0] * periods,
    }, index=idx)


def _csv(inbox: Path) -> Path:
    inbox.mkdir(parents=True, exist_ok=True)
    csv = inbox / "finviz15Apr2026.csv"
    cols = (
        "No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,"
        "Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap"
    )
    csv.write_text(
        cols + "\n"
        "1,AAPL,T,H,USA,180.0,2.5%,200000,1.5,5.0,200.0,150.0,3e9\n",
        encoding="utf-8",
    )
    return csv


def _seed_active_watchlist_entry(
    db_path: Path, *, ticker: str, entry_target: float, last_close: float,
) -> None:
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO watchlist
                   (ticker, added_date, last_qualified_date, status,
                    qualification_count, not_qualified_streak,
                    last_data_asof_date, entry_target, initial_stop_target,
                    last_close)
                   VALUES (?, '2026-04-15', '2026-04-15', 'watch', 1, 0,
                           '2026-04-15', ?, NULL, ?)""",
                (ticker, entry_target, last_close),
            )
    finally:
        conn.close()


def _make_cfg(tmp_path: Path):
    from swing.config import load
    from tests.cli.test_cli_eval import _minimal_config

    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg


def _stub_render(*, ticker, ohlcv, pivot, stop, output_path, pattern_overlay=None):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"stub-png")
    return output_path


def test_step_charts_happy_path_persists_classification_row(
    tmp_path: Path, monkeypatch,
):
    cfg = _make_cfg(tmp_path)
    _csv(cfg.paths.finviz_inbox_dir)
    _seed_active_watchlist_entry(
        cfg.paths.db_path, ticker="AAPL", entry_target=180.0, last_close=180.0,
    )

    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _flag_bars(),
    )
    monkeypatch.setattr("swing.pipeline.runner.render_chart", _stub_render)

    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        rows = list_classifications_for_run(conn, pipeline_run_id=result.run_id)
        assert "AAPL" in rows
        row = rows["AAPL"]
        assert isinstance(row.pattern, str)
        assert row.pattern in ("flag", "none")
        assert row.computed_at is not None
    finally:
        conn.close()


def test_step_charts_too_few_bars_persists_pattern_none(
    tmp_path: Path, monkeypatch,
):
    cfg = _make_cfg(tmp_path)
    _csv(cfg.paths.finviz_inbox_dir)
    _seed_active_watchlist_entry(
        cfg.paths.db_path, ticker="AAPL", entry_target=180.0, last_close=180.0,
    )

    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _flat_bars(20),
    )
    monkeypatch.setattr("swing.pipeline.runner.render_chart", _stub_render)

    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        rows = list_classifications_for_run(conn, pipeline_run_id=result.run_id)
        assert "AAPL" in rows
        assert rows["AAPL"].pattern == "none"
    finally:
        conn.close()
