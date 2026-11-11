"""Demand C -- fixture builders for the cohort-provenance correction surface.

Every shape here is taken from REAL emitter output on the operator's live DB
(plan section 1.4 / 1.6 / 3.4.1-clock), not invented:

  - `evaluation_runs` rows carry the live 1-day (`2026-08-10` ->  `2026-08-11`)
    and 3-day weekend (`2026-08-07` -> `2026-08-10`) `data_asof_date` /
    `action_session_date` gaps. There is NO live run where the two are equal.
  - `candidates` + `candidate_criteria` carry the real criterion roster
    (`swing/evaluation/scoring.py`: 8 TT + 9 VCP names) plus the `risk` layer's
    `risk_feasibility`, with CADL's real `TT8_rs_rank='na'` RS-rank fallback.
  - entry fills use the synthetic naive `T16:00:00` convention -- the ONLY
    shape present across all 46 live `fills` rows.
  - the pipeline window is naive LOCAL (`2026-08-10T17:30:26` ->
    `T17:44:45`, the real 14m19s CADL gap) while `hypothesis_status_history`
    is naive UTC -- the two clock domains the arc normalizes across.

`ensure_schema` seeds `hypothesis_status_history` with `recorded_at` =
MIGRATION APPLY TIME (migration 0017's own documented behaviour), which
post-dates every fixture `run_ts` and would trip the retrospective refusal on
every case. `rebase_status_history_recorded_at` exists for that: it is the
fixture's way of saying "this interval was on record contemporaneously", and a
test that WANTS the retrospective refusal simply does not call it.

No helper here reads `datetime.now()`; every date is frozen.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

# --- The live CADL case (trade 23 / candidate 12341 / DR 172 / run 137) ----
CADL_TICKER = "CADL"
CADL_RUN_TS_LOCAL = "2026-08-10T17:30:26"
CADL_PIPELINE_STARTED_LOCAL = "2026-08-10T17:30:00"
CADL_PIPELINE_FINISHED_LOCAL = "2026-08-10T17:44:45"
# The SAME instants normalized out of Pacific/Honolulu (UTC-10). The DATE
# ROLLS, which is what makes a skipped normalization visible.
CADL_RUN_TS_UTC = "2026-08-11T03:30:26"
CADL_WINDOW_UPPER_UTC = "2026-08-11T03:44:45"
CADL_DATA_ASOF = "2026-08-10"
CADL_ACTION_SESSION = "2026-08-11"
CADL_FILL_DATETIME = "2026-08-12T16:00:00"
CADL_F = "2026-08-12"
CADL_CLOSE = 10.5
CADL_PIVOT = 10.8149995803833

# The trade-21 / LQDA weekend shape -- the section 3.2.2 anchor discriminator.
LQDA_DATA_ASOF = "2026-08-07"
LQDA_ACTION_SESSION = "2026-08-10"
LQDA_RUN_TS_LOCAL = "2026-08-07T17:30:02"
LQDA_F = "2026-08-07"

H1_NAME = "A+ baseline"
H1_ID = 1
# The FAITHFUL derivation for candidate 12341 (plan section 1.6, RD-ruled):
# `TT8_rs_rank='na'` counts as non-pass, so the framework's own builder emits
# the suffix. The clean sibling string belongs to trades 17/18, NOT to CADL.
CADL_LABEL = "A+ baseline (aplus); failed: TT8_rs_rank"
CLEAN_APLUS_LABEL = "A+ baseline (aplus)"

APLUS_ORIGIN = "pipeline_aplus"
UNSET_ORIGIN = "manual_off_pipeline"

# `swing/evaluation/scoring.py:EXPECTED_TT_CRITERIA` / `EXPECTED_VCP_CRITERIA`,
# spelled here so a fixture cannot silently drift from the roster the real
# evaluator emits (a drift test pins the two together).
TT_CRITERIA: tuple[str, ...] = (
    "TT1_above_150_200", "TT2_150_above_200", "TT3_200_rising",
    "TT4_50_above_150_200", "TT5_above_50", "TT6_above_52w_low_30pct",
    "TT7_within_52w_high_25pct", "TT8_rs_rank",
)
VCP_CRITERIA: tuple[str, ...] = (
    "adr", "ma_short_rising", "ma_stack_10_20_50", "orderliness",
    "prior_trend", "proximity_20ma", "pullback", "tightness",
    "vcp_volume_contraction",
)
RISK_CRITERIA: tuple[str, ...] = ("risk_feasibility",)

_LAYER_BY_CRITERION: dict[str, str] = {
    **{n: "trend_template" for n in TT_CRITERIA},
    **{n: "vcp" for n in VCP_CRITERIA},
    **{n: "risk" for n in RISK_CRITERIA},
}

# CADL's real `TT8_rs_rank` row: the RS-rank universe fallback.
CADL_RS_RANK_VALUE = "fallback, excess=+13.31% vs SPY 12w"


def seed_evaluation_run(
    conn: sqlite3.Connection,
    *,
    run_ts: str,
    data_asof_date: str,
    action_session_date: str,
    aplus_count: int = 1,
    watch_count: int = 10,
    skip_count: int = 46,
    excluded_count: int = 3,
    error_count: int = 0,
    tickers_evaluated: int = 60,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO evaluation_runs (
            run_ts, data_asof_date, action_session_date, finviz_csv_path,
            tickers_evaluated, aplus_count, watch_count, skip_count,
            excluded_count, error_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_ts, data_asof_date, action_session_date, None, tickers_evaluated,
         aplus_count, watch_count, skip_count, excluded_count, error_count),
    )
    return int(cur.lastrowid)


def seed_pipeline_run(
    conn: sqlite3.Connection,
    *,
    evaluation_run_id: int | None,
    data_asof_date: str,
    action_session_date: str,
    started_ts: str = CADL_PIPELINE_STARTED_LOCAL,
    finished_ts: str | None = CADL_PIPELINE_FINISHED_LOCAL,
    state: str = "complete",
) -> int:
    cur = conn.execute(
        """
        INSERT INTO pipeline_runs (
            started_ts, finished_ts, trigger, data_asof_date,
            action_session_date, state, lease_token, evaluation_run_id
        ) VALUES (?, ?, 'scheduled', ?, ?, ?, ?, ?)
        """,
        (started_ts, finished_ts, data_asof_date, action_session_date, state,
         f"lease-{started_ts}", evaluation_run_id),
    )
    return int(cur.lastrowid)


def seed_candidate(
    conn: sqlite3.Connection,
    *,
    evaluation_run_id: int,
    ticker: str = CADL_TICKER,
    bucket: str = "aplus",
    non_pass: dict[str, str] | None = None,
    close: float | None = CADL_CLOSE,
    pivot: float | None = CADL_PIVOT,
    rs_method: str = "fallback_spy",
    with_criteria: bool = True,
) -> int:
    """One `candidates` row plus its full criterion roster.

    `non_pass` maps criterion name -> `'fail'` or `'na'`; every other
    criterion is `'pass'`. CADL's live shape is `{'TT8_rs_rank': 'na'}`.
    """
    cur = conn.execute(
        """
        INSERT INTO candidates (
            evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
            adr_pct, tight_streak, pullback_pct, prior_trend_pct, rs_rank,
            rs_return_12w_vs_spy, rs_method, pattern_tag, notes, sector,
            industry
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (evaluation_run_id, ticker, bucket, close, pivot, 9.161, 6.2, 4,
         7.5, 92.0, None, 13.31, rs_method, "vcp", None, "Healthcare",
         "Biotechnology"),
    )
    candidate_id = int(cur.lastrowid)
    if with_criteria:
        seed_criteria(conn, candidate_id=candidate_id, non_pass=non_pass)
    return candidate_id


