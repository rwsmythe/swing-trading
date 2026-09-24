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
--         DROP TRIGGER trg_pfo_no_update;   -- pattern_forward_observations
--         DROP TRIGGER trg_pfo_no_delete;   -- pattern_forward_observations
--         DROP TRIGGER trg_pfo_no_replace;  -- pattern_forward_observations
--         DROP TRIGGER trg_cc_no_update;    -- candidate_criteria
--         DROP TRIGGER trg_cc_no_delete;    -- candidate_criteria
--         DROP TRIGGER trg_cc_no_replace;   -- candidate_criteria
--         DROP TRIGGER trg_te_no_update;    -- trade_events
--         DROP TRIGGER trg_te_no_delete;    -- trade_events
--         DROP TRIGGER trg_te_no_replace;   -- trade_events
--         DROP TRIGGER trg_fac_no_update;   -- finviz_api_calls
--         DROP TRIGGER trg_fac_no_delete;   -- finviz_api_calls
--         DROP TRIGGER trg_fac_no_replace;  -- finviz_api_calls
--         DROP TRIGGER trg_pev_no_update;   -- pattern_evaluations
--         DROP TRIGGER trg_pev_no_delete;   -- pattern_evaluations
--         DROP TRIGGER trg_pev_no_replace;  -- pattern_evaluations
--         DROP TRIGGER trg_er_no_update;    -- evaluation_runs
--         DROP TRIGGER trg_er_no_delete;    -- evaluation_runs
--         DROP TRIGGER trg_er_no_replace;   -- evaluation_runs
--         DROP TRIGGER trg_pde_no_update;   -- pattern_detection_events
--         DROP TRIGGER trg_pde_no_delete;   -- pattern_detection_events
--         DROP TRIGGER trg_pde_no_replace;  -- pattern_detection_events
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

