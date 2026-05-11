-- Enforce the "one open trade per ticker" invariant at the schema level.
-- Without this, two concurrent `swing trade entry` calls (or even one malformed
-- legacy import) can both commit and leave the journal in a broken state where
-- the entry service's pre-insert list_open_trades() check observes nothing
-- conflicting on both sides of a race.
--
-- The partial unique index makes the race-losing INSERT fail with IntegrityError;
-- the entry service catches that and raises DuplicateOpenPositionError.

CREATE UNIQUE INDEX ux_trades_one_open_per_ticker
    ON trades(ticker) WHERE status = 'open';

UPDATE schema_version SET version = 4;
