"""Phase 9 T-A.1 — migration 0017 round-trip (FULL atomic scope).

Per Codex R1 Critical #1 fix (plan §C "Migration atomicity"): the SINGLE
migration file ``0017_phase9_risk_policy_and_reconciliation.sql`` lands ALL
Phase 9 schema in one atomic ``executescript`` pass:

  - 5 new tables (risk_policy, reconciliation_runs,
    reconciliation_discrepancies, hypothesis_status_history,
    account_equity_snapshots).
  - 2 ALTER ADD COLUMNs (trades.risk_policy_id_at_lock,
    review_log.risk_policy_id_at_review_completion).
  - 13 new indexes (2 + 3 + 4 + 2 + 2).
  - risk_policy seed row at policy_id=1 (cfg defaults per spec §3.1.3).
  - hypothesis_status_history seed row per existing hypothesis_registry
    row (4 rows on production; per spec §3.4.1 R3 Major #2 normalization).
  - UPDATE schema_version SET version = 17.

Sub-bundles B/C/D/E DO NOT modify this migration; they ship code that
consumes the schema landed here.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import EXPECTED_SCHEMA_VERSION, ensure_schema


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase9.db"
    return ensure_schema(db_path)


# ============================================================================
# §1 — schema_version + EXPECTED_SCHEMA_VERSION
# ============================================================================


def test_expected_schema_version_constant_is_19() -> None:
    # ensure_schema walks to HEAD; Phase 14 Sub-bundle 3 migration 0023 advanced to 23 (was 22 post-SB2).
    assert EXPECTED_SCHEMA_VERSION == 24


def test_schema_version_row_is_19(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    assert row[0] == 24


# ============================================================================
# §2 — risk_policy table (34 columns; 2 indexes; seed row)
# ============================================================================


_RISK_POLICY_EXPECTED_COLS: frozenset[str] = frozenset({
    "policy_id", "effective_from", "effective_to", "is_active",
    "superseded_by_policy_id", "created_at", "policy_notes",
    "max_account_risk_per_trade_pct", "max_concurrent_positions",
    "max_portfolio_heat_pct", "max_sector_concentration_positions",
    "consecutive_losses_pause_threshold", "consecutive_losses_pause_action",
    "consecutive_losses_streak_reset",
    "drawdown_circuit_breaker_enabled", "drawdown_pause_threshold_R",
    "drawdown_pause_action", "drawdown_size_reduction_pct",
    "drawdown_recovery_threshold_R",
    "capital_floor_constant_dollars",
    "scratch_epsilon_R", "review_lag_threshold_days",
    "low_sample_size_threshold_class_a_n",
    "low_sample_size_threshold_class_b_n",
    "low_sample_size_threshold_class_c_n",
    "low_sample_size_threshold_class_d_n",
    "global_confidence_floor_n", "bootstrap_resample_count",
    "process_grade_weight_entry", "process_grade_weight_management",
    "process_grade_weight_exit",
    "mfe_mae_default_precision_level",
    "trail_MA_period_days", "trail_MA_post_2R_period_days",
})


def test_risk_policy_table_exists_with_34_columns(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA table_info(risk_policy)")
    cols = {r[1] for r in cur.fetchall()}
    assert cols == _RISK_POLICY_EXPECTED_COLS, (
        f"column drift; missing {_RISK_POLICY_EXPECTED_COLS - cols}; "
        f"extra {cols - _RISK_POLICY_EXPECTED_COLS}"
    )
    assert len(cols) == 34


def test_risk_policy_seed_row_is_active(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT policy_id, is_active, capital_floor_constant_dollars, "
        "scratch_epsilon_R, max_concurrent_positions, "
        "max_account_risk_per_trade_pct, max_portfolio_heat_pct, "
        "drawdown_circuit_breaker_enabled, "
        "process_grade_weight_entry, process_grade_weight_management, "
        "process_grade_weight_exit, mfe_mae_default_precision_level, "
        "trail_MA_period_days, trail_MA_post_2R_period_days "
        "FROM risk_policy WHERE policy_id = 1"
    ).fetchone()
    assert row is not None
    (
        policy_id, is_active, capital_floor, eps, max_open,
        max_risk_pct, max_heat, dd_enabled,
        w_entry, w_mgmt, w_exit, mfe_prec, trail_ma, trail_post,
    ) = row
    assert policy_id == 1
    assert is_active == 1
    assert capital_floor == 7500.0
    assert eps == 0.10
    assert max_open >= 1
    assert max_risk_pct > 0
    assert max_heat == 3.0
    assert dd_enabled == 0  # default opt-in disabled per spec §1.4
    # Sum-to-1.0 invariant.
    assert abs((w_entry + w_mgmt + w_exit) - 1.0) < 1e-9
    assert mfe_prec == "daily_approximate"
    assert trail_ma == 21
    assert trail_post is None


def test_risk_policy_seed_timestamps_naive_and_millisecond(
    conn: sqlite3.Connection,
) -> None:
    """Seed row's effective_from + created_at conform to validator format."""
    from swing.data.datetime_helpers import validate_ms_iso

    row = conn.execute(
        "SELECT effective_from, created_at, effective_to FROM risk_policy "
        "WHERE policy_id = 1"
    ).fetchone()
    eff_from, created_at, eff_to = row
    validate_ms_iso(eff_from)
    validate_ms_iso(created_at)
    assert eff_to is None  # active row


