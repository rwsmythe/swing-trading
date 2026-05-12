"""Phase 9 Codex R1 Major #3 fix — visible TOML divergence banner on /config.

Spec §3.1.3 R3 Minor #2: when cfg.account.risk_equity_floor differs from
risk_policy.capital_floor_constant_dollars, the Phase 5 config page MUST
render a yellow-banner warning until the operator resolves the divergence
via swing config policy import-from-toml.

ALSO covers the round-trip Major #2 accept-with-rationale: the T-A.5
cfg-cascade keeps user-config.toml in sync with risk_policy, so
apply_overrides + the divergence-banner stay consistent in the canonical
flow. Hand-edit user-config.toml divergence is V2 hardening.
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
def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    # Isolate user-config.toml reads from the operator's real home dir —
    # otherwise prior tests / the operator's actual user-config.toml leaks
    # divergent values into our fixture (test pollution).
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    cfg_path = _minimal_config(project, home)
    cfg = load_cfg(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg, cfg_path


def test_no_banner_when_cfg_matches_policy(setup):
    cfg, cfg_path = setup
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/config")
    assert resp.status_code == 200
    assert "TOML divergence" not in resp.text


def test_banner_renders_when_user_config_diverges_from_policy(setup):
    """Hand-edit divergence path: user-config.toml's risk_equity_floor diverges
    from policy's capital_floor_constant_dollars — banner renders."""
    cfg, cfg_path = setup
    # Hand-edit user-config.toml to diverge.
    user_overrides_path = cfg.paths.data_dir / "user-config.toml"
    user_overrides_path.parent.mkdir(parents=True, exist_ok=True)
    user_overrides_path.write_text(
        "[account]\nrisk_equity_floor = 5000.0\n", encoding="utf-8",
    )

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/config")
    assert resp.status_code == 200
    assert "TOML divergence" in resp.text
    assert "5000.0" in resp.text
    assert "7500.0" in resp.text


def test_t_a_5_cfg_cascade_keeps_user_config_in_sync_with_policy(setup):
    """Codex R1 Major #2 accept-with-rationale round-trip test: when the
    Phase 5 config_save POST changes risk_equity_floor, user-config.toml
    AND risk_policy are updated together. apply_overrides on the next
    request reads the synced value; no divergence banner."""
    cfg, cfg_path = setup
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        payload = {
            "account.risk_equity_floor": "8500.0",
            "web.chase_factor": str(cfg.web.chase_factor),
            "pipeline.chart_top_n_watch": "1",
            "force": "true",
        }
        resp = client.post(
            "/config", data=payload, headers={"HX-Request": "true"},
        )
        assert resp.status_code in (204, 303)

        # risk_policy + user-config.toml are now both at 8500.0.
        conn = sqlite3.connect(cfg.paths.db_path)
        try:
            active = get_active_policy(conn)
        finally:
            conn.close()
        assert active.capital_floor_constant_dollars == 8500.0

        # Re-render /config: no divergence banner because both sides agree.
        resp = client.get("/config")
        assert resp.status_code == 200
        assert "TOML divergence" not in resp.text
