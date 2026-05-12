"""Phase 9 T-A.5 — Phase 5 config-page POST cascades risk_equity_floor edit
to a new risk_policy row via supersede_active_policy(source='cfg_cascade').
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import load as load_cfg
from swing.data.db import ensure_schema
from swing.data.repos.risk_policy import get_active_policy
from swing.web.app import create_app
from tests.cli.test_cli_eval import _minimal_config


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    cfg = load_cfg(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        yield client, cfg, cfg_path


def _post_form(client, payload, *, hx: bool = True):
    headers = {}
    if hx:
        headers["HX-Request"] = "true"
    return client.post("/config", data=payload, headers=headers)


def _form_payload(cfg, **overrides):
    """Build a config-page POST payload from the loaded cfg."""
    payload = {
        "account.risk_equity_floor": str(cfg.account.risk_equity_floor),
        "web.chase_factor": str(cfg.web.chase_factor),
        "pipeline.chart_top_n_watch": "1",  # safe default; field may exist
    }
    # Some fields may not be in FIELD_REGISTRY; the POST handler reads only
    # paths in FIELD_REGISTRY so extras are harmless.
    payload.update(overrides)
    return payload


def test_config_post_cascades_risk_equity_floor_change_to_new_policy(
    app_client,
):
    """Editing cfg.account.risk_equity_floor creates a new risk_policy row
    via supersede_active_policy(source='cfg_cascade')."""
    client, cfg, cfg_path = app_client

    # Confirm starting policy.
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        starting = get_active_policy(conn)
        assert starting.policy_id == 1
        assert starting.capital_floor_constant_dollars == 7500.0
    finally:
        conn.close()

    # Submit form with risk_equity_floor flipped to 8500.
    payload = _form_payload(cfg, **{"account.risk_equity_floor": "8500.0"})
    payload["force"] = "true"  # accept any soft warnings
    resp = _post_form(client, payload)
    # HTMX success-path: 204 + HX-Redirect (per Phase 5 R1 M2 lesson).
    assert resp.status_code in (204, 303), resp.text

    # New policy row created with cfg_cascade note.
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        active = get_active_policy(conn)
        assert active.policy_id == 2
        assert active.capital_floor_constant_dollars == 8500.0
        assert active.policy_notes == (
            "auto-cascade from cfg.account.risk_equity_floor edit"
        )
    finally:
        conn.close()


def test_config_post_does_not_cascade_when_risk_equity_floor_unchanged(
    app_client,
):
    """Submitting the form with risk_equity_floor unchanged does NOT create
    a new policy row — invariant (a) of the MERGE-semantics write."""
    client, cfg, _cfg_path = app_client

    # Submit form with everything unchanged.
    payload = _form_payload(cfg)
    payload["force"] = "true"
    resp = _post_form(client, payload)
    assert resp.status_code in (204, 303)

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        n = conn.execute("SELECT COUNT(*) FROM risk_policy").fetchone()[0]
        assert n == 1
        active = get_active_policy(conn)
        assert active.policy_id == 1
    finally:
        conn.close()


def test_config_post_chase_factor_change_does_not_cascade(app_client):
    """Editing chase_factor (not a risk_policy field) does NOT create a new
    policy row."""
    client, cfg, _cfg_path = app_client

    payload = _form_payload(cfg, **{"web.chase_factor": "0.02"})
    payload["force"] = "true"
    resp = _post_form(client, payload)
    assert resp.status_code in (204, 303)

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        n = conn.execute("SELECT COUNT(*) FROM risk_policy").fetchone()[0]
        assert n == 1
    finally:
        conn.close()


def test_config_post_hx_redirect_success_response(app_client):
    """Phase 5 R1 M2 lesson preserved: HTMX POST responds with 204 +
    HX-Redirect, NOT a 303 swap-target."""
    client, cfg, _ = app_client
    payload = _form_payload(cfg, **{"account.risk_equity_floor": "8000.0"})
    payload["force"] = "true"
    resp = _post_form(client, payload, hx=True)
    assert resp.status_code == 204
    assert resp.headers.get("HX-Redirect", "").startswith("/config")
