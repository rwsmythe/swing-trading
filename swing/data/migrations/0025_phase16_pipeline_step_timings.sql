-- swing/data/migrations/0025_phase16_pipeline_step_timings.sql
-- Explicit BEGIN; ... COMMIT; per gotcha #9 (executescript implicit-COMMIT discipline),
-- mirroring 0023/0024. _apply_migration runs executescript in autocommit and does NOT
-- open its own BEGIN, so the in-file BEGIN/COMMIT is what makes a mid-script failure
-- atomically roll back. The runner additionally toggles foreign_keys OFF for the
-- duration + wraps the call in try/except rollback().
BEGIN;
CREATE TABLE pipeline_step_timings (
  id          INTEGER PRIMARY KEY,
  run_id      INTEGER NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
  ordinal     INTEGER NOT NULL,          -- 0-based monotonic open-order within the run
  step_name   TEXT    NOT NULL,          -- free-text; no CHECK enum (future steps need no schema change)
  started_ts  TEXT    NOT NULL,          -- wall-clock ISO seconds (_now_iso) at step open
  finished_ts TEXT    NOT NULL,          -- wall-clock ISO seconds at step close (flush closes before insert)
  duration_ms INTEGER NOT NULL,          -- monotonic-sourced, integer-truncated ms
  UNIQUE(run_id, ordinal)
);
-- No separate run_id index: UNIQUE(run_id, ordinal) already indexes run_id as the leading column.
UPDATE schema_version SET version = 25;
COMMIT;
