"""Weather repo round-trip — insert + get_latest_for + upsert by (date, ticker)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from swing.data.db import ensure_schema
from swing.data.models import WeatherRun
from swing.data.repos.weather import insert_weather_run, get_latest_for_date, upsert_weather_run


def _wr(asof: str, status: str = "Bullish", close: float = 480.0) -> WeatherRun:
    return WeatherRun(
        id=None, run_ts=f"{asof}T21:49:00", asof_date=asof, ticker="QQQ",
        status=status, close=close, sma10=475.0, sma20=470.0, sma50=460.0,
        slope20_5bar=0.5, slope10_5bar=0.7, rationale="bullish setup",
    )


def test_insert_and_get_latest_for_date(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            wid = insert_weather_run(conn, _wr("2026-04-15"))
        assert wid > 0

        got = get_latest_for_date(conn, "2026-04-15", ticker="QQQ")
        assert got is not None
        assert got.status == "Bullish"
        assert got.id == wid

        assert get_latest_for_date(conn, "2026-04-16", ticker="QQQ") is None
    finally:
        conn.close()


def test_upsert_replaces_same_date(tmp_path: Path):
    """Re-running the classifier for the same (asof_date, ticker) updates in place — spec §3 ux_weather_asof_ticker."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            upsert_weather_run(conn, _wr("2026-04-15", status="Caution"))
        with conn:
            upsert_weather_run(conn, _wr("2026-04-15", status="Bullish"))

        rows = conn.execute("SELECT status FROM weather_runs WHERE asof_date='2026-04-15'").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "Bullish"
    finally:
        conn.close()
