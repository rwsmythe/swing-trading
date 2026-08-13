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
) -> int:
    cur = conn.execute(
        """
        INSERT INTO fills (
            trade_id, fill_datetime, action, quantity, price, reason,
            reconciliation_status, fill_origin
        ) VALUES (?, ?, ?, ?, ?, ?, 'unreconciled', ?)
        """,
        (trade_id, fill_datetime, action, quantity, price, reason,
         fill_origin),
    )
    return int(cur.lastrowid)


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
) -> dict[str, Any]:
    """The full ACCEPTING CADL shape, with every knob a refusal test needs.

    Defaults reproduce the live case exactly: an `aplus` candidate whose only
    non-pass criterion is `TT8_rs_rank='na'`, a same-run `today_decision`
    recommendation, an entry fill on 2026-08-12, and a single COMPLETE
    pipeline run bounding the persistence window.
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
    )
    if contemporaneous_history:
        rebase_status_history_recorded_at(conn)
    return {
        "evaluation_run_id": run_id,
        "pipeline_run_id": pipeline_ids[0] if pipeline_ids else None,
        "pipeline_run_ids": pipeline_ids,
        "candidate_id": candidate_id,
        "daily_recommendation_id": dr_id,
        "trade_id": trade_id,
        "fill_id": fill_id,
    }
