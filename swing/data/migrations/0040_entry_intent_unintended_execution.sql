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
--         DROP TRIGGER trg_trades_entry_intent_unattested_update;  -- trades (CHARC-S3)
--         DROP TRIGGER trg_trades_entry_intent_unattested_insert;  -- trades (CHARC-S3)
--         DROP TRIGGER trg_eia_trade_binding;                      -- entry_intent_attestations
--         DROP TRIGGER trg_eia_cited_fields;
--         DROP TRIGGER trg_eia_audit_trail;
--         DROP TRIGGER trg_eia_outcome;
--         DROP TRIGGER trg_eia_tier2;
--         DROP TRIGGER trg_eia_structural;
--         DROP TRIGGER trg_eia_no_update;
--         DROP TRIGGER trg_eia_no_delete;
--         DROP TRIGGER trg_eia_no_replace;
--         DROP TABLE entry_intent_attestations;  -- after the two twins (they name it)
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
--
--     BESIDE IT (CHARC-S3.2), the censuses this migration leaves for any FUTURE
--     rebuild, measured on a target_version=40 image by the same method:
--       * entry_intent_attestations (`sql LIKE '%entry_intent_attestations%'
--         AND tbl_name <> 'entry_intent_attestations'`) -> TWO rows:
--         trg_trades_entry_intent_unattested_update (a real reference: its
--         WHEN reads the table) and trg_trades_entry_intent_attested_terminal
--         (a textual hit only: the name appears in its RAISE message). The
--         INSERT twin does not name the table (it refuses the value outright);
--       * trades -> FIVE rows: trg_provenance_corrections_citation_graph (the
--         v39 row above) plus this migration's trg_eia_trade_binding,
--         trg_eia_cited_fields, trg_eia_audit_trail and trg_eia_tier2;
--       * fill_envelope_identity (`sql LIKE '%fill_envelope_identity%' AND
--         tbl_name <> 'fill_envelope_identity'`) -> TWO rows (RULING G1b):
--         trg_provenance_corrections_citation_graph (the v39 reader) and
--         this migration's trg_eia_trade_binding, which binds the STORED
--         envelope reading. No object in this migration reads a fill's
--         envelope itself (the 22-A sweep test is the check).
--
-- (viii) DECLARED LIMITATION (CHARC, G1 (d)): 0037 pairs the PK clause of
--     trg_loml_no_replace with CHECK (link_id > 0) (0037:340), but
--     latch_view_events carries no CHECK (view_event_id > 0) and adding one
--     would be a rebuild of that table, out of 0040, so an explicit
--     view_event_id of -1 is storable and a later REPLACE on it bypasses
--     trg_lve_no_replace's PK clause -- the fabrication class, outside the
--     threat model under R0.K.

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

