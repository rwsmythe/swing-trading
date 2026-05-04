-- Migration 0013: Phase 6 Post-Trade Review Surface
--
-- 10 nullable trade-row additions (operator-input fields populated at review
-- completion; NULL means "not reviewed yet") + new review_log table for
-- daily/weekly/monthly/quarterly/circuit_breaker cadence rows + unique-index
-- on cadence period for idempotent pre-create.
--
-- Locked decisions §2.4 (counterfactual storage shape: realized_R_if_plan_followed
-- only; cost + lucky derived on read), §2.5 (slim 14 + 7 persisted aggregates
-- frozen-at-review), §2.6 (review window default 7 days, configurable later),
-- §2.7 (5 cadence types schema-supported, daily/weekly/monthly UI-wired in V1).
--
-- Schema-level constraints kept minimal:
--   - mistake_tags is JSON-text (validation lives in repo via
--     swing.trades.review.validate_mistake_tags + canonicalize_mistake_tags);
--     SQLite cannot CHECK-constrain a JSON-list of strings against a vocabulary.
--   - Single-letter grade columns CHECK-restricted to ('A','B','C','D','F') so
--     the schema is the floor; Python helpers compute_process_grade enforce
--     value-class semantics (F-floor, disqualifying-D cap, weighted boundaries).
--   - review_type CHECK-restricted to the 5 cadence values (daily/weekly/
--     monthly/quarterly/circuit_breaker) per locked decision §2.7.

-- ----- 10 nullable additions to trades -----

ALTER TABLE trades ADD COLUMN reviewed_at TEXT;
ALTER TABLE trades ADD COLUMN mistake_tags TEXT;
ALTER TABLE trades ADD COLUMN entry_grade TEXT
    CHECK (entry_grade IS NULL OR entry_grade IN ('A','B','C','D','F'));
ALTER TABLE trades ADD COLUMN management_grade TEXT
    CHECK (management_grade IS NULL OR management_grade IN ('A','B','C','D','F'));
ALTER TABLE trades ADD COLUMN exit_grade TEXT
    CHECK (exit_grade IS NULL OR exit_grade IN ('A','B','C','D','F'));
ALTER TABLE trades ADD COLUMN process_grade TEXT
    CHECK (process_grade IS NULL OR process_grade IN ('A','B','C','D','F'));
ALTER TABLE trades ADD COLUMN disqualifying_process_violation INTEGER
    CHECK (disqualifying_process_violation IS NULL OR disqualifying_process_violation IN (0,1));
ALTER TABLE trades ADD COLUMN realized_R_if_plan_followed REAL;
ALTER TABLE trades ADD COLUMN mistake_cost_confidence TEXT
    CHECK (mistake_cost_confidence IS NULL OR mistake_cost_confidence IN ('high','medium','low'));
ALTER TABLE trades ADD COLUMN lesson_learned TEXT;

-- ----- review_log table (slim 14 + 7 persisted aggregates) -----

CREATE TABLE review_log (
    review_id INTEGER PRIMARY KEY,
    review_type TEXT NOT NULL
        CHECK (review_type IN ('daily','weekly','monthly','quarterly','circuit_breaker')),
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    scheduled_date TEXT NOT NULL,
    completed_date TEXT,
    skipped INTEGER NOT NULL DEFAULT 0
        CHECK (skipped IN (0,1)),
    duration_minutes INTEGER,
    n_trades_reviewed INTEGER NOT NULL DEFAULT 0,
    total_mistake_cost_R REAL NOT NULL DEFAULT 0,
    total_lucky_violation_R REAL NOT NULL DEFAULT 0,
    primary_lesson TEXT,
    next_period_focus TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    -- Persisted aggregates (frozen-at-review-completion):
    net_R_effective REAL,
    expectancy_R_effective REAL,
    win_rate REAL,
    avg_win_R REAL,
    avg_loss_R REAL,
    profit_factor REAL,
    max_drawdown_R REAL
);

-- Idempotency support: one cadence row per (type, period_start, period_end)
CREATE UNIQUE INDEX ux_review_log_cadence_period
    ON review_log (review_type, period_start, period_end);

UPDATE schema_version SET version = 13;
