-- 0040_entry_intent_unintended_execution.sql -- Arc 22-B (Demand A).
--
-- The third `trades.entry_intent` value, `unintended_execution` (an execution
-- nobody decided to make), and its evidence-bearing assignment surface. One
-- transaction, the runner's; `foreign_keys=OFF` at the runner, so
-- `PRAGMA foreign_key_check` after the RENAME is asserted by test. Bumps
-- schema_version 39 -> 40.
--
-- REVERSIBILITY HEADER
--
-- (i) THE ONE EDIT to the `trades` DDL (F6: nothing else rides this rebuild).
--     The new DDL is the STORED v39 `trades` text with exactly one change:
--         entry_intent IN ('standard','hypothesis_test_by_design')
--     becomes
--         entry_intent IN ('standard','hypothesis_test_by_design','unintended_execution')
--     Reversing it is the same rebuild with the IN-list restored, which
--     fails loudly while any row carries the third value.
--
-- (ii) EVERY OBJECT THIS MIGRATION CREATES, each with its retiring statement:
--         DROP TRIGGER trg_trades_entry_intent_attested_terminal;  -- trades (N4)
--         DROP TRIGGER trg_lve_actionable_ever_viewed_monotonic;   -- latch_view_events
--         DROP TRIGGER trg_lve_no_delete;                          -- latch_view_events
--         DROP TRIGGER trg_lve_no_replace;                         -- latch_view_events
--         DROP TRIGGER trg_lve_view_window_immutable;              -- latch_view_events
--
-- (iii) THE FIVE `trades` DEPENDANTS, dropped with the old table and
--     re-created VERBATIM from their SOURCE migrations:
--         ux_trades_one_open_per_ticker     0014:230 (the partial UNIQUE)
--         idx_trades_candidate_id           0021:39
--         idx_trades_pattern_evaluation_id  0021:41
--         ux_trades_attempt_id              0038:113
--         trg_trades_attempt_id_immutable   0038:117
--
-- (iv) THE GATE: BackupGateSpec(39, "22b", PHASE22_ARC_B_PRE_MIGRATION_EXPECTED_TABLES,
--     "_phase22_arc_b_backup_gate", "pre-22-B") in swing/data/db.py, clause
--     `pre_version == 39 AND target_version >= 40`.
--
-- (v) THE F1 PIN:
-- clause (4) sha256: 5a78e547f64df25e0f891bd271c8d5e51bbd884866ca6d04c6c85b7803ef3886 (docs/training-epoch-intent-contract.md; derived by test, never read at runtime)
--
-- (vi) `trades` has NO AUTOINCREMENT (`id INTEGER PRIMARY KEY`) -- no sequence
--     carry (NOT 0039's sqlite_sequence step).
--
-- (vii) THE R0.J CENSUS -- the precondition the RENAME bracket was proven
--     against (CHARC-ruled, condition (iv)). Method:
--         SELECT type, name FROM sqlite_master
--         WHERE sql LIKE '%trades%' AND tbl_name <> 'trades'
--           AND type IN ('trigger','view')
--     (a textual superset of every reference) -> 1 row,
--     trg_provenance_corrections_citation_graph; 0 views; 0 objects name
--     trades_new, so legacy mode has no rewrite to skip. SQLite's modern
--     RENAME re-parses every trigger, and that trigger names `trades`, which
--     the DROP has just removed; the bracket below makes the RENAME legacy.
--     A later foreign object referencing `trades` is covered by the same
--     bracket; this header records which objects it was proven against.

BEGIN;

-- 1. The new table: the stored v39 DDL, one edit, the table name.
CREATE TABLE "trades_new" (
  id INTEGER PRIMARY KEY,
  ticker TEXT NOT NULL,
  entry_date TEXT NOT NULL,
  entry_price REAL NOT NULL,
  initial_shares INTEGER NOT NULL,
  initial_stop REAL NOT NULL,
  current_stop REAL NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('entered','managing','partial_exited','closed','reviewed')),
  watchlist_entry_target REAL,
  watchlist_initial_stop REAL,
  notes TEXT,
  hypothesis_label TEXT,
  chart_pattern_algo TEXT,
  chart_pattern_algo_confidence REAL,
  chart_pattern_operator TEXT,
  chart_pattern_classification_pipeline_run_id INTEGER,
  sector TEXT NOT NULL DEFAULT '',
  industry TEXT NOT NULL DEFAULT '',
  reviewed_at TEXT,
  mistake_tags TEXT,
  entry_grade TEXT,
  management_grade TEXT,
  exit_grade TEXT,
  process_grade TEXT,
  disqualifying_process_violation INTEGER,
  realized_R_if_plan_followed REAL,
  mistake_cost_confidence TEXT
      CHECK (mistake_cost_confidence IS NULL OR mistake_cost_confidence IN ('high','medium','low')),
  lesson_learned TEXT,
  trade_origin TEXT NOT NULL CHECK (trade_origin IN
      ('pipeline_aplus','pipeline_watch_hyp_recs','pipeline_watch_manual','manual_off_pipeline')),
  pre_trade_locked_at TEXT NOT NULL,
  current_size REAL NOT NULL DEFAULT 0,
  current_avg_cost REAL,
  last_fill_at TEXT,
  thesis TEXT,
  why_now TEXT,
  invalidation_condition TEXT,
  expected_scenario TEXT,
  premortem_technical TEXT,
  premortem_market_sector TEXT,
  premortem_execution TEXT,
  premortem_additional TEXT,
  event_risk_present INTEGER CHECK (event_risk_present IS NULL OR event_risk_present IN (0,1)),
  event_handling TEXT
      CHECK (event_handling IS NULL OR event_handling IN
        ('avoid_event','hold_through','reduce_before','exit_before','not_applicable')),
  event_type TEXT
      CHECK (event_type IS NULL OR event_type IN
        ('earnings','fed_meeting','cpi_release','economic_data','product_announcement','legal_ruling','other')),
  event_date TEXT,
  gap_risk_present INTEGER CHECK (gap_risk_present IS NULL OR gap_risk_present IN (0,1)),
  gap_risk_handling TEXT
      CHECK (gap_risk_handling IS NULL OR gap_risk_handling IN
        ('accept','reduce_size','tight_stop','exit_before_close','not_applicable')),
  emotional_state_pre_trade TEXT,
  market_regime TEXT
      CHECK (market_regime IS NULL OR market_regime IN ('Bullish','Caution','Bearish')),
  catalyst TEXT
      CHECK (catalyst IS NULL OR catalyst IN
        ('earnings_driven','guidance_change','corporate_action','sector_rotation',
         'macro_event','sympathy_move','product_news','technical_only','other')),
  catalyst_other_description TEXT
, planned_target_R REAL
    CHECK (planned_target_R IS NULL OR planned_target_R > 0), risk_policy_id_at_lock INTEGER
    REFERENCES risk_policy(policy_id) ON DELETE SET NULL, candidate_id INTEGER
    REFERENCES candidates(id) ON DELETE SET NULL, pattern_evaluation_id INTEGER
    REFERENCES pattern_evaluations(id) ON DELETE SET NULL, failure_mode TEXT
    CHECK (failure_mode IS NULL OR failure_mode IN (
        'thesis_invalidated', 'normal_volatility_stop', 'market_regime_shift',
        'adverse_event_shock', 'execution_error', 'failed_to_advance', 'other'
    )), entry_intent TEXT
    CHECK (entry_intent IS NULL OR entry_intent IN ('standard','hypothesis_test_by_design','unintended_execution')), attempt_id TEXT
  CHECK (attempt_id IS NULL
         OR (typeof(attempt_id) = 'text' AND length(attempt_id) = 36)));

