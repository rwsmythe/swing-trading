"""Phase 13 T-T4.SB.5 Sub-task 5B — Item 4: remove lightning glyph.

Plants a ticker within the prior trigger threshold
(``price >= entry_target * 0.99``) and asserts the lightning glyph is
ABSENT from the response.

Pre-fix at HEAD ``9b2a4db`` the glyph IS rendered on the watchlist row
when price is within 1% of entry_target — see existing
``tests/web/test_watchlist_pivot_column.py::
test_lightning_trigger_unchanged_uses_entry_target`` which asserts the
glyph IS present. That test is UPDATED in the same commit to assert
absence, mirroring the operator-locked Item 4 disposition.
"""
from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot


def _patch_price_cache(monkeypatch, ticker: str, price: float) -> None:
    snapshot_map = {
        ticker: PriceSnapshot(
            ticker=ticker,
            price=price,
            asof=datetime.now(),
            is_stale=False,
            source="live",
        )
    }
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: snapshot_map[t] for t in tickers if t in snapshot_map
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def test_watchlist_row_omits_lightning_glyph_at_trigger_threshold(
    seeded_db, seed_watchlist_and_candidate, monkeypatch,
):
    """Item 4: at the prior trigger boundary (price within 1% of
    entry_target) the lightning glyph must be ABSENT.

    Pre-fix the row partial emitted ``⚡`` when
    ``price >= entry_target * 0.99``; post-fix the conditional block is
    deleted. Asserts neither the lightning glyph (U+26A1) nor any
    surrogate-pair encoding appears in the response body.
    """
    cfg, cfg_path = seeded_db
    # Discriminating fixture: 9.95 >= 0.99 * 10.0 = 9.9 → would trigger pre-fix.
    seed_watchlist_and_candidate(
        ticker="UCTT", entry_target=10.0,
        candidate_pivot=10.0, last_close=9.95,
    )
    _patch_price_cache(monkeypatch, "UCTT", 9.95)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/watchlist")
    assert resp.status_code == 200
    # Lightning glyph absent (Item 4 fix).
    assert "⚡" not in resp.text, (
        "Item 4: lightning glyph must be absent from watchlist row HTML"
    )


def test_dashboard_watchlist_top5_omits_lightning_glyph(
    seeded_db, seed_watchlist_and_candidate, monkeypatch,
):
    """Item 4 symmetric coverage on dashboard top-5 watchlist surface.

    Same template partial (`watchlist_row.html.j2`) renders on both
    routes; this test guards against a regression that only covers the
    /watchlist route.
    """
    cfg, cfg_path = seeded_db
    seed_watchlist_and_candidate(
        ticker="PYPL", entry_target=42.00,
        candidate_pivot=100.00, last_close=41.60,
    )
    _patch_price_cache(monkeypatch, "PYPL", 41.60)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "⚡" not in resp.text, (
        "Item 4: lightning glyph must be absent from dashboard top-5 watchlist"
    )
