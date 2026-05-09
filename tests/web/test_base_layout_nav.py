"""Task family D — base-layout top-nav Reviews link contract.

Pins three contracts:
  D.1 — base layout renders an `<a href="/reviews/pending">Reviews</a>`
        link in the topbar (visible link text + canonical href).
  D.2 — nav-link order is exactly Dashboard, Watchlist, Journal, Reviews,
        Pipeline, Config (Reviews inserted between Journal and Pipeline;
        existing entries unmoved).
  D.3 — `/reviews/pending` is registered in the app's route table.
        Per CLAUDE.md "HX-Redirect target route must be verified to exist"
        (Phase 6 R5 I3) lesson generalized to "any link target route must
        be verified" — link points at a real route, not a stale ghost.
"""
from __future__ import annotations

import re

from fastapi.testclient import TestClient

from swing.web.app import create_app
from swing.web.price_cache import PriceCache


# Expected nav order — Reviews inserted between Journal and Pipeline.
EXPECTED_NAV_HREFS = [
    "/",
    "/watchlist",
    "/journal",
    "/reviews/pending",
    "/pipeline",
    "/config",
]


def _client(cfg, cfg_path, monkeypatch):
    """Spin up a TestClient with PriceCache neutralized so GET / is fast +
    deterministic without needing pipeline data seeded."""
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    app = create_app(cfg, cfg_path)
    return app, TestClient(app)


def test_d1_reviews_link_rendered_in_topbar(seeded_db, monkeypatch):
    """D.1 — base.html.j2 nav must include a Reviews link to /reviews/pending."""
    cfg, cfg_path = seeded_db
    app, client = _client(cfg, cfg_path, monkeypatch)
    with client:
        r = client.get("/")
    assert r.status_code == 200, r.text[:300]
    # canonical href present
    assert 'href="/reviews/pending"' in r.text
    # visible link text — tightened to ensure "Reviews" is the anchor text,
    # not just an incidental string elsewhere on the page.
    assert ">Reviews</a>" in r.text


def test_d2_nav_link_order(seeded_db, monkeypatch):
    """D.2 — nav-link order must be Dashboard → Watchlist → Journal →
    Reviews → Pipeline → Config (Reviews inserted between Journal and
    Pipeline; existing entries unmoved)."""
    cfg, cfg_path = seeded_db
    app, client = _client(cfg, cfg_path, monkeypatch)
    with client:
        r = client.get("/")
    assert r.status_code == 200, r.text[:300]

    # Slice out the topbar nav section to avoid matching anchors elsewhere
    # on the page (e.g., dashboard cards that link to /pipeline or /config).
    m = re.search(
        r'<nav class="topbar">(.*?)</nav>', r.text, flags=re.DOTALL,
    )
    assert m is not None, "Could not find <nav class=\"topbar\">...</nav>"
    nav_html = m.group(1)

    hrefs = re.findall(r'<a\s+href="([^"]+)"', nav_html)
    assert hrefs == EXPECTED_NAV_HREFS, (
        f"Nav-link order mismatch.\n"
        f"  expected: {EXPECTED_NAV_HREFS}\n"
        f"  got:      {hrefs}"
    )


def test_d3_reviews_pending_route_registered(seeded_db):
    """D.3 — /reviews/pending must be a registered route in the FastAPI
    app's route table. Pins the contract that the nav link points at a
    real route (Phase 6 R5 I3 lesson generalized).
    """
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/reviews/pending" in paths, (
        f"/reviews/pending not in app.routes; available paths: "
        f"{sorted(p for p in paths if p)}"
    )
