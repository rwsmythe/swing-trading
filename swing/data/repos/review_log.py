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
from dataclasses import dataclass
from datetime import date, timedelta

from swing.data.models import ReviewLog, Trade


# C.10 migration helper (was: list_all_exits shim from repos/trades.py).
# Mirrors the _ExitShape adapter used in web view models — duck-typed
# Exit-shape over fills filtered to non-entry actions. Dies in a future
# cleanup phase when equity.py + review.py refactor to consume Fill
# directly.
@dataclass(frozen=True)
class _ExitShape:
    trade_id: int
    exit_date: str
    exit_price: float
    shares: int
    reason: str | None
    realized_pnl: float | None
    r_multiple: float | None


def _list_all_exitshape_via_fills(
    conn: sqlite3.Connection,
) -> list[_ExitShape]:
    """C.10 migration: return the ExitLike collection that
    ``list_all_exits(conn)`` previously returned, sourced from fills
    (action != 'entry'). Per-fill realized_pnl / r_multiple derive on the
    fly via ``swing.trades.derived_metrics`` — single source of math truth.
    Sort matches the legacy shim by virtue of ``list_all_fills``'s
    ``ORDER BY fill_datetime ASC, fill_id ASC``.
    """
    from swing.data.repos.fills import list_all_fills
    from swing.data.repos.trades import (
        list_closed_trades,
        list_open_trades,
    )
    from swing.trades.derived_metrics import (
        initial_risk_per_share,
        r_multiple,
        realized_pnl,
    )

    trades_by_id: dict[int, Trade] = {}
    for t in list_open_trades(conn):
        if t.id is not None:
            trades_by_id[t.id] = t
    for t in list_closed_trades(conn):
        if t.id is not None:
            trades_by_id[t.id] = t

    out: list[_ExitShape] = []
    for f in list_all_fills(conn):
        if f.action == "entry":
            continue
        trade = trades_by_id.get(f.trade_id)
        if trade is None:
            continue  # orphan fill — skip (parent trade missing)
        rps = initial_risk_per_share(
            entry_price=trade.entry_price,
            initial_stop=trade.initial_stop,
        )
        pnl = realized_pnl(
            entry_price=trade.entry_price, exit_price=f.price,
            quantity=f.quantity,
        )
        if rps == 0 or f.quantity == 0:
            rmult: float | None = None
        else:
            rmult = r_multiple(
                realized_pnl=pnl, initial_risk_per_share=rps,
                quantity=f.quantity,
            )
        exit_date = (
            f.fill_datetime.split("T")[0]
            if "T" in f.fill_datetime else f.fill_datetime
        )
        out.append(_ExitShape(
            trade_id=f.trade_id,
            exit_date=exit_date,
            exit_price=float(f.price),
            shares=int(f.quantity),
            reason=f.reason,
            realized_pnl=pnl,
            r_multiple=rmult,
        ))
    return out

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
    from swing.data.repos.trades import list_closed_trades
    from swing.journal.stats import compute_stats
    from swing.trades.review import (
        compute_actual_realized_R_effective,
        compute_lucky_violation_R,
        compute_max_drawdown_R,
        compute_mistake_cost_R,
        compute_profit_factor,
    )

    # Spec §2.5: required-if-completed fields enforced at repo layer so that
    # direct callers (not just CLI/web) cannot bypass validation.
    if duration_minutes is None or duration_minutes <= 0:
        raise ValueError(
            "complete_review_atomic: duration_minutes must be positive"
        )
    if not primary_lesson or not primary_lesson.strip():
        raise ValueError(
            "complete_review_atomic: primary_lesson is required"
        )
    if not next_period_focus or not next_period_focus.strip():
        raise ValueError(
            "complete_review_atomic: next_period_focus is required"
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
        all_exits = _list_all_exitshape_via_fills(conn)
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
        net_R = stats.total_r  # noqa: N806
        expectancy_R = stats.expectancy_r  # noqa: N806
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

        # Step 5: UPDATE review_log. Phase 9 T-A.7 adds the
        # risk_policy_id_at_review_completion stamp — sub-query reads the
        # active policy_id at completion time (spec §3.1.1). NULL when no
        # active policy exists (operator manually flipped seed inactive);
        # legal per spec §9.4 backwards-compatibility contract.
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
                max_drawdown_R = ?,
                risk_policy_id_at_review_completion = (
                    SELECT policy_id FROM risk_policy WHERE is_active = 1
                )
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
    conn: sqlite3.Connection,
    *,
    window_days: int | None,
    today_iso: str | None,
) -> list[Trade]:
    """Return closed trades whose ``reviewed_at IS NULL``.

    When ``window_days`` is ``None`` (list-view mode, spec §3.1): ALL
    closed-unreviewed trades are returned regardless of close-date age.

    When ``window_days`` is an int (badge mode, spec §2.6): only trades
    whose final exit date is at least ``window_days`` days before
    ``today_iso`` are returned.  ``today_iso`` is required when
    ``window_days`` is not ``None``.

    Uses the option (a) approach: call existing repo helpers
    (``list_closed_trades`` + the C.10-local ``_list_all_exitshape_via_fills``)
    and derive the close-date Python-side. Avoids row-factory complexity and
    keeps column-mapping aligned with the existing ``_row_to_trade`` mapper.

    Production trade volume (<500/year forecast) makes the Python-side filter
    trivially fast.
    """
    from swing.data.repos.trades import list_closed_trades

    all_closed = list_closed_trades(conn)
    all_exits = _list_all_exitshape_via_fills(conn)

    # Compute cutoff only when the window filter is active.
    if window_days is not None:
        assert today_iso is not None, (
            "today_iso is required when window_days is not None"
        )
        today = date.fromisoformat(today_iso)
        cutoff: date | None = today - timedelta(days=window_days)
    else:
        cutoff = None

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
        if cutoff is not None and close_date > cutoff:
            continue
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
