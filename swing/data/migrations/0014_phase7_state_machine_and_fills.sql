-- Phase 7: Trade lifecycle state machine + Fills first-class.
-- Spec: docs/superpowers/specs/2026-05-04-phase7-trade-lifecycle-state-machine-design.md
-- Plan: docs/superpowers/plans/2026-05-04-phase7-trade-lifecycle-state-machine-plan.md §4 T2.

BEGIN TRANSACTION;

-- 1. Create fills table (canonical execution log replacing exits).
CREATE TABLE fills (
  fill_id INTEGER PRIMARY KEY,
  trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
  fill_datetime TEXT NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('entry','trim','exit','stop')),
  quantity REAL NOT NULL CHECK (quantity > 0),
  price REAL NOT NULL CHECK (price > 0),
  reason TEXT,
  rule_based INTEGER CHECK (rule_based IS NULL OR rule_based IN (0,1)),
  fees REAL,
  manual_entry_confidence TEXT
      CHECK (manual_entry_confidence IS NULL OR manual_entry_confidence IN ('high','normal','low')),
  reconciliation_status TEXT NOT NULL DEFAULT 'unreconciled'
      CHECK (reconciliation_status IN ('unreconciled','reconciled_match',
        'reconciled_discrepancy','reconciled_discrepancy_resolved','manual_override')),
  tos_match_id TEXT
);

CREATE INDEX ix_fills_trade ON fills(trade_id, fill_datetime);
CREATE INDEX ix_fills_action ON fills(trade_id, action);

-- 2. Backfill entry-action fills from trades (synthetic close-of-session timestamp).
INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, reason, reconciliation_status)
SELECT id, entry_date || 'T16:00:00', 'entry',
       CAST(initial_shares AS REAL), entry_price, NULL, 'unreconciled'
FROM trades;

-- 3. Backfill exit/trim/stop fills from exits with deterministic ordering.
-- Per-trade: ORDER BY exit_date ASC, id ASC. Last row in ordering = 'exit',
-- earlier rows = 'trim'. Notes merged into reason with ' | ' separator.
INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, reason, reconciliation_status)
SELECT
  e.trade_id,
  e.exit_date || 'T16:00:00',
  CASE
    WHEN e.id = (
      SELECT e2.id FROM exits e2
      WHERE e2.trade_id = e.trade_id
      ORDER BY e2.exit_date DESC, e2.id DESC LIMIT 1
    ) THEN 'exit'
    ELSE 'trim'
  END,
  CAST(e.shares AS REAL),
  e.exit_price,
  CASE
    WHEN e.notes IS NULL OR e.notes = '' THEN e.reason
    ELSE e.reason || ' | ' || e.notes
  END,
  'unreconciled'
FROM exits e;

-- 4. Add new columns to trades (initially NULLABLE for backfill;
--    table-rebuild step 10 adds NOT NULL + CHECK on constrained cols).
-- NOTE: skip `state` here — A.0 already added it to the dataclass; we have
-- not migrated the schema yet, so the column does not exist. Add it here.
ALTER TABLE trades ADD COLUMN state TEXT;
ALTER TABLE trades ADD COLUMN trade_origin TEXT;
ALTER TABLE trades ADD COLUMN pre_trade_locked_at TEXT;
ALTER TABLE trades ADD COLUMN current_size REAL DEFAULT 0;
ALTER TABLE trades ADD COLUMN current_avg_cost REAL;
ALTER TABLE trades ADD COLUMN last_fill_at TEXT;
ALTER TABLE trades ADD COLUMN thesis TEXT;
ALTER TABLE trades ADD COLUMN why_now TEXT;
ALTER TABLE trades ADD COLUMN invalidation_condition TEXT;
ALTER TABLE trades ADD COLUMN expected_scenario TEXT;
ALTER TABLE trades ADD COLUMN premortem_technical TEXT;
ALTER TABLE trades ADD COLUMN premortem_market_sector TEXT;
ALTER TABLE trades ADD COLUMN premortem_execution TEXT;
ALTER TABLE trades ADD COLUMN premortem_additional TEXT;
ALTER TABLE trades ADD COLUMN event_risk_present INTEGER;
ALTER TABLE trades ADD COLUMN event_handling TEXT;
ALTER TABLE trades ADD COLUMN event_type TEXT;
ALTER TABLE trades ADD COLUMN event_date TEXT;
ALTER TABLE trades ADD COLUMN gap_risk_present INTEGER;
ALTER TABLE trades ADD COLUMN gap_risk_handling TEXT;
ALTER TABLE trades ADD COLUMN emotional_state_pre_trade TEXT;
ALTER TABLE trades ADD COLUMN market_regime TEXT;
ALTER TABLE trades ADD COLUMN catalyst TEXT;
ALTER TABLE trades ADD COLUMN catalyst_other_description TEXT;

-- 5. Backfill state from status + reviewed_at + exits-presence.
UPDATE trades SET state = CASE
  WHEN status = 'closed' AND reviewed_at IS NOT NULL THEN 'reviewed'
  WHEN status = 'closed' AND reviewed_at IS NULL     THEN 'closed'
  WHEN EXISTS (SELECT 1 FROM exits WHERE exits.trade_id = trades.id) THEN 'partial_exited'
  ELSE 'managing'
