"""Phase 12 Sub-bundle C.A T-A.1 — migration 0019 row preservation across rebuilds.

Per plan §B.1 acceptance #7 (auto-correct reconciliation plan, 2026-05-15):

  The reconciliation_discrepancies + trade_events rebuilds (CHECK enum
  widening + new column) MUST preserve all existing rows via INSERT-SELECT
  byte-for-byte. The new `ambiguity_kind` column defaults to NULL for all
  copied rows.

Discriminating tests assert row-preservation via column-by-column equality
against a pre-migration snapshot fetched DYNAMICALLY from the test DB —
NOT against a fixed planted count. Plant rows at v18, force a fresh
migration run from v18 → v19, verify equality.

Migration runner discipline (`_apply_migration` toggles `foreign_keys=OFF`
during executescript), so the table rebuild's DROP-RENAME does NOT
cascade-wipe FK-linked rows. CLAUDE.md `Phase 7 backup gate` precedent
documents the discipline.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from swing.data.db import _apply_migration, run_migrations

_MIGRATION_0019_PATH = (
    Path(__file__).resolve().parents[2]
    / "swing"
    / "data"
    / "migrations"
    / "0019_phase12_bundle_c_auto_correct_reconciliation.sql"
)


def _walk_to_v18(db_path: Path) -> sqlite3.Connection:
    """Return a connection with schema_version == 18 (pre-0019 baseline)."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=18)
    conn.commit()
    return conn


# ============================================================================
# §1 — reconciliation_discrepancies row preservation (acceptance #7).
# ============================================================================


def test_rebuild_preserves_existing_discrepancy_rows(tmp_path: Path) -> None:
    """Plant 30 rows mimicking production state (~27 historical resolved + 3
    unresolved-material), apply 0019, assert byte-for-byte preservation.

    Mix of resolution values covers the 5 PRE-existing CHECK enum values to
    pin that NO row preservation drift sneaks past during the rebuild.
    """
    db = tmp_path / "swing.db"
    conn = _walk_to_v18(db)
    try:
        conn.execute(
            "INSERT INTO reconciliation_runs ("
            "run_id, source, started_ts, state"
            ") VALUES (1, 'tos_csv', '2026-05-12T10:00:00.000', 'completed')"
        )

        # Plant 30 rows with a mix of pre-v19 resolution values.
        planted_total = 30
        historical_count = 27
        for i in range(1, planted_total + 1):
            if i <= historical_count:
                resolution = "acknowledged_immaterial"
                resolved_at = "2026-05-12T16:00:00.000"
                resolved_by = "operator"
            else:
                resolution = "unresolved"
                resolved_at = None
                resolved_by = None
            conn.execute(
                "INSERT INTO reconciliation_discrepancies ("
                "discrepancy_id, run_id, discrepancy_type, ticker, "
                "field_name, expected_value_json, actual_value_json, "
                "delta_text, material_to_review, resolution, "
                "resolution_reason, resolved_at, resolved_by, created_at"
                ") VALUES (?, 1, 'entry_price_mismatch', ?, 'entry_price', "
                "'5.30', '5.31', '0.01', ?, ?, ?, ?, ?, '2026-05-12')",
                (
                    i,
                    f"T{i:03d}",
                    1 if i > historical_count else 0,
                    resolution,
                    f"reason-{i}" if resolution != "unresolved" else None,
                    resolved_at,
                    resolved_by,
                ),
            )
        conn.commit()

        # Capture dynamic pre-migration snapshot (column-by-column).
        pre_columns = (
            "discrepancy_id",
            "run_id",
            "discrepancy_type",
            "trade_id",
            "fill_id",
            "cash_movement_id",
            "linked_daily_management_record_id",
            "ticker",
            "field_name",
            "expected_value_json",
            "actual_value_json",
            "delta_text",
            "material_to_review",
            "resolution",
            "resolution_reason",
            "resolved_at",
            "resolved_by",
            "mistake_tag_assigned",
            "created_at",
        )
        select_clause = ", ".join(pre_columns)
        pre_rows = sorted(
            conn.execute(
                f"SELECT {select_clause} FROM reconciliation_discrepancies"
            ).fetchall()
        )
        assert len(pre_rows) == planted_total

        # Apply 0019.
        _apply_migration(conn, _MIGRATION_0019_PATH)
        post_version = conn.execute(
            "SELECT version FROM schema_version"
        ).fetchone()[0]
        assert post_version == 19

        # Same columns, same values (column-by-column equality).
        post_rows = sorted(
            conn.execute(
                f"SELECT {select_clause} FROM reconciliation_discrepancies"
            ).fetchall()
        )
        assert post_rows == pre_rows

        # New ambiguity_kind column is NULL for every copied row.
        ak_rows = conn.execute(
            "SELECT discrepancy_id, ambiguity_kind "
            "FROM reconciliation_discrepancies"
        ).fetchall()
        assert len(ak_rows) == planted_total
        assert all(r[1] is None for r in ak_rows)
    finally:
        conn.close()


