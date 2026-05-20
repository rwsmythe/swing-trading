"""Phase 13 T2.SB2 T-A.2.5 - discriminating tests for current_stage wrapper.

Per plan section G.3 T-A.2.5 Step 2: 2 failing tests covering
``current_stage`` thin wrapper over the shipped Phase 4 evaluation
surface per spec section 5.1.5 LOCK.

V1 LOCK on wrapper semantics: Stage 2 = all 8 TT trend_template checks
pass for the most-recent ``(ticker, action_session_date <= asof_date)``
candidate row. Otherwise -> ``'undefined'``. Full Weinstein 4-stage
labeling (Stage 1/3/4) is V2-deferred (spec line 523 "thin wrapper").
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.evaluation.criteria.trend_template import CHECK_NAMES
from swing.patterns.foundation import current_stage


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase13_t2sb2_trend_state.db"
    return ensure_schema(db_path)


def _plant_aplus_candidate(
    conn: sqlite3.Connection,
    ticker: str,
    action_session: str,
    all_tt_pass: bool,
) -> int:
    cur = conn.execute(
        """INSERT INTO evaluation_runs
           (run_ts, data_asof_date, action_session_date, finviz_csv_path,
            tickers_evaluated, aplus_count, watch_count, skip_count,
            excluded_count, error_count,
            rs_universe_version, rs_universe_hash)
           VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'h1')""",
        (f"{action_session}T21:00:00", action_session, action_session),
    )
    e_id = int(cur.lastrowid)
    cur = conn.execute(
        """INSERT INTO candidates
           (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
            rs_method)
           VALUES (?, ?, 'aplus', 100.0, 101.0, 95.0, 'universe')""",
        (e_id, ticker),
    )
    c_id = int(cur.lastrowid)
    for name in CHECK_NAMES:
        conn.execute(
            """INSERT INTO candidate_criteria
               (candidate_id, criterion_name, layer, result, value, rule)
               VALUES (?, ?, 'trend_template', ?, NULL, NULL)""",
            (c_id, name, "pass" if all_tt_pass else "fail"),
        )
    return c_id


def test_current_stage_returns_stage_2_when_all_8_tt_checks_pass(
    conn: sqlite3.Connection,
) -> None:
    """All 8 trend_template criteria pass for the latest candidate row
    -> wrapper returns ``'stage_2'``.
    """
    with conn:
        _plant_aplus_candidate(
            conn, ticker="AAPL", action_session="2026-04-20", all_tt_pass=True
        )
    out = current_stage(conn, ticker="AAPL", asof_date=date(2026, 4, 20))
    assert out == "stage_2"


def test_current_stage_returns_undefined_when_no_evaluation_for_ticker(
    conn: sqlite3.Connection,
) -> None:
    """Ticker without any evaluation_runs / candidates row -> ``'undefined'``."""
    out = current_stage(conn, ticker="NOSUCH", asof_date=date(2026, 4, 20))
    assert out == "undefined"


def test_current_stage_returns_undefined_when_tt_checks_partially_fail(
    conn: sqlite3.Connection,
) -> None:
    """Defense-in-depth: not all 8 TT pass -> wrapper returns
    ``'undefined'`` per V1 LOCK (Stage 1/3/4 differentiation V2-deferred).
    """
    with conn:
        _plant_aplus_candidate(
            conn, ticker="MSFT", action_session="2026-04-20", all_tt_pass=False
        )
    out = current_stage(conn, ticker="MSFT", asof_date=date(2026, 4, 20))
    assert out == "undefined"


def _plant_candidate_with_tt_state(
    conn: sqlite3.Connection,
    run_id: int,
    ticker: str,
    tt_pass_count: int,
) -> int:
    """Plant one candidate row tied to ``run_id`` + N trend_template
    criterion rows of result='pass' followed by (8-N) of result='fail'.

    Helper for the Codex R1 Major #5 ORDER BY discriminating test. The
    helper deliberately diverges from ``_plant_aplus_candidate`` so the
    caller can control how many TT criteria pass on the planted row.
    """
    cur = conn.execute(
        """INSERT INTO candidates
           (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
            rs_method)
           VALUES (?, ?, 'aplus', 100.0, 101.0, 95.0, 'universe')""",
        (run_id, ticker),
    )
    c_id = int(cur.lastrowid)
    for i, name in enumerate(CHECK_NAMES):
        result = "pass" if i < tt_pass_count else "fail"
        conn.execute(
            """INSERT INTO candidate_criteria
               (candidate_id, criterion_name, layer, result, value, rule)
               VALUES (?, ?, 'trend_template', ?, NULL, NULL)""",
            (c_id, name, result),
        )
    return c_id


def _last_row_id(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT last_insert_rowid()").fetchone()
    return int(row[0])


def test_current_stage_orders_by_run_ts_when_same_action_session_date(
    tmp_path: Path,
) -> None:
    """Codex R1 Major #5: same-session reruns must select by run_ts DESC,
    not by id DESC alone. Plants two evaluation_runs on the same
    action_session_date with the LATER run_ts inserted FIRST (so it gets
    the LOWER id) and the EARLIER run_ts inserted SECOND (so it gets the
    HIGHER id). With id-DESC-only ordering, the second-inserted row wins
    -> only 5 TT pass -> 'undefined'. With run_ts-DESC ordering, the
    first-inserted row wins -> all 8 TT pass -> 'stage_2'.
    """
    db = tmp_path / "stage_ordering.db"
    conn = ensure_schema(db)
    try:
        with conn:
            # FIRST insert: LATER run_ts (this row gets LOWER id).
            conn.execute(
                "INSERT INTO evaluation_runs "
                "(run_ts, data_asof_date, action_session_date, finviz_csv_path, "
                "tickers_evaluated, aplus_count, watch_count, skip_count, "
                "excluded_count, error_count, rs_universe_version, "
                "rs_universe_hash) "
                "VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'h1')",
                ("2026-05-20T16:00:00", "2026-05-20", "2026-05-20"),
            )
            late_runts_low_id = _last_row_id(conn)
            _plant_candidate_with_tt_state(
                conn,
                run_id=late_runts_low_id,
                ticker="AAPL",
                tt_pass_count=8,
            )

            # SECOND insert: EARLIER run_ts (this row gets HIGHER id).
            conn.execute(
                "INSERT INTO evaluation_runs "
                "(run_ts, data_asof_date, action_session_date, finviz_csv_path, "
                "tickers_evaluated, aplus_count, watch_count, skip_count, "
                "excluded_count, error_count, rs_universe_version, "
                "rs_universe_hash) "
                "VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'h1')",
                ("2026-05-20T08:00:00", "2026-05-20", "2026-05-20"),
            )
            early_runts_high_id = _last_row_id(conn)
            _plant_candidate_with_tt_state(
                conn,
                run_id=early_runts_high_id,
                ticker="AAPL",
                tt_pass_count=5,  # partial fail
            )

        out = current_stage(
            conn,
            ticker="AAPL",
            asof_date=date(2026, 5, 20),
        )
        # The LATER run_ts (lower id) wins under run_ts-DESC ordering ->
        # all-8-TT-pass -> 'stage_2'. Under id-DESC-only ordering the
        # higher-id row (with only 5 TT pass) would win -> 'undefined'.
        assert out == "stage_2", (
            f"Expected stage_2 from late-run_ts candidate with all-8-TT-pass; "
            f"got {out!r} - ORDER BY may be using id DESC instead of run_ts DESC"
        )
    finally:
        conn.close()
