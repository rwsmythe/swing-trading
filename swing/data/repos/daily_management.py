"""Daily management records repo (Phase 8, migration 0016).

Two ``record_type`` values share the table:
  * ``daily_snapshot`` — pipeline-step-emitted (UPSERT keyed on
    ``(trade_id, data_asof_session, mfe_mae_precision_level)``); carries full
    position-state.
  * ``event_log`` — operator-discretionary (web POST); each emission is its
    own row; position-state OPTIONAL.

Public API split across multiple Phase 8 tasks:

  Task 2.0: ``insert_snapshot``, ``insert_event_log``
  Task 2.1: ``select_active_snapshot``
  Task 2.2: ``select_history``,
           ``list_for_trade_timeline``,
           ``list_open_position_active_snapshots``
  Task 2.3 (this file, latest): ``upsert_snapshot``, ``tier_upgrade_snapshot``
           + co-located exception classes
           (``SupersededRowImmutableException``, ``TierOrderingError``)
           + co-located ``DAILY_MGMT_PRECISION_RANK`` constant.

CLAUDE.md gotcha (2026-05-06) — the SQLite ``INSERT-OR-REPLACE`` form is
forbidden on this table because the REPLACE conflict-resolution clause is
``DELETE old + INSERT new`` semantically: it would cascade-wipe FK-linked
rows + reissue the auto-increment PK. T2.0's INSERTs are plain INSERTs;
T2.3's UPSERT goes through SELECT-then-UPDATE-or-INSERT against the ACTIVE
row only — REPLACE-conflict-clause is never used.

Module-organization choice (per plan §T2.3 note): exception classes
+ ``DAILY_MGMT_PRECISION_RANK`` are CO-LOCATED here (the repo module) rather
than in ``swing/trades/daily_management.py`` because:

  1. T2.3 lands BEFORE T3.0 — the trades module does not yet exist.
  2. Both exceptions are repo-layer audit-trail invariants (raised by repo
     code), not service-layer policy.
  3. T3.0 will import + re-export from here so callers may continue using
     ``swing.trades.daily_management`` as the public surface — no churn for
     downstream consumers.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from typing import Any

from swing.data.models import DailyManagementRecord


class SupersededRowImmutableException(Exception):  # noqa: N818  -- name fixed by Phase 8 spec §4.2 audit-stability contract
    """Raised when a write attempts to mutate a superseded row, OR when a
    same-tier reflow targets a tier where no active row exists but a
    superseded row at that same tier does. Per spec §6.1 audit-stability
    contract; CLAUDE.md gotcha 2026-05-06."""


class TierOrderingError(Exception):
    """Raised when ``tier_upgrade_snapshot`` is invoked with a new precision
    level that does not strictly outrank the predecessor's level per
    ``DAILY_MGMT_PRECISION_RANK``."""


# Precision-tier rank ordering (spec §3.3). Higher rank = more authoritative;
# tier-upgrade transitions must move strictly higher (rank_new > rank_pred).
# Co-located here because T2.3's repo-layer ``tier_upgrade_snapshot`` consumes
# it; T3.0's ``swing/trades/daily_management.py`` will re-export.
DAILY_MGMT_PRECISION_RANK: dict[str, int] = {
    "daily_approximate": 1,
    "intraday_estimated": 2,
    "intraday_exact": 3,
}

# Canonical 42-column SELECT list for daily_management_records, in the same
# field order as ``DailyManagementRecord`` so positional unpack into the
# dataclass remains stable. Mirrors Phase 7's ``_row_to_trade`` pattern.
_DMR_SELECT_COLS = (
    # Metadata (10):
    "management_record_id, trade_id, record_type, review_date, "
    "data_asof_session, created_at, mfe_mae_precision_level, "
    "pipeline_run_id, is_superseded, superseded_by_record_id, "
    # Position-state (14):
    "current_price, current_stop, current_size, current_avg_cost, "
    "open_R_effective, open_MFE_R_to_date, open_MAE_R_to_date, "
    "intraday_high, intraday_low, position_capital_utilization_pct, "
    "position_capital_denominator_dollars, "
    "position_portfolio_heat_contribution_dollars, "
    "maturity_stage, trail_MA_candidate_price, "
    # Trail-MA stamp/cache (2):
    "trail_MA_period_days, trail_MA_eligibility_flag, "
    # Operator-input (16):
    "thesis_status, prior_stop, new_stop, linked_trade_event_id, "
    "stop_changed, stop_change_reason, volume_behavior, "
    "relative_strength_status, market_regime_change, "
    "sector_condition_change, news_or_event_update, "
    "action_taken, action_reason, emotional_state, "
    "rule_violation_suspected, management_notes"
)


def _row_to_record(row: sqlite3.Row | tuple[Any, ...]) -> DailyManagementRecord:
    """Map a row selected via ``_DMR_SELECT_COLS`` to a ``DailyManagementRecord``."""
    return DailyManagementRecord(
        management_record_id=row[0],
        trade_id=row[1],
        record_type=row[2],
        review_date=row[3],
        data_asof_session=row[4],
        created_at=row[5],
        mfe_mae_precision_level=row[6],
        pipeline_run_id=row[7],
        is_superseded=row[8],
        superseded_by_record_id=row[9],
        current_price=row[10],
        current_stop=row[11],
        current_size=row[12],
        current_avg_cost=row[13],
        open_R_effective=row[14],
        open_MFE_R_to_date=row[15],
        open_MAE_R_to_date=row[16],
        intraday_high=row[17],
        intraday_low=row[18],
        position_capital_utilization_pct=row[19],
        position_capital_denominator_dollars=row[20],
        position_portfolio_heat_contribution_dollars=row[21],
        maturity_stage=row[22],
        trail_MA_candidate_price=row[23],
        trail_MA_period_days=row[24],
        trail_MA_eligibility_flag=row[25],
        thesis_status=row[26],
        prior_stop=row[27],
        new_stop=row[28],
        linked_trade_event_id=row[29],
        stop_changed=row[30],
        stop_change_reason=row[31],
        volume_behavior=row[32],
        relative_strength_status=row[33],
        market_regime_change=row[34],
        sector_condition_change=row[35],
        news_or_event_update=row[36],
        action_taken=row[37],
        action_reason=row[38],
        emotional_state=row[39],
        rule_violation_suspected=row[40],
        management_notes=row[41],
    )


def has_update_today_for_trades(
    conn: sqlite3.Connection,
    trade_ids: Iterable[int],
    *,
    session_date: str,
) -> set[int]:
    """Return the subset of ``trade_ids`` that have an OPERATOR-DRIVEN
    event_log entry whose ``review_date`` equals ``session_date``.

    Predicate:

      ``record_type = 'event_log'``
      AND ``is_superseded = 0``
      AND ``review_date = session_date``

    **3e.15 narrowed semantic (2026-05-10):** the original polish-bundle
    2026-05-09 predicate also matched ``daily_snapshot`` rows (both record
    types satisfied "updated today"). But the pipeline's ``_step_daily_
    management`` step writes a ``daily_snapshot`` row for EVERY open trade
    on every successful run, with ``review_date = last_completed_session
    (run_now)`` — so within hours of session start every open trade
    satisfies the old predicate and the badge collapses to "did pipeline
    run today?" — a question the existing pipeline-status banner already
    answers. Filtering to ``event_log`` only narrows the badge to mean
    "operator personally engaged with this trade today via the daily-
    management form." See ``docs/phase3e-todo.md`` 3e.15.

    **Session-anchor contract (polish-bundle 2026-05-09 Codex R1 Major #1
    fix):** ``session_date`` MUST equal the value the writers stamp into
    ``review_date``. Both writers — the pipeline ``record_snapshot`` in
    ``swing/trades/daily_management.py`` and the web route
    ``daily_management_event_post`` in ``swing/web/routes/trades.py`` —
    stamp ``review_date = last_completed_session(now).isoformat()`` per
    Phase 8 spec §4.5 / R3 Major #2 (canonical session anchor for
    daily-management records is the LAST COMPLETED NYSE session, not the
    forward-looking action session). Therefore badge readers MUST also pass
    ``session_date = last_completed_session(now).isoformat()``. The brief's
    earlier ``action_session_for_run`` reference was incorrect — those two
    functions diverge before market close, after market close, and on
    weekends/holidays. Pinning the read to ``last_completed_session``
    closes the read/write drift Codex R1 Major #1 surfaced.

    Empty ``trade_ids`` returns ``set()`` without hitting the DB.
    """
    ids = list(trade_ids)
    if not ids:
        return set()
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT DISTINCT trade_id FROM daily_management_records "
        f"WHERE trade_id IN ({placeholders}) "
        f"  AND record_type = 'event_log' "
        f"  AND is_superseded = 0 "
        f"  AND review_date = ?",
        (*ids, session_date),
    ).fetchall()
    return {int(r[0]) for r in rows}


def select_active_snapshot(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    data_asof_session: str,
) -> DailyManagementRecord | None:
    """Return the ACTIVE daily_snapshot row for ``(trade_id, data_asof_session)``.

    "Active" = ``record_type='daily_snapshot' AND is_superseded=0``. The
    partial unique index from migration 0016 guarantees at most one such row
    per ``(trade_id, data_asof_session, mfe_mae_precision_level)``; this
    function scopes to the snapshot discriminator and returns the single
    active row regardless of precision tier (callers needing tier-specific
    lookup should filter post-hoc, or use a more specific helper).

    Returns ``None`` if no active snapshot exists for the given key.
    """
    row = conn.execute(
        f"SELECT {_DMR_SELECT_COLS} FROM daily_management_records "
        f"WHERE trade_id = ? AND data_asof_session = ? "
        f"  AND record_type = 'daily_snapshot' AND is_superseded = 0",
        (trade_id, data_asof_session),
    ).fetchone()
    return _row_to_record(row) if row else None


def select_history(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    data_asof_session: str | None = None,
) -> list[DailyManagementRecord]:
    """Return the FULL audit chain for ``trade_id`` (incl. superseded rows).

    Spec §B file map: "full chain incl. superseded; ordered by ``created_at
    ASC, mfe_mae_precision_level ASC``". When ``data_asof_session`` is
    provided, scopes the chain to that single session; ``None`` returns all
    sessions for the trade.

    Distinct from ``list_for_trade_timeline`` (per-trade-detail UI surface
    with the Phase 8 spec §7.2 deterministic ``review_date / created_at /
    management_record_id`` tiebreak ordering).
    """
    if data_asof_session is None:
        rows = conn.execute(
            f"SELECT {_DMR_SELECT_COLS} FROM daily_management_records "
            f"WHERE trade_id = ? "
            f"ORDER BY created_at ASC, mfe_mae_precision_level ASC, "
            f"         management_record_id ASC",
            (trade_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT {_DMR_SELECT_COLS} FROM daily_management_records "
            f"WHERE trade_id = ? AND data_asof_session = ? "
            f"ORDER BY created_at ASC, mfe_mae_precision_level ASC, "
            f"         management_record_id ASC",
            (trade_id, data_asof_session),
        ).fetchall()
    return [_row_to_record(r) for r in rows]


def list_for_trade_timeline(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    include_superseded: bool = False,
) -> list[DailyManagementRecord]:
    """Drive the per-trade timeline drill-down per spec §7.2.

    Returns ``daily_snapshot`` + ``event_log`` rows interleaved
    chronologically. Default predicate ``is_superseded = 0`` (per spec §7.2
    visibility rule + Codex R3 Major #2 fix); ``include_superseded=True``
    returns the full chain so the UI can render the "show superseded"
    toggle.

    ORDER BY clause is canonical per spec §7.2 + plan acceptance criterion:
    ``(review_date ASC, created_at ASC, management_record_id ASC)`` —
    deterministic tiebreak via PK so same-second event_log emissions render
    in insertion order.
    """
    if include_superseded:
        rows = conn.execute(
            f"SELECT {_DMR_SELECT_COLS} FROM daily_management_records "
            f"WHERE trade_id = ? "
            f"ORDER BY review_date ASC, created_at ASC, "
            f"         management_record_id ASC",
            (trade_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT {_DMR_SELECT_COLS} FROM daily_management_records "
            f"WHERE trade_id = ? AND is_superseded = 0 "
            f"ORDER BY review_date ASC, created_at ASC, "
            f"         management_record_id ASC",
            (trade_id,),
        ).fetchall()
    return [_row_to_record(r) for r in rows]


def list_open_position_active_snapshots(
    conn: sqlite3.Connection,
) -> list[DailyManagementRecord]:
    """Drive the §7.1 dashboard tile feed — ONE active snapshot per OPEN trade.

    Predicate per spec §7.1: ``record_type = 'daily_snapshot'`` AND
    ``is_superseded = 0`` AND trade.state IN ``('entered', 'managing',
    'partial_exited')`` (active-trade enum mirroring
    ``swing.data.repos.trades._ACTIVE_STATES_SQL``). Closed/reviewed trades
    do NOT surface in the dashboard tile.

    JOIN against ``trades`` resolves the live state per Phase 7 + Phase 9 R1
    M4 lesson — snapshot rows do not carry trade.state, so an unjoined
    ``WHERE`` clause cannot exclude closed-trade snapshot rows that may
    persist after closure (per spec §6.10 closed-trade snapshot history is
    preserved verbatim).

    Ordering: deterministic by trade_id ASC. Per-trade row uniqueness is
    enforced by the partial-unique-index ``ix_daily_mgmt_active_snapshot``
    over ``(trade_id, data_asof_session, mfe_mae_precision_level) WHERE
    record_type='daily_snapshot' AND is_superseded=0`` — the dashboard tile
    consumes the latest active row per trade.
    """
    # Many DMR columns shadow trades-row columns (current_stop, current_size,
    # etc.) — qualify the SELECT list with the dmr alias so the JOIN doesn't
    # raise "ambiguous column name".
    qualified_cols = ", ".join(
        f"dmr.{c.strip()}" for c in _DMR_SELECT_COLS.split(",")
    )
    # Codex R1 Major 1 fix: clamp to LATEST data_asof_session per trade.
    # Daily snapshots are NOT superseded across sessions (the partial-unique
    # index over (trade_id, data_asof_session, mfe_mae_precision_level)
    # treats different sessions as distinct rows; both retain
    # is_superseded=0). Without this clamp, after multiple pipeline runs
    # over multiple days the query returns one row per (trade, session) —
    # duplicating tile rendering on the dashboard.
    #
    # Tie-break: V1 ships only ``daily_approximate``; if a future tier
    # upgrade lands an ``intraday_exact`` row in the SAME session, the
    # tier_upgrade_snapshot path supersedes the daily_approximate row, so
    # the is_superseded=0 filter alone selects the higher tier within the
    # latest session. The correlated subquery clamps the SESSION; the
    # is_superseded filter clamps the TIER within that session.
    rows = conn.execute(
        f"SELECT {qualified_cols} "
        f"FROM daily_management_records dmr "
        f"INNER JOIN trades t ON t.id = dmr.trade_id "
        f"WHERE dmr.record_type = 'daily_snapshot' "
        f"  AND dmr.is_superseded = 0 "
        f"  AND t.state IN ('entered', 'managing', 'partial_exited') "
        f"  AND dmr.data_asof_session = ("
        f"    SELECT MAX(d2.data_asof_session) "
        f"    FROM daily_management_records d2 "
        f"    WHERE d2.trade_id = dmr.trade_id "
        f"      AND d2.record_type = 'daily_snapshot' "
        f"      AND d2.is_superseded = 0"
        f"  ) "
        f"ORDER BY dmr.trade_id ASC",
    ).fetchall()
    return [_row_to_record(r) for r in rows]


def select_latest_active_snapshot_for_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
) -> DailyManagementRecord | None:
    """Return the LATEST active daily_snapshot row for ``trade_id``,
    clamped to its most-recent ``data_asof_session``.

    Mirrors ``list_open_position_active_snapshots``'s latest-session clamp
    + ``is_superseded=0`` tier-within-session selector. Used by 3e.8 Bundle 3
    composition surfaces that need a single trade's maturity_stage without
    knowing the session anchor (per-trade VM builders: build_open_positions_row,
    build_open_positions_expanded, build_trade_detail_vm).

    Returns ``None`` when no active snapshot exists (e.g., trade just opened
    and no pipeline run has stamped a daily_snapshot yet) — caller's rule
    layer is expected to no-op on the absent-snapshot path.

    Distinct from ``select_active_snapshot`` (which requires the caller to
    supply ``data_asof_session``); this helper bypasses that requirement by
    SELECT MAX-clamping the session at the DB layer.
    """
    qualified_cols = ", ".join(
        f"dmr.{c.strip()}" for c in _DMR_SELECT_COLS.split(",")
    )
    row = conn.execute(
        f"SELECT {qualified_cols} "
        f"FROM daily_management_records dmr "
        f"WHERE dmr.trade_id = ? "
        f"  AND dmr.record_type = 'daily_snapshot' "
        f"  AND dmr.is_superseded = 0 "
        f"  AND dmr.data_asof_session = ("
        f"    SELECT MAX(d2.data_asof_session) "
        f"    FROM daily_management_records d2 "
        f"    WHERE d2.trade_id = ? "
        f"      AND d2.record_type = 'daily_snapshot' "
        f"      AND d2.is_superseded = 0"
        f"  )",
        (trade_id, trade_id),
    ).fetchone()
    return _row_to_record(row) if row else None


def insert_snapshot(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    snapshot_fields: dict[str, Any],
) -> int:
    """Pure INSERT for ``record_type='daily_snapshot'``.

    Caller manages the outer transaction (``with conn:``).

    Caller MUST validate ``snapshot_fields`` per
    ``OPERATION_REQUIRED_FIELDS["snapshot_emit"]`` BEFORE calling this
    function — the repo layer trusts validated input. Optional keys default
    to NULL (``pipeline_run_id``, ``trail_MA_candidate_price``,
    ``trail_MA_period_days``).

    Returns the new ``management_record_id``.
    """
    cur = conn.execute(
        """
        INSERT INTO daily_management_records (
            trade_id, record_type, review_date, data_asof_session, created_at,
            mfe_mae_precision_level, pipeline_run_id, is_superseded,
            current_price, current_stop, current_size, current_avg_cost,
            open_R_effective, open_MFE_R_to_date, open_MAE_R_to_date,
            intraday_high, intraday_low,
            position_capital_utilization_pct,
            position_capital_denominator_dollars,
            position_portfolio_heat_contribution_dollars,
            maturity_stage, trail_MA_candidate_price,
            trail_MA_period_days, trail_MA_eligibility_flag
        ) VALUES (?, 'daily_snapshot', ?, ?, ?, ?, ?, 0,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade_id,
            snapshot_fields["review_date"],
            snapshot_fields["data_asof_session"],
            snapshot_fields["created_at"],
            snapshot_fields["mfe_mae_precision_level"],
            snapshot_fields.get("pipeline_run_id"),
            snapshot_fields["current_price"],
            snapshot_fields["current_stop"],
            snapshot_fields["current_size"],
            snapshot_fields["current_avg_cost"],
            snapshot_fields["open_R_effective"],
            snapshot_fields["open_MFE_R_to_date"],
            snapshot_fields["open_MAE_R_to_date"],
            snapshot_fields["intraday_high"],
            snapshot_fields["intraday_low"],
            snapshot_fields["position_capital_utilization_pct"],
            snapshot_fields["position_capital_denominator_dollars"],
            snapshot_fields["position_portfolio_heat_contribution_dollars"],
            snapshot_fields["maturity_stage"],
            snapshot_fields.get("trail_MA_candidate_price"),
            snapshot_fields.get("trail_MA_period_days"),
            snapshot_fields["trail_MA_eligibility_flag"],
        ),
    )
    return int(cur.lastrowid)


