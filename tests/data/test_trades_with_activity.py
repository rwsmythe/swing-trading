"""Tests for 3e.16 — list_trades_with_activity_in_period helper.

Coverage per dispatch brief §3.1:
  - period predicate union (entry / exit / event) + dedup
  - state-tag priority (OPENED / CLOSED / EVENT / OPENED+CLOSED)
  - activity_ts priority (exits > events > entry)
  - share-weighted realized_R for closed trades
  - inclusive period bounds on both ends
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.trades import (
    TradeActivitySummary,
    add_note_event,
    insert_trade_with_event,
    list_trades_with_activity_in_period,
)
from tests.conftest import insert_exit_fill, make_trade


@pytest.fixture
def conn(tmp_path: Path):
    db = tmp_path / "activity.db"
    ensure_schema(db).close()
    c = sqlite3.connect(db)
    try:
        yield c
    finally:
        c.close()


def _add_trade(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    entry_date: str,
    entry_price: float = 10.0,
    initial_shares: int = 100,
    initial_stop: float = 9.0,
    hypothesis_label: str | None = None,
) -> int:
    with conn:
        return insert_trade_with_event(
            conn,
            make_trade(
                ticker=ticker, entry_date=entry_date,
                entry_price=entry_price, initial_shares=initial_shares,
                initial_stop=initial_stop, current_stop=initial_stop,
                hypothesis_label=hypothesis_label,
                pre_trade_locked_at=f"{entry_date}T09:30:00",
            ),
            event_ts=f"{entry_date}T09:30:00",
        )


def test_includes_trade_entered_in_period(conn):
    tid = _add_trade(conn, ticker="AAA", entry_date="2026-04-15")
    rows = list_trades_with_activity_in_period(
        conn, period_start="2026-04-01", period_end="2026-04-30",
    )
    assert len(rows) == 1
    assert rows[0].trade_id == tid
    assert rows[0].state_tag == "[OPENED]"


def test_includes_trade_exited_in_period(conn):
    # Entry BEFORE period; exit INSIDE period.
    tid = _add_trade(conn, ticker="BBB", entry_date="2026-03-20")
    with conn:
        insert_exit_fill(
            conn, trade_id=tid, exit_date="2026-04-15",
            exit_price=12.0, shares=100,
            fill_datetime="2026-04-15T15:00:00",
        )
    rows = list_trades_with_activity_in_period(
        conn, period_start="2026-04-01", period_end="2026-04-30",
    )
    assert len(rows) == 1
    assert rows[0].trade_id == tid
    assert rows[0].state_tag == "[CLOSED]"
    assert rows[0].exit_date == "2026-04-15"
    assert rows[0].exit_price == 12.0


def test_includes_trade_with_event_in_period(conn):
    # Entry BEFORE period; trade_events row INSIDE period; still open.
    tid = _add_trade(conn, ticker="CCC", entry_date="2026-03-20")
    with conn:
        add_note_event(
            conn, trade_id=tid, event_ts="2026-04-10T11:00:00",
            note="re-checking thesis", rationale="periodic review",
        )
    rows = list_trades_with_activity_in_period(
        conn, period_start="2026-04-01", period_end="2026-04-30",
    )
    assert len(rows) == 1
    assert rows[0].trade_id == tid
    assert rows[0].state_tag == "[EVENT]"
    assert rows[0].exit_date is None
    assert rows[0].realized_R is None


def test_excludes_trades_entirely_outside_period(conn):
    # Trade 1: opened + closed BEFORE period.
    t1 = _add_trade(conn, ticker="DDD", entry_date="2026-02-01")
    with conn:
        insert_exit_fill(
            conn, trade_id=t1, exit_date="2026-02-20",
            exit_price=11.0, shares=100,
            fill_datetime="2026-02-20T15:00:00",
        )
    # Trade 2: opened AFTER period, still open.
    _add_trade(conn, ticker="EEE", entry_date="2026-05-15")
    # Trade 3: opened BEFORE period, still open, NO events in period.
    t3 = _add_trade(conn, ticker="FFF", entry_date="2026-03-01")
    with conn:
        add_note_event(
            conn, trade_id=t3, event_ts="2026-03-10T11:00:00",  # before period
            note="early note",
        )

    rows = list_trades_with_activity_in_period(
        conn, period_start="2026-04-01", period_end="2026-04-30",
    )
    assert rows == []


def test_dedups_trade_with_multiple_activities(conn):
    # Trade with entry IN period AND multiple trade_events IN period AND exit IN period.
    tid = _add_trade(conn, ticker="GGG", entry_date="2026-04-05")
    with conn:
        add_note_event(
            conn, trade_id=tid, event_ts="2026-04-08T11:00:00", note="check 1",
        )
        add_note_event(
            conn, trade_id=tid, event_ts="2026-04-12T11:00:00", note="check 2",
        )
        insert_exit_fill(
            conn, trade_id=tid, exit_date="2026-04-20",
            exit_price=12.0, shares=100,
            fill_datetime="2026-04-20T15:00:00",
        )
    rows = list_trades_with_activity_in_period(
        conn, period_start="2026-04-01", period_end="2026-04-30",
    )
    assert len(rows) == 1
    assert rows[0].trade_id == tid


def test_orders_by_activity_ts_asc(conn):
    # Three trades with progressively later activity in the period.
    # Earliest: AAA, entered + only event mid-period.
    a = _add_trade(conn, ticker="AAA", entry_date="2026-03-01")  # entry before period
    with conn:
        add_note_event(
            conn, trade_id=a, event_ts="2026-04-05T10:00:00", note="early event",
        )
    # Middle: BBB, exited in period.
    b = _add_trade(conn, ticker="BBB", entry_date="2026-03-15")
    with conn:
        insert_exit_fill(
            conn, trade_id=b, exit_date="2026-04-15",
            exit_price=12.0, shares=100,
            fill_datetime="2026-04-15T15:00:00",
        )
    # Latest: CCC, opened in period (entry_date 04-25 → activity_ts = 04-25T00:00:00).
    # But "no exit, no event" → activity_ts is entry-date midnight, which is EARLIER
    # than BBB's exit activity_ts of 04-15T23:59:59. We want CCC LATEST, so push entry later.
    c = _add_trade(conn, ticker="CCC", entry_date="2026-04-28")

    rows = list_trades_with_activity_in_period(
        conn, period_start="2026-04-01", period_end="2026-04-30",
    )
    # Expected order: AAA (event 04-05T10:00), BBB (exit 04-15T23:59:59),
    # CCC (entry 04-28T00:00:00). 04-15T23:59 < 04-28T00:00.
    assert [r.trade_id for r in rows] == [a, b, c]


def test_state_tag_opened_and_closed_same_period_concat(conn):
    # Same-period round trip → "[OPENED+CLOSED]".
    tid = _add_trade(conn, ticker="RRR", entry_date="2026-04-10")
    with conn:
        insert_exit_fill(
            conn, trade_id=tid, exit_date="2026-04-12",
            exit_price=12.0, shares=100,
            fill_datetime="2026-04-12T15:00:00",
        )
    rows = list_trades_with_activity_in_period(
        conn, period_start="2026-04-01", period_end="2026-04-30",
    )
    assert len(rows) == 1
    assert rows[0].state_tag == "[OPENED+CLOSED]"


def test_state_tag_event_when_only_events_in_period(conn):
    # Opened before period, only an event in period, still open.
    tid = _add_trade(conn, ticker="EEE", entry_date="2026-03-10")
    with conn:
        add_note_event(
            conn, trade_id=tid, event_ts="2026-04-10T11:00:00", note="mid",
        )
    rows = list_trades_with_activity_in_period(
        conn, period_start="2026-04-01", period_end="2026-04-30",
    )
    assert rows[0].state_tag == "[EVENT]"


def test_realized_r_share_weighted_for_closed_trade(conn):
    # entry=10, stop=9 → risk-per-share = 1.0. Exit at 12 → +2R per share.
    # Single full-size exit of 100 shares → realized_R = +2.0 * (100/100) = +2.0.
    tid = _add_trade(
        conn, ticker="RRR", entry_date="2026-04-05",
        entry_price=10.0, initial_shares=100, initial_stop=9.0,
    )
    with conn:
        insert_exit_fill(
            conn, trade_id=tid, exit_date="2026-04-20",
            exit_price=12.0, shares=100,
            fill_datetime="2026-04-20T15:00:00",
        )
    rows = list_trades_with_activity_in_period(
        conn, period_start="2026-04-01", period_end="2026-04-30",
    )
    assert rows[0].realized_R == pytest.approx(2.0)


def test_realized_r_split_exit_share_weighted(conn):
    # entry=10, stop=9, initial_shares=100. Trim 40 shares at 11 (R=+1),
    # close remaining 60 at 13 (R=+3). Share-weighted = 1*(40/100) + 3*(60/100) = 2.2.
    tid = _add_trade(
        conn, ticker="SSS", entry_date="2026-04-05",
        entry_price=10.0, initial_shares=100, initial_stop=9.0,
    )
    with conn:
        insert_exit_fill(
            conn, trade_id=tid, exit_date="2026-04-10",
            exit_price=11.0, shares=40, action="trim", close_trade=False,
            fill_datetime="2026-04-10T15:00:00",
        )
        insert_exit_fill(
            conn, trade_id=tid, exit_date="2026-04-20",
            exit_price=13.0, shares=60,
            fill_datetime="2026-04-20T15:00:00",
        )
    rows = list_trades_with_activity_in_period(
        conn, period_start="2026-04-01", period_end="2026-04-30",
    )
    assert rows[0].realized_R == pytest.approx(2.2)
    # Trade-level exit_date / exit_price reflect the LATEST exit fill.
    assert rows[0].exit_date == "2026-04-20"
    assert rows[0].exit_price == 13.0


def test_inclusive_period_bounds_event_on_period_end(conn):
    # trade_events.ts is an ISO DATETIME; period_end is YYYY-MM-DD.
    # The naive `ts <= period_end` string compare would WRONGLY exclude
    # '2026-04-30T15:30:00' > '2026-04-30'. Use date(ts) <= period_end.
    tid = _add_trade(conn, ticker="BND", entry_date="2026-03-01")
    with conn:
        add_note_event(
            conn, trade_id=tid, event_ts="2026-04-30T15:30:00",
            note="last-second-of-period",
        )
    rows = list_trades_with_activity_in_period(
        conn, period_start="2026-04-01", period_end="2026-04-30",
    )
    assert len(rows) == 1
    assert rows[0].trade_id == tid
    assert rows[0].state_tag == "[EVENT]"


def test_empty_period_returns_empty_list(conn):
    # No trades, no events.
    rows = list_trades_with_activity_in_period(
        conn, period_start="2026-04-01", period_end="2026-04-30",
    )
    assert rows == []


def test_trim_only_in_period_on_still_open_trade_tags_event_not_closed(conn):
    """Codex R1 Major #1 regression: a partial-exit ('trim') fill on a
    still-open trade must NOT trigger the [CLOSED] tag.

    Prior implementation tagged any non-entry-fill-in-period as
    was_closed_in_period regardless of trade state. The fix gates
    was_closed_in_period on the trade being in terminal state
    ('closed' / 'reviewed'). A trim fill writes a paired trade_events
    row (event_type='exit' per swing/data/repos/fills.py:65), so the
    trade still surfaces via the [EVENT] branch — the row still appears,
    just under the semantically-correct tag.

    Codex R2 Minor #2 strengthening: the conftest insert_exit_fill helper
    with close_trade=False leaves state='entered', but the real exit
    service transitions a trim to 'partial_exited'. This test flips
    state to 'partial_exited' manually to mirror the real lifecycle
    state machine, ensuring the regression covers the partial_exited
    state (not just entered/managing).
    """
    tid = _add_trade(
        conn, ticker="TRM", entry_date="2026-03-10",
        entry_price=10.0, initial_shares=100, initial_stop=9.0,
    )
    with conn:
        insert_exit_fill(
            conn, trade_id=tid, exit_date="2026-04-15",
            exit_price=11.0, shares=30, action="trim", close_trade=False,
            fill_datetime="2026-04-15T15:00:00",
        )
        # Mirror production exit-service: a trim transitions state to
        # 'partial_exited' (Codex R2 Minor #2).
        conn.execute(
            "UPDATE trades SET state='partial_exited' WHERE id=?", (tid,),
        )
    rows = list_trades_with_activity_in_period(
        conn, period_start="2026-04-01", period_end="2026-04-30",
    )
    assert len(rows) == 1
    assert rows[0].trade_id == tid
    # NOT [CLOSED] — trade is still partial_exited (non-terminal).
    assert rows[0].state_tag == "[EVENT]"
    # No trade-level exit fields populated because state is not closed.
    assert rows[0].exit_date is None
    assert rows[0].exit_price is None
    assert rows[0].realized_R is None


def test_trim_in_period_then_exit_later_does_not_tag_closed_for_earlier_period(conn):
    """Codex R2 Major #1 regression: a trade with a trim fill in April +
    final exit fill in May, viewed from the APRIL cadence review, must
    NOT tag [CLOSED]. The trade IS in terminal state ('closed') by the
    time the April review opens (May exit already happened), AND it has
    a non-entry fill in April (the trim), so the R1-style heuristic
    (terminal-state + any-non-entry-fill-in-period) would incorrectly
    tag [CLOSED]. The R2 fix requires the LAST non-entry fill across all
    time to fall in-period.
    """
    tid = _add_trade(
        conn, ticker="LON", entry_date="2026-03-10",
        entry_price=10.0, initial_shares=100, initial_stop=9.0,
    )
    with conn:
        insert_exit_fill(
            conn, trade_id=tid, exit_date="2026-04-15",
            exit_price=11.0, shares=30, action="trim", close_trade=False,
            fill_datetime="2026-04-15T15:00:00",
        )
        insert_exit_fill(
            conn, trade_id=tid, exit_date="2026-05-10",
            exit_price=13.0, shares=70, action="exit",
            fill_datetime="2026-05-10T15:00:00",
        )
    # APRIL review: should NOT tag [CLOSED] — the actual close was in May.
    rows_apr = list_trades_with_activity_in_period(
        conn, period_start="2026-04-01", period_end="2026-04-30",
    )
    assert len(rows_apr) == 1
    assert rows_apr[0].trade_id == tid
    assert rows_apr[0].state_tag == "[EVENT]"
    # MAY review: SHOULD tag [CLOSED] — the closing fill is in-period.
    rows_may = list_trades_with_activity_in_period(
        conn, period_start="2026-05-01", period_end="2026-05-31",
    )
    assert len(rows_may) == 1
    assert rows_may[0].state_tag == "[CLOSED]"


def test_fill_in_period_with_out_of_period_paired_event_uses_fill_ts(conn):
    """Codex R3 Major #1 regression: in production, the exit service
    writes fill_datetime (based on exit_date) and the paired
    trade_events.ts (based on operator submit time) as separately-
    supplied arguments. They can diverge. A trade with a non-entry fill
    in-period whose paired trade_events row is out-of-period would
    otherwise fall through to entry_date||'T00:00:00' as activity_ts
    (possibly months earlier — violating the period-ordering contract).
    The R3 fix probes latest in-period non-entry fill ts independently
    and uses it as a fallback when neither the close-tag branch nor the
    event-branch qualifies.

    Setup: trade entered 2026-02-01, trim fill 2026-04-15 (in April),
    but the operator submitted the trim record on 2026-05-10 so the
    paired trade_events row was written with ts=2026-05-10. April
    review should anchor on the fill (2026-04-15), not the entry date.
    """
    tid = _add_trade(conn, ticker="DIV", entry_date="2026-02-01")
    # Insert the fill DIRECTLY (bypassing insert_fill_with_event so we
    # control the trade_events.ts independently from fill_datetime).
    with conn:
        conn.execute(
            """
            INSERT INTO fills (trade_id, fill_datetime, action,
                               quantity, price)
            VALUES (?, ?, 'trim', 30, 11.0)
            """,
            (tid, "2026-04-15T15:00:00"),
        )
        # Paired trade_events row was written MUCH later (out-of-period).
        conn.execute(
            """
            INSERT INTO trade_events (trade_id, ts, event_type,
                                      payload_json)
            VALUES (?, ?, 'exit', '{"backfilled":true}')
            """,
            (tid, "2026-05-10T11:00:00"),
        )
    rows = list_trades_with_activity_in_period(
        conn, period_start="2026-04-01", period_end="2026-04-30",
    )
    assert len(rows) == 1
    assert rows[0].trade_id == tid
    assert rows[0].state_tag == "[EVENT]"
    # activity_ts must be the in-period fill ts, NOT entry-date midnight.
    assert rows[0].activity_ts == "2026-04-15T15:00:00"


def test_fractional_second_event_ts_on_period_end_included(conn):
    """Codex R2 Major #2 regression: a trade_events row at
    '2026-04-30T23:59:59.500000' must be INCLUDED in an April review.

    The prior R1 fix used `ts <= 'YYYY-MM-DDT23:59:59'` as the upper
    bound, which compares less than '2026-04-30T23:59:59.500000'
    lexicographically — so fractional-second timestamps at the very end
    of period_end were silently excluded. The R2 fix uses a half-open
    next-day-midnight upper bound that is fully inclusive of any sub-
    second precision on the last day.
    """
    tid = _add_trade(conn, ticker="FRAC", entry_date="2026-03-15")
    with conn:
        # Insert trade_event directly so we control fractional-second ts.
        conn.execute(
            """
            INSERT INTO trade_events (trade_id, ts, event_type, payload_json)
            VALUES (?, ?, 'note', '{"note":"sub-second"}')
            """,
            (tid, "2026-04-30T23:59:59.500000"),
        )
    rows = list_trades_with_activity_in_period(
        conn, period_start="2026-04-01", period_end="2026-04-30",
    )
    assert len(rows) == 1
    assert rows[0].trade_id == tid
    assert rows[0].state_tag == "[EVENT]"


def test_ordering_is_deterministic_for_same_day_closes(conn):
    """Codex R1 Major #4 regression: two trades closing on the same day
    receive identical activity_ts ('YYYY-MM-DDT23:59:59'). The sort must
    be stable on a secondary key so the rendered order doesn't depend on
    SQLite's UNION row-order.
    """
    # Insert two trades with closes on the SAME day. Tickers chosen so
    # alphabetic ordering is unambiguous (AAA < BBB).
    a = _add_trade(conn, ticker="AAA", entry_date="2026-03-10")
    b = _add_trade(conn, ticker="BBB", entry_date="2026-03-11")
    with conn:
        insert_exit_fill(
            conn, trade_id=b, exit_date="2026-04-15",
            exit_price=12.0, shares=100,
            fill_datetime="2026-04-15T15:00:00",
        )
        insert_exit_fill(
            conn, trade_id=a, exit_date="2026-04-15",
            exit_price=12.0, shares=100,
            fill_datetime="2026-04-15T15:00:00",
        )
    rows = list_trades_with_activity_in_period(
        conn, period_start="2026-04-01", period_end="2026-04-30",
    )
    assert [r.ticker for r in rows] == ["AAA", "BBB"]
    # Both have the same activity_ts string — secondary key must break the tie.
    assert rows[0].activity_ts == rows[1].activity_ts == "2026-04-15T23:59:59"


def test_summary_field_set_matches_locked_contract(conn):
    # All §0.3 #3 locked fields must be on the dataclass + populated correctly.
    tid = _add_trade(
        conn, ticker="ZZZ", entry_date="2026-04-05",
        entry_price=10.0, initial_shares=100, initial_stop=9.0,
        hypothesis_label="VCP-breakout",
    )
    with conn:
        insert_exit_fill(
            conn, trade_id=tid, exit_date="2026-04-20",
            exit_price=12.0, shares=100,
            fill_datetime="2026-04-20T15:00:00",
        )
    rows = list_trades_with_activity_in_period(
        conn, period_start="2026-04-01", period_end="2026-04-30",
    )
    s = rows[0]
    assert isinstance(s, TradeActivitySummary)
    assert s.trade_id == tid
    assert s.ticker == "ZZZ"
    assert s.entry_date == "2026-04-05"
    assert s.entry_price == 10.0
    assert s.exit_date == "2026-04-20"
    assert s.exit_price == 12.0
    assert s.realized_R == pytest.approx(2.0)
    assert s.hypothesis_label == "VCP-breakout"
    assert s.state_tag == "[OPENED+CLOSED]"
    assert s.activity_ts == "2026-04-20T23:59:59"
