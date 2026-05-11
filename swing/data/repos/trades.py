"""Trades + trade_events repo (Phase 7 — exits → fills migration).

Every mutation of `trades` writes a `trade_events` row in the same transaction.
This is enforced by exposing only `*_with_event` mutation functions; there is no
`insert_trade` without `_with_event` companion.

Phase 7 (Sub-A T6 + Sub-C C.14) changes:
 - `status` (legacy 'open'|'closed') dropped end-to-end. The `state` column
   (CHECK enum: 'entered'|'managing'|'partial_exited'|'closed'|'reviewed') is
   the lifecycle field.
 - 23 new columns persisted in INSERT/SELECT (trade_origin, pre_trade_locked_at,
   current_size, current_avg_cost, last_fill_at, thesis, why_now,
   invalidation_condition, expected_scenario, premortem_*, event_*,
   gap_risk_*, emotional_state_pre_trade, market_regime, catalyst,
   catalyst_other_description).
 - `insert_exit_with_event` DELETED (Sub-C C.14). Exit data path lives in
   `swing/data/repos/fills.py`'s `insert_fill_with_event` (Sub-A T4) plus
   the state-mutation service in `swing/trades/state.py` (Sub-A T5).
 - `list_exits_for_trade` + `list_all_exits` + `_ExitLikeRow` DELETED
   (Sub-C C.14). Consumers source non-entry fills directly via
   `swing/data/repos/fills.py::list_fills_for_trade` /
   `list_all_fills` and reconstruct realized_pnl / r_multiple via
   per-module `_list_all_exitshape_via_fills` adapters that wrap
   `swing/trades/derived_metrics.py` (single source of math truth).
 - Direct `UPDATE trades SET status='closed'` writes removed; the state-mutation
   service in `swing/trades/state.py` (Sub-A T5) is the sole `state` write path.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

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
    market_regime, catalyst, catalyst_other_description,
    planned_target_R
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

    WARNING (Phase 7 R2 Minor 1): Callers MUST follow this with
    ``swing.data.repos.fills.insert_fill_with_event`` (action='entry') in
    the same transaction. Skipping the fill leaves ``trades.current_size``
    at 0, ``current_avg_cost`` NULL, ``last_fill_at`` NULL — incorrect
    aggregate denorm state. The canonical atomic flow lives in
    ``swing.trades.entry.record_entry`` (Sub-B Task B.3); other call sites
    must replicate the pattern.
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
             catalyst_other_description,
             planned_target_R)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?,
                ?)
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
            # Phase 8 (migration 0016) — pre-trade-locked R-multiple target.
            trade.planned_target_R,
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
      51:planned_target_R (Phase 8 / migration 0016)
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
        planned_target_R=row[51],
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


# ---------------------------------------------------------------------------
# 3e.16 — cadence-review trade-activity summary helper.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TradeActivitySummary:
    """One row of ``list_trades_with_activity_in_period`` output.

    Locked field set per 3e.16 dispatch brief §0.3 #3. Consumed by
    ``swing/web/view_models/trades.py::build_cadence_complete_vm`` to render
    the per-trade summary section on the cadence completion form.
    """
    trade_id: int
    ticker: str
    entry_date: str
    entry_price: float
    exit_date: str | None
    exit_price: float | None
    realized_R: float | None  # noqa: N815 — operator-facing R-multiple convention
    hypothesis_label: str | None
    state_tag: str  # '[OPENED]' / '[CLOSED]' / '[EVENT]' / '[OPENED+CLOSED]'
    activity_ts: str  # ISO datetime used for ASC chronological ordering


def _share_weighted_realized_r(
    *,
    entry_price: float,
    initial_stop: float,
    initial_shares: int,
    fills: list[tuple[float, float]],  # (exit_price, quantity)
) -> float | None:
    """Mirror of ``swing.trades.review.compute_actual_realized_R_effective``.

    Re-implemented in the repo layer (per Phase 6 §A.1 byte-identical pattern)
    so the helper does not import from the trades-service layer. Formula:
        share_weighted_R = sum_i (r_multiple_i * quantity_i / initial_shares)
    where r_multiple_i = (exit_price_i - entry_price) / (entry_price - initial_stop).
    Returns None for ill-defined math (zero risk-per-share or zero shares).
    """
    risk_per_share = entry_price - initial_stop
    if risk_per_share == 0 or initial_shares == 0:
        return None
    total = 0.0
    for exit_price, quantity in fills:
        if quantity == 0:
            continue
        r_mult = (exit_price - entry_price) / risk_per_share
        total += r_mult * (quantity / initial_shares)
    return total


def list_trades_with_activity_in_period(
    conn: sqlite3.Connection,
    *,
    period_start: str,  # ISO date YYYY-MM-DD
    period_end: str,    # ISO date YYYY-MM-DD (inclusive)
) -> list[TradeActivitySummary]:
    """Return distinct trades with at least one activity (entry, exit,
    or trade_event) inside [period_start, period_end] inclusive, ordered
    by activity_ts ASC.

    Contract per 3e.16 dispatch brief §0.3 #6. The three predicates are:

      * was_opened_in_period: ``entry_date >= ps AND entry_date <= pe``
      * was_closed_in_period: trade is in terminal state
        (``'closed'`` or ``'reviewed'``) AND the LAST non-entry fill
        across all time falls in-period (Codex R2 Major #1 fix). The
        prior implementation tested "any non-entry fill in-period",
        which incorrectly tagged the April cadence review as [CLOSED]
        for a trade that trimmed in April but exited in May — by April
        review time the trade is terminally closed AND has a non-entry
        (trim) fill in-period, but the actual close happened later.
        A 'trim' fill on a still-open trade also does not qualify
        (state-not-terminal) — that case falls through to [EVENT] via
        the paired trade_events row. Phase 7 fills are the
        source-of-truth for exit dates; the ``exits`` table is dropped.
      * had_event_in_period: any ``trade_events`` row with ``ts``
        in the half-open interval ``[ps||'T00:00:00', (pe+1day)||'T00:00:00')``
        (Codex R2 Major #2 — half-open form is fully inclusive of
        fractional-second datetimes like ``2026-04-30T23:59:59.500000``;
        sargable against the ``(trade_id, ts)`` composite index per
        brief watch-item; ANY event_type counts — operator wants to see
        "this trade was touched during the period" regardless of
        event_type per brief §3.1 watch items).

    ``state_tag`` priority: OPENED+CLOSED > OPENED > CLOSED > EVENT (the
    same-period round-trip case renders as the concatenated form). A trade
    opened in period that also has trade_events is tagged ``[OPENED]``, not
    ``[OPENED+EVENT]`` — the entry IS the event.

    ``activity_ts`` priority (latest relevant activity in period; per
    brief §0.3 #4 plus Codex R3 Major #1 fill-fallback):

      1. ``was_closed_in_period`` → ``latest_exit_date_in_period||'T23:59:59'``
      2. ``had_event_in_period`` → ``latest_event_ts_in_period``
      3. ``has_non_entry_fill_in_period`` (R3 fix) →
         ``latest_in_period_fill_ts``. Production exit-service writes
         ``fill_datetime`` and the paired ``trade_events.ts`` separately
         (fill_datetime tracks exit_date; event_ts tracks operator
         submit time), so they can diverge — a fill in-period whose
         paired event is out-of-period would otherwise fall through to
         ``entry_date||'T00:00:00'`` (possibly months earlier).
      4. ``was_opened_in_period`` → ``entry_date||'T00:00:00'``

    The string is used purely for ASC chronological ordering; consumers
    should not interpret it as the trade's canonical timestamp (exit
    fills carry their own ``fill_datetime``). Sort is stable on
    ``(activity_ts, ticker, trade_id)`` so identical activity_ts strings
    (multi-trade same-day exits) render deterministically.

    ``realized_R`` is the share-weighted R-multiple per
    ``compute_actual_realized_R_effective`` semantics. NULL for trades whose
    DB ``state`` is not yet ``'closed'``/``'reviewed'`` (still-open trades
    show ``None`` even if a partial-exit fill landed in-period).

    Note on Phase 7 fills source-of-truth: ``_list_all_exitshape_via_fills``
    (web view-model layer) is the canonical adapter for the "non-entry fills
    as exits" abstraction. This helper does not import that adapter because
    it lives in the web layer; instead the same ``action != 'entry'``
    predicate is applied directly against the ``fills`` table per the
    byte-identical re-implementation pattern (brief §3.1 A.AC.6, Phase 6
    §A.1 lesson). Any future change to the adapter's "non-entry =
    exit-shape" definition MUST be mirrored here.
    """
    # Brief §3.1 watch-item: trade_events.ts is ISO datetime; period_end is
    # ISO date. Use half-open range predicates against the next-day
    # midnight upper bound: fully inclusive of fractional-second datetimes
    # (Codex R2 Major #2) AND sargable against the (trade_id, ts)
    # composite index (Codex R1 Major #2).
    from datetime import date as _date
    from datetime import timedelta as _timedelta
    period_start_ts = f"{period_start}T00:00:00"
    period_end_exclusive_ts = (
        _date.fromisoformat(period_end) + _timedelta(days=1)
    ).isoformat() + "T00:00:00"

    # 1. Find candidate trade_ids via UNION across the three predicates.
    # NOTE: the trade_events / fills branches of the candidate UNION can't
    # leverage the (trade_id, ts) composite index because trade_id is not
    # constrained at this step — these are necessarily table scans (sargable
    # on ts, but the leading composite-index column is absent). The
    # per-trade probes further down DO leverage the index.
    candidate_rows = conn.execute(
        """
        SELECT DISTINCT trade_id FROM (
            SELECT id AS trade_id FROM trades
              WHERE entry_date >= ? AND entry_date <= ?
            UNION
            SELECT trade_id FROM fills
              WHERE action != 'entry'
                AND fill_datetime >= ? AND fill_datetime < ?
            UNION
            SELECT trade_id FROM trade_events
              WHERE ts >= ? AND ts < ?
        )
        """,
        (
            period_start, period_end,
            period_start_ts, period_end_exclusive_ts,
            period_start_ts, period_end_exclusive_ts,
        ),
    ).fetchall()
    if not candidate_rows:
        return []

    summaries: list[TradeActivitySummary] = []
    for (trade_id,) in candidate_rows:
        trade = get_trade(conn, trade_id)
        if trade is None:
            # Orphan event/fill with no parent trade — defensive skip.
            continue

        # was_opened_in_period (entry_date inclusive on both ends)
        was_opened = period_start <= trade.entry_date <= period_end

        # Codex R2 Major #1: was_closed_in_period requires the LAST
        # non-entry fill (across all time, not just in-period) to fall
        # in-period AND the trade to be in terminal state. This
        # distinguishes "the closing fill landed in this period" from
        # "any historical non-entry fill happens to be in this period"
        # — the latter would mis-tag a trim-in-April + exit-in-May trade
        # as [CLOSED] when the April cadence review opens (terminal-state
        # + has-in-period-fill is True under the prior heuristic).
        was_closed_in_period = False
        latest_exit_date_in_period: str | None = None
        if trade.state in ("closed", "reviewed"):
            last_fill_row = conn.execute(
                """
                SELECT MAX(fill_datetime) FROM fills
                WHERE trade_id = ? AND action != 'entry'
                """,
                (trade_id,),
            ).fetchone()
            last_fill_ts_all_time = last_fill_row[0]
            if (
                last_fill_ts_all_time is not None
                and period_start_ts <= last_fill_ts_all_time < period_end_exclusive_ts
            ):
                was_closed_in_period = True
                latest_exit_date_in_period = (
                    last_fill_ts_all_time.split("T")[0]
                    if "T" in last_fill_ts_all_time
                    else last_fill_ts_all_time
                )

        # Latest trade_events.ts INSIDE period (used for [EVENT] activity_ts).
        # Range-form half-open predicate against (trade_id, ts) composite index.
        row = conn.execute(
            """
            SELECT MAX(ts) FROM trade_events
            WHERE trade_id = ?
              AND ts >= ? AND ts < ?
            """,
            (trade_id, period_start_ts, period_end_exclusive_ts),
        ).fetchone()
        latest_event_ts_in_period = row[0]
        had_event_in_period = latest_event_ts_in_period is not None

        # Latest in-period NON-ENTRY fill ts (independent of close-state
        # gating). Codex R3 Major #1: in production the exit service
        # writes fill_datetime and the paired trade_events.ts as
        # separately-supplied arguments, so they can diverge. A fill
        # in-period whose paired event is out-of-period would otherwise
        # fall through to entry_date midnight as activity_ts (possibly
        # months earlier). This probe gives the [EVENT] branch a sane
        # in-period anchor for that case.
        row = conn.execute(
            """
            SELECT MAX(fill_datetime) FROM fills
            WHERE trade_id = ? AND action != 'entry'
              AND fill_datetime >= ? AND fill_datetime < ?
            """,
            (trade_id, period_start_ts, period_end_exclusive_ts),
        ).fetchone()
        latest_in_period_fill_ts = row[0]

        # state_tag derivation (brief §0.3 #2 priority).
        if was_opened and was_closed_in_period:
            state_tag = "[OPENED+CLOSED]"
        elif was_opened:
            state_tag = "[OPENED]"
        elif was_closed_in_period:
            state_tag = "[CLOSED]"
        else:
            state_tag = "[EVENT]"

        # activity_ts derivation (brief §0.3 #4 priority + R3 fill-fallback).
        if was_closed_in_period:
            activity_ts = f"{latest_exit_date_in_period}T23:59:59"
        elif had_event_in_period:
            activity_ts = latest_event_ts_in_period
        elif latest_in_period_fill_ts is not None:
            # Codex R3 Major #1: in-period non-entry fill whose paired
            # event ts diverged out-of-period. Anchor on the fill ts.
            activity_ts = latest_in_period_fill_ts
        else:
            # was_opened MUST be True (else trade_id wouldn't be in candidate set).
            activity_ts = f"{trade.entry_date}T00:00:00"

        # Trade-level exit fields + realized_R: populated only when the trade
        # itself is fully closed (state in 'closed'/'reviewed'). Uses ALL
        # non-entry fills (not just in-period ones) because operator wants to
        # see the trade's actual realized outcome.
        exit_date: str | None = None
        exit_price: float | None = None
        realized_r: float | None = None
        if trade.state in ("closed", "reviewed"):
            exit_rows = conn.execute(
                """
                SELECT fill_datetime, price, quantity FROM fills
                WHERE trade_id = ? AND action != 'entry'
                ORDER BY fill_datetime ASC, fill_id ASC
                """,
                (trade_id,),
            ).fetchall()
            if exit_rows:
                latest = exit_rows[-1]
                exit_date = latest[0].split("T")[0] if "T" in latest[0] else latest[0]
                exit_price = float(latest[1])
                realized_r = _share_weighted_realized_r(
                    entry_price=trade.entry_price,
                    initial_stop=trade.initial_stop,
                    initial_shares=trade.initial_shares,
                    fills=[(float(r[1]), float(r[2])) for r in exit_rows],
                )

        summaries.append(TradeActivitySummary(
            trade_id=trade_id,
            ticker=trade.ticker,
            entry_date=trade.entry_date,
            entry_price=trade.entry_price,
            exit_date=exit_date,
            exit_price=exit_price,
            realized_R=realized_r,
            hypothesis_label=trade.hypothesis_label,
            state_tag=state_tag,
            activity_ts=activity_ts,
        ))

    # Codex R1 Major #4: secondary sort keys (ticker, trade_id) make ties
    # deterministic when multiple trades share the same activity_ts string
    # (multi-trade same-day closes collapse to YYYY-MM-DDT23:59:59).
    summaries.sort(key=lambda s: (s.activity_ts, s.ticker, s.trade_id))
    return summaries
