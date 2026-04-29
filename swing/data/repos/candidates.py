"""Candidates + CandidateCriteria repository."""
from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from swing.data.models import Candidate, CriterionResult, EvaluationRun


def insert_evaluation_run(conn: sqlite3.Connection, run: EvaluationRun) -> int:
    """Insert an evaluation_runs row. Does NOT commit — caller wraps in a transaction
    (e.g. `with conn:`) so the run + candidates + criteria persist atomically.
    """
    cur = conn.execute(
        """
        INSERT INTO evaluation_runs
            (run_ts, data_asof_date, action_session_date, finviz_csv_path,
             tickers_evaluated, aplus_count, watch_count, skip_count,
             excluded_count, error_count, rs_universe_version, rs_universe_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run.run_ts,
            run.data_asof_date,
            run.action_session_date,
            run.finviz_csv_path,
            run.tickers_evaluated,
            run.aplus_count,
            run.watch_count,
            run.skip_count,
            run.excluded_count,
            run.error_count,
            run.rs_universe_version,
            run.rs_universe_hash,
        ),
    )
    return int(cur.lastrowid)


def insert_candidates(
    conn: sqlite3.Connection, run_id: int, candidates: Sequence[Candidate]
) -> None:
    """Insert candidate + criteria rows. Does NOT commit — caller wraps in a transaction."""
    for c in candidates:
        cur = conn.execute(
            """
            INSERT INTO candidates
                (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                 adr_pct, tight_streak, pullback_pct, prior_trend_pct,
                 rs_rank, rs_return_12w_vs_spy, rs_method, pattern_tag, notes,
                 sector, industry)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                c.ticker,
                c.bucket,
                c.close,
                c.pivot,
                c.initial_stop,
                c.adr_pct,
                c.tight_streak,
                c.pullback_pct,
                c.prior_trend_pct,
                c.rs_rank,
                c.rs_return_12w_vs_spy,
                c.rs_method,
                c.pattern_tag,
                c.notes,
                c.sector,
                c.industry,
            ),
        )
        cid = int(cur.lastrowid)
        for crit in c.criteria:
            conn.execute(
                """
                INSERT INTO candidate_criteria
                    (candidate_id, criterion_name, layer, result, value, rule)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (cid, crit.criterion_name, crit.layer, crit.result, crit.value, crit.rule),
            )


def fetch_candidates_for_run(conn: sqlite3.Connection, run_id: int) -> list[Candidate]:
    cand_rows = conn.execute(
        """
        SELECT id, ticker, bucket, close, pivot, initial_stop, adr_pct,
               tight_streak, pullback_pct, prior_trend_pct, rs_rank,
               rs_return_12w_vs_spy, rs_method, pattern_tag, notes,
               sector, industry
        FROM candidates
        WHERE evaluation_run_id = ?
        ORDER BY ticker
        """,
        (run_id,),
    ).fetchall()

    result: list[Candidate] = []
    for row in cand_rows:
        cid = row[0]
        crit_rows = conn.execute(
            """
            SELECT criterion_name, layer, result, value, rule
            FROM candidate_criteria
            WHERE candidate_id = ?
            ORDER BY criterion_name
            """,
            (cid,),
        ).fetchall()
        criteria = tuple(
            CriterionResult(name, layer, res, val, rule)
            for (name, layer, res, val, rule) in crit_rows
        )
        result.append(
            Candidate(
                ticker=row[1],
                bucket=row[2],
                close=row[3],
                pivot=row[4],
                initial_stop=row[5],
                adr_pct=row[6],
                tight_streak=row[7],
                pullback_pct=row[8],
                prior_trend_pct=row[9],
                rs_rank=row[10],
                rs_return_12w_vs_spy=row[11],
                rs_method=row[12],
                pattern_tag=row[13],
                notes=row[14],
                criteria=criteria,
                sector=row[15],
                industry=row[16],
            )
        )
    return result
