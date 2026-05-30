"""Phase 13 T2.SB6c task T-A.6c.1 — v21 migration atomic landing discriminating tests.

Per plan §G.1 step 1a-1c + brainstorm spec §2.1 / §2.2 / §B.5 enumerations.

Covers 21 discriminating tests:

  Delta A (8): trades.candidate_id INTEGER NULL + FK candidates(id) ON DELETE
  SET NULL + idx_trades_candidate_id + paired __dataclass + __row_to_trade +
  __INSERT-SVAI surfaces.

  Delta B (9): trades.pattern_evaluation_id INTEGER NULL + FK
  pattern_evaluations(id) ON DELETE SET NULL + idx_trades_pattern_evaluation_id
  + paired surfaces. The extra test is the direct-row-delete FK cascade test
  per Codex R1 MAJOR #4 (vs chained cascade through pipeline_runs which is
  blocked by trades.chart_pattern_classification_pipeline_run_id FK NO ACTION).

  Backup-gate (4): SB6c backup file written at pre==20+target>=21; strict
  equality at pre==19 + multi-step v19->v21 bypasses SB6c gate;
  EXPECTED_SCHEMA_VERSION constant == 21.

§A.14 paired-discipline LOCK: schema + dataclass + read-path mapper +
write-path INSERT extension + ALL tests land in ONE commit.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data import db as db_module
from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    ensure_schema,
    run_migrations,
)
from swing.data.models import Trade
from swing.data.repos.trades import (
    _TRADE_SELECT_COLS,
    _row_to_trade,
    get_trade,
    insert_trade_with_event,
)

# ============================================================================
# Helpers
# ============================================================================


def _seed_v20_db(tmp_path: Path) -> Path:
    """Apply migrations up to v20 (NOT v21) for SVAI legacy-branch tests."""
    db_path = tmp_path / "v20.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=20)
    conn.close()
    return db_path


def _v21_conn(tmp_path: Path) -> sqlite3.Connection:
    """Apply migrations through v21 (the new target)."""
    db_path = tmp_path / "v21.db"
    conn = ensure_schema(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _seed_candidate_and_pattern_evaluation(
    conn: sqlite3.Connection,
) -> tuple[int, int, int, int]:
    """Seed minimal rows so we can FK-link a trade.

    Returns (evaluation_run_id, pipeline_run_id, candidate_id,
    pattern_evaluation_id).
    """
    cur = conn.execute(
        """
        INSERT INTO evaluation_runs (
            run_ts, data_asof_date, action_session_date,
            tickers_evaluated, aplus_count, watch_count, skip_count,
            excluded_count, error_count
        ) VALUES (?, ?, ?, 0, 0, 0, 0, 0, 0)
        """,
        ("2026-05-22T12:00:00.000", "2026-05-22", "2026-05-22"),
    )
    evaluation_run_id = int(cur.lastrowid)

    cur = conn.execute(
        """
        INSERT INTO pipeline_runs (
            started_ts, finished_ts, trigger, data_asof_date,
            action_session_date, state, lease_token, evaluation_run_id
        ) VALUES (?, ?, 'manual', ?, ?, 'complete', ?, ?)
        """,
        (
            "2026-05-22T12:00:00.000",
            "2026-05-22T12:05:00.000",
            "2026-05-22",
            "2026-05-22",
            "tok-1",
            evaluation_run_id,
        ),
    )
    pipeline_run_id = int(cur.lastrowid)

    cur = conn.execute(
        """
        INSERT INTO candidates (evaluation_run_id, ticker, bucket, rs_method)
        VALUES (?, 'ABC', 'aplus', 'unavailable')
        """,
        (evaluation_run_id,),
    )
    candidate_id = int(cur.lastrowid)

    cur = conn.execute(
        """
        INSERT INTO pattern_evaluations (
            pipeline_run_id, ticker, pattern_class, detector_version,
            geometric_score, geometric_score_json, composite_score,
            structural_evidence_json, feature_distribution_log_json,
            window_start_date, window_end_date, created_at
        ) VALUES (?, 'ABC', 'vcp', 'vcp-v1.0', 0.8, '{}', 0.8, '{}', '{}',
                  '2026-05-01', '2026-05-22', '2026-05-22T12:00:00.000')
        """,
        (pipeline_run_id,),
    )
    pattern_evaluation_id = int(cur.lastrowid)
    conn.commit()
    return evaluation_run_id, pipeline_run_id, candidate_id, pattern_evaluation_id


def _make_trade(
    *, candidate_id: int | None = None, pattern_evaluation_id: int | None = None,
) -> Trade:
    return Trade(
        id=None,
        ticker="ABC",
        entry_date="2026-05-22",
        entry_price=100.0,
        initial_shares=10,
        initial_stop=95.0,
        current_stop=95.0,
        state="entered",
        watchlist_entry_target=None,
        watchlist_initial_stop=None,
        notes=None,
        trade_origin="pipeline_aplus",
        pre_trade_locked_at="2026-05-22T12:00:00.000",
        current_size=10.0,
        candidate_id=candidate_id,
        pattern_evaluation_id=pattern_evaluation_id,
    )


# ============================================================================
# Step 1a — Delta A (8 tests)
# ============================================================================


def test_v21_migration_adds_candidate_id_column_at_position_52(
    tmp_path: Path,
) -> None:
    """Delta A - row[52] locked per OQ-9 (SELECT-projected via _TRADE_SELECT_COLS).

    The OQ-9 LOCK speaks to the ``_row_to_trade`` row-index position (the
    SELECT-projected order via ``_TRADE_SELECT_COLS``), NOT the underlying
    ``PRAGMA table_info`` cid (which is influenced by independent migrations
    like 0017 ``risk_policy_id_at_lock``).
    """
    conn = _v21_conn(tmp_path)
    try:
        # Column exists in trades + is INTEGER + nullable (cid-agnostic).
        cols = conn.execute("PRAGMA table_info(trades)").fetchall()
        by_name = {c[1]: c for c in cols}
        assert "candidate_id" in by_name, (
            "candidate_id not in trades cols post-v21"
        )
        assert by_name["candidate_id"][2].upper() == "INTEGER"
        assert by_name["candidate_id"][3] == 0  # nullable

        # Row-projection position: candidate_id is at row[52] of the
        # _TRADE_SELECT_COLS-projected SELECT, between planned_target_R (51)
        # and pattern_evaluation_id (53).
        select_col_names = [
            c.strip() for c in _TRADE_SELECT_COLS.replace("\n", " ").split(",")
            if c.strip()
        ]
        # Defensive split: any trailing comma-less last token gets caught.
        assert "candidate_id" in select_col_names
        assert select_col_names.index("candidate_id") == 52, (
            "candidate_id row-projection position drift: "
            f"got {select_col_names.index('candidate_id')} != 52 "
            f"(full list: {select_col_names})"
        )
    finally:
        conn.close()


def test_v21_migration_adds_fk_to_candidates_id_on_delete_set_null(
    tmp_path: Path,
) -> None:
    """Delta A - FK with ON DELETE SET NULL targets candidates(id)."""
    conn = _v21_conn(tmp_path)
    try:
        fks = conn.execute("PRAGMA foreign_key_list(trades)").fetchall()
        # PRAGMA foreign_key_list row: (id, seq, table, from, to, on_update,
        # on_delete, match)
        matches = [
            fk for fk in fks
            if fk[2] == "candidates" and fk[3] == "candidate_id" and fk[4] == "id"
        ]
        assert matches, (
            "FK candidates(id) not found for trades.candidate_id"
        )
        assert matches[0][6] == "SET NULL", (
            f"on_delete must be SET NULL, got {matches[0][6]!r}"
        )
    finally:
        conn.close()


def test_v21_migration_creates_idx_trades_candidate_id(
    tmp_path: Path,
) -> None:
    """Delta A - index idx_trades_candidate_id exists in sqlite_master."""
    conn = _v21_conn(tmp_path)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
            ("idx_trades_candidate_id",),
        ).fetchone()
        assert row is not None, "idx_trades_candidate_id not found"
    finally:
        conn.close()


def test_v21_migration_backfills_existing_trades_with_null_candidate_id(
    tmp_path: Path,
) -> None:
    """Delta A - pre-v21 existing trade rows backfill to NULL candidate_id (OQ-1)."""
    # Seed a v20 DB + plant a trade.
    db_path = _seed_v20_db(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        conn.execute(
            """
            INSERT INTO trades (ticker, entry_date, entry_price, initial_shares,
                                initial_stop, current_stop, state,
                                trade_origin, pre_trade_locked_at, current_size)
            VALUES ('XYZ', '2026-05-01', 50.0, 5, 45.0, 45.0, 'entered',
                    'manual_off_pipeline', '2026-05-01T12:00:00.000', 5.0)
            """
        )
        conn.commit()
        # Apply v21.
        run_migrations(conn, target_version=21)
        # candidate_id is NULL for the pre-existing row.
        row = conn.execute(
            "SELECT candidate_id FROM trades WHERE ticker='XYZ'"
        ).fetchone()
        assert row is not None
        assert row[0] is None, (
            f"expected NULL candidate_id for pre-v21 trade, got {row[0]!r}"
        )
    finally:
        conn.close()


def test_row_to_trade_populates_candidate_id_from_row_52(
    tmp_path: Path,
) -> None:
    """Delta A - _row_to_trade maps row[52] -> Trade.candidate_id."""
    conn = _v21_conn(tmp_path)
    try:
        _, _, candidate_id, _ = _seed_candidate_and_pattern_evaluation(conn)
        trade = _make_trade(candidate_id=candidate_id)
        with conn:
            tid = insert_trade_with_event(
                conn, trade,
                event_ts="2026-05-22T12:30:00.000",
            )
        # Read back via canonical path.
        fetched = get_trade(conn, tid)
        assert fetched is not None
        assert fetched.candidate_id == candidate_id
    finally:
        conn.close()


def test_row_to_trade_populates_candidate_id_None_when_null_column(  # noqa: N802
    tmp_path: Path,
) -> None:
    """Delta A - _row_to_trade returns candidate_id=None when SQL column NULL."""
    conn = _v21_conn(tmp_path)
    try:
        trade = _make_trade(candidate_id=None)
        with conn:
            tid = insert_trade_with_event(
                conn, trade,
                event_ts="2026-05-22T12:30:00.000",
            )
        fetched = get_trade(conn, tid)
        assert fetched is not None
        assert fetched.candidate_id is None
    finally:
        conn.close()


def test_insert_trade_with_candidate_id_persists_via_schema_aware_path(
    tmp_path: Path,
) -> None:
    """Delta A - schema-aware INSERT path persists candidate_id at v21+."""
    conn = _v21_conn(tmp_path)
    try:
        _, _, candidate_id, _ = _seed_candidate_and_pattern_evaluation(conn)
        trade = _make_trade(candidate_id=candidate_id)
        with conn:
            tid = insert_trade_with_event(
                conn, trade,
                event_ts="2026-05-22T12:30:00.000",
            )
        row = conn.execute(
            "SELECT candidate_id FROM trades WHERE id=?", (tid,),
        ).fetchone()
        assert row[0] == candidate_id
    finally:
        conn.close()


def test_fk_cascade_on_candidates_delete_sets_trade_candidate_id_null(
    tmp_path: Path,
) -> None:
    """Delta A - FK ON DELETE SET NULL: deleting candidate nulls trade backlink."""
    conn = _v21_conn(tmp_path)
    try:
        _, _, candidate_id, _ = _seed_candidate_and_pattern_evaluation(conn)
        trade = _make_trade(candidate_id=candidate_id)
        with conn:
            tid = insert_trade_with_event(
                conn, trade,
                event_ts="2026-05-22T12:30:00.000",
            )
        # Drop the candidate row.
        conn.execute("DELETE FROM candidates WHERE id=?", (candidate_id,))
        conn.commit()
        # Trade survives; candidate_id is now NULL.
        row = conn.execute(
            "SELECT id, candidate_id FROM trades WHERE id=?", (tid,),
        ).fetchone()
        assert row is not None, "trade was unexpectedly cascade-deleted"
        assert row[1] is None, (
            f"candidate_id should SET NULL on candidate delete, got {row[1]!r}"
        )
    finally:
        conn.close()


# ============================================================================
# Step 1b — Delta B (9 tests)
# ============================================================================


def test_v21_migration_adds_pattern_evaluation_id_column_at_position_53(
    tmp_path: Path,
) -> None:
    """Delta B - row[53] locked per OQ-9 (SELECT-projected via _TRADE_SELECT_COLS).

    Like Delta A, OQ-9 LOCK refers to ``_row_to_trade`` row index, NOT the
    underlying ``PRAGMA table_info`` cid.
    """
    conn = _v21_conn(tmp_path)
    try:
        cols = conn.execute("PRAGMA table_info(trades)").fetchall()
        by_name = {c[1]: c for c in cols}
        assert "pattern_evaluation_id" in by_name
        assert by_name["pattern_evaluation_id"][2].upper() == "INTEGER"
        assert by_name["pattern_evaluation_id"][3] == 0  # nullable

        select_col_names = [
            c.strip() for c in _TRADE_SELECT_COLS.replace("\n", " ").split(",")
            if c.strip()
        ]
        assert "pattern_evaluation_id" in select_col_names
        assert select_col_names.index("pattern_evaluation_id") == 53, (
            "pattern_evaluation_id row-projection position drift: "
            f"got {select_col_names.index('pattern_evaluation_id')} != 53 "
            f"(full list: {select_col_names})"
        )
    finally:
        conn.close()


def test_v21_migration_adds_fk_to_pattern_evaluations_id_on_delete_set_null(
    tmp_path: Path,
) -> None:
    """Delta B - FK with ON DELETE SET NULL targets pattern_evaluations(id)."""
    conn = _v21_conn(tmp_path)
    try:
        fks = conn.execute("PRAGMA foreign_key_list(trades)").fetchall()
        matches = [
            fk for fk in fks
            if fk[2] == "pattern_evaluations"
            and fk[3] == "pattern_evaluation_id"
            and fk[4] == "id"
        ]
        assert matches, (
            "FK pattern_evaluations(id) not found for trades.pattern_evaluation_id"
        )
        assert matches[0][6] == "SET NULL", (
            f"on_delete must be SET NULL, got {matches[0][6]!r}"
        )
    finally:
        conn.close()


def test_v21_migration_creates_idx_trades_pattern_evaluation_id(
    tmp_path: Path,
) -> None:
    """Delta B - index idx_trades_pattern_evaluation_id exists."""
    conn = _v21_conn(tmp_path)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
            ("idx_trades_pattern_evaluation_id",),
        ).fetchone()
        assert row is not None, "idx_trades_pattern_evaluation_id not found"
    finally:
        conn.close()


def test_v21_migration_backfills_existing_trades_with_null_pattern_evaluation_id(
    tmp_path: Path,
) -> None:
    """Delta B - pre-v21 existing trade rows backfill to NULL pattern_evaluation_id."""
    db_path = _seed_v20_db(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        conn.execute(
            """
            INSERT INTO trades (ticker, entry_date, entry_price, initial_shares,
                                initial_stop, current_stop, state,
                                trade_origin, pre_trade_locked_at, current_size)
            VALUES ('PQR', '2026-05-01', 50.0, 5, 45.0, 45.0, 'entered',
                    'manual_off_pipeline', '2026-05-01T12:00:00.000', 5.0)
            """
        )
        conn.commit()
        run_migrations(conn, target_version=21)
        row = conn.execute(
            "SELECT pattern_evaluation_id FROM trades WHERE ticker='PQR'"
        ).fetchone()
        assert row is not None
        assert row[0] is None
    finally:
        conn.close()


def test_row_to_trade_populates_pattern_evaluation_id_from_row_53(
    tmp_path: Path,
) -> None:
    """Delta B - _row_to_trade maps row[53] -> Trade.pattern_evaluation_id."""
    conn = _v21_conn(tmp_path)
    try:
        _, _, _, pe_id = _seed_candidate_and_pattern_evaluation(conn)
        trade = _make_trade(pattern_evaluation_id=pe_id)
        with conn:
            tid = insert_trade_with_event(
                conn, trade,
                event_ts="2026-05-22T12:30:00.000",
            )
        fetched = get_trade(conn, tid)
        assert fetched is not None
        assert fetched.pattern_evaluation_id == pe_id
    finally:
        conn.close()


def test_row_to_trade_populates_pattern_evaluation_id_None_when_null_column(  # noqa: N802
    tmp_path: Path,
) -> None:
    """Delta B - _row_to_trade returns pattern_evaluation_id=None when NULL."""
    conn = _v21_conn(tmp_path)
    try:
        trade = _make_trade(pattern_evaluation_id=None)
        with conn:
            tid = insert_trade_with_event(
                conn, trade,
                event_ts="2026-05-22T12:30:00.000",
            )
        fetched = get_trade(conn, tid)
        assert fetched is not None
        assert fetched.pattern_evaluation_id is None
    finally:
        conn.close()


def test_insert_trade_with_pattern_evaluation_id_persists(
    tmp_path: Path,
) -> None:
    """Delta B - schema-aware INSERT path persists pattern_evaluation_id."""
    conn = _v21_conn(tmp_path)
    try:
        _, _, _, pe_id = _seed_candidate_and_pattern_evaluation(conn)
        trade = _make_trade(pattern_evaluation_id=pe_id)
        with conn:
            tid = insert_trade_with_event(
                conn, trade,
                event_ts="2026-05-22T12:30:00.000",
            )
        row = conn.execute(
            "SELECT pattern_evaluation_id FROM trades WHERE id=?", (tid,),
        ).fetchone()
        assert row[0] == pe_id
    finally:
        conn.close()


def test_fk_cascade_on_pattern_evaluations_delete_sets_trade_pattern_evaluation_id_null(
    tmp_path: Path,
) -> None:
    """Delta B - FK ON DELETE SET NULL on pattern_evaluations (chained via pipeline_runs).

    pattern_evaluations has FK to pipeline_runs ON DELETE CASCADE; deleting
    pipeline_runs would cascade-delete the pattern_evaluations row, which in
    turn would fire ON DELETE SET NULL on the trade backlink. BUT: trades.
    chart_pattern_classification_pipeline_run_id has FK to pipeline_runs with
    NO ACTION (default), which would BLOCK the pipeline_runs delete when a
    trade refers to it via that older FK. So this test directly deletes the
    pattern_evaluations row (NOT the pipeline_runs row) to exercise the
    Delta B FK in isolation.
    """
    conn = _v21_conn(tmp_path)
    try:
        _, _, _, pe_id = _seed_candidate_and_pattern_evaluation(conn)
        trade = _make_trade(pattern_evaluation_id=pe_id)
        with conn:
            tid = insert_trade_with_event(
                conn, trade,
                event_ts="2026-05-22T12:30:00.000",
            )
        # Direct delete of pattern_evaluations row.
        conn.execute("DELETE FROM pattern_evaluations WHERE id=?", (pe_id,))
        conn.commit()
        row = conn.execute(
            "SELECT id, pattern_evaluation_id FROM trades WHERE id=?", (tid,),
        ).fetchone()
        assert row is not None, "trade was unexpectedly cascade-deleted"
        assert row[1] is None, (
            "pattern_evaluation_id should SET NULL on pattern_evaluations delete, "
            f"got {row[1]!r}"
        )
    finally:
        conn.close()


def test_pattern_evaluations_direct_delete_sets_trade_pattern_evaluation_id_null(
    tmp_path: Path,
) -> None:
    """Delta B - Codex R1 MAJOR #4 — direct row deletion exercises the new FK.

    Distinct from the chained-cascade test above: this test verifies the
    direct-deletion path against the pattern_evaluations row independently
    of any pipeline_runs cascade.
    """
    conn = _v21_conn(tmp_path)
    try:
        _, _, _, pe_id = _seed_candidate_and_pattern_evaluation(conn)
        trade_a = _make_trade(pattern_evaluation_id=pe_id)
        with conn:
            tid_a = insert_trade_with_event(
                conn, trade_a,
                event_ts="2026-05-22T12:30:00.000",
            )
        # A second trade that does NOT reference pe_id stays untouched.
        trade_b = Trade(
            id=None,
            ticker="DEF",
            entry_date="2026-05-22",
            entry_price=20.0,
            initial_shares=3,
            initial_stop=18.0,
            current_stop=18.0,
            state="entered",
            watchlist_entry_target=None,
            watchlist_initial_stop=None,
            notes=None,
            trade_origin="manual_off_pipeline",
            pre_trade_locked_at="2026-05-22T12:00:00.000",
            current_size=3.0,
            candidate_id=None,
            pattern_evaluation_id=None,
        )
        with conn:
            tid_b = insert_trade_with_event(
                conn, trade_b,
                event_ts="2026-05-22T12:31:00.000",
            )
        conn.execute("DELETE FROM pattern_evaluations WHERE id=?", (pe_id,))
        conn.commit()
        row_a = conn.execute(
            "SELECT pattern_evaluation_id FROM trades WHERE id=?", (tid_a,),
        ).fetchone()
        row_b = conn.execute(
            "SELECT pattern_evaluation_id FROM trades WHERE id=?", (tid_b,),
        ).fetchone()
        assert row_a[0] is None
        assert row_b[0] is None  # never had one, stays NULL
    finally:
        conn.close()


# ============================================================================
# Step 1c — Backup-gate (4 tests)
# ============================================================================


def _seed_v20_db_for_backup_tests(tmp_path: Path) -> Path:
    """Apply migrations up to v20."""
    db_path = tmp_path / "v20.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=20)
    conn.close()
    return db_path


def test_run_migrations_v20_to_v21_creates_backup_with_correct_filename(
    tmp_path: Path,
) -> None:
    """Backup-gate fires at pre_version=20 + target=21 with SB6c filename prefix."""
    db_path = _seed_v20_db_for_backup_tests(tmp_path)
    backup_dir = tmp_path / "backups"

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        run_migrations(conn, target_version=21, backup_dir=backup_dir)
    finally:
        conn.close()

    backups = list(backup_dir.glob("swing-pre-phase13-sb6c-migration-*.db"))
    assert backups, (
        f"SB6c backup file missing from {backup_dir}; "
        f"contents: {list(backup_dir.iterdir())}"
    )
    assert hasattr(db_module, "_phase13_sb6c_backup_gate"), (
        "_phase13_sb6c_backup_gate function not defined in swing.data.db"
    )


def test_run_migrations_v20_to_v21_strict_equality_pre_version_predicate(
    tmp_path: Path,
) -> None:
    """SB6c gate fires only at pre_version==20 (strict equality, not <=)."""
    # Seed v19 + walk forward to v21 without SB6c file.
    db_path = tmp_path / "v19.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=19)
    conn.close()

    backup_dir = tmp_path / "backups"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        run_migrations(conn, target_version=21, backup_dir=backup_dir)
    finally:
        conn.close()

    sb6c_backups = list(backup_dir.glob("swing-pre-phase13-sb6c-migration-*.db"))
    assert sb6c_backups == [], (
        "SB6c gate must NOT fire from pre_version<20 per strict-equality "
        f"discipline; found unexpected: {sb6c_backups}"
    )


def test_run_migrations_v19_to_v21_skips_sb6c_backup_uses_phase13_v20_backup_only(
    tmp_path: Path,
) -> None:
    """Multi-version jump v19->v21 fires v20 phase13 gate, NOT SB6c gate."""
    db_path = tmp_path / "v19.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=19)
    conn.close()

    backup_dir = tmp_path / "backups"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        run_migrations(conn, target_version=21, backup_dir=backup_dir)
    finally:
        conn.close()

    # Phase 13 (v20) backup IS written; SB6c (v21) backup is NOT.
    phase13_v20_backups = list(
        backup_dir.glob("swing-pre-phase13-migration-*.db")
    )
    sb6c_backups = list(backup_dir.glob("swing-pre-phase13-sb6c-migration-*.db"))
    assert phase13_v20_backups, (
        "Phase 13 v20 backup should be written at pre_version=19; "
        f"backup_dir: {list(backup_dir.iterdir())}"
    )
    assert sb6c_backups == [], (
        "SB6c backup must NOT fire from pre_version<20; "
        f"found unexpected: {sb6c_backups}"
    )


def test_expected_schema_version_constant_is_21_post_sb6c() -> None:
    """EXPECTED_SCHEMA_VERSION constant tracks HEAD (now 22 post-Phase-14-SB2).

    Test name preserved (stale-name-but-current-assertion) per cumulative
    discipline; Phase 14 Sub-bundle 3 migration 0023 bumps HEAD from 22 to 23.
    """
    assert EXPECTED_SCHEMA_VERSION == 23, (
        f"EXPECTED_SCHEMA_VERSION must be 23, got {EXPECTED_SCHEMA_VERSION}"
    )


# ============================================================================
# Smoke: _TRADE_SELECT_COLS contains both new columns (binding for read-path).
# ============================================================================


def test_trade_select_cols_includes_new_v21_columns() -> None:
    """Read-path SELECT-cols list includes candidate_id + pattern_evaluation_id.

    Defends against the T3.SB3 R1 M#1 read-path-mapping-lags-write-path gotcha.
    """
    assert "candidate_id" in _TRADE_SELECT_COLS
    assert "pattern_evaluation_id" in _TRADE_SELECT_COLS


def test_row_to_trade_index_map_matches_select_cols(
    tmp_path: Path,
) -> None:
    """End-to-end column-position check via _row_to_trade reconstruction."""
    conn = _v21_conn(tmp_path)
    try:
        _, _, candidate_id, pe_id = _seed_candidate_and_pattern_evaluation(
            conn
        )
        trade = _make_trade(
            candidate_id=candidate_id, pattern_evaluation_id=pe_id,
        )
        with conn:
            tid = insert_trade_with_event(
                conn, trade,
                event_ts="2026-05-22T12:30:00.000",
            )
        # Read the raw row via _TRADE_SELECT_COLS + map manually.
        row = conn.execute(
            f"SELECT {_TRADE_SELECT_COLS} FROM trades WHERE id=?",  # noqa: S608
            (tid,),
        ).fetchone()
        assert row is not None
        trade_obj = _row_to_trade(row)
        assert trade_obj.candidate_id == candidate_id
        assert trade_obj.pattern_evaluation_id == pe_id
    finally:
        conn.close()


# ============================================================================
# Sanity: schema_version table reaches 21 after migration.
# ============================================================================


def test_schema_version_reaches_21_after_v21_migration(
    tmp_path: Path,
) -> None:
    """SELECT version FROM schema_version returns HEAD (23) post-migration.

    Test name preserved (stale-name-but-current-assertion); _v21_conn uses
    ensure_schema which walks to HEAD, now v23 post-Phase-14-SB3.
    """
    conn = _v21_conn(tmp_path)
    try:
        ver = conn.execute("SELECT version FROM schema_version").fetchone()
        assert ver[0] == 23, f"schema_version != 23, got {ver[0]}"
    finally:
        conn.close()


# Allow `pytest` to be import-available; the import is used for cross-bundle
# pin sibling test file. Avoid unused-import linter rejection by referencing
# below.
_ = pytest
