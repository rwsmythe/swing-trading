-- Migration 0017 — Phase 9: Risk_Policy + Reconciliation Depth
--
-- COMPLETE-AND-ATOMIC schema landing per plan §C "Migration atomicity"
-- (Codex R1 Critical #1 fix). This SINGLE file lands ALL Phase 9 schema in
-- one executescript pass:
--
--   1. CREATE TABLE risk_policy (34 cols per spec §3.1; "28 cols" subtotal in
--      spec text is a brainstorm-phase miscount — column LIST is binding,
--      Codex R1 Major #2). 2 indexes (1 partial-unique active + 1 timeline).
--      Seed row at policy_id=1 from cfg defaults per spec §3.1.3.
--   2. CREATE TABLE reconciliation_runs (19 cols per spec §3.2 enumerated
--      list; "17" text subtotal is brainstorm miscount). 3 indexes.
--   3. CREATE TABLE reconciliation_discrepancies (19 cols per spec §3.3
--      enumerated list; "18" text subtotal is brainstorm miscount). 4 indexes.
--      ON DELETE CASCADE from reconciliation_runs.
--   4. CREATE TABLE hypothesis_status_history (7 cols per spec §3.4). 2 indexes
--      (1 partial-unique current + 1 timeline). Seed one row per existing
--      hypothesis_registry row per spec §3.4.1 R3 Major #2.
--   5. CREATE TABLE account_equity_snapshots (8 cols per spec §3.5). 2 indexes
--      (1 unique (date,source) + 1 date lookup).
--   6. ALTER TABLE trades ADD COLUMN risk_policy_id_at_lock (FK, NULLABLE).
--   7. ALTER TABLE review_log ADD COLUMN risk_policy_id_at_review_completion
--      (FK, NULLABLE).
--   8. UPDATE schema_version SET version = 17 (LAST statement; Codex R1
--      Critical #1 — version bump fires only after all schema work lands).
--
-- Sub-bundles B/C/D/E DO NOT modify this migration; they ship code that
-- consumes the schema.
--
-- Lesson inheritance:
--   - foreign_keys=OFF runner discipline (Phase 7 hotfix 283d4fa) — runner
--     toggles globally; this migration has no rebuilds.
--   - executescript() partial-failure rollback wrapper (Phase 7 Sub-A R1 M3)
--     — runner-owned (swing/data/db.py:_apply_migration).
--   - Backup gate fires only on current_version == 16 AND target >= 17
--     (filename swing-pre-phase9-migration-<ISO>.db) — runner-level Phase 9
--     gate added alongside this migration in swing/data/db.py.
--   - Datetime discipline: TEXT datetime columns store naive-UTC millisecond
--     precision YYYY-MM-DDTHH:MM:SS.SSS (spec §9.3 + §3.1.3 R3 Major #1).
--     SQL seed rows construct via strftime('%Y-%m-%dT%H:%M:%f', 'now');
--     hypothesis_status_history seed normalizes to day-start anchor via
--     strftime('%Y-%m-%dT00:00:00.000', hypothesis_registry.created_at) per
--     spec §3.4.1 R3 Major #2.
--   - NO INSERT OR REPLACE anywhere (CLAUDE.md gotcha + plan §A.8 baseline).
--   - Sum-to-1.0 cross-field CHECK on process_grade_weight_* (spec §3.1
--     R1 Minor #4 defense-in-depth).

-- ============================================================================
-- §1. risk_policy table (34 columns) + 2 indexes + seed row
-- ============================================================================

CREATE TABLE risk_policy (
    -- Metadata (7):
    policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    is_active INTEGER NOT NULL CHECK (is_active IN (0, 1)) DEFAULT 1,
    superseded_by_policy_id INTEGER REFERENCES risk_policy(policy_id),
    created_at TEXT NOT NULL,
    policy_notes TEXT,

    -- Trading-risk (7):
    max_account_risk_per_trade_pct REAL NOT NULL
        CHECK (max_account_risk_per_trade_pct > 0),
    max_concurrent_positions INTEGER NOT NULL
        CHECK (max_concurrent_positions > 0),
    max_portfolio_heat_pct REAL NOT NULL
        CHECK (max_portfolio_heat_pct > 0),
    max_sector_concentration_positions INTEGER NOT NULL
        CHECK (max_sector_concentration_positions > 0),
    consecutive_losses_pause_threshold INTEGER NOT NULL
        CHECK (consecutive_losses_pause_threshold > 0),
    consecutive_losses_pause_action TEXT NOT NULL
        CHECK (consecutive_losses_pause_action IN ('review_required')),
    consecutive_losses_streak_reset TEXT NOT NULL
        CHECK (consecutive_losses_streak_reset IN ('review_completed')),

    -- Drawdown circuit breaker (5; default opt-in disabled per spec §1.4):
    drawdown_circuit_breaker_enabled INTEGER NOT NULL
        CHECK (drawdown_circuit_breaker_enabled IN (0, 1)) DEFAULT 0,
    drawdown_pause_threshold_R REAL
        CHECK (drawdown_pause_threshold_R IS NULL
               OR drawdown_pause_threshold_R < 0),
    drawdown_pause_action TEXT
        CHECK (drawdown_pause_action IS NULL
               OR drawdown_pause_action IN ('halt_new_entries', 'reduce_size')),
    drawdown_size_reduction_pct REAL
        CHECK (drawdown_size_reduction_pct IS NULL
               OR (drawdown_size_reduction_pct > 0
                   AND drawdown_size_reduction_pct <= 1)),
    drawdown_recovery_threshold_R REAL
        CHECK (drawdown_recovery_threshold_R IS NULL
               OR drawdown_recovery_threshold_R < 0),

    -- Capital + sizing (1):
    capital_floor_constant_dollars REAL NOT NULL
        CHECK (capital_floor_constant_dollars > 0),

    -- Statistics-methodology (9):
    scratch_epsilon_R REAL NOT NULL CHECK (scratch_epsilon_R > 0),
    review_lag_threshold_days INTEGER NOT NULL
        CHECK (review_lag_threshold_days > 0),
    low_sample_size_threshold_class_a_n INTEGER NOT NULL
        CHECK (low_sample_size_threshold_class_a_n > 0),
    low_sample_size_threshold_class_b_n INTEGER NOT NULL
        CHECK (low_sample_size_threshold_class_b_n > 0),
    low_sample_size_threshold_class_c_n INTEGER NOT NULL
        CHECK (low_sample_size_threshold_class_c_n > 0),
    low_sample_size_threshold_class_d_n INTEGER NOT NULL
        CHECK (low_sample_size_threshold_class_d_n > 0),
    global_confidence_floor_n INTEGER NOT NULL
        CHECK (global_confidence_floor_n > 0),
    bootstrap_resample_count INTEGER NOT NULL
        CHECK (bootstrap_resample_count > 0),

    -- Process-grade weights (3; sum to 1.0 cross-field CHECK below):
    process_grade_weight_entry REAL NOT NULL
        CHECK (process_grade_weight_entry > 0
               AND process_grade_weight_entry < 1),
    process_grade_weight_management REAL NOT NULL
        CHECK (process_grade_weight_management > 0
               AND process_grade_weight_management < 1),
    process_grade_weight_exit REAL NOT NULL
        CHECK (process_grade_weight_exit > 0
               AND process_grade_weight_exit < 1),

    -- MFE/MAE + trail-MA (3):
    mfe_mae_default_precision_level TEXT NOT NULL
        CHECK (mfe_mae_default_precision_level IN
               ('daily_approximate', 'intraday_estimated', 'intraday_exact')),
    trail_MA_period_days INTEGER NOT NULL
        CHECK (trail_MA_period_days > 0),
    trail_MA_post_2R_period_days INTEGER
        CHECK (trail_MA_post_2R_period_days IS NULL
               OR trail_MA_post_2R_period_days > 0),

    -- Sum-to-1.0 cross-field defense (spec §3.1 R1 Minor #4):
    CHECK (ABS((process_grade_weight_entry
                + process_grade_weight_management
                + process_grade_weight_exit) - 1.0) < 1e-9)
);

-- Active-policy partial-unique: forbids two non-superseded rows.
CREATE UNIQUE INDEX ux_risk_policy_active
    ON risk_policy (is_active)
    WHERE is_active = 1;

-- Effective-from timeline reads.
CREATE INDEX ix_risk_policy_effective_from
    ON risk_policy (effective_from);

-- Seed row at policy_id=1 from cfg defaults (spec §3.1.3).
-- Timestamps via strftime('%Y-%m-%dT%H:%M:%f', 'now') = millisecond precision
-- per spec §9.3 + §3.1.3 R3 Major #1.
INSERT INTO risk_policy (
    effective_from, is_active, created_at, policy_notes,
    max_account_risk_per_trade_pct, max_concurrent_positions,
    max_portfolio_heat_pct, max_sector_concentration_positions,
    consecutive_losses_pause_threshold, consecutive_losses_pause_action,
    consecutive_losses_streak_reset,
    drawdown_circuit_breaker_enabled,
    capital_floor_constant_dollars,
    scratch_epsilon_R, review_lag_threshold_days,
    low_sample_size_threshold_class_a_n,
    low_sample_size_threshold_class_b_n,
    low_sample_size_threshold_class_c_n,
    low_sample_size_threshold_class_d_n,
    global_confidence_floor_n, bootstrap_resample_count,
    process_grade_weight_entry, process_grade_weight_management,
    process_grade_weight_exit,
    mfe_mae_default_precision_level, trail_MA_period_days
) VALUES (
    strftime('%Y-%m-%dT%H:%M:%f', 'now'), 1,
    strftime('%Y-%m-%dT%H:%M:%f', 'now'),
    'Phase 9 seed from swing.config.toml defaults at migration apply time',
    0.50, 6, 3.0, 3,
    3, 'review_required', 'review_completed',
    0,
    7500.0,
    0.10, 7,
    3, 5, 5, 10,
    20, 1000,
    0.40, 0.35, 0.25,
    'daily_approximate', 21
);

-- ============================================================================
-- §2. reconciliation_runs table (19 columns) + 3 indexes
-- ============================================================================

CREATE TABLE reconciliation_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL
        CHECK (source IN ('tos_csv', 'schwab_api', 'manual', 'system_audit')),
    source_artifact_path TEXT,
    source_artifact_sha256 TEXT,
    period_start TEXT,
    period_end TEXT,
    started_ts TEXT NOT NULL,
    finished_ts TEXT,
    state TEXT NOT NULL
        CHECK (state IN ('running', 'completed', 'failed')) DEFAULT 'running',
    account_equity_journal_dollars REAL,
    account_equity_source_dollars REAL,
    equity_delta_dollars REAL,
    trades_reconciled_count INTEGER,
    fills_reconciled_count INTEGER,
    discrepancies_count INTEGER,
    unresolved_discrepancies_count INTEGER,
    summary_json TEXT,
    error_message TEXT,
    notes TEXT
);

CREATE INDEX ix_reconciliation_runs_started_ts
    ON reconciliation_runs (started_ts);

CREATE INDEX ix_reconciliation_runs_state
    ON reconciliation_runs (state)
    WHERE state IN ('running', 'failed');

CREATE INDEX ix_reconciliation_runs_source
    ON reconciliation_runs (source, started_ts);

-- ============================================================================
-- §3. reconciliation_discrepancies table (19 columns) + 4 indexes
-- ============================================================================

CREATE TABLE reconciliation_discrepancies (
    discrepancy_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL
        REFERENCES reconciliation_runs(run_id) ON DELETE CASCADE,
    discrepancy_type TEXT NOT NULL
        CHECK (discrepancy_type IN (
            'close_price_mismatch', 'stop_mismatch', 'position_qty_mismatch',
            'cash_movement_mismatch', 'sector_tamper', 'snapshot_mismatch',
            'unmatched_open_fill', 'unmatched_close_fill',
            'entry_price_mismatch', 'equity_delta'
        )),
    trade_id INTEGER REFERENCES trades(id) ON DELETE SET NULL,
    fill_id INTEGER REFERENCES fills(fill_id) ON DELETE SET NULL,
    cash_movement_id INTEGER
        REFERENCES cash_movements(id) ON DELETE SET NULL,
    linked_daily_management_record_id INTEGER
        REFERENCES daily_management_records(management_record_id)
        ON DELETE SET NULL,
    ticker TEXT,
    field_name TEXT NOT NULL,
    expected_value_json TEXT,
    actual_value_json TEXT,
    delta_text TEXT,
    material_to_review INTEGER NOT NULL CHECK (material_to_review IN (0, 1)),
    resolution TEXT NOT NULL
        CHECK (resolution IN (
            'journal_corrected', 'source_treated_canonical',
            'manual_override', 'unresolved', 'acknowledged_immaterial'
        )) DEFAULT 'unresolved',
    resolution_reason TEXT,
    resolved_at TEXT,
    resolved_by TEXT,
    mistake_tag_assigned TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX ix_reconciliation_discrepancies_run
    ON reconciliation_discrepancies (run_id);

CREATE INDEX ix_reconciliation_discrepancies_trade
    ON reconciliation_discrepancies (trade_id)
    WHERE trade_id IS NOT NULL;

CREATE INDEX ix_reconciliation_discrepancies_unresolved
    ON reconciliation_discrepancies (resolution)
    WHERE resolution = 'unresolved';

CREATE INDEX ix_reconciliation_discrepancies_material
    ON reconciliation_discrepancies (trade_id, material_to_review)
    WHERE material_to_review = 1 AND resolution = 'unresolved';

-- ============================================================================
-- §4. hypothesis_status_history table (7 columns) + 2 indexes + seed rows
-- ============================================================================

CREATE TABLE hypothesis_status_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    hypothesis_id INTEGER NOT NULL
        REFERENCES hypothesis_registry(id) ON DELETE CASCADE,
    status TEXT NOT NULL
        CHECK (status IN (
            'active', 'paused', 'closed-escaped', 'closed-target-met'
        )),
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    change_reason TEXT,
    recorded_at TEXT NOT NULL
);

CREATE INDEX ix_hypothesis_status_history_hyp
    ON hypothesis_status_history (hypothesis_id, effective_from);

-- Partial-unique: ONE current open-interval row per hypothesis.
CREATE UNIQUE INDEX ux_hypothesis_status_history_current
    ON hypothesis_status_history (hypothesis_id)
    WHERE effective_to IS NULL;

-- Seed: one open-interval row per existing hypothesis_registry row.
-- Per spec §3.4.1 R3 Major #2: effective_from = day-start anchor of the
-- registry's created_at (preserves chronology); recorded_at = migration
-- apply time. change_reason = NULL for seeds (no prior change).
INSERT INTO hypothesis_status_history (
    hypothesis_id, status, effective_from, effective_to,
    change_reason, recorded_at
)
SELECT
    id,
    status,
    strftime('%Y-%m-%dT00:00:00.000', created_at),
    NULL,
    NULL,
    strftime('%Y-%m-%dT%H:%M:%f', 'now')
FROM hypothesis_registry;

-- ============================================================================
-- §5. account_equity_snapshots table (8 columns) + 2 indexes
-- ============================================================================

CREATE TABLE account_equity_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,
    equity_dollars REAL NOT NULL CHECK (equity_dollars > 0),
    source TEXT NOT NULL
        CHECK (source IN ('manual', 'schwab_api', 'tos_csv')),
    source_artifact_path TEXT,
    recorded_at TEXT NOT NULL,
    recorded_by TEXT NOT NULL,
    notes TEXT
);

CREATE UNIQUE INDEX ux_account_equity_snapshots_date_source
    ON account_equity_snapshots (snapshot_date, source);

CREATE INDEX ix_account_equity_snapshots_date
    ON account_equity_snapshots (snapshot_date);

-- ============================================================================
-- §6. ALTER ADD COLUMNs on trades + review_log (no rebuild)
-- ============================================================================

ALTER TABLE trades ADD COLUMN risk_policy_id_at_lock INTEGER
    REFERENCES risk_policy(policy_id);

ALTER TABLE review_log ADD COLUMN risk_policy_id_at_review_completion INTEGER
    REFERENCES risk_policy(policy_id);

-- ============================================================================
-- §7. Schema version bump (LAST statement; Codex R1 Critical #1)
-- ============================================================================

UPDATE schema_version SET version = 17;
