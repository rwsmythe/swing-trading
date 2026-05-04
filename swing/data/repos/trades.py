"""Trades + trade_events repo (Phase 7 — exits → fills migration).

Every mutation of `trades` writes a `trade_events` row in the same transaction.
This is enforced by exposing only `*_with_event` mutation functions; there is no
`insert_trade` without `_with_event` companion.

Phase 7 (Sub-A T6) changes:
 - `status` (legacy 'open'|'closed') dropped end-to-end. The `state` column
   (CHECK enum: 'entered'|'managing'|'partial_exited'|'closed'|'reviewed') is
   the lifecycle field.
 - 23 new columns persisted in INSERT/SELECT (trade_origin, pre_trade_locked_at,
   current_size, current_avg_cost, last_fill_at, thesis, why_now,
   invalidation_condition, expected_scenario, premortem_*, event_*,
   gap_risk_*, emotional_state_pre_trade, market_regime, catalyst,
   catalyst_other_description).
 - `insert_exit_with_event` REMOVED. Exit data path moves to fills via
   `swing/data/repos/fills.py` (Sub-A T4).
 - `list_exits_for_trade` + `list_all_exits` SHIMMED on top of fills (return
   `_ExitLikeRow` NamedTuples preserving the legacy attribute surface). Shim is
   removable when Sub-B T9 (journal) + Sub-C T1 (web view models) and the other
   callers cited in plan §2.1 migrate to the fills repo.
 - Direct `UPDATE trades SET status='closed'` writes removed; the state-mutation
   service in `swing/trades/state.py` (Sub-A T5) is the sole `state` write path.
"""
from __future__ import annotations

import json
import sqlite3
from typing import NamedTuple

from swing.data.models import Trade, TradeEvent

# Active-trade state set — tickers with this state are NOT closed.
# Used by list_open_trades, find_any_open_trade, find_open_trade_by_match,
# and the update_stop_with_event atomic guard.
_ACTIVE_STATES_SQL = "('entered','managing','partial_exited')"
# Closed-or-reviewed state set — list_closed_trades returns both.
_CLOSED_STATES_SQL = "('closed','reviewed')"


