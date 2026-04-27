"""Trades + exits + trade_events repo.

Every mutation of `trades` writes a `trade_events` row in the same transaction.
This is enforced by exposing only `*_with_event` mutation functions; there is no
`insert_trade` without `_with_event` companion.
"""
from __future__ import annotations

import json
import sqlite3

from swing.data.models import Exit, Trade, TradeEvent


def _validate_chart_pattern_invariant(trade: Trade) -> None:
    """Repo-layer cross-column invariant per spec §3.2.2 (R2 M2).

    SQLite ALTER TABLE cannot add a multi-column row CHECK without a
    heavyweight rebuild. V1 enforces the invariant here. V2 hardens at
    schema level when the next trade-table rebuild bundles other changes.
    """
    algo = trade.chart_pattern_algo
    conf = trade.chart_pattern_algo_confidence
    anchor = trade.chart_pattern_classification_pipeline_run_id
    if (algo is None) != (anchor is None):
        raise ValueError(
            "chart_pattern invariant: algo and "
            "chart_pattern_classification_pipeline_run_id must both be "
            "NULL or both be non-NULL"
        )
    if algo == "flag" and conf is None:
        raise ValueError(
            "chart_pattern invariant: chart_pattern_algo='flag' requires "
            "chart_pattern_algo_confidence NOT NULL"
        )
    if algo == "none" and conf is not None:
        raise ValueError(
            "chart_pattern invariant: chart_pattern_algo='none' requires "
            "chart_pattern_algo_confidence NULL"
        )


