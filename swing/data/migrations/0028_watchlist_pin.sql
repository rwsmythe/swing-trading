-- Migration 0028: watchlist pin (Phase 16 / Arc 7). ADDITIVE columns only —
-- no table rewrite, no change to existing rows. Explicit BEGIN;...COMMIT; per
-- gotcha #9 (_apply_migration runs executescript in autocommit; 0023-0027 all wrap).
BEGIN;
ALTER TABLE watchlist ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0, 1));
ALTER TABLE watchlist ADD COLUMN pin_note TEXT;
ALTER TABLE watchlist ADD COLUMN pinned_at TEXT;
UPDATE schema_version SET version = 28;
COMMIT;