# Full SELECT column list for trades. Defined once to avoid drift across the
# 5+ SELECT call-sites (recurring repo-SELECT-coverage bug per plan §2.1).
# Order MUST match _row_to_trade's positional indexing.
_TRADE_SELECT_COLS = """
    id, ticker, entry_date, entry_price, initial_shares, initial_stop,
    current_stop, state, watchlist_entry_target,
    watchlist_initial_stop, notes, hypothesis_label,
    chart_pattern_algo, chart_pattern_algo_confidence,
    chart_pattern_operator, chart_pattern_classification_pipeline_run_id,
    sector, industry,
    reviewed_at, mistake_tags, entry_grade, management_grade,
    exit_grade, process_grade, disqualifying_process_violation,
    realized_R_if_plan_followed, mistake_cost_confidence, lesson_learned,
    trade_origin, pre_trade_locked_at, current_size, current_avg_cost,
    last_fill_at,
    thesis, why_now, invalidation_condition, expected_scenario,
    premortem_technical, premortem_market_sector, premortem_execution,
    premortem_additional,
    event_risk_present, event_handling, event_type, event_date,
    gap_risk_present, gap_risk_handling, emotional_state_pre_trade,
    market_regime, catalyst, catalyst_other_description
"""


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
    if algo is None and conf is not None:
        raise ValueError(
            "chart_pattern invariant: chart_pattern_algo_confidence requires "
            "chart_pattern_algo NOT NULL (no orphan confidence)"
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
             current_stop, state, watchlist_entry_target,
             watchlist_initial_stop, notes, hypothesis_label,
             chart_pattern_algo, chart_pattern_algo_confidence,
             chart_pattern_operator,
             chart_pattern_classification_pipeline_run_id,
             sector, industry,
             trade_origin, pre_trade_locked_at, current_size,
             current_avg_cost, last_fill_at,
             thesis, why_now, invalidation_condition, expected_scenario,
             premortem_technical, premortem_market_sector,
             premortem_execution, premortem_additional,
             event_risk_present, event_handling, event_type, event_date,
             gap_risk_present, gap_risk_handling,
             emotional_state_pre_trade, market_regime, catalyst,
             catalyst_other_description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?)
        """,
        (
            trade.ticker, trade.entry_date, trade.entry_price,
            trade.initial_shares, trade.initial_stop, trade.current_stop,
            trade.state,
            trade.watchlist_entry_target, trade.watchlist_initial_stop,
            trade.notes, trade.hypothesis_label,
            trade.chart_pattern_algo, trade.chart_pattern_algo_confidence,
            trade.chart_pattern_operator,
            trade.chart_pattern_classification_pipeline_run_id,
            trade.sector, trade.industry,
            # Phase 7 lifecycle fields (NOT NULL in schema).
            trade.trade_origin, trade.pre_trade_locked_at, trade.current_size,
            trade.current_avg_cost, trade.last_fill_at,
            # Phase 7 pre-trade decision fields (all NULLABLE).
            trade.thesis, trade.why_now, trade.invalidation_condition,
            trade.expected_scenario,
            trade.premortem_technical, trade.premortem_market_sector,
            trade.premortem_execution, trade.premortem_additional,
            trade.event_risk_present, trade.event_handling,
            trade.event_type, trade.event_date,
            trade.gap_risk_present, trade.gap_risk_handling,
            trade.emotional_state_pre_trade, trade.market_regime,
            trade.catalyst, trade.catalyst_other_description,
        ),
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


def insert_exit_with_event(*args, **kwargs):
    """[T6 STUB] Phase 7 removes the exits table and this entry point.

    Sub-B T4 (exit service) routes exits through the fills repo's
    ``insert_fill_with_event`` (Sub-A T4) plus the state-mutation service
    ``swing.trades.state`` (Sub-A T5). Calling this function is a programming
    error; it is retained as an importable symbol only because many production
    modules (`swing/trades/exit.py`, journal/web/cli) and their tests import
    it at module load time. Removing the symbol cleanly would break test
    collection across ~9 files and prevent the fast-suite from running until
    Sub-B/Sub-C land.

    Removed when Sub-B T4 lands the exit-service rewrite (no remaining
    importer).
    """
    raise RuntimeError(
        "insert_exit_with_event removed in Phase 7 — use the fills repo "
        "(insert_fill_with_event) + state-transition service. Called with: "
        f"{args!r} {kwargs!r}"
    )


def update_stop_with_event(
    conn: sqlite3.Connection, *, trade_id: int, new_stop: float,
    event_ts: str, rationale: str | None = None,
    notes: str | None = None,
) -> None:
    """Update trades.current_stop + write 'stop_adjust' event in same txn.
    Phase 3c §4.4 / Phase 7 T6: atomic active-state guard closes the
    close-then-stop race. Missing or closed trade → ValueError, no event.
    """
    trade = get_trade(conn, trade_id)
    if trade is None:
        raise ValueError(f"trade {trade_id} not found")
    if trade.current_stop == new_stop:
        return  # no-op
    payload = {"old_stop": trade.current_stop, "new_stop": new_stop}
    cur = conn.execute(
        f"UPDATE trades SET current_stop = ? "
        f"WHERE id = ? AND state IN {_ACTIVE_STATES_SQL}",  # noqa: S608 (literal-only states)
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
        f"SELECT {_TRADE_SELECT_COLS} FROM trades WHERE id = ?",  # noqa: S608
        (trade_id,),
    ).fetchone()
    return _row_to_trade(row) if row else None


def list_open_trades(conn: sqlite3.Connection) -> list[Trade]:
    rows = conn.execute(
        f"SELECT {_TRADE_SELECT_COLS} FROM trades "  # noqa: S608
        f"WHERE state IN {_ACTIVE_STATES_SQL} "
        f"ORDER BY entry_date, ticker"
    ).fetchall()
    return [_row_to_trade(r) for r in rows]


def list_closed_trades(
    conn: sqlite3.Connection, *, since_date: str | None = None
) -> list[Trade]:
    """Return trades in 'closed' or 'reviewed' state (full lifecycle terminals).

    The since_date branch filters to trades that have a non-entry fill on/after
    the cutoff (analogue of the prior `EXISTS exits.exit_date >= ?` predicate).
    """
    if since_date:
        rows = conn.execute(
            f"SELECT {_TRADE_SELECT_COLS} FROM trades t "  # noqa: S608
            f"WHERE t.state IN {_CLOSED_STATES_SQL} "
            "  AND EXISTS (SELECT 1 FROM fills f "
            "              WHERE f.trade_id = t.id "
            "                AND f.action != 'entry' "
            "                AND substr(f.fill_datetime, 1, 10) >= ?) "
            "ORDER BY t.entry_date DESC, t.ticker",
            (since_date,),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT {_TRADE_SELECT_COLS} FROM trades "  # noqa: S608
            f"WHERE state IN {_CLOSED_STATES_SQL} "
            "ORDER BY entry_date DESC, ticker"
        ).fetchall()
    return [_row_to_trade(r) for r in rows]


# ---------------------------------------------------------------------------
# Phase 7 T6 fills-backed shim — Exit-shape rows for Sub-B/Sub-C callers
# ---------------------------------------------------------------------------


class _ExitLikeRow(NamedTuple):
    """Shape-compatible Exit replacement for Sub-B/Sub-C callers.

    Mirrors the legacy `Exit` dataclass attribute surface (`.exit_date`,
    `.exit_price`, `.shares`, `.reason`, `.realized_pnl`, `.r_multiple`,
    `.notes`) so existing consumers (web view models, journal, equity math,
    pipeline runner, recommendations, parity fetcher, equity calculator)
    keep working until they migrate to the fills repo helpers.

    Removed in tandem with `list_exits_for_trade` + `list_all_exits` once
    Sub-B T9 (journal) + Sub-C T1 (web view models) + the remaining callers
    cited in plan §2.1 finish their predicate rewrites.
    """
    trade_id: int
    exit_date: str
    exit_price: float
    shares: int
    reason: str | None
    realized_pnl: float | None
    r_multiple: float | None
    notes: str | None


def _fill_row_to_exitlike(
    fill_row: tuple, *, entry_price: float | None, initial_stop: float | None,
) -> _ExitLikeRow:
    """Map a fills row tuple to the Exit-shape NamedTuple.

    fills column order: trade_id, fill_datetime, quantity, price, reason
    (the SELECT below pins this; do not reorder without updating).

    realized_pnl = (fill_price - entry_price) * quantity (long-only convention,
    matching the legacy Exit math). r_multiple = realized_pnl / (risk_per_share
    * quantity) where risk_per_share = entry_price - initial_stop. Both are
    None if the prerequisites are missing.
    """
    trade_id, fill_dt, qty, fill_price, reason = fill_row
    # exit_date is the YYYY-MM-DD prefix of fill_datetime (which is
    # ISO-8601 'YYYY-MM-DDTHH:MM:SS' per migration 0014 backfill).
    exit_date = fill_dt.split("T")[0] if "T" in fill_dt else fill_dt
    realized_pnl: float | None
    r_multiple: float | None
    if entry_price is not None:
        realized_pnl = (fill_price - entry_price) * qty
        risk_per_share = (
            entry_price - initial_stop
            if initial_stop is not None else None
        )
        if risk_per_share is not None and risk_per_share != 0 and qty != 0:
            r_multiple = realized_pnl / (risk_per_share * qty)
        else:
            r_multiple = None
    else:
        realized_pnl = None
        r_multiple = None
    return _ExitLikeRow(
        trade_id=trade_id,
        exit_date=exit_date,
        exit_price=float(fill_price),
        shares=int(qty),
        reason=reason,
        realized_pnl=realized_pnl,
        r_multiple=r_multiple,
        notes=None,  # fills schema has no separate notes column post-Phase-7
    )


def list_exits_for_trade(
    conn: sqlite3.Connection, trade_id: int,
) -> list[_ExitLikeRow]:
    """[T6 SHIM] Phase 7 deprecates the exits table.

    Returns fills-backed Exit-shape rows for Sub-B/Sub-C callers that have
    not yet migrated. Filters action != 'entry' so the synthetic entry-fill
    backfilled by migration 0014 does not surface as an exit.

    Removed when Sub-B T9 (journal) + Sub-C T1 (web view models) rewrite
    their callers to use a fills-repo helper directly.
    """
    fill_rows = conn.execute(
        "SELECT trade_id, fill_datetime, quantity, price, reason "
        "FROM fills WHERE trade_id = ? AND action != 'entry' "
        "ORDER BY fill_datetime ASC, fill_id ASC",
        (trade_id,),
    ).fetchall()
    if not fill_rows:
        return []
    entry_row = conn.execute(
        "SELECT entry_price, initial_stop FROM trades WHERE id = ?",
        (trade_id,),
    ).fetchone()
    if entry_row is None:
        return []
    entry_price, initial_stop = entry_row
    return [
        _fill_row_to_exitlike(r, entry_price=entry_price, initial_stop=initial_stop)
        for r in fill_rows
    ]


def list_all_exits(conn: sqlite3.Connection) -> list[_ExitLikeRow]:
    """[T6 SHIM] Same as list_exits_for_trade but across all trades.

    Implementation joins fills→trades to fetch entry_price/initial_stop in a
    single query (avoiding N+1).
    """
    rows = conn.execute(
        "SELECT f.trade_id, f.fill_datetime, f.quantity, f.price, f.reason, "
        "       t.entry_price, t.initial_stop "
        "FROM fills f JOIN trades t ON t.id = f.trade_id "
        "WHERE f.action != 'entry' "
        "ORDER BY substr(f.fill_datetime, 1, 10) ASC, f.fill_id ASC"
    ).fetchall()
    out: list[_ExitLikeRow] = []
    for r in rows:
        fill_tuple = (r[0], r[1], r[2], r[3], r[4])
        out.append(_fill_row_to_exitlike(
            fill_tuple, entry_price=r[5], initial_stop=r[6],
        ))
    return out


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

    Returns the OLDEST active trade for the ticker (FIFO policy, matching US
    tax-lot convention for long positions). Phase 7 T6: active-state predicate
    replaces the legacy `status='open'` filter.
    """
    row = conn.execute(
        f"SELECT {_TRADE_SELECT_COLS} FROM trades "  # noqa: S608
        f"WHERE ticker = ? AND state IN {_ACTIVE_STATES_SQL} "
        "ORDER BY entry_date ASC LIMIT 1",
        (ticker,),
    ).fetchone()
    return _row_to_trade(row) if row else None