def test_rebuild_preserves_all_5_legacy_resolution_values(tmp_path: Path) -> None:
    """Discriminating test: a row planted under each of the 5 pre-v19 enum
    values survives the rebuild (cross-column CHECK does NOT inadvertently
    reject legacy NULL ambiguity_kind for any of them).
    """
    db = tmp_path / "swing_legacy_resolutions.db"
    conn = _walk_to_v18(db)
    try:
        conn.execute(
            "INSERT INTO reconciliation_runs ("
            "run_id, source, started_ts, state"
            ") VALUES (1, 'tos_csv', '2026-05-12T10:00:00.000', 'completed')"
        )
        legacy_resolutions = (
            "journal_corrected",
            "source_treated_canonical",
            "manual_override",
            "unresolved",
            "acknowledged_immaterial",
        )
        for idx, resolution in enumerate(legacy_resolutions, start=1):
            conn.execute(
                "INSERT INTO reconciliation_discrepancies ("
                "discrepancy_id, run_id, discrepancy_type, ticker, "
                "field_name, material_to_review, resolution, created_at"
                ") VALUES (?, 1, 'entry_price_mismatch', ?, 'entry_price', "
                "0, ?, '2026-05-12')",
                (idx, f"L{idx}", resolution),
            )
        conn.commit()

        _apply_migration(conn, _MIGRATION_0019_PATH)

        rows = conn.execute(
            "SELECT discrepancy_id, resolution, ambiguity_kind "
            "FROM reconciliation_discrepancies "
            "ORDER BY discrepancy_id"
        ).fetchall()
        assert [r[1] for r in rows] == list(legacy_resolutions)
        assert all(r[2] is None for r in rows)
    finally:
        conn.close()


# ============================================================================
# §2 — reconciliation_discrepancies indexes preserved across rebuild
#     (acceptance #8 + #12).
# ============================================================================


def test_rebuild_preserves_all_4_legacy_indexes_and_adds_partial(
    tmp_path: Path,
) -> None:
    """All 4 v17 indexes get re-created; the new partial index lands too."""
    db = tmp_path / "indexes.db"
    conn = _walk_to_v18(db)
    try:
        pre_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='reconciliation_discrepancies' "
            "AND name NOT LIKE 'sqlite_autoindex_%'"
        ).fetchall()
        pre_names = {r[0] for r in pre_rows}
        assert pre_names == {
            "ix_reconciliation_discrepancies_run",
            "ix_reconciliation_discrepancies_trade",
            "ix_reconciliation_discrepancies_unresolved",
            "ix_reconciliation_discrepancies_material",
        }

        _apply_migration(conn, _MIGRATION_0019_PATH)

        post_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='reconciliation_discrepancies' "
            "AND name NOT LIKE 'sqlite_autoindex_%'"
        ).fetchall()
        post_names = {r[0] for r in post_rows}
        assert post_names == pre_names | {
            "ix_reconciliation_discrepancies_pending_ambiguity",
        }
    finally:
        conn.close()


# ============================================================================
# §3 — trade_events row preservation (acceptance #10).
# ============================================================================


