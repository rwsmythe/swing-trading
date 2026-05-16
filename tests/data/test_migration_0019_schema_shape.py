"""Phase 12 Sub-bundle C.A T-A.1 — migration 0019 schema shape + CHECK constraints.

Per plan §B.1 acceptance criteria 3-12 + 15 (auto-correct reconciliation
plan, 2026-05-15):

  - 20 columns on reconciliation_corrections (#3) + 4 indexes (#4).
  - resolution CHECK enum widened 5 → 9 on reconciliation_discrepancies (#5).
  - ambiguity_kind column + 7-value CHECK enum on reconciliation_discrepancies
    (#6).
  - 4 existing indexes + 1 new partial index on reconciliation_discrepancies
    (#8, #12).
  - review_log gets superseded_by_correction_id (nullable FK; #9).
  - schwab_api_calls gets linked_correction_id (nullable FK; #11).
  - trade_events event_type CHECK widened 6 → 7 (#10).
  - Cross-column CHECK on (ambiguity_kind, resolution) bidirectional (#15).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema

# ============================================================================
# Fixture: fresh v19 DB with seeded reconciliation_runs row for FK references.
# ============================================================================


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase12_bundle_c_a_shape.db"
    conn = ensure_schema(db_path)
    conn.execute(
        "INSERT INTO reconciliation_runs ("
        "source, started_ts, state"
        ") VALUES ('tos_csv', '2026-05-15T10:00:00.000', 'completed')"
    )
    return conn


def _plant_run(conn: sqlite3.Connection, *, run_id: int) -> None:
    """Ensure a reconciliation_runs row exists at the given id (for FK refs)."""
    existing = conn.execute(
        "SELECT run_id FROM reconciliation_runs WHERE run_id = ?", (run_id,)
    ).fetchone()
    if existing:
        return
    conn.execute(
        "INSERT INTO reconciliation_runs ("
        "run_id, source, started_ts, state"
        ") VALUES (?, 'tos_csv', '2026-05-15T10:00:00.000', 'completed')",
        (run_id,),
    )


# ============================================================================
# §1 — reconciliation_corrections table (20 columns + 4 indexes).
# ============================================================================


_CORRECTIONS_EXPECTED_COLS: frozenset[str] = frozenset({
    "correction_id",
    "discrepancy_id",
    "correction_action",
    "correction_choice",
    "affected_table",
    "affected_row_id",
    "field_name",
    "pre_correction_value_json",
    "source_canonical_value_json",
    "applied_value_json",
    "operator_truth_value_json",
    "applied_at",
    "applied_by",
    "correction_set_id",
    "superseded_by_correction_id",
    "risk_policy_id_at_correction",
    "schwab_api_call_id",
    "reconciliation_run_id",
    "correction_reason",
    "notes",
})


def test_reconciliation_corrections_has_20_columns(
    conn: sqlite3.Connection,
) -> None:
    """Plan §B.1 acceptance #3 LOCK — spec §3.1 header says 19 but the
    enumerated rows are 20; banked as §I.16 V2.1 §VII.F amendment candidate.
    """
    cur = conn.execute("PRAGMA table_info(reconciliation_corrections)")
    cols = {r[1] for r in cur.fetchall()}
    assert cols == _CORRECTIONS_EXPECTED_COLS, (
        f"column drift; missing {_CORRECTIONS_EXPECTED_COLS - cols}; "
        f"extra {cols - _CORRECTIONS_EXPECTED_COLS}"
    )
    assert len(cols) == 20


def test_reconciliation_corrections_has_4_indexes(
    conn: sqlite3.Connection,
) -> None:
    """Plan §B.1 acceptance #4 — exactly 4 explicit indexes."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND tbl_name='reconciliation_corrections' "
        "AND name NOT LIKE 'sqlite_autoindex_%'"
    ).fetchall()
    names = {r[0] for r in rows}
    expected = {
        "ix_reconciliation_corrections_discrepancy",
        "ix_reconciliation_corrections_affected_row",
        "ix_reconciliation_corrections_run",
        "ix_reconciliation_corrections_action",
    }
    assert names == expected, (
        f"index drift; missing {expected - names}; extra {names - expected}"
    )


