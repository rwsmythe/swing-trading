"""Phase 9 Codex R1 Major #1 fix — post-migration cfg ratification.

Spec §3.1.3 SEED MAP requires four risk_policy fields to come from cfg
(max_account_risk_per_trade_pct = cfg.risk.max_risk_pct × 100,
max_concurrent_positions = cfg.position_limits.hard_cap_open,
capital_floor_constant_dollars = cfg.account.risk_equity_floor,
review_lag_threshold_days = cfg.review.review_window_days). The migration
0017 SQL cannot Python-eval cfg, so it hard-codes conservative defaults
matching the SHIPPED swing.config.toml.

When the operator's swing.config.toml differs from those defaults at the
v16 → v17 transition, ``ratify_seed_from_cfg_on_v17_landing`` supersedes
the migration's hard-coded seed with the operator's actual values.
"""
from __future__ import annotations

import dataclasses
import sqlite3
from pathlib import Path

import pytest

from swing.config import load as load_cfg
from swing.data.db import ensure_schema
from swing.data.repos.risk_policy import get_active_policy
from swing.trades.risk_policy import ratify_seed_from_cfg_on_v17_landing
from tests.cli.test_cli_eval import _minimal_config


@pytest.fixture
def cfg(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    return load_cfg(_minimal_config(project, home))


@pytest.fixture
def conn(cfg) -> sqlite3.Connection:
    return ensure_schema(cfg.paths.db_path)


def test_ratify_no_op_when_cfg_matches_seed(conn, cfg) -> None:
    """When all 4 mirrored fields match the migration's hard-coded seed,
    ratification returns None and active policy is unchanged."""
    starting = get_active_policy(conn)
    result = ratify_seed_from_cfg_on_v17_landing(conn, cfg)
    assert result is None
    after = get_active_policy(conn)
    assert after.policy_id == starting.policy_id


def test_ratify_supersedes_when_cfg_diverges_capital_floor(conn, cfg) -> None:
    """When cfg.account.risk_equity_floor differs from the seed's
    capital_floor_constant_dollars, ratification supersedes."""
    divergent = dataclasses.replace(
        cfg, account=dataclasses.replace(cfg.account, risk_equity_floor=8500.0),
    )
    new_id = ratify_seed_from_cfg_on_v17_landing(conn, divergent)
    assert new_id == 2
    active = get_active_policy(conn)
    assert active.policy_id == 2
    assert active.capital_floor_constant_dollars == 8500.0
    assert "auto-ratified" in (active.policy_notes or "")


def test_ratify_supersedes_when_cfg_diverges_max_concurrent_positions(
    conn, cfg,
) -> None:
    """When cfg.position_limits.hard_cap_open differs from the seed's
    max_concurrent_positions, ratification supersedes."""
    divergent = dataclasses.replace(
        cfg,
        position_limits=dataclasses.replace(
            cfg.position_limits, hard_cap_open=4,
        ),
    )
    new_id = ratify_seed_from_cfg_on_v17_landing(conn, divergent)
    assert new_id == 2
    active = get_active_policy(conn)
    assert active.max_concurrent_positions == 4


def test_ratify_supersedes_when_cfg_diverges_max_risk_pct(conn, cfg) -> None:
    """cfg.risk.max_risk_pct (decimal) maps to risk_policy
    .max_account_risk_per_trade_pct as cfg × 100. Operator's 0.0075 → 0.75."""
    divergent = dataclasses.replace(
        cfg, risk=dataclasses.replace(cfg.risk, max_risk_pct=0.0075),
    )
    new_id = ratify_seed_from_cfg_on_v17_landing(conn, divergent)
    assert new_id == 2
    active = get_active_policy(conn)
    assert active.max_account_risk_per_trade_pct == pytest.approx(0.75)
