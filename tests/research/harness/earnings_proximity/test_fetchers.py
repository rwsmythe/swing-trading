"""Unit tests for the earnings-proximity harness fetchers.

Covers cache hit / miss / stale, the yfinance MultiIndex squeeze pattern,
the absent-earnings-data contract (→ empty list, not None), and the
`threads=` kwarg regression guard from CLAUDE.md.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _flat_ohlcv(dates: list[date], base: float = 100.0) -> pd.DataFrame:
    """Build a flat-columns DataFrame mirroring yf.download single-ticker."""
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
    return pd.DataFrame(
        {
            "Open": [base + i for i in range(len(dates))],
            "High": [base + i + 0.5 for i in range(len(dates))],
            "Low": [base + i - 0.5 for i in range(len(dates))],
            "Close": [base + i + 0.1 for i in range(len(dates))],
            "Volume": [1_000_000 for _ in range(len(dates))],
        },
        index=idx,
    )


def _multiindex_ohlcv(tickers: list[str], dates: list[date]) -> pd.DataFrame:
    """Build a MultiIndex-columns DataFrame mirroring yf.download(group_by='ticker').

    Column MultiIndex: level 0 = ticker, level 1 = price field.
    """
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
    frames = {}
    for i, t in enumerate(tickers):
        base = 100.0 + 50 * i
        for field in ("Open", "High", "Low", "Close", "Volume"):
            col = (t, field)
            if field == "Volume":
                frames[col] = [1_000_000 for _ in range(len(dates))]
            elif field == "High":
                frames[col] = [base + j + 0.5 for j in range(len(dates))]
            elif field == "Low":
                frames[col] = [base + j - 0.5 for j in range(len(dates))]
            elif field == "Open":
                frames[col] = [base + j for j in range(len(dates))]
            else:  # Close
                frames[col] = [base + j + 0.1 for j in range(len(dates))]
    cols = pd.MultiIndex.from_tuples(list(frames.keys()), names=["Ticker", "Price"])
    return pd.DataFrame(frames, index=idx, columns=cols)


# ----------------------------------------------------------------------------
# OHLCV fetcher
# ----------------------------------------------------------------------------


def test_load_ohlcv_cache_miss_fetches_and_writes(tmp_path, monkeypatch):
    """Cache miss triggers yf.download, writes per-ticker parquet, returns dict."""
    from research.harness.earnings_proximity import fetchers as mod

    call_log = {"calls": 0, "kwargs": {}}
    dates = [date(2026, 4, 20), date(2026, 4, 21), date(2026, 4, 22)]

    def fake_download(*, tickers, start, end, **kwargs):
        call_log["calls"] += 1
        call_log["kwargs"] = kwargs
        call_log["tickers"] = list(tickers)
        return _multiindex_ohlcv(list(tickers), dates)

    monkeypatch.setattr(mod.yf, "download", fake_download)

    out = mod.load_ohlcv(
        ["AAPL", "MSFT"],
        start=date(2026, 4, 20),
        end=date(2026, 4, 23),
        cache_dir=tmp_path,
    )

    assert set(out.keys()) == {"AAPL", "MSFT"}
    for t in ("AAPL", "MSFT"):
        df = out[t]
        assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
        assert len(df) == 3
        assert (tmp_path / "ohlcv" / f"{t}.parquet").exists()
    assert call_log["calls"] == 1
    # yf.download MUST be called with threads=False (CLAUDE.md gotcha).
    assert call_log["kwargs"].get("threads") is False


def test_load_ohlcv_cache_hit_skips_fetch(tmp_path, monkeypatch):
    """Cache hit does NOT call yfinance; frame comes from disk."""
    from research.harness.earnings_proximity import fetchers as mod

    # Seed cache.
    dates = [date(2026, 4, 20), date(2026, 4, 21), date(2026, 4, 22)]
    seed = _flat_ohlcv(dates)
    (tmp_path / "ohlcv").mkdir()
    seed.to_parquet(tmp_path / "ohlcv" / "AAPL.parquet")

    def fake_download(**kwargs):  # pragma: no cover - must not be called
        raise AssertionError(f"yf.download should not be called on cache hit; kwargs={kwargs}")

    monkeypatch.setattr(mod.yf, "download", fake_download)

    out = mod.load_ohlcv(
        ["AAPL"],
        start=date(2026, 4, 20),
        end=date(2026, 4, 23),
        cache_dir=tmp_path,
    )
    assert "AAPL" in out
    assert len(out["AAPL"]) == 3


def test_load_ohlcv_cache_partial_coverage_refetches(tmp_path, monkeypatch):
    """Cache covers [Apr 20, Apr 22] but request covers through Apr 25 → refetch."""
    from research.harness.earnings_proximity import fetchers as mod

    seed_dates = [date(2026, 4, 20), date(2026, 4, 21), date(2026, 4, 22)]
    (tmp_path / "ohlcv").mkdir()
    _flat_ohlcv(seed_dates).to_parquet(tmp_path / "ohlcv" / "AAPL.parquet")

    call_log = {"calls": 0}
    fetch_dates = [
        date(2026, 4, 20), date(2026, 4, 21), date(2026, 4, 22),
        date(2026, 4, 23), date(2026, 4, 24),
    ]

    def fake_download(*, tickers, start, end, **kwargs):
        call_log["calls"] += 1
        return _multiindex_ohlcv(list(tickers), fetch_dates)

    monkeypatch.setattr(mod.yf, "download", fake_download)

    out = mod.load_ohlcv(
        ["AAPL"],
        start=date(2026, 4, 20),
        end=date(2026, 4, 25),
        cache_dir=tmp_path,
    )
    assert call_log["calls"] == 1
    assert len(out["AAPL"]) == 5


def test_load_ohlcv_squeezes_multiindex_single_ticker(tmp_path, monkeypatch):
    """Per CLAUDE.md gotcha: yf.download(group_by='ticker') on a single ticker
    still returns MultiIndex columns in newer yfinance. Squeeze to per-ticker."""
    from research.harness.earnings_proximity import fetchers as mod

    dates = [date(2026, 4, 20), date(2026, 4, 21)]

    def fake_download(*, tickers, start, end, **kwargs):
        # Single-ticker MultiIndex — the regression case.
        return _multiindex_ohlcv(list(tickers), dates)

    monkeypatch.setattr(mod.yf, "download", fake_download)

    out = mod.load_ohlcv(
        ["AAPL"],
        start=date(2026, 4, 20),
        end=date(2026, 4, 22),
        cache_dir=tmp_path,
    )
    df = out["AAPL"]
    # Flat columns after squeeze.
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    # Close is a Series (not a 1-column DataFrame).
    close = df["Close"]
    assert close.ndim == 1
    assert isinstance(float(close.iloc[-1]), float)


def test_load_ohlcv_does_not_call_ticker_history(tmp_path, monkeypatch):
    """OHLCV must go through yf.download (batched, accepts threads=False),
    NOT per-ticker Ticker.history() (which rejects threads= on yfinance >= 1.2)."""
    from research.harness.earnings_proximity import fetchers as mod

    def fake_download(*, tickers, start, end, **kwargs):
        return _multiindex_ohlcv(list(tickers), [date(2026, 4, 20)])

    monkeypatch.setattr(mod.yf, "download", fake_download)

    class PoisonTicker:
        def history(self, **kwargs):  # pragma: no cover
            raise AssertionError("Ticker.history() must not be called in OHLCV path")

    monkeypatch.setattr(mod.yf, "Ticker", lambda _t: PoisonTicker())

    mod.load_ohlcv(
        ["AAPL"],
        start=date(2026, 4, 20),
        end=date(2026, 4, 21),
        cache_dir=tmp_path,
    )
    # Absence of AssertionError is the assertion.


def test_load_ohlcv_creates_cache_dir(tmp_path, monkeypatch):
    from research.harness.earnings_proximity import fetchers as mod

    nested = tmp_path / "missing-parent" / "cache"

    def fake_download(*, tickers, start, end, **kwargs):
        return _multiindex_ohlcv(list(tickers), [date(2026, 4, 20)])

    monkeypatch.setattr(mod.yf, "download", fake_download)
    mod.load_ohlcv(["AAPL"], start=date(2026, 4, 20), end=date(2026, 4, 21), cache_dir=nested)
    assert (nested / "ohlcv" / "AAPL.parquet").exists()


# ----------------------------------------------------------------------------
# Earnings fetcher
# ----------------------------------------------------------------------------


def test_load_earnings_cache_miss_fetches_and_writes(tmp_path, monkeypatch):
    from research.harness.earnings_proximity import fetchers as mod

    ny = "America/New_York"
    idx = pd.DatetimeIndex([
        pd.Timestamp("2025-03-06 16:00", tz=ny),
        pd.Timestamp("2025-06-05 16:00", tz=ny),
        pd.Timestamp("2025-09-04 16:00", tz=ny),
    ])
    raw = pd.DataFrame({"EPS Estimate": [0.1, 0.2, 0.3]}, index=idx)

    call_log = {"calls": 0, "limit": None, "threads": "unset"}

    class FakeTicker:
        def __init__(self, t):
            call_log["ticker"] = t

        def get_earnings_dates(self, **kwargs):
            call_log["calls"] += 1
            call_log["limit"] = kwargs.get("limit")
            call_log["threads"] = kwargs.get("threads", "unset")
            if "threads" in kwargs:
                raise TypeError(
                    "get_earnings_dates() got an unexpected keyword argument 'threads'"
                )
            return raw

    monkeypatch.setattr(mod.yf, "Ticker", FakeTicker)

    out = mod.load_earnings(["SLDB"], cache_dir=tmp_path)

    assert out == {"SLDB": [date(2025, 3, 6), date(2025, 6, 5), date(2025, 9, 4)]}
    assert call_log["calls"] == 1
    assert call_log["limit"] == 30
    # threads= must NOT be passed (CLAUDE.md: TypeError on yfinance >= 1.2).
    assert call_log["threads"] == "unset"
    cache_file = tmp_path / "earnings" / "SLDB.json"
    assert cache_file.exists()
    payload = json.loads(cache_file.read_text())
    assert payload["ticker"] == "SLDB"
    assert payload["earnings_dates"] == ["2025-03-06", "2025-06-05", "2025-09-04"]
    assert "fetched_ts" in payload


def test_load_earnings_cache_hit_fresh_skips_fetch(tmp_path, monkeypatch):
    from research.harness.earnings_proximity import fetchers as mod

    (tmp_path / "earnings").mkdir()
    (tmp_path / "earnings" / "AAPL.json").write_text(
        json.dumps(
            {
                "ticker": "AAPL",
                "fetched_ts": datetime.now(timezone.utc).isoformat(),
                "earnings_dates": ["2026-01-28", "2026-04-30"],
            }
        )
    )

    class Poison:
        def get_earnings_dates(self, **_kw):  # pragma: no cover
            raise AssertionError("should not call yfinance on fresh cache hit")

    monkeypatch.setattr(mod.yf, "Ticker", lambda _t: Poison())

    out = mod.load_earnings(["AAPL"], cache_dir=tmp_path, cache_max_age_hours=24)
    assert out == {"AAPL": [date(2026, 1, 28), date(2026, 4, 30)]}


def test_load_earnings_cache_stale_refetches(tmp_path, monkeypatch):
    from research.harness.earnings_proximity import fetchers as mod

    (tmp_path / "earnings").mkdir()
    stale_ts = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    (tmp_path / "earnings" / "AAPL.json").write_text(
        json.dumps(
            {
                "ticker": "AAPL",
                "fetched_ts": stale_ts,
                "earnings_dates": ["2025-01-01"],
            }
        )
    )

    ny = "America/New_York"
    raw = pd.DataFrame(
        {"EPS Estimate": [0.5]},
        index=pd.DatetimeIndex([pd.Timestamp("2026-01-28 16:00", tz=ny)]),
    )

    called = {"n": 0}

    class FakeTicker:
        def __init__(self, _t):
            pass

        def get_earnings_dates(self, **_kw):
            called["n"] += 1
            return raw

    monkeypatch.setattr(mod.yf, "Ticker", FakeTicker)

    out = mod.load_earnings(["AAPL"], cache_dir=tmp_path, cache_max_age_hours=24)
    assert called["n"] == 1
    assert out == {"AAPL": [date(2026, 1, 28)]}


def test_load_earnings_absent_data_returns_empty_list(tmp_path, monkeypatch):
    """Per method record: absent earnings data → do NOT exclude, flag for review.

    The fetcher contract for empty data is `[]`, never `None`."""
    from research.harness.earnings_proximity import fetchers as mod

    class FakeTicker:
        def __init__(self, _t):
            pass

        def get_earnings_dates(self, **_kw):
            return pd.DataFrame()  # Empty — the OTC / newly-listed case.

    monkeypatch.setattr(mod.yf, "Ticker", FakeTicker)

    out = mod.load_earnings(["NEWCO"], cache_dir=tmp_path)
    assert out == {"NEWCO": []}
    payload = json.loads((tmp_path / "earnings" / "NEWCO.json").read_text())
    assert payload["earnings_dates"] == []


def test_load_earnings_absent_data_none_return_also_empty(tmp_path, monkeypatch):
    """yfinance can return None for get_earnings_dates on some tickers."""
    from research.harness.earnings_proximity import fetchers as mod

    class FakeTicker:
        def __init__(self, _t):
            pass

        def get_earnings_dates(self, **_kw):
            return None

    monkeypatch.setattr(mod.yf, "Ticker", FakeTicker)
    out = mod.load_earnings(["ZERO"], cache_dir=tmp_path)
    assert out == {"ZERO": []}


def test_load_earnings_extracts_ny_timezone_dates(tmp_path, monkeypatch):
    """Late-day ET release (16:00 ET = 21:00 UTC) must map to the ET calendar
    date, not UTC/local. A naive .date() on a UTC-converted timestamp would
    still land on the same day for 16:00 ET, so we stress-test with an
    11pm-ET row that would roll to the next day in UTC."""
    from research.harness.earnings_proximity import fetchers as mod

    ny = "America/New_York"
    # 2025-06-04 23:30 ET == 2025-06-05 03:30 UTC — .date() must NOT roll to Jun 5.
    idx = pd.DatetimeIndex([pd.Timestamp("2025-06-04 23:30", tz=ny)])
    raw = pd.DataFrame({"EPS Estimate": [0.0]}, index=idx)

    class FakeTicker:
        def __init__(self, _t):
            pass

        def get_earnings_dates(self, **_kw):
            return raw

    monkeypatch.setattr(mod.yf, "Ticker", FakeTicker)
    out = mod.load_earnings(["TEST"], cache_dir=tmp_path)
    assert out == {"TEST": [date(2025, 6, 4)]}


def test_load_earnings_dates_sorted_ascending(tmp_path, monkeypatch):
    from research.harness.earnings_proximity import fetchers as mod

    ny = "America/New_York"
    # yfinance returns newest-first; we want sorted ascending.
    idx = pd.DatetimeIndex([
        pd.Timestamp("2026-04-30 16:00", tz=ny),
        pd.Timestamp("2025-10-28 07:00", tz=ny),
        pd.Timestamp("2025-07-30 16:00", tz=ny),
    ])
    raw = pd.DataFrame({"EPS Estimate": [0.1, 0.2, 0.3]}, index=idx)

    class FakeTicker:
        def __init__(self, _t):
            pass

        def get_earnings_dates(self, **_kw):
            return raw

    monkeypatch.setattr(mod.yf, "Ticker", FakeTicker)
    out = mod.load_earnings(["AAPL"], cache_dir=tmp_path)
    assert out["AAPL"] == [date(2025, 7, 30), date(2025, 10, 28), date(2026, 4, 30)]
