"""Unit tests for the earnings-proximity harness fetchers.

Covers cache hit / miss / stale, the yfinance MultiIndex squeeze pattern,
the absent-earnings-data contract (→ empty list, not None), and the
`threads=` kwarg regression guard from CLAUDE.md.
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pandas as pd

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
                "fetched_ts": datetime.now(UTC).isoformat(),
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
    stale_ts = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
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


def test_load_ohlcv_with_stats_reports_per_ticker_hit_miss(tmp_path, monkeypatch):
    """Fix for adversarial-review issue 2: fetchers must report actual
    per-ticker cache outcomes, not a file-existence count."""
    from research.harness.earnings_proximity import fetchers as mod

    # Pre-seed AAPL cache covering the request window; MSFT has no cache.
    seed_dates = [date(2026, 4, 20), date(2026, 4, 21), date(2026, 4, 22)]
    (tmp_path / "ohlcv").mkdir()
    _flat_ohlcv(seed_dates).to_parquet(tmp_path / "ohlcv" / "AAPL.parquet")

    def fake_download(*, tickers, start, end, **kwargs):
        return _multiindex_ohlcv(list(tickers), seed_dates)

    monkeypatch.setattr(mod.yf, "download", fake_download)

    data, stats = mod.load_ohlcv_with_stats(
        ["AAPL", "MSFT"],
        start=date(2026, 4, 20),
        end=date(2026, 4, 23),
        cache_dir=tmp_path,
    )
    assert set(data.keys()) == {"AAPL", "MSFT"}
    assert stats.hits == ("AAPL",)
    assert stats.misses == ("MSFT",)
    assert stats.hit_count == 1
    assert stats.miss_count == 1


def test_load_earnings_with_stats_reports_per_ticker_hit_miss(tmp_path, monkeypatch):
    """Fix for adversarial-review issue 2 (earnings half): the earnings
    fetcher reports fresh hits and stale-or-missing misses by ticker."""
    from research.harness.earnings_proximity import fetchers as mod

    (tmp_path / "earnings").mkdir()
    # AAPL cache fresh.
    (tmp_path / "earnings" / "AAPL.json").write_text(
        json.dumps(
            {
                "ticker": "AAPL",
                "fetched_ts": datetime.now(UTC).isoformat(),
                "earnings_dates": ["2026-04-30"],
            }
        )
    )

    class FakeTicker:
        def __init__(self, _t):
            pass

        def get_earnings_dates(self, **_kw):
            return pd.DataFrame()

    monkeypatch.setattr(mod.yf, "Ticker", FakeTicker)

    data, stats = mod.load_earnings_with_stats(
        ["AAPL", "NEWCO"], cache_dir=tmp_path, cache_max_age_hours=24
    )
    assert "AAPL" in data and "NEWCO" in data
    assert stats.hits == ("AAPL",)
    assert stats.misses == ("NEWCO",)


def test_covers_returns_true_when_fetch_end_is_future_and_cache_covers_today(monkeypatch):
    """Session 2c Open Issue #3: when the requested fetch_end is beyond
    yfinance's available data (i.e., > today), `_covers()` previously
    returned False even when the cache covered every available bar,
    triggering an unnecessary 7+ minute refetch on every run.

    The fix clamps the effective comparison endpoint to today (the most
    recent date for which yfinance can return a bar), so a cache that
    covers up through the most recent completed session is treated as
    fully covering any fetch_end ≤ today + future_buffer.
    """
    from research.harness.earnings_proximity import fetchers as mod

    fixed_today = date(2026, 4, 24)
    monkeypatch.setattr(mod, "_today", lambda: fixed_today)

    # Cache extends through the most recent completed session (yesterday).
    cache_dates = [date(2024, 4, 19)] + [date(2026, 4, 22), date(2026, 4, 23)]
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in cache_dates])
    cached = pd.DataFrame(
        {
            "Open": [100.0, 100.0, 100.0],
            "High": [101.0, 101.0, 101.0],
            "Low": [99.0, 99.0, 99.0],
            "Close": [100.5, 100.5, 100.5],
            "Volume": [1_000_000, 1_000_000, 1_000_000],
        },
        index=idx,
    )

    # fetch_end ≈ 30 sessions past window_end — well beyond today.
    fetch_end_future = date(2026, 6, 5)
    assert mod._covers(cached, date(2024, 4, 19), fetch_end_future), (
        "_covers must accept a future fetch_end when cache covers up "
        "through today (clamping the effective end to today)."
    )


def test_covers_unchanged_for_fetch_end_at_or_before_today(monkeypatch):
    """No regression for fetch_end ≤ today — the original semantics
    (idx_max ≥ end - 1 day) are preserved."""
    from research.harness.earnings_proximity import fetchers as mod

    fixed_today = date(2026, 4, 24)
    monkeypatch.setattr(mod, "_today", lambda: fixed_today)

    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in (date(2024, 4, 19), date(2024, 4, 22))])
    cached = pd.DataFrame(
        {
            "Open": [100.0, 100.0],
            "High": [101.0, 101.0],
            "Low": [99.0, 99.0],
            "Close": [100.5, 100.5],
            "Volume": [1_000_000, 1_000_000],
        },
        index=idx,
    )
    # fetch_end = 2024-04-23 (exclusive) → needs idx_max ≥ 2024-04-22. Cache has it.
    assert mod._covers(cached, date(2024, 4, 19), date(2024, 4, 23))
    # fetch_end = 2024-04-25 (exclusive) → needs idx_max ≥ 2024-04-24. Cache fails.
    assert not mod._covers(cached, date(2024, 4, 19), date(2024, 4, 25))


def test_covers_false_for_empty_cache_with_future_fetch_end(monkeypatch):
    """An empty cache with a future fetch_end must still report no coverage —
    the future-clamp must not turn an empty cache into a hit."""
    from research.harness.earnings_proximity import fetchers as mod

    fixed_today = date(2026, 4, 24)
    monkeypatch.setattr(mod, "_today", lambda: fixed_today)

    empty = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    assert not mod._covers(empty, date(2024, 4, 19), date(2026, 6, 5))


def test_covers_false_for_partial_cache_with_future_fetch_end(monkeypatch):
    """Cache that does NOT extend up through today must report False even
    when fetch_end is in the future. The clamp does not weaken the
    coverage check below today."""
    from research.harness.earnings_proximity import fetchers as mod

    fixed_today = date(2026, 4, 24)
    monkeypatch.setattr(mod, "_today", lambda: fixed_today)

    # Cache stops three weeks ago — well before today.
    idx = pd.DatetimeIndex([pd.Timestamp("2024-04-19"), pd.Timestamp("2026-04-03")])
    cached = pd.DataFrame(
        {
            "Open": [100.0, 100.0],
            "High": [101.0, 101.0],
            "Low": [99.0, 99.0],
            "Close": [100.5, 100.5],
            "Volume": [1_000_000, 1_000_000],
        },
        index=idx,
    )
    assert not mod._covers(cached, date(2024, 4, 19), date(2026, 6, 5))


def test_load_ohlcv_with_stats_skips_refetch_when_cache_covers_through_today(
    tmp_path, monkeypatch
):
    """End-to-end guard for the C4 fix: a load_ohlcv_with_stats call with
    a future fetch_end must NOT call yfinance when the cache covers up
    through today. Pre-fix this was the wasted-7-minutes-per-run case."""
    from research.harness.earnings_proximity import fetchers as mod

    fixed_today = date(2026, 4, 24)
    monkeypatch.setattr(mod, "_today", lambda: fixed_today)

    # Pre-seed AAPL cache covering through today's recent completed session.
    seed_dates = [date(2024, 4, 19), date(2026, 4, 22), date(2026, 4, 23)]
    (tmp_path / "ohlcv").mkdir()
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in seed_dates])
    seed = pd.DataFrame(
        {
            "Open": [100.0, 100.0, 100.0],
            "High": [101.0, 101.0, 101.0],
            "Low": [99.0, 99.0, 99.0],
            "Close": [100.5, 100.5, 100.5],
            "Volume": [1_000_000, 1_000_000, 1_000_000],
        },
        index=idx,
    )
    seed.to_parquet(tmp_path / "ohlcv" / "AAPL.parquet")

    def fake_download(**kwargs):  # pragma: no cover — must not be called
        raise AssertionError(
            f"yf.download must not be called for cache-covered request; kwargs={kwargs}"
        )

    monkeypatch.setattr(mod.yf, "download", fake_download)

    data, stats = mod.load_ohlcv_with_stats(
        ["AAPL"],
        start=date(2024, 4, 19),
        end=date(2026, 6, 5),  # Future-dated fetch_end.
        cache_dir=tmp_path,
    )
    assert "AAPL" in data
    assert stats.hits == ("AAPL",)
    assert stats.misses == ()


def test_covers_handles_weekend_today_with_friday_cache(monkeypatch):
    """Adversarial-review Major #2: on a weekend (Sat/Sun) or on Monday
    pre-market, the cache's most recent bar is Friday. The literal
    ``end - 1 day`` clamp would compare against Sunday (not a session)
    and report False, triggering an unnecessary refetch. The session-aware
    clamp must walk back to Friday."""
    from research.harness.earnings_proximity import fetchers as mod

    # Monday 2026-04-27. Cache last bar = Friday 2026-04-24.
    monday = date(2026, 4, 27)
    monkeypatch.setattr(mod, "_today", lambda: monday)

    friday_close = date(2026, 4, 24)
    idx = pd.DatetimeIndex(
        [pd.Timestamp("2024-04-19"), pd.Timestamp(friday_close)]
    )
    cached = pd.DataFrame(
        {
            "Open": [100.0, 100.0],
            "High": [101.0, 101.0],
            "Low": [99.0, 99.0],
            "Close": [100.5, 100.5],
            "Volume": [1_000_000, 1_000_000],
        },
        index=idx,
    )
    assert mod._covers(cached, date(2024, 4, 19), date(2026, 6, 5)), (
        "_covers must clamp 'today - 1 day = Sunday' to most recent NYSE "
        "session (Friday) so a Friday-close cache passes on Monday "
        "pre-market without a wasted refetch."
    )


def test_covers_handles_post_holiday_today_with_pre_holiday_cache(monkeypatch):
    """Same class as the weekend case: July 4 2025 was an NYSE holiday
    (Friday). On Monday 2025-07-07, ``today - 1 day`` is Sunday 2025-07-06
    (non-session). The most recent session at-or-before 2025-07-06 is
    Thursday 2025-07-03 (NYSE was closed Friday for Independence Day)."""
    from research.harness.earnings_proximity import fetchers as mod

    monday_after_holiday = date(2025, 7, 7)
    monkeypatch.setattr(mod, "_today", lambda: monday_after_holiday)

    pre_holiday_thursday = date(2025, 7, 3)
    idx = pd.DatetimeIndex(
        [pd.Timestamp("2024-07-03"), pd.Timestamp(pre_holiday_thursday)]
    )
    cached = pd.DataFrame(
        {
            "Open": [100.0, 100.0],
            "High": [101.0, 101.0],
            "Low": [99.0, 99.0],
            "Close": [100.5, 100.5],
            "Volume": [1_000_000, 1_000_000],
        },
        index=idx,
    )
    assert mod._covers(cached, date(2024, 7, 3), date(2025, 9, 1))


def test_load_ohlcv_remediates_poisoned_pre_existing_cache(tmp_path, monkeypatch):
    """Adversarial-review Major #1: parquets written by Session 2c (or any
    pre-C3 run) contain pre-IPO NaN-padded rows. A warm-cache run on the
    post-fix harness reads those parquets directly; the dropna must
    remediate them at consumer-return time so the caller never sees NaN
    OHLC. The on-disk parquet is intentionally left aligned with
    yfinance's raw output (NaN rows preserved) so :func:`_covers` keeps
    reporting True on subsequent runs and the cache does not enter an
    infinite refetch loop on mid-window-IPO tickers — see
    :func:`_drop_ohlc_nan_rows`.
    """
    from research.harness.earnings_proximity import fetchers as mod

    # Pre-seed a poisoned cache: 3 NaN rows + 3 valid rows.
    valid_dates = [date(2026, 4, 20), date(2026, 4, 21), date(2026, 4, 22)]
    pre_ipo_dates = [date(2026, 4, 17), date(2026, 4, 18), date(2026, 4, 19)]
    all_dates = pre_ipo_dates + valid_dates
    nan = float("nan")
    cache_path = tmp_path / "ohlcv" / "POISONED.parquet"
    cache_path.parent.mkdir()
    poisoned = pd.DataFrame(
        {
            "Open": [nan, nan, nan, 100.0, 101.0, 102.0],
            "High": [nan, nan, nan, 100.5, 101.5, 102.5],
            "Low": [nan, nan, nan, 99.5, 100.5, 101.5],
            "Close": [nan, nan, nan, 100.1, 101.1, 102.1],
            "Volume": [nan, nan, nan, 1_000_000, 1_000_000, 1_000_000],
        },
        index=pd.DatetimeIndex([pd.Timestamp(d) for d in all_dates]),
    )
    poisoned.to_parquet(cache_path)

    # Pin _today to 2026-04-23 so _covers's session clamp resolves to
    # Wed 2026-04-22 (cache's last bar).
    monkeypatch.setattr(mod, "_today", lambda: date(2026, 4, 23))

    def fake_download(**kwargs):  # pragma: no cover — must not be called
        raise AssertionError(
            f"yf.download must not run on cache that covers the window; kwargs={kwargs}"
        )

    monkeypatch.setattr(mod.yf, "download", fake_download)

    out = mod.load_ohlcv(
        ["POISONED"],
        start=date(2026, 4, 17),
        end=date(2026, 4, 23),
        cache_dir=tmp_path,
    )

    df = out["POISONED"]
    assert len(df) == len(valid_dates), (
        "Poisoned cache must be remediated at consumer-return time; got "
        f"{len(df)} rows, expected {len(valid_dates)}."
    )
    for col in ("Open", "High", "Low", "Close"):
        assert not df[col].isna().any()

    # On-disk parquet is intentionally NOT rewritten — keeping it aligned
    # with yfinance's raw output is what lets _covers stay True next run
    # for mid-window-IPO tickers (the dropna is applied at every read).
    re_read = pd.read_parquet(cache_path)
    assert len(re_read) == len(all_dates), (
        "Cache file must remain aligned with raw yfinance output "
        "(idx_min == window start) to avoid infinite refetch loops on "
        "mid-window-IPO tickers."
    )


def test_load_ohlcv_drops_pre_ipo_nan_rows(tmp_path, monkeypatch):
    """yf.download(group_by='ticker') pads pre-IPO dates with NaN rows back
    to the requested window start. Session 2c hit this on 8 SPX/NDX tickers
    and crashed swing.evaluation.criteria.risk_feasibility downstream
    (int(budget // NaN) raises). The fetcher must strip rows where any of
    Open/High/Low/Close is NaN BEFORE caching, so all callers inherit the
    fix without needing a per-driver dropna preprocess.
    """
    from research.harness.earnings_proximity import fetchers as mod

    valid_dates = [date(2026, 4, 20), date(2026, 4, 21), date(2026, 4, 22)]
    pre_ipo_dates = [date(2026, 4, 17), date(2026, 4, 18), date(2026, 4, 19)]

    def fake_download(*, tickers, start, end, **kwargs):
        # NaN-padded pre-IPO rows + valid trailing rows. Mirrors yfinance's
        # group_by='ticker' batch behavior for tickers that didn't exist at
        # the requested start.
        all_dates = pre_ipo_dates + valid_dates
        idx = pd.DatetimeIndex([pd.Timestamp(d) for d in all_dates])
        ticker = list(tickers)[0]
        cols = pd.MultiIndex.from_tuples(
            [
                (ticker, "Open"),
                (ticker, "High"),
                (ticker, "Low"),
                (ticker, "Close"),
                (ticker, "Volume"),
            ],
            names=["Ticker", "Price"],
        )
        nan = float("nan")
        rows = []
        for _ in pre_ipo_dates:
            rows.append([nan, nan, nan, nan, nan])
        for j in range(len(valid_dates)):
            rows.append([100.0 + j, 100.5 + j, 99.5 + j, 100.1 + j, 1_000_000])
        return pd.DataFrame(rows, index=idx, columns=cols)

    monkeypatch.setattr(mod.yf, "download", fake_download)

    out = mod.load_ohlcv(
        ["NEWIPO"],
        start=date(2026, 4, 17),
        end=date(2026, 4, 23),
        cache_dir=tmp_path,
    )

    df = out["NEWIPO"]
    assert len(df) == len(valid_dates), (
        f"pre-IPO NaN rows must be dropped at consumer return time; got "
        f"{len(df)} rows, expected {len(valid_dates)} (valid trailing rows only)."
    )
    # No NaNs in OHLC columns of the returned frame.
    for col in ("Open", "High", "Low", "Close"):
        assert not df[col].isna().any(), f"{col} should have no NaN after dropna"
    # The on-disk cache is intentionally LEFT aligned with yfinance's raw
    # output (NaN rows kept) so _covers reports True on subsequent runs
    # rather than re-fetching the same NaN-padded data forever.
    cached = pd.read_parquet(tmp_path / "ohlcv" / "NEWIPO.parquet")
    assert len(cached) == len(pre_ipo_dates) + len(valid_dates), (
        "Cache file must keep the raw NaN-padded rows; consumer-return "
        "dropna handles user-visible cleanliness."
    )


def test_load_ohlcv_keeps_volume_nan_rows_with_valid_ohlc(tmp_path, monkeypatch):
    """Holiday/halt sessions can have Volume=NaN but valid OHLC (e.g., zero
    trading on a partial-session day). Those rows are real bars and must be
    kept — the dropna must subset on OHLC only, not on Volume.
    """
    from research.harness.earnings_proximity import fetchers as mod

    dates = [date(2026, 4, 20), date(2026, 4, 21), date(2026, 4, 22)]

    def fake_download(*, tickers, start, end, **kwargs):
        idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
        ticker = list(tickers)[0]
        cols = pd.MultiIndex.from_tuples(
            [
                (ticker, "Open"),
                (ticker, "High"),
                (ticker, "Low"),
                (ticker, "Close"),
                (ticker, "Volume"),
            ],
            names=["Ticker", "Price"],
        )
        rows = [
            [100.0, 100.5, 99.5, 100.1, 1_000_000],
            [101.0, 101.5, 100.5, 101.1, float("nan")],  # Volume NaN, OHLC valid.
            [102.0, 102.5, 101.5, 102.1, 1_500_000],
        ]
        return pd.DataFrame(rows, index=idx, columns=cols)

    monkeypatch.setattr(mod.yf, "download", fake_download)

    out = mod.load_ohlcv(
        ["AAPL"],
        start=date(2026, 4, 20),
        end=date(2026, 4, 23),
        cache_dir=tmp_path,
    )
    df = out["AAPL"]
    assert len(df) == 3, "Volume-NaN rows with valid OHLC must NOT be dropped."


def test_load_ohlcv_handles_all_nan_frame_gracefully(tmp_path, monkeypatch):
    """Ticker with no valid data in the window (entirely NaN-padded — e.g.,
    every requested date is pre-IPO) must not crash; result is an empty
    frame and stats reflect a miss without a stale partial cache write.
    """
    from research.harness.earnings_proximity import fetchers as mod

    dates = [date(2026, 4, 20), date(2026, 4, 21), date(2026, 4, 22)]

    def fake_download(*, tickers, start, end, **kwargs):
        idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
        ticker = list(tickers)[0]
        cols = pd.MultiIndex.from_tuples(
            [
                (ticker, "Open"),
                (ticker, "High"),
                (ticker, "Low"),
                (ticker, "Close"),
                (ticker, "Volume"),
            ],
            names=["Ticker", "Price"],
        )
        nan = float("nan")
        rows = [[nan, nan, nan, nan, nan] for _ in dates]
        return pd.DataFrame(rows, index=idx, columns=cols)

    monkeypatch.setattr(mod.yf, "download", fake_download)

    data, stats = mod.load_ohlcv_with_stats(
        ["EMPTY"],
        start=date(2026, 4, 20),
        end=date(2026, 4, 23),
        cache_dir=tmp_path,
    )
    assert "EMPTY" in data
    assert data["EMPTY"].empty, "All-NaN OHLCV must collapse to empty after dropna."
    assert stats.misses == ("EMPTY",)


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
