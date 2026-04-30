"""Tests for swing.data.ohlcv_archive.read_or_fetch_archive.

Covers cache-empty / cache-fresh / cache-stale-incremental / weekly-refresh
branches; atomic-replace correctness under simulated crash; empty-result
ticker handling; MultiIndex column squeeze; threads=False yfinance kwarg.

Time-stability: every test monkeypatches `_last_completed_session_today` to
a fixed date (FIXED_TODAY = 2026-04-29). The helper's weekly-refresh check
compares (today - last_full_refresh_date).days >= 7; without the
monkeypatch, tests pinning last_full_refresh_date relative to end_date
would silently flip into the weekly-refresh branch in future test runs as
real wallclock advances. The fixture below applies the monkeypatch
automatically to every test in this module.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import pandas as pd
import pytest

FIXED_TODAY = date(2026, 4, 29)


@pytest.fixture(autouse=True)
def _pin_today(monkeypatch):
    """Pin `_last_completed_session_today` to FIXED_TODAY for every test in
    this module. Tests that need a different `today` can re-monkeypatch
    inside the test body — autouse fixtures apply BEFORE per-test setup
    runs, and the per-test monkeypatch.setattr overrides cleanly.
    """
    from swing.data import ohlcv_archive as mod
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED_TODAY)


def _mk_yf_frame(
    dates: list[date],
    close: float = 100.0,
    multiindex: bool = False,
) -> pd.DataFrame:
    """Build a synthetic yfinance-shape DataFrame keyed by date."""
    df = pd.DataFrame(
        {
            "Open": [close] * len(dates),
            "High": [close] * len(dates),
            "Low": [close] * len(dates),
            "Close": [close] * len(dates),
            "Volume": [1000] * len(dates),
        },
        index=pd.to_datetime(dates),
    )
    if multiindex:
        df.columns = pd.MultiIndex.from_product([df.columns, ["AAPL"]])
    return df


def test_new_ticker_triggers_full_history_fetch(tmp_path, monkeypatch):
    """Archive doesn't exist → full-history yfinance call → archive written +
    meta written → returns DataFrame with the fetched rows."""
    from swing.data import ohlcv_archive as mod

    recorded_kwargs: dict = {}

    def fake_download(ticker, **kwargs):
        recorded_kwargs.update(kwargs)
        return _mk_yf_frame([date(2026, 4, 25), date(2026, 4, 28)])

    monkeypatch.setattr(mod.yf, "download", fake_download)
    end_date = date(2026, 4, 28)

    result = mod.read_or_fetch_archive(
        "AAPL", end_date=end_date, cache_dir=tmp_path, archive_history_days=1260,
    )

    assert result is not None
    assert len(result) == 2
    assert (tmp_path / "AAPL.parquet").exists()
    assert (tmp_path / "AAPL.meta.json").exists()
    meta = json.loads((tmp_path / "AAPL.meta.json").read_text())
    assert meta["last_full_refresh_date"] == FIXED_TODAY.isoformat()
    assert recorded_kwargs.get("threads") is False, (
        "helper did not pass threads=False to yf.download; "
        f"got {recorded_kwargs}"
    )
    from swing.data.ohlcv_archive import _calendar_window_for_trading_days
    expected_full_start = FIXED_TODAY - timedelta(
        days=_calendar_window_for_trading_days(1260)
    )
    assert recorded_kwargs.get("start") == expected_full_start, (
        f"full-history start kwarg should be {expected_full_start} "
        f"(FIXED_TODAY - calendar window for 1260 trading days); "
        f"got {recorded_kwargs.get('start')} — calendar/trading-day "
        f"semantic regression"
    )


def test_cache_fresh_skips_yfinance(tmp_path, monkeypatch):
    """Archive has bars through end_date AND last_full_refresh < 7 days ago →
    NO yfinance call → returns the archive DataFrame ≤ end_date."""
    from swing.data import ohlcv_archive as mod

    end_date = date(2026, 4, 28)
    archive = _mk_yf_frame([
        FIXED_TODAY - timedelta(days=2),
        FIXED_TODAY - timedelta(days=1),
        FIXED_TODAY,
    ])
    archive.to_parquet(tmp_path / "AAPL.parquet")
    (tmp_path / "AAPL.meta.json").write_text(
        json.dumps({"last_full_refresh_date": (end_date - timedelta(days=3)).isoformat()})
    )

    def boom(*args, **kwargs):
        raise AssertionError("yf.download must NOT be called when archive is fresh")

    monkeypatch.setattr(mod.yf, "download", boom)

    result = mod.read_or_fetch_archive(
        "AAPL", end_date=end_date, cache_dir=tmp_path, archive_history_days=1260,
    )
    assert result is not None
    # Archive has [4-27, 4-28, 4-29]; end_date=4-28 slice → [4-27, 4-28] = 2 bars.
    assert len(result) == 2


def test_cache_stale_incremental_fetches_only_the_gap(tmp_path, monkeypatch):
    """Archive's latest_stored_bar = end_date - 3; last_full_refresh < 7 days
    ago → incremental fetch with start = latest+1, end = end_date+1 → archive
    appended → returns combined DataFrame.

    Discriminating: assertion checks yfinance.download's `start` kwarg is
    equal to (latest_stored + 1 day), NOT (end_date - archive_history_days). A bug
    that fetched full history on every call would also produce a 'has bars'
    result; only the kwarg assertion catches the gap-fetch contract.
    """
    from swing.data import ohlcv_archive as mod

    end_date = date(2026, 4, 28)
    latest_stored = end_date - timedelta(days=3)
    archive_dates = [
        latest_stored - timedelta(days=2),
        latest_stored - timedelta(days=1),
        latest_stored,
    ]
    archive = _mk_yf_frame(archive_dates)
    archive.to_parquet(tmp_path / "AAPL.parquet")
    (tmp_path / "AAPL.meta.json").write_text(
        json.dumps({"last_full_refresh_date": (end_date - timedelta(days=3)).isoformat()})
    )

    recorded_kwargs: dict = {}

    def fake_download(ticker, **kwargs):
        recorded_kwargs.update(kwargs)
        gap_dates = [end_date - timedelta(days=2), end_date - timedelta(days=1), end_date]
        return _mk_yf_frame(gap_dates)

    monkeypatch.setattr(mod.yf, "download", fake_download)

    result = mod.read_or_fetch_archive(
        "AAPL", end_date=end_date, cache_dir=tmp_path, archive_history_days=1260,
    )
    assert result is not None

    expected_start = latest_stored + timedelta(days=1)
    assert recorded_kwargs.get("start") == expected_start, (
        f"expected incremental gap fetch start={expected_start}, "
        f"got start={recorded_kwargs.get('start')}"
    )
    saved = pd.read_parquet(tmp_path / "AAPL.parquet")
    assert len(saved) == 6


def test_weekly_full_refresh_triggers_when_meta_is_8_days_old(tmp_path, monkeypatch):
    """`last_full_refresh_date == today - 8 days` → full-history fetch (NOT
    incremental); archive overwritten; meta updated to today.

    Discriminating: assertion checks yfinance.download's `start` kwarg is
    `end_date - _calendar_window_for_trading_days(archive_history_days)` days
    (full-window via market-calendar-ratio conversion), NOT `latest_stored + 1 day`
    (incremental) AND NOT raw `timedelta(days=archive_history_days)` (calendar
    misinterpretation, Codex R1 Critical 1 + R2 Critical 1 failure mode).
    Distinguishes weekly-refresh path from incremental path AND from the
    superseded raw-calendar-days heuristic.
    """
    from swing.data import ohlcv_archive as mod

    end_date = date(2026, 4, 28)
    archive = _mk_yf_frame([end_date - timedelta(days=1), end_date])
    archive.to_parquet(tmp_path / "AAPL.parquet")
    stale_meta_date = end_date - timedelta(days=8)
    (tmp_path / "AAPL.meta.json").write_text(
        json.dumps({"last_full_refresh_date": stale_meta_date.isoformat()})
    )

    recorded_kwargs: dict = {}

    def fake_download(ticker, **kwargs):
        recorded_kwargs.update(kwargs)
        return _mk_yf_frame([end_date - timedelta(days=2), end_date - timedelta(days=1), end_date])

    monkeypatch.setattr(mod.yf, "download", fake_download)

    mod.read_or_fetch_archive(
        "AAPL", end_date=end_date, cache_dir=tmp_path, archive_history_days=1260,
    )

    from swing.data.ohlcv_archive import _calendar_window_for_trading_days
    expected_start = FIXED_TODAY - timedelta(days=_calendar_window_for_trading_days(1260))
    assert recorded_kwargs.get("start") == expected_start, (
        f"expected weekly-refresh full-window start={expected_start}, "
        f"got start={recorded_kwargs.get('start')} — incremental path or "
        f"raw-calendar-days fallback fired instead"
    )
    meta = json.loads((tmp_path / "AAPL.meta.json").read_text())
    assert meta["last_full_refresh_date"] == FIXED_TODAY.isoformat()


def test_atomic_replace_preserves_prior_archive_under_simulated_crash(tmp_path, monkeypatch):
    """Pre-existing archive; mid-write os.replace raises → prior archive
    unchanged; no leftover *.parquet.tmp files."""
    from swing.data import ohlcv_archive as mod

    end_date = date(2026, 4, 28)
    pre_existing = _mk_yf_frame([date(2026, 1, 1)], close=99.0)
    pre_existing.to_parquet(tmp_path / "AAPL.parquet")
    (tmp_path / "AAPL.meta.json").write_text(
        json.dumps({"last_full_refresh_date": (end_date - timedelta(days=8)).isoformat()})
    )

    def fake_download(ticker, **kwargs):
        return _mk_yf_frame([end_date], close=200.0)

    monkeypatch.setattr(mod.yf, "download", fake_download)

    real_replace = mod.os.replace

    def crashing_replace(src, dst):
        if str(dst).endswith("AAPL.parquet"):
            raise OSError("simulated crash mid-rename")
        return real_replace(src, dst)

    monkeypatch.setattr(mod.os, "replace", crashing_replace)

    with pytest.raises(OSError, match="simulated crash"):
        mod.read_or_fetch_archive(
            "AAPL", end_date=end_date, cache_dir=tmp_path, archive_history_days=1260,
        )

    survived = pd.read_parquet(tmp_path / "AAPL.parquet")
    assert survived.loc[pd.Timestamp("2026-01-01"), "Close"] == 99.0
    assert list(tmp_path.glob("*.parquet.tmp")) == []


def test_empty_yfinance_result_returns_none(tmp_path, monkeypatch):
    """yfinance returns empty DataFrame (delisted / bad ticker / no history)
    → helper returns None; archive NOT written."""
    from swing.data import ohlcv_archive as mod

    def empty_download(ticker, **kwargs):
        return pd.DataFrame()

    monkeypatch.setattr(mod.yf, "download", empty_download)

    result = mod.read_or_fetch_archive(
        "DELISTED", end_date=date(2026, 4, 28), cache_dir=tmp_path, archive_history_days=1260,
    )
    assert result is None
    assert not (tmp_path / "DELISTED.parquet").exists()


def test_multiindex_columns_are_squeezed(tmp_path, monkeypatch):
    """yfinance ≥1.2 single-ticker `yf.download` returns MultiIndex columns
    (`Price × Ticker`); helper must squeeze to flat columns so `df['Close']`
    is a Series.
    """
    from swing.data import ohlcv_archive as mod

    def multiindex_download(ticker, **kwargs):
        return _mk_yf_frame([date(2026, 4, 28)], multiindex=True)

    monkeypatch.setattr(mod.yf, "download", multiindex_download)

    result = mod.read_or_fetch_archive(
        "AAPL", end_date=date(2026, 4, 28), cache_dir=tmp_path, archive_history_days=1260,
    )
    assert result is not None
    assert result["Close"].ndim == 1, (
        "MultiIndex columns not squeezed — df['Close'] is still a DataFrame"
    )


def test_end_date_in_past_returns_archive_slice_up_to_end_date(tmp_path, monkeypatch):
    """Archive extends beyond end_date (e.g., as_of_date in the past for
    research-branch parity). Helper returns rows ≤ end_date; never returns
    rows past end_date."""
    from swing.data import ohlcv_archive as mod

    archive_end = FIXED_TODAY  # 2026-04-29; archive must cover today so no gap fetch.
    archive = _mk_yf_frame([archive_end - timedelta(days=i) for i in range(10)])
    archive.to_parquet(tmp_path / "AAPL.parquet")
    (tmp_path / "AAPL.meta.json").write_text(
        json.dumps({"last_full_refresh_date": (archive_end - timedelta(days=2)).isoformat()})
    )

    def boom(*args, **kwargs):
        raise AssertionError("yf.download must NOT be called when archive covers end_date")

    monkeypatch.setattr(mod.yf, "download", boom)

    end_date = archive_end - timedelta(days=4)
    result = mod.read_or_fetch_archive(
        "AAPL", end_date=end_date, cache_dir=tmp_path, archive_history_days=1260,
    )
    assert result is not None
    assert result.index.max().date() <= end_date, (
        f"helper returned bars past end_date={end_date}; max bar={result.index.max().date()}"
    )


def test_corrupted_meta_falls_back_to_full_refresh(tmp_path, monkeypatch):
    """Meta JSON is corrupted (not parseable) → helper treats it as 'no meta'
    and triggers full-history refresh. Defensive: never crash on a bad meta."""
    from swing.data import ohlcv_archive as mod

    end_date = date(2026, 4, 28)
    archive = _mk_yf_frame([end_date - timedelta(days=1), end_date])
    archive.to_parquet(tmp_path / "AAPL.parquet")
    (tmp_path / "AAPL.meta.json").write_text("{not valid json")

    fetched = []

    def tracking_download(ticker, **kwargs):
        fetched.append(kwargs)
        return _mk_yf_frame([end_date - timedelta(days=2), end_date - timedelta(days=1), end_date])

    monkeypatch.setattr(mod.yf, "download", tracking_download)

    result = mod.read_or_fetch_archive(
        "AAPL", end_date=end_date, cache_dir=tmp_path, archive_history_days=1260,
    )
    assert result is not None
    assert len(fetched) == 1, "corrupted meta should trigger exactly one refresh"
    from swing.data.ohlcv_archive import _calendar_window_for_trading_days
    assert fetched[0].get("start") == FIXED_TODAY - timedelta(
        days=_calendar_window_for_trading_days(1260)
    )


def test_parquet_fresh_meta_missing_recovers_via_full_refresh(tmp_path, monkeypatch):
    """Codex R1 Major 1 resolution — cross-file atomicity skew is benign.

    Scenario: a previous run wrote `{TICKER}.parquet` atomically, then
    crashed BEFORE writing `{TICKER}.meta.json`. The next read sees a
    fresh-looking parquet with no meta. Helper's freshness logic must
    treat 'meta missing' as 'last_full_refresh_date unknown' →
    needs_full_refresh = True → recovery via a full-history refresh.
    Cost: one extra yfinance call. Correctness: preserved. Discriminating:
    asserts the refresh actually fires (NOT a vacuous 'returns data' check).
    """
    from swing.data import ohlcv_archive as mod

    end_date = date(2026, 4, 28)
    archive = _mk_yf_frame([end_date - timedelta(days=1), end_date])
    archive.to_parquet(tmp_path / "AAPL.parquet")
    assert not (tmp_path / "AAPL.meta.json").exists()

    refresh_calls = []

    def tracking_download(ticker, **kwargs):
        refresh_calls.append(kwargs)
        return _mk_yf_frame([end_date - timedelta(days=2),
                             end_date - timedelta(days=1), end_date])

    monkeypatch.setattr(mod.yf, "download", tracking_download)

    result = mod.read_or_fetch_archive(
        "AAPL", end_date=end_date, cache_dir=tmp_path, archive_history_days=1260,
    )

    assert result is not None
    assert len(refresh_calls) == 1, (
        "fresh-parquet/missing-meta skew should trigger exactly one refresh; "
        f"got {len(refresh_calls)} yfinance calls"
    )
    from swing.data.ohlcv_archive import _calendar_window_for_trading_days
    assert refresh_calls[0].get("start") == FIXED_TODAY - timedelta(
        days=_calendar_window_for_trading_days(1260)
    ), "full-history start kwarg missing — incremental path fired instead"
    assert (tmp_path / "AAPL.meta.json").exists()


def test_historical_end_date_does_not_truncate_archive_on_full_refresh(tmp_path, monkeypatch):
    """Codex R1 Major 1 resolution — full-refresh path must always fetch up to
    today (last_completed_session), NEVER up to caller's historical end_date.
    Otherwise a backdated PriceFetcher.get(as_of_date=...) call could overwrite
    the archive with truncated history.

    Discriminating: passes a historical end_date AND empty archive (forcing
    full refresh) and asserts the recorded yfinance start/end are anchored at
    FIXED_TODAY, not the historical end_date.
    """
    from swing.data import ohlcv_archive as mod
    from swing.data.ohlcv_archive import _calendar_window_for_trading_days

    historical_end = date(2025, 6, 1)
    recorded_kwargs: dict = {}

    def fake_download(ticker, **kwargs):
        recorded_kwargs.update(kwargs)
        return _mk_yf_frame([
            FIXED_TODAY - timedelta(days=2),
            FIXED_TODAY - timedelta(days=1),
            FIXED_TODAY,
        ])

    monkeypatch.setattr(mod.yf, "download", fake_download)

    result = mod.read_or_fetch_archive(
        "AAPL", end_date=historical_end, cache_dir=tmp_path,
        archive_history_days=1260,
    )

    # Discriminating: fetch end is today, NOT the historical end_date.
    # _yf_download_window adds +1 day to make end exclusive, so the recorded
    # `end` kwarg is FIXED_TODAY + 1 day.
    assert recorded_kwargs.get("end") == FIXED_TODAY + timedelta(days=1), (
        f"helper fetched up to caller's historical end_date instead of today; "
        f"got end={recorded_kwargs.get('end')}, expected {FIXED_TODAY + timedelta(days=1)}"
    )
    assert recorded_kwargs.get("start") == FIXED_TODAY - timedelta(
        days=_calendar_window_for_trading_days(1260)
    )
    # Return value sliced to historical end_date — but archive on disk has
    # today's bars too.
    assert result is not None
    saved = pd.read_parquet(tmp_path / "AAPL.parquet")
    assert FIXED_TODAY in [d.date() for d in saved.index]


def test_incremental_path_enforces_retention_cap(tmp_path, monkeypatch):
    """Codex R1 Major 2 resolution — incremental path must enforce
    archive_history_days. Otherwise active tickers grow unbounded over
    years of operation.

    Discriminating: seed archive with EXACTLY archive_history_days bars
    extending up to (today - 1). Trigger incremental gap (1 day) and assert
    the on-disk archive is still EXACTLY archive_history_days bars (oldest
    bar dropped, today's bar appended).
    """
    from swing.data import ohlcv_archive as mod

    cap = 100  # small cap to test trim
    # Seed archive with `cap` bars ending at FIXED_TODAY - 1 day
    archive_dates = [FIXED_TODAY - timedelta(days=i) for i in range(1, cap + 1)]
    archive_dates.reverse()  # oldest first
    archive = _mk_yf_frame(archive_dates)
    archive.to_parquet(tmp_path / "AAPL.parquet")
    (tmp_path / "AAPL.meta.json").write_text(
        json.dumps({"last_full_refresh_date": (FIXED_TODAY - timedelta(days=1)).isoformat()})
    )

    def fake_download(ticker, **kwargs):
        # Gap fetch returns just FIXED_TODAY's bar.
        return _mk_yf_frame([FIXED_TODAY])

    monkeypatch.setattr(mod.yf, "download", fake_download)

    mod.read_or_fetch_archive(
        "AAPL", end_date=FIXED_TODAY, cache_dir=tmp_path, archive_history_days=cap,
    )

    saved = pd.read_parquet(tmp_path / "AAPL.parquet")
    assert len(saved) == cap, (
        f"incremental path did not enforce retention cap; "
        f"saved has {len(saved)} bars, expected {cap}"
    )
    # Newest bar is FIXED_TODAY (gap appended).
    assert saved.index.max().date() == FIXED_TODAY
    # Oldest bar dropped (was FIXED_TODAY - cap days; now FIXED_TODAY - cap + 1 days).
    assert saved.index.min().date() == FIXED_TODAY - timedelta(days=cap - 1), (
        f"oldest bar should have been trimmed; got {saved.index.min().date()}"
    )