INSERT INTO trades_new (
    id,
    ticker,
    entry_date,
    entry_price,
    initial_shares,
    initial_stop,
    current_stop,
    state,
    watchlist_entry_target,
    watchlist_initial_stop,
    notes,
    hypothesis_label,
    chart_pattern_algo,
    chart_pattern_algo_confidence,
    chart_pattern_operator,
    chart_pattern_classification_pipeline_run_id,
    sector,
    industry,
    reviewed_at,
    mistake_tags,
    entry_grade,
    management_grade,
    exit_grade,
    process_grade,
    disqualifying_process_violation,
    realized_R_if_plan_followed,
    mistake_cost_confidence,
    lesson_learned,
    trade_origin,
    pre_trade_locked_at,
    current_size,
    current_avg_cost,
    last_fill_at,
    thesis,
    why_now,
    invalidation_condition,
    expected_scenario,
    premortem_technical,
    premortem_market_sector,
    premortem_execution,
    premortem_additional,
    event_risk_present,
    event_handling,
    event_type,
    event_date,
    gap_risk_present,
    gap_risk_handling,
    emotional_state_pre_trade,
    market_regime,
    catalyst,
    catalyst_other_description,
    planned_target_R,
    risk_policy_id_at_lock,
    candidate_id,
    pattern_evaluation_id,
    failure_mode,
    entry_intent,
    attempt_id
)
SELECT
    id,
    ticker,
    entry_date,
    entry_price,
    initial_shares,
    initial_stop,
    current_stop,
    state,
    watchlist_entry_target,
    watchlist_initial_stop,
    notes,
    hypothesis_label,
    chart_pattern_algo,
    chart_pattern_algo_confidence,
    chart_pattern_operator,
    chart_pattern_classification_pipeline_run_id,
    sector,
    industry,
    reviewed_at,
    mistake_tags,
    entry_grade,
    management_grade,
    exit_grade,
    process_grade,
    disqualifying_process_violation,
    realized_R_if_plan_followed,
    mistake_cost_confidence,
    lesson_learned,
    trade_origin,
    pre_trade_locked_at,
    current_size,
    current_avg_cost,
    last_fill_at,
    thesis,
    why_now,
    invalidation_condition,
    expected_scenario,
    premortem_technical,
    premortem_market_sector,
    premortem_execution,
    premortem_additional,
    event_risk_present,
    event_handling,
    event_type,
    event_date,
    gap_risk_present,
    gap_risk_handling,
    emotional_state_pre_trade,
    market_regime,
    catalyst,
    catalyst_other_description,
    planned_target_R,
    risk_policy_id_at_lock,
    candidate_id,
    pattern_evaluation_id,
    failure_mode,
    entry_intent,
    attempt_id