def test_reconciliation_corrections_correction_action_check_enum(
    conn: sqlite3.Connection,
) -> None:
    """correction_action CHECK enforces 3 values:
    'auto_applied', 'operator_resolved_ambiguity', 'operator_overridden'.
    """
    # Plant a discrepancy that the corrections row can reference.
    conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "run_id, discrepancy_type, field_name, material_to_review, "
        "resolution, created_at"
        ") VALUES (1, 'entry_price_mismatch', 'price', 0, 'unresolved', "
        "'2026-05-15')"
    )
    disc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    for valid in (
        "auto_applied",
        "operator_resolved_ambiguity",
        "operator_overridden",
    ):
        conn.execute(
            "INSERT INTO reconciliation_corrections ("
            "discrepancy_id, correction_action, affected_table, "
            "affected_row_id, field_name, pre_correction_value_json, "
            "applied_value_json, applied_at, applied_by, "
            "reconciliation_run_id"
            ") VALUES (?, ?, 'fills', 1, 'price', '5.00', '5.30', "
            "'2026-05-15T10:00:00.000', 'auto', 1)",
            (disc_id, valid),
        )

    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO reconciliation_corrections ("
            "discrepancy_id, correction_action, affected_table, "
            "affected_row_id, field_name, pre_correction_value_json, "
            "applied_value_json, applied_at, applied_by, "
            "reconciliation_run_id"
            ") VALUES (?, 'invalid_action', 'fills', 1, 'price', "
            "'5.00', '5.30', '2026-05-15T10:00:00.000', 'auto', 1)",
            (disc_id,),
        )


def test_reconciliation_corrections_affected_table_check_enum(
    conn: sqlite3.Connection,
) -> None:
    """affected_table CHECK enforces 4 values."""
    conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "run_id, discrepancy_type, field_name, material_to_review, "
        "resolution, created_at"
        ") VALUES (1, 'entry_price_mismatch', 'price', 0, 'unresolved', "
        "'2026-05-15')"
    )
    disc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    for valid in ("fills", "trades", "cash_movements", "account_equity_snapshots"):
        conn.execute(
            "INSERT INTO reconciliation_corrections ("
            "discrepancy_id, correction_action, affected_table, "
            "affected_row_id, field_name, pre_correction_value_json, "
            "applied_value_json, applied_at, applied_by, "
            "reconciliation_run_id"
            ") VALUES (?, 'auto_applied', ?, 1, 'price', '5.00', '5.30', "
            "'2026-05-15T10:00:00.000', 'auto', 1)",
            (disc_id, valid),
        )

    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO reconciliation_corrections ("
            "discrepancy_id, correction_action, affected_table, "
            "affected_row_id, field_name, pre_correction_value_json, "
            "applied_value_json, applied_at, applied_by, "
            "reconciliation_run_id"
            ") VALUES (?, 'auto_applied', 'review_log', 1, 'price', "
            "'5.00', '5.30', '2026-05-15T10:00:00.000', 'auto', 1)",
            (disc_id,),
        )


