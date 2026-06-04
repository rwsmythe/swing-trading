-- Phase 15 B-7 (operator failure-mode classification) migration 0024 / v24:
-- add the nullable, CHECK-constrained failure_mode TEXT column to trades.
-- A nullable ADD COLUMN whose CHECK references only the new column is a cheap,
-- NON-rebuild migration (contrast 0023's chart_renders rebuild, forced by an
-- enum-VALUE rename of an existing column). Existing rows backfill implicitly to
-- NULL (OQ-6 forward-only). NULL = "no failure attributed" (winner or
-- unclassified loss) -- NOT a vocabulary token.
--
-- gotcha #9: explicit BEGIN; ... COMMIT; (executescript implicit-COMMIT
-- discipline). The runner's _apply_migration wraps this in try/except with
-- rollback on any mid-script failure.
BEGIN;
ALTER TABLE trades ADD COLUMN failure_mode TEXT
    CHECK (failure_mode IS NULL OR failure_mode IN (
        'thesis_invalidated', 'normal_volatility_stop', 'market_regime_shift',
        'adverse_event_shock', 'execution_error', 'failed_to_advance', 'other'
    ));
UPDATE schema_version SET version = 24;
COMMIT;
