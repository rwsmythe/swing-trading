-- 0021_phase13_t2_sb6c_trades_backlinks.sql
-- Phase 13 T2.SB6c — v21 migration: trades backlinks to candidates +
-- pattern_evaluations (closes T2.SB6b V1 simplifications #4 + #5 +
-- enables outcome bucketing per spec §5.10 lines 785-790 + line 775).
--
-- Atomic via explicit BEGIN ... COMMIT per CLAUDE.md gotcha
-- "executescript() implicit COMMIT" + migration 0020 precedent.
--
-- Schema deltas (declared order):
--   1. ALTER TABLE trades ADD COLUMN candidate_id INTEGER
--      REFERENCES candidates(id) ON DELETE SET NULL.
--   2. ALTER TABLE trades ADD COLUMN pattern_evaluation_id INTEGER
--      REFERENCES pattern_evaluations(id) ON DELETE SET NULL.
--   3. CREATE INDEX idx_trades_candidate_id ON trades(candidate_id).
--   4. CREATE INDEX idx_trades_pattern_evaluation_id
--      ON trades(pattern_evaluation_id).
--   5. UPDATE schema_version SET version = 21 (MUST be FINAL statement
--      before COMMIT; per Phase 9 §A.0 R1 Critical #1 precedent).
--
-- Bumps schema_version 20 -> 21.
--
-- Backfill semantics (OQ-1 LOCK): NULL for all pre-v21 existing rows.
-- No heuristic match — `manual_off_pipeline` trades legitimately have no
-- candidate_id; pre-T-A.6c.4 pipeline trades did not capture the anchor.
--
-- SQLite ALTER TABLE ADD COLUMN supports the REFERENCES clause for
-- newly-added columns. The FK is parsed + honored on subsequent
-- writes/deletes but is NOT enforced retroactively against existing
-- rows (NULL backfill satisfies any FK trivially).

BEGIN;

ALTER TABLE trades ADD COLUMN candidate_id INTEGER
    REFERENCES candidates(id) ON DELETE SET NULL;

ALTER TABLE trades ADD COLUMN pattern_evaluation_id INTEGER
    REFERENCES pattern_evaluations(id) ON DELETE SET NULL;

CREATE INDEX idx_trades_candidate_id ON trades(candidate_id);

CREATE INDEX idx_trades_pattern_evaluation_id
    ON trades(pattern_evaluation_id);

UPDATE schema_version SET version = 21;

COMMIT;
