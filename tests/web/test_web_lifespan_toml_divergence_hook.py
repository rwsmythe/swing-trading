"""Phase 9 T-A.5 — web app post-ensure_schema TOML divergence hook.

Per Codex R3 M#1 architectural fix (plan §A.5.1): the web app startup
invokes check_and_reconcile_toml_divergence(conn, cfg) AFTER ensure_schema
has brought the DB to v17, sets app.state.cfg to the corrected immutable
Config when divergence is detected.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import load as load_cfg
from swing.data.db import ensure_schema
from swing.web.app import create_app
from swing.web.cli_cmd import run_server  # noqa: F401  -- import surface check
from tests.cli.test_cli_eval import _minimal_config


@pytest.fixture
def divergent_setup(tmp_path: Path):
    """Build a v17 DB whose risk_policy.capital_floor_constant_dollars (7500)
    diverges from cfg.account.risk_equity_floor (5000)."""
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    # First, migrate to v17 with risk_equity_floor=7500 (matches seed).
    cfg = load_cfg(cfg_path)
    ensure_schema(cfg.paths.db_path).close()

    # Now flip the TOML to 5000 (introduces divergence).
    text = cfg_path.read_text(encoding="utf-8")
    text = text.replace(
        "risk_equity_floor = 7500.0",
        "risk_equity_floor = 5000.0",
    )
    cfg_path.write_text(text, encoding="utf-8")
    cfg = load_cfg(cfg_path)
    return cfg, cfg_path


def test_create_app_applies_divergence_correction_to_app_state_cfg(
    divergent_setup,
):
    """create_app sets app.state.cfg to the corrected Config (TOML 5000 →
    risk_policy 7500)."""
    cfg, cfg_path = divergent_setup
    # Pre-condition: cfg loaded from TOML has the divergent value.
    assert cfg.account.risk_equity_floor == 5000.0

    app = create_app(cfg, cfg_path)
    with TestClient(app):
        # app.state.cfg should now reflect the policy value, NOT the TOML.
        assert app.state.cfg.account.risk_equity_floor == 7500.0


def test_create_app_no_divergence_keeps_cfg_unchanged(tmp_path: Path):
    """When TOML matches risk_policy, app.state.cfg is the original cfg."""
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load_cfg(cfg_path)
    ensure_schema(cfg.paths.db_path).close()

    app = create_app(cfg, cfg_path)
    with TestClient(app):
        assert app.state.cfg.account.risk_equity_floor == 7500.0
        # Identity preserved when no divergence.
        assert app.state.cfg is cfg


def test_create_app_pre_v17_db_no_crash(tmp_path: Path):
    """If the DB file is pre-v17 (test fixture skipping ensure_schema), the
    web app startup hook silently returns (cfg, None) — no crash, no
    correction. (Defensive — production never hits this because run_server
    calls connect() first which enforces schema-version match.)"""
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load_cfg(cfg_path)
    # Create an empty DB file (no schema_version table).
    cfg.paths.db_path.parent.mkdir(parents=True, exist_ok=True)
    sqlite3.connect(cfg.paths.db_path).close()

    app = create_app(cfg, cfg_path)
    with TestClient(app):
        # app.state.cfg unchanged (silent skip).
        assert app.state.cfg.account.risk_equity_floor == 7500.0
