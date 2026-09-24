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
--         DROP TRIGGER trg_lve_first_view_immutable;  -- latch_view_events (F-I5)
--         DROP TRIGGER trg_rr_no_delete;   -- reconciliation_runs
--         DROP TRIGGER trg_rr_no_replace;  -- reconciliation_runs
--         DROP TRIGGER trg_rr_immutable;   -- reconciliation_runs
--         DROP TRIGGER trg_rd_no_delete;   -- reconciliation_discrepancies
--         DROP TRIGGER trg_rd_no_replace;  -- reconciliation_discrepancies
--         DROP TRIGGER trg_rd_immutable;   -- reconciliation_discrepancies
--         DROP TRIGGER trg_rc_no_delete;   -- reconciliation_corrections
--         DROP TRIGGER trg_rc_no_replace;  -- reconciliation_corrections
--         DROP TRIGGER trg_rc_immutable;   -- reconciliation_corrections
--         DROP TRIGGER trg_sac_no_delete;   -- schwab_api_calls
--         DROP TRIGGER trg_sac_no_replace;  -- schwab_api_calls
--         DROP TRIGGER trg_sac_immutable;   -- schwab_api_calls
--         DROP TRIGGER trg_yfc_no_delete;   -- yfinance_calls
--         DROP TRIGGER trg_yfc_no_replace;  -- yfinance_calls
--         DROP TRIGGER trg_yfc_immutable;   -- yfinance_calls
--         DROP TRIGGER trg_aes_no_delete;   -- account_equity_snapshots
--         DROP TRIGGER trg_aes_no_replace;  -- account_equity_snapshots
--         DROP TRIGGER trg_aes_immutable;   -- account_equity_snapshots
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

-- ============================================================================
-- 3. F-I5 -- the latch_view_events FIRST-VIEW twin (RD F-I5 (a); CHARC's
--    shape, binding). The contract it enforces, QUOTED rather than paraphrased:
--      0032:31  "first_viewed_ts + latch_state_at_first_view are IMMUTABLE after
--               insert"
--      0033:62  "actionable_at_first_view -- set at INSERT, NEVER rewritten"
--      22-B R0.K narrowed the leg-1 WINDOW to (first_viewed_ts, ticker) -- held
--               by trg_lve_view_window_immutable -- and did not license the
--               other first-view columns to move.
--    The seven columns are exactly the ones the sole writer's merge UPDATE
--    (repos/latch_view_events.py:157-167) never names; excluded: the five
--    writer-updated columns, pipeline_run_id (under the identity trigger),
--    first_viewed_ts / ticker (under the existing window twin). An UPDATE OF
--    trigger with no WHEN carries no NULL hazard.
-- ============================================================================
CREATE TRIGGER trg_lve_first_view_immutable
BEFORE UPDATE OF candidate_id, evaluation_run_id, detection_date, surface,
                 view_session_date, latch_state_at_first_view,
                 actionable_at_first_view
ON latch_view_events
FOR EACH ROW
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_lve_first_view_immutable: the latch_view_events first-view columns (candidate_id, evaluation_run_id, detection_date, surface, view_session_date, latch_state_at_first_view, actionable_at_first_view) are IMMUTABLE after insert: leg-1 evidence (0032, 0033, 22-B R0.K; RD F-I5). To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

-- ============================================================================
-- 4. reconciliation_runs / reconciliation_discrepancies -- (c) (RD F-I1 row 11):
--    no_delete + no_replace (PK only) + a column-scoped immutability twin. The
--    mutable set is the writers' MEASURED UPDATE set, read at all twelve sites
--    (repos/reconciliation.py:191/:235/:399/:412/:442, trades/reconciliation.py:721,
--    trades/reconciliation_auto_correct.py:996/:1002/:1583/:1976/:2053/:2623);
--    everything else is immutable BY EXCLUSION, incl. the as-detected evidence
--    (expected_value_json / actual_value_json) and the source artifact sha. The
--    SET NULL FKs admit value -> NULL only with the parent row GONE (a17):
--    discrepancies.fill_id is REACHABLE (split_into_partials deletes the fill,
--    reconciliation_auto_correct.py:3226).
-- ============================================================================
CREATE TRIGGER trg_rr_no_delete BEFORE DELETE ON reconciliation_runs
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_rr_no_delete: reconciliation_runs rows are PERMANENT from migration 0041; a reconciliation run carries its identity and source artifact as detected (RD F-I1 row 11). A delete would erase the record and let a rowid be reissued. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_rr_no_replace BEFORE INSERT ON reconciliation_runs
WHEN COALESCE(EXISTS (SELECT 1 FROM reconciliation_runs
              WHERE (NEW.run_id != -1 AND run_id = NEW.run_id)), 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_rr_no_replace: reconciliation_runs rows are PERMANENT from migration 0041. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE / ON CONFLICT DO NOTHING) would DELETE the existing row without firing trg_rr_no_delete and reissue or move its id; a reconciliation run carries its identity and source artifact as detected (RD F-I1 row 11). A writer that needs idempotency pre-filters with WHERE NOT EXISTS. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_rr_immutable
