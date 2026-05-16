-- 0019_phase12_bundle_c_auto_correct_reconciliation.sql
-- Phase 12 Sub-bundle C Sub-sub-bundle C.A — auto-correct reconciliation foundation.
-- Lands the schema deltas backing the three-tier resolution model
-- (tier 1 unambiguous auto-correct / tier 2 ambiguity surfaced / tier 3 operator
-- override) per spec §3.8 ordered declaration.
--
-- Atomic via explicit BEGIN; ... COMMIT; per CLAUDE.md gotcha
-- "executescript() implicit COMMIT" + migration 0018 precedent.
-- Runner-level conn.rollback() can undo partial DDL only when the SQL itself
-- opens an explicit transaction.
--
-- Schema deltas (spec §3.8 declared order):
--   1. CREATE TABLE reconciliation_corrections (20 cols + 4 indexes).
--   2. Rebuild reconciliation_discrepancies — widen `resolution` CHECK
--      5 → 9 values; add new nullable `ambiguity_kind` column with 7-value
--      CHECK enum; add cross-column CHECK pinning resolution/ambiguity_kind
--      consistency; preserve all existing rows + 4 existing indexes;
--      add new partial index ix_..._pending_ambiguity.
--   3. ALTER review_log ADD COLUMN superseded_by_correction_id (nullable FK).
--   4. ALTER schwab_api_calls ADD COLUMN linked_correction_id (nullable FK).
--      Codex R1 Minor #2 fix: this step lands BEFORE the trade_events rebuild
--      per spec §11.2 declared order.
--   5. Rebuild trade_events — widen `event_type` CHECK 6 → 7 values
--      (add 'reconciliation_auto_correct'); preserve rows + index.
--   6. UPDATE schema_version SET version = 19. MUST be the FINAL statement
--      before COMMIT; per Phase 9 §A.0 R1 Critical #1 precedent.
--
-- Bumps schema_version 18 -> 19.

BEGIN;

-- ============================================================================
-- 1. reconciliation_corrections audit table (20 columns + 4 indexes).
--    Spec §3.1 header says "19 columns" but enumerated rows are 20 — banked
--    as V2.1 §VII.F amendment candidate (§I.16 in the plan); plan §B.1
--    acceptance criterion #3 LOCKS 20.
-- ============================================================================

CREATE TABLE reconciliation_corrections (
    correction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    discrepancy_id INTEGER NOT NULL
        REFERENCES reconciliation_discrepancies(discrepancy_id)
        ON DELETE CASCADE,
    correction_action TEXT NOT NULL CHECK (correction_action IN (
        'auto_applied', 'operator_resolved_ambiguity', 'operator_overridden'
    )),
    correction_choice TEXT,
    affected_table TEXT NOT NULL CHECK (affected_table IN (
        'fills', 'trades', 'cash_movements', 'account_equity_snapshots'
    )),
    affected_row_id INTEGER NOT NULL,
    field_name TEXT NOT NULL,
    pre_correction_value_json TEXT NOT NULL,
    source_canonical_value_json TEXT,
    applied_value_json TEXT NOT NULL,
    operator_truth_value_json TEXT,
    applied_at TEXT NOT NULL,
    applied_by TEXT NOT NULL CHECK (applied_by IN ('auto', 'operator')),
    correction_set_id INTEGER,
    superseded_by_correction_id INTEGER
        REFERENCES reconciliation_corrections(correction_id) ON DELETE SET NULL,
    risk_policy_id_at_correction INTEGER
        REFERENCES risk_policy(policy_id) ON DELETE SET NULL,
    schwab_api_call_id INTEGER
        REFERENCES schwab_api_calls(call_id) ON DELETE SET NULL,
    reconciliation_run_id INTEGER NOT NULL
        REFERENCES reconciliation_runs(run_id) ON DELETE CASCADE,
    correction_reason TEXT,
    notes TEXT
);

CREATE INDEX ix_reconciliation_corrections_discrepancy
    ON reconciliation_corrections(discrepancy_id, applied_at);
CREATE INDEX ix_reconciliation_corrections_affected_row
    ON reconciliation_corrections(affected_table, affected_row_id, applied_at);
CREATE INDEX ix_reconciliation_corrections_run
    ON reconciliation_corrections(reconciliation_run_id);
CREATE INDEX ix_reconciliation_corrections_action
    ON reconciliation_corrections(correction_action, applied_at);

-- ============================================================================
-- 2. reconciliation_discrepancies rebuild
--    - widen `resolution` CHECK enum 5 → 9 (5 existing per §A.7.1 preserved
--      verbatim + 4 new: 'auto_corrected_from_schwab',
--      'pending_ambiguity_resolution', 'operator_resolved_ambiguity',
--      'operator_overridden').
--    - add NEW nullable `ambiguity_kind` column with 7-value CHECK enum.
--    - add bidirectional cross-column CHECK enforcing pairing between
--      `resolution` and `ambiguity_kind`.
--    - preserve all existing rows via INSERT-SELECT; `ambiguity_kind` is NULL
--      for all copied rows.
--    - preserve all 4 existing indexes + create new
--      ix_reconciliation_discrepancies_pending_ambiguity partial index.
-- ============================================================================

