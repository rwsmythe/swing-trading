"""Phase 9 Codex R2 Major #1 fix — `swing config reset` cascades to risk_policy.

After T-A.5 cfg-cascade lands a divergent risk_equity_floor in user-config
.toml + risk_policy, calling `swing config reset account.risk_equity_floor`
deletes the override and falls back to tracked TOML's value. Without a
reset cascade, risk_policy stays at the cascaded value while cfg falls
back — recreating divergence the cascade was supposed to close.
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
def cfg_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    return _minimal_config(project, home)


@pytest.fixture
def migrated_cfg(cfg_path: Path):
    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    assert result.exit_code == 0, result.output
    return load_cfg(cfg_path)


def test_config_reset_risk_equity_floor_cascades_back_to_tracked(
    cfg_path: Path, migrated_cfg,
) -> None:
    """Set + Reset round-trip: cfg-set 8500 → cascade to policy 8500. Then
    reset → policy should fall BACK to tracked TOML's 7500.0."""
    runner = CliRunner()
    # Step 1: set to 8500 (cascades to policy_id=2 with capital_floor=8500).
    result = runner.invoke(
        main, [
            "--config", str(cfg_path),
            "config", "set",
            "account.risk_equity_floor", "8500.0",
            "--force",
        ],
    )
    assert result.exit_code == 0, result.output
    conn = sqlite3.connect(migrated_cfg.paths.db_path)
    try:
        active = get_active_policy(conn)
        assert active.capital_floor_constant_dollars == 8500.0
    finally:
        conn.close()

    # Step 2: reset (deletes override; should cascade to policy back to
    # tracked TOML's 7500.0).
    result = runner.invoke(
        main, [
            "--config", str(cfg_path),
            "config", "reset",
            "account.risk_equity_floor",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Cascaded reset to risk_policy" in result.output

    conn = sqlite3.connect(migrated_cfg.paths.db_path)
    try:
        active = get_active_policy(conn)
        assert active.capital_floor_constant_dollars == 7500.0
    finally:
        conn.close()


def test_config_reset_chase_factor_does_not_cascade(
    cfg_path: Path, migrated_cfg,
) -> None:
    """`web.chase_factor` has no policy mirror → no reset cascade."""
    runner = CliRunner()
    # Set to non-default first so reset has something to delete.
    result = runner.invoke(
        main, [
            "--config", str(cfg_path),
            "config", "set",
            "web.chase_factor", "0.02",
            "--force",
        ],
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(
        main, [
            "--config", str(cfg_path),
            "config", "reset",
            "web.chase_factor",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Cascaded reset to risk_policy" not in result.output

    conn = sqlite3.connect(migrated_cfg.paths.db_path)
    try:
        n = conn.execute("SELECT COUNT(*) FROM risk_policy").fetchone()[0]
        # Only the seed (no cascades fired since chase_factor isn't a mirror).
        assert n == 1
    finally:
        conn.close()
