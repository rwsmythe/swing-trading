-- 0010_trade_chart_pattern.sql
--
-- Four columns on trades for the chart-pattern algo's per-trade encoding.
-- Brief locked-constraint #6: algo and operator values stored separately so future
-- agreement-rate / calibration analysis can compare them. Effective-pattern-for-
-- analysis = COALESCE(chart_pattern_operator, chart_pattern_algo). The
-- pipeline_run_id column persists the audit anchor of which cached
-- classification the trade was entered against (R4 Major 1 — without
-- persisting this, the "audit anchor" added in R3 evaporates at record_entry
-- return).

ALTER TABLE trades ADD COLUMN chart_pattern_algo TEXT
    CHECK (chart_pattern_algo IS NULL OR chart_pattern_algo IN ('none', 'flag'));
ALTER TABLE trades ADD COLUMN chart_pattern_algo_confidence REAL
    CHECK (chart_pattern_algo_confidence IS NULL
           OR (chart_pattern_algo_confidence >= 0.0
               AND chart_pattern_algo_confidence <= 1.0));
ALTER TABLE trades ADD COLUMN chart_pattern_operator TEXT;
-- Audit anchor: the pipeline_run_id of the cached classification row whose
-- pattern/confidence values the operator-facing entry surface displayed at
-- entry time. NULL when no cache row was available (out-of-scope ticker or
-- classifier-error row was the only one present). The column is declared
-- with `REFERENCES pipeline_runs(id)`; whether the FK is ENFORCED depends on
-- `PRAGMA foreign_keys = ON` (SQLite default is OFF unless set per-connection).
-- The project's existing connection setup turns FKs on. Even with FKs enforced,
-- V1 deliberately does NOT rely on:
--   (a) cross-table cascade semantics (no ON DELETE/UPDATE specified, so the
--       default "NO ACTION" applies — a deleted pipeline_runs row whose id is
--       referenced here would block the delete; pipeline_runs rows are not
--       deleted in normal operation), or
--   (b) tamper-proof provenance (per §3.6 threat model the value is operator-
--       claimed input from a hidden form field, not server-verified). The FK
--       gives schema-level "this column is shaped like a pipeline_runs id" but
--       NOT "this trade was demonstrably classified by that pipeline run."
ALTER TABLE trades ADD COLUMN chart_pattern_classification_pipeline_run_id INTEGER
    REFERENCES pipeline_runs(id);

UPDATE schema_version SET version = 10;
