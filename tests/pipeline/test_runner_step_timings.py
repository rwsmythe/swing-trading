# tests/pipeline/test_runner_step_timings.py
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from swing.config import load
from swing.data.db import ensure_schema
from swing.data.repos.pipeline_step_timings import list_step_timings, step_durations_by_name
from swing.pipeline.runner import run_pipeline_internal
from tests.cli.test_cli_eval import _minimal_config


def _ohlcv(end="2026-04-15"):
    closes = [100.0 + i * 0.5 for i in range(260)]
    idx = pd.bdate_range(end=end, periods=len(closes))
    return pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1_000_000] * len(closes),
    }, index=idx)


def _setup_cfg(tmp_path: Path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = load(_minimal_config(project, home))
    ensure_schema(cfg.paths.db_path).close()
    inbox = cfg.paths.finviz_inbox_dir
    inbox.mkdir(parents=True, exist_ok=True)
    cols = ("No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,"
            "Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap")
    (inbox / "finviz15Apr2026.csv").write_text(
        cols + "\n1,AAPL,T,H,USA,180.0,2.5%,200000,1.5,5.0,200.0,150.0,3e9\n",
        encoding="utf-8",
    )
    return cfg


def test_run_persists_timings_on_complete(tmp_path, monkeypatch):
    cfg = _setup_cfg(tmp_path)
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"
    conn = sqlite3.connect(cfg.paths.db_path)  # tuple rows -> positional repo OK
    try:
        rows = list_step_timings(conn, result.run_id)
        assert len(rows) >= 2  # the finally flushed the real ledger
        # ordinals are unique + monotonic from 0
        assert [r.ordinal for r in rows] == list(range(len(rows)))
        # _setup_cfg writes a CSV -> this is the NON-empty path: site-1 never fires,
        # so finviz_fetch appears EXACTLY once (weather then finviz_fetch). Discriminating:
        # a naive last-wins persist or a dropped-row bug breaks the count/sum equality.
        names = [r.step_name for r in rows]
        assert names.count("finviz_fetch") == 1
        assert "weather" in names
        totals = step_durations_by_name(conn, result.run_id)
        assert totals["finviz_fetch"] == sum(
            r.duration_ms for r in rows if r.step_name == "finviz_fetch"
        )
    finally:
        conn.close()


def test_run_persists_partial_timings_on_failed(tmp_path, monkeypatch):
    cfg = _setup_cfg(tmp_path)

    def fail_get(self, ticker, lookback_days, *, as_of_date=None):
        if ticker == "QQQ":
            return _ohlcv()
        raise RuntimeError("simulated yfinance outage")  # evaluation aborts

    monkeypatch.setattr("swing.prices.PriceFetcher.get", fail_get)
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "failed"
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        rows = list_step_timings(conn, result.run_id)
        assert len(rows) >= 1  # partial timings persisted via the finally flush
    finally:
        conn.close()


def test_run_persists_timings_on_force_clear(tmp_path, monkeypatch):
    """spec §6.4 force_cleared mid-step: timings persist via the flush's fresh
    connect() despite the revoked lease. Mirrors test_runner.py's
    test_runner_detects_mid_run_lease_revocation revocation mechanism."""
    import sqlite3
    from swing.data.repos.pipeline import force_clear

    cfg = _setup_cfg(tmp_path)
    cleared = {"done": False}

    def fetcher_get(self, ticker, lookback_days, *, as_of_date=None):
        # First OHLCV fetch -> force-clear the running lease (admin revoke between
        # step boundaries), then return normally so the step body proceeds toward
        # the LeaseRevokedError on its next write.
        if not cleared["done"]:
            conn = sqlite3.connect(cfg.paths.db_path)
            try:
                row = conn.execute(
                    "SELECT id FROM pipeline_runs WHERE state='running'"
                ).fetchone()
                if row is not None:
                    with conn:
                        force_clear(conn, run_id=row[0], error_message="test-revoke")
                    cleared["done"] = True
            finally:
                conn.close()
        return _ohlcv()

    monkeypatch.setattr("swing.prices.PriceFetcher.get", fetcher_get)
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "force_cleared"
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        # Partial timings persisted by the finally flush via a FRESH connect()
        # (no lease token needed); the force_cleared pipeline_runs row survives.
        assert len(list_step_timings(conn, result.run_id)) >= 1
    finally:
        conn.close()


def test_run_survives_flush_failure(tmp_path, monkeypatch, caplog):
    """spec §6.4b at the REAL finally boundary: if flush raises, run_pipeline_internal
    swallows + logs it and the RunResult is unchanged. This catches a runner that
    forgot the try/except (the lease-level test cannot -- it mirrors the wrapper by
    hand)."""
    import logging as _logging

    from swing.pipeline.lease import Lease

    cfg = _setup_cfg(tmp_path)
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )

    def boom(self):
        raise RuntimeError("flush exploded")

    monkeypatch.setattr(Lease, "flush_step_timings", boom)
    with caplog.at_level(_logging.ERROR, logger="swing.pipeline.runner"):
        result = run_pipeline_internal(cfg=cfg, trigger="manual")
    # (a) outcome unchanged -- flush failure does not flip a complete run to failed.
    assert result.state == "complete"
    # (b) the runner's finally logged the flush error (proves the try/except exists).
    assert any("flush failed" in r.getMessage() for r in caplog.records)
