-- 0020_phase13_charts_patterns_autofill_usability.sql
-- Phase 13 T2.SB1 task T-A.1.1 — v20 single migration atomic landing.
--
-- Lands the Phase 13 4-theme arc schema substrate per spec §3 + §7.2:
--   - Theme 2 pattern recognition: pattern_exemplars + pattern_evaluations.
--   - Theme 1 chart rendering: chart_renders cache.
--   - Theme 3 auto-fill provenance: fills widening (fill_origin + audit cols);
--     review_log widening; schwab_api_calls.surface CHECK widening.
--   - Theme 4 Q4 close-tracking: watchlist_close_track_flags +
--     watchlist_close_track_flag_events.
--
-- Atomic via explicit BEGIN; ... COMMIT; per CLAUDE.md gotcha
-- "executescript() implicit COMMIT" + migration 0019 precedent.
-- Runner-level conn.rollback() can undo partial DDL only when the SQL itself
-- opens an explicit transaction.
--
-- Schema deltas (declared order):
--   1. CREATE TABLE pattern_exemplars (19 cols + 5 cross-column CHECKs
--      + 2 indexes). Self-FK on parent_exemplar_id ON DELETE RESTRICT per
--      Codex R6 M#2 closure.
--   2. CREATE TABLE chart_renders (9 cols + cross-column CHECK + 3 partial
--      unique indexes per spec §3.2 SQLite NULL-distinct defense).
--   3. CREATE TABLE pattern_evaluations (15 cols + 1 unique index +
--      FK pipeline_run_id CASCADE).
--   4. CREATE TABLE watchlist_close_track_flags (7 cols + partial unique
--      index on active flags only per spec §7.2 D-Q4.1 Codex R1 M#9 closure).
--   5. CREATE TABLE watchlist_close_track_flag_events (6 cols + FK flag_id
--      CASCADE).
--   6. Rebuild schwab_api_calls — widen `surface` CHECK 2 → 4 values
--      (add 'trade_entry' + 'trade_exit'); preserve all rows + all 4
--      existing indexes + all FKs.
--   7. ALTER TABLE fills ADD 4 columns:
--        - fill_origin TEXT NOT NULL DEFAULT 'operator_typed' (5-value CHECK).
--        - schwab_source_value_json TEXT NULL.
--        - operator_corrected_value_json TEXT NULL.
--        - auto_fill_audit_at TEXT NULL.
--      Backfill DEFAULT 'operator_typed' applies to all existing rows
--      transparently per SQLite semantics (per spec §6.4 + OQ-7 V1 simple).
--   8. ALTER TABLE review_log ADD 1 column:
--        - auto_populated_field_keys_json TEXT NULL.
--   9. UPDATE schema_version SET version = 20. MUST be FINAL statement
--      before COMMIT; per Phase 9 §A.0 R1 Critical #1 precedent.
--
-- Bumps schema_version 19 -> 20.

BEGIN;

-- ============================================================================
-- 1. pattern_exemplars (Theme 2 labeling library; spec §3.1)
--
-- 19 columns. ALL detector-class columns reference DETECTOR_PATTERN_CLASSES
-- per spec §3.0 LOCK ('vcp', 'flat_base', 'cup_with_handle',
-- 'high_tight_flag', 'double_bottom_w').
--
-- 5 numbered cross-column CHECK invariants per spec §3.1 (schema-defended;
-- Python-side __post_init__ validator mirrors per Phase 12 C.A T-A.2 LOCK):
--   #1 Relabel-vs-non-relabel coherence.
--   #2 Source-vs-decision matrix.
--   #3 parent_exemplar_id linkage (codex_silver requires parent; others NULL).
--   #4 geometric_score_json nullability per label_source.
--   #5 labeler_evidence_json source coherence.
-- ============================================================================

CREATE TABLE pattern_exemplars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    timeframe TEXT NOT NULL CHECK (timeframe IN ('daily', 'weekly')),
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    proposed_pattern_class TEXT NOT NULL CHECK (proposed_pattern_class IN (
        'vcp', 'flat_base', 'cup_with_handle',
        'high_tight_flag', 'double_bottom_w'
    )),
    final_decision TEXT NOT NULL CHECK (final_decision IN (
        'confirmed', 'watch', 'rejected', 'relabeled', 'generated'
    )),
    final_pattern_class TEXT CHECK (
        final_pattern_class IS NULL OR final_pattern_class IN (
            'vcp', 'flat_base', 'cup_with_handle',
            'high_tight_flag', 'double_bottom_w'
        )
    ),
    label_source TEXT NOT NULL CHECK (label_source IN (
        'curated_gold', 'claude_silver', 'codex_silver',
        'closed_loop_review', 'organic_trade_history',
        'synthetic', 'perturbation'
    )),
    ai_labeler_version TEXT,
    gold_validated_at TEXT,
    codex_reviewed INTEGER NOT NULL DEFAULT 0 CHECK (codex_reviewed IN (0, 1)),
    codex_agreement INTEGER CHECK (
        codex_agreement IS NULL OR codex_agreement IN (0, 1)
    ),
    geometric_score_json TEXT,
    labeler_evidence_json TEXT,
    structural_evidence_json TEXT NOT NULL,
    quality_grade INTEGER CHECK (
        quality_grade IS NULL OR quality_grade BETWEEN 1 AND 5
    ),
    notes TEXT,
    parent_exemplar_id INTEGER
        REFERENCES pattern_exemplars(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL CHECK (created_by IN (
        'operator', 'claude_dispatch', 'codex_dispatch', 'synthetic_generator'
    )),

    -- Invariant #1: relabel-vs-non-relabel coherence (spec §3.1).
    CHECK (
        (final_decision = 'relabeled'
            AND final_pattern_class IS NOT NULL
            AND final_pattern_class != proposed_pattern_class)
        OR (final_decision != 'relabeled' AND final_pattern_class IS NULL)
    ),

    -- Invariant #2: source-vs-decision matrix (spec §3.1).
    CHECK (
        (label_source = 'curated_gold' AND final_decision = 'confirmed')
        OR (label_source IN (
                'claude_silver', 'codex_silver',
                'closed_loop_review', 'organic_trade_history'
            )
            AND final_decision IN (
                'confirmed', 'watch', 'rejected', 'relabeled'
            ))
        OR (label_source IN ('synthetic', 'perturbation')
            AND final_decision = 'generated')
    ),

    -- Invariant #3: parent_exemplar_id linkage (Codex R5 M#2 + R6 M#2).
    CHECK (
        (label_source = 'codex_silver' AND parent_exemplar_id IS NOT NULL)
        OR (label_source != 'codex_silver' AND parent_exemplar_id IS NULL)
    ),

    -- Invariant #4: geometric_score_json nullability (Codex R6 m#2).
    CHECK (
        (geometric_score_json IS NULL
            AND (label_source IN ('claude_silver', 'codex_silver')
                OR (label_source = 'curated_gold'
                    AND labeler_evidence_json IS NOT NULL)))
        OR (geometric_score_json IS NOT NULL
            AND label_source IN (
                'curated_gold', 'closed_loop_review',
                'organic_trade_history', 'synthetic', 'perturbation'
            ))
    ),

    -- Invariant #5: labeler_evidence_json source coherence (Codex R6 M#1).
    CHECK (
        (labeler_evidence_json IS NOT NULL
            AND label_source IN (
                'claude_silver', 'codex_silver', 'curated_gold'
            ))
        OR (labeler_evidence_json IS NULL
            AND label_source IN (
                'closed_loop_review', 'organic_trade_history',
                'synthetic', 'perturbation'
            ))
    )
);

CREATE INDEX ix_pattern_exemplars_proposed_class_source
    ON pattern_exemplars(proposed_pattern_class, label_source);

CREATE INDEX ix_pattern_exemplars_ticker_start_date
    ON pattern_exemplars(ticker, start_date);

-- ============================================================================
-- 2. chart_renders (Theme 1 cache; spec §3.2)
--
-- 9 columns + 1 cross-column CHECK + 3 partial unique indexes (per Codex R1
-- M#3 closure SQLite NULL-distinct semantics defense).
-- ============================================================================

CREATE TABLE chart_renders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    surface TEXT NOT NULL CHECK (surface IN (
        'watchlist_row', 'hyprec_detail', 'position_detail',
        'market_weather', 'theme2_annotated'
    )),
    pipeline_run_id INTEGER
        REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    pattern_class TEXT CHECK (
        pattern_class IS NULL OR pattern_class IN (
            'vcp', 'flat_base', 'cup_with_handle',
            'high_tight_flag', 'double_bottom_w'
        )
    ),
    chart_svg_bytes BLOB NOT NULL,
    source_data_hash TEXT NOT NULL,
    rendered_at TEXT NOT NULL,
    data_asof_date TEXT NOT NULL,

    -- Cross-column CHECK: theme2_annotated requires both pattern_class +
    -- pipeline_run_id non-NULL; all other surfaces require pattern_class NULL.
    -- Closes Codex R2 M#5 (partial-index predicate also requires
    -- pipeline_run_id IS NOT NULL for theme2_annotated).
    CHECK (
        (surface = 'theme2_annotated'
            AND pattern_class IS NOT NULL
            AND pipeline_run_id IS NOT NULL)
        OR (surface != 'theme2_annotated' AND pattern_class IS NULL)
    )
);