def seed_criteria(
    conn: sqlite3.Connection,
    *,
    candidate_id: int,
    non_pass: dict[str, str] | None = None,
) -> None:
    non_pass = dict(non_pass or {})
    for name in (*TT_CRITERIA, *VCP_CRITERIA, *RISK_CRITERIA):
        result = non_pass.get(name, "pass")
        value = CADL_RS_RANK_VALUE if name == "TT8_rs_rank" else None
        conn.execute(
            """
            INSERT INTO candidate_criteria (
                candidate_id, criterion_name, layer, result, value, rule
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (candidate_id, name, _LAYER_BY_CRITERION[name], result, value,
             None),
        )


def seed_recommendation(
    conn: sqlite3.Connection,
    *,
    evaluation_run_id: int,
    data_asof_date: str,
    action_session_date: str,
    ticker: str = CADL_TICKER,
    recommendation: str = "today_decision",
    action_text: str | None = (
        "Buy-stop $10.81 ... 19 sh ... $37.41 risk = 19 x ($11.1300 cap - "
        "$9.1610 stop)"
    ),
) -> int:
    cur = conn.execute(
        """
        INSERT INTO daily_recommendations (
            evaluation_run_id, data_asof_date, action_session_date, ticker,
            recommendation, action_text, entry_target, stop_target, shares,
            risk_dollars, risk_pct, rationale
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (evaluation_run_id, data_asof_date, action_session_date, ticker,
         recommendation, action_text, 10.8149995803833, 9.161, 19, 37.41,
         0.5, "A+ setup; VCP tight."),
    )
    return int(cur.lastrowid)


def seed_trade(
    conn: sqlite3.Connection,
    *,
    ticker: str = CADL_TICKER,
    entry_date: str = CADL_F,
    state: str = "entered",
    trade_origin: str = UNSET_ORIGIN,
    hypothesis_label: str | None = None,
    candidate_id: int | None = None,
    entry_intent: str | None = "standard",
    entry_price: float = 10.81,
    initial_shares: int = 19,
    current_size: float | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at,
            current_size, current_avg_cost, last_fill_at, hypothesis_label,
            candidate_id, entry_intent
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ticker, entry_date, entry_price, initial_shares, 9.161, 9.161, state,
         trade_origin, f"{entry_date}T16:00:00",
         float(initial_shares) if current_size is None else current_size,
         entry_price, f"{entry_date}T16:00:00", hypothesis_label,
         candidate_id, entry_intent),
    )
    return int(cur.lastrowid)


# THE LIVE CADL ENTRY FILL'S ENVELOPE, VERBATIM (RD, 2026-08-26).
#
# Read read-only off the operator's database on 2026-08-26:
#
#     SELECT schwab_source_value_json FROM fills WHERE fill_id = 45
#
# fill 45 / trade 23 / CADL / action='entry' / fill_origin='schwab_auto'.
# Reproduced here rather than invented, because a fixture that quietly
# disagrees with the emitter is this project's most-repeated test defect.
#
# WHY THIS CONSTANT EXISTS AT ALL. `seed_fill` defaulted `fill_origin` to
# `schwab_auto` and did not model the envelope, so every fixture built on it
# asserted a pair NO PRODUCTION WRITER PRODUCES -- a trusted origin with no
# envelope, which is RD's own 22A-R3-13 INCONSISTENT EVIDENCE PAIR. The
# silence was the unresolved fact; naming the live shape is what resolves it.
CADL_LIVE_ENVELOPE = (
    '{"entry_date": "2026-08-12", "entry_date_source": "execution_leg", '
    '"entry_price": 10.82, "schwab_instrument_symbol": "CADL", '
    '"schwab_order_id": "1007547048146", "shares": 18}'
)


