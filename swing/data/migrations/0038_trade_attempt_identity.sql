-- 0038_trade_attempt_identity.sql
-- 22-A4: the PER-ATTEMPT IDENTITY TOKEN on `trades`.
--
-- The primitive 22-A's declared residual is blocked on: a token that is
-- CO-DURABLE with the row it identifies (written by the SAME INSERT, in the
-- SAME transaction -- anything stamped afterwards is a run-level stamp, gotcha
-- #30) and UNIQUE PER ATTEMPT (it survives rollback-and-retry without
-- collision, which the rowid does not: a rolled-back rowid is handed straight
-- to the next insert by the engine).
--
-- ADDITIVE. One ADD COLUMN, one partial UNIQUE index, one BEFORE UPDATE
-- trigger. Nothing is rebuilt, no existing row is mutated, and there is NO
-- BACKFILL -- every pre-existing row reads NULL, which is what the partial
-- index is for.
--
-- Atomic via explicit BEGIN; ... COMMIT; per gotcha #9 (executescript issues an
-- implicit COMMIT and runs its statements in autocommit, so a migration
-- without its own transaction could leave the column present with neither its
-- index nor its immutability trigger). Bumps schema_version 37 -> 38.
--
-- ONE MIGRATION, ONE TASK, ONE VERSION BUMP (0037's header rule, copied
-- deliberately). The runner applies a version ONCE and only when strictly
-- greater than the database's current version -- "current = _current_version(
-- conn); if current >= target_version: return" (swing/data/db.py) -- so
-- anything added to THIS file after any database has recorded v38 would never
-- run on that database again, silently, with CI green because fresh fixtures
-- always apply the whole file. A versioned migration file is an ATOMIC
-- deliverable.
--
-- ============================================================================
-- REVERSIBILITY HEADER
-- ============================================================================
-- The guard is retired by exactly two statements:
--
--     DROP INDEX ux_trades_attempt_id;
--     DROP TRIGGER trg_trades_attempt_id_immutable;
--
-- The COLUMN stays. It is nullable and inert: no read path requires it, no
-- write path fails without it, and dropping a column from `trades` is a table
-- rebuild -- a far larger operation than the thing being undone. A DROP ENDS
-- the proven guarantee rather than falsifying it, so any drop happens only
-- inside a NEW numbered migration.
--
-- ============================================================================
-- WHY EACH PIECE HAS THE SHAPE IT HAS
-- ============================================================================
-- WHY NULLABLE: every one of the rows already in `trades` predates the token
-- and there is no honest value to invent for them. A NOT NULL column would
-- demand a backfill, and a backfilled token would be a stamp asserting an
-- attempt identity that was never minted -- exactly the falsehood the primitive
-- exists to make impossible.
--
-- WHY THE INDEX IS PARTIAL: `WHERE attempt_id IS NOT NULL`. SQLite treats NULLs
-- as distinct in a UNIQUE index, so a full index would also work today -- but
-- the partial form says the intent in the schema: uniqueness is a claim about
-- MINTED tokens, and the legacy rows are not participants.
--
-- WHY THE CHECK CARRIES `typeof(...) = 'text'` AND NOT ONLY THE LENGTH:
-- MEASURED -- a 36-BYTE BLOB satisfies SQLite's `length()` exactly as a
-- 36-character string does, so a length-only CHECK ADMITS it, and the UNIQUE
-- index then holds that BLOB beside its byte-identical text twin without
-- complaint. The typeof half is what makes the column a text key.
-- The CHECK is length-only BEYOND that (it does not attempt to validate uuid4
-- shape) because SQLite has no uuid parser; the canonical-form validation is
-- the Python side's -- `swing/data/repos/trades.py::validate_attempt_id`, the
-- SINGLE validation authority, called by the repo's pre-write guard and by
-- `swing/trades/entry.py::_begin_attempt_identity` alike.
--
-- WHY THE TRIGGER IS UNCONDITIONAL AND CARRIES NO `WHEN`: a validation trigger
-- whose WHEN clause can evaluate to NULL does not fire AT ALL -- it fails OPEN,
-- silently (verified by execution 2026-08-25, the 22-A citation trigger). This
-- trigger has nothing to evaluate: EVERY update of `attempt_id` is refused,
-- including NULL -> token and token -> NULL. A token that can be re-assigned
-- after insertion is not an identity.
--
-- ============================================================================
-- TWO JURISDICTION NOTES (CHARC, 2026-09-06) -- the limits of the trigger,
-- recorded in the file rather than left to be met in a review
-- ============================================================================
-- (A) A `BEFORE UPDATE` TRIGGER CANNOT SEE `INSERT OR REPLACE`. The guard
--     covers UPDATE. REPLACE's implicit DELETE does not fire DELETE triggers
--     unless PRAGMA recursive_triggers is ON, which is OFF by default and is
--     never enabled in this repo -- so a REPLACE writer against `trades` would
--     re-issue the row with a different token and this trigger would never see
--     it. The family was GREPPED EMPTY against `trades`, and the method is
--     recorded because a bare "we checked" is what this class survives on:
--     `insert or replace into trades` / `replace into trades` return ZERO
--     across swing/; the broader `insert or replace|replace into` returns 45
--     hits across 22 files, of which ZERO are executable statements -- every
--     one is prose in a migration header, a trigger message, or a docstring
--     warning about this very class. A future REPLACE writer against `trades`
--     is therefore a DECLARED BREACH rather than an unknown.
-- (B) 22-B DEMAND A REBUILDS `trades` (DROP + CREATE). A rebuild that does not
--     RE-CREATE both `ux_trades_attempt_id` and
--     `trg_trades_attempt_id_immutable` SILENTLY DROPS THE GUARD -- the 0035
--     header's own lesson about what a rebuild costs, applied forward. CHARC
--     has banked this as a 22-B PRECONDITION; it is written here so the next
--     rebuild's author meets it in the file rather than in a review.
-- ============================================================================

BEGIN;

-- 1. THE COLUMN.
ALTER TABLE trades ADD COLUMN attempt_id TEXT
  CHECK (attempt_id IS NULL
         OR (typeof(attempt_id) = 'text' AND length(attempt_id) = 36));

-- 2. UNIQUENESS, over minted tokens only.
CREATE UNIQUE INDEX ux_trades_attempt_id
  ON trades(attempt_id) WHERE attempt_id IS NOT NULL;

-- 3. WRITE-ONCE. See "why the trigger is unconditional" above.
CREATE TRIGGER trg_trades_attempt_id_immutable
BEFORE UPDATE OF attempt_id ON trades
BEGIN SELECT RAISE(ABORT, '22-A4 barrier trg_trades_attempt_id_immutable: trades.attempt_id is WRITE-ONCE. It is minted per attempt and written by the INSERT that creates the row, in that same transaction; a token that can be re-assigned afterwards is not an identity, and the settle-by-identity read would then confirm the wrong attempt. To retire the barrier see the reversibility header of 0038_trade_attempt_identity.sql.'); END;

-- 4. THE VERSION BUMP IS THE FINAL STATEMENT (Phase 9 section A.0 precedent --
--    a truncated transaction would leave the version stamp ahead of the schema).
UPDATE schema_version SET version = 38;

COMMIT;
