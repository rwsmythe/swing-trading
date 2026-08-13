-- 0036_provenance_corrections.sql
-- Demand C: the cohort-key provenance-correction audit table.
-- ADDITIVE ONLY. Nothing is rebuilt, dropped or renamed.
-- Atomic via explicit BEGIN; ... COMMIT; per gotcha #9 (executescript
-- implicit COMMIT). Bumps schema_version 35 -> 36.
--
-- WHY A NEW TABLE RATHER THAN REUSING reconciliation_corrections (plan
-- section 2). That table declares BOTH `discrepancy_id` AND
-- `reconciliation_run_id` NOT NULL with ON DELETE CASCADE FKs, so a row in it
-- is by construction the CHILD of a reconciliation run and a discrepancy. A
-- provenance correction has neither. Relaxing those NOT NULLs is a REBUILD --
-- the highest-risk shape of migration this project runs (db.py's own words at
-- the 0035 gate) -- on the audit table of record, it would strand the existing
-- rows in a table that no longer guarantees anchoring, and it would silently
-- make a SHIPPED module's stated refusal false
-- (`entry_date_correction.py:15-19` and `cli.py:2231-2236` both justify
-- `--discrepancy` by citing exactly those two NOT NULLs). It also cannot make
-- the citation STRUCTURAL, which is the whole point: the citation would live
-- in `pre_correction_value_json` as unenforced text.

BEGIN;

CREATE TABLE provenance_corrections (
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

    risk_policy_id_at_correction INTEGER REFERENCES risk_policy(policy_id) ON DELETE SET NULL,

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

-- ONE correction per trade, enforced by the SCHEMA. This became available only
-- once V1 dropped the supersession chain (Codex R1 Major 1): a chain needs two
-- live heads for the duration of one statement, and SQLite evaluates
-- uniqueness per statement with no deferral for indexes, so a chain and this
-- index are mutually exclusive. V1 does not re-correct, so the index is both
-- correct and strictly stronger than a service-layer guard.
CREATE UNIQUE INDEX ux_provenance_corrections_trade
    ON provenance_corrections(trade_id);
CREATE INDEX ix_provenance_corrections_cited_candidate
    ON provenance_corrections(cited_candidate_id);



-- ============================================================================
-- THE CITATION GRAPH, ENFORCED (Codex R5 Major 2).
--
-- The FKs prove each cited row EXISTS. They do NOT prove those rows form the
-- contemporaneous PAIR the correction asserts: a row could cite candidate A
-- while declaring evaluation run B, cite a pipeline row belonging to another
-- run, or cite a status interval belonging to another hypothesis. Since this
-- arc ADVERTISES the citation as structural, the claim and the code have to
-- agree -- and this was declined TWICE on the grounds that SQLite cannot
-- express cross-table relationships without composite FKs against UNIQUE
-- indexes on tables this arc does not own. That is true of FOREIGN KEYS and
-- FALSE of TRIGGERS, which can query the parent rows; this migration already
-- relies on triggers for its append-only guard, so the precedent was already
-- here. Subqueries are prohibited in CHECK constraints but permitted in a
-- trigger WHEN clause -- verified at the prompt.
--
-- "Impossible through the current service emitter" is NOT "unreachable" on
-- this codebase: the generic corrector interpolates a PRAGMA-validated column
-- name into dynamic SQL, so a writer no column-name grep can see is the
-- standing shape here (D36). The reservation added by this arc closes that
-- door for the three cohort columns; this trigger closes it for the audit
-- row's own coherence.
--
-- EVERY relation below is satisfied by the live CADL citation graph, read
-- read-only off the operator DB before this was written: candidate 12341 ->
-- evaluation run 137 (run_ts 2026-08-10T17:30:26, action session 2026-08-11),
-- daily_recommendations 172 (today_decision, CADL, 2026-08-11), pipeline run
-- 151 (complete, finished 2026-08-10T17:44:45), hypothesis 1 'A+ baseline'
-- via status-history row 1, trade 23 / entry fill 45 (2026-08-12T16:00:00).
-- ============================================================================
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
)
BEGIN
    SELECT RAISE(ABORT, 'provenance_corrections: the cited rows exist but do not form the citation graph this correction asserts (candidate->run, recommendation->run/ticker/kind, pipeline->run, status-history->hypothesis, registry name, fill->trade, trade<->candidate ticker). The citation is STRUCTURAL: a row may not claim a contemporaneous pair it does not have.');
