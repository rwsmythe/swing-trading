-- 0034_h1_decision_criteria_amendment.sql
-- The H1 ("A+ baseline") decision-criteria amendment. A V2.1 section VII.F
-- source-of-truth amendment to a PRE-REGISTERED decision rule, taking the
-- route migration 0008's own header prescribed in advance (lines 7-12): "A
-- formal amendment requires a NEW migration with an explicit version bump ...
-- not an in-place UPDATE." Bumps schema_version 33 -> 34.
--
-- Governance record: docs/h1-criteria-amendment-commissioning-brief.md (RD's,
-- criterion text operator-signed 2026-07-29) and
-- docs/h1-criteria-amendment-charc-section3-pass.md (CHARC's, which owns this
-- mechanism). This migration takes its OWN number and carries nothing else, so
-- the amendment is independently auditable in migration history rather than
-- buried inside a feature migration.
--
-- WHY. The frozen Wilson leg is mis-calibrated for this style of system:
-- lower-bound Wilson > 30% at n=20 requires 11 wins of 20, a 55% raw win rate,
-- which no measured cohort in this program approaches and which typical
-- breakout/trend systems do not reach. As written the criterion would likely
-- REJECT a genuinely profitable trend-following system -- a false negative on
-- success. The win-rate floor was doing a real job (guarding the mean-R claim
-- against a single outlier at small n) and that job is RETAINED by the
-- top-1-concentration cap, which was chosen by stress test over a
-- leave-one-out alternative that failed a real fat-tailed trend shape. This is
-- a re-calibration, not a loosening.
--
-- ATOMICITY. Explicit transaction per the executescript implicit-COMMIT gotcha
-- (#9): _apply_migration does NOT open its own transaction, so without the
-- wrapper a mid-script failure would leave the ADD COLUMN applied and the
-- UPDATEs missing -- exactly the half-amended row this migration exists to
-- prevent.
--
-- ================= THE PRESERVATION MECHANISM =========================
-- Overwriting decision_criteria in place without preserving the original
-- would destroy the evidence of what was pre-registered, defeating the whole
-- purpose of pre-registration. So one additive nullable TEXT column,
-- `preregistered_decision_criteria`, holds the original.
--
-- NULL SEMANTICS -- DEFINED, NOT INCIDENTAL. NULL means: this row has
-- never been amended; its `decision_criteria` IS the pre-registered text.
-- NULL does NOT mean "unknown". That definition is what makes leaving rows
-- 2-5 NULL safe rather than ambiguous, and it is the reason those rows are
-- deliberately not written here.
--
-- `status_change_reason` was considered for this and REJECTED: step 7 of every
-- status transition (swing/trades/hypothesis.py) overwrites that column, and
-- H1's criterion exists precisely to drive a transition at n=20 -- the
-- preservation would have been destroyed by the very event it exists to
-- inform. It would also fabricate a status change that never happened (H1
-- remains `active`) and desynchronise the denormalized row from
-- hypothesis_status_history. Nothing writes the new column at runtime, so it
-- survives every transition.
--
-- The preservation UPDATE writes a hard-coded LITERAL rather than
-- `SET preregistered_decision_criteria = decision_criteria`. The latter looks
-- idempotent but is not: on any second pass it would preserve the AMENDED text
-- and destroy the original. The literal form is idempotent by construction.
--
-- ================= THE STORED FORM ====================================
-- The amended criterion is stored as a SINGLE LINE. The brief's section 1
-- renders it wrapped across 8 markdown lines; that wrapping is presentation,
-- and each wrap point becomes a single space. Single-line matches the 0008
-- value being replaced (one SQL string literal, no embedded newline) and the
-- 0026 house style (single-line value assembled via ||); no decision_criteria
-- value in this registry has ever carried an embedded newline. The fragments
-- below are split at the brief's own wrap points, each carrying one trailing
-- space, so the migration source reads against the operator-signed block
-- line for line.
--
-- CANONICAL STORED VALUE: length 577,
-- sha256 6bdd723ce8a8ea1d00b8dbcfa7b50ec056a6282ee3a5110990b2f0894b7b3e73.
-- The digest is the referent, asserted in
-- tests/data/test_migration_0034_h1_criteria_amendment.py. "Matches the brief"
-- is NOT a referent -- the brief does not exist as these bytes.
--
-- Targeted by `name`, which is UNIQUE and is what the cohort readers key on
-- (swing/metrics/tier.py); the primary key is an autoincrement accident of
-- seed order. Nothing else on the row changes: not statement, not
-- target_sample_size (stays 20), not status. Rows 2-5 are untouched -- H2/H3/H4
-- do not gate on Wilson, and H5 only REPORTS it as a diagnostic.
--
-- ================= WHY THIS MIGRATION REFUSES TO FAIL OPEN =============
-- UNIQUE on `name` guarantees AT MOST one match, not EXACTLY one. A bare
-- `UPDATE ... WHERE name = 'A+ baseline'` that matches zero rows is not an
-- error in SQL: it would commit, bump the version to 34, and report success
-- having amended nothing. Worse, if the live `decision_criteria` had drifted
-- from the pre-registered text by any route, the bare form would overwrite it
-- AND write this file's hard-coded copy into the preservation column --
-- MANUFACTURING a pre-registration record that never existed and concealing
-- the drift in the same stroke. On a governance record whose entire value is
-- being trustworthy about what was registered before the data arrived, that
-- silent outcome is worse than a failed migration.
--
-- So the amendment is bracketed by two guards. SQLite has no procedural
-- ABORT outside a trigger, so each is expressed as a single-row insert into a
-- temp table with a named CHECK; a violation raises IntegrityError, and
-- _apply_migration rolls the whole script back and re-raises, leaving the DB
-- untouched at v33. The constraint NAMES are the operator-facing error text.
--
--   PRE  -- refuses unless EXACTLY ONE 'A+ baseline' row exists AND its
--           decision_criteria is still, byte for byte, the 0008 original.
--           This migration amends exactly one known text; anything else is a
--           condition to stop and investigate, not to overwrite.
--   POST -- a LENGTH-AND-PRESERVATION check, and no more than that. It
--           requires the criterion to be 577 characters, the preservation
--           column to hold the original, and the two to differ -- which is
--           enough to catch the UPDATE matching zero rows, a preservation
--           that never landed, and the realistic || failure of one dropped or
--           doubled join space. It is NOT proof that the bytes are correct: a
--           BALANCED corruption (one space dropped, another doubled) holds
--           length at 577 and would pass. SQLite has no sha256, so the
--           byte-level proof lives in the test suite, which asserts the real
--           digest. The constraint is named for what it actually checks.

BEGIN;

CREATE TEMP TABLE _h1_amendment_preflight (
  ok INTEGER NOT NULL
    CONSTRAINT h1_amendment_refuses_unless_exactly_one_unamended_a_plus_baseline_row
    CHECK (ok = 1)
);
INSERT INTO _h1_amendment_preflight (ok)
SELECT CASE WHEN (
    SELECT COUNT(*) FROM hypothesis_registry
    WHERE name = 'A+ baseline'
      AND decision_criteria =
          'Mean R-multiple > 0; lower-bound Wilson CI on win rate > 30%'
  ) = 1 THEN 1 ELSE 0 END;
DROP TABLE _h1_amendment_preflight;

ALTER TABLE hypothesis_registry
  ADD COLUMN preregistered_decision_criteria TEXT;

-- Preserve the original FIRST. Verbatim from 0008 line 52.
UPDATE hypothesis_registry
SET preregistered_decision_criteria =
  'Mean R-multiple > 0; lower-bound Wilson CI on win rate > 30%'
WHERE name = 'A+ baseline';

-- Then amend.
UPDATE hypothesis_registry
SET decision_criteria =
  'Mean R-multiple > 0 across the 20 closed labeled trades, AND no single trade '
  || 'contributes 50% or more of gross profit (gross profit = sum of positive '
  || 'R-multiples). COHORT: the 20 are STANDARD-intent trades only, per the '
  || '2026-06-10 training-epoch declaration; pre-epoch hypothesis_test_by_design '
  || 'trades are settled tuition and do NOT count toward the 20. If the cohort has '
  || 'no winners, the mean-R criterion fails and the decision is negative. Win rate '
  || 'and its Wilson lower bound are REPORTED as diagnostics alongside median R and '
  || 'top-3 concentration, but do not gate the decision.'
WHERE name = 'A+ baseline';

CREATE TEMP TABLE _h1_amendment_postcheck (
  ok INTEGER NOT NULL
    CONSTRAINT h1_amendment_refuses_a_criterion_of_the_wrong_length_or_a_lost_preservation
    CHECK (ok = 1)
);
INSERT INTO _h1_amendment_postcheck (ok)
SELECT CASE WHEN (
    SELECT COUNT(*) FROM hypothesis_registry
    WHERE name = 'A+ baseline'
      AND length(decision_criteria) = 577
      AND preregistered_decision_criteria =
          'Mean R-multiple > 0; lower-bound Wilson CI on win rate > 30%'
      AND decision_criteria <> preregistered_decision_criteria
  ) = 1 THEN 1 ELSE 0 END;
DROP TABLE _h1_amendment_postcheck;

UPDATE schema_version SET version = 34;
COMMIT;
