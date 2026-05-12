"""Phase 9 Codex R3 Major #3 fix — reset / set cascades skip no-op cases.

Avoid polluting the audit chain with no-op supersessions when:
  - operator runs `swing config reset` on a field whose user-config
    override didn't exist OR whose value matches the active policy;
  - operator runs `swing config set` on a field with the value that
    already matches the active policy.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from swing.config import load as load_cfg
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


def _policy_count(db_path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM risk_policy").fetchone()[0]
    finally:
        conn.close()


def test_reset_with_no_existing_override_does_not_pollute_audit(
    cfg_path: Path, migrated_cfg,
) -> None:
    """Operator clicks reset on a field that has no user-config override
    AND whose tracked value matches the active policy — cascade skipped,
    no new policy_id created."""
    n_before = _policy_count(migrated_cfg.paths.db_path)
    runner = CliRunner()
    result = runner.invoke(
        main, [
            "--config", str(cfg_path),
            "config", "reset", "account.risk_equity_floor",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Cascaded reset" not in result.output
    assert _policy_count(migrated_cfg.paths.db_path) == n_before


def test_set_to_existing_active_value_does_not_pollute_audit(
    cfg_path: Path, migrated_cfg,
) -> None:
    """Operator runs `swing config set account.risk_equity_floor 7500.0`
    when the active policy already has 7500.0 — override is written but
    no risk_policy supersession (no-op cascade skipped)."""
    n_before = _policy_count(migrated_cfg.paths.db_path)
    runner = CliRunner()
    result = runner.invoke(
        main, [
            "--config", str(cfg_path),
            "config", "set",
            "account.risk_equity_floor", "7500.0",
            "--force",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Cascaded to risk_policy" not in result.output
    assert _policy_count(migrated_cfg.paths.db_path) == n_before
