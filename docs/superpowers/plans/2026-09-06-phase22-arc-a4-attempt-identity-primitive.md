# 22-A4 -- The attempt-identity primitive, and clause 2's return on top of it (implementation plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** give `record_entry` a way to answer *"did MY attempt land?"* from the DURABLE ledger, and
then let clause 2 return on top of it -- a commit whose own return was lost is settled by a READ
that both **sees only committed state** and **identifies our attempt**, rather than by an alarm that
is honest but wrong about a durable row.

**Architecture:** one additive migration and four edits. (1) `trades.attempt_id TEXT` (nullable,
`CHECK length = 36`) plus a UNIQUE partial index, migration **0038**, `EXPECTED_SCHEMA_VERSION`
37 -> 38, one backup gate. (2) `insert_trade_with_event` gains an explicit `attempt_id` keyword and a
FOURTH schema-era INSERT branch that carries the column, so the token is written **in the same
INSERT as the row it identifies** -- co-durability by construction, not by argument. (3)
`record_entry` mints one `uuid4` per attempt at the point the attempt begins (after the entire
pre-existing gauntlet, so LOCK clause (c)'s ordering is untouched) and captures the connection's
own database path for the confirming read. (4) `_entry_transaction` records FOUR observations
instead of one (three NEW fields beside `committed`) -- did the body finish, did the commit return, and is the transaction RESOLVED -- on
BOTH paths, **observing rather than re-plumbing** (Python's own context manager already rolls back a
failed commit, MEASURED (3b), so the pre-arc path's behaviour is unchanged); `record_entry`'s
post-commit handler then settles a lost commit by opening a **FRESH connection** and reading
`WHERE attempt_id = ?`, returning SUCCESS with a `post_commit_warnings` entry when the row is there
and re-raising the ORIGINAL when it is not.

**Tech Stack:** Python 3.14.2 (`pyproject` targets >=3.11), sqlite3 with LEGACY transaction control
(`isolation_level=''`, measured), the live database in WAL (measured), `pytest` with `-n auto` in
`addopts`, `ruff check swing/` (`E,F,W,I,N,UP,B,SIM`).

**Spec:** [`docs/phase22-arc-a3-a4-commissioning-brief.md`](../../phase22-arc-a3-a4-commissioning-brief.md)
(the **22-A4** half only), which derives from
[`docs/22-a-merge-request.md`](../../22-a-merge-request.md) S4.4 -- the CHARC + RD split ruling of
2026-09-02 that REVERTED clause 2 and commissioned this primitive.
**Plan base:** `edfea928` (branch `22-a4-plan`, worktree `.worktrees/22-a4-plan`).

> ## REVIEW STATUS: **SIX ADVERSARIAL ROUNDS. BOTH RULINGS LANDED; ROUND 6 RAN ON THE FINAL SHAPE.**
>
> Rounds 1-5 at the binding `strong` tier, all five mechanical assertions passing every counted
> round; the loop honoured the mandated round-5 gate rather than relabelling itself converged.
> **Then TASK 0 WAS RULED (2026-09-06): RD ruled `uuid4` SATISFIES constraint 2** -- *"never
> reusable" means the mechanism contains no path that REISSUES a token; the ENGINE reissues a
> rolled-back rowid, an RNG does not* -- **and CHARC RATIFIED five schema items with ONE CONDITION
> that widened the envelope by one module** (the corrector's typed refusal, Task 1b). The plan was
> amended for both, and **round 6 ran on the frozen final shape.**
>
> **THIS PLAN IS NOT AUTHORIZED TO EXECUTE. TWO RD RIDER CLAUSES ARE ROUTED BACK AND OPEN**
> (S9 RD item 2), and `A4-R6-1` is the finding that forced this sentence: the plan cannot call
> itself final while holding an item its own governing director told it to stop-and-route on.
> **Both clauses were attached as load-bearing and both failed verification at the code:** the S7.7
> detection reason (*"no false-confirm mechanism"* -- REPRODUCED FALSE) and the S2.0.1 re-open
> trigger (*"fork"* -- `uuid4` holds no forkable state, MEASURED from source). **RD's RULING itself is
> unaffected by either** -- it rests on the no-reissue-path reading, which verifies -- so what is
> open is wording he owns, not the decision. **Task 0's checklist carries the open box; the ladder
> below is otherwise ready.** Full ledger: `.copowers-findings.md`.

**Baseline measured on `edfea928` before any change** (S11 records the number and the command).

---

## Global Constraints

- **ENVELOPE, as widened by CHARC's ruling of 2026-09-06.** The brief's text was
  `swing/trades/entry.py`, `swing/data/` (migration 0038, models, repo), tests -- **nothing in
  `swing/web/` or `swing/cli.py`**, which remains true and is why the warning this arc emits reaches
  the operator with no further caller work (verified at both sites: S1.5).
  **IT NOW ADDS EXACTLY ONE MODULE: `swing/trades/reconciliation_auto_correct.py`.**
  **CHARC's ground, and it is a ruling ABOUT this plan's own scoping:** *"I cannot rule the class
  binding one week and bank its next instance because the plan's envelope was drawn one module
  short."* The tier-2 corrector ADMITS `field_name="attempt_id"` today and the new trigger then
  ABORTs it, so the operator receives a raw `sqlite3.IntegrityError` -- **authorize-then-abort, the
  class he ruled on 2026-09-01 after five instances in 22-A.** The widening is bounded to the typed
  refusal and its test (Task 1b); **no other change to that module, and no sweep.**
- **RD'S THREE CONSTRAINTS ARE BINDING AND ARE NOT NEGOTIABLE BY THIS PLAN** (S1). If a design
  cannot satisfy all three, the plan STOPS and routes rather than designing around one.
- **THE LIVE DATABASE IS NOT TOUCHED.** It is at v37 with real money-bearing trades and four live
  latch links. This plan did NOT open it; the migration set on disk tops out at
  `0037_latch_order_mandate_links.sql`, whose final statement is `UPDATE schema_version SET version
  = 37` (read from the FILE). Every test in this plan builds its own `tmp_path` database. The live
  migration is an OPERATOR-WITNESSED, POST-MERGE gate (S6) and belongs to nobody in this worktree.
- **Branch:** all work on the arc branch; conventional commits (`feat(data):`, `feat(trades):`,
  `fix(trades):`, `test(...)`). **ZERO `Co-Authored-By`. No `--no-verify`. No amend.**
- **TDD:** failing test -> see it fail -> minimal implementation -> see it pass -> commit, one
  red/green cycle per task. **Every regression assertion is computed under BOTH the pre-fix and the
  post-fix path**, and this plan states both values for every test it specifies.
- **ONE MIGRATION, ONE VERSION BUMP, ONE ATOMIC FILE** (the 0037 header's own rule): the runner
  applies a version once and only when strictly greater than the database's current version, so
  anything added to `0038` after any database has recorded v38 never runs on that database again,
  silently, with CI green because fresh fixtures always apply the whole file.
- **`ruff check swing/` clean.** Test-file lint is out of scope; match each test file's existing
  style.
- **ASCII in user-facing strings.** The new warning text reaches the CLI's stderr through 22-A3's
  reader, and Windows cp1252 crashes on non-ASCII (`pytest` `capsys` hides it). The warning is
  ASCII by construction and is additionally passed through 22-A3's `ascii_safe` on the CLI side.

---

## S1. THE THREE CONSTRAINTS, RE-DERIVED AGAINST THE CODE -- **and which of them exist today**

> **This section runs BEFORE any design, because the arc's own governing rule is applied to itself:**
> *a ruled mechanism carries the preconditions that make its evidence admissible, and names which of
> them exist today.* That rule was earned four times in one week. Nothing below is inherited from
> the brief; every claim carries **the method that produced it**, and three of the brief's own
> statements are corrected or sharpened here.

**Summary, stated first so the answer is not buried:**

| RD constraint | Does it exist TODAY? | What supplies it |
|---|---|---|
| **1. CO-DURABLE** | **The MECHANISM exists; the TOKEN does not.** Everything `_record_entry_inner` writes is already inside one transaction on both paths (measured). Nothing in it identifies the attempt. | 0038's column, written in the entry INSERT itself (S2.0). |
| **2. UNIQUE PER ATTEMPT** | **NO. Nothing in the schema or in the request is unique per attempt.** `trades.id` is a bare rowid (measured: reused after rollback); `event_ts` is second-granularity `datetime.now()` at both call sites; no other candidate exists. | A client-minted `uuid4` plus a UNIQUE partial index (S2.0). |
| **3. DURABLE-VISIBILITY READ** | **The CAPABILITY exists and is UNUSED. No production path opens a second connection to confirm a write.** `open_connection` exists, `_resolve_main_db_path` exists, and a fresh reader is measurably unblocked in both journal modes -- but nothing wires them to the entry path, and the database path is not otherwise reachable from inside `record_entry`. | The probe in S2.3, assembled from the two existing pieces. |

### S1.1 CO-DURABLE -- **the mechanism EXISTS, the token does NOT**

*Constraint, verbatim:* **written in the SAME transaction as the row it identifies. Anything else is
a stamp (gotcha #30).**

**Method: read `record_entry` and `_entry_transaction` end to end, then MEASURE the connection's
transaction-control mode rather than assume it.**

- Both transaction paths put the whole of `_record_entry_inner` inside one transaction.
  `swing/trades/entry.py:1035-1160`: `immediate=False` yields inside `with conn:`; `immediate=True`
  yields between an explicit `BEGIN IMMEDIATE` and `conn.commit()`.
- **The deferred path's atomicity rests on a runtime property worth measuring rather than assuming:
  `with conn:` does NOT begin a transaction** -- sqlite3's legacy mode begins one implicitly at the
  first DML. If the connection were in autocommit, `with conn:` would commit nothing, each statement
  would land separately, and co-durability would be vacuous. **MEASURED on this runtime** (a
  connection from `swing/data/db.py:open_connection` on a HEAD database): `conn.isolation_level ==
  ''` and `conn.autocommit == -1` (`sqlite3.LEGACY_TRANSACTION_CONTROL`). The implicit deferred
  BEGIN is in force, so the trade INSERT, the `risk_policy_id_at_lock` UPDATE, the entry event, the
  entry fill and the watchlist archive commit together or not at all.
- **The only production INSERTER of `trades` rows is `record_entry`** -- and the first draft of this
  bullet stopped there, which was the round-4 CRITICAL (`A4-R4-1`). Method for the INSERT half, a
  READ rather than a token count -- **and the command's REAL output is reported, not a tidied version of it**
  (`A4-R7-6`). `grep -rn "INSERT INTO trades" swing/` returns **FIVE hits, not three**: the three
  era-branches of `insert_trade_with_event` (`swing/data/repos/trades.py:246`, `:305`, `:369`),
  **plus `INSERT INTO trades_new` at `0014_phase7_state_machine_and_fills.sql:197`** (the historical
  Phase-7 rebuild -- a DIFFERENT TABLE that the substring matches), **plus a `__pycache__` binary
  match**. **Three exact `trades` targets; five substring hits.** The earlier text stated the
  conclusion and the command as if they agreed, which is the "state what your grep PROVES" rule
  failing on the bullet that invokes it. **(r5)'s walk must therefore parse the TABLE TOKEN with a
  word boundary and exclude caches, or it will count `trades_new` as an unreasoned writer and its
  declared counts will be wrong.** `grep -rn "insert_trade_with_event" swing/`
  returns **exactly one** call site, `swing/trades/entry.py:1421`. The f-string-INSERT family was
  enumerated separately (`fill_envelope_identity.py:91`, `latch_order_intents.py:143`,
  `provenance_corrections.py:90`, `risk_policy.py:212`) and none targets `trades`.
- **THE UPDATE CENSUS, WITH THE GREP THAT PRODUCED IT AND ITS COUNT** (CHARC, 2026-09-06 -- the
  first version of this bullet named one site and left the other for the next reviewer to re-find,
  which reads as an incomplete census even when the omitted site is harmless).
  **`grep -rn 'UPDATE trades SET {' swing/` returns EXACTLY TWO sites, and both were READ:**
  - `swing/data/repos/trades.py:735` -- `update_trade_review_fields`. **BENIGN, and classified rather
    than merely counted:** its `set_clauses` list is built from FIXED literal column names in code
    (the eleven review columns, plus a PRAGMA-gated `failure_mode`); **no caller-supplied column name
    reaches the interpolation.** It cannot write `attempt_id`.
  - `swing/trades/reconciliation_auto_correct.py:2085` -- the generic one, below. **This is the one
    that matters.**
- **AND THE GENERIC UPDATER IS WHY THE TRIGGER EXISTS.**
  `swing/trades/reconciliation_auto_correct.py:_update_journal_field` composes
  `UPDATE trades SET {field_name} = ?` with the COLUMN NAME INTERPOLATED, and its safety rests on an
  allowlist-by-EXCLUSION: `_RESERVED_JOURNAL_FIELDS` (`:178-183`) names five coupled columns, and
  `validate_trade_correction` (`swing/trades/reconciliation_validators.py:171`) validates only
  `current_stop` and `state`. **A new `trades` column is therefore WRITABLE BY DEFAULT through the
  tier-2 operator-truth path the moment it exists** -- and a written-after-the-fact `attempt_id`
  destroys exactly the property this arc is built on: attempt A rolls back, an operator correction
  assigns A's token `X` to a DIFFERENT trade in the same ticker, and A's probe confirms it.
  **This is the D36 lesson arriving on the plan that quotes D36:** a dynamic-SQL sweep was done for
  INSERTs and not for UPDATEs, and "the only writer" was asserted from the narrower search.
  **Closed at the SCHEMA level in S2.0** (an immutability trigger), which covers this writer and
  every future one, rather than by editing an allowlist in a module outside the envelope.
- **What does NOT exist:** no column, no side table and no in-transaction artifact identifies the
  ATTEMPT. `trade_events` does get a row in the same transaction, but its `ts` is the caller's
  `event_ts` and its id is another bare rowid; neither identifies an attempt.

**Verdict: constraint 1's mechanism is already true of anything written inside
`_record_entry_inner`. What is missing is a value to write.**

### S1.2 UNIQUE PER ATTEMPT -- **does NOT exist, and the brief's REASON is right for a reason it does not give**

*Constraint, verbatim:* **never reusable across attempts; survives rollback-and-retry without
collision. Rowid fails by construction.**

**Method: read the schema for `trades`, then REPRODUCE the reuse rather than cite it.**

- **`trades.id` is `INTEGER PRIMARY KEY` -- a bare rowid alias with NO `AUTOINCREMENT`**
  (`swing/data/migrations/0014_phase7_state_machine_and_fills.sql:132`, the current definition after
  the Phase-7 rebuild). **This is a correction worth stating.** CLAUDE.md's gotcha and the brief both
  explain the reuse via *"`sqlite_sequence` rolls back with the insert, so `AUTOINCREMENT` does not
  pin it."* That sentence is TRUE, and it is about a table `trades` is not. On `trades` there is no
  `sqlite_sequence` row at all: the next rowid is `max(rowid) + 1`, so reuse after a rollback is not
  a subtlety, it is the DEFAULT. The gotcha's stronger form still matters, because it forecloses
  "just add AUTOINCREMENT" as a cheap fix.
- **REPRODUCED, both forms** (scratch database, this runtime): a plain-rowid table and an
  `AUTOINCREMENT` table each had row 1 inserted and rolled back; a SECOND connection then inserted a
  different row and **was issued id 1 in both cases**. `WHERE id = ?` therefore confirms a concurrent
  writer's row as ours -- `22A-FIX-R10-03` re-derived on this tree rather than quoted from it.
- **No other per-attempt candidate exists.** The nearest is `EntryRequest.event_ts`, and it is
  **`datetime.now().isoformat(timespec="seconds")`** at BOTH production call sites
  (`swing/cli.py:769`, `swing/web/routes/trades.py:1623`) -- second granularity, so two attempts in
  the same second are indistinguishable, and a retry after a failed entry is exactly the case where
  two attempts arrive close together. `pre_trade_locked_at` is derived from `entry_date` and is
  identical across retries by construction. Nothing else on `EntryRequest` is minted per call.

**Verdict: constraint 2 does NOT exist today, in the schema or in the request. It must be created.**

### S1.3 DURABLE-VISIBILITY READ -- **the capability exists, the wiring does not, and one MEASURED fact changes the design**

*Constraint, verbatim:* **the confirming read runs where only committed state is visible: a FRESH
connection, or after a PROVEN resolution. A failed rollback VOIDS the read.**

**Method: read the connection layer for what is available, then MEASURE the four behaviours the
design depends on instead of reasoning about SQLite from memory.**

- **Available today:** `swing/data/db.py:open_connection(path, *, busy_timeout_ms=...)` -- the single
  opener every connection in the project routes through -- and
  `swing/data/db.py:_resolve_main_db_path(conn)`, which answers `PRAGMA database_list` and returns
  `None` for an in-memory database. `connect()` also exists but performs a schema-version check the
  probe does not want.
- **NOT available:** `record_entry` receives a `sqlite3.Connection` and has no other handle on the
  database. There is no factory, no path, and no config guaranteed present (`cfg` is documented as
  legitimately `None`). **So the path must come from the connection itself.** `cfg.paths.db_path` is
  explicitly REJECTED as the source in S2.1: a config value is not provenance for which database
  this connection is attached to.
- **MEASURED (1) -- a fresh connection cannot see the writer's uncommitted row.** With connection A
  holding an open transaction containing an uncommitted INSERT, a newly opened connection B read
  `COUNT(*) = 0`. This is the structural half of VISIBILITY, and it holds without any cooperation
  from A.
- **MEASURED (2) -- a fresh READER is not blocked by an open write transaction, in EITHER journal
  mode.** In WAL (the live mode: `PRAGMA journal_mode` reads `wal` on a database built by
  `ensure_schema`) readers never block; in rollback-journal mode a reader is admitted while the
  writer holds RESERVED. The probe does not deadlock behind the writer merely because a transaction
  is open.
- **MEASURED (3), and this one CHANGES THE DESIGN -- in the classic commit-time failure the fresh
  read is BLOCKED until the writer's transaction is resolved.** Reproduced with no proxy at all:
  connection B holds an open read transaction, connection A inserts and calls `commit()`, and the
  commit raises `OperationalError: database is locked` with `A.in_transaction` still **True**. A
  third, freshly-opened connection then ALSO got `database is locked`, because the failed commit
  leaves A holding a PENDING lock. **After `A.rollback()` the same fresh read succeeded and returned
  absent.** So the ruled order -- (i) resolve, (ii) open a FRESH connection, (iii) read -- is not
  merely conservative: the resolution is what makes the read POSSIBLE in the commonest
  commit-failure shape.
- **MEASURED (3b) -- AND THE TWO COMMIT FORMS BEHAVE DIFFERENTLY, WHICH THE FIRST DRAFT OF THIS PLAN
  GOT WRONG** (`A4-R1-2`; the finding was correct and this line replaces the claim it disproved).
  In the SAME world, with the SAME lock held by B:
  - `conn.execute(INSERT); conn.commit()` -> the commit raises and `conn.in_transaction` is **True**;
  - `with conn: conn.execute(INSERT)` -> the automatic commit raises and `conn.in_transaction` is
    **False**.

  **`sqlite3.Connection.__exit__` rolls the transaction back when its own commit fails** on Python
  3.14.2, exactly as the sqlite3 documentation says. The first draft measured the direct form and
  generalised it to the context manager; it does not generalise. **The consequence is a
  SIMPLIFICATION:** the deferred path already resolves itself, so this arc adds no rollback there,
  changes no exception identity there, and only OBSERVES. (The sub-case where `__exit__`'s own
  rollback ALSO fails is not constructible on this machine, and the design does not need it to be:
  the wrapper READS `conn.in_transaction` rather than assuming either answer -- see S2.2.)
- **MEASURED (4) -- `conn.in_transaction` is False after a commit that returned**, so a lost-commit
  handler that finds `in_transaction` True is looking at a commit that did NOT land. That is what
  makes rule (i)'s cost provably zero (S2.4).

**Verdict: constraint 3's ingredients exist and are unused. Nothing in `swing/` opens a second
connection to confirm a write; this arc is the first.**

### S1.4 THE BRIEF'S OTHER PREMISES, re-derived

- **"Clause 2 reverted; the commit-raises path keeps re-raising"** -- **HOLDS.** `_settle_lost_commit`
  and `_entry_is_durable` are GONE: `grep -rn "_settle_lost_commit\|_entry_is_durable" swing/ tests/`
  returns three hits, all three inside the declaration comment at `swing/trades/entry.py:979-999`
  recording what was removed. The residual is pinned by
  `tests/trades/test_22a_task9_entry_wiring.py:3191`
  (`test_CONTRACT_a_commit_whose_own_return_was_LOST_re_raises`, parametrised over both paths).
  **That test is this arc's pre-fix half and is REWRITTEN, not deleted** (S3 (c), **Task 4**).
- **"`_CommitOutcome.committed` is an observation of the commit's own return"** -- **HOLDS**: set on
  the statement after `commit()` returns on the immediate path (`entry.py:1128`) and after the
  `with conn:` block on the deferred path (`entry.py:1067`).
- **"Both `_entry_transaction` paths are bound"** -- **HOLDS, and it costs LESS than the first draft
  of this plan claimed.** That draft said a commit raising inside `__exit__` leaves the transaction
  OPEN with no rollback attempted, and proposed adding one; **MEASURED (3b) disproves it** --
  `__exit__` rolls back, `in_transaction` reads False, and the pre-arc path already resolves itself.
  So this arc adds **no rollback and no exception-identity change** to the deferred path; it adds
  only the three NEW observation fields (S2.2). The one thing it must still handle is the residual
  where
  `__exit__`'s own rollback failed, and it handles that by READING `conn.in_transaction` instead of
  assuming either outcome.
- **CHARC's shape -- `attempt_id TEXT` nullable, client-generated `uuid4`, same INSERT, UNIQUE
  partial index, migration 0038 ADDITIVE, one ADD COLUMN plus one index plus the version bump** --
  **SURVIVES VERIFICATION, with ONE addition and ONE documented divergence** (S2.0). The addition is
  a `CHECK (attempt_id IS NULL OR length(attempt_id) = 36)`; the divergence is that the token is
  **not** a `Trade` dataclass field and is **not** read by `_row_to_trade`.
- **A DEFECT THE NEW INDEX INTRODUCES, found by verifying the premise rather than by review**
  (fixed in S2.5): `_record_entry_inner`'s IntegrityError mapper reads
  `if "UNIQUE" in str(exc) and "trades" in str(exc)` (`entry.py:1489`) and re-raises as
  `DuplicateOpenPositionError`. **MEASURED:** a `ux_trades_attempt_id` violation produces
  `UNIQUE constraint failed: trades.attempt_id`, which satisfies both substrings -- so without a fix
  the new index would report *"Already an open position in AAA (race-detected)"* over a ticker that
  has no open position, on the money-bearing path. Today `trades` carries **exactly one** UNIQUE
  index (`SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='trades'` on a HEAD
  database returns `ux_trades_one_open_per_ticker` plus two non-unique indexes), which is why the
  loose match has been correct until now.

### S1.5 The 22-A3 caller half -- **verified present, so this arc adds NO caller work**

`post_commit_warnings` now has readers at both surfaces: `swing/web/routes/trades.py:2239` / `:2363`
(assembled and delivered into the notice partial) and `swing/cli.py:902-937` (coerced,
ASCII-printed, exit status unchanged). A clause-2 warning therefore reaches the operator through
machinery that already exists and has already been operator-witnessed in a browser.

### S1.6 Everything else this plan leans on

- **No `record_entry` call site runs against a below-HEAD schema TODAY -- and that stops being true
  the moment this arc bumps HEAD, which is the point.** Method: take the six test files mentioning
  both `record_entry` and `target_version` and READ each. Two are prose only
  (`case_registry_22a.py:386`, `test_exit.py:36`); `test_22a_task4_authorization_ladder.py` and
  `test_22a_task9_entry_wiring.py` migrate to 36 and then to **the literal 37**;
  `test_entry.py` and `test_phase7_entry_risk_policy_stamp.py` migrate to `EXPECTED_SCHEMA_VERSION`.
  **The literal-37 sites mean "migrate to HEAD" and say "migrate to 37"**, so after the bump they
  would leave a v37 database and drive `record_entry` against a schema with no `attempt_id` column
  -- silently exercising the pre-v38 drop path (S7.5) instead of the production one. They are part
  of the mirror family below and are re-spelled, not left to rot.
- **No production or test path calls `record_entry` with an in-memory database.** Of the 28 test
  files containing `:memory:`, exactly one also mentions `record_entry`, and its `:memory:`
  connection is a scratch database comparing a JSON reader against a SQLite one
  (`test_22a_task9_entry_wiring.py:1749`); it is never passed to `record_entry`.
- **`trades` has 57 columns and `models.Trade` has 56 fields**, and the difference is exactly
  `{risk_policy_id_at_lock}` (MEASURED by comparing `PRAGMA table_info(trades)` against
  `dataclasses.fields(Trade)` on a HEAD database). That single precedent -- a `trades` column
  written by the entry service in the same transaction and deliberately absent from the dataclass
  and from all four SELECT projections -- is the ground for S2.0's divergence, and the measurement
  itself becomes a DRIFT COMPARATOR in Task 2.
- **The migration runner discovers files by glob** (`_MIGRATIONS_DIR.glob("*.sql")`, applied when
  `current < version <= min(target_version, EXPECTED_SCHEMA_VERSION)`), so `0038` plus the constant
  bump is the whole registration. **Every migration since 0027 carries its own backup gate**
  (verified by reading `run_migrations`'s gate list, 0027 through 0037 inclusive), so 0038 gets one
  -- STRICT equality `current_version == 37`, per the `pre_version == (target - 1)` gotcha.
- **The version bump's mirror family has SIX SPELLINGS, and the first draft of this section found
  two.** `A4-R1-5` named a third and a fourth; re-counting by grepping each SPELLING SEPARATELY
  rather than the concept found two more. This is the recipe's own lesson -- *a token grep bounds a
  family from BELOW, and only a READ establishes a manifest* -- arriving on the plan that quotes it,
  so the corrected census is stated **with the method for each row and as a FLOOR**:

  | # | spelling | count | how found |
  |---|---|---|---|
  | 1 | `EXPECTED_SCHEMA_VERSION == 37` | 26 | grep on the constant |
  | 2 | bare-literal assertions -- `version`, `ver[0]`, `version_row[0]`, `row[0]`, `post`, `cur.fetchone()[0]` `== 37` | 11 | regex over `assert <expr> == 37` |
  | 3 | `_current_version(conn) == 37` | 4 | named by `A4-R1-5`; a CALL-expression form neither original grep could match |
  | 4 | **`versions[-1] <= 37`** -- the L3 migration-authorization ceiling in `tests/data/test_no_schema_change_v3.py:41` | 1 | named by `A4-R1-5`; an INEQUALITY, structurally invisible to any equality grep |
  | 5 | chained `version == EXPECTED_SCHEMA_VERSION == 37` | 1 | the same regex, read rather than counted |
  | 6 | **`target_version=37` call sites** -- **12** `run_migrations(...)` calls and **3** direct `_phase22_arc_a_backup_gate(...)` calls | 15 total, of which only **7** are migrate-to-HEAD | found by following row 4's thread; not assertions at all, so no assertion grep could see them |

  **Row 4 is the load-bearing one and it is not a chore: it is an AUTHORIZATION GATE.** Its own
  comment says raising the ceiling is *"the guard WORKING AS DESIGNED for an AUTHORIZED migration
  (CHARC's section-3 pass). An UNAUTHORIZED one must still trip it, which is why the bump belongs in
  the same commit as the migration and nowhere else."* Task 1 honours that literally.
  **Row 6 is the subtle one, and the first draft of this row was WRONG about it** (`A4-R4-10`; it
  called all 15 HEAD aliases and said all 15 get re-spelled). The correct split, by READING each:
  **8 stay pinned at 37** -- every occurrence in `tests/data/test_22a_task2_migration_0037.py`, whose
  subject IS migration 0037 or which passes 37 as a literal ARGUMENT to the backup gate under test.
  **7 build a v36 world and then want production HEAD**, and those **KEEP their 37 call and gain a
  SECOND one to `EXPECTED_SCHEMA_VERSION`** -- they are not retargeted, because a single 36 -> 38
  jump would bypass the new gate entirely (Task 1 states the mechanism). **Sites whose intent really
  is an OLDER schema (`target_version=36` before seeding a pre-barrier world, `target_version=16` in
  `test_exit.py`) are EXCLUDED and must not be touched.** Two of the four
  `_current_version(...) == 37` sites (row 3) are likewise 0037-result assertions and stay.
  **No total is quoted, deliberately:** the families OVERLAP (a chained
  `version == EXPECTED_SCHEMA_VERSION == 37` is counted in rows 1 and 5), so a single number would be
  a manifest that cannot be reconciled. The manifest is the six greps plus a read of every hit.
  **The CLOSURE CHECK is not the grep and never was: it is the full fast suite**, which fails on
  every missed equality and on the inequality ceiling. Row 6 is the exception -- it fails NOTHING,
  which is exactly why it had to be found by reading.

---

## S2. THE DESIGN DECISIONS, OWNED

### S2.0 THE SHAPE -- decision: **CHARC's shape, with ONE addition and ONE divergence, both argued**

**FOUR shapes are on the table. The first three satisfy constraints 1 and 3 identically and differ
only in RISK; the fourth differs on CONSTRAINT 2 ITSELF, which is why it is a ruling and not a
preference.**

| shape | co-durable? | unique? | visible? | cost |
|---|---|---|---|---|
| **(S-a)** column written **in the entry INSERT**, plus a `Trade` dataclass field and a `_row_to_trade` reader (CHARC's stated shape) | by construction (one statement) | index | probe | a FOURTH INSERT branch **and** a FIFTH SELECT-projection era **and** a new positional index in `_row_to_trade` |
| **(S-b)** column written **in the entry INSERT** via an explicit `attempt_id=` keyword on `insert_trade_with_event`; **no** dataclass field, **no** reader | by construction (one statement) | index | probe | a FOURTH INSERT branch only |
| **(S-c)** column written by a same-transaction `UPDATE trades SET attempt_id = ? WHERE id = ?` in `_record_entry_inner`, exactly as `risk_policy_id_at_lock` already is | by transaction atomicity (one inference step) | index | probe | no repo INSERT change at all |
| **(S-d)** **(S-b) PLUS a durable ALLOCATOR**: a side table burns an identifier in its OWN committed transaction BEFORE the entry attempt; that identifier is then written into `trades.attempt_id` in the entry INSERT | **unchanged from (S-b)** -- the token is still in the same INSERT, and the allocator row is never used as evidence that the trade landed | **STRUCTURAL**, not probabilistic | probe (unchanged -- it still reads `trades`) | a second table, a second migration object, and **a second COMMIT on the money path before the entry** |

> ## **DECISION: (S-b) -- RULED BY RD 2026-09-06, not chosen by this plan.**
>
> Rounds 1-3 walked this from *"the index makes a collision impossible"* (false) to *"the allocator
> is a stamp"* (false) to the actual position: **(S-b) satisfies RD constraint 2 PROBABILISTICALLY
> and (S-d) satisfies it STRUCTURALLY.** The plan then STOPPED and routed rather than narrowing a
> binding constraint by judging the residual small enough. **RD RULED on 2026-09-06; the question is
> CLOSED and this block records the answer, not the ask.**
>
> **RD's ruling, and its REASON, because the reason is the part that binds future appeals:**
> *"never reusable" = the mechanism must contain **no path that REISSUES** a token.* **The rowid
> failed because the ENGINE hands a rolled-back id to the next insert** -- reuse is an active,
> designed-in mechanism. `uuid4` has no such path; a repetition is an RNG failure, not a behaviour of
> the mechanism. **Collision-resistance is already this system's admissibility standard** (the H1
> amendment pinned by sha256; broker snapshots by digest), so the ruling demands no certainty beyond
> what the existing evidence chain rests on.
>
> **(S-d) is NOT deleted. It is BANKED IN FULL at S2.0.1 with a named re-open trigger** -- refusing
> it today is a **D46 application** (more machinery, a second commit surface and a separate
> connection ON THE MONEY PATH, against a failure with no mechanism and no observed instance), and
> that calculus changes if the platform ever acquires a correlated-RNG hazard.

*Why (S-d) is on the table at all, and why the first draft was WRONG to wave it off* (`A4-R2-1`).
That draft rejected a durable reservation on the ground that it "makes it a STAMP (gotcha #30)".
**That reasoning is false and the reviewer was right to say so:** the allocator's row is not
provenance for anything -- the token still lands in the entry INSERT, and the confirming read still
queries `trades`. Nor does an allocator-commit failure recreate the ambiguity: it happens BEFORE the
entry transaction, so nothing has landed and the identifier is simply abandoned. **(S-d) is a real
alternative that satisfies RD constraint 2 STRUCTURALLY, which is more than (S-b) does.**
*Why this plan nevertheless proposes (S-b):* (S-d) buys structural uniqueness against an exposure
measured at about `n^2 / 2^123` (~1e-27 at `n = 10^5`, S7.7) and pays a table, a second migration
object, an attempt-log-by-side-effect this arc explicitly declined at S2.6, and **an extra COMMIT on
the money-bearing path** whose own failure modes must then be contained. That is a judgment about
proportion, and **a plan may not settle a binding constraint by judgment** -- so S9 routes the
choice to RD with both options costed. **If he reads constraint 2 as requiring structural
uniqueness, (S-d) is the design and this plan's task ladder gains one table.**

*Why not (S-c), despite being the smallest diff:* co-durability would be true because the
transaction is atomic, which is one inference away from being true because it is the same statement.
This arc's whole subject is the difference between evidence that is admissible by construction and
evidence that is admissible by argument, and it would be a poor advertisement to take the arguable
form of its own primitive. (S-c) also loses the mechanical check the brief asks for: a future entry
INSERT that omits the column would silently write NULL, and no static walk over INSERT column lists
could see it.

*Why not (S-a) -- the DIVERGENCE from CHARC's shape, stated rather than absorbed:* the `Trade`
dataclass field and the `_row_to_trade` reader buy nothing this arc uses and cost a change to the
hottest read path in the repo. `_row_to_trade` is **positional** over a 56-entry index map, and
`_trade_select_cols` composes **four** era projections; adding the column properly means a fifth era
and a new index in all of them, touching every `trades` reader in the codebase for a token no reader
wants. Adding the field WITHOUT widening the projections is worse: `Trade.attempt_id` would read
`None` for a row that carries a token -- a model that lies, which is the `#31` class. And the
project already has exactly this precedent, measured rather than recalled: **`risk_policy_id_at_lock`
is 1 of 57 `trades` columns, is written by the entry service inside the entry transaction, and is
absent from `models.Trade` and from all four projections** (S1.6). The token is INTERNAL attempt
identity, never domain data, and keeping it off the domain model also keeps it from being adopted as
a business key later.

**The divergence was not a silent one, and it is now RULED:** it was routed to CHARC as a named
question and he **ACCEPTED it on 2026-09-06**, having verified 57 / 56 / `{risk_policy_id_at_lock}`
against the live database himself. It is made mechanical rather than merely explained --
**Task 1** (not Task 2; the mirrors were merged into one commit at `A4-R2-3`) adds a
**DRIFT COMPARATOR** -- the `trades`
column set minus `Trade`'s field set must equal exactly `{"risk_policy_id_at_lock", "attempt_id"}`
-- so the omission is an enumerated, reasoned exclusion list that fails loudly the day a third
column joins it. Per the amended gotcha #11, **the comparator is the mandatory member of the mirror
set**, and it is the one mirror that does not depend on choosing the right grep.

**THE ADDITION TO CHARC'S SHAPE:**
`CHECK (attempt_id IS NULL OR (typeof(attempt_id) = 'text' AND length(attempt_id) = 36))`.
**THE `typeof` GUARD IS NOT DECORATION, AND ITS ABSENCE WAS ROUND 6'S SHARPEST NEW FINDING**
(`A4-R6-4`). With `length(...) = 36` alone, **MEASURED: a 36-BYTE BLOB passes the CHECK and sits in
the UNIQUE index ALONGSIDE its byte-identical TEXT twin** -- `[(1, 'text', 36), (2, 'blob', 36)]` --
which **falsifies this section's own "at most ONE LIVE row per token" claim at the schema boundary**.
Adding `typeof(attempt_id) = 'text'` rejects the BLOB (measured). The asymmetry is worth naming: the
BANKED integer branch at S2.0.1 already carried a `typeof` guard, added in round 4 for exactly this
class, and **the SHIPPING text branch did not** -- the fix was applied to the design that is not
being built. The Python mirror is `isinstance(attempt_id, str)`, not a length check alone, and
(m1)/(m6)/(r3) each gain a 36-byte-BLOB rejection case.
Without it, `attempt_id = ''` is a legal, non-NULL, INDEXED value -- and CLAUDE.md carries a
standing gotcha about exactly this (`... or ""` colliding with SQL nullability), so the empty string
is a value this codebase has produced before. Two empty-string tokens would collide on the UNIQUE
index and REFUSE a money-bearing entry. **MEASURED:** with the CHECK in place,
`INSERT ... attempt_id=''` raises `CHECK constraint failed: attempt_id IS NULL OR length(attempt_id)
= 36`, and a 36-character value is accepted. The CHECK is deliberately about LENGTH and not about
hex-and-dashes: the schema should not pin the generator's textual form, and length alone excludes
the empty string and obvious junk. The 36 is mirrored in Python as one constant and the two
representations are compared by a drift test that reads the CHECK text back out of `sqlite_master`
(MEASURED: `ALTER TABLE ... ADD COLUMN ... CHECK (...)` is preserved verbatim in the stored schema).

**What the UNIQUE index actually buys -- STATED PRECISELY, because the first draft of this plan
overstated it and the overstatement was the round-1 CRITICAL (`A4-R1-1`).** That draft said the index
makes a collision "IMPOSSIBLE TO COMMIT", which is FALSE for the case that matters: **a rolled-back
token leaves no trace in the index**, so an attempt that later minted the same value would be
admitted. What the index does buy, and it is worth the one line of DDL:

- **At most ONE LIVE row per token.** The probe can therefore never find two rows, and
  "present" is never ambiguous among committed rows.
- **A SYSTEMATIC token-reuse BUG becomes a loud pre-commit failure** -- a mint that returns a
  constant, a caller that reuses a token, a copy-paste in a future writer. That is the failure mode
  a design can actually have, and the index catches it the first time two live rows would share a
  value.
- **It does NOT make uniqueness structural.** Uniqueness ACROSS attempts rests on `uuid4`, so it is
  PROBABILISTIC. That is declared at S7.7 with its arithmetic, pinned by execution at test (RD-b2),
  and routed to RD at S9 as a question about how his constraint 2 should be read -- because the
  constraint's own gloss ("rowid fails by construction") is about an identifier the system
  RE-ISSUES, and nothing re-issues a `uuid4`.

It is partial (`WHERE attempt_id IS NOT NULL`) because legacy rows, every non-entry test writer, and
any pre-v38 row carry NULL, and **MEASURED:** two NULL-token rows coexist happily under it.

**THE SECOND ADDITION TO CHARC'S SHAPE, AND IT IS NOT OPTIONAL: AN IMMUTABILITY TRIGGER.**

```sql
CREATE TRIGGER trg_trades_attempt_id_immutable BEFORE UPDATE OF attempt_id ON trades
BEGIN SELECT RAISE(ABORT, '22-A4: trades.attempt_id is WRITE-ONCE, set by the entry INSERT ...'); END;
```

*Why (round 4's CRITICAL, `A4-R4-1`):* `swing/trades/reconciliation_auto_correct.py` composes
`UPDATE trades SET {field_name} = ?` with the column name INTERPOLATED, allowlisted **by
exclusion**. A column added to `trades` is writable through the tier-2 operator-truth path from the
moment it exists, and a token that can be re-assigned after insertion is not identity at all -- it
enables a FALSE SUCCESS in which A's rolled-back token is attached to somebody else's row and A's
probe confirms it. *Why a TRIGGER and not an allowlist entry:* the trigger lives in the migration
(in envelope), and it covers **every** writer including ones not yet written, where reserving
`("trades", "attempt_id")` covers exactly one module -- and that module is outside this arc's
envelope. **The allowlist entry is still worth having as a MESSAGE-QUALITY belt** (a typed
`ReservedJournalFieldError` reads better than a trigger ABORT surfacing as `IntegrityError`) and is
BANKED at S8 and routed at S9 rather than taken here.
*Note on shape:* the trigger has NO `WHEN` clause, so the NULL-`WHEN` fail-open gotcha does not
apply. It is unconditional -- it refuses even a no-op UPDATE that merely names the column -- because
a writer that names the column is a writer that should not exist. Reversible in one statement
(`DROP TRIGGER trg_trades_attempt_id_immutable;`), recorded in the migration's reversibility header.

**Why one token on the `trades` row certifies the WHOLE attempt.** The entry transaction writes a
trade row, a trade event, a fill, the risk-policy stamp and possibly a watchlist archive. They are
atomic together (S1.1). So the presence of the token on the trade row is not evidence about the
trade row alone; it is evidence that the transaction COMMITTED, which is exactly the fact clause 2
needs.

### S2.0.1 THE (S-d) BRANCH -- **NOT TAKEN, BANKED IN FULL, WITH A NAMED RE-OPEN TRIGGER**

> **RD's disposition, 2026-09-06: banked rather than deleted.** *"If a platform change ever
> introduces a correlated-RNG hazard -- fork, VM snapshot-resume -- the fork re-opens with the design
> already executable."* **THE RE-OPEN TRIGGER IS THE SPECIFICATION'S REASON FOR EXISTING**, so it is
> stated as a condition an operator or director can recognise: *any change that lets two processes or
> two resumed images draw from the SAME entropy stream.*
>
> **BUT "FORK" IS STRUCK FROM THE TRIGGER LIST AND ROUTED BACK -- IT DOES NOT VERIFY AT THE CODE**
> (`A4-R6-11`). **MEASURED, by reading CPython 3.14's `uuid.uuid4` source:** it is
> `int.from_bytes(os.urandom(16))` **per call**. There is no process-local PRNG whose state a `fork`
> would clone, so **acquiring `fork` by porting to a POSIX platform does not, by itself, create the
> correlated state the trigger is meant to detect** -- it would fire on an ordinary platform port
> with no hazard present, and activate a materially more expensive design on the money path.
> **What SURVIVES as a trigger:** a change of GENERATOR away from `os.urandom`, or a measured
> condition capable of DUPLICATING THE OS ENTROPY STREAM (VM snapshot-resume / image cloning, where
> that premise is actually established). This is the SECOND clause of RD's riders that failed
> verification, and it is routed with the first at S9 RD item 2.
>
> Refusing it today is a **D46 application**: it is more machinery -- a second commit surface and a
> separate connection **on the money path** -- defending against a failure with **no mechanism and no
> observed instance**.

The delta below is what a re-opened fork executes; it changes nothing else.

- **Migration 0038 gains one table**, still additive, still no rebuild:
  `CREATE TABLE attempt_id_allocations (attempt_id INTEGER PRIMARY KEY AUTOINCREMENT, allocated_at
  TEXT NOT NULL)`. `AUTOINCREMENT` is load-bearing HERE in a way it is not on `trades`: the whole
  point is that a retired value is never reissued, and the row is never deleted, so
  `sqlite_sequence` only ever advances.
- **`trades.attempt_id` becomes `INTEGER`, and the representation is CHOSEN, not left open**
  (`A4-R4-3`: "TEXT or INTEGER" is not an implementable branch -- it changes the column type, the
  Python type, the validator, the CHECK, the probe's parameter and both drift tests).
  **The CHECK becomes `attempt_id IS NULL OR (typeof(attempt_id) = 'integer' AND attempt_id > 0)`,
  and the `typeof` guard is REQUIRED. MEASURED on this runtime:** with a bare
  `CHECK(a IS NULL OR a > 0)`, the value `'abc'` is **ACCEPTED** on a TEXT column AND on an INTEGER
  column (SQLite affinity comparison puts text above integers); with the `typeof` guard it is
  rejected, and so is `''`. `ATTEMPT_ID_LENGTH` is replaced by a positivity+type predicate in the
  Python mirror and the drift comparator reads the new CHECK text.
- **`_begin_attempt_identity` gains one COMMITTED write BEFORE the entry transaction:** open the
  allocation on a **SEPARATE connection** (never the caller's, so it cannot disturb the caller's
  transaction state), `INSERT INTO attempt_id_allocations (allocated_at) VALUES (?)`, commit, take
  `lastrowid`, close. **Every step of that lifecycle is contained and bounded, and each is named
  because "contained" without a boundary list is the same overstatement this plan has already made
  twice:** open, INSERT, commit and close are each inside the `Exception` containment, the close is
  additionally contained on its own (a raising close must not lose an allocation already committed),
  and **the allocator connection uses the same bounded `_PROBE_BUSY_TIMEOUT_MS` rather than the
  30-second project default** -- a contained failure that takes 30 s still delays an ordinary entry
  by 30 s, which is a cost the operator feels even though the entry succeeds. Any failure yields
  `token=None` and today's behaviour.
- **Nothing else moves.** The token still lands in the entry INSERT (co-durability unchanged), the
  probe still reads `trades` (the allocation row is never evidence that a trade landed), and the
  UNIQUE partial index stays as the live-row guard.
- **What it costs, stated so the ruling is informed:** a table that grows one row per post-gauntlet
  attempt -- **an attempt log by side effect**, which S2.6 explicitly declined as out of scope, so
  taking (S-d) also RE-OPENS that scope line; a second COMMIT on the money-bearing path; and a new
  pre-entry failure mode which is contained but is nonetheless new code between the operator and
  the ledger.
- **What it buys:** RD constraint 2 satisfied BY CONSTRUCTION, and the residual of S7.7 closed
  rather than declared.
- **Test consequences, named so the ladder is executable either way:** **(RD-b2) INVERTS** -- under
  (S-d) a second attempt cannot acquire a burned identifier, so the row asserts the allocator
  REFUSES reuse instead of asserting the probe confirms it; **(m1)/(m6) gain the allocation table
  and the typed CHECK**, including the MEASURED `'abc'`-is-accepted-without-`typeof` case as a
  rejection assertion; **(w) additionally asserts the allocation is COMMITTED before the entry
  transaction opens**; **(e2) gains four allocator-failure variants** (open raises, INSERT raises,
  commit raises, close raises), each asserting the entry still SUCCEEDS with `attempt_id IS NULL`;
  **(e3), new:** a pre-existing downstream refusal (the PE-anchor guard) leaves a COMMITTED
  allocation row and no trade -- the durable side effect of `A4-R4-8`, asserted rather than
  discovered; S7.7 becomes "no longer a limitation -- closed by ruling", kept for its history; and
  S2.6's "no attempt log" scope line is re-opened and re-decided.

### S2.1 WHERE THE ATTEMPT BEGINS -- decision: **mint the token and capture the path AFTER the entire pre-existing gauntlet, in one contained helper**

The token and the database path are acquired at the point `outcome = _CommitOutcome()` is
constructed today (`entry.py:830-831`) -- that is, **after** validation, the stop check, the
duplicate check, the hard cap, the soft warn, the recognition read and the caller-held-transaction
refusal, and **before** the guarded region.

*Why there and not at the top of the function -- with the claim NARROWED to what is true*
(`A4-R4-8`). **The mint is upstream of MOST pre-existing refusals, not all of them.** Upstream:
validation, the stop check, the duplicate check, the hard cap, the soft warn, the recognition read,
the caller-held-transaction refusal -- each of those issues **zero** new statements and raises
exactly as before. **DOWNSTREAM of the mint, and named rather than glossed:** the PE-anchor guard
(`entry.py:1243-1287`, relocated into `_record_entry_inner` by 22-A) and the latch resolver's own
refusals, which run inside the transaction. **22-A's LOCK clause (c)** -- *"every pre-existing
failure branch raises the same exception, with the same message, at the same point"* -- still holds
for ALL of them, because the mint changes no branch and no ordering; what the first draft
over-claimed was that they are all upstream. **Under (S-b) the difference costs one wasted uuid4.
Under (S-d) it is MATERIAL** -- a durable allocation row would be committed before a pre-existing
refusal, so the allocator becomes a log of refused requests and adds a write to branches this plan
says issue none; S2.0.1 accepts and tests that explicitly. **LOCK clause (d)** -- *"when the envelope carries no usable broker order
id, the RESOLVER issues zero additional database queries"* -- is untouched for the same reason and
for one more: its subject is the resolver, and the resolver is not on this path at all. (For
completeness, the two shipped clause-(d) tests each compare statement counts between two
`record_entry` calls, so a constant per-call statement would cancel in both; the argument above does
not lean on that, but the tests are not put at risk either.)

*Why the path comes from the CONNECTION and not from `cfg`:* `cfg.paths.db_path` is a configuration
value; `PRAGMA database_list` is **this connection's own answer about which database it is attached
to**. A caller can legally pass a connection to a different database than `cfg` names (every test
does), and `cfg` may be `None`. Using `cfg` here would be gotcha #30's shape one level up -- a
system-level value standing in for a per-object fact -- and would produce the worst possible error:
a probe that reads the WRONG database and answers "absent" (or, catastrophically, finds a
same-token row that is not ours -- impossible in practice but the reasoning is the point).

*Containment, and the exception CLASS is chosen deliberately:*

```
_AttemptIdentity = (token: str | None, db_path: Path | None)

def _begin_attempt_identity(conn) -> _AttemptIdentity:
    try:
        token = _mint_attempt_token()          # str(uuid.uuid4())
        # THE RESULT IS VALIDATED, NOT ONLY THE CALL (A4-R3-6).  A mint that
        # RETURNS "" / "short" / bytes raises nothing, so containment around
        # the CALL does not cover it -- and the repo's pre-write validator
        # would then reject it and FAIL AN ENTRY THAT WOULD HAVE SUCCEEDED,
        # which is the one thing this helper exists to prevent.  The empty
        # string is not hypothetical here: it is why the CHECK exists (S2.0).
        if not isinstance(token, str) or len(token) != ATTEMPT_ID_LENGTH:
            <contained WARNING>; return _AttemptIdentity(None, None)
    except Exception:                          # NOT BaseException -- see below
        <contained WARNING>; return _AttemptIdentity(None, None)
    try:
        db_path = _resolve_main_db_path(conn)  # PRAGMA database_list; None for :memory:
    except Exception:
        <contained WARNING>; db_path = None
    return _AttemptIdentity(token, db_path)
```

`Exception`, not `BaseException`, and the asymmetry is the point: this code runs **PRE-COMMIT**,
where nothing is durable and failing is the HONEST answer, so a `KeyboardInterrupt` or `SystemExit`
must propagate. That is the mirror image of 22-A3's S7.12 reasoning (its route guard catches
`BaseException` precisely because it runs POST-commit, where the contract's direction governs).

**THE PROPERTY THIS BUYS, STATED AT ITS REAL WIDTH** (`A4-R3-6` narrowed it, correctly): **no
ORDINARY (`Exception`-class) failure or malformed return of the identity apparatus can convert an
entry that would have succeeded into a failure.** When it fails, `token` and/or `db_path` are
`None`, clause 2 is unavailable, and the behaviour is exactly today's. **Two exceptions to that
sentence are deliberate and are named rather than papered over:** an interrupt during the mint
propagates BY DESIGN (above), and a token COLLISION at the UNIQUE index refuses the entry (S7.8) --
which is the index doing its job. The first draft's unqualified "can never" was contradicted by
both.

*The token is written even when `db_path` is `None`* (an in-memory database, where no fresh
connection to the same data is possible). It costs nothing and it leaves the row identifiable for
forensics; only the probe is unavailable.

*The mint is a named module-level function* (`_mint_attempt_token`) rather than an inline
`uuid.uuid4()` call, so tests can plant a deterministic token and can make the mint raise. That is a
testability decision, stated so it is not mistaken for indirection.

### S2.2 WHAT `_entry_transaction` RECORDS -- decision: **FOUR observations (THREE new fields), on both paths; the deferred path is OBSERVED and NOT re-plumbed**

> **This section was rewritten after round 1.** Its first version proposed adding a rollback to the
> deferred path, on a premise `A4-R1-2` disproved: `sqlite3.Connection.__exit__` ALREADY rolls back
> when its own commit fails (MEASURED (3b)). The corrected design is strictly smaller, and it no
> longer changes any pre-arc behaviour.

`_CommitOutcome` gains **THREE** fields beside `committed`, for **four observations in total** -- stated as a count because the first draft's manifest said "+2" while its table listed three (`A4-R3-9`), and an executor following the manifest would have dropped `cleanup_raised`, which is a mandatory gate input:

| field | meaning | set where |
|---|---|---|
| `body_completed: bool` | the entry body finished; whatever failed next was the COMMIT or later | immediately after `yield` returns, inside the transaction, on both paths |
| `committed: bool` | **the commit's own return was observed** (unchanged) | after `commit()` returns / after the `with conn:` block, **inside the protected suite on both paths** |
| `resolution: str` | the PHYSICAL state, RE-READ from `conn.in_transaction` after any rollback attempt: `"unattempted"` / `"not_needed"` / `"rolled_back"` / `"still_open"` | in the failure handler of both paths |
| `cleanup_raised: bool` | the rollback CALL raised -- a fact about the CALL, not about the transaction | same handler |

Every one of them is an OBSERVATION of this function's own calls or of the connection's own state,
never an inference -- the property that made `committed` admissible where the reverted clause-2 read
was not. `resolution` is what lets `record_entry` honour RD's rule (i) mechanically instead of by
comment.

**The immediate path** keeps its shape exactly; three assignments are added and the two existing
cleanup messages are untouched (they are pinned by shipped tests):

```
try:
    conn.execute("BEGIN IMMEDIATE")
    yield
    outcome.body_completed = True
    conn.commit()
    outcome.committed = True
except BaseException as write_error:
    if conn.in_transaction:
        try:
            conn.rollback()
        except BaseException as cleanup_error:
            outcome.cleanup_raised = True
            # THE STATE IS RE-READ, NEVER INFERRED FROM THE RAISE -- the same
            # re-derivation the two shipped messages below already do.
            outcome.resolution = (
                "still_open" if conn.in_transaction else "rolled_back")
            <the two existing branch messages, unchanged>
            raise cleanup_error from write_error
        # **RE-READ AFTER THE RETURNING ARM TOO** (`A4-R7-8`).  This line used to
        # assign "rolled_back" UNCONDITIONALLY when `rollback()` returned, so the
        # field contract's own words -- *re-read from `conn.in_transaction` after
        # ANY rollback attempt* -- were honoured on the raising arm and INFERRED
        # on the returning one.  A rollback that returns without taking effect
        # would then be classified `rolled_back` and ADMIT the probe.
        outcome.resolution = (
            "rolled_back" if not conn.in_transaction else "still_open")
    else:
        outcome.resolution = "not_needed"
    raise
```

**`resolution` AND `cleanup_raised` ARE TWO FACTS, AND THE FIRST DRAFT CONFLATED THEM**
(`A4-R2-7`). It set `resolution = "unresolved"` whenever `rollback()` raised. **That is false against
a fixture ALREADY IN THIS TREE:** `_RollbackAfterEffect`
(`tests/trades/test_22a_task9_entry_wiring.py:3039`) performs the REAL rollback and THEN raises, so
the transaction is RESOLVED, the row is GONE, and the draft would have labelled it unresolved. The
production handler four lines below already re-derives its message from `conn.in_transaction` for
exactly this reason (*"a cleanup warning that is WRONG about the state teaches an operator to
distrust the right ones"*), and the observation field must be built the same way. **So: `resolution`
describes the TRANSACTION, `cleanup_raised` describes the CALL, and the admissibility gate reads
BOTH** (S2.4).

**The deferred path** gains the SAME observations and **nothing else** -- no rollback, no message,
no change to which exception escapes:

```
try:
    with conn:
        yield
        outcome.body_completed = True
    outcome.committed = True          # INSIDE the try -- see below
except BaseException:
    if outcome.body_completed and not outcome.committed:
        _observe_resolution(conn, outcome)   # shared with the immediate path
    raise
```

**`outcome.committed = True` IS INSIDE THE `try`, AND THAT IS NOT A STYLE CHOICE** (`A4-R1-3`). The
first draft put it after the `except`, which left a reachable window: an asynchronous exception
delivered after `with conn:` returned -- so after the commit was DURABLE -- but before the
assignment escaped this frame with `body_completed=True, committed=False,
resolution="unattempted"`, the settle gate rejected `"unattempted"`, and a durable entry was reported
as a failure. The plan's own S7.12 claimed that window was closed while the pseudocode left it open.
Inside the `try`, the same exception is caught here, `resolution` is observed as `"not_needed"`
(`in_transaction` is False after a commit that returned), and `record_entry` settles it. The
immediate path already had this shape; now both do, and **test (k3) asserts it STATICALLY** rather
than trusting a reading -- the window contains no statement, so no injected exception can reach it,
but an AST walk can prove the assignment is lexically inside the protected suite.

**`_observe_resolution` is shared, and its rollback arm is the RESIDUAL one on this path.** On the
deferred path `in_transaction` is normally False by the time the handler runs, because `__exit__`
already rolled back -- so the shared helper writes `resolution = "not_needed"` and issues no
statement at all. The rollback arm fires only where `__exit__`'s own rollback ALSO failed and left
the transaction open. **On the deferred path a failure there is CONTAINED and LOGGED, it sets
`cleanup_raised`, and the ORIGINAL exception still escapes**, so the pre-arc path's exception
identity is preserved byte-for-byte. That asymmetry with the immediate path (which raises
`cleanup_error from write_error`) is DELIBERATE and has a reason: on the deferred path the rollback
is `__exit__`'s job and its failure is already reflected in what escaped, so a second, louder report
from us would replace an exception the caller's tests already pin, for no new information.

*Why the resolution matters at all, given that the probe uses a FRESH connection:* the fresh
connection supplies VISIBILITY on its own (MEASURED (1)); the resolution supplies something else,
and naming it precisely is what stops this being cargo cult. **A resolved transaction is what makes
an ABSENT answer DURABLE.** With the writer's transaction still open, "absent" is a statement about
a moment: a caller that reuses the connection and commits later turns the row durable AFTER we
reported failure. Once the transaction is resolved, "absent" is a statement about the ledger. And
MEASURED (3) adds a blunter reason: while the writer holds a PENDING lock the fresh reader is
BLOCKED outright, so without resolution there is frequently no read to have.

### S2.3 THE PROBE -- decision: **a repo read for the SQL, a service function for the connection lifecycle, and a bounded busy timeout**

```
# swing/data/repos/trades.py
def find_trade_id_by_attempt_id(conn, attempt_id) -> tuple[int, str] | None:
    """(id, ticker) of the trade carrying this attempt token, or None.
    Schema-aware: on a pre-v38 schema the column does not exist, the token
    cannot have been stored, and ABSENT is the truthful answer."""
```

```
# swing/trades/entry.py
_PROBE_BUSY_TIMEOUT_MS = 2000

def _durability_probe(db_path, attempt_id) -> tuple[int, str] | None:
    probe = open_connection(db_path, busy_timeout_ms=_PROBE_BUSY_TIMEOUT_MS)
    try:
        return find_trade_id_by_attempt_id(probe, attempt_id)
    finally:
        <contained close>
```

- **The connection is FRESH by construction** -- `open_connection` on the path, never the writer's
  handle. This is the half of R10-02 that is closed by construction rather than by discipline, and
  Task 5 pins it with a test that captures the connection object the repo read receives and asserts
  it **is not** the writer's connection.
- **`open_connection`, not `connect`:** `connect` adds a schema-version check, i.e. another
  statement and another failure mode, on a path whose entire job is to be reliable when things are
  already going wrong. The schema version cannot have changed underneath us.
- **The busy timeout is BOUNDED and named.** The project default is 30 s; a lost-commit probe that
  hangs a money-bearing web submit for 30 s is a poor trade when the fallback -- re-raise, the
  alarm -- is the safe direction anyway. 2 s is long enough to outlast a passing lock and short
  enough that the operator sees an answer.
- **`PRAGMA read_uncommitted` is NOT checked at runtime, and that is a decision.** Shared-cache mode
  is the only way a second connection could observe uncommitted data, the probe opens its own
  plain-path connection, and the pragma defaults to 0. A runtime branch here would be defensive dead
  code whose own test can only assert the default; the precondition is pinned by a TEST that asserts
  the probe connection reads `read_uncommitted = 0`, which is the right instrument for a
  construction-time property.
- **The probe corroborates the TICKER.** The token alone is sufficient for identity, so this is a
  second, independent signal rather than the first: if a row carries our token but a different
  ticker, something is wrong in a way no design anticipated, and the honest response is the ALARM
  (return `None`, re-raise, log at ERROR). The rule this follows is the one the arc already owns --
  a mismatch may raise the alarm; only a match may be asserted from. Price is deliberately NOT
  corroborated: a float comparison across the Python/SQLite boundary is the rounding-authority
  gotcha's own territory and buys nothing the token has not already established.

### S2.4 CLAUSE 2'S RETURN -- decision: **one new branch in the EXISTING post-commit handler, gated on three observations**

`record_entry`'s handler keeps its shape. The gate `if result is None or not outcome.committed:
raise` splits:

```
except BaseException as post_commit_error:
    if result is None:
        raise                       # the body never finished; nothing to report
    if not outcome.committed:
        # THE ESCAPING EXCEPTION IS PASSED IN (A4-R3-5): the helper must attach
        # its own failures to THAT object via `log_contained_note`, and it
        # cannot reach it otherwise.  RETURN CONTRACT (A4-R3-4): the probe's
        # `tuple[int, str] | None` is passed through unchanged -- there is no
        # settlement dataclass, and the tuple is UNPACKED here.
        settled = _settle_by_attempt_identity(
            attempt, outcome, req, post_commit_error)
        if settled is None:
            raise                   # THE ALARM -- unchanged, today's behaviour
        settled_trade_id, _settled_ticker = settled
        result = dataclasses.replace(result, trade_id=settled_trade_id)
        first_warning = <the LOST-COMMIT text>
    else:
        first_warning = <the existing POST-COMMIT-STEP text, unchanged>
    ... existing degraded-result construction and contained ERROR log ...
    return degraded
```

`_settle_by_attempt_identity` returns `None` -- i.e. the alarm -- unless **all** of the following
are observed:

1. `outcome.body_completed` is True (the failure is at or after the commit, not before it);
2. `outcome.resolution in {"not_needed", "rolled_back"}` **AND `outcome.cleanup_raised` is False** --
   **RD's rule (i), taken LITERALLY and closed by assertion rather than by comment**: the brief says
   *"if the rollback itself raises, the connection is DISCARDED and NO read is attempted on it"*, so
   a raising rollback refuses the read **even when the state re-read shows the rollback took
   effect** (`A4-R2-7`'s after-effect case). Both fields are checked because they are two different
   facts;
3. the attempt has BOTH a token and a database path;
4. the probe returns a row, and its ticker matches the request's.

**`"unattempted"` is a BELT, not an expected value.** After the `A4-R1-3` fix (S2.2), whenever
`body_completed and not committed` the failure handler always writes a resolution on both paths, so
`"unattempted"` should be unreachable there. Condition 2 rejects it anyway, because the alternative
is a gate whose safety depends on an exhaustiveness argument about assignment placement -- and this
arc's subject is not trusting arguments where an observation is available. **Test (k3) is what turns
that belt into a proof** rather than leaving it as the same kind of argument.

**Honouring rule (i) forecloses nothing -- and the FIRST DRAFT'S VERSION OF THIS ARGUMENT WAS
WRONG, so here it is rebuilt on the corrected state model** (`A4-R2-7`). The draft said
`"unresolved"` is reachable only from `in_transaction == True`; `_RollbackAfterEffect` is a
counterexample already in the tree. The correct argument enumerates the TWO refusal branches and
shows the row is provably absent in each:

- **`resolution == "still_open"`** (the rollback did not take effect). The handler only attempts a
  rollback when `in_transaction` was True on entry, and MEASURED (4) says `in_transaction` is False
  after a commit that RETURNED -- so on this branch the commit did not land, the row is PENDING, and
  a fresh connection would read ABSENT.
- **`cleanup_raised` with `resolution == "rolled_back"`** (the after-effect case). The rollback took
  effect, so the row is GONE, and a fresh connection would read ABSENT.

**In both branches the refused read would have answered ABSENT, and ABSENT is what the refusal
produces.** Rule (i) therefore costs nothing, and it is independently right for RD's reason: a
connection whose rollback raised is of unknown health, and an answer that can change under you is
not evidence.

**`outcome.committed` is NOT set by a successful settle.** It means *the commit's own return was
observed*, and it did not happen. The settle produces a different, weaker-but-admissible fact --
*the ledger contains this attempt's row* -- and conflating the two would destroy the distinction
this arc exists to draw.

**The returned `trade_id` comes from the PROBE, not from `lastrowid`.** `result.trade_id` is what
the INSERT's cursor reported inside a transaction whose commit we could not observe; the probe's id
is what the durable table says. They cannot legitimately differ, and using the probe's is the
admissible choice rather than the equivalent one. (A difference would mean the token landed on a row
we did not insert, which condition 4's ticker corroboration already turns into the alarm.)

**Signature and return, stated exactly because the first draft was inconsistent about both**
(`A4-R3-4`, `A4-R3-5`):
`_settle_by_attempt_identity(attempt, outcome, req, post_commit_error) -> tuple[int, str] | None`.
It returns the PROBE's own tuple, unchanged -- no wrapper dataclass exists and none is needed -- and
it takes the escaping exception as its fourth argument, because S2.4 requires its own failures to be
attached to that exact object and test (g) asserts that object's identity survives. A helper that
could not name the exception could not honour either.

**Containment: `_settle_by_attempt_identity` contains `BaseException`.** Here -- unlike S2.1's
pre-commit mint -- the module's own R11-03 property governs: **nothing that happens while diagnosing
a failure may change which exception escapes**. A probe failure is REPORTED through
`log_contained_note(log, post_commit_error, ...)` -- which emits the ERROR record and, **only if the
sink itself raises**, attaches a note (`A4-R4-5`: the first draft said the probe failure becomes a
note, which is not what that helper does) -- and the ORIGINAL propagates with its type, args and
chaining intact. The cost is that an interrupt delivered during the probe is swallowed in favour of
the commit's own exception; both are failures, so no false success can be manufactured, and the
identity of what escapes is the property the codebase pins.

### S2.5 THE INTEGRITY-ERROR MAPPING -- decision: **narrow the match to `trades.ticker` in the same task that adds the index**

`_record_entry_inner`'s `except sqlite3.IntegrityError` maps `"UNIQUE" in str(exc) and "trades" in
str(exc)` to `DuplicateOpenPositionError`. S1.4 measured that a `ux_trades_attempt_id` violation
satisfies both substrings. The match becomes `"UNIQUE constraint failed: trades.ticker" in
str(exc)` -- the exact message SQLite emits for the belt index (MEASURED) -- and anything else
re-raises as the `IntegrityError` it is. **This lands in the SAME commit as the index**, because a
schema change and the Python mirror that keeps it honest are one atomic deliverable (#11), and
because between the two commits the tree would carry a live false-message path on the entry surface.

### S2.6 WHAT THIS PLAN DELIBERATELY DOES NOT DO

- **No `swing/web/` and no `swing/cli.py` change.** 22-A3 shipped the readers; this arc's warning
  rides them.
- **No `Trade` dataclass field, no `_row_to_trade` widening, no fifth SELECT era** (S2.0, routed).
- **No backfill of `attempt_id` for existing rows.** They are legacy, they carry NULL, and a
  synthesised token for a row nobody attempted would be a fabricated fact of exactly the kind this
  arc exists to refuse.
- **No trigger requiring `attempt_id` on `trades` INSERTs.** 396 test-file call sites and every
  legacy row write NULL legitimately; a NOT NULL barrier is not available, and a partial one would
  be a barrier that does not barrier.
- **No change to what happens when the entry body itself fails.** That path was never in doubt.
- **No second consumer of the token.** It is written, indexed and read by one probe. A reconciliation
  or audit surface over `attempt_id` is a different arc with a different justification.

---

## S3. TEST DESIGN -- every assertion computed under BOTH paths

> **The rule this section is written against:** a DISCRIMINATING test that passes under both the
> pre-fix and the post-fix path is worthless, so each discriminating entry states **what the
> assertion evaluates to before the change and after it**. Where "before" is not a state this tree
> has ever been in, the pre-fix path is the NAIVE implementation the test exists to exclude, and it
> is named.
>
> **A SECOND, SEPARATE ROSTER EXISTS AND IS LABELLED AS SUCH** (`A4-R1-8`): (i) and (j) are
> REGRESSION CONTROLS. They pass identically on both trees BY DESIGN -- their job is to fail if this
> arc breaks something it must not touch -- and they are NOT evidence that clause 2 was implemented.
> The first draft of this section swept them under a universal claim; separating the rosters is the
> fix, because a control counted as evidence inflates the evidence.
>
> **CHARC's standing trap is honoured throughout:** a test asserting only *"it raised"* or *"it did
> not crash"* passes an implementation that swallows everything. Every row below asserts the RESULT
> SHAPE, the ROW COUNT, or the IDENTITY of what escaped.

### The full roster

| id | subject | kills |
|---|---|---|
| (m1)-(m6) | migration 0038: column, CHECK, index, gate, no-op re-run, data preserved, CHECK/Python drift | a schema that does not enforce what the design assumes |
| **(m7)** | the IMMUTABILITY trigger: a direct `UPDATE trades SET attempt_id` ABORTs (schema half) | **`A4-R4-1` -- a token re-assignable after insertion is not identity** |
| **(m8a-c)** | the corrector's TYPED refusal, its ORDER-INDEPENDENCE, and its DELIVERY through unchanged CLI/web callers | **`A4-R6-6`/`A4-R6-7`/`A4-R7-3` -- authorize-then-abort, key-order dependence, and a refusal the operator never sees** |
| (r1)-(r6) | repo: write, pre-v38 drop, malformed reject, model/schema drift comparator, static INSERT closure walk, IntegrityError mapping | the mirror family (#11) and the defect the index introduces |
| **(RD-a1)** | the probe is NOT CALLED when the rollback RAISED -- in BOTH its shapes | **R10-02 by assertion, not comment** |
| **(RD-a2)** | the probe NEVER receives the writer's connection | **R10-02's structural half** |
| **(RD-a3)** | rollback raises before taking effect, row PENDING -> NOT SUCCESS | **R10-02's reproduction** |
| **(RD-b)** | a concurrent insert takes our freed rowid -> NOT confirmed as ours | **R10-03** |
| **(RD-b2)** | a rolled-back token REUSED by a later committed row IS confirmed -- the declared residual, VERIFIED not asserted | a declaration nobody executed (`A4-R1-1`) |
| (c) | commit raises, row LANDED -> SUCCESS with warning, both paths | the arc's headline |
| (c2) | a REAL (unproxied) commit failure -> resolved, probe absent, re-raise | proxy-only test theatre |
| (d) | commit raises, row ABSENT -> re-raises the ORIGINAL | a settle that invents rows |
| **(w)** | ONE token flows mint -> INSERT argument -> probe argument, with a mint that returns DIFFERENT values each call | **a disconnected or double-minted identity that every constant-token test blesses** |
| (e) | co-durability OBSERVED AT THE TRANSACTION BOUNDARY: the writer sees the token while a fresh connection sees no row | **a post-commit stamp that the committed/rolled-back pair cannot tell from the real thing** |
| (e2) | the identity apparatus cannot FAIL an entry | a nicety that breaks the money path |
| (f) | no database path (in-memory) -> today's behaviour, no crash | an unguarded probe |
| (g) | a raising probe leaves the ORIGINAL exception untouched | the R11-03 class inside the new code |
| (h) | the probe connection reads `read_uncommitted = 0` | visibility assumed rather than pinned |
| (k) | the deferred path OBSERVES its own already-resolved lost commit | a wrapper that assumes instead of reading |
| (k2) | the deferred path's exception identity is UNCHANGED | an arc that quietly re-plumbs the pre-arc path |
| **(k3)** | STATIC: the `committed` assignment is inside the protected suite on BOTH paths | **`A4-R1-3`'s window, which no injected exception can reach** |

**REGRESSION CONTROLS -- a separate roster, identical under both paths by design:**

| id | subject | what it protects |
|---|---|---|
| (i) | the belt still refuses a same-ticker retry | the belt is not mistaken for the fix, and is not weakened by it |
| (j) | the post-commit-STEP path is byte-unchanged | 22-A3's shipped clause-1 behaviour, through a handler this arc edits |

---

### (m1) The column, the CHECK, and the version

**Post-fix:** `EXPECTED_SCHEMA_VERSION == 38`; after `run_migrations(target_version=38)`,
`PRAGMA table_info(trades)` contains `attempt_id`; `INSERT ... attempt_id = NULL` succeeds;
`attempt_id = <36 chars>` succeeds; `attempt_id = ''`, `attempt_id = <35 chars>` **and a 36-BYTE
BLOB (`b"..."` of length 36)** each raise `sqlite3.IntegrityError` naming the CHECK. **The BLOB case
is the one that fails a length-only predicate** (`A4-R7-1`; MEASURED: length-only ACCEPTS it and the
UNIQUE index then holds it beside its byte-identical text twin, so this row is what makes the
`typeof` half testable rather than merely written down). **Pre-fix:** the constant is 37 and the column does not
exist, so the first two assertions raise `OperationalError: no such column`. **Pre-fix, per assertion** (`A4-R3-10`, and the sentence this replaces still said "the first
assertions fail with `no such column`" two lines before contradicting itself -- `A4-R6-13`): `EXPECTED_SCHEMA_VERSION == 38` fails with `AssertionError`
(it is 37); the `PRAGMA table_info` membership check fails with `AssertionError`; only the SQL that
NAMES `attempt_id` raises `OperationalError: no such column`. **Task 1's declared first red is the
`AssertionError` on the constant**, which is the first assertion in file order. **MEASURED already**
for the CHECK's two rejections and its acceptance (S2.0), so the test encodes a verified behaviour
rather than an expected one.

### (m2) The UNIQUE partial index

**Post-fix:** two rows with the same non-NULL token -> `IntegrityError: UNIQUE constraint failed:
trades.attempt_id`; **N rows with NULL tokens all commit** (MEASURED). **Pre-fix:** no index, both
insert cleanly -- so a test that only asserted "NULLs are allowed" would pass on both trees and is
not sufficient on its own; the duplicate-rejection half is what distinguishes.

### (m3) The backup gate

**Post-fix:** `_phase22_arc_a4_backup_gate` writes a `swing-pre-22a4-migration-<ISO>.db` and
verifies it when `current_version == 37 and target_version >= 38`; it does **nothing** at
`current_version == 36` (STRICT equality, the `pre_version == (target - 1)` gotcha) and raises
`MigrationBackupRequiredException` for an in-memory source. **Pre-fix:** the function does not
exist. The 36-and-target-38 case is the one that distinguishes a `<=` gate from an `==` gate and is
asserted explicitly.

### (m4) Re-running the migration is a no-op

Run `run_migrations(target_version=38)` **twice**; the second call changes nothing (version stays
38, one `attempt_id` column, one index). **Pre-fix, and it is COMPUTABLE rather than "n/a"
(`A4-R1-9`):** the runner caps at `min(target_version, EXPECTED_SCHEMA_VERSION)`, which is 37 today,
so the version assertion reads **37** and the test fails on the first call. This is the standing
run-db-migrate-twice discipline.

### (m5) Existing rows survive and backfill to NULL

Seed three v37 trades, migrate to 38, assert all three rows are present with identical values and
their ids unchanged, and `attempt_id IS NULL`. **Pre-fix, COMPUTABLE (`A4-R1-9`):** the
`attempt_id` query raises `OperationalError: no such column: attempt_id`. **Post-fix if the
migration were a REBUILD rather than an `ADD COLUMN`:** this is the test that would notice a silent
id renumbering.

### (m6) DRIFT COMPARATOR #1 -- the CHECK text versus the Python constant

Read `SELECT sql FROM sqlite_master WHERE name = 'trades'` on a v38 database and assert it contains
**BOTH** `typeof(attempt_id) = 'text'` **AND** `length(attempt_id) = {ATTEMPT_ID_LENGTH}` built from
the Python constant. **Asserting only the length fragment would PASS THE DEFECTIVE DDL**
(`A4-R7-1`) -- the comparator would certify a CHECK that admits a BLOB, which is the one thing a
drift comparator must never do. **Post-fix:** passes. **Pre-fix / on drift:** changing either
representation alone fails, and dropping the `typeof` clause from the migration fails HERE. **MEASURED:** SQLite preserves
the `ALTER TABLE ... ADD COLUMN ... CHECK (...)` clause verbatim in the stored schema text, so this
comparator reads the real constraint and not a copy of it.

### (m7) THE TOKEN IS WRITE-ONCE -- asserted at the schema AND through the real corrector path

**Post-fix, half 1 -- the SCHEMA guard:** a direct `UPDATE trades SET attempt_id = <a VALID 36-char
token> WHERE id = ?` on a v38 database raises `sqlite3.IntegrityError` naming the trigger.
**THE VALUE IS CHECK-VALID SO THE TRIGGER IS ISOLATED FROM EVERY OTHER CONSTRAINT** -- and the
REASON first given for that was FALSE, which is worth recording because it was believed for two
rounds. `A4-R5-6` said `'x'` "trips the CHECK before reaching the trigger"; **MEASURED, it does not:
a BEFORE UPDATE trigger fires FIRST, so both an invalid and a valid value abort with the trigger's
own `immutable` message.** A valid token is still the right choice -- it removes any doubt about
WHICH constraint refused -- but the discriminator is not the CHECK ordering; it is the
**MUTATION PROOF** (remove the `CREATE TRIGGER`, show this RED), which is why the proof gates Task 1
rather than decorating it.

**Post-fix, half 2 -- the CORRECTOR path, and it asserts the TYPED error:** driven through
`swing/trades/reconciliation_auto_correct.py`'s tier-2 operator-truth path with
`field_name="attempt_id"`, the correction is refused with the **typed refusal from Task 1b -- NOT a
raw `sqlite3.IntegrityError`** -- and the row's token is unchanged. Asserting the TYPE is the whole
point of CHARC's condition: an `IntegrityError` surfacing from a trigger IS the authorize-then-abort
shape, so a test satisfied by it would ratify the defect.

**Pre-fix (the column with no trigger and no refusal -- what the first three drafts specified):**
both halves succeed, and the second is the reachable one: an operator correction re-assigns a
rolled-back token to a different trade in the same ticker, and the settle then confirms a row this
attempt did not write. **Half 2 is the load-bearing one** -- the direct UPDATE proves the trigger
exists; only the corrector path proves it covers the writer that actually reaches it, and only the
TYPE assertion proves the operator is told why.

### (m8) THE CORRECTOR REFUSES `attempt_id` -- typed, order-independent, and DELIVERED

**Three named rows, because Task 1b adds three load-bearing test classes and the first version of it
gave them no ids, no pre-/post-fix values, no exact result shapes and no files** (`A4-R7-3`). They
are separated from (m7) because **their red base is different**: at Task 1b, Task 1's trigger already
exists, so the pre-fix behaviour is a raw `sqlite3.IntegrityError` -- **not** (m7)'s older
"both writes succeed" world.

**(m8a) SERVICE -- the typed refusal.** Drive the tier-2 operator-truth path with
`field_name="attempt_id"`. **Pre-fix (Task 1 landed, Task 1b not yet):** `sqlite3.IntegrityError`
from the trigger. **Post-fix:** exactly `ImmutableJournalFieldError`, the row's token unchanged, and
the message naming the column as WRITE-ONCE IDENTITY that no surface writes.

**(m8b) ORDER-INDEPENDENCE -- the preflight half.** A MULTI-FIELD correction with an ordinary field
FIRST and `attempt_id` LAST. **Post-fix:** the refusal is raised by
`_preflight_reserved_transitions` before any write, **ZERO journal `UPDATE` statements are issued**
(counted on an instrumented connection), and no correction or audit row is written. **Against a
backstop-only implementation** (the check only in `_update_journal_field`): the ordinary field's
UPDATE has already executed when the refusal fires, and the statement count is non-zero -- which is
the key-order dependence the module's own comment says it was restructured to eliminate.

**(m8c) DELIVERY through the UNCHANGED callers -- the half that makes this CHARC's condition rather
than a type change.** Both mappings were read at the source:
- **CLI** (`swing/cli.py:3941`): `ValueError` -> `click.UsageError` -> **exit code 2**, the refusal
  message on stderr, **no traceback**.
- **WEB** (`swing/web/routes/reconcile.py:1670`): `ValueError` -> **status 400** with the message in
  the error band and the operator's submission preserved.
**Pre-fix:** `ImmutableJournalFieldError` deriving from bare `Exception` (the shape `A4-R6-6`
caught) reaches NEITHER handler -- an uncaught CLI traceback and a web 500. **The assertions are the
exact exit code and the exact status**, not merely "not success": a weak delivery row would pass on
any non-success result and would certify nothing about legibility.

**Files:** `tests/trades/test_22a4_corrector_refusal.py` (m8a, m8b) and
`tests/web/test_routes/test_22a4_corrector_refusal_delivery.py` + the CLI half in
`tests/cli/test_22a4_corrector_refusal_cli.py` (m8c). **Task 1b's declared first red is (m8a)'s
`sqlite3.IntegrityError`.**

### (r1) The repo writes the token
### (r1) The repo writes the token

`insert_trade_with_event(conn, trade, event_ts=..., attempt_id=TOK)` on a v38 database ->
`SELECT attempt_id FROM trades WHERE id = ?` returns `TOK`. **Pre-fix:** `TypeError: unexpected
keyword argument`.

### (r2) A pre-v38 schema DROPS the token and still inserts

On a v37 database, the same call inserts the row, returns an id, and logs a contained WARNING.
**AND A SECOND VARIANT WITH A RAISING LOG HANDLER, because the first does not test containment at
all** (`A4-R7-9`): `swing/data/repos/trades.py` has **no logger and no containment helper today**, so
a plain `log.warning(...)` would satisfy the first variant and **abort the transaction** when the
sink raises -- failing a money-bearing entry for an identity nicety, which is precisely what S7.5's
reason forbids. **Task 1 therefore specifies the containment explicitly** (the same
contain-and-continue shape as `entry.py`'s `log_contained`, or a local equivalent; the repo may not
import the entry service). **Post-fix, both variants:** row count 1, `attempt_id IS NULL`. **The alternative implementation this excludes** is one that raises: that
would make the identity apparatus able to FAIL an entry, which S2.1's whole containment posture
forbids, and the consequence of dropping is exactly today's behaviour (the probe is schema-aware and
answers ABSENT, so the caller re-raises as it does today).

### (r3) A malformed token is refused BEFORE any write

`attempt_id=""`, `attempt_id="short"`, a 37-character string, **and a 36-BYTE `bytes` value**
-> `ValueError` from the repo, and `SELECT COUNT(*) FROM trades` is **0** (the row-count half is what
distinguishes a pre-write guard from a post-write one). **The `bytes` case pins the `isinstance`
half of the validator** (`A4-R7-1`): a 36-byte `bytes` passes a bare `len(...) == 36` in Python
exactly as a BLOB passes `length()` in SQLite, so a length-only validator would let it through to
the CHECK -- or, on a tree whose CHECK is also length-only, all the way into the index.
**Pre-fix, concretely rather than "n/a":** `insert_trade_with_event` has no `attempt_id` keyword, so
the call raises `TypeError`.

### (r4) DRIFT COMPARATOR #2 -- the schema versus the model

`{c for c in PRAGMA table_info(trades)} - {f.name for f in dataclasses.fields(Trade)} ==
{"risk_policy_id_at_lock", "attempt_id"}`, with the reason for each member in the test's docstring.
**EQUALITY, NEVER A SUPERSET CHECK -- CHARC made this the MANDATORY member of the mirror set**
(2026-09-06): *"the one mirror that defends the set."* A `>=` or subset form would silently absorb the
next column added without a decision, which is precisely the failure the comparator exists to catch,
and it is the same softening the LOCK-A docstring refuses one section over.
**Post-fix:** passes. **Pre-fix:** the set is `{"risk_policy_id_at_lock"}` (MEASURED today), so the
test fails on the current tree and passes only once the column exists -- and it fails again the day
a third column is added without a decision. This is the mandatory comparator of the mirror set: the
one mirror that does not depend on choosing the right grep.

### (r5) STATIC CLOSURE CHECK -- every entry INSERT carries the column

Walk every `INSERT INTO trades` statement in `swing/` (string constants via `ast`, plus a raw-text
scan for the dynamic-SQL family, so the walk cannot be defeated by an f-string). **THE TABLE NAME IS
MATCHED AS A TOKEN WITH A WORD BOUNDARY, AND `__pycache__` IS EXCLUDED** (`A4-R7-6`): a raw substring
also matches `INSERT INTO trades_new` -- the Phase-7 rebuild, a different table -- which the walk
would otherwise report as an unreasoned fifth writer and fail on. Historical migration rebuild
statements are classified explicitly rather than left to the substring. Then assert each
EITHER names `attempt_id` OR is on a **THREE-member REASONED EXCLUSION list**, each cited by the
schema era it serves.

**The counts, corrected (`A4-R1-4` -- the first draft said "two excluded" and "three statements ...
makes four" in the same paragraph, which is both wrong and self-contradictory).** Read off
`swing/data/repos/trades.py`: the existing branches are **v27+ (`:246`), v21-v26 (`:305`) and
pre-v21 (`:369`)** -- THREE. Adding the v38 branch makes **FOUR statements: ONE carrying the column
and THREE reasoned era exclusions.**

**Post-fix:** four statements, the assertion passes. **Pre-fix:** three statements, none carrying
the column, so the assertion fails on the carrying-branch requirement.

**THE MUTATION PROOF IS PART OF THE TASK, IS RUN, AND IS SHOWN RED IN BOTH DIRECTIONS:**
(1) remove `attempt_id` from the v38 INSERT column list -> the test must fail;
(2) add a fifth `INSERT INTO trades` statement that neither carries the column nor is on the
exclusion list -> the test must fail. Direction (2) is the one that matters for the future, because
it is how a new writer would actually arrive. Per the recipe, the fix is not the list -- it is the
closure check that walks what the code actually contains and asserts every item is on the list or
on the reasoned exclusion list, and it is a STATIC walk rather than a runtime trace because a trace
only sees the branches a fixture happened to take.

### (r6) The IntegrityError mapping no longer mis-labels

Two rows with the same non-NULL token through `record_entry`'s own inner path ->
**`sqlite3.IntegrityError` propagates**, NOT `DuplicateOpenPositionError`; and a genuine same-ticker
open duplicate still raises `DuplicateOpenPositionError` naming the ticker. **Pre-fix (the loose
match plus the new index):** the first case raises `DuplicateOpenPositionError("Already an open
position in AAA (race-detected)")` over a ticker with no open position. **MEASURED:** both SQLite
messages, so the assertion is written against the real strings.

---

### (RD-a1) THE PROBE IS NOT CALLED WHEN THE ROLLBACK RAISED

**TWO fixtures, because a raising rollback has TWO shapes and only one of them was covered**
(`A4-R2-7`):
**(a)** a proxy whose `commit()` raises and whose `rollback()` raises WITHOUT taking effect -- the
transaction stays open, the row stays pending;
**(b)** a NEW combined proxy -- `commit()` raises WITHOUT landing, and `rollback()` performs the
REAL rollback and THEN raises -- so the transaction is RESOLVED and the row is gone while
`cleanup_raised` is True. **The existing `_RollbackAfterEffect`
(`tests/trades/test_22a_task9_entry_wiring.py:3039`) CANNOT be reused for this** (`A4-R3-3`,
verified at the source): its `commit()` commits normally and returns, so `record_entry` succeeds and
its raising `rollback()` is never reached. Making the BODY fail instead is not equivalent either --
`result` stays `None` and the settle gate refuses at condition 0, before `cleanup_raised` can
discriminate anything. The new proxy borrows `_RollbackAfterEffect`'s rollback half and
`_CommitNeverLands`'s commit half.
**(c)** a THIRD fixture whose `rollback()` RETURNS NORMALLY while leaving `in_transaction` TRUE --
the arm no earlier fixture covered (`A4-R7-8`). **Post-fix:** `resolution` reads `"still_open"` (the
state RE-READ, not inferred from the call returning) and the probe count is **0**. **Against the
pseudocode this replaces**, which assigned `"rolled_back"` whenever the call returned: the resolution
is misclassified and **the probe is ADMITTED** -- a read let in under a falsely clean label.
`_durability_probe` is monkeypatched to a sentinel that RECORDS calls.

**Post-fix:** `record_entry` raises; **the sentinel's call count is 0**; `outcome.cleanup_raised`
is True and `outcome.resolution` reads `"still_open"` (the state RE-READ, not inferred).
In shape **(b)** the same assertions hold with `resolution == "rolled_back"` and `cleanup_raised`
True -- **the read is refused because the CALL raised, not because the transaction is open.** That is
rule (i) taken literally, and shape (b) is the row that proves the gate reads both fields rather than
inferring one from the other.
**Pre-fix (the naive implementation this excludes -- one that probes whenever the commit is lost):**
the count is 1 in both shapes. **Against the first draft's single-field gate:** shape (b) would be
labelled `"unresolved"` on a resolved transaction, so the state model would be wrong even where the
outcome happened to be right. RD's rule (i) is closed by an assertion instead of by the comment that
R10-02's own site carried while the next line walked past it.

*Teardown:* the writer's transaction is rolled back in a `finally` so the temporary database is not
left locked for the rest of the module.

### (RD-a2) THE PROBE NEVER RECEIVES THE WRITER'S CONNECTION

**`swing.trades.entry.find_trade_id_by_attempt_id` is monkeypatched** -- the name AS BOUND IN THE
CONSUMING MODULE, not at its definition site (`A4-R4-7`). `entry.py` imports its repo functions
directly (`entry.py:14`), so patching `swing.data.repos.trades.<name>` would rebind a name the
service no longer consults, and the capture would silently record nothing. **Task 2 additionally
requires the import to stay in that established style**, so the patch target and the code style are
pinned together rather than one drifting from the other. The patch captures the connection object it
is handed. Drive the (c) fixture (commit raises with the row landed).

**Post-fix:** the captured object **is not** the writer's connection, and it is a
`sqlite3.Connection` opened on the same path. **Pre-fix (the R10-02 shape -- reading on the writer's
own handle):** the captured object IS the writer's connection. This is the half of VISIBILITY that
is closed by construction, and it is pinned so a later refactor cannot quietly re-introduce the
convenience of "we already have a connection right here".

### (RD-a3) R10-02 REPRODUCED -- a pending row is never reported durable

**Fixture:** commit raises without landing; `rollback()` raises **before taking effect**, so the
writer's transaction stays OPEN with the entry row PENDING.

**Post-fix:** `record_entry` RAISES (the cleanup error chained from the write error); no
`EntryResult` is returned; **a FRESH connection sees `COUNT(*) = 0`** for the ticker -- which is the
sharpest part of the row, because it shows that the false SUCCESS in R10-02 came specifically from
reading the WRITER's own connection and not from any property of the ledger.
**Pre-fix (the reverted clause-2 helper, and any implementation that reads on `conn`):** the read
observes the writer's own uncommitted row and returns SUCCESS carrying a "DURABLE" warning over a
merely-pending row.

### (RD-b) A CONCURRENT INSERT TAKING OUR ROWID IS NOT CONFIRMED AS OURS

**Fixture:** a connection proxy whose `commit()` raises without landing, and whose `rollback()`
performs the real rollback and **then, on a SECOND connection, inserts a different trade** -- which
is issued the rowid our rolled-back attempt had just used (MEASURED: this is the default on a bare
`INTEGER PRIMARY KEY`, and it is also what `AUTOINCREMENT` would have done).

**Premise asserted first, so the test cannot pass for the wrong reason:** `SELECT ticker FROM trades
WHERE id = <our INSERT's lastrowid>` returns the OTHER ticker, and its `attempt_id` is not ours.

**Post-fix:** the probe is keyed `WHERE attempt_id = ?`, finds nothing, and `record_entry` re-raises
the ORIGINAL `OperationalError`; `SELECT COUNT(*) FROM trades WHERE ticker = <ours>` is **0**.
**Pre-fix (a rowid-keyed probe -- the reverted helper):** the read finds the OTHER row and returns
SUCCESS naming a trade the operator never entered. That is `22A-FIX-R10-03`, reproduced on this tree
rather than quoted, and killed.

### (RD-b2) THE DECLARED RESIDUAL, VERIFIED BY EXECUTION -- a rolled-back token CAN be re-minted

**Why this row exists:** `A4-R1-1` showed the plan's claim that the index makes a duplicate token
"impossible to commit" is FALSE for a token that was rolled back -- the index keeps no memory of it.
The design is unchanged (S2.0), the claim is rewritten, and the residual is DECLARED at S7.7. **A
declaration nobody executes is a claim, so this row executes it.**

**Fixture:** attempt A mints token `X` and its commit fails without landing; A rolls back, so `X`
exists nowhere. A second connection then commits a row for the SAME ticker carrying `X` (planted by
raw INSERT -- a `uuid4` collision is not reproducible, and the test's subject is the CONSEQUENCE of
one, not its likelihood). The probe then runs.

**Post-fix:** the probe **DOES** return that row and the settle would confirm it -- **and the test
ASSERTS exactly that**, with a docstring naming it as S7.7's declared residual, its arithmetic
(about `n^2 / 2^123`; ~1e-27 at `n = 10^5`), and the two independent conditions a real occurrence
would need (an RNG collision AND the same ticker). **Pre-fix:** the column does not exist.
**This test must be READ AS A DECLARATION, not as an aspiration:** if a future arc makes uniqueness
structural, this row is the one that must be inverted, and its failure is the notification.

### (c) A COMMIT WHOSE OWN RETURN WAS LOST, WITH THE ROW LANDED -> SUCCESS

**Fixture:** the module's existing `_RaiseAfterCommit` proxy (performs the REAL commit, then
raises), parametrised over BOTH paths -- on the latched path the raise comes from `commit()`, on the
pre-arc path from `with conn:`'s `__exit__`.

**Post-fix:** `record_entry` RETURNS an `EntryResult`; `result.trade_id` equals the id the probe
read; **exactly ONE** row exists for the ticker; `result.post_commit_warnings` contains an entry
naming the trade id and saying the commit's own return was lost, durability was confirmed by attempt
identity, and the entry must NOT be retried; the connection is not left in a transaction.
**Pre-fix (today's tree):** `sqlite3.OperationalError` propagates -- which is precisely what
`tests/trades/test_22a_task9_entry_wiring.py:3191` asserts today. **That test is this row's pre-fix
half; Task 4 REWRITES it in place rather than deleting it**, keeping its declaration prose as the
record of what changed and why.

### (c2) A REAL COMMIT FAILURE, NO PROXY

**Fixture, taken from MEASURED (3)/(3b) rather than invented:** a rollback-journal database, a
second connection holding an open READ transaction, and the entry's commit failing with `database is
locked`. Run on **both** paths, because MEASURED (3b) proved they differ.

**Post-fix, deferred path:** `__exit__` rolled back, so `conn.in_transaction` is **False**,
`resolution` reads `"not_needed"`, the probe runs on a fresh connection **and succeeds** (it is
blocked while the writer holds the PENDING lock and is not after resolution -- MEASURED (3)),
returns ABSENT, and the ORIGINAL `OperationalError` propagates; `COUNT(*) == 0`.
**Post-fix, immediate path:** identical outcome, reached through the wrapper's OWN rollback,
`resolution == "rolled_back"`.
**Pre-fix, both paths:** the same `OperationalError` propagates -- so the ESCAPING EXCEPTION does
not discriminate, and **the discriminating assertion is `resolution` plus the fact that the probe
ran and returned ABSENT** (captured via the same monkeypatch as RD-a1). Stated explicitly because a
row whose only assertion is "it raised" would pass on both trees.
*Why this row exists at all:* every other lost-commit row uses a proxy, and a proxy tests the
handler rather than the condition. This one produces the real condition, on the real context
manager, and it is the row that would have caught the first draft's `A4-R1-2` premise error.

### (d) A COMMIT WHOSE OWN RETURN WAS LOST, WITH THE ROW ABSENT -> RE-RAISE

The module's existing `_CommitNeverLands` proxy. **Post-fix:** the ORIGINAL exception's CLASS and
MESSAGE propagate (`sqlite3.OperationalError`, "database is locked"), `COUNT(*) == 0`, and
`conn.in_transaction` is False.

**AND THAT IS NOT ENOUGH, BECAUSE ALL THREE ARE ALSO TRUE ON TODAY'S TREE** (`A4-R3-7`; the first
draft answered this by naming a hypothetical naive implementation, which does not make the row
evidence for THIS arc). **The discriminating assertions are added:** the probe was called **exactly
once**, **with the minted token**, **on a connection that is not the writer's**, and it returned
`None`. **Pre-fix on the current tree:** there is no probe, so the call count is 0 and the row
fails. That also excludes an implementation which skips settlement entirely and re-raises by
accident -- which would otherwise look identical from the outside.

### (w) ONE TOKEN, END TO END -- mint to INSERT argument to probe argument

**Why this row exists (`A4-R2-4`): every other identity row plants a CONSTANT token, and a constant
masks the two defects that matter.** An implementation that minted separately for the INSERT and for
the settlement would pass every constant-token test and then, in production, probe for a token it
never wrote -- re-raising over every durable lost commit, silently, with the suite green. And no row
asserted that `record_entry` passes its OWN token to the repo at all: a correct repo (r1) plus a
`record_entry` that calls it with `attempt_id=None` and stamps later also passes.

**Fixture:** `_mint_attempt_token` monkeypatched to return a DIFFERENT valid 36-character value on
each call; `insert_trade_with_event` wrapped to capture its `attempt_id` keyword;
`find_trade_id_by_attempt_id` wrapped to capture the token it is handed. Drive the (c) lost-commit
fixture so all three points are reached.

**Post-fix:** the mint is called **exactly once**; the captured INSERT argument **equals** the minted
value; the captured probe argument **equals** the same value; and the persisted row's `attempt_id`
equals it too. **Pre-fix / against the two defective implementations named above:** the mint-count
assertion fails the double-mint, and the INSERT-argument assertion fails the disconnected one --
neither of which any constant-token row can see.

### (w2) THE MINT'S OWN CONTRACT -- that it draws from `uuid.uuid4` at all

**Why this row exists (`A4-R6-5`): every identity row including (w) monkeypatches
`_mint_attempt_token` ITSELF, so a production mint returning a CONSTANT valid 36-character string
passes all of them** -- and LOCK-A only checks that the token is valid and non-NULL. A constant mint
is precisely the systematic-reuse defect S7.8 says is deterministic rather than astronomical, and the
plan claimed (w) excluded it "by construction". **It did not.**

**Post-fix:** patch **`uuid.uuid4`** (one level BELOW the mint) with distinct sentinel UUIDs; assert
`_mint_attempt_token` calls the provider **exactly once per mint** and returns **exactly
`str(sentinel)`**; then drive **TWO attempts, the first rolled back**, and assert the second mint
produced a **DIFFERENT** token. **Pre-fix / against a caching or constant mint:** the second attempt
returns the first token and the row fails -- which no `_mint_attempt_token`-level patch can detect.
**S7.8's claim is narrowed to match:** (w) proves the token is threaded consistently; **(w2)** is
what excludes a reissuing generator, and neither makes reuse impossible *by construction* -- that
word belonged to the banked allocator and has been removed.

### (e) CO-DURABILITY, OBSERVED AT THE TRANSACTION BOUNDARY

> **Rewritten after `A4-R2-5`.** The first version asserted "committed row carries the token /
> rolled-back leaves none", and the reviewer showed that pair is satisfied by a LATE STAMP: commit
> the trade with no token, then `UPDATE` it in a second transaction. The committed half sees a
> token, the rolled-back half never reaches the update, and the test goes green over a design that
> violates the constraint it exists to prove. The observation has to happen at the boundary.

**Fixture:** a connection proxy whose `commit()` FIRST performs two reads and only then commits --
(a) on the WRITER's own connection, `SELECT attempt_id FROM trades WHERE id = ?`; (b) on a FRESH
connection, `SELECT COUNT(*) FROM trades WHERE attempt_id = ?`.

**Post-fix, at the boundary:** (a) returns the minted token -- the writer already holds it, so it
was written by the INSERT and not afterwards -- while (b) returns **0**, because nothing is durable
yet. **Post-fix, after the commit:** exactly one row, `attempt_id == TOK`, and the entry event, the
fill and the risk-policy stamp all present -- the token's presence coincides with the whole
transaction's.
**Post-fix, rolled back** (drive an entry whose body raises after the INSERT): `SELECT COUNT(*) FROM
trades WHERE attempt_id IS NOT NULL` is **0** and `COUNT(*) FROM trades` is 0.
**Against the LATE-STAMP implementation:** read (a) returns `None` at the boundary -- the row exists,
pending, with no token -- and the test fails there, which is precisely where it must.
**Pre-fix:** the column does not exist.

### (e2) THE IDENTITY APPARATUS CANNOT FAIL AN ENTRY

**SEVEN CONTAINED-FAILURE VARIANTS PLUS ONE INTERRUPT-PROPAGATION CONTROL -- eight scenarios**
(`A4-R6-9`: the first version said "six" and then enumerated seven, with the interrupt case tacked on
outside the count; a manifest an executor can under-read by one is the defect, not the arithmetic).
**The seven contained failures:** (1) `_mint_attempt_token` RAISES; it RETURNS (2) `""`, (3)
`"short"`, (4) a 37-character string, (5) `b"..."` (bytes), (6) `None`; and (7)
`_resolve_main_db_path` RAISES. **Plus (8), a CONTROL of the opposite polarity:** a
`KeyboardInterrupt` from the mint PROPAGATES and is not swallowed.
**And a NINTH, added by `A4-R6-4`:** a 36-BYTE BLOB return, which passes a bare length check and must
be contained as identity-unavailable rather than reaching the repo. **The
malformed-RETURN variants are the ones that matter**: without result validation in
`_begin_attempt_identity` (S2.1) the value reaches the repo, trips the pre-write `ValueError` that
(r3) requires, and FAILS AN ENTRY THAT WOULD HAVE SUCCEEDED -- the exact outcome the containment
exists to prevent, arriving through the containment's own blind spot.
**Post-fix, all EIGHT contained variants (1-7 plus the BLOB):** `record_entry` SUCCEEDS; the row is
present with `attempt_id IS NULL` (the raise and the six malformed returns) or with a valid token but
no probe available (the path variant); and a WARNING is logged in each case.
**Post-fix, the control:** the `KeyboardInterrupt` escapes and no row is written.
**Pre-fix (an uncontained implementation):** the exception escapes and a money-bearing entry fails
because an identity nicety was unavailable.
*Both variants also assert the exit condition of the containment: a `KeyboardInterrupt` from the
mint is NOT swallowed* -- the `Exception`-not-`BaseException` choice of S2.1, asserted rather than
described.

### (f) NO DATABASE PATH -> TODAY'S BEHAVIOUR

An in-memory connection (`_resolve_main_db_path` returns `None`) driven through the (c) fixture.
**Post-fix:** the ORIGINAL exception propagates; no crash inside the settle; a contained WARNING
records that the probe was unavailable. **Pre-fix (an implementation that assumes a path):**
`TypeError`/`OperationalError` from `open_connection(None)` -- a NEW failure mode introduced on the
lost-commit path, which is the one place a new failure mode is least welcome.

### (g) A RAISING PROBE LEAVES THE ORIGINAL EXCEPTION UNTOUCHED

`_durability_probe` monkeypatched to raise a distinctive exception.

**What `log_contained_note` ACTUALLY does, because the first draft of this row described it wrongly**
(`A4-R4-5`, verified at `swing/trades/entry.py:251-315`): it EMITS the message through the logger and
attaches a note to the escaping exception **only when the logging SINK itself raises**. With a
working logger there is no note. The helper is still the right one -- the probe failure IS reported,
the escaping exception's evidence IS preserved across the whole sequence, and a failing sink is
itself surfaced -- but the assertion has to match.

**Post-fix, working sink:** the ORIGINAL commit exception escapes with its **type, `args`,
`__cause__` and `__context__` unchanged**, and an ERROR record naming the probe failure was emitted.
**Post-fix, RAISING sink:** same exception, same evidence, **plus** a note recording the sink
failure. **Pre-fix (an uncontained probe):** the probe's exception replaces the commit's and the
caller is told about a probe rather than about the entry. This is the R11-03 property applied to the
code this arc adds -- asserted on the IDENTITY of what escapes, never on "no crash".

### (h) THE PROBE CONNECTION IS NOT SHARED-CACHE

**The PRAGMA is executed INSIDE the monkeypatched repo reader, while it still owns the LIVE probe
connection, and only the scalar is stored** (`A4-R2-8`: the first draft said "capture the connection
as in RD-a2 and then query it", which runs against a connection `_durability_probe` has already
closed in its `finally`).
**Post-fix:** the stored scalar is 0. **Pre-fix, concretely:** `_durability_probe` does not exist,
so the monkeypatch target cannot be imported -- this pins the construction-time precondition that makes "a fresh connection sees only committed state" TRUE rather than assumed,
without adding a runtime branch that would be defensive dead code.

### (i) THE BELT IS STILL THE BELT -- a CONTROL, not a fix

After a settled SUCCESS from (c), a second `record_entry` for the same ticker raises
`DuplicateOpenPositionError` naming the ticker. **Post-fix and pre-fix: identical.** It is here so
the belt is not mistaken for the fix and so the arc cannot silently weaken it: what CHANGED is that
the operator is now TOLD the entry exists, so the retry that the belt refuses should no longer
happen.

### (j) THE POST-COMMIT-STEP PATH IS UNCHANGED

`outcome.committed` True with a later failure -> the existing degraded warning text, byte for byte,
and no lost-commit warning. **Post-fix and pre-fix: identical.** A regression control on 22-A3's
shipped clause-1 behaviour, because S2.4 edits the handler both branches run through.

### (k) THE DEFERRED PATH OBSERVES ITS OWN RESOLUTION -- it does not perform it

> **Rewritten after `A4-R1-2`.** The first draft asserted `in_transaction is True` pre-fix and
> proposed adding a rollback. MEASURED (3b) says otherwise: `sqlite3.Connection.__exit__` rolls back
> when its own commit fails, so `in_transaction` reads **False** on both trees. The row that would
> have gone green against a false premise is replaced by the one that measures the real thing.

`_CommitNeverLands`-shaped failure on the **pre-arc** path (the commit raises without landing).

**Post-fix:** `conn.in_transaction` is **False** afterwards (unchanged from pre-fix -- Python did
that, not this arc); `outcome.body_completed` is True, `outcome.committed` is False, and
**`outcome.resolution == "not_needed"`**; nothing partial is visible to a fresh connection; the
ORIGINAL exception propagated. **Pre-fix:** `_CommitOutcome` has no `resolution` field at all, so
the assertion raises `AttributeError`. **The discriminator is the OBSERVATION, not the connection
state** -- which is the honest statement, because the connection state was never this arc's to fix
on that path.

### (k2) THE DEFERRED PATH'S EXCEPTION IDENTITY IS UNCHANGED -- a LOCK assertion

> **Also rewritten after `A4-R1-2`,** and its polarity is INVERTED: the first draft declared a
> behaviour change here and routed it to CHARC. There is no change to declare, so this row now pins
> the ABSENCE of one.

Drive the pre-arc path so the commit raises, and additionally make the wrapper's residual
`_observe_resolution` rollback arm raise (a proxy whose `in_transaction` reports True after
`__exit__` and whose
`rollback()` raises).

**Post-fix:** the ORIGINAL write exception escapes -- **not** a cleanup exception, **not** a chained
`raise ... from ...` -- with its type, args and `__cause__` unchanged; `outcome.cleanup_raised` is
True; the rollback failure is present in the logs; and the probe is NOT called.
**Pre-fix:** the original escapes too (there is no arm) -- so **the discriminating assertions are
`cleanup_raised is True` and the probe's call count of ZERO**, and the exception-identity
assertion is a LOCK: it fails an implementation that copies the immediate path's
`raise cleanup_error from write_error` onto the pre-arc path, which is what the first draft would
have shipped.

### (k3) THE `committed` OBSERVATION IS INSIDE THE RESOLVING SUITE -- static AND runtime

> **Rewritten after `A4-R2-6`, which disproved this row's founding claim and then weakened its
> assertion.** The first version said the window "cannot be simulated"; it can, with a
> `sys.settrace` line hook. And its AST predicate -- "inside SOME `try` whose handlers cover
> `BaseException`" -- is satisfied by an unrelated or nested `try/except BaseException: raise` that
> records no resolution at all, so the test could have blessed the very window it was written to
> close.

**(k3a) STATIC, and the predicate is now specific:** parse `swing/trades/entry.py` with `ast`, locate
`_entry_transaction`, and assert that every assignment to `outcome.committed` sits directly in the
`Try.body` of a `try` **whose handler both (i) writes `outcome.resolution` (directly or through the
shared `_observe_resolution` call) and (ii) re-raises** -- on both branches of the `immediate` split.
**Post-fix:** passes. **Against the first draft's shape:** the deferred assignment is outside the
`Try` entirely -> fails. **Against a nested-decoy shape:** the enclosing handler writes no
resolution -> fails, where the weak predicate passed.

**(k3b) RUNTIME, because it turns out to be reachable:** install a `sys.settrace` local trace hook
that raises a sentinel exception at the line of the deferred path's `outcome.committed = True`,
after the `with` has returned. **Post-fix:** the handler catches it, `resolution` reads
`"not_needed"`, `record_entry` settles by probe and returns SUCCESS over the durable row.
**Against the first draft's shape:** the sentinel escapes `_entry_transaction` uncaught,
`resolution` is `"unattempted"`, the settle gate refuses, and `record_entry` re-raises **over a
durable entry** -- the exact defect, demonstrated rather than argued. *Kept alongside (k3a) rather
than replacing it: the trace hook proves the behaviour at ONE line, the AST walk proves the property
for every assignment including ones added later.*

---

## S4. FILE STRUCTURE

**New:**

| path | what |
|---|---|
| `swing/data/migrations/0038_trade_attempt_identity.sql` | `ALTER TABLE trades ADD COLUMN attempt_id TEXT CHECK (...)`, the UNIQUE partial index, **the `trg_trades_attempt_id_immutable` BEFORE-UPDATE trigger (S2.0 -- MANDATORY; it is what closes the `A4-R4-1` false-success path)**, `UPDATE schema_version SET version = 38`, inside an explicit `BEGIN; ... COMMIT;` (gotcha #9), with a reversibility header naming BOTH the `DROP INDEX` and the `DROP TRIGGER` |
| `tests/data/test_migration_0038_attempt_identity.py` | (m1)-(m6), **(m7) the schema trigger**, (r4), (r5) -- all in Task 1's single commit |
| `tests/trades/test_22a4_corrector_refusal.py` | **(m8a) typed refusal, (m8b) order-independence** -- Task 1b |
| `tests/cli/test_22a4_corrector_refusal_cli.py` + `tests/web/test_routes/test_22a4_corrector_refusal_delivery.py` | **(m8c) delivery through the UNCHANGED callers** -- Task 1b |
| `tests/trades/test_22a4_attempt_identity.py` | (e), (e2), **(w)**, **(w2) the mint contract**, (f), (g), (h), (r1)-(r3), (r6) |
| `tests/trades/test_22a4_clause2_settlement.py` | (RD-a1), (RD-a2), (RD-a3), (RD-b), **(RD-b2)**, (c2), (k), (k2), **(k3)** |

**Edited:**

| path | what |
|---|---|
| `swing/data/db.py` | `EXPECTED_SCHEMA_VERSION` 37 -> 38; `PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES`; `_create_pre_phase22_arc_a4_migration_backup`; `_phase22_arc_a4_backup_gate` + its call in `run_migrations` |
| `swing/data/repos/trades.py` | `insert_trade_with_event(..., attempt_id=None)` + the v38 INSERT branch + the shape guard + the pre-v38 contained drop; new `find_trade_id_by_attempt_id`; `ATTEMPT_ID_LENGTH` |
| `swing/trades/entry.py` | `_mint_attempt_token`, `_AttemptIdentity`, `_begin_attempt_identity`, `_durability_probe`, `_settle_by_attempt_identity`, `_observe_resolution`; `_CommitOutcome` +3 fields (`body_completed`, `resolution`, `cleanup_raised`) for FOUR observations total; both `_entry_transaction` paths (observations only on the deferred one); the post-commit handler's new branch; the narrowed IntegrityError match; the declaration block rewritten |
| `tests/trades/test_22a_task9_entry_wiring.py` | `test_CONTRACT_a_commit_whose_own_return_was_LOST_re_raises` rewritten in place as the settled-by-identity row (test (c)); its declaration prose kept as the record of what changed |
| the version mirror family, **SIX spellings across ~30 files, NO total quoted** | 26 `EXPECTED_SCHEMA_VERSION == 37`; 11 bare-literal assertions; 4 `_current_version(...) == 37` (**2 of which stay at 37**); 1 chained (overlaps row 1); **1 INEQUALITY ceiling `versions[-1] <= 37` -- the L3 authorization gate**; and **15 `target_version=37` call sites -- 12 `run_migrations(...)` calls plus 3 direct `_phase22_arc_a_backup_gate(...)` calls -- of which 8 STAY PINNED and 7 gain a SECOND call to `EXPECTED_SCHEMA_VERSION`**. Counts are FLOORS and OVERLAP (`A4-R4-10`); the manifest is the greps plus a READ of every hit. The closure check is the full suite for the assertion families and a READ for the call sites, which fail nothing. |

**Untouched, and named so the envelope is checkable:** `swing/web/**`, `swing/cli.py`,
`swing/data/models.py`, `swing/trades/latched_origin.py`, `swing/trades/cohort_provenance_correction.py`.

---

## S5. TASK LADDER (TDD; one red -> green -> commit per task)

### Task 0: **RULED 2026-09-06 -- CLOSED. Recorded here because the ladder below was blocked on it.**

- [x] **RD RULED: `uuid4` SATISFIES constraint 2. The shape is (S-b).** **The canonical reading,
      binding on every future appeal:** *"never reusable" means the mechanism must contain **NO PATH
      THAT REISSUES** a token.* The rowid failed **because the ENGINE ITSELF hands a rolled-back id
      to the next insert -- reuse is an active, designed-in mechanism.** `uuid4` has no reissue path;
      a repetition is an RNG FAILURE, not a behaviour of the mechanism. **And it demands no certainty
      beyond what this project's evidence chain already rests on:** the H1 amendment text is pinned
      by sha256 and broker snapshots by digest -- **collision-resistance IS the admissibility
      standard elsewhere in this system.**
- [x] **CHARC RATIFIED five items** (S9): migration 0038 as shaped, the LOCK-A amendment in the
      stated shape, the `<= 37` -> `<= 38` ceiling **opened for 0038 only**, the backup gate and its
      expected-tables set, and **the S2.0 divergence** (no `Trade` field, no `_row_to_trade` change --
      he verified 57 / 56 / `{risk_policy_id_at_lock}` on the live database himself).
- [x] **ONE CONDITION ATTACHED, and it WIDENS THE ENVELOPE: S8.6 is NOT banked -- the corrector's
      typed refusal SHIPS IN THIS ARC.** See Global Constraints and Task 1b.
- [ ] **RIDER CLAUSE 1 ROUTED BACK -- RD's S7.7 DETECTION REASON.** He attached it as load-bearing
      and instructed stop-and-route if it failed. **It failed:** *"a rolled-back token leaves no row
      to confirm"* is true at the instant of rollback and does not survive to probe time
      (REPRODUCED). See S7.7 and S9 RD item 2. **Scope, so it does not read stronger than it is:**
      the counterexample lives ENTIRELY INSIDE the collision branch, so it refutes the REASON without
      changing the practical weight.
- [ ] **RIDER CLAUSE 2 ROUTED BACK -- the `fork` RE-OPEN TRIGGER for the banked allocator.**
      MEASURED from CPython 3.14 source: `uuid4` is `int.from_bytes(os.urandom(16))` per call, with
      no process-local PRNG state, so a POSIX port that acquires `fork` would fire the trigger with
      no hazard present. Bare `fork` is struck; generator-change and entropy-duplication survive.
      **THIS SECOND BOX EXISTS BECAUSE THE CHECKLIST PREVIOUSLY SAID "ONE CLAUSE" WHILE THE FRONT
      MATTER AND S9 SAID TWO** (`A4-R7-4`) -- an authorization checklist that can be marked closed
      without disposing of a director-owned clause is the claimed-fix-not-present class applied to
      governance.
- [ ] **NEITHER CLAUSE AFFECTS THE RULING**, which rests on the no-reissue-path reading and
      verifies. What is open is wording RD owns.

### Task 0b: **THE 22-A LOCK-A AMENDMENT** -- lands in Task 1's commit, ruled at Task 0

**The defect this closes was found by review, not by the suite** (`A4-R3-2`, verified at the source).
`tests/trades/test_22a_task9_entry_wiring.py:1037-1041` asserts BOTH
`set(a) == set(LOCK_A_PRE_ARC_ROW)` (the complete `trades` COLUMN SET) and `a ==
LOCK_A_PRE_ARC_ROW` (full dict equality) against a golden captured by running `record_entry` at the
pre-arc commit `a18a3771`. **Adding `attempt_id` fails both**, and the test's own docstring
ANTICIPATED this arc: *"If a later change adds a `trades` column, a dict comparison would fail on the
diff -- but a comparison written to tolerate that (subset, or key intersection) would silently stop
covering the new column, so the failure is left loud."*

- [ ] **The amendment is therefore constrained by that docstring and must NOT soften the
      comparison.** Assert `set(a) == set(LOCK_A_PRE_ARC_ROW) | {"attempt_id"}` -- the addition
      NAMED, not tolerated -- then `{k: v for k, v in a.items() if k != "attempt_id"} ==
      LOCK_A_PRE_ARC_ROW` (byte identity preserved for every PRE-EXISTING column), then a THIRD
      assertion that `a["attempt_id"]` is a valid non-NULL token. The lock gets STRONGER: it now
      covers the new column explicitly instead of merely failing on it.
- [ ] **BOTH ROWS, NOT ONE** (`A4-R4-2`). The shipped test compares `a` (the `cfg`-PASSED run) AND
      `b` (the `cfg=None` run) against the golden; the first draft of this task amended only `a`, and
      `b == LOCK_A_PRE_ARC_ROW` fails for the same reason the moment the column exists. Both get the
      three-assertion treatment, **and `b`'s token must be non-NULL too** -- which is the assertion
      that pins S2.1's decision to mint regardless of `cfg`.
- [ ] **THIS IS WHY THE MINT LANDS IN TASK 1 AND NOT LATER** (`A4-R4-2`, the sequencing half): a task
      that adds the column and the repo capability but leaves `record_entry` passing the new
      `attempt_id=None` default cannot satisfy its own amended lock, so the prescribed
      red -> green -> commit cycle could not close. Task 1 therefore carries the mint and the
      threading as well; Task 2 keeps only what does not affect the persisted row.
- [ ] **`record_entry`'s docstring becomes false and is rewritten in the same commit.**
      `swing/trades/entry.py:633` promises that `cfg=None` leaves *"every persisted value
      byte-identical to the pre-arc behaviour"*, and S2.1 writes a token regardless of `cfg`. Leaving
      it is the #31 class -- a comment that still reads true while the code moved underneath it. New
      text: byte-identical for every pre-arc COLUMN, plus a per-attempt `attempt_id` that is not
      part of the pre-arc row and carries no domain meaning.
- [ ] **ROUTED, not assumed** (S9 CHARC item **5**): LOCK clause (a) belongs to a merged arc.

### Task 1: **THE SCHEMA AND EVERY MIRROR, IN ONE COMMIT** (migration 0038 + the repo write/read + the version-mirror family + the IntegrityError narrowing)

> **Tasks 1 and 2 were SEPARATE in the first draft and are now ONE** (`A4-R2-3`). Splitting them
> contradicted gotcha #11 (*"schema-CHECK + Python-constant + dataclass-validator MUST land in ONE
> task for atomic consistency"*), the commissioning brief's *"Mirrors in ONE commit (#11)"*, and this
> plan's own S2.5 sentence saying a schema change and the Python mirror that keeps it honest are one
> atomic deliverable. It would also have produced an intermediate revision carrying schema v38 with
> no validator, no carrying INSERT branch and no closure check.

- [ ] Write `0038_trade_attempt_identity.sql`: explicit `BEGIN;`, one `ALTER TABLE trades ADD COLUMN
      attempt_id TEXT CHECK (attempt_id IS NULL OR (typeof(attempt_id) = 'text' AND
      length(attempt_id) = 36))` -- **the `typeof` half is REQUIRED and this checklist carried the
      vulnerable length-only form for a full round after S2.0 was corrected** (`A4-R7-1`; MEASURED:
      a 36-BYTE BLOB passes length-only and sits in the UNIQUE index beside its byte-identical text
      twin) -- one
      `CREATE UNIQUE INDEX ux_trades_attempt_id ON trades(attempt_id) WHERE attempt_id IS NOT NULL`,
      **one `CREATE TRIGGER trg_trades_attempt_id_immutable BEFORE UPDATE OF attempt_id ON trades
      BEGIN SELECT RAISE(ABORT, '...'); END;`**, `UPDATE schema_version SET version = 38` as the
      FINAL statement, `COMMIT;`. The header carries: the reversibility clause -- **BOTH
      `DROP INDEX ux_trades_attempt_id;` AND `DROP TRIGGER trg_trades_attempt_id_immutable;`**, the
      column staying because it is nullable and inert -- why nullable, why partial, why the CHECK is
      length-only, why the trigger is unconditional and carries no `WHEN`, the
      one-migration-one-version-bump rule, **and the TWO JURISDICTION NOTES CHARC requires in the
      header itself (2026-09-06)**:
      **(A) A `BEFORE UPDATE` TRIGGER CANNOT SEE `INSERT OR REPLACE`.** The header states that the
      guard covers **UPDATE**, and that the REPLACE family was **GREPPED EMPTY against `trades`** --
      so a future REPLACE writer is **a DECLARED BREACH rather than an unknown**. *Method and count,
      recorded because a bare "we checked" is what this class survives on:* CHARC grepped the family
      across `swing/`; re-run here, `insert or replace into trades` / `replace into trades` returns
      **ZERO**, and the broader `insert or replace|replace into` returns 45 hits across 22 files of
      which **ZERO are executable statements** -- every one is prose in a migration header, a trigger
      message, or a docstring warning about this very class.
      **(B) 22-B DEMAND A REBUILDS `trades` (DROP + CREATE).** A rebuild that does not RE-CREATE both
      `ux_trades_attempt_id` and `trg_trades_attempt_id_immutable` **silently drops the guard** --
      the 0035 header's own lesson about what a rebuild costs, applied forward. CHARC has banked it
      as a **22-B precondition**; this header records it so the next rebuild's author meets it in the
      file rather than in a review.
      **THE TRIGGER IS NOT OPTIONAL, AND ITS ABSENCE FROM THIS CHECKLIST WAS THE ROUND-5 CRITICAL**
      (`A4-R5-1`): round 4 added it to S2.0's prose and to the test roster and to NOTHING an executor
      reads as a work item, so a plan whose prose called it mandatory shipped a ladder that omitted
      it -- and the omitted thing is the only guard against the `A4-R4-1` false success.
- [ ] `swing/data/db.py`: `EXPECTED_SCHEMA_VERSION = 38`;
      `PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES = PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES |
      {"candidates_immutability_epoch", "latch_order_mandate_links", "fill_envelope_identity"}` (the
      three tables 0037 created, read out of the migration file rather than recalled);
      `_create_pre_phase22_arc_a4_migration_backup` (the 0037 mirror, filename
      `swing-pre-22a4-migration-<ISO>.db`); `_phase22_arc_a4_backup_gate` firing ONLY at
      `current_version == 37 and target_version >= 38`; its call added to `run_migrations` after the
      22-A gate.
- [ ] `swing/data/repos/trades.py`, **in this same commit**: `ATTEMPT_ID_LENGTH = 36` (the Python
      side of the CHECK); `insert_trade_with_event(conn, trade, *, event_ts, rationale=None,
      attempt_id=None)` with the shape validation BEFORE any write -- **`None`, OR
      `isinstance(attempt_id, str)` AND exactly `ATTEMPT_ID_LENGTH` characters -> `ValueError`. The
      `isinstance` half mirrors the CHECK's `typeof` half and is not optional** (`A4-R7-1`): a
      36-byte `bytes` value satisfies a bare length test in Python exactly as a BLOB satisfies
      `length()` in SQLite; the FOURTH era branch selected by
      `"attempt_id" in cols`, identical to the v27+ branch plus the one column and one placeholder,
      **with the new column's bound parameter verified against its position, not just its name**;
      the pre-v38 contained-WARNING drop; and `find_trade_id_by_attempt_id(conn, attempt_id)`,
      schema-aware.
- [ ] `swing/trades/entry.py`: narrow the IntegrityError match to
      `"UNIQUE constraint failed: trades.ticker"` (S2.5), with the measured message quoted at the
      site and the reason -- the new index makes the loose match a FALSE "already an open position".
- [ ] **THE MINT AND THE THREADING LAND HERE, AS ACTUAL CHECKBOXES** (`A4-R6-2`: Task 0b and Task 2
      both said the mint had moved into Task 1 and Task 1 contained no such work, while Task 2 still
      scheduled it -- the amendment was announced in two places and performed in neither):
      `_mint_attempt_token()`, `_AttemptIdentity`, **the COMPLETE `_begin_attempt_identity(conn)` per
      S2.1 -- `Exception`-not-`BaseException` containment AND result validation
      (`isinstance(str)` + exact length), not a stub to be hardened later** (`A4-R7-2`: splitting the
      helper across two commits meant Task 1 either shipped a helper that could fail an otherwise
      successful entry, or Task 2 had no genuine red) -- and the
      `record_entry` -> `_record_entry_inner` -> `insert_trade_with_event(attempt_id=...)` threading.
      **Task 1's amended LOCK-A asserts a non-NULL token on BOTH rows, so without these the task
      cannot reach its own green.**
- [ ] **(e) and (e2) ARE SCHEDULED HERE TOO**, with the complete helper they test (`A4-R7-2`).
      **(e2) is written with ALL EIGHT contained variants PLUS the `KeyboardInterrupt` propagation
      control, ENUMERATED FROM S3's list so the two manifests cannot drift** (`A4-R6-9`).
      *This requirement lived only in Task 2's checklist and was DROPPED when Task 2 was withdrawn
      above -- found by this plan's own post-round-7 self-audit looking for exactly that class, and
      restored here. A withdrawal is an edit, and an edit can lose a fix as easily as a rewrite can.*
- [ ] **(w2), THE MINT-CONTRACT TEST, IS SCHEDULED HERE -- it goes where the mint goes.** Found
      missing by the post-round-6 SELF-AUDIT: (w2) was specified in S3, listed in S4's file manifest
      and cited in S7.8, and appeared in **no task checklist at all** -- a decision propagated into
      the argument and not into the work, which is `A4-R5-1`'s exact class recurring on a different
      object. It patches `uuid.uuid4` (one level BELOW `_mint_attempt_token`), asserts one provider
      call per mint and exact stringification, and drives TWO attempts with the first rolled back,
      requiring DISTINCT tokens.
- [ ] **Sweep the version mirror family -- ALL SIX SPELLINGS of S1.6, in THIS commit, CLASSIFYING
      EACH BY READING IT** (`A4-R2-2`). The rules:
      - **The five ASSERTION families become 38 where the assertion is about HEAD.** Two
        `_current_version(...) == 37` sites in `tests/data/test_22a_task2_migration_0037.py` are
        assertions about **migration 0037's own result** and STAY at 37.
      - **The INEQUALITY ceiling `versions[-1] <= 37`** (`tests/data/test_no_schema_change_v3.py:41`)
        becomes 38 HERE and nowhere else -- its own comment says raising it is *"the guard WORKING AS
        DESIGNED for an AUTHORIZED migration ... which is why the bump belongs in the same commit as
        the migration and nowhere else."*
      - **The 15 `target_version=37` call sites are NOT a single class.** Eight of them are in
        `tests/data/test_22a_task2_migration_0037.py` (`:106`, `:129`, `:143`, `:148`, `:163`,
        `:393`, `:567`, `:748`) and are **0037's own subject or literal arguments to the 22-A backup
        gate under test -- they STAY at 37.** The remaining seven build a v36 world and then want
        PRODUCTION HEAD (`test_22a_task3_epoch_reader.py:306`;
        `test_22a_task4_authorization_ladder.py:90/:944/:1030`;
        `test_22a_task6a_competitor_liveness.py:97/:588`; `test_22a_task9_entry_wiring.py:89`).
      - **For those seven, ADD a second call rather than retargeting the first:** keep
        `run_migrations(..., target_version=37, ...)` and follow it with
        `run_migrations(..., target_version=EXPECTED_SCHEMA_VERSION, ...)`. **A single 36 -> 38 jump
        would bypass the new gate**, because `run_migrations` evaluates every gate ONCE against the
        INITIAL `current`, so a call starting at 36 can never satisfy `current_version == 37` -- the
        strict-equality design working as intended, and a silent hole if the plan had said
        "retarget".
      - **Sites whose intent really is an OLDER schema (`target_version=36` before seeding a
        pre-barrier world, `target_version=16` in `test_exit.py`) are NOT touched.**
      - **A SEVENTH SPELLING: SEMANTIC NAMES AND COMMENTS, which no value-grep can see**
        (`A4-R7-12`). `tests/data/test_22a_task2_migration_0037.py:98` is
        `def test_expected_schema_version_is_37()` whose BODY is a HEAD assertion -- the assertion
        becomes 38 and **the NAME must too**, or the file documents the opposite of what it checks.
        `tests/data/test_no_schema_change_v3.py:34` carries the comment *"so the ceiling is now 37"*
        beside the ceiling this commit raises. **Distinguish these from 0037-SPECIFIC test names,
        which correctly stay pinned.** Not behaviour-bearing; documentation-bearing, in executable
        files.
      - **The counts in S1.6 are FLOORS WITH OVERLAP and are not an edit manifest.** The manifest is
        produced by running the six greps and READING every hit.
- [ ] **Tests:** (m1)-(m6), **(m7) HALF 1 ONLY -- the schema trigger, direct UPDATE, with its
      MUTATION PROOF (remove the `CREATE TRIGGER`, show it RED, restore) required before this task
      can go green.** **(m7) HALF 2 -- the corrector's TYPED refusal -- belongs to Task 1b and MUST
      NOT be required here** (`A4-R6-3`: requiring the whole of (m7) before the task that implements
      the refusal made Task 1 unreachable in its own prescribed order, the amendment-induced
      dependency error the one-cycle-per-task rule exists to prevent). Also (r1)-(r4), (r6), and
      (r5) the static INSERT closure walk over **FOUR**
      statements -- ONE carrying and **THREE** reasoned era exclusions -- **with its mutation proof
      run and shown RED IN BOTH DIRECTIONS** (column removed from the v38 branch; an unreasoned fifth
      statement added). **RED first**: (m1)'s FIRST assertion, `EXPECTED_SCHEMA_VERSION == 38`, fails with
      `AssertionError` (it reads 37); the SQL assertions that NAME the column raise
      `OperationalError: no such column` (`A4-R4-12` -- the two are different transcripts and the
      task must declare the one it will actually see).
- [ ] Commit: `feat(data): Task 1 -- migration 0038 trades.attempt_id, the UNIQUE partial index, the repo write/read mirrors and the version-mirror family, in one commit`

### Task 1b: **THE CORRECTOR'S TYPED REFUSAL** -- CHARC's attached condition, shipping in this arc

> **Ruled 2026-09-06.** This was S8.6, proposed as a banked follow-on; CHARC refused the banking and
> widened the envelope by exactly `swing/trades/reconciliation_auto_correct.py` (Global Constraints).
> **The trigger stays the GUARD OF RECORD** -- it covers writers not yet written -- **and the typed
> refusal is its LEGIBLE FACE.**

- [ ] Add the refusal so `field_name="attempt_id"` on `trades` is refused BEFORE the UPDATE is
      composed, with a typed error, not an abort from the database.
- [ ] **THE SHAPE IS THIS PLAN'S, THE BEHAVIOUR IS RULED.** A **SIBLING set** (e.g.
      `_IMMUTABLE_JOURNAL_FIELDS`) is the likely shape rather than a new entry in
      `_RESERVED_JOURNAL_FIELDS`, because **the existing dict means something different**: its
      **SEVEN** members (`A4-R7-10`; counted at `reconciliation_auto_correct.py:178-190`, and they
      span `fills` as well as `trades` -- `fills.action` and `fills.trade_id` are ROLE columns added
      later) encode COUPLED invariants that can only be written coherently alongside other rows, and
      its message directs the operator to the surface that writes them together. `attempt_id` has no
      such surface.
- [ ] **THE MESSAGE MUST NOT NAME A "COUPLED SURFACE" -- THERE IS NONE.** It names the column as
      **WRITE-ONCE IDENTITY THAT NO SURFACE WRITES**: set by the entry INSERT, never corrected,
      never re-assigned, and refusing it is not a routing hint but a statement that the operation
      does not exist. A message copied from the coupled-surface family would send an operator
      looking for a screen that cannot be built.
- [ ] **THE TYPE MUST BE CALLER-COMPATIBLE, OR THE CONDITION IS NOT MET** (`A4-R6-6`, verified at
      the source). The sibling type is **`ImmutableJournalFieldError(ValueError)`** -- NOT a bare
      `Exception` subclass. The existing `ReservedJournalFieldError` inherits **directly from
      `Exception`** (`reconciliation_auto_correct.py:109`), and both callers reach a `ValueError`
      handler with no handler for that type (`swing/cli.py:3929` region;
      `swing/web/routes/reconcile.py:1640`) -- so a bare-`Exception` refusal would surface as an
      uncaught CLI traceback and a web 500. **That is the same operator experience CHARC's condition
      exists to replace**, arriving one layer out. Deriving from `ValueError` reaches both existing
      handlers with **no production caller edit**.
- [ ] **THE CHECK GOES IN BOTH PLACES, SHARING ONE PREDICATE AND ONE MESSAGE** (`A4-R6-7`, verified
      at the source): `_preflight_reserved_transitions` **and** `_update_journal_field`. The module
      applies multi-field corrections SEQUENTIALLY and preflights the whole payload for exactly that
      reason -- its own comment says a per-field-only check made refusal depend on **JSON KEY
      ORDER**. A backstop-only implementation would execute an earlier field's UPDATE before
      discovering `attempt_id` second.
- [ ] **Tests: (m8a), (m8b) and (m8c)** -- the named S3 rows for this task (`A4-R7-3`): the typed
      service refusal, the multi-field preflight asserting ZERO journal UPDATEs, and DELIVERY through
      the unchanged CLI (exit 2, no traceback) and web (status 400) callers. **(m7) half 2 is
      SUPERSEDED by (m8a)** -- it belonged to a red base that no longer exists once Task 1 lands the
      trigger. **Declared first red: (m8a)'s `sqlite3.IntegrityError`.**
- [ ] **Bounded:** one sibling refusal set, one message constant, the shared predicate at two call
      sites, and the assertions above. **No other change to that module and no sweep** -- the
      widening is exactly this.
- [ ] Commit: `feat(trades): Task 1b -- the corrector refuses attempt_id with a typed error instead of authorizing it into a trigger abort`

### Task 2: **WITHDRAWN -- folded into Task 1. The number is kept so every downstream reference stays valid.**

> **`A4-R7-2`.** Task 2 held the identity apparatus's SAFETY behaviour while Task 1 held the mint
> itself, and the two could not both have honest red/green contracts: if Task 1 implemented S2.1
> fully, Task 2's (e2) was already green; if it did not, Task 1 committed a helper that could fail an
> otherwise successful entry -- on the money path, for a commit. **Task 1 now owns the complete
> helper and both tests.**
>
> **The heading is kept as a withdrawal stub rather than deleted, and the tasks below are NOT
> renumbered.** Renumbering is what produced `A4-R3-11` and then `A4-R7-11`: every stale
> "Task N" reference in this document is a defect this loop has already paid for twice, and a
> withdrawal stub costs one paragraph where a renumber costs a sweep that has failed before.
>
> **One item moved OUT of this task rather than into Task 1:** the direct import of
> `find_trade_id_by_attempt_id` into `entry.py` now lands in **Task 4**, with its first consumer
> (`_durability_probe`). Adding it earlier would commit an unused import and **break the Ruff-clean
> gate this plan requires of every commit** -- the import seam's discipline (`A4-R4-7`) is recorded
> at Task 4 instead.

### Task 3: `_entry_transaction` records FOUR observations (THREE new fields), on both paths

- [ ] `_CommitOutcome` gains `body_completed`, `resolution` and `cleanup_raised`, each documented
      as an OBSERVATION -- and `resolution` is RE-READ from `conn.in_transaction` after any rollback
      attempt, never inferred from the fact that the call raised (`A4-R2-7`).
- [ ] Immediate path: set `body_completed` after `yield`; set `resolution` + `cleanup_raised` in all
      arms of the existing cleanup ladder **without changing either existing message**, through the
      shared `_observe_resolution` so the two paths cannot drift.
- [ ] Deferred path: **OBSERVE only.** Move `outcome.committed = True` INSIDE the `try`
      (`A4-R1-3`), and on a lost commit read `conn.in_transaction` -- normally already False because
      `__exit__` rolled back (MEASURED (3b)). The residual rollback arm of `_observe_resolution`
      fires only when the
      transaction is still open; **its failure is contained and the ORIGINAL exception still
      escapes**, so the pre-arc path's exception identity is unchanged.
- [ ] **Tests:** (k), (k2), (k3). **RED first**: (k) asserts a `resolution` field that does not yet
      exist, and (k3)'s AST walk fails against any shape that leaves the assignment unguarded.
- [ ] Commit: `feat(trades): Task 3 -- the transaction wrapper observes body-completion, resolution and cleanup failure on both paths`

### Task 4: clause 2 returns

- [ ] `_durability_probe(db_path, attempt_id)` per S2.3 -- `open_connection`, bounded busy timeout,
      contained close.
- [ ] **The direct import of `find_trade_id_by_attempt_id` into `entry.py` lands HERE, with its
      first consumer** (`A4-R7-2`): earlier would be an unused import and a Ruff-clean violation.
      **Keep `entry.py`'s existing `from swing.data.repos.trades import ...` style**, so test
      (RD-a2)'s patch target -- `swing.trades.entry.find_trade_id_by_attempt_id` -- is the name the
      service actually consults (`A4-R4-7`).
- [ ] **`_settle_by_attempt_identity(attempt, outcome, req, post_commit_error)`** per S2.4 -- the
      FOUR-argument signature (`A4-R4-6`: Task 4 previously specified three, which makes S2.4's
      required exception-preservation impossible without hidden exception discovery), the four
      observed conditions, `BaseException`-contained, ticker-corroborated, returning the probe's
      `tuple[int, str] | None` UNCHANGED, ALARM on anything unproven.
- [ ] The new branch in `record_entry`'s post-commit handler; the lost-commit warning text (ASCII,
      naming the trade id and saying DO NOT RETRY).
- [ ] **Tests:** **(w)** the end-to-end token-flow row, (RD-a1) in BOTH rollback shapes, (RD-a2),
      (RD-a3), (RD-b), **(RD-b2)**, (c) -- **rewriting
      `test_CONTRACT_a_commit_whose_own_return_was_LOST_re_raises` in place** -- (c2), (d), (f),
      (g), (h), plus the two regression controls (i) and (j).
- [ ] Commit: `feat(trades): Task 4 -- clause 2 returns, settled by a fresh-connection read on attempt identity`

### Task 5: the declaration in code says what is now true

- [ ] Rewrite `swing/trades/entry.py:973-1030`'s DECLARED-RESIDUAL block: it currently says the
      residual is declared and the primitive is *"deliberately NOT built here."* It becomes the
      record of BOTH -- what the residual was, both reproductions, and how each precondition is now
      supplied -- because the two reproductions are the reason the design has the shape it has, and
      deleting them would leave the shape unexplained.
- [ ] Update `_entry_transaction`'s and `_CommitOutcome`'s docstrings for the new observations.
- [ ] No behaviour change; the suite must be unchanged-green.
- [ ] Commit: `docs(trades): Task 5 -- the entry-path declaration records the supplied preconditions, not a residual`

### Task 6: the PRE-REVIEW full-suite gate

- [ ] `python -m pytest -m "not slow" -q` from the worktree; fix to GREEN **before** the Codex loop,
      so the review converges on a green diff. Compare against the plan-time baseline in S11.
- [ ] `ruff check swing/` clean.

### Task 7: the POST-CONVERGENCE final-head gate

- [ ] Re-run the full fast suite on the final head after the last review fix; the number in the
      return report is READ OFF THAT RUN.
- [ ] `git log <base>..HEAD --format='%H%n%(trailers)'` -- every commit's trailers empty.

---

## S6. THE LIVE-MIGRATION GATE -- **operator-witnessed, POST-MERGE, and it is not optional**

**This arc bumps `EXPECTED_SCHEMA_VERSION`, and `connect()` REFUSES a database whose version does
not match** (`swing/data/db.py:2251-2256`). So the moment this merges, the operator's live v37
database is refused by every surface until `swing db-migrate` runs. That is not a side effect to be
discovered; it is the gate.

- **Nobody in this worktree touches the live database.** The executing implementer's tests all build
  their own `tmp_path` databases, and the plan author did not open it.
- **TWO BACKUPS ARE TAKEN AND THEY LIVE IN DIFFERENT PLACES -- the witness must not confuse them**
  (`A4-R1-7`, verified at the source). `swing db-migrate` takes its OWN general snapshot into
  `cfg.paths.backups_dir` and **prints that path** (`swing/cli.py:258-270`); it then calls
  `ensure_schema(db_path)` with **no** `backup_dir` (`:310`), so the ARC gate's backup defaults to
  `src_path.parent` -- the database's own directory, `~/swing-data/` -- and **its name is never
  printed.** The arc backup is the VERIFIED one: `_phase22_arc_a4_backup_gate` fires at exactly
  `current_version == 37`, writes `swing-pre-22a4-migration-<ISO>.db`, and checks it against
  `PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES` before any statement of 0038 runs; on failure it
  raises `MigrationBackupRequiredException` and the source database is untouched. **Both are usable
  for recovery** (the general one is a full `Connection.backup()` taken immediately before), so the
  correction here is to the INSTRUCTIONS, not to the safety. Making the CLI print the arc backup, or
  route it through `backups_dir`, would touch `swing/cli.py` and is **out of envelope**; the
  underlying gap is BANKED at S8.
- **The witness steps, one at a time, each awaiting the operator's result** (the standing
  step-by-step rule -- a batched runbook collapses the gate into a self-report):
  0. **BEFORE MIGRATING -- record the BEFORE-IMAGE** (`A4-R1-6`; without it steps 3 and 4 compare
     against nothing): `SELECT version FROM schema_version`; `SELECT COUNT(*) FROM trades`;
     `PRAGMA table_info(trades)` (assert `attempt_id` is ABSENT, so step 3 is a real transition and
     not a re-read); `SELECT COUNT(*) FROM latch_order_mandate_links`; and the FULL
     `SELECT id, ticker, state FROM trades WHERE state IN ('entered','managing','partial_exited')
     ORDER BY id`. Report all five.
  0b. **`ls ~/swing-data/swing-pre-22a4-migration-*.db` BEFORE migrating and record the result**
     (normally empty). Without this, step 1's `ls` is satisfied by a leftover file from a failed or
     earlier attempt and would CERTIFY A BACKUP THE GATE DID NOT TAKE (`A4-R3-8`).
  1. `swing db-migrate` -> report the printed version and the printed GENERAL backup path, then
     `ls ~/swing-data/swing-pre-22a4-migration-*.db` again and **identify the EXACTLY ONE path that
     is new relative to step 0b**. Open THAT file read-only (a COPY -- never through `ensure_schema`,
     which would migrate the recovery artifact away) and confirm `SELECT version FROM schema_version`
     is **37** and its table set matches the expected set. A backup nobody opened is a filename, not
     a pre-image.
  2. `SELECT version FROM schema_version` -> 38.
  3. `PRAGMA table_info(trades)` -> `attempt_id` present; `SELECT COUNT(*) FROM trades` **equal to
     step 0's count**; `SELECT COUNT(*) FROM trades WHERE attempt_id IS NOT NULL` -> 0.
  4. `SELECT COUNT(*) FROM latch_order_mandate_links` **equal to step 0's**, and
     `SELECT id, ticker, state FROM trades WHERE state IN ('entered','managing','partial_exited')
     ORDER BY id` **byte-identical to step 0's list** -- ids included, because an `ADD COLUMN` must
     not renumber anything and this is the assertion that would notice if it had.
  5. `swing web` loads the dashboard and the trade-entry form renders.
  6. **The first real entry after the migration carries a non-NULL `attempt_id`** -- the only
     end-to-end proof that the token is being written on the production path, and the one step a
     seeded fixture cannot substitute for (the seeded-gate-masks-default-state lesson).
- **Rollback**, if step 3 or 4 disagrees: restore the pre-migration backup; the index is droppable
  in one statement and the column is nullable and inert.

---

## S7. ACCEPTED LIMITATIONS -- each with its reason, challenge explicitly invited

> These are DECISIONS, not oversights. **A finding that re-raises one of these without engaging its
> stated reason is out of scope; a finding that shows a reason is UNSOUND -- that the argument does
> not hold, that the limitation is larger than declared, or that a cheaper alternative was
> mis-rejected -- is IN scope and is what this review is for.** The immediately preceding arc had six
> of its eighteen limitation REASONS disproved by measurement, and each disproof was worth more than
> the claim it replaced; that is the standard these are written to.

1. **THE ARC DOES NOT CLOSE THE WHOLE RESIDUAL -- AND THE TWO REFUSAL BRANCHES ARE NOT THE SAME
   SIZE, WHICH THIS ENTRY PREVIOUSLY BLURRED** (`A4-R6-8`).
   **(a) `resolution == "still_open"` -- GENUINELY INDETERMINATE.** The transaction may still be
   open with the entry row PENDING, and a later commit on that connection could make it durable
   AFTER the caller was told the entry failed. This is the residual proper.
   **(b) `rolled_back` with `cleanup_raised` -- NOT indeterminate at all.** The rollback took
   effect, `in_transaction` re-reads false, and **the row is provably GONE; nothing can commit it
   later.** The read is refused here only because RD's rule (i) is taken LITERALLY, and the refusal
   costs nothing because the answer would have been ABSENT anyway (S2.4). Saying otherwise
   overstates the arc's own surviving exposure, and S2.4 and S9 item 3 already had it right.
   **The "possibly durable later" exposure belongs to (a) ALONE** (`A4-R7-5`: the sentence that
   followed used to say "in both", re-creating the very conflation the two clauses above had just
   corrected -- and re-creating `A4-R6-8` one round after it was closed). In (b) the row is gone and
   nothing can commit it. In both, no read is attempted and the alarm is raised;
   **for (a) that alarm may be wrong about a row that later lands, and for (b) it is simply the
   literal rule refusing a read whose answer was already ABSENT.** In (a), and a later commit on that connection could make the row durable AFTER the caller was
   told the entry failed. *Reason:* that state is genuinely indeterminate -- there is no fact to
   read, because the fact has not been decided yet -- and RD's canon governs: the function may RAISE
   the indeterminate and may never ASSERT durability. **What changed is the SIZE of the residual, not
   its existence:** it now covers only the double-failure branch instead of every lost commit, and
   its direction is unchanged (told-failed over a possibly-durable row -> retry ->
   `ux_trades_one_open_per_ticker` refuses, naming the existing position). **The belt still does NOT
   cover a ticker CLOSED between the two attempts**, and that remains the uncovered direction.
2. **THE SETTLE IS BEST-EFFORT: WHEN THE PROBE CANNOT READ, THE ANSWER IS THE ALARM, EVEN OVER A
   DURABLE ROW.** A probe that times out on its bounded 2 s busy timeout, hits an I/O error, or
   cannot open the file produces `None` and the ORIGINAL exception is re-raised. *Reason:* the whole
   arc exists because an unproven assertion of durability is the expensive direction; a probe that
   escalated its own failure into a claim would be the reverted clause 2 wearing a better costume.
   The cost is a possibly-false FAILURE report -- **and "belt-covered" is CONDITIONAL, which the
   first draft of this entry did not say** (`A4-R4-11`). The belt refuses a retry only while the
   original trade is still OPEN; if the operator closes the position between attempts, a retry
   passes `ux_trades_one_open_per_ticker` and the exposure is a DOUBLE POSITION, exactly as S7.1
   says for the other residual. **The closed-between-attempts exception applies to every branch that
   answers with the alarm, not only to the raising-rollback one.**
3. **NO LONGER A LIMITATION -- WITHDRAWN AFTER MEASUREMENT, and the entry is KEPT so the withdrawal
   is readable.** The first draft declared a behaviour change here: it believed
   `sqlite3.Connection.__exit__` left a failed commit's transaction OPEN, proposed adding a rollback
   to the pre-arc path, and accepted that the escaping exception would change in the
   commit-raises-AND-rollback-raises sub-case. **`A4-R1-2` disproved the premise and MEASURED (3b)
   confirms it: `__exit__` rolls back.** So no rollback is added, no exception identity changes, and
   the routing item this generated is withdrawn from S9. **What remains is a LOCK rather than a
   declaration** -- test (k2) now asserts that the pre-arc path's escaping exception is UNCHANGED,
   which fails an implementation that copies the immediate path's `raise cleanup_error from
   write_error` across. *Kept because a limitation that was withdrawn by measurement is worth as
   much as one that survived: the first draft would have declared, routed and shipped a change that
   was never needed.*
4. **AN ATTEMPT THAT NEVER REACHES THE INSERT LEAVES NO TRACE, AND THE TWO WAYS THAT HAPPENS ARE
   DIFFERENT** (narrowed after `A4-R1-10`, which caught this entry contradicting S2.1). The mint
   happens AFTER the gauntlet, so a refusal by validation, the stop check, the duplicate check, the
   hard cap, the soft warn, the recognition read or the caller-held-transaction guard **mints
   nothing at all**. Between the mint and the INSERT -- the PE-anchor guard, the resolver -- a token
   exists only in Python memory and is never written anywhere, so there is nothing to roll back. Only
   a failure AFTER the INSERT and before the commit leaves a token that was written and is then
   rolled back WITH its row. (`A4-R2-9`: the first draft collapsed those two into one clause and so
   overstated what the ledger ever holds.)
   *Reason, for both:* `attempt_id` is identity for a ROW, not an attempt LOG. Storing refused
   attempts needs a second table and is a different instrument with a different justification.
   Stated so nobody reads the column as an attempt audit -- and stated in two clauses because the
   first draft said the gauntlet refusals mint an unstored token, which its own S2.1 forbids.
5. **A PRE-v38 SCHEMA SILENTLY DROPS THE TOKEN** (contained WARNING, insert proceeds). *Reason:* the
   alternative is to fail a money-bearing entry because an identity nicety is unavailable, which
   S2.1's containment posture forbids outright. The consequence of the drop is EXACTLY today's
   behaviour, because the probe is schema-aware and answers ABSENT. Reachability is tests only:
   production is gated at v38 by `connect()`, and S1.6 measured that no `record_entry` call site runs
   below HEAD.
6. **AN IN-MEMORY (OR OTHERWISE FILE-LESS) CONNECTION CANNOT BE SETTLED.** `_resolve_main_db_path`
   returns `None` and clause 2 is unavailable. *Reason:* a "fresh connection" to `:memory:` is a
   different database, so there is no durable state to read; answering from the writer's own handle
   is the exact defect this arc closes. MEASURED: no production or test path calls `record_entry`
   with an in-memory database (S1.6).
7. **UNIQUENESS ACROSS ATTEMPTS IS PROBABILISTIC, NOT STRUCTURAL -- RULED ACCEPTABLE BY RD
   2026-09-06, AND WIDENED HERE ON HIS THREE RIDERS.** The reachable-in-principle sequence: attempt A
   mints `X`, its commit fails without landing, A rolls back so `X` exists nowhere, a later attempt
   independently mints `X` and commits for the same ticker, and A's probe confirms that row.

   *Why the design stands -- RD's reason, not the plan's:* **"never reusable" means the mechanism
   contains NO PATH THAT REISSUES a token.** The rowid failed because **the ENGINE hands a
   rolled-back id to the next insert** -- an active, designed-in reuse mechanism. `uuid4` has no such
   path, so a repetition is an RNG FAILURE rather than a behaviour of the mechanism, and
   **collision-resistance is already this system's admissibility standard** (the H1 amendment pinned
   by sha256, broker snapshots by digest).

   *The arithmetic, and what it does NOT price* (`A4-R4-9`): independent RNG collision over `n`
   lifetime entries is about `n^2 / 2^123` -- **~1e-27 at `n = 10^5`** -- and a real occurrence would
   ALSO have to carry the same ticker to pass corroboration. **IT PRICES INDEPENDENT DRAWS ONLY.**
   **THE CORRELATED FAILURE MODE IT DOES NOT PRICE, NAMED (RD rider 1):** a DEGRADED OR REPEATING
   RNG -- two draws sharing generator state. Under it the "collision" is not astronomical at all; it
   is systematic, and the arithmetic above is silent about it. **Platform-scoped fact, MEASURED by
   reading the source rather than recalled:** CPython 3.14's `uuid4` is
   `int.from_bytes(os.urandom(16))` **per call** -- there is no process-local PRNG state at all, so
   the classic correlated cause, fork without reseed, cannot correlate these draws.
   **AND THAT CUTS BOTH WAYS, which was round 6's finding** (`A4-R6-11`): RD's rider named **fork**
   as a re-open trigger for the banked allocator, and since `uuid4` holds no forkable state, **a
   POSIX port that merely acquires `fork` would fire the trigger with no hazard present** -- and
   activate a materially more expensive design on the money path. **The surviving triggers are a
   GENERATOR change away from `os.urandom`, or a measured condition that DUPLICATES THE OS ENTROPY
   STREAM** (VM snapshot-resume / image cloning, where that premise is established). The wording is
   RD's, so the correction is ROUTED rather than taken silently -- **the second of his two rider
   clauses that failed verification** (S9 RD item 2).

   **THE DETECTION STORY, VERIFIED BY EXECUTION RATHER THAN ASSERTED -- AND ONE HALF OF RD's RIDER
   DID NOT VERIFY.** He attached it as load-bearing and instructed stop-and-route on failure, so both
   halves were run against a model carrying the real CHECK, both real indexes and the real mapper:

   - **A duplicate of a COMMITTED token is REFUSED LOUDLY, never silently confirmed. VERIFIED** --
     the second INSERT raises `UNIQUE constraint failed: trades.attempt_id`, so the entry is refused
     before any confirming read exists. **BUT THE "LOUDLY" IS LOAD-BEARING ON S2.5, AND THAT
     DEPENDENCY IS NAMED HERE BECAUSE IT ENTERED THE PLAN FOR AN UNRELATED REASON:** the SHIPPED
     mapper (`"UNIQUE" in msg and "trades" in msg`) matches that message and would report *"Already
     an open position in BBB (race-detected)"* -- loud, and WRONG about a position that does not
     exist. It is only TRUTHFULLY loud because S2.5 narrows the match to `trades.ticker`. **Measured
     both ways.**
   - **The duplicate of a ROLLED-BACK token DOES have a false-confirm mechanism -- so the rider's
     REASON does not hold, though its PRACTICAL WEIGHT is unchanged. ROUTED BACK TO RD (S9 RD item
     2).** His stated reason was *"a rolled-back token leaves no row to confirm."* That is true at
     the instant of rollback and **does not survive to probe time**. **REPRODUCED:** A rolls back
     (zero rows carry `X`), a second connection mints the same `X` for the SAME ticker and COMMITS,
     A's probe then finds that row, **ticker corroboration PASSES**, and A would return SUCCESS
     naming a trade it did not write.
     **AND THE SCOPE OF THAT COUNTEREXAMPLE IS STATED HERE RATHER THAN LEFT TO READ STRONGER THAN IT
     IS** (the orchestrator's qualification when he routed it, carried into the plan because a plan
     should not bank an overstatement in its own favour): **the scenario lives ENTIRELY INSIDE THE
     COLLISION BRANCH.** It is conditioned on the very duplicate the rider was about, so it does not
     add a new exposure or widen the residual -- **the practical weight stays bounded by the
     collision probability above (~1e-27 at `n = 10^5`, and the same ticker required).** What it
     refutes is the rider's REASON, not its conclusion. *"Reproduced false" is accurate about the
     mechanism and would read as stronger than the scenario warrants if left unqualified.*
     **The RULING is unaffected** -- it rests on the no-reissue-path reading, which verifies -- and
     the honest statement replaces the rider's: *in the undetectable case the false confirm is
     exactly the residual this entry declares, bounded by the same arithmetic, and pinned by
     execution at (RD-b2) rather than argued away.*

   *(S-d), which satisfies constraint 2 STRUCTURALLY, is NOT declined on merit and NOT deleted:* it
   is BANKED IN FULL at S2.0.1 with the re-open trigger above. Refusing it today is a D46 call --
   more machinery, a second commit surface and a separate connection on the money path, against a
   failure with no mechanism and no observed instance. **PINNED BY EXECUTION at test (RD-b2).**
   *(Three earlier versions of this entry declined the allocator as "a stamp"; all three were
   disproved -- `A4-R2-1`, `A4-R3-1`, `A4-R4-9` -- and a fourth live copy survived into this plan's
   own uncounted self-sweep. Recorded because a reason that lost four times is the most instructive
   line in S7.)*
   *The separate third-party question is folded in here:* the token is minted inside `record_entry`,
   is not on `EntryRequest`, and is never transmitted, so a deliberate reuse needs write access to
   the database plus knowledge of an in-flight token -- outside any threat model this
   single-operator system has.
8. **THE UNIQUE INDEX TURNS A COLLISION WITH A *LIVE* TOKEN INTO A HARD ENTRY REFUSAL -- AND IT
   CATCHES NOTHING ELSE.** *Reason, restated from the corrected model after `A4-R4-9` found this
   entry still carrying the disproved one:* the index constrains **simultaneously live rows** only.
   It is NOT "constraint 2's enforcement": a token that was rolled back leaves no trace, so a
   collision with it is admitted. **That also means a SYSTEMATIC mint-reuse BUG is caught only when
   the first use COMMITTED** -- if the first use rolled back, the index is silent and the collision
   is deterministic rather than astronomically unlikely, which is a different and much larger
   exposure than the RNG arithmetic in S7.7 prices. The refusal it does produce is unreachable in
   practice (`uuid4`, minted per call, not caller-supplied, validated at S2.1) and, after Task 1's
   narrowing, surfaces as the `IntegrityError` it is rather than as a false "already an open
   position". **The systematic-reuse case is covered by TESTS, not by construction, and the
   distinction is the point** (`A4-R6-5`): **(w)** asserts one mint per attempt and consistent
   threading, but it patches `_mint_attempt_token` itself, so **a constant mint passes it**;
   **(w2)** is the row that actually bites, patching `uuid.uuid4` one level below and requiring two
   attempts to yield two distinct tokens. *"Impossible by construction"* was this entry's own
   overclaim for two rounds -- that phrase belongs to the banked allocator (S2.0.1) and to nothing
   in the shipped shape.
9. **NOTHING PERSISTS THE FACT THAT A SETTLE HAPPENED.** The operator sees the warning and the ERROR
   log records it; no table records "this entry was confirmed by identity rather than by its own
   commit". *Reason:* that is a second schema object with a different purpose, and this arc's schema
   footprint is deliberately **one column, one index and one immutability trigger -- no TABLE**. If
   CHARC wants the audit surface, it is a
   separate arc with its own migration.
10. **`EntryResult` DISTINGUISHES THE TWO WARNING KINDS ONLY BY TEXT.** A caller wanting to branch on
    "settled by identity" versus "a post-commit step failed" must read prose. *Reason:* the envelope
    forbids caller changes, and adding a typed field with no reader would be a contract with no
    consumer -- the exact gap 22-A3 was commissioned to close. Flagged as a follow-on at S8 rather
    than half-built here.
11. **THE STATIC INSERT CLOSURE WALK IS A DECLARED HEURISTIC.** It reads string constants via `ast`
    plus a raw-text scan for the f-string family; a statement assembled from fragments across
    modules, or executed via `executescript` from a data file, is invisible to it. *Reason:* the
    standing declare-versus-widen ruling. **THE BACKSTOPS THIS ENTRY USED TO CLAIM DO NOT COVER THE
    DECLARED HOLE, and the reason was UNSOUND rather than merely optimistic** (`A4-R7-7`): a NEW
    fragmented writer inserting into the EXISTING schema without `attempt_id` **changes no column, so
    (r4) stays green; does not touch `record_entry`, so (e) stays green; and evades the static walk
    by definition.** All three miss it. **What they actually cover, stated instead of overclaimed:**
    (r4) covers SCHEMA/MODEL DRIFT and (e) covers THE CANONICAL ENTRY PATH, and **neither closes the
    invisible-writer class.** Closing it needs a writer registry or a parser over every executable
    SQL source -- a different arc. **The honest declaration is that this hole has ONE heuristic guard
    and NO independent backstop**, which is a smaller claim than the one it replaces and is the one
    the evidence supports.
12. **THE TERMINAL-RETURN AND CALL-to-STORE WINDOWS SURVIVE, INHERITED FROM 22-A3 (its S7.4 and
    S7.17).** An asynchronous exception delivered at the frame's exit handoff, or between
    `record_entry`'s return and the caller's `STORE_FAST`, is outside any guard this arc adds.
    *Reason:* unchanged -- no caller-only restructuring reaches an interval containing no statements,
    and the direction is the belt-covered one -- **CONDITIONALLY belt-covered, on exactly S7.2's
    terms and for the same reason** (`A4-R6-10`): the belt refuses a retry only while the first trade
    remains OPEN, so if the position is closed between attempts the double-position direction
    survives here too. The plan states that qualification in all three places rather than letting one
    of them read stronger than the others. **What this arc DOES close, and it is worth naming
    because it is the same class:** the window between `conn.commit()` returning and
    `outcome.committed = True`. An exception delivered there used to look exactly like a failed
    commit; now it is settled by the probe and returns SUCCESS.
13. **THE TOKEN IS NOT SURFACED ANYWHERE AND IS NOT PART OF ANY EXPORT, BRIEFING OR RECONCILIATION.**
    *Reason:* one consumer, one purpose. A second consumer would need its own justification, and a
    column that appears in an operator-facing surface acquires a meaning it was not designed to carry.
14. **THE PRIMITIVE IS ENTRY-ONLY.** `swing/trades/exit.py`'s fill path and
    `update_stop_with_event` have the same lost-commit shape and get no attempt identity here.
    *Reason:* the envelope is the entry path, and the money-bearing double-write hazard the whole
    contract was written for is the DOUBLE ENTRY. Flagged at S8 with its own reasoning so it is
    owned rather than merely disclosed.

---

## S8. FLAGGED, NOT FIXED -- and where each goes

Per the recipe's locks: a defect or gap outside scope is FLAGGED in the return report, never fixed
inline and never silently absorbed. Each carries a proposed disposition; the orchestrator rules.

1. **CLAUDE.md's rolled-back-rowid gotcha explains the mechanism via `sqlite_sequence` and
   `AUTOINCREMENT`, and `trades` has NEITHER.** The gotcha is TRUE and it is STRONGER than it reads:
   on a bare `INTEGER PRIMARY KEY` the reuse is the default, not an `AUTOINCREMENT` subtlety.
   Proposed: **BANKED** for the orchestrator's next CLAUDE.md pass -- one clause, not a rewrite.
   (Owner: orchestrator. Trigger: the next gotcha edit.)
2. **THE EXIT AND STOP-ADJUST PATHS HAVE THE SAME LOST-COMMIT SHAPE AND NO IDENTITY.**
   `swing/trades/exit.py` and `swing/data/repos/trades.py:update_stop_with_event` both write inside a
   caller-owned transaction with no per-attempt token. The consequence is milder than a double entry
   (a duplicated exit fill is detectable against the position; a duplicated stop-adjust is
   idempotent-ish), which is why it is not folded in. Proposed: **BANKED**, owner CHARC, trigger =
   the next time a duplicate-write incident touches either path.
3. **`EntryResult` HAS NO TYPED DISCRIMINATOR FOR THE TWO WARNING KINDS** (S7.10). Proposed:
   **BANKED** with a named shape (an enum-tagged warning tuple) and an explicit precondition: it
   needs a caller that wants to branch, and today neither does.
4. **THE FOUR PRE-COMMIT LOGGING CALLS IN `_record_entry_inner` REMAIN UNCONTAINED**
   (`entry.py:824`, `:892`, `:903`, `:918`) -- 22-A3's S7.11, unchanged and unchallenged: they run
   inside the transaction, so a raising sink aborts the write and reporting a failure is honest.
   Proposed: **DECLINED** as a change, cited to 22-A3's declaration; recorded here only so the reader
   knows it was re-examined rather than forgotten.
5. **NO OPERATOR SURFACE SHOWS WHETHER AN ENTRY WAS CONFIRMED BY IDENTITY.** The warning is
   transient; the log is durable but is not a UI. Proposed: **BANKED** together with S8.3, since a
   surface without a typed discriminator would have to parse prose.
6. **NO LONGER BANKED -- CHARC RULED IT SHIPS IN THIS ARC, and the entry is KEPT so the reversal is
   readable.** This plan proposed BANKING the corrector's typed refusal because
   `swing/trades/reconciliation_auto_correct.py` sat outside the envelope. **CHARC refused the
   banking and widened the envelope instead:** *"I cannot rule the class binding one week and bank
   its next instance because the plan's envelope was drawn one module short."* The tier-2 path
   ADMITS `field_name="attempt_id"` and the trigger then ABORTs -- **authorize-then-abort**, the
   class he ruled on 2026-09-01 after five instances in 22-A. **It is now Task 1b**, bounded to a
   refusal entry, a message constant and the corrector-path assertion. *What this entry records for
   the future is the SHAPE OF THE MISTAKE:* a plan can convert a ruled-binding class into a banked
   follow-on purely by where it drew its own envelope, and neither the plan nor its five review
   rounds flagged that as a scoping decision -- only the director whose class it was.
7. **VERSION-GATE BACKUPS LAND IN THE DATABASE'S OWN DIRECTORY AND ARE NEVER NAMED TO THE OPERATOR**
   (`A4-R1-7`). `swing db-migrate` prints only its own general snapshot in `backups_dir`, while every
   arc gate's verified pre-image defaults to `src_path.parent` because `ensure_schema` is called
   with no `backup_dir`. The artifacts are therefore invisible to any sweep, retention policy or
   backup audit that looks at `backups_dir`, and the operator cannot cite the one whose integrity
   was actually CHECKED. This arc corrects its own WITNESS INSTRUCTIONS (S6) and does not touch the
   CLI. Proposed: **BANKED**, owner CHARC, trigger = the next `swing/cli.py`-scoped arc or the next
   backup-retention question; the fix is one `backup_dir=` argument and one `echo`, and it affects
   every migration gate since 0027, not just this one.

---

## S9. ROUTING -- **two director tripwires, and what each is asked**

### To CHARC -- the §3 schema tripwire -- **RULED 2026-09-06: FIVE ITEMS RATIFIED, ONE CONDITION**

**Why it fired:** a new migration, a new column on the money-bearing `trades` table, a new UNIQUE
index, an immutability trigger and a schema-version bump. **All five items below are RATIFIED as
shaped.** The one CONDITION he attached is item 7, and it WIDENS THIS ARC'S ENVELOPE.

1. **The migration's shape.** `0038` is ADDITIVE: one `ALTER TABLE ... ADD COLUMN` with a
   column-scoped CHECK, one partial UNIQUE index, **one `BEFORE UPDATE OF attempt_id` immutability
   trigger**, one version bump, inside an explicit `BEGIN;/COMMIT;`. **The trigger is the part to
   look hardest at:** it exists because `swing/trades/reconciliation_auto_correct.py` allowlists
   `trades` columns BY EXCLUSION, so a new column is operator-writable through the tier-2 path from
   the moment it exists, and a re-writable token is not identity (S2.0, `A4-R4-1`). It is
   unconditional, carries no `WHEN` (so the NULL-`WHEN` fail-open gotcha cannot apply), and is
   retired by one statement, **and the reversibility header names BOTH the `DROP INDEX` and the
   `DROP TRIGGER`** (`A4-R6-13`: item 1 previously said only the index, while Task 1 correctly
   required both). **No rebuild**, so none of the 0035-class rebuild hazards (id renumbering, index
   loss, FK cascade) are in play, and the reversibility header names **both the `DROP INDEX` and the
   `DROP TRIGGER`** (`A4-R7-11`: this sentence still said "the single `DROP INDEX`" two paragraphs
   after item 1 correctly required both) that
   retires it.
2. **THE DIVERGENCE FROM YOUR STATED SHAPE, put first because it is the thing to rule on.** Your
   shape named four mirrors: the dataclass field, the repo INSERT column list, the `_row_to_trade`
   reader, and a static closure check. **This plan takes the INSERT column list and the closure check
   and DECLINES the dataclass field and the reader**, on the ground in S2.0: the reader change means
   a fifth SELECT-projection era and a new positional index in a 56-entry map, touching every
   `trades` reader for a token no reader wants, while the alternative (field without projection) is a
   model that lies. The measured precedent is `risk_policy_id_at_lock`. **The substitute offered is
   mechanical, not rhetorical:** a DRIFT COMPARATOR asserting `trades` columns minus `Trade` fields
   equals exactly `{risk_policy_id_at_lock, attempt_id}`, so the omission is an enumerated reasoned
   exclusion that fails the day a third column joins it. **If you want the full four mirrors, say so
   and the plan takes them** -- the cost is bounded and stated, and this is your call, not the
   author's.
3. **A ROUTING ITEM IS WITHDRAWN, AND THE WITHDRAWAL IS REPORTED RATHER THAN SILENTLY DROPPED.**
   The first draft of this plan asked you to confirm a behaviour change on the pre-arc transaction
   path. **There is none.** Round 1 disproved the premise (`__exit__` already rolls back a failed
   commit -- MEASURED (3b)), so the deferred path is now OBSERVED and not re-plumbed, and test (k2)
   LOCKS its exception identity instead of declaring a change to it. Nothing to rule on; recorded
   because a routing request that quietly disappears is indistinguishable from one that was answered.
4. **The backup gate and its expected-tables set**, derived from 0037's three new tables read out of
   the migration file. **And one thing the gate does NOT do, flagged rather than fixed:** its
   verified pre-image lands in the DATABASE's directory, not `backups_dir`, and is never named to
   the operator -- true of every gate since 0027, banked at **S8.7** (renumbered when the typed
   refusal stopped being banked and became Task 1b -- `A4-R6-13`), out of this envelope.
**RATIFIED, all five. What follows is the record of what was ruled, kept because an executor needs
to know which parts are settled and by whom.**

5. **THE 22-A LOCK-A AMENDMENT (Task 0b) -- RATIFIED in the stated shape**, with `b`'s non-NULL
   token pinning mint-regardless-of-`cfg`. An amendment to a MERGED arc's lock.
   `test_the_lock_a...` asserts the complete `trades` column set and full row equality against a
   golden captured at the pre-arc commit; `attempt_id` breaks both, and the test's own docstring says
   the failure was left loud on purpose so that a later column could not be silently tolerated. The
   plan's amendment keeps byte identity for every pre-existing column, NAMES the addition in the
   column-set assertion, and adds a third assertion on the new column -- strengthening rather than
   softening. **Confirm the shape, or rule a different one.**
6. **The version bump touches an AUTHORIZATION GATE, not just assertions -- and the gate is
   OPENED.** CHARC opened `versions[-1] <= 37` -> `<= 38` **for 0038 ONLY, in the migration's own
   commit and nowhere else.** The backup gate and its expected-tables set are RATIFIED.
   `tests/data/test_no_schema_change_v3.py:41` asserts `versions[-1] <= 37` and its own comment says
   raising it is the section-3 pass being exercised. Task 1 raises it to 38 in the migration's own
   commit and nowhere else. **This is the mechanical form of your gate, and this plan is asking you
   to open it.**

7. **THE CONDITION HE ATTACHED, and it is the one item that WIDENED THIS ARC: the corrector's typed
   refusal SHIPS (Task 1b).** The plan proposed banking it because
   `swing/trades/reconciliation_auto_correct.py` sat outside the envelope. **He refused the
   banking:** *"I cannot rule the class binding one week and bank its next instance because the
   plan's envelope was drawn one module short."* The tier-2 path ADMITS `field_name="attempt_id"`
   and the trigger then ABORTs -- **authorize-then-abort**, his own class, ruled 2026-09-01 after
   five instances in 22-A. Bounded to one refusal entry, one message constant and one assertion on
   the TYPED error; **the trigger remains the guard of record and the refusal is its legible face.**
8. **The two JURISDICTION NOTES are written into the migration header**, not left to a reviewer:
   (A) a `BEFORE UPDATE` trigger cannot see `INSERT OR REPLACE`, and the REPLACE family was grepped
   EMPTY against `trades` -- re-run here, **zero executable REPLACE statements anywhere in `swing/`**
   (45 textual hits across 22 files, every one prose in a migration header, a trigger message or a
   docstring) -- so a future REPLACE writer is a **declared breach rather than an unknown**;
   (B) **22-B Demand A rebuilds `trades`**, and a rebuild that does not re-create the index AND the
   trigger silently drops the guard -- banked by CHARC as a 22-B precondition and recorded in the
   header so the next rebuild's author meets it in the file.

### To RD -- the admissibility gate -- **RULED 2026-09-06, WITH TWO RIDER CLAUSES ROUTED BACK**

**Why it fired:** the token is admissibility machinery -- the thing that makes a durability read
EVIDENCE -- and RD's three constraints are its specification. **Constraint 2 is RULED: `uuid4`
satisfies it, because "never reusable" means the mechanism contains no path that REISSUES a token,
and `uuid4` has none.** Items 1 and 3-6 below are closed by that ruling. **Item 2 is OPEN and carries
BOTH rider clauses that failed verification** -- the S7.7 detection reason and the `fork` re-open
trigger. They are the only things in this plan still waiting on him, and Task 0 carries one unchecked
box for each.

1. **S1 is the answer to your ruling's own precondition question**, and it says: the CO-DURABLE
   MECHANISM exists and its token does not; UNIQUE PER ATTEMPT does not exist at all; the
   DURABLE-VISIBILITY capability exists and is wired to nothing. Each is re-derived against the code
   with the method that produced it, and two of your constraints' supporting facts were REPRODUCED
   on this tree rather than cited (rowid reuse; a fresh connection's blindness to uncommitted rows).
2. **ROUTED BACK -- YOUR S7.7 DETECTION RIDER DOES NOT FULLY VERIFY AT THE CODE, AND YOU INSTRUCTED
   STOP-AND-ROUTE IF IT DID NOT.** Both halves were run against a model carrying the real CHECK, both
   real indexes and the real mapper:
   - **"A committed-duplicate token is REFUSED LOUDLY by the UNIQUE index" -- VERIFIED**, with a
     dependency you should see: the refusal message is
     `UNIQUE constraint failed: trades.attempt_id`, which **the SHIPPED mapper turns into "Already an
     open position in BBB (race-detected)"** -- loud, and false about a position that does not exist.
     It is TRUTHFULLY loud only because S2.5 narrows that match to `trades.ticker`, a fix that
     entered this plan in round 1 for an unrelated reason. **Your rider's first half is load-bearing
     on it.**
   - **"The undetectable case has no false-confirm mechanism, because a rolled-back token leaves no
     row to confirm" -- THE REASON DOES NOT HOLD; REPRODUCED THE OPPOSITE.** The premise is true at
     the instant of rollback and does not survive to probe time: A rolls back (zero rows carry `X`),
     a second connection mints the same `X` for the SAME ticker and COMMITS, A's probe finds that
     row, **ticker corroboration PASSES**, and A returns SUCCESS naming a trade it did not write.
     **SCOPE, stated so this does not read stronger than it is:** the scenario lives ENTIRELY INSIDE
     THE COLLISION BRANCH -- it is conditioned on the very duplicate the rider was about -- so it
     **refutes the REASON without changing the practical weight**, which stays bounded by the
     collision probability. No new exposure; no wider residual.
   **AND A SECOND RIDER CLAUSE FAILED THE SAME WAY (`A4-R6-11`): "fork" as a re-open trigger for the
   banked allocator.** MEASURED by reading CPython 3.14's source: `uuid4` is
   `int.from_bytes(os.urandom(16))` **per call**, with no process-local PRNG state -- so a POSIX port
   that acquires `fork` creates none of the correlated state the trigger is meant to detect, and the
   trigger would fire on an ordinary platform change while activating a materially more expensive
   design on the money path. **The plan struck bare `fork` and kept the triggers that do verify:** a
   generator change away from `os.urandom`, or a measured condition duplicating the OS entropy
   stream.
   **YOUR RULING IS UNAFFECTED BY EITHER** -- it rests on the no-reissue-path reading, which
   verifies. What failed is two of the riders' stated REASONS, and the plan will not write an
   unverified reason into a declared limitation or a re-open trigger. **S7.7 and S2.0.1 now state the
   verified versions.** Confirm both replacements, or rule them differently.
3. **Rule (i) -- "a failed rollback VOIDS the read" -- is implemented LITERALLY as "no read is
   attempted whenever the rollback CALL raised," and S2.4 argues its cost is ZERO** by enumerating
   the two refusal branches (`still_open`; `rolled_back` with `cleanup_raised`) and showing the row
   is provably ABSENT in each. **The first version of that argument was WRONG** (`A4-R2-7`): it
   claimed the refusal branch implies `in_transaction == True`, and this tree's own
   `_RollbackAfterEffect` fixture is the counterexample -- the rollback takes effect and then raises.
   The state model now separates the TRANSACTION's state from the CALL's failure. **The rebuilt
   argument is offered for challenge**: if it is wrong, the rule is still honoured, but the plan's
   claim about what it costs would be overstated.
4. **The ticker corroboration is ALARM-NEVER-ASSERT applied inside the probe**: a mismatch raises the
   alarm, a match asserts nothing the token had not already established. Confirm that reading, or
   rule it superfluous and it comes out.
5. **The surviving indeterminate branch (S7.1)** is declared with its direction and its belt, exactly
   as the old residual was. This arc SHRINKS the residual rather than eliminating it, and says so in
   the section that leads the limitations rather than the one that closes it.
6. **CONSTRAINT 2 -- CLOSED BY YOUR RULING OF 2026-09-06, and the entry is KEPT so the closure is
   readable.** The plan RECOMMENDED (S-b) and refused to SELECT it, on the ground that proportion is
   not a basis for a plan to narrow a binding constraint; it specified (S-d) in full so the ruling
   would cost no further planning pass. **You ruled `uuid4` satisfies constraint 2, and the reason
   is what binds future appeals:** *"never reusable" = the mechanism contains **no path that
   REISSUES** a token; the rowid failed because the ENGINE hands a rolled-back id to the next insert.
   A `uuid4` repetition is an RNG failure, not a behaviour of the mechanism* -- and
   collision-resistance is already this system's admissibility standard (sha256-pinned amendment
   text, digest-pinned broker snapshots). **Your three riders are landed:** S7.7 widened with the
   correlated-RNG mode it does NOT price and the platform-scoped `os.urandom` / no-fork-on-Windows
   note (rider 1, with its detection half ROUTED BACK at item 2); RD-a / RD-b unchanged as the
   deciding tests plus (RD-b2) in its (S-b) polarity (rider 2); **(S-d) BANKED IN FULL at S2.0.1
   with a named re-open trigger, not deleted** (rider 3).
7. **Your both-modes attachment, honoured in the form this arc admits.** There is no arm flag here,
   so the analogue is stated instead: **every negative row in S3 asserts counterfactual fields** --
   row counts, the identity of the escaping exception, a sentinel's call count -- never the bare
   "it raised" that would pass an implementation swallowing everything.

---

## S10. WHAT AN EXECUTOR MUST READ BEFORE TOUCHING ANYTHING

1. This plan's **S1** -- it is the only place the three constraints are tied to code, and every
   design decision downstream cites it.
2. `swing/trades/entry.py:628-1165` -- `record_entry`, `_CommitOutcome`, the DECLARED-RESIDUAL block,
   and both `_entry_transaction` paths. The block at `:973-1030` explains why the shipped code has
   the shape it has; **Task 5** rewrites it and cannot do so honestly without having read it.
3. `docs/22-a-merge-request.md` **S4.4** -- the ruling, and the two reproductions this arc's tests
   re-derive.
4. `docs/superpowers/plans/2026-09-02-phase22-arc-a3-record-entry-caller-half.md` **S7** -- the
   limitation-declaration standard, and the containment idiom (`log_contained`,
   `log_contained_note`, `safe_text`, `ascii_safe`) this arc reuses rather than re-invents.
5. `CLAUDE.md` §Gotchas -- #9 (executescript / explicit BEGIN), #11 and its 2026-08 amendments (the
   mirror family is bigger than the canonical triple; the comparator is mandatory; grep each member
   separately), the migration backup-gate strict-equality clause, the rolled-back-rowid entry and the
   writer-quoting-itself entry.
6. `swing/data/migrations/0037_latch_order_mandate_links.sql`'s header -- the
   one-migration-one-version-bump rule and the reversibility-header format this arc copies.

---

## S11. REVIEW STATUS AND BASELINE

**Baseline measured on `edfea928` at plan time, before any change:**
`python -m pytest -m "not slow" -q` -> **12155 passed, 13 skipped** in 505.66 s. The executing arc's
Task 6 and Task 7 runs are compared against THAT number, not against a remembered one.

**Adversarial review:** see the round ledger below; full transcripts and per-finding adjudications in
`.copowers-findings.md` at the worktree root, raw transcripts `.codex-review-r<N>.txt`.

| round | tier / model / effort | C / MAJ / MIN | new | reopened | reverted | verdict |
|---|---|---|---|---|---|---|
| 1 | `strong` / `gpt-5.6-sol` / `high` | 1 / 6 / 3 | 10 | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| 2 | `strong` / `gpt-5.6-sol` / `high` | 0 / 7 / 2 | 9 | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| 3 | `strong` / `gpt-5.6-sol` / `high` | 1 / 8 / 3 | 12 | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| 4 | `strong` / `gpt-5.6-sol` / `high` | 1 / 10 / 1 | 12 | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| SS | *(uncounted self-sweep, no Codex)* | 0 / 0 / 9 | 9 | - | - | *no verdict; no effect on convergence* |
| 5 | `strong` / `gpt-5.6-sol` / `high` | 1 / 7 / 4 | 12 | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| **6** | `strong` / `gpt-5.6-sol` / `high` | 0 / 11 / 2 | 13 (**6 new ground, 7 residual**) | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |

**TOKEN SPEND, six counted rounds:** 437,776 + 230,647 + 246,268 + 320,775 + 317,038 + 307,420 =
**1,859,924**. (The disqualified round-1 attempt produced no transcript and therefore no footer.)

**GATE STATE: the round-5 gate was honoured and the orchestrator ruled CONTINUE with a bounded stop
rule -- *"run round 6 on the final shape; if it returns residuals of these amendments rather than new
ground, STOP and disposition -- do not open round 7."*** Round 6 returned **a MIX: 6 NEW GROUND and 7
RESIDUAL**, which is not the stop rule's stated case, and **round 7 was NOT opened** -- opening one
was not authorized and the honest report of a mixed result belongs to the gate-holder, not to the
author's judgment. **All 13 are dispositioned; 11 are FIXED and 2 are ROUTED** (both RD rider
clauses). The loop is therefore **NOT CONVERGED and is stopped by instruction**, with the finding
composition -- 0 CRITICAL for the first time, and the residual share rising to 7 of 13 -- as the
evidence for whatever the gate-holder decides next.

**Round 6's new ground was concentrated in the AMENDMENTS, which is what the round was for:** the
`typeof` gap that let a 36-byte BLOB share the index with its text twin, the typed refusal that
would have reached the operator as a traceback, the corrector's key-order preflight, and the mint
contract that no test actually pinned.

All five mechanical assertions passed every counted round (model, effort `high`, anchored
`^ERROR` = 0, anchored `^tokens used` footer present, exactly one DISTINCT anchored verdict token
with the other at zero). One attempt-1 invocation of round 1 was DISQUALIFIED before it counted --
MSYS path-mangling produced an empty transcript while the harness reported exit 0; the two-signal
rule caught it. Per-round assertions and per-finding adjudications: `.copowers-findings.md`.
