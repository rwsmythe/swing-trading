-- Tranche C pipeline-linkage bundle (T1).
--
-- 1. Add `evaluation_run_id` FK to `pipeline_runs` so the chart-scope resolver
--    and today_decisions can bind to the *pipeline's own* eval run, replacing
--    the heuristic `data_asof_date + run_ts <= finished_ts` query that races
--    against mid-pipeline standalone `swing eval` calls (spec §4 drift mode A,
--    Bug 7).
-- 2. Add `pipeline_chart_targets` to persist per-pipeline-run chart-target
--    tickers + per-ticker outcome (`pending` -> `ok` | `fetcher_failed` |
--    `too_few_bars`). Replaces the live re-derivation of the near-by-proximity
--    set (spec §4 drift mode B) and enables the chart-reason split that
--    spec §8 deferred (T5).
--
-- Backfill semantics: legacy `pipeline_runs` rows get `evaluation_run_id`
-- NULL (the column is nullable). The chart-scope resolver retains the
-- heuristic eval-linkage query as a fallback for those rows.

ALTER TABLE pipeline_runs ADD COLUMN evaluation_run_id INTEGER REFERENCES evaluation_runs(id);

CREATE TABLE pipeline_chart_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_run_id INTEGER NOT NULL REFERENCES pipeline_runs(id),
    ticker TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('aplus', 'near_proximity')),
    chart_status TEXT NOT NULL CHECK (chart_status IN ('ok', 'fetcher_failed', 'too_few_bars', 'pending')),
    UNIQUE (pipeline_run_id, ticker)
);

CREATE INDEX idx_pipeline_chart_targets_run ON pipeline_chart_targets(pipeline_run_id);

UPDATE schema_version SET version = 6;
