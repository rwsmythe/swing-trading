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
