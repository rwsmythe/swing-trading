"""Integration tests — entry, soft-warn loop, stop-adjust, cold-cache entry.

Each test spins up a full in-process app (create_app + TestClient) and exercises
a complete user workflow end-to-end: seed DB → HTTP request(s) → DB assertion.
"""
from __future__ import annotations

import time

from tests.web.conftest import full_phase7_entry_payload


# ---------------------------------------------------------------------------
# Test 1: entry end-to-end
# ---------------------------------------------------------------------------

def test_entry_end_to_end(seeded_db, monkeypatch):
    """Seed watchlist, mock price cache, GET form, POST entry → trade in DB."""
    from datetime import datetime

    from fastapi.testclient import TestClient

    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.data.repos.trades import list_open_trades
    from swing.web.app import create_app
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db

    # Seed watchlist entry for AAPL.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()

    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(ticker=t, price=180.95, asof=datetime.now(),
                             is_stale=False, source="live")
            for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        # GET the entry form — should render with AAPL prefill.
        r_get = client.get("/trades/entry/form?ticker=AAPL")
        assert r_get.status_code == 200
        assert "AAPL" in r_get.text

        # POST the entry.
        r_post = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data=full_phase7_entry_payload(
                ticker="AAPL",
                entry_date="2026-04-18",
                entry_price="180.95",
                shares="5",
                initial_stop="170.00",
                rationale="aplus-setup",
            ),
        )
    assert r_post.status_code == 200
    assert "open-position-" in r_post.text
    assert "AAPL" in r_post.text

    # Verify the trade is in the DB.
    conn2 = connect(cfg.paths.db_path)
    try:
        trades = list_open_trades(conn2)
    finally:
        conn2.close()
    assert len(trades) == 1
    assert trades[0].ticker == "AAPL"
    assert trades[0].entry_price == 180.95


# ---------------------------------------------------------------------------
# Test 2: soft-warn loop end-to-end
# ---------------------------------------------------------------------------

def test_soft_warn_loop_end_to_end(seeded_db, monkeypatch):
    """First submit at soft cap → confirm fragment; second with force=true → row."""
    from datetime import datetime

    from fastapi.testclient import TestClient

    from swing.data.db import connect
    from swing.data.models import Trade, WatchlistEntry
    from swing.data.repos.trades import insert_trade_with_event
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.app import create_app
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db

    # Seed 4 open trades (= soft_warn_open default) + AAPL watchlist entry.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            for i, ticker in enumerate(("MSFT", "NVDA", "GOOG", "META")):
                insert_trade_with_event(conn, Trade(
                    id=None, ticker=ticker, entry_date="2026-04-15",
                    entry_price=100.0, initial_shares=1, initial_stop=90.0,
                    current_stop=90.0, state="entered",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ), event_ts=f"2026-04-15T09:{30 + i}:00")
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()

    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(ticker=t, price=180.95, asof=datetime.now(),
                             is_stale=False, source="live")
            for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    form_data = full_phase7_entry_payload(
        ticker="AAPL",
        entry_date="2026-04-18",
        entry_price="180.95",
        shares="1",
        initial_stop="170.00",
        rationale="aplus-setup",
    )
    with TestClient(app) as client:
        # First submit — no force; should receive soft-warn confirm fragment.
        r1 = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data=form_data,
        )
        assert r1.status_code == 200
        assert "Soft cap reached" in r1.text
        assert 'name="force" value="true"' in r1.text

        # Second submit — with force=true; should succeed and return a row.
        r2 = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data={**form_data, "force": "true"},
        )
        assert r2.status_code == 200
        assert "open-position-" in r2.text


# ---------------------------------------------------------------------------
# Test 3: stop-adjust end-to-end
# ---------------------------------------------------------------------------

def test_stop_adjust_end_to_end(seeded_db, monkeypatch):
    """Seed NVDA trade, POST stop adjustment to 912.0, verify DB updated."""
    from datetime import datetime

    from fastapi.testclient import TestClient

    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades, get_trade
    from swing.web.app import create_app
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()

    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "NVDA": PriceSnapshot(ticker="NVDA", price=932.0, asof=datetime.now(),
                                  is_stale=False, source="live"),
        },
    )

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/stop",
            headers={"HX-Request": "true"},
            data={"new_stop": "912.00", "rationale": "trail-10ma"},
        )
    assert r.status_code == 200
    assert f"open-position-{trade.id}" in r.text
    assert "912.00" in r.text

    # Verify DB updated.
    conn2 = connect(cfg.paths.db_path)
    try:
        updated = get_trade(conn2, trade.id)
    finally:
        conn2.close()
    assert updated is not None
    assert updated.current_stop == 912.0


# ---------------------------------------------------------------------------
# Test 4: cold-cache entry renders last-close fallback
# ---------------------------------------------------------------------------

def test_cold_cache_entry_renders_last_close_fallback(seeded_db, monkeypatch):
    """yfinance raises TimeoutError during market hours → fallback to last_close (178.25)."""
    import time as _time

    from fastapi.testclient import TestClient

    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.app import create_app
    from swing.web.price_cache import PriceCache

    cfg, cfg_path = seeded_db

    # Seed watchlist entry.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=178.25, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))

            # Insert a candidates row with close=178.25 for AAPL so
            # _last_close() can find it (used by _fetch_with_fallback).
            with conn:
                cur = conn.execute(
                    """INSERT INTO evaluation_runs
                       (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                        tickers_evaluated, aplus_count, watch_count, skip_count,
                        excluded_count, error_count, rs_universe_version, rs_universe_hash)
                       VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'hash')""",
                    ("2026-04-17T21:00:00", "2026-04-17", "2026-04-18"),
                )
                run_id = cur.lastrowid
            with conn:
                conn.execute(
                    """INSERT INTO candidates
                       (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                        adr_pct, tight_streak, pullback_pct, prior_trend_pct,
                        rs_rank, rs_return_12w_vs_spy, rs_method, pattern_tag, notes)
                       VALUES (?, 'AAPL', 'aplus', 178.25, 181.0, 170.0,
                               2.5, 3, NULL, NULL, NULL, NULL, 'unavailable', NULL, NULL)""",
                    (run_id,),
                )
    finally:
        conn.close()

    # Force yfinance.download to raise TimeoutError so _fetch_live_price fails.
    import yfinance as yf
    monkeypatch.setattr(yf, "download", lambda *a, **kw: (_ for _ in ()).throw(TimeoutError("test timeout")))

    # Force market_hours_now to return True so the live-fetch code path is taken.
    monkeypatch.setattr(PriceCache, "market_hours_now", lambda self: True)

    # is_degraded must be False so _fetch_with_fallback doesn't short-circuit.
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    t0 = _time.monotonic()
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=AAPL")
    elapsed = _time.monotonic() - t0

    assert r.status_code == 200
    # Fallback price 178.25 must appear in the rendered form, OR stale indicator.
    assert "stale" in r.text.lower() or "178.25" in r.text
    # Must not hang.
    assert elapsed < 10.0