def find_open_trade_by_match(
    conn: sqlite3.Connection, *, ticker: str, entry_date: str,
    initial_shares: int | None = None,
) -> Trade | None:
    """For TOS reconciliation.

    Strict match on (ticker, entry_date, shares); fuzzy on (ticker, entry_date)
    if shares is None. Phase 7 T6: active-state predicate replaces
    `status='open'`.
    """
    if initial_shares is not None:
        row = conn.execute(
            f"SELECT {_TRADE_SELECT_COLS} FROM trades "  # noqa: S608
            f"WHERE ticker = ? AND entry_date = ? AND initial_shares = ? "
            f"  AND state IN {_ACTIVE_STATES_SQL} "
            "LIMIT 1",
            (ticker, entry_date, initial_shares),
        ).fetchone()
    else:
        row = conn.execute(
            f"SELECT {_TRADE_SELECT_COLS} FROM trades "  # noqa: S608
            f"WHERE ticker = ? AND entry_date = ? "
            f"  AND state IN {_ACTIVE_STATES_SQL} "
            "LIMIT 1",
            (ticker, entry_date),
        ).fetchone()
    return _row_to_trade(row) if row else None


def _row_to_trade(row: tuple) -> Trade:
    """Map a SELECT row (column order = _TRADE_SELECT_COLS) to a Trade.

    Index map (must match _TRADE_SELECT_COLS):
      0:id 1:ticker 2:entry_date 3:entry_price 4:initial_shares 5:initial_stop
      6:current_stop 7:state 8:watchlist_entry_target 9:watchlist_initial_stop
      10:notes 11:hypothesis_label 12:chart_pattern_algo
      13:chart_pattern_algo_confidence 14:chart_pattern_operator
      15:chart_pattern_classification_pipeline_run_id 16:sector 17:industry
      18:reviewed_at 19:mistake_tags 20:entry_grade 21:management_grade
      22:exit_grade 23:process_grade 24:disqualifying_process_violation
      25:realized_R_if_plan_followed 26:mistake_cost_confidence 27:lesson_learned
      28:trade_origin 29:pre_trade_locked_at 30:current_size 31:current_avg_cost
      32:last_fill_at
      33:thesis 34:why_now 35:invalidation_condition 36:expected_scenario
      37:premortem_technical 38:premortem_market_sector 39:premortem_execution
      40:premortem_additional
      41:event_risk_present 42:event_handling 43:event_type 44:event_date
      45:gap_risk_present 46:gap_risk_handling 47:emotional_state_pre_trade
      48:market_regime 49:catalyst 50:catalyst_other_description
    """
    dpv = row[24]
    return Trade(
        id=row[0], ticker=row[1], entry_date=row[2], entry_price=row[3],
        initial_shares=row[4], initial_stop=row[5], current_stop=row[6],
        state=row[7], watchlist_entry_target=row[8],
        watchlist_initial_stop=row[9], notes=row[10],
        hypothesis_label=row[11],
        chart_pattern_algo=row[12],
        chart_pattern_algo_confidence=row[13],
        chart_pattern_operator=row[14],
        chart_pattern_classification_pipeline_run_id=row[15],
        sector=row[16], industry=row[17],
        reviewed_at=row[18],
        mistake_tags=row[19],
        entry_grade=row[20],
        management_grade=row[21],
        exit_grade=row[22],
        process_grade=row[23],
        disqualifying_process_violation=bool(dpv) if dpv is not None else None,
        realized_R_if_plan_followed=row[25],
        mistake_cost_confidence=row[26],
        lesson_learned=row[27],
        trade_origin=row[28] if row[28] is not None else "manual_off_pipeline",
        pre_trade_locked_at=row[29] if row[29] is not None else "",
        current_size=row[30] if row[30] is not None else 0.0,
        current_avg_cost=row[31],
        last_fill_at=row[32],
        thesis=row[33],
        why_now=row[34],
        invalidation_condition=row[35],
        expected_scenario=row[36],
        premortem_technical=row[37],
        premortem_market_sector=row[38],
        premortem_execution=row[39],
        premortem_additional=row[40],
        event_risk_present=row[41],
        event_handling=row[42],
        event_type=row[43],
        event_date=row[44],
        gap_risk_present=row[45],
        gap_risk_handling=row[46],
        emotional_state_pre_trade=row[47],
        market_regime=row[48],
        catalyst=row[49],
        catalyst_other_description=row[50],
    )