def test_risk_policy_active_partial_unique_index_forbids_two_active(
    conn: sqlite3.Connection,
) -> None:
    """Spec §3.1.2: ux_risk_policy_active partial-unique on is_active=1."""
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        conn.execute(
            "INSERT INTO risk_policy ("
            "effective_from, is_active, created_at, "
            "max_account_risk_per_trade_pct, max_concurrent_positions, "
            "max_portfolio_heat_pct, max_sector_concentration_positions, "
            "consecutive_losses_pause_threshold, consecutive_losses_pause_action, "
            "consecutive_losses_streak_reset, drawdown_circuit_breaker_enabled, "
            "capital_floor_constant_dollars, scratch_epsilon_R, "
            "review_lag_threshold_days, low_sample_size_threshold_class_a_n, "
            "low_sample_size_threshold_class_b_n, low_sample_size_threshold_class_c_n, "
            "low_sample_size_threshold_class_d_n, global_confidence_floor_n, "
            "bootstrap_resample_count, process_grade_weight_entry, "
            "process_grade_weight_management, process_grade_weight_exit, "
            "mfe_mae_default_precision_level, trail_MA_period_days"
            ") VALUES ("
            "'2026-05-11T00:00:00.000', 1, '2026-05-11T00:00:00.000', "
            "0.50, 6, 3.0, 3, 3, 'review_required', 'review_completed', 0, "
            "7500.0, 0.10, 7, 3, 5, 5, 10, 20, 1000, 0.40, 0.35, 0.25, "
            "'daily_approximate', 21)"
        )


def test_risk_policy_indexes_present(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND tbl_name='risk_policy' ORDER BY name"
    ).fetchall()
    names = {r[0] for r in rows}
    assert "ux_risk_policy_active" in names
    assert "ix_risk_policy_effective_from" in names


def test_risk_policy_grade_weight_sum_check_blocks_invalid(
    conn: sqlite3.Connection,
) -> None:
    """CHECK ABS(entry+mgmt+exit - 1.0) < 1e-9 enforced (spec §3.1 R1 Minor #4 defense)."""
    # First flag the seed inactive so the partial-unique index is free.
    conn.execute("UPDATE risk_policy SET is_active = 0 WHERE policy_id = 1")
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO risk_policy ("
            "effective_from, is_active, created_at, "
            "max_account_risk_per_trade_pct, max_concurrent_positions, "
            "max_portfolio_heat_pct, max_sector_concentration_positions, "
            "consecutive_losses_pause_threshold, consecutive_losses_pause_action, "
            "consecutive_losses_streak_reset, drawdown_circuit_breaker_enabled, "
            "capital_floor_constant_dollars, scratch_epsilon_R, "
            "review_lag_threshold_days, low_sample_size_threshold_class_a_n, "
            "low_sample_size_threshold_class_b_n, low_sample_size_threshold_class_c_n, "
            "low_sample_size_threshold_class_d_n, global_confidence_floor_n, "
            "bootstrap_resample_count, process_grade_weight_entry, "
            "process_grade_weight_management, process_grade_weight_exit, "
            "mfe_mae_default_precision_level, trail_MA_period_days"
            ") VALUES ("
            "'2026-05-11T00:00:00.001', 1, '2026-05-11T00:00:00.001', "
            "0.50, 6, 3.0, 3, 3, 'review_required', 'review_completed', 0, "
            "7500.0, 0.10, 7, 3, 5, 5, 10, 20, 1000, 0.50, 0.35, 0.25, "
            "'daily_approximate', 21)"
        )


