-- Hypothesis registry — pre-registered investigation plan v0.1.
--
-- Per `docs/hypothesis-recommendation-backend-brief.md` §4.1, the operator's
-- evidence-generation framing depends on the SAME anti-rationalization
-- discipline as research-study pre-registration: the four hypotheses below,
-- their target sample sizes, and tripwire thresholds are FROZEN at this
-- migration. CLI mutations may flip `status` (and record the reason) but
-- cannot edit `target_sample_size`, `consecutive_loss_tripwire`,
-- `absolute_loss_tripwire_pct`, or `decision_criteria`. A formal amendment
-- requires a NEW migration with an explicit version bump (signaling the
-- change passed through the source-of-truth correction protocol, V2.1
-- §VII.F), not an in-place UPDATE.
--
-- Additive only: this migration introduces a new table; no ALTER on
-- existing tables. `ensure_schema` is the SANCTIONED path — it gates on
-- schema_version and only runs this script when the DB is at v7. INSERT
-- OR IGNORE on the seed rows is keyed on the UNIQUE `name` column for
-- the path where ensure_schema applies the migration once and then later
-- code paths re-touch the same connection. Adversarial review R2 Major 1:
-- earlier "defense in depth" CREATE TABLE IF NOT EXISTS was reverted —
-- it would have silently blessed a stale/malformed pre-existing table as
-- v8 without verifying schema match. Plain CREATE TABLE errors out hard
-- on accidental manual rerun, which is the right signal.

CREATE TABLE hypothesis_registry (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  statement TEXT NOT NULL,
  target_sample_size INTEGER NOT NULL CHECK (target_sample_size > 0),
  decision_criteria TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'paused', 'closed-escaped', 'closed-target-met')),
  consecutive_loss_tripwire INTEGER NOT NULL CHECK (consecutive_loss_tripwire > 0),
  absolute_loss_tripwire_pct REAL NOT NULL CHECK (absolute_loss_tripwire_pct > 0),
  created_at TEXT NOT NULL,
  status_changed_at TEXT,
  status_change_reason TEXT,
  -- notes: operator free-text annotations (e.g. mid-investigation context
  -- the operator wants to remember). status-change audit trail uses the
  -- dedicated `status_change_reason` column.
  notes TEXT
);
CREATE INDEX ix_hypothesis_status ON hypothesis_registry(status);

INSERT OR IGNORE INTO hypothesis_registry
  (name, statement, target_sample_size, decision_criteria,
   consecutive_loss_tripwire, absolute_loss_tripwire_pct, created_at)
VALUES
  ('A+ baseline',
   'Production A+ candidates produce positive expectancy',
   20,
   'Mean R-multiple > 0; lower-bound Wilson CI on win rate > 30%',
   5, 5.0, '2026-04-25'),
  ('Near-A+ defensible: extension test',
   'Watch-bucket candidates failing ONLY proximity_20ma produce edge within 25% of A+ baseline',
   10,
   'Mean R-multiple within 25% of A+ baseline mean',
   4, 5.0, '2026-04-25'),
  ('Sub-A+ VCP-not-formed',
   'Watch-bucket candidates failing tightness OR vcp_volume_contraction produce reliable losses validating framework discipline',
   5,
   'Confirm negative mean R-multiple',
   3, 5.0, '2026-04-25'),
  ('Capital-blocked: smaller-position test',
   'Candidates A+ except risk_feasibility, taken with smaller-than-standard position size, produce positive expectancy',
   10,
   'Mean R-multiple positive; defensibility of smaller-position approach',
   4, 5.0, '2026-04-25');

UPDATE schema_version SET version = 8;
