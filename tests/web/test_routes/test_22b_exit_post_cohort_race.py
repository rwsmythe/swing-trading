"""Arc 22-B RULING R1-3-SURFACES item 1 (i) -- the exit route's post-commit
dashboard rebuild is a SECONDARY panel of a page doing something else (the
exit already committed above it). It CONTAINS ``CohortReadRacedError`` ONLY
(never a bare except) and returns the COMMITTED exit with the 22-A3
degraded-success notice naming the trade -- the shape ``POST /trades/entry``
already carries -- instead of a 500 over a durable write.

BANKED, pre-existing, not this arc's: the exit route's post-commit rebuild
is uncontained for ANY OTHER exception (unlike the entry route's `except
BaseException` at `routes/trades.py` around line 2338) -- the register
carries it as the exit-side twin of 22-A3; this arc contains only the typed
CohortReadRacedError.
"""
from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import Trade
from swing.data.repos import trades as trades_repo
from swing.data.repos.trades import list_open_trades
from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot


def _patch_price_cache(monkeypatch) -> None:
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: PriceSnapshot(
                ticker=t, price=110.0, asof=datetime.now(),
                is_stale=False, source="live",
            )
            for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _seed_open_trade(cfg, ticker: str = "NVDA") -> int:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trades_repo.insert_trade_with_event(conn, Trade(
                id=None, ticker=ticker, entry_date="2026-04-15",
                entry_price=100.0, initial_shares=10, initial_stop=95.0,
                current_stop=95.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
        return int(trade.id)
    finally:
        conn.close()


def _plant_cohort_race(monkeypatch) -> None:
    """Simulate a ``CohortReadRacedError`` leaking out of the post-commit
    ``build_dashboard`` rebuild -- the exit route's OWN containment is the
    thing under test here (RULING R1-3-SURFACES (i)), not the mechanism by
    which the hyp-recs panel's builder happens to isolate the race
    internally (a SEPARATE fix, at ``dashboard.py:578``, covered by its
    own tests). Patching at the ``trades`` module's import site exercises
    the exit route's try/except boundary directly, regardless of whether
    ``build_dashboard`` itself ever leaks this error once its own
    isolation lands."""
    import swing.metrics.cohort as cohort_mod
    import swing.web.routes.trades as trades_mod

    def raced(*, cfg, cache, executor, ohlcv_cache):
        raise cohort_mod.CohortReadRacedError((3,))

    monkeypatch.setattr(trades_mod, "build_dashboard", raced)


def test_full_close_exit_contains_the_race_degraded_success_b22_237(
        seeded_db, monkeypatch) -> None:
    """Discriminator: the trade is CLOSED in the DB and the response is the
    degraded-success fragment naming it (a 500 FAILS; an unclosed trade
    FAILS)."""
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg)
    _patch_price_cache(monkeypatch)
    _plant_cohort_race(monkeypatch)
    with TestClient(create_app(cfg, cfg_path),
                    raise_server_exceptions=False) as client:
        resp = client.post(
            f"/trades/{trade_id}/exit",
            data={
                "exit_date": "2026-05-19", "exit_price": "120.50",
                "shares": "10", "reason": "manual", "notes": "",
            },
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    assert f"Trade #{trade_id}" in resp.text, resp.text
    assert "banner-degraded" in resp.text, resp.text
    assert "cohort read" in resp.text, resp.text
    conn = connect(cfg.paths.db_path)
    try:
        (state,) = conn.execute(
            "SELECT state FROM trades WHERE id = ?", (trade_id,)).fetchone()
    finally:
        conn.close()
    assert state in ("closed", "reviewed"), state


def test_partial_close_exit_contains_the_race_degraded_success_b22_237(
        seeded_db, monkeypatch) -> None:
    """The partial-close branch never reaches the row re-render (the
    dashboard rebuild races BEFORE the fully_closed/partial split); the
    trade is durably PARTIALLY closed and the response degrades the same
    way as the full-close case."""
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg)
    _patch_price_cache(monkeypatch)
    _plant_cohort_race(monkeypatch)
    with TestClient(create_app(cfg, cfg_path),
                    raise_server_exceptions=False) as client:
        resp = client.post(
            f"/trades/{trade_id}/exit",
            data={
                "exit_date": "2026-05-19", "exit_price": "120.50",
                "shares": "4", "reason": "manual", "notes": "",
            },
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    assert f"Trade #{trade_id}" in resp.text, resp.text
    assert "banner-degraded" in resp.text, resp.text
    conn = connect(cfg.paths.db_path)
    try:
        (state, current_size) = conn.execute(
            "SELECT state, current_size FROM trades WHERE id = ?",
            (trade_id,)).fetchone()
    finally:
        conn.close()
    assert state == "partial_exited", state
    assert current_size == 6, current_size