# ============================================================================
# §3 — reconciliation_runs table (17 columns; 3 indexes)
# ============================================================================


_RECON_RUNS_EXPECTED_COLS: frozenset[str] = frozenset({
    "run_id", "source", "source_artifact_path", "source_artifact_sha256",
    "period_start", "period_end", "started_ts", "finished_ts", "state",
    "account_equity_journal_dollars", "account_equity_source_dollars",
    "equity_delta_dollars", "trades_reconciled_count",
    "fills_reconciled_count", "discrepancies_count",
    "unresolved_discrepancies_count", "summary_json",
})
# spec §3.2 lists 17 columns total; "error_message" + "notes" + the 14
# enumerated above + run_id = 17. The frozenset above lists the 16 metric/
# state columns; error_message + notes are added below.
# Phase 11 (migration 0018) ALTER ADD: schwab_api_call_id FK NULLABLE.
_RECON_RUNS_EXPECTED_COLS = _RECON_RUNS_EXPECTED_COLS | {
    "error_message", "notes", "schwab_api_call_id",
}


def test_reconciliation_runs_table_exists_with_19_columns(
    conn: sqlite3.Connection,
) -> None:
    """Spec §3.2 enumerates 17 distinct fields; we count two-side: see comment.

    Recount per spec §3.2 (line-by-line): run_id, source, source_artifact_path,
    source_artifact_sha256, period_start, period_end, started_ts, finished_ts,
    state, account_equity_journal_dollars, account_equity_source_dollars,
    equity_delta_dollars, trades_reconciled_count, fills_reconciled_count,
    discrepancies_count, unresolved_discrepancies_count, summary_json,
    error_message, notes = 19 distinct columns.

    Spec text "Field count: 17 columns" is a brainstorm-phase miscount
    (parallels Codex R1 Major #2 risk_policy "28 vs 34" — column LIST is
    binding; subtotal is advisory). We assert the LIST.
    """
    cur = conn.execute("PRAGMA table_info(reconciliation_runs)")
    cols = {r[1] for r in cur.fetchall()}
    assert cols == _RECON_RUNS_EXPECTED_COLS, (
        f"column drift; missing {_RECON_RUNS_EXPECTED_COLS - cols}; "
        f"extra {cols - _RECON_RUNS_EXPECTED_COLS}"
    )


def test_reconciliation_runs_state_check_enum(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO reconciliation_runs (source, started_ts, state) "
            "VALUES ('tos_csv', '2026-05-11T00:00:00.000', 'invalid_state')"
        )


def test_reconciliation_runs_source_check_enum(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO reconciliation_runs (source, started_ts, state) "
            "VALUES ('not_a_source', '2026-05-11T00:00:00.000', 'running')"
        )


def test_reconciliation_runs_indexes_present(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND tbl_name='reconciliation_runs' ORDER BY name"
    ).fetchall()
    names = {r[0] for r in rows}
    assert "ix_reconciliation_runs_started_ts" in names
    assert "ix_reconciliation_runs_state" in names
    assert "ix_reconciliation_runs_source" in names


# ============================================================================
# §4 — reconciliation_discrepancies table (18 columns; 4 indexes; FK CASCADE)
# ============================================================================


