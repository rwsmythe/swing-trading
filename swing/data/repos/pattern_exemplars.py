"""``pattern_exemplars`` repo — Phase 13 T2.SB1 task T-A.1.1b.

Minimum CRUD (insert / get_by_id / list) per plan §G.1 T-A.1.1b acceptance.
Caller-tx contract per Phase 8 forward-binding lesson #4 (Finviz I1 +
Phase 9 Sub-bundle A lesson family): repo functions NEVER call
``conn.commit()`` — the caller wraps with the outer ``with conn:`` (or
explicit ``BEGIN IMMEDIATE``).

NO ``INSERT OR REPLACE`` per CLAUDE.md gotcha + plan §A.15 LOCK
(``pattern_exemplars`` is an audit-trail-with-uniqueness table; REPLACE
would cascade-wipe parent_exemplar_id FK references + history-rewrite PKs).

Schema CHECK + Python constant + dataclass ``__post_init__`` validator
discipline (Phase 12 C.A T-A.2 LOCK) lands at T-A.1.1. This module
consumes the dataclass shape with all 5 cross-column invariants validated
on construction.
"""
from __future__ import annotations

import sqlite3

from swing.data.models import PatternExemplar

# Column order used by all SELECT statements + the PatternExemplar
# constructor — single source of truth so list / get-by-id stay aligned
# with the dataclass field order (V1: positional construction).
_EXEMPLAR_COLUMNS: tuple[str, ...] = (
    "id",
    "ticker",
    "timeframe",
    "start_date",
    "end_date",
    "proposed_pattern_class",
    "final_decision",
    "label_source",
    "structural_evidence_json",
    "created_at",
    "created_by",
    "final_pattern_class",
    "ai_labeler_version",
    "gold_validated_at",
    "codex_reviewed",
    "codex_agreement",
    "geometric_score_json",
    "labeler_evidence_json",
    "quality_grade",
    "notes",
    "parent_exemplar_id",
)

_SELECT_COLUMNS_SQL: str = ", ".join(_EXEMPLAR_COLUMNS)


def _row_to_exemplar(row: tuple) -> PatternExemplar:
    """Map a SELECT row (in ``_EXEMPLAR_COLUMNS`` order) to a PatternExemplar."""
    return PatternExemplar(
        id=row[0],
        ticker=row[1],
        timeframe=row[2],
        start_date=row[3],
        end_date=row[4],
        proposed_pattern_class=row[5],
        final_decision=row[6],
        label_source=row[7],
        structural_evidence_json=row[8],
        created_at=row[9],
        created_by=row[10],
        final_pattern_class=row[11],
        ai_labeler_version=row[12],
        gold_validated_at=row[13],
        codex_reviewed=row[14],
        codex_agreement=row[15],
        geometric_score_json=row[16],
        labeler_evidence_json=row[17],
        quality_grade=row[18],
        notes=row[19],
        parent_exemplar_id=row[20],
    )


def insert_exemplar(conn: sqlite3.Connection, exemplar: PatternExemplar) -> int:
    """Insert one ``pattern_exemplars`` row; return new id.

    Caller-tx contract: NO ``conn.commit()``; caller owns the transaction.
    All schema CHECKs + cross-column invariants validated by ``PatternExemplar``
    dataclass on construction (plan §A.14 paired-atomic-landing LOCK).
    """
    cur = conn.execute(
        f"""
        INSERT INTO pattern_exemplars
            ({_SELECT_COLUMNS_SQL.replace('id, ', '', 1)})
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            exemplar.ticker,
            exemplar.timeframe,
            exemplar.start_date,
            exemplar.end_date,
            exemplar.proposed_pattern_class,
            exemplar.final_decision,
            exemplar.label_source,
            exemplar.structural_evidence_json,
            exemplar.created_at,
            exemplar.created_by,
            exemplar.final_pattern_class,
            exemplar.ai_labeler_version,
            exemplar.gold_validated_at,
            exemplar.codex_reviewed,
            exemplar.codex_agreement,
            exemplar.geometric_score_json,
            exemplar.labeler_evidence_json,
            exemplar.quality_grade,
            exemplar.notes,
            exemplar.parent_exemplar_id,
        ),
    )
    return int(cur.lastrowid)


def get_exemplar_by_id(
    conn: sqlite3.Connection, exemplar_id: int,
) -> PatternExemplar | None:
    """Return the exemplar with matching id, or None."""
    row = conn.execute(
        f"SELECT {_SELECT_COLUMNS_SQL} FROM pattern_exemplars WHERE id = ?",
        (exemplar_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_exemplar(row)


def list_exemplars(
    conn: sqlite3.Connection,
    *,
    pattern_class: str | None = None,
    label_source: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[PatternExemplar]:
    """List exemplars filtered by optional pattern_class / label_source.

    Ordered by (id ASC) for deterministic pagination.

    Per plan §G.1 T-A.1.1b acceptance #1c: pagination works correctly
    (limit + offset cooperate; default returns all rows when limit is None).
    """
    where_clauses: list[str] = []
    params: list[object] = []
    if pattern_class is not None:
        where_clauses.append("proposed_pattern_class = ?")
        params.append(pattern_class)
    if label_source is not None:
        where_clauses.append("label_source = ?")
        params.append(label_source)

    where_sql = ""
    if where_clauses:
        where_sql = " WHERE " + " AND ".join(where_clauses)

    limit_sql = ""
    if limit is not None:
        limit_sql = " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    rows = conn.execute(
        f"SELECT {_SELECT_COLUMNS_SQL} FROM pattern_exemplars"
        f"{where_sql} ORDER BY id ASC{limit_sql}",
        tuple(params),
    ).fetchall()
    return [_row_to_exemplar(r) for r in rows]