def seed_fill(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    fill_datetime: str = CADL_FILL_DATETIME,
    action: str = "entry",
    quantity: float = 19.0,
    price: float = 10.81,
    fill_origin: str = "schwab_auto",
    reason: str | None = None,
    schwab_source_value_json: str | None = None,
) -> int:
    """Seed a fill.  THE ENVELOPE IS MODELLED EXPLICITLY (RD, 2026-08-26).

    This helper defaulted ``fill_origin='schwab_auto'`` and did not model
    ``schwab_source_value_json`` AT ALL, and that silence was an unresolved
    fact rather than a neutral omission: ``schwab_auto`` carries an envelope BY
    CONSTRUCTION (both production writers build the two in one expression), so
    every fixture built on this helper was quietly asserting a pair no
    production writer produces -- the INCONSISTENT EVIDENCE PAIR of RD's own
    22A-R3-13 ruling.  The parameter makes the choice VISIBLE at each call
    site: ``None`` now means "this fixture deliberately models an
    envelope-less fill", which is a statement rather than a default.

    AND WHEN AN ENVELOPE IS SET, ITS STORED READING IS SET WITH IT.  Migration
    0037's citation trigger compares the AUTHORITY'S PERSISTED reading of the
    envelope, never the document (PERSIST-CANONICAL); production writes the two
    together in ``insert_fill_with_event``.  A fixture that wrote only the
    document would be modelling a state no writer produces and would fail
    closed -- correctly, but for a reason about the fixture rather than about
    the code under test.
    """
    cur = conn.execute(
        """
        INSERT INTO fills (
            trade_id, fill_datetime, action, quantity, price, reason,
            reconciliation_status, fill_origin, schwab_source_value_json
        ) VALUES (?, ?, ?, ?, ?, ?, 'unreconciled', ?, ?)
        """,
        (trade_id, fill_datetime, action, quantity, price, reason,
         fill_origin, schwab_source_value_json),
    )
    fill_id = int(cur.lastrowid)
    if schwab_source_value_json is not None:
        _record_envelope_identity(conn, fill_id, schwab_source_value_json)
    return fill_id


def _record_envelope_identity(
    conn: sqlite3.Connection, fill_id: int, envelope: str,
) -> None:
    from swing.data.repos.fill_envelope_identity import (
        record_identity,
        table_exists,
    )
    if table_exists(conn):
        record_identity(conn, fill_id=fill_id, envelope_raw=envelope)


def set_fill_envelope(
    conn: sqlite3.Connection, fill_id: int, envelope: str | None,
) -> None:
    """Put an envelope on an EXISTING fill the way production does.

    A raw ``UPDATE fills SET schwab_source_value_json = ...`` writes the
    document and no reading, which post-0037 is a fill whose envelope the
    authority has never seen -- a state the citation trigger refuses.  Tests
    that want the ORDINARY shape use this; a test that wants the unread state
    writes the raw UPDATE deliberately and says so.
    """
    conn.execute(
        "UPDATE fills SET schwab_source_value_json = ? WHERE fill_id = ?",
        (envelope, fill_id))
    if envelope is not None:
        _record_envelope_identity(conn, fill_id, envelope)


def rebase_status_history_recorded_at(
    conn: sqlite3.Connection, *, recorded_at: str = "2026-04-25T00:00:00.000",
) -> None:
    """Make every seeded status interval CONTEMPORANEOUS.

    `ensure_schema` runs migration 0017, whose seeds carry
    `recorded_at = <migration apply time>` -- i.e. TODAY. Those are backdated
    assertions and the surface REFUSES them by design (plan section 3.4.1).
    A fixture that wants an ADMISSIBLE interval says so explicitly here; a
    fixture that wants the retrospective refusal just skips this call.
    """
    # 22-I: 0041's trg_hsh_immutable freezes recorded_at. The seeded rows are
    # written BY THE MIGRATION (stamped at apply time) and are undeletable, so
    # the contemporaneous world cannot be re-planted by a raw INSERT; the guard
    # is dropped on this TEST DB for the rebase only (tests/_22i_guard_seam.py;
    # a fixture-construction use, reported in the 22-I exec ledger).
    from tests._22i_guard_seam import guards_dropped

    with guards_dropped(conn, "trg_hsh_immutable"):
        conn.execute(
            "UPDATE hypothesis_status_history SET recorded_at = ?",
            (recorded_at,),
        )


