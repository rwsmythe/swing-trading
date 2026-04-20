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

    def fake_fetch(ticker, *, n_bars=60, as_of_date=None):
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

    def fake_fetch(ticker, *, n_bars=60, as_of_date=None):
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
    def fake_fetch(ticker, *, n_bars=60, as_of_date=None):
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

    def slow_fetch(ticker, *, n_bars=60, as_of_date=None):
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

    def always_fail(ticker, *, n_bars=60, as_of_date=None):
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

    def always_fail(ticker, *, n_bars=60, as_of_date=None):
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

    def always_fail(ticker, *, n_bars=60, as_of_date=None):
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

    def no_data_fetch(ticker, *, n_bars=60, as_of_date=None):
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

    def mixed_fetch(ticker, *, n_bars=60, as_of_date=None):
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

    def no_data_fetch(ticker, *, n_bars=60, as_of_date=None):
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

    def mixed_fetch(ticker, *, n_bars=60, as_of_date=None):
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
