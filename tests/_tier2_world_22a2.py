"""22-A2 fixture world: trade 25 (OII) at the SQL grain, pre-barrier.

The values are TRADE 25'S REAL ROW SHAPE, read off the operator's database at
census (22-A2 ledger P2-P4, P8, P11, P24-P26, P31, P36), including the real row
ids -- candidate 12284, run 136, recommendation 169, pipeline 150, trade 25,
fill 48 -- so a fixture cannot quietly agree with itself on a value production
never wrote.

HOW A PRE-BARRIER FIRE IS PRODUCED (the production way, not by moving an
immutable boundary): the evaluation rows are inserted on a v36 schema and the
migrations run AFTERWARDS, so 0037 seeds ``max_candidate_id_at_barrier`` at or
above 12284 and the link the validity insert mints reads
``pre_barrier_reconstructed``.

THE BASE PAYLOAD IS THE REAL EMITTER'S (SS-1's rule, one version up): an
identical world built at HEAD with NO latch rows is corrected by the
production service (``last_word``, because the fill's order resolves to no
link there), and that row's columns seed the tier-2 payload.  The tier-2
columns are then hand-built from the plan's section-2 roster -- a SQL-grain
fixture the trigger either admits or refuses; the SERVICE-built blob is
Task 5's, and A2-42 compares the two representations.
"""
from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path
from typing import Any

from swing.data.db import EXPECTED_SCHEMA_VERSION, open_connection, run_migrations

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "tier2"
SEVENTH_BLOB_FIXTURE = FIXTURE_DIR / "trade25_seventh_blob.json"
LINE57_FIXTURE = FIXTURE_DIR / "rd_state_9f315cc6_line57.txt"

T25_TICKER = "OII"
T25_CANDIDATE_ID = 12284
T25_RUN_ID = 136
T25_REC_ID = 169
T25_PIPELINE_ID = 150
T25_TRADE_ID = 25
T25_FILL_ID = 48
T25_RUN_TS = "2026-08-07T17:30:02"
T25_DATA_ASOF = "2026-08-07"
T25_ACTION_SESSION = "2026-08-10"
T25_PIPELINE_STARTED = "2026-08-07T17:30:00"
T25_PIPELINE_FINISHED = "2026-08-07T17:39:07"
T25_PIVOT = 53.97999954223633
T25_INITIAL_STOP = 41.41999816894531
T25_CLOSE = 53.49
T25_FILL_SESSION = "2026-08-17"
T25_FILL_DATETIME = "2026-08-17T16:00:00"
T25_FILL_PRICE = 53.98
T25_FILL_QTY = 2
T25_ORDER_ID = "1007523377009"
T25_ENVELOPE = json.dumps(
    {"entry_date": T25_FILL_SESSION, "entry_date_source": "execution_leg",
     "entry_price": T25_FILL_PRICE, "schwab_instrument_symbol": T25_TICKER,
     "schwab_order_id": T25_ORDER_ID, "shares": T25_FILL_QTY},
    sort_keys=True)
T25_PLACE_TS = "2026-08-10T12:00:00"
T25_VALIDITY_TS = "2026-08-10T12:05:00"
T25_LIMIT = 53.98
T25_AUTHOR_INSTANT = "2026-08-10T02:41:33-10:00"
T25_APPLIED_AT = "2026-09-23T12:00:00.000"


