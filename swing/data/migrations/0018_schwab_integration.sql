-- 0018_schwab_integration.sql
-- Lands schwab_api_calls audit table + ALTERs on account_equity_snapshots and
-- reconciliation_runs for V1 Schwab API integration.
-- Atomic via explicit BEGIN; ... COMMIT; per Codex R1 Critical #1 +
-- CLAUDE.md gotcha "executescript() implicit COMMIT". Runner-level
-- conn.rollback() can undo partial DDL only when the SQL itself opens
-- an explicit transaction.
-- Bumps schema_version 17 -> 18.

BEGIN;

CREATE TABLE schwab_api_calls (
    call_id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                            TEXT NOT NULL,
    endpoint                      TEXT NOT NULL,
    http_status                   INTEGER,
    response_time_ms              INTEGER,
    rate_limit_remaining          INTEGER,
    signature_hash                TEXT,
    status                        TEXT NOT NULL,
    error_message                 TEXT,
    linked_snapshot_id            INTEGER,
    linked_reconciliation_run_id  INTEGER,
    pipeline_run_id               INTEGER,
    surface                       TEXT NOT NULL,
    environment                   TEXT NOT NULL,

    CHECK (status IN (
        'in_flight', 'success', 'error',
        'auth_failed', 'rate_limited', 'concurrent_refresh'
    )),
    CHECK (surface IN ('pipeline', 'cli')),
    CHECK (environment IN ('sandbox', 'production')),
    CHECK (endpoint IN (
        'oauth.code_exchange', 'oauth.refresh', 'oauth.revoke',
        'accounts.linked', 'accounts.details',
        'accounts.orders.list', 'accounts.transactions.list',
        'marketdata.quotes', 'marketdata.pricehistory'
    )),

    FOREIGN KEY (linked_snapshot_id)
        REFERENCES account_equity_snapshots(snapshot_id)
        ON DELETE SET NULL,
    FOREIGN KEY (linked_reconciliation_run_id)
        REFERENCES reconciliation_runs(run_id)
        ON DELETE SET NULL,
    FOREIGN KEY (pipeline_run_id)
        REFERENCES pipeline_runs(id)
        ON DELETE SET NULL
    -- NOTE: plan §C.1 text writes REFERENCES pipeline_runs(run_id) but the
    -- pipeline_runs PK is `id` (set by migration 0003); banked as V2.1
    -- §VII.F plan-text amendment candidate (Phase 9 Sub-bundle D D2-class
    -- deviation — plan-vs-actual-schema column-name drift).
);

CREATE INDEX ix_schwab_api_calls_ts
    ON schwab_api_calls(ts);

CREATE INDEX ix_schwab_api_calls_status_ts
    ON schwab_api_calls(status, ts);

CREATE INDEX ix_schwab_api_calls_pipeline_run_id_ts
    ON schwab_api_calls(pipeline_run_id, ts);

CREATE INDEX ix_schwab_api_calls_surface_ts
    ON schwab_api_calls(surface, ts);

ALTER TABLE account_equity_snapshots
    ADD COLUMN schwab_account_hash TEXT;

ALTER TABLE reconciliation_runs
    ADD COLUMN schwab_api_call_id INTEGER
        REFERENCES schwab_api_calls(call_id) ON DELETE SET NULL;

UPDATE schema_version SET version = 18;

COMMIT;