-- 7. entry_intent_attestations -- its SCHEMA IS THE EVIDENCE RULE (the 0036
--    pattern). One row per assignment of `unintended_execution`, append-only,
--    written ONLY by `swing trade assign-intent` (swing/trades/
--    entry_intent_assignment.py -> swing/data/repos/entry_intent_attestations.py)
--    in ONE BEGIN IMMEDIATE: this row FIRST, then the `trades` UPDATE. Every
--    admission trigger below is the SQL twin of a service check
--    (AUTHORIZE-THEN-ABORT: the trigger predicate set is a subset of the
--    service's); every validation WHEN is `NOT COALESCE(<predicate>, 0)`, and
--    every JSON column of THIS table read by a trigger goes through a
--    json_valid guard (json_each / json_extract on malformed text RAISE, even
--    behind AND). No trigger reads a fill's envelope (RULING G1b, 22-A
--    PERSIST-CANONICAL): the order id is bound to the authority's STORED
--    reading in fill_envelope_identity, and placement_session is a
--    service-only derivation SQL stores and bounds but never re-reads.
--    The row carries NO P&L, MFE or MAE: running state is not evidence.
CREATE TABLE entry_intent_attestations (
    -- An OMITTED integer PK presents as -1 inside a BEFORE INSERT trigger; the
    -- CHECK makes -1 unstorable, so trg_eia_no_replace can ignore it (the
    -- 0037 fill_envelope_identity convention).
    attestation_id INTEGER PRIMARY KEY AUTOINCREMENT CHECK (attestation_id > 0),
    trade_id INTEGER NOT NULL UNIQUE REFERENCES trades(id) ON DELETE RESTRICT,
    assigned_value TEXT NOT NULL CHECK (assigned_value = 'unintended_execution'),
    admission_tier TEXT NOT NULL
        CHECK (admission_tier IN ('structural','contemporaneous_record')),
    trade_entry_date TEXT NOT NULL
        CHECK (COALESCE(length(trade_entry_date) = 10
               AND date(trade_entry_date) IS NOT NULL
               AND date(trade_entry_date) = trade_entry_date
               AND CAST(substr(trade_entry_date, 1, 4) AS INTEGER) BETWEEN 1 AND 9999, 0)),
    -- The 0039 shape (R3-05): ON DELETE SET NULL, never RESTRICT -- evidence
    -- bookkeeping never blocks a money-bearing operation (split_into_partials
    -- DELETEs the consolidated fill). The pointer may go NULL; the frozen
    -- NUMBER is what the binding trigger and the drift reader compare against.
    entry_fill_id INTEGER REFERENCES fills(fill_id) ON DELETE SET NULL,
    entry_fill_id_at_assignment INTEGER NOT NULL,
    entry_broker_order_id TEXT,
    -- ===== tier 2 (contemporaneous_record) =====
    placement_session TEXT
        CHECK (placement_session IS NULL OR COALESCE(length(placement_session) = 10
               AND date(placement_session) IS NOT NULL
               AND date(placement_session) = placement_session
               AND CAST(substr(placement_session, 1, 4) AS INTEGER) BETWEEN 1 AND 9999, 0)),
    placement_session_source TEXT
        CHECK (placement_session_source IN ('schwab_envelope','entry_date_fallback')),
    admitted_leg TEXT CHECK (admitted_leg IN ('telemetry','deployment')),
    leg_evidence_json TEXT
        CHECK (leg_evidence_json IS NULL OR json_valid(leg_evidence_json)),
    -- ===== structural (N5 (b): the LINK only) =====
    cited_latch_link_id INTEGER
        REFERENCES latch_order_mandate_links(link_id) ON DELETE RESTRICT,
    cited_latch_terminal_rung TEXT CHECK (cited_latch_terminal_rung IN
        ('invalidation','criteria_lapsed','horizon','declined')),
    cited_latch_terminal_session TEXT
        CHECK (cited_latch_terminal_session IS NULL
               OR COALESCE(length(cited_latch_terminal_session) = 10
               AND date(cited_latch_terminal_session) IS NOT NULL
               AND date(cited_latch_terminal_session) = cited_latch_terminal_session
               AND CAST(substr(cited_latch_terminal_session, 1, 4) AS INTEGER)
                   BETWEEN 1 AND 9999, 0)),
    cited_latch_probe_json TEXT
        CHECK (cited_latch_probe_json IS NULL OR json_valid(cited_latch_probe_json)),
    -- ===== evidence =====
    cited_fields_json TEXT NOT NULL
        CHECK (json_valid(cited_fields_json)
               AND json_type(cited_fields_json) = 'array'
               AND json_array_length(cited_fields_json) >= 1),
    cited_text_snapshot_json TEXT NOT NULL
        CHECK (json_valid(cited_text_snapshot_json)
               AND json_type(cited_text_snapshot_json) = 'object'),
    audit_trail_checked_at TEXT NOT NULL,
    corrections_touching_cited_fields INTEGER NOT NULL
        CHECK (corrections_touching_cited_fields = 0),
    -- The EARLIEST non-entry fill's datetime (trim/exit/stop), or NULL if the
    -- trade had none at assignment. Written ONCE; never back-filled.
    outcome_known_at TEXT
        CHECK (outcome_known_at IS NULL OR COALESCE(
               length(outcome_known_at) = 19
               AND outcome_known_at GLOB
                   '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
               AND datetime(outcome_known_at) IS NOT NULL
               AND date(substr(outcome_known_at, 1, 10)) IS NOT NULL
               AND date(substr(outcome_known_at, 1, 10)) = substr(outcome_known_at, 1, 10)
               AND CAST(substr(outcome_known_at, 1, 4) AS INTEGER) BETWEEN 1 AND 9999
               AND CAST(substr(outcome_known_at, 12, 2) AS INTEGER) <= 23
               AND CAST(substr(outcome_known_at, 15, 2) AS INTEGER) <= 59
               AND CAST(substr(outcome_known_at, 18, 2) AS INTEGER) <= 59, 0)),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    applied_at TEXT NOT NULL,
    applied_by TEXT NOT NULL,
    CHECK (entry_fill_id IS NULL OR entry_fill_id = entry_fill_id_at_assignment),
    -- The paired-tier CHECK: total (every operand non-NULL by construction).
    CHECK ((admission_tier = 'structural'
            AND cited_latch_link_id IS NOT NULL
            AND cited_latch_terminal_rung IS NOT NULL
            AND cited_latch_terminal_session IS NOT NULL
            AND cited_latch_probe_json IS NOT NULL
            AND placement_session IS NULL
            AND placement_session_source IS NULL
            AND admitted_leg IS NULL
            AND leg_evidence_json IS NULL)
        OR (admission_tier = 'contemporaneous_record'
            AND cited_latch_link_id IS NULL
            AND cited_latch_terminal_rung IS NULL
            AND cited_latch_terminal_session IS NULL
            AND cited_latch_probe_json IS NULL
            AND placement_session IS NOT NULL
            AND placement_session_source IS NOT NULL
            AND admitted_leg IS NOT NULL
            AND leg_evidence_json IS NOT NULL)),
    -- DEATH strictly BEFORE the fill session (same-session is a MANDATE fill
    -- under R6). NULL only on tier 2, where the paired CHECK forces NULL.
    CHECK (COALESCE(cited_latch_terminal_session < trade_entry_date, 1)),
    -- Leg 2: the placement strictly before the 21-B instrument's deployment
    -- session 2026-08-03 (N1, RD).
    CHECK (COALESCE(admitted_leg <> 'deployment'
                    OR placement_session < '2026-08-03', 1)),
    -- P3, test (a): the record pre-dates the outcome (CF-R3-1).
    CHECK (outcome_known_at IS NULL
           OR trade_entry_date < substr(outcome_known_at, 1, 10))
);

