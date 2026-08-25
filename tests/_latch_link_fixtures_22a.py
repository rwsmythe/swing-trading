"""22-A fixture builders: an A+ fire, a place intent, and a broker acceptance.

Every shape here is copied from the SHIPPED 0033 fixture kit
(``tests/data/test_migration_0033.py``), which was itself derived from real
emitter output, rather than re-invented -- a synthetic fixture that does not
match the production INSERT shape is this project's most-repeated test defect.

THE FIXTURES ARE COMPLETE OR THEY CANNOT INSERT.  An ``accepted_by_broker``
validity row is CHECKed to carry a non-blank ``actual_broker_order_id``, a
known order type and duration, a non-NULL limit price and quantity, and the
FULL broker-snapshot roster envelope; and it inherits its parent place row's
``action_session_date`` (the trigger's session leg).  A fixture listing only
the four ``actual_*`` fields FAILS against the correct schema, and the tempting
repair is to weaken the CHECKs rather than complete the fixture.
"""
from __future__ import annotations

import json
import sqlite3

RUN_ID = 121
TICKER = "FTRE"
DETECTION_DATE = "2026-07-20"
GOOD_SESSION = "2026-07-29"
GOOD_TS = "2026-07-29T12:00:00"
DIGEST64 = "a" * 64
BROKER_ORDER_ID = "1002937461"

PIVOT = 18.34
INITIAL_STOP = 14.88


def snapshot_envelope(**over) -> str:
    """EXACTLY the 0033 roster -- the migration's own ``json_remove`` path list
    is the machine-readable source of truth and it closes on EXTRA keys."""
    env = {
        "broker_snapshot_ts": GOOD_TS,
        "broker_snapshot_branch": "presence",
        "broker_snapshot_digest": DIGEST64,
        "broker_snapshot_session": GOOD_SESSION,
        "attributable_order_count": 1,
        "exact_framework_match_count": 0,
        "indeterminate": False,
    }
    env.update(over)
    return json.dumps(env)


def seed_fire(
    conn: sqlite3.Connection,
    *,
    run_id: int = RUN_ID,
    ticker: str = TICKER,
    pivot: float | None = PIVOT,
    initial_stop: float | None = INITIAL_STOP,
    candidate_id: int | None = None,
    action_session_date: str = DETECTION_DATE,
) -> int:
    """An evaluation run plus one A+ candidate on it.  Returns the candidate id.

    ``action_session_date`` is the RUN's, and the identity-coherence trigger
    requires every intent's ``detection_date`` to equal it -- so the two move
    together or the intent insert aborts.
    """
    exists = conn.execute(
        "SELECT 1 FROM evaluation_runs WHERE id = ?", (run_id,)).fetchone()
    if exists is None:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) "
            "VALUES (?, '2026-07-17T20:06:25', '2026-07-17', ?, 1, 1, 0, 0, 0, 0)",
            (run_id, action_session_date),
        )
    cols = "evaluation_run_id, ticker, bucket, close, pivot, initial_stop, rs_method"
    vals: list = [run_id, ticker, "aplus", 18.34, pivot, initial_stop, "universe"]
    if candidate_id is not None:
        cols = "id, " + cols
        vals = [candidate_id, *vals]
    cur = conn.execute(
        f"INSERT INTO candidates ({cols}) VALUES ({', '.join('?' * len(vals))})",
        tuple(vals),
    )
    return int(cur.lastrowid)


def place_row(candidate_id: int, **over) -> dict:
    """A MINIMAL VALID ``place`` row -- the whole drift-capable derivation block
    included, because the schema requires it."""
    row = {
        "candidate_id": candidate_id, "evaluation_run_id": RUN_ID,
        "ticker": TICKER, "detection_date": DETECTION_DATE,
        "pipeline_run_id": None, "idempotency_key": "key-place",
        "action_session_date": GOOD_SESSION, "recorded_ts": GOOD_TS,
        "surface": "latch_panel", "intent_kind": "place",
        "framework_order_type": "LIMIT",
        "framework_duration": "GOOD_TILL_CANCEL",
        "framework_stop_price": None, "framework_limit_price": 18.89,
        "framework_quantity": 9,
        "derivation_zone_cap_pct": 3.0, "derivation_sizing_equity": 7500.0,
        "derivation_max_risk_pct": 0.005, "derivation_position_pct_cap": 0.15,
        "derivation_risk_policy_id": None,
        "derivation_sizing_basis": "limit_price",
        "derivation_regime_close": 19.20,
        "derivation_regime_close_session": GOOD_SESSION,
        "derivation_real_equity": 1234.56, "derivation_equity_floor": 7500.0,
        "derivation_nightly_recommendation_shares": 10,
    }
    row.update(over)
    return row


def validity_row(candidate_id: int, place_intent_id: int,
                 key: str = "key-validity", **over) -> dict:
    """A COMPLETE ``accepted_by_broker`` validity row."""
    row = {
        "candidate_id": candidate_id, "evaluation_run_id": RUN_ID,
        "ticker": TICKER, "detection_date": DETECTION_DATE,
        "pipeline_run_id": None, "idempotency_key": key,
        "action_session_date": GOOD_SESSION, "recorded_ts": GOOD_TS,
        "surface": "latch_panel", "intent_kind": "validity",
        "validated_place_intent_id": place_intent_id,
        "validity_outcome": "accepted_by_broker",
        "validity_detail": snapshot_envelope(),
        "actual_order_type": "LIMIT", "actual_duration": "GOOD_TILL_CANCEL",
        "actual_stop_price": None, "actual_limit_price": 18.89,
        "actual_quantity": 10, "actual_broker_order_id": BROKER_ORDER_ID,
    }
    row.update(over)
    return row


def insert_intent(conn: sqlite3.Connection, row: dict) -> int:
    cols = ", ".join(row)
    placeholders = ", ".join("?" * len(row))
    cur = conn.execute(
        f"INSERT INTO latch_order_intents ({cols}) VALUES ({placeholders})",
        tuple(row.values()),
    )
    return int(cur.lastrowid)


def accept_order(
    conn: sqlite3.Connection,
    candidate_id: int,
    *,
    key: str = "key-validity",
    place_key: str = "key-place",
    **validity_over,
) -> tuple[int, int]:
    """Place an order and record the broker's acceptance.

    Returns ``(place_intent_id, validity_intent_id)``.  The minting trigger
    fires on the second INSERT -- it is never called directly here, because a
    fixture that mints its own link would test the fixture rather than the
    trigger.
    """
    place_id = insert_intent(
        conn, place_row(candidate_id, idempotency_key=place_key))
    validity_id = insert_intent(
        conn, validity_row(candidate_id, place_id, key=key, **validity_over))
    return place_id, validity_id
