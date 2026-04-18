"""Weather runner — integrates classifier + price fetch + repo write."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from swing.data.db import ensure_schema
from swing.data.repos.weather import get_latest_for_date
from swing.weather.runner import run_weather


def _ohlcv():
    closes = [100.0 + i * 0.5 for i in range(60)]
    idx = pd.bdate_range(end="2026-04-15", periods=60)
    return pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1_000_000] * 60,
    }, index=idx)


def test_run_weather_writes_row(tmp_path: Path):
    db_path = tmp_path / "swing.db"
    ensure_schema(db_path).close()

    fake_fetcher = MagicMock()
    fake_fetcher.get.return_value = _ohlcv()

    result = run_weather(
        db_path=db_path, fetcher=fake_fetcher,
        ticker="QQQ", as_of_date=None, run_ts="2026-04-15T21:49:00",
    )
    assert result.status == "Bullish"

    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        row = get_latest_for_date(conn, "2026-04-15", ticker="QQQ")
        assert row is not None
        assert row.status == "Bullish"
        assert row.run_ts == "2026-04-15T21:49:00"
    finally:
        conn.close()
    fake_fetcher.get.assert_called_once_with("QQQ", lookback_days=180, as_of_date=None)


def test_run_weather_upserts_on_repeat(tmp_path: Path):
    db_path = tmp_path / "swing.db"
    ensure_schema(db_path).close()

    fake_fetcher = MagicMock()
    fake_fetcher.get.return_value = _ohlcv()

    run_weather(db_path=db_path, fetcher=fake_fetcher, ticker="QQQ",
                as_of_date=None, run_ts="2026-04-15T21:49:00")
    run_weather(db_path=db_path, fetcher=fake_fetcher, ticker="QQQ",
                as_of_date=None, run_ts="2026-04-15T22:00:00")

    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT COUNT(*) FROM weather_runs WHERE asof_date='2026-04-15' AND ticker='QQQ'"
        ).fetchone()
        assert rows[0] == 1
    finally:
        conn.close()
