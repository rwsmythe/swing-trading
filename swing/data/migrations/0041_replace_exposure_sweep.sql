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
--         DROP TRIGGER trg_lve_pk_immutable;          -- latch_view_events (B2)
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
--         DROP TRIGGER trg_rp_no_delete;    -- risk_policy
--         DROP TRIGGER trg_rp_no_replace;   -- risk_policy
--         DROP TRIGGER trg_rp_immutable;    -- risk_policy
--         DROP TRIGGER trg_hr_no_delete;    -- hypothesis_registry
--         DROP TRIGGER trg_hr_no_replace;   -- hypothesis_registry
--         DROP TRIGGER trg_hr_immutable;    -- hypothesis_registry
--         DROP TRIGGER trg_hsh_no_delete;   -- hypothesis_status_history
--         DROP TRIGGER trg_hsh_no_replace;  -- hypothesis_status_history
--         DROP TRIGGER trg_hsh_immutable;   -- hypothesis_status_history
--         DROP TRIGGER trg_dmr_no_delete;   -- daily_management_records
--         DROP TRIGGER trg_dmr_no_replace;  -- daily_management_records
--         DROP TRIGGER trg_dmr_immutable;   -- daily_management_records
--         DROP TRIGGER trg_rl_no_delete;    -- review_log
--         DROP TRIGGER trg_rl_no_replace;   -- review_log
--         DROP TRIGGER trg_rl_immutable;    -- review_log
--         DROP TRIGGER trg_pex_no_delete;   -- pattern_exemplars
--         DROP TRIGGER trg_pex_no_replace;  -- pattern_exemplars
--         DROP TRIGGER trg_wla_no_delete;   -- watchlist_archive
--         DROP TRIGGER trg_wla_no_replace;  -- watchlist_archive
--         DROP TRIGGER trg_pex_pk_immutable;  -- pattern_exemplars (B2)
--         DROP TRIGGER trg_wla_pk_immutable;  -- watchlist_archive (B2)
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
--    candidate_criteria's composite PK HIDES its rowid (the table is not
--    WITHOUT ROWID), so its no_replace carries the hidden-rowid clause
--    (NEW.rowid != -1 AND rowid = NEW.rowid) AND the composite-key clause
--    (Reviewer B B-1, CHARC ruling 2026-09-25).
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
              WHERE (NEW.rowid != -1 AND rowid = NEW.rowid)
                 OR (candidate_id = NEW.candidate_id AND criterion_name = NEW.criterion_name)), 0)
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

