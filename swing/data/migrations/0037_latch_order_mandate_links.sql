-- 0037_latch_order_mandate_links.sql
-- 22-A: the durable order<->mandate LINK, and the STRUCTURAL immutability that
-- makes the mandate's frozen invalidation provable.
-- ADDITIVE. Nothing is rebuilt, no existing row is mutated, and the only
-- DROPs are the two provenance_corrections triggers this same transaction
-- immediately re-creates (see THE CONDITION-4 ADJUDICATION below).
-- Atomic via explicit BEGIN; ... COMMIT; per gotcha #9 (executescript issues an
-- implicit COMMIT and runs its statements in autocommit, so a migration
-- without its own transaction would leave provenance_corrections momentarily
-- unguarded between a DROP and its CREATE). Bumps schema_version 36 -> 37.
--
-- ONE MIGRATION, ONE TASK, ONE VERSION BUMP (review 22A-R9-11). The runner
-- applies a version ONCE and only when strictly greater than the database's
-- current version -- "current = _current_version(conn); if current >=
-- target_version: return" (swing/data/db.py) -- so anything added to THIS file
-- after any database has recorded v37 would never run on that database again,
-- silently, with CI green because fresh fixtures always apply the whole file.
-- A versioned migration file is an ATOMIC deliverable.
--
-- ============================================================================
-- REVERSIBILITY HEADER (CHARC CONDITION 3, 2026-08-24)
-- ============================================================================
-- The candidates barrier is retired by exactly two statements:
--
--     DROP TRIGGER trg_candidates_no_update;
--     DROP TRIGGER trg_candidates_no_delete;
--
-- and the conflict-scoped INSERT barrier by one more:
--
--     DROP TRIGGER trg_candidates_no_replace;
--
-- The other conflict-scoped INSERT barriers this migration installs -- each on
-- an append-only table whose 0033/0036/S3 DELETE trigger REPLACE was measured
-- to bypass -- are retired one statement each:
--
--     DROP TRIGGER trg_loml_no_replace;   -- latch_order_mandate_links
--     DROP TRIGGER trg_loi_no_replace;    -- latch_order_intents
--     DROP TRIGGER trg_pc_no_replace;     -- provenance_corrections
--
-- The stored-canonical reading table installed by section 3d carries the same
-- three-barrier set, retired one statement each:
--
--     DROP TRIGGER trg_fei_no_update;
--     DROP TRIGGER trg_fei_no_delete;
--     DROP TRIGGER trg_fei_no_replace;
--
-- DROPPING THESE THREE IS NOT SILENT, unlike the three above it: the citation
-- trigger compares against fill_envelope_identity rows, so an edited or
-- substituted reading changes what a correction is allowed to claim. Their loss
-- is a loss of the ONLY structural guarantee that the value SQL compares is the
-- value the authority actually derived.
--
-- NOTE the asymmetry, because it decides what a drop COSTS. Dropping either
-- candidates barrier mechanically halts structural admission (the reader's
-- body check sees it). Dropping any of these THREE does not: they guard
-- append-only ledgers the reader does not introspect, so their loss is silent
-- and the PROCEDURAL half -- a drop happens only inside a NEW numbered
-- migration -- is the whole record.
--
-- A DROP ENDS the proven guarantee rather than falsifying it, so ANY DROP MUST
-- ITSELF BE RECORDED: it is performed ONLY inside a NEW numbered migration,
-- which is the record. That is the procedural half.
--
-- THE MECHANICAL HALF, which is what makes single-state coherent: the
-- admission reader verifies BOTH barrier triggers exist AT READ TIME -- and
-- compares their BODIES against a verbatim pinned copy, not their names --
-- and refuses barrier_not_installed if either is absent or altered. So a drop
-- mechanically HALTS structural admission whether or not anyone remembered to
-- write the record. The emergency escape hatch survives; what it can no longer
-- do is leave admission running on a claim the barrier no longer backs.
--
-- ============================================================================
-- THE CONDITION-4 ADJUDICATION (CHARC, 2026-08-24) -- named here so the next
-- reader of "the migration is ADDITIVE; nothing dropped" finds the decision
-- rather than the ambiguity.
-- ============================================================================
-- CONDITION 4 said: additive; nothing rebuilt, nothing dropped, no existing row
-- touched. This migration exceeds its LETTER in two places, BOTH ROUTED AND
-- BOTH APPROVED:
--   EXCEPTION 1 -- THREE CREATE TRIGGERs on candidates_immutability_epoch
--     rather than the two originally enumerated. Purely additive: the count
--     moving is not a widening of the condition's KIND. (The third trigger's
--     PURPOSE changed at the Option-C carve, from guarding an ERA SEQUENCE --
--     which single-state cannot represent -- to closing a measured
--     INSERT OR REPLACE hole; surfaced at his section-3 gate, not absorbed.)
--   EXCEPTION 2 -- the TRANSACTIONAL replacement of two provenance_corrections
--     triggers. SQLite has no ALTER TRIGGER and both must learn six new
--     columns. His ruling, verbatim: "A transactional DROP+CREATE that replaces
--     a guard with an EQUAL-OR-STRONGER guard is not a DROP in Condition-4's
--     sense -- but it is ALWAYS DECLARED, NEVER SILENT."
--   EXCEPTION 3 -- A SECOND NEW TABLE, fill_envelope_identity (section 3d),
--     with its three append-only triggers, added at the PERSIST-CANONICAL
--     reshape (CHARC + RD, 2026-08-26). DECLARED HERE RATHER THAN ABSORBED,
--     under EXCEPTION 1's own reasoning read across from triggers to tables:
--     a second CREATE TABLE meets CONDITION 4's criterion exactly as the first
--     did -- nothing rebuilt, nothing dropped, NO EXISTING ROW TOUCHED -- so
--     the count moving is not a widening of the condition's KIND. It carries
--     NO BACKFILL precisely so that "no existing row touched" stays literally
--     true and so that no judgment is ever made in SQL; the service fills it.
--     The alternative shape -- ADD COLUMN on `fills` plus an UPDATE backfill --
--     WAS rejected on this ground: the UPDATE would have touched 51 existing
--     rows, which is a different KIND and would have had to be routed.

BEGIN;

-- ============================================================================
-- 1. THE SINGLE-STATE IMMUTABILITY EPOCH
--
-- One row, one boundary, no eras. A fire is either at-or-below the boundary
-- (PRE-barrier: it already existed when the barrier was installed, so no
-- structural proof of its frozen values is available) or STRICTLY ABOVE it
-- (POST-barrier: it was created under the barrier, so the value derive_latches
-- reads live IS the value the fire declared).
--
-- THE COMPARISON IS STRICTLY GREATER THAN, AND THE BOUNDARY ROW IS PRE-BARRIER
-- (inherited finding 22A-R9-02). A candidate whose id EQUALS
-- max_candidate_id_at_barrier already existed at migration time. ">=" would
-- stamp it live_at_acceptance and mint a false structural-proof label for the
-- one row the boundary is named after.
-- ============================================================================
CREATE TABLE candidates_immutability_epoch (
  epoch_id                    INTEGER PRIMARY KEY CHECK (epoch_id = 1),
  max_candidate_id_at_barrier INTEGER NOT NULL,
  applied_at                  TEXT    NOT NULL
);

-- Seeded from the live table, so the boundary is a MEASUREMENT rather than a
-- constant somebody typed. COALESCE covers an empty candidates table (a fresh
-- database migrating 0001 -> 0037 in one walk): boundary 0 means every future
-- fire is post-barrier, which is exactly right for a database that has never
-- held an unbarriered candidate.
INSERT INTO candidates_immutability_epoch (epoch_id, max_candidate_id_at_barrier, applied_at)
SELECT 1, COALESCE(MAX(id), 0), strftime('%Y-%m-%dT%H:%M:%SZ', 'now') FROM candidates;

-- THE THREE EPOCH TRIGGERS, CREATED AFTER THE SEEDING ROW.
--
-- A TWO-TRIGGER EPOCH IS FAIL-OPEN AT SQLITE'S DEFAULT, MEASURED BY EXECUTION
-- (sqlite 3.50.4): for the REPLACE conflict-resolution strategy SQLite fires
-- DELETE triggers IF AND ONLY IF PRAGMA recursive_triggers is ON, and it is OFF
-- by default. "grep -rn recursive_triggers swing/ tests/" returns ZERO hits and
-- swing/data/db.py sets only busy_timeout, foreign_keys and journal_mode -- so
-- the default governs in production. With UPDATE+DELETE triggers only,
-- INSERT OR REPLACE, bare REPLACE and INSERT OR IGNORE all reach the row.
--
-- AND THE DIRECTION OF THAT FAILURE IS THE UNTOLERABLE ONE: an INSERT OR
-- REPLACE LOWERING max_candidate_id_at_barrier stamps a PRE-barrier fire
-- live_at_acceptance -- a false structural-proof label minted by the very
-- mechanism that exists to make the proof honest. Raising it merely costs an
-- admission (fail-closed, survivable).
--
-- The CHECK (epoch_id = 1) is kept as the declarative belt -- it alone stops a
-- plain second-row INSERT -- but the trigger is the load-bearing half, because
-- REPLACE satisfies the CHECK by deleting the row that conflicts with it.
CREATE TRIGGER trg_candidates_epoch_no_update BEFORE UPDATE ON candidates_immutability_epoch
BEGIN SELECT RAISE(ABORT, '22-A barrier trg_candidates_epoch_no_update: the candidates immutability epoch is written ONCE by migration 0037 and never again. Its boundary is what stamps a fire pre- or post-barrier, so an edit would re-tier fires that are already linked. To retire the barrier see the reversibility header of 0037_latch_order_mandate_links.sql.'); END;

CREATE TRIGGER trg_candidates_epoch_no_delete BEFORE DELETE ON candidates_immutability_epoch
BEGIN SELECT RAISE(ABORT, '22-A barrier trg_candidates_epoch_no_delete: the candidates immutability epoch is PERMANENT. Deleting it would leave every freeze_tier derivation without a boundary to compare against. To retire the barrier see the reversibility header of 0037_latch_order_mandate_links.sql.'); END;

CREATE TRIGGER trg_candidates_epoch_no_insert BEFORE INSERT ON candidates_immutability_epoch
BEGIN SELECT RAISE(ABORT, '22-A barrier trg_candidates_epoch_no_insert: the candidates immutability epoch is seeded ONCE by migration 0037. This trigger exists because INSERT OR REPLACE bypasses a DELETE trigger whenever PRAGMA recursive_triggers is OFF, which is SQLite default and this repo never enables it -- a measured fail-open path to a false structural-proof label. To retire the barrier see the reversibility header of 0037_latch_order_mandate_links.sql.'); END;

-- ============================================================================
-- 2. THE candidates IMMUTABILITY BARRIER -- UPDATE, DELETE and the
--    CONFLICT-SCOPED INSERT that closes REPLACE.
--
-- This is the arc's PROOF of RD's frozen-value gate for every fire created
-- after it. Writer-absence is not evidence (D36): "no UPDATE/DELETE path
-- exists for candidates" is a claim with a shelf life, and the barrier is what
-- converts it into a structural property.
-- ============================================================================
CREATE TRIGGER trg_candidates_no_update BEFORE UPDATE ON candidates
BEGIN SELECT RAISE(ABORT, '22-A barrier trg_candidates_no_update: candidates rows are IMMUTABLE from migration 0037. A re-evaluation APPENDS a new row; it never edits an existing one. To change a fire''s recorded values you must add an evaluation run. To retire the barrier see the reversibility header of 0037_latch_order_mandate_links.sql.'); END;

CREATE TRIGGER trg_candidates_no_delete BEFORE DELETE ON candidates
BEGIN SELECT RAISE(ABORT, '22-A barrier trg_candidates_no_delete: candidates rows are PERMANENT from migration 0037. The latch identity space and every provenance citation address rows by a REUSABLE rowid, so a delete would silently repoint them. Pruning is a migration-level operation -- see the reversibility header of 0037_latch_order_mandate_links.sql.'); END;

-- THE UPDATE+DELETE PAIR IS FAIL-OPEN TO REPLACE, ON THIS ARC'S LOAD-BEARING
-- TABLE, AND IT IS WORSE HERE THAN ON THE EPOCH (CHARC's generalisation of the
-- epoch finding, 2026-08-24). MEASURED at production settings
-- (recursive_triggers default OFF, foreign_keys ON) against the real candidates
-- shape, which carries TWO conflict targets -- id INTEGER PRIMARY KEY and
-- UNIQUE(evaluation_run_id, ticker):
--
--   INSERT OR REPLACE on the UNIQUE  -> SUCCEEDS: id moved 12284 -> 12285,
--                                       pivot/stop rewritten,
--                                       candidate_criteria CASCADE-wiped 1 -> 0
--   bare REPLACE on the rowid PK     -> SUCCEEDS: id preserved, pivot/stop
--                                       rewritten, candidate_criteria wiped
--
-- That is exactly the id-reuse catastrophe the DELETE half exists to prevent,
-- reached with BOTH barrier triggers present, canonical and UNFIRED -- so the
-- admission reader's body-comparison integrity check cannot see it. The
-- triggers are not altered; they are BYPASSED.
--
-- ONE THING INCIDENTALLY PROTECTS THE WRONG HALF and must not be mistaken for a
-- defence: with a citing link row present, candidate_id REFERENCES
-- candidates(id) ON DELETE RESTRICT blocks both REPLACE paths. So the FK covers
-- the POST-acceptance population and leaves the PRE-acceptance population fully
-- exposed -- and pre-acceptance is precisely the window that matters, because
-- the link copies frozen_pivot / frozen_invalidation AT MINT TIME. A REPLACE
-- before acceptance rewrites the very values that are then frozen and stamped
-- live_at_acceptance.
--
-- THE FIX CANNOT BE THE EPOCH'S. candidates must accept ordinary INSERTs every
-- night, so a blanket BEFORE INSERT barrier is unavailable. What is available
-- is a CONFLICT-SCOPED one: refuse an INSERT that would COLLIDE with an
-- existing row, so REPLACE can never reach its delete half. BEFORE INSERT
-- triggers fire BEFORE conflict resolution deletes anything -- the property the
-- fix rests on, measured rather than assumed.
--
-- TWO BEHAVIOUR CHANGES, DECLARED rather than discovered at the live pipeline
-- gate: (a) INSERT OR IGNORE on a duplicate candidate now ABORTS where it
-- previously no-op'd, and (b) a plain duplicate INSERT now aborts with THIS
-- message rather than SQLite's UNIQUE message -- same outcome, different text,
-- and this text is the more useful of the two. Neither is reachable from
-- production today: a case-insensitive grep for "insert or replace|replace
-- into" across swing/ (*.py, *.sql) returns ZERO executable statements (every
-- hit is a comment FORBIDDING the idiom) and insert_candidates uses a plain
-- INSERT. That is SERVICE-prevention at an incidence of zero, which is exactly
-- the posture the barrier exists to replace.
--
-- THE PK CONFLICT CLAUSE READS `NEW.<pk> != -1`, AND THE `IS NOT NULL` FORM IT
-- REPLACES NEVER FIRED (Codex 22A-R8-02; CHARC-ruled 2026-08-26). In a BEFORE
-- INSERT trigger an OMITTED `INTEGER PRIMARY KEY` -- and an explicit NULL --
-- both present as `-1`, reproduced independently on sqlite 3.50.4. So
-- `NEW.<pk> IS NULL` is ALWAYS false: the old clause was dead text that
-- happened to work, and the moment a row at id `-1` exists it ABORTS every
-- ordinary id-omitting append. All four no-REPLACE barriers in this migration
-- use the `!= -1` form, and each ships the three-direction discriminating set
-- the ruling names -- an ordinary append SUCCEEDS, a conflicting REPLACE
-- ABORTS, an explicit conflicting id ABORTS.
--
-- THE RESIDUAL ON AN EXISTING TABLE, DECLARED: `candidates`,
-- `latch_order_intents` and `provenance_corrections` cannot carry a
-- `CHECK (pk > 0)` without a table rebuild, so on those three an EXPLICIT `-1`
-- INSERT is indistinguishable from an omitted one and would re-open exactly
-- the hazard above. INCIDENCE ZERO, established by READING each production
-- writer's column list rather than by grepping for the column name -- all
-- three omit the PK entirely, and a test reads those three lists so the
-- declaration cannot rot into prose. `latch_order_mandate_links` is NEW and
-- carries the CHECK instead.
CREATE TRIGGER trg_candidates_no_replace BEFORE INSERT ON candidates
WHEN EXISTS (SELECT 1 FROM candidates
              WHERE (evaluation_run_id = NEW.evaluation_run_id AND ticker = NEW.ticker)
                 OR (NEW.id != -1 AND id = NEW.id))
