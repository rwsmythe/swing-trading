-- Migration 0016: Phase 8 Daily_Management + MFE/MAE Precision Surface
--
-- 1. ALTER trades to add planned_target_R (single nullable column; no rebuild).
-- 2. CREATE TABLE daily_management_records (single-table-with-discriminator
--    per spec §3.2; 42 columns per spec §3.1).
-- 3. Indexes per spec §3.3 (4 indexes — 2 partial-unique + 2 lookup).
-- 4. Bump schema_version to 16.
--
-- Lesson inheritance:
--   - foreign_keys=OFF runner discipline (Phase 7 hotfix 283d4fa) — applies
--     globally; this migration does NOT trigger any rebuild but the runner
--     still toggles OFF/ON around executescript() per the binding discipline.
--   - executescript() partial-failure rollback wrapper (Phase 7 Sub-A R1 M3) —
--     in the runner; T1.1 has the discriminating test.
--   - Backup gate fires only on current_version == 15 AND target >= 16 (Phase 7
--     Sub-A code-review I1) — runner-level; backup filename
--     swing-pre-phase8-migration-<ISO>.db (§A.5).

-- ----- 1. ADD COLUMN planned_target_R on trades -----

ALTER TABLE trades ADD COLUMN planned_target_R REAL
    CHECK (planned_target_R IS NULL OR planned_target_R > 0);

-- ----- 2. CREATE TABLE daily_management_records -----

CREATE TABLE daily_management_records (
    -- Metadata (10 columns):
    management_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER NOT NULL
        REFERENCES trades(id) ON DELETE CASCADE,
    record_type TEXT NOT NULL
        CHECK (record_type IN ('daily_snapshot', 'event_log')),
    review_date TEXT NOT NULL,         -- ISO date YYYY-MM-DD; validator enforces format
    data_asof_session TEXT NOT NULL,   -- ISO date YYYY-MM-DD; for daily_snapshot must equal review_date
    created_at TEXT NOT NULL,          -- naive UTC ISO datetime; validator enforces
    mfe_mae_precision_level TEXT NOT NULL
        CHECK (mfe_mae_precision_level IN ('daily_approximate','intraday_estimated','intraday_exact')),
    pipeline_run_id INTEGER
        REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    is_superseded INTEGER NOT NULL DEFAULT 0
        CHECK (is_superseded IN (0,1)),
    superseded_by_record_id INTEGER
        REFERENCES daily_management_records(management_record_id) ON DELETE SET NULL,

    -- Position-state snapshot fields (14 columns; nullable on schema, validator-required for snapshot_emit):
    current_price REAL CHECK (current_price IS NULL OR current_price > 0),
    current_stop REAL CHECK (current_stop IS NULL OR current_stop > 0),
    current_size REAL CHECK (current_size IS NULL OR current_size >= 0),
    current_avg_cost REAL CHECK (current_avg_cost IS NULL OR current_avg_cost > 0),
    open_R_effective REAL,
    open_MFE_R_to_date REAL CHECK (open_MFE_R_to_date IS NULL OR open_MFE_R_to_date >= 0),
    open_MAE_R_to_date REAL CHECK (open_MAE_R_to_date IS NULL OR open_MAE_R_to_date >= 0),
    intraday_high REAL CHECK (intraday_high IS NULL OR intraday_high > 0),
    intraday_low REAL CHECK (intraday_low IS NULL OR intraday_low > 0),
    position_capital_utilization_pct REAL,
    position_capital_denominator_dollars REAL,
    position_portfolio_heat_contribution_dollars REAL
        CHECK (position_portfolio_heat_contribution_dollars IS NULL
               OR position_portfolio_heat_contribution_dollars >= 0),
    maturity_stage TEXT
        CHECK (maturity_stage IS NULL OR maturity_stage IN
               ('pre_+1.5R','+1.5R_to_+2R','>=+2R_trail_eligible')),
    trail_MA_candidate_price REAL
        CHECK (trail_MA_candidate_price IS NULL OR trail_MA_candidate_price > 0),

    -- Trail-MA period stamp (per-row stamp per spec §6.6):
    trail_MA_period_days INTEGER
        CHECK (trail_MA_period_days IS NULL OR trail_MA_period_days > 0),

    -- Trail-MA eligibility cached derivation:
    trail_MA_eligibility_flag INTEGER
        CHECK (trail_MA_eligibility_flag IS NULL OR trail_MA_eligibility_flag IN (0,1)),

    -- Operator-input fields (15 columns; required only for event_log per validator):
    thesis_status TEXT
        CHECK (thesis_status IS NULL OR thesis_status IN ('intact','weakening','invalidated')),
    prior_stop REAL CHECK (prior_stop IS NULL OR prior_stop > 0),
    new_stop REAL CHECK (new_stop IS NULL OR new_stop > 0),
    linked_trade_event_id INTEGER
        REFERENCES trade_events(id) ON DELETE SET NULL,
    stop_changed INTEGER
        CHECK (stop_changed IS NULL OR stop_changed IN (0,1)),
    stop_change_reason TEXT,
    volume_behavior TEXT
        CHECK (volume_behavior IS NULL OR volume_behavior IN
               ('confirming','neutral','distribution','fading')),
    relative_strength_status TEXT
        CHECK (relative_strength_status IS NULL OR relative_strength_status IN
               ('improving','flat','weakening')),
    market_regime_change INTEGER
        CHECK (market_regime_change IS NULL OR market_regime_change IN (0,1)),
    sector_condition_change INTEGER
        CHECK (sector_condition_change IS NULL OR sector_condition_change IN (0,1)),
    news_or_event_update TEXT,
    action_taken TEXT
        CHECK (action_taken IS NULL OR action_taken IN
               ('hold','trim','exit','stop','move_stop','no_action')),
    action_reason TEXT,
    emotional_state TEXT,             -- JSON-list-text; validation in service layer
    rule_violation_suspected INTEGER
        CHECK (rule_violation_suspected IS NULL OR rule_violation_suspected IN (0,1)),
    management_notes TEXT
);

-- ----- 3. Indexes -----

-- Active-snapshot uniqueness (predicate excludes superseded rows + event_log rows):
CREATE UNIQUE INDEX ux_daily_mgmt_snapshot_active_per_session
    ON daily_management_records (trade_id, data_asof_session)
    WHERE record_type = 'daily_snapshot' AND is_superseded = 0;

-- Per-precision uniqueness (idempotency key for tier-aware writes; covers all snapshot rows including superseded):
CREATE UNIQUE INDEX ux_daily_mgmt_snapshot_precision_per_session
    ON daily_management_records (trade_id, data_asof_session, mfe_mae_precision_level)
    WHERE record_type = 'daily_snapshot';

-- Timeline reads (per spec §7.2; cardinality at our scale ~ 2K rows/year — index trivial):
CREATE INDEX ix_daily_mgmt_trade_review
    ON daily_management_records (trade_id, review_date);

-- Pipeline-run traceability:
CREATE INDEX ix_daily_mgmt_pipeline_run
    ON daily_management_records (pipeline_run_id)
    WHERE pipeline_run_id IS NOT NULL;

-- ----- 4. Bump schema_version -----

UPDATE schema_version SET version = 16;
