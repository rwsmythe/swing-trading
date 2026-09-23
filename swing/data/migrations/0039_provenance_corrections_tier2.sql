-- 0039_provenance_corrections_tier2.sql
-- 22-A2 (PROOF MACHINERY): the third admission tier `latch_ladder_tier2` and
-- the seventh citation column `cited_frozen_value_evidence_json`.
-- A TABLE REBUILD of provenance_corrections (the 0031/0033 precedent), ruled by
-- CHARC as F12 = (A) under SIX binding conditions (22-A2 ledger R0.12). Atomic
-- via explicit BEGIN; ... COMMIT; per gotcha #9; the runner holds
-- foreign_keys=OFF. Bumps schema_version 38 -> 39.
--
-- WHY A REBUILD. The tier enum is a COLUMN-LEVEL CHECK stored inside the
-- table's DDL (0037 added it by ADD COLUMN), and SQLite 3.50.4 cannot widen a
-- CHECK by ALTER (measured: `ALTER ... DROP CONSTRAINT` and `ALTER COLUMN ...
-- DROP CHECK` are syntax errors). No additive statement can admit a third
-- value. The rebuild RELAXES NOTHING: every CHECK is carried verbatim; the one
-- enum 0037's own comment declared incomplete is widened; the carved seventh
-- column is appended.
--
-- ============================================================================
-- REVERSIBILITY HEADER (F12 condition 5)
-- ============================================================================
-- THE THREE TEXTUAL EDITS. The v39 stored DDL of provenance_corrections is the
-- STORED v38 DDL (sqlite_master.sql on a v38 database) with EXACTLY:
--   (1) the name token: `CREATE TABLE provenance_corrections (` becomes
--       `CREATE TABLE "provenance_corrections" (` -- SQLite's own RENAME
--       rendering, because the table is created under a scratch name below
--       and renamed;
--   (2) the tier IN-list widened: `('last_word', 'latch_ladder')` becomes
--       `('last_word', 'latch_ladder', 'latch_ladder_tier2')`;
--   (3) `, cited_frozen_value_evidence_json TEXT` appended as the LAST COLUMN,
--       directly after `cited_latch_probe_json TEXT` and before the
--       table-level CHECKs (where SQLite's own ADD COLUMN would have put it).
-- tests/data/test_migration_0039_provenance_corrections_tier2.py applies these
-- three edits to a v38 image's stored text and asserts BYTEWISE equality.
--
-- THE GATE ROW (P28). swing/data/db.py carries
--   BackupGateSpec(38, "22a2", PHASE22_ARC_A2_PRE_MIGRATION_EXPECTED_TABLES,
--                  "_phase22_arc_a2_backup_gate", "pre-22-A2")
-- so a database at v38 migrated to any target >= 39 writes the image
-- swing-pre-22a2-migration-<UTC>Z.db before this file runs, and the
-- db-migrate CLI echoes its path.
--
-- THE SEVEN OBJECTS dropped (the table takes its six dependants with it) and
-- re-created here: the table; ux_provenance_corrections_trade and
-- ix_provenance_corrections_cited_candidate (VERBATIM, 0036);
-- trg_provenance_corrections_append_only_delete (VERBATIM, 0036);
-- trg_pc_no_replace (VERBATIM, 0037); trg_provenance_corrections_append_only_update
-- (0037 + the seventh column); trg_provenance_corrections_citation_graph (0037 +
-- the 22-A2 edits). No object outside the table references it.
--
-- THE REVERSE is another rebuild, to the v38 DDL (the three edits undone) with
-- the two changed triggers restored to their 0037 text -- LEGAL ONLY WHILE NO
-- `latch_ladder_tier2` ROW EXISTS, because the v38 CHECK would reject it and the
-- seventh column's data has nowhere to go. A reverse is itself a new numbered
-- migration, never a hand edit.
--
-- THE GRAMMAR-BUMP OBLIGATION (CHARC G-T7F-AMEND, RD's second facet; D60).
-- The seventh blob carries TWO versions. `$.evidence_version` is the blob's
-- GRAMMAR (the key roster, the types, the bindings) and is pinned by LITERAL
-- in the citation trigger below, mirroring the Python
-- FROZEN_VALUE_EVIDENCE_VERSION; `$.derivation_version` is the version of the
-- CODE the values are a function of (FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION,
-- bound to an AST digest by test) and is typed TEXT here, never bound, so a
-- derivation bump needs NO migration. A FUTURE MIGRATION THAT BUMPS THE
-- GRAMMAR VERSION MUST DECLARE, AS PART OF THAT MIGRATION, HOW THE PRE-EXISTING
-- `latch_ladder_tier2` ROWS REPLAY: EITHER a per-version recompute adapter
-- (the read-time replay re-derives an old-grammar row under its own grammar),
-- OR a declared exclusion with its reason (those rows read excluded and named,
-- never admitted on the stored grade). The composition that migration's gate
-- reads is CODE x THE LIVE ROWS, not only CODE x THE LIVE SCHEMA: the trigger
-- guards only the rows written after it, and the rows already written are
-- replayed by code that no longer speaks their grammar.
--
-- THE D51 MANIFEST DIFF (condition 4) reads exactly FOUR changed line pairs --
-- `# schema_version`, `table provenance_corrections`, and the two changed
-- triggers -- and ZERO deletions. Any other changed or deleted line is an
-- object this rebuild forgot.
-- ============================================================================

BEGIN;

-- 1. The new table: the STORED v38 DDL with edits 2 and 3 applied and the
--    name token set to the scratch name (edit 1 is SQLite's RENAME below).
CREATE TABLE provenance_corrections__0039 (
    provenance_correction_id INTEGER PRIMARY KEY AUTOINCREMENT,

    trade_id      INTEGER NOT NULL REFERENCES trades(id)      ON DELETE RESTRICT,
    -- ON DELETE SET NULL, NOT RESTRICT (Codex R7 Major 1). RESTRICT would make
    -- cohort bookkeeping BLOCK a supported money-bearing operation: the
    -- production `split_into_partials` handler DELETEs the consolidated fill
    -- (`reconciliation_auto_correct.py:2926`, `DELETE FROM fills WHERE
    -- fill_id = ?`), including entry fills, and two shipped tests protect that
    -- capability. After a provenance correction existed, a legitimate
    -- date-preserving execution-grain split of the cited fill would die on an
    -- FK IntegrityError -- the exact priority inversion the plan's section
    -- 3.1.3 says must be avoided, introduced by the plan two sections later.
    -- Migration 0035 already set the precedent: its own `fill_id` reference is
    -- ON DELETE SET NULL. The PROVENANCE survives the delete in the frozen
    -- snapshot below; the pointer is a convenience and is allowed to go NULL.
    entry_fill_id INTEGER REFERENCES fills(fill_id) ON DELETE SET NULL,
    -- THE FROZEN NUMBER (Codex R9 Major 2). `entry_fill_id` goes NULL the
    -- moment the fill is deleted, so it CANNOT be the thing the snapshot is
    -- checked against -- after a split, the JSON would be the only surviving
    -- identity and nothing would ever have bound it to the fill actually used.
    -- A plain NOT NULL scalar with NO FK survives the delete and is what the
    -- snapshot CHECK pins.
    --
    -- IT IS NOT AN IMMUTABLE *IDENTITY*, and round 9 called it one (Codex R11
    -- Major 1). `fills.fill_id` is INTEGER PRIMARY KEY WITHOUT AUTOINCREMENT
    -- (`0014_phase7_state_machine_and_fills.sql`) -- a bare rowid -- so SQLite
    -- REUSES the number when the deleted row held the maximum. Verified: a
    -- date-preserving split of the max fill reinserts a partial that comes
    -- back wearing the SAME fill_id with the SAME fill_datetime. The NUMBER is
    -- durable; the ROW is not. Deletion is therefore detected from
    -- `entry_fill_id IS NULL` (which an INSERT does not restore, also
    -- verified), never from the number matching.
    entry_fill_id_at_correction INTEGER NOT NULL,
    -- The fill's identity, owner, role and datetime frozen verbatim, so a
    -- deleted or replaced fill leaves the audit row still able to say WHAT it
    -- anchored on -- and able to PROVE it was that fill.
    entry_fill_snapshot_json TEXT NOT NULL,

    -- THE CITATION. NOT NULL is the evidence rule made structural: the schema
    -- refuses a correction that does not name the records it derives from.
    -- ON DELETE RESTRICT (not CASCADE, not SET NULL): an audit row whose
    -- citation can vanish is not a citation, and RESTRICT matches the
    -- latch_view_events.candidate_id precedent from migration 0033.
    cited_candidate_id            INTEGER NOT NULL REFERENCES candidates(id)             ON DELETE RESTRICT,
    cited_daily_recommendation_id INTEGER NOT NULL REFERENCES daily_recommendations(id)  ON DELETE RESTRICT,
    cited_evaluation_run_id       INTEGER NOT NULL REFERENCES evaluation_runs(id)        ON DELETE RESTRICT,

    -- THE HYPOTHESIS ASSIGNMENT'S OWN PROVENANCE (Codex R1 Critical 1). The
    -- matcher filters on registry `status`, which is MUTABLE, so the derived
    -- hypothesis is only as contemporaneous as the status it was evaluated
    -- against. The interval that made it active is cited structurally.
    cited_hypothesis_id                INTEGER NOT NULL REFERENCES hypothesis_registry(id)              ON DELETE RESTRICT,
    cited_hypothesis_status_history_id INTEGER NOT NULL REFERENCES hypothesis_status_history(history_id) ON DELETE RESTRICT,
    cited_hypothesis_status_at_record  TEXT NOT NULL,
    -- The interval must cover the WHOLE uncertainty window, because run_ts is
    -- the run's START and the record is persisted later (14m19s on the live
    -- CADL run). Both bounds are frozen so the window this correction actually
    -- proved is legible without re-deriving it.
    -- FOUR clock columns, each with ONE job (Codex R6 Critical 1). The _raw
    -- pair is naive LOCAL verbatim from the source rows; the _utc pair is the
    -- normalized form. History timestamps are compared ONLY against _utc; the
    -- pipeline snapshot is validated ONLY against _raw. Storing one pair and
    -- pretending it serves both is what round 5 did.
    cited_pipeline_finished_ts_raw     TEXT NOT NULL,
    cited_run_ts_utc                   TEXT NOT NULL,
    cited_status_window_upper_utc      TEXT NOT NULL,
    -- The pipeline row that SUPPLIED that upper bound, cited rather than merely
    -- consulted: pipeline_runs.evaluation_run_id is a nullable NON-UNIQUE FK, so
    -- "exactly one complete row" is unrecoverable after the fact without this.
    cited_pipeline_run_id              INTEGER NOT NULL REFERENCES pipeline_runs(id) ON DELETE RESTRICT,
    cited_pipeline_run_snapshot_json   TEXT NOT NULL,
    -- recorded_at of the cited interval. An interval recorded AFTER run_ts is a
    -- RETROSPECTIVE assertion (migration 0017 backdated its seeds) and the
    -- service REFUSES it; this column makes the admitted ones checkable.
    cited_hypothesis_status_recorded_at TEXT NOT NULL,
    -- THE CITED INTERVAL'S OWN BOUNDS, FROZEN (Codex R1 Major 4). The FK pins
    -- WHICH history row was cited; it does nothing about that row CHANGING.
    -- `update_close_open_interval` writes `effective_to` IN PLACE on every
    -- supported status transition (`repos/hypothesis_status_history.py:66`),
    -- so without these the drift reader had nothing to compare and printed
    -- "no citation drift" after a real, supported mutation of the very row the
    -- correction's authority rests on. `_to` is NULL for a still-open
    -- interval, which is the shape the live H1 row has.
    cited_hypothesis_status_effective_from TEXT NOT NULL,
    cited_hypothesis_status_effective_to   TEXT,
    -- The registry NAME as spelled when the label was written. The FK above is
    -- the identity; this is the join-key rendering (plan section 3.4.1a).
    cited_hypothesis_name_at_correction TEXT NOT NULL,

    -- THE ANCHORS AS EVALUATED, FROZEN AT WRITE TIME (#30 applied to this
    -- table itself): per-row provenance is carried, not re-derived later. A
    -- reader must never have to re-join to learn what this correction claimed.
    cited_candidate_action_session_date      TEXT NOT NULL,
    cited_recommendation_action_session_date TEXT NOT NULL,
    entry_fill_session_date                  TEXT NOT NULL,
    cited_run_ts_raw                         TEXT NOT NULL,

    -- The cited daily_recommendations row is MUTABLE IN PLACE (Codex R1
    -- Critical 2; `upsert_recommendation` DO UPDATE SET rewrites even
    -- `evaluation_run_id`). RESTRICT stops it disappearing and does nothing
    -- about it changing, so its content at authorization is frozen here and
    -- drift is REPORTED by the read command.
    cited_recommendation_snapshot_json TEXT NOT NULL,
    -- THE CITED CANDIDATE'S DERIVATION-BEARING CONTENT, FROZEN (Codex R4
    -- Major 3). Re-deriving the label ALONE is not enough:
    -- `_non_pass_criterion_names` observes only the SET OF NAMES whose result
    -- is not `pass`, so flipping the live CADL case's `TT8_rs_rank` from `na`
    -- to `fail` leaves that set -- and the label -- UNCHANGED, while the
    -- correction's stored reason specifically records the `na` evidence.
    -- Criterion `value` / `rule` / `layer` changes and the deletion of a
    -- PASSING criterion are invisible the same way. The reader does BOTH:
    -- re-derives (catches meaning) and compares this (catches content).
    cited_candidate_snapshot_json TEXT NOT NULL,

    -- The label format and the na-counts-as-non-pass rule are CODE, not data,
    -- so no FK can pin them; the version constant makes a later change visible
    -- (and a sha256 source pin makes bumping it non-optional).
    derivation_rule_version TEXT NOT NULL,

    pre_value_json        TEXT NOT NULL,
    applied_value_json    TEXT NOT NULL,
    corrected_fields_json TEXT NOT NULL,

    applied_at        TEXT NOT NULL,
    applied_by        TEXT NOT NULL,
    correction_reason TEXT NOT NULL,

    risk_policy_id_at_correction INTEGER REFERENCES risk_policy(policy_id) ON DELETE SET NULL, admission_tier TEXT NOT NULL
    DEFAULT 'last_word' CHECK (admission_tier IN ('last_word', 'latch_ladder', 'latch_ladder_tier2')), cited_latch_link_id INTEGER
    REFERENCES latch_order_mandate_links(link_id) ON DELETE RESTRICT, cited_latch_validity_intent_id INTEGER
    REFERENCES latch_order_intents(intent_id) ON DELETE RESTRICT, cited_latch_place_intent_id INTEGER
    REFERENCES latch_order_intents(intent_id) ON DELETE RESTRICT, cited_latch_broker_order_id TEXT, cited_latch_probe_json TEXT, cited_frozen_value_evidence_json TEXT,

    -- Three-predicate date guards, per migration 0033's own lesson: a SQLite
    -- CHECK PASSES when its expression is NULL, so date('2026-99-99') IS NULL
    -- accepts a length-correct invalid date. Round-trip equality catches the
    -- NORMALISING case, IS NOT NULL catches the INVALID case, and the year
    -- floor catches year zero (which SQLite round-trips and Python's
    -- date.fromisoformat RAISES on -- the DB holding a row the read path
    -- cannot hydrate).
    CHECK (date(cited_candidate_action_session_date) IS NOT NULL
           AND date(cited_candidate_action_session_date) = cited_candidate_action_session_date
           AND cited_candidate_action_session_date >= '1900-01-01'),
    CHECK (date(cited_recommendation_action_session_date) IS NOT NULL
           AND date(cited_recommendation_action_session_date) = cited_recommendation_action_session_date
           AND cited_recommendation_action_session_date >= '1900-01-01'),
    CHECK (date(entry_fill_session_date) IS NOT NULL
           AND date(entry_fill_session_date) = entry_fill_session_date
           AND entry_fill_session_date >= '1900-01-01'),

    -- CONTEMPORANEITY, ENFORCED BY THE SCHEMA. A cross-TABLE comparison cannot
    -- be a SQLite CHECK -- but FREEZING the anchors onto this row (above)
    -- makes it INTRA-row, and an intra-row CHECK is exactly what SQLite does
    -- enforce. This does NOT replace the service-layer gate, whose job is to
    -- prove the frozen values equal the cited rows' actual columns; it makes a
    -- correction row that ASSERTS a post-dating citation physically
    -- un-INSERTable.
    CHECK (cited_candidate_action_session_date      <= entry_fill_session_date),
    CHECK (cited_recommendation_action_session_date <= entry_fill_session_date),

    -- EVERY AUDIT TIMESTAMP HAS A GRAMMAR, not merely an ORDERING (Codex R2
    -- Major 2). The ordering CHECKs below are LEXICAL, so before these guards
    -- a row carrying 'aaa' / 'bbb' / 'ccc' / 'zzz' as its four clock columns
    -- satisfied every one of them and INSERTed cleanly -- an audit row whose
    -- window is not a window. GLOB is this repo's established grammar idiom
    -- for a TEXT date column (`0029_cash_reconciliation.sql:16`).
    --
    -- The shape is `YYYY-MM-DDTHH:MM:SS` with an OPTIONAL `.` + 1-6 digits,
    -- and nothing else: no offset, no `Z`, no space separator, no trailing
    -- junk. `datetime(substr(...,1,19))` then rejects an impossible calendar
    -- value that the digit-shape alone would accept ('2026-99-99T00:00:00').
    -- The NOT-GLOB clause is what stops `substr(x,21) GLOB '[0-9]*'` from
    -- accepting `.5abc` -- a leading-digit test says nothing about the rest.
    CHECK (
        (cited_run_ts_raw GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
         OR (length(cited_run_ts_raw) BETWEEN 21 AND 26
             AND substr(cited_run_ts_raw,1,19) GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
             AND substr(cited_run_ts_raw,20,1) = '.'
             AND substr(cited_run_ts_raw,21) NOT GLOB '*[^0-9]*'))
        -- ROUND-TRIP, not `IS NOT NULL` (Codex R3 Major 5). SQLite
        -- NORMALISES an impossible date rather than returning NULL:
        -- datetime('2026-02-30T00:00:00') is '2026-03-02 00:00:00', so
        -- the row INSERTed and then CRASHED the supported reader at
        -- hydration. Verified at the prompt: the round-trip catches
        -- Feb 30, but SQLite HAPPILY ECHOES hour 24 and year zero --
        -- both of which Python's fromisoformat RAISES on -- so the hour
        -- bound and the year floor are separately load-bearing.
        AND datetime(substr(cited_run_ts_raw,1,19))
                = replace(substr(cited_run_ts_raw,1,19),'T',' ')
        AND substr(cited_run_ts_raw,1,4) >= '1900'
        AND substr(cited_run_ts_raw,12,2) <= '23'),
    CHECK (
        (cited_pipeline_finished_ts_raw GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
         OR (length(cited_pipeline_finished_ts_raw) BETWEEN 21 AND 26
             AND substr(cited_pipeline_finished_ts_raw,1,19) GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
             AND substr(cited_pipeline_finished_ts_raw,20,1) = '.'
             AND substr(cited_pipeline_finished_ts_raw,21) NOT GLOB '*[^0-9]*'))
        -- ROUND-TRIP, not `IS NOT NULL` (Codex R3 Major 5). SQLite
        -- NORMALISES an impossible date rather than returning NULL:
        -- datetime('2026-02-30T00:00:00') is '2026-03-02 00:00:00', so
        -- the row INSERTed and then CRASHED the supported reader at
        -- hydration. Verified at the prompt: the round-trip catches
        -- Feb 30, but SQLite HAPPILY ECHOES hour 24 and year zero --
        -- both of which Python's fromisoformat RAISES on -- so the hour
        -- bound and the year floor are separately load-bearing.
        AND datetime(substr(cited_pipeline_finished_ts_raw,1,19))
                = replace(substr(cited_pipeline_finished_ts_raw,1,19),'T',' ')
        AND substr(cited_pipeline_finished_ts_raw,1,4) >= '1900'
        AND substr(cited_pipeline_finished_ts_raw,12,2) <= '23'),
    CHECK (
        (cited_run_ts_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
         OR (length(cited_run_ts_utc) BETWEEN 21 AND 26
             AND substr(cited_run_ts_utc,1,19) GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
             AND substr(cited_run_ts_utc,20,1) = '.'
             AND substr(cited_run_ts_utc,21) NOT GLOB '*[^0-9]*'))
        -- ROUND-TRIP, not `IS NOT NULL` (Codex R3 Major 5). SQLite
        -- NORMALISES an impossible date rather than returning NULL:
        -- datetime('2026-02-30T00:00:00') is '2026-03-02 00:00:00', so
        -- the row INSERTed and then CRASHED the supported reader at
        -- hydration. Verified at the prompt: the round-trip catches
        -- Feb 30, but SQLite HAPPILY ECHOES hour 24 and year zero --
        -- both of which Python's fromisoformat RAISES on -- so the hour
        -- bound and the year floor are separately load-bearing.
        AND datetime(substr(cited_run_ts_utc,1,19))
                = replace(substr(cited_run_ts_utc,1,19),'T',' ')
        AND substr(cited_run_ts_utc,1,4) >= '1900'
        AND substr(cited_run_ts_utc,12,2) <= '23'),
    CHECK (
        (cited_status_window_upper_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
         OR (length(cited_status_window_upper_utc) BETWEEN 21 AND 26
             AND substr(cited_status_window_upper_utc,1,19) GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
             AND substr(cited_status_window_upper_utc,20,1) = '.'
             AND substr(cited_status_window_upper_utc,21) NOT GLOB '*[^0-9]*'))
        -- ROUND-TRIP, not `IS NOT NULL` (Codex R3 Major 5). SQLite
        -- NORMALISES an impossible date rather than returning NULL:
        -- datetime('2026-02-30T00:00:00') is '2026-03-02 00:00:00', so
        -- the row INSERTed and then CRASHED the supported reader at
        -- hydration. Verified at the prompt: the round-trip catches
        -- Feb 30, but SQLite HAPPILY ECHOES hour 24 and year zero --
        -- both of which Python's fromisoformat RAISES on -- so the hour
        -- bound and the year floor are separately load-bearing.
        AND datetime(substr(cited_status_window_upper_utc,1,19))
                = replace(substr(cited_status_window_upper_utc,1,19),'T',' ')
        AND substr(cited_status_window_upper_utc,1,4) >= '1900'
        AND substr(cited_status_window_upper_utc,12,2) <= '23'),
    CHECK (
        (cited_hypothesis_status_recorded_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
         OR (length(cited_hypothesis_status_recorded_at) BETWEEN 21 AND 26
             AND substr(cited_hypothesis_status_recorded_at,1,19) GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
             AND substr(cited_hypothesis_status_recorded_at,20,1) = '.'
             AND substr(cited_hypothesis_status_recorded_at,21) NOT GLOB '*[^0-9]*'))
        -- ROUND-TRIP, not `IS NOT NULL` (Codex R3 Major 5). SQLite
        -- NORMALISES an impossible date rather than returning NULL:
        -- datetime('2026-02-30T00:00:00') is '2026-03-02 00:00:00', so
        -- the row INSERTed and then CRASHED the supported reader at
        -- hydration. Verified at the prompt: the round-trip catches
        -- Feb 30, but SQLite HAPPILY ECHOES hour 24 and year zero --
        -- both of which Python's fromisoformat RAISES on -- so the hour
        -- bound and the year floor are separately load-bearing.
        AND datetime(substr(cited_hypothesis_status_recorded_at,1,19))
                = replace(substr(cited_hypothesis_status_recorded_at,1,19),'T',' ')
        AND substr(cited_hypothesis_status_recorded_at,1,4) >= '1900'
        AND substr(cited_hypothesis_status_recorded_at,12,2) <= '23'),
    CHECK (
        (cited_hypothesis_status_effective_from GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
         OR (length(cited_hypothesis_status_effective_from) BETWEEN 21 AND 26
             AND substr(cited_hypothesis_status_effective_from,1,19) GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
             AND substr(cited_hypothesis_status_effective_from,20,1) = '.'
             AND substr(cited_hypothesis_status_effective_from,21) NOT GLOB '*[^0-9]*'))
        -- ROUND-TRIP, not `IS NOT NULL` (Codex R3 Major 5). SQLite
        -- NORMALISES an impossible date rather than returning NULL:
        -- datetime('2026-02-30T00:00:00') is '2026-03-02 00:00:00', so
        -- the row INSERTed and then CRASHED the supported reader at
        -- hydration. Verified at the prompt: the round-trip catches
        -- Feb 30, but SQLite HAPPILY ECHOES hour 24 and year zero --
        -- both of which Python's fromisoformat RAISES on -- so the hour
        -- bound and the year floor are separately load-bearing.
        AND datetime(substr(cited_hypothesis_status_effective_from,1,19))
                = replace(substr(cited_hypothesis_status_effective_from,1,19),'T',' ')
        AND substr(cited_hypothesis_status_effective_from,1,4) >= '1900'
        AND substr(cited_hypothesis_status_effective_from,12,2) <= '23'),
    CHECK (cited_hypothesis_status_effective_to IS NULL OR (
        (cited_hypothesis_status_effective_to GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
         OR (length(cited_hypothesis_status_effective_to) BETWEEN 21 AND 26
             AND substr(cited_hypothesis_status_effective_to,1,19) GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
             AND substr(cited_hypothesis_status_effective_to,20,1) = '.'
             AND substr(cited_hypothesis_status_effective_to,21) NOT GLOB '*[^0-9]*'))
        -- ROUND-TRIP, not `IS NOT NULL` (Codex R3 Major 5). SQLite
        -- NORMALISES an impossible date rather than returning NULL:
        -- datetime('2026-02-30T00:00:00') is '2026-03-02 00:00:00', so
        -- the row INSERTed and then CRASHED the supported reader at
        -- hydration. Verified at the prompt: the round-trip catches
        -- Feb 30, but SQLite HAPPILY ECHOES hour 24 and year zero --
        -- both of which Python's fromisoformat RAISES on -- so the hour
        -- bound and the year floor are separately load-bearing.
        AND datetime(substr(cited_hypothesis_status_effective_to,1,19))
                = replace(substr(cited_hypothesis_status_effective_to,1,19),'T',' ')
        AND substr(cited_hypothesis_status_effective_to,1,4) >= '1900'
        AND substr(cited_hypothesis_status_effective_to,12,2) <= '23')),
    CHECK (
        (applied_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
         OR (length(applied_at) BETWEEN 21 AND 26
             AND substr(applied_at,1,19) GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
             AND substr(applied_at,20,1) = '.'
             AND substr(applied_at,21) NOT GLOB '*[^0-9]*'))
        -- ROUND-TRIP, not `IS NOT NULL` (Codex R3 Major 5). SQLite
        -- NORMALISES an impossible date rather than returning NULL:
        -- datetime('2026-02-30T00:00:00') is '2026-03-02 00:00:00', so
        -- the row INSERTed and then CRASHED the supported reader at
        -- hydration. Verified at the prompt: the round-trip catches
        -- Feb 30, but SQLite HAPPILY ECHOES hour 24 and year zero --
        -- both of which Python's fromisoformat RAISES on -- so the hour
        -- bound and the year floor are separately load-bearing.
        AND datetime(substr(applied_at,1,19))
                = replace(substr(applied_at,1,19),'T',' ')
        AND substr(applied_at,1,4) >= '1900'
        AND substr(applied_at,12,2) <= '23'),

    -- The window is well-formed in BOTH domains, compared within each. These
    -- ORDERINGS are lexical and are only meaningful because the GRAMMAR guards
    -- above force a fixed-width canonical form, under which lexical order IS
    -- chronological order.
    CHECK (cited_run_ts_raw <= cited_pipeline_finished_ts_raw),
    CHECK (cited_run_ts_utc <= cited_status_window_upper_utc),
    -- The admitted status interval was on record by the START of the window.
    -- The evidence rule made structural: a retrospective interval cannot be
    -- filed at all, not merely flagged. `recorded_at` is naive UTC, so it is
    -- compared against the UTC bound and NEVER against the raw local one --
    -- that comparison would be wrong by ten hours.
    CHECK (cited_hypothesis_status_recorded_at <= cited_run_ts_utc),

    -- THE THREE SNAPSHOTS ARE PINNED IN SQL, NOT ONLY IN `__post_init__`
    -- (Codex R7 Major 2). The tests require RAW INSERTs of `{}`, malformed
    -- JSON and wrong-id snapshots to be REJECTED -- and a raw INSERT never
    -- constructs the dataclass, so a `__post_init__`-only design would accept
    -- every one of them.
    --
    -- THE `CASE WHEN json_valid(...) THEN COALESCE(<all predicates>, 0) ELSE 0
    -- END` FORM IS MANDATORY, and two weaker drafts were wrong (Codex R7 M2,
    -- R8 M1). A SQLite CHECK PASSES when its expression is NULL.
    -- `json_extract('{}','$.id')` is NULL, so the bare form ACCEPTED `{}`;
    -- adding `IS NOT NULL` on `$.id` ALONE then still ACCEPTED the PARTIAL
    -- object `{"id":172}`, because the remaining comparisons went NULL --
    -- existence != completeness, inside the fix for it. `COALESCE(..., 0)`
    -- collapses every NULL to a failure at once, and the `CASE WHEN
    -- json_valid` gate is this repo's established malformed-JSON pattern
    -- (`0033_latch_order_intents.sql`, whose exception-TYPE contract
    -- `tests/data/test_migration_0033.py` pins).
    CHECK (CASE WHEN json_valid(cited_recommendation_snapshot_json) THEN COALESCE(
               json_extract(cited_recommendation_snapshot_json, '$.id')
                   = cited_daily_recommendation_id
           AND json_extract(cited_recommendation_snapshot_json, '$.evaluation_run_id')
                   = cited_evaluation_run_id
           AND json_extract(cited_recommendation_snapshot_json, '$.action_session_date')
                   = cited_recommendation_action_session_date, 0)
           ELSE 0 END),
    CHECK (CASE WHEN json_valid(cited_pipeline_run_snapshot_json) THEN COALESCE(
               json_extract(cited_pipeline_run_snapshot_json, '$.id')
                   = cited_pipeline_run_id
           AND json_extract(cited_pipeline_run_snapshot_json, '$.evaluation_run_id')
                   = cited_evaluation_run_id
           AND json_extract(cited_pipeline_run_snapshot_json, '$.state') = 'complete'
           AND json_extract(cited_pipeline_run_snapshot_json, '$.finished_ts')
                   = cited_pipeline_finished_ts_raw, 0)
           ELSE 0 END),
    -- The snapshot must BE the fill this correction anchored on -- id, owner
    -- and role, not merely a well-formed object (Codex R9 Major 2). Without
    -- the id equality, `entry_fill_id=45` with snapshot `{"fill_id":999,...}`
    -- passed BOTH layers and the audit would durably assert contemporaneity
    -- against a fill it never used.
    CHECK (CASE WHEN json_valid(entry_fill_snapshot_json) THEN COALESCE(
               json_extract(entry_fill_snapshot_json, '$.fill_id')
                   = entry_fill_id_at_correction
           AND json_extract(entry_fill_snapshot_json, '$.trade_id') = trade_id
           AND json_extract(entry_fill_snapshot_json, '$.action') = 'entry'
           AND json_extract(entry_fill_snapshot_json, '$.fill_datetime') IS NOT NULL
           AND substr(json_extract(entry_fill_snapshot_json, '$.fill_datetime'), 1, 10)
                   = entry_fill_session_date, 0)
           ELSE 0 END),
    -- The convenience FK, while it still points anywhere, must point at the
    -- same fill the frozen scalar names.
    CHECK (entry_fill_id IS NULL OR entry_fill_id = entry_fill_id_at_correction),

    -- The cited interval must itself be well-formed and must COVER the frozen
    -- window it is cited as covering. Intra-row, so SQLite enforces it.
    -- COVERAGE IS COMPARED AT SECOND GRANULARITY, STRICTLY, AT BOTH ENDS
    -- (Codex R3 Major 2). The grammar admits 0-6 fractional digits, and a
    -- LEXICAL comparison across differing precisions is wrong: verified,
    -- '2026-08-11T03:44:45.0' > '2026-08-11T03:44:45' is TRUE although they
    -- are the SAME INSTANT and the half-open interval does not cover the
    -- bound. Truncating to `substr(...,1,19)` removes the precision axis
    -- entirely, and STRICT at both ends is the conservative direction: an
    -- interval that starts or ends inside the window's own boundary SECOND
    -- has not been shown to cover it. The model mirrors this comparison
    -- EXACTLY, so the two layers accept the same set.
    CHECK (substr(cited_hypothesis_status_effective_from,1,19)
           < substr(cited_run_ts_utc,1,19)),
    CHECK (cited_hypothesis_status_effective_to IS NULL
           OR substr(cited_hypothesis_status_effective_to,1,19)
              > substr(cited_status_window_upper_utc,1,19)),

    -- THE VALUE ENVELOPES ARE PINNED TOO (Codex R1 Major 3). Without these,
    -- `pre_value_json` / `applied_value_json` / `corrected_fields_json` were
    -- unconstrained TEXT: a row could claim ONE corrected field, carry
    -- malformed or empty value JSON, or declare an applied candidate
    -- UNRELATED to `cited_candidate_id` -- an audit row that does not describe
    -- its own correction, in the one ledger this arc exists to keep honest.
    -- Same `CASE WHEN json_valid(...) THEN COALESCE(..., 0) ELSE 0 END` form
    -- as the snapshots above, for the same NULL-passes-a-CHECK reason.
    --
    -- EXACTLY the three coupled fields IN ORDER, not a subset: this surface
    -- writes all three together or none, and a row claiming fewer would assert
    -- a partial cohort assignment the service cannot produce.
    --
    -- Written with INDEXED extraction rather than `EXISTS (SELECT ... FROM
    -- json_each(...))`, because SQLite PROHIBITS SUBQUERIES IN CHECK
    -- CONSTRAINTS -- verified at the prompt on 3.50.4 before this was written
    -- down ("subqueries prohibited in CHECK constraints"), which would have
    -- made the whole CREATE TABLE fail rather than merely under-constrain.
    CHECK (CASE WHEN json_valid(corrected_fields_json) THEN COALESCE(
               json_array_length(corrected_fields_json) = 3
           AND json_extract(corrected_fields_json, '$[0]')
                   = 'trades.hypothesis_label'
           AND json_extract(corrected_fields_json, '$[1]')
                   = 'trades.candidate_id'
           AND json_extract(corrected_fields_json, '$[2]')
                   = 'trades.trade_origin', 0)
           ELSE 0 END),
    -- The APPLIED envelope must name the candidate this row CITES. Otherwise
    -- the audit says "I wrote candidate X" while citing candidate Y.
    -- `json_type` rather than `json_extract IS NOT NULL` for the presence
    -- checks: `json_extract` cannot distinguish a JSON null from an ABSENT
    -- key (both give SQL NULL), so a partial envelope would slip through --
    -- the same existence-is-not-completeness trap the snapshot CHECKs above
    -- were rewritten for. Verified: json_type('{}', path) is NULL,
    -- json_type('{"k":null}', path) is 'null', json_type('{"k":"x"}', path)
    -- is 'text'.
    CHECK (CASE WHEN json_valid(applied_value_json) THEN COALESCE(
               json_extract(applied_value_json, '$."trades.candidate_id"')
                   = cited_candidate_id
           AND json_type(applied_value_json, '$."trades.hypothesis_label"')
                   = 'text'
           AND json_type(applied_value_json, '$."trades.trade_origin"')
                   = 'text'
           -- NON-EMPTY, not merely present (Codex R2 Major 2). `json_type =
           -- 'text'` accepts `""`, which the model REJECTS -- so a
           -- schema-valid row existed that the supported reader crashed on
           -- while hydrating. The two layers now accept the same set.
           AND length(trim(json_extract(
                   applied_value_json, '$."trades.hypothesis_label"'))) > 0
           -- THE ORIGIN IS PINNED, not merely non-empty (Codex R4 Major 2).
           -- Binding only `candidate_id` let an audit row cite an A+
           -- candidate with the correct label and
           -- `trade_origin='pipeline_watch_manual'` -- an impossible cohort
           -- assignment that passed BOTH layers. V1 corrects `aplus`
           -- candidates ONLY (the boundary of what is DERIVABLE, not a scope
           -- cut), so `pipeline_aplus` is the only truthful applied origin;
           -- widening it is a V2 migration alongside the entry-side change
           -- that would make a watch correction derivable at all.
           AND json_extract(applied_value_json, '$."trades.trade_origin"')
                   = 'pipeline_aplus', 0)
           ELSE 0 END),
    -- The PRE envelope must record the UNSET state this surface requires as
    -- its precondition -- the correction FILLS empty provenance, so a pre-row
    -- asserting anything else contradicts the gate that let it be written.
    CHECK (CASE WHEN json_valid(pre_value_json) THEN COALESCE(
               json_extract(pre_value_json, '$."trades.trade_origin"')
                   = 'manual_off_pipeline'
           AND json_type(pre_value_json, '$."trades.hypothesis_label"')
                   = 'null'
           AND json_type(pre_value_json, '$."trades.candidate_id"')
                   = 'null', 0)
           ELSE 0 END),

    CHECK (CASE WHEN json_valid(cited_candidate_snapshot_json) THEN COALESCE(
               json_extract(cited_candidate_snapshot_json, '$.id')
                   = cited_candidate_id
           AND json_extract(cited_candidate_snapshot_json, '$.evaluation_run_id')
                   = cited_evaluation_run_id
           AND json_extract(cited_candidate_snapshot_json, '$.bucket')
                   = 'aplus'
           AND json_type(cited_candidate_snapshot_json, '$.criteria')
                   = 'array', 0)
           ELSE 0 END),

    -- The hypothesis NAME must be non-empty in SQL too (Codex R4 Minor 5).
    -- `__post_init__` already rejects an empty or whitespace-only name, so
    -- without this a RAW row inserted cleanly and then made
    -- `list_provenance_corrections` raise during hydration -- aborting the
    -- whole supported CLI report rather than surfacing one bad row.
    CHECK (length(trim(cited_hypothesis_name_at_correction)) > 0),

    CHECK (applied_by = 'operator'),
    CHECK (length(trim(correction_reason)) > 0),
    CHECK (length(trim(derivation_rule_version)) > 0),
    -- The correction may only be recorded on the strength of a hypothesis that
    -- was ACTIVE when the framework wrote the cited record.
    CHECK (cited_hypothesis_status_at_record = 'active')
);

-- 2. Every row, by EXPLICIT column list carrying provenance_correction_id.
INSERT INTO provenance_corrections__0039 (
    provenance_correction_id,
    trade_id,
    entry_fill_id,
    entry_fill_id_at_correction,
    entry_fill_snapshot_json,
    cited_candidate_id,
    cited_daily_recommendation_id,
    cited_evaluation_run_id,
    cited_hypothesis_id,
    cited_hypothesis_status_history_id,
    cited_hypothesis_status_at_record,
    cited_pipeline_finished_ts_raw,
    cited_run_ts_utc,
    cited_status_window_upper_utc,
    cited_pipeline_run_id,
    cited_pipeline_run_snapshot_json,
    cited_hypothesis_status_recorded_at,
    cited_hypothesis_status_effective_from,
    cited_hypothesis_status_effective_to,
    cited_hypothesis_name_at_correction,
    cited_candidate_action_session_date,
    cited_recommendation_action_session_date,
    entry_fill_session_date,
    cited_run_ts_raw,
    cited_recommendation_snapshot_json,
    cited_candidate_snapshot_json,
    derivation_rule_version,
    pre_value_json,
    applied_value_json,
    corrected_fields_json,
    applied_at,
    applied_by,
    correction_reason,
    risk_policy_id_at_correction,
    admission_tier,
    cited_latch_link_id,
    cited_latch_validity_intent_id,
    cited_latch_place_intent_id,
    cited_latch_broker_order_id,
    cited_latch_probe_json)
SELECT
    provenance_correction_id,
    trade_id,
    entry_fill_id,
    entry_fill_id_at_correction,
    entry_fill_snapshot_json,
    cited_candidate_id,
    cited_daily_recommendation_id,
    cited_evaluation_run_id,
    cited_hypothesis_id,
    cited_hypothesis_status_history_id,
    cited_hypothesis_status_at_record,
    cited_pipeline_finished_ts_raw,
    cited_run_ts_utc,
    cited_status_window_upper_utc,
    cited_pipeline_run_id,
    cited_pipeline_run_snapshot_json,
    cited_hypothesis_status_recorded_at,
    cited_hypothesis_status_effective_from,
    cited_hypothesis_status_effective_to,
    cited_hypothesis_name_at_correction,
    cited_candidate_action_session_date,
    cited_recommendation_action_session_date,
    entry_fill_session_date,
    cited_run_ts_raw,
    cited_recommendation_snapshot_json,
    cited_candidate_snapshot_json,
    derivation_rule_version,
    pre_value_json,
    applied_value_json,
    corrected_fields_json,
    applied_at,
    applied_by,
    correction_reason,
    risk_policy_id_at_correction,
    admission_tier,
    cited_latch_link_id,
    cited_latch_validity_intent_id,
    cited_latch_place_intent_id,
    cited_latch_broker_order_id,
    cited_latch_probe_json
  FROM provenance_corrections;

-- 3. The AUTOINCREMENT counter, carried BY STATEMENT (E-2): equality holds by
--    mechanism, not by the live coincidence seq = max id.
DELETE FROM sqlite_sequence WHERE name = 'provenance_corrections__0039';
INSERT INTO sqlite_sequence (name, seq)
SELECT 'provenance_corrections__0039', seq FROM sqlite_sequence
 WHERE name = 'provenance_corrections';

-- 4. The old table, with its two indexes and four triggers.
DROP TABLE provenance_corrections;

-- 5. Rename. SQLite rewrites the stored name token to "provenance_corrections".
ALTER TABLE provenance_corrections__0039 RENAME TO provenance_corrections;

-- 6. The four UNCHANGED objects, VERBATIM from their source statements
--    (0036 :526-529 and :708; 0037 :2294). Created AFTER the rows exist.
CREATE UNIQUE INDEX ux_provenance_corrections_trade
    ON provenance_corrections(trade_id);
CREATE INDEX ix_provenance_corrections_cited_candidate
    ON provenance_corrections(cited_candidate_id);

CREATE TRIGGER trg_provenance_corrections_append_only_delete
BEFORE DELETE ON provenance_corrections
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'provenance_corrections is APPEND-ONLY: a correction cannot be deleted. Deleting one would reopen the trade for a different citation, which is the re-correction path V1 deliberately does not have.');
END;

