"""Weather repo — insert/upsert/get_latest. Caller wraps in `with conn:`."""
from __future__ import annotations

import sqlite3

from swing.data.models import WeatherRun

_INSERT_SQL = """
INSERT INTO weather_runs
    (run_ts, asof_date, ticker, status, close, sma10, sma20, sma50,
     slope20_5bar, slope10_5bar, rationale)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_UPSERT_SQL = _INSERT_SQL + """
ON CONFLICT(asof_date, ticker) DO UPDATE SET
    run_ts = excluded.run_ts,
    status = excluded.status,
    close = excluded.close,
    sma10 = excluded.sma10,
    sma20 = excluded.sma20,
    sma50 = excluded.sma50,
    slope20_5bar = excluded.slope20_5bar,
    slope10_5bar = excluded.slope10_5bar,
    rationale = excluded.rationale
"""


def _params(w: WeatherRun) -> tuple:
    return (w.run_ts, w.asof_date, w.ticker, w.status, w.close,
            w.sma10, w.sma20, w.sma50, w.slope20_5bar, w.slope10_5bar, w.rationale)


def insert_weather_run(conn: sqlite3.Connection, w: WeatherRun) -> int:
    cur = conn.execute(_INSERT_SQL, _params(w))
    return int(cur.lastrowid)


def upsert_weather_run(conn: sqlite3.Connection, w: WeatherRun) -> int:
    cur = conn.execute(_UPSERT_SQL, _params(w))
    return int(cur.lastrowid)


def get_latest_for_date(
    conn: sqlite3.Connection, asof_date: str, *, ticker: str = "QQQ"
) -> WeatherRun | None:
    row = conn.execute(
        """
        SELECT id, run_ts, asof_date, ticker, status, close, sma10, sma20, sma50,
               slope20_5bar, slope10_5bar, rationale
        FROM weather_runs
        WHERE asof_date = ? AND ticker = ?
        """,
        (asof_date, ticker),
    ).fetchone()
    if row is None:
        return None
    return WeatherRun(
        id=row[0], run_ts=row[1], asof_date=row[2], ticker=row[3], status=row[4],
        close=row[5], sma10=row[6], sma20=row[7], sma50=row[8],
        slope20_5bar=row[9], slope10_5bar=row[10], rationale=row[11],
    )
