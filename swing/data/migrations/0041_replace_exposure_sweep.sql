-- 0041_replace_exposure_sweep.sql -- Arc 22-I (the REPLACE-exposure sweep).
--
-- This migration ADDS TRIGGERS ONLY, REBUILDS NOTHING: no table, index, view
-- or column is created, altered or rebuilt, and no row is written except the
-- schema_version bump. One transaction, the runner's (`foreign_keys=OFF` at
-- the runner). Bumps schema_version 40 -> 41.
--
-- D60 DECLARATION: pre-existing rows replay unchanged: a trigger does not
-- touch stored rows. Every guard below binds FUTURE statements only; a row
-- already stored at v40 is neither read nor rewritten by this file.
--
-- WHY. A declared append-only / immutability contract with no SQL guard is a
-- WRITER-ABSENCE claim (RD, F-I1): it holds only while nobody writes. At the
-- default `PRAGMA recursive_triggers = 0` (this repo never enables it) an
-- INSERT OR REPLACE deletes the conflicting row WITHOUT firing any DELETE
-- trigger, and a BEFORE INSERT trigger cannot see the statement's conflict
-- algorithm, so a guard is the TRIPLE no_update + no_delete + a
-- conflict-scoped no_replace (the 0037 shape). Every WHEN this file writes is
-- COALESCE-wrapped (a NULL WHEN fails OPEN); every PK clause in a no_replace is
-- `(NEW.<pk> != -1 AND <pk> = NEW.<pk>)` (an omitted INTEGER PRIMARY KEY is -1
-- inside BEFORE INSERT, 0037's measurement).
--
-- ============================================================================
-- REVERSIBILITY HEADER
-- ============================================================================
-- (i) THE GATE: BackupGateSpec(40, "22i", PHASE22_ARC_I_PRE_MIGRATION_EXPECTED_TABLES,
--     "_phase22_arc_i_backup_gate", "pre-22-I") in swing/data/db.py, clause
--     `pre_version == 40 AND target_version >= 41`: a database at v40 migrated
--     to any target >= 41 writes the image swing-pre-22i-migration-<UTC>Z.db
--     before this file runs.
--
-- (ii) EVERY OBJECT THIS MIGRATION CREATES, each with its retiring statement:
--
--         DROP TRIGGER trg_provenance_corrections_append_only_update;  -- then (iii)
--
-- (iii) THE ONE REBUILT OBJECT (F-I2, CHARC-ruled): trg_provenance_corrections_
--     append_only_update is DROPPED and CREATED again. Its new text is the
--     STORED v40 sqlite_master.sql with EXACTLY two substitutions:
--         `FOR EACH ROW WHEN NOT (`   becomes   `FOR EACH ROW WHEN NOT COALESCE((`
--         the closing `<newline>)<newline>BEGIN`
--                                     becomes   `<newline>), 0)<newline>BEGIN`
--     (stored 4,140 chars -> 4,153; the inverse transform reproduces the v40
--     text byte-for-byte). WHY: with the FK-null branch TRUE, a `=`-compared
--     column going NULL in the same statement made the WHEN NULL, and a NULL
--     WHEN does not fire -- the trigger failed OPEN on 30 of 30 such columns
--     (census section 2). The wrap turns NULL into a refusal. To restore the
--     v40 object: DROP TRIGGER trg_provenance_corrections_append_only_update;
--     then re-create it from its source text,
--     0039_provenance_corrections_tier2.sql:704 (unchanged since).
--
-- ============================================================================

BEGIN;

-- ============================================================================
-- F-I2. trg_provenance_corrections_append_only_update, REBUILT with the
-- COALESCE wrap (header (iii)). Everything between the two substitutions is
-- the stored v40 text, verbatim.
-- ============================================================================
DROP TRIGGER trg_provenance_corrections_append_only_update;

CREATE TRIGGER trg_provenance_corrections_append_only_update
BEFORE UPDATE ON provenance_corrections
FOR EACH ROW WHEN NOT COALESCE((
    ((NEW.entry_fill_id IS NULL AND OLD.entry_fill_id IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM fills WHERE fill_id = OLD.entry_fill_id))
     OR (NEW.entry_fill_id IS OLD.entry_fill_id))
    AND ((NEW.risk_policy_id_at_correction IS NULL
          AND OLD.risk_policy_id_at_correction IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM risk_policy
                          WHERE policy_id = OLD.risk_policy_id_at_correction))
         OR (NEW.risk_policy_id_at_correction
             IS OLD.risk_policy_id_at_correction))
    AND (NEW.entry_fill_id IS NOT OLD.entry_fill_id
         OR NEW.risk_policy_id_at_correction
            IS NOT OLD.risk_policy_id_at_correction)
    AND NEW.provenance_correction_id = OLD.provenance_correction_id
           AND NEW.trade_id = OLD.trade_id
           AND NEW.entry_fill_id_at_correction = OLD.entry_fill_id_at_correction
           AND NEW.entry_fill_snapshot_json = OLD.entry_fill_snapshot_json
           AND NEW.cited_candidate_id = OLD.cited_candidate_id
           AND NEW.cited_daily_recommendation_id = OLD.cited_daily_recommendation_id
           AND NEW.cited_evaluation_run_id = OLD.cited_evaluation_run_id
           AND NEW.cited_hypothesis_id = OLD.cited_hypothesis_id
           AND NEW.cited_hypothesis_status_history_id = OLD.cited_hypothesis_status_history_id
           AND NEW.cited_hypothesis_status_at_record = OLD.cited_hypothesis_status_at_record
           AND NEW.cited_pipeline_finished_ts_raw = OLD.cited_pipeline_finished_ts_raw
           AND NEW.cited_run_ts_utc = OLD.cited_run_ts_utc
           AND NEW.cited_status_window_upper_utc = OLD.cited_status_window_upper_utc
           AND NEW.cited_pipeline_run_id = OLD.cited_pipeline_run_id
           AND NEW.cited_pipeline_run_snapshot_json = OLD.cited_pipeline_run_snapshot_json
           AND NEW.cited_hypothesis_status_recorded_at = OLD.cited_hypothesis_status_recorded_at
           AND NEW.cited_hypothesis_status_effective_from = OLD.cited_hypothesis_status_effective_from
           AND (NEW.cited_hypothesis_status_effective_to IS OLD.cited_hypothesis_status_effective_to)
           AND NEW.cited_hypothesis_name_at_correction = OLD.cited_hypothesis_name_at_correction
           AND NEW.cited_candidate_action_session_date = OLD.cited_candidate_action_session_date
           AND NEW.cited_recommendation_action_session_date = OLD.cited_recommendation_action_session_date
           AND NEW.entry_fill_session_date = OLD.entry_fill_session_date
           AND NEW.cited_run_ts_raw = OLD.cited_run_ts_raw
           AND NEW.cited_recommendation_snapshot_json = OLD.cited_recommendation_snapshot_json
           AND NEW.cited_candidate_snapshot_json = OLD.cited_candidate_snapshot_json
           AND NEW.derivation_rule_version = OLD.derivation_rule_version
           AND NEW.pre_value_json = OLD.pre_value_json
           AND NEW.applied_value_json = OLD.applied_value_json
           AND NEW.corrected_fields_json = OLD.corrected_fields_json
           AND NEW.applied_at = OLD.applied_at
           AND NEW.applied_by = OLD.applied_by
           AND NEW.correction_reason = OLD.correction_reason
           -- the SIX 22-A columns
           AND NEW.admission_tier IS OLD.admission_tier
           AND NEW.cited_latch_link_id IS OLD.cited_latch_link_id
           AND NEW.cited_latch_validity_intent_id IS OLD.cited_latch_validity_intent_id
           AND NEW.cited_latch_place_intent_id IS OLD.cited_latch_place_intent_id
           AND NEW.cited_latch_broker_order_id IS OLD.cited_latch_broker_order_id
           AND NEW.cited_latch_probe_json IS OLD.cited_latch_probe_json
           -- the 22-A2 seventh column (0039)
           AND NEW.cited_frozen_value_evidence_json IS OLD.cited_frozen_value_evidence_json
), 0)
BEGIN
    SELECT RAISE(ABORT, 'provenance_corrections is APPEND-ONLY: the only permitted UPDATE is the FK-driven nulling of entry_fill_id or risk_policy_id_at_correction. V1 records provenance ONCE per trade and there is no re-correction path.');
END;

-- The version bump is the FINAL statement before COMMIT.
UPDATE schema_version SET version = 41;

COMMIT;
