"""Review_Log repo (Phase 6, migration 0013).

Owns idempotent pre-create + atomic completion (aggregate-freezing in a single
transaction). Read paths support dashboard cadence cards + needs-review badge
+ pending-list view.

Semantic split: ``list_pending`` surfaces cadence rows whose ``completed_date IS
NULL`` (used by the CLI ``swing review complete --list``). The ``/reviews/pending``
web route instead surfaces *unreviewed closed trades* via
``list_unreviewed_closed_trades`` — a completely separate concept. These two
"pending" surfaces are unrelated; never conflate them (R2 Minor 2 + R3 Minor 1).
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from swing.data.models import ReviewLog, Trade


# review_log column order per migration 0013 (for positional row access):
# 0  review_id
# 1  review_type
# 2  period_start
# 3  period_end
# 4  scheduled_date
# 5  completed_date
# 6  skipped
# 7  duration_minutes
# 8  n_trades_reviewed
# 9  total_mistake_cost_R
# 10 total_lucky_violation_R
# 11 primary_lesson
# 12 next_period_focus
# 13 created_at
# 14 net_R_effective
# 15 expectancy_R_effective
# 16 win_rate
# 17 avg_win_R
# 18 avg_loss_R
# 19 profit_factor
# 20 max_drawdown_R


def insert_pre_create(
    conn: sqlite3.Connection,
    *,
    review_type: str,
    period_start: str,
    period_end: str,
    scheduled_date: str,
) -> int | None:
    """Idempotent: returns new review_id, or None when a row already exists for
    (review_type, period_start, period_end). Caller wraps in ``with conn:``.

    Only swallows UNIQUE constraint violations (idempotent no-op). Any other
    IntegrityError (CHECK violation, etc.) re-raises so the caller learns about
    validation failures.
    """
    try:
        cur = conn.execute(
            """
            INSERT INTO review_log
                (review_type, period_start, period_end, scheduled_date)
            VALUES (?, ?, ?, ?)
            """,
            (review_type, period_start, period_end, scheduled_date),
        )
        return int(cur.lastrowid)
    except sqlite3.IntegrityError as exc:
        msg = str(exc)
        if "UNIQUE" in msg or "ux_review_log_cadence_period" in msg:
            return None
        raise


def complete_review_atomic(
    conn: sqlite3.Connection,
    *,
    review_id: int,
    completed_date: str,
    duration_minutes: int,
    primary_lesson: str,
    next_period_focus: str,
) -> None:
    """Mark review complete + freeze all aggregates atomically.

    Owns a ``BEGIN IMMEDIATE`` transaction. The caller must NOT wrap this
    in ``with conn:`` — the function manages its own BEGIN/COMMIT/ROLLBACK.

    Pipeline inside the transaction:
      1. Read (period_start, period_end) from the review_log row.
      2. Select closed trades whose final exit_date falls in [period_start, period_end].
      3. Compute 7 aggregates via swing.journal.stats.compute_stats (5 fields)
         + swing.trades.review.compute_profit_factor + compute_max_drawdown_R.
      4. Compute total_mistake_cost_R + total_lucky_violation_R by summing
         per-trade mistake/lucky helpers across the period's closed trades.
      5. UPDATE review_log with all computed fields + caller-supplied text fields.

    Caller does NOT supply aggregates — computed INSIDE the transaction (R1
    Major 1 fix vs. earlier draft API).
    """
    from swing.data.repos.trades import list_all_exits, list_closed_trades
    from swing.journal.stats import compute_stats
    from swing.trades.review import (
        compute_actual_realized_R_effective,
        compute_lucky_violation_R,
        compute_max_drawdown_R,
        compute_mistake_cost_R,
        compute_profit_factor,
    )

    conn.execute("BEGIN IMMEDIATE")
    try:
        # Step 1: read the period from review_log:
        row = conn.execute(
            "SELECT period_start, period_end FROM review_log WHERE review_id = ?",
            (review_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"review_log row #{review_id} not found")
        period_start, period_end = row[0], row[1]

        # Step 2: select closed trades whose final exit_date in [start, end]:
        all_closed = list_closed_trades(conn)
        all_exits = list_all_exits(conn)
        ps = date.fromisoformat(period_start)
        pe = date.fromisoformat(period_end)
        period_trades: list[Trade] = []
        for t in all_closed:
            relevant = [
                date.fromisoformat(e.exit_date)
                for e in all_exits
                if e.trade_id == t.id
            ]
            if not relevant:
                continue
            close_date = max(relevant)
            if ps <= close_date <= pe:
                period_trades.append(t)

        # Step 3: compute aggregates via compute_stats:
        stats = compute_stats(trades=period_trades, exits=all_exits)
        net_R = stats.total_r
        expectancy_R = stats.expectancy_r
        win_rate = stats.win_rate
        avg_win = stats.avg_win_r
        avg_loss = stats.avg_loss_r

        exits_list = list(all_exits)
        profit_factor = compute_profit_factor(period_trades, exits_list)
        max_dd = compute_max_drawdown_R(period_trades, exits_list)

        # Step 4: total_mistake_cost_R + total_lucky_violation_R per-trade sum:
        total_cost = 0.0
        total_lucky = 0.0
        for t in period_trades:
            actual = compute_actual_realized_R_effective(t, exits_list)
            total_cost += compute_mistake_cost_R(
                realized_R_if_plan_followed=t.realized_R_if_plan_followed,
                actual_realized_R_effective=actual,
            )
            total_lucky += compute_lucky_violation_R(
                realized_R_if_plan_followed=t.realized_R_if_plan_followed,
                actual_realized_R_effective=actual,
            )

        # Step 5: UPDATE review_log:
        conn.execute(
            """
            UPDATE review_log SET
                completed_date = ?,
                duration_minutes = ?,
                n_trades_reviewed = ?,
                primary_lesson = ?,
                next_period_focus = ?,
                total_mistake_cost_R = ?,
                total_lucky_violation_R = ?,
                net_R_effective = ?,
                expectancy_R_effective = ?,
                win_rate = ?,
                avg_win_R = ?,
                avg_loss_R = ?,
                profit_factor = ?,
                max_drawdown_R = ?
            WHERE review_id = ?
            """,
            (
                completed_date, duration_minutes, len(period_trades),
                primary_lesson, next_period_focus,
                total_cost, total_lucky,
                net_R, expectancy_R, win_rate, avg_win, avg_loss,
                profit_factor, max_dd, review_id,
            ),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


# Alias: the test module imports both names.
complete_review = complete_review_atomic


def get(conn: sqlite3.Connection, review_id: int) -> ReviewLog | None:
    row = conn.execute(
        "SELECT * FROM review_log WHERE review_id = ?", (review_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_review_log(row)


def list_recent(
    conn: sqlite3.Connection, *, review_type: str, limit: int = 1,
) -> list[ReviewLog]:
    """Most recent rows by BUSINESS PERIOD, not by insert time.

    R1 Minor 2 fix: a backfilled cadence row (e.g., operator manually
    inserts a missed weekly review) would jump to the top under
    ``ORDER BY created_at DESC`` even though its period_end is older than
    the current latest cadence. Order by period_end DESC + scheduled_date
    DESC (tiebreaker for same-period entries) so the dashboard cards
    surface the operator's CURRENT cadence, not the most-recently-typed
    backfill.
    """
    rows = conn.execute(
        """
        SELECT * FROM review_log
        WHERE review_type = ?
        ORDER BY period_end DESC, scheduled_date DESC
        LIMIT ?
        """,
        (review_type, limit),
    ).fetchall()
    return [_row_to_review_log(r) for r in rows]


def list_pending(
    conn: sqlite3.Connection, *, review_type: str | None = None,
) -> list[ReviewLog]:
    """Pre-created cadence rows whose ``completed_date IS NULL``.

    Used ONLY by the cadence-completion CLI (``swing review complete --list``)
    and a future cadence-pending dashboard surface (V2). NOT used by the
    ``/reviews/pending`` route — that route surfaces *unreviewed closed trades*
    (a different entity) via ``list_unreviewed_closed_trades``. These two
    "pending" concepts are unrelated. (R2 Minor 2 + R3 Minor 1 clarification.)
    """
    if review_type is None:
        rows = conn.execute(
            """
            SELECT * FROM review_log
            WHERE completed_date IS NULL
            ORDER BY period_end DESC
            """,
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM review_log
            WHERE completed_date IS NULL AND review_type = ?
            ORDER BY period_end DESC
            """,
            (review_type,),
        ).fetchall()
    return [_row_to_review_log(r) for r in rows]