FROM trades;

-- 2. Drop the old table (takes its five dependants).
DROP TABLE trades;

-- 3. The RENAME, inside a bracket exactly two statements wide (R0.J).
-- R0.J: modern RENAME re-parses every trigger; 0039's cross-table trg_provenance_corrections_citation_graph names trades.
PRAGMA legacy_alter_table=ON;
ALTER TABLE trades_new RENAME TO trades;
PRAGMA legacy_alter_table=OFF;

-- 4. The five dependants, VERBATIM from their sources (header (iii)).
CREATE UNIQUE INDEX ux_trades_one_open_per_ticker
  ON trades(ticker) WHERE state IN ('entered','managing','partial_exited');

CREATE INDEX idx_trades_candidate_id ON trades(candidate_id);

CREATE INDEX idx_trades_pattern_evaluation_id
    ON trades(pattern_evaluation_id);

CREATE UNIQUE INDEX ux_trades_attempt_id
  ON trades(attempt_id) WHERE attempt_id IS NOT NULL;

CREATE TRIGGER trg_trades_attempt_id_immutable
BEFORE UPDATE OF attempt_id ON trades
BEGIN SELECT RAISE(ABORT, '22-A4 barrier trg_trades_attempt_id_immutable: trades.attempt_id is WRITE-ONCE. It is minted per attempt and written by the INSERT that creates the row, in that same transaction; a token that can be re-assigned afterwards is not an identity, and the settle-by-identity read would then confirm the wrong attempt. To retire the barrier see the reversibility header of 0038_trade_attempt_identity.sql.'); END;