def test_reconciliation_corrections_applied_by_check_enum(
    conn: sqlite3.Connection,
) -> None:
    """applied_by CHECK enforces ('auto', 'operator')."""
    conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "run_id, discrepancy_type, field_name, material_to_review, "
        "resolution, created_at"
        ") VALUES (1, 'entry_price_mismatch', 'price', 0, 'unresolved', "
        "'2026-05-15')"
    )
    disc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    for valid in ("auto", "operator"):
        conn.execute(
            "INSERT INTO reconciliation_corrections ("
            "discrepancy_id, correction_action, affected_table, "
            "affected_row_id, field_name, pre_correction_value_json, "
            "applied_value_json, applied_at, applied_by, "
            "reconciliation_run_id"
            ") VALUES (?, 'auto_applied', 'fills', 1, 'price', '5.00', "
            "'5.30', '2026-05-15T10:00:00.000', ?, 1)",
            (disc_id, valid),
        )

    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO reconciliation_corrections ("
            "discrepancy_id, correction_action, affected_table, "
            "affected_row_id, field_name, pre_correction_value_json, "
            "applied_value_json, applied_at, applied_by, "
            "reconciliation_run_id"
            ") VALUES (?, 'auto_applied', 'fills', 1, 'price', '5.00', "
            "'5.30', '2026-05-15T10:00:00.000', 'system', 1)",
            (disc_id,),
        )


def test_reconciliation_corrections_discrepancy_fk_cascade(
    conn: sqlite3.Connection,
) -> None:
    """FK discrepancy_id → reconciliation_discrepancies ON DELETE CASCADE."""
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "run_id, discrepancy_type, field_name, material_to_review, "
        "resolution, created_at"
        ") VALUES (1, 'entry_price_mismatch', 'price', 0, 'unresolved', "
        "'2026-05-15')"
    )
    disc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO reconciliation_corrections ("
        "discrepancy_id, correction_action, affected_table, "
        "affected_row_id, field_name, pre_correction_value_json, "
        "applied_value_json, applied_at, applied_by, "
        "reconciliation_run_id"
        ") VALUES (?, 'auto_applied', 'fills', 1, 'price', '5.00', "
        "'5.30', '2026-05-15T10:00:00.000', 'auto', 1)",
        (disc_id,),
    )
    correction_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Deleting the parent discrepancy cascades to the correction row.
    conn.execute(
        "DELETE FROM reconciliation_discrepancies WHERE discrepancy_id = ?",
        (disc_id,),
    )
    remaining = conn.execute(
        "SELECT correction_id FROM reconciliation_corrections "
        "WHERE correction_id = ?",
        (correction_id,),
    ).fetchone()
    assert remaining is None


def test_reconciliation_corrections_run_fk_cascade(
    conn: sqlite3.Connection,
) -> None:
    """FK reconciliation_run_id → reconciliation_runs ON DELETE CASCADE."""
    conn.execute("PRAGMA foreign_keys=ON")
    _plant_run(conn, run_id=9001)
    conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "run_id, discrepancy_type, field_name, material_to_review, "
        "resolution, created_at"
        ") VALUES (9001, 'entry_price_mismatch', 'price', 0, 'unresolved', "
        "'2026-05-15')"
    )
    disc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO reconciliation_corrections ("
        "discrepancy_id, correction_action, affected_table, "
        "affected_row_id, field_name, pre_correction_value_json, "
        "applied_value_json, applied_at, applied_by, "
        "reconciliation_run_id"
        ") VALUES (?, 'auto_applied', 'fills', 1, 'price', '5.00', '5.30', "
        "'2026-05-15T10:00:00.000', 'auto', 9001)",
        (disc_id,),
    )
    correction_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "DELETE FROM reconciliation_runs WHERE run_id = ?", (9001,)
    )
    remaining = conn.execute(
        "SELECT correction_id FROM reconciliation_corrections "
        "WHERE correction_id = ?",
        (correction_id,),
    ).fetchone()
    assert remaining is None


# ============================================================================
# §2 — reconciliation_discrepancies — resolution CHECK enum widened to 9.
# ============================================================================


_VALID_RESOLUTIONS = (
    # 5 preserved from migration 0017
    "journal_corrected",
    "source_treated_canonical",
    "manual_override",
    "unresolved",
    "acknowledged_immaterial",
    # 4 new at v19
    "auto_corrected_from_schwab",
    # 'pending_ambiguity_resolution' + 'operator_resolved_ambiguity' covered
    # under the cross-column CHECK tests below (they require non-NULL
    # ambiguity_kind to pass the CHECK).
    "operator_overridden",
)