def list_unreviewed_closed_trades(
    conn: sqlite3.Connection, *, window_days: int, today_iso: str,
) -> list[Trade]:
    """Return closed trades whose final exit date <= today - window_days AND
    whose ``reviewed_at IS NULL``.

    Uses the option (a) approach: call existing repo helpers
    (``list_closed_trades`` + ``list_all_exits``) and derive the close-date
    Python-side. Avoids row-factory complexity and keeps column-mapping aligned
    with the existing ``_row_to_trade`` mapper.

    Production trade volume (<500/year forecast) makes the Python-side filter
    trivially fast.
    """
    from swing.data.repos.trades import list_all_exits, list_closed_trades

    all_closed = list_closed_trades(conn)
    all_exits = list_all_exits(conn)
    today = date.fromisoformat(today_iso)
    cutoff = today - timedelta(days=window_days)
    out: list[Trade] = []
    for t in all_closed:
        if t.reviewed_at is not None:
            continue
        relevant = [
            date.fromisoformat(e.exit_date)
            for e in all_exits
            if e.trade_id == t.id
        ]
        if not relevant:
            continue
        close_date = max(relevant)
        if close_date <= cutoff:
            out.append(t)
    return out


def count_needs_review(
    conn: sqlite3.Connection, *, window_days: int, today_iso: str,
) -> int:
    """Count closed trades that need review (see ``list_unreviewed_closed_trades``)."""
    return len(list_unreviewed_closed_trades(
        conn, window_days=window_days, today_iso=today_iso,
    ))


def _row_to_review_log(row: tuple) -> ReviewLog:  # type: ignore[type-arg]
    """Map a positional sqlite3 row (SELECT * FROM review_log) to ReviewLog.

    Column order follows migration 0013 (see module-level comment).
    """
    skipped_raw = row[6]
    return ReviewLog(
        review_id=row[0],
        review_type=row[1],
        period_start=row[2],
        period_end=row[3],
        scheduled_date=row[4],
        completed_date=row[5],
        skipped=bool(skipped_raw) if skipped_raw is not None else False,
        duration_minutes=row[7],
        n_trades_reviewed=row[8],
        total_mistake_cost_R=row[9],
        total_lucky_violation_R=row[10],
        primary_lesson=row[11],
        next_period_focus=row[12],
        created_at=row[13],
        net_R_effective=row[14],
        expectancy_R_effective=row[15],
        win_rate=row[16],
        avg_win_R=row[17],
        avg_loss_R=row[18],
        profit_factor=row[19],
        max_drawdown_R=row[20],
    )
