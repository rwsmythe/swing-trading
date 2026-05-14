"""Phase 11 Sub-bundle C T-C.6 — Pipeline + market-data ladder integration.

Per dispatch brief T-C.6 + plan §H.6: verifies `_step_evaluate` +
`_step_charts` callsites consume the cache layer's ladder integration
(T-C.4) such that pipeline-internal Schwab quote/window fetches write
`surface='pipeline'` audit rows under production AND ZERO audit rows
under sandbox / ladder-disabled. NO new pipeline step; NO ordering change.

Four bound tests (per brief §Tasks-C T-C.6):
  1. Existing pipeline tests continue to pass (covered separately by the
     full fast-suite run; no per-test assertion here — see test #5 below
     for a structural check that the helper-injection point doesn't
     break the `_step_evaluate` signature).
  2. Under `environment='production'` + ladder_enabled + mock schwab
     client, the warm helper produces `schwab_api_calls` rows tagged
     `surface='pipeline'`.
  3. Under `environment='sandbox'`, the ladder short-circuits → ZERO
     `schwab_api_calls` rows written for the warm.
  4. Cache hit rate: two warm invocations within TTL → second invocation
     does NOT re-fire the ladder hook (cache hit served from memory).
  5. Pipeline-step signature smoke: `_step_evaluate(..., price_cache=None)`
     is accepted + behaves identically to pre-T-C.6 when no cache is
     supplied (regression guard for downstream invokers).

Pattern mirrors `tests/integration/test_schwab_pipeline_production_only_gate.py`
(SimpleNamespace cfg, MagicMock client, ensure_schema in tmp_path).
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from swing.data.db import ensure_schema
from swing.integrations.schwab import client as schwab_client_module
from swing.pipeline.runner import (
    _construct_pipeline_schwab_client,
    _install_pipeline_marketdata_caches,
    _warm_pipeline_marketdata,
)
from swing.web.price_cache import PriceSnapshot


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def v18_conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "t-c6-test.db")


@pytest.fixture(autouse=True)
def reset_schwab_redaction_state():
    original_factory = logging.getLogRecordFactory()
    original_installed = schwab_client_module._FACTORY_INSTALLED
    original_orig = schwab_client_module._ORIGINAL_RECORD_FACTORY
    original_secrets = set(schwab_client_module._GLOBAL_KNOWN_SECRETS)
    schwab_client_module._GLOBAL_KNOWN_SECRETS.clear()
    schwab_client_module._FACTORY_INSTALLED = False
    schwab_client_module._ORIGINAL_RECORD_FACTORY = None
    logging.setLogRecordFactory(logging.LogRecord)
    yield
    logging.setLogRecordFactory(original_factory)
    schwab_client_module._FACTORY_INSTALLED = original_installed
    schwab_client_module._ORIGINAL_RECORD_FACTORY = original_orig
    schwab_client_module._GLOBAL_KNOWN_SECRETS.clear()
    schwab_client_module._GLOBAL_KNOWN_SECRETS.update(original_secrets)


def _make_cfg(
    *, env: str, ladder_enabled: bool, db_path: Path, prices_cache_dir: Path,
) -> SimpleNamespace:
    """Build a cfg-shaped namespace exposing the fields the T-C.6 wiring +
    PriceCache reads."""
    schwab_ns = SimpleNamespace(
        environment=env,
        marketdata_ladder_enabled=ladder_enabled,
        timeout_seconds=30.0,
        callback_url="https://127.0.0.1",
        account_hash="abcd...",
        lookback_days=7,
    )
    integrations_ns = SimpleNamespace(schwab=schwab_ns)
    web_ns = SimpleNamespace(
        price_cache_ttl_seconds=120,
        price_fetch_timeout_seconds=3,
        max_concurrent_price_fetches=8,
        ohlcv_cache_ttl_seconds=3600,
        max_concurrent_ohlcv_fetches=8,
        circuit_breaker_cooldown_seconds=60,
    )
    paths_ns = SimpleNamespace(
        db_path=db_path, prices_cache_dir=prices_cache_dir,
    )
    archive_ns = SimpleNamespace(archive_history_days=1260)
    return SimpleNamespace(
        integrations=integrations_ns, web=web_ns, paths=paths_ns,
        archive=archive_ns,
    )


def _mock_quote_resp(symbol: str, last_price: float = 150.0) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {
        symbol: {
            "quote": {
                "lastPrice": last_price,
                "bidPrice": last_price - 0.5,
                "askPrice": last_price + 0.5,
                "mark": last_price,
                "quoteTimeInLong": 1715692800000,
                "delayed": False,
            },
        },
    }
    resp.status_code = 200
    resp.headers = {}
    return resp


def _count_audit(conn: sqlite3.Connection, *, surface: str | None = None) -> int:
    if surface is None:
        return conn.execute(
            "SELECT COUNT(*) FROM schwab_api_calls",
        ).fetchone()[0]
    return conn.execute(
        "SELECT COUNT(*) FROM schwab_api_calls WHERE surface = ?", (surface,),
    ).fetchone()[0]


# ============================================================================
# Test 1 — Pipeline-step signature smoke (regression guard)
# ============================================================================


def test_step_evaluate_accepts_price_cache_kwarg_default_none(tmp_path):
    """The `_step_evaluate` signature gains a new `price_cache=None` kwarg
    in T-C.6. When omitted (downstream invokers that don't pass it) +
    when supplied as None, behavior must be identical to pre-T-C.6.
    """
    import inspect

    from swing.pipeline.runner import _step_evaluate

    sig = inspect.signature(_step_evaluate)
    params = sig.parameters
    assert "price_cache" in params
    assert params["price_cache"].default is None


# ============================================================================
# Test 2 — Production + ladder enabled → `surface='pipeline'` audit rows
# ============================================================================


def test_warm_under_production_writes_pipeline_audit_rows(
    v18_conn, tmp_path, monkeypatch,
):
    """When schwab_client is provided + env='production' +
    ladder_enabled=True, the warm helper fires the T-C.1 quote wrapper
    + writes audit rows tagged `surface='pipeline'`.
    """
    db_path = tmp_path / "t-c6-prod.db"
    # Re-open the conn against the tmp db so subsequent helper invocations
    # also see the schema (the fixture-built conn references a different
    # path); we use a fresh ensure_schema-built db here.
    v18_conn.close()
    fresh_conn = ensure_schema(db_path)
    cfg = _make_cfg(
        env="production", ladder_enabled=True, db_path=db_path,
        prices_cache_dir=tmp_path / "cache",
    )
    schwab = MagicMock()
    schwab.quotes.return_value = _mock_quote_resp("AAPL", 150.0)

    # Pre-flight: zero audit rows.
    assert _count_audit(fresh_conn) == 0

    # Inject the mock client directly (skip the constructor seam — we
    # want to test the helper behavior, not the seam).
    # pipeline_run_id=None avoids FK violation against pipeline_runs table
    # in the unit-test seam — production callsite passes lease.run_id which
    # always exists (lease.acquire INSERTs the row).
    price_cache, _ = _install_pipeline_marketdata_caches(
        cfg, schwab_client=schwab, pipeline_run_id=None,
    )
    assert price_cache is not None

    # Force market-hours so PriceCache attempts a live fetch through the
    # ladder hook (not the after-hours last-close branch).
    monkeypatch.setattr(price_cache, "market_hours_now", lambda: True)

    _warm_pipeline_marketdata(
        cfg=cfg, price_cache=price_cache, held_tickers=["AAPL"],
    )

    fresh_conn = sqlite3.connect(str(db_path))
    try:
        # Pipeline-surface audit rows present.
        total = _count_audit(fresh_conn)
        pipeline_rows = _count_audit(fresh_conn, surface="pipeline")
        assert total >= 1, (
            "expected at least one schwab_api_calls audit row under production"
        )
        assert pipeline_rows >= 1, (
            "expected the audit row to carry surface='pipeline'"
        )
    finally:
        fresh_conn.close()


# ============================================================================
# Test 3 — Sandbox short-circuit → ZERO audit rows
# ============================================================================


def test_warm_under_sandbox_writes_zero_audit_rows(
    v18_conn, tmp_path, monkeypatch,
):
    """When env='sandbox', the ladder short-circuits BEFORE any schwabdev
    call + writes ZERO `schwab_api_calls` rows. Cache fills via the
    yfinance fallback path (which we mock so no real network hit fires).
    """
    db_path = tmp_path / "t-c6-sandbox.db"
    v18_conn.close()
    fresh_conn = ensure_schema(db_path)
    cfg = _make_cfg(
        env="sandbox", ladder_enabled=True, db_path=db_path,
        prices_cache_dir=tmp_path / "cache",
    )
    schwab = MagicMock()
    # Even though schwab is supplied, sandbox short-circuit skips the call.

    # pipeline_run_id=None avoids FK violation against pipeline_runs table
    # in the unit-test seam — production callsite passes lease.run_id which
    # always exists (lease.acquire INSERTs the row).
    price_cache, _ = _install_pipeline_marketdata_caches(
        cfg, schwab_client=schwab, pipeline_run_id=None,
    )
    assert price_cache is not None

    monkeypatch.setattr(price_cache, "market_hours_now", lambda: True)
    # Mock the yfinance fallback at the PriceCache._fetch_live_price level
    # so the ladder's yfinance fallback succeeds without network.
    monkeypatch.setattr(price_cache, "_fetch_live_price", lambda _t: 99.0)

    _warm_pipeline_marketdata(
        cfg=cfg, price_cache=price_cache, held_tickers=["AAPL"],
    )

    fresh_conn = sqlite3.connect(str(db_path))
    try:
        # Sandbox short-circuit lives at the LADDER layer per T-C.3 LOCK —
        # ZERO schwab_api_calls rows in any surface.
        assert _count_audit(fresh_conn) == 0, (
            "sandbox env must NOT produce schwab_api_calls audit rows"
        )
        # schwabdev was never called (ladder short-circuit fires BEFORE
        # the schwabdev invocation).
        assert not schwab.quotes.called, (
            "sandbox short-circuit must not invoke schwabdev"
        )
    finally:
        fresh_conn.close()


# ============================================================================
# Test 4 — Cache hit: second warm invocation does NOT re-fire ladder
# ============================================================================


def test_warm_twice_within_ttl_only_fires_ladder_once_per_ticker(
    v18_conn, tmp_path, monkeypatch,
):
    """PriceCache TTL provides the test-#4 hit-rate property: invoking
    `_warm_pipeline_marketdata` twice in succession within TTL means the
    second invocation hits cache for already-fetched tickers + does NOT
    fire the ladder hook again. Under production env this translates to
    a smaller schwab_api_calls row count after the second run than naive
    "2 * tickers" would predict.
    """
    db_path = tmp_path / "t-c6-cachehit.db"
    v18_conn.close()
    fresh_conn = ensure_schema(db_path)
    cfg = _make_cfg(
        env="production", ladder_enabled=True, db_path=db_path,
        prices_cache_dir=tmp_path / "cache",
    )
    schwab = MagicMock()
    schwab.quotes.return_value = _mock_quote_resp("AAPL", 150.0)

    price_cache, _ = _install_pipeline_marketdata_caches(
        cfg, schwab_client=schwab, pipeline_run_id=None,
    )
    assert price_cache is not None
    monkeypatch.setattr(price_cache, "market_hours_now", lambda: True)

    _warm_pipeline_marketdata(
        cfg=cfg, price_cache=price_cache, held_tickers=["AAPL"],
    )
    _warm_pipeline_marketdata(
        cfg=cfg, price_cache=price_cache, held_tickers=["AAPL"],
    )

    # The schwabdev `Client.quotes` should have been called EXACTLY ONCE
    # — the second warm invocation hit cache.
    assert schwab.quotes.call_count == 1, (
        f"expected exactly one schwabdev quotes call (second warm should "
        f"hit cache); got {schwab.quotes.call_count}"
    )

    fresh_conn = sqlite3.connect(str(db_path))
    try:
        # Audit rows: one per ladder invocation = exactly one row total
        # for AAPL across both warms.
        total = _count_audit(fresh_conn)
        assert total == 1, (
            f"expected exactly one schwab_api_calls audit row after two "
            f"TTL-warm invocations; got {total}"
        )
    finally:
        fresh_conn.close()


# ============================================================================
# Test 5 — Default `_construct_pipeline_schwab_client` returns None
# ============================================================================


def test_construct_pipeline_schwab_client_returns_none_by_default(tmp_path):
    """Pipeline cannot prompt for credentials; default `_construct_*`
    helper returns None unless tests monkeypatch. Matches the precedent
    set by `_step_schwab_snapshot` (`client=None` → silent-skip)."""
    cfg = _make_cfg(
        env="production", ladder_enabled=True,
        db_path=tmp_path / "any.db",
        prices_cache_dir=tmp_path / "cache",
    )
    client = _construct_pipeline_schwab_client(cfg)
    assert client is None


# ============================================================================
# Test 6 — None client → no caches constructed (pipeline yfinance-only)
# ============================================================================


def test_install_caches_with_none_client_returns_none_pair():
    """When schwab_client is None, both caches are None. Pipeline retains
    existing PriceFetcher/yfinance path; ZERO `schwab_api_calls` rows
    written."""
    cfg = SimpleNamespace()  # cfg not even consulted when client is None
    price_cache, ohlcv_cache = _install_pipeline_marketdata_caches(
        cfg, schwab_client=None, pipeline_run_id=None,
    )
    assert price_cache is None
    assert ohlcv_cache is None


# ============================================================================
# Test 7 — `_warm_pipeline_marketdata` is a no-op when cache is None
# ============================================================================


def test_warm_with_none_cache_is_noop(tmp_path):
    """The warm helper MUST tolerate `price_cache=None` (the common
    pipeline-internal case where no schwab_client could be constructed)
    + return without raising. The pipeline's existing PriceFetcher path
    remains the authoritative price source."""
    cfg = SimpleNamespace()
    # Should not raise.
    _warm_pipeline_marketdata(
        cfg=cfg, price_cache=None, held_tickers=["AAPL", "MSFT"],
    )


# ============================================================================
# Test 8 — Pipeline step ordering UNCHANGED post-T-C.6
# ============================================================================


def test_pipeline_step_ordering_unchanged_post_tc6():
    """Per brief CRITICAL pre-emption #2: NO step ordering change. The
    sequence of `lease.step(...)` invocations in `run_pipeline_internal`
    MUST match the pre-T-C.6 sequence exactly.
    """
    import inspect

    from swing.pipeline import runner

    src = inspect.getsource(runner.run_pipeline_internal)
    # The expected sequence per existing pre-T-C.6 ordering. Anchored
    # against the source so any future re-ordering must trip this test.
    expected = [
        "weather",
        "finviz_fetch",
        "evaluate",
        "daily_management",
        "watchlist",
        "recommendations",
        "schwab_snapshot",
        "schwab_orders",
        "charts",
        "export",
        "complete",
    ]
    # Naive substring-presence + in-order check via cumulative .index().
    cursor = 0
    for step in expected:
        marker = f'lease.step("{step}")'
        found_at = src.find(marker, cursor)
        assert found_at != -1, (
            f"missing or out-of-order lease.step({step!r}) in "
            f"run_pipeline_internal source"
        )
        cursor = found_at + len(marker)
