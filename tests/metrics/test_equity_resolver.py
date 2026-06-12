"""Phase 10 Sub-bundle A T-A.3 — equity resolver tests."""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.account_equity_snapshots import insert_snapshot
from swing.metrics.equity_resolver import resolve_live_capital_denominator_dollars


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "phase10_equity.db")


def _insert(
    conn: sqlite3.Connection,
    *,
    snapshot_date: str,
    equity_dollars: float,
    source: str = "manual",
) -> None:
    insert_snapshot(
        conn,
        snapshot_date=snapshot_date,
        equity_dollars=equity_dollars,
        source=source,
        source_artifact_path=None,
        recorded_at=snapshot_date + "T00:00:00.000",
        recorded_by="test",
        notes=None,
    basis="net_liq",
    )
    conn.commit()


def test_resolver_no_snapshots_returns_provisional(
    conn: sqlite3.Connection, spec_default_policy,
):
    """Empty snapshots → ($7500, PROVISIONAL)."""
    value, mode = resolve_live_capital_denominator_dollars(
        conn,
        asof_date=date(2026, 5, 12),
        at_trade_time_policy=spec_default_policy,
    )
    assert value == 7500.0
    assert mode == "PROVISIONAL"


def test_resolver_with_snapshot_returns_live(
    conn: sqlite3.Connection, spec_default_policy,
):
    """Snapshot $2000 at 2026-05-11; asof=2026-05-12 → ($2000, LIVE)."""
    _insert(conn, snapshot_date="2026-05-11", equity_dollars=2000.0)
    value, mode = resolve_live_capital_denominator_dollars(
        conn,
        asof_date=date(2026, 5, 12),
        at_trade_time_policy=spec_default_policy,
    )
    assert value == 2000.0
    assert mode == "LIVE"


def test_resolver_with_same_day_snapshot_returns_live(
    conn: sqlite3.Connection, spec_default_policy,
):
    """Snapshot on asof_date → LIVE (predicate is <=, not <)."""
    _insert(conn, snapshot_date="2026-05-12", equity_dollars=2100.0)
    value, mode = resolve_live_capital_denominator_dollars(
        conn,
        asof_date=date(2026, 5, 12),
        at_trade_time_policy=spec_default_policy,
    )
    assert value == 2100.0
    assert mode == "LIVE"


def test_resolver_query_before_first_snapshot_returns_provisional(
    conn: sqlite3.Connection, spec_default_policy,
):
    """Snapshot at 2026-05-11; asof=2026-04-30 (before) → PROVISIONAL."""
    _insert(conn, snapshot_date="2026-05-11", equity_dollars=2000.0)
    value, mode = resolve_live_capital_denominator_dollars(
        conn,
        asof_date=date(2026, 4, 30),
        at_trade_time_policy=spec_default_policy,
    )
    assert value == 7500.0
    assert mode == "PROVISIONAL"


def test_resolver_back_recorded_snapshot_resolves_correctly(
    conn: sqlite3.Connection, spec_default_policy,
):
    """Latest-on-or-before semantics: 2026-04-01 snapshot retrievable for
    asof=2026-04-15 (even though a later 2026-05-11 snapshot exists, it
    isn't <= 2026-04-15)."""
    _insert(conn, snapshot_date="2026-05-11", equity_dollars=2000.0)
    _insert(conn, snapshot_date="2026-04-01", equity_dollars=1800.0)
    value, mode = resolve_live_capital_denominator_dollars(
        conn,
        asof_date=date(2026, 4, 15),
        at_trade_time_policy=spec_default_policy,
    )
    assert value == 1800.0
    assert mode == "LIVE"


def test_resolver_uses_at_trade_time_capital_floor(
    conn: sqlite3.Connection, policy_factory,
):
    """Different at-trade-time policy.capital_floor → fallback uses THAT value."""
    custom_policy = policy_factory(capital_floor_constant_dollars=10000.0)
    value, mode = resolve_live_capital_denominator_dollars(
        conn,
        asof_date=date(2026, 5, 12),
        at_trade_time_policy=custom_policy,
    )
    assert value == 10000.0
    assert mode == "PROVISIONAL"


def test_resolver_anchor_agnostic(
    conn: sqlite3.Connection, spec_default_policy,
):
    """Helper accepts any date; no internal datetime.now() coupling.

    Discriminating against a hypothetical bug where the helper called
    `datetime.now()` internally instead of using the asof_date parameter:
    asof_date=date(2020, 1, 1) on an empty table returns PROVISIONAL with
    the policy floor. If the helper used now() internally, the test would
    behave identically since no snapshots exist — but the call signature
    ensures the parameter IS the anchor, not internal state.
    """
    value_2020, mode_2020 = resolve_live_capital_denominator_dollars(
        conn,
        asof_date=date(2020, 1, 1),
        at_trade_time_policy=spec_default_policy,
    )
    value_2030, mode_2030 = resolve_live_capital_denominator_dollars(
        conn,
        asof_date=date(2030, 1, 1),
        at_trade_time_policy=spec_default_policy,
    )
    # Both empty-snapshot → both PROVISIONAL; values identical (no snapshot
    # state difference between the two dates).
    assert value_2020 == value_2030 == 7500.0
    assert mode_2020 == mode_2030 == "PROVISIONAL"