def test_rebuild_preserves_trade_events_rows(tmp_path: Path) -> None:
    """Plant trade_events rows under each of the 6 v17 event_type values;
    assert byte-for-byte preservation post-rebuild AND ix_trade_events_trade
    re-created.
    """
    db = tmp_path / "trade_events.db"
    conn = _walk_to_v18(db)
    try:
        # Plant a closed trade to anchor the trade_events rows.
        conn.execute(
            "INSERT INTO trades ("
            "ticker, entry_date, entry_price, initial_shares, initial_stop, "
            "current_stop, state, trade_origin, pre_trade_locked_at"
            ") VALUES ('PRESERVE', '2026-05-01', 10.0, 100, 9.0, 9.0, "
            "'closed', 'pipeline_aplus', '2026-05-01T09:30:00.000')"
        )
        trade_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        legacy_event_types = (
            "entry",
            "stop_adjust",
            "note",
            "exit",
            "flag",
            "pre_trade_edit",
        )
        for idx, et in enumerate(legacy_event_types, start=1):
            conn.execute(
                "INSERT INTO trade_events ("
                "trade_id, ts, event_type, payload_json, rationale, notes"
                ") VALUES (?, ?, ?, ?, ?, ?)",
                (
                    trade_id,
                    f"2026-05-15T10:00:{idx:02d}.000",
                    et,
                    f'{{"k":{idx}}}',
                    f"rationale-{et}",
                    f"notes-{et}",
                ),
            )
        conn.commit()

        pre_columns = (
            "id",
            "trade_id",
            "ts",
            "event_type",
            "payload_json",
            "rationale",
            "notes",
        )
        select_clause = ", ".join(pre_columns)
        pre_rows = sorted(
            conn.execute(
                f"SELECT {select_clause} FROM trade_events "
                f"WHERE trade_id = ?",
                (trade_id,),
            ).fetchall()
        )
        assert len(pre_rows) == 6

        _apply_migration(conn, _MIGRATION_0019_PATH)

        post_rows = sorted(
            conn.execute(
                f"SELECT {select_clause} FROM trade_events "
                f"WHERE trade_id = ?",
                (trade_id,),
            ).fetchall()
        )
        assert post_rows == pre_rows

        # ix_trade_events_trade still present post-rebuild.
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='trade_events' "
            "AND name NOT LIKE 'sqlite_autoindex_%'"
        ).fetchall()
        names = {r[0] for r in rows}
        assert "ix_trade_events_trade" in names

        # The widened CHECK enum now accepts 'reconciliation_auto_correct'.
        conn.execute(
            "INSERT INTO trade_events ("
            "trade_id, ts, event_type, payload_json"
            ") VALUES (?, '2026-05-15T11:00:00.000', "
            "'reconciliation_auto_correct', '{\"applied\":true}')",
            (trade_id,),
        )
    finally:
        conn.close()


# ============================================================================
# §4 — Existing schwab_api_calls + review_log rows survive the ALTER ADDs
#     and gain NULL for the new column (acceptance #9 + #11).
# ============================================================================


def test_existing_schwab_api_calls_row_has_null_linked_correction_id(
    tmp_path: Path,
) -> None:
    db = tmp_path / "schwab_api_calls_preserved.db"
    conn = _walk_to_v18(db)
    try:
        conn.execute(
            "INSERT INTO schwab_api_calls ("
            "ts, endpoint, status, surface, environment"
            ") VALUES ('2026-05-14T10:00:00.000', 'accounts.linked', "
            "'success', 'cli', 'production')"
        )
        call_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()

        _apply_migration(conn, _MIGRATION_0019_PATH)

        row = conn.execute(
            "SELECT linked_correction_id FROM schwab_api_calls "
            "WHERE call_id = ?",
            (call_id,),
        ).fetchone()
        assert row[0] is None
    finally:
        conn.close()


def test_existing_review_log_row_has_null_superseded_by_correction_id(
    tmp_path: Path,
) -> None:
    db = tmp_path / "review_log_preserved.db"
    conn = _walk_to_v18(db)
    try:
        # review_log is cadence-grain (no per-trade FK).
        conn.execute(
            "INSERT INTO review_log ("
            "review_type, period_start, period_end, scheduled_date"
            ") VALUES ('weekly', '2026-05-01', '2026-05-10', '2026-05-12')"
        )
        review_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()

        _apply_migration(conn, _MIGRATION_0019_PATH)

        row = conn.execute(
            "SELECT superseded_by_correction_id FROM review_log "
            "WHERE review_id = ?",
            (review_id,),
        ).fetchone()
        assert row[0] is None
    finally:
        conn.close()
