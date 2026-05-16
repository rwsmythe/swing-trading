"""Phase 12 Sub-bundle C Sub-sub-bundle C.A Task T-A.3 — reconciliation_corrections repo CRUD.

Per plan §B.3 acceptance criteria:
- Module exposes 7 pure-CRUD functions (caller-tx; no ``conn.commit()`` inside repo).
- ``insert_correction(conn, correction) -> int`` returns new ``correction_id``.
- ``get_correction(conn, correction_id) -> ReconciliationCorrection | None``.
- ``list_corrections_by_discrepancy(conn, discrepancy_id)`` ordered by
  ``applied_at ASC, correction_id ASC``.
- ``list_corrections_by_run(conn, run_id)``.
- ``list_corrections_by_affected_row(conn, affected_table, affected_row_id)``.
- ``update_superseded_by(conn, correction_id, superseded_by_correction_id)``.
- ``count_corrections_by_action(conn) -> dict[str, int]``.
- NO ``INSERT OR REPLACE``; UPDATE-only for supersede-pointer-set.
- All SQL parameterized.

Discriminating tests:
- Insert + read-back.
- FK CASCADE from ``discrepancy_id`` DELETE propagates.
- FK SET NULL from ``risk_policy_id_at_correction`` /
  ``schwab_api_call_id`` DELETE (NULLABLE FK columns).
- Listing order ascending ``applied_at`` + ``correction_id ASC`` tiebreaker.
- Supersede-pointer two-step semantics.
- Anchor-self-reference pattern (per OQ-6 disposition).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.datetime_helpers import now_ms
from swing.data.db import ensure_schema
from swing.data.models import ReconciliationCorrection
from swing.data.repos import reconciliation_corrections as repo

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def conn_with_v19_schema_and_run(tmp_path: Path) -> sqlite3.Connection:
    """Connection at schema v19 with a planted reconciliation_runs row and a
    planted reconciliation_discrepancies row.

    Returns a connection where:
      - reconciliation_runs has a row at run_id = 1
      - reconciliation_discrepancies has a row at discrepancy_id = 1
        attached to that run.

    Callers use these row IDs as FK targets for ReconciliationCorrection
    instances they construct.
    """
    conn = ensure_schema(tmp_path / "phase12_ca.db")
    # Plant a reconciliation_runs row (FK target for corrections).
    conn.execute(
        "INSERT INTO reconciliation_runs ("
        "source, started_ts, state"
        ") VALUES ('tos_csv', ?, 'completed')",
        (now_ms(),),
    )
    # Plant a reconciliation_discrepancies row.
    conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "run_id, discrepancy_type, field_name, material_to_review, created_at"
        ") VALUES (1, 'close_price_mismatch', 'price', 1, ?)",
        (now_ms(),),
    )
    conn.commit()
    return conn


def _build_correction(
    *,
    discrepancy_id: int = 1,
    reconciliation_run_id: int = 1,
    correction_action: str = "auto_applied",
    correction_choice: str | None = None,
    affected_table: str = "fills",
    affected_row_id: int = 100,
    field_name: str = "price",
    pre_correction_value_json: str = '"5.00"',
    source_canonical_value_json: str | None = '"5.10"',
    applied_value_json: str = '"5.10"',
    operator_truth_value_json: str | None = None,
    applied_at: str | None = None,
    applied_by: str = "auto",
    correction_set_id: int | None = None,
    superseded_by_correction_id: int | None = None,
    risk_policy_id_at_correction: int | None = None,
    schwab_api_call_id: int | None = None,
    correction_reason: str | None = None,
    notes: str | None = None,
) -> ReconciliationCorrection:
    return ReconciliationCorrection(
        correction_id=0,  # pre-INSERT placeholder; ignored by insert_correction
        discrepancy_id=discrepancy_id,
        correction_action=correction_action,
        correction_choice=correction_choice,
        affected_table=affected_table,
        affected_row_id=affected_row_id,
        field_name=field_name,
        pre_correction_value_json=pre_correction_value_json,
        source_canonical_value_json=source_canonical_value_json,
        applied_value_json=applied_value_json,
        operator_truth_value_json=operator_truth_value_json,
        applied_at=applied_at or now_ms(),
        applied_by=applied_by,
        correction_set_id=correction_set_id,
        superseded_by_correction_id=superseded_by_correction_id,
        risk_policy_id_at_correction=risk_policy_id_at_correction,
        schwab_api_call_id=schwab_api_call_id,
        reconciliation_run_id=reconciliation_run_id,
        correction_reason=correction_reason,
        notes=notes,
    )


# ===========================================================================
# §1 — insert_correction + get_correction (round-trip)
# ===========================================================================


def test_insert_and_get_correction_round_trip(conn_with_v19_schema_and_run):
    conn = conn_with_v19_schema_and_run
    rc = _build_correction(
        applied_at="2026-05-15T12:00:00.000",
        correction_reason="tier-1 unambiguous",
        notes="planted by test",
    )
    cid = repo.insert_correction(conn, rc)
    assert cid > 0

    fetched = repo.get_correction(conn, cid)
    assert fetched is not None
    assert fetched.correction_id == cid
    assert fetched.discrepancy_id == 1
    assert fetched.correction_action == "auto_applied"
    assert fetched.correction_choice is None
    assert fetched.affected_table == "fills"
    assert fetched.affected_row_id == 100
    assert fetched.field_name == "price"
    assert fetched.pre_correction_value_json == '"5.00"'
    assert fetched.source_canonical_value_json == '"5.10"'
    assert fetched.applied_value_json == '"5.10"'
    assert fetched.operator_truth_value_json is None
    assert fetched.applied_at == "2026-05-15T12:00:00.000"
    assert fetched.applied_by == "auto"
    assert fetched.correction_set_id is None
    assert fetched.superseded_by_correction_id is None
    assert fetched.risk_policy_id_at_correction is None
    assert fetched.schwab_api_call_id is None
    assert fetched.reconciliation_run_id == 1
    assert fetched.correction_reason == "tier-1 unambiguous"
    assert fetched.notes == "planted by test"


def test_get_correction_returns_none_when_missing(conn_with_v19_schema_and_run):
    conn = conn_with_v19_schema_and_run
    assert repo.get_correction(conn, 9999) is None


def test_insert_correction_does_not_commit(conn_with_v19_schema_and_run, tmp_path):
    """Caller-tx discipline: repo must NOT call ``conn.commit()`` so an
    un-committed INSERT is invisible to a separate connection."""
    conn = conn_with_v19_schema_and_run
    rc = _build_correction()
    cid = repo.insert_correction(conn, rc)
    assert cid > 0
    # Open a fresh connection BEFORE commit — should NOT see the new row.
    fresh = sqlite3.connect(str(tmp_path / "phase12_ca.db"))
    row = fresh.execute(
        "SELECT correction_id FROM reconciliation_corrections WHERE correction_id = ?",
        (cid,),
    ).fetchone()
    fresh.close()
    assert row is None, "repo.insert_correction must NOT commit"
    conn.commit()
    # After commit it's persisted.
    fresh2 = sqlite3.connect(str(tmp_path / "phase12_ca.db"))
    row2 = fresh2.execute(
        "SELECT correction_id FROM reconciliation_corrections WHERE correction_id = ?",
        (cid,),
    ).fetchone()
    fresh2.close()
    assert row2 is not None


# ===========================================================================
# §2 — list_corrections_by_discrepancy (order discipline)
# ===========================================================================


def test_list_corrections_by_discrepancy_orders_by_applied_at_then_id(
    conn_with_v19_schema_and_run,
):
    conn = conn_with_v19_schema_and_run
    # Insert 3 corrections; two share applied_at to exercise PK tiebreak.
    c_late = _build_correction(applied_at="2026-05-15T15:00:00.000")
    c_early_a = _build_correction(applied_at="2026-05-15T09:00:00.000")
    c_early_b = _build_correction(applied_at="2026-05-15T09:00:00.000")

    id_late = repo.insert_correction(conn, c_late)
    id_early_a = repo.insert_correction(conn, c_early_a)
    id_early_b = repo.insert_correction(conn, c_early_b)
    conn.commit()

    rows = repo.list_corrections_by_discrepancy(conn, 1)
    assert [r.correction_id for r in rows] == [id_early_a, id_early_b, id_late]


def test_list_corrections_by_discrepancy_returns_empty_when_no_match(
    conn_with_v19_schema_and_run,
):
    conn = conn_with_v19_schema_and_run
    rows = repo.list_corrections_by_discrepancy(conn, 9999)
    assert rows == []


# ===========================================================================
# §3 — list_corrections_by_run
# ===========================================================================


def test_list_corrections_by_run_filters_by_run_id(
    conn_with_v19_schema_and_run,
):
    conn = conn_with_v19_schema_and_run
    # Insert a second run + discrepancy.
    conn.execute(
        "INSERT INTO reconciliation_runs (source, started_ts, state) "
        "VALUES ('tos_csv', ?, 'completed')",
        (now_ms(),),
    )
    conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "run_id, discrepancy_type, field_name, material_to_review, created_at"
        ") VALUES (2, 'stop_mismatch', 'stop', 1, ?)",
        (now_ms(),),
    )
    conn.commit()

    id1 = repo.insert_correction(
        conn,
        _build_correction(reconciliation_run_id=1, discrepancy_id=1),
    )
    id2 = repo.insert_correction(
        conn,
        _build_correction(reconciliation_run_id=2, discrepancy_id=2),
    )
    conn.commit()

    rows_for_1 = repo.list_corrections_by_run(conn, 1)
    rows_for_2 = repo.list_corrections_by_run(conn, 2)
    assert [r.correction_id for r in rows_for_1] == [id1]
    assert [r.correction_id for r in rows_for_2] == [id2]


# ===========================================================================
# §4 — list_corrections_by_affected_row
# ===========================================================================


def test_list_corrections_by_affected_row_filters_by_table_and_id(
    conn_with_v19_schema_and_run,
):
    conn = conn_with_v19_schema_and_run
    id_fill_100 = repo.insert_correction(
        conn,
        _build_correction(affected_table="fills", affected_row_id=100,
                          applied_at="2026-05-15T09:00:00.000"),
    )
    id_fill_100_b = repo.insert_correction(
        conn,
        _build_correction(affected_table="fills", affected_row_id=100,
                          applied_at="2026-05-15T10:00:00.000"),
    )
    repo.insert_correction(
        conn,
        _build_correction(affected_table="fills", affected_row_id=101),
    )
    repo.insert_correction(
        conn,
        _build_correction(affected_table="trades", affected_row_id=100),
    )
    conn.commit()

    rows = repo.list_corrections_by_affected_row(conn, "fills", 100)
    assert [r.correction_id for r in rows] == [id_fill_100, id_fill_100_b]


# ===========================================================================
# §5 — update_superseded_by (two-step + anchor self-reference)
# ===========================================================================


def test_update_superseded_by_two_step_semantics(
    conn_with_v19_schema_and_run,
):
    conn = conn_with_v19_schema_and_run
    id1 = repo.insert_correction(conn, _build_correction())
    id2 = repo.insert_correction(conn, _build_correction())
    conn.commit()

    repo.update_superseded_by(conn, id1, id2)
    conn.commit()

    row1 = repo.get_correction(conn, id1)
    row2 = repo.get_correction(conn, id2)
    assert row1.superseded_by_correction_id == id2
    assert row2.superseded_by_correction_id is None


def test_update_superseded_by_anchor_self_reference(
    conn_with_v19_schema_and_run,
):
    """Per OQ-6 disposition: an anchor row's correction_set_id may point at
    itself. Two-step: INSERT (returns N), then UPDATE correction_set_id = N.
    """
    conn = conn_with_v19_schema_and_run
    anchor = _build_correction(correction_set_id=None)
    anchor_id = repo.insert_correction(conn, anchor)
    # Two-step: now stamp correction_set_id = anchor_id on the anchor row itself.
    conn.execute(
        "UPDATE reconciliation_corrections "
        "SET correction_set_id = ? WHERE correction_id = ?",
        (anchor_id, anchor_id),
    )
    conn.commit()

    fetched = repo.get_correction(conn, anchor_id)
    assert fetched.correction_id == anchor_id
    assert fetched.correction_set_id == anchor_id


# ===========================================================================
# §6 — count_corrections_by_action
# ===========================================================================


def test_count_corrections_by_action_empty_returns_zero_dict(
    conn_with_v19_schema_and_run,
):
    conn = conn_with_v19_schema_and_run
    counts = repo.count_corrections_by_action(conn)
    assert counts == {
        "auto_applied": 0,
        "operator_resolved_ambiguity": 0,
        "operator_overridden": 0,
    }


def test_count_corrections_by_action_returns_per_action_counts(
    conn_with_v19_schema_and_run,
):
    conn = conn_with_v19_schema_and_run
    # 3 auto_applied
    for _ in range(3):
        repo.insert_correction(conn, _build_correction(correction_action="auto_applied"))
    # 2 operator_resolved_ambiguity (must supply correction_choice + applied_by='operator')
    for _ in range(2):
        repo.insert_correction(
            conn,
            _build_correction(
                correction_action="operator_resolved_ambiguity",
                correction_choice="trust_schwab",
                applied_by="operator",
            ),
        )
    # 1 operator_overridden
    repo.insert_correction(
        conn,
        _build_correction(
            correction_action="operator_overridden",
            applied_by="operator",
            operator_truth_value_json='"5.05"',
            correction_reason="manual override",
        ),
    )
    conn.commit()

    counts = repo.count_corrections_by_action(conn)
    assert counts == {
        "auto_applied": 3,
        "operator_resolved_ambiguity": 2,
        "operator_overridden": 1,
    }


# ===========================================================================
# §7 — FK CASCADE / SET NULL coverage
# ===========================================================================


def test_fk_cascade_from_discrepancy_delete_propagates_to_corrections(
    conn_with_v19_schema_and_run,
):
    conn = conn_with_v19_schema_and_run
    # SQLite requires PRAGMA foreign_keys=ON per-connection; ensure_schema
    # sets it but be defensive.
    conn.execute("PRAGMA foreign_keys = ON")
    cid = repo.insert_correction(conn, _build_correction(discrepancy_id=1))
    conn.commit()
    assert repo.get_correction(conn, cid) is not None

    conn.execute("DELETE FROM reconciliation_discrepancies WHERE discrepancy_id = 1")
    conn.commit()

    assert repo.get_correction(conn, cid) is None


def test_fk_cascade_from_run_delete_propagates_to_corrections(
    conn_with_v19_schema_and_run,
):
    """``reconciliation_run_id`` FK is ON DELETE CASCADE per migration 0019."""
    conn = conn_with_v19_schema_and_run
    conn.execute("PRAGMA foreign_keys = ON")
    cid = repo.insert_correction(conn, _build_correction(reconciliation_run_id=1))
    conn.commit()
    assert repo.get_correction(conn, cid) is not None

    # Run delete cascades discrepancy delete first, which CASCADEs to corrections
    # — both paths converge on the same destruction. The key behavior to pin
    # is the row is gone after run delete.
    conn.execute("DELETE FROM reconciliation_runs WHERE run_id = 1")
    conn.commit()
    assert repo.get_correction(conn, cid) is None


def test_fk_set_null_from_risk_policy_delete(conn_with_v19_schema_and_run):
    """``risk_policy_id_at_correction`` FK is ON DELETE SET NULL."""
    conn = conn_with_v19_schema_and_run
    conn.execute("PRAGMA foreign_keys = ON")
    # Use the migration-0017-seeded risk_policy row (policy_id=1) as the FK
    # target. To exercise ON DELETE SET NULL safely without disturbing the
    # seed row + chronology fields, we instead INSERT a fresh row by cloning
    # the seed row's column values (no semantic meaning; just a valid FK
    # target we can DELETE without tripping cross-row invariants).
    seed_row = conn.execute(
        "SELECT * FROM risk_policy WHERE policy_id = 1"
    ).fetchone()
    col_names = [
        d[0] for d in conn.execute("SELECT * FROM risk_policy LIMIT 0").description
    ]
    # Build INSERT excluding policy_id (AUTOINCREMENT) + is_active (must not
    # collide with seed row's active flag — set 0 here so seed stays active).
    placeholders = []
    values = []
    cols_to_insert = []
    for name, val in zip(col_names, seed_row, strict=True):
        if name == "policy_id":
            continue
        cols_to_insert.append(name)
        if name == "is_active":
            values.append(0)
        else:
            values.append(val)
        placeholders.append("?")
    cur = conn.execute(
        f"INSERT INTO risk_policy ({', '.join(cols_to_insert)}) "
        f"VALUES ({', '.join(placeholders)})",
        tuple(values),
    )
    policy_id = cur.lastrowid
    cid = repo.insert_correction(
        conn,
        _build_correction(risk_policy_id_at_correction=policy_id),
    )
    conn.commit()

    fetched = repo.get_correction(conn, cid)
    assert fetched.risk_policy_id_at_correction == policy_id

    conn.execute("DELETE FROM risk_policy WHERE policy_id = ?", (policy_id,))
    conn.commit()

    fetched_after = repo.get_correction(conn, cid)
    assert fetched_after is not None
    assert fetched_after.risk_policy_id_at_correction is None


def test_fk_set_null_from_schwab_api_call_delete(conn_with_v19_schema_and_run):
    """``schwab_api_call_id`` FK is ON DELETE SET NULL."""
    conn = conn_with_v19_schema_and_run
    conn.execute("PRAGMA foreign_keys = ON")
    # Plant a schwab_api_calls row.
    cur = conn.execute(
        "INSERT INTO schwab_api_calls ("
        "ts, endpoint, status, surface, environment"
        ") VALUES (?, 'marketdata.quotes', 'success', 'cli', 'sandbox')",
        (now_ms(),),
    )
    call_id = cur.lastrowid
    cid = repo.insert_correction(
        conn,
        _build_correction(schwab_api_call_id=call_id),
    )
    conn.commit()

    fetched = repo.get_correction(conn, cid)
    assert fetched.schwab_api_call_id == call_id

    conn.execute("DELETE FROM schwab_api_calls WHERE call_id = ?", (call_id,))
    conn.commit()

    fetched_after = repo.get_correction(conn, cid)
    assert fetched_after is not None
    assert fetched_after.schwab_api_call_id is None


def test_fk_set_null_from_superseded_by_correction_delete(
    conn_with_v19_schema_and_run,
):
    """``superseded_by_correction_id`` self-FK is ON DELETE SET NULL."""
    conn = conn_with_v19_schema_and_run
    conn.execute("PRAGMA foreign_keys = ON")
    id1 = repo.insert_correction(conn, _build_correction())
    id2 = repo.insert_correction(conn, _build_correction())
    repo.update_superseded_by(conn, id1, id2)
    conn.commit()
    assert repo.get_correction(conn, id1).superseded_by_correction_id == id2

    # Delete the superseding row; the superseded row's pointer is SET NULL,
    # not CASCADE-deleted (CASCADE on the parent FK would wipe id1).
    # But correction_id FK on superseded_by_correction_id has ON DELETE SET NULL.
    # The discrepancy FK on id1 still anchors it, so the row survives.
    conn.execute(
        "DELETE FROM reconciliation_corrections WHERE correction_id = ?",
        (id2,),
    )
    conn.commit()
    row1 = repo.get_correction(conn, id1)
    assert row1 is not None
    assert row1.superseded_by_correction_id is None