@pytest.mark.parametrize("resolution", _VALID_RESOLUTIONS)
def test_reconciliation_discrepancies_resolution_check_accepts_widened(
    conn: sqlite3.Connection, resolution: str,
) -> None:
    """All 9 widened resolution values accept INSERTs (except the 2 that
    require non-NULL ambiguity_kind, which are tested in §4)."""
    conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "run_id, discrepancy_type, field_name, material_to_review, "
        "resolution, created_at"
        ") VALUES (1, 'entry_price_mismatch', 'price', 0, ?, '2026-05-15')",
        (resolution,),
    )


def test_reconciliation_discrepancies_resolution_check_rejects_invalid(
    conn: sqlite3.Connection,
) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO reconciliation_discrepancies ("
            "run_id, discrepancy_type, field_name, material_to_review, "
            "resolution, created_at"
            ") VALUES (1, 'entry_price_mismatch', 'price', 0, 'foobar', "
            "'2026-05-15')"
        )


# ============================================================================
# §3 — ambiguity_kind column + 7-value CHECK enum.
# ============================================================================


_VALID_AMBIGUITY_KINDS = (
    "multi_partial_vs_consolidated",
    "multi_match_within_window",
    "unknown_schwab_subtype",
    "field_shape_incompatible",
    "schwab_returned_no_match",
    "validator_rejected",
    "unsupported",
)


def test_reconciliation_discrepancies_ambiguity_kind_column_exists(
    conn: sqlite3.Connection,
) -> None:
    """Acceptance #6: nullable TEXT column with 7-value CHECK enum exists."""
    cur = conn.execute("PRAGMA table_info(reconciliation_discrepancies)")
    rows = cur.fetchall()
    info = {r[1]: r for r in rows}  # name -> (cid, name, type, notnull, ...)
    assert "ambiguity_kind" in info
    # notnull == 0 (nullable)
    assert info["ambiguity_kind"][3] == 0


@pytest.mark.parametrize("kind", _VALID_AMBIGUITY_KINDS)
def test_reconciliation_discrepancies_ambiguity_kind_accepts_valid(
    conn: sqlite3.Connection, kind: str,
) -> None:
    """All 7 ambiguity_kind values accept inserts when paired with the
    matching resolution under the cross-column CHECK.
    """
    conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "run_id, discrepancy_type, field_name, material_to_review, "
        "resolution, ambiguity_kind, created_at"
        ") VALUES (1, 'entry_price_mismatch', 'price', 0, "
        "'pending_ambiguity_resolution', ?, '2026-05-15')",
        (kind,),
    )


def test_reconciliation_discrepancies_ambiguity_kind_rejects_invalid(
    conn: sqlite3.Connection,
) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO reconciliation_discrepancies ("
            "run_id, discrepancy_type, field_name, material_to_review, "
            "resolution, ambiguity_kind, created_at"
            ") VALUES (1, 'entry_price_mismatch', 'price', 0, "
            "'pending_ambiguity_resolution', 'foobar', '2026-05-15')"
        )


# ============================================================================
# §4 — Cross-column CHECK (ambiguity_kind, resolution) bidirectional.
#     Plan §B.1 acceptance #15 — discriminating test.
# ============================================================================


def test_cross_column_check_rejects_ambiguity_kind_with_wrong_resolution(
    conn: sqlite3.Connection,
) -> None:
    """resolution='unresolved' + ambiguity_kind='unsupported' MUST raise.

    Cross-column CHECK enforces: ambiguity_kind IS NOT NULL implies
    resolution IN ('pending_ambiguity_resolution', 'operator_resolved_ambiguity').
    """
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO reconciliation_discrepancies ("
            "run_id, discrepancy_type, field_name, material_to_review, "
            "resolution, ambiguity_kind, created_at"
            ") VALUES (1, 'entry_price_mismatch', 'price', 0, 'unresolved', "
            "'unsupported', '2026-05-15')"
        )


