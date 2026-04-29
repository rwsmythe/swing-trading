-- Migration 0012: capture Finviz Sector + Industry on candidates + trades.
--
-- Both columns are already validated by `swing/pipeline/finviz_schema.py`'s
-- REQUIRED_COLUMNS (ingested but discarded pre-this-migration). This migration
-- closes the gap: candidates carry the per-pipeline-run snapshot; trades
-- freeze the value at entry-time per the snapshot-at-entry-surface pattern
-- (precedents: hypothesis_label / migration 0007; chart_pattern_* / 0010).
--
-- Additive only: NOT NULL DEFAULT '' so historical rows pre-migration get
-- empty strings rather than NULL; this preserves any future query that
-- filters on `sector != ''` from accidentally matching backfilled rows
-- and avoids NULL-handling at every read site. ALTER TABLE ADD COLUMN with
-- a constant DEFAULT is O(metadata) on SQLite (no row rewrite).
--
-- No cross-column invariants in V1 (unlike chart_pattern_*'s 4 invariants):
-- sector + industry are independent free-text descriptors. V1 trusts Finviz
-- as source of truth; future V2 may add concentration constraints but not
-- field-format invariants.

ALTER TABLE candidates ADD COLUMN sector TEXT NOT NULL DEFAULT '';
ALTER TABLE candidates ADD COLUMN industry TEXT NOT NULL DEFAULT '';

ALTER TABLE trades ADD COLUMN sector TEXT NOT NULL DEFAULT '';
ALTER TABLE trades ADD COLUMN industry TEXT NOT NULL DEFAULT '';

UPDATE schema_version SET version = 12;