def build_cadl_case(
    conn: sqlite3.Connection,
    *,
    run_ts: str = CADL_RUN_TS_LOCAL,
    data_asof_date: str = CADL_DATA_ASOF,
    action_session_date: str = CADL_ACTION_SESSION,
    dr_action_session_date: str | None = None,
    dr_data_asof_date: str | None = None,
    recommendation: str = "today_decision",
    bucket: str = "aplus",
    non_pass: dict[str, str] | None = None,
    fill_datetime: str = CADL_FILL_DATETIME,
    entry_date: str = CADL_F,
    trade_state: str = "entered",
    pipeline_finished_ts: str | None = CADL_PIPELINE_FINISHED_LOCAL,
    pipeline_state: str = "complete",
    pipeline_rows: int = 1,
    contemporaneous_history: bool = True,
    entry_intent: str | None = "standard",
    ticker: str = CADL_TICKER,
    fill_envelope: str | None = None,
) -> dict[str, Any]:
    """The full ACCEPTING CADL shape, with every knob a refusal test needs.

    Defaults reproduce the live case exactly: an `aplus` candidate whose only
    non-pass criterion is `TT8_rs_rank='na'`, a same-run `today_decision`
    recommendation, an entry fill on 2026-08-12, and a single COMPLETE
    pipeline run bounding the persistence window.

    ``fill_envelope`` IS MODELLED EXPLICITLY AND DEFAULTS TO ABSENT (RD,
    2026-08-26), AND THE DEFAULT IS A STATEMENT RATHER THAN A GAP.

    The live fill CARRIES an envelope -- ``CADL_LIVE_ENVELOPE`` above, read
    verbatim off the row -- so "reproduces the live case exactly" was never
    true of this field, and the fixture was modelling a trusted origin with no
    envelope: the pair RD's 22A-R3-13 ruling exists to flag, which no writer
    produces. The DEFAULT stays absent because the correction-surface cases
    built on it were written against that world and the ruling is scoped to the
    ENTRY path, so flipping the default would re-point roughly a hundred tests
    that are about something else. Callers that want the LIVE shape now say so,
    and ``test_the_live_CADL_shape_is_a_pair_a_writer_actually_produces``
    exercises it.

    When an envelope IS supplied, its stored reading is written with it --
    production writes the two together, and migration 0037's citation trigger
    compares the reading rather than the document (PERSIST-CANONICAL).
    """
    if non_pass is None:
        non_pass = {"TT8_rs_rank": "na"}
    run_id = seed_evaluation_run(
        conn, run_ts=run_ts, data_asof_date=data_asof_date,
        action_session_date=action_session_date,
    )
    pipeline_ids: list[int] = []
    for _ in range(pipeline_rows):
        pipeline_ids.append(seed_pipeline_run(
            conn, evaluation_run_id=run_id, data_asof_date=data_asof_date,
            action_session_date=action_session_date,
            finished_ts=pipeline_finished_ts, state=pipeline_state,
        ))
    candidate_id = seed_candidate(
        conn, evaluation_run_id=run_id, ticker=ticker, bucket=bucket,
        non_pass=non_pass,
    )
    dr_id = seed_recommendation(
        conn, evaluation_run_id=run_id,
        data_asof_date=dr_data_asof_date or data_asof_date,
        action_session_date=dr_action_session_date or action_session_date,
        ticker=ticker, recommendation=recommendation,
    )
    trade_id = seed_trade(
        conn, ticker=ticker, entry_date=entry_date, state=trade_state,
        entry_intent=entry_intent,
    )
    fill_id = seed_fill(
        conn, trade_id=trade_id, fill_datetime=fill_datetime,
        schwab_source_value_json=fill_envelope,
    )
    if contemporaneous_history:
        rebase_status_history_recorded_at(conn)
    # The PRODUCTION recommendation snapshot, so a test that needs one never
    # hand-writes a partial object production cannot emit.
    from swing.data.repos.recommendations import snapshot_recommendation_row
    return {
        "dr_snapshot": snapshot_recommendation_row(conn, dr_id),
        "evaluation_run_id": run_id,
        "pipeline_run_id": pipeline_ids[0] if pipeline_ids else None,
        "pipeline_run_ids": pipeline_ids,
        "candidate_id": candidate_id,
        "daily_recommendation_id": dr_id,
        "trade_id": trade_id,
        "fill_id": fill_id,
    }


# ===========================================================================
# THE LIVE SG CASE (trade 29 / fill 60 / candidates 15811, 15901, 15980;
# evaluation runs 192-194 / pipeline runs 206-208), the D104 watch-fire
# relabel arc.  Every value below was read `mode=ro` off the operator's live
# database on 2026-11-11 (the plan's live-shape facts); the criteria are the
# 18 live `candidate_criteria` rows per candidate, VERBATIM and in rowid
# order.  Values NOT read live are named where they are set.
# ===========================================================================
SG_TICKER = "SG"
SG_TRADE_ID = 29
SG_FILL_ID = 60
SG_FIRE_CANDIDATE_ID = 15901        # eval 193, the H2 fire (D104)
SG_LAST_WORD_CANDIDATE_ID = 15980   # eval 194, the batch night
SG_OLDER_CANDIDATE_ID = 15811       # eval 192
SG_FILL_DATETIME = "2026-11-06T16:00:00"
SG_FILL_SESSION = "2026-11-06"
SG_BASELINE_LABEL = (
    "Broad-watch baseline (watch); failed: proximity_20ma, tightness")
# The label RD witnessed in the 2026-11-05 briefing (brief section 0).
SG_FIRE_LABEL = (
    "Near-A+ defensible: extension test (watch); failed: proximity_20ma")
SG_WATCH_MANUAL_ORIGIN = "pipeline_watch_manual"
SG_BY_DESIGN_INTENT = "hypothesis_test_by_design"
SG_LIVE_ENVELOPE = (
    '{"entry_date": "2026-11-06", "entry_date_source": "execution_leg", '
    '"entry_price": 11.945, "schwab_instrument_symbol": "SG", '
    '"schwab_order_id": "1008560562620", "shares": 11}'
)
SG_LIVE_OPERATOR_CORRECTED = (
    '{"entry_date": "2026-11-06", "entry_price": 11.95, "shares": 11}')

