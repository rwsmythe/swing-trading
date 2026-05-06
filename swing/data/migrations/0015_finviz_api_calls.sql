-- Migration 0015: Finviz Elite API integration — finviz_api_calls audit table
--
-- Persists every fetch attempt (success, error, skipped_manual_override) with
-- timing + rate-limit headroom + signature-hash for drift detection. Each
-- pipeline run records exactly ONE row regardless of outcome.
--
-- Locked decisions §2.4: status enum CHECK-restricted; ts ISO-8601 lexicographic
-- sort-safe; index on (ts DESC) supports `swing finviz status` ordering.
--
-- Additive-only migration; no table rebuild; foreign_keys=OFF discipline at the
-- runner level applies but is moot here (no FKs introduced).

CREATE TABLE finviz_api_calls (
    call_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    screen_query TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN ('ok','error','skipped_manual_override')),
    row_count INTEGER,
    response_time_ms INTEGER,
    rate_limit_remaining INTEGER,
    signature_hash TEXT,
    error_message TEXT
);

CREATE INDEX ix_finviz_api_calls_ts_desc ON finviz_api_calls (ts DESC);

UPDATE schema_version SET version = 15;
