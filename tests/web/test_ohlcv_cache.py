"""OhlcvCache — TTL cache + sliding-window breaker + deadline-as-failure.
Spec §3.2, §4.3, §4.4."""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest

from swing.config import Config


@pytest.fixture
def cfg(test_cfg):
    c, _ = test_cfg
    return c


def _bars(closes, start="2026-01-02") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(closes), freq="B")
    return pd.DataFrame({"Close": closes}, index=idx)


def test_cache_hit_returns_bundle_without_refetch(cfg, monkeypatch):
    """A hit within TTL returns the cached bundle and does NOT re-invoke fetch."""
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.pipeline import ohlcv as ohlcv_mod

    calls = {"n": 0}

    def fake_fetch(ticker, *, n_bars=60, as_of_date=None, **_):
        calls["n"] += 1
        return _bars([100.0 + i for i in range(50)])

    monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", fake_fetch)
    cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        r1 = cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
        r2 = cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
    assert r1["AAPL"].sma10 is not None
    assert r2["AAPL"].sma10 is not None
    assert calls["n"] == 1, "second call should be a cache hit"


def test_cache_miss_triggers_fetch_and_stores_bundle(cfg, monkeypatch):
    """A first-time request fetches and caches."""
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.pipeline import ohlcv as ohlcv_mod

    def fake_fetch(ticker, *, n_bars=60, as_of_date=None, **_):
        return _bars([100.0 + i for i in range(50)])

    monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", fake_fetch)
    cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        r = cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
    assert r["AAPL"].sma10 is not None
    assert r["AAPL"].sma20 is not None
    assert r["AAPL"].sma50 is not None
    assert r["AAPL"].previous_close is not None


def test_ttl_expiry_triggers_refetch(cfg, monkeypatch):
    """Past TTL → cache entry is evicted and refetched."""
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.pipeline import ohlcv as ohlcv_mod

    # Override TTL to 0.1s for test speed.
    from dataclasses import replace as _replace
    tiny_web = _replace(cfg.web, ohlcv_cache_ttl_seconds=0)
    tiny_cfg = _replace(cfg, web=tiny_web)

    calls = {"n": 0}
    def fake_fetch(ticker, *, n_bars=60, as_of_date=None, **_):
        calls["n"] += 1
        return _bars([100.0] * 50)

    monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", fake_fetch)
    cache = OhlcvCache(tiny_cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
        time.sleep(0.05)
        cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
    assert calls["n"] == 2, "TTL expired → refetch"


def test_deadline_miss_returns_empty_bundle_and_is_not_cached(cfg, monkeypatch):
    """A fetch that misses the deadline returns OhlcvBundle.empty() and does
    NOT pollute the cache. Next request re-attempts."""
    from swing.web.ohlcv_cache import OhlcvCache, OhlcvBundle
    from swing.pipeline import ohlcv as ohlcv_mod

    call_count = {"n": 0}

    def slow_fetch(ticker, *, n_bars=60, as_of_date=None, **_):
        call_count["n"] += 1
        # First call sleeps past the deadline; second call returns immediately.
        if call_count["n"] == 1:
            time.sleep(0.3)
            return _bars([100.0] * 50)
        return _bars([100.0] * 50)

    monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", slow_fetch)
    cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        r1 = cache.get_many_bundles(["AAPL"], deadline_seconds=0.05, executor=ex)
        r2 = cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
    assert r1["AAPL"].sma10 is None, "deadline miss → empty bundle"
    assert r2["AAPL"].sma10 is not None, "next request re-fetches (no cached empty)"


def test_circuit_breaker_trips_when_failure_fraction_exceeds_half(cfg, monkeypatch):
    """Mirrors PriceCache sliding-window: >50% failures in window → breaker
    trips. Deadline misses count as failures (spec §4.3)."""
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.pipeline import ohlcv as ohlcv_mod

    def always_fail(ticker, *, n_bars=60, as_of_date=None, **_):
        raise RuntimeError("network down")

    monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", always_fail)
    cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=4) as ex:
        # Force enough requests to fill the window and exceed 50%.
        for _ in range(20):
            cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
    assert cache.is_degraded() is True