-- B2 (Reviewer B pass 2; CHARC ruling, Branch A): view_event_id is FROZEN.
--    latch_view_events' four update guards (trg_lve_identity_coherent_update,
--    trg_lve_actionable_ever_viewed_monotonic, trg_lve_view_window_immutable,
--    trg_lve_first_view_immutable) are all `UPDATE OF` lists and none names
--    view_event_id, so `UPDATE OR REPLACE ... SET view_event_id = <existing>`
--    deleted the holder with no guard firing. An `UPDATE OF view_event_id`
--    list would not close it: `UPDATE OF` is keyed on the column NAME and the
--    rowid is also reachable as rowid / oid / _rowid_ (measured, the B2 fork).
--    A BLANKET trigger comparing the VALUE closes every spelling; a same-value
--    SET is a true no-op and is admitted. The WHEN is `IS`, never NULL; the
--    COALESCE is invariant 2's idiom, kept for uniformity.
CREATE TRIGGER trg_lve_pk_immutable
BEFORE UPDATE ON latch_view_events
FOR EACH ROW
WHEN NOT COALESCE(NEW.view_event_id IS OLD.view_event_id, 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_lve_pk_immutable: latch_view_events.view_event_id is FROZEN from migration 0041. An UPDATE OR REPLACE that moves a row onto another row''s key resolves the conflict by an implicit DELETE of the holder, which does not fire trg_lve_no_delete (recursive_triggers is OFF), and trg_lve_no_replace is BEFORE INSERT and never sees an UPDATE. The rowid is reachable as view_event_id, rowid, oid and _rowid_; this guard compares the value, not the name. The first-view columns are frozen by trg_lve_first_view_immutable; the writer columns stay mutable (RD F-I5). To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

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

-- ============================================================================
-- 8. risk_policy / hypothesis_registry / hypothesis_status_history -- (c) (RD
--    F-I1 rows 7, 8, 9). risk_policy: every policy value immutable; is_active
--    moves 1 -> 0 only (D); effective_to and superseded_by_policy_id are
--    write-once (the supersession writes the flag twice, trades/risk_policy.py:162
--    then :203 -- NEW IS OLD covers the repeat); no_replace scoped to the PK and
--    the partial ux_risk_policy_active. hypothesis_registry: only the writer's
--    three (status, status_changed_at, status_change_reason; trades/
--    hypothesis.py:269-273) move; everything else frozen BY EXCLUSION, so 0034's
--    preregistered_decision_criteria is covered without being named.
--    hypothesis_status_history: effective_to write-once; no_replace scoped to
--    the PK and the partial ux_hypothesis_status_history_current.
-- ============================================================================
CREATE TRIGGER trg_rp_no_delete BEFORE DELETE ON risk_policy
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_rp_no_delete: risk_policy rows are PERMANENT from migration 0041; a risk_policy row is cited by every correction, review and order derivation that stamps it (RD F-I1 row 7). A delete would erase the record and let a rowid be reissued. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_rp_no_replace BEFORE INSERT ON risk_policy
WHEN COALESCE(EXISTS (SELECT 1 FROM risk_policy
              WHERE (NEW.policy_id != -1 AND policy_id = NEW.policy_id)
                 OR (NEW.is_active = 1 AND is_active = 1)), 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_rp_no_replace: risk_policy rows are PERMANENT from migration 0041. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE / ON CONFLICT DO NOTHING) would DELETE the existing row without firing trg_rp_no_delete and reissue or move its id; a risk_policy row is cited by every correction, review and order derivation that stamps it (RD F-I1 row 7). A writer that needs idempotency pre-filters with WHERE NOT EXISTS. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_rp_immutable
BEFORE UPDATE ON risk_policy
FOR EACH ROW
WHEN NOT COALESCE(
      NEW.policy_id IS OLD.policy_id
  AND NEW.effective_from IS OLD.effective_from
  AND NEW.created_at IS OLD.created_at
  AND NEW.policy_notes IS OLD.policy_notes
  AND NEW.max_account_risk_per_trade_pct IS OLD.max_account_risk_per_trade_pct
  AND NEW.max_concurrent_positions IS OLD.max_concurrent_positions
  AND NEW.max_portfolio_heat_pct IS OLD.max_portfolio_heat_pct
  AND NEW.max_sector_concentration_positions IS OLD.max_sector_concentration_positions
  AND NEW.consecutive_losses_pause_threshold IS OLD.consecutive_losses_pause_threshold
  AND NEW.consecutive_losses_pause_action IS OLD.consecutive_losses_pause_action
  AND NEW.consecutive_losses_streak_reset IS OLD.consecutive_losses_streak_reset
  AND NEW.drawdown_circuit_breaker_enabled IS OLD.drawdown_circuit_breaker_enabled
  AND NEW.drawdown_pause_threshold_R IS OLD.drawdown_pause_threshold_R
  AND NEW.drawdown_pause_action IS OLD.drawdown_pause_action
  AND NEW.drawdown_size_reduction_pct IS OLD.drawdown_size_reduction_pct
  AND NEW.drawdown_recovery_threshold_R IS OLD.drawdown_recovery_threshold_R
  AND NEW.capital_floor_constant_dollars IS OLD.capital_floor_constant_dollars
  AND NEW.scratch_epsilon_R IS OLD.scratch_epsilon_R
  AND NEW.review_lag_threshold_days IS OLD.review_lag_threshold_days
  AND NEW.low_sample_size_threshold_class_a_n IS OLD.low_sample_size_threshold_class_a_n
  AND NEW.low_sample_size_threshold_class_b_n IS OLD.low_sample_size_threshold_class_b_n
  AND NEW.low_sample_size_threshold_class_c_n IS OLD.low_sample_size_threshold_class_c_n
  AND NEW.low_sample_size_threshold_class_d_n IS OLD.low_sample_size_threshold_class_d_n
  AND NEW.global_confidence_floor_n IS OLD.global_confidence_floor_n
  AND NEW.bootstrap_resample_count IS OLD.bootstrap_resample_count
  AND NEW.process_grade_weight_entry IS OLD.process_grade_weight_entry
  AND NEW.process_grade_weight_management IS OLD.process_grade_weight_management
  AND NEW.process_grade_weight_exit IS OLD.process_grade_weight_exit
  AND NEW.mfe_mae_default_precision_level IS OLD.mfe_mae_default_precision_level
  AND NEW.trail_MA_period_days IS OLD.trail_MA_period_days
  AND NEW.trail_MA_post_2R_period_days IS OLD.trail_MA_post_2R_period_days
  AND (NEW.effective_to IS OLD.effective_to OR OLD.effective_to IS NULL)
  AND (NEW.superseded_by_policy_id IS OLD.superseded_by_policy_id OR OLD.superseded_by_policy_id IS NULL)
  AND (NEW.is_active IS OLD.is_active OR (OLD.is_active = 1 AND NEW.is_active = 0))
, 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_rp_immutable: risk_policy: this UPDATE changes a column outside the writer''s measured UPDATE set (none); write-once NULL to value: effective_to, superseded_by_policy_id; is_active moves 1 to 0 only; a risk_policy row is cited by every correction, review and order derivation that stamps it (RD F-I1 row 7). To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_hr_no_delete BEFORE DELETE ON hypothesis_registry
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_hr_no_delete: hypothesis_registry rows are PERMANENT from migration 0041; hypothesis_registry is the pre-registration record H1 is pinned against (RD F-I1 row 8). A delete would erase the record and let a rowid be reissued. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_hr_no_replace BEFORE INSERT ON hypothesis_registry
WHEN COALESCE(EXISTS (SELECT 1 FROM hypothesis_registry
              WHERE (NEW.id != -1 AND id = NEW.id)
                 OR (name = NEW.name)), 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_hr_no_replace: hypothesis_registry rows are PERMANENT from migration 0041. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE / ON CONFLICT DO NOTHING) would DELETE the existing row without firing trg_hr_no_delete and reissue or move its id; hypothesis_registry is the pre-registration record H1 is pinned against (RD F-I1 row 8). A writer that needs idempotency pre-filters with WHERE NOT EXISTS. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_hr_immutable
BEFORE UPDATE ON hypothesis_registry
FOR EACH ROW
WHEN NOT COALESCE(
      -- AMENDMENT PRECEDENT (RD F-I1 row 8; CHARC note (i)): a formal amendment
      -- of a pre-registered hypothesis is a MIGRATION that DROPs and re-CREATEs
      -- this twin around its UPDATE (0034 is the precedent), never a writer.
      NEW.id IS OLD.id
  AND NEW.name IS OLD.name
  AND NEW.statement IS OLD.statement
  AND NEW.target_sample_size IS OLD.target_sample_size
  AND NEW.decision_criteria IS OLD.decision_criteria
  AND NEW.consecutive_loss_tripwire IS OLD.consecutive_loss_tripwire
  AND NEW.absolute_loss_tripwire_pct IS OLD.absolute_loss_tripwire_pct
  AND NEW.created_at IS OLD.created_at
  AND NEW.notes IS OLD.notes
  AND NEW.preregistered_decision_criteria IS OLD.preregistered_decision_criteria
, 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_hr_immutable: hypothesis_registry: this UPDATE changes a column outside the writer''s measured UPDATE set (status, status_changed_at, status_change_reason); hypothesis_registry is the pre-registration record H1 is pinned against (RD F-I1 row 8). To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_hsh_no_delete BEFORE DELETE ON hypothesis_status_history
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_hsh_no_delete: hypothesis_status_history rows are PERMANENT from migration 0041; hypothesis_status_history is cited and bound by the citation trigger (RD F-I1 row 9). A delete would erase the record and let a rowid be reissued. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_hsh_no_replace BEFORE INSERT ON hypothesis_status_history
WHEN COALESCE(EXISTS (SELECT 1 FROM hypothesis_status_history
              WHERE (NEW.history_id != -1 AND history_id = NEW.history_id)
                 OR (NEW.effective_to IS NULL AND effective_to IS NULL AND hypothesis_id = NEW.hypothesis_id)), 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_hsh_no_replace: hypothesis_status_history rows are PERMANENT from migration 0041. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE / ON CONFLICT DO NOTHING) would DELETE the existing row without firing trg_hsh_no_delete and reissue or move its id; hypothesis_status_history is cited and bound by the citation trigger (RD F-I1 row 9). A writer that needs idempotency pre-filters with WHERE NOT EXISTS. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_hsh_immutable
BEFORE UPDATE ON hypothesis_status_history
FOR EACH ROW
WHEN NOT COALESCE(
      NEW.history_id IS OLD.history_id
  AND NEW.hypothesis_id IS OLD.hypothesis_id
  AND NEW.status IS OLD.status
  AND NEW.effective_from IS OLD.effective_from
  AND NEW.change_reason IS OLD.change_reason
  AND NEW.recorded_at IS OLD.recorded_at
  AND (NEW.effective_to IS OLD.effective_to OR OLD.effective_to IS NULL)
, 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_hsh_immutable: hypothesis_status_history: this UPDATE changes a column outside the writer''s measured UPDATE set (none); write-once NULL to value: effective_to; hypothesis_status_history is cited and bound by the citation trigger (RD F-I1 row 9). To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

-- ============================================================================
-- 9. daily_management_records -- (c) (RD F-I1 row 10; S3-F2; RD's plan-stage
--    FLIP tightening, 2026-09-24). The immutable set is always frozen; DATA (the
--    reflow SET list, daily_management.py:621-640) moves only while the row is
--    ACTIVE and stays so. Admitted transitions: ACTIVE_STAY (the reflow),
--    FLIP (is_superseded 0 -> 1, DATA frozen -- step 3, :822), WINDOW (the
--    pointer NULL -> value on a just-flipped row -- step 5, :875), FROZEN_FK
--    (pipeline_run_id nulled on a superseded row with its run GONE, a17).
--    is_superseded 1 -> 0 and the self-FK superseded_by_record_id value -> NULL
--    / other have no admitting clause (no SET-NULL exemption on the self-FK: its
--    only cascade is a delete trg_dmr_no_delete refuses). no_replace mirrors
--    both partial UNIQUE indexes.
-- ============================================================================
CREATE TRIGGER trg_dmr_no_delete BEFORE DELETE ON daily_management_records
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_dmr_no_delete: daily_management_records rows are PERMANENT from migration 0041; a superseded snapshot is NEVER updated post-supersede (RD F-I1 row 10, S3-F2, the FLIP tightening). A delete would erase the record and let a rowid be reissued. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_dmr_no_replace BEFORE INSERT ON daily_management_records
WHEN COALESCE(EXISTS (SELECT 1 FROM daily_management_records
              WHERE (NEW.management_record_id != -1 AND management_record_id = NEW.management_record_id)
                 OR (record_type = 'daily_snapshot' AND NEW.record_type = 'daily_snapshot' AND trade_id = NEW.trade_id AND data_asof_session = NEW.data_asof_session AND ((is_superseded = 0 AND NEW.is_superseded = 0) OR mfe_mae_precision_level = NEW.mfe_mae_precision_level))), 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_dmr_no_replace: daily_management_records rows are PERMANENT from migration 0041. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE / ON CONFLICT DO NOTHING) would DELETE the existing row without firing trg_dmr_no_delete and reissue or move its id; a superseded snapshot is NEVER updated post-supersede (RD F-I1 row 10, S3-F2, the FLIP tightening). A writer that needs idempotency pre-filters with WHERE NOT EXISTS. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_dmr_immutable
BEFORE UPDATE ON daily_management_records
FOR EACH ROW
WHEN NOT COALESCE(
      NEW.management_record_id IS OLD.management_record_id
  AND NEW.trade_id IS OLD.trade_id
  AND NEW.record_type IS OLD.record_type
  AND NEW.review_date IS OLD.review_date
  AND NEW.data_asof_session IS OLD.data_asof_session
  AND NEW.mfe_mae_precision_level IS OLD.mfe_mae_precision_level
  AND NEW.thesis_status IS OLD.thesis_status
  AND NEW.prior_stop IS OLD.prior_stop
  AND NEW.new_stop IS OLD.new_stop
  AND NEW.stop_changed IS OLD.stop_changed
  AND NEW.stop_change_reason IS OLD.stop_change_reason
  AND NEW.volume_behavior IS OLD.volume_behavior
  AND NEW.relative_strength_status IS OLD.relative_strength_status
  AND NEW.market_regime_change IS OLD.market_regime_change
  AND NEW.sector_condition_change IS OLD.sector_condition_change
  AND NEW.news_or_event_update IS OLD.news_or_event_update
  AND NEW.action_taken IS OLD.action_taken
  AND NEW.action_reason IS OLD.action_reason
  AND NEW.emotional_state IS OLD.emotional_state
  AND NEW.rule_violation_suspected IS OLD.rule_violation_suspected
  AND NEW.management_notes IS OLD.management_notes
  AND (NEW.linked_trade_event_id IS OLD.linked_trade_event_id
        OR (OLD.linked_trade_event_id IS NOT NULL AND NEW.linked_trade_event_id IS NULL
            AND NOT EXISTS (SELECT 1 FROM trade_events WHERE id = OLD.linked_trade_event_id)))
  AND (      -- ACTIVE_STAY: the reflow (daily_management.py:621); DATA free
          (OLD.is_superseded = 0 AND OLD.superseded_by_record_id IS NULL
             AND NEW.is_superseded = 0 AND NEW.superseded_by_record_id IS NULL)
       -- FLIP: step 3 (:822), is_superseded 0 -> 1, DATA frozen (RD tightening)
       OR (OLD.is_superseded = 0 AND NEW.is_superseded = 1
             AND OLD.superseded_by_record_id IS NULL AND NEW.superseded_by_record_id IS NULL
             AND NEW.current_price IS OLD.current_price
             AND NEW.current_stop IS OLD.current_stop
             AND NEW.current_size IS OLD.current_size
             AND NEW.current_avg_cost IS OLD.current_avg_cost
             AND NEW.open_R_effective IS OLD.open_R_effective
             AND NEW.open_MFE_R_to_date IS OLD.open_MFE_R_to_date
             AND NEW.open_MAE_R_to_date IS OLD.open_MAE_R_to_date
             AND NEW.intraday_high IS OLD.intraday_high
             AND NEW.intraday_low IS OLD.intraday_low
             AND NEW.position_capital_utilization_pct IS OLD.position_capital_utilization_pct
             AND NEW.position_capital_denominator_dollars IS OLD.position_capital_denominator_dollars
             AND NEW.position_portfolio_heat_contribution_dollars IS OLD.position_portfolio_heat_contribution_dollars
             AND NEW.maturity_stage IS OLD.maturity_stage
             AND NEW.trail_MA_candidate_price IS OLD.trail_MA_candidate_price
             AND NEW.trail_MA_period_days IS OLD.trail_MA_period_days
             AND NEW.trail_MA_eligibility_flag IS OLD.trail_MA_eligibility_flag
             AND NEW.pipeline_run_id IS OLD.pipeline_run_id
             AND NEW.created_at IS OLD.created_at)
       -- WINDOW: step 5 (:875), the pointer NULL -> value (S3-F2)
       OR (OLD.is_superseded = 1 AND OLD.superseded_by_record_id IS NULL
             AND NEW.is_superseded = 1 AND NEW.superseded_by_record_id IS NOT NULL
             AND NEW.current_price IS OLD.current_price
             AND NEW.current_stop IS OLD.current_stop
             AND NEW.current_size IS OLD.current_size
             AND NEW.current_avg_cost IS OLD.current_avg_cost
             AND NEW.open_R_effective IS OLD.open_R_effective
             AND NEW.open_MFE_R_to_date IS OLD.open_MFE_R_to_date
             AND NEW.open_MAE_R_to_date IS OLD.open_MAE_R_to_date
             AND NEW.intraday_high IS OLD.intraday_high
             AND NEW.intraday_low IS OLD.intraday_low
             AND NEW.position_capital_utilization_pct IS OLD.position_capital_utilization_pct
             AND NEW.position_capital_denominator_dollars IS OLD.position_capital_denominator_dollars
             AND NEW.position_portfolio_heat_contribution_dollars IS OLD.position_portfolio_heat_contribution_dollars
             AND NEW.maturity_stage IS OLD.maturity_stage
             AND NEW.trail_MA_candidate_price IS OLD.trail_MA_candidate_price
             AND NEW.trail_MA_period_days IS OLD.trail_MA_period_days
             AND NEW.trail_MA_eligibility_flag IS OLD.trail_MA_eligibility_flag
             AND NEW.pipeline_run_id IS OLD.pipeline_run_id
             AND NEW.created_at IS OLD.created_at)
       -- FROZEN_FK: only the FK-driven nulling of pipeline_run_id (a17)
       OR (OLD.is_superseded = 1 AND NEW.is_superseded = 1
             AND NEW.superseded_by_record_id IS OLD.superseded_by_record_id
             AND NEW.current_price IS OLD.current_price
             AND NEW.current_stop IS OLD.current_stop
             AND NEW.current_size IS OLD.current_size
             AND NEW.current_avg_cost IS OLD.current_avg_cost
             AND NEW.open_R_effective IS OLD.open_R_effective
             AND NEW.open_MFE_R_to_date IS OLD.open_MFE_R_to_date
             AND NEW.open_MAE_R_to_date IS OLD.open_MAE_R_to_date
             AND NEW.intraday_high IS OLD.intraday_high
             AND NEW.intraday_low IS OLD.intraday_low
             AND NEW.position_capital_utilization_pct IS OLD.position_capital_utilization_pct
             AND NEW.position_capital_denominator_dollars IS OLD.position_capital_denominator_dollars
             AND NEW.position_portfolio_heat_contribution_dollars IS OLD.position_portfolio_heat_contribution_dollars
             AND NEW.maturity_stage IS OLD.maturity_stage
             AND NEW.trail_MA_candidate_price IS OLD.trail_MA_candidate_price
             AND NEW.trail_MA_period_days IS OLD.trail_MA_period_days
             AND NEW.trail_MA_eligibility_flag IS OLD.trail_MA_eligibility_flag
             AND NEW.created_at IS OLD.created_at
             AND (NEW.pipeline_run_id IS OLD.pipeline_run_id
              OR (OLD.pipeline_run_id IS NOT NULL AND NEW.pipeline_run_id IS NULL
                  AND NOT EXISTS (SELECT 1 FROM pipeline_runs WHERE id = OLD.pipeline_run_id)))))
, 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_dmr_immutable: daily_management_records: an UPDATE outside the admitted transitions: ACTIVE_STAY (the reflow), FLIP (is_superseded 0 to 1, data frozen), WINDOW (the supersede pointer NULL to value) or FROZEN_FK (pipeline_run_id nulled after its run is gone); a superseded snapshot is NEVER updated post-supersede (RD F-I1 row 10, S3-F2, the FLIP tightening). To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

-- ============================================================================
-- 10. review_log -- (c) (RD F-I1 row 17; S3-F3 (A); S3-F4 (i)). The barrier
--    pair: no_delete, and no_replace scoped to the PK and the UNIQUE cadence key
--    ux_review_log_cadence_period (review_type, period_start, period_end). The
--    nightly writer insert_pre_create (repos/review_log.py, runner.py:4207)
--    pre-filters with WHERE NOT EXISTS (F-I3, CHARC S3-F4 (i)), so its
--    idempotent no-op never reaches this barrier; the barrier is NEVER narrowed
--    to admit it. The RAISE text deliberately does NOT contain the word the
--    writer's retained belt matches (UNIQUE / the index name), so the belt can
--    never become a second, string-matched mechanism ((ii) refused).
-- ============================================================================
CREATE TRIGGER trg_rl_no_delete BEFORE DELETE ON review_log
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_rl_no_delete: review_log rows are PERMANENT from migration 0041; a completed review freezes the operator''s process-review aggregates (RD F-I1 row 17, S3-F3 (A)). A delete would erase the record and let a rowid be reissued. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_rl_no_replace BEFORE INSERT ON review_log
WHEN COALESCE(EXISTS (SELECT 1 FROM review_log
              WHERE (NEW.review_id != -1 AND review_id = NEW.review_id)
                 OR (review_type = NEW.review_type AND period_start = NEW.period_start AND period_end = NEW.period_end)), 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_rl_no_replace: review_log rows are PERMANENT from migration 0041. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE / ON CONFLICT DO NOTHING) on the PK or the cadence key (review_type, period_start, period_end) would DELETE the existing row without firing trg_rl_no_delete and reissue or move its id; a completed review freezes the operator''s process-review aggregates (RD F-I1 row 17, S3-F3 (A)). A writer that needs idempotency pre-filters with WHERE NOT EXISTS. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

-- review_log's twin (S3-F3 (A)): I (review_id, review_type, period_start,
-- period_end, scheduled_date, skipped, created_at) frozen ALWAYS; the S set
-- (completed_date, the aggregates, the completion text) frozen once
-- OLD.completed_date IS NOT NULL, with risk_policy_id_at_review_completion
-- F-shaped while frozen (a17; DEAD-BY-PARENT-GUARD, trg_rp_no_delete);
-- superseded_by_correction_id is M (reconciliation_auto_correct.py:2404
-- overwrites it unconditionally). Its SERVICE TWIN ships FIRST (T12a):
-- complete_review_atomic refuses a completed row with
-- ReviewAlreadyCompletedError before any UPDATE, so this refusal is
-- unreachable through the service (authorize-then-abort, harness 5.1).
CREATE TRIGGER trg_rl_immutable
BEFORE UPDATE ON review_log
FOR EACH ROW
WHEN NOT COALESCE(
      NEW.review_id IS OLD.review_id
  AND NEW.review_type IS OLD.review_type
  AND NEW.period_start IS OLD.period_start
  AND NEW.period_end IS OLD.period_end
  AND NEW.scheduled_date IS OLD.scheduled_date
  AND NEW.skipped IS OLD.skipped
  AND NEW.created_at IS OLD.created_at
  AND (      -- PENDING: the pre-completion row stays writable (the completion itself)
          OLD.completed_date IS NULL
       -- FROZEN: once completed, the aggregates + completion text never move
       OR (NEW.completed_date IS OLD.completed_date
             AND NEW.duration_minutes IS OLD.duration_minutes
             AND NEW.n_trades_reviewed IS OLD.n_trades_reviewed
             AND NEW.primary_lesson IS OLD.primary_lesson
             AND NEW.next_period_focus IS OLD.next_period_focus
             AND NEW.total_mistake_cost_R IS OLD.total_mistake_cost_R
             AND NEW.total_lucky_violation_R IS OLD.total_lucky_violation_R
             AND NEW.net_R_effective IS OLD.net_R_effective
             AND NEW.expectancy_R_effective IS OLD.expectancy_R_effective
             AND NEW.win_rate IS OLD.win_rate
             AND NEW.avg_win_R IS OLD.avg_win_R
             AND NEW.avg_loss_R IS OLD.avg_loss_R
             AND NEW.profit_factor IS OLD.profit_factor
             AND NEW.max_drawdown_R IS OLD.max_drawdown_R
             AND NEW.auto_populated_field_keys_json IS OLD.auto_populated_field_keys_json
             AND (NEW.risk_policy_id_at_review_completion IS OLD.risk_policy_id_at_review_completion
                  OR (OLD.risk_policy_id_at_review_completion IS NOT NULL AND NEW.risk_policy_id_at_review_completion IS NULL
                      AND NOT EXISTS (SELECT 1 FROM risk_policy WHERE policy_id = OLD.risk_policy_id_at_review_completion)))))
, 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_rl_immutable: review_log: this UPDATE changes an identity column (review_id, review_type, period_start, period_end, scheduled_date, skipped, created_at), or a frozen aggregate / completion field of an ALREADY-completed review (only superseded_by_correction_id moves after completion; risk_policy_id_at_review_completion is nulled only after its policy row is gone); a completed review freezes the operator''s process-review aggregates (RD F-I1 row 17, S3-F3 (A)). To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

-- ============================================================================
-- 11. pattern_exemplars / watchlist_archive -- (c) with NO twin (RD F-I1 rows
--    15, 18; AL-11): labels and removed_date are edited in place BY DESIGN, so
--    the barrier pair lands -- no_delete, and no_replace scoped to the PK
--    (neither table declares a UNIQUE key) -- plus a PK freeze (Reviewer B B2;
--    CHARC ruling, Branch A): without an update guard, `UPDATE OR REPLACE ...
--    SET id = <existing>` deleted the holder with no barrier firing. The freeze
--    is a BLANKET BEFORE UPDATE comparing the VALUE of id, because the rowid is
--    reachable as id / rowid / oid / _rowid_ and an `UPDATE OF id` list sees
--    only the first (the B2 fork). Every non-PK column stays mutable at the
--    schema (AL-11). The sole INSERT writers (repos/pattern_exemplars.py:91,
--    repos/watchlist.py:89) omit the PK, so an ordinary append never reaches
--    the barrier, and no production writer names id in a SET list.
-- ============================================================================
CREATE TRIGGER trg_pex_no_delete BEFORE DELETE ON pattern_exemplars
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_pex_no_delete: pattern_exemplars rows are PERMANENT from migration 0041; an exemplar is an audit-trail-with-uniqueness row whose id parent_exemplar_id cites (RD F-I1 row 15). A delete would erase the record and let a rowid be reissued. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_pex_no_replace BEFORE INSERT ON pattern_exemplars
WHEN COALESCE(EXISTS (SELECT 1 FROM pattern_exemplars
              WHERE (NEW.id != -1 AND id = NEW.id)), 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_pex_no_replace: pattern_exemplars rows are PERMANENT from migration 0041. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE / ON CONFLICT DO NOTHING) would DELETE the existing row without firing trg_pex_no_delete and reissue or move its id; an exemplar is an audit-trail-with-uniqueness row whose id parent_exemplar_id cites (RD F-I1 row 15). A writer that needs idempotency pre-filters with WHERE NOT EXISTS. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_wla_no_delete BEFORE DELETE ON watchlist_archive
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_wla_no_delete: watchlist_archive rows are PERMANENT from migration 0041; the watchlist archive is an audit trail of every removal (RD F-I1 row 18). A delete would erase the record and let a rowid be reissued. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_wla_no_replace BEFORE INSERT ON watchlist_archive
WHEN COALESCE(EXISTS (SELECT 1 FROM watchlist_archive
              WHERE (NEW.id != -1 AND id = NEW.id)), 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_wla_no_replace: watchlist_archive rows are PERMANENT from migration 0041. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE / ON CONFLICT DO NOTHING) would DELETE the existing row without firing trg_wla_no_delete and reissue or move its id; the watchlist archive is an audit trail of every removal (RD F-I1 row 18). A writer that needs idempotency pre-filters with WHERE NOT EXISTS. To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_pex_pk_immutable
BEFORE UPDATE ON pattern_exemplars
FOR EACH ROW
WHEN NOT COALESCE(NEW.id IS OLD.id, 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_pex_pk_immutable: pattern_exemplars.id is FROZEN from migration 0041. An UPDATE OR REPLACE that moves a row onto another row''s key resolves the conflict by an implicit DELETE of the holder, which does not fire trg_pex_no_delete (recursive_triggers is OFF), and trg_pex_no_replace is BEFORE INSERT and never sees an UPDATE. The rowid is reachable as id, rowid, oid and _rowid_; this guard compares the value, not the name. Every other column stays mutable at the schema (plan AL-11). To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

CREATE TRIGGER trg_wla_pk_immutable
BEFORE UPDATE ON watchlist_archive
FOR EACH ROW
WHEN NOT COALESCE(NEW.id IS OLD.id, 0)
BEGIN SELECT RAISE(ABORT, '22-I barrier trg_wla_pk_immutable: watchlist_archive.id is FROZEN from migration 0041. An UPDATE OR REPLACE that moves a row onto another row''s key resolves the conflict by an implicit DELETE of the holder, which does not fire trg_wla_no_delete (recursive_triggers is OFF), and trg_wla_no_replace is BEFORE INSERT and never sees an UPDATE. The rowid is reachable as id, rowid, oid and _rowid_; this guard compares the value, not the name. Every other column stays mutable at the schema (plan AL-11). To retire the barrier see the reversibility header of 0041_replace_exposure_sweep.sql.'); END;

-- The version bump is the FINAL statement before COMMIT.
UPDATE schema_version SET version = 41;

COMMIT;
