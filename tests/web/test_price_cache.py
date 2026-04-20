"""PriceCache — TTL, market-hours, timeout fallback, circuit breaker."""
from __future__ import annotations

import time
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from swing.data.db import connect, ensure_schema


def _seed_candidate(cfg, ticker: str, close: float) -> None:
    """Seed one evaluation_runs + one candidate so last-close fallback has data."""
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 0, 0, 1, 0, 0, ?, ?)""",
                ("2026-04-17T21:49:00", "2026-04-17", "2026-04-20",
                 "test-v1", "deadbeef"),
            )
            run_id = cur.lastrowid
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, rs_method)
                   VALUES (?, ?, 'skip', ?, 'universe')""",
                (run_id, ticker, close),
            )
    finally:
        conn.close()


def test_cache_hit_within_ttl(seeded_db, monkeypatch):
    from swing.web.price_cache import PriceCache
    cfg, _ = seeded_db
    _seed_candidate(cfg, "AAPL", 180.0)

    cache = PriceCache(cfg)

    # Force market hours True and a deterministic live fetch.
    monkeypatch.setattr(cache, "market_hours_now", lambda: True)
    call_count = [0]

    def fake_fetch(ticker: str) -> float:
        call_count[0] += 1
        return 181.50

    monkeypatch.setattr(cache, "_fetch_live_price", fake_fetch)

    s1 = cache.get("AAPL")
    s2 = cache.get("AAPL")
    assert s1.price == 181.50
    assert not s1.is_stale
    assert call_count[0] == 1  # second call was cache hit


def test_market_closed_returns_last_close(seeded_db, monkeypatch):
    from swing.web.price_cache import PriceCache
    cfg, _ = seeded_db
    _seed_candidate(cfg, "AAPL", 178.25)

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "market_hours_now", lambda: False)

    s = cache.get("AAPL")
    assert s.price == 178.25
    assert s.is_stale
    assert s.source == "last_close_market_closed"


def test_fetch_timeout_falls_back(seeded_db, monkeypatch):
    from swing.web.price_cache import PriceCache
    cfg, _ = seeded_db
    _seed_candidate(cfg, "AAPL", 175.50)

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "market_hours_now", lambda: True)

    def boom(ticker):
        raise TimeoutError("yfinance hung")

    monkeypatch.setattr(cache, "_fetch_live_price", boom)

    s = cache.get("AAPL")
    assert s.price == 175.50
    assert s.is_stale
    assert s.source == "last_close"


def test_unknown_ticker_returns_none_price_fallback(seeded_db, monkeypatch):
    from swing.web.price_cache import PriceCache
    cfg, _ = seeded_db
    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "market_hours_now", lambda: False)
    s = cache.get("NOPE")
    assert s is None


def test_get_many_parallel_dispatch(seeded_db, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    for t, px in (("AAPL", 180.0), ("MSFT", 420.0), ("NVDA", 900.0)):
        _seed_candidate(cfg, t, px)

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "market_hours_now", lambda: True)

    def fake_fetch(ticker):
        time.sleep(0.05)
        return {"AAPL": 181.0, "MSFT": 421.0, "NVDA": 901.0}[ticker]

    monkeypatch.setattr(cache, "_fetch_live_price", fake_fetch)

    executor = ThreadPoolExecutor(max_workers=3)
    try:
        snaps = cache.get_many(["AAPL", "MSFT", "NVDA"], deadline_seconds=2.0, executor=executor)
    finally:
        executor.shutdown(wait=True)
    assert set(snaps.keys()) == {"AAPL", "MSFT", "NVDA"}
    assert snaps["AAPL"].price == 181.0
    assert snaps["MSFT"].price == 421.0
    assert snaps["NVDA"].price == 901.0
    assert not any(s.is_stale for s in snaps.values())


