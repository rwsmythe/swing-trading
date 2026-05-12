"""Phase 9 Codex R3 Major #1 fix — `import-from-toml` covers all 4 mirrored fields.

The db_migrate ratification covers 4 spec §3.1.3 SEED MAP fields. After a
ratification failure (R2 M#3 surfacing), the operator's recovery path is
`swing config policy import-from-toml --field <name>` — that command MUST
support all 4 fields, not just capital_floor_constant_dollars.
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


def test_import_max_concurrent_positions(cfg_path: Path, migrated_cfg) -> None:
    """Hand-edit cfg.position_limits.hard_cap_open + import-from-toml."""
    text = cfg_path.read_text(encoding="utf-8")
    text = text.replace("hard_cap_open = 6", "hard_cap_open = 4")
    cfg_path.write_text(text, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        main, [
            "--config", str(cfg_path),
            "config", "policy", "import-from-toml",
            "--field", "max_concurrent_positions",
        ],
    )
    assert result.exit_code == 0, result.output

    conn = sqlite3.connect(migrated_cfg.paths.db_path)
    try:
        active = get_active_policy(conn)
        assert active.max_concurrent_positions == 4
    finally:
        conn.close()


def test_import_max_account_risk_pct_applies_x100_transform(
    cfg_path: Path, migrated_cfg,
) -> None:
    """cfg.risk.max_risk_pct is fraction (0.0075); spec form is percent
    (0.75). Import multiplies by 100 at the boundary."""
    text = cfg_path.read_text(encoding="utf-8")
    text = text.replace("max_risk_pct = 0.005", "max_risk_pct = 0.0075")
    cfg_path.write_text(text, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        main, [
            "--config", str(cfg_path),
            "config", "policy", "import-from-toml",
            "--field", "max_account_risk_per_trade_pct",
        ],
    )
    assert result.exit_code == 0, result.output

    conn = sqlite3.connect(migrated_cfg.paths.db_path)
    try:
        active = get_active_policy(conn)
        assert active.max_account_risk_per_trade_pct == pytest.approx(0.75)
    finally:
        conn.close()


def test_import_review_lag_threshold_days(cfg_path: Path, migrated_cfg) -> None:
    """cfg.review.review_window_days is the cfg counterpart for
    risk_policy.review_lag_threshold_days."""
    text = cfg_path.read_text(encoding="utf-8")
    # _minimal_config doesn't include [review] section; cfg uses default
    # ReviewConfig.review_window_days=7. Append a divergent override.
    text += "\n[review]\nreview_window_days = 14\n"
    cfg_path.write_text(text, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        main, [
            "--config", str(cfg_path),
            "config", "policy", "import-from-toml",
            "--field", "review_lag_threshold_days",
        ],
    )
    assert result.exit_code == 0, result.output

    conn = sqlite3.connect(migrated_cfg.paths.db_path)
    try:
        active = get_active_policy(conn)
        assert active.review_lag_threshold_days == 14
    finally:
        conn.close()


def test_import_capital_floor_still_works_post_extension(
    cfg_path: Path, migrated_cfg,
) -> None:
    """Regression — extending the map didn't break the pre-existing field."""
    text = cfg_path.read_text(encoding="utf-8")
    text = text.replace("risk_equity_floor = 7500.0", "risk_equity_floor = 8000.0")
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
        assert active.capital_floor_constant_dollars == 8000.0
    finally:
        conn.close()
