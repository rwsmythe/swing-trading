"""Arc 22-B shared fixtures -- REAL row shapes, read off the live v39 DB.

Every value below was read with plain ``sqlite3`` ``mode=ro`` on the live
journal (2026-09-23; plan ledger R0.C K5 / R0.F-2): trade 20 (AMN) with its
two-space ``notes``, its entry fill 41 and Schwab envelope, its outcome fill 44
(``stop``, 2026-08-11), and the AMN ``latch_view_events`` row 5 (a 0033
backfill row: first viewed 2026-08-01, ``actionable_ever_viewed`` 0). Rows are
planted by RAW ``INSERT`` (the 18-B.1 technique) so a write-barrier on a repo
writer never blocks the fixture.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

TRADE20 = {
    "id": 20,
    "ticker": "AMN",
    "entry_date": "2026-08-07",
    "entry_price": 36.43,
    "initial_shares": 5,
    "initial_stop": 33.72,
    "current_stop": 33.72,
    "state": "reviewed",
    "notes": ("Stale A+ latch order fired after A+ condition disappeared.  "
              "This happened as we were working on the latch removal code."),
    "why_now": "Accidental entry while working on latch/unlatch mechanism",
    "thesis": "Old A+ setup, high likelihood of loss",
    "emotional_state_pre_trade": '["distracted"]',
    "hypothesis_label": None,
    "entry_intent": None,
    "trade_origin": "manual_off_pipeline",
    "pre_trade_locked_at": "2026-08-07T16:00:00",
}
FILL41_ENVELOPE = ('{"entry_date": "2026-08-01", "entry_price": 36.43, '
                   '"schwab_instrument_symbol": "AMN", '
                   '"schwab_order_id": "1007427919619", "shares": 5}')
FILL41 = {"fill_id": 41, "trade_id": 20, "fill_datetime": "2026-08-07T16:00:00",
          "action": "entry", "quantity": 5.0, "price": 36.43,
          "schwab_source_value_json": FILL41_ENVELOPE}
FILL44 = {"fill_id": 44, "trade_id": 20, "fill_datetime": "2026-08-11T16:00:00",
          "action": "stop", "quantity": 5.0, "price": 33.73,
          "schwab_source_value_json": None}
AMN_ORDER_ID = "1007427919619"

# The AMN fire and its telemetry row 5, verbatim.
AMN_RUN_ID = 131
AMN_PIPELINE_ID = 145
AMN_CANDIDATE_ID = 11926
LVE_ROW5 = {
    "view_event_id": 5, "candidate_id": AMN_CANDIDATE_ID,
    "evaluation_run_id": AMN_RUN_ID, "ticker": "AMN",
    "detection_date": "2026-08-03", "pipeline_run_id": AMN_PIPELINE_ID,
    "surface": "latch_panel", "view_session_date": "2026-08-03",
    "first_viewed_ts": "2026-08-01T05:09:56",
    "last_viewed_ts": "2026-08-02T23:43:45", "view_count": 4,
    "latch_state_at_first_view": "armed", "latch_state_at_last_view": "armed",
    "actionable_at_first_view": 0, "actionable_at_last_view": 0,
    "actionable_ever_viewed": 0,
}


def insert_row(conn: sqlite3.Connection, table: str, row: dict[str, Any]) -> int:
    cols = ", ".join(row)
    marks = ", ".join("?" * len(row))
    cur = conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})",
                       tuple(row.values()))
    return int(cur.lastrowid)


def seed_fire(conn: sqlite3.Connection, *, run_id: int, pipeline_id: int,
              candidate_id: int, ticker: str, action_session: str,
              data_asof: str = "2026-07-31") -> None:
    """An A+ fire: evaluation run + its pipeline twin + an `aplus` candidate
    (the identity triggers of `latch_view_events` check exactly these)."""
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
        "action_session_date, finviz_csv_path, tickers_evaluated, aplus_count, "
        "watch_count, skip_count, excluded_count, error_count) "
        "VALUES (?, ?, ?, ?, NULL, 60, 1, 10, 46, 3, 0)",
        (run_id, f"{data_asof}T18:00:00", data_asof, action_session))
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, finished_ts, trigger, "
        "data_asof_date, action_session_date, state, lease_token, "
        "evaluation_run_id) VALUES (?, ?, ?, 'scheduled', ?, ?, 'complete', "
        "?, ?)",
        (pipeline_id, f"{data_asof}T17:55:00", f"{data_asof}T18:05:00",
         data_asof, action_session, f"lease-{pipeline_id}", run_id))
    conn.execute(
        "INSERT INTO candidates (id, evaluation_run_id, ticker, bucket, close, "
        "pivot, initial_stop, adr_pct, tight_streak, pullback_pct, "
        "prior_trend_pct, rs_rank, rs_return_12w_vs_spy, rs_method, "
        "pattern_tag, notes, sector, industry) "
        "VALUES (?, ?, ?, 'aplus', 36.0, 36.43, 33.72, 4.1, 5, 8.0, 60.0, NULL, "
        "20.1, 'universe', 'vcp', NULL, 'Healthcare', 'Medical Care Facilities')",
        (candidate_id, run_id, ticker))


def seed_amn_row5(conn: sqlite3.Connection, **overrides: Any) -> dict[str, Any]:
    """The AMN fire + `latch_view_events` row 5, raw. Returns the row planted."""
    seed_fire(conn, run_id=AMN_RUN_ID, pipeline_id=AMN_PIPELINE_ID,
              candidate_id=AMN_CANDIDATE_ID, ticker="AMN",
              action_session="2026-08-03")
    row = {**LVE_ROW5, **overrides}
    insert_row(conn, "latch_view_events", row)
    return row


def seed_trade20(conn: sqlite3.Connection, *, with_outcome: bool = True,
                 **overrides: Any) -> int:
    """Trade 20 + fill 41 (+ fill 44 unless ``with_outcome=False``), raw."""
    trade = {**TRADE20, **overrides}
    trade.setdefault("current_size", 0.0 if with_outcome else 5.0)
    insert_row(conn, "trades", trade)
    own_ids = trade["id"] == TRADE20["id"]  # a twin trade gets fresh fill ids

    def _fill(f: dict[str, Any]) -> dict[str, Any]:
        row = {**f, "trade_id": trade["id"]}
        if not own_ids:
            del row["fill_id"]
        return row

    insert_row(conn, "fills", _fill(FILL41))
    if with_outcome:
        insert_row(conn, "fills", _fill(FILL44))
    return int(trade["id"])


def record_envelope_readings(conn: sqlite3.Connection) -> int:
    """The AUTHORITY's stored reading of every envelope-bearing entry fill.

    RULING G1b: 0040's binding trigger compares the attestation's order id to
    the STORED ``fill_envelope_identity`` reading, never to the envelope. In
    production the entry writer records that reading
    (``_record_envelope_identity_or_log``) and ``assign`` re-verifies it; a
    fixture that plants fills RAW must establish it the same way before it
    plants an attestation row naming an order id.
    """
    from swing.data.repos.fill_envelope_identity import (
        ensure_entry_fill_identities,
    )

    return ensure_entry_fill_identities(conn)


def envelope(**overrides: Any) -> str:
    base = json.loads(FILL41_ENVELOPE)
    base.update(overrides)
    return json.dumps(base)
