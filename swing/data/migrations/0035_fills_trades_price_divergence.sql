-- 0035_fills_trades_price_divergence.sql
-- Phase 21 boundary wave, item 5 (A-4) — a first-class
-- `fills_trades_price_divergence` discrepancy type.
--
-- Widen the reconciliation_discrepancies.discrepancy_type CHECK enum 11 -> 12.
--
-- WHAT THE TYPE IS. The 20-A A-5 fills<->trades consistency invariant compares
-- a trade's entry-fill VWAP against `trades.entry_price` and emits a MATERIAL
-- diagnostic when they disagree beyond display precision. The shipped no-schema
-- approximation (A4-i) emits it as `entry_price_mismatch` with
-- `field_name='internal_consistency'` and an `actual_value_json` discriminator,
-- because the taxonomy had no word for a fills-vs-trades PRICE divergence
-- internal to the journal. This migration gives it its own word (A4-iii).
--
-- WHAT IT IS NOT. It is NOT a broker-vs-journal DATE divergence. The live
-- evidence that motivated the rider — discrepancy 95, an `entry_price_mismatch`
-- whose prices agree to four decimals ($+0.0000) while the DATES disagree by
-- six sessions — is evidence for the CLASS (the taxonomy is too coarse and
-- forces true findings through wrong words), not an instance of THIS type. It
-- stays an `entry_price_mismatch` row after this migration, and it is closed by
-- correcting the journal, not by retyping it. A `entry_date_mismatch` type
-- would be mechanically free to add in this same rebuild and is deliberately
-- NOT added: it is new ruled content, posed rather than built.
--
-- SQLite cannot ALTER a CHECK constraint -> table-rebuild following the
-- 0031/0019 pattern (_new table + INSERT-SELECT copy + DROP + RENAME). EVERY
-- column, index (incl. the pending_ambiguity partial index), FK, and the
-- cross-column resolution/ambiguity_kind CHECK of the CURRENT (post-0031)
-- table is preserved verbatim; only the discrepancy_type enum gains one value.
-- The current definition was read back off `ensure_schema` HEAD before writing
-- this file rather than copied from 0031 on faith — they agree, because no
-- migration between 0031 and 0034 touched this table.
--
-- Atomic via explicit BEGIN; ... COMMIT; per CLAUDE.md gotcha #9
-- ("executescript() implicit COMMIT"). The runner's _apply_migration wraps in
-- try/except + holds foreign_keys=OFF so the rebuild does NOT cascade-null
-- child rows referencing reconciliation_discrepancies(discrepancy_id) (the
-- reconciliation_corrections FK) during the DROP.
--
-- Bumps schema_version 34 -> 35.

BEGIN;

-- ============================================================================
-- reconciliation_discrepancies rebuild — widen discrepancy_type CHECK 11 -> 12.
--   Add 'fills_trades_price_divergence'. Everything else copied verbatim from
--   the current (0031) definition: all columns, the resolution 9-value CHECK,
--   the ambiguity_kind 7-value CHECK, the cross-column pairing CHECK, all 5
--   indexes, and all FKs.
-- ============================================================================

CREATE TABLE reconciliation_discrepancies_new (
    discrepancy_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL
        REFERENCES reconciliation_runs(run_id) ON DELETE CASCADE,
    discrepancy_type TEXT NOT NULL CHECK (discrepancy_type IN (
        'close_price_mismatch', 'stop_mismatch', 'position_qty_mismatch',
        'cash_movement_mismatch', 'sector_tamper', 'snapshot_mismatch',
        'unmatched_open_fill', 'unmatched_close_fill',
        'entry_price_mismatch', 'equity_delta',
        'untracked_broker_position',
        'fills_trades_price_divergence'
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
    material_to_review, resolution, ambiguity_kind, resolution_reason,
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
-- Schema version bump. MUST be the FINAL statement before COMMIT per the
-- Phase 9 §A.0 R1 Critical #1 precedent (a truncated transaction would leave
-- the version stamp ahead of the schema).
-- ============================================================================

UPDATE schema_version SET version = 35;

COMMIT;
