"""`provenance_corrections` repo (migration 0036) -- Demand C.

APPEND-ONLY, and ONE row per trade enforced by
``ux_provenance_corrections_trade`` rather than by prose. There is no UPDATE
and no DELETE here on purpose: V1 records a trade's provenance once, so a
re-correction path would be an authority decision this surface has not been
given (plan limitation 4).

Pure CRUD inside the CALLER's transaction -- these functions DO NOT commit.
The service (``swing/trades/cohort_provenance_correction.py``) owns
``BEGIN IMMEDIATE`` / COMMIT / ROLLBACK, and a repo that opened its own
``with conn:`` would commit that single transaction out from under it
(CLAUDE.md, SQLite section).
"""
from __future__ import annotations

import sqlite3

from swing.data.models import ProvenanceCorrection

# The column order is shared by the INSERT and the SELECT so the two cannot
# drift apart -- the read-path mapper widening in the SAME place as the write
# path (#11).
_COLUMNS: tuple[str, ...] = (
    "trade_id",
    "entry_fill_id",
    "entry_fill_id_at_correction",
    "entry_fill_snapshot_json",
    "cited_candidate_id",
    "cited_daily_recommendation_id",
    "cited_evaluation_run_id",
    "cited_hypothesis_id",
    "cited_hypothesis_status_history_id",
    "cited_hypothesis_status_at_record",
    "cited_pipeline_finished_ts_raw",
    "cited_run_ts_utc",
    "cited_status_window_upper_utc",
    "cited_pipeline_run_id",
    "cited_pipeline_run_snapshot_json",
    "cited_hypothesis_status_recorded_at",
    "cited_hypothesis_status_effective_from",
    "cited_hypothesis_status_effective_to",
    "cited_hypothesis_name_at_correction",
    "cited_candidate_action_session_date",
    "cited_recommendation_action_session_date",
    "entry_fill_session_date",
    "cited_run_ts_raw",
    "cited_recommendation_snapshot_json",
    "derivation_rule_version",
    "pre_value_json",
    "applied_value_json",
    "corrected_fields_json",
    "applied_at",
    "applied_by",
    "correction_reason",
    "risk_policy_id_at_correction",
)

_SELECT = "provenance_correction_id, " + ", ".join(_COLUMNS)


def _row_to_model(row: tuple) -> ProvenanceCorrection:
    return ProvenanceCorrection(
        provenance_correction_id=row[0],
        **{name: row[i + 1] for i, name in enumerate(_COLUMNS)},
    )


def insert_provenance_correction(
    conn: sqlite3.Connection, correction: ProvenanceCorrection,
) -> int:
    """INSERT one audit row inside the caller's transaction; return its id.

    The dataclass has already validated every mirror of the 0036 CHECKs at
    construction, so a row reaching here is coherent; the CHECKs remain as the
    barrier against a RAW INSERT that never built one.
    """
    placeholders = ", ".join("?" * len(_COLUMNS))
    cur = conn.execute(
        f"INSERT INTO provenance_corrections ({', '.join(_COLUMNS)}) "
        f"VALUES ({placeholders})",
        tuple(getattr(correction, name) for name in _COLUMNS),
    )
    return int(cur.lastrowid)


def get_correction_for_trade(
    conn: sqlite3.Connection, trade_id: int,
) -> ProvenanceCorrection | None:
    """The trade's correction, or None.

    A bare equality on `trade_id`, which the UNIQUE index makes single-valued
    -- so this reader is the SELECT-first idempotency lookup the refusal
    ladder leads with, and it cannot be fooled by row order.
    """
    row = conn.execute(
        f"SELECT {_SELECT} FROM provenance_corrections WHERE trade_id = ?",
        (trade_id,),
    ).fetchone()
    return _row_to_model(row) if row else None


def list_provenance_corrections(
    conn: sqlite3.Connection, *, trade_id: int | None = None,
) -> list[ProvenanceCorrection]:
    """Every correction, oldest id first; optionally scoped to one trade.

    Ordered by the AUTOINCREMENT primary key rather than by `applied_at`:
    `applied_at` is an unconstrained TEXT column, so ordering on it is the
    lexical-timestamp class this arc refuses everywhere else.
    """
    if trade_id is None:
        rows = conn.execute(
            f"SELECT {_SELECT} FROM provenance_corrections "
            "ORDER BY provenance_correction_id ASC",
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT {_SELECT} FROM provenance_corrections "
            "WHERE trade_id = ? ORDER BY provenance_correction_id ASC",
            (trade_id,),
        ).fetchall()
    return [_row_to_model(r) for r in rows]
