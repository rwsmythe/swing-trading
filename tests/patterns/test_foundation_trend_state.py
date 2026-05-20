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