def insert_event_log(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    event_log_fields: dict[str, Any],
) -> int:
    """Pure INSERT for ``record_type='event_log'``. Position-state OPTIONAL.

    Caller manages the outer transaction (``with conn:``).

    Caller MUST validate per ``OPERATION_REQUIRED_FIELDS["event_log_emit"]``.
    Position-state fields (``current_price``, ``current_stop``, etc.) are
    OPTIONAL on event_log per spec §3.1.1 R1 Critical 1 — the operator can
    log a free-form event without committing to a fresh price/stop snapshot.

    Returns the new ``management_record_id``.
    """
    cur = conn.execute(
        """
        INSERT INTO daily_management_records (
            trade_id, record_type, review_date, data_asof_session, created_at,
            mfe_mae_precision_level, pipeline_run_id, is_superseded,
            current_price, current_stop, current_size, current_avg_cost,
            open_R_effective, open_MFE_R_to_date, open_MAE_R_to_date,
            intraday_high, intraday_low,
            position_capital_utilization_pct,
            position_capital_denominator_dollars,
            position_portfolio_heat_contribution_dollars,
            maturity_stage, trail_MA_candidate_price,
            trail_MA_period_days, trail_MA_eligibility_flag,
            thesis_status, prior_stop, new_stop, linked_trade_event_id,
            stop_changed, stop_change_reason,
            volume_behavior, relative_strength_status,
            market_regime_change, sector_condition_change,
            news_or_event_update,
            action_taken, action_reason, emotional_state,
            rule_violation_suspected, management_notes
        ) VALUES (?, 'event_log', ?, ?, ?, ?, ?, 0,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade_id,
            event_log_fields["review_date"],
            event_log_fields["data_asof_session"],
            event_log_fields["created_at"],
            event_log_fields["mfe_mae_precision_level"],
            event_log_fields.get("pipeline_run_id"),
            # Position-state — all optional on event_log:
            event_log_fields.get("current_price"),
            event_log_fields.get("current_stop"),
            event_log_fields.get("current_size"),
            event_log_fields.get("current_avg_cost"),
            event_log_fields.get("open_R_effective"),
            event_log_fields.get("open_MFE_R_to_date"),
            event_log_fields.get("open_MAE_R_to_date"),
            event_log_fields.get("intraday_high"),
            event_log_fields.get("intraday_low"),
            event_log_fields.get("position_capital_utilization_pct"),
            event_log_fields.get("position_capital_denominator_dollars"),
            event_log_fields.get(
                "position_portfolio_heat_contribution_dollars"
            ),
            event_log_fields.get("maturity_stage"),
            event_log_fields.get("trail_MA_candidate_price"),
            event_log_fields.get("trail_MA_period_days"),
            event_log_fields.get("trail_MA_eligibility_flag"),
            # Operator-input fields:
            event_log_fields.get("thesis_status"),
            event_log_fields.get("prior_stop"),
            event_log_fields.get("new_stop"),
            event_log_fields.get("linked_trade_event_id"),
            event_log_fields.get("stop_changed"),
            event_log_fields.get("stop_change_reason"),
            event_log_fields.get("volume_behavior"),
            event_log_fields.get("relative_strength_status"),
            event_log_fields.get("market_regime_change"),
            event_log_fields.get("sector_condition_change"),
            event_log_fields.get("news_or_event_update"),
            event_log_fields.get("action_taken"),
            event_log_fields.get("action_reason"),
            event_log_fields.get("emotional_state"),
            event_log_fields.get("rule_violation_suspected"),
            event_log_fields.get("management_notes"),
        ),
    )
    return int(cur.lastrowid)


def upsert_snapshot(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    snapshot_fields: dict[str, Any],
) -> int:
    """SELECT-then-UPDATE-or-INSERT against the active row only (spec §4.2).

    Same-tier reflow updates the active row in place — preserves
    ``management_record_id`` + ``is_superseded`` + ``superseded_by_record_id``
    chain. Higher-tier writes go through ``tier_upgrade_snapshot``, NOT this
    path.

    Caller manages the outer (deferred-mode) transaction — Codex R3 M2
    ``with conn:``.

    Caller MUST validate ``snapshot_fields`` per
    ``OPERATION_REQUIRED_FIELDS["snapshot_emit"]`` BEFORE calling. The repo
    layer trusts validated input — mirrors T2.0 ``insert_snapshot`` discipline.

    CLAUDE.md gotcha 2026-05-06 — this function MUST NOT use the SQLite
    REPLACE conflict-resolution clause. That clause is ``DELETE old + INSERT
    new`` semantically: it would cascade-wipe FK-linked rows (event_log
    audit-FK chains pointing at the prior PK) and mint a new auto-increment
    PK (history rewrite). The SELECT-then-UPDATE-or-INSERT pattern below
    preserves both.

    Raises:
        SupersededRowImmutableException — if no active row exists at the
            target ``(trade_id, data_asof_session, mfe_mae_precision_level)``
            but a superseded row does. Means tier-upgrade has already
            occurred at this tier; same-tier reflow is meaningless.

    Returns the (preserved or newly-minted) ``management_record_id``.
    """
    # Step 1: lookup active row at this tier (spec §4.2 + §A.6 partial-unique-
    # index predicate: record_type='daily_snapshot' AND is_superseded=0).
    cur = conn.execute(
        """
        SELECT management_record_id FROM daily_management_records
        WHERE trade_id = ? AND data_asof_session = ?
          AND mfe_mae_precision_level = ?
          AND record_type = 'daily_snapshot' AND is_superseded = 0
        """,
        (
            trade_id,
            snapshot_fields["data_asof_session"],
            snapshot_fields["mfe_mae_precision_level"],
        ),
    )
    row = cur.fetchone()
    if row is not None:
        existing_active_id = row[0]
        # Step 2: in-place UPDATE — preserves PK + audit-chain pointers.
        # Audit columns (record_type, is_superseded, superseded_by_record_id,
        # review_date, mfe_mae_precision_level, trade_id) are intentionally
        # NOT mutated by reflow — only data fields update.
        conn.execute(
            """
            UPDATE daily_management_records
            SET current_price = ?,
                current_stop = ?,
                current_size = ?,
                current_avg_cost = ?,
                open_R_effective = ?,
                open_MFE_R_to_date = ?,
                open_MAE_R_to_date = ?,
                intraday_high = ?,
                intraday_low = ?,
                position_capital_utilization_pct = ?,
                position_capital_denominator_dollars = ?,
                position_portfolio_heat_contribution_dollars = ?,
                maturity_stage = ?,
                trail_MA_candidate_price = ?,
                trail_MA_period_days = ?,
                trail_MA_eligibility_flag = ?,
                pipeline_run_id = ?,
                created_at = ?
            WHERE management_record_id = ?
            """,
            (
                snapshot_fields["current_price"],
                snapshot_fields["current_stop"],
                snapshot_fields["current_size"],
                snapshot_fields["current_avg_cost"],
                snapshot_fields["open_R_effective"],
                snapshot_fields["open_MFE_R_to_date"],
                snapshot_fields["open_MAE_R_to_date"],
                snapshot_fields["intraday_high"],
                snapshot_fields["intraday_low"],
                snapshot_fields["position_capital_utilization_pct"],
                snapshot_fields["position_capital_denominator_dollars"],
                snapshot_fields[
                    "position_portfolio_heat_contribution_dollars"
                ],
                snapshot_fields["maturity_stage"],
                snapshot_fields.get("trail_MA_candidate_price"),
                snapshot_fields.get("trail_MA_period_days"),
                snapshot_fields["trail_MA_eligibility_flag"],
                snapshot_fields.get("pipeline_run_id"),
                snapshot_fields["created_at"],
                existing_active_id,
            ),
        )
        return int(existing_active_id)

    # Step 3: no active row — check whether a superseded row exists at this
    # exact tier. If so, the active row was tier-upgraded away; same-tier
    # reflow is meaningless (audit-stability contract per spec §4.2/§6.1).
    cur = conn.execute(
        """
        SELECT 1 FROM daily_management_records
        WHERE trade_id = ? AND data_asof_session = ?
          AND mfe_mae_precision_level = ?
          AND record_type = 'daily_snapshot' AND is_superseded = 1
        LIMIT 1
        """,
        (
            trade_id,
            snapshot_fields["data_asof_session"],
            snapshot_fields["mfe_mae_precision_level"],
        ),
    )
    if cur.fetchone() is not None:
        raise SupersededRowImmutableException(
            f"trade {trade_id} session "
            f"{snapshot_fields['data_asof_session']!r} tier "
            f"{snapshot_fields['mfe_mae_precision_level']!r} has been "
            "tier-upgraded; same-tier reflow rejected."
        )

    # Step 4: fresh INSERT — same column shape as ``insert_snapshot``.
    cur = conn.execute(
        """
        INSERT INTO daily_management_records (
            trade_id, record_type, review_date, data_asof_session, created_at,
            mfe_mae_precision_level, pipeline_run_id, is_superseded,
            current_price, current_stop, current_size, current_avg_cost,
            open_R_effective, open_MFE_R_to_date, open_MAE_R_to_date,
            intraday_high, intraday_low,
            position_capital_utilization_pct,
            position_capital_denominator_dollars,
            position_portfolio_heat_contribution_dollars,
            maturity_stage, trail_MA_candidate_price,
            trail_MA_period_days, trail_MA_eligibility_flag
        ) VALUES (?, 'daily_snapshot', ?, ?, ?, ?, ?, 0,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade_id,
            snapshot_fields["review_date"],
            snapshot_fields["data_asof_session"],
            snapshot_fields["created_at"],
            snapshot_fields["mfe_mae_precision_level"],
            snapshot_fields.get("pipeline_run_id"),
            snapshot_fields["current_price"],
            snapshot_fields["current_stop"],
            snapshot_fields["current_size"],
            snapshot_fields["current_avg_cost"],
            snapshot_fields["open_R_effective"],
            snapshot_fields["open_MFE_R_to_date"],
            snapshot_fields["open_MAE_R_to_date"],
            snapshot_fields["intraday_high"],
            snapshot_fields["intraday_low"],
            snapshot_fields["position_capital_utilization_pct"],
            snapshot_fields["position_capital_denominator_dollars"],
            snapshot_fields["position_portfolio_heat_contribution_dollars"],
            snapshot_fields["maturity_stage"],
            snapshot_fields.get("trail_MA_candidate_price"),
            snapshot_fields.get("trail_MA_period_days"),
            snapshot_fields["trail_MA_eligibility_flag"],
        ),
    )
    return int(cur.lastrowid)