def _seed_rows(conn: sqlite3.Connection, *, with_envelope_reading: bool) -> None:
    from tests.trades._cohort_provenance_fixtures import (
        H1_ID,
        rebase_status_history_recorded_at,
        seed_criteria,
    )

    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
        "action_session_date, finviz_csv_path, tickers_evaluated, aplus_count, "
        "watch_count, skip_count, excluded_count, error_count) "
        "VALUES (?, ?, ?, ?, NULL, 60, 1, 10, 46, 3, 0)",
        (T25_RUN_ID, T25_RUN_TS, T25_DATA_ASOF, T25_ACTION_SESSION))
    conn.execute(
        "INSERT INTO candidates (id, evaluation_run_id, ticker, bucket, close, "
        "pivot, initial_stop, adr_pct, tight_streak, pullback_pct, "
        "prior_trend_pct, rs_rank, rs_return_12w_vs_spy, rs_method, "
        "pattern_tag, notes, sector, industry) "
        "VALUES (?, ?, ?, 'aplus', ?, ?, ?, 4.1, 5, 8.0, 60.0, NULL, 20.1, "
        "'universe', 'vcp', NULL, 'Energy', 'Oil & Gas Equipment & Services')",
        (T25_CANDIDATE_ID, T25_RUN_ID, T25_TICKER, T25_CLOSE, T25_PIVOT,
         T25_INITIAL_STOP))
    seed_criteria(conn, candidate_id=T25_CANDIDATE_ID)
    conn.execute(
        "INSERT INTO daily_recommendations (id, evaluation_run_id, "
        "data_asof_date, action_session_date, ticker, recommendation, "
        "action_text, entry_target, stop_target, shares, risk_dollars, "
        "risk_pct, rationale) VALUES (?, ?, ?, ?, ?, 'today_decision', "
        "'Buy-stop $53.98 ... 2 sh', ?, ?, 2, 25.12, 0.5, 'A+ setup.')",
        (T25_REC_ID, T25_RUN_ID, T25_DATA_ASOF, T25_ACTION_SESSION,
         T25_TICKER, T25_PIVOT, T25_INITIAL_STOP))
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, finished_ts, trigger, "
        "data_asof_date, action_session_date, state, lease_token, "
        "evaluation_run_id) VALUES (?, ?, ?, 'scheduled', ?, ?, 'complete', "
        "?, ?)",
        (T25_PIPELINE_ID, T25_PIPELINE_STARTED, T25_PIPELINE_FINISHED,
         T25_DATA_ASOF, T25_ACTION_SESSION, f"lease-{T25_PIPELINE_STARTED}",
         T25_RUN_ID))
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, trade_origin, "
        "pre_trade_locked_at, current_size, current_avg_cost, last_fill_at, "
        "hypothesis_label, candidate_id, entry_intent) VALUES (?, ?, ?, ?, ?, "
        "41.42, 41.42, 'entered', 'manual_off_pipeline', ?, ?, ?, ?, NULL, "
        "NULL, 'standard')",
        (T25_TRADE_ID, T25_TICKER, T25_FILL_SESSION, T25_FILL_PRICE,
         T25_FILL_QTY, T25_FILL_DATETIME, float(T25_FILL_QTY), T25_FILL_PRICE,
         T25_FILL_DATETIME))
    conn.execute(
        "INSERT INTO fills (fill_id, trade_id, fill_datetime, action, "
        "quantity, price, reason, reconciliation_status, fill_origin, "
        "schwab_source_value_json) VALUES (?, ?, ?, 'entry', ?, ?, NULL, "
        "'unreconciled', 'schwab_auto', ?)",
        (T25_FILL_ID, T25_TRADE_ID, T25_FILL_DATETIME, float(T25_FILL_QTY),
         T25_FILL_PRICE, T25_ENVELOPE))
    if with_envelope_reading:
        record_reading(conn)
    rebase_status_history_recorded_at(conn)
    assert H1_ID == 1


def record_reading(conn: sqlite3.Connection) -> None:
    """The authority's stored reading of fill 48's envelope (PERSIST-CANONICAL)."""
    from swing.data.repos.fill_envelope_identity import record_identity
    record_identity(conn, fill_id=T25_FILL_ID, envelope_raw=T25_ENVELOPE)


def base_last_word_payload(tmp_path: Path) -> dict[str, Any]:
    """Every column of the PRODUCTION service's row, on an UNLINKED twin world.

    The service writes ``last_word`` there because fill 48's order resolves to
    no link; its snapshots, frozen anchors and derived keys are the real
    emitter's output for trade 25's row shape.
    """
    from swing.data.db import ensure_schema
    from swing.trades import cohort_provenance_correction as cpc

    conn = ensure_schema(tmp_path / "t25_base.db")
    try:
        _seed_rows(conn, with_envelope_reading=True)
        conn.commit()
        original = cpc._APPLIED_AT_CLOCK
        cpc._APPLIED_AT_CLOCK = lambda: T25_APPLIED_AT
        try:
            cpc.correct_cohort_provenance(
                conn, trade_id=T25_TRADE_ID,
                cited_candidate_id=T25_CANDIDATE_ID,
                cited_recommendation_id=T25_REC_ID,
                reason="22-A2 fixture: the real emitter's base row")
        finally:
            cpc._APPLIED_AT_CLOCK = original
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(provenance_corrections)")]
        row = conn.execute("SELECT * FROM provenance_corrections").fetchone()
        return dict(zip(cols, row, strict=True))
    finally:
        conn.close()