-- ============================================================================
-- 1. THE (a) TRIPLES, BLANKET -- RD F-I1 partition (a): pattern_forward_observations,
--    candidate_criteria, trade_events, finviz_api_calls, pattern_evaluations,
--    evaluation_runs. Each gets no_update (no WHEN: every column is immutable),
--    no_delete, and the conflict-scoped no_replace (the PK clause, plus each
--    UNIQUE key the table declares). No production UPDATE or DELETE reaches any
--    of them (plan ledger STEP 3 grep, re-read at 22-I executing round 0).
--    candidate_criteria's PK is composite, so it carries no -1 clause.
-- ============================================================================
CREATE TRIGGER trg_pfo_no_update BEFORE UPDATE ON pattern_forward_observations
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_pfo_no_update: pattern_forward_observations rows are IMMUTABLE from migration 0041; the forward-observation log is the shadow program measurement substrate (RD F-I1 row 1). A row is APPENDED, never edited. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_pfo_no_delete BEFORE DELETE ON pattern_forward_observations
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_pfo_no_delete: pattern_forward_observations rows are PERMANENT from migration 0041; the forward-observation log is the shadow program measurement substrate (RD F-I1 row 1). A delete would erase the record and let a rowid be reissued. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_pfo_no_replace BEFORE INSERT ON pattern_forward_observations
WHEN COALESCE(EXISTS (SELECT 1 FROM pattern_forward_observations
              WHERE (NEW.observation_id != -1 AND observation_id = NEW.observation_id)
                 OR (detection_id = NEW.detection_id AND observation_date = NEW.observation_date)), 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_pfo_no_replace: pattern_forward_observations rows are PERMANENT from migration 0041. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE / ON CONFLICT DO NOTHING) would DELETE the existing row without firing trg_pfo_no_delete and reissue or move its id; the forward-observation log is the shadow program measurement substrate (RD F-I1 row 1). A writer that needs idempotency pre-filters with WHERE NOT EXISTS. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_cc_no_update BEFORE UPDATE ON candidate_criteria
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_cc_no_update: candidate_criteria rows are IMMUTABLE from migration 0041; a fire''s criteria are the evidence of WHY a mandate fired (RD F-I1 row 3). A row is APPENDED, never edited. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_cc_no_delete BEFORE DELETE ON candidate_criteria
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_cc_no_delete: candidate_criteria rows are PERMANENT from migration 0041; a fire''s criteria are the evidence of WHY a mandate fired (RD F-I1 row 3). A delete would erase the record and let a rowid be reissued. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_cc_no_replace BEFORE INSERT ON candidate_criteria
WHEN COALESCE(EXISTS (SELECT 1 FROM candidate_criteria
              WHERE (candidate_id = NEW.candidate_id AND criterion_name = NEW.criterion_name)), 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_cc_no_replace: candidate_criteria rows are PERMANENT from migration 0041. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE / ON CONFLICT DO NOTHING) would DELETE the existing row without firing trg_cc_no_delete and reissue or move its id; a fire''s criteria are the evidence of WHY a mandate fired (RD F-I1 row 3). A writer that needs idempotency pre-filters with WHERE NOT EXISTS. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_te_no_update BEFORE UPDATE ON trade_events
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_te_no_update: trade_events rows are IMMUTABLE from migration 0041; trade_events is the audit log every trade mutation writes (RD F-I1 row 5). A row is APPENDED, never edited. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_te_no_delete BEFORE DELETE ON trade_events
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_te_no_delete: trade_events rows are PERMANENT from migration 0041; trade_events is the audit log every trade mutation writes (RD F-I1 row 5). A delete would erase the record and let a rowid be reissued. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_te_no_replace BEFORE INSERT ON trade_events
WHEN COALESCE(EXISTS (SELECT 1 FROM trade_events
              WHERE (NEW.id != -1 AND id = NEW.id)), 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_te_no_replace: trade_events rows are PERMANENT from migration 0041. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE / ON CONFLICT DO NOTHING) would DELETE the existing row without firing trg_te_no_delete and reissue or move its id; trade_events is the audit log every trade mutation writes (RD F-I1 row 5). A writer that needs idempotency pre-filters with WHERE NOT EXISTS. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_fac_no_update BEFORE UPDATE ON finviz_api_calls
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_fac_no_update: finviz_api_calls rows are IMMUTABLE from migration 0041; finviz_api_calls is the audit head of the screen population (RD F-I1 row 13). A row is APPENDED, never edited. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_fac_no_delete BEFORE DELETE ON finviz_api_calls
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_fac_no_delete: finviz_api_calls rows are PERMANENT from migration 0041; finviz_api_calls is the audit head of the screen population (RD F-I1 row 13). A delete would erase the record and let a rowid be reissued. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_fac_no_replace BEFORE INSERT ON finviz_api_calls
WHEN COALESCE(EXISTS (SELECT 1 FROM finviz_api_calls
              WHERE (NEW.call_id != -1 AND call_id = NEW.call_id)), 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_fac_no_replace: finviz_api_calls rows are PERMANENT from migration 0041. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE / ON CONFLICT DO NOTHING) would DELETE the existing row without firing trg_fac_no_delete and reissue or move its id; finviz_api_calls is the audit head of the screen population (RD F-I1 row 13). A writer that needs idempotency pre-filters with WHERE NOT EXISTS. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_pev_no_update BEFORE UPDATE ON pattern_evaluations
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_pev_no_update: pattern_evaluations rows are IMMUTABLE from migration 0041; a trade row''s pattern_evaluation_id cites these rows, the 22-A anchor (RD F-I1 row 14). A row is APPENDED, never edited. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_pev_no_delete BEFORE DELETE ON pattern_evaluations
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_pev_no_delete: pattern_evaluations rows are PERMANENT from migration 0041; a trade row''s pattern_evaluation_id cites these rows, the 22-A anchor (RD F-I1 row 14). A delete would erase the record and let a rowid be reissued. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_pev_no_replace BEFORE INSERT ON pattern_evaluations
WHEN COALESCE(EXISTS (SELECT 1 FROM pattern_evaluations
              WHERE (NEW.id != -1 AND id = NEW.id)
                 OR (pipeline_run_id = NEW.pipeline_run_id AND ticker = NEW.ticker AND pattern_class = NEW.pattern_class)), 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_pev_no_replace: pattern_evaluations rows are PERMANENT from migration 0041. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE / ON CONFLICT DO NOTHING) would DELETE the existing row without firing trg_pev_no_delete and reissue or move its id; a trade row''s pattern_evaluation_id cites these rows, the 22-A anchor (RD F-I1 row 14). A writer that needs idempotency pre-filters with WHERE NOT EXISTS. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_er_no_update BEFORE UPDATE ON evaluation_runs
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_er_no_update: evaluation_runs rows are IMMUTABLE from migration 0041; evaluation_runs is the run identity every candidate, recommendation and citation hangs off (RD F-I1, added from the excluded list). A row is APPENDED, never edited. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_er_no_delete BEFORE DELETE ON evaluation_runs
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_er_no_delete: evaluation_runs rows are PERMANENT from migration 0041; evaluation_runs is the run identity every candidate, recommendation and citation hangs off (RD F-I1, added from the excluded list). A delete would erase the record and let a rowid be reissued. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_er_no_replace BEFORE INSERT ON evaluation_runs
WHEN COALESCE(EXISTS (SELECT 1 FROM evaluation_runs
              WHERE (NEW.id != -1 AND id = NEW.id)), 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_er_no_replace: evaluation_runs rows are PERMANENT from migration 0041. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE / ON CONFLICT DO NOTHING) would DELETE the existing row without firing trg_er_no_delete and reissue or move its id; evaluation_runs is the run identity every candidate, recommendation and citation hangs off (RD F-I1, added from the excluded list). A writer that needs idempotency pre-filters with WHERE NOT EXISTS. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