_RECON_DISC_EXPECTED_COLS: frozenset[str] = frozenset({
    "discrepancy_id", "run_id", "discrepancy_type", "trade_id", "fill_id",
    "cash_movement_id", "linked_daily_management_record_id", "ticker",
    "field_name", "expected_value_json", "actual_value_json", "delta_text",
    "material_to_review", "resolution", "resolution_reason", "resolved_at",
    "resolved_by", "mistake_tag_assigned", "created_at",
    # Phase 12 Sub-bundle C.A T-A.1 added `ambiguity_kind` via 0019 rebuild;
    # legacy 19 → widened 20.
    "ambiguity_kind",
})


def test_reconciliation_discrepancies_table_exists_with_20_columns(
    conn: sqlite3.Connection,
) -> None:
    """Spec §3.3 enumerated 19 distinct fields at Phase 9; migration 0019
    widened to 20 by adding `ambiguity_kind` (tier-2 pending classification).

    Listed: discrepancy_id, run_id, discrepancy_type, trade_id, fill_id,
    cash_movement_id, linked_daily_management_record_id, ticker, field_name,
    expected_value_json, actual_value_json, delta_text, material_to_review,
    resolution, ambiguity_kind, resolution_reason, resolved_at, resolved_by,
    mistake_tag_assigned, created_at = 20.
    """
    cur = conn.execute("PRAGMA table_info(reconciliation_discrepancies)")
    cols = {r[1] for r in cur.fetchall()}
    assert cols == _RECON_DISC_EXPECTED_COLS, (
        f"column drift; missing {_RECON_DISC_EXPECTED_COLS - cols}; "
        f"extra {cols - _RECON_DISC_EXPECTED_COLS}"
    )


def test_reconciliation_discrepancies_fk_cascade_from_runs(
    conn: sqlite3.Connection,
) -> None:
    """Deleting a reconciliation_runs row cascades child discrepancies."""
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "INSERT INTO reconciliation_runs (source, started_ts, state) "
        "VALUES ('tos_csv', '2026-05-11T10:00:00.000', 'completed')"
    )
    run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "run_id, discrepancy_type, field_name, material_to_review, "
        "resolution, created_at"
        ") VALUES (?, 'close_price_mismatch', 'price', 1, 'unresolved', "
        "'2026-05-11T10:00:00.000')",
        (run_id,),
    )
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_discrepancies"
    ).fetchone()[0] == 1
    conn.execute("DELETE FROM reconciliation_runs WHERE run_id = ?", (run_id,))
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_discrepancies"
    ).fetchone()[0] == 0


def test_reconciliation_discrepancies_type_enum_check(
    conn: sqlite3.Connection,
) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "INSERT INTO reconciliation_runs (source, started_ts, state) "
        "VALUES ('tos_csv', '2026-05-11T10:00:00.000', 'completed')"
    )
    run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO reconciliation_discrepancies ("
            "run_id, discrepancy_type, field_name, material_to_review, "
            "resolution, created_at"
            ") VALUES (?, 'not_a_real_type', 'price', 1, 'unresolved', "
            "'2026-05-11T10:00:00.000')",
            (run_id,),
        )


def test_reconciliation_discrepancies_indexes_present(
    conn: sqlite3.Connection,
) -> None:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND tbl_name='reconciliation_discrepancies' ORDER BY name"
    ).fetchall()
    names = {r[0] for r in rows}
    assert "ix_reconciliation_discrepancies_run" in names
    assert "ix_reconciliation_discrepancies_trade" in names
    assert "ix_reconciliation_discrepancies_unresolved" in names
    assert "ix_reconciliation_discrepancies_material" in names


# ============================================================================
# §5 — hypothesis_status_history table (7 cols; 2 indexes; per-hyp seed rows)
# ============================================================================


_HYP_HISTORY_EXPECTED_COLS: frozenset[str] = frozenset({
    "history_id", "hypothesis_id", "status", "effective_from",
    "effective_to", "change_reason", "recorded_at",
})