CREATE TRIGGER trg_pc_no_replace BEFORE INSERT ON provenance_corrections
WHEN EXISTS (SELECT 1 FROM provenance_corrections
              WHERE (NEW.provenance_correction_id != -1
                     AND provenance_correction_id = NEW.provenance_correction_id)
                 OR trade_id = NEW.trade_id)
BEGIN SELECT RAISE(ABORT, '22-A barrier trg_pc_no_replace: provenance_corrections is APPEND-ONLY. A conflicting INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE) would DELETE the existing correction, bypassing trg_provenance_corrections_append_only_delete at the default PRAGMA recursive_triggers=OFF, and rewrite or renumber the audit row of record for this trade. V1 records provenance ONCE per trade and has no re-correction path. To retire the barrier see the reversibility header of 0037_latch_order_mandate_links.sql.'); END;

-- 7. The append-only UPDATE guard: 0037's text plus the seventh column,
--    compared with IS (a NULL-safe comparison; `=` would fail OPEN).
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
           -- the 22-A2 seventh column (0039)
           AND NEW.cited_frozen_value_evidence_json IS OLD.cited_frozen_value_evidence_json
)
BEGIN
    SELECT RAISE(ABORT, 'provenance_corrections is APPEND-ONLY: the only permitted UPDATE is the FK-driven nulling of entry_fill_id or risk_policy_id_at_correction. V1 records provenance ONCE per trade and there is no re-correction path.');
