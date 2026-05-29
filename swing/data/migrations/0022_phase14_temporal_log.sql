-- swing/data/migrations/0022_phase14_temporal_log.sql
-- Phase 14 Sub-bundle 2 -- v22 migration: temporal pattern detection +
-- observation log infrastructure (2 NEW append-only tables).
-- Atomic via explicit BEGIN; ... COMMIT; per CLAUDE.md gotcha #9
-- (executescript implicit COMMIT) + migration 0021 precedent.
-- Bumps schema_version 21 -> 22.
--
-- APPEND-ONLY INVARIANT (spec section 2.3 NORMATIVE): no application code
-- path ever UPDATEs or DELETEs a row in either table. Detection FACTS
-- (structural_anchors_json, composite_score, per_pattern_metadata_json,
-- data_asof_date, ...) are LOCKED at detection. ohlc_today_json is LOCKED
-- at observation and NEVER re-fetched. Eliminates gotchas #26 + #37 by
-- construction (forward-walk; no archive re-read; no regeneration).
--
-- NOTE for future maintainers: pattern_forward_observations.status allows
-- 6 values for forward-compat, BUT V1+ only EMITS the ruleset-agnostic
-- subset {pending, triggered_open, invalidated, expired}. The
-- triggered_closed_at_target / triggered_closed_at_stop values are RESERVED
-- for the Phase 15+ replay engine (OUT-OF-SCOPE). The dead V1+ values are
-- NOT a wiring gap.

BEGIN;

CREATE TABLE pattern_detection_events (
    detection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    detection_date TEXT NOT NULL,            -- action_session_date (operator-facing label the verdict is FOR)
    data_asof_date TEXT NOT NULL,            -- detector DATA cutoff (last completed bar); forward-walk boundary anchor
    pattern_class TEXT NOT NULL CHECK (pattern_class IN (
        'vcp', 'flat_base', 'cup_with_handle',
        'high_tight_flag', 'double_bottom_w'
    )),
    structural_anchors_json TEXT NOT NULL,   -- LOCKED at detection (window + full evidence asdict)
    composite_score REAL NOT NULL,           -- LOCKED at detection
    detector_version TEXT NOT NULL,          -- provenance: which detector emitted this
    finviz_screen_state TEXT,                -- canonicalized per-ticker eval/screen state JSON (nullable for non-pipeline)
    source TEXT NOT NULL CHECK (source IN (
        'pipeline', 'v2_cohort', 'd2_baseline', 'backfill', 'synthetic'
    )),
    per_pattern_metadata_json TEXT NOT NULL, -- LOCKED (sector/industry/adr_pct/atr_pct/ret_90d/prox_52w/rs_rank/close/market_cap-null)
    pipeline_run_id INTEGER
        REFERENCES pipeline_runs(id) ON DELETE SET NULL,  -- AUDIT LINKAGE: detection SURVIVES run pruning (not a fact mutation)
    chart_render_id INTEGER
        REFERENCES chart_renders(id) ON DELETE SET NULL,  -- AUDIT LINKAGE to ephemeral run-scoped chart cache; NULL on render-fail or later refresh
    created_at TEXT NOT NULL                 -- INSERT timestamp (ISO)
);

-- One detection per (source, ticker, detection_date, pattern_class). For
-- source='pipeline', detection_date == the run's action_session_date.
CREATE UNIQUE INDEX idx_pde_source_ticker_date_class
    ON pattern_detection_events(source, ticker, detection_date, pattern_class);
CREATE INDEX idx_pde_ticker_date
    ON pattern_detection_events(ticker, detection_date);
CREATE INDEX idx_pde_class_date
    ON pattern_detection_events(pattern_class, detection_date);
CREATE INDEX idx_pde_pipeline_run_id
    ON pattern_detection_events(pipeline_run_id);
-- Daily observe-step open scan (Codex chain #2 Minor #4): list_observable_detections
-- filters (source = ? AND data_asof_date < ?); a (source, data_asof_date) index
-- serves that range predicate directly.
CREATE INDEX idx_pde_source_data_asof
    ON pattern_detection_events(source, data_asof_date);

CREATE TABLE pattern_forward_observations (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    detection_id INTEGER NOT NULL
        REFERENCES pattern_detection_events(detection_id) ON DELETE RESTRICT,  -- append-only: cannot delete a detection with observations
    observation_date TEXT NOT NULL,          -- the trading session this bar belongs to (ISO)
    ohlc_today_json TEXT NOT NULL,           -- LOCKED at observation; never re-fetched ({open,high,low,close,volume,provider})
    status TEXT NOT NULL CHECK (status IN (
        'pending', 'triggered_open',
        'triggered_closed_at_target', 'triggered_closed_at_stop',
        'invalidated', 'expired'
    )),
    status_change_event TEXT CHECK (
        status_change_event IS NULL OR status_change_event IN (
            'entry_fired', 'stop_fired', 'target_fired',
            'time_exit', 'shape_break', 'observation_horizon_reached'
        )
    ),
    sessions_since_detection INTEGER NOT NULL
        CHECK (sessions_since_detection >= 0),  -- count from detection.data_asof_date UP TO AND INCLUDING observation_date; mirrors the dataclass validator (gotcha #11)
    created_at TEXT NOT NULL,                 -- INSERT timestamp (ISO)

    UNIQUE (detection_id, observation_date)
);

CREATE INDEX idx_pfo_detection_date
    ON pattern_forward_observations(detection_id, observation_date);
CREATE INDEX idx_pfo_observation_date
    ON pattern_forward_observations(observation_date);
CREATE INDEX idx_pfo_status
    ON pattern_forward_observations(status);

UPDATE schema_version SET version = 22;   -- MUST be the final DML/DDL statement before COMMIT

COMMIT;