BEFORE UPDATE ON reconciliation_runs
FOR EACH ROW
WHEN NOT COALESCE(
      NEW.run_id IS OLD.run_id
  AND NEW.source IS OLD.source
  AND NEW.source_artifact_path IS OLD.source_artifact_path
  AND NEW.source_artifact_sha256 IS OLD.source_artifact_sha256
  AND NEW.period_start IS OLD.period_start
  AND NEW.period_end IS OLD.period_end
  AND NEW.started_ts IS OLD.started_ts
  AND (NEW.schwab_api_call_id IS OLD.schwab_api_call_id
        OR (OLD.schwab_api_call_id IS NOT NULL AND NEW.schwab_api_call_id IS NULL
            AND NOT EXISTS (SELECT 1 FROM schwab_api_calls WHERE call_id = OLD.schwab_api_call_id)))
, 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_rr_immutable: reconciliation_runs: this UPDATE changes a column outside the writer''s measured UPDATE set (state, finished_ts, account_equity_journal_dollars, account_equity_source_dollars, equity_delta_dollars, trades_reconciled_count, fills_reconciled_count, discrepancies_count, unresolved_discrepancies_count, summary_json, notes, error_message); FK nulled only after its parent row is gone: schwab_api_call_id; a reconciliation run carries its identity and source artifact as detected (RD F-I1 row 11). To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_rd_no_delete BEFORE DELETE ON reconciliation_discrepancies
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_rd_no_delete: reconciliation_discrepancies rows are PERMANENT from migration 0041; a discrepancy carries its identity and as-detected evidence (RD F-I1 row 11). A delete would erase the record and let a rowid be reissued. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_rd_no_replace BEFORE INSERT ON reconciliation_discrepancies
WHEN COALESCE(EXISTS (SELECT 1 FROM reconciliation_discrepancies
              WHERE (NEW.discrepancy_id != -1 AND discrepancy_id = NEW.discrepancy_id)), 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_rd_no_replace: reconciliation_discrepancies rows are PERMANENT from migration 0041. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE / ON CONFLICT DO NOTHING) would DELETE the existing row without firing trg_rd_no_delete and reissue or move its id; a discrepancy carries its identity and as-detected evidence (RD F-I1 row 11). A writer that needs idempotency pre-filters with WHERE NOT EXISTS. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_rd_immutable
BEFORE UPDATE ON reconciliation_discrepancies
FOR EACH ROW
WHEN NOT COALESCE(
      NEW.discrepancy_id IS OLD.discrepancy_id
  AND NEW.run_id IS OLD.run_id
  AND NEW.discrepancy_type IS OLD.discrepancy_type
  AND NEW.ticker IS OLD.ticker
  AND NEW.field_name IS OLD.field_name
  AND NEW.expected_value_json IS OLD.expected_value_json
  AND NEW.actual_value_json IS OLD.actual_value_json
  AND NEW.delta_text IS OLD.delta_text
  AND NEW.created_at IS OLD.created_at
  AND (NEW.trade_id IS OLD.trade_id
        OR (OLD.trade_id IS NOT NULL AND NEW.trade_id IS NULL
            AND NOT EXISTS (SELECT 1 FROM trades WHERE id = OLD.trade_id)))
  AND (NEW.fill_id IS OLD.fill_id
        OR (OLD.fill_id IS NOT NULL AND NEW.fill_id IS NULL
            AND NOT EXISTS (SELECT 1 FROM fills WHERE fill_id = OLD.fill_id)))
  AND (NEW.cash_movement_id IS OLD.cash_movement_id
        OR (OLD.cash_movement_id IS NOT NULL AND NEW.cash_movement_id IS NULL
            AND NOT EXISTS (SELECT 1 FROM cash_movements WHERE id = OLD.cash_movement_id)))
  AND (NEW.linked_daily_management_record_id IS OLD.linked_daily_management_record_id
        OR (OLD.linked_daily_management_record_id IS NOT NULL AND NEW.linked_daily_management_record_id IS NULL
            AND NOT EXISTS (SELECT 1 FROM daily_management_records WHERE management_record_id = OLD.linked_daily_management_record_id)))
, 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_rd_immutable: reconciliation_discrepancies: this UPDATE changes a column outside the writer''s measured UPDATE set (resolution, resolution_reason, resolved_at, resolved_by, ambiguity_kind, mistake_tag_assigned, material_to_review); FK nulled only after its parent row is gone: trade_id, fill_id, cash_movement_id, linked_daily_management_record_id; a discrepancy carries its identity and as-detected evidence (RD F-I1 row 11). To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

-- ============================================================================
-- 5. reconciliation_corrections -- (c) (RD F-I1 row 6, S3-F1 as amended). The
--    table trg_eia_audit_trail reads as THE audit trail. No column is mutable:
--    correction_set_id and superseded_by_correction_id are WRITE-ONCE (NULL ->
--    value; the anchor self-reference at reconciliation_auto_correct.py:3251,
--    the supersede pointer at repos/reconciliation_corrections.py:208 and
--    entry_date_correction.py:1543); the self-FK superseded_by_correction_id
--    carries NO SET-NULL exemption (its only cascade is a delete this file's
--    no_delete refuses). risk_policy_id_at_correction / schwab_api_call_id keep
--    the uniform a17 exemption, DEAD-BY-PARENT-GUARD (both parents get
--    no_delete below). correction_id is AUTOINCREMENT; the -1 clause applies.
-- ============================================================================
CREATE TRIGGER trg_rc_no_delete BEFORE DELETE ON reconciliation_corrections
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_rc_no_delete: reconciliation_corrections rows are PERMANENT from migration 0041; reconciliation_corrections is THE audit trail trg_eia_audit_trail reads (RD F-I1 row 6). A delete would erase the record and let a rowid be reissued. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_rc_no_replace BEFORE INSERT ON reconciliation_corrections
WHEN COALESCE(EXISTS (SELECT 1 FROM reconciliation_corrections
              WHERE (NEW.correction_id != -1 AND correction_id = NEW.correction_id)), 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_rc_no_replace: reconciliation_corrections rows are PERMANENT from migration 0041. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE / ON CONFLICT DO NOTHING) would DELETE the existing row without firing trg_rc_no_delete and reissue or move its id; reconciliation_corrections is THE audit trail trg_eia_audit_trail reads (RD F-I1 row 6). A writer that needs idempotency pre-filters with WHERE NOT EXISTS. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_rc_immutable
BEFORE UPDATE ON reconciliation_corrections
FOR EACH ROW
WHEN NOT COALESCE(
      NEW.correction_id IS OLD.correction_id
  AND NEW.discrepancy_id IS OLD.discrepancy_id
  AND NEW.correction_action IS OLD.correction_action
  AND NEW.correction_choice IS OLD.correction_choice
  AND NEW.affected_table IS OLD.affected_table
  AND NEW.affected_row_id IS OLD.affected_row_id
  AND NEW.field_name IS OLD.field_name
  AND NEW.pre_correction_value_json IS OLD.pre_correction_value_json
  AND NEW.source_canonical_value_json IS OLD.source_canonical_value_json
  AND NEW.applied_value_json IS OLD.applied_value_json
  AND NEW.operator_truth_value_json IS OLD.operator_truth_value_json
  AND NEW.applied_at IS OLD.applied_at
  AND NEW.applied_by IS OLD.applied_by
  AND NEW.reconciliation_run_id IS OLD.reconciliation_run_id
  AND NEW.correction_reason IS OLD.correction_reason
  AND NEW.notes IS OLD.notes
  AND (NEW.correction_set_id IS OLD.correction_set_id OR OLD.correction_set_id IS NULL)
  AND (NEW.superseded_by_correction_id IS OLD.superseded_by_correction_id OR OLD.superseded_by_correction_id IS NULL)
  AND (NEW.risk_policy_id_at_correction IS OLD.risk_policy_id_at_correction
        OR (OLD.risk_policy_id_at_correction IS NOT NULL AND NEW.risk_policy_id_at_correction IS NULL
            AND NOT EXISTS (SELECT 1 FROM risk_policy WHERE policy_id = OLD.risk_policy_id_at_correction)))
  AND (NEW.schwab_api_call_id IS OLD.schwab_api_call_id
        OR (OLD.schwab_api_call_id IS NOT NULL AND NEW.schwab_api_call_id IS NULL
            AND NOT EXISTS (SELECT 1 FROM schwab_api_calls WHERE call_id = OLD.schwab_api_call_id)))
, 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_rc_immutable: reconciliation_corrections: this UPDATE changes a column outside the writer''s measured UPDATE set (none); write-once NULL to value: correction_set_id, superseded_by_correction_id; FK nulled only after its parent row is gone: risk_policy_id_at_correction, schwab_api_call_id; reconciliation_corrections is THE audit trail trg_eia_audit_trail reads (RD F-I1 row 6). To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

-- ============================================================================
-- 6. schwab_api_calls / yfinance_calls -- (c) (RD F-I1 row 12): UPDATE-in-place
--    BY DESIGN (record_call_finish closes the row), so no blanket no_update: the
--    twin freezes only what the writers never write -- by exclusion of their
--    measured UPDATE set (repos/schwab_api_calls.py:102/:119/:133/:165,
--    reconciliation_auto_correct.py:2370, scripts/fix_phase2_misleading_audit_
--    rows.py:102; repos/yfinance_calls.py:87). pipeline_run_id keeps the a17
--    exemption (DELETABLE-NO-PRODUCTION-DELETER).
-- ============================================================================
CREATE TRIGGER trg_sac_no_delete BEFORE DELETE ON schwab_api_calls
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_sac_no_delete: schwab_api_calls rows are PERMANENT from migration 0041; an API audit row''s PK and start identity are the immutable handle (RD F-I1 row 12). A delete would erase the record and let a rowid be reissued. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_sac_no_replace BEFORE INSERT ON schwab_api_calls
WHEN COALESCE(EXISTS (SELECT 1 FROM schwab_api_calls
              WHERE (NEW.call_id != -1 AND call_id = NEW.call_id)), 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_sac_no_replace: schwab_api_calls rows are PERMANENT from migration 0041. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE / ON CONFLICT DO NOTHING) would DELETE the existing row without firing trg_sac_no_delete and reissue or move its id; an API audit row''s PK and start identity are the immutable handle (RD F-I1 row 12). A writer that needs idempotency pre-filters with WHERE NOT EXISTS. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_sac_immutable
BEFORE UPDATE ON schwab_api_calls
FOR EACH ROW
WHEN NOT COALESCE(
      NEW.call_id IS OLD.call_id
  AND NEW.ts IS OLD.ts
  AND NEW.endpoint IS OLD.endpoint
  AND NEW.surface IS OLD.surface
  AND NEW.environment IS OLD.environment
  AND (NEW.pipeline_run_id IS OLD.pipeline_run_id
        OR (OLD.pipeline_run_id IS NOT NULL AND NEW.pipeline_run_id IS NULL
            AND NOT EXISTS (SELECT 1 FROM pipeline_runs WHERE id = OLD.pipeline_run_id)))
, 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_sac_immutable: schwab_api_calls: this UPDATE changes a column outside the writer''s measured UPDATE set (http_status, response_time_ms, rate_limit_remaining, signature_hash, status, error_message, linked_snapshot_id, linked_reconciliation_run_id, linked_correction_id); FK nulled only after its parent row is gone: pipeline_run_id; an API audit row''s PK and start identity are the immutable handle (RD F-I1 row 12). To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_yfc_no_delete BEFORE DELETE ON yfinance_calls
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_yfc_no_delete: yfinance_calls rows are PERMANENT from migration 0041; an API audit row''s PK and start identity are the immutable handle (RD F-I1 row 12). A delete would erase the record and let a rowid be reissued. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_yfc_no_replace BEFORE INSERT ON yfinance_calls
WHEN COALESCE(EXISTS (SELECT 1 FROM yfinance_calls
              WHERE (NEW.call_id != -1 AND call_id = NEW.call_id)), 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_yfc_no_replace: yfinance_calls rows are PERMANENT from migration 0041. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE / ON CONFLICT DO NOTHING) would DELETE the existing row without firing trg_yfc_no_delete and reissue or move its id; an API audit row''s PK and start identity are the immutable handle (RD F-I1 row 12). A writer that needs idempotency pre-filters with WHERE NOT EXISTS. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_yfc_immutable
BEFORE UPDATE ON yfinance_calls
FOR EACH ROW
WHEN NOT COALESCE(
      NEW.call_id IS OLD.call_id
  AND NEW.ts IS OLD.ts
  AND NEW.call_type IS OLD.call_type
  AND NEW.ticker IS OLD.ticker
  AND NEW.ticker_count IS OLD.ticker_count
  AND NEW.surface IS OLD.surface
  AND (NEW.pipeline_run_id IS OLD.pipeline_run_id
        OR (OLD.pipeline_run_id IS NOT NULL AND NEW.pipeline_run_id IS NULL
            AND NOT EXISTS (SELECT 1 FROM pipeline_runs WHERE id = OLD.pipeline_run_id)))
, 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_yfc_immutable: yfinance_calls: this UPDATE changes a column outside the writer''s measured UPDATE set (response_time_ms, status, rows_returned, error_message); FK nulled only after its parent row is gone: pipeline_run_id; an API audit row''s PK and start identity are the immutable handle (RD F-I1 row 12). To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

-- ============================================================================
-- 7. account_equity_snapshots -- (c) (RD F-I1 row 16): the value is re-recorded by
--    design (the source ladder, SELECT-then-UPDATE-or-INSERT at
--    repos/account_equity_snapshots.py:77/:121) and stamped (audit_service.py:339),
--    so those columns stay mutable; the identity (snapshot_id and the UNIQUE key
--    snapshot_date, source, basis) is frozen. The corrector's dynamic
--    SET {field_name} branch (reconciliation_auto_correct.py:2325-2328) is
--    SERVICE-prevented (AL-7): _resolve_affected_target never returns this
--    table; if it ever did, this twin refuses loudly.
-- ============================================================================
CREATE TRIGGER trg_aes_no_delete BEFORE DELETE ON account_equity_snapshots
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_aes_no_delete: account_equity_snapshots rows are PERMANENT from migration 0041; a snapshot''s identity is the key the source ladder looks it up by (RD F-I1 row 16). A delete would erase the record and let a rowid be reissued. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_aes_no_replace BEFORE INSERT ON account_equity_snapshots
WHEN COALESCE(EXISTS (SELECT 1 FROM account_equity_snapshots
              WHERE (NEW.snapshot_id != -1 AND snapshot_id = NEW.snapshot_id)
                 OR (snapshot_date = NEW.snapshot_date AND source = NEW.source AND basis = NEW.basis)), 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_aes_no_replace: account_equity_snapshots rows are PERMANENT from migration 0041. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE / ON CONFLICT DO NOTHING) would DELETE the existing row without firing trg_aes_no_delete and reissue or move its id; a snapshot''s identity is the key the source ladder looks it up by (RD F-I1 row 16). A writer that needs idempotency pre-filters with WHERE NOT EXISTS. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_aes_immutable
BEFORE UPDATE ON account_equity_snapshots
FOR EACH ROW
WHEN NOT COALESCE(
      NEW.snapshot_id IS OLD.snapshot_id
  AND NEW.snapshot_date IS OLD.snapshot_date
  AND NEW.source IS OLD.source
  AND NEW.basis IS OLD.basis
, 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_aes_immutable: account_equity_snapshots: this UPDATE changes a column outside the writer''s measured UPDATE set (equity_dollars, source_artifact_path, recorded_at, recorded_by, notes, schwab_account_hash); a snapshot''s identity is the key the source ladder looks it up by (RD F-I1 row 16). To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

-- The version bump is the FINAL statement before COMMIT.
UPDATE schema_version SET version = 41;

COMMIT;