# (eval id, run_ts, data_asof, action_session, pipeline id, started, finished)
SG_RUNS: tuple[tuple[int, str, str, str, int, str, str], ...] = (
    (192, "2026-11-03T17:30:04", "2026-11-03", "2026-11-04",
     206, "2026-11-03T17:30:04", "2026-11-03T17:34:17"),
    (193, "2026-11-04T17:30:04", "2026-11-04", "2026-11-05",
     207, "2026-11-04T17:30:04", "2026-11-04T17:34:17"),
    (194, "2026-11-05T17:30:15", "2026-11-05", "2026-11-06",
     208, "2026-11-05T17:30:15", "2026-11-05T17:36:20"),
)

# candidate id -> (eval id, close, pivot, initial_stop, adr_pct, tight_streak,
#                  pullback_pct, prior_trend_pct, rs_return_12w_vs_spy)
SG_CANDIDATES: dict[int, tuple] = {
    15811: (192, 11.40999984741211, 11.949000358581543, 8.970000267028809,
            5.270621989764364, 1, 0.52, 94.89, 1.1177427462780027),
    15901: (193, 11.800000190734863, 11.949000358581543, 8.975000381469727,
            5.263322736970535, 2, 0.0, 103.62, 1.1941060122593852),
    15980: (194, 11.550000190734863, 11.949000358581543, 9.460000038146973,
            5.259590449667274, 0, 2.12, 104.89, 1.0356564475700996),
}

SG_CRITERIA: dict[int, tuple[tuple[str, str, str, str | None, str | None], ...]] = {
    15811: (
        ('TT1_above_150_200', 'trend_template', 'pass', 'close=11.41 150MA=7.72 200MA=7.23', 'close > 150MA AND close > 200MA'),
        ('TT2_150_above_200', 'trend_template', 'pass', '150MA=7.72 200MA=7.23', '150MA > 200MA'),
        ('TT3_200_rising', 'trend_template', 'pass', '200MA now=7.23 vs 21bars ago=6.91', '200MA rising over 21 bars'),
        ('TT4_50_above_150_200', 'trend_template', 'pass', '50MA=8.63 150MA=7.72 200MA=7.23', '50MA > 150MA AND 50MA > 200MA'),
        ('TT5_above_50', 'trend_template', 'pass', 'close=11.41 50MA=8.63', 'close > 50MA'),
        ('TT6_above_52w_low_30pct', 'trend_template', 'pass', '+142.8% above 52w low', '>= 30.0% above 52w low'),
        ('TT7_within_52w_high_25pct', 'trend_template', 'pass', '-0.5% from 52w high', '<= 25.0% below 52w high'),
        ('TT8_rs_rank', 'trend_template', 'pass', 'fallback, excess=+111.77% vs SPY 12w', 'outside universe; pass if excess >= +20%'),
        ('prior_trend', 'vcp', 'pass', '94.9%', '>= 25.0% required'),
        ('ma_stack_10_20_50', 'vcp', 'pass', '10MA=10.70 20MA=10.34 50MA=8.63', '10MA > 20MA > 50MA'),
        ('ma_short_rising', 'vcp', 'pass', '10:True 20:True 50:True', 'all three short MAs rising over 5 bars'),
        ('proximity_20ma', 'vcp', 'fail', '+10.32%', '|price - 20MA| <= 5.0% of 20MA'),
        ('adr', 'vcp', 'pass', '5.27%', '>= 4.0% required for sufficient volatility'),
        ('pullback', 'vcp', 'pass', '0.5%', '< 25.0% from consolidation high'),
        ('tightness', 'vcp', 'fail', '1 day streak', '>= 2 consec. days with range <= 0.67 x ADR (3.53%)'),
        ('vcp_volume_contraction', 'vcp', 'pass', 'cons:4,373,110 vs trend:5,883,923', 'consolidation avg volume < prior trend avg volume'),
        ('orderliness', 'vcp', 'pass', 'max 2.68x, CV 0.46', 'max bar <= 3.0x median AND range CV <= 0.60'),
        ('risk_feasibility', 'risk', 'pass', '12 sh, $35.75 risk', '>= 1 share fits in 0.5% of equity ($37.50)'),
    ),
    15901: (
        ('TT1_above_150_200', 'trend_template', 'pass', 'close=11.80 150MA=7.77 200MA=7.25', 'close > 150MA AND close > 200MA'),
        ('TT2_150_above_200', 'trend_template', 'pass', '150MA=7.77 200MA=7.25', '150MA > 200MA'),
        ('TT3_200_rising', 'trend_template', 'pass', '200MA now=7.25 vs 21bars ago=6.92', '200MA rising over 21 bars'),
        ('TT4_50_above_150_200', 'trend_template', 'pass', '50MA=8.73 150MA=7.77 200MA=7.25', '50MA > 150MA AND 50MA > 200MA'),
        ('TT5_above_50', 'trend_template', 'pass', 'close=11.80 50MA=8.73', 'close > 50MA'),
        ('TT6_above_52w_low_30pct', 'trend_template', 'pass', '+151.1% above 52w low', '>= 30.0% above 52w low'),
        ('TT7_within_52w_high_25pct', 'trend_template', 'pass', '-0.0% from 52w high', '<= 25.0% below 52w high'),
        ('TT8_rs_rank', 'trend_template', 'pass', 'fallback, excess=+119.41% vs SPY 12w', 'outside universe; pass if excess >= +20%'),
        ('prior_trend', 'vcp', 'pass', '103.6%', '>= 25.0% required'),
        ('ma_stack_10_20_50', 'vcp', 'pass', '10MA=10.86 20MA=10.48 50MA=8.73', '10MA > 20MA > 50MA'),
        ('ma_short_rising', 'vcp', 'pass', '10:True 20:True 50:True', 'all three short MAs rising over 5 bars'),
        ('proximity_20ma', 'vcp', 'fail', '+12.65%', '|price - 20MA| <= 5.0% of 20MA'),
        ('adr', 'vcp', 'pass', '5.26%', '>= 4.0% required for sufficient volatility'),
        ('pullback', 'vcp', 'pass', '0.0%', '< 25.0% from consolidation high'),
        ('tightness', 'vcp', 'pass', '2 day streak', '>= 2 consec. days with range <= 0.67 x ADR (3.53%)'),
        ('vcp_volume_contraction', 'vcp', 'pass', 'cons:4,397,585 vs trend:5,886,952', 'consolidation avg volume < prior trend avg volume'),
        ('orderliness', 'vcp', 'pass', 'max 2.68x, CV 0.46', 'max bar <= 3.0x median AND range CV <= 0.60'),
        ('risk_feasibility', 'risk', 'pass', '12 sh, $35.69 risk', '>= 1 share fits in 0.5% of equity ($37.50)'),
    ),
    15980: (
        ('TT1_above_150_200', 'trend_template', 'pass', 'close=11.55 150MA=7.81 200MA=7.28', 'close > 150MA AND close > 200MA'),
        ('TT2_150_above_200', 'trend_template', 'pass', '150MA=7.81 200MA=7.28', '150MA > 200MA'),
        ('TT3_200_rising', 'trend_template', 'pass', '200MA now=7.28 vs 21bars ago=6.93', '200MA rising over 21 bars'),
        ('TT4_50_above_150_200', 'trend_template', 'pass', '50MA=8.82 150MA=7.81 200MA=7.28', '50MA > 150MA AND 50MA > 200MA'),
        ('TT5_above_50', 'trend_template', 'pass', 'close=11.55 50MA=8.82', 'close > 50MA'),
        ('TT6_above_52w_low_30pct', 'trend_template', 'pass', '+145.7% above 52w low', '>= 30.0% above 52w low'),
        ('TT7_within_52w_high_25pct', 'trend_template', 'pass', '-2.1% from 52w high', '<= 25.0% below 52w high'),
        ('TT8_rs_rank', 'trend_template', 'pass', 'fallback, excess=+103.57% vs SPY 12w', 'outside universe; pass if excess >= +20%'),
        ('prior_trend', 'vcp', 'pass', '104.9%', '>= 25.0% required'),
        ('ma_stack_10_20_50', 'vcp', 'pass', '10MA=11.00 20MA=10.57 50MA=8.82', '10MA > 20MA > 50MA'),
        ('ma_short_rising', 'vcp', 'pass', '10:True 20:True 50:True', 'all three short MAs rising over 5 bars'),
        ('proximity_20ma', 'vcp', 'fail', '+9.23%', '|price - 20MA| <= 5.0% of 20MA'),
        ('adr', 'vcp', 'pass', '5.26%', '>= 4.0% required for sufficient volatility'),
        ('pullback', 'vcp', 'pass', '2.1%', '< 25.0% from consolidation high'),
        ('tightness', 'vcp', 'fail', '0 day streak', '>= 2 consec. days with range <= 0.67 x ADR (3.52%)'),
        ('vcp_volume_contraction', 'vcp', 'pass', 'cons:4,458,440 vs trend:5,851,485', 'consolidation avg volume < prior trend avg volume'),
        ('orderliness', 'vcp', 'pass', 'max 2.68x, CV 0.46', 'max bar <= 3.0x median AND range CV <= 0.60'),
        ('risk_feasibility', 'risk', 'pass', '15 sh, $37.34 risk', '>= 1 share fits in 0.5% of equity ($37.50)'),
    ),
}