def test_cross_column_check_rejects_pending_with_null_ambiguity_kind(
    conn: sqlite3.Connection,
) -> None:
    """resolution='pending_ambiguity_resolution' + ambiguity_kind=NULL MUST raise.

    Cross-column CHECK enforces: resolution IN
    ('pending_ambiguity_resolution', 'operator_resolved_ambiguity') implies
    ambiguity_kind IS NOT NULL.
    """
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO reconciliation_discrepancies ("
            "run_id, discrepancy_type, field_name, material_to_review, "
            "resolution, ambiguity_kind, created_at"
            ") VALUES (1, 'entry_price_mismatch', 'price', 0, "
            "'pending_ambiguity_resolution', NULL, '2026-05-15')"
        )


def test_cross_column_check_rejects_operator_resolved_with_null_ambiguity_kind(
    conn: sqlite3.Connection,
) -> None:
    """resolution='operator_resolved_ambiguity' + ambiguity_kind=NULL MUST raise."""
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO reconciliation_discrepancies ("
            "run_id, discrepancy_type, field_name, material_to_review, "
            "resolution, ambiguity_kind, created_at"
            ") VALUES (1, 'entry_price_mismatch', 'price', 0, "
            "'operator_resolved_ambiguity', NULL, '2026-05-15')"
        )


def test_cross_column_check_accepts_pending_with_ambiguity_kind(
    conn: sqlite3.Connection,
) -> None:
    """Valid: resolution='pending_ambiguity_resolution' + non-NULL ambiguity_kind."""
    conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "run_id, discrepancy_type, field_name, material_to_review, "
        "resolution, ambiguity_kind, created_at"
        ") VALUES (1, 'entry_price_mismatch', 'price', 0, "
        "'pending_ambiguity_resolution', 'multi_partial_vs_consolidated', "
        "'2026-05-15')"
    )


def test_cross_column_check_accepts_operator_resolved_with_ambiguity_kind(
    conn: sqlite3.Connection,
) -> None:
    """Valid: resolution='operator_resolved_ambiguity' + non-NULL ambiguity_kind."""
    conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "run_id, discrepancy_type, field_name, material_to_review, "
        "resolution, ambiguity_kind, created_at"
        ") VALUES (1, 'entry_price_mismatch', 'price', 0, "
        "'operator_resolved_ambiguity', 'validator_rejected', '2026-05-15')"
    )


def test_cross_column_check_accepts_non_pending_with_null_ambiguity_kind(
    conn: sqlite3.Connection,
) -> None:
    """Valid: resolution='unresolved' + ambiguity_kind=NULL."""
    conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "run_id, discrepancy_type, field_name, material_to_review, "
        "resolution, ambiguity_kind, created_at"
        ") VALUES (1, 'entry_price_mismatch', 'price', 0, 'unresolved', "
        "NULL, '2026-05-15')"
    )


# ============================================================================
# §5 — reconciliation_discrepancies indexes (4 preserved + 1 new partial).
# ============================================================================