END;

-- 6. Backfill pre_trade_locked_at = entry_date + 'T16:00:00'.
UPDATE trades SET pre_trade_locked_at = entry_date || 'T16:00:00';

-- 7. Backfill trade_origin (operator-confirmed FIRM per spec §12.3 + 2026-05-04 update).
--    VIR=manual; DHC + CC=watch+hyp_recs; YOU=aplus (4th in-flight trade entered
--    2026-05-04 between writing-plans and Sub-A dispatch).
UPDATE trades SET trade_origin = CASE
  WHEN ticker = 'VIR' THEN 'manual_off_pipeline'
  WHEN ticker IN ('DHC', 'CC') THEN 'pipeline_watch_hyp_recs'
  WHEN ticker = 'YOU' THEN 'pipeline_aplus'
  ELSE 'manual_off_pipeline'
END;

-- 8. Backfill current_size, current_avg_cost, last_fill_at from fills aggregates.
UPDATE trades SET
  current_size = COALESCE((
    SELECT SUM(CASE WHEN action = 'entry' THEN quantity ELSE -quantity END)
    FROM fills WHERE fills.trade_id = trades.id
  ), 0),
  current_avg_cost = (
    SELECT price FROM fills
    WHERE fills.trade_id = trades.id AND action = 'entry'
    ORDER BY fill_datetime ASC, fill_id ASC LIMIT 1
  ),
  last_fill_at = (
    SELECT MAX(fill_datetime) FROM fills WHERE fills.trade_id = trades.id
  );

-- 9. Drop exits table (data preserved in fills).
DROP TABLE exits;

-- 10. Table-rebuild trades: drop status, add NOT NULL + CHECK on state/trade_origin/
--     pre_trade_locked_at/current_size, recreate partial-unique-index against state.
DROP INDEX IF EXISTS ux_trades_one_open_per_ticker;

CREATE TABLE trades_new (
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
);

INSERT INTO trades_new
  (id, ticker, entry_date, entry_price, initial_shares, initial_stop, current_stop,
   state, watchlist_entry_target, watchlist_initial_stop, notes, hypothesis_label,
   chart_pattern_algo, chart_pattern_algo_confidence, chart_pattern_operator,
   chart_pattern_classification_pipeline_run_id, sector, industry,
   reviewed_at, mistake_tags, entry_grade, management_grade, exit_grade,
   process_grade, disqualifying_process_violation, realized_R_if_plan_followed,
   mistake_cost_confidence, lesson_learned,
   trade_origin, pre_trade_locked_at, current_size, current_avg_cost, last_fill_at,
   thesis, why_now, invalidation_condition, expected_scenario,
   premortem_technical, premortem_market_sector, premortem_execution, premortem_additional,
   event_risk_present, event_handling, event_type, event_date,
   gap_risk_present, gap_risk_handling, emotional_state_pre_trade,
   market_regime, catalyst, catalyst_other_description)
SELECT
  id, ticker, entry_date, entry_price, initial_shares, initial_stop, current_stop,
  state, watchlist_entry_target, watchlist_initial_stop, notes, hypothesis_label,
  chart_pattern_algo, chart_pattern_algo_confidence, chart_pattern_operator,
  chart_pattern_classification_pipeline_run_id, sector, industry,
  reviewed_at, mistake_tags, entry_grade, management_grade, exit_grade,
  process_grade, disqualifying_process_violation, realized_R_if_plan_followed,
  mistake_cost_confidence, lesson_learned,
  trade_origin, pre_trade_locked_at, current_size, current_avg_cost, last_fill_at,
  thesis, why_now, invalidation_condition, expected_scenario,
  premortem_technical, premortem_market_sector, premortem_execution, premortem_additional,
  event_risk_present, event_handling, event_type, event_date,
  gap_risk_present, gap_risk_handling, emotional_state_pre_trade,
  market_regime, catalyst, catalyst_other_description
FROM trades;

DROP TABLE trades;
ALTER TABLE trades_new RENAME TO trades;

CREATE UNIQUE INDEX ux_trades_one_open_per_ticker
  ON trades(ticker) WHERE state IN ('entered','managing','partial_exited');

-- 11. Table-rebuild trade_events to expand event_type CHECK.
CREATE TABLE trade_events_new (
  id INTEGER PRIMARY KEY,
  trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
  ts TEXT NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN
      ('entry','stop_adjust','note','exit','flag','pre_trade_edit')),
  payload_json TEXT,
  rationale TEXT,
  notes TEXT
);

INSERT INTO trade_events_new (id, trade_id, ts, event_type, payload_json, rationale, notes)
SELECT id, trade_id, ts, event_type, payload_json, rationale, notes FROM trade_events;

DROP TABLE trade_events;
ALTER TABLE trade_events_new RENAME TO trade_events;

CREATE INDEX ix_trade_events_trade ON trade_events(trade_id, ts);

-- 12. Bump schema_version.
UPDATE schema_version SET version = 14;

COMMIT;
