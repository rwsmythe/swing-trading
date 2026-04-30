"""Tests for swing.prices.PriceFetcher (archive-helper-mocked)."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from swing.prices import PriceFetcher


def test_pricefetcher_get_consumes_archive_helper(tmp_path: Path, monkeypatch):
    """`PriceFetcher.get` calls `read_or_fetch_archive` with the resolved
    end_date and the constructor's archive_history_days; returns a DataFrame.

    Discriminating: under a regression that bypassed the helper (e.g.,
    fell back to direct yf.download for missing-archive case), the assertion
    on the helper-call-recording fails. Under a regression that passed the
    wrong end_date (e.g., today-as-naive-date instead of last_completed_session),
    the assertion on the recorded end_date fails.
    """
    recorded: dict = {}

    def fake_helper(ticker, *, end_date, cache_dir, archive_history_days):
        recorded["ticker"] = ticker
        recorded["end_date"] = end_date
        recorded["cache_dir"] = cache_dir
        recorded["archive_history_days"] = archive_history_days
        return pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [101.0, 102.0],
                "Low": [99.0, 100.0],
                "Close": [100.5, 101.5],
                "Volume": [1000, 1100],
            },
            index=pd.to_datetime([end_date - timedelta(days=1), end_date]),
        )

    monkeypatch.setattr("swing.prices.read_or_fetch_archive", fake_helper)

    fetcher = PriceFetcher(cache_dir=tmp_path, archive_history_days=1260)
    df = fetcher.get("AAPL", lookback_days=120, as_of_date=date(2026, 4, 28))

    assert recorded["ticker"] == "AAPL"
    assert recorded["end_date"] == date(2026, 4, 28)
    assert recorded["cache_dir"] == tmp_path
    assert recorded["archive_history_days"] == 1260
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_pricefetcher_get_slices_to_lookback_days(tmp_path: Path, monkeypatch):
    """`get(ticker, lookback_days, as_of_date)` returns only bars within
    `[as_of_date - lookback_days, as_of_date]`. The helper may return a
    deeper archive; PriceFetcher slices on the calendar window.
    """
    end_date = date(2026, 4, 28)
    deep_archive = pd.DataFrame(
        {
            "Open": [1.0] * 200,
            "High": [1.0] * 200,
            "Low": [1.0] * 200,
            "Close": [1.0] * 200,
            "Volume": [1] * 200,
        },
        index=pd.to_datetime([end_date - timedelta(days=199 - i) for i in range(200)]),
    )

    def fake_helper(ticker, *, end_date, cache_dir, archive_history_days):
        return deep_archive

    monkeypatch.setattr("swing.prices.read_or_fetch_archive", fake_helper)

    fetcher = PriceFetcher(cache_dir=tmp_path, archive_history_days=1260)
    df = fetcher.get("AAPL", lookback_days=30, as_of_date=end_date)

    earliest = df.index.min().date()
    assert earliest >= end_date - timedelta(days=30), (
        f"sliced too widely; earliest bar {earliest} is outside the 30-day lookback"
    )
    assert df.index.max().date() <= end_date


def test_pricefetcher_get_raises_on_empty_helper_result(tmp_path: Path, monkeypatch):
    """When `read_or_fetch_archive` returns None (delisted / bad ticker),
    `PriceFetcher.get` raises `ValueError` to preserve the prior API
    contract (callers may catch this exception)."""
    monkeypatch.setattr("swing.prices.read_or_fetch_archive", lambda *a, **kw: None)

    fetcher = PriceFetcher(cache_dir=tmp_path, archive_history_days=1260)
    with pytest.raises(ValueError, match="No data for"):
        fetcher.get("DELISTED", lookback_days=120, as_of_date=date(2026, 4, 28))


def test_pricefetcher_default_archive_history_days_is_5y(tmp_path: Path):
    """Constructor `archive_history_days` defaults to 1260 when omitted (kwarg-with-default
    preserves backward-compat with existing call sites that don't pass the kwarg)."""
    fetcher = PriceFetcher(cache_dir=tmp_path)
    assert fetcher.archive_history_days == 1260


def test_pricefetcher_clear_cache_removes_meta_and_tmp_files(tmp_path: Path):
    """`clear_cache` removes `*.parquet`, `*.meta.json`, and `*.parquet.tmp`
    orphan files. Returns count deleted."""
    (tmp_path / "AAPL.parquet").write_text("fake")
    (tmp_path / "AAPL.meta.json").write_text("{}")
    (tmp_path / "AAPL.parquet.tmp").write_text("orphan tmp")
    (tmp_path / "MSFT.parquet").write_text("fake")
    (tmp_path / "README.txt").write_text("not a cache file; preserved")

    fetcher = PriceFetcher(cache_dir=tmp_path)
    count = fetcher.clear_cache()

    assert count == 4  # AAPL.parquet, AAPL.meta.json, AAPL.parquet.tmp, MSFT.parquet
    assert not (tmp_path / "AAPL.parquet").exists()
    assert not (tmp_path / "AAPL.meta.json").exists()
    assert not (tmp_path / "AAPL.parquet.tmp").exists()
    assert not (tmp_path / "MSFT.parquet").exists()
    assert (tmp_path / "README.txt").exists()