def test_reconciliation_discrepancies_has_5_indexes(
    conn: sqlite3.Connection,
) -> None:
    """Acceptance #8 + #12 — 4 preserved + 1 new partial pending_ambiguity index."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND tbl_name='reconciliation_discrepancies' "
        "AND name NOT LIKE 'sqlite_autoindex_%'"
    ).fetchall()
    names = {r[0] for r in rows}
    expected = {
        "ix_reconciliation_discrepancies_run",
        "ix_reconciliation_discrepancies_trade",
        "ix_reconciliation_discrepancies_unresolved",
        "ix_reconciliation_discrepancies_material",
        "ix_reconciliation_discrepancies_pending_ambiguity",
    }
    assert names == expected, (
        f"index drift; missing {expected - names}; extra {names - expected}"
    )


def test_pending_ambiguity_partial_index_predicate(
    conn: sqlite3.Connection,
) -> None:
    """Acceptance #12 — new partial index has predicate
    `WHERE resolution = 'pending_ambiguity_resolution'`.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' "
        "AND name='ix_reconciliation_discrepancies_pending_ambiguity'"
    ).fetchone()
    assert row is not None
    sql = row[0]
    assert "WHERE resolution = 'pending_ambiguity_resolution'" in sql, (
        f"expected partial-index predicate; got: {sql}"
    )
    assert "ambiguity_kind" in sql
    assert "created_at" in sql


# ============================================================================
# §6 — review_log.superseded_by_correction_id (acceptance #9).
# ============================================================================


def test_review_log_has_superseded_by_correction_id(
    conn: sqlite3.Connection,
) -> None:
    cur = conn.execute("PRAGMA table_info(review_log)")
    info = {r[1]: r for r in cur.fetchall()}
    assert "superseded_by_correction_id" in info
    assert info["superseded_by_correction_id"][3] == 0  # notnull == 0 (nullable)


def test_review_log_superseded_fk_set_null_on_correction_delete(
    conn: sqlite3.Connection,
) -> None:
    """Acceptance #9 — FK ON DELETE SET NULL nulls the back-pointer when the
    referenced reconciliation_corrections row is deleted.
    """
    conn.execute("PRAGMA foreign_keys=ON")
    # Plant a discrepancy for the corrections row to reference.
    conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "run_id, discrepancy_type, field_name, material_to_review, "
        "resolution, created_at"
        ") VALUES (1, 'entry_price_mismatch', 'price', 0, 'unresolved', "
        "'2026-05-15')"
    )
    disc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO reconciliation_corrections ("
        "discrepancy_id, correction_action, affected_table, "
        "affected_row_id, field_name, pre_correction_value_json, "
        "applied_value_json, applied_at, applied_by, "
        "reconciliation_run_id"
        ") VALUES (?, 'auto_applied', 'fills', 1, 'price', '5.00', '5.30', "
        "'2026-05-15T10:00:00.000', 'auto', 1)",
        (disc_id,),
    )
    correction_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Plant a review_log row that references the correction. review_log is
    # cadence-grain (no per-trade FK; see Phase 10 Sub-bundle B forward-binding
    # lesson — cadence-vs-per-trade-FK asymmetry).
    conn.execute(
        "INSERT INTO review_log ("
        "review_type, period_start, period_end, scheduled_date, "
        "superseded_by_correction_id"
        ") VALUES ('weekly', '2026-05-01', '2026-05-10', '2026-05-12', ?)",
        (correction_id,),
    )
    review_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Before deletion: FK pointer populated.
    pre = conn.execute(
        "SELECT superseded_by_correction_id FROM review_log WHERE review_id = ?",
        (review_id,),
    ).fetchone()
    assert pre[0] == correction_id

    # Delete the correction; review_log survives with NULL pointer.
    conn.execute(
        "DELETE FROM reconciliation_corrections WHERE correction_id = ?",
        (correction_id,),
    )
    post = conn.execute(
        "SELECT superseded_by_correction_id FROM review_log WHERE review_id = ?",
        (review_id,),
    ).fetchone()
    assert post[0] is None


# ============================================================================
# §7 — schwab_api_calls.linked_correction_id (acceptance #11).
# ============================================================================


def test_schwab_api_calls_has_linked_correction_id(
    conn: sqlite3.Connection,
) -> None:
    cur = conn.execute("PRAGMA table_info(schwab_api_calls)")
    info = {r[1]: r for r in cur.fetchall()}
    assert "linked_correction_id" in info
    assert info["linked_correction_id"][3] == 0  # nullable


