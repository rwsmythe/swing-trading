"""Phase 13 T1.SB0 Codex R3 Major #1 fix — yfinance window-ladder fallback
returns FULL archive history, NOT 60-row truncation.

Pre-fix: `_yf_window_fallback` at `swing/pipeline/runner.py` called
`fetch_daily_bars(ticker, n_bars=60, ...)`. The 60-row cap silently truncated
the chart-step bars-worker window (which slices to ``window_days=200``
calendar days AFTER the hook). Result: any pipeline run with a constructed
Schwab client whose ladder fell back to yfinance rendered/classified from
~60 business days instead of 200 calendar days.

Post-fix: `_yf_window_fallback` calls ``read_or_fetch_archive`` directly,
returning the full archive (~1260 business days under
``archive_history_days`` default). Bundle worker (60-bar SMA50 requirement)
is unaffected: `compute_smas` rolls over whatever it receives. Bars worker
gets sufficient history to slice to any V1 chart window.

Discriminator: invoke `_yf_window_fallback` via a constructed pipeline
marketdata cache; assert the returned DataFrame has >> 60 rows.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from swing.config import load
from tests.cli.test_cli_eval import _minimal_config


def _make_cfg(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    # _bars_hook opens a DB connection per call — schema must be ready.
    from swing.data.db import ensure_schema
    ensure_schema(cfg.paths.db_path).close()
    return cfg


def _full_archive_fixture(end: pd.Timestamp, n_rows: int = 1200) -> pd.DataFrame:
    """Simulates the full per-ticker archive (~5 years of business days)."""
    idx = pd.bdate_range(end=end, periods=n_rows)
    closes = [100.0 + i * 0.05 for i in range(n_rows)]
    return pd.DataFrame(
        {
            "Open": [c - 0.05 for c in closes],
            "High": [c + 0.30 for c in closes],
            "Low": [c - 0.30 for c in closes],
            "Close": closes,
            "Volume": [1_000_000 + i for i in range(n_rows)],
        },
        index=idx,
    )


def test_yf_window_fallback_returns_full_archive_not_60_row_truncation(
    tmp_path: Path, monkeypatch,
):
    """Codex R3 Major #1: yfinance fallback must NOT cap at 60 rows.

    Discriminator: post-fix, the returned DataFrame has > 60 rows (the
    full archive). Pre-fix, capped at 60 rows -> the bars worker's
    200-day slice cannot recover history.
    """
    from swing.pipeline.runner import _install_pipeline_marketdata_caches

    cfg = _make_cfg(tmp_path)
    end = pd.Timestamp("2026-04-30")
    fixture = _full_archive_fixture(end=end, n_rows=1200)

    def _stub_read_or_fetch_archive(ticker, *, end_date, cache_dir, archive_history_days):
        return fixture.loc[fixture.index.date <= end_date].copy()

    def _stub_session(now_dt):
        return end.date()

    monkeypatch.setattr(
        "swing.pipeline.runner.read_or_fetch_archive", _stub_read_or_fetch_archive,
    )
    # Patch the binding the runner's `_yf_window_fallback` actually consults
    # (Codex R4 Minor #1 fix 2026-05-18). Pre-fix the patch targeted the
    # source module `swing.evaluation.dates`, but the runner imports
    # `last_completed_session` at module load (line 36) — so its captured
    # binding lives at `swing.pipeline.runner.last_completed_session`.
    # Patching the source module did not affect the runner's binding;
    # the test happened to pass incidentally because the wall-clock-driven
    # fallback returned enough history anyway. Patching at the runner-
    # local binding makes the test deterministic + actually exercises
    # the intended end-date pin.
    monkeypatch.setattr(
        "swing.pipeline.runner.last_completed_session", _stub_session,
    )
    monkeypatch.setattr(
        "swing.web.ohlcv_cache.last_completed_session", _stub_session,
    )

    # Patch fetch_window_via_ladder at its source module (the runner does a
    # deferred `from swing.integrations.schwab.marketdata_ladder import
    # fetch_window_via_ladder` inside `_install_pipeline_marketdata_caches`;
    # patching at the source ensures the closure picks up the stub).
    # Stub falls through to yfinance fallback so we exercise the fix path.
    def _stub_ladder(ticker, *, start, end, cfg, schwab_client,
                    yfinance_fallback_fn, conn, surface, pipeline_run_id):
        window = yfinance_fallback_fn(ticker, start, end)
        return (window, "yfinance")

    monkeypatch.setattr(
        "swing.integrations.schwab.marketdata_ladder.fetch_window_via_ladder",
        _stub_ladder,
    )

    # Construct a mock Schwab client so _install_pipeline_marketdata_caches
    # installs the ladder hook (otherwise it returns (None, None)).
    mock_client = MagicMock()
    price_cache, ohlcv_cache = _install_pipeline_marketdata_caches(
        cfg, mock_client, pipeline_run_id=1,
    )
    assert price_cache is not None
    assert ohlcv_cache is not None
    assert ohlcv_cache._ladder_bars_fetcher is not None

    # Invoke get_or_fetch — which routes through the ladder hook → fallback.
    df = ohlcv_cache.get_or_fetch(ticker="AAPL", window_days=200)

    # Post-fix: 200 calendar days ≈ 140+ business days; pre-fix would have
    # capped at 60 rows from the n_bars=60 truncation. Assert > 60 rows.
    assert len(df) > 60, (
        f"yf_window_fallback returned too few rows ({len(df)}); "
        f"pre-fix 60-row truncation would have prevented full 200-day window. "
        f"Codex R3 Major #1 fix did not apply."
    )
    # And the window obeys the calendar-day slice.
    cutoff = end.date() - pd.Timedelta(days=200)
    assert all(d.date() >= cutoff for d in df.index), (
        f"some rows past cutoff {cutoff}"
    )
    assert all(d.date() <= end.date() for d in df.index)
