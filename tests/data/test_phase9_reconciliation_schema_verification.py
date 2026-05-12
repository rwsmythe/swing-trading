"""Phase 9 Task B.0 — consumer-side verification of reconciliation schema.

Sub-bundle A's migration 0017 landed both ``reconciliation_runs`` (19 cols
+ 3 indexes) and ``reconciliation_discrepancies`` (19 cols + 4 indexes) per
the binding LIST in the migration file. The plan §E text says "17 + 18 cols"
which is a stale brainstorm miscount — column LIST in
``swing/data/migrations/0017_phase9_risk_policy_and_reconciliation.sql`` is
binding (same Codex R1 Major #2 precedent as risk_policy "28 vs 34").

This task does NOT modify the migration. Sub-bundle B consumes the schema
landed by Sub-bundle A; the tests here verify the consumer's contract holds.

Mirrors the fixture pattern in ``tests/data/test_migration_0017.py``.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase9_b0.db"
    return ensure_schema(db_path)


# ============================================================================
# §1 — reconciliation_runs table shape (19 columns + 3 indexes)
# ============================================================================


_RECON_RUNS_EXPECTED_COLS: frozenset[str] = frozenset({
    "run_id", "source", "source_artifact_path", "source_artifact_sha256",
    "period_start", "period_end", "started_ts", "finished_ts", "state",
    "account_equity_journal_dollars", "account_equity_source_dollars",
    "equity_delta_dollars", "trades_reconciled_count",
    "fills_reconciled_count", "discrepancies_count",
    "unresolved_discrepancies_count", "summary_json", "error_message",
    "notes",
})


def test_reconciliation_runs_has_19_columns(conn: sqlite3.Connection) -> None:
    """Plan §E says 17; migration LIST enumerates 19 (binding).

    Per dispatch brief §0.5 #1 + Codex R1 Major #2 precedent: column LIST
    is binding; subtotal text is advisory.
    """
    cur = conn.execute("PRAGMA table_info(reconciliation_runs)")
    cols = {r[1] for r in cur.fetchall()}
    assert cols == _RECON_RUNS_EXPECTED_COLS, (
        f"column drift; missing {_RECON_RUNS_EXPECTED_COLS - cols}; "
        f"extra {cols - _RECON_RUNS_EXPECTED_COLS}"
    )
    assert len(cols) == 19


def test_reconciliation_runs_indexes_present(conn: sqlite3.Connection) -> None:
    """3 indexes per migration §2: started_ts, state (partial), source (composite)."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND tbl_name='reconciliation_runs' ORDER BY name"
    ).fetchall()
    names = {r[0] for r in rows}
    assert "ix_reconciliation_runs_started_ts" in names
    assert "ix_reconciliation_runs_state" in names
    assert "ix_reconciliation_runs_source" in names


def test_reconciliation_runs_state_index_is_partial(conn: sqlite3.Connection) -> None:
    """ix_reconciliation_runs_state has WHERE state IN ('running','failed')."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' "
        "AND name='ix_reconciliation_runs_state'"
    ).fetchone()
    assert row is not None
    sql = row[0]
    assert "WHERE" in sql
    assert "running" in sql
    assert "failed" in sql


def test_reconciliation_runs_source_index_is_composite(
    conn: sqlite3.Connection,
) -> None:
    """ix_reconciliation_runs_source is composite (source, started_ts)."""
    rows = conn.execute(
        "PRAGMA index_info(ix_reconciliation_runs_source)"
    ).fetchall()
    # PRAGMA index_info returns (seqno, cid, name) per indexed column.
    indexed_cols = [r[2] for r in rows]
    assert indexed_cols == ["source", "started_ts"]


# ============================================================================
# §2 — reconciliation_runs CHECK enums
# ============================================================================


def test_reconciliation_runs_source_check_rejects_invalid(
    conn: sqlite3.Connection,
) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO reconciliation_runs (source, started_ts) "
            "VALUES ('not_a_source', '2026-05-12T10:00:00.000')"
        )


def test_reconciliation_runs_state_check_rejects_invalid(
    conn: sqlite3.Connection,
) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO reconciliation_runs (source, started_ts, state) "
            "VALUES ('tos_csv', '2026-05-12T10:00:00.000', 'not_a_state')"
        )


def test_reconciliation_runs_source_check_accepts_all_enum_values(
    conn: sqlite3.Connection,
) -> None:
    """All 4 source enum values per migration §2 land cleanly."""
    for source in ("tos_csv", "schwab_api", "manual", "system_audit"):
        conn.execute(
            "INSERT INTO reconciliation_runs (source, started_ts) "
            "VALUES (?, '2026-05-12T10:00:00.000')",
            (source,),
        )


# ============================================================================
# §3 — reconciliation_discrepancies table shape (19 columns + 4 indexes)
# ============================================================================


_RECON_DISC_EXPECTED_COLS: frozenset[str] = frozenset({
    "discrepancy_id", "run_id", "discrepancy_type", "trade_id", "fill_id",
    "cash_movement_id", "linked_daily_management_record_id", "ticker",
    "field_name", "expected_value_json", "actual_value_json", "delta_text",
    "material_to_review", "resolution", "resolution_reason", "resolved_at",
    "resolved_by", "mistake_tag_assigned", "created_at",
})


def test_reconciliation_discrepancies_has_19_columns(
    conn: sqlite3.Connection,
) -> None:
    """Plan §E says 18; migration LIST enumerates 19 (binding)."""
    cur = conn.execute("PRAGMA table_info(reconciliation_discrepancies)")
    cols = {r[1] for r in cur.fetchall()}
    assert cols == _RECON_DISC_EXPECTED_COLS, (
        f"column drift; missing {_RECON_DISC_EXPECTED_COLS - cols}; "
        f"extra {cols - _RECON_DISC_EXPECTED_COLS}"
    )
    assert len(cols) == 19


def test_reconciliation_discrepancies_indexes_present(
    conn: sqlite3.Connection,
) -> None:
    """4 indexes per migration §3: run, trade (partial), unresolved (partial),
    material (composite partial)."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND tbl_name='reconciliation_discrepancies' ORDER BY name"
    ).fetchall()
    names = {r[0] for r in rows}
    assert "ix_reconciliation_discrepancies_run" in names
    assert "ix_reconciliation_discrepancies_trade" in names
    assert "ix_reconciliation_discrepancies_unresolved" in names
    assert "ix_reconciliation_discrepancies_material" in names