-- Partial unique index #1: run-bound cache rows (watchlist/hyprec/market_weather).
CREATE UNIQUE INDEX idx_chart_renders_run_bound
    ON chart_renders(ticker, surface, pipeline_run_id)
    WHERE pipeline_run_id IS NOT NULL AND surface != 'theme2_annotated';

-- Partial unique index #2: position_detail (NULL pipeline_run_id; one per ticker).
CREATE UNIQUE INDEX idx_chart_renders_position_detail
    ON chart_renders(ticker, surface)
    WHERE pipeline_run_id IS NULL AND surface = 'position_detail';

-- Partial unique index #3: theme2_annotated (pattern_class + pipeline_run_id).
CREATE UNIQUE INDEX idx_chart_renders_theme2_annotated
    ON chart_renders(ticker, surface, pipeline_run_id, pattern_class)
    WHERE surface = 'theme2_annotated' AND pipeline_run_id IS NOT NULL;

-- ============================================================================
-- 3. pattern_evaluations (Theme 2 detector run output cache; spec §3.3)
--
-- 15 columns. One verdict per (pipeline_run_id, ticker, pattern_class).
-- FK pipeline_run_id ON DELETE CASCADE — verdict tied to one run.
-- ============================================================================

CREATE TABLE pattern_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_run_id INTEGER NOT NULL
        REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    pattern_class TEXT NOT NULL CHECK (pattern_class IN (
        'vcp', 'flat_base', 'cup_with_handle',
        'high_tight_flag', 'double_bottom_w'
    )),
    detector_version TEXT NOT NULL,
    geometric_score REAL NOT NULL,
    geometric_score_json TEXT NOT NULL,
    template_match_score REAL,
    template_match_nearest_exemplar_ids_json TEXT,
    composite_score REAL NOT NULL,
    structural_evidence_json TEXT NOT NULL,
    feature_distribution_log_json TEXT NOT NULL,
    window_start_date TEXT NOT NULL,
    window_end_date TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Unique index: one verdict per pattern per ticker per run.
