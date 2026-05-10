"""Weather runner — fetch QQQ OHLCV, classify, persist."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from swing.data.db import connect
from swing.data.models import WeatherRun
from swing.data.repos.weather import upsert_weather_run
from swing.prices import PriceFetcher
from swing.weather.classifier import WeatherClassification, classify_weather


def run_weather(
    *, db_path: Path, fetcher: PriceFetcher, ticker: str = "QQQ",
    as_of_date: date | None = None, run_ts: str,
    lookback_days: int = 180,
) -> WeatherClassification:
    """Fetch OHLCV, classify, persist. Returns the classification.
    Caller is responsible for failure handling — exceptions propagate."""
    ohlcv = fetcher.get(ticker, lookback_days=lookback_days, as_of_date=as_of_date)
    classification = classify_weather(ohlcv)

    conn = connect(db_path)
    try:
        with conn:
            upsert_weather_run(conn, WeatherRun(
                id=None, run_ts=run_ts, asof_date=classification.asof_date,
                ticker=ticker, status=classification.status,
                close=classification.close,
                sma10=classification.sma10, sma20=classification.sma20,
                sma50=classification.sma50,
                slope20_5bar=classification.slope20_5bar,
                slope10_5bar=classification.slope10_5bar,
                rationale=classification.rationale,
            ))
    finally:
        conn.close()
    return classification