def build_pre_barrier_world(
    tmp_path: Path, name: str = "t25", *, target_version: int = EXPECTED_SCHEMA_VERSION,
) -> tuple[sqlite3.Connection, dict[str, int]]:
    """Trade 25's rows on v36, then migrated, then the latch rows -> a
    ``pre_barrier_reconstructed`` link on candidate 12284."""
    from tests._latch_link_fixtures_22a import insert_intent, place_row, validity_row

    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    conn = open_connection(root / "swing.db")
    run_migrations(conn, target_version=36)
    _seed_rows(conn, with_envelope_reading=False)   # no FEI table at v36
    conn.commit()
    run_migrations(conn, target_version=target_version, backup_dir=root / "bak")
    record_reading(conn)
    place = place_row(
        T25_CANDIDATE_ID, run_id=T25_RUN_ID, ticker=T25_TICKER,
        detection_date=T25_ACTION_SESSION, action_session_date=T25_ACTION_SESSION,
        recorded_ts=T25_PLACE_TS, idempotency_key="t25-place",
        framework_limit_price=T25_LIMIT, framework_quantity=T25_FILL_QTY)
    place_id = insert_intent(conn, place)
    validity = validity_row(
        T25_CANDIDATE_ID, place_id, key="t25-validity", run_id=T25_RUN_ID,
        ticker=T25_TICKER, detection_date=T25_ACTION_SESSION,
        action_session_date=T25_ACTION_SESSION, recorded_ts=T25_VALIDITY_TS,
        actual_limit_price=T25_LIMIT, actual_quantity=T25_FILL_QTY,
        actual_broker_order_id=T25_ORDER_ID)
    validity_id = insert_intent(conn, validity)
    conn.commit()
    link = conn.execute(
        "SELECT link_id, freeze_tier FROM latch_order_mandate_links "
        "WHERE broker_order_id = ?", (T25_ORDER_ID,)).fetchone()
    assert link is not None and link[1] == "pre_barrier_reconstructed", link
    return conn, {"place_id": place_id, "validity_id": validity_id,
                  "link_id": link[0]}


def load_seventh_blob(conn: sqlite3.Connection, *, applied_at: str) -> dict:
    """The literal section-2 blob with its TWO world-dependent raws bound.

    ``barrier_armed_at.raw`` is the epoch row's ``applied_at`` -- stamped by
    migration 0037 at migration time and immutable thereafter, so a test world
    cannot carry the live ``2026-09-02T10:03:33Z`` -- and ``read_at.raw`` /
    ``evaluated_at`` are the row's own ``applied_at``.  Every other value is
    the literal file's.
    """
    blob = json.loads(SEVENTH_BLOB_FIXTURE.read_text(encoding="utf-8"))
    epoch = conn.execute(
        "SELECT applied_at FROM candidates_immutability_epoch "
        "WHERE epoch_id = 1").fetchone()[0]
    endpoints = blob["interval"]["endpoints"]
    endpoints["barrier_armed_at"]["raw"] = epoch
    endpoints["barrier_armed_at"]["utc"] = epoch           # already UTC-Z
    endpoints["read_at"]["raw"] = applied_at
    endpoints["read_at"]["utc"] = applied_at + "Z"         # naive UTC ms
    blob["evaluated_at"] = applied_at
    return blob