END;

-- ============================================================================
-- APPEND-ONLY, ENFORCED (Codex R3 Major 6).
--
-- `ux_provenance_corrections_trade` only stops a SECOND row existing at the
-- same time. It does nothing about REWRITING the existing citation, and
-- nothing about DELETING it and reopening the trade for a different one --
-- so "V1 records provenance ONCE, enforced by the schema rather than by
-- prose" was true of the count and false of the content. Omitting UPDATE and
-- DELETE repo functions is a CONVENTION, and this table's whole purpose is to
-- hold a claim nobody can quietly revise.
--
-- The UPDATE trigger cannot simply reject everything: TWO of this table's own
-- FKs are `ON DELETE SET NULL` (`entry_fill_id` -- deliberately, so cohort
-- bookkeeping never vetoes the money-bearing split handler -- and
-- `risk_policy_id_at_correction`), and SQLite implements that action as an
-- UPDATE. So the trigger permits EXACTLY those two transitions, in the
-- value -> NULL direction only, with every other column byte-identical. The
-- "unchanged" test is NULL-AWARE (`IS`, not `=`): `NULL = NULL` is NULL, and
-- a NULL WHEN clause does not fire the trigger, which would have silently
-- allowed a rewrite of any nullable column.
-- ============================================================================
CREATE TRIGGER trg_provenance_corrections_append_only_update
BEFORE UPDATE ON provenance_corrections
FOR EACH ROW WHEN NOT (
    -- THE FK-DRIVEN nulling of one pointer, or the other, or both -- and the
    -- PARENT MUST ACTUALLY BE GONE (Codex R4 Minor 6). Recognising only the
    -- VALUE TRANSITION let a direct `UPDATE ... SET entry_fill_id = NULL`
    -- succeed while the fill still existed, after which the reader falsely
    -- reported the fill had been DELETED. Subqueries are prohibited in CHECK
    -- constraints but ARE permitted in a trigger WHEN clause -- verified at
    -- the prompt -- so the exception is stated as what it actually is.
    ((NEW.entry_fill_id IS NULL AND OLD.entry_fill_id IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM fills WHERE fill_id = OLD.entry_fill_id))
     OR (NEW.entry_fill_id IS OLD.entry_fill_id))
    AND ((NEW.risk_policy_id_at_correction IS NULL
          AND OLD.risk_policy_id_at_correction IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM risk_policy
                          WHERE policy_id = OLD.risk_policy_id_at_correction))
         OR (NEW.risk_policy_id_at_correction
             IS OLD.risk_policy_id_at_correction))
    -- ...and it must actually BE one of them, not a no-op cover for a rewrite
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
)
BEGIN
    -- SQL string literals do NOT concatenate by adjacency, so this message is
    -- one literal. (Caught by the migration failing to apply at all.)
    SELECT RAISE(ABORT, 'provenance_corrections is APPEND-ONLY: the only permitted UPDATE is the FK-driven nulling of entry_fill_id or risk_policy_id_at_correction. V1 records provenance ONCE per trade and there is no re-correction path.');
END;

CREATE TRIGGER trg_provenance_corrections_append_only_delete
BEFORE DELETE ON provenance_corrections
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'provenance_corrections is APPEND-ONLY: a correction cannot be deleted. Deleting one would reopen the trade for a different citation, which is the re-correction path V1 deliberately does not have.');
END;

-- Schema version bump. MUST be the FINAL statement before COMMIT per the
-- Phase 9 section A.0 R1 Critical #1 precedent (a truncated transaction would
-- leave the version stamp ahead of the schema).
UPDATE schema_version SET version = 36;

COMMIT;