def test_is_degraded_clears_after_cooldown(cfg, monkeypatch):
    """After the breaker cools down, is_degraded() returns False."""
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.pipeline import ohlcv as ohlcv_mod

    # Override breaker cooldown to 0.1s.
    from dataclasses import replace as _replace
    fast_web = _replace(cfg.web, circuit_breaker_cooldown_seconds=0)
    fast_cfg = _replace(cfg, web=fast_web)

    def always_fail(ticker, *, n_bars=60, as_of_date=None, **_):
        raise RuntimeError("boom")

    monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", always_fail)
    cache = OhlcvCache(fast_cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        for _ in range(20):
            cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
    # With cooldown=0 the breaker should already have cleared.
    time.sleep(0.01)
    assert cache.is_degraded() is False


def test_reset_circuit_breaker_clears_degraded(cfg, monkeypatch):
    """Explicit reset clears the window + the degraded flag."""
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.pipeline import ohlcv as ohlcv_mod

    def always_fail(ticker, *, n_bars=60, as_of_date=None, **_):
        raise RuntimeError("boom")

    monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", always_fail)
    cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        for _ in range(20):
            cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
    assert cache.is_degraded() is True
    cache.reset_circuit_breaker()
    assert cache.is_degraded() is False


def test_empty_bundle_from_bad_ticker_does_not_trip_breaker(cfg, monkeypatch):
    """A ticker that yfinance serves with no data (empty DataFrame)
    returns an empty bundle but MUST NOT increment the breaker — that's
    a per-ticker data issue, not a source failure."""
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.pipeline import ohlcv as ohlcv_mod

    def no_data_fetch(ticker, *, n_bars=60, as_of_date=None, **_):
        return None  # fetch returned empty result, no exception

    monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", no_data_fetch)
    cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        for _ in range(20):
            cache.get_many_bundles(["DEAD"], deadline_seconds=5.0, executor=ex)
    # Even 20 empty-result fetches should NOT trip the breaker.
    assert cache.is_degraded() is False


def test_mixed_window_empty_does_not_mask_real_failure(cfg, monkeypatch):
    """R2 Major 1 regression: if empty-result for one ticker dilutes actual
    fetch failures for another ticker, the breaker could fail to trip.
    Ternary accounting (empty = neutral) prevents this dilution."""
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.pipeline import ohlcv as ohlcv_mod

    calls = {"DEAD": 0, "GOOD": 0}

    def mixed_fetch(ticker, *, n_bars=60, as_of_date=None, **_):
        calls[ticker] = calls.get(ticker, 0) + 1
        if ticker == "DEAD":
            return None  # healthy-but-empty (no exception)
        raise RuntimeError("source down")  # unhealthy for GOOD

    monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", mixed_fetch)
    cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=4) as ex:
        # Alternate DEAD + GOOD. Without ternary accounting, DEAD's
        # "successes" would dilute GOOD's failures below 50%.
        for _ in range(10):
            cache.get_many_bundles(["DEAD", "GOOD"], deadline_seconds=5.0, executor=ex)

    # Breaker SHOULD trip because all real source signals (GOOD's failures)
    # are failures; DEAD's empty-results are neutral and don't pad the window.
    assert cache.is_degraded() is True


def test_empty_bundle_cached_as_sentinel(cfg, monkeypatch):
    """R2 Major 2 regression: a ticker that returns empty repeatedly should
    hit the cache (sentinel) on subsequent requests within TTL — not
    refetch every page render."""
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.pipeline import ohlcv as ohlcv_mod

    calls = {"n": 0}

    def no_data_fetch(ticker, *, n_bars=60, as_of_date=None, **_):
        calls["n"] += 1
        return None

    monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", no_data_fetch)
    cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        cache.get_many_bundles(["DEAD"], deadline_seconds=5.0, executor=ex)
        cache.get_many_bundles(["DEAD"], deadline_seconds=5.0, executor=ex)
        cache.get_many_bundles(["DEAD"], deadline_seconds=5.0, executor=ex)
    # First call fetches; next two hit the empty-sentinel cache.
    assert calls["n"] == 1


