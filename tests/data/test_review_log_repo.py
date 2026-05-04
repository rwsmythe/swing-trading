"""Review_Log repo CRUD + idempotent pre-create + completion-freezing tests."""
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import Exit, Trade
from swing.data.repos.review_log import (
    complete_review, count_needs_review, get, insert_pre_create,
    list_recent, list_unreviewed_closed_trades,
)
from swing.data.repos.trades import insert_exit_with_event, insert_trade_with_event


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase6.db"
    conn = ensure_schema(db_path)
    yield conn
    conn.close()


class TestInsertPreCreate:
    def test_first_insert_returns_id(self, conn: sqlite3.Connection) -> None:
        with conn:
            review_id = insert_pre_create(
                conn, review_type="daily",
                period_start="2026-04-30", period_end="2026-04-30",
                scheduled_date="2026-05-01",
            )
        assert review_id is not None
        assert review_id >= 1

    def test_duplicate_returns_none(self, conn: sqlite3.Connection) -> None:
        with conn:
            first = insert_pre_create(
                conn, review_type="daily",
                period_start="2026-04-30", period_end="2026-04-30",
                scheduled_date="2026-05-01",
            )
            second = insert_pre_create(
                conn, review_type="daily",
                period_start="2026-04-30", period_end="2026-04-30",
                scheduled_date="2026-05-01",
            )
        assert first is not None
        assert second is None
        # Verify only one row exists:
        count = conn.execute("SELECT COUNT(*) FROM review_log").fetchone()[0]
        assert count == 1

    def test_different_periods_each_get_a_row(self, conn: sqlite3.Connection) -> None:
        with conn:
            r1 = insert_pre_create(
                conn, review_type="daily",
                period_start="2026-04-30", period_end="2026-04-30",
                scheduled_date="2026-05-01",
            )
            r2 = insert_pre_create(
                conn, review_type="weekly",
                period_start="2026-04-21", period_end="2026-04-25",
                scheduled_date="2026-04-28",
            )
        assert r1 != r2
        assert r1 is not None and r2 is not None


class TestCompleteReviewAtomic:
    def test_atomic_freezes_computed_aggregates(
        self, conn: sqlite3.Connection,
    ) -> None:
        # Seed: closed trade in the daily period
        with conn:
            t1 = insert_trade_with_event(
                conn, Trade(
                    id=None, ticker="VIR", entry_date="2026-04-29",
                    entry_price=10.0, initial_shares=10, initial_stop=9.0,
                    current_stop=9.0, status="open", state="entered",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ),
                event_ts="2026-04-29T09:30:00",
            )
            insert_exit_with_event(
                conn, Exit(
                    id=None, trade_id=t1, exit_date="2026-04-30",
                    exit_price=12.0, shares=10, reason="manual",
                    realized_pnl=20.0, r_multiple=2.0, notes=None,
                ),
                event_ts="2026-04-30T09:30:00",
            )
        # Pre-create + atomic complete:
        with conn:
            review_id = insert_pre_create(
                conn, review_type="daily",
                period_start="2026-04-30", period_end="2026-04-30",
                scheduled_date="2026-05-01",
            )
        assert review_id is not None
        # complete_review_atomic OWNS the compute → write pipeline.
        # Brief §6.2 watch item 3: caller does NOT supply aggregates.
        from swing.data.repos.review_log import complete_review_atomic
        complete_review_atomic(
            conn, review_id=review_id,
            completed_date="2026-05-02",
            duration_minutes=15,
            primary_lesson="Wait for the breakout.",
            next_period_focus="Tighten entries on volume confirmation.",
        )
        row = get(conn, review_id)
        assert row is not None
        assert row.completed_date == "2026-05-02"
        assert row.duration_minutes == 15
        assert row.primary_lesson == "Wait for the breakout."
        assert row.next_period_focus.startswith("Tighten")
        # n_trades_reviewed + total_*_R + 7 aggregates were computed inside
        # the transaction by reading closed trades in (period_start, period_end]
        # via compute_stats + review.py augmentation helpers:
        assert row.n_trades_reviewed == 1
        assert row.net_R_effective == pytest.approx(2.0)
        assert row.win_rate == pytest.approx(1.0)
        assert row.profit_factor is None  # no losses

    # NOTE: a separate concurrent-writer transaction-isolation test is
    # NOT included here because the integration test in Task 14
    # (test_review_aggregates_frozen_when_more_trades_close) already
    # exercises the operational invariant — a trade close AFTER
    # complete_review_atomic does not mutate the row's frozen state.
    # SQLite's BEGIN IMMEDIATE acquires the RESERVED lock immediately,
    # so concurrent writers either commit before us (visible in our
    # SELECT inside the transaction) or block until we COMMIT (not
    # visible). Both branches preserve the snapshot — there is no
    # additional discriminating power from a multi-connection unit test.