CREATE TABLE reconciliation_discrepancies_new (
    discrepancy_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL
        REFERENCES reconciliation_runs(run_id) ON DELETE CASCADE,
    discrepancy_type TEXT NOT NULL CHECK (discrepancy_type IN (
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
    resolution TEXT NOT NULL CHECK (resolution IN (
        'journal_corrected', 'source_treated_canonical',
        'manual_override', 'unresolved', 'acknowledged_immaterial',
        'auto_corrected_from_schwab', 'pending_ambiguity_resolution',
        'operator_resolved_ambiguity', 'operator_overridden'
    )) DEFAULT 'unresolved',
    ambiguity_kind TEXT CHECK (ambiguity_kind IS NULL OR ambiguity_kind IN (
        'multi_partial_vs_consolidated', 'multi_match_within_window',
        'unknown_schwab_subtype', 'field_shape_incompatible',
        'schwab_returned_no_match', 'validator_rejected', 'unsupported'
    )),
    resolution_reason TEXT,
    resolved_at TEXT,
    resolved_by TEXT,
    mistake_tag_assigned TEXT,
    created_at TEXT NOT NULL,
    CHECK (
        (ambiguity_kind IS NULL
            AND resolution NOT IN (
                'pending_ambiguity_resolution',
                'operator_resolved_ambiguity'
            ))
        OR
        (ambiguity_kind IS NOT NULL
            AND resolution IN (
                'pending_ambiguity_resolution',
                'operator_resolved_ambiguity'
            ))
    )
);

INSERT INTO reconciliation_discrepancies_new (
    discrepancy_id, run_id, discrepancy_type, trade_id, fill_id,
    cash_movement_id, linked_daily_management_record_id, ticker,
    field_name, expected_value_json, actual_value_json, delta_text,
    material_to_review, resolution, ambiguity_kind, resolution_reason,
    resolved_at, resolved_by, mistake_tag_assigned, created_at
)
SELECT
    discrepancy_id, run_id, discrepancy_type, trade_id, fill_id,
    cash_movement_id, linked_daily_management_record_id, ticker,
    field_name, expected_value_json, actual_value_json, delta_text,
    material_to_review, resolution, NULL, resolution_reason,
    resolved_at, resolved_by, mistake_tag_assigned, created_at
FROM reconciliation_discrepancies;

DROP TABLE reconciliation_discrepancies;
ALTER TABLE reconciliation_discrepancies_new
    RENAME TO reconciliation_discrepancies;

CREATE INDEX ix_reconciliation_discrepancies_run
    ON reconciliation_discrepancies(run_id);
CREATE INDEX ix_reconciliation_discrepancies_trade
    ON reconciliation_discrepancies(trade_id)
    WHERE trade_id IS NOT NULL;
CREATE INDEX ix_reconciliation_discrepancies_unresolved
    ON reconciliation_discrepancies(resolution)
    WHERE resolution = 'unresolved';
CREATE INDEX ix_reconciliation_discrepancies_material
    ON reconciliation_discrepancies(trade_id, material_to_review)
    WHERE material_to_review = 1 AND resolution = 'unresolved';
CREATE INDEX ix_reconciliation_discrepancies_pending_ambiguity
    ON reconciliation_discrepancies(ambiguity_kind, created_at)
    WHERE resolution = 'pending_ambiguity_resolution';

-- ============================================================================
-- 3. review_log column add (spec §11.2 step 4).
--    Nullable FK to reconciliation_corrections(correction_id) ON DELETE SET NULL.
-- ============================================================================

ALTER TABLE review_log
    ADD COLUMN superseded_by_correction_id INTEGER
        REFERENCES reconciliation_corrections(correction_id) ON DELETE SET NULL;

-- ============================================================================
-- 4. schwab_api_calls column add (spec §11.2 step 5).
--    Codex R1 Minor #2 fix: moved BEFORE trade_events rebuild to match spec
--    §11.2 declared order.
-- ============================================================================

ALTER TABLE schwab_api_calls
    ADD COLUMN linked_correction_id INTEGER
        REFERENCES reconciliation_corrections(correction_id) ON DELETE SET NULL;

-- ============================================================================
-- 5. trade_events rebuild (spec §11.2 step 6).
--    Widen `event_type` CHECK enum 6 → 7 values; preserve all rows; recreate
--    the ix_trade_events_trade index.
-- ============================================================================

CREATE TABLE trade_events_new (
    id INTEGER PRIMARY KEY,
    trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
    ts TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'entry', 'stop_adjust', 'note', 'exit', 'flag', 'pre_trade_edit',
        'reconciliation_auto_correct'
    )),
    payload_json TEXT,
    rationale TEXT,
    notes TEXT
);

INSERT INTO trade_events_new (
    id, trade_id, ts, event_type, payload_json, rationale, notes
)
SELECT
    id, trade_id, ts, event_type, payload_json, rationale, notes
FROM trade_events;

DROP TABLE trade_events;
ALTER TABLE trade_events_new RENAME TO trade_events;

CREATE INDEX ix_trade_events_trade ON trade_events(trade_id, ts);

-- ============================================================================
-- 6. Schema version bump.
--    MUST be the FINAL statement before COMMIT per Phase 9 §A.0 R1 Critical
--    #1 precedent (truncated transaction would leave version stamp ahead of
--    schema).
-- ============================================================================

UPDATE schema_version SET version = 19;

COMMIT;