def test_sentinel_hits_do_not_mask_real_failure(cfg, monkeypatch):
    """R3 Major 1 regression: after an empty sentinel is cached, subsequent
    cache hits for that bad ticker must be accounted NEUTRAL, not success.
    Otherwise they'd pad the breaker window and mask real failures elsewhere."""
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.pipeline import ohlcv as ohlcv_mod

    def mixed_fetch(ticker, *, n_bars=60, as_of_date=None, **_):
        if ticker == "DEAD":
            return None  # healthy-but-empty — caches as sentinel on first call
        raise RuntimeError("source down")  # unhealthy

    monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", mixed_fetch)
    cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=4) as ex:
        # First round: DEAD fetches + caches empty sentinel; GOOD raises.
        # Subsequent rounds: DEAD hits sentinel (should be NEUTRAL); GOOD keeps raising.
        for _ in range(15):
            cache.get_many_bundles(["DEAD", "GOOD"], deadline_seconds=5.0, executor=ex)

    # DEAD's sentinel hits must not dilute GOOD's failures. Breaker should trip.
    assert cache.is_degraded() is True


def test_degraded_mode_serves_warm_cache(cfg, monkeypatch):
    """R4 Major 1 regression: when the breaker is tripped, already-cached
    bundles within TTL must still be served (not replaced with empty bundles).
    Only misses are short-circuited during cooldown."""
    from swing.web.ohlcv_cache import OhlcvCache, OhlcvBundle
    from swing.pipeline import ohlcv as ohlcv_mod

    def good_fetch(ticker, *, n_bars=60, as_of_date=None, **_):
        return _bars([100.0 + i for i in range(50)])

    monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", good_fetch)
    cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        # Prime the cache for AAPL.
        r1 = cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
        assert r1["AAPL"].sma10 is not None
        # Force the breaker tripped by directly setting degraded_until.
        with cache._lock:
            cache._degraded_until = time.monotonic() + 60.0
        assert cache.is_degraded() is True
        # Cache hit should still return the warm bundle, NOT an empty one.
        r2 = cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
    assert r2["AAPL"].sma10 is not None, "warm cache must be served during degraded mode"


def test_degraded_mode_short_circuits_only_misses(cfg, monkeypatch):
    """R4 Major 1 symmetric case: with warm cache for one ticker and a miss
    for another during degraded mode, the warm ticker is served and the
    miss returns empty — without a fetch attempt."""
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.pipeline import ohlcv as ohlcv_mod

    fetch_tickers: list[str] = []

    def tracking_fetch(ticker, *, n_bars=60, as_of_date=None, **_):
        fetch_tickers.append(ticker)
        return _bars([100.0 + i for i in range(50)])

    monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", tracking_fetch)
    cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        # Prime AAPL only.
        cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
        fetch_tickers.clear()
        # Force degraded.
        with cache._lock:
            cache._degraded_until = time.monotonic() + 60.0
        # Request both: AAPL hits cache (warm), MSFT misses and should NOT fetch.
        r = cache.get_many_bundles(["AAPL", "MSFT"], deadline_seconds=5.0, executor=ex)
    assert r["AAPL"].sma10 is not None, "warm AAPL served from cache"
    assert r["MSFT"].sma10 is None, "MSFT miss short-circuited during degraded mode"
    assert fetch_tickers == [], "no fetch should have been attempted during degraded mode"


