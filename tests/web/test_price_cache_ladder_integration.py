"""PriceCache + OhlcvCache integration with Schwab market-data ladder (T-C.4).

Per Phase 11 Sub-bundle C T-C.4 dispatch brief — verifies:
  - Cache routes live fetches through the ladder when a ladder fetcher is
    installed; provider tag stamped onto entries.
  - Sandbox / ladder-disabled paths short-circuit at the ladder layer; cache
    code stays env-agnostic; provider remains 'yfinance' on the fallback path.
  - PriceSnapshot.provider field is distinct from the existing source TTL
    field (regression guard for §A.8 LOCK).
  - Cache miss invokes ladder; cache hit does NOT.
  - OhlcvBundle.provider mirrors PriceSnapshot.provider semantics.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest

from swing.data.db import connect, ensure_schema


# ---------- shared fixtures ----------


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


def _bars(closes, start="2026-01-02") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(closes), freq="B")
    return pd.DataFrame({"Close": closes}, index=idx)


# ============================================================================
# PriceSnapshot.provider field smoke + regression guard (T-C.3 covers but
# re-verified from T-C.4's vantage point)
# ============================================================================


def test_pricesnapshot_provider_field_defaults_none_preserving_source():
    """Critical regression guard (pre-emption #3): the new `provider` field
    defaults to None so a pre-existing fixture that constructs a
    PriceSnapshot without `provider` continues to work; `source` (TTL state)
    is preserved as a distinct field."""
    from datetime import datetime
    from swing.web.price_cache import PriceSnapshot

    snap = PriceSnapshot(
        ticker="AAPL", price=100.0, asof=datetime.now(),
        is_stale=False, source="live",
    )
    # `source` (TTL-state) preserved untouched.
    assert snap.source == "live"
    # `provider` (new provenance) defaults to None — not stamped.
    assert snap.provider is None


def test_pricesnapshot_source_and_provider_are_independent_fields():
    """A single snapshot can carry both a TTL-state `source` AND a
    provenance `provider` simultaneously — they are distinct concerns."""
    from datetime import datetime
    from swing.web.price_cache import PriceSnapshot

    snap = PriceSnapshot(
        ticker="AAPL", price=100.0, asof=datetime.now(),
        is_stale=False, source="live", provider="schwab_api",
    )
    assert snap.source == "live"  # TTL state
    assert snap.provider == "schwab_api"  # data origin
    assert snap.source != snap.provider


# ============================================================================
# PriceCache + ladder integration
# ============================================================================


def test_pricecache_fill_via_ladder_stamps_schwab_provider(seeded_db, monkeypatch):
    """Production-env ladder path: fetcher returns ('schwab_api') →
    cache stores entry with provider='schwab_api'."""
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "market_hours_now", lambda: True)

    def ladder_fetch(ticker: str) -> tuple[float, str]:
        return (181.50, "schwab_api")

    cache.set_ladder_fetcher(ladder_fetch)

    snap = cache.get("AAPL")
    assert snap is not None
    assert snap.price == 181.50
    assert snap.source == "live"  # TTL-state preserved
    assert snap.provider == "schwab_api"  # provenance stamped
    assert not snap.is_stale


def test_pricecache_fill_via_ladder_stamps_yfinance_provider_on_fallback(
    seeded_db, monkeypatch,
):
    """Sandbox or auth-failure path: ladder short-circuits to yfinance
    and reports provider='yfinance'. Cache stays env-agnostic — it just
    propagates whatever the ladder returned."""
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "market_hours_now", lambda: True)

    def ladder_fetch_yfinance_branch(ticker: str) -> tuple[float, str]:
        # Simulates the ladder's sandbox short-circuit OR a failed Schwab
        # attempt that fell back to yfinance — either way provider='yfinance'.
        return (180.25, "yfinance")

    cache.set_ladder_fetcher(ladder_fetch_yfinance_branch)

    snap = cache.get("AAPL")
    assert snap is not None
    assert snap.price == 180.25
    assert snap.provider == "yfinance"
    assert snap.source == "live"


def test_pricecache_miss_invokes_ladder_hit_does_not(seeded_db, monkeypatch):
    """Cache miss → ladder called. Cache hit (within TTL) → ladder NOT called."""
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "market_hours_now", lambda: True)

    call_count = {"n": 0}

    def ladder_fetch(ticker: str) -> tuple[float, str]:
        call_count["n"] += 1
        return (100.0, "schwab_api")

    cache.set_ladder_fetcher(ladder_fetch)

    # First call: miss → ladder invoked.
    s1 = cache.get("AAPL")
    assert call_count["n"] == 1
    assert s1.provider == "schwab_api"

    # Second call within TTL: hit → ladder NOT invoked.
    s2 = cache.get("AAPL")
    assert call_count["n"] == 1, "cache hit must not re-invoke ladder"
    assert s2.provider == "schwab_api"


def test_pricecache_no_ladder_preserves_legacy_yfinance_path(seeded_db, monkeypatch):
    """When set_ladder_fetcher is NOT called, the cache uses its legacy
    yfinance-only path — provider remains None (no provenance tagging).
    Critical backward-compat: existing fixtures that don't know about the
    ladder continue to work unchanged."""
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "market_hours_now", lambda: True)
    monkeypatch.setattr(cache, "_fetch_live_price", lambda t: 99.5)

    snap = cache.get("AAPL")
    assert snap.price == 99.5
    assert snap.source == "live"
    # No ladder installed → provider stays None for backward compat.
    assert snap.provider is None


# ============================================================================
# OhlcvBundle.provider field smoke + regression guard
# ============================================================================


def test_ohlcvbundle_provider_field_defaults_none():
    """Critical regression guard: legacy OhlcvBundle constructors (no
    `provider` arg) continue to produce bundles with provider=None."""
    from swing.web.ohlcv_cache import OhlcvBundle

    b = OhlcvBundle(
        sma10=100.0, sma20=99.0, sma50=98.0,
        previous_close=100.5, fetched_at=time.monotonic(),
        adr_pct=2.5,
    )
    assert b.provider is None
    assert b.sma10 == 100.0


def test_ohlcvbundle_provider_validator_rejects_invalid_value():
    """Mirrors PriceSnapshot.provider validator — only None / 'schwab_api'
    / 'yfinance' are legal."""
    from swing.web.ohlcv_cache import OhlcvBundle

    with pytest.raises(ValueError, match="provider must be one of"):
        OhlcvBundle(
            sma10=None, sma20=None, sma50=None,
            previous_close=None, fetched_at=time.monotonic(),
            provider="bloomberg",
        )


# ============================================================================
# OhlcvCache + ladder integration
# ============================================================================


def test_ohlcvcache_fill_via_ladder_stamps_schwab_provider(test_cfg, monkeypatch):
    """Production-env ladder path: fetcher returns Schwab-tagged bars → cache
    stores OhlcvBundle with provider='schwab_api'."""
    from swing.web.ohlcv_cache import OhlcvCache

    cfg, _ = test_cfg
    cache = OhlcvCache(cfg)

    def ladder_bars_fetch(ticker: str) -> tuple:
        return (_bars([100.0 + i for i in range(50)]), "schwab_api")

    cache.set_ladder_bars_fetcher(ladder_bars_fetch)

    with ThreadPoolExecutor(max_workers=2) as ex:
        r = cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)

    bundle = r["AAPL"]
    assert bundle.sma10 is not None
    assert bundle.provider == "schwab_api"


def test_ohlcvcache_fill_via_ladder_stamps_yfinance_provider_on_fallback(
    test_cfg, monkeypatch,
):
    """Sandbox short-circuit OR Schwab failure path: ladder returns yfinance
    bars + provider='yfinance' tag."""
    from swing.web.ohlcv_cache import OhlcvCache

    cfg, _ = test_cfg
    cache = OhlcvCache(cfg)

    def ladder_bars_fetch_yfinance(ticker: str) -> tuple:
        return (_bars([95.0 + i for i in range(50)]), "yfinance")

    cache.set_ladder_bars_fetcher(ladder_bars_fetch_yfinance)

    with ThreadPoolExecutor(max_workers=2) as ex:
        r = cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)

    bundle = r["AAPL"]
    assert bundle.sma10 is not None
    assert bundle.provider == "yfinance"


def test_ohlcvcache_miss_invokes_ladder_hit_does_not(test_cfg, monkeypatch):
    """Cache miss → ladder bars fetcher invoked. Cache hit (within TTL) →
    fetcher NOT invoked. Mirrors PriceCache discipline."""
    from swing.web.ohlcv_cache import OhlcvCache

    cfg, _ = test_cfg
    cache = OhlcvCache(cfg)

    call_count = {"n": 0}

    def ladder_bars_fetch(ticker: str) -> tuple:
        call_count["n"] += 1
        return (_bars([100.0 + i for i in range(50)]), "schwab_api")

    cache.set_ladder_bars_fetcher(ladder_bars_fetch)

    with ThreadPoolExecutor(max_workers=2) as ex:
        # First call: miss → ladder invoked.
        r1 = cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
        assert call_count["n"] == 1
        assert r1["AAPL"].provider == "schwab_api"

        # Second call: hit → ladder NOT invoked again.
        r2 = cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
        assert call_count["n"] == 1, "cache hit must not re-invoke ladder"
        assert r2["AAPL"].provider == "schwab_api"


def test_ohlcvcache_no_ladder_preserves_legacy_yfinance_path(test_cfg, monkeypatch):
    """Backward compat: when no ladder fetcher is installed, the worker uses
    the legacy `ohlcv_mod.fetch_daily_bars` path. provider stays None."""
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.pipeline import ohlcv as ohlcv_mod

    cfg, _ = test_cfg

    def fake_fetch(ticker, *, n_bars=60, as_of_date=None, **_):
        return _bars([110.0 + i for i in range(50)])

    monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", fake_fetch)
    cache = OhlcvCache(cfg)
    # Explicitly do NOT call set_ladder_bars_fetcher.

    with ThreadPoolExecutor(max_workers=2) as ex:
        r = cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)

    bundle = r["AAPL"]
    assert bundle.sma10 is not None
    # Legacy path: provider remains None (no provenance tagging).
    assert bundle.provider is None


# ============================================================================
# Composition with the actual ladder (light integration)
# ============================================================================


def test_pricecache_ladder_integration_with_sandbox_cfg(seeded_db, monkeypatch):
    """When the cache's ladder fetcher wraps `fetch_quote_via_ladder` and the
    cfg has environment='sandbox', the ladder short-circuits to yfinance.
    Cache code stays env-agnostic; provider comes back as 'yfinance'."""
    from datetime import datetime as _dt

    from swing.integrations.schwab.marketdata_ladder import fetch_quote_via_ladder
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, _ = seeded_db
    # Override schwab environment to sandbox.
    from dataclasses import replace as _replace
    sandbox_schwab = _replace(cfg.integrations.schwab, environment="sandbox")
    sandbox_integrations = _replace(cfg.integrations, schwab=sandbox_schwab)
    sandbox_cfg = _replace(cfg, integrations=sandbox_integrations)

    cache = PriceCache(sandbox_cfg)
    monkeypatch.setattr(cache, "market_hours_now", lambda: True)

    # yfinance fallback returns a PriceSnapshot stub; the ladder receives this
    # via the callback and returns (snapshot, 'yfinance') under sandbox.
    def yfinance_fallback(ticker: str) -> PriceSnapshot:
        return PriceSnapshot(
            ticker=ticker, price=200.0, asof=_dt.now(),
            is_stale=False, source="live",
        )

    def ladder_fetch(ticker: str) -> tuple[float, str]:
        # In production the cache uses a real conn / surface. For this test
        # those are unused because sandbox short-circuits before any conn
        # access; pass minimal sentinels.
        snap, provider_tag = fetch_quote_via_ladder(
            ticker,
            cfg=sandbox_cfg,
            schwab_client=None,
            yfinance_fallback_fn=yfinance_fallback,
            conn=None,  # unused in sandbox short-circuit branch
            surface="test",
        )
        return (snap.price, provider_tag)

    cache.set_ladder_fetcher(ladder_fetch)

    snap = cache.get("AAPL")
    assert snap is not None
    assert snap.price == 200.0
    # Sandbox short-circuit at ladder → provider tag 'yfinance'.
    assert snap.provider == "yfinance"