BEGIN SELECT RAISE(ABORT, '22-A barrier trg_candidates_no_replace: candidates rows are PERMANENT from migration 0037. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE) would DELETE the existing row, bypassing trg_candidates_no_delete, reusing its id and cascade-wiping candidate_criteria. A re-evaluation APPENDS a new row under a new evaluation_run_id. To retire the barrier see the reversibility header of 0037_latch_order_mandate_links.sql.'); END;

-- ============================================================================
-- 3. THE LINK: one row per BROKER-ACCEPTED latch order.
--
-- WHY A NEW TABLE AT ALL. The acceptance row in latch_order_intents genuinely
-- IS a durable order<->mandate link -- append-only, trigger-protected, carrying
-- actual_broker_order_id and candidate_id on one row. What it does NOT carry is
-- the fire's INVALIDATION, and it can never be made to: trg_loi_no_update and
-- trg_loi_no_delete ABORT every UPDATE and DELETE (0033), so a new column on
-- that table could never be back-filled for an existing acceptance. An
-- implementation built on it alone must read candidates.initial_stop live at
-- comparison time with nothing to check it against -- precisely the shape RD's
-- frozen-value gate refuses.
--
-- link_id is AUTOINCREMENT, deliberately. provenance_corrections cites it by
-- id; a bare rowid is REUSED when the row holding the maximum is deleted, and
-- an audit citation that can silently repoint at a different row is not a
-- citation (the fills.fill_id-reuse class this repo already paid for at 0036).
--
-- NO UNIQUE ON broker_order_id. A duplicate would abort the LEDGER write, and
-- cohort bookkeeping must never block a money-bearing operation (0036:26-38).
-- Cardinality is the READER's COUNT: two links sharing one broker order id
-- refuse ambiguous_accepted_orders at admission. UNIQUE(validity_intent_id) IS
-- declared -- the minting trigger fires once per validity row, so it cannot
-- conflict, and it is what makes "one link per acceptance" structural.
--
-- NO frozen_zone_cap COLUMN. The buy-zone cap is a pure function of the frozen
-- pivot (zone_cap_for_pivot), used only by the price-consistency REFUSAL guard
-- and never as evidence. Storing it would duplicate arithmetic into SQL and
-- carry a false "frozen" claim; deriving it at read time removes both.
--
-- THE FROZEN COLUMNS ARE NULLABLE, and that is the priority ruling rather than
-- laxity: candidates.pivot / initial_stop are unconstrained REAL columns, so a
-- junk fire is representable. A NOT NULL or a bare "> 0" NOT NULL here would
-- make the minting trigger ABORT the operator's acceptance record. NULL lands,
-- and admission later refuses frozen_value_unavailable.
--
-- EVERY FK IS ON DELETE RESTRICT. On a table whose UPDATE trigger aborts every
-- UPDATE, ON DELETE SET NULL is UNIMPLEMENTABLE -- the cascade IS an UPDATE
-- (0033's own lesson, inherited rather than re-derived).
-- ============================================================================
CREATE TABLE latch_order_mandate_links (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,

    validity_intent_id INTEGER NOT NULL UNIQUE
        REFERENCES latch_order_intents(intent_id) ON DELETE RESTRICT,
    place_intent_id    INTEGER NOT NULL
        REFERENCES latch_order_intents(intent_id) ON DELETE RESTRICT,
    candidate_id       INTEGER NOT NULL
        REFERENCES candidates(id) ON DELETE RESTRICT,

    -- The denormalised identity block, copied from the accepting intent. Rung
    -- 3c binds every one of these back to its authoritative source at
    -- admission, because a copy nothing checks is a forgery surface: a RAW link
    -- could cite a GENUINE accepted validity row while substituting a different
    -- broker order id or an inflated quantity.
    evaluation_run_id  INTEGER NOT NULL,
    ticker             TEXT    NOT NULL,
    detection_date     TEXT    NOT NULL,
    broker_order_id    TEXT    NOT NULL,

    frozen_pivot        REAL,
    frozen_invalidation REAL,
    actual_quantity     INTEGER,

    -- TWO-VALUED under single-state. gap_era_reconstructed and the era model it
    -- names are CARVED to 22-A2, so a pre-barrier reconstruction can never be
    -- read as a post-barrier freeze and there is no third state to confuse with
    -- either. Mirrored by LATCH_FREEZE_TIERS in swing/trades/latched_origin.py,
    -- and a drift test asserts the two spellings hold the same values (#11 --
    -- the comparator is the only mirror that defends the set).
    freeze_tier TEXT NOT NULL
        CHECK (freeze_tier IN ('live_at_acceptance', 'pre_barrier_reconstructed')),

    linked_at TEXT NOT NULL,

    CHECK (frozen_pivot        IS NULL OR frozen_pivot        > 0),
    CHECK (frozen_invalidation IS NULL OR frozen_invalidation > 0),
    CHECK (actual_quantity     IS NULL OR actual_quantity     > 0),
    CHECK (length(trim(ticker)) > 0),
    CHECK (length(trim(broker_order_id)) > 0),
    -- THE SENTINEL IS UNAMBIGUOUS ON THIS TABLE FOREVER (CHARC-ruled
    -- 2026-08-26, on 22A-R8-02). An OMITTED INTEGER PRIMARY KEY presents as
    -- `-1` in a BEFORE INSERT trigger, not NULL -- reproduced independently on
    -- sqlite 3.50.4 -- which is why `trg_loml_no_replace` spells its PK
    -- conflict clause `NEW.link_id != -1 AND link_id = NEW.link_id`. This
    -- CHECK runs on the STORED value AFTER assignment, so an omitted id
    -- (assigned a positive AUTOINCREMENT rowid) passes while a negative id can
    -- never exist, and the barrier's sentinel can therefore never collide with
    -- a real row. A NEW table can carry this; an EXISTING one cannot without a
    -- table rebuild, which is why the three existing tables declare the
    -- residual instead (see the no-REPLACE barriers above and their tests).
    CHECK (link_id > 0),
    CHECK (evaluation_run_id > 0),
    -- The three-predicate date guard, per 0033's own lesson: length, parseable,
    -- and round-trips. date('2026-08-32') is NULL; date('2026-8-1') parses but
    -- does NOT round-trip; a bare length check accepts both.
    CHECK (COALESCE(length(detection_date) = 10
           AND date(detection_date) IS NOT NULL
           AND date(detection_date) = detection_date
           AND CAST(substr(detection_date, 1, 4) AS INTEGER) BETWEEN 1 AND 9999, 0))
);

CREATE INDEX ix_loml_broker_order_id ON latch_order_mandate_links(broker_order_id);
CREATE INDEX ix_loml_candidate_id    ON latch_order_mandate_links(candidate_id);
CREATE INDEX ix_loml_ticker          ON latch_order_mandate_links(ticker);

CREATE TRIGGER trg_loml_no_update BEFORE UPDATE ON latch_order_mandate_links
BEGIN SELECT RAISE(ABORT, '22-A barrier trg_loml_no_update: latch_order_mandate_links is append-only. A link records what the broker accepted at one instant; editing it would rewrite the frozen values the admission proof rests on. To retire the barrier see the reversibility header of 0037_latch_order_mandate_links.sql.'); END;

CREATE TRIGGER trg_loml_no_delete BEFORE DELETE ON latch_order_mandate_links
BEGIN SELECT RAISE(ABORT, '22-A barrier trg_loml_no_delete: latch_order_mandate_links is append-only. Deleting a link would erase the only durable record binding a broker order to its mandate. To retire the barrier see the reversibility header of 0037_latch_order_mandate_links.sql.'); END;

-- AND THE CONFLICT-SCOPED INSERT THAT CLOSES REPLACE, on the arc's OWN table
-- (Codex 22A-R3-03/R3-10, VERIFIED BY EXECUTION 2026-08-25). This migration
-- repairs the REPLACE bypass carefully for `candidates` and for the epoch and
-- LEFT ITS OWN LINK TABLE OPEN: at the default `recursive_triggers=0` an
-- INSERT OR REPLACE deletes the conflicting row WITHOUT firing
-- trg_loml_no_delete, then inserts a new one -- measured, rewriting
-- frozen_pivot 18.34 -> 999.99 with both append-only triggers present and
-- unfired. The durable order<->mandate record is the thing the whole admission
-- proof rests on, so an append-only claim it does not have is worse here than
-- anywhere else in the file.
--
-- BOTH UNIQUE KEYS ARE SCOPED: the PRIMARY KEY and the UNIQUE on
-- validity_intent_id. Guarding only one leaves the other as a live REPLACE
-- path, which is the same half-swept shape as the bypass itself.
CREATE TRIGGER trg_loml_no_replace BEFORE INSERT ON latch_order_mandate_links
WHEN EXISTS (SELECT 1 FROM latch_order_mandate_links
              WHERE (NEW.link_id != -1 AND link_id = NEW.link_id)
                 OR validity_intent_id = NEW.validity_intent_id)
BEGIN SELECT RAISE(ABORT, '22-A barrier trg_loml_no_replace: latch_order_mandate_links is append-only. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE) would DELETE the existing link, bypassing trg_loml_no_delete, and rewrite the frozen values the admission proof rests on. One acceptance mints one link and it is never replaced. To retire the barrier see the reversibility header of 0037_latch_order_mandate_links.sql.'); END;


-- ============================================================================
-- 3b. THE REPLACE BYPASS ON latch_order_intents -- the LEDGER the minting
--     trigger fires from (Codex 22A-R3-11's sibling; the probe CHARC directed,
--     VERIFIED BY EXECUTION 2026-08-25).
--
-- 0033 gives this table trg_loi_no_update and trg_loi_no_delete and NO
-- no_replace, which is the same shape this migration already repaired one
-- table over. It matters more here than anywhere else in the file: the
-- acceptance row IS what the minting trigger fires from and what a link's
-- evidence cites, so 22-A's whole admission proof rests on it.
--
-- MEASURED at production settings (recursive_triggers default OFF), on a
-- `place` intent with NO minted link:
--
--   control UPDATE / DELETE          -> BLOCKED by 0033's two triggers
--   INSERT OR REPLACE on the rowid PK-> SUCCEEDS: framework_limit_price
--                                       rewritten 18.89 -> 999.99
--   REPLACE on UNIQUE(idempotency_key)
--                                    -> SUCCEEDS and MOVES intent_id 1 -> 2
--
-- both barrier triggers present, canonical, and UNFIRED.
--
-- ONE THING INCIDENTALLY PROTECTS THE WRONG HALF, exactly as it does for
-- `candidates`, and it must not be mistaken for a defence: once a link cites a
-- row, latch_order_mandate_links' ON DELETE RESTRICT FKs block both REPLACE
-- paths. So the FK covers the POST-acceptance population -- and leaves every
-- `place` intent BEFORE its acceptance fully exposed. That is the window that
-- matters, because the place row carries the framework's own prepared-order
-- derivation and the validity row's parent pointer, and THREE of the five live
-- intent rows are unlinked `place` rows.
--
-- BOTH CONFLICT TARGETS ARE SCOPED -- the rowid PK and UNIQUE(idempotency_key).
-- Guarding one leaves the other live, which is the half-swept shape of the
-- bypass itself.
--
-- THE PRODUCTION WRITER NEEDED A COMPANION CHANGE, and this is the ONE place
-- this barrier differs from `candidates`. record_intent (swing/data/repos/
-- latch_order_intents.py) issued
-- "INSERT ... VALUES (...) ON CONFLICT(idempotency_key) DO NOTHING" -- the
-- INSERT-time no-op that covers its documented LOST RACE, pinned by
-- test_a_lost_race_returns_the_winners_row_without_an_integrity_error.
-- MEASURED: a conflict-scoped BEFORE INSERT trigger ABORTS that statement,
-- because a BEFORE INSERT trigger fires BEFORE conflict resolution and SQLite
-- offers NO way for it to see which resolution algorithm the statement carries
-- -- so it cannot distinguish DO NOTHING (which deletes nothing) from REPLACE
-- (which deletes the conflicting row). On `candidates` this never arose:
-- insert_candidates issues a plain INSERT.
--
-- THE REPAIR IS IN THE WRITER, NOT IN THE BARRIER, so the barrier stays
-- blanket over BOTH conflict targets rather than being narrowed to fit.
-- record_intent's step 2 now reads
--
--   INSERT INTO latch_order_intents (...) SELECT ?,?,...
--    WHERE NOT EXISTS (SELECT 1 FROM latch_order_intents
--                       WHERE idempotency_key = ?)
--      ON CONFLICT(idempotency_key) DO NOTHING
--
-- so the lost-race path inserts ZERO ROWS instead of presenting a conflict:
-- the barrier is never reached and step 3's re-SELECT returns the winner's row
-- exactly as before. The ON CONFLICT clause is RETAINED, not replaced. BOTH
-- pre-existing repo tests -- the lost-race contract and the trace-callback pin
-- asserting the executed SQL still carries ON CONFLICT(idempotency_key) DO
-- NOTHING and no OR REPLACE -- pass UNMODIFIED, which is the evidence that the
-- observable contract did not move. A narrower barrier was the alternative and
-- was REJECTED: it would have had to leave one of the two conflict targets
-- live, and UNIQUE(idempotency_key) is the target measured to MOVE intent_id.
-- ============================================================================
CREATE TRIGGER trg_loi_no_replace BEFORE INSERT ON latch_order_intents
WHEN EXISTS (SELECT 1 FROM latch_order_intents
              WHERE (NEW.intent_id != -1 AND intent_id = NEW.intent_id)
                 OR idempotency_key = NEW.idempotency_key)
BEGIN SELECT RAISE(ABORT, '22-A barrier trg_loi_no_replace: latch_order_intents is append-only. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE / ON CONFLICT DO NOTHING) would DELETE the existing intent, bypassing trg_loi_no_delete at the default PRAGMA recursive_triggers=OFF, reusing its intent_id and rewriting the ledger row the minting trigger fires from and the link evidence cites. A correction is a NEW row under a NEW idempotency_key; a replay is answered by record_intent SELECT-first. To retire the barrier see the reversibility header of 0037_latch_order_mandate_links.sql.'); END;

-- ============================================================================
-- 3d. THE STORED CANONICAL READING OF A FILL'S ENVELOPE -- PERSIST-CANONICAL.
--
-- THE RULING THIS TABLE EXISTS TO ENCODE (CHARC 2026-08-26, adopting RD's
-- sentence verbatim):
--
--     SQL VERIFIES A FACT; IT MUST NEVER RE-DERIVE A JUDGMENT ACROSS AN ENGINE
--     BOUNDARY -- the twin mirrors the AUTHORITY by consuming its OUTPUT, not
--     by reimplementing its reasoning.
--
-- WHAT IT REPLACES, AND WHY THE REPLACEMENT IS STRUCTURAL RATHER THAN ANOTHER
-- FIX. Ten review rounds ran without converging, and three CONSECUTIVE rounds
-- each produced a DISTINCT engine-semantic divergence -- every one real, every
-- one found only after the previous had been fixed:
--
--   NaN inside a document   python json.loads ACCEPTS  |  sqlite json_valid REJECTS
--   trim/strip ASCII space  both strip                 |  AGREE
--   trim/strip tab/NL/NBSP  python strips              |  sqlite does NOT
--   1002937461 == '..'      python False               |  SQL (TEXT affinity) True
--
-- Zero findings were ever reopened, so this was not careless execution: it is a
-- structural property of mirroring a nontrivial predicate across two engines
-- that disagree in at least three independent ways, and nothing said three was
-- the last. So the mirror is REMOVED. The SERVICE canonicalises a fill's
-- envelope ONCE, PERSISTS its reading here, and every SQL site downstream
-- compares a STORED VALUE instead of parsing the document again.
--
-- envelope_raw IS THE BINDING, AND IT IS THE REASON THIS IS A FACT CHECK.
-- The row records WHICH DOCUMENT was judged, verbatim. Every consumer joins on
-- `fei.envelope_raw = fills.schwab_source_value_json` -- a plain TEXT equality,
-- no parsing, no normalisation, no coercion -- so a reading whose document
-- later changed simply stops matching and the surface fails CLOSED. That is
-- what lets a trigger consume a judgment it is forbidden to make.
--
-- TWO STATES, NOT THREE. 'canonical' means the authority read the document and
-- these are its values (either may be NULL: a well-formed envelope naming no
-- order is canonical and names nothing). 'refused' means the authority could
-- NOT read it to a single unambiguous value. A fill whose envelope is NULL has
-- NO ROW AT ALL and needs none -- `schwab_source_value_json IS NULL` is itself
-- a fact, and it is how every pre-22-A fill passes.
--
-- NO BACKFILL, DELIBERATELY, and this is the load-bearing consequence of the
-- ruling. A SQL backfill would have to decide, in SQL, what each existing
-- envelope says -- which is the re-derivation this table exists to delete,
-- merely moved from verification time to migration time. So the migration
-- creates the table EMPTY and the SERVICE fills it: existing fills are
-- canonicalised on demand by the one authority, inside the same write
-- reservation that consumes the result. CONDITION 4 is satisfied exactly as
-- section 3's own backfill satisfies it -- nothing rebuilt, nothing dropped,
-- NO EXISTING ROW TOUCHED.
--
-- WHAT THIS TABLE CANNOT DO, declared here rather than discovered later: a raw
-- writer that stores an identity row AND a citation that AGREE WITH EACH OTHER
-- but disagree with the envelope passes every check below. That is the SAME
-- trust boundary as before -- the trigger never could judge truth, only
-- CONSISTENCY -- and stating it is the condition on which the reshape was
-- ruled. See section 6's limitations block for the full statement.
--
-- identity_id is a plain INTEGER PRIMARY KEY (a rowid alias): nothing cites an
-- identity row by id, so the AUTOINCREMENT reuse hazard the link table pays
-- for does not apply here. UNIQUE(fill_id, envelope_raw) is the key every
-- consumer addresses, and it is what makes the lookup single-valued.
-- ============================================================================
CREATE TABLE fill_envelope_identity (
    -- CHECK (identity_id > 0) IS THE OTHER HALF OF THE SENTINEL CONTRACT, and
    -- it was MISSING here while the link table carried it (Codex 22A-R11-06).
    -- REPRODUCED on sqlite 3.50.4 at the default recursive_triggers=0: insert
    -- a row explicitly at -1, then INSERT OR REPLACE a -1 row with a DIFFERENT
    -- (fill_id, envelope_raw); the first row was SILENTLY DELETED and
    -- replaced, trg_fei_no_delete never fired, and this table's append-only
    -- guarantee -- the whole reason a stored reading can be trusted -- was
    -- false. The barrier below must ignore NEW.identity_id = -1 because an
    -- OMITTED integer primary key presents as -1 rather than NULL, so the
    -- sentinel has to be impossible as a STORED value. A NEW table can
    -- guarantee that with a CHECK; the three EXISTING tables cannot without a
    -- rebuild this convention forbids, which is why they DECLARE the residual
    -- and every NEW table closes it by construction. A test walks both new
    -- tables rather than the one that happened to be remembered.
    identity_id INTEGER PRIMARY KEY CHECK (identity_id > 0),

    -- NO FOREIGN KEY ON fill_id, AND THAT IS MEASURED RATHER THAN CASUAL.
    -- `split_into_partials` DELETEs the consolidated fill and rebuilds it as
    -- partials (reconciliation_auto_correct.py:2966), and task 11a now
    -- PRESERVES the envelope onto the rebuilt rows -- so an envelope-bearing
    -- fill genuinely does get deleted on a supported operational path. All
    -- THREE delete actions block it, verified by execution on sqlite 3.50.4 at
    -- the default PRAGMA recursive_triggers=0: RESTRICT and NO ACTION raise
    -- `FOREIGN KEY constraint failed`, and CASCADE DOES fire this table's own
    -- BEFORE DELETE trigger and aborts with the append-only message. A
    -- reference of any kind would therefore convert a legitimate reconciliation
    -- into a hard failure -- cohort bookkeeping blocking an operational
    -- correction, which 0036:26-38 already ruled against.
    --
    -- THE ORPHAN IT PERMITS IS HARMLESS BY CONSTRUCTION, and the reason is the
    -- same reason envelope_raw exists. fills.fill_id is a plain rowid alias and
    -- IS reused; a stale reading whose fill was deleted can therefore be
    -- addressed again. But every consumer joins on BOTH fill_id AND
    -- envelope_raw, so a reused id carrying a DIFFERENT document does not match
    -- at all, and a reused id carrying the SAME document is the same document,
    -- for which the stale reading is the correct reading. The only way the two
    -- could differ is a canonicaliser change, and record_identity RAISES on
    -- exactly that rather than preferring either answer.
    fill_id      INTEGER NOT NULL,
    envelope_raw TEXT    NOT NULL,

    envelope_state TEXT NOT NULL
        CHECK (envelope_state IN ('canonical', 'refused')),

    broker_order_id   TEXT,
    instrument_symbol TEXT,

    canonicalizer_version TEXT NOT NULL,
    recorded_ts           TEXT NOT NULL,

    -- A REFUSAL CARRIES NO IDENTITY. Without this a raw writer could record
    -- "the authority refused this document" and simultaneously hand the
    -- trigger an order id to compare against -- a refusal that still admits.
    CHECK (envelope_state = 'canonical'
           OR (broker_order_id IS NULL AND instrument_symbol IS NULL)),
    -- A STORED IDENTITY IS PRESENT OR ABSENT, never blank. `length(x) > 0` is
    -- a fact about the stored string and NOT a normalisation: it does not
    -- trim, fold or coerce anything, so it cannot disagree with Python.
    CHECK (broker_order_id   IS NULL OR length(broker_order_id)   > 0),
    CHECK (instrument_symbol IS NULL OR length(instrument_symbol) > 0),

    UNIQUE (fill_id, envelope_raw)
);

CREATE INDEX ix_fei_broker_order_id ON fill_envelope_identity(broker_order_id);

CREATE TRIGGER trg_fei_no_update BEFORE UPDATE ON fill_envelope_identity
BEGIN SELECT RAISE(ABORT, '22-A barrier trg_fei_no_update: fill_envelope_identity is append-only. A row records what the authority read out of ONE document at one instant; editing it would silently re-point every citation that compares against it. A new document is a NEW row. To retire the barrier see the reversibility header of 0037_latch_order_mandate_links.sql.'); END;

CREATE TRIGGER trg_fei_no_delete BEFORE DELETE ON fill_envelope_identity
BEGIN SELECT RAISE(ABORT, '22-A barrier trg_fei_no_delete: fill_envelope_identity is append-only. Deleting a reading would erase the only record of what the authority read, and every consumer would then fail closed with no way to tell erasure from absence. To retire the barrier see the reversibility header of 0037_latch_order_mandate_links.sql.'); END;

-- THE CONFLICT-SCOPED INSERT BARRIER, for the reason measured three times in
-- this same file: at the default PRAGMA recursive_triggers=OFF an
-- INSERT OR REPLACE DELETES the conflicting row WITHOUT firing the DELETE
-- trigger. Both unique keys are scoped -- the rowid PK and UNIQUE(fill_id,
-- envelope_raw) -- because guarding one leaves the other live, which is the
-- same half-swept shape as the bypass itself. The `!= -1` spelling is the
-- CHARC-ruled sentinel contract: an OMITTED INTEGER PRIMARY KEY presents as
-- -1 in a BEFORE INSERT trigger, not NULL (reproduced on sqlite 3.50.4).
-- The ignore is only SAFE because the table's CHECK (identity_id > 0) makes a
-- stored -1 impossible; without it the sentinel collides with a real row and
-- the barrier can be walked straight past (Codex 22A-R11-06, measured).
CREATE TRIGGER trg_fei_no_replace BEFORE INSERT ON fill_envelope_identity
WHEN EXISTS (SELECT 1 FROM fill_envelope_identity
              WHERE (NEW.identity_id != -1 AND identity_id = NEW.identity_id)
                 OR (fill_id = NEW.fill_id
                     AND envelope_raw = NEW.envelope_raw))
BEGIN SELECT RAISE(ABORT, '22-A barrier trg_fei_no_replace: fill_envelope_identity is append-only. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE) would DELETE the existing reading, bypassing trg_fei_no_delete at the default PRAGMA recursive_triggers=OFF, and substitute a different identity for the same document -- which is exactly the forgery the stored reading exists to make impossible. To retire the barrier see the reversibility header of 0037_latch_order_mandate_links.sql.'); END;


-- ============================================================================
-- 4. THE MINTING TRIGGER, and the BACKFILL.
--
-- A TRIGGER, NOT A SERVICE HOOK. A hook in record_intent or in the route is
-- skippable and invisible to a raw INSERT -- the D36 shape. A trigger cannot be
-- bypassed by any writer.
--
-- IT MUST BE INCAPABLE OF RAISING. Each copied value is guarded AT THE SOURCE
-- by a CASE, so a junk fire lands NULL frozen values rather than aborting the
-- operator's acceptance record.
--
-- THE TIER IS DERIVED, NEVER HARD-CODED (review 22A-R7-03). The specification
-- for this trigger once read freeze_tier='live_at_acceptance' unconditionally,
-- which would have given a POST-migration acceptance of a PRE-migration fire a
-- false structural-proof label -- the exact defect the epoch exists to prevent,
-- written into the epoch's own migration. It was the TWELFTH mirror site of the
-- freeze-tier family and an eleven-site sweep could not have found it, because
-- that sweep looked for the enum's VALUE SET and this line hard-coded ONE
-- MEMBER of it. A value-set sweep does not find a hard-coded single member.
-- The CASE below and the one in the backfill are the SQL twin of
-- freeze_tier_for_candidate; a test runs both spellings over the same fixtures.
-- ============================================================================
CREATE TRIGGER trg_latch_link_mint_on_acceptance
AFTER INSERT ON latch_order_intents
FOR EACH ROW WHEN NEW.intent_kind = 'validity'
             AND NEW.validity_outcome = 'accepted_by_broker'
             AND NEW.actual_broker_order_id IS NOT NULL
BEGIN
    INSERT INTO latch_order_mandate_links (
        validity_intent_id, place_intent_id, candidate_id, evaluation_run_id,
        ticker, detection_date, broker_order_id,
        frozen_pivot, frozen_invalidation, actual_quantity,
        freeze_tier, linked_at)
    SELECT NEW.intent_id,
           NEW.validated_place_intent_id,
           NEW.candidate_id,
           NEW.evaluation_run_id,
           NEW.ticker,
           NEW.detection_date,
           NEW.actual_broker_order_id,
           CASE WHEN typeof(c.pivot) = 'real' AND c.pivot > 0
                THEN c.pivot ELSE NULL END,
           CASE WHEN typeof(c.initial_stop) = 'real' AND c.initial_stop > 0
                THEN c.initial_stop ELSE NULL END,
           NEW.actual_quantity,
           CASE WHEN c.id > (SELECT max_candidate_id_at_barrier
                               FROM candidates_immutability_epoch
                              WHERE epoch_id = 1)
                THEN 'live_at_acceptance' ELSE 'pre_barrier_reconstructed' END,
           strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
      FROM candidates c
     WHERE c.id = NEW.candidate_id;
END;

-- THE BACKFILL is a GENERAL statement over the ledger, never a hand-written
-- row, and it derives the tier through the SAME CASE rather than stating a
-- constant -- the second single-member site the corrected sweep found. Its
-- expected result on the live database today is exactly ONE row at
-- pre_barrier_reconstructed, and the test asserts that as an OUTCOME of the
-- derivation rather than as an input to it: the epoch was seeded from
-- MAX(candidates.id) moments ago, so every candidate that exists is at-or-below
-- the boundary and no backfilled link can be post-barrier.
INSERT INTO latch_order_mandate_links (
    validity_intent_id, place_intent_id, candidate_id, evaluation_run_id,
    ticker, detection_date, broker_order_id,
    frozen_pivot, frozen_invalidation, actual_quantity,
    freeze_tier, linked_at)
SELECT v.intent_id,
       v.validated_place_intent_id,
       v.candidate_id,
       v.evaluation_run_id,
       v.ticker,
       v.detection_date,
       v.actual_broker_order_id,
       CASE WHEN typeof(c.pivot) = 'real' AND c.pivot > 0
            THEN c.pivot ELSE NULL END,
       CASE WHEN typeof(c.initial_stop) = 'real' AND c.initial_stop > 0
            THEN c.initial_stop ELSE NULL END,
       v.actual_quantity,
       CASE WHEN c.id > (SELECT max_candidate_id_at_barrier
                           FROM candidates_immutability_epoch
                          WHERE epoch_id = 1)
            THEN 'live_at_acceptance' ELSE 'pre_barrier_reconstructed' END,
       strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
  FROM latch_order_intents v
  JOIN candidates c ON c.id = v.candidate_id
 WHERE v.intent_kind = 'validity'
   AND v.validity_outcome = 'accepted_by_broker'
   AND v.actual_broker_order_id IS NOT NULL
   AND v.validated_place_intent_id IS NOT NULL;

-- ============================================================================
-- 5. THE CORRECTION SURFACE LEARNS THE LATCH LADDER -- SIX ADD COLUMNs.
--
-- admission_tier takes a CONSTANT default, so NOT NULL DEFAULT is legal and the
-- existing CADL row becomes 'last_word' -- which is true of it. The five
-- citation columns default NULL, as SQLite requires for an added FK column.
--
-- The tier enum is TWO-VALUED in this arc; latch_ladder_tier2 arrives with
-- 22-A2 and the tier-2 evidence class it belongs to. A column-level CHECK IS
-- accepted and ENFORCED by ALTER TABLE ADD COLUMN on the installed SQLite
-- (3.50.4) -- verified at the prompt before this was written, per 0036's
-- four-CHECK-semantics-surprises lesson -- so the SQL half of the enum mirror
-- lives here and PROVENANCE_ADMISSION_TIERS mirrors it (#11).
-- ============================================================================
ALTER TABLE provenance_corrections ADD COLUMN admission_tier TEXT NOT NULL
    DEFAULT 'last_word' CHECK (admission_tier IN ('last_word', 'latch_ladder'));
ALTER TABLE provenance_corrections ADD COLUMN cited_latch_link_id INTEGER
    REFERENCES latch_order_mandate_links(link_id) ON DELETE RESTRICT;
ALTER TABLE provenance_corrections ADD COLUMN cited_latch_validity_intent_id INTEGER
    REFERENCES latch_order_intents(intent_id) ON DELETE RESTRICT;
ALTER TABLE provenance_corrections ADD COLUMN cited_latch_place_intent_id INTEGER
    REFERENCES latch_order_intents(intent_id) ON DELETE RESTRICT;
ALTER TABLE provenance_corrections ADD COLUMN cited_latch_broker_order_id TEXT;
ALTER TABLE provenance_corrections ADD COLUMN cited_latch_probe_json TEXT;

-- ============================================================================
-- 6. THE CITATION GRAPH, RE-CREATED (CONDITION-4 EXCEPTION 2).
--
-- The EIGHT relations 0036 established are carried VERBATIM. What is added is
-- the tier / paired-NULL rule and, under 'latch_ladder', the latch citation's
-- own structural bindings plus a VERSIONED, CLOSED evidence schema.
--
-- WHY A TRIGGER RATHER THAN TABLE-LEVEL CHECKs. ALTER TABLE ADD COLUMN cannot
-- add a TABLE-level CHECK, and the paired-NULL rule is cross-column; the
-- bindings are cross-TABLE, which no CHECK can express (subqueries are
-- prohibited in CHECK constraints and permitted in a trigger WHEN clause --
-- verified). The only alternative is rebuilding the audit table of record.
--
-- THE COALESCE WRAPPER ON THE LATCH BLOCK IS LOAD-BEARING, AND MEASURED. In a
-- trigger's WHEN NOT (...) clause a single NULL conjunct makes the WHOLE
-- predicate NULL, and a NULL WHEN DOES NOT FIRE THE TRIGGER -- so an evidence
-- blob with a MISSING required key silently passes: json_type(blob,'$.absent')
-- is NULL, NULL = 'text' is NULL, and the row is accepted. Verified by
-- execution on 3.50.4: without COALESCE a blob omitting a required key is
-- ACCEPTED; with COALESCE(..., 0) it is REJECTED. 0036's own CHECKs use the
-- same idiom for the same reason; this is that trap arriving one layer up, in
-- the construct whose failure mode is silence rather than an error.
--
-- WHAT THIS TRIGGER CLAIMS, NARROWED TO WHAT IT CAN ESTABLISH. Four limits,
-- stated here rather than only in the plan (the fourth is the PERSIST-CANONICAL
-- declaration and it is stated FIRST because it is the widest):
--   (0) IT CANNOT JUDGE A FILL'S ENVELOPE AT ALL. It verifies that the
--       AUTHORITY'S STORED READING and the row's CITATION agree, and nothing
--       more. A RAW WRITER THAT STORES TWO EQUAL-BUT-WRONG VALUES -- a forged
--       fill_envelope_identity row plus a citation matching it -- PASSES THE
--       EQUALITY CHECK. Declared at the reshape as a condition of the ruling,
--       CHARC + RD 2026-08-26, rather than discovered later.
--
--       AND IT IS THE SAME TRUST BOUNDARY AS BEFORE, which is why the loss is
--       acceptable rather than merely accepted: the clause this replaced could
--       equally be satisfied by a FORGED ENVELOPE -- a clean, canonical
--       document naming an order the fill never came from passed every one of
--       its checks. The trigger never could judge TRUTH, only CONSISTENCY.
--       What changed is which two artefacts must agree.
--
--       WHAT IT STILL CATCHES: a citation naming a different order than the
--       stored reading; a reading the authority REFUSED; a document the
--       authority has NOT read (the raw writer's own shape); and a document
--       that CHANGED after its reading was taken, because the join is on the
--       fill AND the document. The acceptance is PINNED by
--       test_THE_DECLARED_LIMITATION_two_equal_but_wrong_values_are_ACCEPTED;
--       if that ever starts REJECTING, correct this declaration rather than
--       silencing the test.
--
--       There is no SQL fix, by construction. The only instrument that could
--       close it is an AUTHENTICATED envelope (a server-side nonce or a
--       POST-time broker re-fetch), which is the same V2 fix limitation L10
--       already names for the document itself.
--
--   (1) Element-wise equality of expected_sessions and observed_sessions proves
--       the two arrays agree with EACH OTHER, not with the NYSE calendar or
--       with the archive. Two identical fabricated arrays pass -- including two
--       EMPTY arrays for a non-empty window. A trigger cannot enumerate a
--       session calendar. The coverage FACT is established by the service.
--   (2) json_remove(<obj>, <every allowed key>) = '{}' rejects EXTRA keys but
--       does NOT establish that every REQUIRED key exists, because SQLite
--       renders both a missing path and a JSON null as SQL NULL. Every required
--       field therefore ALSO carries a positive json_type assertion, under the
--       COALESCE wrapper above.
--   (3) bars_through is deliberately NOT SQL-bound: a trigger cannot walk an
--       exchange calendar, and pretending otherwise is how horizon_session and
--       bars_through were once collapsed into one field with two incompatible
--       definitions. It is presence- and type-checked here and validated in the
--       service. Stated so the next reader finds a decision rather than a gap.
--
-- THE SINGLE ROUNDING AUTHORITY (RD's ruled principle). Python rounds
-- half-to-EVEN and SQLite rounds half-AWAY-from-zero; they disagree on exactly
-- the eighth-dollar values (.125 / .625), and 24 live candidates rows sit on
-- that family. So the blob carries the RAW operands, each bound by a plain =
-- against its SOURCE column -- an IDENTITY check, same value and same domain,
-- no rounding, no cross-domain comparison -- and the SERVICE'S VERDICT travels
-- as a datum (invalidation_equal_at_dp / pivot_equal_at_dp, with compare_dp
-- binding the precision the service used, so a later PRICE_DP change cannot
-- silently re-interpret an old row). SQL NEVER rounds and NEVER compares two
-- independently-sourced prices to each other. The residual is declared: SQL
-- cannot verify that the recorded verdict is the CORRECT rounding of the two
-- raw operands. That is strictly smaller than what a raw-equality clause
-- exposed -- both raws stay bound to the cited link and the cited candidate, so
-- a forger cannot name a different mandate -- and it is the unavoidable price
-- of the rule, because ANY SQL-side recomputation re-creates the cross-domain
-- comparison the rule exists to forbid.
--
-- THE $.authorization ROSTER IS THE MACHINE-READABLE SOURCE OF TRUTH. The
-- json_remove path list below is the closure list; AUTHORIZATION_CLAUSES in
-- swing/trades/latched_origin.py mirrors it, and a test parses the path list
-- out of THIS FILE and asserts exact set equality with that roster -- the
-- 0033 LATCH_BROKER_SNAPSHOT_KEYS precedent, so neither is a hand-maintained
-- copy of the other. SIXTEEN entries: the ELEVEN ladder rungs plus the FIVE
-- envelope guards enumerated SEPARATELY, because one lumped envelope_guards
-- entry cannot distinguish "all five passed" from "one ran and four never did".
-- ============================================================================
DROP TRIGGER trg_provenance_corrections_citation_graph;

CREATE TRIGGER trg_provenance_corrections_citation_graph
BEFORE INSERT ON provenance_corrections
FOR EACH ROW WHEN NOT (
    -- the cited candidate belongs to the cited run, and is an aplus row
    EXISTS (SELECT 1 FROM candidates ca
            WHERE ca.id = NEW.cited_candidate_id
              AND ca.evaluation_run_id = NEW.cited_evaluation_run_id
              AND ca.bucket = 'aplus')
    -- the frozen run anchors ARE that run's own columns
    AND EXISTS (SELECT 1 FROM evaluation_runs er
                WHERE er.id = NEW.cited_evaluation_run_id
                  AND er.run_ts = NEW.cited_run_ts_raw
                  AND er.action_session_date
                      = NEW.cited_candidate_action_session_date)
    -- the cited recommendation belongs to the same run and the same ticker,
    -- is a today_decision, and carries the frozen anchor
    AND EXISTS (SELECT 1 FROM daily_recommendations dr
                WHERE dr.id = NEW.cited_daily_recommendation_id
                  AND dr.evaluation_run_id = NEW.cited_evaluation_run_id
                  AND dr.recommendation = 'today_decision'
                  AND dr.action_session_date
                      = NEW.cited_recommendation_action_session_date
                  AND dr.ticker = (SELECT ca.ticker FROM candidates ca
                                   WHERE ca.id = NEW.cited_candidate_id))
    -- the cited pipeline row OWNS that run, is complete, and supplied the bound
    AND EXISTS (SELECT 1 FROM pipeline_runs pr
                WHERE pr.id = NEW.cited_pipeline_run_id
                  AND pr.evaluation_run_id = NEW.cited_evaluation_run_id
                  AND pr.state = 'complete'
                  AND pr.finished_ts = NEW.cited_pipeline_finished_ts_raw)
    -- the cited interval belongs to the cited hypothesis and IS what was frozen
    AND EXISTS (SELECT 1 FROM hypothesis_status_history h
                WHERE h.history_id = NEW.cited_hypothesis_status_history_id
                  AND h.hypothesis_id = NEW.cited_hypothesis_id
                  AND h.status = NEW.cited_hypothesis_status_at_record
                  AND h.effective_from
                      = NEW.cited_hypothesis_status_effective_from
                  AND h.effective_to
                      IS NEW.cited_hypothesis_status_effective_to
                  AND h.recorded_at
                      = NEW.cited_hypothesis_status_recorded_at)
    -- the frozen NAME is that hypothesis's name as spelled right now
    AND EXISTS (SELECT 1 FROM hypothesis_registry hr
                WHERE hr.id = NEW.cited_hypothesis_id
                  AND hr.name = NEW.cited_hypothesis_name_at_correction)
    -- the anchoring fill is an ENTRY fill of THIS trade on the frozen session
    AND EXISTS (SELECT 1 FROM fills f
                WHERE f.fill_id = NEW.entry_fill_id_at_correction
                  AND f.trade_id = NEW.trade_id
                  AND f.action = 'entry'
                  AND substr(f.fill_datetime, 1, 10)
                      = NEW.entry_fill_session_date)
    -- and the trade and the cited candidate are the same instrument
    AND EXISTS (SELECT 1 FROM trades t
                WHERE t.id = NEW.trade_id
                  AND t.ticker = (SELECT ca.ticker FROM candidates ca
                                  WHERE ca.id = NEW.cited_candidate_id))

    -- ========== THE SUBJECT FILL'S ENVELOPE HAS BEEN READ BY THE AUTHORITY,
    -- AND THIS CLAUSE ASKS ONLY THAT (PERSIST-CANONICAL, CHARC + RD
    -- 2026-08-26; it REPLACES the canonicality twin of 22A-R9-03/SS-4).
    --
    -- WHAT THE TWIN USED TO DO, AND WHY IT COULD NOT BE MADE TO WORK. It
    -- re-implemented `envelope_is_canonical` in SQL -- json_valid, json_type,
    -- json_each duplicate-counting, trim(), a type roster -- so that a RAW
    -- correction could not pick an authority SQLite reads differently from
    -- the service. It was correct in intent and structurally unfinishable:
    -- three consecutive review rounds each found a NEW way the two engines
    -- disagree (NaN documents, tab/newline/NBSP whitespace, integer-vs-TEXT
    -- affinity), every one real, every one invisible until the previous was
    -- fixed. RD's sentence, adopted by CHARC as the convention: SQL VERIFIES
    -- A FACT; IT MUST NEVER RE-DERIVE A JUDGMENT ACROSS AN ENGINE BOUNDARY.
    --
    -- SO THE CLAUSE NOW ASKS A FACT. Either the fill carries NO envelope --
    -- `IS NULL` is a fact, not a reading -- or the authority has read the
    -- EXACT document on the fill and did not refuse it. Nothing here parses,
    -- normalises or coerces anything.
    --
    -- `fei.envelope_raw = f.schwab_source_value_json` IS THE LOAD-BEARING
    -- HALF. It binds the stored reading to the document it was read from, so
    -- a reading whose document later changed stops matching and this clause
    -- fails CLOSED. Without it the stored value would be a floating claim
    -- about a fill rather than a statement about a document.
    --
    -- ABSENT ENVELOPES STILL PASS, and that is still the ordinary case: every
    -- pre-22-A fill is in exactly that state and the `last_word` ladder this
    -- surface was built for depends on it. What changed is that an envelope
    -- the authority REFUSED, or one it has never seen, no longer passes --
    -- previously an unreadable document passed on the ground that both
    -- domains read absence, which was true only while SQL was still reading.
    AND (
        (SELECT f.schwab_source_value_json FROM fills f
          WHERE f.fill_id = NEW.entry_fill_id_at_correction) IS NULL
        OR EXISTS (
            SELECT 1 FROM fill_envelope_identity fei
              JOIN fills f2 ON f2.fill_id = fei.fill_id
             WHERE fei.fill_id = NEW.entry_fill_id_at_correction
               AND fei.envelope_raw = f2.schwab_source_value_json
               AND fei.envelope_state = 'canonical'))

    -- ===================== 22-A: THE TIER AND ITS CITATION ==================
    AND COALESCE((
        -- 'last_word': ALL FIVE citation columns NULL. The tier a row claims
        -- and the evidence it carries may not disagree.
        --
        -- AND THE ABSENCE OF EVIDENCE MUST BE AN ABSENCE OF AUTHORITY (Codex
        -- 22A-R6-01). Proving only that the five columns are NULL made the
        -- tier an OPERATOR-SELECTABLE LABEL: a raw correction could set
        -- 'last_word', erase the citation, and bypass every latch refusal on a
        -- fill whose own envelope names an accepted order. That is the widest
        -- wrong ACCEPTANCE in the arc -- the eleven-rung authority downgraded
        -- by writing a different word in a column.
        --
        -- So the branch now REQUIRES that the authoritative fill's broker
        -- order resolves to NO link. A fill with no envelope, or one whose
        -- STORED reading names no order, yields NULL, `l.broker_order_id =
        -- NULL` is NULL, NOT EXISTS holds, and last_word is admitted -- which
        -- is right: no usable order id means no latch authority exists to
        -- bypass.
        --
        -- PERSIST-CANONICAL: this reads the AUTHORITY'S STORED ANSWER, never
        -- the document. The `json_valid` CASE that used to guard a
        -- `json_extract` here is gone with the extract it protected; both
        -- sides of the comparison are now TEXT columns, so equality is plain
        -- and neither engine has a reading to disagree about. The clause
        -- above has already established that the reading exists and was not
        -- refused, so a document nobody has read cannot reach this branch.
        (NEW.admission_tier = 'last_word'
         AND NEW.cited_latch_link_id IS NULL
         AND NEW.cited_latch_validity_intent_id IS NULL
         AND NEW.cited_latch_place_intent_id IS NULL
         AND NEW.cited_latch_broker_order_id IS NULL
         AND NEW.cited_latch_probe_json IS NULL
         AND NOT EXISTS (
             SELECT 1 FROM latch_order_mandate_links l
              WHERE l.broker_order_id = (
                  SELECT fei.broker_order_id
                    FROM fill_envelope_identity fei
                    JOIN fills f ON f.fill_id = fei.fill_id
                   WHERE fei.fill_id = NEW.entry_fill_id_at_correction
                     AND fei.envelope_raw = f.schwab_source_value_json
                     AND fei.envelope_state = 'canonical')))
        OR
        -- 'latch_ladder': ALL FIVE present, each bound to its source.
        (NEW.admission_tier = 'latch_ladder'
         AND NEW.cited_latch_link_id IS NOT NULL
         AND NEW.cited_latch_validity_intent_id IS NOT NULL
         AND NEW.cited_latch_place_intent_id IS NOT NULL
         AND NEW.cited_latch_broker_order_id IS NOT NULL
         AND NEW.cited_latch_probe_json IS NOT NULL

         -- the LINK is the one the row claims, on the cited candidate, naming
         -- the cited order and the two cited intents
         AND EXISTS (SELECT 1 FROM latch_order_mandate_links l
                     WHERE l.link_id = NEW.cited_latch_link_id
                       AND l.candidate_id = NEW.cited_candidate_id
                       AND l.broker_order_id = NEW.cited_latch_broker_order_id
                       AND l.validity_intent_id = NEW.cited_latch_validity_intent_id
                       AND l.place_intent_id = NEW.cited_latch_place_intent_id)
         -- the cited VALIDITY row is accepted, carries that order id, and its
         -- own parent IS the cited place row (the relation a raw link can
         -- otherwise assert falsely while every other check passes)
         AND EXISTS (SELECT 1 FROM latch_order_intents v
                     WHERE v.intent_id = NEW.cited_latch_validity_intent_id
                       AND v.intent_kind = 'validity'
                       AND v.validity_outcome = 'accepted_by_broker'
                       AND v.actual_broker_order_id = NEW.cited_latch_broker_order_id
                       AND v.validated_place_intent_id = NEW.cited_latch_place_intent_id)
         -- the cited PLACE row is a place row on the cited candidate
         AND EXISTS (SELECT 1 FROM latch_order_intents p
                     WHERE p.intent_id = NEW.cited_latch_place_intent_id
                       AND p.intent_kind = 'place'
                       AND p.candidate_id = NEW.cited_candidate_id)

         -- THE CITED ORDER IS THE ONE THE SUBJECT FILL NAMES (Codex
         -- 22A-R6-02). Every clause above binds the citation to ITSELF -- the
         -- link to its intents, the intents to each other -- and the only
         -- subject-envelope field checked anywhere was the instrument SYMBOL.
         -- So a raw correction could cite ANY otherwise-compatible accepted
         -- link on the ticker while the fill's own envelope named a different
         -- order, or none: a mandate the fill cannot prove it came from,
         -- admitted structurally.
         --
         -- PERSIST-CANONICAL: the fill's order id is the one the AUTHORITY
         -- stored against this exact document, compared TEXT to TEXT. This
         -- clause is where the reshape's guarantee is cashed: a raw writer
         -- whose citation names a DIFFERENT order than the stored reading
         -- aborts here, which is condition (2) of the ruling.
         AND (SELECT fei.broker_order_id
                FROM fill_envelope_identity fei
                JOIN fills f ON f.fill_id = fei.fill_id
               WHERE fei.fill_id = NEW.entry_fill_id_at_correction
                 AND fei.envelope_raw = f.schwab_source_value_json
                 AND fei.envelope_state = 'canonical')
             = NEW.cited_latch_broker_order_id

         -- AND THE ORDER NAMES EXACTLY ONE LINK (Codex 22A-R6-03).
         -- `broker_order_id` is deliberately NOT unique, and the resolver
         -- COUNTS: two links refuse `ambiguous_accepted_orders`. The trigger
         -- verified only that the SELECTED link exists, so a raw correction
         -- could pick one of two ambiguous mandates and assign its cohort keys
         -- permanently. The reader counts; so does the twin.
         AND (SELECT COUNT(*) FROM latch_order_mandate_links l2
               WHERE l2.broker_order_id = NEW.cited_latch_broker_order_id) = 1

         -- ---------------- THE PROBE EVIDENCE, CLOSED AND BOUND -------------
         --
         -- EVERY BLOB CLAUSE SITS INSIDE A `CASE WHEN json_valid(...)` AND
         -- THAT IS NOT COSMETIC (Codex 22A-R3-12, VERIFIED BY EXECUTION on
         -- sqlite 3.50.4). SQLite does NOT short-circuit AND for the purpose
         -- of skipping a JSON function's error: `SELECT 0 AND
         -- json_extract('{bad','$.x')` RAISES "malformed JSON" -- measured,
         -- both operand orders. So a raw INSERT carrying a non-NULL,
         -- non-JSON `cited_latch_probe_json` made the WHOLE TRIGGER raise an
         -- OperationalError instead of reaching its own RAISE(ABORT), and the
         -- operator got an engine error in place of the citation message.
         --
         -- `CASE WHEN` DOES defer its branches (measured the same way), so
         -- the guard now JUDGES the malformed value instead of dying on it.
         -- DIRECTION, stated so the severity is not overclaimed: both
         -- behaviours REFUSE the write, and this trigger is on
         -- `provenance_corrections`, which the money-bearing entry path never
         -- touches. The gain is a legible refusal, not a closed hole.
         AND CASE WHEN json_valid(NEW.cited_latch_probe_json) THEN (
             json_type(NEW.cited_latch_probe_json) = 'object'
         AND json_remove(NEW.cited_latch_probe_json,
                 '$.evidence_version', '$.fire_candidate_id', '$.ticker',
                 '$.fill_session', '$.horizon_session', '$.bars_through',
                 '$.clear_reason', '$.clear_session', '$.admission_basis',
                 '$.criteria_lapse_forced_off', '$.freeze_tier',
                 '$.archive_status', '$.frozen_invalidation_raw',
                 '$.live_invalidation_raw', '$.frozen_pivot_raw',
                 '$.live_pivot_raw', '$.invalidation_equal_at_dp',
                 '$.pivot_equal_at_dp', '$.compare_dp', '$.coverage',
                 '$.probe_guards', '$.authorization') = '{}'

         -- the schema's own version, pinned. A row written under an older shape
         -- must be DISTINGUISHABLE rather than silently re-interpreted.
         AND json_type(NEW.cited_latch_probe_json, '$.evidence_version') = 'text'
         AND json_extract(NEW.cited_latch_probe_json, '$.evidence_version') = '2026-08-25.1'

         AND json_type(NEW.cited_latch_probe_json, '$.fire_candidate_id') = 'integer'
         AND json_extract(NEW.cited_latch_probe_json, '$.fire_candidate_id')
             = NEW.cited_candidate_id
         AND json_type(NEW.cited_latch_probe_json, '$.ticker') = 'text'
         AND json_extract(NEW.cited_latch_probe_json, '$.ticker')
             = (SELECT t.ticker FROM trades t WHERE t.id = NEW.trade_id)
         AND json_type(NEW.cited_latch_probe_json, '$.fill_session') = 'text'
         AND json_extract(NEW.cited_latch_probe_json, '$.fill_session')
             = NEW.entry_fill_session_date
         -- horizon_session IS the fill session and IS bound; bars_through is
         -- the exchange-calendar-derived prior session and is NOT (limit 3).
         AND json_type(NEW.cited_latch_probe_json, '$.horizon_session') = 'text'
         AND json_extract(NEW.cited_latch_probe_json, '$.horizon_session')
             = NEW.entry_fill_session_date
         -- `bars_through` IS SYNTACTICALLY VALIDATED (Codex 22A-R5-05). AL-5
         -- says SQL cannot know the exchange CALENDAR; it says nothing about
         -- whether a claimed session string is a DATE at all, and a
         -- `json_type = 'text'` check accepted "garbage". The same
         -- four-predicate guard this migration applies to
         -- `latch_order_mandate_links.detection_date` -- length, parseable,
         -- round-trips, and the YEAR BOUND that rejects SQLite's year-zero
         -- dates -- applies here. Calendar truthfulness stays the service's.
         AND json_type(NEW.cited_latch_probe_json, '$.bars_through') = 'text'
         AND length(json_extract(NEW.cited_latch_probe_json,
                 '$.bars_through')) = 10
         AND date(json_extract(NEW.cited_latch_probe_json,
                 '$.bars_through')) IS NOT NULL
         AND date(json_extract(NEW.cited_latch_probe_json,
                 '$.bars_through'))
             = json_extract(NEW.cited_latch_probe_json, '$.bars_through')
         AND CAST(substr(json_extract(NEW.cited_latch_probe_json,
                 '$.bars_through'), 1, 4) AS INTEGER) BETWEEN 1 AND 9999

         -- the lapse rung was FORCED OFF: RD's bound is that a latch never dies
         -- of drift, so an admission derived with the rung armed is a different
         -- judgment wearing the same name.
         AND json_type(NEW.cited_latch_probe_json, '$.criteria_lapse_forced_off') = 'integer'
         AND json_extract(NEW.cited_latch_probe_json, '$.criteria_lapse_forced_off') = 1

         AND json_type(NEW.cited_latch_probe_json, '$.freeze_tier') = 'text'
         AND json_extract(NEW.cited_latch_probe_json, '$.freeze_tier')
             = (SELECT l.freeze_tier FROM latch_order_mandate_links l
                 WHERE l.link_id = NEW.cited_latch_link_id)

         -- THE ADMISSION BASIS. Without it an admission reached through the
         -- same-session tie would either ABORT here or record clear_reason null
         -- and FALSELY CLAIM an armed probe -- a false provenance claim minted
         -- by the fix that made the mechanism correct.
         AND json_type(NEW.cited_latch_probe_json, '$.admission_basis') = 'text'
         AND (
             (json_extract(NEW.cited_latch_probe_json, '$.admission_basis') = 'armed'
              AND json_type(NEW.cited_latch_probe_json, '$.clear_reason') = 'null'
              AND json_type(NEW.cited_latch_probe_json, '$.clear_session') = 'null')
             OR
             -- THE THREE REACHABLE REASONS. invalidation is admitted by the
             -- RULE (fill-wins is uniform) but is UNREACHABLE through the
             -- production probe -- bar_bound is the session BEFORE the fill, so
             -- an invalidation can never carry the fill session's date and a row
             -- claiming one is incoherent by construction. fill is excluded by
             -- the rule itself: another trade's fill is a consumption.
             (json_extract(NEW.cited_latch_probe_json, '$.admission_basis')
                  = 'subject_fill_wins_same_session_tie'
              AND json_type(NEW.cited_latch_probe_json, '$.clear_reason') = 'text'
              AND json_extract(NEW.cited_latch_probe_json, '$.clear_reason')
                  IN ('declined', 'superseded', 'horizon')
              AND json_type(NEW.cited_latch_probe_json, '$.clear_session') = 'text'
              AND json_extract(NEW.cited_latch_probe_json, '$.clear_session')
                  = NEW.entry_fill_session_date)
         )

         -- THE FOUR RAW OPERANDS, EACH BOUND BY IDENTITY TO ITS SOURCE. A
         -- number a row supplies about itself proves only that the row is
         -- self-consistent.
         AND json_type(NEW.cited_latch_probe_json, '$.frozen_invalidation_raw')
             IN ('real', 'integer')
         AND json_extract(NEW.cited_latch_probe_json, '$.frozen_invalidation_raw')
             = (SELECT l.frozen_invalidation FROM latch_order_mandate_links l
                 WHERE l.link_id = NEW.cited_latch_link_id)
         AND json_type(NEW.cited_latch_probe_json, '$.live_invalidation_raw')
             IN ('real', 'integer')
         AND json_extract(NEW.cited_latch_probe_json, '$.live_invalidation_raw')
             = (SELECT ca.initial_stop FROM candidates ca
                 WHERE ca.id = NEW.cited_candidate_id)
         AND json_type(NEW.cited_latch_probe_json, '$.frozen_pivot_raw')
             IN ('real', 'integer')
         AND json_extract(NEW.cited_latch_probe_json, '$.frozen_pivot_raw')
             = (SELECT l.frozen_pivot FROM latch_order_mandate_links l
                 WHERE l.link_id = NEW.cited_latch_link_id)
         AND json_type(NEW.cited_latch_probe_json, '$.live_pivot_raw')
             IN ('real', 'integer')
         AND json_extract(NEW.cited_latch_probe_json, '$.live_pivot_raw')
             = (SELECT ca.pivot FROM candidates ca
                 WHERE ca.id = NEW.cited_candidate_id)

         -- THE SERVICE'S VERDICT, CARRIED AS A DATUM. SQL asserts the verdicts
         -- are 1 and that compare_dp is the precision the service used. It does
         -- NOT recompute them -- that is the rule, not an omission.
         AND json_type(NEW.cited_latch_probe_json, '$.invalidation_equal_at_dp') = 'integer'
         AND json_extract(NEW.cited_latch_probe_json, '$.invalidation_equal_at_dp') = 1
         AND json_type(NEW.cited_latch_probe_json, '$.pivot_equal_at_dp') = 'integer'
         AND json_extract(NEW.cited_latch_probe_json, '$.pivot_equal_at_dp') = 1
         AND json_type(NEW.cited_latch_probe_json, '$.compare_dp') = 'integer'
         AND json_extract(NEW.cited_latch_probe_json, '$.compare_dp') = 2

         -- ARCHIVE STATUS: 'ok' unless the judging window was empty.
         AND json_type(NEW.cited_latch_probe_json, '$.archive_status') IN ('text', 'null')
         AND (json_type(NEW.cited_latch_probe_json, '$.coverage.window_empty') = 'true'
              OR json_extract(NEW.cited_latch_probe_json, '$.archive_status') = 'ok')

         -- COVERAGE: exactly one of the two shapes, each closed at its own
         -- level. The arrays are compared ELEMENT BY ELEMENT via json_each --
         -- equal lengths plus an empty missing_sessions accepts two unrelated
         -- or duplicated arrays -- with duplicate rejection and an ISO-date
         -- check on every element. Note json_each's own `type` column is used:
         -- the ONE-ARGUMENT json_type() parses its argument AS JSON and raises
         -- "malformed JSON" on a bare date string (measured).
         AND json_type(NEW.cited_latch_probe_json, '$.coverage') = 'object'
         AND (
             (CASE WHEN json_type(NEW.cited_latch_probe_json, '$.coverage')
                        = 'object'
                   THEN json_remove(json_extract(NEW.cited_latch_probe_json, '$.coverage'),
                          '$.window_empty') = '{}'
                   ELSE 0 END
              AND json_type(NEW.cited_latch_probe_json, '$.coverage.window_empty') = 'true')
             OR
             (CASE WHEN json_type(NEW.cited_latch_probe_json, '$.coverage')
                        = 'object'
                   THEN json_remove(json_extract(NEW.cited_latch_probe_json, '$.coverage'),
                          '$.expected_sessions', '$.observed_sessions',
                          '$.missing_sessions') = '{}'
                   ELSE 0 END
              AND json_type(NEW.cited_latch_probe_json, '$.coverage.expected_sessions') = 'array'
              AND json_type(NEW.cited_latch_probe_json, '$.coverage.observed_sessions') = 'array'
              AND json_type(NEW.cited_latch_probe_json, '$.coverage.missing_sessions') = 'array'
              AND json_array_length(NEW.cited_latch_probe_json, '$.coverage.missing_sessions') = 0
              AND json_array_length(NEW.cited_latch_probe_json, '$.coverage.expected_sessions')
                  = json_array_length(NEW.cited_latch_probe_json, '$.coverage.observed_sessions')
              AND NOT EXISTS (
                  SELECT 1
                    FROM json_each(NEW.cited_latch_probe_json, '$.coverage.expected_sessions') e
                    LEFT JOIN json_each(NEW.cited_latch_probe_json,
                                        '$.coverage.observed_sessions') o ON o.key = e.key
                   WHERE o.value IS NOT e.value)
              AND (SELECT COUNT(DISTINCT value) FROM json_each(
                      NEW.cited_latch_probe_json, '$.coverage.expected_sessions'))
                  = json_array_length(NEW.cited_latch_probe_json, '$.coverage.expected_sessions')
              -- THE YEAR BOUND IS PART OF THE GUARD (Codex 22A-R5-05). The
              -- other three predicates accept SQLite's year-zero dates
              -- ('0000-01-01' has length 10, parses, and round-trips), which
              -- the same guard on `detection_date` rejects. Four predicates
              -- here too, so the two spellings of "is this a date" agree.
              AND NOT EXISTS (
                  SELECT 1
                    FROM json_each(NEW.cited_latch_probe_json, '$.coverage.expected_sessions') e
                   WHERE e.type <> 'text' OR length(e.value) <> 10
                      OR date(e.value) IS NULL OR date(e.value) <> e.value
                      OR CAST(substr(e.value, 1, 4) AS INTEGER)
                         NOT BETWEEN 1 AND 9999))
         )

         -- ------------- $.probe_guards: THE PROBE'S OWN REFUSAL-CAPABLE
         -- CLAUSES. $.authorization covers the AUTHORIZER's rungs; the PROBE
         -- has clauses of its own -- the fill-session check, fire-membership
         -- uniqueness and the decision as-of ordering -- and they had NO
         -- verdict slot, so an audit could not tell "the guard passed" from
         -- "the guard never ran" for exactly the three clauses that decide
         -- whether the delegated derivation is trustworthy. Same standing
         -- rule, same {input, verdict} shape, closed on the SAME roster
         -- (PROBE_GUARD_CLAUSES in swing/trades/latched_origin.py), with the
         -- comparison running roster-to-SQL and roster-to-emitter rather than
         -- SQL-to-emitter -- a key-set check that derives its expectation from
         -- THIS FILE cannot catch a key missing from both halves.
         AND json_type(NEW.cited_latch_probe_json, '$.probe_guards') = 'object'
         AND CASE WHEN json_type(NEW.cited_latch_probe_json, '$.probe_guards')
                       = 'object'
                  THEN json_remove(json_extract(NEW.cited_latch_probe_json, '$.probe_guards'),
                 '$.fill_session_is_session', '$.fire_membership',
                 '$.decision_ordering') = '{}'
                  ELSE 0 END

         -- THE FILL SESSION THE GUARD JUDGED IS THE ROW'S OWN. An unbound copy
         -- would let a row attest a check it ran against a different date.
         AND CASE WHEN json_type(NEW.cited_latch_probe_json, '$.probe_guards.fill_session_is_session')
                       = 'object'
                  THEN json_remove(json_extract(NEW.cited_latch_probe_json,
                 '$.probe_guards.fill_session_is_session'), '$.input', '$.verdict') = '{}'
                  ELSE 0 END
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.probe_guards.fill_session_is_session.verdict') = 'pass'
         AND json_type(NEW.cited_latch_probe_json,
                 '$.probe_guards.fill_session_is_session.input') = 'text'
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.probe_guards.fill_session_is_session.input')
             = NEW.entry_fill_session_date

         -- EXACTLY ONE latch's candidate_set may contain the fire. The count
         -- is derivation state no subquery can reach, so SQL binds the VALUE
         -- (it must be 1) rather than re-deriving it; two is the shape
         -- ambiguous_fire_membership refuses and is not an admission.
         AND CASE WHEN json_type(NEW.cited_latch_probe_json, '$.probe_guards.fire_membership')
                       = 'object'
                  THEN json_remove(json_extract(NEW.cited_latch_probe_json,
                 '$.probe_guards.fire_membership'), '$.input', '$.verdict') = '{}'
                  ELSE 0 END
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.probe_guards.fire_membership.verdict') = 'pass'
         AND json_type(NEW.cited_latch_probe_json,
                 '$.probe_guards.fire_membership.input') = 'integer'
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.probe_guards.fire_membership.input') = 1

         -- THE DECISIONS THE AS-OF RULE ORDERED, each [intent_id,
         -- recorded_ts].
         --
         -- THE BINDING IS WRITER-SUPPLIED-PAIRS-ONLY, AND IT IS NOT AL-3
         -- (Codex 22A-R9-05; CHARC ruled 2026-08-26). This comment cited AL-3
         -- -- "rungs 7, 8 and fire_membership are service-validated" -- for a
         -- clause AL-3 does not name, which SILENTLY BROADENED a declared
         -- limitation roster to cover something nobody had ruled on. AL-3
         -- stands as written and does NOT extend here; this clause carries its
         -- own declaration, below, which is narrower than AL-3 in one
         -- direction and weaker in another and therefore cannot borrow it.
         --
         -- WHAT IS PROVED: every pair the writer DID supply is well-shaped and
         -- MATCHES a real `latch_order_intents` row on BOTH halves. That is
         -- more than AL-3's clauses get -- a fabricated pair is REJECTED here,
         -- where a fabricated rung-7 array is accepted.
         --
         -- WHAT IS NOT PROVED, DECLARED AS A LIMITATION WITH ITS REASON: the
         -- COMPLETENESS of the supply. An EMPTY array satisfies this clause
         -- vacuously, and so does any SUBSET of the decisions the fold
         -- actually consulted. The reason is exact: the guard validates the
         -- CONSISTENCY of what was supplied and does not enforce the
         -- COMPLETENESS of supply, because nothing in this schema specifies
         -- what the required decision set IS. A clause enforcing a set no
         -- authority has ruled would be a guess wearing a constraint's
         -- clothing, and on this table a wrong REFUSAL is permanent.
         --
         -- BANKED TO 22-A2 WITH ITS TRIGGER: when the proof machinery
         -- specifies the required decision set, this guard gains its
         -- completeness half, where that authority will exist. The reviewer's
         -- proposed anti-admission predicate -- refuse `latch_ladder` whenever
         -- ANY same-ticker decision is recorded at-or-after the fill session --
         -- is a real behaviour widening rather than a patch, and it is that
         -- arc's question. It is written down here so the next reader meets
         -- the limitation and its owner in the same paragraph.
         AND CASE WHEN json_type(NEW.cited_latch_probe_json, '$.probe_guards.decision_ordering')
                       = 'object'
                  THEN json_remove(json_extract(NEW.cited_latch_probe_json,
                 '$.probe_guards.decision_ordering'), '$.input', '$.verdict') = '{}'
                  ELSE 0 END
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.probe_guards.decision_ordering.verdict') = 'pass'
         AND json_type(NEW.cited_latch_probe_json,
                 '$.probe_guards.decision_ordering.input') = 'array'
         -- THE ELEMENT SHAPE IS VALIDATED AND EACH PAIR IS BOUND (Codex
         -- 22A-R5-06). Typing only the OUTER value accepted strings, objects,
         -- one-element arrays and nonexistent ids -- so the "consulted
         -- decisions" record could name rows that do not exist while reading
         -- as evidence. This does NOT ask SQL to reconstruct the admissible
         -- fold topology -- see the COMPLETENESS limitation declared above,
         -- which is this clause's own and is NOT AL-3's. What SQL can do is
         -- insist that every claimed pair is `[integer intent_id, text
         -- recorded_ts]` and that the pair MATCHES a real intent row on both
         -- halves.
         AND NOT EXISTS (
             SELECT 1
               FROM json_each(NEW.cited_latch_probe_json,
                              '$.probe_guards.decision_ordering.input') d
              WHERE d.type <> 'array'
                 OR json_array_length(d.value) <> 2
                 OR json_type(d.value, '$[0]') <> 'integer'
                 OR json_type(d.value, '$[1]') <> 'text'
                 OR NOT EXISTS (
                        SELECT 1 FROM latch_order_intents x
                         WHERE x.intent_id = json_extract(d.value, '$[0]')
                           AND x.recorded_ts = json_extract(d.value, '$[1]')))

         -- ------------- $.authorization: ONE ENTRY PER REFUSAL-CAPABLE CLAUSE
         -- If a clause can REFUSE an admission, the blob records the INPUT it
         -- judged and the VERDICT it reached -- or "passed" and "never ran" are
         -- indistinguishable at audit. A MISSING entry is REJECTED rather than
         -- read as a pass, and PRESENCE IS NOT FIDELITY: the SQL-bound entries
         -- have their recorded input bound by subquery to its source, so a
         -- fabricated input is rejected too.
         AND json_type(NEW.cited_latch_probe_json, '$.authorization') = 'object'
         AND CASE WHEN json_type(NEW.cited_latch_probe_json, '$.authorization')
                       = 'object'
                  THEN json_remove(json_extract(NEW.cited_latch_probe_json, '$.authorization'),
                 '$.rung1_link_ticker', '$.rung2_link_parent',
                 '$.rung3_validity_outcome', '$.rung3b_latest_validity_child',
                 '$.rung3c_link_broker_order_id', '$.rung4_governing_place_intent',
                 '$.rung5_cancel_intent_id', '$.rung6_consuming_trade_id',
                 '$.rung7_consumption_scan_fill_ids', '$.rung8_competitor_link_ids',
                 '$.rung9_stored_freeze_tier', '$.guard_fill_origin',
                 '$.guard_envelope_symbol', '$.guard_quantity',
                 '$.guard_framework_price_bound',
                 '$.guard_broker_limit_bound') = '{}'
                  ELSE 0 END

         -- every entry is closed to exactly {input, verdict} and every verdict
         -- is 'pass' (a non-pass entry contradicts the admission it sits in)
         AND CASE WHEN json_type(NEW.cited_latch_probe_json, '$.authorization.rung1_link_ticker')
                       = 'object'
                  THEN json_remove(json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung1_link_ticker'), '$.input', '$.verdict') = '{}'
                  ELSE 0 END
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung1_link_ticker.verdict') = 'pass'
         AND json_type(NEW.cited_latch_probe_json,
                 '$.authorization.rung1_link_ticker.input') = 'text'
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung1_link_ticker.input')
             = (SELECT l.ticker FROM latch_order_mandate_links l
                 WHERE l.link_id = NEW.cited_latch_link_id)
         -- ...AND THE LINK'S TICKER IS THE TRADE'S (Codex 22A-R5-01). Binding
         -- the input to `l.ticker` proves only that the row repeats itself;
         -- rung 1 in the service compares the link's ticker to the REQUEST's,
         -- and without this the trigger accepted a link carrying a forged
         -- ticker while every other clause passed.
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung1_link_ticker.input')
             = (SELECT t.ticker FROM trades t WHERE t.id = NEW.trade_id)

         AND CASE WHEN json_type(NEW.cited_latch_probe_json, '$.authorization.rung2_link_parent')
                       = 'object'
                  THEN json_remove(json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung2_link_parent'), '$.input', '$.verdict') = '{}'
                  ELSE 0 END
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung2_link_parent.verdict') = 'pass'
         AND json_type(NEW.cited_latch_probe_json,
                 '$.authorization.rung2_link_parent.input') = 'integer'
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung2_link_parent.input')
             = (SELECT l.place_intent_id FROM latch_order_mandate_links l
                 WHERE l.link_id = NEW.cited_latch_link_id)

         AND CASE WHEN json_type(NEW.cited_latch_probe_json, '$.authorization.rung3_validity_outcome')
                       = 'object'
                  THEN json_remove(json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung3_validity_outcome'), '$.input', '$.verdict') = '{}'
                  ELSE 0 END
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung3_validity_outcome.verdict') = 'pass'
         AND json_type(NEW.cited_latch_probe_json,
                 '$.authorization.rung3_validity_outcome.input') = 'text'
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung3_validity_outcome.input')
             = (SELECT v.validity_outcome FROM latch_order_intents v
                 WHERE v.intent_id = NEW.cited_latch_validity_intent_id)
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung3_validity_outcome.input') = 'accepted_by_broker'

         -- THE LATEST VALIDITY CHILD, by the SAME TOTAL ORDER the classifier
         -- uses -- (recorded_ts, intent_id), swing/latches/classification.py
         -- _order_key -- spelled here as ORDER BY ... DESC LIMIT 1 rather than
         -- MAX(intent_id), which is a DIFFERENT order whenever a later-inserted
         -- row carries an earlier recorded_ts.
         AND CASE WHEN json_type(NEW.cited_latch_probe_json, '$.authorization.rung3b_latest_validity_child')
                       = 'object'
                  THEN json_remove(json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung3b_latest_validity_child'), '$.input', '$.verdict') = '{}'
                  ELSE 0 END
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung3b_latest_validity_child.verdict') = 'pass'
         AND json_type(NEW.cited_latch_probe_json,
                 '$.authorization.rung3b_latest_validity_child.input') = 'integer'
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung3b_latest_validity_child.input')
             = NEW.cited_latch_validity_intent_id
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung3b_latest_validity_child.input')
             = (SELECT x.intent_id FROM latch_order_intents x
                 WHERE x.validated_place_intent_id = NEW.cited_latch_place_intent_id
                   AND x.intent_kind = 'validity'
                 ORDER BY x.recorded_ts DESC, x.intent_id DESC LIMIT 1)

         AND CASE WHEN json_type(NEW.cited_latch_probe_json, '$.authorization.rung3c_link_broker_order_id')
                       = 'object'
                  THEN json_remove(json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung3c_link_broker_order_id'), '$.input', '$.verdict') = '{}'
                  ELSE 0 END
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung3c_link_broker_order_id.verdict') = 'pass'
         AND json_type(NEW.cited_latch_probe_json,
                 '$.authorization.rung3c_link_broker_order_id.input') = 'text'
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung3c_link_broker_order_id.input')
             = (SELECT v.actual_broker_order_id FROM latch_order_intents v
                 WHERE v.intent_id = NEW.cited_latch_validity_intent_id)
         -- RUNG 3c IS ABOUT *EVERY* DUPLICATED LINK FIELD, and the recorded
         -- entry can only carry one (Codex 22A-R5-01). The service binds all
         -- five -- broker order id, quantity, ticker, evaluation run and
         -- detection date -- back to the validity row and the candidate's own
         -- run; the trigger bound the order id alone, so a raw link could cite
         -- a GENUINE accepted validity row while carrying an inflated quantity
         -- or a substituted run. The remaining four are bound HERE, under the
         -- rung whose contract they are, rather than as a separate clause that
         -- would read as belonging to nothing.
         AND EXISTS (
             SELECT 1 FROM latch_order_mandate_links l
               JOIN latch_order_intents v
                 ON v.intent_id = NEW.cited_latch_validity_intent_id
               JOIN candidates ca ON ca.id = NEW.cited_candidate_id
               JOIN evaluation_runs er ON er.id = ca.evaluation_run_id
              WHERE l.link_id = NEW.cited_latch_link_id
                AND l.actual_quantity IS v.actual_quantity
                AND l.ticker = ca.ticker
                AND l.evaluation_run_id = ca.evaluation_run_id
                AND l.detection_date = er.action_session_date)

         -- THE GOVERNING PLACE CYCLE AS OF THE FILL. A later place opens a new
         -- cycle and RETIRES the earlier order regardless of what the earlier
         -- order's own validity children say. The as-of bound is STRICTLY
         -- BEFORE the fill session, the same date-only clock policy the service
         -- applies: an intent recorded ON the fill session is UNORDERABLE
         -- against it and refuses rather than being counted either way.
         AND CASE WHEN json_type(NEW.cited_latch_probe_json, '$.authorization.rung4_governing_place_intent')
                       = 'object'
                  THEN json_remove(json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung4_governing_place_intent'), '$.input', '$.verdict') = '{}'
                  ELSE 0 END
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung4_governing_place_intent.verdict') = 'pass'
         AND json_type(NEW.cited_latch_probe_json,
                 '$.authorization.rung4_governing_place_intent.input') = 'integer'
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung4_governing_place_intent.input')
             = NEW.cited_latch_place_intent_id
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung4_governing_place_intent.input')
             = (SELECT x.intent_id FROM latch_order_intents x
                 WHERE x.candidate_id = NEW.cited_candidate_id
                   AND x.intent_kind = 'place'
                   AND date(x.recorded_ts) < NEW.entry_fill_session_date
                 ORDER BY x.recorded_ts DESC, x.intent_id DESC LIMIT 1)

         -- NO CANCELLATION OF *THIS BROKER ORDER* at-or-before the fill. The
         -- recorded input is JSON null -- "none found" -- and the null is
         -- BOUND: the trigger asserts there genuinely is none.
         --
         -- ORDER-SCOPED, NOT CANDIDATE-SCOPED (Codex 22A-R4-04). A cancel row
         -- is REQUIRED by 0033's CHECK to name one broker order -- there is no
         -- by-ticker cancel path -- so a candidate-wide NOT EXISTS rejects a
         -- truthful citation whose fire had an OLDER order cancelled before
         -- being re-placed. BOTH HALVES MOVED TOGETHER with the service's own
         -- rung 5 (`swing/trades/latched_origin.py`); a twin that encoded a
         -- DIFFERENT predicate from the reader is the same defect as a missing
         -- twin, and here the divergence would authorize a correction that
         -- then aborts at the INSERT.
         AND CASE WHEN json_type(NEW.cited_latch_probe_json, '$.authorization.rung5_cancel_intent_id')
                       = 'object'
                  THEN json_remove(json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung5_cancel_intent_id'), '$.input', '$.verdict') = '{}'
                  ELSE 0 END
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung5_cancel_intent_id.verdict') = 'pass'
         AND json_type(NEW.cited_latch_probe_json,
                 '$.authorization.rung5_cancel_intent_id.input') = 'null'
         AND NOT EXISTS (SELECT 1 FROM latch_order_intents x
                         WHERE x.candidate_id = NEW.cited_candidate_id
                           AND x.intent_kind = 'cancel'
                           AND x.actual_broker_order_id
                               = NEW.cited_latch_broker_order_id
                           AND date(x.recorded_ts) <= NEW.entry_fill_session_date)

         -- NO OTHER TRADE HAS CONSUMED THIS ORDER. Order-linked, never
         -- COUNT(*) over the candidate: the ordinary entry path assigns
         -- candidate_id from pipeline provenance with no accepted order
         -- anywhere near it, so a count would let an unrelated trade falsely
         -- block the real order-linked fill.
         AND CASE WHEN json_type(NEW.cited_latch_probe_json, '$.authorization.rung6_consuming_trade_id')
                       = 'object'
                  THEN json_remove(json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung6_consuming_trade_id'), '$.input', '$.verdict') = '{}'
                  ELSE 0 END
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung6_consuming_trade_id.verdict') = 'pass'
         AND json_type(NEW.cited_latch_probe_json,
                 '$.authorization.rung6_consuming_trade_id.input') = 'null'
         -- PERSIST-CANONICAL, AND IT DISSOLVES 22A-R7-04's HAZARD RATHER
         -- THAN GUARDING IT. This scan's input used to be ANOTHER ROW's
         -- operator-submitted document, so a malformed envelope on an
         -- unrelated trade could abort this trigger with an engine error
         -- instead of its own legible refusal -- which is why it carried the
         -- CASE-not-AND-chain form. It now reads STORED readings, which are
         -- never parsed, so there is no JSON function left to protect.
         --
         -- WHAT IT CANNOT SEE, stated because the service compensates for it:
         -- an entry fill whose envelope the authority REFUSED stores no order
         -- id, so a consumption hiding inside such a document is invisible
         -- here. The service's rung 6 refuses on exactly that population
         -- (`consumption_evidence_unavailable`), which keeps the SERVICE at
         -- least as strong as its twin -- the direction that never produces
         -- an authorize-then-abort.
         AND NOT EXISTS (SELECT 1 FROM fill_envelope_identity fei
                         JOIN fills f2 ON f2.fill_id = fei.fill_id
                         WHERE f2.action = 'entry'
                           AND f2.trade_id <> NEW.trade_id
                           AND fei.envelope_raw = f2.schwab_source_value_json
                           AND fei.envelope_state = 'canonical'
                           AND fei.broker_order_id
                               = NEW.cited_latch_broker_order_id)

         -- SERVICE-VALIDATED (L17). Rungs 7 and 8 rest on a scan result and on
         -- derivation state that no subquery can reach, so SQL asserts their
         -- PRESENCE, TYPE and verdict and nothing more. A fabricated input on
         -- either is ACCEPTED -- that is a LIMIT of the trigger, declared, not
         -- a guarantee.
         AND CASE WHEN json_type(NEW.cited_latch_probe_json, '$.authorization.rung7_consumption_scan_fill_ids')
                       = 'object'
                  THEN json_remove(json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung7_consumption_scan_fill_ids'),
                 '$.input', '$.verdict') = '{}'
                  ELSE 0 END
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung7_consumption_scan_fill_ids.verdict') = 'pass'
         AND json_type(NEW.cited_latch_probe_json,
                 '$.authorization.rung7_consumption_scan_fill_ids.input') = 'array'

         AND CASE WHEN json_type(NEW.cited_latch_probe_json, '$.authorization.rung8_competitor_link_ids')
                       = 'object'
                  THEN json_remove(json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung8_competitor_link_ids'),
                 '$.input', '$.verdict') = '{}'
                  ELSE 0 END
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung8_competitor_link_ids.verdict') = 'pass'
         AND json_type(NEW.cited_latch_probe_json,
                 '$.authorization.rung8_competitor_link_ids.input') = 'array'

         -- RUNG 9 IS RD'S REFUSE-BY-DEFAULT, MADE STRUCTURAL IN THE AUDIT ROW.
         -- A latch_ladder correction may only cite a POST-barrier link.
         --
         -- AND THE TWIN RE-DERIVES RATHER THAN TRUSTING THE STORED GRADE
         -- (Codex 22A-R5-02 / 22A-R3-02, CHARC ruled 2026-08-25). The clause
         -- below binds `input` to `latch_order_mandate_links.freeze_tier` and
         -- then requires the literal -- both of which are statements about a
         -- STORED value. The Python ladder does not stop there: it RE-DERIVES
         -- the tier at read time from the epoch boundary and requires BOTH to
         -- say live_at_acceptance. A forged link written with the live tier
         -- for a PRE-barrier candidate satisfied every stored-value check and
         -- inserted -- a structural admission for a fire AL-4 says has no
         -- evidence at all.
         --
         -- ONE COMPARISON closes it, ALONGSIDE the tier literal rather than
         -- instead of it: the reader checks the GUARD is real, the trigger
         -- checks the CLAIM is derivable, and both authorities are now
         -- consulted where they live. The predicate MIRRORS
         -- `freeze_tier_for_candidate`: STRICTLY GREATER THAN the boundary
         -- (the boundary row itself is PRE-barrier, inherited finding
         -- 22A-R9-02), and an ABSENT epoch row rejects -- which matches the
         -- reader's `boundary is None -> pre_barrier` branch and fails closed.
         --
         -- WHAT IT STILL DOES NOT DO, stated rather than left to look
         -- complete: it does not compare the barrier TRIGGER BODIES against
         -- sqlite_master. That is R3-02's in-trigger body comparison, and it
         -- is UNFIXED-NOT-REOPENED by the same ruling -- the reader owns the
         -- guard-is-real question and a trigger cannot ask it cheaply.
         AND CASE WHEN json_type(NEW.cited_latch_probe_json, '$.authorization.rung9_stored_freeze_tier')
                       = 'object'
                  THEN json_remove(json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung9_stored_freeze_tier'), '$.input', '$.verdict') = '{}'
                  ELSE 0 END
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung9_stored_freeze_tier.verdict') = 'pass'
         AND json_type(NEW.cited_latch_probe_json,
                 '$.authorization.rung9_stored_freeze_tier.input') = 'text'
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung9_stored_freeze_tier.input')
             = (SELECT l.freeze_tier FROM latch_order_mandate_links l
                 WHERE l.link_id = NEW.cited_latch_link_id)
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung9_stored_freeze_tier.input') = 'live_at_acceptance'
         AND EXISTS (SELECT 1 FROM candidates_immutability_epoch e
                     WHERE NEW.cited_candidate_id
                           > e.max_candidate_id_at_barrier)

         -- THE FIVE ENVELOPE GUARDS, SEPARATELY ENUMERATED AND -- at CORRECTION
         -- time -- SQL-BOUND. Their inputs are operator-submitted at ENTRY, but
         -- by the time a correction cites them they are PERSISTED on the fill
         -- this row already names (entry_fill_id_at_correction), so a subquery
         -- CAN reach them and a fabricated input is rejected rather than merely
         -- present.
         AND CASE WHEN json_type(NEW.cited_latch_probe_json, '$.authorization.guard_fill_origin')
                       = 'object'
                  THEN json_remove(json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.guard_fill_origin'), '$.input', '$.verdict') = '{}'
                  ELSE 0 END
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.guard_fill_origin.verdict') = 'pass'
         AND json_type(NEW.cited_latch_probe_json,
                 '$.authorization.guard_fill_origin.input') = 'text'
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.guard_fill_origin.input')
             = (SELECT f.fill_origin FROM fills f
                 WHERE f.fill_id = NEW.entry_fill_id_at_correction)
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.guard_fill_origin.input')
             IN ('schwab_auto', 'schwab_auto_then_operator_corrected')

         AND CASE WHEN json_type(NEW.cited_latch_probe_json, '$.authorization.guard_envelope_symbol')
                       = 'object'
                  THEN json_remove(json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.guard_envelope_symbol'), '$.input', '$.verdict') = '{}'
                  ELSE 0 END
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.guard_envelope_symbol.verdict') = 'pass'
         AND json_type(NEW.cited_latch_probe_json,
                 '$.authorization.guard_envelope_symbol.input') = 'text'
         -- PERSIST-CANONICAL. The `json_extract` on the LEFT stays: the probe
         -- blob is the AUTHORITY'S OWN OUTPUT, and reading a value the service
         -- wrote is consuming its output, which is precisely what the ruling
         -- endorses. The `json_extract` that USED to be on the right read the
         -- OPERATOR'S document and re-derived the service's symbol reading;
         -- that one is gone, replaced by the stored reading of the same
         -- document.
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.guard_envelope_symbol.input')
             = (SELECT fei.instrument_symbol
                  FROM fill_envelope_identity fei
                  JOIN fills f ON f.fill_id = fei.fill_id
                 WHERE fei.fill_id = NEW.entry_fill_id_at_correction
                   AND fei.envelope_raw = f.schwab_source_value_json
                   AND fei.envelope_state = 'canonical')
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.guard_envelope_symbol.input')
             = (SELECT t.ticker FROM trades t WHERE t.id = NEW.trade_id)

         AND CASE WHEN json_type(NEW.cited_latch_probe_json, '$.authorization.guard_quantity')
                       = 'object'
                  THEN json_remove(json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.guard_quantity'), '$.input', '$.verdict') = '{}'
                  ELSE 0 END
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.guard_quantity.verdict') = 'pass'
         AND json_type(NEW.cited_latch_probe_json,
                 '$.authorization.guard_quantity.input') IN ('real', 'integer')
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.guard_quantity.input')
             = (SELECT f.quantity FROM fills f
                 WHERE f.fill_id = NEW.entry_fill_id_at_correction)
         -- AND THE GUARD'S VERDICT, NOT ONLY ITS INPUT (Codex 22A-R5-01). A
         -- fill of 100 could truthfully record input=100 against an accepted
         -- quantity of 2 and the row inserted: input FIDELITY is not predicate
         -- TRUTH, and both operands are SQL-reachable, so this is neither AL-3
         -- nor the rounding limit.
         --
         -- THE NULL BRANCH MIRRORS THE SERVICE EXACTLY: `actual_quantity` is
         -- nullable (0037's own CHECK is `IS NULL OR > 0`) and
         -- `assert_fill_consistent_with_order` skips the inequality when it is
         -- NULL. A bare `<=` would evaluate NULL, take the COALESCE to 0 and
         -- REJECT a row the service admits -- a twin STRONGER than its reader,
         -- which authorizes a correction that then aborts at the INSERT.
         --
         -- The `> 0` half of the service's guard is NOT restated: 0014 CHECKs
         -- `fills.quantity > 0` and the clause above binds the input to that
         -- column, so a non-positive input is schema-prevented rather than
         -- unchecked. Cited rather than defended twice.
         AND (
             (SELECT l.actual_quantity FROM latch_order_mandate_links l
               WHERE l.link_id = NEW.cited_latch_link_id) IS NULL
             OR json_extract(NEW.cited_latch_probe_json,
                    '$.authorization.guard_quantity.input')
                <= (SELECT l.actual_quantity FROM latch_order_mandate_links l
                     WHERE l.link_id = NEW.cited_latch_link_id)
         )

         AND CASE WHEN json_type(NEW.cited_latch_probe_json, '$.authorization.guard_framework_price_bound')
                       = 'object'
                  THEN json_remove(json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.guard_framework_price_bound'), '$.input', '$.verdict') = '{}'
                  ELSE 0 END
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.guard_framework_price_bound.verdict') = 'pass'
         AND json_type(NEW.cited_latch_probe_json,
                 '$.authorization.guard_framework_price_bound.input') IN ('real', 'integer')
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.guard_framework_price_bound.input')
             = (SELECT f.price FROM fills f
                 WHERE f.fill_id = NEW.entry_fill_id_at_correction)

         -- NULLABLE BY DESIGN, and bound with IS so a JSON null must match a
         -- SQL NULL rather than passing on NULL propagation. 0033 CHECKs that
         -- an accepted_by_broker row carries actual_limit_price NOT NULL, so
         -- the null branch is defensive against a shape the schema forbids --
         -- stated rather than left to look like an oversight.
         AND CASE WHEN json_type(NEW.cited_latch_probe_json, '$.authorization.guard_broker_limit_bound')
                       = 'object'
                  THEN json_remove(json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.guard_broker_limit_bound'), '$.input', '$.verdict') = '{}'
                  ELSE 0 END
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.guard_broker_limit_bound.verdict') = 'pass'
         AND json_type(NEW.cited_latch_probe_json,
                 '$.authorization.guard_broker_limit_bound.input')
             IN ('real', 'integer', 'null')
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.guard_broker_limit_bound.input')
             IS (SELECT v.actual_limit_price FROM latch_order_intents v
                  WHERE v.intent_id = NEW.cited_latch_validity_intent_id)
         ) ELSE 0 END
        )
    ), 0)
)
BEGIN
    SELECT RAISE(ABORT, 'provenance_corrections: the cited rows exist but do not form the citation graph this correction asserts (candidate->run, recommendation->run/ticker/kind, pipeline->run, status-history->hypothesis, registry name, fill->trade, trade<->candidate ticker, and -- for admission_tier latch_ladder -- link->candidate/order/intents, the accepted validity row and its place parent, and a closed VERSIONED probe-evidence blob whose every bound field matches its source and whose $.authorization records one passing entry per refusal-capable clause). The citation is STRUCTURAL: a row may not claim a contemporaneous pair it does not have, nor an admission whose evidence it cannot produce. A correction is also refused when the Schwab envelope on the anchoring fill carries a duplicate, padded, blank or non-string schwab_order_id or schwab_instrument_symbol: Python and SQLite read such a document DIFFERENTLY, so the authority it names is ambiguous and no citation may rest on it.');
END;

-- ============================================================================
-- 7. APPEND-ONLY, RE-CREATED with the SIX new columns.
--
-- The shipped trigger ENUMERATES every column, so a column added without
-- updating it becomes freely REWRITABLE on an append-only audit table. Not
-- optional.
--
-- EVERY ONE OF THE SIX IS COMPARED WITH `IS`, NEVER `=`. Five are NULLABLE
-- (only admission_tier carries NOT NULL DEFAULT), and NULL = NULL evaluates to
-- NULL, which makes the WHEN guard NULL and DOES NOT FIRE THE TRIGGER -- so an
-- `=` comparison would silently permit a rewrite of exactly the columns that
-- carry the latch citation. admission_tier is compared with `IS` too: it is
-- non-nullable today, and a comparison whose correctness depends on a
-- NOT NULL somewhere else is a #31-shaped promise.
--
-- THE OLD GUARANTEE SURVIVES, and the test is computed against the OLD one: for
-- every column the PRE-0037 trigger protected, a barred write must STILL fail.
-- A test written only against the six new columns passes a replacement that
-- silently dropped protection on an old one.
-- ============================================================================
DROP TRIGGER trg_provenance_corrections_append_only_update;

CREATE TRIGGER trg_provenance_corrections_append_only_update
BEFORE UPDATE ON provenance_corrections
FOR EACH ROW WHEN NOT (
    ((NEW.entry_fill_id IS NULL AND OLD.entry_fill_id IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM fills WHERE fill_id = OLD.entry_fill_id))
     OR (NEW.entry_fill_id IS OLD.entry_fill_id))
    AND ((NEW.risk_policy_id_at_correction IS NULL
          AND OLD.risk_policy_id_at_correction IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM risk_policy
                          WHERE policy_id = OLD.risk_policy_id_at_correction))
         OR (NEW.risk_policy_id_at_correction
             IS OLD.risk_policy_id_at_correction))
    AND (NEW.entry_fill_id IS NOT OLD.entry_fill_id
         OR NEW.risk_policy_id_at_correction
            IS NOT OLD.risk_policy_id_at_correction)
    AND NEW.provenance_correction_id = OLD.provenance_correction_id
           AND NEW.trade_id = OLD.trade_id
           AND NEW.entry_fill_id_at_correction = OLD.entry_fill_id_at_correction
           AND NEW.entry_fill_snapshot_json = OLD.entry_fill_snapshot_json
           AND NEW.cited_candidate_id = OLD.cited_candidate_id
           AND NEW.cited_daily_recommendation_id = OLD.cited_daily_recommendation_id
           AND NEW.cited_evaluation_run_id = OLD.cited_evaluation_run_id
           AND NEW.cited_hypothesis_id = OLD.cited_hypothesis_id
           AND NEW.cited_hypothesis_status_history_id = OLD.cited_hypothesis_status_history_id
           AND NEW.cited_hypothesis_status_at_record = OLD.cited_hypothesis_status_at_record
           AND NEW.cited_pipeline_finished_ts_raw = OLD.cited_pipeline_finished_ts_raw
           AND NEW.cited_run_ts_utc = OLD.cited_run_ts_utc
           AND NEW.cited_status_window_upper_utc = OLD.cited_status_window_upper_utc
           AND NEW.cited_pipeline_run_id = OLD.cited_pipeline_run_id
           AND NEW.cited_pipeline_run_snapshot_json = OLD.cited_pipeline_run_snapshot_json
           AND NEW.cited_hypothesis_status_recorded_at = OLD.cited_hypothesis_status_recorded_at
           AND NEW.cited_hypothesis_status_effective_from = OLD.cited_hypothesis_status_effective_from
           AND (NEW.cited_hypothesis_status_effective_to IS OLD.cited_hypothesis_status_effective_to)
           AND NEW.cited_hypothesis_name_at_correction = OLD.cited_hypothesis_name_at_correction
           AND NEW.cited_candidate_action_session_date = OLD.cited_candidate_action_session_date
           AND NEW.cited_recommendation_action_session_date = OLD.cited_recommendation_action_session_date
           AND NEW.entry_fill_session_date = OLD.entry_fill_session_date
           AND NEW.cited_run_ts_raw = OLD.cited_run_ts_raw
           AND NEW.cited_recommendation_snapshot_json = OLD.cited_recommendation_snapshot_json
           AND NEW.cited_candidate_snapshot_json = OLD.cited_candidate_snapshot_json
           AND NEW.derivation_rule_version = OLD.derivation_rule_version
           AND NEW.pre_value_json = OLD.pre_value_json
           AND NEW.applied_value_json = OLD.applied_value_json
           AND NEW.corrected_fields_json = OLD.corrected_fields_json
           AND NEW.applied_at = OLD.applied_at
           AND NEW.applied_by = OLD.applied_by
           AND NEW.correction_reason = OLD.correction_reason
           -- the SIX 22-A columns
           AND NEW.admission_tier IS OLD.admission_tier
           AND NEW.cited_latch_link_id IS OLD.cited_latch_link_id
           AND NEW.cited_latch_validity_intent_id IS OLD.cited_latch_validity_intent_id
           AND NEW.cited_latch_place_intent_id IS OLD.cited_latch_place_intent_id
           AND NEW.cited_latch_broker_order_id IS OLD.cited_latch_broker_order_id
           AND NEW.cited_latch_probe_json IS OLD.cited_latch_probe_json
)
BEGIN
    SELECT RAISE(ABORT, 'provenance_corrections is APPEND-ONLY: the only permitted UPDATE is the FK-driven nulling of entry_fill_id or risk_policy_id_at_correction. V1 records provenance ONCE per trade and there is no re-correction path.');
END;


-- ============================================================================
-- THE REPLACE BYPASS ON provenance_corrections (Codex 22A-R3-11, VERIFIED BY
-- EXECUTION 2026-08-25 -- the FOURTH confirmed member of the family and the
-- one on Demand C's own audit table of record).
--
-- 0036 gives this table an append-only UPDATE trigger and an append-only
-- DELETE trigger and NO no_replace. MEASURED at production settings
-- (recursive_triggers default OFF) against the real correction shape, which
-- carries TWO conflict targets -- provenance_correction_id INTEGER PRIMARY KEY
-- AUTOINCREMENT and the UNIQUE index ux_provenance_corrections_trade:
--
--   control UPDATE      -> BLOCKED ("provenance_corrections is APPEND-ONLY")
--   control DELETE      -> BLOCKED ("a correction cannot be deleted")
--   INSERT OR REPLACE   -> SUCCEEDS: correction_reason rewritten in place
--   bare REPLACE        -> SUCCEEDS: same
--
-- with BOTH append-only triggers present, canonical and UNFIRED. The DELETE
-- trigger is bypassed because REPLACE's implicit DELETE does not fire DELETE
-- triggers unless PRAGMA recursive_triggers is ON; it is OFF by default and
-- this repo never turns it on.
--
-- WHY IT IS WORSE HERE THAN ALMOST ANYWHERE. This is the audit table of
-- record: every row is a claim about WHY a trade's cohort keys were changed,
-- and the whole point of 0036's two triggers is that such a claim can never be
-- edited. A REPLACE through the UNIQUE additionally MOVES the correction's own
-- id, which any citation of it then silently repoints -- the id-reuse class
-- 0036's AUTOINCREMENT was chosen to avoid, arriving through the other door.
--
-- BOTH CONFLICT TARGETS ARE SCOPED. Guarding one leaves the other live.
--
-- NO PRODUCTION BEHAVIOUR CHANGE, and the search that establishes it:
-- insert_provenance_correction (swing/data/repos/provenance_corrections.py) is
-- the ONE writer and issues a PLAIN INSERT with no ON CONFLICT clause, and
-- correct_cohort_provenance refuses a second correction per trade at its own
-- SELECT-first ladder before reaching it. A case-insensitive grep for
-- "insert or replace|replace into" across swing/ (*.py, *.sql) returns ZERO
-- executable statements. The production writer is pinned by a test that drives
-- correct_cohort_provenance on a SECOND trade and asserts the append lands.
-- ============================================================================
CREATE TRIGGER trg_pc_no_replace BEFORE INSERT ON provenance_corrections
WHEN EXISTS (SELECT 1 FROM provenance_corrections
              WHERE (NEW.provenance_correction_id != -1
                     AND provenance_correction_id = NEW.provenance_correction_id)
                 OR trade_id = NEW.trade_id)
BEGIN SELECT RAISE(ABORT, '22-A barrier trg_pc_no_replace: provenance_corrections is APPEND-ONLY. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE) would DELETE the existing correction, bypassing trg_provenance_corrections_append_only_delete at the default PRAGMA recursive_triggers=OFF, and rewrite or renumber the audit row of record for this trade. V1 records provenance ONCE per trade and has no re-correction path. To retire the barrier see the reversibility header of 0037_latch_order_mandate_links.sql.'); END;

-- Schema version bump. MUST be the FINAL statement before COMMIT per the
-- Phase 9 section A.0 precedent (a truncated transaction would leave the
-- version stamp ahead of the schema).
UPDATE schema_version SET version = 37;

COMMIT;
