"""Trade routes: GET /trades/entry/sizing-hint (tolerant contract) for now."""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.web.app import create_app


def test_sizing_hint_happy_path(seeded_db, monkeypatch):
    """Valid entry/stop with feasible sizing → numbers fragment, always 200.

    Uses entry=10.0, stop=9.0 so that with test equity ($1200) and
    max_risk_pct=0.005 ($6 budget, rps=$1) → 6 shares → feasible.
    seeded_db ensures schema exists so connect() succeeds.
    """
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/sizing-hint?entry_price=10.0&initial_stop=9.0")
    assert r.status_code == 200
    assert "sizing-hint" in r.text
    # Feasible result: text should include "sh".
    assert "sh" in r.text.lower()


def test_sizing_hint_missing_params(test_cfg):
    """Missing query params → 200 with dim guidance."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/sizing-hint")
    assert r.status_code == 200
    assert "valid entry price" in r.text.lower()


def test_sizing_hint_blank_params(test_cfg):
    """Blank query params → 200 with dim guidance."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/sizing-hint?entry_price=&initial_stop=")
    assert r.status_code == 200
    assert "valid entry price" in r.text.lower()


def test_sizing_hint_non_numeric(test_cfg):
    """Non-numeric values → 200 with dim guidance (no 422)."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/sizing-hint?entry_price=abc&initial_stop=xyz")
    assert r.status_code == 200
    assert "valid entry price" in r.text.lower()


def test_sizing_hint_stop_ge_entry(test_cfg):
    """stop >= entry → 200 with dim guidance (no compute_shares call, so no ValueError)."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/sizing-hint?entry_price=100.0&initial_stop=100.0")
    assert r.status_code == 200
    assert "stop &lt; entry" in r.text or "valid entry price" in r.text.lower()


def test_sizing_hint_zero_equity(seeded_db, monkeypatch):
    """Zero equity → 200 with feasible=False guidance, not 500."""
    cfg, cfg_path = seeded_db
    # Force equity=0 by patching current_equity where the route reads it.
    monkeypatch.setattr("swing.web.routes.trades.current_equity", lambda **_kw: 0.0)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/sizing-hint?entry_price=180.0&initial_stop=170.0")
    assert r.status_code == 200
    assert "no equity" in r.text.lower() or "unavailable" in r.text.lower()