-- 5. N4 layer 3 (CHARC-ruled): the value is TERMINAL for every writer. Both
--    WHEN operands are non-NULL by construction (COALESCE; IS NOT), so the
--    WHEN can never evaluate NULL. A same-value UPDATE passes; NULL -> the
--    value passes (the assignment path).
CREATE TRIGGER trg_trades_entry_intent_attested_terminal
BEFORE UPDATE OF entry_intent ON trades
FOR EACH ROW
WHEN COALESCE(OLD.entry_intent,'') = 'unintended_execution'
 AND NEW.entry_intent IS NOT OLD.entry_intent
BEGIN SELECT RAISE(ABORT, 'entry_intent is attested (an entry_intent_attestations row exists); no reversal surface exists -- a reversal is a NEW evidence class with its own record'); END;

-- 6. The FOUR latch_view_events evidence belts (R0.G/R0.H; R0.K). Leg 1 of
--    the tier-2 admission reads this table, so it earns the barriers: every
--    column the leg READS is a column the schema GUARDS. The sole production
--    writer (swing/data/repos/latch_view_events.py record_view) is unchanged:
--    its UPDATE sets last_viewed_ts, latch_state_at_last_view,
--    actionable_at_last_view, view_count and actionable_ever_viewed (via MAX),
--    and its plain INSERT's lost-race `except sqlite3.IntegrityError` catches
--    the no_replace ABORT and takes the UPDATE path.
CREATE TRIGGER trg_lve_actionable_ever_viewed_monotonic
BEFORE UPDATE OF actionable_ever_viewed ON latch_view_events
FOR EACH ROW
WHEN NOT COALESCE(NEW.actionable_ever_viewed >= OLD.actionable_ever_viewed, 0)
BEGIN SELECT RAISE(ABORT, 'latch_view_events actionable_ever_viewed is monotonic (0 -> 1 only): leg-1 evidence (22-B R0.G)'); END;

CREATE TRIGGER trg_lve_no_delete
BEFORE DELETE ON latch_view_events
FOR EACH ROW
BEGIN SELECT RAISE(ABORT, 'latch_view_events rows cannot be deleted: leg-1 evidence (22-B R0.G)'); END;

-- The 0037 trg_loml_no_replace shape: the PK conflict clause (an omitted
-- INTEGER PRIMARY KEY presents as -1 inside a BEFORE INSERT trigger) OR the
-- 0033 UNIQUE key. EXISTS is never NULL.
CREATE TRIGGER trg_lve_no_replace
BEFORE INSERT ON latch_view_events
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM latch_view_events
             WHERE (NEW.view_event_id != -1 AND view_event_id = NEW.view_event_id)
                OR (candidate_id = NEW.candidate_id
                    AND view_session_date = NEW.view_session_date
                    AND surface = NEW.surface))
BEGIN SELECT RAISE(ABORT, 'latch_view_events: a conflicting INSERT (INSERT OR REPLACE / REPLACE) would rewrite leg-1 evidence (22-B R0.H)'); END;

CREATE TRIGGER trg_lve_view_window_immutable
BEFORE UPDATE OF first_viewed_ts, ticker ON latch_view_events
FOR EACH ROW
BEGIN SELECT RAISE(ABORT, 'latch_view_events first_viewed_ts and ticker are immutable: leg-1 evidence window (22-B R0.K)'); END;

-- 7. (0040 part 2 -- entry_intent_attestations and its two trades twins --
--    is appended here.)

-- 8. The version bump is the FINAL statement before COMMIT.
UPDATE schema_version SET version = 40;

COMMIT;