def test_schwab_api_calls_linked_correction_fk_set_null_on_delete(
    conn: sqlite3.Connection,
) -> None:
    """FK linked_correction_id → reconciliation_corrections ON DELETE SET NULL."""
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "run_id, discrepancy_type, field_name, material_to_review, "
        "resolution, created_at"
        ") VALUES (1, 'entry_price_mismatch', 'price', 0, 'unresolved', "
        "'2026-05-15')"
    )
    disc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO reconciliation_corrections ("
        "discrepancy_id, correction_action, affected_table, "
        "affected_row_id, field_name, pre_correction_value_json, "
        "applied_value_json, applied_at, applied_by, "
        "reconciliation_run_id"
        ") VALUES (?, 'auto_applied', 'fills', 1, 'price', '5.00', '5.30', "
        "'2026-05-15T10:00:00.000', 'auto', 1)",
        (disc_id,),
    )
    correction_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.execute(
        "INSERT INTO schwab_api_calls ("
        "ts, endpoint, status, surface, environment, linked_correction_id"
        ") VALUES ('2026-05-15T10:00:00.000', 'accounts.linked', 'success', "
        "'cli', 'production', ?)",
        (correction_id,),
    )
    call_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    pre = conn.execute(
        "SELECT linked_correction_id FROM schwab_api_calls WHERE call_id = ?",
        (call_id,),
    ).fetchone()
    assert pre[0] == correction_id

    conn.execute(
        "DELETE FROM reconciliation_corrections WHERE correction_id = ?",
        (correction_id,),
    )
    post = conn.execute(
        "SELECT linked_correction_id FROM schwab_api_calls WHERE call_id = ?",
        (call_id,),
    ).fetchone()
    assert post[0] is None


# ============================================================================
# §8 — trade_events event_type CHECK widened 6 → 7 (acceptance #10).
# ============================================================================


_VALID_EVENT_TYPES = (
    "entry",
    "stop_adjust",
    "note",
    "exit",
    "flag",
    "pre_trade_edit",
    "reconciliation_auto_correct",
)


@pytest.mark.parametrize("event_type", _VALID_EVENT_TYPES)
def test_trade_events_event_type_check_accepts_widened(
    conn: sqlite3.Connection, event_type: str,
) -> None:
    """All 7 widened event_type values accept INSERTs."""
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        "INSERT INTO trades ("
        "ticker, entry_date, entry_price, initial_shares, initial_stop, "
        "current_stop, state, trade_origin, pre_trade_locked_at"
        ") VALUES (?, '2026-05-01', 10.0, 100, 9.0, 9.0, 'closed', "
        "'pipeline_aplus', '2026-05-01T09:30:00.000')",
        (f"T{event_type[:7]}",),
    )
    trade_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO trade_events (trade_id, ts, event_type) "
        "VALUES (?, '2026-05-15T10:00:00.000', ?)",
        (trade_id, event_type),
    )


def test_trade_events_event_type_check_rejects_invalid(
    conn: sqlite3.Connection,
) -> None:
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        "INSERT INTO trades ("
        "ticker, entry_date, entry_price, initial_shares, initial_stop, "
        "current_stop, state, trade_origin, pre_trade_locked_at"
        ") VALUES ('INV', '2026-05-01', 10.0, 100, 9.0, 9.0, 'closed', "
        "'pipeline_aplus', '2026-05-01T09:30:00.000')"
    )
    trade_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO trade_events (trade_id, ts, event_type) "
            "VALUES (?, '2026-05-15T10:00:00.000', 'invalid_event')",
            (trade_id,),
        )


def test_trade_events_index_recreated(conn: sqlite3.Connection) -> None:
    """Acceptance #10 — ix_trade_events_trade survives the rebuild."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND tbl_name='trade_events' AND name NOT LIKE 'sqlite_autoindex_%'"
    ).fetchall()
    names = {r[0] for r in rows}
    assert "ix_trade_events_trade" in names
