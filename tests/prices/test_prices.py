"""Tests for swing.prices."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from swing.prices import PriceFetcher


def _fake_df(n: int = 2) -> pd.DataFrame:
    closes = [10.0 + i * 0.5 for i in range(n)]
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [c + 0.1 for c in closes],
            "Low": [c - 0.1 for c in closes],
            "Close": closes,
            "Volume": [1_000_000] * n,
        },
        index=pd.bdate_range(start="2026-04-15", periods=n),
    )


def test_cache_miss_calls_fetch(tmp_path: Path):
    fetcher = PriceFetcher(cache_dir=tmp_path)
    with patch.object(fetcher, "_fetch_from_yf", return_value=_fake_df(2)) as mock_fetch:
        result = fetcher.get("AAPL", lookback_days=10)
    mock_fetch.assert_called_once()
    assert len(result) == 2


def test_cache_hit_skips_fetch(tmp_path: Path):
    fetcher = PriceFetcher(cache_dir=tmp_path)
    with patch.object(fetcher, "_fetch_from_yf", return_value=_fake_df(1)):
        fetcher.get("AAPL", lookback_days=10)
    # Second call should hit cache — _fetch_from_yf not called
    with patch.object(fetcher, "_fetch_from_yf") as mock_fetch:
        result = fetcher.get("AAPL", lookback_days=10)
        mock_fetch.assert_not_called()
    assert len(result) == 1


def test_cache_miss_on_different_ticker(tmp_path: Path):
    fetcher = PriceFetcher(cache_dir=tmp_path)

    def side_effect(ticker, lookback, as_of_date):
        if ticker == "AAPL":
            return _fake_df(1)
        return _fake_df(1)

    with patch.object(fetcher, "_fetch_from_yf", side_effect=side_effect) as mock_fetch:
        fetcher.get("AAPL", lookback_days=10)
        fetcher.get("MSFT", lookback_days=10)
    assert mock_fetch.call_count == 2


def test_get_honors_as_of_date(tmp_path: Path):
    fetcher = PriceFetcher(cache_dir=tmp_path)
    fake = _fake_df(3)  # 4/15, 4/16, 4/17
    with patch.object(fetcher, "_fetch_from_yf", return_value=fake):
        fetcher.get("AAPL", lookback_days=10, as_of_date=date(2026, 4, 16))
    cached_files = list(tmp_path.glob("*.parquet"))
    assert any("asof-2026-04-16" in p.name for p in cached_files)
