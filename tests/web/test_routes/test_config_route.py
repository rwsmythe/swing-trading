"""Post-Phase-12 Sub-bundle 2 Task T-2.3 — /config nav-link to /schwab/status.

Per plan §B T-2.3 acceptance criteria (3 discriminating tests):
  1. /config response contains href='/schwab/status' + 'Schwab integration
     status' (or 'Schwab status') text.
  2. /schwab/setup nav-link preserved (no regression).
  3. /schwab/status target route registered in app.routes (Phase 6 I3
     HX-Redirect-target-unrouted gotcha inheritance).

Mirror of Phase 12 Sub-bundle B `7b75d4a` orchestrator-inline gate-fix
that added the /schwab/setup nav-link to /config (the "External
integrations" section). This task ADDS a second link (status) in the
same section without disturbing the existing setup link.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.web.app import create_app


def _isolate_home(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))


# ---------------------------------------------------------------------------
# (1) /config response contains href="/schwab/status" + status link text.
# ---------------------------------------------------------------------------

def test_config_nav_link_to_schwab_status_renders(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 1 — operator-facing nav-link visible in External integrations
    section. Required for /schwab/status discoverability (without it,
    operator only sees CLI status output)."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/config")
    assert r.status_code == 200
    assert 'href="/schwab/status"' in r.text
    # Plan §B T-2.3 acceptance: "Schwab integration status" or "Schwab
    # status" text. Implementation uses "Schwab integration status".
    assert "Schwab integration status" in r.text


# ---------------------------------------------------------------------------
# (2) /schwab/setup nav-link preserved (no regression).
# ---------------------------------------------------------------------------

def test_config_preserves_schwab_setup_nav_link(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 2 — existing nav-link to /schwab/setup is NOT regressed by
    the T-2.3 addition (Phase 12 Sub-bundle B `7b75d4a` orchestrator-
    inline gate-fix added it; this test pins it stays)."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/config")
    assert r.status_code == 200
    assert 'href="/schwab/setup"' in r.text
    assert "Schwab OAuth" in r.text or "Set up" in r.text


# ---------------------------------------------------------------------------
# (3) /schwab/status target route registered in app.routes (Phase 6 I3).
# ---------------------------------------------------------------------------

def test_config_nav_link_target_route_registered(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 3 (Phase 6 I3 inheritance) — the /schwab/status link target
    MUST resolve in app.routes. TestClient verifies link href text but
    does NOT follow; a typo or missing route registration would silently
    404 the operator's browser click.

    Defense complements T-2.1 test 1 (route-registration check) by
    tying the navigation surface to the route registration via a single
    discriminating test."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    app = create_app(cfg, cfg_path)
    assert any(
        getattr(r, "path", None) == "/schwab/status" for r in app.routes
    ), (
        "/schwab/status nav-link target NOT in app.routes; T-2.3 link "
        "would 404 the operator"
    )
