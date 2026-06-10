-- Migration 0026: broad-watch-baseline hypothesis (V2.1 §VII.F amendment).
-- ADDITIVE. The four frozen H1-H4 rows from 0008 are UNTOUCHED. INSERT OR IGNORE
-- keyed on the UNIQUE `name` column (mirrors 0008) so a re-run is a no-op.
-- Explicit BEGIN;...COMMIT; per gotcha #9 (executescript runs in autocommit;
-- _apply_migration does NOT open its own transaction -- 0023/0024/0025 all wrap).
-- Load-bearing here: the history INSERT...SELECT below is NON-idempotent, so a
-- mid-script failure must roll back the registry insert too.
BEGIN;
INSERT OR IGNORE INTO hypothesis_registry
  (name, statement, target_sample_size, decision_criteria,
   consecutive_loss_tripwire, absolute_loss_tripwire_pct, created_at, notes)
VALUES
  ('Broad-watch baseline',
   'The widened watch pool (bucket==watch, any non-pass set, not matching a '
   || 'narrower active hypothesis), priced by the mechanical shadow ruleset, '
   || 'establishes the baseline expectancy of the population the temporal log '
   || 'contains and the operator actually trades.',
   30,
   'SHADOW-measured (not closed live trades): primary read = realistic bracket '
   || 'arm on the closed_only and mtm_at_horizon censoring scenarios at N>=30 '
   || 'priced shadow signals; report mean R + Wilson lower-bound win rate across '
   || 'all four censoring scenarios. Pre-registered as a BASELINE: negative or '
   || 'zero mean R is a bankable validation of A+ gate selectivity; positive mean '
   || 'R triggers cohort-refinement research (which miss-sets carry the edge), '
   || 'NOT direct deployment.',
   5, 5.0, '2026-06-09',
   'Measurement substrate is the shadow-expectancy engine '
   || '(research/harness/shadow_expectancy), not labeled live trades. The baseline '
   || 'cohort = watch signals NOT otherwise matching a narrower active hypothesis '
   || '(the honest complement, via fallback matching). Surfaced by the production '
   || 'matcher ONLY in shadow/measurement context (opt-in); live recommendation '
   || 'surfaces never surface it. Tripwires apply only if the operator labels live '
   || 'watch trades with this hypothesis (permitted; matches practice). Not an '
   || 'operator recommendation cohort. Registry amendment via migration 0026 per '
   || 'V2.1 §VII.F.');

-- Seed the initial OPEN status-history interval for the new row, mirroring
-- migration 0017's per-row seed. Without this the governance/progress timeline
-- is EMPTY until the first status transition. Scoped to the new row only (the
-- four frozen rows already have their 0017 seed -- UNTOUCHED).
INSERT INTO hypothesis_status_history
  (hypothesis_id, status, effective_from, effective_to, change_reason, recorded_at)
SELECT id, status,
       strftime('%Y-%m-%dT00:00:00.000', created_at), NULL, NULL,
       strftime('%Y-%m-%dT%H:%M:%f', 'now')
FROM hypothesis_registry
WHERE name = 'Broad-watch baseline';

UPDATE schema_version SET version = 26;
COMMIT;