-- The binding: the trade, its entry date, NO relabel (entry_intent IS NULL at
-- insert -- the service inserts BEFORE it updates `trades`), the AUTHORITATIVE
-- entry fill (repos/fills.py get_authoritative_entry_fill's order), and the
-- order id the AUTHORITY stored for the fill's CURRENT document (RULING G1b):
-- stored values only. An envelope-less fill joins no reading and reads NULL
-- on both sides; an id named over a REFUSED reading, or over a document never
-- read, ABORTS.
CREATE TRIGGER trg_eia_trade_binding
BEFORE INSERT ON entry_intent_attestations
FOR EACH ROW
WHEN NOT COALESCE(
    EXISTS (SELECT 1 FROM trades t
            WHERE t.id = NEW.trade_id
              AND t.entry_date = NEW.trade_entry_date
              AND t.entry_intent IS NULL)
    AND NEW.entry_fill_id IS NOT NULL
    AND NEW.entry_fill_id = NEW.entry_fill_id_at_assignment
    AND NEW.entry_fill_id = (SELECT f.fill_id FROM fills f
                             WHERE f.trade_id = NEW.trade_id AND f.action = 'entry'
                             ORDER BY f.fill_datetime ASC, f.fill_id ASC LIMIT 1)
    AND NEW.entry_broker_order_id IS (
        SELECT fei.broker_order_id
        FROM fill_envelope_identity fei
        JOIN fills f ON f.fill_id = fei.fill_id
                    AND fei.envelope_raw = f.schwab_source_value_json
        WHERE f.fill_id = NEW.entry_fill_id_at_assignment
          AND fei.envelope_state = 'canonical'),
    0)
BEGIN SELECT RAISE(ABORT, 'entry_intent_attestations: the row does not bind to its trade (the trade exists with this entry_date and NULL entry_intent; the authoritative entry fill; the order id of its stored canonical envelope reading)'); END;

-- The citation: a closed allowlist of TEXT members, no duplicates, at least
-- one DESCRIPTIVE field (notes/why_now, F2 S4), and a snapshot whose key set
-- is the cited set and whose values are the live columns, byte for byte.
CREATE TRIGGER trg_eia_cited_fields
BEFORE INSERT ON entry_intent_attestations
FOR EACH ROW
WHEN NOT COALESCE(
    json_valid(NEW.cited_fields_json)
    AND json_valid(NEW.cited_text_snapshot_json)
    AND NOT EXISTS (
        SELECT 1 FROM json_each(CASE WHEN json_valid(NEW.cited_fields_json)
                                     THEN NEW.cited_fields_json ELSE '[]' END)
        WHERE type <> 'text'
           OR value NOT IN ('notes','why_now','thesis','emotional_state_pre_trade'))
    AND (SELECT COUNT(DISTINCT value) FROM json_each(
            CASE WHEN json_valid(NEW.cited_fields_json)
                 THEN NEW.cited_fields_json ELSE '[]' END))
      = (SELECT COUNT(*) FROM json_each(
            CASE WHEN json_valid(NEW.cited_fields_json)
                 THEN NEW.cited_fields_json ELSE '[]' END))
    AND EXISTS (
        SELECT 1 FROM json_each(CASE WHEN json_valid(NEW.cited_fields_json)
                                     THEN NEW.cited_fields_json ELSE '[]' END)
        WHERE value IN ('notes','why_now'))
    AND NOT EXISTS (
        SELECT 1 FROM json_each(CASE WHEN json_valid(NEW.cited_text_snapshot_json)
                                     THEN NEW.cited_text_snapshot_json ELSE '{}' END) s
        WHERE s.key NOT IN (
            SELECT value FROM json_each(CASE WHEN json_valid(NEW.cited_fields_json)
                                             THEN NEW.cited_fields_json ELSE '[]' END)))
    AND NOT EXISTS (
        SELECT 1 FROM json_each(CASE WHEN json_valid(NEW.cited_fields_json)
                                     THEN NEW.cited_fields_json ELSE '[]' END) c
        WHERE c.value NOT IN (
            SELECT key FROM json_each(CASE WHEN json_valid(NEW.cited_text_snapshot_json)
                                           THEN NEW.cited_text_snapshot_json ELSE '{}' END)))
    AND NOT EXISTS (
        SELECT 1 FROM json_each(CASE WHEN json_valid(NEW.cited_text_snapshot_json)
                                     THEN NEW.cited_text_snapshot_json ELSE '{}' END) s
        JOIN trades t ON t.id = NEW.trade_id
        WHERE s.type <> 'text'
           OR s.value IS NOT (CASE s.key
                                  WHEN 'notes' THEN t.notes
                                  WHEN 'why_now' THEN t.why_now
                                  WHEN 'thesis' THEN t.thesis
                                  WHEN 'emotional_state_pre_trade'
                                      THEN t.emotional_state_pre_trade
                              END)),
    0)
BEGIN SELECT RAISE(ABORT, 'entry_intent_attestations: the citation is not admissible (a closed allowlist of notes/why_now/thesis/emotional_state_pre_trade, no duplicates, at least one of notes/why_now, and a snapshot equal to the live text)'); END;

-- P2 over BOTH audit tables (F2 S2): no reconciliation correction has touched
-- a cited field -- by field_name OR as a key of either JSON envelope (P2-b, a
-- multi-field correction names only its first key) -- and no provenance
-- correction names one (P2-a: schema-vacuous today, required by S2).
CREATE TRIGGER trg_eia_audit_trail
BEFORE INSERT ON entry_intent_attestations
FOR EACH ROW
WHEN NOT COALESCE(
    NOT EXISTS (
        SELECT 1 FROM reconciliation_corrections rc
        WHERE rc.affected_table = 'trades'
          AND rc.affected_row_id = NEW.trade_id
          AND (rc.field_name IN (
                   SELECT value FROM json_each(
                       CASE WHEN json_valid(NEW.cited_fields_json)
                            THEN NEW.cited_fields_json ELSE '[]' END))
               OR EXISTS (
                   SELECT 1 FROM json_each(
                       CASE WHEN json_valid(rc.pre_correction_value_json)
                                 AND json_type(rc.pre_correction_value_json) = 'object'
                            THEN rc.pre_correction_value_json ELSE '{}' END) k
                   WHERE k.key IN (
                       SELECT value FROM json_each(
                           CASE WHEN json_valid(NEW.cited_fields_json)
                                THEN NEW.cited_fields_json ELSE '[]' END)
                       UNION SELECT 'trades.' || value FROM json_each(
                           CASE WHEN json_valid(NEW.cited_fields_json)
                                THEN NEW.cited_fields_json ELSE '[]' END)))
               OR EXISTS (
                   SELECT 1 FROM json_each(
                       CASE WHEN json_valid(rc.applied_value_json)
                                 AND json_type(rc.applied_value_json) = 'object'
                            THEN rc.applied_value_json ELSE '{}' END) k
                   WHERE k.key IN (
                       SELECT value FROM json_each(
                           CASE WHEN json_valid(NEW.cited_fields_json)
                                THEN NEW.cited_fields_json ELSE '[]' END)
                       UNION SELECT 'trades.' || value FROM json_each(
                           CASE WHEN json_valid(NEW.cited_fields_json)
                                THEN NEW.cited_fields_json ELSE '[]' END)))))
    AND NOT EXISTS (
        SELECT 1 FROM provenance_corrections pc
        WHERE pc.trade_id = NEW.trade_id
          AND EXISTS (
              SELECT 1 FROM json_each(
                  CASE WHEN json_valid(pc.corrected_fields_json)
                       THEN pc.corrected_fields_json ELSE '[]' END) e
              WHERE e.value IN (
                  SELECT 'trades.' || value FROM json_each(
                      CASE WHEN json_valid(NEW.cited_fields_json)
                           THEN NEW.cited_fields_json ELSE '[]' END)))),
    0)
BEGIN SELECT RAISE(ABORT, 'entry_intent_attestations: a correction in the audit trail (reconciliation_corrections or provenance_corrections) has touched a cited field'); END;

-- P3 (E2): outcome_known_at IS the earliest non-entry fill, NULL iff none.
CREATE TRIGGER trg_eia_outcome
BEFORE INSERT ON entry_intent_attestations
FOR EACH ROW
WHEN NOT COALESCE(
    NEW.outcome_known_at IS (SELECT MIN(f.fill_datetime) FROM fills f
                             WHERE f.trade_id = NEW.trade_id
                               AND f.action IN ('trim','exit','stop')),
    0)
BEGIN SELECT RAISE(ABORT, 'entry_intent_attestations: outcome_known_at is not the earliest non-entry fill of the trade'); END;

-- P1 for tier 2 (N1, RD; R0.H leg window): no structural record exists for the
-- order (no link, no order-naming intent; with no order id, none for the
-- ticker at or before the entry -- E9), the placement session is paired with
-- its source (a fallback IS the entry date; an envelope-sourced value is the
-- service's derivation, stored and bounded here but never re-read from the
-- envelope -- RULING G1b), and the admitted leg's evidence is EXACTLY what the
-- leg decides on, bound by VALUE.
--   SPEAK = the ticker's latch_view_events rows with
--           date(first_viewed_ts) >= '2026-08-03' (recorded under the
--           actionability instrument; earlier rows are 0033's backfill);
--   PRE   = SPEAK rows with date(first_viewed_ts) <= placement_session.
CREATE TRIGGER trg_eia_tier2
BEFORE INSERT ON entry_intent_attestations
FOR EACH ROW
WHEN NOT COALESCE(NEW.admission_tier IS NOT 'contemporaneous_record' OR (
    (NEW.entry_broker_order_id IS NULL
     OR (NOT EXISTS (SELECT 1 FROM latch_order_mandate_links l
                     WHERE l.broker_order_id = NEW.entry_broker_order_id)
         AND NOT EXISTS (SELECT 1 FROM latch_order_intents i
                         WHERE i.actual_broker_order_id = NEW.entry_broker_order_id)))
    AND (NEW.entry_broker_order_id IS NOT NULL
         OR (NOT EXISTS (SELECT 1 FROM latch_order_mandate_links l
                         WHERE l.ticker = (SELECT ticker FROM trades WHERE id = NEW.trade_id)
                           AND l.detection_date <= NEW.trade_entry_date)
             AND NOT EXISTS (SELECT 1 FROM latch_order_intents i
                             WHERE i.actual_broker_order_id IS NOT NULL
                               AND i.ticker = (SELECT ticker FROM trades WHERE id = NEW.trade_id)
                               AND i.detection_date <= NEW.trade_entry_date)))
    AND (NEW.placement_session_source = 'schwab_envelope'
         OR (NEW.placement_session_source = 'entry_date_fallback'
             AND NEW.placement_session = NEW.trade_entry_date))
    AND NOT EXISTS (
        SELECT 1 FROM latch_view_events v
        WHERE v.ticker = (SELECT ticker FROM trades WHERE id = NEW.trade_id)
          AND date(v.first_viewed_ts) >= '2026-08-03'
          AND date(v.first_viewed_ts) <= NEW.placement_session
          AND v.actionable_ever_viewed = 1)
    AND ((NEW.admitted_leg = 'telemetry'
          AND EXISTS (
              SELECT 1 FROM latch_view_events v
              WHERE v.ticker = (SELECT ticker FROM trades WHERE id = NEW.trade_id)
                AND date(v.first_viewed_ts) >= '2026-08-03'
                AND date(v.first_viewed_ts) <= NEW.placement_session)
          AND json_type(CASE WHEN json_valid(NEW.leg_evidence_json)
                             THEN NEW.leg_evidence_json ELSE '{}' END) = 'object'
          AND (SELECT COUNT(*) FROM json_each(
                  CASE WHEN json_valid(NEW.leg_evidence_json)
                       THEN NEW.leg_evidence_json ELSE '{}' END)) = 1
          AND json_type(CASE WHEN json_valid(NEW.leg_evidence_json)
                             THEN NEW.leg_evidence_json ELSE '{}' END,
                        '$.telemetry_rows') = 'array'
          AND json_array_length(CASE WHEN json_valid(NEW.leg_evidence_json)
                                     THEN NEW.leg_evidence_json ELSE '{}' END,
                                '$.telemetry_rows')
              = (SELECT COUNT(*) FROM latch_view_events v
                 WHERE v.ticker = (SELECT ticker FROM trades WHERE id = NEW.trade_id)
                   AND date(v.first_viewed_ts) >= '2026-08-03'
                   AND date(v.first_viewed_ts) <= NEW.placement_session)
          AND NOT EXISTS (
              SELECT 1 FROM latch_view_events v
              WHERE v.ticker = (SELECT ticker FROM trades WHERE id = NEW.trade_id)
                AND date(v.first_viewed_ts) >= '2026-08-03'
                AND date(v.first_viewed_ts) <= NEW.placement_session
                AND NOT EXISTS (
                    SELECT 1 FROM json_each(
                        CASE WHEN json_valid(NEW.leg_evidence_json)
                             THEN NEW.leg_evidence_json ELSE '{}' END,
                        '$.telemetry_rows') e
                    WHERE json_extract(e.value, '$.view_event_id') = v.view_event_id
                      AND json_extract(e.value, '$.actionable_ever_viewed') = 0
                      AND json_extract(e.value, '$.first_viewed_ts') IS v.first_viewed_ts
                      AND json_extract(e.value, '$.view_session_date')
                          IS v.view_session_date)))
         OR (NEW.admitted_leg = 'deployment'
             AND NOT EXISTS (
                 SELECT 1 FROM latch_view_events v
                 WHERE v.ticker = (SELECT ticker FROM trades WHERE id = NEW.trade_id)
                   AND date(v.first_viewed_ts) >= '2026-08-03'
                   AND date(v.first_viewed_ts) <= NEW.placement_session)
             AND NEW.placement_session < '2026-08-03'
             AND json_type(CASE WHEN json_valid(NEW.leg_evidence_json)
                                THEN NEW.leg_evidence_json ELSE '{}' END) = 'object'
             AND json_extract(CASE WHEN json_valid(NEW.leg_evidence_json)
                                   THEN NEW.leg_evidence_json ELSE '{}' END,
                              '$.deployment_session') = '2026-08-03'
             AND json_extract(CASE WHEN json_valid(NEW.leg_evidence_json)
                                   THEN NEW.leg_evidence_json ELSE '{}' END,
                              '$.placement_session') = NEW.placement_session
             AND (SELECT COUNT(*) FROM json_each(
                     CASE WHEN json_valid(NEW.leg_evidence_json)
                          THEN NEW.leg_evidence_json ELSE '{}' END)) = 2))),
    0)
BEGIN SELECT RAISE(ABORT, 'entry_intent_attestations: the contemporaneous_record admission is not supported by the record (a structural record exists for the order, the placement session is not the recorded one, the instrument offered the order, or the admitted leg and its evidence do not match)'); END;

-- The structural tier (F3 (a) narrowed by N5 (b)): the cited LINK is the
-- fill's order, and the probe JSON binds to the row by VALUE. The
-- death-before-fill DERIVATION is service-only (mandate_alive_at, Python).
CREATE TRIGGER trg_eia_structural
BEFORE INSERT ON entry_intent_attestations
FOR EACH ROW
WHEN NOT COALESCE(NEW.admission_tier IS NOT 'structural' OR (
    NEW.entry_broker_order_id IS NOT NULL
    AND EXISTS (SELECT 1 FROM latch_order_mandate_links l
                WHERE l.link_id = NEW.cited_latch_link_id
                  AND l.broker_order_id = NEW.entry_broker_order_id)
    AND json_valid(NEW.cited_latch_probe_json)
    AND json_extract(CASE WHEN json_valid(NEW.cited_latch_probe_json)
                          THEN NEW.cited_latch_probe_json ELSE '{}' END,
                     '$.link_id') = NEW.cited_latch_link_id
    AND json_extract(CASE WHEN json_valid(NEW.cited_latch_probe_json)
                          THEN NEW.cited_latch_probe_json ELSE '{}' END,
                     '$.clear_reason') = NEW.cited_latch_terminal_rung
    AND json_extract(CASE WHEN json_valid(NEW.cited_latch_probe_json)
                          THEN NEW.cited_latch_probe_json ELSE '{}' END,
                     '$.clear_session') = NEW.cited_latch_terminal_session
    AND json_extract(CASE WHEN json_valid(NEW.cited_latch_probe_json)
                          THEN NEW.cited_latch_probe_json ELSE '{}' END,
                     '$.decline_reason') = 'mandate_not_alive'
    AND json_extract(CASE WHEN json_valid(NEW.cited_latch_probe_json)
                          THEN NEW.cited_latch_probe_json ELSE '{}' END,
                     '$.fire_candidate_id')
        = (SELECT l.candidate_id FROM latch_order_mandate_links l
           WHERE l.link_id = NEW.cited_latch_link_id)),
    0)
BEGIN SELECT RAISE(ABORT, 'entry_intent_attestations: the structural citation does not bind (the cited link is not the fill''s order, or the probe evidence does not match the recorded rung and session)'); END;

-- The append-only TRIPLE (the 22-I convention). The ONE permitted UPDATE is
-- the FK-driven nulling of entry_fill_id (ON DELETE SET NULL, the 0039 shape).
CREATE TRIGGER trg_eia_no_update
BEFORE UPDATE ON entry_intent_attestations
FOR EACH ROW
WHEN NOT COALESCE(
    NEW.entry_fill_id IS NULL AND OLD.entry_fill_id IS NOT NULL
    AND NOT EXISTS (SELECT 1 FROM fills WHERE fill_id = OLD.entry_fill_id)
    AND NEW.attestation_id IS OLD.attestation_id
    AND NEW.trade_id IS OLD.trade_id
    AND NEW.assigned_value IS OLD.assigned_value
    AND NEW.admission_tier IS OLD.admission_tier
    AND NEW.trade_entry_date IS OLD.trade_entry_date
    AND NEW.entry_fill_id_at_assignment IS OLD.entry_fill_id_at_assignment
    AND NEW.entry_broker_order_id IS OLD.entry_broker_order_id
    AND NEW.placement_session IS OLD.placement_session
    AND NEW.placement_session_source IS OLD.placement_session_source
    AND NEW.admitted_leg IS OLD.admitted_leg
    AND NEW.leg_evidence_json IS OLD.leg_evidence_json
    AND NEW.cited_latch_link_id IS OLD.cited_latch_link_id
    AND NEW.cited_latch_terminal_rung IS OLD.cited_latch_terminal_rung
    AND NEW.cited_latch_terminal_session IS OLD.cited_latch_terminal_session
    AND NEW.cited_latch_probe_json IS OLD.cited_latch_probe_json
    AND NEW.cited_fields_json IS OLD.cited_fields_json
    AND NEW.cited_text_snapshot_json IS OLD.cited_text_snapshot_json
    AND NEW.audit_trail_checked_at IS OLD.audit_trail_checked_at
    AND NEW.corrections_touching_cited_fields IS OLD.corrections_touching_cited_fields
    AND NEW.outcome_known_at IS OLD.outcome_known_at
    AND NEW.reason IS OLD.reason
    AND NEW.applied_at IS OLD.applied_at
    AND NEW.applied_by IS OLD.applied_by,
    0)
BEGIN SELECT RAISE(ABORT, 'entry_intent_attestations is APPEND-ONLY: the only permitted UPDATE is the FK-driven nulling of entry_fill_id when its fill is deleted'); END;

CREATE TRIGGER trg_eia_no_delete
BEFORE DELETE ON entry_intent_attestations
FOR EACH ROW
BEGIN SELECT RAISE(ABORT, 'entry_intent_attestations is APPEND-ONLY: an attestation cannot be deleted'); END;

-- Conflict-scoped (the REPLACE gotcha: REPLACE's implicit delete fires no
-- DELETE trigger at recursive_triggers=OFF). The service's INSERT carries no
-- ON CONFLICT, so the DO-NOTHING facet does not arise. EXISTS is never NULL.
CREATE TRIGGER trg_eia_no_replace
BEFORE INSERT ON entry_intent_attestations
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM entry_intent_attestations
             WHERE (NEW.attestation_id != -1 AND attestation_id = NEW.attestation_id)
                OR trade_id = NEW.trade_id)
BEGIN SELECT RAISE(ABORT, 'entry_intent_attestations is APPEND-ONLY: a conflicting INSERT (INSERT OR REPLACE / REPLACE) would rewrite the attestation of record; one trade carries one attestation'); END;

-- The two unattested `trades` twins (CHARC-S3 condition 2, RD's
-- recommendation adopted; N4's text untouched). Created AFTER the table's
-- CREATE because their bodies name it. The value is UNWRITABLE WITHOUT ITS
-- ATTESTATION ROW, at the schema. Both WHENs are TOTAL (COALESCE and NOT
-- EXISTS are never NULL). The INSERT twin also fires on the INSERT half of
-- INSERT OR REPLACE INTO trades: it NARROWS AL-3's entry_intent facet and does
-- NOT close AL-3.
CREATE TRIGGER trg_trades_entry_intent_unattested_update
BEFORE UPDATE OF entry_intent ON trades
FOR EACH ROW
WHEN COALESCE(NEW.entry_intent,'') = 'unintended_execution'
 AND NOT EXISTS (SELECT 1 FROM entry_intent_attestations WHERE trade_id = NEW.id)
BEGIN SELECT RAISE(ABORT, 'entry_intent unintended_execution requires its attestation row; use swing trade assign-intent'); END;

CREATE TRIGGER trg_trades_entry_intent_unattested_insert
BEFORE INSERT ON trades
FOR EACH ROW
WHEN COALESCE(NEW.entry_intent,'') = 'unintended_execution'
BEGIN SELECT RAISE(ABORT, 'entry_intent unintended_execution requires its attestation row; use swing trade assign-intent'); END;

-- 8. The version bump is the FINAL statement before COMMIT.
UPDATE schema_version SET version = 40;

COMMIT;
