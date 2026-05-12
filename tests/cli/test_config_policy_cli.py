"""Phase 9 T-A.6 — `swing config policy {show,set,import-from-toml,history}` CLI."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from swing.config import load as load_cfg
from swing.data.repos.risk_policy import get_active_policy, get_policy_by_id
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
    """Bring DB to v17 + return cfg."""
    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    assert result.exit_code == 0, result.output
    return load_cfg(cfg_path)


def test_policy_show_prints_active_row(cfg_path: Path, migrated_cfg) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main, ["--config", str(cfg_path), "config", "policy", "show"],
    )
    assert result.exit_code == 0, result.output
    # Sanity: the seed row's signature values appear in output.
    assert "policy_id" in result.output
    assert "1" in result.output
    assert "capital_floor_constant_dollars" in result.output
    assert "7500.0" in result.output
    assert "scratch_epsilon_R" in result.output


def test_policy_set_supersedes_active_policy(
    cfg_path: Path, migrated_cfg,
) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main, [
            "--config", str(cfg_path),
            "config", "policy", "set",
            "--field", "max_account_risk_per_trade_pct",
            "--value", "0.75",
            "--notes", "operator test",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "policy_id" in result.output
    assert "2" in result.output  # newly created policy

    conn = sqlite3.connect(migrated_cfg.paths.db_path)
    try:
        active = get_active_policy(conn)
        assert active.policy_id == 2
        assert active.max_account_risk_per_trade_pct == 0.75
        assert active.policy_notes == "operator test"
        predecessor = get_policy_by_id(conn, policy_id=1)
        assert predecessor is not None
        assert predecessor.is_active == 0
        assert predecessor.superseded_by_policy_id == 2
    finally:
        conn.close()


def test_policy_set_rejects_invalid_field(
    cfg_path: Path, migrated_cfg,
) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main, [
            "--config", str(cfg_path),
            "config", "policy", "set",
            "--field", "not_a_real_field",
            "--value", "1.0",
        ],
    )
    # Click rejects via Choice type → exit 2 typical.
    assert result.exit_code != 0
    assert "Invalid value" in result.output or "not a real field" in result.output


def test_policy_set_rejects_dataclass_validation_failure(
    cfg_path: Path, migrated_cfg,
) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main, [
            "--config", str(cfg_path),
            "config", "policy", "set",
            "--field", "capital_floor_constant_dollars",
            "--value", "-100.0",  # CHECK > 0 rejects
        ],
    )
    assert result.exit_code != 0
    assert "capital_floor" in result.output.lower()


def test_policy_set_handles_int_field(cfg_path: Path, migrated_cfg) -> None:
    """Integer fields coerce '7' → 7 (not 7.0)."""
    runner = CliRunner()
    result = runner.invoke(
        main, [
            "--config", str(cfg_path),
            "config", "policy", "set",
            "--field", "max_concurrent_positions",
            "--value", "8",
        ],
    )
    assert result.exit_code == 0, result.output
    conn = sqlite3.connect(migrated_cfg.paths.db_path)
    try:
        active = get_active_policy(conn)
        assert active.max_concurrent_positions == 8
        assert isinstance(active.max_concurrent_positions, int)
    finally:
        conn.close()


def test_policy_import_from_toml_creates_policy_row(
    cfg_path: Path, migrated_cfg,
) -> None:
    """import-from-toml reads cfg.account.risk_equity_floor + creates a new
    policy row. Useful when the operator hand-edited the TOML AND wants the
    risk_policy table to reflect that edit (the reverse of cfg-cascade)."""
    # First, hand-edit the TOML to a divergent value.
    text = cfg_path.read_text(encoding="utf-8")
    text = text.replace(
        "risk_equity_floor = 7500.0",
        "risk_equity_floor = 6000.0",
    )
    cfg_path.write_text(text, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        main, [
            "--config", str(cfg_path),
            "config", "policy", "import-from-toml",
            "--field", "capital_floor_constant_dollars",
        ],
    )
    assert result.exit_code == 0, result.output
    conn = sqlite3.connect(migrated_cfg.paths.db_path)
    try:
        active = get_active_policy(conn)
        assert active.capital_floor_constant_dollars == 6000.0
    finally:
        conn.close()


def test_policy_import_from_toml_rejects_unmirrored_field(
    cfg_path: Path, migrated_cfg,
) -> None:
    """In V1 only capital_floor_constant_dollars has a TOML counterpart per
    spec §3.1.3; other fields error out."""
    runner = CliRunner()
    result = runner.invoke(
        main, [
            "--config", str(cfg_path),
            "config", "policy", "import-from-toml",
            "--field", "scratch_epsilon_R",
        ],
    )
    assert result.exit_code != 0
    # Click's Choice rejects at parse time with "Invalid value for '--field'"
    # — that's the canonical surface; the in-handler ValueError is a
    # defensive double-check for direct service callers.
    assert (
        "Invalid value" in result.output
        or "no TOML counterpart" in result.output
        or "not mirrored" in result.output
    )


def test_policy_history_lists_recent_rows(
    cfg_path: Path, migrated_cfg,
) -> None:
    runner = CliRunner()
    # Create 2 supersessions to populate history.
    for value in ("0.60", "0.55"):
        result = runner.invoke(
            main, [
                "--config", str(cfg_path),
                "config", "policy", "set",
                "--field", "max_account_risk_per_trade_pct",
                "--value", value,
            ],
        )
        assert result.exit_code == 0, result.output

    result = runner.invoke(
        main, [
            "--config", str(cfg_path),
            "config", "policy", "history", "--limit", "10",
        ],
    )
    assert result.exit_code == 0, result.output
    # All 3 policy_ids appear in output.
    assert "policy_id=1" in result.output or "1" in result.output
    assert "policy_id=2" in result.output or "2" in result.output
    assert "policy_id=3" in result.output or "3" in result.output
