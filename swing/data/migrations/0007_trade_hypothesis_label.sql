-- Add a free-text `hypothesis_label` column to `trades` so the operator-recorded
-- pre-trade hypothesis (e.g. "Sub-A+ candidate meeting TT + price threshold",
-- "A+ except risk_feasibility, smaller position than standard") rides alongside
-- every trade entry. The label is captured at trade-entry time and FROZEN — the
-- operational branch's evidence-generation framing depends on the same anti-
-- rationalization discipline as research-study pre-registration (no outcome-
-- driven re-labeling).
--
-- Additive only: the column is nullable with no default, so existing rows
-- (e.g. the historical VIS trade) get NULL on upgrade. SQLite's
-- ALTER TABLE ADD COLUMN does not rewrite the table for nullable columns
-- without defaults, so the migration is O(metadata) regardless of row count.
--
-- Free text by design: per operator confirmation 2026-04-25, hypothesis classes
-- have not yet stabilized; controlled-vocabulary enum is deferred until 5+
-- labeled trades reveal the natural categories.

ALTER TABLE trades ADD COLUMN hypothesis_label TEXT;

UPDATE schema_version SET version = 7;
