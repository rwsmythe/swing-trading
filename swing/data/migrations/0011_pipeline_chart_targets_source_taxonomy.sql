-- Migration 0011: chart_targets source taxonomy expansion for chart-scope policy v2.
--
-- Adds 'open_position' and 'tag_aware_top_n' to the source CHECK constraint.
-- Retains 'near_proximity' for legacy rows from pipeline runs prior to this
-- migration (no backfill — historical accuracy preserved per audit-trail discipline).
--
-- After this migration, _step_charts writes 'tag_aware_top_n' for the watchlist
-- tier (never 'near_proximity'). The 'near_proximity' value is read-only legacy.

CREATE TABLE pipeline_chart_targets_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_run_id INTEGER NOT NULL REFERENCES pipeline_runs(id),
    ticker TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN (
        'aplus',
        'near_proximity',
        'open_position',
        'tag_aware_top_n'
    )),
    chart_status TEXT NOT NULL CHECK (chart_status IN ('ok', 'fetcher_failed', 'too_few_bars', 'pending')),
    UNIQUE (pipeline_run_id, ticker)
);

INSERT INTO pipeline_chart_targets_new (id, pipeline_run_id, ticker, source, chart_status)
SELECT id, pipeline_run_id, ticker, source, chart_status
FROM pipeline_chart_targets;

DROP TABLE pipeline_chart_targets;
ALTER TABLE pipeline_chart_targets_new RENAME TO pipeline_chart_targets;

CREATE INDEX idx_pipeline_chart_targets_run ON pipeline_chart_targets(pipeline_run_id);

UPDATE schema_version SET version = 11;