# The live `hypothesis_status_history`, rows 1-8 (history_id, hypothesis_id,
# status, effective_from, effective_to, recorded_at, change_reason).  The
# change_reason of row 7 is ABBREVIATED (233 chars live; not
# derivation-bearing); every other value is verbatim.
SG_LIVE_HISTORY: tuple[tuple, ...] = (
    (1, 1, "active", "2026-04-25T00:00:00.000", None,
     "2026-05-12T08:18:10.560", None),
    (2, 2, "active", "2026-04-25T00:00:00.000", "2026-05-12T17:22:54.847",
     "2026-05-12T08:18:10.560", None),
    (3, 3, "active", "2026-04-25T00:00:00.000", "2026-06-04T07:18:45.126",
     "2026-05-12T08:18:10.560", None),
    (4, 4, "active", "2026-04-25T00:00:00.000", None,
     "2026-05-12T08:18:10.560", None),
    (5, 2, "paused", "2026-05-12T17:22:54.847", "2026-05-12T17:22:56.143",
     "2026-05-12T17:22:54.847", "operator gate S4 (will revert)"),
    (6, 2, "active", "2026-05-12T17:22:56.143", None,
     "2026-05-12T17:22:56.143", "operator gate S4 revert to baseline"),
    (7, 3, "closed-target-met", "2026-06-04T07:18:45.126", None,
     "2026-06-04T07:18:45.126",
     "n=10 (2x target 5); mean R -0.20; net -$79.02; win rate 20%. "
     "(abbreviated in the fixture)"),
    (8, 5, "active", "2026-06-09T00:00:00.000", None,
     "2026-06-10T09:43:00.617", None),
)


