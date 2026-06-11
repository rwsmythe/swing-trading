-- Migration 0027 / v27: add the nullable, CHECK-constrained entry_intent TEXT
-- column to trades (tuition-vs-error instrument; design spec 2026-06-10).
-- A nullable ADD COLUMN whose CHECK references only the new column is a cheap,
-- NON-rebuild migration (same shape as 0024's failure_mode). Existing rows
-- backfill implicitly to NULL (operator-driven backfill is a separate CLI pass,
-- spec section 6). NULL = "unclassified" (a distinct third facet; NEVER coerced
-- to 'standard' -- spec L4 / section 3 corollary 3).
--
-- gotcha #9: explicit BEGIN; ... COMMIT; (executescript implicit-COMMIT
-- discipline). The runner's _apply_migration wraps this with rollback-on-error.
BEGIN;
ALTER TABLE trades ADD COLUMN entry_intent TEXT
    CHECK (entry_intent IS NULL OR entry_intent IN ('standard','hypothesis_test_by_design'));
UPDATE schema_version SET version = 27;
COMMIT;