def test_reconciliation_discrepancies_trade_index_is_partial(
    conn: sqlite3.Connection,
) -> None:
    """ix_reconciliation_discrepancies_trade has WHERE trade_id IS NOT NULL."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' "
        "AND name='ix_reconciliation_discrepancies_trade'"
    ).fetchone()
    assert row is not None
    assert "trade_id IS NOT NULL" in row[0]


def test_reconciliation_discrepancies_unresolved_index_is_partial(
    conn: sqlite3.Connection,
) -> None:
    """ix_reconciliation_discrepancies_unresolved has WHERE resolution='unresolved'."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' "
        "AND name='ix_reconciliation_discrepancies_unresolved'"
    ).fetchone()
    assert row is not None
    assert "unresolved" in row[0]
    assert "WHERE" in row[0]


def test_reconciliation_discrepancies_material_index_is_partial_composite(
    conn: sqlite3.Connection,
) -> None:
    """ix_reconciliation_discrepancies_material is composite + partial."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' "
        "AND name='ix_reconciliation_discrepancies_material'"
    ).fetchone()
    assert row is not None
    sql = row[0]
    assert "WHERE" in sql
    assert "material_to_review" in sql
    assert "resolution" in sql
    # Composite-key columns.
    info_rows = conn.execute(
        "PRAGMA index_info(ix_reconciliation_discrepancies_material)"
    ).fetchall()
    indexed_cols = [r[2] for r in info_rows]
    assert indexed_cols == ["trade_id", "material_to_review"]


# ============================================================================
# §4 — reconciliation_discrepancies CHECK enums
# ============================================================================


def _insert_run(conn: sqlite3.Connection, source: str = "tos_csv") -> int:
    conn.execute(
        "INSERT INTO reconciliation_runs (source, started_ts, state) "
        "VALUES (?, '2026-05-12T10:00:00.000', 'completed')",
        (source,),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def test_discrepancies_discrepancy_type_check_rejects_invalid(
    conn: sqlite3.Connection,
) -> None:
    run_id = _insert_run(conn)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO reconciliation_discrepancies ("
            "run_id, discrepancy_type, field_name, material_to_review, "
            "resolution, created_at"
            ") VALUES (?, 'not_a_type', 'price', 1, 'unresolved', "
            "'2026-05-12T10:00:00.000')",
            (run_id,),
        )


def test_discrepancies_resolution_check_rejects_invalid(
    conn: sqlite3.Connection,
) -> None:
    run_id = _insert_run(conn)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO reconciliation_discrepancies ("
            "run_id, discrepancy_type, field_name, material_to_review, "
            "resolution, created_at"
            ") VALUES (?, 'close_price_mismatch', 'price', 1, 'not_real', "
            "'2026-05-12T10:00:00.000')",
            (run_id,),
        )


def test_discrepancies_material_to_review_check_rejects_invalid(
    conn: sqlite3.Connection,
) -> None:
    """material_to_review IN (0, 1)."""
    run_id = _insert_run(conn)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO reconciliation_discrepancies ("
            "run_id, discrepancy_type, field_name, material_to_review, "
            "resolution, created_at"
            ") VALUES (?, 'close_price_mismatch', 'price', 2, 'unresolved', "
            "'2026-05-12T10:00:00.000')",
            (run_id,),
        )


def test_discrepancies_all_discrepancy_type_enum_values_accepted(
    conn: sqlite3.Connection,
) -> None:
    """All 10 discrepancy_type enum values per migration §3 land cleanly."""
    run_id = _insert_run(conn)
    for dtype in (
        "close_price_mismatch", "stop_mismatch", "position_qty_mismatch",
        "cash_movement_mismatch", "sector_tamper", "snapshot_mismatch",
        "unmatched_open_fill", "unmatched_close_fill",
        "entry_price_mismatch", "equity_delta",
    ):
        conn.execute(
            "INSERT INTO reconciliation_discrepancies ("
            "run_id, discrepancy_type, field_name, material_to_review, "
            "resolution, created_at"
            ") VALUES (?, ?, 'fld', 0, 'unresolved', "
            "'2026-05-12T10:00:00.000')",
            (run_id, dtype),
        )


def test_discrepancies_all_resolution_enum_values_accepted(
    conn: sqlite3.Connection,
) -> None:
    """All 5 resolution enum values per migration §3 land cleanly."""
    run_id = _insert_run(conn)
    for resolution in (
        "journal_corrected", "source_treated_canonical", "manual_override",
        "unresolved", "acknowledged_immaterial",
    ):
        conn.execute(
            "INSERT INTO reconciliation_discrepancies ("
            "run_id, discrepancy_type, field_name, material_to_review, "
            "resolution, created_at"
            ") VALUES (?, 'close_price_mismatch', 'fld', 0, ?, "
            "'2026-05-12T10:00:00.000')",
            (run_id, resolution),
        )


def test_discrepancies_resolution_default_is_unresolved(
    conn: sqlite3.Connection,
) -> None:
    """resolution column defaults to 'unresolved' per migration §3."""
    run_id = _insert_run(conn)
    conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "run_id, discrepancy_type, field_name, material_to_review, created_at"
        ") VALUES (?, 'close_price_mismatch', 'price', 1, "
        "'2026-05-12T10:00:00.000')",
        (run_id,),
    )
    row = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    assert row[0] == "unresolved"


# ============================================================================
# §5 — FK CASCADE on run_id (delete run → child discrepancies wiped)
# ============================================================================


def test_discrepancies_run_id_fk_cascade(conn: sqlite3.Connection) -> None:
    """ON DELETE CASCADE: deleting a reconciliation_runs row removes child
    discrepancies."""
    conn.execute("PRAGMA foreign_keys = ON")
    run_id = _insert_run(conn)
    conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "run_id, discrepancy_type, field_name, material_to_review, "
        "resolution, created_at"
        ") VALUES (?, 'close_price_mismatch', 'price', 1, 'unresolved', "
        "'2026-05-12T10:00:00.000')",
        (run_id,),
    )
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_discrepancies WHERE run_id = ?",
        (run_id,),
    ).fetchone()[0] == 1
    conn.execute("DELETE FROM reconciliation_runs WHERE run_id = ?", (run_id,))
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_discrepancies WHERE run_id = ?",
        (run_id,),
    ).fetchone()[0] == 0


# ============================================================================
# §6 — FK SET NULL on trade_id / fill_id / cash_movement_id /
#       linked_daily_management_record_id (delete parent → discrepancy survives
#       with NULL FK column)
# ============================================================================


def _insert_trade(conn: sqlite3.Connection, ticker: str = "TESTSN") -> int:
    conn.execute(
        "INSERT INTO trades ("
        "ticker, entry_date, entry_price, initial_shares, initial_stop, "
        "current_stop, state, sector, industry, trade_origin, "
        "pre_trade_locked_at, current_size"
        ") VALUES ("
        "?, '2026-05-12', 100.0, 10, 95.0, 95.0, 'entered', "
        "'Tech', 'Software', 'manual_off_pipeline', "
        "'2026-05-12T15:30:00.000', 10"
        ")",
        (ticker,),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _insert_fill(conn: sqlite3.Connection, trade_id: int) -> int:
    conn.execute(
        "INSERT INTO fills ("
        "trade_id, fill_datetime, action, quantity, price"
        ") VALUES (?, '2026-05-12T16:00:00', 'entry', 10.0, 100.0)",
        (trade_id,),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _insert_cash_movement(conn: sqlite3.Connection) -> int:
    conn.execute(
        "INSERT INTO cash_movements (date, kind, amount, ref) "
        "VALUES ('2026-05-12', 'deposit', 100.0, 'test-ref-sn')"
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _insert_dmr(conn: sqlite3.Connection, trade_id: int) -> int:
    """Insert a daily_management_records row of type event_log.

    Service-layer validators require richer per-record-type field sets, but
    the SCHEMA only requires the 6 NOT NULL columns at the table level:
    trade_id, record_type, review_date, data_asof_session, created_at,
    mfe_mae_precision_level. Sufficient for FK SET NULL verification.
    """
    conn.execute(
        "INSERT INTO daily_management_records ("
        "trade_id, record_type, review_date, data_asof_session, created_at, "
        "mfe_mae_precision_level"
        ") VALUES (?, 'event_log', '2026-05-12', '2026-05-12', "
        "'2026-05-12T16:00:00.000', 'daily_approximate')",
        (trade_id,),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _insert_discrepancy(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    trade_id: int | None = None,
    fill_id: int | None = None,
    cash_movement_id: int | None = None,
    linked_dmr_id: int | None = None,
) -> int:
    conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "run_id, discrepancy_type, trade_id, fill_id, cash_movement_id, "
        "linked_daily_management_record_id, field_name, material_to_review, "
        "resolution, created_at"
        ") VALUES (?, 'close_price_mismatch', ?, ?, ?, ?, 'price', 1, "
        "'unresolved', '2026-05-12T10:00:00.000')",
        (run_id, trade_id, fill_id, cash_movement_id, linked_dmr_id),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def test_discrepancies_trade_id_fk_set_null(conn: sqlite3.Connection) -> None:
    """ON DELETE SET NULL on trade_id: discrepancy row survives delete of trade."""
    conn.execute("PRAGMA foreign_keys = ON")
    run_id = _insert_run(conn)
    trade_id = _insert_trade(conn, ticker="TRDSN1")
    disc_id = _insert_discrepancy(conn, run_id, trade_id=trade_id)
    conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    row = conn.execute(
        "SELECT trade_id FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (disc_id,),
    ).fetchone()
    assert row is not None, "discrepancy row must survive trade DELETE"
    assert row[0] is None, "trade_id must be SET NULL after parent delete"


def test_discrepancies_fill_id_fk_set_null(conn: sqlite3.Connection) -> None:
    """ON DELETE SET NULL on fill_id: discrepancy row survives delete of fill."""
    conn.execute("PRAGMA foreign_keys = ON")
    run_id = _insert_run(conn)
    trade_id = _insert_trade(conn, ticker="TRDSN2")
    fill_id = _insert_fill(conn, trade_id)
    disc_id = _insert_discrepancy(conn, run_id, fill_id=fill_id)
    conn.execute("DELETE FROM fills WHERE fill_id = ?", (fill_id,))
    row = conn.execute(
        "SELECT fill_id FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (disc_id,),
    ).fetchone()
    assert row is not None
    assert row[0] is None


def test_discrepancies_cash_movement_id_fk_set_null(
    conn: sqlite3.Connection,
) -> None:
    """ON DELETE SET NULL on cash_movement_id."""
    conn.execute("PRAGMA foreign_keys = ON")
    run_id = _insert_run(conn)
    cm_id = _insert_cash_movement(conn)
    disc_id = _insert_discrepancy(conn, run_id, cash_movement_id=cm_id)
    conn.execute("DELETE FROM cash_movements WHERE id = ?", (cm_id,))
    row = conn.execute(
        "SELECT cash_movement_id FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (disc_id,),
    ).fetchone()
    assert row is not None
    assert row[0] is None


def test_discrepancies_linked_daily_management_record_id_fk_set_null(
    conn: sqlite3.Connection,
) -> None:
    """ON DELETE SET NULL on linked_daily_management_record_id.

    Deleting the daily_management_records row directly (not via cascading
    trade delete) so this test exclusively exercises the SET NULL contract
    on linked_daily_management_record_id (not the trade FK cascade chain).
    """
    conn.execute("PRAGMA foreign_keys = ON")
    run_id = _insert_run(conn)
    trade_id = _insert_trade(conn, ticker="TRDSN3")
    dmr_id = _insert_dmr(conn, trade_id)
    disc_id = _insert_discrepancy(conn, run_id, linked_dmr_id=dmr_id)
    conn.execute(
        "DELETE FROM daily_management_records "
        "WHERE management_record_id = ?",
        (dmr_id,),
    )
    row = conn.execute(
        "SELECT linked_daily_management_record_id "
        "FROM reconciliation_discrepancies WHERE discrepancy_id = ?",
        (disc_id,),
    ).fetchone()
    assert row is not None
    assert row[0] is None
