"""Phase 14 close-out (A-7): topbar render of the Schwab checker badge.

These are the UNSEEDED/default-state witnesses (the regression the SB5.5 seeded
gate missed, per feedback_seeded_gate_masks_default_state): a production + ladder
app with NO constructible Schwab client installs no checker and writes no
sidecar, yet the topbar must still surface the UNKNOWN (Schwab?, warn) badge so a
silent checker failure is visible. Real Config + real create_app render.
"""
from __future__ import annotations

import dataclasses

from fastapi.testclient import TestClient

from swing.web.app import create_app


def _with_schwab(base_cfg, *, environment: str, marketdata_ladder_enabled: bool):
    schwab = dataclasses.replace(
        base_cfg.integrations.schwab,
        environment=environment,
        marketdata_ladder_enabled=marketdata_ladder_enabled,
    )
    integ = dataclasses.replace(base_cfg.integrations, schwab=schwab)
    return dataclasses.replace(base_cfg, integrations=integ)


def test_topbar_shows_unknown_badge_unseeded(monkeypatch, tmp_path, seeded_db):
    # UNSEEDED precondition: production + ladder enabled, isolated HOME with NO
    # pre-existing sidecar, AND no constructible Schwab client, so the lifespan
    # installs NO checker and writes NO sidecar at startup.
    cfg, cfg_path = seeded_db
    cfg = _with_schwab(cfg, environment="production", marketdata_ladder_enabled=True)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    import swing.web.app as web_app
    monkeypatch.setattr(web_app, "_construct_web_schwab_client", lambda cfg: None)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.text
        assert "schwab-health-badge--warn" in body
        assert "Schwab?" in body
    # No sidecar was created by the lifespan before the first rendered request.
    from swing.integrations.schwab.checker_resilience import (
        checker_liveness_sidecar_path,
    )
    assert not checker_liveness_sidecar_path("production").exists()


def test_topbar_hides_badge_in_sandbox(monkeypatch, tmp_path, seeded_db):
    cfg, cfg_path = seeded_db
    cfg = _with_schwab(cfg, environment="sandbox", marketdata_ladder_enabled=True)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "schwab-health-badge" not in resp.text


def test_topbar_hides_badge_when_ladder_disabled(monkeypatch, tmp_path, seeded_db):
    cfg, cfg_path = seeded_db
    cfg = _with_schwab(
        cfg, environment="production", marketdata_ladder_enabled=False,
    )
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "schwab-health-badge" not in resp.text
