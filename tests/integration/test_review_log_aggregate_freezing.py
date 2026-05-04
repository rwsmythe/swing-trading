"""End-to-end: aggregates persisted on Review_Log row are frozen-at-completion.

Brief §6.2 watch item 11 (4th sub-item).
"""
from pathlib import Path

import pytest

from swing.data.db import connect, ensure_schema
from swing.data.models import Exit, Trade
from swing.data.repos.review_log import (
    complete_review_atomic, get, insert_pre_create,
)
from swing.data.repos.trades import insert_exit_with_event, insert_trade_with_event


def test_review_aggregates_frozen_when_more_trades_close(tmp_path: Path) -> None:
    """R1 Major 1 + R2 Major 2: complete_review_atomic OWNS the freeze.

    Pre-condition: 1 closed trade in period.
    Action 1: complete_review_atomic — reads + computes + writes atomically.
    Action 2: close another trade IN THE SAME PERIOD.
    Post-condition: re-fetched review_log row aggregates UNCHANGED.
    """
    db_path = tmp_path / "phase6.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    try:
        # Seed: trade T1 closed 2026-04-15 with R=+1.0
        # NOTE: insert_exit_with_event auto-flips status; insert as open then exit
        with conn:
            t1 = insert_trade_with_event(
                conn, Trade(
                    id=None, ticker="T1", entry_date="2026-04-01",
                    entry_price=10.0, initial_shares=10, initial_stop=9.0,
                    current_stop=9.0, status="open",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ),
                event_ts="2026-04-01T09:30:00",
            )
            insert_exit_with_event(
                conn, Exit(
                    id=None, trade_id=t1, exit_date="2026-04-15",
                    exit_price=11.0, shares=10, reason="manual",
                    realized_pnl=10.0, r_multiple=1.0, notes=None,
                ),
                event_ts="2026-04-15T09:30:00",
            )
        with conn:
            review_id = insert_pre_create(
                conn, review_type="daily",
                period_start="2026-04-15", period_end="2026-04-15",
                scheduled_date="2026-04-16",
            )
        assert review_id is not None
        # Atomic complete-and-freeze:
        complete_review_atomic(
            conn, review_id=review_id,
            completed_date="2026-04-16",
            duration_minutes=10,
            primary_lesson="Inaugural trade.",
            next_period_focus="Same setup.",
        )
        row = get(conn, review_id)
        assert row is not None
        assert row.n_trades_reviewed == 1
        assert row.net_R_effective == pytest.approx(1.0)
        assert row.win_rate == pytest.approx(1.0)
        assert row.profit_factor is None  # no losses
        # Now close ANOTHER trade in the SAME period (2026-04-15):
        with conn:
            t2 = insert_trade_with_event(
                conn, Trade(
                    id=None, ticker="T2", entry_date="2026-04-10",
                    entry_price=20.0, initial_shares=5, initial_stop=18.0,
                    current_stop=18.0, status="open",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ),
                event_ts="2026-04-10T09:30:00",
            )
            insert_exit_with_event(
                conn, Exit(
                    id=None, trade_id=t2, exit_date="2026-04-15",
                    exit_price=22.0, shares=5, reason="manual",
                    realized_pnl=10.0, r_multiple=1.0, notes=None,
                ),
                event_ts="2026-04-15T09:30:00",
            )
        # Re-fetch — aggregates MUST be unchanged (frozen):
        row2 = get(conn, review_id)
        assert row2 is not None
        assert row2.net_R_effective == pytest.approx(1.0)  # NOT 2.0
        assert row2.n_trades_reviewed == 1                  # NOT 2
        assert row2.profit_factor is None
    finally:
        conn.close()