def test_get_many_deadline_falls_back(seeded_db, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    _seed_candidate(cfg, "AAPL", 180.0)
    _seed_candidate(cfg, "MSFT", 420.0)

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "market_hours_now", lambda: True)

    def slow(ticker):
        time.sleep(5.0)
        return 1.0

    monkeypatch.setattr(cache, "_fetch_live_price", slow)

    executor = ThreadPoolExecutor(max_workers=2)
    t0 = time.monotonic()
    try:
        snaps = cache.get_many(["AAPL", "MSFT"], deadline_seconds=0.3, executor=executor)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    elapsed = time.monotonic() - t0
    # Deadline is honored; both fall back to last_close.
    assert elapsed < 2.0
    assert snaps["AAPL"].is_stale and snaps["AAPL"].source == "last_close"
    assert snaps["MSFT"].is_stale and snaps["MSFT"].source == "last_close"


def test_circuit_breaker_trips_and_recovers(seeded_db, monkeypatch):
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    _seed_candidate(cfg, "AAPL", 180.0)
    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "market_hours_now", lambda: True)

    # Record 15 failures to drive failure fraction > 0.5 over a 20-wide window.
    for _ in range(15):
        cache._record_outcome(success=False)
    for _ in range(5):
        cache._record_outcome(success=True)

    # Force the breaker evaluation by calling _maybe_trip_breaker directly.
    cache._maybe_trip_breaker()
    assert cache.is_degraded()

    # During degraded mode, get() returns last-close without touching the network.
    def should_not_be_called(ticker):
        raise AssertionError("live fetch must be skipped in degraded mode")

    monkeypatch.setattr(cache, "_fetch_live_price", should_not_be_called)
    s = cache.get("AAPL")
    assert s.is_stale
    assert s.source == "last_close"


def test_circuit_breaker_is_instance_scoped(seeded_db):
    from swing.web.price_cache import PriceCache
    cfg, _ = seeded_db
    a = PriceCache(cfg)
    b = PriceCache(cfg)
    for _ in range(20):
        a._record_outcome(success=False)
    a._maybe_trip_breaker()
    assert a.is_degraded()
    # The second instance must not inherit degraded state.
    assert not b.is_degraded()


def test_fetch_live_price_handles_multiindex_column_frame(seeded_db, monkeypatch):
    """Regression: yfinance >= ~0.2.4x returns a MultiIndex column DataFrame
    (Price × Ticker) even for single-ticker `group_by='column'` calls. That
    makes `df["Close"]` a DataFrame (one column per ticker), not a Series,
    and `float(df["Close"].iloc[-1])` fails with `float() argument must be
    a string or a real number, not 'Series'`. The fetch must accept both
    shapes so the cache continues to serve live prices after yfinance
    updates."""
    import pandas as pd
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    cache = PriceCache(cfg)

    # Synthesize the shape current yfinance returns for a single ticker:
    # columns = MultiIndex with levels ["Price", "Ticker"], one sub-column
    # per field per ticker. df["Close"] → DataFrame with one column (ticker).
    cols = pd.MultiIndex.from_tuples(
        [("Close", "SPY"), ("Open", "SPY"), ("High", "SPY"),
         ("Low", "SPY"), ("Volume", "SPY")],
        names=["Price", "Ticker"],
    )
    data = [[181.25, 181.20, 181.30, 181.20, 1000],
            [181.28, 181.25, 181.35, 181.25, 2000]]
    df = pd.DataFrame(
        data, columns=cols,
        index=pd.date_range(end="2026-04-20 15:59", periods=2, freq="min"),
    )
    monkeypatch.setattr("yfinance.download", lambda *a, **kw: df)

    price = cache._fetch_live_price("SPY")
    assert price == 181.28