def test_ohlcv_cache_cold_start_hydrates_from_disk_archive(cfg, monkeypatch):
    """Empty in-memory cache + warm disk archive → bundle hydrates via the
    archive-aware fetch_daily_bars (Task 5 wrapping). Discriminating: counts
    helper invocations; verifies bundle SMA values reflect archive content,
    not yfinance live values."""
    import json
    from datetime import date, timedelta
    from concurrent.futures import ThreadPoolExecutor

    from swing.web.ohlcv_cache import OhlcvCache
    from swing.data import ohlcv_archive as archive_mod
    from swing.pipeline import ohlcv as ohlcv_mod

    cache_dir = cfg.paths.prices_cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)

    end_date = date(2026, 4, 28)
    archive_dates = [end_date - timedelta(days=i) for i in range(60, 0, -1)]
    archive_df = pd.DataFrame(
        {
            "Open": [100.0]*60, "High": [100.0]*60, "Low": [100.0]*60,
            "Close": [100.0 + i for i in range(60)],
            "Volume": [1000]*60,
        },
        index=pd.to_datetime(archive_dates),
    )
    archive_df.to_parquet(cache_dir / "AAPL.parquet")
    (cache_dir / "AAPL.meta.json").write_text(
        json.dumps({"last_full_refresh_date": end_date.isoformat()})
    )

    # Codex R1 Major 4 resolution: pin "today" so the weekly-refresh check
    # is stable across wallclock advance. Without this, once real today
    # drifts >7 days past end_date, the helper would enter the
    # weekly-refresh branch and try to call yfinance live.
    monkeypatch.setattr(
        archive_mod, "_last_completed_session_today",
        lambda: end_date + timedelta(days=1),
    )
    # Safety guard: ensure no real network call happens — the worker passes
    # end_date = action_session_for_run(now()) which is real-today, so the
    # helper may attempt an incremental gap fetch beyond our archive's
    # latest_stored. Patch yf.download to return empty so the gap is a no-op.
    monkeypatch.setattr(archive_mod.yf, "download", lambda *a, **kw: pd.DataFrame())

    helper_calls: list[str] = []
    real_helper = archive_mod.read_or_fetch_archive

    def counting_helper(ticker, *, end_date, cache_dir, archive_history_days):
        helper_calls.append(ticker)
        return real_helper(
            ticker, end_date=end_date, cache_dir=cache_dir,
            archive_history_days=archive_history_days,
        )

    monkeypatch.setattr(ohlcv_mod, "read_or_fetch_archive", counting_helper)

    cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        bundles = cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)

    assert "AAPL" in bundles
    bundle = bundles["AAPL"]
    # Discriminating: bundle reflects archive's known Close pattern.
    # Strip rule may peel off the last bar (date == end_date == today-1
    # under the pin); confirm previous_close is one of the known values
    # 158.0 (post-strip) or 159.0 (no strip).
    assert bundle.previous_close in (158.0, 159.0), (
        f"cold-start did not hydrate from disk archive; got previous_close={bundle.previous_close}"
    )
    assert helper_calls == ["AAPL"]


def test_ohlcv_cache_warm_hit_does_not_call_helper(cfg, monkeypatch):
    """In-memory cache hit → no disk archive read. Discriminating:
    helper-side fail-loud monkeypatch confirms zero invocations during the
    second call after a successful warm-up."""
    from concurrent.futures import ThreadPoolExecutor
    from swing.web.ohlcv_cache import OhlcvBundle, OhlcvCache
    from swing.pipeline import ohlcv as ohlcv_mod

    cache = OhlcvCache(cfg)
    warm_bundle = OhlcvBundle(
        sma10=10.0, sma20=20.0, sma50=50.0,
        previous_close=99.0, fetched_at=time.monotonic(),
    )
    cache._store["AAPL"] = (warm_bundle, time.monotonic())

    def boom(*args, **kwargs):
        raise AssertionError("read_or_fetch_archive must NOT be called on a warm hit")

    monkeypatch.setattr(ohlcv_mod, "read_or_fetch_archive", boom)

    with ThreadPoolExecutor(max_workers=2) as ex:
        bundles = cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)

    assert bundles["AAPL"].previous_close == 99.0
