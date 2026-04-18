-- Per-run traceability: record the RS universe version + file hash that
-- produced each evaluation run. Nullable for runs recorded before this migration.

ALTER TABLE evaluation_runs ADD COLUMN rs_universe_version TEXT;
ALTER TABLE evaluation_runs ADD COLUMN rs_universe_hash TEXT;

UPDATE schema_version SET version = 2;
