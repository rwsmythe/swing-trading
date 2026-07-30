"""latch_order_intents repository (migration 0033, Phase 21 Arc 21-B).

APPEND-ONLY. The table's own triggers ABORT every UPDATE and every DELETE, so
there is no update path here by construction -- a correction is a NEW row.

Caller-controlled tx discipline: these functions issue NO BEGIN/COMMIT/ROLLBACK;
the route owns `with conn:`.

SCOPE: `record_intent` is the IDEMPOTENT WRITE ONLY (the plan's handler steps 4,
6 and 7: SELECT-by-key, `INSERT ... ON CONFLICT DO NOTHING`, re-SELECT). It does
NO HTTP parsing, NO re-derivation and renders NO fragment -- THE ROUTE owns the
other steps and all responses. Pushing "the seven-step order" into the repo
would put web and derivation concerns in the data layer.
"""
from __future__ import annotations

import sqlite3

from swing.data.models import LatchOrderIntent

_COLS = (
    "intent_id, candidate_id, evaluation_run_id, ticker, detection_date, "
    "pipeline_run_id, idempotency_key, action_session_date, recorded_ts, "
    "surface, intent_kind, decline_reason, attested_disposition, "
    "validated_place_intent_id, framework_order_type, framework_duration, "
    "framework_stop_price, framework_limit_price, framework_quantity, "
    "derivation_zone_cap_pct, derivation_sizing_equity, derivation_max_risk_pct, "
    "derivation_position_pct_cap, derivation_risk_policy_id, "
    "derivation_sizing_basis, derivation_regime_close, "
    "derivation_regime_close_session, derivation_real_equity, "
    "derivation_equity_floor, derivation_nightly_recommendation_shares, "
    "actual_order_type, actual_duration, actual_stop_price, actual_limit_price, "
    "actual_quantity, actual_broker_order_id, validity_outcome, validity_detail"
)

_COL_NAMES: tuple[str, ...] = tuple(c.strip() for c in _COLS.split(","))
# Every column EXCEPT the autoincrement PK -- the INSERT column list, derived
# so it can never drift from the read list.
_INSERT_COLS: tuple[str, ...] = _COL_NAMES[1:]


def _row_to_model(row: tuple) -> LatchOrderIntent:
    return LatchOrderIntent(**dict(zip(_COL_NAMES, row, strict=True)))


def get_intent_by_key(
    conn: sqlite3.Connection, *, idempotency_key: str,
) -> LatchOrderIntent | None:
    row = conn.execute(
        f"SELECT {_COLS} FROM latch_order_intents WHERE idempotency_key = ?",
        (idempotency_key,),
    ).fetchone()
    return None if row is None else _row_to_model(row)


def get_intent(
    conn: sqlite3.Connection, *, intent_id: int,
) -> LatchOrderIntent | None:
    row = conn.execute(
        f"SELECT {_COLS} FROM latch_order_intents WHERE intent_id = ?",
        (intent_id,),
    ).fetchone()
    return None if row is None else _row_to_model(row)


def list_intents_for_latch(
    conn: sqlite3.Connection, *, candidate_id: int,
) -> list[LatchOrderIntent]:
    """Every intent on one latch, in the arc's canonical total order.

    `(recorded_ts, intent_id)` -- the tiebreak on `intent_id` is load-bearing
    because `recorded_ts` is WHOLE SECONDS, so two rows can share one, and the
    GOVERNING row within a kind is the LATEST by exactly this order.
    """
    rows = conn.execute(
        f"SELECT {_COLS} FROM latch_order_intents WHERE candidate_id = ? "
        "ORDER BY recorded_ts, intent_id",
        (candidate_id,),
    ).fetchall()
    return [_row_to_model(r) for r in rows]


def list_intents_since(
    conn: sqlite3.Connection, *, since_ts: str,
) -> list[LatchOrderIntent]:
    """Every intent RECORDED at or after `since_ts`.

    THE TIME AXIS IS `recorded_ts`, NOT `action_session_date`. The row carries
    both, and filtering on the mandate session would put a validity answer given
    in August ABOUT a July render into JULY, and would drop a post-month-end
    CORRECTION out of the current read entirely. Both are silent misbucketings
    of a measurement read once a month. `action_session_date` is PROVENANCE AND
    DISPLAY ONLY -- it answers "which session's mandate was this about", never
    "which month does this row belong to".
    """
    rows = conn.execute(
        f"SELECT {_COLS} FROM latch_order_intents WHERE recorded_ts >= ? "
        "ORDER BY recorded_ts, intent_id",
        (since_ts,),
    ).fetchall()
    return [_row_to_model(r) for r in rows]


def record_intent(
    conn: sqlite3.Connection, *, intent: LatchOrderIntent,
) -> LatchOrderIntent:
    """Idempotently append `intent`; return the row that is now of record.

    Three steps, and the ORDER is the point:

      1. SELECT by `idempotency_key` -- FOUND means REPLAY, return the existing
         row. The SELECT-first idempotency discipline: the terminal-state read
         precedes the write.
      2. `INSERT ... ON CONFLICT(idempotency_key) DO NOTHING`. This is an
         INSERT-time NO-OP, **NOT** `INSERT OR REPLACE` -- no DELETE, no new PK,
         no cascade, so the append-only property holds.
      3. re-SELECT by key and return THAT row. This covers the LOST RACE: two
         requests can both miss step 1, and the loser returns the winner's row
         rather than surfacing an IntegrityError.
    """
    existing = get_intent_by_key(conn, idempotency_key=intent.idempotency_key)
    if existing is not None:
        return existing
    placeholders = ",".join("?" * len(_INSERT_COLS))
    conn.execute(
        f"INSERT INTO latch_order_intents ({', '.join(_INSERT_COLS)}) "
        f"VALUES ({placeholders}) ON CONFLICT(idempotency_key) DO NOTHING",
        tuple(getattr(intent, name) for name in _INSERT_COLS),
    )
    stored = get_intent_by_key(conn, idempotency_key=intent.idempotency_key)
    if stored is None:  # pragma: no cover - defensive
        raise RuntimeError(
            "latch_order_intents row vanished between INSERT and re-SELECT")
    return stored