def test_market_hours_now_passes_timestamp_not_datetime(seeded_db, monkeypatch):
    """Regression: `exchange_calendars.is_open_at_time` now raises TypeError
    when given a `datetime.datetime` (expects `pd.Timestamp`). The prior
    implementation passed `datetime.now(timezone.utc)` and caught the
    resulting TypeError silently, permanently returning False. That made
    the PriceCache always fall back to last-close, even during live
    trading hours. Assert the calendar receives a pd.Timestamp."""
    import pandas as pd
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    cache = PriceCache(cfg)

    received_args: dict = {}

    class FakeCal:
        def is_open_at_time(self, ts, *, ignore_breaks=True):
            received_args["ts_type"] = type(ts).__name__
            received_args["ts"] = ts
            return True  # pretend market is open

    monkeypatch.setattr(
        "exchange_calendars.get_calendar", lambda name: FakeCal(),
    )

    result = cache.market_hours_now()
    assert result is True, (
        f"market_hours_now returned {result}; likely silently caught TypeError. "
        f"got={received_args}"
    )
    assert received_args.get("ts_type") == "Timestamp", (
        f"is_open_at_time received {received_args.get('ts_type')}, "
        f"expected pandas Timestamp"
    )


def test_fetch_live_price_skips_trailing_nan_close(seeded_db, monkeypatch):
    """Last minute bar can be NaN while yfinance streams a fresh minute
    whose close hasn't finalized — R2 Minor 1. The cache must return the
    most recent NON-NaN Close rather than raise."""
    import numpy as np
    import pandas as pd
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    cache = PriceCache(cfg)

    closes = [181.25, 181.30, 181.28, np.nan]  # last bar NaN
    df = pd.DataFrame(
        {"Close": closes, "Open": closes, "High": closes, "Low": closes, "Volume": [0] * 4},
        index=pd.date_range(end="2026-04-17 15:59", periods=4, freq="min"),
    )
    monkeypatch.setattr("yfinance.download", lambda *a, **kw: df)

    price = cache._fetch_live_price("AAPL")
    assert price == 181.28   # last NON-NaN close


def test_fetch_live_price_raises_when_all_close_nan(seeded_db, monkeypatch):
    import numpy as np
    import pandas as pd
    import pytest
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    cache = PriceCache(cfg)

    df = pd.DataFrame(
        {"Close": [np.nan, np.nan], "Open": [1.0, 1.0], "High": [1.0, 1.0],
         "Low": [1.0, 1.0], "Volume": [0, 0]},
        index=pd.date_range(end="2026-04-17 15:59", periods=2, freq="min"),
    )
    monkeypatch.setattr("yfinance.download", lambda *a, **kw: df)

    with pytest.raises(RuntimeError, match="all Close"):
        cache._fetch_live_price("AAPL")


def test_fetch_live_price_raises_on_empty_frame(seeded_db, monkeypatch):
    import pandas as pd
    import pytest
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    cache = PriceCache(cfg)
    monkeypatch.setattr("yfinance.download", lambda *a, **kw: pd.DataFrame())

    with pytest.raises(RuntimeError, match="no bars"):
        cache._fetch_live_price("AAPL")


def test_refresh_all_invalidates_and_next_get_refetches(seeded_db, monkeypatch):
    """refresh_all is invalidate-only: it pops entries from the cache so the
    next get/get_many re-fetches. It does NOT itself hit the network (that
    would duplicate work — POST /prices/refresh rebuilds the VM after calling
    refresh_all, and the VM build triggers the actual re-fetch via get_many).
    """
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    _seed_candidate(cfg, "AAPL", 180.0)
    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "market_hours_now", lambda: True)

    fetch_calls = [0]
    def counting_fetch(ticker):
        fetch_calls[0] += 1
        return 181.0

    monkeypatch.setattr(cache, "_fetch_live_price", counting_fetch)

    # Populate cache.
    s1 = cache.get("AAPL")
    assert s1.price == 181.0
    assert fetch_calls[0] == 1

    # Second get hits cache — no new fetch.
    cache.get("AAPL")
    assert fetch_calls[0] == 1

    # refresh_all invalidates.
    cache.refresh_all(["AAPL"])
    cache.get("AAPL")
    assert fetch_calls[0] == 2, "refresh_all must invalidate; next get re-fetches"
