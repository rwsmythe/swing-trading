"""Phase 9 Codex R1 Major #4 fix — `swing config set` cascades to risk_policy.

The legacy `swing config set` CLI writes to user-config.toml. When the field
has a risk_policy mirror counterpart (per spec §3.1.3), the CLI MUST also
supersede the active risk_policy with the new value, mirroring the web
config_save cascade in T-A.5.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from swing.config import load as load_cfg
from swing.data.repos.risk_policy import get_active_policy
from tests.cli.test_cli_eval import _minimal_config


@pytest.fixture
def cfg_path(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    return _minimal_config(project, home)


@pytest.fixture
def migrated_cfg(cfg_path: Path):
    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    assert result.exit_code == 0, result.output
    return load_cfg(cfg_path)


def test_config_set_risk_equity_floor_cascades_to_risk_policy(
    cfg_path: Path, migrated_cfg,
) -> None:
    """`swing config set account.risk_equity_floor 8500.0` updates BOTH
    user-config.toml AND risk_policy."""
    runner = CliRunner()
    result = runner.invoke(
        main, [
            "--config", str(cfg_path),
            "config", "set",
            "account.risk_equity_floor", "8500.0",
            "--force",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Cascaded to risk_policy" in result.output

    conn = sqlite3.connect(migrated_cfg.paths.db_path)
    try:
        active = get_active_policy(conn)
        assert active.capital_floor_constant_dollars == 8500.0
    finally:
        conn.close()


def test_config_set_chase_factor_does_not_cascade(
    cfg_path: Path, migrated_cfg,
) -> None:
    """`web.chase_factor` has no risk_policy counterpart — no cascade."""
    runner = CliRunner()
    result = runner.invoke(
        main, [
            "--config", str(cfg_path),
            "config", "set",
            "web.chase_factor", "0.02",
            "--force",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Cascaded to risk_policy" not in result.output

    conn = sqlite3.connect(migrated_cfg.paths.db_path)
    try:
        n = conn.execute("SELECT COUNT(*) FROM risk_policy").fetchone()[0]
        assert n == 1
    finally:
        conn.close()
