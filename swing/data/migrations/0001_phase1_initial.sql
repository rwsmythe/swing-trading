-- Phase 1 schema — evaluation-only tables. Later phases extend.

CREATE TABLE schema_version (
  version INTEGER PRIMARY KEY
);
INSERT INTO schema_version (version) VALUES (1);

-- evaluation batch (one per evaluator run — Phase 1 has no pipeline wrapping it yet)
CREATE TABLE evaluation_runs (
  id INTEGER PRIMARY KEY,
  run_ts TEXT NOT NULL,
  data_asof_date TEXT NOT NULL,
  action_session_date TEXT NOT NULL,
  finviz_csv_path TEXT,
  tickers_evaluated INTEGER NOT NULL,
  aplus_count INTEGER NOT NULL,
  watch_count INTEGER NOT NULL,
  skip_count INTEGER NOT NULL,
  excluded_count INTEGER NOT NULL,
  error_count INTEGER NOT NULL
);

-- one row per (evaluation_run, ticker)
CREATE TABLE candidates (
  id INTEGER PRIMARY KEY,
  evaluation_run_id INTEGER NOT NULL REFERENCES evaluation_runs(id),
  ticker TEXT NOT NULL,
  bucket TEXT NOT NULL CHECK (bucket IN ('aplus','watch','skip','error','excluded')),
  close REAL,
  pivot REAL,
  initial_stop REAL,
  adr_pct REAL,
  tight_streak INTEGER,
  pullback_pct REAL,
  prior_trend_pct REAL,
  rs_rank INTEGER,
  rs_return_12w_vs_spy REAL,
  rs_method TEXT NOT NULL CHECK (rs_method IN ('universe','fallback_spy','unavailable')),
  pattern_tag TEXT,
  notes TEXT,
  UNIQUE(evaluation_run_id, ticker)
);

CREATE INDEX ix_candidates_run_bucket ON candidates(evaluation_run_id, bucket);
CREATE INDEX ix_candidates_ticker ON candidates(ticker);

-- per-criterion result for each candidate row
CREATE TABLE candidate_criteria (
  candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
  criterion_name TEXT NOT NULL,
  layer TEXT NOT NULL CHECK (layer IN ('trend_template','vcp','risk')),
  result TEXT NOT NULL CHECK (result IN ('pass','fail','na')),
  value TEXT,
  rule TEXT,
  PRIMARY KEY (candidate_id, criterion_name)
);
