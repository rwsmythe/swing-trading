"""Candidates + CandidateCriteria repository."""
from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from swing.data.models import Candidate, CriterionResult, EvaluationRun


def insert_evaluation_run(conn: sqlite3.Connection, run: EvaluationRun) -> int:
    """Insert an evaluation_runs row. Does NOT commit -- caller wraps in a transaction
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
    """Insert candidate + criteria rows. Does NOT commit -- caller wraps in a transaction."""
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


@dataclass(frozen=True)
class CandidateSectorIndustryRecord:
    """Most-recent candidates-row Sector + Industry pair WITH provenance.

    Provenance metadata (candidate_id + evaluation_run_id) carried per
    Codex R1.M#6 LOCK so the V2.G3 backfill dry-run table can cite the
    source_candidate_id + source_evaluation_run_id columns required by
    spec section 4.3. For tickers with no qualifying row, the
    "no-match" sentinel is constructed with empty strings + ``None``
    provenance fields (per migration 0012_sector_industry.sql TEXT NOT
    NULL DEFAULT '' convention applied to the ABSENT-row case).
    """
    sector: str
    industry: str
    candidate_id: int | None
    evaluation_run_id: int | None


def get_latest_sector_industry_per_ticker(
    conn: sqlite3.Connection,
    tickers: Sequence[str],
) -> dict[str, CandidateSectorIndustryRecord]:
    """Return {ticker: CandidateSectorIndustryRecord} keyed on the
    most-recent ``candidates`` row per ticker with non-empty sector AND
    non-empty industry. Tickers with no qualifying row map to a record
    with empty-string sector/industry + ``None`` provenance fields
    (per migration ``0012_sector_industry.sql`` TEXT NOT NULL DEFAULT
    '' convention applied to the ABSENT-row case).

    Used by the Phase 14 Sub-bundle 1 V2.G3 backfill helper to repair
    empty ``trades.sector`` / ``trades.industry`` values on legacy or
    candidates-rotation cases. Backwards-compat: operator-acknowledged
    DHA/DHC legacy trades (no qualifying candidates row) return the
    no-match sentinel; the open-positions template renders em-dash for
    empty. The provenance fields let the V2.G3 dry-run table cite
    which historical candidates row supplied each backfill
    (spec section 4.3 + Codex R1.M#6 LOCK).

    Empty ``tickers`` input returns ``{}`` without executing SQL
    (CLAUDE.md gotcha #20 runtime-binding-shape + empty-input audit).

    Ordering: most-recent first via
    ``ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY
    evaluation_run_id DESC, id DESC)`` -- 1:1 cardinality per
    cumulative gotcha #18.
    """
    if not tickers:
        return {}
    placeholders = ",".join("?" * len(tickers))
    sql = f"""
        SELECT ticker, sector, industry, id, evaluation_run_id FROM (
            SELECT
                c.ticker, c.sector, c.industry, c.id, c.evaluation_run_id,
                ROW_NUMBER() OVER (
                    PARTITION BY c.ticker
                    ORDER BY c.evaluation_run_id DESC, c.id DESC
                ) AS rn
            FROM candidates c
            WHERE c.ticker IN ({placeholders})
              AND c.sector != ''
              AND c.industry != ''
        ) ranked
        WHERE ranked.rn = 1
    """
    out: dict[str, CandidateSectorIndustryRecord] = {}
    for row in conn.execute(sql, list(tickers)):
        out[row[0]] = CandidateSectorIndustryRecord(
            sector=row[1], industry=row[2],
            candidate_id=row[3], evaluation_run_id=row[4],
        )
    for t in tickers:
        out.setdefault(
            t,
            CandidateSectorIndustryRecord(
                sector="", industry="",
                candidate_id=None, evaluation_run_id=None,
            ),
        )
    return out