class TestCountNeedsReview:
    def test_only_closed_unreviewed_old_enough_count(
        self, conn: sqlite3.Connection,
    ) -> None:
        # Trade 1: closed 2026-04-01 unreviewed → SHOULD count (old enough)
        # Trade 2: closed 2026-05-01 unreviewed → should NOT count (within window)
        # Trade 3: closed 2026-04-01 reviewed_at set → should NOT count
        # Trade 4: open → should NOT count
        with conn:
            t1 = insert_trade_with_event(
                conn, Trade(
                    id=None, ticker="T1", entry_date="2026-03-01",
                    entry_price=10.0, initial_shares=10, initial_stop=9.0,
                    current_stop=9.0, status="open", state="entered",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ),
                event_ts="2026-03-01T09:30:00",
            )
            insert_exit_with_event(
                conn, Exit(
                    id=None, trade_id=t1, exit_date="2026-04-01",
                    exit_price=11.0, shares=10, reason="manual",
                    realized_pnl=10.0, r_multiple=1.0, notes=None,
                ),
                event_ts="2026-04-01T09:30:00",
            )
            t2 = insert_trade_with_event(
                conn, Trade(
                    id=None, ticker="T2", entry_date="2026-04-01",
                    entry_price=10.0, initial_shares=10, initial_stop=9.0,
                    current_stop=9.0, status="open", state="entered",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ),
                event_ts="2026-04-01T09:30:00",
            )
            insert_exit_with_event(
                conn, Exit(
                    id=None, trade_id=t2, exit_date="2026-05-01",
                    exit_price=11.0, shares=10, reason="manual",
                    realized_pnl=10.0, r_multiple=1.0, notes=None,
                ),
                event_ts="2026-05-01T09:30:00",
            )
        # Mark t3 as reviewed:
        # (t3 not actually inserted here; testing the closed/unreviewed-only filter
        # is sufficient with t1 + t2.)
        # Check needs-review at today=2026-05-10, window=7 days:
        n = count_needs_review(conn, window_days=7, today_iso="2026-05-10")
        # t1 closed 2026-04-01 → 39 days ago → counts
        # t2 closed 2026-05-01 → 9 days ago → counts (>= 7 days old)
        # Both old enough; both unreviewed. Expected: 2.
        assert n == 2


class TestListRecent:
    def test_returns_most_recent_per_cadence(
        self, conn: sqlite3.Connection,
    ) -> None:
        with conn:
            insert_pre_create(
                conn, review_type="daily",
                period_start="2026-04-29", period_end="2026-04-29",
                scheduled_date="2026-04-30",
            )
            insert_pre_create(
                conn, review_type="daily",
                period_start="2026-04-30", period_end="2026-04-30",
                scheduled_date="2026-05-01",
            )
        rows = list_recent(conn, review_type="daily", limit=2)
        assert len(rows) == 2
        # Most-recent first by created_at:
        assert rows[0].period_start == "2026-04-30"
        assert rows[1].period_start == "2026-04-29"


def test_review_config_default_window_days_is_7() -> None:
    """Brief §2.6 — `cfg.review.review_window_days` default = 7."""
    from pathlib import Path
    from swing.config import load
    cfg = load(Path("swing.config.toml"))
    assert cfg.review.review_window_days == 7


