# research/harness/minervini_exemplar_recall/stage_db.py
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from swing.data.db import ensure_schema
from swing.data.models import Candidate, CriterionResult, EvaluationRun
from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
from swing.patterns.foundation import current_stage

_FORCED_TT = tuple(
    CriterionResult(f"TT{i + 1}", "trend_template", "pass") for i in range(8)
)


def build_stage_db(path: Path) -> sqlite3.Connection:
    """Fresh v24 schema-correct scratch DB (writable research scratch, not production)."""
    return ensure_schema(Path(path))


def _minimal_candidate(ticker: str, tt_results: tuple[CriterionResult, ...]) -> Candidate:
    return Candidate(
        ticker=ticker,
        bucket="aplus",  # bucket is irrelevant to current_stage; any value is fine.
        close=None,
        pivot=None,
        initial_stop=None,
        adr_pct=None,
        tight_streak=None,
        pullback_pct=None,
        prior_trend_pct=None,
        rs_rank=None,
        rs_return_12w_vs_spy=None,
        rs_method="unavailable",
        pattern_tag=None,
        notes=None,
        criteria=tuple(tt_results),
    )


def seed_session(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    session: date,
    tt_results: tuple[CriterionResult, ...],
    mode: str,
) -> None:
    """Insert one evaluation_run + candidate keyed at action_session_date=session.

    mode='faithful' -> seed the session's actual 8 trend_template results (stage_2 iff 8/8 pass).
    mode='isolated' -> 8 forced 'pass' rows (always stage_2)."""
    if mode == "isolated":
        criteria = _FORCED_TT
    elif mode == "faithful":
        criteria = tuple(c for c in tt_results if c.layer == "trend_template")
        names = {c.criterion_name for c in criteria}
        # Exactly 8 UNIQUE TT names: current_stage counts result='pass' rows blindly, so 8
        # duplicate passes would falsely seed stage_2 (spec section 6.1 missing/duplicate guard).
        if len(criteria) != 8 or len(names) != 8:
            raise ValueError(
                f"faithful seed needs exactly 8 UNIQUE trend_template rows, "
                f"got {len(criteria)} rows / {len(names)} distinct names"
            )
    else:
        raise ValueError(f"unknown stage mode: {mode!r}")

    iso = session.isoformat()
    run = EvaluationRun(
        id=None,
        run_ts=f"{iso}T00:00:00+00:00",
        data_asof_date=iso,
        action_session_date=iso,
        finviz_csv_path=None,
        tickers_evaluated=1,
        aplus_count=1,
        watch_count=0,
        skip_count=0,
        excluded_count=0,
        error_count=0,
    )
    with conn:
        run_id = insert_evaluation_run(conn, run)
        insert_candidates(conn, run_id, [_minimal_candidate(ticker, criteria)])


def stage_at(conn: sqlite3.Connection, ticker: str, session: date) -> str:
    return current_stage(conn, ticker, session)
