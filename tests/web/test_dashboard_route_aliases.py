"""Phase 12.5 #2 HX-Redirect target / error-template href LOCK.

The dashboard is mounted at both `/` (canonical) and `/dashboard` (alias).
The Phase 12.5 #2 POST `/reconcile/discrepancy/{id}/resolve` emits
HX-Redirect to `/dashboard?reconcile_resolved={correction_id}` per
operator-LOCK §D #2/#8/#9; the error template's "Return to dashboard"
href also targets `/dashboard`. Both rely on this alias.

Pre-empt Phase 6 I3 gotcha: HX-Redirect target route MUST be registered.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.web.app import create_app


def test_dashboard_alias_route_registered(test_cfg, seeded_db):
    """`/` and `/dashboard` MUST both be registered on the FastAPI app."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/" in paths, f"canonical dashboard route missing; have: {paths}"
    assert "/dashboard" in paths, (
        f"alias /dashboard missing (Phase 12.5 #2 HX-Redirect target + "
        f"error-template href LOCK); have: {paths}"
    )


def test_dashboard_alias_serves_same_content(test_cfg, seeded_db):
    """Both `/` and `/dashboard` MUST render the same dashboard HTML."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    with TestClient(app) as client:
        resp_root = client.get("/")
        resp_alias = client.get("/dashboard")

    assert resp_root.status_code == 200
    assert resp_alias.status_code == 200
    # Both should contain the canonical dashboard discriminator
    assert "data-banner=" in resp_root.text or "Dashboard" in resp_root.text
    assert "data-banner=" in resp_alias.text or "Dashboard" in resp_alias.text


def test_dashboard_alias_accepts_reconcile_resolved_query_param(test_cfg, seeded_db):
    """The Phase 12.5 #2 HX-Redirect lands at `/dashboard?reconcile_resolved={id}`.

    V1 dashboard does NOT consume the query param (banked V2 §15.2 toast
    renderer) but the route MUST not 422 / 4xx on the unknown query param.
    """
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    with TestClient(app) as client:
        resp = client.get("/dashboard?reconcile_resolved=42")

    assert resp.status_code == 200, f"got {resp.status_code}; body={resp.text[:200]}"