-- ============================================================================
-- 2. pattern_detection_events -- the (a) triple whose no_update is the a17 TWIN
--    (CHARC a17, the parent-gone clause accepted @ 7e0463ed). The ONE admitted
--    UPDATE is chart_render_id or pipeline_run_id going value -> NULL with its
--    parent row GONE (the ON DELETE SET NULL action; the chart prune/refresh is
--    REACHABLE, pipeline_runs has no production deleter), every other column
--    unchanged; the third conjunct makes a no-op UPDATE abort (the v40
--    trg_eia_no_update shape).
-- ============================================================================
CREATE TRIGGER trg_pde_no_update
BEFORE UPDATE ON pattern_detection_events
FOR EACH ROW
WHEN NOT COALESCE(
      (NEW.chart_render_id IS OLD.chart_render_id
        OR (OLD.chart_render_id IS NOT NULL AND NEW.chart_render_id IS NULL
            AND NOT EXISTS (SELECT 1 FROM chart_renders WHERE id = OLD.chart_render_id)))
  AND (NEW.pipeline_run_id IS OLD.pipeline_run_id
        OR (OLD.pipeline_run_id IS NOT NULL AND NEW.pipeline_run_id IS NULL
            AND NOT EXISTS (SELECT 1 FROM pipeline_runs WHERE id = OLD.pipeline_run_id)))
  AND (NEW.chart_render_id IS NOT OLD.chart_render_id OR NEW.pipeline_run_id IS NOT OLD.pipeline_run_id)
  AND NEW.detection_id IS OLD.detection_id
  AND NEW.ticker IS OLD.ticker
  AND NEW.detection_date IS OLD.detection_date
  AND NEW.data_asof_date IS OLD.data_asof_date
  AND NEW.pattern_class IS OLD.pattern_class
  AND NEW.structural_anchors_json IS OLD.structural_anchors_json
  AND NEW.composite_score IS OLD.composite_score
  AND NEW.detector_version IS OLD.detector_version
  AND NEW.finviz_screen_state IS OLD.finviz_screen_state
  AND NEW.source IS OLD.source
  AND NEW.per_pattern_metadata_json IS OLD.per_pattern_metadata_json
  AND NEW.created_at IS OLD.created_at
, 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_pde_no_update: pattern_detection_events: the ONE admitted UPDATE is the FK-driven nulling of chart_render_id or pipeline_run_id after its parent row is GONE (a17); a detection is the anchor every forward observation hangs off (RD F-I1 row 2). To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_pde_no_delete BEFORE DELETE ON pattern_detection_events
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_pde_no_delete: pattern_detection_events rows are PERMANENT from migration 0041; a detection is the anchor every forward observation hangs off (RD F-I1 row 2). A delete would erase the record and let a rowid be reissued. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_pde_no_replace BEFORE INSERT ON pattern_detection_events
WHEN COALESCE(EXISTS (SELECT 1 FROM pattern_detection_events
              WHERE (NEW.detection_id != -1 AND detection_id = NEW.detection_id)
                 OR (source = NEW.source AND ticker = NEW.ticker AND detection_date = NEW.detection_date AND pattern_class = NEW.pattern_class)), 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_pde_no_replace: pattern_detection_events rows are PERMANENT from migration 0041. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE / ON CONFLICT DO NOTHING) would DELETE the existing row without firing trg_pde_no_delete and reissue or move its id; a detection is the anchor every forward observation hangs off (RD F-I1 row 2). A writer that needs idempotency pre-filters with WHERE NOT EXISTS. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

-- The version bump is the FINAL statement before COMMIT.
UPDATE schema_version SET version = 41;

COMMIT;
