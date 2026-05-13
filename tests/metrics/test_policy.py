"""Phase 10 Sub-bundle A T-A.2 — risk_policy LIVE vs AT-TRADE-TIME resolver tests."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.risk_policy import get_active_policy
from swing.metrics.policy import (
    get_review_policy_id_stamp,
    get_trade_policy_id_stamp,
    read_at_review_time_policy,
    read_at_trade_time_policy,
    read_live_policy,
)
from swing.trades.risk_policy import supersede_active_policy


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "phase10_policy.db")


# ---------------------------------------------------------------------------
# read_live_policy
# ---------------------------------------------------------------------------

def test_read_live_policy_returns_active(conn: sqlite3.Connection):
    """Seed has policy_id=1 active; supersede creates policy_id=2 active +
    deactivates 1. read_live_policy returns 2."""
    new_id = supersede_active_policy(
        conn,
        field_updates={"max_account_risk_per_trade_pct": 0.75},
        notes="test",
    )
    assert new_id == 2

    live = read_live_policy(conn)
    assert live.policy_id == 2
    assert live.is_active == 1


def test_read_live_policy_matches_repo_helper(conn: sqlite3.Connection):
    """read_live_policy is a thin wrapper over get_active_policy."""
    via_metrics = read_live_policy(conn)
    via_repo = get_active_policy(conn)
    assert via_metrics == via_repo


# ---------------------------------------------------------------------------
# read_at_trade_time_policy
# ---------------------------------------------------------------------------

def test_read_at_trade_time_uses_stamp(conn: sqlite3.Connection):
    """When stamp resolves, return that exact policy + bool=False."""
    supersede_active_policy(
        conn,
        field_updates={"max_account_risk_per_trade_pct": 0.75},
        notes="successor",
    )
    # policy_id=1 is now superseded but still exists; stamp resolves to it.
    policy, fallback = read_at_trade_time_policy(conn, policy_id_stamp=1)
    assert policy.policy_id == 1
    assert policy.is_active == 0
    assert fallback is False


def test_read_at_trade_time_falls_back_for_null(conn: sqlite3.Connection):
    """NULL stamp → LIVE policy + bool=True (legacy pre-Phase-9 trade)."""
    policy, fallback = read_at_trade_time_policy(conn, policy_id_stamp=None)
    assert policy.is_active == 1
    assert fallback is True


def test_read_at_trade_time_falls_back_for_orphaned_id(conn: sqlite3.Connection):
    """Nonexistent stamp → LIVE policy + bool=True (defensive)."""
    policy, fallback = read_at_trade_time_policy(conn, policy_id_stamp=999)
    assert policy.is_active == 1
    assert fallback is True


def test_read_at_trade_time_stamp_to_active_policy_returns_no_fallback(
    conn: sqlite3.Connection,
):
    """Stamp pointing at the LIVE policy resolves cleanly without fallback flag."""
    policy, fallback = read_at_trade_time_policy(conn, policy_id_stamp=1)
    assert policy.policy_id == 1
    assert policy.is_active == 1
    assert fallback is False


# ---------------------------------------------------------------------------
# read_at_review_time_policy (mirrors read_at_trade_time_policy)
# ---------------------------------------------------------------------------

def test_read_at_review_time_falls_back_for_null(conn: sqlite3.Connection):
    """NULL stamp on review_log → LIVE + bool=True."""
    policy, fallback = read_at_review_time_policy(conn, policy_id_stamp=None)
    assert policy.is_active == 1
    assert fallback is True


def test_read_at_review_time_uses_stamp(conn: sqlite3.Connection):
    """Stamp present on review_log → that exact policy + bool=False."""
    supersede_active_policy(
        conn,
        field_updates={"max_account_risk_per_trade_pct": 0.75},
        notes="successor",
    )
    policy, fallback = read_at_review_time_policy(conn, policy_id_stamp=1)
    assert policy.policy_id == 1
    assert fallback is False


# ---------------------------------------------------------------------------
# get_trade_policy_id_stamp / get_review_policy_id_stamp
# ---------------------------------------------------------------------------

def _seed_minimal_trade(
    conn: sqlite3.Connection, *, trade_id: int, stamp: int | None,
) -> None:
    """Insert a row into trades using only the NOT-NULL columns; stamp
    risk_policy_id_at_lock to ``stamp`` (or NULL)."""
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "hypothesis_label, risk_policy_id_at_lock) "
        "VALUES (?, 'TEST', '2026-05-12', 10.0, 100, 9.0, 9.0, "
        "'entered', 'Sector', 'Industry', 'manual_off_pipeline', "
        "'2026-05-12T09:00:00.000', 100, 'test-cohort', ?)",
        (trade_id, stamp),
    )
    conn.commit()


def test_get_trade_policy_id_stamp_reads_column(conn: sqlite3.Connection):
    _seed_minimal_trade(conn, trade_id=1, stamp=1)
    assert get_trade_policy_id_stamp(conn, trade_id=1) == 1


def test_get_trade_policy_id_stamp_returns_none_for_null_column(
    conn: sqlite3.Connection,
):
    _seed_minimal_trade(conn, trade_id=2, stamp=None)
    assert get_trade_policy_id_stamp(conn, trade_id=2) is None


def test_get_trade_policy_id_stamp_returns_none_for_missing_trade(
    conn: sqlite3.Connection,
):
    """Missing trade_id → None (caller should pre-validate)."""
    assert get_trade_policy_id_stamp(conn, trade_id=999) is None


def test_get_review_policy_id_stamp_returns_none_for_missing_review(
    conn: sqlite3.Connection,
):
    """Missing review_id → None."""
    assert get_review_policy_id_stamp(conn, review_id=999) is None