def update_trade_review_fields(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    reviewed_at: str,
    mistake_tags_json: str,
    entry_grade: str,
    management_grade: str,
    exit_grade: str,
    process_grade: str,
    disqualifying_process_violation: bool | None,
    realized_R_if_plan_followed: float | None,  # noqa: N803
    mistake_cost_confidence: str,
    lesson_learned: str,
) -> None:
    """UPDATE the 10 review fields atomically. Caller wraps in `with conn:`.
    All 10 fields written together — partial-state review rows are not valid.
    mistake_tags_json must be canonicalized by caller.
    Missing trade_id raises ValueError."""
    cur = conn.execute(
        """
        UPDATE trades SET
            reviewed_at = ?,
            mistake_tags = ?,
            entry_grade = ?,
            management_grade = ?,
            exit_grade = ?,
            process_grade = ?,
            disqualifying_process_violation = ?,
            realized_R_if_plan_followed = ?,
            mistake_cost_confidence = ?,
            lesson_learned = ?
        WHERE id = ?
        """,
        (reviewed_at, mistake_tags_json, entry_grade, management_grade,
         exit_grade, process_grade,
         (None if disqualifying_process_violation is None
          else (1 if disqualifying_process_violation else 0)),
         realized_R_if_plan_followed, mistake_cost_confidence,
         lesson_learned, trade_id),
    )
    if cur.rowcount == 0:
        raise ValueError(f"trade {trade_id} not found")