def tier_upgrade_snapshot(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    data_asof_session: str,
    new_precision_level: str,
    snapshot_fields: dict[str, Any],
) -> int:
    """6-step transactional sequence per spec §3.3.

    The audit-trail dual-column pattern: predecessor row keeps its data
    fields verbatim (NEVER updated post-supersede; immutability contract per
    spec §4.2), but its ``is_superseded`` flips to 1 and
    ``superseded_by_record_id`` is set to the new successor's PK. The
    successor is inserted as a fresh row at ``new_precision_level``.

    Caller manages the outer (deferred-mode) ``with conn:`` transaction —
    Codex R3 M2.

    Sequence (per plan §H pseudocode, verbatim):

      Step 0 (validator): new tier MUST strictly outrank predecessor's tier
                          (rank_new > rank_pred); else TierOrderingError.
      Step 1: BEGIN — caller's responsibility.
      Step 2: SELECT predecessor by partial-unique-index key.
      Step 3: flag predecessor.is_superseded = 1 BY EXACT PK.
      Step 4: INSERT successor at the new (higher) tier.
      Step 5: UPDATE predecessor.superseded_by_record_id = successor.PK.
      Step 6: COMMIT — caller's responsibility.

    Raises:
        TierOrderingError — new tier does not strictly outrank predecessor,
        OR no active daily_snapshot predecessor exists at any tier (Codex
        R1 Major 4: tier upgrades require a seeded predecessor; call
        ``upsert_snapshot`` first).

    Returns the new successor's ``management_record_id``.
    """
    # Step 0 + Step 2: SELECT predecessor (active row at any tier for this
    # session) to validate tier ordering AND capture the exact PK to flip.
    pred_row = conn.execute(
        """
        SELECT management_record_id, mfe_mae_precision_level
        FROM daily_management_records
        WHERE trade_id = ? AND data_asof_session = ?
          AND record_type = 'daily_snapshot' AND is_superseded = 0
        """,
        (trade_id, data_asof_session),
    ).fetchone()
    # Codex R1 Major 4 fix: tier_upgrade_snapshot REQUIRES a predecessor.
    # Without this guard, a direct call could land an intraday_exact (or
    # any higher-tier) active row with no daily_approximate root, breaking
    # the audit-chain "tier upgrade replaces existing active row" model.
    # The pipeline path always seeds via upsert_snapshot first; the guard
    # protects ad-hoc / future caller paths from quietly bypassing the
    # invariant.
    if pred_row is None:
        raise TierOrderingError(
            f"tier_upgrade_snapshot requires an existing active "
            f"daily_snapshot predecessor at a lower tier for "
            f"trade_id={trade_id}, data_asof_session={data_asof_session!r}; "
            f"got none. Call upsert_snapshot first to seed the "
            f"daily_approximate predecessor."
        )

    pred_level = pred_row[1]
    pred_rank = DAILY_MGMT_PRECISION_RANK[pred_level]
    new_rank = DAILY_MGMT_PRECISION_RANK[new_precision_level]
    if new_rank <= pred_rank:
        raise TierOrderingError(
            f"new tier {new_precision_level!r} (rank {new_rank}) must be "
            f"strictly higher than predecessor {pred_level!r} "
            f"(rank {pred_rank})"
        )

    predecessor_id = pred_row[0]

    # Step 3: flag predecessor superseded BY EXACT PK. Done BEFORE the
    # successor INSERT so the partial-unique-index predicate
    # (record_type='daily_snapshot' AND is_superseded=0) does not collide
    # with the existing predecessor row at (trade_id, data_asof_session).
    # predecessor_id is guaranteed non-None per the Codex R1 Major 4
    # invariant raised above.
    conn.execute(
        "UPDATE daily_management_records SET is_superseded = 1 "
        "WHERE management_record_id = ?",
        (predecessor_id,),
    )

    # Step 4: INSERT successor (fresh row at the new higher tier).
    cur = conn.execute(
        """
        INSERT INTO daily_management_records (
            trade_id, record_type, review_date, data_asof_session, created_at,
            mfe_mae_precision_level, pipeline_run_id, is_superseded,
            current_price, current_stop, current_size, current_avg_cost,
            open_R_effective, open_MFE_R_to_date, open_MAE_R_to_date,
            intraday_high, intraday_low,
            position_capital_utilization_pct,
            position_capital_denominator_dollars,
            position_portfolio_heat_contribution_dollars,
            maturity_stage, trail_MA_candidate_price,
            trail_MA_period_days, trail_MA_eligibility_flag
        ) VALUES (?, 'daily_snapshot', ?, ?, ?, ?, ?, 0,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade_id,
            snapshot_fields["review_date"],
            snapshot_fields["data_asof_session"],
            snapshot_fields["created_at"],
            new_precision_level,
            snapshot_fields.get("pipeline_run_id"),
            snapshot_fields["current_price"],
            snapshot_fields["current_stop"],
            snapshot_fields["current_size"],
            snapshot_fields["current_avg_cost"],
            snapshot_fields["open_R_effective"],
            snapshot_fields["open_MFE_R_to_date"],
            snapshot_fields["open_MAE_R_to_date"],
            snapshot_fields["intraday_high"],
            snapshot_fields["intraday_low"],
            snapshot_fields["position_capital_utilization_pct"],
            snapshot_fields["position_capital_denominator_dollars"],
            snapshot_fields["position_portfolio_heat_contribution_dollars"],
            snapshot_fields["maturity_stage"],
            snapshot_fields.get("trail_MA_candidate_price"),
            snapshot_fields.get("trail_MA_period_days"),
            snapshot_fields["trail_MA_eligibility_flag"],
        ),
    )
    successor_id = int(cur.lastrowid)

    # Step 5: UPDATE predecessor.superseded_by_record_id BY EXACT PK.
    # predecessor_id is guaranteed non-None per the Codex R1 Major 4
    # invariant raised above.
    conn.execute(
        "UPDATE daily_management_records "
        "SET superseded_by_record_id = ? "
        "WHERE management_record_id = ?",
        (successor_id, predecessor_id),
    )

    # Step 6: COMMIT — caller's responsibility.
    return successor_id
