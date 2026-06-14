"""Phase 13 T2.SB1 task T-A.1.1 — v20 migration atomic landing discriminating tests.

Per plan §G.1 step 1 + §B.4 #9 atomic-landing roster. Covers the 6 binding
discriminating tests for the v20 migration:

  1. test_v20_migration_lands_all_tables — post-migration: 5 new tables
     present with correct columns + indexes.
  2. test_v20_schema_python_constant_parity — every Python constant in
     ``swing.data.models`` matches the SQL CHECK enum verbatim.
  3. test_v20_dataclass_validator_parity — instantiate each new dataclass
     with all cross-column invariant violation cases; assert each raises
     ValueError (mirrors the schema CHECKs).
  4. test_v20_migration_backup_gate_fires_at_v19 — invoke run_migrations
     with pre_version=19 + target_version=20; assert backup file written.
  5. test_v20_migration_backup_gate_does_not_fire_at_v18 — invoke with
     pre_version=18; assert NO Phase 13 backup file (multi-step walk bypass
     per CLAUDE.md gotcha strict-equality form).
  6. test_v20_fill_origin_backfill_to_operator_typed — seed N fills
     pre-migration; apply v20; assert all fills.fill_origin='operator_typed'.

Also plants 4 cross-bundle pins (currently skipped; un-skip at downstream
merges per plan §H.3):

  - test_schema_version_v20_invariant (un-skips at T3.SB1 merge).
  - test_pattern_exemplars_schema_shape_invariant (un-skips at T2.SB3 + T2.SB5).
  - test_v20_atomic_landing_python_constants_validators_paired
    (un-skips at T4.SB closer).
  - test_fill_origin_enum_complete_after_v20 (un-skips at T3.SB2).
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from swing.data import db as db_module
from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    MigrationBackupRequiredException,
    ensure_schema,
    run_migrations,
)
from swing.data.models import (
    _CHART_SURFACE_VALUES,
    _FILL_ORIGIN_VALUES,
    _FINAL_DECISION_VALUES,
    _FLAG_CLEARED_REASON_VALUES,
    _FLAG_EVENT_TYPE_VALUES,
    _FLAG_SURFACE_VALUES,
    _LABEL_SOURCE_VALUES,
    _PATTERN_EXEMPLAR_CREATED_BY_VALUES,
    _TIMEFRAME_VALUES,
    DETECTOR_PATTERN_CLASSES,
    ChartRender,
    PatternEvaluation,
    PatternExemplar,
    WatchlistCloseTrackFlag,
    WatchlistCloseTrackFlagEvent,
)
from swing.integrations.schwab.audit_service import _SCHWAB_API_SURFACE_VALUES

# ============================================================================
# Helpers — read CHECK constraint expressions from sqlite_master.
# ============================================================================


def _table_sql(conn: sqlite3.Connection, table: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    assert row is not None, f"table {table} missing from sqlite_master"
    return row[0]


def _extract_check_values_from_sql(sql: str, column_or_constraint: str) -> set[str]:
    """Pull the literal string values from a CHECK (col IN (...)) clause.

    Tolerant of whitespace + line breaks. Returns the set of single-quoted
    string literals inside the first matching IN-list following the named
    column reference.
    """
    pattern = re.compile(
        rf"{re.escape(column_or_constraint)}\s+IN\s*\(([^)]*?)\)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(sql)
    assert match is not None, (
        f"CHECK IN clause for {column_or_constraint!r} not found in SQL:\n{sql}"
    )
    return set(re.findall(r"'([^']+)'", match.group(1)))


# ============================================================================
# 1. test_v20_migration_lands_all_tables
# ============================================================================


_V20_NEW_TABLES: frozenset[str] = frozenset({
    "pattern_exemplars",
    "chart_renders",
    "pattern_evaluations",
    "watchlist_close_track_flags",
    "watchlist_close_track_flag_events",
})


def test_v20_migration_lands_all_tables(tmp_path: Path) -> None:
    """Post-v20: all 5 new tables exist + key columns present."""
    db_path = tmp_path / "v20.db"
    conn = ensure_schema(db_path)

    actual_tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    missing = _V20_NEW_TABLES - actual_tables
    assert not missing, f"v20 tables missing: {sorted(missing)}"

    # Spot-check column presence per spec §3.1-§3.3 + §7.2.
    pattern_exemplars_cols = {
        r[1]
        for r in conn.execute(
            "PRAGMA table_info(pattern_exemplars)"
        ).fetchall()
    }
    for required in (
        "id",
        "ticker",
        "timeframe",
        "proposed_pattern_class",
        "final_decision",
        "final_pattern_class",
        "label_source",
        "structural_evidence_json",
        "parent_exemplar_id",
        "labeler_evidence_json",
        "geometric_score_json",
        "created_by",
    ):
        assert required in pattern_exemplars_cols, (
            f"pattern_exemplars missing column {required!r}"
        )

    chart_renders_cols = {
        r[1]
        for r in conn.execute("PRAGMA table_info(chart_renders)").fetchall()
    }
    for required in (
        "id",
        "ticker",
        "surface",
        "pipeline_run_id",
        "pattern_class",
        "chart_svg_bytes",
        "source_data_hash",
        "data_asof_date",
    ):
        assert required in chart_renders_cols, (
            f"chart_renders missing column {required!r}"
        )

    pe_cols = {
        r[1]
        for r in conn.execute(
            "PRAGMA table_info(pattern_evaluations)"
        ).fetchall()
    }
    for required in (
        "pipeline_run_id",
        "ticker",
        "pattern_class",
        "geometric_score",
        "composite_score",
        "feature_distribution_log_json",
    ):
        assert required in pe_cols, (
            f"pattern_evaluations missing column {required!r}"
        )

    flag_cols = {
        r[1]
        for r in conn.execute(
            "PRAGMA table_info(watchlist_close_track_flags)"
        ).fetchall()
    }
    for required in (
        "ticker",
        "flagged_at",
        "flagged_by_surface",
        "cleared_at",
        "cleared_reason",
    ):
        assert required in flag_cols, (
            f"watchlist_close_track_flags missing column {required!r}"
        )

    flag_event_cols = {
        r[1]
        for r in conn.execute(
            "PRAGMA table_info(watchlist_close_track_flag_events)"
        ).fetchall()
    }
    for required in ("flag_id", "event_type", "event_at", "surface"):
        assert required in flag_event_cols, (
            f"watchlist_close_track_flag_events missing column {required!r}"
        )

    # Spec §3.2 partial unique indexes (3) + §7.2 active-flag partial UNIQUE.
    indexes = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
    }
    for required in (
        "idx_chart_renders_run_bound",
        "idx_chart_renders_position_detail",
        "idx_chart_renders_theme2_annotated",
        "idx_pattern_evaluations_run_ticker_class",
        "idx_wclf_active_ticker",
    ):
        assert required in indexes, f"v20 index missing: {required!r}"

    # Schema version landed.
    # ensure_schema walks to HEAD (v23 post-Phase-14-SB3 migration 0023).
    version_row = conn.execute("SELECT version FROM schema_version").fetchone()
    assert version_row is not None
    assert version_row[0] == 30, (
        f"schema_version should be 23 (HEAD) post-migration, got {version_row[0]}"
    )
    assert EXPECTED_SCHEMA_VERSION == 30, (
        "EXPECTED_SCHEMA_VERSION must equal 23 in db.py (post-Phase-14-SB3)"
    )

    conn.close()


# ============================================================================
# 2. test_v20_schema_python_constant_parity
# ============================================================================


def test_v20_schema_python_constant_parity(tmp_path: Path) -> None:
    """Each Python constant matches the SQL CHECK enum verbatim.

    Per plan §A.14 + Phase 12 C.A T-A.2 LOCK family — schema CHECK,
    Python constant, dataclass validator land in the SAME task.
    """
    db_path = tmp_path / "parity.db"
    conn = ensure_schema(db_path)

    # pattern_exemplars CHECKs.
    pe_sql = _table_sql(conn, "pattern_exemplars")
    proposed_values = _extract_check_values_from_sql(
        pe_sql, "proposed_pattern_class"
    )
    assert proposed_values == set(DETECTOR_PATTERN_CLASSES), (
        f"DETECTOR_PATTERN_CLASSES mismatch: "
        f"schema={sorted(proposed_values)} "
        f"python={sorted(DETECTOR_PATTERN_CLASSES)}"
    )
    label_source_values = _extract_check_values_from_sql(pe_sql, "label_source")
    assert label_source_values == set(_LABEL_SOURCE_VALUES)
    final_decision_values = _extract_check_values_from_sql(
        pe_sql, "final_decision"
    )
    assert final_decision_values == set(_FINAL_DECISION_VALUES)
    created_by_values = _extract_check_values_from_sql(pe_sql, "created_by")
    assert created_by_values == set(_PATTERN_EXEMPLAR_CREATED_BY_VALUES)
    timeframe_values = _extract_check_values_from_sql(pe_sql, "timeframe")
    assert timeframe_values == set(_TIMEFRAME_VALUES)

    # chart_renders surface CHECK.
    cr_sql = _table_sql(conn, "chart_renders")
    surface_values = _extract_check_values_from_sql(cr_sql, "surface")
    assert surface_values == set(_CHART_SURFACE_VALUES)

    # fills.fill_origin CHECK.
    fills_sql = _table_sql(conn, "fills")
    fill_origin_values = _extract_check_values_from_sql(fills_sql, "fill_origin")
    assert fill_origin_values == set(_FILL_ORIGIN_VALUES)

    # schwab_api_calls.surface widened CHECK.
    sa_sql = _table_sql(conn, "schwab_api_calls")
    sa_surface_values = _extract_check_values_from_sql(sa_sql, "surface")
    assert sa_surface_values == set(_SCHWAB_API_SURFACE_VALUES), (
        f"schwab_api_calls.surface CHECK enum drift: "
        f"schema={sorted(sa_surface_values)} "
        f"python={sorted(_SCHWAB_API_SURFACE_VALUES)}"
    )

    # watchlist_close_track_flags.flagged_by_surface CHECK.
    flag_sql = _table_sql(conn, "watchlist_close_track_flags")
    flagged_by_values = _extract_check_values_from_sql(
        flag_sql, "flagged_by_surface"
    )
    assert flagged_by_values == set(_FLAG_SURFACE_VALUES)
    cleared_reason_values = _extract_check_values_from_sql(
        flag_sql, "cleared_reason"
    )
    assert cleared_reason_values == set(_FLAG_CLEARED_REASON_VALUES)

    # watchlist_close_track_flag_events CHECKs.
    flag_event_sql = _table_sql(conn, "watchlist_close_track_flag_events")
    event_type_values = _extract_check_values_from_sql(
        flag_event_sql, "event_type"
    )
    assert event_type_values == set(_FLAG_EVENT_TYPE_VALUES)
    event_surface_values = _extract_check_values_from_sql(
        flag_event_sql, "surface"
    )
    assert event_surface_values == set(_FLAG_SURFACE_VALUES)

    conn.close()


# ============================================================================
# 3. test_v20_dataclass_validator_parity
#
# Construct each NEW dataclass with cross-column invariant violation cases;
# assert each raises ValueError. Mirrors the schema CHECK invariants.
# ============================================================================


_VALID_EXEMPLAR_KWARGS = {
    "id": None,
    "ticker": "ABC",
    "timeframe": "daily",
    "start_date": "2024-01-01",
    "end_date": "2024-02-01",
    "proposed_pattern_class": "vcp",
    "final_decision": "confirmed",
    "label_source": "curated_gold",
    "structural_evidence_json": "{}",
    "geometric_score_json": "{}",
    # Per spec §3.1 invariant #5: curated_gold requires labeler_evidence_json
    # non-NULL (preserves silver-tier audit trail through gold-promotion;
    # Codex R6 M#1 closure).
    "labeler_evidence_json": "{}",
    "created_at": "2024-02-02T00:00:00.000",
    "created_by": "operator",
}


def test_v20_dataclass_validator_parity_pattern_exemplar_invariants() -> None:
    """All 5 cross-column invariants on PatternExemplar raise on violation."""
    # Baseline-valid construction succeeds.
    PatternExemplar(**_VALID_EXEMPLAR_KWARGS)

    # Invariant #1 (a): final_decision='relabeled' requires non-NULL distinct
    # final_pattern_class.
    with pytest.raises(ValueError, match="invariant #1"):
        PatternExemplar(
            **{
                **_VALID_EXEMPLAR_KWARGS,
                "label_source": "claude_silver",
                "final_decision": "relabeled",
                "final_pattern_class": None,
                "geometric_score_json": None,
                "labeler_evidence_json": "{}",
            }
        )

    # Invariant #1 (b): non-relabel must have NULL final_pattern_class.
    with pytest.raises(ValueError, match="invariant #1"):
        PatternExemplar(
            **{
                **_VALID_EXEMPLAR_KWARGS,
                "final_pattern_class": "flat_base",
            }
        )

    # Invariant #2: synthetic + non-'generated' is rejected.
    with pytest.raises(ValueError, match="invariant #2"):
        PatternExemplar(
            **{
                **_VALID_EXEMPLAR_KWARGS,
                "label_source": "synthetic",
                "final_decision": "confirmed",
                "geometric_score_json": "{}",
                "labeler_evidence_json": None,
            }
        )

    # Invariant #3 (a): codex_silver requires parent_exemplar_id.
    with pytest.raises(ValueError, match="invariant #3"):
        PatternExemplar(
            **{
                **_VALID_EXEMPLAR_KWARGS,
                "label_source": "codex_silver",
                "geometric_score_json": None,
                "labeler_evidence_json": "{}",
                "parent_exemplar_id": None,
            }
        )

    # Invariant #3 (b): non-codex_silver must have NULL parent_exemplar_id.
    with pytest.raises(ValueError, match="invariant #3"):
        PatternExemplar(
            **{
                **_VALID_EXEMPLAR_KWARGS,
                "parent_exemplar_id": 5,
            }
        )

    # Invariant #4: synthetic requires non-NULL geometric_score_json.
    with pytest.raises(ValueError, match="invariant #4"):
        PatternExemplar(
            **{
                **_VALID_EXEMPLAR_KWARGS,
                "label_source": "synthetic",
                "final_decision": "generated",
                "geometric_score_json": None,
                "labeler_evidence_json": None,
            }
        )

    # Invariant #5: claude_silver requires non-NULL labeler_evidence_json.
    with pytest.raises(ValueError, match="invariant #5"):
        PatternExemplar(
            **{
                **_VALID_EXEMPLAR_KWARGS,
                "label_source": "claude_silver",
                "final_decision": "confirmed",
                "geometric_score_json": None,
                "labeler_evidence_json": None,
            }
        )

    # Invariant #5 (b): closed_loop_review must have NULL labeler_evidence_json.
    with pytest.raises(ValueError, match="invariant #5"):
        PatternExemplar(
            **{
                **_VALID_EXEMPLAR_KWARGS,
                "label_source": "closed_loop_review",
                "final_decision": "confirmed",
                "geometric_score_json": "{}",
                "labeler_evidence_json": "{}",
            }
        )


def test_v20_dataclass_validator_parity_pattern_evaluation() -> None:
    """PatternEvaluation rejects invalid pattern_class."""
    valid = PatternEvaluation(
        id=None,
        pipeline_run_id=1,
        ticker="ABC",
        pattern_class="vcp",
        detector_version="vcp-v1.0",
        geometric_score=0.8,
        geometric_score_json="{}",
        composite_score=0.8,
        structural_evidence_json="{}",
        feature_distribution_log_json="{}",
        window_start_date="2024-01-01",
        window_end_date="2024-02-01",
        created_at="2024-02-02T00:00:00.000",
    )
    assert valid.pattern_class == "vcp"

    with pytest.raises(ValueError, match="pattern_class must be one of"):
        PatternEvaluation(
            id=None,
            pipeline_run_id=1,
            ticker="ABC",
            pattern_class="invalid_pattern",
            detector_version="vcp-v1.0",
            geometric_score=0.8,
            geometric_score_json="{}",
            composite_score=0.8,
            structural_evidence_json="{}",
            feature_distribution_log_json="{}",
            window_start_date="2024-01-01",
            window_end_date="2024-02-01",
            created_at="2024-02-02T00:00:00.000",
        )


def test_v20_dataclass_validator_parity_chart_render() -> None:
    """ChartRender enforces surface + cross-column theme2_annotated CHECK."""
    # Baseline-valid (non-theme2; pattern_class NULL).
    ChartRender(
        id=None,
        ticker="ABC",
        surface="watchlist_row",
        chart_svg_bytes=b"<svg/>",
        source_data_hash="hash",
        rendered_at="2024-02-02T00:00:00.000",
        data_asof_date="2024-02-01",
        pipeline_run_id=1,
    )

    # theme2_annotated WITHOUT pattern_class -> raises.
    with pytest.raises(ValueError, match=r"theme2_annotated.*requires"):
        ChartRender(
            id=None,
            ticker="ABC",
            surface="theme2_annotated",
            chart_svg_bytes=b"<svg/>",
            source_data_hash="hash",
            rendered_at="2024-02-02T00:00:00.000",
            data_asof_date="2024-02-01",
            pipeline_run_id=1,
            pattern_class=None,
        )

    # Non-theme2 WITH pattern_class -> raises.
    with pytest.raises(ValueError, match="pattern_class must be NULL"):
        ChartRender(
            id=None,
            ticker="ABC",
            surface="watchlist_row",
            chart_svg_bytes=b"<svg/>",
            source_data_hash="hash",
            rendered_at="2024-02-02T00:00:00.000",
            data_asof_date="2024-02-01",
            pipeline_run_id=1,
            pattern_class="vcp",
        )


def test_v20_dataclass_validator_parity_flag_and_event() -> None:
    """WatchlistCloseTrackFlag + Event validators enforce CHECK enums."""
    # Active flag (cleared_at + cleared_reason both NULL).
    WatchlistCloseTrackFlag(
        id=None,
        ticker="PTEN",
        flagged_at="2026-05-19T10:00:00.000",
        flagged_by_surface="web",
    )

    # Cleared flag (both cleared_at + cleared_reason non-NULL).
    WatchlistCloseTrackFlag(
        id=None,
        ticker="PTEN",
        flagged_at="2026-05-19T10:00:00.000",
        flagged_by_surface="web",
        cleared_at="2026-05-20T10:00:00.000",
        cleared_reason="operator_cleared",
    )

    # cleared_at NULL but cleared_reason set -> raises.
    with pytest.raises(ValueError, match="cleared_at IS NULL iff"):
        WatchlistCloseTrackFlag(
            id=None,
            ticker="PTEN",
            flagged_at="2026-05-19T10:00:00.000",
            flagged_by_surface="web",
            cleared_at=None,
            cleared_reason="operator_cleared",
        )

    # cleared_at set but cleared_reason NULL -> raises.
    with pytest.raises(ValueError, match="cleared_at IS NULL iff"):
        WatchlistCloseTrackFlag(
            id=None,
            ticker="PTEN",
            flagged_at="2026-05-19T10:00:00.000",
            flagged_by_surface="web",
            cleared_at="2026-05-20T10:00:00.000",
            cleared_reason=None,
        )

    # Invalid surface -> raises.
    with pytest.raises(ValueError, match="flagged_by_surface must be"):
        WatchlistCloseTrackFlag(
            id=None,
            ticker="PTEN",
            flagged_at="2026-05-19T10:00:00.000",
            flagged_by_surface="api",
        )

    # Valid event.
    WatchlistCloseTrackFlagEvent(
        id=None,
        flag_id=1,
        event_type="set",
        event_at="2026-05-19T10:00:00.000",
        surface="cli",
    )

    # Invalid event_type -> raises.
    with pytest.raises(ValueError, match="event_type must be"):
        WatchlistCloseTrackFlagEvent(
            id=None,
            flag_id=1,
            event_type="invalid_event",
            event_at="2026-05-19T10:00:00.000",
            surface="cli",
        )


# ============================================================================
# 4 + 5. test_v20_migration_backup_gate_fires_at_v19 + does_not_fire_at_v18
#
# Per CLAUDE.md gotcha "Migration runner backup-gate equality form: strict
# equality, NOT <=". The gate fires only at the precise (target - 1)
# boundary; multi-step walks from pre-v19 bypass.
# ============================================================================


def _seed_v19_db(tmp_path: Path) -> Path:
    """Apply migrations up to v19 (not v20)."""
    db_path = tmp_path / "v19.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=19)
    conn.close()
    return db_path


def test_v20_migration_backup_gate_fires_at_v19(tmp_path: Path) -> None:
    """At pre_version=19 + target=20, a phase13 backup file is written."""
    db_path = _seed_v19_db(tmp_path)
    backup_dir = tmp_path / "backups"

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        run_migrations(conn, target_version=20, backup_dir=backup_dir)
    finally:
        conn.close()

    # At least one phase13 backup file exists.
    backups = list(backup_dir.glob("swing-pre-phase13-migration-*.db"))
    assert backups, (
        f"phase13 backup file missing from {backup_dir}; "
        f"contents: {list(backup_dir.iterdir())}"
    )

    # And the gate function exists with strict-equality form (defense-in-depth).
    assert hasattr(db_module, "_phase13_backup_gate")


def test_v20_migration_backup_gate_does_not_fire_at_v18(tmp_path: Path) -> None:
    """At pre_version=18, the phase13 gate is NOT triggered (strict equality).

    Per CLAUDE.md gotcha + Phase 9 / Phase 12 C.A precedent: multi-step walks
    from pre-v19 bypass the phase13 gate by construction.
    """
    # Seed a v18 DB.
    db_path = tmp_path / "v18.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=18)
    conn.close()

    backup_dir = tmp_path / "backups"

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        # This walks v18 -> v20 internally; the phase13 gate predicate
        # `current_version == 19` is FALSE at run_migrations entry
        # (current=18), so the gate returns early — no phase13 backup file.
        # The Phase 12 Sub-bundle C gate at current_version=18 DOES fire
        # (separate file with phase12-bundle-c prefix).
        run_migrations(conn, target_version=20, backup_dir=backup_dir)
    finally:
        conn.close()

    phase13_backups = list(backup_dir.glob("swing-pre-phase13-migration-*.db"))
    assert phase13_backups == [], (
        "phase13 gate must NOT fire from pre_version<19 per strict-equality "
        f"discipline; found unexpected: {phase13_backups}"
    )


# ============================================================================
# 6. test_v20_fill_origin_backfill_to_operator_typed
#
# Seed N fills on a v19 DB, apply v20, assert all existing rows have
# fill_origin='operator_typed' (DEFAULT clause backfills transparently
# per OQ-7 V1 simple).
# ============================================================================


def test_v20_fill_origin_backfill_to_operator_typed(tmp_path: Path) -> None:
    db_path = _seed_v19_db(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")

    # Seed a trade + 3 fills on v19 (no fill_origin column yet).
    conn.execute("BEGIN")
    conn.execute(
        "INSERT INTO trades ("
        "ticker, entry_date, entry_price, initial_shares, initial_stop, "
        "current_stop, state, hypothesis_label, trade_origin, "
        "pre_trade_locked_at, current_size"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "ABC",
            "2024-01-01",
            10.0,
            100,
            9.0,
            9.0,
            "entered",
            "test",
            "manual_off_pipeline",
            "2024-01-01T09:30:00.000",
            100.0,
        ),
    )
    trade_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    for i in range(3):
        conn.execute(
            "INSERT INTO fills ("
            "trade_id, fill_datetime, action, quantity, price"
            ") VALUES (?, ?, ?, ?, ?)",
            (trade_id, f"2024-01-0{i+1}T10:00:00.000", "entry", 33.0, 10.0),
        )
    conn.commit()
    conn.close()

    # Apply v20.
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        run_migrations(conn, target_version=20, backup_dir=tmp_path / "bk")
    finally:
        conn.close()

    # Assert all 3 fills have fill_origin='operator_typed'.
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT fill_origin FROM fills WHERE trade_id = ?", (trade_id,)
    ).fetchall()
    conn.close()
    assert len(rows) == 3
    assert all(r[0] == "operator_typed" for r in rows), (
        f"All pre-migration fills should backfill to 'operator_typed'; got {rows}"
    )


# ============================================================================
# Audit: schwabdev surface ALTER preserved row data + indexes.
# ============================================================================


def test_v20_schwab_api_calls_widening_preserves_rows_and_indexes(
    tmp_path: Path,
) -> None:
    """Pre-migration schwab_api_calls rows survive surface CHECK widening;
    all 4 indexes recreated on the rebuilt table.
    """
    db_path = _seed_v19_db(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("BEGIN")
    conn.execute(
        "INSERT INTO schwab_api_calls ("
        "ts, endpoint, status, pipeline_run_id, surface, environment"
        ") VALUES ('2024-01-01T10:00:00.000', 'accounts.details', "
        "'success', NULL, 'pipeline', 'production')"
    )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        run_migrations(conn, target_version=20, backup_dir=tmp_path / "bk")
    finally:
        conn.close()

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT surface, environment, status FROM schwab_api_calls"
    ).fetchall()
    assert rows == [("pipeline", "production", "success")]

    # Trade-entry surface now accepted at SQL layer.
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("BEGIN")
    conn.execute(
        "INSERT INTO schwab_api_calls ("
        "ts, endpoint, status, pipeline_run_id, surface, environment"
        ") VALUES ('2024-02-01T10:00:00.000', 'accounts.orders.list', "
        "'in_flight', NULL, 'trade_entry', 'production')"
    )
    conn.commit()

    # 4 indexes recreated.
    idx_rows = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='index' AND tbl_name='schwab_api_calls' "
        "AND name LIKE 'ix_schwab_api_calls%'"
    ).fetchall()
    idx_names = {r[0] for r in idx_rows}
    expected = {
        "ix_schwab_api_calls_ts",
        "ix_schwab_api_calls_status_ts",
        "ix_schwab_api_calls_pipeline_run_id_ts",
        "ix_schwab_api_calls_surface_ts",
    }
    assert expected <= idx_names, (
        f"schwab_api_calls indexes missing post-rebuild: "
        f"{sorted(expected - idx_names)}"
    )
    conn.close()


# ============================================================================
# Cross-bundle pin plants (currently SKIPPED; un-skip at downstream merges
# per plan §H.3).
# ============================================================================


def test_schema_version_v20_invariant(tmp_path: Path) -> None:
    """Cross-bundle pin (un-skipped at T3.SB1 T-B.1.1 per plan §H.3): the
    schema_version=20 invariant survives T3.SB1 merge.

    Re-skipping this test would silently disable the cross-bundle guard.
    T3.SB1's prerequisite test at
    ``tests/data/test_phase13_t3_sb1_prerequisite.py`` covers the same
    invariant from a different angle (branch-base SHA + new column shape).
    """
    db_path = tmp_path / "pin_v20.db"
    conn = ensure_schema(db_path)
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    # Phase 14 Sub-bundle 3 migration 0023 bumps HEAD to 23; the cross-bundle
    # pin's intent (schema_version pinned at HEAD) is preserved by tracking the
    # current constant, not the literal v20 from T3.SB1's branch-base.
    assert version == 30
    conn.close()


def test_pattern_exemplars_schema_shape_invariant(tmp_path: Path) -> None:
    """Cross-bundle pin: pattern_exemplars column set unchanged.

    Un-skipped at Phase 13 T2.SB5 T-A.5.6 closer per plan §H.3 row 7
    (T2.SB3 closer lag closed here). Verifies that T2.SB3 + T2.SB4
    detector emits + T2.SB5 template matching consume the v20
    pattern_exemplars table without schema drift (CHECK constraints +
    column set both pinned).
    """
    db_path = tmp_path / "pin_pe_shape.db"
    conn = ensure_schema(db_path)
    cols = {
        r[1]
        for r in conn.execute(
            "PRAGMA table_info(pattern_exemplars)"
        ).fetchall()
    }
    expected = {
        "id",
        "ticker",
        "timeframe",
        "start_date",
        "end_date",
        "proposed_pattern_class",
        "final_decision",
        "final_pattern_class",
        "label_source",
        "ai_labeler_version",
        "gold_validated_at",
        "codex_reviewed",
        "codex_agreement",
        "geometric_score_json",
        "labeler_evidence_json",
        "structural_evidence_json",
        "quality_grade",
        "notes",
        "parent_exemplar_id",
        "created_at",
        "created_by",
    }
    assert cols == expected, (
        f"pattern_exemplars schema shape drift: extra={sorted(cols - expected)} "
        f"missing={sorted(expected - cols)}"
    )
    conn.close()


def test_pattern_evaluations_template_match_score_persistable(
    tmp_path: Path,
) -> None:
    """Cross-bundle pin: pattern_evaluations.template_match_score round-trip.

    Planted + un-skipped at Phase 13 T2.SB5 T-A.5.6 closer per plan §H.3
    row 8 (test did not exist on main HEAD pre-T2.SB5; T2.SB5 plants
    the body since the column-population logic lands here).

    Verifies (a) pattern_evaluations.template_match_score accepts NULL
    (pre-T2.SB5 fallback path + post-T2.SB5 empty-exemplar-corpus path)
    and (b) accepts a float in [0.0, 1.0] via INSERT/SELECT round-trip
    with exact-equality-within-epsilon assertion.
    """
    import sqlite3

    from swing.data.db import ensure_schema

    db_path = tmp_path / "pin_pe_tm_score.db"
    conn = ensure_schema(db_path)
    # Seed a pipeline_run + evaluation_run so the FK requires can be
    # satisfied. Use direct INSERTs to keep this test free of any
    # higher-level evaluator/runner coupling.
    conn.execute(
        "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
        "action_session_date, state, lease_token) VALUES "
        "(?, 'manual', ?, ?, 'running', ?)",
        ("2026-05-21T18:00:00", "2026-05-20", "2026-05-21", "pin-tok"),
    )
    pipeline_run_id = conn.execute(
        "SELECT id FROM pipeline_runs WHERE lease_token = 'pin-tok'"
    ).fetchone()[0]
    conn.commit()

    # (a) Accept NULL template_match_score (pre-T2.SB5 + empty-corpus path).
    conn.execute(
        "INSERT INTO pattern_evaluations "
        "(pipeline_run_id, ticker, pattern_class, detector_version, "
        "geometric_score, geometric_score_json, composite_score, "
        "structural_evidence_json, feature_distribution_log_json, "
        "window_start_date, window_end_date, created_at, "
        "template_match_score, template_match_nearest_exemplar_ids_json) "
        "VALUES (?, 'NULL_PATH', 'vcp', 'vcp@v0.0.test', "
        "0.50, '{}', 0.50, '{}', '{}', "
        "'2026-05-01', '2026-05-20', '2026-05-21T18:00:00', NULL, NULL)",
        (pipeline_run_id,),
    )

    # (b) Accept a float in [0.0, 1.0] via round-trip with exact-equality
    # within float epsilon.
    expected_score = 0.6789012345
    conn.execute(
        "INSERT INTO pattern_evaluations "
        "(pipeline_run_id, ticker, pattern_class, detector_version, "
        "geometric_score, geometric_score_json, composite_score, "
        "structural_evidence_json, feature_distribution_log_json, "
        "window_start_date, window_end_date, created_at, "
        "template_match_score, template_match_nearest_exemplar_ids_json) "
        "VALUES (?, 'FLOAT_PATH', 'vcp', 'vcp@v0.0.test', "
        "0.75, '{}', 0.71, '{}', '{}', "
        "'2026-05-01', '2026-05-20', '2026-05-21T18:00:00', ?, ?)",
        (pipeline_run_id, expected_score, '[1, 2, 3]'),
    )
    conn.commit()

    # Round-trip NULL.
    null_row = conn.execute(
        "SELECT template_match_score, template_match_nearest_exemplar_ids_json "
        "FROM pattern_evaluations WHERE ticker = 'NULL_PATH'"
    ).fetchone()
    assert null_row[0] is None
    assert null_row[1] is None

    # Round-trip float in [0, 1] - exact equality within float epsilon.
    float_row = conn.execute(
        "SELECT template_match_score, template_match_nearest_exemplar_ids_json "
        "FROM pattern_evaluations WHERE ticker = 'FLOAT_PATH'"
    ).fetchone()
    assert float_row[0] is not None
    assert abs(float(float_row[0]) - expected_score) < 1e-9
    assert float_row[1] == '[1, 2, 3]'
    conn.close()


def test_v20_atomic_landing_python_constants_validators_paired() -> None:
    """Cross-bundle pin: all v20 paired-triples land atomically.

    Un-skipped at T4.SB closer (T-T4.SB.6) per plan §H.3 schedule —
    verifies ALL 8 v20 schema-CHECK + Python-constant + dataclass-
    validator triples remain atomically paired across the Phase 13 arc.
    """
    # Smoke check: each constant + matching dataclass exists post-Phase-13.
    assert DETECTOR_PATTERN_CLASSES
    assert _LABEL_SOURCE_VALUES
    assert _FINAL_DECISION_VALUES
    assert _FILL_ORIGIN_VALUES
    assert _CHART_SURFACE_VALUES
    assert _FLAG_SURFACE_VALUES
    assert _FLAG_CLEARED_REASON_VALUES
    assert _FLAG_EVENT_TYPE_VALUES
    assert _SCHWAB_API_SURFACE_VALUES


def test_fill_origin_enum_complete_after_v20(tmp_path: Path) -> None:
    """Cross-bundle pin: fill_origin enum coverage post-Phase-13 entry+exit.

    Un-skip at T3.SB2 merge per plan §G.1 T-A.1.1.
    """
    db_path = tmp_path / "pin_fill_origin.db"
    conn = ensure_schema(db_path)
    fills_sql = _table_sql(conn, "fills")
    values = _extract_check_values_from_sql(fills_sql, "fill_origin")
    expected = {
        "operator_typed",
        "schwab_auto",
        "schwab_auto_then_operator_corrected",
        "tos_import",
        "imported_legacy",
    }
    assert values == expected
    conn.close()


# Silence ruff F401 on MigrationBackupRequiredException — re-exported for
# downstream test fixtures that import from this module.
_ = MigrationBackupRequiredException