END;

-- 8. The citation graph: 0037's text with the 22-A2 edits ONLY (tier head,
--    last_word seventh NULL, probe version by tier, rung 9 by tier + the
--    seventh-column block, one RAISE sentence).
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

    -- ===== THE AUTHORIZATION'S FOUR FILL-SIDE OPERANDS: PRESENT, AND BOUND
    -- ===== TO THE CITED FILL (Codex 22A-R15-01).
    --
    -- `R14-02` added quantity / price / fill_origin / envelope to the frozen
    -- entry-fill snapshot because the latch ladder's every rung reads them and
    -- a stored proof whose operands are not frozen is not a proof.  NOTHING
    -- OUTSIDE THE SERVICE then required them: `swing/data/models.py`'s
    -- validator and `0036:390-397`'s CHECK both require only fill_id /
    -- trade_id / action (+ fill_datetime).  So a RAW correction -- the AL-10
    -- trust boundary this whole trigger exists to police -- could carry an
    -- SQL-bound latch probe with the operands OMITTED or FALSIFIED, and every
    -- layer read green.
    --
    -- INSERT-TIME RULE.  The five live pre-operand rows are untouched: they
    -- were written before the freeze existed and no UPDATE or DELETE path
    -- changes here.  The drift reader already reports them by name.
    --
    -- IT VERIFIES A FACT, NEVER A JUDGMENT.  Each freeze is compared to the
    -- fill's OWN column, in SQL's own domain, with the NULL-safe `IS` -- same
    -- value, same domain, no rounding and no cross-engine re-derivation.  It
    -- is the identical shape as the four RAW OPERANDS block further down.
    --
    -- THE PRESENCE ASSERTION IS SEPARATE AND IS LOAD-BEARING.  `json_extract`
    -- on an ABSENT path returns SQL NULL, so `IS <column>` alone reads an
    -- OMITTED operand as agreement whenever the column is itself NULL --
    -- which is every pre-22-A envelope.  `json_type(...) IS NOT NULL`
    -- distinguishes an absent path (NULL) from a JSON `null` VALUE (the text
    -- 'null'), and that is exactly the distinction the omission case turns on.
    --
    -- THE ORDINARY BRANCH BINDS THE **JSON TYPE** AS WELL AS THE VALUE (Codex
    -- 22A-FIX-R2-01, verified by execution twice -- by the reviewer and here).
    -- `IS` applies the SOURCE COLUMN'S AFFINITY, so a bare value comparison is
    -- blind to the freeze's own storage class: MEASURED, JSON text `"2.0"`
    -- compares EQUAL to a REAL `2.0`, and -- the sharper one -- a JSON OBJECT
    -- compares EQUAL to a TEXT column holding the same minified document.
    -- Production freezes an envelope as a JSON STRING and never as that
    -- object, so both shapes are snapshots the freezer could not emit passing
    -- the clause written to require its output.  Each ordinary branch
    -- therefore pairs the value comparison with a `json_type` that must AGREE
    -- with the column's `typeof()`, one storage class at a time.
    --
    -- THE `'object'` BRANCH IS THE FREEZER'S DECLARED DIGEST ESCAPE, AND IT IS
    -- CLOSED AND TYPE-BOUND (Codex 22A-FIX-R1-01).  `_json_safe_operand`
    -- writes a type-tagged object when the value cannot be written as JSON --
    -- a BLOB (SQLite does not enforce column affinity; 22A-R13-01 measured
    -- that shape reaching production) or a non-finite REAL (`json.dumps(inf)`
    -- emits the bare token `Infinity`, which `json_valid` reads FALSE, so a
    -- truthful freeze would be rejected by the row's own CHECK).
    --
    -- **THE FIRST DRAFT ADMITTED *ANY* OBJECT once the column was a BLOB or an
    -- infinity, and that was a REACHABLE WRONG ACCEPTANCE at the raw-write
    -- trust boundary** -- a forger could freeze `{}` beside a BLOB column and
    -- satisfy the clause the binding exists to enforce.  MEASURED by the
    -- reviewer against this exact predicate shape.  The escape now requires:
    --   * the column's `typeof()` to be the one that MAKES the escape legal;
    --   * the object to be CLOSED to the freezer's own key pair (`json_remove`
    --     of the two keys is `'{}'`), so no third key can ride along;
    --   * the `type` tag to be the one the freezer actually writes for that
    --     `typeof()` -- **`'bytes'` EXACTLY** (Codex 22A-FIX-R2-02, verified by
    --     execution): `sqlite3` returns a BLOB column as Python `bytes` for
    --     EVERY binding, including a `bytearray` or a `memoryview` written in,
    --     so `_json_safe_operand` can only ever tag a CITED FILL `'bytes'`.
    --     Admitting the other two tags left the declared type-tag consistency
    --     unverifiable in exactly the way the digest's VALUE already is, which
    --     is one declared residual too many; and
    --   * for a non-finite REAL, the `repr` to be the EXACT sign the column
    --     carries -- `'inf'` or `'-inf'`, which is what Python's `repr` emits
    --     (measured), so the two infinities cannot be interchanged.
    --
    -- **THE RESIDUAL, DECLARED: SQLite HAS NO `sha256`, so the BLOB digest's
    -- VALUE is not verified -- only its SHAPE (64 lower-case hex characters)
    -- and its type tag.**  That is AL-10's boundary exactly (the trigger
    -- verifies CONSISTENCY, never TRUTH) and it is strictly smaller than what
    -- the any-object branch exposed: a forger must now produce a well-formed
    -- digest object beside a genuinely BLOB column rather than an empty one.
    --
    -- `fill_origin` GETS NO ESCAPE AT ALL, and that is SCHEMA-PREVENTION
    -- rather than an omission: `fills.fill_origin` carries a five-value
    -- `CHECK (fill_origin IN (...))` (migration `0020:394`), and MEASURED by
    -- execution, that CHECK rejects BOTH a BLOB and an infinity -- SQLite
    -- compares a BLOB to TEXT as unequal, so no enum member matches.  A
    -- column that cannot hold either value needs no escape from either.
    --
    -- FAIL-CLOSED BY CONSTRUCTION.  A malformed snapshot cannot reach a JSON
    -- function (the `json_valid` CASE, 22A-R3-12's class), and any NULL
    -- anywhere in the chain collapses through `COALESCE(..., 0)` to a REFUSAL
    -- rather than to a trigger that silently does not fire.
    AND COALESCE((
        SELECT CASE WHEN json_valid(NEW.entry_fill_snapshot_json) THEN (
                json_type(NEW.entry_fill_snapshot_json, '$.quantity')
                    IS NOT NULL
            AND json_type(NEW.entry_fill_snapshot_json, '$.price')
                    IS NOT NULL
            AND json_type(NEW.entry_fill_snapshot_json, '$.fill_origin')
                    IS NOT NULL
            AND json_type(NEW.entry_fill_snapshot_json, '$.envelope')
                    IS NOT NULL
            AND ((json_extract(NEW.entry_fill_snapshot_json,
                          '$.quantity') IS f.quantity
                  AND ((typeof(f.quantity) = 'null'
                        AND json_type(NEW.entry_fill_snapshot_json,
                                '$.quantity') = 'null')
                    OR (typeof(f.quantity) = 'text'
                        AND json_type(NEW.entry_fill_snapshot_json,
                                '$.quantity') = 'text')
                    OR (typeof(f.quantity) = 'integer'
                        AND json_type(NEW.entry_fill_snapshot_json,
                                '$.quantity') = 'integer')
                    OR (typeof(f.quantity) = 'real'
                        AND json_type(NEW.entry_fill_snapshot_json,
                                '$.quantity') = 'real')))
                 OR (typeof(f.quantity) = 'real'
                     AND (f.quantity = 9e999 OR f.quantity = -9e999)
                     AND json_type(NEW.entry_fill_snapshot_json,
                             '$.quantity') = 'object'
                     AND json_remove(json_extract(
                             NEW.entry_fill_snapshot_json, '$.quantity'),
                             '$.type', '$.repr') = '{}'
                     AND json_extract(NEW.entry_fill_snapshot_json,
                             '$.quantity.type') = 'float'
                     AND json_extract(NEW.entry_fill_snapshot_json,
                             '$.quantity.repr')
                         = CASE WHEN f.quantity = 9e999 THEN 'inf'
                                ELSE '-inf' END)
                 OR (typeof(f.quantity) = 'blob'
                     AND json_type(NEW.entry_fill_snapshot_json,
                             '$.quantity') = 'object'
                     AND json_remove(json_extract(
                             NEW.entry_fill_snapshot_json, '$.quantity'),
                             '$.type', '$.sha256') = '{}'
                     AND json_extract(NEW.entry_fill_snapshot_json,
                             '$.quantity.type') = 'bytes'
                     AND length(json_extract(
                             NEW.entry_fill_snapshot_json,
                             '$.quantity.sha256')) = 64
                     AND NOT json_extract(
                             NEW.entry_fill_snapshot_json,
                             '$.quantity.sha256') GLOB '*[^0-9a-f]*'))
            AND ((json_extract(NEW.entry_fill_snapshot_json,
                          '$.price') IS f.price
                  AND ((typeof(f.price) = 'null'
                        AND json_type(NEW.entry_fill_snapshot_json,
                                '$.price') = 'null')
                    OR (typeof(f.price) = 'text'
                        AND json_type(NEW.entry_fill_snapshot_json,
                                '$.price') = 'text')
                    OR (typeof(f.price) = 'integer'
                        AND json_type(NEW.entry_fill_snapshot_json,
                                '$.price') = 'integer')
                    OR (typeof(f.price) = 'real'
                        AND json_type(NEW.entry_fill_snapshot_json,
                                '$.price') = 'real')))
                 OR (typeof(f.price) = 'real'
                     AND (f.price = 9e999 OR f.price = -9e999)
                     AND json_type(NEW.entry_fill_snapshot_json,
                             '$.price') = 'object'
                     AND json_remove(json_extract(
                             NEW.entry_fill_snapshot_json, '$.price'),
                             '$.type', '$.repr') = '{}'
                     AND json_extract(NEW.entry_fill_snapshot_json,
                             '$.price.type') = 'float'
                     AND json_extract(NEW.entry_fill_snapshot_json,
                             '$.price.repr')
                         = CASE WHEN f.price = 9e999 THEN 'inf'
                                ELSE '-inf' END)
                 OR (typeof(f.price) = 'blob'
                     AND json_type(NEW.entry_fill_snapshot_json,
                             '$.price') = 'object'
                     AND json_remove(json_extract(
                             NEW.entry_fill_snapshot_json, '$.price'),
                             '$.type', '$.sha256') = '{}'
                     AND json_extract(NEW.entry_fill_snapshot_json,
                             '$.price.type') = 'bytes'
                     AND length(json_extract(
                             NEW.entry_fill_snapshot_json,
                             '$.price.sha256')) = 64
                     AND NOT json_extract(
                             NEW.entry_fill_snapshot_json,
                             '$.price.sha256') GLOB '*[^0-9a-f]*'))
            AND json_extract(NEW.entry_fill_snapshot_json,
                    '$.fill_origin') IS f.fill_origin
            AND json_type(NEW.entry_fill_snapshot_json,
                    '$.fill_origin') = 'text'
            AND ((json_extract(NEW.entry_fill_snapshot_json,
                          '$.envelope') IS f.schwab_source_value_json
                  AND ((typeof(f.schwab_source_value_json) = 'null'
                        AND json_type(NEW.entry_fill_snapshot_json,
                                '$.envelope') = 'null')
                    OR (typeof(f.schwab_source_value_json) = 'text'
                        AND json_type(NEW.entry_fill_snapshot_json,
                                '$.envelope') = 'text')
                    OR (typeof(f.schwab_source_value_json) = 'integer'
                        AND json_type(NEW.entry_fill_snapshot_json,
                                '$.envelope') = 'integer')
                    OR (typeof(f.schwab_source_value_json) = 'real'
                        AND json_type(NEW.entry_fill_snapshot_json,
                                '$.envelope') = 'real')))
                 OR (typeof(f.schwab_source_value_json) = 'real'
                     AND (f.schwab_source_value_json = 9e999 OR f.schwab_source_value_json = -9e999)
                     AND json_type(NEW.entry_fill_snapshot_json,
                             '$.envelope') = 'object'
                     AND json_remove(json_extract(
                             NEW.entry_fill_snapshot_json, '$.envelope'),
                             '$.type', '$.repr') = '{}'
                     AND json_extract(NEW.entry_fill_snapshot_json,
                             '$.envelope.type') = 'float'
                     AND json_extract(NEW.entry_fill_snapshot_json,
                             '$.envelope.repr')
                         = CASE WHEN f.schwab_source_value_json = 9e999 THEN 'inf'
                                ELSE '-inf' END)
                 OR (typeof(f.schwab_source_value_json) = 'blob'
                     AND json_type(NEW.entry_fill_snapshot_json,
                             '$.envelope') = 'object'
                     AND json_remove(json_extract(
                             NEW.entry_fill_snapshot_json, '$.envelope'),
                             '$.type', '$.sha256') = '{}'
                     AND json_extract(NEW.entry_fill_snapshot_json,
                             '$.envelope.type') = 'bytes'
                     AND length(json_extract(
                             NEW.entry_fill_snapshot_json,
                             '$.envelope.sha256')) = 64
                     AND NOT json_extract(
                             NEW.entry_fill_snapshot_json,
                             '$.envelope.sha256') GLOB '*[^0-9a-f]*'))
        ) ELSE 0 END
          FROM fills f
         WHERE f.fill_id = NEW.entry_fill_id_at_correction), 0)

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
        -- FEI-CONSUMER subject_reading_is_canonical :: VERSION_BLIND
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
         -- 22-A2: and no frozen-value evidence (the seventh column).
         AND NEW.cited_frozen_value_evidence_json IS NULL
         -- FEI-CONSUMER last_word_subject_order_id :: VERSION_BLIND
         -- READS THE STORED READING AS EVIDENCE OF ABSENCE, so a version
         -- filter here WIDENS acceptance rather than tightening it (L19).
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
        -- 22-A2 (0039): 'latch_ladder_tier2' SHARES this whole body (E-4) --
        -- one $.authorization closure list -- and differs only at the probe
        -- version and at rung 9, where each tier's clauses sit in a CASE.
        (NEW.admission_tier IN ('latch_ladder', 'latch_ladder_tier2')
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
         -- FEI-CONSUMER cited_order_is_the_subject_order :: VERSION_BLIND
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
         -- 22-A2 (F11): the tier-2 blob carries its OWN version, because its
         -- rung-9 entry says escaped_by_tier2; latch_ladder blobs are unchanged.
         AND json_extract(NEW.cited_latch_probe_json, '$.evidence_version')
             = CASE NEW.admission_tier
                   WHEN 'latch_ladder' THEN '2026-08-25.1'
                   WHEN 'latch_ladder_tier2' THEN '2026-09-23.1' END

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
         -- for a clause AL-3 does not name, which SILENTLY BROADENED a
         -- declared limitation roster to cover something nobody had ruled
         -- on. AL-3 does NOT extend here; this clause carries its own
         -- declaration, below, which is narrower than AL-3 in one direction
         -- and weaker in another and therefore cannot borrow it.
         --
         -- THE ROSTER IS NOT RESTATED IN THIS FILE, and that is the durable
         -- half of the fix (operator-ruled 2026-08-27). This comment used to
         -- QUOTE AL-3's membership, so a reader had TWO places to learn the
         -- roster and they could disagree -- which is how the broadening
         -- happened in the first place. The ONE roster is the
         -- closure-checked region in plan limitation L17, held against
         -- AUTHORIZATION_CLAUSES + PROBE_GUARD_CLAUSES and against THIS
         -- FILE's bindings, in BOTH directions, by
         -- `tests/data/test_22a_al3_closure.py`. That roster has since been
         -- CORRECTED: this clause is a REASONED EXCLUSION there, named with
         -- the ground CHARC ruled, rather than an unexplained silence.
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
         --
         -- THIS ORDERING IS A **FACT**, NOT A RE-DERIVED JUDGMENT, AND THE
         -- REASON IS THE SCHEMA (CHARC, ruled 2026-09-01). The rule that SQL
         -- must never re-derive a judgment across an engine boundary targets
         -- INTERPRETATION -- parsing, normalization, coercion, semantic
         -- predicates -- where the two engines hold independent opinions. An
         -- ordering over STORED KEYS is a QUERY ABOUT THE TABLE, provided the
         -- key carries no interpretive freedom, and here it carries none:
         -- `recorded_ts` is FORMAT-CONSTRAINED by `0033:704-712` (length
         -- exactly 19, a GLOB fixing all 19 positions, `datetime()` non-null,
         -- both date halves, and per-component ranges), so it is a FIXED-WIDTH
         -- canonical ISO string, which orders LEXICALLY exactly as it orders
         -- CHRONOLOGICALLY. Python's authority compares the same strings by
         -- the same tuple. The engines cannot disagree because the schema
         -- removed the degree of freedom.
         --
         -- WHERE THE KEY IS AN UNCONSTRAINED TEXT TIMESTAMP THE RULE DOES
         -- BIND -- the query is then an interpretation wearing a query's
         -- clothes (D38). Read this as a decision with its ground, not as a
         -- violation to be "fixed": removing the ordering loses a real defense
         -- against a forger citing a genuine-but-not-GOVERNING row, and its
         -- only divergence direction would be a wrong REFUSAL of a truthful
         -- row -- cheap, legible and adjudicable.
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
         --
         -- THIS ORDERING IS A **FACT**, NOT A RE-DERIVED JUDGMENT, FOR THE
         -- SAME REASON AS RUNG 3b ABOVE (CHARC, ruled 2026-09-01).
         -- `recorded_ts` is FORMAT-CONSTRAINED by `0033:704-712` -- length
         -- exactly 19, a GLOB fixing all 19 positions, `datetime()` non-null,
         -- both date halves, per-component ranges -- so it is a FIXED-WIDTH
         -- canonical ISO string whose LEXICAL order IS its CHRONOLOGICAL
         -- order, and Python's authority (`swing/latches/classification.py`
         -- `_order_key`) compares the same strings by the same tuple. An
         -- ordering over a key with no interpretive freedom is a QUERY ABOUT
         -- THE TABLE; the engine-boundary rule targets INTERPRETATION, and it
         -- WOULD bind here if `recorded_ts` were an unconstrained TEXT
         -- timestamp (D38). Read this as a decision with its ground, not as a
         -- violation to be "fixed".
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
         -- THE SCAN'S POPULATION IS ESTABLISHED FIRST, IN SQL TOO (Codex
         -- 22A-R12-01). A scan over STORED readings can only see documents the
         -- authority has READ, so a competing entry fill whose reading is
         -- MISSING or REFUSED is ignorance -- and the scan below would read
         -- that ignorance as ABSENCE and admit the widest wrong acceptance
         -- available here: a raw correction claiming a mandate as unconsumed
         -- while another trade already consumes it.
         --
         -- ONLY THE `refused` HALF WAS EVER DECLARED, and the MISSING half
         -- became reachable in this same arc when the entry path's identity
         -- write was CONTAINED (22A-R11-02) -- "envelope present, reading
         -- absent" is a state the writer can now leave behind. A limitation
         -- declared for one of two reachable populations is the roster defect
         -- one level down.
         --
         -- THE TWIN IS BROUGHT UP TO THE SERVICE, NEVER PAST IT. The service's
         -- rung 6 runs `ensure_entry_fill_identities` over exactly this
         -- population (`action='entry' AND schwab_source_value_json IS NOT
         -- NULL`) BEFORE it scans, and then refuses on any `refused` reading
         -- (`consumption_evidence_unavailable`). So on the service path this
         -- clause is satisfied by construction and there is no state the
         -- service admits and the trigger then aborts -- the
         -- authorize-then-abort shape this arc met four times. A fill with NO
         -- envelope is excluded on BOTH sides, because it never gets a reading
         -- and never should; a clause requiring one would refuse every
         -- ordinary manual trade in the book.
         AND NOT EXISTS (
             SELECT 1 FROM fills f3
              WHERE f3.action = 'entry'
                AND (f3.trade_id IS NULL OR f3.trade_id <> NEW.trade_id)
                AND f3.schwab_source_value_json IS NOT NULL
                -- FEI-CONSUMER rung6_population_has_been_read :: VERSION_BLIND
                AND NOT EXISTS (
                    SELECT 1 FROM fill_envelope_identity fei3
                     WHERE fei3.fill_id = f3.fill_id
                       AND fei3.envelope_raw
                           = f3.schwab_source_value_json
                       AND fei3.envelope_state = 'canonical'))

         -- FEI-CONSUMER rung6_consumption_scan :: VERSION_BLIND
         -- The SECOND clause that reads a stored reading as evidence of
         -- ABSENCE; filtering it on the version hides a stale consumer from
         -- the one scan that exists to find one (L19).
         AND NOT EXISTS (SELECT 1 FROM fill_envelope_identity fei
                         JOIN fills f2 ON f2.fill_id = fei.fill_id
                         WHERE f2.action = 'entry'
                           AND f2.trade_id <> NEW.trade_id
                           AND fei.envelope_raw = f2.schwab_source_value_json
                           AND fei.envelope_state = 'canonical'
                           AND fei.broker_order_id
                               = NEW.cited_latch_broker_order_id)

         -- SERVICE-VALIDATED (L17 / AL-3). These TWO rest on a scan result
         -- and on derivation state that no subquery can reach, so SQL
         -- asserts their PRESENCE, TYPE and verdict and nothing more. A
         -- fabricated input on either is ACCEPTED -- that is a LIMIT of the
         -- trigger, declared, not a guarantee.
         --
         -- L17's ROSTER IS CLOSURE-CHECKED AND IS NOT COPIED HERE: this
         -- comment names only the two clauses it sits above, so it can never
         -- again read as a statement of the WHOLE roster. Membership lives
         -- in the marked region inside L17 and is held against this file by
         -- `tests/data/test_22a_al3_closure.py`, which asserts that every
         -- clause the code calls service-validated is declared there AND
         -- that every clause declared SQL-bound really binds its input HERE.
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
         AND json_type(NEW.cited_latch_probe_json,
                 '$.authorization.rung9_stored_freeze_tier.input') = 'text'
         AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung9_stored_freeze_tier.input')
             = (SELECT l.freeze_tier FROM latch_order_mandate_links l
                 WHERE l.link_id = NEW.cited_latch_link_id)
         -- 22-A2 (F11, 0039): rung 9's verdict, the tier it may cite, the
         -- side of the boundary and the seventh column are PER TIER. The
         -- 'latch_ladder' branch below is 0037's clause set, unchanged in
         -- meaning, plus the seventh column's NULL: it therefore REFUSES a
         -- blob whose rung 9 says escaped_by_tier2, so an escape can never
         -- be laundered into a tier-1 row. The 'latch_ladder_tier2' branch
         -- is RD's refuse-by-default ESCAPED -- never removed -- by the
         -- four-part conjunction the service evaluated (S12.1 #3), whose
         -- attestation the seventh column carries, closed and bound.
         -- SQL NEVER ROUNDS HERE (S4.3a; F8): it binds the service's found
         -- texts by containment and the raw operands by identity.
         AND CASE NEW.admission_tier
         WHEN 'latch_ladder' THEN (
             json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung9_stored_freeze_tier.verdict') = 'pass'
             AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung9_stored_freeze_tier.input') = 'live_at_acceptance'
             AND EXISTS (SELECT 1 FROM candidates_immutability_epoch e
                         WHERE NEW.cited_candidate_id
                               > e.max_candidate_id_at_barrier)
             AND NEW.cited_frozen_value_evidence_json IS NULL)
         WHEN 'latch_ladder_tier2' THEN (
             -- TIER2-PREDICATE rung9_escaped_verdict
             json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung9_stored_freeze_tier.verdict') = 'escaped_by_tier2'
             -- TIER2-PREDICATE rung9_pre_barrier_input
             AND json_extract(NEW.cited_latch_probe_json,
                 '$.authorization.rung9_stored_freeze_tier.input')
                 = 'pre_barrier_reconstructed'
             -- TIER2-PREDICATE rung9_pre_barrier_candidate
             -- A declared BELT, the twin of the latch_ladder branch's `>`: the
             -- minting CASE already makes a pre_barrier_reconstructed link
             -- imply this, so no mutation isolates it.
             AND EXISTS (SELECT 1 FROM candidates_immutability_epoch e
                         WHERE NEW.cited_candidate_id
                               <= e.max_candidate_id_at_barrier)
             -- TIER2-PREDICATE seventh_present
             AND NEW.cited_frozen_value_evidence_json IS NOT NULL
             -- THE SEVENTH COLUMN, CLOSED AND BOUND. The json_valid CASE is
             -- 0037's R3-12 precedent (a malformed blob is JUDGED, never
             -- allowed to raise an engine error); any NULL collapses through
             -- the enclosing COALESCE to a REFUSAL.
             AND CASE WHEN json_valid(NEW.cited_frozen_value_evidence_json) THEN (
             -- TIER2-PREDICATE blob_closed
             json_type(NEW.cited_frozen_value_evidence_json) = 'object'
             AND json_remove(NEW.cited_frozen_value_evidence_json,
                 '$.evidence_version', '$.derivation_version',
                 '$.ruling_citation', '$.verification_method',
                 '$.evaluated_at', '$.artifact_path', '$.artifact_commit_sha',
                 '$.quoted_text', '$.quoted_ticker_text', '$.quoted_action_session_text',
                 '$.quoted_pivot_text', '$.quoted_invalidation_text', '$.live_pivot_raw',
                 '$.live_invalidation_raw', '$.pivot_equal_at_dp', '$.invalidation_equal_at_dp',
                 '$.compare_dp', '$.author_instant', '$.author_date_et',
                 '$.committer_instant', '$.fill_session_date', '$.resolved_remote_ref_sha',
                 '$.descendant_count', '$.remote_ref_updated_at', '$.remote_ref_age_seconds',
                 '$.anchor_strength', '$.time_anchor_residual', '$.interval',
                 '$.uncovered_window_prose') = '{}'
             -- TIER2-PREDICATE evidence_version
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.evidence_version') = 'text'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.evidence_version') = '2026-09-23.1'
             -- TIER2-PREDICATE derivation_version
             -- The DERIVATION version (CHARC G-T7F item 3 (B)): TEXT, and nothing
             -- about its value. A derivation change is invisible to SQL by
             -- construction; the read-time replay compares it, as an observation.
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.derivation_version') = 'text'
             -- TIER2-PREDICATE attestation_texts
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.ruling_citation') = 'text'
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.verification_method') = 'text'
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.artifact_path') = 'text'
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.author_instant') = 'text'
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.committer_instant') = 'text'
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.resolved_remote_ref_sha') = 'text'
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.anchor_strength') = 'text'
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.time_anchor_residual') = 'text'
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.uncovered_window_prose') = 'text'
             -- TIER2-PREDICATE evaluated_at_is_applied_at
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.evaluated_at') = 'text'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.evaluated_at') = NEW.applied_at
             -- TIER2-PREDICATE artifact_commit_sha_shape
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.artifact_commit_sha') = 'text'
             AND length(json_extract(NEW.cited_frozen_value_evidence_json, '$.artifact_commit_sha')) = 40
             AND NOT json_extract(NEW.cited_frozen_value_evidence_json, '$.artifact_commit_sha') GLOB '*[^0-9a-f]*'
             -- TIER2-PREDICATE quoted_text_one_line
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.quoted_text') = 'text'
             AND length(json_extract(NEW.cited_frozen_value_evidence_json, '$.quoted_text')) > 0
             AND instr(json_extract(NEW.cited_frozen_value_evidence_json, '$.quoted_text'), char(10)) = 0
             AND instr(json_extract(NEW.cited_frozen_value_evidence_json, '$.quoted_text'), char(13)) = 0
             -- TIER2-PREDICATE quoted_ticker
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.quoted_ticker_text') = 'text'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.quoted_ticker_text') = (SELECT ca.ticker FROM candidates ca WHERE ca.id = NEW.cited_candidate_id)
             AND instr(json_extract(NEW.cited_frozen_value_evidence_json, '$.quoted_text'),
                       json_extract(NEW.cited_frozen_value_evidence_json, '$.quoted_ticker_text')) > 0
             -- TIER2-PREDICATE quoted_action_session
             -- ISO preferred; MM-DD only when the ET author year is the
             -- action session's year (RD's F13 year rule).
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.quoted_action_session_text') = 'text'
             AND (json_extract(NEW.cited_frozen_value_evidence_json, '$.quoted_action_session_text')
                      = (SELECT er.action_session_date FROM evaluation_runs er
                   WHERE er.id = NEW.cited_evaluation_run_id)
                  OR (json_extract(NEW.cited_frozen_value_evidence_json, '$.quoted_action_session_text')
                          = substr((SELECT er.action_session_date FROM evaluation_runs er
                   WHERE er.id = NEW.cited_evaluation_run_id), 6)
                      AND substr(json_extract(NEW.cited_frozen_value_evidence_json, '$.author_date_et'), 1, 4)
                          = substr((SELECT er.action_session_date FROM evaluation_runs er
                   WHERE er.id = NEW.cited_evaluation_run_id), 1, 4)))
             AND instr(json_extract(NEW.cited_frozen_value_evidence_json, '$.quoted_text'),
                       json_extract(NEW.cited_frozen_value_evidence_json, '$.quoted_action_session_text')) > 0
             -- TIER2-PREDICATE quoted_pivot
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.quoted_pivot_text') = 'text'
             AND instr(json_extract(NEW.cited_frozen_value_evidence_json, '$.quoted_text'),
                       json_extract(NEW.cited_frozen_value_evidence_json, '$.quoted_pivot_text')) > 0
             -- TIER2-PREDICATE quoted_invalidation
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.quoted_invalidation_text') = 'text'
             AND instr(json_extract(NEW.cited_frozen_value_evidence_json, '$.quoted_text'),
                       json_extract(NEW.cited_frozen_value_evidence_json, '$.quoted_invalidation_text')) > 0
             -- TIER2-PREDICATE live_pivot_raw
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.live_pivot_raw') IN ('real', 'integer')
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.live_pivot_raw') = (SELECT ca.pivot FROM candidates ca WHERE ca.id = NEW.cited_candidate_id)
             -- TIER2-PREDICATE live_invalidation_raw
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.live_invalidation_raw') IN ('real', 'integer')
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.live_invalidation_raw')
                 = (SELECT ca.initial_stop FROM candidates ca WHERE ca.id = NEW.cited_candidate_id)
             -- TIER2-PREDICATE equal_at_dp_verdicts
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.pivot_equal_at_dp') = 'integer'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.pivot_equal_at_dp') = 1
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.invalidation_equal_at_dp') = 'integer'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.invalidation_equal_at_dp') = 1
             -- TIER2-PREDICATE compare_dp
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.compare_dp') = 'integer'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.compare_dp') = 2
             -- TIER2-PREDICATE fill_session_date
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.fill_session_date') = 'text'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.fill_session_date') = NEW.entry_fill_session_date
             -- TIER2-PREDICATE author_date_before_fill
             -- A consistency check between two recorded ISO dates, never a
             -- clock conversion (the ET conversion is the service's, F7).
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.author_date_et') = 'text'
             AND length(json_extract(NEW.cited_frozen_value_evidence_json, '$.author_date_et')) = 10
             AND date(json_extract(NEW.cited_frozen_value_evidence_json, '$.author_date_et'))
                 = json_extract(NEW.cited_frozen_value_evidence_json, '$.author_date_et')
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.author_date_et') < NEW.entry_fill_session_date
             -- TIER2-PREDICATE remote_ref_attestation
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.descendant_count') = 'integer'
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.remote_ref_updated_at') IN ('text', 'null')
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.remote_ref_age_seconds') IN ('integer', 'null')
             -- TIER2-PREDICATE interval_closed
             -- endpoints + segments + ONE typed key, record_position: where
             -- record_at sits relative to barrier_armed_at (CHARC G-NEG).
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.interval') = 'object'
             AND CASE WHEN json_type(NEW.cited_frozen_value_evidence_json, '$.interval') = 'object'
                      THEN json_remove(json_extract(NEW.cited_frozen_value_evidence_json, '$.interval'),
                             '$.endpoints', '$.segments', '$.record_position') = '{}'
                      ELSE 0 END
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.interval.record_position') = 'text'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.record_position')
                 IN ('before_barrier', 'inside_coverage')
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints') = 'object'
             AND CASE WHEN json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints') = 'object'
                      THEN json_remove(json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints'),
                             '$.fire_lo', '$.fire_hi', '$.record_at',
                             '$.barrier_armed_at', '$.read_at') = '{}'
                      ELSE 0 END
             -- TIER2-PREDICATE interval_endpoint_fire_lo
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.fire_lo') = 'object'
             AND CASE WHEN json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.fire_lo') = 'object'
                      THEN json_remove(json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.fire_lo'),
                             '$.raw', '$.utc', '$.clock_domain', '$.source') = '{}'
                      ELSE 0 END
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.fire_lo.raw') = 'text'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.fire_lo.raw') = NEW.cited_run_ts_raw
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.fire_lo.utc') = 'text'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.fire_lo.clock_domain') = 'naive_local_pipeline'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.fire_lo.source') = 'evaluation_runs.run_ts'
             -- TIER2-PREDICATE interval_endpoint_fire_hi
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.fire_hi') = 'object'
             AND CASE WHEN json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.fire_hi') = 'object'
                      THEN json_remove(json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.fire_hi'),
                             '$.raw', '$.utc', '$.clock_domain', '$.source') = '{}'
                      ELSE 0 END
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.fire_hi.raw') = 'text'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.fire_hi.raw') = NEW.cited_pipeline_finished_ts_raw
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.fire_hi.utc') = 'text'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.fire_hi.clock_domain') = 'naive_local_pipeline'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.fire_hi.source') = 'pipeline_runs.finished_ts'
             -- TIER2-PREDICATE interval_endpoint_record_at
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.record_at') = 'object'
             AND CASE WHEN json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.record_at') = 'object'
                      THEN json_remove(json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.record_at'),
                             '$.raw', '$.utc', '$.clock_domain', '$.source') = '{}'
                      ELSE 0 END
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.record_at.raw') = 'text'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.record_at.raw') = json_extract(NEW.cited_frozen_value_evidence_json, '$.author_instant')
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.record_at.utc') = 'text'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.record_at.clock_domain') = 'iso_offset'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.record_at.source') = 'git_author_instant'
             -- TIER2-PREDICATE interval_endpoint_barrier_armed_at
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.barrier_armed_at') = 'object'
             AND CASE WHEN json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.barrier_armed_at') = 'object'
                      THEN json_remove(json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.barrier_armed_at'),
                             '$.raw', '$.utc', '$.clock_domain', '$.source') = '{}'
                      ELSE 0 END
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.barrier_armed_at.raw') = 'text'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.barrier_armed_at.raw') = (SELECT e.applied_at FROM candidates_immutability_epoch e
                     WHERE e.epoch_id = 1)
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.barrier_armed_at.utc') = 'text'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.barrier_armed_at.clock_domain') = 'utc_z'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.barrier_armed_at.source') = 'candidates_immutability_epoch.applied_at'
             -- TIER2-PREDICATE interval_endpoint_read_at
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.read_at') = 'object'
             AND CASE WHEN json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.read_at') = 'object'
                      THEN json_remove(json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.read_at'),
                             '$.raw', '$.utc', '$.clock_domain', '$.source') = '{}'
                      ELSE 0 END
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.read_at.raw') = 'text'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.read_at.raw') = NEW.applied_at
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.read_at.utc') = 'text'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.read_at.clock_domain') = 'naive_utc_ms'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.endpoints.read_at.source') = 'provenance_corrections.applied_at'
             -- TIER2-PREDICATE interval_segment_order
             -- The emitted kinds in the canonical order fire,
             -- writer_absence_only, match_only, covered -- match_only OPTIONAL
             -- (RD F2.I-NEG; CHARC G-NEG). Its presence IFF record_at.utc <
             -- barrier_armed_at.utc is the SERVICE twin's (this predicate's
             -- mirror): SQL recomputes NO duration and never reads a utc
             -- value (R8-03, AL2-9), so here it asserts the ORDER only.
             AND json_type(NEW.cited_frozen_value_evidence_json, '$.interval.segments') = 'array'
             AND json_array_length(NEW.cited_frozen_value_evidence_json, '$.interval.segments') IN (3, 4)
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.segments[0].kind') = 'fire'
             AND json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.segments[1].kind') = 'writer_absence_only'
             AND CASE json_array_length(NEW.cited_frozen_value_evidence_json, '$.interval.segments')
                 WHEN 4 THEN (
                     json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.segments[2].kind') = 'match_only'
                     AND json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.segments[3].kind')
                         IN ('covered', 'uncovered_barrier_absent'))
                 WHEN 3 THEN
                     json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.segments[2].kind')
                         IN ('covered', 'uncovered_barrier_absent')
                 ELSE 0 END
             AND NOT EXISTS (
                 SELECT 1 FROM json_each(NEW.cited_frozen_value_evidence_json, '$.interval.segments') s
                  WHERE CASE WHEN s.type = 'object' THEN (
                            json_remove(s.value, '$.kind', '$.from', '$.to',
                                        '$.seconds') <> '{}'
                            OR json_type(s.value, '$.from') IS NOT 'text'
                            OR json_type(s.value, '$.to') IS NOT 'text'
                            OR json_type(s.value, '$.seconds') IS NULL
                            OR json_type(s.value, '$.seconds')
                               NOT IN ('integer', 'real'))
                        ELSE 1 END)
             -- TIER2-PREDICATE record_position_consistent
             -- CHARC's G-NEG belt: two representations of ONE fact agree,
             -- with no utc read and no duration -- 'before_barrier' iff a
             -- match_only span exists (length 4), 'inside_coverage' iff not
             -- (length 3). An absent or foreign value reads NULL/0: refused.
             AND CASE json_array_length(NEW.cited_frozen_value_evidence_json, '$.interval.segments')
                 WHEN 4 THEN json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.record_position') = 'before_barrier'
                 WHEN 3 THEN json_extract(NEW.cited_frozen_value_evidence_json, '$.interval.record_position') = 'inside_coverage'
                 ELSE 0 END
             ) ELSE 0 END)
         ELSE 0 END

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
             -- FEI-CONSUMER guard_envelope_symbol_binding :: VERSION_BLIND
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
    SELECT RAISE(ABORT, 'provenance_corrections: the cited rows exist but do not form the citation graph this correction asserts (candidate->run, recommendation->run/ticker/kind, pipeline->run, status-history->hypothesis, registry name, fill->trade, trade<->candidate ticker, the frozen entry-fill snapshot''s four authorization operands (quantity, price, fill_origin, envelope) present and equal to the cited fill''s own columns, and -- for admission_tier latch_ladder -- link->candidate/order/intents, the accepted validity row and its place parent, and a closed VERSIONED probe-evidence blob whose every bound field matches its source and whose $.authorization records one passing entry per refusal-capable clause). For admission_tier latch_ladder_tier2 (22-A2) the same latch citation is required with rung 9 recorded as escaped_by_tier2 on a PRE-barrier link, plus a closed, versioned frozen-value evidence blob whose every bound field matches its source. The citation is STRUCTURAL: a row may not claim a contemporaneous pair it does not have, nor an admission whose evidence it cannot produce. A correction is also refused when the Schwab envelope on the anchoring fill carries a duplicate, padded, blank or non-string schwab_order_id or schwab_instrument_symbol: Python and SQLite read such a document DIFFERENTLY, so the authority it names is ambiguous and no citation may rest on it.');
END;

-- Schema version bump. MUST be the FINAL statement before COMMIT.
UPDATE schema_version SET version = 39;

COMMIT;