def seed_sg_registry_as_live(conn: sqlite3.Connection) -> None:
    """Make the registry and its history the live 2026-11-11 shape.

    `ensure_schema` writes H3 `active` and history rows 1-5 (row 5 = H5)
    stamped at apply time; live has H3 `closed-target-met`, H2's
    active/paused/active cycle and H5 at row 8.  The migration-written rows
    are held by 0041's no_delete + immutable guards, so this is the
    guard-seam's kind 4 (fixture construction over migration-written rows,
    reproducing the live shape).
    """
    from tests._22i_guard_seam import guards_dropped

    with guards_dropped(conn, "trg_hsh_no_delete", "trg_hsh_immutable",
                        "trg_hsh_no_replace"):
        conn.execute("DELETE FROM hypothesis_status_history")
        conn.executemany(
            "INSERT INTO hypothesis_status_history (history_id, hypothesis_id,"
            " status, effective_from, effective_to, recorded_at,"
            " change_reason) VALUES (?, ?, ?, ?, ?, ?, ?)",
            SG_LIVE_HISTORY)
    conn.execute(
        "UPDATE hypothesis_registry SET status = 'closed-target-met', "
        "status_changed_at = '2026-06-04T07:18:45.126' WHERE id = 3")
    conn.execute(
        "UPDATE hypothesis_registry SET status_changed_at = "
        "'2026-05-12T17:22:56.143' WHERE id = 2")