def test_hypothesis_status_history_table_exists_with_7_columns(
    conn: sqlite3.Connection,
) -> None:
    cur = conn.execute("PRAGMA table_info(hypothesis_status_history)")
    cols = {r[1] for r in cur.fetchall()}
    assert cols == _HYP_HISTORY_EXPECTED_COLS, (
        f"column drift; missing {_HYP_HISTORY_EXPECTED_COLS - cols}; "
        f"extra {cols - _HYP_HISTORY_EXPECTED_COLS}"
    )
    assert len(cols) == 7


def test_hypothesis_status_history_seed_one_row_per_hypothesis(
    conn: sqlite3.Connection,
) -> None:
    """Seed migration creates one row per existing hypothesis_registry row.

    Production DB has 4 hypothesis_registry rows seeded by 0008. Fresh test
    DB has the same 4 rows seeded by 0008. Each gets one open-interval
    (effective_to IS NULL) row in hypothesis_status_history.
    """
    n_hyp = conn.execute("SELECT COUNT(*) FROM hypothesis_registry").fetchone()[0]
    assert n_hyp >= 1, "test DB seeds hypothesis_registry rows"
    n_hist = conn.execute(
        "SELECT COUNT(*) FROM hypothesis_status_history"
    ).fetchone()[0]
    assert n_hist == n_hyp
    # All seeded rows are the current open interval.
    n_open = conn.execute(
        "SELECT COUNT(*) FROM hypothesis_status_history "
        "WHERE effective_to IS NULL"
    ).fetchone()[0]
    assert n_open == n_hyp
    # Each seed row's status matches the corresponding registry status.
    rows = conn.execute(
        "SELECT hsh.hypothesis_id, hsh.status, hr.status "
        "FROM hypothesis_status_history hsh "
        "JOIN hypothesis_registry hr ON hr.id = hsh.hypothesis_id "
        "WHERE hsh.effective_to IS NULL"
    ).fetchall()
    for hyp_id, hist_status, reg_status in rows:
        assert hist_status == reg_status, (
            f"hypothesis_id={hyp_id} seed status drift: hist={hist_status} "
            f"vs registry={reg_status}"
        )


def test_hypothesis_status_history_seed_timestamps_naive_ms(
    conn: sqlite3.Connection,
) -> None:
    """Seed effective_from = strftime('%Y-%m-%dT00:00:00.000', created_at)
    per spec §3.4.1 R3 Major #2; recorded_at = migration apply time."""
    from swing.data.datetime_helpers import validate_ms_iso

    rows = conn.execute(
        "SELECT effective_from, recorded_at FROM hypothesis_status_history "
        "WHERE effective_to IS NULL"
    ).fetchall()
    assert rows, "expect at least one seeded row"
    for eff_from, recorded_at in rows:
        validate_ms_iso(eff_from)
        validate_ms_iso(recorded_at)
        # Day-start anchor — last 12 chars are 'T00:00:00.000'.
        assert eff_from.endswith("T00:00:00.000"), (
            f"seed effective_from not normalized to day-start: {eff_from!r}"
        )