def tier2_probe_blob(conn: sqlite3.Connection, ids: dict[str, int]) -> dict:
    """A truthful probe blob for the escaped rung 9 (version 2026-09-23.1)."""
    from swing.trades.latched_origin import (
        AUTHORIZATION_KEYS,
        LATCH_PROBE_TIER2_EVIDENCE_VERSION,
        PROBE_EVIDENCE_KEYS,
    )

    link = conn.execute(
        "SELECT frozen_pivot, frozen_invalidation, freeze_tier "
        "FROM latch_order_mandate_links WHERE link_id = ?",
        (ids["link_id"],)).fetchone()
    sessions = ["2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13",
                "2026-08-14"]
    authorization = {
        "rung1_link_ticker": T25_TICKER,
        "rung2_link_parent": ids["place_id"],
        "rung3_validity_outcome": "accepted_by_broker",
        "rung3b_latest_validity_child": ids["validity_id"],
        "rung3c_link_broker_order_id": T25_ORDER_ID,
        "rung4_governing_place_intent": ids["place_id"],
        "rung5_cancel_intent_id": None,
        "rung6_consuming_trade_id": None,
        "rung7_consumption_scan_fill_ids": [T25_FILL_ID],
        "rung8_competitor_link_ids": [],
        "rung9_stored_freeze_tier": link[2],
        "guard_fill_origin": "schwab_auto",
        "guard_envelope_symbol": T25_TICKER,
        "guard_quantity": float(T25_FILL_QTY),
        "guard_framework_price_bound": T25_FILL_PRICE,
        "guard_broker_limit_bound": T25_LIMIT,
    }
    assert set(authorization) == set(AUTHORIZATION_KEYS)
    auth = {k: {"input": v, "verdict": "pass"} for k, v in authorization.items()}
    auth["rung9_stored_freeze_tier"]["verdict"] = "escaped_by_tier2"
    blob = {
        "evidence_version": LATCH_PROBE_TIER2_EVIDENCE_VERSION,
        "fire_candidate_id": T25_CANDIDATE_ID,
        "ticker": T25_TICKER,
        "fill_session": T25_FILL_SESSION,
        "horizon_session": T25_FILL_SESSION,
        "bars_through": "2026-08-14",
        "clear_reason": None,
        "clear_session": None,
        "admission_basis": "armed",
        "criteria_lapse_forced_off": 1,
        "freeze_tier": link[2],
        "archive_status": "ok",
        "frozen_invalidation_raw": link[1],
        "live_invalidation_raw": T25_INITIAL_STOP,
        "frozen_pivot_raw": link[0],
        "live_pivot_raw": T25_PIVOT,
        "invalidation_equal_at_dp": 1,
        "pivot_equal_at_dp": 1,
        "compare_dp": 2,
        "coverage": {"expected_sessions": sessions,
                     "observed_sessions": list(sessions),
                     "missing_sessions": []},
        "probe_guards": {
            "fill_session_is_session": {"input": T25_FILL_SESSION,
                                        "verdict": "pass"},
            "fire_membership": {"input": 1, "verdict": "pass"},
            "decision_ordering": {"input": [[ids["place_id"], T25_PLACE_TS]],
                                  "verdict": "pass"},
        },
        "authorization": auth,
    }
    assert set(blob) == set(PROBE_EVIDENCE_KEYS)
    return blob


def truthful_tier2_payload(
    tmp_path: Path, name: str = "t25",
) -> tuple[sqlite3.Connection, dict[str, Any], dict[str, int]]:
    """``(conn, payload, ids)``: a pre-barrier world and a TRUTHFUL
    ``latch_ladder_tier2`` row the citation trigger must ADMIT on raw INSERT."""
    base = base_last_word_payload(tmp_path)
    conn, ids = build_pre_barrier_world(tmp_path, name)
    payload = copy.deepcopy(base)
    payload["provenance_correction_id"] = None
    payload.update(
        admission_tier="latch_ladder_tier2",
        cited_latch_link_id=ids["link_id"],
        cited_latch_validity_intent_id=ids["validity_id"],
        cited_latch_place_intent_id=ids["place_id"],
        cited_latch_broker_order_id=T25_ORDER_ID,
        cited_latch_probe_json=json.dumps(tier2_probe_blob(conn, ids)),
        cited_frozen_value_evidence_json=json.dumps(
            load_seventh_blob(conn, applied_at=payload["applied_at"])),
    )
    return conn, payload, ids


def insert_payload(conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
    conn.execute(
        f"INSERT INTO provenance_corrections ({', '.join(payload)}) "
        f"VALUES ({', '.join('?' * len(payload))})", tuple(payload.values()))
