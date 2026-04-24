-- Add a free-text `notes` column to `trade_events` so that stop-adjust events
-- can carry operator context alongside the required `rationale`. `trades.notes`
-- and `exits.notes` already exist on their entity rows; `stop_adjust` is the
-- only mutation that (until now) had no place to attach free-form notes, which
-- left the web/CLI surfaces asymmetric with entry/exit.

ALTER TABLE trade_events ADD COLUMN notes TEXT;

UPDATE schema_version SET version = 5;