def test_hypothesis_status_history_partial_unique_current_index(
    conn: sqlite3.Connection,
) -> None:
    """ux_hypothesis_status_history_current forbids two open intervals per hypothesis."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND tbl_name='hypothesis_status_history' ORDER BY name"
    ).fetchall()
    names = {r[0] for r in rows}
    assert "ux_hypothesis_status_history_current" in names
    assert "ix_hypothesis_status_history_hyp" in names

    # Insert a second open-interval row for an existing hypothesis_id;
    # should violate the partial-unique index.
    seed = conn.execute(
        "SELECT hypothesis_id, status FROM hypothesis_status_history "
        "WHERE effective_to IS NULL LIMIT 1"
    ).fetchone()
    assert seed is not None
    hyp_id, status = seed
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        conn.execute(
            "INSERT INTO hypothesis_status_history ("
            "hypothesis_id, status, effective_from, effective_to, "
            "change_reason, recorded_at"
            ") VALUES (?, ?, '2026-05-12T00:00:00.000', NULL, NULL, "
            "'2026-05-12T00:00:00.000')",
            (hyp_id, status),
        )


def test_hypothesis_status_history_status_check_enum(
    conn: sqlite3.Connection,
) -> None:
    seed = conn.execute(
        "SELECT id FROM hypothesis_registry LIMIT 1"
    ).fetchone()
    assert seed is not None
    hyp_id = seed[0]
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO hypothesis_status_history ("
            "hypothesis_id, status, effective_from, effective_to, "
            "change_reason, recorded_at"
            ") VALUES (?, 'invalid_status', '2026-05-12T00:00:00.000', "
            "'2026-05-13T00:00:00.000', NULL, '2026-05-12T00:00:00.000')",
            (hyp_id,),
        )


def test_hypothesis_status_history_fk_cascade_from_registry(
    conn: sqlite3.Connection,
) -> None:
    """ON DELETE CASCADE on hypothesis_id (spec §3.4)."""
    conn.execute("PRAGMA foreign_keys = ON")
    seed = conn.execute(
        "SELECT id FROM hypothesis_registry LIMIT 1"
    ).fetchone()
    hyp_id = seed[0]
    n_before = conn.execute(
        "SELECT COUNT(*) FROM hypothesis_status_history WHERE hypothesis_id = ?",
        (hyp_id,),
    ).fetchone()[0]
    assert n_before >= 1
    conn.execute("DELETE FROM hypothesis_registry WHERE id = ?", (hyp_id,))
    n_after = conn.execute(
        "SELECT COUNT(*) FROM hypothesis_status_history WHERE hypothesis_id = ?",
        (hyp_id,),
    ).fetchone()[0]
    assert n_after == 0


# ============================================================================
# §6 — account_equity_snapshots table (8 cols; 2 indexes; unique date+source)
# ============================================================================


_AES_EXPECTED_COLS: frozenset[str] = frozenset({
    "snapshot_id", "snapshot_date", "equity_dollars", "source",
    "source_artifact_path", "recorded_at", "recorded_by", "notes",
    # Phase 11 (migration 0018) ALTER ADD: schwab_account_hash TEXT NULLABLE.
    "schwab_account_hash",
})


def test_account_equity_snapshots_table_exists_with_8_columns(
    conn: sqlite3.Connection,
) -> None:
    # Test name preserved for git-history continuity; Phase 11 added a 9th
    # column (schwab_account_hash) so the count assertion below tracks HEAD.
    cur = conn.execute("PRAGMA table_info(account_equity_snapshots)")
    cols = {r[1] for r in cur.fetchall()}
    assert cols == _AES_EXPECTED_COLS, (
        f"column drift; missing {_AES_EXPECTED_COLS - cols}; "
        f"extra {cols - _AES_EXPECTED_COLS}"
    )
    assert len(cols) == 9  # Phase 11: 8 -> 9 (schwab_account_hash ALTER)


def test_account_equity_snapshots_unique_date_source(
    conn: sqlite3.Connection,
) -> None:
    """ux_account_equity_snapshots_date_source enforces (date, source) uniqueness."""
    conn.execute(
        "INSERT INTO account_equity_snapshots ("
        "snapshot_date, equity_dollars, source, recorded_at, recorded_by"
        ") VALUES ('2026-05-08', 1000.00, 'manual', "
        "'2026-05-08T16:00:00.000', 'operator')"
    )
    # Same date + same source: rejected.
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        conn.execute(
            "INSERT INTO account_equity_snapshots ("
            "snapshot_date, equity_dollars, source, recorded_at, recorded_by"
            ") VALUES ('2026-05-08', 2000.00, 'manual', "
            "'2026-05-08T17:00:00.000', 'operator')"
        )
    # Same date + DIFFERENT source: accepted (per spec §3.5).
    conn.execute(
        "INSERT INTO account_equity_snapshots ("
        "snapshot_date, equity_dollars, source, recorded_at, recorded_by"
        ") VALUES ('2026-05-08', 1500.00, 'tos_csv', "
        "'2026-05-08T18:00:00.000', 'operator')"
    )


def test_account_equity_snapshots_source_check_enum(
    conn: sqlite3.Connection,
) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO account_equity_snapshots ("
            "snapshot_date, equity_dollars, source, recorded_at, recorded_by"
            ") VALUES ('2026-05-08', 1000.00, 'invalid_source', "
            "'2026-05-08T16:00:00.000', 'operator')"
        )


def test_account_equity_snapshots_equity_positive_check(
    conn: sqlite3.Connection,
) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO account_equity_snapshots ("
            "snapshot_date, equity_dollars, source, recorded_at, recorded_by"
            ") VALUES ('2026-05-08', -10.00, 'manual', "
            "'2026-05-08T16:00:00.000', 'operator')"
        )


def test_account_equity_snapshots_indexes_present(
    conn: sqlite3.Connection,
) -> None:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND tbl_name='account_equity_snapshots' ORDER BY name"
    ).fetchall()
    names = {r[0] for r in rows}
    assert "ux_account_equity_snapshots_date_source" in names
    assert "ix_account_equity_snapshots_date" in names


# ============================================================================
# §7 — ALTER ADDs on trades + review_log
# ============================================================================


def test_trades_risk_policy_id_at_lock_column_exists(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA table_info(trades)")
    cols = {r[1] for r in cur.fetchall()}
    assert "risk_policy_id_at_lock" in cols


def test_review_log_risk_policy_id_at_review_completion_column_exists(
    conn: sqlite3.Connection,
) -> None:
    cur = conn.execute("PRAGMA table_info(review_log)")
    cols = {r[1] for r in cur.fetchall()}
    assert "risk_policy_id_at_review_completion" in cols


def test_legacy_trade_insert_has_null_risk_policy_id_at_lock(
    conn: sqlite3.Connection,
) -> None:
    """Legacy INSERT (no Phase 9 stamp) leaves risk_policy_id_at_lock NULL.

    Verifies the ALTER ADD COLUMN landed as NULLABLE so existing trades
    pre-Phase-9 stay legal post-migration.
    """
    conn.execute(
        "INSERT INTO trades ("
        "ticker, entry_date, entry_price, initial_shares, initial_stop, "
        "current_stop, state, sector, industry, trade_origin, "
        "pre_trade_locked_at, current_size"
        ") VALUES ("
        "'TESTLEG', '2026-05-11', 100.0, 10, 95.0, 95.0, 'entered', "
        "'Tech', 'Software', 'manual_off_pipeline', "
        "'2026-05-11T15:30:00.000', 10"
        ")"
    )
    row = conn.execute(
        "SELECT risk_policy_id_at_lock FROM trades WHERE ticker = 'TESTLEG'"
    ).fetchone()
    assert row[0] is None


def test_trades_risk_policy_id_at_lock_fk_to_risk_policy(
    conn: sqlite3.Connection,
) -> None:
    """FK constraint accepts policy_id=1 (seed) and rejects unknown ids."""
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "INSERT INTO trades ("
        "ticker, entry_date, entry_price, initial_shares, initial_stop, "
        "current_stop, state, sector, industry, trade_origin, "
        "pre_trade_locked_at, current_size, risk_policy_id_at_lock"
        ") VALUES ("
        "'TESTFK', '2026-05-11', 100.0, 10, 95.0, 95.0, 'entered', "
        "'Tech', 'Software', 'manual_off_pipeline', "
        "'2026-05-11T15:30:00.000', 10, 1"
        ")"
    )
    # Unknown policy_id rejected.
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        conn.execute(
            "INSERT INTO trades ("
            "ticker, entry_date, entry_price, initial_shares, initial_stop, "
            "current_stop, state, sector, industry, trade_origin, "
            "pre_trade_locked_at, current_size, risk_policy_id_at_lock"
            ") VALUES ("
            "'TESTFKBAD', '2026-05-11', 100.0, 10, 95.0, 95.0, 'entered', "
            "'Tech', 'Software', 'manual_off_pipeline', "
            "'2026-05-11T15:30:00.000', 10, 99999"
            ")"
        )
