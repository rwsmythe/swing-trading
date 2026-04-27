"""Repo for `pipeline_pattern_classifications` cache table (migration 0009)."""
from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Mapping

from swing.data.models import PipelinePatternClassification
from swing.evaluation.patterns.flag_classifier import FlagClassificationResult


def _confidence_for_persistence(result: FlagClassificationResult) -> float | None:
    """Translate dataclass `confidence: float` → DB `confidence REAL` per
    spec §3.2.3: NULL when pattern != 'flag', otherwise the float value."""
    return result.confidence if result.pattern == "flag" else None


def _date_iso(d) -> str | None:
    return d.isoformat() if d is not None else None


def _serialize_components(components: dict) -> str:
    """Strict-JSON serialization: replace NaN with None per RFC 8259.
    NaN may arise from _enrich_components when SMA windows exceed
    flag_start_idx. RFC 8259 has no NaN literal; downstream strict-JSON
    consumers (SQLite json1, external analyzers) reject it."""
    cleaned = {
        k: (None if isinstance(v, float) and math.isnan(v) else v)
        for k, v in components.items()
    }
    return json.dumps(cleaned, sort_keys=True, allow_nan=False)


def insert_classification(
    conn: sqlite3.Connection, *, pipeline_run_id: int, ticker: str,
    result: FlagClassificationResult, computed_at: str,
) -> int:
    """Insert one row. Caller wraps in `with conn:`. Returns row id.

    Persistence rules (spec §3.2.3):
      - pattern='flag': all anchor/confidence columns NOT NULL.
      - pattern='none': anchor/confidence columns NULL; components_json
        carries best-attempted measurements.
      - pattern is None (classifier error): same NULLs; components_json
        carries an "error" key.
    """
    if result.pattern == "flag":
        confidence = result.confidence
        pivot = result.pivot
        pole_high = result.pole_high
        flag_low = result.flag_low
        pole_start = _date_iso(result.pole_start_date)
        pole_end = _date_iso(result.pole_end_date)
        flag_start = _date_iso(result.flag_start_date)
        flag_end = _date_iso(result.flag_end_date)
        pattern = "flag"
    else:
        confidence = None
        pivot = pole_high = flag_low = None
        pole_start = pole_end = flag_start = flag_end = None
        pattern = result.pattern
    cur = conn.execute(
        """
        INSERT INTO pipeline_pattern_classifications
          (pipeline_run_id, ticker, pattern, confidence, components_json,
           pivot, pole_high, flag_low,
           pole_start_date, pole_end_date, flag_start_date, flag_end_date,
           computed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            pipeline_run_id, ticker, pattern, confidence,
            _serialize_components(result.components),
            pivot, pole_high, flag_low,
            pole_start, pole_end, flag_start, flag_end,
            computed_at,
        ),
    )
    return int(cur.lastrowid)


def _row_to_classification(row: tuple) -> PipelinePatternClassification:
    return PipelinePatternClassification(
        id=row[0], pipeline_run_id=row[1], ticker=row[2],
        pattern=row[3], confidence=row[4], components_json=row[5],
        pivot=row[6], pole_high=row[7], flag_low=row[8],
        pole_start_date=row[9], pole_end_date=row[10],
        flag_start_date=row[11], flag_end_date=row[12],
        computed_at=row[13],
    )


def get_classification(
    conn: sqlite3.Connection, *, pipeline_run_id: int, ticker: str,
) -> PipelinePatternClassification | None:
    row = conn.execute(
        """
        SELECT id, pipeline_run_id, ticker, pattern, confidence,
               components_json, pivot, pole_high, flag_low,
               pole_start_date, pole_end_date, flag_start_date, flag_end_date,
               computed_at
        FROM pipeline_pattern_classifications
        WHERE pipeline_run_id = ? AND ticker = ?
        """,
        (pipeline_run_id, ticker),
    ).fetchone()
    return _row_to_classification(row) if row else None


def list_classifications_for_run(
    conn: sqlite3.Connection, *, pipeline_run_id: int,
) -> Mapping[str, PipelinePatternClassification]:
    rows = conn.execute(
        """
        SELECT id, pipeline_run_id, ticker, pattern, confidence,
               components_json, pivot, pole_high, flag_low,
               pole_start_date, pole_end_date, flag_start_date, flag_end_date,
               computed_at
        FROM pipeline_pattern_classifications
        WHERE pipeline_run_id = ?
        """,
        (pipeline_run_id,),
    ).fetchall()
    return {row[2]: _row_to_classification(row) for row in rows}