def build_sg_case(
    conn: sqlite3.Connection,
    *,
    entry_intent: str = SG_BY_DESIGN_INTENT,
    trade_origin: str = SG_WATCH_MANUAL_ORIGIN,
    hypothesis_label: str | None = SG_BASELINE_LABEL,
    candidate_id: int | None = SG_LAST_WORD_CANDIDATE_ID,
    buckets: dict[int, str] | None = None,
    fill_price: float = 11.95,
    pipeline_complete: dict[int, bool] | None = None,
    live_registry: bool = True,
    criteria_results: dict[int, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Trade 29's live world: three SG watch rows, its trade, fill and FEI row.

    No `daily_recommendations` row exists for SG on 193 or 194 (live).  No
    latch link exists for the fill's order (live).  ``buckets``,
    ``pipeline_complete`` and ``criteria_results`` (candidate id ->
    criterion name -> result, overriding the live RESULT only, planted by
    the same raw INSERT) are refusal-test knobs; the defaults are live.
    """
    buckets = dict(buckets or {})
    pipeline_complete = dict(pipeline_complete or {})
    criteria_results = dict(criteria_results or {})
    for (run_id, run_ts, asof, action, pr_id, started,
         finished) in SG_RUNS:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, finviz_csv_path, tickers_evaluated, "
            "aplus_count, watch_count, skip_count, excluded_count, "
            "error_count) VALUES (?, ?, ?, ?, NULL, 85, 0, 16, 68, 1, 0)",
            (run_id, run_ts, asof, action))
        if pipeline_complete.get(run_id, True):
            conn.execute(
                "INSERT INTO pipeline_runs (id, started_ts, finished_ts, "
                "trigger, data_asof_date, action_session_date, state, "
                "lease_token, evaluation_run_id) VALUES "
                "(?, ?, ?, 'scheduled', ?, ?, 'complete', ?, ?)",
                (pr_id, started, finished, asof, action, f"lease-{pr_id}",
                 run_id))
    for cid, (run_id, close, pivot, stop, adr, tight, pullback, prior,
              rs_ret) in SG_CANDIDATES.items():
        conn.execute(
            "INSERT INTO candidates (id, evaluation_run_id, ticker, bucket, "
            "close, pivot, initial_stop, adr_pct, tight_streak, pullback_pct,"
            " prior_trend_pct, rs_rank, rs_return_12w_vs_spy, rs_method, "
            "pattern_tag, notes, sector, industry) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, 'fallback_spy', NULL,"
            " NULL, 'Consumer Cyclical', 'Restaurants')",
            (cid, run_id, SG_TICKER, buckets.get(cid, "watch"), close, pivot,
             stop, adr, tight, pullback, prior, rs_ret))
        conn.executemany(
            "INSERT INTO candidate_criteria (candidate_id, criterion_name, "
            "layer, result, value, rule) VALUES (?, ?, ?, ?, ?, ?)",
            [(cid, name, layer,
              criteria_results.get(cid, {}).get(name, result), value, rule)
             for (name, layer, result, value, rule) in SG_CRITERIA[cid]])
    if live_registry:
        seed_sg_registry_as_live(conn)
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, trade_origin, "
        "pre_trade_locked_at, current_size, current_avg_cost, last_fill_at, "
        "hypothesis_label, candidate_id, entry_intent, sector, industry) "
        "VALUES (?, ?, ?, ?, 11, 8.98, 8.98, 'managing', ?, ?, 11.0, ?, ?, "
        "?, ?, ?, 'Consumer Cyclical', 'Restaurants')",
        (SG_TRADE_ID, SG_TICKER, SG_FILL_SESSION, fill_price, trade_origin,
         SG_FILL_DATETIME, fill_price, SG_FILL_DATETIME, hypothesis_label,
         candidate_id, entry_intent))
    conn.execute(
        "INSERT INTO fills (fill_id, trade_id, fill_datetime, action, "
        "quantity, price, manual_entry_confidence, reconciliation_status, "
        "fill_origin, schwab_source_value_json, operator_corrected_value_json,"
        " auto_fill_audit_at) VALUES (?, ?, ?, 'entry', 11.0, ?, 'normal', "
        "'unreconciled', 'schwab_auto_then_operator_corrected', ?, ?, "
        "'2026-11-06T20:43:54.570250+00:00')",
        (SG_FILL_ID, SG_TRADE_ID, SG_FILL_DATETIME, fill_price,
         SG_LIVE_ENVELOPE, SG_LIVE_OPERATOR_CORRECTED))
    _record_envelope_identity(conn, SG_FILL_ID, SG_LIVE_ENVELOPE)
    return {
        "trade_id": SG_TRADE_ID,
        "fill_id": SG_FILL_ID,
        "fire_candidate_id": SG_FIRE_CANDIDATE_ID,
        "last_word_candidate_id": SG_LAST_WORD_CANDIDATE_ID,
        "older_candidate_id": SG_OLDER_CANDIDATE_ID,
        "fire_evaluation_run_id": 193,
        "fire_pipeline_run_id": 207,
    }


def watch_fire_payload(
    conn: sqlite3.Connection, *, fire_candidate_id: int = SG_FIRE_CANDIDATE_ID,
    trade_id: int = SG_TRADE_ID, apply_trade_update: bool = True,
    correction_kind: str = "watch_fire_relabel",
    admission_tier: str = "last_fire",
) -> dict[str, Any]:
    """The kind-2 row's every column, from the PRODUCTION derivation helpers.

    Built from ``derive_cohort_keys_for_fire`` (the one derivation), the
    production snapshot helpers and the authoritative-fill resolver, so the
    row is the emitter's shape rather than a hand-written one.  With
    ``apply_trade_update`` the trade is first moved to the applied values
    through the production writer, as the service does (the citation
    trigger's kind-2 arm reads the trade at INSERT time).
    """
    from swing.data.repos.trades import update_cohort_provenance
    from swing.trades import cohort_provenance_correction as cpc

    trade = cpc._load_trade_or_refuse(conn, trade_id)
    fill = cpc.resolve_authoritative_entry_fill(conn, trade_id)
    cited = cpc.fetch_candidate_by_id(conn, fire_candidate_id)
    run = cpc.get_evaluation_run_by_id(conn, cited.evaluation_run_id)
    run_ts_parsed = cpc._require_naive_datetime(run.run_ts, what="run_ts")
    keys = cpc.derive_cohort_keys_for_fire(
        conn, candidate=cited.candidate, candidate_id=fire_candidate_id,
        evaluation_run_id=int(cited.evaluation_run_id),
        run_ts_parsed=run_ts_parsed)
    pre = {
        "trades.hypothesis_label": trade.hypothesis_label,
        "trades.candidate_id": trade.candidate_id,
        "trades.trade_origin": trade.trade_origin,
    }
    applied = {
        "trades.hypothesis_label": keys.hypothesis_label,
        "trades.candidate_id": fire_candidate_id,
        "trades.trade_origin": trade.trade_origin,
    }
    if apply_trade_update:
        update_cohort_provenance(
            conn, trade_id=trade_id, hypothesis_label=keys.hypothesis_label,
            candidate_id=fire_candidate_id, trade_origin=trade.trade_origin)
    si = keys.status_interval
    return {
        "trade_id": trade_id,
        "entry_fill_id": fill.fill_id,
        "entry_fill_id_at_correction": fill.fill_id,
        "entry_fill_snapshot_json": json.dumps(fill.snapshot(), sort_keys=True),
        "cited_candidate_id": fire_candidate_id,
        "cited_daily_recommendation_id": None,
        "cited_evaluation_run_id": int(cited.evaluation_run_id),
        "cited_hypothesis_id": keys.hypothesis_id,
        "cited_hypothesis_status_history_id": si.history_id,
        "cited_hypothesis_status_at_record": si.status,
        "cited_pipeline_finished_ts_raw": keys.pipeline_finished_ts_raw,
        "cited_run_ts_utc": cpc._to_utc_naive(run_ts_parsed).isoformat(),
        "cited_status_window_upper_utc": keys.status_window_upper_utc,
        "cited_pipeline_run_id": keys.pipeline_run_id,
        "cited_pipeline_run_snapshot_json": json.dumps(
            keys.pipeline_snapshot, sort_keys=True),
        "cited_hypothesis_status_recorded_at": si.recorded_at_raw,
        "cited_hypothesis_status_effective_from": si.effective_from_raw,
        "cited_hypothesis_status_effective_to": si.effective_to_raw,
        "cited_hypothesis_name_at_correction": keys.hypothesis_name,
        "cited_candidate_action_session_date": str(run.action_session_date),
        "cited_recommendation_action_session_date": None,
        "entry_fill_session_date": SG_FILL_SESSION,
        "cited_run_ts_raw": str(run.run_ts),
        "cited_recommendation_snapshot_json": None,
        "cited_candidate_snapshot_json": json.dumps(
            cpc.candidate_provenance_snapshot(cited), sort_keys=True),
        "derivation_rule_version": cpc.DERIVATION_RULE_VERSION,
        "pre_value_json": json.dumps(pre, sort_keys=True),
        "applied_value_json": json.dumps(applied, sort_keys=True),
        "corrected_fields_json": json.dumps(
            ["trades.hypothesis_label", "trades.candidate_id"]),
        "applied_at": "2026-11-12T09:00:00",
        "applied_by": "operator",
        "correction_reason": "D104 fixture: the SG fire relabel",
        "admission_tier": admission_tier,
        "correction_kind": correction_kind,
    }
