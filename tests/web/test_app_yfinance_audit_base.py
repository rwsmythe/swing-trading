"""Phase 18 Arc 18-C: the web app installs a persistent surface='web' yfinance
audit base from the finalized app.state.cfg, so ALL web-triggered yfinance calls
(live-price AND archive reads reached from non-dashboard routes) record with
surface='web' -- proving the process-wide base, not a dashboard-only hook."""
from __future__ import annotations

import sqlite3
from datetime import date

import pandas as pd
import pytest

import swing.data.ohlcv_archive as arch
from swing.data import yfinance_audit_context as ctxmod
from swing.data.yfinance_audit_context import get_yfinance_audit_context


@pytest.fixture(autouse=True)
def _reset_ctx():
    ctxmod._reset_for_test()
    yield
    ctxmod._reset_for_test()


def test_create_app_sets_web_base_from_finalized_cfg(seeded_db):
    from swing.web.app import create_app
    cfg, cfg_path = seeded_db
    create_app(cfg, cfg_path)
    c = get_yfinance_audit_context()
    assert c is not None
    assert c.surface == "web"
    assert c.pipeline_run_id is None
    assert str(c.db_path) == str(cfg.paths.db_path)


def test_archive_chokepoint_under_web_base_records_web_surface(seeded_db, monkeypatch):
    # Construct the app (installs the web base) WITHOUT pre-seeding context, then
    # drive the ohlcv_archive chokepoint (the path a non-dashboard chart route
    # reaches via read_or_fetch_archive) and assert it records surface='web'.
    from swing.web.app import create_app
    cfg, cfg_path = seeded_db
    create_app(cfg, cfg_path)
    monkeypatch.setattr(arch.yf, "download", lambda *a, **k: pd.DataFrame(
        {"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5], "Volume": [9]},
        index=pd.DatetimeIndex([pd.Timestamp("2026-06-10")]),
    ))
    arch._yf_download_window("AAPL", start=date(2026, 6, 1), end=date(2026, 6, 10))
    conn = sqlite3.connect(cfg.paths.db_path)
    row = conn.execute(
        "SELECT call_type, surface FROM yfinance_calls"
    ).fetchone()
    conn.close()
    assert row == ("download_single", "web")
