-- Phase 14 Sub-bundle 3 (chart-surface uniformity) migration 0023:
-- atomically rename the chart_renders.surface enum value
-- 'hyprec_detail' -> 'ticker_detail' (id-preserving single-table rebuild).
--
-- The single cached detail-chart row is read by BOTH the hyp-rec-expand
-- caller AND the watchlist-expand caller; 'ticker_detail' is the
-- caller-agnostic surface name. NO candlestick / column-shape change here
-- (that is T-3.2+). Only the one CHECK enum token differs from the live
-- v22 chart_renders DDL; the table body + 3 partial indexes are recreated
-- verbatim from the migrated-to-v22 live schema.
--
-- gotcha #9: explicit BEGIN; ... COMMIT; (executescript implicit-COMMIT
-- discipline). The runner's _apply_migration wraps this in try/except
-- with rollback on any mid-script failure.
BEGIN;
CREATE TABLE chart_renders_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    surface TEXT NOT NULL CHECK (surface IN (
        'watchlist_row', 'ticker_detail', 'position_detail',
        'market_weather', 'theme2_annotated'
    )),
    pipeline_run_id INTEGER
        REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    pattern_class TEXT CHECK (
        pattern_class IS NULL OR pattern_class IN (
            'vcp', 'flat_base', 'cup_with_handle',
            'high_tight_flag', 'double_bottom_w'
        )
    ),
    chart_svg_bytes BLOB NOT NULL,
    source_data_hash TEXT NOT NULL,
    rendered_at TEXT NOT NULL,
    data_asof_date TEXT NOT NULL,

    -- Cross-column CHECK: theme2_annotated requires both pattern_class +
    -- pipeline_run_id non-NULL; all other surfaces require pattern_class NULL.
    -- Closes Codex R2 M#5 (partial-index predicate also requires
    -- pipeline_run_id IS NOT NULL for theme2_annotated).
    CHECK (
        (surface = 'theme2_annotated'
            AND pattern_class IS NOT NULL
            AND pipeline_run_id IS NOT NULL)
        OR (surface != 'theme2_annotated' AND pattern_class IS NULL)
    )
);
INSERT INTO chart_renders_new (id, ticker, surface, pipeline_run_id,
        pattern_class, chart_svg_bytes, source_data_hash, rendered_at,
        data_asof_date)
    SELECT id, ticker,
        CASE WHEN surface = 'hyprec_detail' THEN 'ticker_detail' ELSE surface END,
        pipeline_run_id, pattern_class, chart_svg_bytes, source_data_hash,
        rendered_at, data_asof_date
    FROM chart_renders;
DROP TABLE chart_renders;
ALTER TABLE chart_renders_new RENAME TO chart_renders;
CREATE UNIQUE INDEX idx_chart_renders_run_bound
    ON chart_renders(ticker, surface, pipeline_run_id)
    WHERE pipeline_run_id IS NOT NULL AND surface != 'theme2_annotated';
CREATE UNIQUE INDEX idx_chart_renders_position_detail
    ON chart_renders(ticker, surface)
    WHERE pipeline_run_id IS NULL AND surface = 'position_detail';
CREATE UNIQUE INDEX idx_chart_renders_theme2_annotated
    ON chart_renders(ticker, surface, pipeline_run_id, pattern_class)
    WHERE surface = 'theme2_annotated' AND pipeline_run_id IS NOT NULL;
UPDATE schema_version SET version = 23;
COMMIT;