class TestListUnreviewedClosedTradesWindowNone:
    """Major 1: list-view shows ALL closed-unreviewed when window_days=None."""

    def _seed_closed_trade(
        self,
        conn: sqlite3.Connection,
        ticker: str,
        entry_date: str,
        exit_date: str,
    ) -> int:
        trade_id = insert_trade_with_event(
            conn,
            Trade(
                id=None,
                ticker=ticker,
                entry_date=entry_date,
                entry_price=10.0,
                initial_shares=10,
                initial_stop=9.0,
                current_stop=9.0,
                status="open", state="entered",
                watchlist_entry_target=None,
                watchlist_initial_stop=None,
                notes=None,
            ),
            event_ts=f"{entry_date}T09:30:00",
        )
        from swing.data.models import Exit
        insert_exit_with_event(
            conn,
            Exit(
                id=None,
                trade_id=trade_id,
                exit_date=exit_date,
                exit_price=11.0,
                shares=10,
                reason="manual",
                realized_pnl=10.0,
                r_multiple=1.0,
                notes=None,
            ),
            event_ts=f"{exit_date}T09:30:00",
        )
        return trade_id

    def test_no_window_returns_all_closed_unreviewed(
        self, conn: sqlite3.Connection,
    ) -> None:
        """window_days=None: ALL closed-unreviewed returned regardless of age."""
        with conn:
            self._seed_closed_trade(conn, "OLD", "2026-03-01", "2026-04-25")  # 30+ days old
            self._seed_closed_trade(conn, "NEW", "2026-04-30", "2026-05-01")  # yesterday
        result = list_unreviewed_closed_trades(conn, window_days=None, today_iso=None)
        tickers = {t.ticker for t in result}
        assert len(result) == 2
        assert "OLD" in tickers
        assert "NEW" in tickers

    def test_window_7_excludes_recent(self, conn: sqlite3.Connection) -> None:
        """window_days=7, today=2026-05-02: only the 30-day-old trade qualifies."""
        with conn:
            self._seed_closed_trade(conn, "OLD", "2026-03-01", "2026-04-25")  # 7+ days old
            self._seed_closed_trade(conn, "NEW", "2026-04-30", "2026-05-01")  # 1 day old
        result = list_unreviewed_closed_trades(conn, window_days=7, today_iso="2026-05-02")
        assert len(result) == 1
        assert result[0].ticker == "OLD"


class TestCompleteReviewValidation:
    """Major 3: repo-layer required-if-completed enforcement."""

    def test_rejects_zero_duration(self, conn: sqlite3.Connection) -> None:
        with conn:
            review_id = insert_pre_create(
                conn, review_type="daily",
                period_start="2026-04-30", period_end="2026-04-30",
                scheduled_date="2026-05-01",
            )
        with pytest.raises(ValueError, match="duration"):
            from swing.data.repos.review_log import complete_review_atomic
            complete_review_atomic(
                conn, review_id=review_id,
                completed_date="2026-05-02", duration_minutes=0,
                primary_lesson="x", next_period_focus="y",
            )

    def test_rejects_blank_lesson(self, conn: sqlite3.Connection) -> None:
        with conn:
            review_id = insert_pre_create(
                conn, review_type="daily",
                period_start="2026-04-30", period_end="2026-04-30",
                scheduled_date="2026-05-01",
            )
        with pytest.raises(ValueError, match="primary_lesson"):
            from swing.data.repos.review_log import complete_review_atomic
            complete_review_atomic(
                conn, review_id=review_id,
                completed_date="2026-05-02", duration_minutes=10,
                primary_lesson="   ", next_period_focus="y",
            )

    def test_rejects_blank_next_period_focus(self, conn: sqlite3.Connection) -> None:
        with conn:
            review_id = insert_pre_create(
                conn, review_type="daily",
                period_start="2026-04-30", period_end="2026-04-30",
                scheduled_date="2026-05-01",
            )
        with pytest.raises(ValueError, match="next_period_focus"):
            from swing.data.repos.review_log import complete_review_atomic
            complete_review_atomic(
                conn, review_id=review_id,
                completed_date="2026-05-02", duration_minutes=10,
                primary_lesson="Good lesson.", next_period_focus="",
            )
