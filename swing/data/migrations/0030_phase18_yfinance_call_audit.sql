-- 0030_phase18_yfinance_call_audit.sql
-- Lands the yfinance_calls audit table (Phase 18 Arc 18-C) mirroring
-- schwab_api_calls (0018) for yfinance fetch observability (feeds 18-D/18-E).
-- Atomic via explicit BEGIN; ... COMMIT; per CLAUDE.md gotcha #9
-- "executescript() implicit COMMIT" (runner-level rollback can only undo
-- partial DDL when the SQL itself opens an explicit transaction).
-- Bumps schema_version 29 -> 30.
--
-- TWO deliberate divergences from schwab_api_calls (BY DESIGN):
--   (1) status CHECK includes 'empty' as a FIRST-CLASS value, DISTINCT from
--       'error' (CLAUDE.md F6 gotcha): yfinance returns empty for rate-limit /
--       network / weekend reasons, a transient data-collection signal the
--       monitors must distinguish from a hard error.
--   (2) NO `environment` column. yfinance is the always-on, environment-
--       agnostic fetcher (no sandbox/production domain-row gating, unlike
--       Schwab). Adding it would imply a gating that does not exist.

BEGIN;

CREATE TABLE yfinance_calls (
    call_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                TEXT NOT NULL,             -- ISO 8601 naive; call start
    call_type         TEXT NOT NULL,
    ticker            TEXT,                      -- single/intraday shapes
    ticker_count      INTEGER,                   -- batch shape (N tickers, ONE row)
    response_time_ms  INTEGER,
    status            TEXT NOT NULL,
    rows_returned     INTEGER,                   -- rows in the frame yf.download returned; 0 on empty
    error_message     TEXT,                      -- sanitized/truncated yfinance exc string
    pipeline_run_id   INTEGER,                   -- FK to pipeline_runs(id); NULL for cli/web
    surface           TEXT NOT NULL,

    CHECK (call_type IN (
        'download_single', 'download_batch', 'download_intraday'
    )),
    CHECK (status IN (
        'in_flight', 'success', 'empty', 'error'
    )),
    CHECK (surface IN ('pipeline', 'cli', 'web')),

    -- Numeric defense-in-depth under the dataclass (Codex R3 MINOR -- inserts
    -- bypass dataclass validation):
    CHECK (response_time_ms IS NULL OR response_time_ms >= 0),
    CHECK (rows_returned   IS NULL OR rows_returned   >= 0),
    CHECK (ticker_count    IS NULL OR ticker_count    >  0),
    -- No empty/whitespace ticker for single/intraday rows (Codex R7 MINOR):
    CHECK (ticker IS NULL OR length(trim(ticker)) > 0),

    -- (NOTE -- operator/director decision section-9 #2, LOCKED to SET NULL): the
    -- SQL run-linkage CHECK is DROPPED. It was incompatible with ON DELETE SET
    -- NULL (a parent-delete NULLs a pipeline row's run_id, which would have
    -- violated the CHECK). The run-linkage invariant is relocated to its correct
    -- layer: the CONTEXT-INSTALL validation in yfinance_audit_context.py, which
    -- catches a context-install bug at the SOURCE (upstream of the insert) and
    -- never sees the post-delete state. R12 is ADDRESSED, not abandoned.

    -- Shape invariant (Codex R3 MINOR): batch carries ticker_count (ticker NULL);
    -- single/intraday carry ticker (ticker_count NULL). Holds at insert time too
    -- (the in-flight row is inserted WITH the shape fields populated -- both are
    -- known at call start).
    CHECK (
        (call_type = 'download_batch'
            AND ticker_count IS NOT NULL AND ticker IS NULL)
        OR
        (call_type IN ('download_single', 'download_intraday')
            AND ticker IS NOT NULL AND ticker_count IS NULL)
    ),

    -- ON DELETE SET NULL (operator/director decision section-9 #2, LOCKED): the
    -- DIRECT mirror of schwab_api_calls (0018) + the audit-linkage convention
    -- (temporal_log 0022 -- "detection SURVIVES run pruning"). On a pipeline_runs
    -- delete the audit row SURVIVES and loses only its run link (pipeline_run_id
    -- -> NULL). No run-linkage CHECK to violate (dropped above); no future-pruning
    -- landmine (no pruning-order coupling). The run-linkage guard lives at the
    -- context-install layer, not here.
    FOREIGN KEY (pipeline_run_id)
        REFERENCES pipeline_runs(id)
        ON DELETE SET NULL
);

CREATE INDEX ix_yfinance_calls_ts
    ON yfinance_calls(ts);

CREATE INDEX ix_yfinance_calls_status_ts
    ON yfinance_calls(status, ts);

CREATE INDEX ix_yfinance_calls_pipeline_run_id_ts
    ON yfinance_calls(pipeline_run_id, ts);

CREATE INDEX ix_yfinance_calls_call_type_ts
    ON yfinance_calls(call_type, ts);

CREATE INDEX ix_yfinance_calls_surface_ts
    ON yfinance_calls(surface, ts);          -- monitors filter by surface (mirrors schwab)

CREATE INDEX ix_yfinance_calls_ticker_ts
    ON yfinance_calls(ticker, ts);           -- ticker-level health is a natural yfinance query

UPDATE schema_version SET version = 30;

COMMIT;
