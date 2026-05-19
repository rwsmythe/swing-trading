"""Phase 13 T2.SB1 T-A.1.1b — pattern_exemplars repo CRUD discriminating tests.

Per plan §G.1 T-A.1.1b Step 1: 3 discriminating tests covering
(a) insert_row roundtrips through SQL; (b) get_by_id returns inserted row;
(c) list_* paginates correctly. Caller-tx contract verified (NO ``conn.commit()``
inside repo functions; assertion via in_transaction-on-failure check).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import PatternExemplar
from swing.data.repos import pattern_exemplars as repo


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase13_t2sb1_repo_exemplars.db"
    return ensure_schema(db_path)


def _make_curated_gold_exemplar(**overrides: object) -> PatternExemplar:
    base = {
        "id": None,
        "ticker": "ABC",
        "timeframe": "daily",
        "start_date": "2024-01-01",
        "end_date": "2024-02-01",
        "proposed_pattern_class": "vcp",
        "final_decision": "confirmed",
        "label_source": "curated_gold",
        "structural_evidence_json": "{\"contractions\": []}",
        "geometric_score_json": "{\"score\": 0.9}",
        # Per spec §3.1 invariant #5 (Codex R6 M#1): curated_gold requires
        # labeler_evidence_json non-NULL.
        "labeler_evidence_json": "{\"narrative\": \"sample\"}",
        "created_at": "2024-02-02T00:00:00.000",
        "created_by": "operator",
    }
    base.update(overrides)
    return PatternExemplar(**base)


def test_insert_pattern_exemplar_roundtrips_through_sql(
    conn: sqlite3.Connection,
) -> None:
    """insert_exemplar persists; SELECT post-INSERT returns matching values."""
    exemplar = _make_curated_gold_exemplar()
    with conn:
        exemplar_id = repo.insert_exemplar(conn, exemplar)
    row = conn.execute(
        "SELECT ticker, proposed_pattern_class, label_source, final_decision, "
        "structural_evidence_json, created_by "
        "FROM pattern_exemplars WHERE id = ?",
        (exemplar_id,),
    ).fetchone()
    assert row == (
        "ABC", "vcp", "curated_gold", "confirmed",
        "{\"contractions\": []}", "operator",
    )


def test_get_pattern_exemplar_by_id_returns_inserted_row(
    conn: sqlite3.Connection,
) -> None:
    """get_exemplar_by_id reconstructs the PatternExemplar dataclass.

    Also covers the None-on-missing branch.
    """
    exemplar = _make_curated_gold_exemplar(ticker="XYZ")
    with conn:
        exemplar_id = repo.insert_exemplar(conn, exemplar)

    fetched = repo.get_exemplar_by_id(conn, exemplar_id)
    assert fetched is not None
    assert fetched.ticker == "XYZ"
    assert fetched.proposed_pattern_class == "vcp"
    assert fetched.label_source == "curated_gold"
    assert fetched.final_decision == "confirmed"
    assert fetched.created_by == "operator"

    # None on missing.
    assert repo.get_exemplar_by_id(conn, 999_999) is None


def test_list_pattern_exemplars_paginates_correctly(
    conn: sqlite3.Connection,
) -> None:
    """list_exemplars + limit/offset + pattern_class/label_source filters work."""
    with conn:
        for i, pclass in enumerate(
            ["vcp", "vcp", "flat_base", "cup_with_handle", "vcp"]
        ):
            ex = _make_curated_gold_exemplar(
                ticker=f"T{i}",
                proposed_pattern_class=pclass,
            )
            repo.insert_exemplar(conn, ex)

    # No filter: all 5.
    all_rows = repo.list_exemplars(conn)
    assert len(all_rows) == 5

    # pattern_class filter: 3 VCP.
    vcp_rows = repo.list_exemplars(conn, pattern_class="vcp")
    assert len(vcp_rows) == 3
    assert all(r.proposed_pattern_class == "vcp" for r in vcp_rows)

    # label_source filter (all are curated_gold).
    gold_rows = repo.list_exemplars(conn, label_source="curated_gold")
    assert len(gold_rows) == 5

    # Combined filter.
    vcp_gold = repo.list_exemplars(
        conn, pattern_class="vcp", label_source="curated_gold",
    )
    assert len(vcp_gold) == 3

    # Pagination: limit=2 offset=0 returns first 2 by id ASC.
    first_two = repo.list_exemplars(conn, limit=2, offset=0)
    assert len(first_two) == 2
    assert first_two[0].id < first_two[1].id

    # offset=2 returns next 2.
    next_two = repo.list_exemplars(conn, limit=2, offset=2)
    assert len(next_two) == 2
    assert next_two[0].id > first_two[1].id


def test_repo_does_not_commit_within_function(
    conn: sqlite3.Connection,
) -> None:
    """Caller-tx contract: repo does NOT commit; rollback rolls back insert.

    Mirrors Phase 8 forward-binding lesson #4 / Phase 9 Sub-bundle A lesson
    family (Finviz I1 + 'Repo functions must NOT call conn.commit()').
    """
    exemplar = _make_curated_gold_exemplar(ticker="ROLLED_BACK")
    conn.execute("BEGIN")
    repo.insert_exemplar(conn, exemplar)
    conn.rollback()

    rows = repo.list_exemplars(conn)
    assert all(r.ticker != "ROLLED_BACK" for r in rows)