CREATE UNIQUE INDEX idx_pattern_evaluations_run_ticker_class
    ON pattern_evaluations(pipeline_run_id, ticker, pattern_class);

-- ============================================================================
-- 4. watchlist_close_track_flags (Theme 4 Q4; spec §7.2 D-Q4.1)
--
-- 7 columns. Partial unique index on ACTIVE flags only (closes Codex R1 M#9):
-- re-flagging a previously-cleared ticker INSERTs a new lifecycle row.
-- ============================================================================

CREATE TABLE watchlist_close_track_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    flagged_at TEXT NOT NULL,
    flagged_by_surface TEXT NOT NULL CHECK (flagged_by_surface IN (
        'web', 'cli'
    )),
    reason_text TEXT,
    cleared_at TEXT,
    cleared_reason TEXT CHECK (
        cleared_reason IS NULL OR cleared_reason IN (
            'operator_cleared', 'auto_cleared_on_position_open'
        )
    ),

    -- Cross-column CHECK: cleared_reason set iff cleared_at set.
    CHECK (
        (cleared_at IS NULL AND cleared_reason IS NULL)
        OR (cleared_at IS NOT NULL AND cleared_reason IS NOT NULL)
    )
);

-- Partial unique index: at most one ACTIVE flag per ticker (Codex R1 M#9).
CREATE UNIQUE INDEX idx_wclf_active_ticker
    ON watchlist_close_track_flags(ticker)
    WHERE cleared_at IS NULL;

-- ============================================================================
-- 5. watchlist_close_track_flag_events (Theme 4 Q4 audit; spec §7.2 D-Q4.7)
--
-- 6 columns. Append-only per-event audit (set / clear). FK flag_id CASCADE.
-- ============================================================================

CREATE TABLE watchlist_close_track_flag_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flag_id INTEGER NOT NULL
        REFERENCES watchlist_close_track_flags(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (event_type IN ('set', 'clear')),
    event_at TEXT NOT NULL,
    surface TEXT NOT NULL CHECK (surface IN ('web', 'cli')),
    reason_text TEXT
);

CREATE INDEX ix_watchlist_close_track_flag_events_flag_id
    ON watchlist_close_track_flag_events(flag_id, event_at);

-- ============================================================================
-- 6. schwab_api_calls rebuild — widen `surface` CHECK 2 → 4 values
--    (add 'trade_entry' + 'trade_exit' per Theme 3 §6.4 + §B.4 #5).
--    Preserve all rows + all 4 existing indexes + all FKs (3 forward FKs +
--    1 from reconciliation_runs.schwab_api_call_id).
-- ============================================================================

CREATE TABLE schwab_api_calls_new (
    call_id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                            TEXT NOT NULL,
    endpoint                      TEXT NOT NULL,
    http_status                   INTEGER,
    response_time_ms              INTEGER,
    rate_limit_remaining          INTEGER,
    signature_hash                TEXT,
    status                        TEXT NOT NULL,
    error_message                 TEXT,
    linked_snapshot_id            INTEGER,
    linked_reconciliation_run_id  INTEGER,
    pipeline_run_id               INTEGER,
    surface                       TEXT NOT NULL,
    environment                   TEXT NOT NULL,
    linked_correction_id          INTEGER,

    CHECK (status IN (
        'in_flight', 'success', 'error',
        'auth_failed', 'rate_limited', 'concurrent_refresh'
    )),
    -- Widened CHECK: add 'trade_entry' + 'trade_exit' (Theme 3 §6.4).
    CHECK (surface IN ('pipeline', 'cli', 'trade_entry', 'trade_exit')),
    CHECK (environment IN ('sandbox', 'production')),
    CHECK (endpoint IN (
        'oauth.code_exchange', 'oauth.refresh', 'oauth.revoke',
        'accounts.linked', 'accounts.details',
        'accounts.orders.list', 'accounts.transactions.list',
        'marketdata.quotes', 'marketdata.pricehistory'
    )),

    FOREIGN KEY (linked_snapshot_id)
        REFERENCES account_equity_snapshots(snapshot_id)
        ON DELETE SET NULL,
    FOREIGN KEY (linked_reconciliation_run_id)
        REFERENCES reconciliation_runs(run_id)
        ON DELETE SET NULL,
    FOREIGN KEY (pipeline_run_id)
        REFERENCES pipeline_runs(id)
        ON DELETE SET NULL,
    FOREIGN KEY (linked_correction_id)
        REFERENCES reconciliation_corrections(correction_id)
        ON DELETE SET NULL
);

INSERT INTO schwab_api_calls_new (
    call_id, ts, endpoint, http_status, response_time_ms,
    rate_limit_remaining, signature_hash, status, error_message,
    linked_snapshot_id, linked_reconciliation_run_id, pipeline_run_id,
    surface, environment, linked_correction_id
)
SELECT
    call_id, ts, endpoint, http_status, response_time_ms,
    rate_limit_remaining, signature_hash, status, error_message,
    linked_snapshot_id, linked_reconciliation_run_id, pipeline_run_id,
    surface, environment, linked_correction_id
FROM schwab_api_calls;

DROP TABLE schwab_api_calls;
ALTER TABLE schwab_api_calls_new RENAME TO schwab_api_calls;

CREATE INDEX ix_schwab_api_calls_ts
    ON schwab_api_calls(ts);

CREATE INDEX ix_schwab_api_calls_status_ts
    ON schwab_api_calls(status, ts);

CREATE INDEX ix_schwab_api_calls_pipeline_run_id_ts
    ON schwab_api_calls(pipeline_run_id, ts);

CREATE INDEX ix_schwab_api_calls_surface_ts
    ON schwab_api_calls(surface, ts);

-- ============================================================================
-- 7. fills widening — add 4 columns (Theme 3 §6.4 + spec §3.4).
--    fill_origin DEFAULT 'operator_typed' backfills existing rows per OQ-7 V1.
-- ============================================================================

ALTER TABLE fills ADD COLUMN fill_origin TEXT NOT NULL DEFAULT 'operator_typed'
    CHECK (fill_origin IN (
        'operator_typed', 'schwab_auto',
        'schwab_auto_then_operator_corrected', 'tos_import', 'imported_legacy'
    ));

ALTER TABLE fills ADD COLUMN schwab_source_value_json TEXT;

ALTER TABLE fills ADD COLUMN operator_corrected_value_json TEXT;

ALTER TABLE fills ADD COLUMN auto_fill_audit_at TEXT;

-- ============================================================================
-- 8. review_log widening — add 1 column (Theme 3 §6.3 + spec §3.4).
-- ============================================================================

ALTER TABLE review_log ADD COLUMN auto_populated_field_keys_json TEXT;

-- ============================================================================
-- 9. Schema version bump — MUST be final statement before COMMIT
--    per Phase 9 §A.0 R1 Critical #1 precedent.
-- ============================================================================

UPDATE schema_version SET version = 20;

COMMIT;