def insert_trade_with_event(
    conn: sqlite3.Connection, trade: Trade, *,
    event_ts: str, rationale: str | None = None,
) -> int:
    """Insert a trade and an 'entry' trade_event in the same transaction.
    Caller wraps in `with conn:`. Returns the new trade id.
    """
    _validate_chart_pattern_invariant(trade)
    cur = conn.execute(
        """
        INSERT INTO trades
            (ticker, entry_date, entry_price, initial_shares, initial_stop,
             current_stop, status, watchlist_entry_target,
             watchlist_initial_stop, notes, hypothesis_label,
             chart_pattern_algo, chart_pattern_algo_confidence,
             chart_pattern_operator,
             chart_pattern_classification_pipeline_run_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (trade.ticker, trade.entry_date, trade.entry_price, trade.initial_shares,
         trade.initial_stop, trade.current_stop, trade.status,
         trade.watchlist_entry_target, trade.watchlist_initial_stop, trade.notes,
         trade.hypothesis_label, trade.chart_pattern_algo,
         trade.chart_pattern_algo_confidence, trade.chart_pattern_operator,
         trade.chart_pattern_classification_pipeline_run_id),
    )
    trade_id = int(cur.lastrowid)
    payload = {
        "ticker": trade.ticker,
        "entry_date": trade.entry_date,
        "entry_price": trade.entry_price,
        "initial_shares": trade.initial_shares,
        "initial_stop": trade.initial_stop,
    }
    conn.execute(
        """
        INSERT INTO trade_events (trade_id, ts, event_type, payload_json, rationale)
        VALUES (?, ?, 'entry', ?, ?)
        """,
        (trade_id, event_ts, json.dumps(payload, sort_keys=True), rationale),
    )
    return trade_id


def insert_exit_with_event(
    conn: sqlite3.Connection, exit_row: Exit, *,
    event_ts: str, rationale: str | None = None,
) -> int:
    """Insert an exit + 'exit' trade_event. Flips trade.status to 'closed' if
    cumulative exits == initial_shares. All in caller's transaction.
    Raises ValueError if shares exceeds remaining."""
    trade = get_trade(conn, exit_row.trade_id)
    if trade is None:
        raise ValueError(f"trade {exit_row.trade_id} not found")
    if trade.status != "open":
        raise ValueError(f"trade {exit_row.trade_id} is already closed")

    sold = conn.execute(
        "SELECT COALESCE(SUM(shares), 0) FROM exits WHERE trade_id = ?",
        (exit_row.trade_id,),
    ).fetchone()[0]
    remaining = trade.initial_shares - sold
    if exit_row.shares > remaining:
        raise ValueError(f"exit shares {exit_row.shares} exceeds remaining {remaining}")

    cur = conn.execute(
        """
        INSERT INTO exits
            (trade_id, exit_date, exit_price, shares, reason,
             realized_pnl, r_multiple, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (exit_row.trade_id, exit_row.exit_date, exit_row.exit_price,
         exit_row.shares, exit_row.reason, exit_row.realized_pnl,
         exit_row.r_multiple, exit_row.notes),
    )
    exit_id = int(cur.lastrowid)
    payload = {
        "exit_date": exit_row.exit_date,
        "exit_price": exit_row.exit_price,
        "shares": exit_row.shares,
        "reason": exit_row.reason,
        "realized_pnl": exit_row.realized_pnl,
        "r_multiple": exit_row.r_multiple,
    }
    conn.execute(
        """
        INSERT INTO trade_events (trade_id, ts, event_type, payload_json, rationale)
        VALUES (?, ?, 'exit', ?, ?)
        """,
        (exit_row.trade_id, event_ts, json.dumps(payload, sort_keys=True), rationale),
    )
    if exit_row.shares == remaining:
        conn.execute(
            "UPDATE trades SET status='closed' WHERE id = ?",
            (exit_row.trade_id,),
        )
    return exit_id


def update_stop_with_event(
    conn: sqlite3.Connection, *, trade_id: int, new_stop: float,
    event_ts: str, rationale: str | None = None,
    notes: str | None = None,
) -> None:
    """Update trades.current_stop + write 'stop_adjust' event in same txn.
    Phase 3c §4.4: atomic status='open' guard closes the close-then-stop race.
    Missing or closed trade → ValueError with no event insert."""
    trade = get_trade(conn, trade_id)
    if trade is None:
        raise ValueError(f"trade {trade_id} not found")
    if trade.current_stop == new_stop:
        return  # no-op
    payload = {"old_stop": trade.current_stop, "new_stop": new_stop}
    cur = conn.execute(
        "UPDATE trades SET current_stop = ? WHERE id = ? AND status = 'open'",
        (new_stop, trade_id),
    )
    if cur.rowcount == 0:
        raise ValueError(f"trade {trade_id} is not open or does not exist")
    conn.execute(
        """
        INSERT INTO trade_events (trade_id, ts, event_type, payload_json, rationale, notes)
        VALUES (?, ?, 'stop_adjust', ?, ?, ?)
        """,
        (trade_id, event_ts, json.dumps(payload, sort_keys=True), rationale, notes),
    )


def add_note_event(
    conn: sqlite3.Connection, *, trade_id: int, event_ts: str,
    note: str, rationale: str | None = None,
) -> None:
    """Free-text 'note' event — does NOT mutate trades, just adds an audit row."""
    payload = {"note": note}
    conn.execute(
        """
        INSERT INTO trade_events (trade_id, ts, event_type, payload_json, rationale)
        VALUES (?, ?, 'note', ?, ?)
        """,
        (trade_id, event_ts, json.dumps(payload, sort_keys=True), rationale),
    )


def get_trade(conn: sqlite3.Connection, trade_id: int) -> Trade | None:
    row = conn.execute(
        """
        SELECT id, ticker, entry_date, entry_price, initial_shares, initial_stop,
               current_stop, status, watchlist_entry_target,
               watchlist_initial_stop, notes, hypothesis_label,
               chart_pattern_algo, chart_pattern_algo_confidence,
               chart_pattern_operator, chart_pattern_classification_pipeline_run_id
        FROM trades WHERE id = ?
        """,
        (trade_id,),
    ).fetchone()
    return _row_to_trade(row) if row else None


def list_open_trades(conn: sqlite3.Connection) -> list[Trade]:
    rows = conn.execute(
        """
        SELECT id, ticker, entry_date, entry_price, initial_shares, initial_stop,
               current_stop, status, watchlist_entry_target,
               watchlist_initial_stop, notes, hypothesis_label,
               chart_pattern_algo, chart_pattern_algo_confidence,
               chart_pattern_operator, chart_pattern_classification_pipeline_run_id
        FROM trades WHERE status='open' ORDER BY entry_date, ticker
        """,
    ).fetchall()
    return [_row_to_trade(r) for r in rows]


def list_closed_trades(
    conn: sqlite3.Connection, *, since_date: str | None = None
) -> list[Trade]:
    if since_date:
        rows = conn.execute(
            """
            SELECT t.id, t.ticker, t.entry_date, t.entry_price, t.initial_shares,
                   t.initial_stop, t.current_stop, t.status, t.watchlist_entry_target,
                   t.watchlist_initial_stop, t.notes, t.hypothesis_label,
                   t.chart_pattern_algo, t.chart_pattern_algo_confidence,
                   t.chart_pattern_operator, t.chart_pattern_classification_pipeline_run_id
            FROM trades t
            WHERE t.status='closed'
              AND EXISTS (SELECT 1 FROM exits e WHERE e.trade_id=t.id AND e.exit_date >= ?)
            ORDER BY t.entry_date DESC, t.ticker
            """,
            (since_date,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, ticker, entry_date, entry_price, initial_shares, initial_stop,
                   current_stop, status, watchlist_entry_target,
                   watchlist_initial_stop, notes, hypothesis_label,
                   chart_pattern_algo, chart_pattern_algo_confidence,
                   chart_pattern_operator, chart_pattern_classification_pipeline_run_id
            FROM trades WHERE status='closed' ORDER BY entry_date DESC, ticker
            """,
        ).fetchall()
    return [_row_to_trade(r) for r in rows]


def list_exits_for_trade(conn: sqlite3.Connection, trade_id: int) -> list[Exit]:
    rows = conn.execute(
        """
        SELECT id, trade_id, exit_date, exit_price, shares, reason,
               realized_pnl, r_multiple, notes
        FROM exits WHERE trade_id = ? ORDER BY exit_date, id
        """,
        (trade_id,),
    ).fetchall()
    return [
        Exit(id=r[0], trade_id=r[1], exit_date=r[2], exit_price=r[3],
             shares=r[4], reason=r[5], realized_pnl=r[6], r_multiple=r[7], notes=r[8])
        for r in rows
    ]


def list_all_exits(conn: sqlite3.Connection) -> list[Exit]:
    rows = conn.execute(
        """
        SELECT id, trade_id, exit_date, exit_price, shares, reason,
               realized_pnl, r_multiple, notes
        FROM exits ORDER BY exit_date, id
        """,
    ).fetchall()
    return [
        Exit(id=r[0], trade_id=r[1], exit_date=r[2], exit_price=r[3],
             shares=r[4], reason=r[5], realized_pnl=r[6], r_multiple=r[7], notes=r[8])
        for r in rows
    ]


def list_events_for_trade(conn: sqlite3.Connection, trade_id: int) -> list[TradeEvent]:
    rows = conn.execute(
        """
        SELECT id, trade_id, ts, event_type, payload_json, rationale, notes
        FROM trade_events WHERE trade_id = ? ORDER BY ts, id
        """,
        (trade_id,),
    ).fetchall()
    return [
        TradeEvent(id=r[0], trade_id=r[1], ts=r[2], event_type=r[3],
                   payload_json=r[4], rationale=r[5], notes=r[6])
        for r in rows
    ]


def find_any_open_trade(
    conn: sqlite3.Connection, *, ticker: str,
) -> Trade | None:
    """For TOS CLOSE-fill reconciliation.

    Returns the OLDEST open trade for the ticker (FIFO policy, matching US tax-lot
    convention for long positions without explicit lot designation). Under the
    Phase 2 entry invariant (swing.trades.entry raises DuplicateOpenPositionException
    if a ticker already has an open position), there is at most one open trade
    per ticker — so FIFO here is the same as "the one".

    Phase 4 legacy import may theoretically violate this invariant if the legacy
    data has concurrent open positions. In that case, FIFO yields deterministic
    behavior; the caller should review the reconciliation report and use
    `swing trade exit --trade-id ...` with an explicit ID rather than auto-match.
    """
    row = conn.execute(
        """
        SELECT id, ticker, entry_date, entry_price, initial_shares, initial_stop,
               current_stop, status, watchlist_entry_target,
               watchlist_initial_stop, notes, hypothesis_label,
               chart_pattern_algo, chart_pattern_algo_confidence,
               chart_pattern_operator, chart_pattern_classification_pipeline_run_id
        FROM trades WHERE ticker=? AND status='open'
        ORDER BY entry_date ASC LIMIT 1
        """,
        (ticker,),
    ).fetchone()
    return _row_to_trade(row) if row else None


def find_open_trade_by_match(
    conn: sqlite3.Connection, *, ticker: str, entry_date: str,
    initial_shares: int | None = None,
) -> Trade | None:
    """For TOS reconciliation. Strict match on (ticker, entry_date, shares); fuzzy on (ticker, entry_date) if shares is None."""
    if initial_shares is not None:
        row = conn.execute(
            """
            SELECT id, ticker, entry_date, entry_price, initial_shares, initial_stop,
                   current_stop, status, watchlist_entry_target,
                   watchlist_initial_stop, notes, hypothesis_label,
                   chart_pattern_algo, chart_pattern_algo_confidence,
                   chart_pattern_operator, chart_pattern_classification_pipeline_run_id
            FROM trades WHERE ticker=? AND entry_date=? AND initial_shares=? AND status='open'
            LIMIT 1
            """,
            (ticker, entry_date, initial_shares),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT id, ticker, entry_date, entry_price, initial_shares, initial_stop,
                   current_stop, status, watchlist_entry_target,
                   watchlist_initial_stop, notes, hypothesis_label,
                   chart_pattern_algo, chart_pattern_algo_confidence,
                   chart_pattern_operator, chart_pattern_classification_pipeline_run_id
            FROM trades WHERE ticker=? AND entry_date=? AND status='open'
            LIMIT 1
            """,
            (ticker, entry_date),
        ).fetchone()
    return _row_to_trade(row) if row else None


def _row_to_trade(row: tuple) -> Trade:
    return Trade(
        id=row[0], ticker=row[1], entry_date=row[2], entry_price=row[3],
        initial_shares=row[4], initial_stop=row[5], current_stop=row[6],
        status=row[7], watchlist_entry_target=row[8],
        watchlist_initial_stop=row[9], notes=row[10],
        hypothesis_label=row[11],
        chart_pattern_algo=row[12],
        chart_pattern_algo_confidence=row[13],
        chart_pattern_operator=row[14],
        chart_pattern_classification_pipeline_run_id=row[15],
    )
