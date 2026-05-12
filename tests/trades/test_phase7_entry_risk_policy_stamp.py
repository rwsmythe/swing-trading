"""Phase 9 T-A.7 — record_entry stamps trades.risk_policy_id_at_lock.

Spec §3.1.1 + plan T-A.7: at pre_trade_locked_at time, the entry service
stamps the trades row with the active risk_policy.policy_id. The stamp
preserves at-trade-time semantics for capital_floor / scratch_epsilon /
trail-MA periods even when the policy is later superseded.

Tests:
  - record_entry stamps the seed policy_id=1 at trade creation.
  - After supersede_active_policy, a NEW entry stamps the NEW policy_id.
  - Legacy trades pre-Phase-9 carry NULL stamp; read-path resolution
    falls back to current active policy (verified via direct INSERT
    bypassing the service to mimic legacy semantics).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import run_migrations
from swing.trades.entry import record_entry
from swing.trades.risk_policy import supersede_active_policy
from tests.trades.test_entry import _full_req, _seed_v14


@pytest.fixture
def conn(tmp_path: Path):
    """v17 DB (Phase 9 schema seeded with policy_id=1)."""
    import sqlite3
    db = tmp_path / "test.db"
    c = sqlite3.connect(db)
    run_migrations(c, target_version=17, backup_dir=tmp_path)
    return c


def _read_stamp(conn, trade_id: int):
    return conn.execute(
        "SELECT risk_policy_id_at_lock FROM trades WHERE id = ?",
        (trade_id,),
    ).fetchone()[0]


def test_record_entry_stamps_seed_policy_id(conn) -> None:
    """Fresh DB seed → policy_id=1 → entry stamps 1."""
    req = _full_req(ticker="STAMP1", entry_date="2026-05-11")
    result = record_entry(conn, req, soft_warn=10, hard_cap=20, force=True)
    stamp = _read_stamp(conn, result.trade_id)
    assert stamp == 1


def test_record_entry_stamps_new_policy_after_supersede(conn) -> None:
    """After supersede_active_policy → new active policy_id → next entry
    stamps the NEW id (read-time-vs-lock-time semantics work)."""
    new_policy_id = supersede_active_policy(
        conn,
        field_updates={"max_account_risk_per_trade_pct": 0.75},
        notes="operator test",
    )
    assert new_policy_id == 2

    req = _full_req(ticker="STAMPN", entry_date="2026-05-11")
    result = record_entry(conn, req, soft_warn=10, hard_cap=20, force=True)
    stamp = _read_stamp(conn, result.trade_id)
    assert stamp == 2


def test_legacy_trade_insert_has_null_stamp(conn) -> None:
    """Direct INSERT bypassing the entry service mimics legacy pre-Phase-9
    trades. Column is NULLable; read-time resolution by callers falls back
    to current active policy per spec §9.4."""
    conn.execute(
        "INSERT INTO trades ("
        "ticker, entry_date, entry_price, initial_shares, initial_stop, "
        "current_stop, state, sector, industry, trade_origin, "
        "pre_trade_locked_at, current_size"
        ") VALUES ("
        "'LEGACY', '2026-04-01', 50.0, 10, 47.0, 47.0, 'entered', "
        "'Tech', 'Software', 'manual_off_pipeline', "
        "'2026-04-01T15:30:00.000', 10"
        ")"
    )
    stamp = conn.execute(
        "SELECT risk_policy_id_at_lock FROM trades WHERE ticker = 'LEGACY'"
    ).fetchone()[0]
    assert stamp is None


def test_record_entry_stamp_in_same_transaction_as_trade_row(conn) -> None:
    """Stamp UPDATE happens inside the same `with conn:` as
    insert_trade_with_event. Discriminating via post-call query: the trade
    row + its stamp + the entry trade_event are all visible together (no
    half-state where the trade row exists but the stamp is NULL)."""
    req = _full_req(ticker="ATOMIC", entry_date="2026-05-11")
    result = record_entry(conn, req, soft_warn=10, hard_cap=20, force=True)
    row = conn.execute(
        "SELECT t.risk_policy_id_at_lock, "
        "(SELECT COUNT(*) FROM trade_events WHERE trade_id = t.id "
        " AND event_type = 'entry') AS n_events "
        "FROM trades t WHERE t.id = ?",
        (result.trade_id,),
    ).fetchone()
    stamp, n_events = row
    assert stamp == 1
    assert n_events == 1


def test_record_entry_no_active_policy_leaves_stamp_null(conn) -> None:
    """Defensive: when no active policy exists (operator manually flipped
    the seed inactive), the entry service stamps NULL — does NOT raise.
    Plan §9.4 backwards-compatibility contract: NULL stamp is legal; read
    paths fall back to current active policy."""
    conn.execute("UPDATE risk_policy SET is_active = 0")
    conn.commit()
    req = _full_req(ticker="NOPOL", entry_date="2026-05-11")
    result = record_entry(conn, req, soft_warn=10, hard_cap=20, force=True)
    stamp = _read_stamp(conn, result.trade_id)
    assert stamp is None
