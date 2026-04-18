-- Phase 2 schema additions: weather, watchlist, trades, exits, cash, audit, recommendations, pipeline runs, config revisions.

-- Market weather (one row per classifier run)
CREATE TABLE weather_runs (
  id INTEGER PRIMARY KEY,
  run_ts TEXT NOT NULL,
  asof_date TEXT NOT NULL,
  ticker TEXT NOT NULL DEFAULT 'QQQ',
  status TEXT NOT NULL CHECK (status IN ('Bullish','Caution','Bearish')),
  close REAL NOT NULL,
  sma10 REAL, sma20 REAL, sma50 REAL,
  slope20_5bar REAL, slope10_5bar REAL,
  rationale TEXT
);
CREATE UNIQUE INDEX ux_weather_asof_ticker ON weather_runs(asof_date, ticker);

-- Active watchlist
CREATE TABLE watchlist (
  ticker TEXT PRIMARY KEY,
  added_date TEXT NOT NULL,
  last_qualified_date TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('watch','skip','near_trigger')),
  qualification_count INTEGER NOT NULL DEFAULT 1,
  not_qualified_streak INTEGER NOT NULL DEFAULT 0,
  last_data_asof_date TEXT NOT NULL,                 -- last data date the streak was evaluated against (idempotency key for §5.4)
  entry_target REAL,                                 -- frozen at first add (legacy parity)
  initial_stop_target REAL,                          -- frozen at first add
  last_close REAL, last_pivot REAL, last_stop REAL, last_adr_pct REAL,
  missing_criteria TEXT,                             -- semicolon-joined names of dynamic criteria failing today
  notes TEXT
);

-- Watchlist archive (audit trail of removed tickers)
CREATE TABLE watchlist_archive (
  id INTEGER PRIMARY KEY,
  ticker TEXT NOT NULL,
  added_date TEXT NOT NULL,
  removed_date TEXT NOT NULL,
  reason TEXT NOT NULL,
  qualification_count INTEGER,
  last_data_asof_date TEXT,
  notes TEXT
);
CREATE INDEX ix_watchlist_archive_ticker ON watchlist_archive(ticker);

-- Trades (current state — mutable; audit trail in trade_events)
CREATE TABLE trades (
  id INTEGER PRIMARY KEY,
  ticker TEXT NOT NULL,
  entry_date TEXT NOT NULL,
  entry_price REAL NOT NULL,
  initial_shares INTEGER NOT NULL,
  initial_stop REAL NOT NULL,
  current_stop REAL NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('open','closed')),
  watchlist_entry_target REAL,
  watchlist_initial_stop REAL,
  notes TEXT
);
CREATE INDEX ix_trades_ticker_status ON trades(ticker, status);

-- Exits (partials supported; sum to <= initial_shares enforced at app layer)
CREATE TABLE exits (
  id INTEGER PRIMARY KEY,
  trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
  exit_date TEXT NOT NULL,
  exit_price REAL NOT NULL,
  shares INTEGER NOT NULL CHECK (shares > 0),
  reason TEXT NOT NULL,
  realized_pnl REAL NOT NULL,
  r_multiple REAL NOT NULL,
  notes TEXT
);
CREATE INDEX ix_exits_trade ON exits(trade_id);

-- Cash deposits / withdrawals
CREATE TABLE cash_movements (
  id INTEGER PRIMARY KEY,
  date TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('deposit','withdraw')),
  amount REAL NOT NULL CHECK (amount >= 0),
  ref TEXT,
  note TEXT
);
CREATE UNIQUE INDEX ux_cash_ref ON cash_movements(ref) WHERE ref IS NOT NULL;

-- Trade events (immutable audit log; required for every trades mutation)
CREATE TABLE trade_events (
  id INTEGER PRIMARY KEY,
  trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
  ts TEXT NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('entry','stop_adjust','note','exit','flag')),
  payload_json TEXT NOT NULL,
  rationale TEXT
);
CREATE INDEX ix_trade_events_trade ON trade_events(trade_id, ts);

-- Daily recommendations (immutable session snapshot)
CREATE TABLE daily_recommendations (
  id INTEGER PRIMARY KEY,
  evaluation_run_id INTEGER NOT NULL REFERENCES evaluation_runs(id),
  data_asof_date TEXT NOT NULL,
  action_session_date TEXT NOT NULL,
  ticker TEXT NOT NULL,
  recommendation TEXT NOT NULL CHECK (recommendation IN
      ('today_decision','watchlist_watch','watchlist_skip','near_trigger')),
  action_text TEXT,
  entry_target REAL,
  stop_target REAL,
  shares INTEGER,
  risk_dollars REAL,
  risk_pct REAL,
  rationale TEXT
);
CREATE UNIQUE INDEX ux_daily_recs_action_session_date_ticker_rec
  ON daily_recommendations(action_session_date, ticker, recommendation);
CREATE INDEX ix_daily_recs_session ON daily_recommendations(action_session_date);

-- Pipeline runs (lease-fenced)
CREATE TABLE pipeline_runs (
  id INTEGER PRIMARY KEY,
  started_ts TEXT NOT NULL,
  finished_ts TEXT,
  trigger TEXT NOT NULL CHECK (trigger IN ('scheduled','manual')),
  data_asof_date TEXT NOT NULL,
  action_session_date TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('running','complete','failed','blocked','force_cleared')),
  lease_token TEXT NOT NULL,
  lease_heartbeat_ts TEXT,
  last_step_progress_ts TEXT,
  current_step TEXT,
  weather_status TEXT CHECK (weather_status IN ('ok','failed','skipped')),
  evaluation_status TEXT CHECK (evaluation_status IN ('ok','failed','skipped')),
  watchlist_status TEXT CHECK (watchlist_status IN ('ok','failed','skipped')),
  recommendations_status TEXT CHECK (recommendations_status IN ('ok','failed','skipped')),
  charts_status TEXT CHECK (charts_status IN ('ok','failed','skipped')),
  export_status TEXT CHECK (export_status IN ('ok','failed','skipped')),
  rs_universe_version TEXT,
  rs_universe_hash TEXT,
  finviz_csv_path TEXT,
  error_message TEXT,
  warnings_json TEXT  -- export size warnings, stale-lease nags, etc.
);
CREATE INDEX ix_pipeline_runs_state ON pipeline_runs(state);
CREATE INDEX ix_pipeline_runs_session ON pipeline_runs(action_session_date);

-- At most one pipeline_runs row can be 'running' at a time. Critical for the
-- lease contract: without this, two processes doing SELECT-then-INSERT can
-- both observe "no active run" and both INSERT. The partial unique index
-- makes the second INSERT fail with IntegrityError even under concurrency.
CREATE UNIQUE INDEX ux_pipeline_one_running ON pipeline_runs(state) WHERE state = 'running';

-- Config audit trail (every /settings save writes a row)
CREATE TABLE config_revisions (
  id INTEGER PRIMARY KEY,
  ts TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'cli'  -- 'cli' or 'web' (Phase 3)
);

-- Bump schema version
UPDATE schema_version SET version = 3;
