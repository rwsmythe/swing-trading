-- 0009_pipeline_pattern_classifications.sql
--
-- Pipeline-time pattern classification cache. One row per (pipeline_run_id, ticker)
-- for tickers in chart-scope. Bound to pipeline_runs.id; reads bind via
-- pipeline_runs.evaluation_run_id → pipeline_run_id (Bug 7 family discipline).

CREATE TABLE pipeline_pattern_classifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_run_id INTEGER NOT NULL REFERENCES pipeline_runs(id),
    ticker TEXT NOT NULL,
    pattern TEXT
        CHECK (pattern IS NULL OR pattern IN ('none', 'flag')),
    confidence REAL
        CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    components_json TEXT NOT NULL,          -- frozen feature snapshot (falsifiability)
    pivot REAL,
    pole_high REAL,
    flag_low REAL,
    -- First-class boundary dates for queryability without JSON-extracting
    -- (adversarial-review R1 Minor 2). All four NULL on classifier-error rows
    -- and on rows where no candidate passed any gate (best-attempted baseline).
    pole_start_date TEXT,
    pole_end_date TEXT,
    flag_start_date TEXT,
    flag_end_date TEXT,
    computed_at TEXT NOT NULL,              -- ISO timestamp
    UNIQUE (pipeline_run_id, ticker),
    -- Row-level state-shape constraint (adversarial-review R2 Major 2).
    -- SQLite enforces this at INSERT/UPDATE time so the schema rejects
    -- inconsistent NULL combinations rather than relying on app discipline.
    --
    --   pattern='flag': all anchor + confidence columns NOT NULL
    --   pattern='none': anchor + confidence columns ALL NULL (best-attempted
    --                   measurements live in components_json, not first-class)
    --   pattern  IS NULL  (classifier error): anchor + confidence columns ALL NULL
    --
    -- components_json is NOT NULL in every row by separate column constraint.
    CONSTRAINT pattern_state_consistency CHECK (
        (pattern = 'flag'
         AND confidence       IS NOT NULL
         AND pivot            IS NOT NULL
         AND pole_high        IS NOT NULL
         AND flag_low         IS NOT NULL
         AND pole_start_date  IS NOT NULL
         AND pole_end_date    IS NOT NULL
         AND flag_start_date  IS NOT NULL
         AND flag_end_date    IS NOT NULL)
        OR
        ((pattern = 'none' OR pattern IS NULL)
         AND confidence       IS NULL
         AND pivot            IS NULL
         AND pole_high        IS NULL
         AND flag_low         IS NULL
         AND pole_start_date  IS NULL
         AND pole_end_date    IS NULL
         AND flag_start_date  IS NULL
         AND flag_end_date    IS NULL)
    )
);

CREATE INDEX idx_pattern_classifications_run ON pipeline_pattern_classifications(pipeline_run_id);

UPDATE schema_version SET version = 9;
