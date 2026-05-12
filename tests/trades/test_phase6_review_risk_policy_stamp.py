"""Phase 9 T-A.7 — complete_review_atomic stamps review_log
.risk_policy_id_at_review_completion.

Spec §3.1.1 + plan T-A.7: at review completion time, the repo stamps the
review_log row with the active risk_policy.policy_id. The stamp preserves
which scratch_epsilon + process_grade_weights produced the frozen
aggregates even when the policy is later superseded.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import Trade
from swing.data.repos.review_log import (
    complete_review_atomic, get, insert_pre_create,
)
from swing.data.repos.trades import insert_trade_with_event
from swing.trades.risk_policy import supersede_active_policy
from tests.conftest import insert_exit_fill


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase9_review_stamp.db"
    conn = ensure_schema(db_path)
    yield conn
    conn.close()


def _seed_closed_trade_with_review(conn) -> int:
    with conn:
        t1 = insert_trade_with_event(
            conn, Trade(
                id=None, ticker="VIR", entry_date="2026-04-29",
                entry_price=10.0, initial_shares=10, initial_stop=9.0,
                current_stop=9.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ),
            event_ts="2026-04-29T09:30:00",
        )
        insert_exit_fill(
            conn, trade_id=t1, exit_date="2026-04-30",
            exit_price=12.0, shares=10, reason="manual",
            fill_datetime="2026-04-30T09:30:00",
        )
    with conn:
        review_id = insert_pre_create(
            conn, review_type="daily",
            period_start="2026-04-30", period_end="2026-04-30",
            scheduled_date="2026-05-01",
        )
    assert review_id is not None
    return review_id


def test_complete_review_stamps_seed_policy(conn) -> None:
    review_id = _seed_closed_trade_with_review(conn)
    complete_review_atomic(
        conn, review_id=review_id,
        completed_date="2026-05-02",
        duration_minutes=15,
        primary_lesson="Wait for the breakout.",
        next_period_focus="Tighten entries on volume confirmation.",
    )
    stamp = conn.execute(
        "SELECT risk_policy_id_at_review_completion FROM review_log "
        "WHERE review_id = ?",
        (review_id,),
    ).fetchone()[0]
    assert stamp == 1


def test_complete_review_stamps_new_policy_after_supersede(conn) -> None:
    review_id = _seed_closed_trade_with_review(conn)
    new_id = supersede_active_policy(
        conn,
        field_updates={"max_account_risk_per_trade_pct": 0.75},
        notes="bumped between trade close + review",
    )
    assert new_id == 2

    complete_review_atomic(
        conn, review_id=review_id,
        completed_date="2026-05-02",
        duration_minutes=15,
        primary_lesson="Wait for the breakout.",
        next_period_focus="Tighten entries on volume confirmation.",
    )
    stamp = conn.execute(
        "SELECT risk_policy_id_at_review_completion FROM review_log "
        "WHERE review_id = ?",
        (review_id,),
    ).fetchone()[0]
    assert stamp == 2


def test_legacy_review_log_pre_create_has_null_stamp(conn) -> None:
    """A pre_create row before completion has NULL stamp; the column is
    only populated at completion time per spec §3.1.1."""
    with conn:
        review_id = insert_pre_create(
            conn, review_type="daily",
            period_start="2026-04-30", period_end="2026-04-30",
            scheduled_date="2026-05-01",
        )
    assert review_id is not None
    stamp = conn.execute(
        "SELECT risk_policy_id_at_review_completion FROM review_log "
        "WHERE review_id = ?",
        (review_id,),
    ).fetchone()[0]
    assert stamp is None


def test_complete_review_no_active_policy_leaves_stamp_null(conn) -> None:
    """When no active policy exists, completion stamps NULL (the SELECT
    sub-query returns NULL); does NOT raise. Backwards-compatible with
    legacy review_log rows."""
    review_id = _seed_closed_trade_with_review(conn)
    conn.execute("UPDATE risk_policy SET is_active = 0")
    conn.commit()
    complete_review_atomic(
        conn, review_id=review_id,
        completed_date="2026-05-02",
        duration_minutes=15,
        primary_lesson="Wait for the breakout.",
        next_period_focus="Tighten entries on volume confirmation.",
    )
    stamp = conn.execute(
        "SELECT risk_policy_id_at_review_completion FROM review_log "
        "WHERE review_id = ?",
        (review_id,),
    ).fetchone()[0]
    assert stamp is None
