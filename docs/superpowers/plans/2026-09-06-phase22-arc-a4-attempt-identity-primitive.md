# 22-A4 -- The attempt-identity primitive, and clause 2's return on top of it (implementation plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** give `record_entry` a way to answer *"did MY attempt land?"* from the DURABLE ledger, and
then let clause 2 return on top of it -- a commit whose own return was lost is settled by a READ
that both **sees only committed state** and **identifies our attempt**, rather than by an alarm that
is honest but wrong about a durable row.

**Architecture:** one additive migration and four edits. (1) `trades.attempt_id TEXT` (nullable,
`CHECK typeof = 'text' AND length = 36`) plus a UNIQUE partial index, migration **0038**,
`EXPECTED_SCHEMA_VERSION`
37 -> 38, one backup gate. (2) `insert_trade_with_event` gains an explicit `attempt_id` keyword and a
FOURTH schema-era INSERT branch that carries the column, so the token is written **in the same
INSERT as the row it identifies** -- co-durability by construction, not by argument. (3)
`record_entry` mints one `uuid4` per attempt at the point the attempt begins (after the entire
pre-existing gauntlet, so LOCK clause (c)'s ordering is untouched) and captures the connection's
own database path for the confirming read. (4) `_entry_transaction` records THREE observations
instead of one (two NEW fields beside `committed`) -- did the commit return, is the transaction
RESOLVED, and did a rollback CALL raise -- on
BOTH paths, **observing rather than re-plumbing** (Python's own context manager already rolls back a
failed commit, MEASURED (3b), so the pre-arc path's behaviour is unchanged; where that internal
rollback ITSELF fails, CPython raises the rollback's exception with the commit's chained as
`__context__` -- SOURCE (S1) -- so `record_entry` OBSERVES the failure at its own except site,
one frame out, instead of re-plumbing the path, and RD's rule (i) is literal on both paths.
**The body-completion observation is NOT a fourth field:** `record_entry`'s shipped
`result is not None` guard already is one, and adding a mirror of it would have put a statement
inside the byte-locked `with conn:` suite -- RD's PIN 1 on `A4-R10-1`, 2026-09-07); `record_entry`'s
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

> ## REVIEW STATUS: **ELEVEN ADVERSARIAL ROUNDS, THEN A SETTLING SWEEP, THEN THE FIX LEG. ALL FOURTEEN OF ROUND 11's FINDINGS ARE NOW CLOSED -- THIRTEEN FIXED IN THE ARTIFACT, THE FOURTEENTH SETTLED BY A NETWORK FETCH. NOTHING FROM ROUND 11 IS OPEN. THE PLAN AWAITS A GATE WITH A DISPOSITION -- IT IS NOT SELF-AUTHORIZED.**
>
> **ROUND 11 RETURNED `NEW_CRITICAL_MAJOR_FOUND`: 14 findings (1 CRITICAL, 11 MAJOR, 2 MINOR;
> 8 NEW GROUND, 6 RESIDUAL), returned UNFIXED by instruction** -- the sweep cell was told to run ONE
> confirming round and stop whatever it returned. **All five mechanical assertions passed and there
> was no dead attempt.**
>
> **THE 2026-09-07 FIX LEG THEN DISPOSITIONED EVERY ONE OF THEM IN WRITING: 13 FIXED, 1 ROUTED AND
> THEN SETTLED THE SAME DAY, NONE BANKED, NO CODEX ROUND RUN.** The operator authorized the fix leg and then a gate with a
> disposition; **a twelfth counted round requires his written authorization and does not exist.**
> The leg ran in a fresh cell because the sweep cell measured 446,282 against the 400K cap. The
> disposition table, the instrument results and what the instruments still cannot see are in **S11**.
>
> **THE CRITICAL, `A4-R11-1`, IS FIXED.** `escaping.__context__` was an ordinary attribute lookup,
> and a `sqlite3.Error` subclass defining `__context__` as a property read `None` while the base slot
> held the commit exception -- a FALSE NEGATIVE that re-admitted the probe and rebuilt the `A4-R9-3`
> window. The read now goes through `_CONTEXT_SLOT`
> (`BaseException.__dict__["__context__"]`, the same source as this module's own `_EVIDENCE_SLOTS`),
> contained in the alarm direction, discriminated by (k7a)-(k7b) in Task 3. **The plan's claim that
> false negatives were "structurally impossible within its scope" was FALSE and is STRUCK.**
>
> **`A4-R11-2` WAS RULED BY RD AND IS ADOPTED WITH ALL THREE CONDITIONS:** capture
> `sys.exc_info()[1]` immediately before the transaction context manager and exclude that object by
> `is`-identity; **(RD-a4) rebuilt as a FOUR-ROW MATRIX** over {`inside_except` x `chained`}, every
> cell computed under BOTH predicates; and the `A4-R11-1` containment covering the context read.
> *(A measured premise correction rides with it: the ruling was relayed naming `sys.exception()`,
> which is Python 3.12+, and `pyproject.toml:9` declares `>=3.11`.)*
>
> **AND THE LAST OPEN ITEM IS CLOSED: `A4-R11-9` IS SETTLED, NOT ROUTED** (S8 item 8). The
> orchestrator made the network fetch this cell could not, using the method this plan wrote down:
> `https://raw.githubusercontent.com/python/cpython/v3.14.2/Modules/_sqlite/connection.c` ->
> **80,695 bytes, sha256 `8cc0d9df05860c0b3fe6929ff392f8f85c9e1a5ef89c0cba31ab09ba03b3369e`**,
> CONTENT-IDENTICAL to the preserved copy after newline normalisation. **SOURCE (S1) HOLDS at the
> TAGGED SOURCE.** Round 11's counter-claim (2,532 lines, `:2211-2243`) matches neither.
> **The correction it forced lands against this plan's own rule:** the digest previously pinned
> (`7487db46...`) was the hash of OUR copy, LF converted to CRLF by a text-mode write --
> **a local copy's digest is provenance of the READING, never of the SOURCE**, which is the exact
> gap the citation rule exists to close, live inside that rule's own worked example.
> RD-ratified remedy, now standing: **pin the UPSTREAM digest together with the fetch URL.**
> **The narrowing-by-measurement stands and is now belt-and-braces** -- the rollback-SUCCEEDS half
> was independently measured on this machine, only the chains-on-failure half ever rested on the C
> source, and that half is now confirmed upstream.
> The full per-finding adjudication, each with what was verified by execution, is in
> `.copowers-findings.md` under **Round 11**; the dispositions are in **S11**.
>
> **WHY THE SWEEP HAPPENED, AND WHAT IT BOUGHT.** **THE LOOP HAD NO SETTLING STEP, AND THAT IS WHAT
> ROUNDS 8, 9 AND 10 WERE SPENDING THEMSELVES ON.**
> Round 10 returned 6 of its 7 findings RESIDUAL -- four of them residuals of the amendment pass
> written the same day. The shape was ruling -> amend -> review-of-the-wake, with nothing in
> between. **The gate-holder ruled a DEDICATED SELF-SWEEP followed by ONE confirming round on the
> settled artifact** (the recipe's Expansion-#13 provision, §5.1), and this document is the settled
> artifact. **Sweep findings carry UNCOUNTED ids (`SS-N`): no Codex, no round number, and NO effect
> on convergence** -- the uncounted status is what keeps the step honest, and S11 lists them.
>
> **Round 10's seven are ALL DISPOSED HERE** (they were returned unfixed by instruction):
> `A4-R10-1` and `A4-R10-2` were ROUTED and **RD RULED BOTH on 2026-09-07** -- the predicate is
> SCOPED and its `isinstance` filter REMOVED (S2.2, S2.4, Task 3/4), and the probability sentence is
> **his own text, shipped verbatim** (S7.7). `A4-R10-3` (tests scheduled by artifact rather than by
> assertion), `A4-R10-4` (a journal-mode over-generalisation, now MEASURED per fixture shape),
> `A4-R10-6` (a warning-site count the `A4-R9-1` fix invalidated) and `A4-R10-7` (SIX spellings
> versus a SEVENTH) are fixed in the sweep. `A4-R10-5` stays REFUTED on the evidence **and its
> remedy is adopted anyway as a standing rule**: an out-of-repo citation anchors on CONTENT and pins
> the file by **the UPSTREAM digest together with the fetch URL** -- **a local copy's digest is
> provenance of the READING, never of the SOURCE** (RD-ratified 2026-09-07 when the network fetch
> that closed `A4-R11-9` showed this entry's own pin was a hash of our copy; Global Constraints;
> SOURCE (S1)).
> Full per-finding adjudication in `.copowers-findings.md`; the ledger's totals are re-derivable by a
> one-line command rather than by reading.
>
> Rounds 1-9 at the binding `strong` tier, all five mechanical assertions passing every counted
> round, zero reopened and zero reverted throughout. **Round 9 did NOT converge** -- it opened nine
> findings, three of which bore on rulings just made and were ROUTED rather than amended, because a
> plan may not rewrite a ruling's premise on its own authority. **RD ruled all three on 2026-09-07,
> and this document is the amended shape.**
>
> **RULING 1 -- `A4-R9-2`: BRANCH A SELECTED. RULE (i) IS LITERAL ON BOTH PATHS.** Round 9's
> reviewer was right that CPython exposes `__exit__`'s internal rollback failure; the plan's
> two-round claim that *"the wrapper cannot see whether that internal rollback raised"* is
> **FALSE and is struck everywhere**. `with conn:` stays **byte-identical** -- no hand-rolled
> transaction plumbing, so option (b) stays rejected -- and the wrapper instead **inspects what
> propagates and its `__context__` chain at the except site**; a detected rollback failure VOIDS the
> probe exactly as the immediate path does (S2.2, S2.4, S7.15).
>
> **RULING 2 -- `A4-R9-3` CLOSES STRUCTURALLY, AND RD'S ITEM-3 ACCEPTANCE OF 2026-09-06 IS
> SUPERSEDED.** That acceptance declared the deferred-path gap COVERED-not-accepted on constraint 3.
> Branch A removes the gap, so the composition window round 9 found -- rollback-raised admitting a
> probe that then reads a colliding token another transaction committed -- **has no admitting step
> left**. **ONE ruling governs this path, not two side by side:** the 2026-09-06 acceptance is
> recorded as superseded, not carried alongside (S7.15).
>
> **RULING 3 -- `A4-R9-4`, THEN `A4-R10-2`: the S7.7 wording is CORRECTED TWICE, and the FOURTH
> statement is RD's own and ships VERBATIM.** *"EQUALS the collision probability"* was wrong (an
> equality where only a bound holds); *"`P(false confirm) < P(collision)`"* was wrong too
> (strictness needs a probability model, and the conjuncts may not be multiplied without
> independence). **S7.7 now carries, word for word:** *"The false-confirm event requires the conjunction of (a) a token collision, (b) same-ticker, and (c) the probe-window timing; its probability is therefore AT MOST the collision probability (containment). No independence is assumed and no strictness is claimed."*
>
> **THE OTHER FOUR ROUND-9 FINDINGS ARE FIXED IN THIS PASS, NOT DEFERRED:** `A4-R9-1` (the Python
> validator was not equivalent to the SQL CHECK -- embedded NUL, lone surrogate), `A4-R9-5` (the
> tier-3 override path reaches no preflight), `A4-R9-6` (a rollback-journal measurement generalised
> to WAL), `A4-R9-7` (Task 3 could not reach green). `A4-R9-8` and `A4-R9-9` were fixed in the
> previous pass.
>
> **AUTHORIZATION STATE, STATED ONCE AND WITHOUT CONTRADICTION:** CHARC's five ratifications and his
> attached condition (Task 1b) are landed. RD's rulings of 2026-09-06, of 2026-09-07 on round 9, and
> of 2026-09-07 on round 10's `A4-R10-1` and `A4-R10-2` are ALL landed. **No director item was open
> when round 11 ran; round 11 then opened TWO** -- `A4-R11-2` and `A4-R11-9`. **`A4-R11-2` WAS
> RULED BY RD on 2026-09-07 and is landed with all three of its conditions** (S2.2, (RD-a4), Task 3)
> -- it was NOT amended on the plan's own authority, which is the standing rule and was honoured.
> **`A4-R11-9` IS SETTLED** (S8 item 8). It was ROUTED by the fix leg -- it needed a network fetch,
> not a ruling, and the leg did not substitute anything that would have looked like a settlement --
> and the orchestrator then made that fetch, by the method the routing wrote down. **No director
> item and no round-11 finding is open.**
> **THIS PLAN IS NOT AUTHORIZED TO EXECUTE. Its state is: every round-11 finding CLOSED in writing,
> awaiting a gate with a disposition.** *No twelfth counted round has been authorized, and none was
> run.*
>
> **ONE CORRECTION THIS PASS OWES AGAINST THE RULING IT APPLIED, stated here rather than buried:**
> the `A4-R10-1` ruling was relayed with the rationale that a cleanly-completed block leaves
> `__context__` None, so the ambient-`except` false positive lives entirely in the excluded region.
> **MEASURED 2026-09-07: it does not** -- `__context__` is set from the THREAD's handled exception,
> so a caller inside an `except` still produces a non-None context on the commit-failed/rollback-OK
> row, and the removed type filter would have caught it. **The DECISION stood on its other leg**
> (a false positive costs a settle that does not happen; a false NEGATIVE admits a read rule (i)
> refuses), and the false positive had ZERO production instances by a read of both call sites.
> **SUPERSEDED 2026-09-07 BY RD's `A4-R11-2` RULING: the cost is no longer PAID, it is not
> INCURRED** -- the ambient object is captured before the transaction and excluded by identity, and
> **(RD-a4)'s four-row matrix drives all four cells under both predicates.** *Kept because the
> correction was owed against a ruling and the record of owing it is worth more than a tidy
> paragraph.* S2.2 carries both measurements.
>
> Full ledger: `.copowers-findings.md`; raw transcripts `.codex-review-r1..r11.txt`.

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
- **EVERY CITATION TO A FILE OUTSIDE THIS REPOSITORY IS ANCHORED ON CONTENT AND PINS THE FILE BY
  ITS UPSTREAM DIGEST TOGETHER WITH THE FETCH URL** (adopted 2026-09-07 from `A4-R10-5`;
  **AMENDED THE SAME DAY, RD-ratified, when the network fetch that closed `A4-R11-9` showed this
  rule's own worked example was breaking it**). A bare line number into a file no reader here can
  open is unverifiable, and this plan has already had one such citation confidently refuted with
  counter-line-numbers that were themselves unsourced. Cite the FUNCTION NAME and a VERBATIM
  fragment a reader can grep; give **the UPSTREAM digest and the URL it was fetched from**; keep
  line numbers as a convenience against the pinned bytes.
  **A LOCAL COPY'S DIGEST IS PROVENANCE OF THE READING, NEVER OF THE SOURCE -- and the failure is
  invisible, because the hash is real and it verifies.** SOURCE (S1) pinned `7487db46...` for two
  weeks; that digest was the hash of OUR copy, whose LF had been converted to CRLF by a text-mode
  write. It pinned WHICH BYTES WERE READ and said nothing about WHOSE they were, which is the exact
  gap this rule exists to close -- **so the rule as first written closed only half of it.** Two
  readers verified against that copy and were both right about the copy.
  **THE COROLLARY ON COUNTS: a line count is a CONVENIENCE, never a pin.** Three numbers have been
  asserted for that one file (2,532 / 2,717 / 2,718); the byte size and the digest never moved.
  Report a count with the METHOD that produced it (`wc -l` and `splitlines()` agree at 2,717 on a
  file ending in a newline; an editor showing a phantom trailing line reports 2,718).
  **The rule binds the code this plan ships too** -- `_exit_rollback_failed`'s docstring
  carries the content anchor, not the line range (Task 3).
  **AND IT HAS AN IN-REPO COROLLARY, ADDED THE SAME DAY BY THE SWEEP THAT FOUND FOUR IN-REPO
  ANCHORS WRONG AT ONCE (`SS-12`): every `file.py:N` citation NAMES THE SYMBOL it points at.** An
  in-repo line number is checkable, so it is weaker than the out-of-repo case -- but it DRIFTS,
  nobody re-checks it, and this plan carried a set of four that pointed into the wrong function
  entirely while their COUNT was correct. The symbol is what survives an edit; the number is a
  convenience. **The sweep's method was an AST walk, not a grep** -- a grep for `log\.` finds
  logging calls but cannot tell you which FUNCTION contains them, which is the fact the entry was
  making.
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
  `swing/trades/entry.py:1035-1163` (`_entry_transaction`): `immediate=False` yields inside `with conn:`; `immediate=True`
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
  declared counts will be wrong.** **AND THE SAME RULE APPLIES TO THE GREP TWO LINES DOWN, WHICH IT WAS NOT GETTING** (`SS-17`).
  `grep -rn "insert_trade_with_event" swing/` returns **NINE hits, not one**: the DEFINITION
  (`swing/data/repos/trades.py:214`), the IMPORT (`swing/trades/entry.py:14`), **exactly one CALL
  (`swing/trades/entry.py:1421`)**, three PROSE mentions (`swing/data/repos/fills.py:31`,
  `swing/trades/entry.py:1443`, `:1471`) and **three `__pycache__` binary matches**. The CLAIM --
  one call site -- is TRUE and was established by READING all nine; the sentence reported the
  conclusion in the grammar of the command's output, which is the exact defect `A4-R7-6` names one
  bullet above. *Recorded rather than silently corrected: a bullet that invokes a rule and then
  breaks it two lines later is worth more as a correction than as a tidy sentence.* The f-string-INSERT family was
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
  allowlist-by-EXCLUSION: `_RESERVED_JOURNAL_FIELDS` (`:178-196`) names **SEVEN** coupled `(table, column)` pairs
  (MEASURED by reading the dict literal end to end, 2026-09-07 -- **this bullet said "five" at
  `:178-183` while Task 1b said SEVEN, and BOTH ranges were short**; `A4-R11-13`), and
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
  `ensure_schema` -- re-MEASURED 2026-09-07) the reader was admitted; in rollback-journal mode a
  reader is admitted while the writer holds RESERVED. The probe does not deadlock behind the writer
  merely because a transaction is open.
  **SCOPE, NARROWED 2026-09-07 (`A4-R10-4`, whose second half this plan had not touched): this
  measured ONE condition -- an open write transaction -- and it is NOT the claim "a WAL reader never
  blocks".** WAL readers can still get `SQLITE_BUSY` from an EXCLUSIVE lock (`VACUUM`, a
  `BEGIN EXCLUSIVE`, a checkpoint-restart), from WAL-index recovery after an abnormal exit, and from
  the last connection's closing checkpoint. **This is why the probe carries a BOUNDED busy timeout
  and a contained failure path (S2.3) rather than an argument that it cannot block** -- the
  narrowing costs the design nothing, because the design never leaned on the wider claim.
- **MEASURED (3) -- IN ROLLBACK-JOURNAL MODE, in the classic commit-time failure the fresh read is
  BLOCKED until the writer's transaction is resolved. THE JOURNAL MODE IS PART OF THE MEASUREMENT
  AND WAS PREVIOUSLY OMITTED** (`A4-R9-6`; the omission mattered because **the LIVE database is
  WAL**, so an unlabelled reading of this line generalises a rollback-journal fact onto the live
  mode, which is exactly the two-path-divergence class this project has a gotcha for). Reproduced
  with no proxy at all, on a **rollback-journal** temporary database:
  connection B holds an open read transaction, connection A inserts and calls `commit()`, and the
  commit raises `OperationalError: database is locked` with `A.in_transaction` still **True**. A
  third, freshly-opened connection then ALSO got `database is locked`, because the failed commit
  leaves A holding a PENDING lock. **After `A.rollback()` the same fresh read succeeded and returned
  absent.**
  **WHAT THIS DOES AND DOES NOT LICENSE, now that the mode is named.** In rollback-journal mode the
  ruled order -- (i) resolve, (ii) open a FRESH connection, (iii) read -- is not merely
  conservative: the resolution is what makes the read POSSIBLE in the commonest commit-failure
  shape. **In WAL it is NOT: MEASURED (2) admitted a fresh reader against an open write
  transaction, which is the condition this failure shape produces**, so on the
  live database the resolution's value rests on the OTHER argument alone -- that a resolved
  transaction is what makes an ABSENT answer a statement about the LEDGER rather than about a
  moment (S2.2). The plan carried the blocking reason as the "blunter" one; on the mode the operator
  actually runs, it does not apply, and S2.2 now says so.
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
  changes no exception identity there, and only OBSERVES. (An earlier draft added here that the
  sub-case where `__exit__`'s own rollback ALSO fails *"is not constructible on this machine"*.
  **That sentence is STRUCK:** it IS constructible on the sibling arm -- MEASURED (6) -- and the
  commit arm is closed by SOURCE (S1). The sub-case is not merely possible, it is OBSERVABLE, and
  that is what Branch A rests on.)
- **MEASURED (4) -- `conn.in_transaction` is False after a commit that returned**, so a lost-commit
  handler that finds `in_transaction` True is looking at a commit that did NOT land. That is what
  makes rule (i)'s cost provably zero (S2.4).

> **THE FOUR FACTS BELOW DECIDED THE `A4-R9-2` RULING (RD, 2026-09-07). They were produced by
> EXECUTION and by a SOURCE READ, in that order, and they are recorded separately from the design
> because a ruling's evidence should be checkable without reading the design it authorised.**
> Runtime for all of them: **Python 3.14.2 / sqlite3 3.50.4**, the same interpreter S11's baseline
> ran on. The script is preserved at `~/swing-data/review-transcripts/22-a4-plan/item2-experiment.py`.

- **MEASURED (5) -- A PYTHON-LEVEL `rollback()` OVERRIDE IS NOT INVOKED BY THE C `__exit__`.**
  A `sqlite3.connect(factory=<Connection subclass overriding rollback>)` connection ran the whole
  failed-commit sequence with the override's counter at **zero**: `pysqlite_connection_exit_impl`
  calls the C rollback implementation directly and never performs the Python attribute lookup.
  **Banked as a fact about the TEST LEVER, not only about this arc:** `factory=` is the obvious
  reach for anyone who next wants to intercept transaction control, and it silently does nothing.
- **MEASURED (6) -- A ROLLBACK FAILURE INSIDE `__exit__` REACHES THE CALLER; IT IS NOT SWALLOWED.**
  On the BLOCK-ERROR arm (the arm where a failure can be forced natively, via a progress handler
  that raises): the block raised `ValueError("block-error")`, `__exit__`'s rollback then failed, and
  what propagated to the caller was **`OperationalError: interrupted` with `__context__` set to the
  original `ValueError`.** The rollback's exception REPLACES the propagating one and preserves the
  original as its context. **This is the observable signal Branch A reads.**
- **MEASURED (7) -- A FAILED COMMIT LEAVES `in_transaction` TRUE, so `__exit__`'s rollback is REAL
  WORK AND NOT A NO-OP.** Immediately after `commit()` raises and before any rollback,
  `conn.in_transaction` reads **True**. **This is the fact that makes the whole clause
  non-vacuous:** if the exit's rollback had nothing to do, "the rollback might also fail" would be a
  hypothetical about a call that does not happen. It happens, it does work, and it can fail.
  (It does not contradict MEASURED (3b): (3b) reads the state AFTER `__exit__` has completed its
  rollback; (7) reads it BETWEEN the failed commit and that rollback.)
- **SOURCE (S1) -- THE COMMIT-FAIL ARM, CLOSED BY CITATION RATHER THAN LEFT AN INFERENCE.**
  MEASURED (6) is the block-error arm; the arm this design actually runs on is the commit-fail arm,
  and **it cannot be forced natively** -- MEASURED (6a): the post-commit-failure rollback makes
  **zero** progress-handler callbacks, so the one native lever does not reach it. It is closed by
  reading **CPython v3.14.2, `Modules/_sqlite/connection.c`**.

  **THE CITATION IS ANCHORED ON CONTENT AND THE FILE IS PINNED BY DIGEST -- NEVER ON BARE LINE
  NUMBERS** (`A4-R10-5`, adopted 2026-09-07 as a RULE for this plan and not only as a fix to this
  entry). Round 10 confidently refuted this citation by asserting the function sits at 2211-2243,
  which is `create_collation` in the file the citation was taken from; that round ran
  `sandbox: read-only` with `approval: never` and made no network call, so its counter-numbers were
  not sourced either. **Neither side could settle it from the document, and that is the defect: a
  line-numbered citation to a file OUTSIDE this repository is unverifiable by any reader, so it
  invites exactly that exchange.** The remedy is an anchor a reader can grep and a digest a reader
  can check:

  - **THE FILE, PINNED AT THE UPSTREAM SOURCE AND NOT AT A LOCAL COPY (SETTLED 2026-09-07 by a
    network fetch; `A4-R11-9` CLOSED).**
    **FETCH URL:** `https://raw.githubusercontent.com/python/cpython/v3.14.2/Modules/_sqlite/connection.c`
    **UPSTREAM sha256 `8cc0d9df05860c0b3fe6929ff392f8f85c9e1a5ef89c0cba31ab09ba03b3369e`, 80,695 bytes.**
    A copy is preserved beside this arc's review evidence at
    `~/swing-data/review-transcripts/22-a4-plan/cpython-3.14.2-Modules-_sqlite-connection.c`, and
    **its digest is now the upstream one** -- verified on disk 2026-09-07:
    `sha256sum` returns `8cc0d9df...`, 80,695 bytes, LF-only, final newline present.
    **THE RULE THIS ENTRY NOW OBEYS, RATIFIED BY RD AND WRITTEN AGAINST ITS OWN PRIOR TEXT: PIN THE
    UPSTREAM DIGEST TOGETHER WITH THE FETCH URL. A LOCAL COPY'S DIGEST IS PROVENANCE OF THE READING,
    NEVER OF THE SOURCE.** The digest this entry previously carried
    (`7487db46...`, "2,717 lines") was an artifact of a text-mode write converting LF to CRLF in the
    preserving process -- **a hash of our copy, pinning which bytes we read and not whose they
    were**, which is the exact gap the citation rule exists to close. *Recorded rather than
    silently swapped: the rule was adopted on 2026-09-07 and the entry that adopted it was breaking
    it on the same page.*
    **AND THE LINE COUNT IS REPORTED WITH THE METHOD, because three different numbers have now been
    asserted for this file (2,532 / 2,717 / 2,718).** MEASURED on the pinned bytes: `wc -l` = **2,717**
    and Python `splitlines()` = **2,717**; the file ends with a newline, so an editor that shows a
    phantom final line reports 2,718. **The bytes and the digest are identical either way, and they
    are the pin** -- the line count is exactly the fragile artifact this rule demotes to a
    convenience. Round 11's counter-claim (2,532 lines, the function at `:2211-2243`) matches
    neither convention and was produced with no network.
    **Any reader disagreeing with a line number below should first check the UPSTREAM digest against
    the URL**: two files both truthfully called "CPython 3.14.2 connection.c" can differ if one came
    from a distribution patch, and the digest is what makes the disagreement decidable.
  - **THE ANCHOR is the function `pysqlite_connection_exit_impl`** and, inside it, the verbatim
    comment **"Commit failed; try to rollback in order to unlock the database.  If rollback also
    fails, chain the exceptions."** `grep -n` on either locates the branch in any copy.
  - **THE BRANCH, read** (line numbers are a CONVENIENCE against the pinned file, not the
    citation): `:2377` the function; `:2386` no pending exception -> commit; `:2389` pending
    exception -> `pysqlite_connection_rollback_impl`; `:2394-95` the comment above;
    `:2396 PyObject *exc = PyErr_GetRaisedException()` captures the COMMIT error; `:2397` calls
    **the identical rollback implementation as `:2389`**; `:2399 _PyErr_ChainExceptions1(exc)` on
    rollback failure -- the ROLLBACK's exception is raised and the COMMIT's becomes its
    `__context__`; `:2403 PyErr_SetRaisedException(exc)` on rollback success -- the COMMIT's
    exception is re-raised unchanged. **Re-verified against the pinned file 2026-09-07.**

  **So the two arms share one rollback implementation and one propagation rule, and the
  commit-fail arm is MEASURED-AT-SOURCE rather than inferred.**

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
  the statement after `commit()` returns on the immediate path (`entry.py:1107`, **corrected from
  `:1128` by the 2026-09-07 sweep -- `:1128` is `conn.rollback()`, `SS-11`**) and after the
  `with conn:` block on the deferred path (`entry.py:1067`).
- **"Both `_entry_transaction` paths are bound"** -- **HOLDS, and it costs LESS than the first draft
  of this plan claimed.** That draft said a commit raising inside `__exit__` leaves the transaction
  OPEN with no rollback attempted, and proposed adding one; **MEASURED (3b) disproves it** --
  `__exit__` rolls back, `in_transaction` reads False, and the pre-arc path already resolves itself.
  So this arc adds **no rollback, no exception-identity change and -- after `SS-9` -- NO STATEMENT
  AT ALL** to `_entry_transaction`'s deferred branch; the two NEW observation fields
  (`resolution`, `cleanup_raised`) are written for that path from `record_entry`'s own post-commit
  handler (S2.2). The one thing it must still handle is the residual
  where
  `__exit__`'s own rollback failed, and it handles that with TWO observations rather than an
  assumption: it READS `conn.in_transaction` for the TRANSACTION's state, and it READS the
  propagating exception's `__context__` chain for the CALL's failure (SOURCE (S1), MEASURED (6)).
  **Neither is an inference, which is the property that made `committed` admissible.**
- **CHARC's shape -- `attempt_id TEXT` nullable, client-generated `uuid4`, same INSERT, UNIQUE
  partial index, migration 0038 ADDITIVE, one ADD COLUMN plus one index plus the version bump** --
  **SURVIVES VERIFICATION, with ONE addition and ONE documented divergence** (S2.0). The addition is
  a `CHECK (attempt_id IS NULL OR (typeof(attempt_id) = 'text' AND length(attempt_id) = 36))`
  -- **the `typeof` half included here too, because `A4-R7-1` was a fix that reached the prose and
  not the DDL and this is one of the prose sites** (S2.0 carries the authoritative text); the
  divergence is that the token is
  **not** a `Trade` dataclass field and is **not** read by `_row_to_trade`.
- **A DEFECT THE NEW INDEX INTRODUCES, found by verifying the premise rather than by review**
  (fixed in S2.5): `_record_entry_inner`'s IntegrityError mapper reads
  `if "UNIQUE" in str(exc) and "trades" in str(exc)` (`entry.py:1490`) and re-raises as
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
  the moment this arc bumps HEAD, which is the point. THE CENSUS BELOW WAS RE-MEASURED 2026-09-07
  (`A4-R11-11`) AND ITS PREVIOUS VERSION ATTACHED THE DROP-PATH REASON TO A FILE THAT NEVER CALLS
  `record_entry`.** Method, and it is now per-file rather than per-file-list: for each of the six
  test files mentioning both `record_entry` and `target_version`, count the `record_entry(` CALL
  sites, not the mentions.

  | file | `record_entry` mentions | actual CALLS | what it migrates to |
  |---|---|---|---|
  | `tests/trades/case_registry_22a.py` | 1 | **0** -- prose | -- |
  | `tests/trades/test_exit.py` | 1 | **0** -- prose | 16, deliberately older |
  | `tests/trades/test_22a_task4_authorization_ladder.py` | 1 | **0** -- prose at `:277` | the literal 37 (x3) |
  | `tests/trades/test_22a_task9_entry_wiring.py` | 30 | **5** | the literal 37 (`:89`) |
  | `tests/trades/test_entry.py` | 76 | **39** | `EXPECTED_SCHEMA_VERSION` |
  | `tests/trades/test_phase7_entry_risk_policy_stamp.py` | 12 | **4** | `EXPECTED_SCHEMA_VERSION` |

  **So the drop-path reason -- "after the bump this leaves a v37 database and drives `record_entry`
  against a schema with no `attempt_id`, silently exercising the pre-v38 path (S7.5) instead of the
  production one" -- holds for EXACTLY ONE site: `test_22a_task9_entry_wiring.py:89`.**
  `test_22a_task4_authorization_ladder.py` was named beside it and never calls the service at all.
  **The other six migrate-to-HEAD sites in row 6 below are still re-spelled, for a DIFFERENT and
  weaker reason, stated as the judgement it is:** they build a v36 world and then want production
  HEAD for the 22-A machinery under test, and a fixture pinned one version behind HEAD is a
  false-green risk for any HEAD-dependent assertion added later. **The closure check for both is the
  full fast suite**, which is red if a site needed the change and silent if it did not.
  *The census's own text already said the manifest is the greps PLUS a read of every hit; the greps
  were done and the REASON attached to the hits was not re-derived per file, which is how a true
  count carried a false explanation.*
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
  **AND THE FAMILY IS SEVEN SPELLINGS, NOT SIX** (`A4-R10-7`): the six above are the ones a VALUE
  GREP can see; **the seventh is SEMANTIC NAMES AND COMMENTS** -- `def
  test_expected_schema_version_is_37()` whose body asserts HEAD, and a comment reading *"so the
  ceiling is now 37"* beside the ceiling this arc raises (`A4-R7-12`, enumerated in Task 1). It has
  no value token to grep and it fails NOTHING, so it is found by reading or not at all. **This plan
  said "SIX" in two places and "a SEVENTH" in a third for three rounds** -- a mirror-count
  discrepancy inside the section about mirror counts, which is the joke the class keeps telling.
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
> **"FORK" IS STRUCK FROM THE TRIGGER LIST -- ROUTED, AND CONFIRMED STRUCK BY RD 2026-09-06 ON THIS
> MEASUREMENT** (`A4-R6-11`). **MEASURED, by reading CPython 3.14's `uuid.uuid4` source:** it is
> `int.from_bytes(os.urandom(16))` **per call**. There is no process-local PRNG whose state a `fork`
> would clone, so **acquiring `fork` by porting to a POSIX platform does not, by itself, create the
> correlated state the trigger is meant to detect** -- it would fire on an ordinary platform port
> with no hazard present, and activate a materially more expensive design on the money path.
>
> **THE SURVIVING TRIGGERS, EXACTLY TWO, AS RULED:**
> **(a)** a change of GENERATOR away from `os.urandom`;
> **(b)** a MEASURED condition that DUPLICATES THE OS ENTROPY STREAM.
>
> **VM SNAPSHOT-RESUME IS AN INSTANCE OF (b), NEVER AN INDEPENDENT TRIGGER.** Resumed guests
> replaying the entropy pool is the documented mechanism `vmgenid` exists to signal, so it qualifies
> **only where that duplication is actually established** -- never on the bare fact that a VM was
> snapshotted. Recording it as an instance rather than a third bullet is what stops the trigger list
> re-acquiring the looseness `fork` was struck for.
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
        #
        # **THE SAME FUNCTION THE REPO'S PRE-WRITE GUARD CALLS** (A4-R9-1).
        # Two hand-written validators over one column are a mirror pair that
        # can drift, and the drift that matters is the one where THIS side
        # ADMITS what the WRITE side refuses -- which converts a contained
        # degradation into a failed money-bearing entry.  One authority.
        validate_attempt_id(token)             # raises ValueError; see below
    except Exception:                          # NOT BaseException -- see below
        <contained WARNING>; return _AttemptIdentity(None, None)
    try:
        db_path = _resolve_main_db_path(conn)  # PRAGMA database_list; None for :memory:
    except Exception:
        <contained WARNING>; db_path = None
    return _AttemptIdentity(token, db_path)
```

**THE VALIDATOR ITSELF, AND WHY `isinstance(str) AND len == 36` WAS NOT GOOD ENOUGH** (`A4-R9-1`).
It lives ONCE, in `swing/data/repos/trades.py` beside `ATTEMPT_ID_LENGTH`, and both the service
helper above and the repo's pre-write guard call it:

```
# swing/data/repos/trades.py
ATTEMPT_ID_LENGTH = 36          # the Python side of the CHECK's length half

def validate_attempt_id(value) -> None:
    """Raise ValueError unless `value` is a CANONICAL lowercase uuid4 string.
    STRICTER than the SQL CHECK on purpose: the CHECK is the storage
    contract, this is the ADMISSION contract, and it must not admit anything
    the CHECK -- or the parameter BINDING one layer below it -- would refuse."""
    if not isinstance(value, str):            # mirrors the CHECK's typeof half
        raise ValueError(...)
    if len(value) != ATTEMPT_ID_LENGTH:       # mirrors the CHECK's length half
        raise ValueError(...)
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError(...) from exc
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError(...)
```

**THE TWO VALUES THAT DEFEATED THE OLD PREDICATE, both reachable from a mint returning a
plausible-looking string, and both landing INSIDE the money-bearing INSERT rather than before it:**

- **A 35-CHARACTER STRING PLUS AN EMBEDDED NUL.** Python `len(...)` counts **36**; SQLite
  `length()` on the stored TEXT counts **35**, because `length()` stops at the NUL. The old
  predicate ADMITS it, the CHECK REFUSES it, and the refusal arrives as an `IntegrityError` from
  the entry INSERT -- the ordinary-path failure S2.1 exists to exclude, produced by the guard that
  exists to exclude it. `uuid.UUID` rejects it at parse.
- **A LONE SURROGATE** (e.g. `"\ud800"` inside an otherwise 36-character string). It has Python
  length 36 and never reaches the CHECK at all: `sqlite3` raises at **parameter binding**, one
  layer BELOW the CHECK, so a plan that reasons only about the CHECK cannot see it. `uuid.UUID`
  rejects it at parse.

**WHY VERSION-4 AND CANONICAL ROUND-TRIP AND NOT JUST "PARSES AS A UUID".** `uuid.UUID` accepts
braces, a `urn:uuid:` prefix, uppercase hex and embedded hyphens in the wrong places; several of
those are 36 characters. Requiring `str(parsed) == value` pins the exact stored representation --
which the UNIQUE index depends on, since `'A...'` and `'a...'` are DIFFERENT text keys and would
defeat the index that S7.8 says catches a live duplicate. Requiring `version == 4` is a deliberate
coupling to the mint's generator and is **named as a mirror**: if S7.7's re-open trigger (a) ever
fires and the generator changes, this predicate is one of the sites that must change with it.

**THE COST, STATED BECAUSE IT REACHES EVERY TEST IN S3:** a planted token must now be a canonical
lowercase v4 string. The plan's fixtures use `"00000000-0000-4000-8000-000000000001"` and siblings
(version nibble `4`, variant nibble in `{8,9,a,b}`); a bare `"x" * 36` no longer passes the repo
guard, which is the point -- **and it is the reason (r3)'s and (e2)'s rosters below grow rather than
merely change wording.**

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

### S2.2 THE THREE OBSERVATIONS (TWO NEW FIELDS) -- decision: **the IMMEDIATE path observes them in `_entry_transaction`; the DEFERRED path is observed by `record_entry`, and `_entry_transaction`'s deferred branch is LEFT UNEDITED**

> **This section was rewritten after round 1.** Its first version proposed adding a rollback to the
> deferred path, on a premise `A4-R1-2` disproved: `sqlite3.Connection.__exit__` ALREADY rolls back
> when its own commit fails (MEASURED (3b)). The corrected design is strictly smaller, and it no
> longer changes any pre-arc behaviour.

`_CommitOutcome` gains **TWO** fields beside `committed`, for **three observations in total** -- stated as a count because the first draft's manifest said "+2" while its table listed three (`A4-R3-9`), and an executor following the manifest would have dropped `cleanup_raised`, which is a mandatory gate input:

> **`body_completed` WAS THE FOURTH, AND IT IS GONE -- RULED BY RD, 2026-09-07 (his PIN 1 on
> `A4-R10-1`), and the reason is the byte-lock.** The field existed to say *the entry body finished,
> so whatever failed next was the COMMIT or later*, and on the deferred path the only place to set
> it is **inside the `with conn:` suite** -- which put a new statement inside the one block this arc
> promises not to edit, while three separate places in this plan claimed `with conn:` was
> byte-identical. **`record_entry` ALREADY OBSERVES THE SAME FACT AND HAS SINCE 22-A3:**
> `entry.py:830` pre-initialises `result: EntryResult | None = None` BEFORE the `try`, `entry.py:862`
> assigns it INSIDE the block from `_record_entry_inner`'s return, and the shipped guard at
> `entry.py:884` already reads `if result is None or not outcome.committed: raise` (**`:884`, not
> the `:880` this ruling was relayed with -- `:880` is inside the comment block above it; corrected
> by the 2026-09-07 sweep, `SS-11`**). **`result is not
> None` is non-None if and only if the body ran to completion**, it is `record_entry`'s observation
> of its own assignment, and it is PRE-ARC code this plan does not touch. A second field mirroring it
> would be the mirror-drift class (#11) bought for nothing. **So: no new flag, no statement inside
> `with conn:`, and the byte-identity claim holds in its strongest form.** *S2.4 condition 1 is now
> that shipped guard rather than a field of ours, and it is also the SCOPE for both deferred-path
> observations, which live in `record_entry` for the same reason (`SS-9`, below).*

| field | meaning | set where |
|---|---|---|
| `committed: bool` | **the commit's own return was observed** (unchanged) | IMMEDIATE: after `commit()` returns, **inside the protected suite**. DEFERRED: after the `with conn:` block, **exactly where it already is** -- the `A4-R1-3` window is closed on that path by `record_entry`'s own observation instead of by a `try` here (see below) |
| `resolution: str` | the PHYSICAL state, RE-READ from `conn.in_transaction` after any rollback attempt: `"unattempted"` / `"not_needed"` / `"rolled_back"` / `"still_open"` | **IMMEDIATE path:** `_entry_transaction`'s own failure handler. **DEFERRED path:** `record_entry`'s post-commit handler. **BOTH name the state through the SAME NON-MUTATING `_read_resolution(conn, *, attempted)` helper** -- which reads and never rolls back (`A4-R11-4`) |
| `cleanup_raised: bool` | **a rollback call raised** -- a fact about the CALL, not about the transaction | **IMMEDIATE path:** `_entry_transaction`'s handler, from its OWN `rollback()` raising (a direct observation). **DEFERRED path:** `record_entry`'s post-commit handler, from `_exit_rollback_failed(post_commit_error, ambient)` -- **and from nowhere else on this path**, because the deferred observation performs NO rollback (`A4-R11-3`/`A4-R11-4`) |

> **BOTH DEFERRED-PATH OBSERVATIONS LIVE ONE FRAME OUT, AND `_entry_transaction`'s DEFERRED BRANCH
> IS LEFT LITERALLY UNEDITED. THE 2026-09-07 SWEEP FOUND THIS IN THIS PASS'S OWN FIRST EDIT
> (`SS-9`).** RD's PIN 1 removed the `body_completed` field, which removed the scope condition
> the handler in `_entry_transaction`'s deferred branch had been using -- and the first version of this amendment
> answered that by calling the then-mutating shared helper **UNCONDITIONALLY** there. **That silently widened
> the arc onto a pre-arc failure branch:** on a deferred BODY-RAISE (`result is None`), the
> unconditional call reads `conn.in_transaction`, and in the sub-case where `__exit__`'s own
> rollback ALSO failed and left the transaction open, that helper's retry arm would issue
> **a rollback the pre-arc path never issued**, plus a log line, on a branch outside this arc's
> declared subject. **22-A LOCK clause (c) is about that branch.**
>
> **The correct move is the SAME one RD made for the predicate: put the observation in the frame
> that already has the scope.** `record_entry`'s handler has `conn`, has `post_commit_error`, has
> `result`, has `_reserve`, and raises at `result is None` BEFORE any of this runs -- so the
> body-raise branch is excluded by code that already ships. **`_entry_transaction`'s
> `if not immediate:` branch therefore needs NO `try`, NO `except`, NO added statement and NO `as`
> binding: it is the pre-arc statements, unchanged.** *(k3a) asserts that as an AST property*
> rather than leaving it as the prose claim it has been in three sections for three rounds.

Every one of them is an OBSERVATION -- of a call the WRITING frame itself made, of the connection's
own state, or of an exception that frame itself caught --
never an inference, the property that made `committed` admissible where the reverted clause-2 read
was not. **"The writing frame" is `_entry_transaction` on the immediate path and `record_entry` on
the deferred one, and the distinction is load-bearing rather than incidental:** each field is written
where the fact is DIRECTLY available, which is why no arm of this design has to reason about what
another frame must have done. `resolution` is what lets `record_entry` honour RD's rule (i)
mechanically instead of by comment.

**The immediate path** keeps its shape exactly, INCLUDING its `raise cleanup_error from
write_error`. **What the two paths share is the NON-MUTATING `_read_resolution`, and nothing else**
(`A4-R11-4`, and it dissolves `A4-R11-3` with it).

> **THE SHARED HELPER USED TO OWN A ROLLBACK, AND IT COULD NOT.** Task 3 said the helper "owns a
> rollback, contains its failure, and does not change what escapes"; the shipped immediate ladder
> must LOG that exact cleanup exception and then `raise cleanup_error from write_error`
> (`swing/trades/entry.py:1126-1163`; the chained re-raise is `:1162`). **Both cannot hold.** *And this is worse than a
> contradiction a reviewer found, because THE SETTLING SWEEP SAW THE TENSION AND WROTE A SENTENCE
> INSTEAD OF RESOLVING IT* -- the retired text said the helper is "shown INLINE below rather than as
> a call, because what it does is the point," which is an explanation standing in for a design.
> **The resolution is a SPLIT:** `_read_resolution(conn, *, attempted)` NAMES the physical state and
> mutates nothing; the immediate path keeps its OWN rollback inline in its OWN pre-arc ladder, with
> both existing messages and the chained re-raise untouched; **and the deferred path performs NO
> rollback at all.**
>
> **REMOVING THE DEFERRED RETRY IS NOT A NEW BEHAVIOUR -- IT IS THE PRE-ARC ONE** (`A4-R11-3`). The
> retry existed only in this pass's own `SS-9` fix, and it ran on the wounded connection BEFORE
> `_exit_rollback_failed` had detected the failure. RD's rule (i) is *"the connection is DISCARDED
> and NO read is attempted on it"*; issuing a second rollback on it is not that. With the retry
> gone, `__exit__` leaves the connection exactly as it left it pre-arc, and the deferred path's
> `cleanup_raised` has EXACTLY ONE source -- the chained exception -- which also makes (k5)'s
> discriminating claim unconditional rather than fixture-dependent.

```
def _read_resolution(conn, *, attempted: bool) -> str:
    """NAME the physical transaction state.  NON-MUTATING: it issues no
    SQL, performs no rollback, and cannot change what escapes.

    `conn.in_transaction` is an attribute read on the handle, not a
    statement, so this is safe to call on a connection rule (i) says must
    not be READ FROM.  `attempted` says whether THIS FRAME issued the
    rollback, which is the only thing distinguishing `rolled_back` from
    `not_needed` once the state is resolved.

    Contained in the ALARM direction for the same reason as
    `_exit_rollback_failed`: an unreadable state is `still_open`, which the
    S2.4 gate REFUSES.
    """
    try:
        open_ = bool(conn.in_transaction)
    except BaseException:  # noqa: BLE001 -- the CLASS, and it ALARMS
        return "still_open"
    if open_:
        return "still_open"
    return "rolled_back" if attempted else "not_needed"
```

**The immediate path's ladder, with the two existing cleanup messages untouched and pinned by
shipped tests:**

```
try:
    conn.execute("BEGIN IMMEDIATE")
    yield
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
            outcome.resolution = _read_resolution(conn, attempted=True)
            <the two existing branch messages, unchanged>
            # AND THE CHAINED RE-RAISE IS THE IMMEDIATE PATH'S OWN AND STAYS
            # HERE (`A4-R11-4`).  A shared helper that contained this failure
            # could not preserve it, which is why the shared thing is the
            # non-mutating READ and not the rollback.
            raise cleanup_error from write_error
        # **RE-READ AFTER THE RETURNING ARM TOO** (`A4-R7-8`).  This line used to
        # assign "rolled_back" UNCONDITIONALLY when `rollback()` returned, so the
        # field contract's own words -- *re-read from `conn.in_transaction` after
        # ANY rollback attempt* -- were honoured on the raising arm and INFERRED
        # on the returning one.  A rollback that returns without taking effect
        # would then be classified `rolled_back` and ADMIT the probe.
        outcome.resolution = _read_resolution(conn, attempted=True)
    else:
        outcome.resolution = _read_resolution(conn, attempted=False)
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

**The deferred path in `_entry_transaction` is NOT EDITED AT ALL.** These are the pre-arc lines and
they are what ships:

```
if not immediate:
    with conn:
        yield
    outcome.committed = True
    return
```

**Its TWO observations are taken in `record_entry`'s post-commit handler instead**, because that is
the frame where the scope is already observed and the pre-arc body-raise branch is already excluded:

```
# swing/trades/entry.py -- record_entry's post-commit handler
except BaseException as post_commit_error:
    if result is None:
        raise                      # PRE-ARC, UNCHANGED: the body never finished,
                                   # so nothing below runs on that branch
    if not outcome.committed:
        # ---- THE DEFERRED PATH'S OBSERVATIONS, both of them ----
        # `not _reserve`: the IMMEDIATE path took its own observations in
        # `_entry_transaction`, from its OWN rollback call.  Layering an
        # inference over a direct observation is the one thing this arc
        # exists not to do, so neither line runs there.
        #
        # **DETECTION FIRST, THEN THE READ** (`A4-R11-3`).  Nothing in this
        # block mutates the connection -- there is no retry rollback here,
        # by design -- but the ORDER still states rule (i) rather than
        # merely satisfying it: the failure is DETECTED before anything
        # else touches the handle, and what remains is `in_transaction`,
        # an attribute read that issues no SQL.
        if not _reserve:
            if _exit_rollback_failed(post_commit_error, ambient):
                outcome.cleanup_raised = True
            # `attempted=False`: THIS FRAME issued no rollback.  `__exit__`
            # owns this path's rollback, and the gate reads the PHYSICAL
            # state, which is re-read either way.
            outcome.resolution = _read_resolution(conn, attempted=False)
        raise                       # TASK 3 STOPS HERE; Task 4 replaces this
        ... the gate, S2.4 ...
```

**AND THE PRE-ARC GATE IS SPLIT IN TASK 3, NOT TASK 4** (`A4-R11-5`). `record_entry`'s shipped
`if result is None or not outcome.committed: raise` (`swing/trades/entry.py:884`) becomes two
branches **in the commit that adds the observations**, each ending in the same bare `raise`.
**The behaviour is byte-for-byte what it was** -- both arms re-raise -- and it is the only shape in
which Task 3 can reach its own specified green state: (k3a)'s Task-3 half requires the observation
to sit AFTER the `result is None` raise, and with the guard intact an observation after it is
UNREACHABLE whenever `committed` is False while one before it violates the asserted ordering.
*This is the schedule/reachability class at instance five, produced by the fix for instance four,
and it is the one instance `assertion_schedule_audit.py` is structurally blind to -- it detects a
row scheduled before a SYMBOL exists, and this was a row scheduled against a code SHAPE its task
declined to create.*

**WHY THE SIGNAL IS READABLE HERE AT ALL.** `__exit__` owns this path's rollback, so no frame can
observe the CALL -- but CPython does not swallow its failure, it PROPAGATES it and chains the commit
error beneath it as `__context__` (SOURCE (S1)). **A propagating exception is visible in every frame
it passes through**, and `record_entry`'s is the first one that also knows whether the body
completed. That coincidence is the whole design: **the fact and its scope are observable in the same
place, and in no other.**

**THE SCOPE IS ALSO WHAT LETS THE TYPE FILTER GO.** Both conditions are pre-existing or this arc's
own: `result is not None` is the shipped guard at `entry.py:884`, `not outcome.committed` is
clause 3's observation. Neither is new machinery, and the body-raised rows of the table below are
excluded by them before the predicate is called.

**`_exit_rollback_failed` -- THE PREDICATE, ITS SCOPE, AND ITS FAIL-OPEN DIRECTION.** This is the
whole of Branch A. **It lives in `entry.py` and is called from `record_entry`'s post-commit handler,
NOT from `_entry_transaction`** -- see the call site above.

> **RULED BY RD, 2026-09-07 (`A4-R10-1`): THE `isinstance` FILTER IS REMOVED. SCOPE THE INSPECTION,
> THEN USE A CONTEXT CHECK.** The predicate was doing two jobs -- deciding WHEN to look and
> WHAT to look at -- and the type filter was carrying both. Split: the SCOPE (`result is not None`
> and `not outcome.committed`, both already observed) decides when; a context check
> decides what. **The consequence that mattered to the ruling: the non-`sqlite3.Error` residue that
> `A4-R9-3` and `A4-R10-1` were rebuilt on CEASES TO EXIST, because nothing inspects types any
> more.**
>
> **AMENDED 2026-09-07 BY RD (`A4-R11-2`), AND THE AMENDMENT REMOVES THE COST THE RULING ACCEPTED
> RATHER THAN RE-ARGUING IT.** The bare check's one measured false positive was the caller running
> inside an ambient `except`. **Capture `sys.exc_info()[1]` IMMEDIATELY BEFORE the transaction
> context manager and exclude exactly that object by `is`-identity.** The capture POINT is part of
> the ruling: **not at function entry** -- any `except` frame between the capture and the `with`'s
> exit must belong to `record_entry` itself, where the envelope can see it, and only a capture
> adjacent to the `with` guarantees that. On rollback-success the re-raised COMMIT error's
> `__context__` IS the captured ambient object; on rollback-failure the escaping ROLLBACK error's
> `__context__` is the COMMIT error, which the ambient never is. **Both measured rows are satisfied:
> the false-positive row now ADMITS the probe, the chained row still VOIDS it.** The nested case
> composes without a special branch -- the rollback failure's `__context__` is the COMMIT error at
> the FIRST link, and the first link is the only one the predicate reads. **(RD-a4) is rebuilt as a
> FOUR-ROW MATRIX over {inside_except x chained}, each row computed under BOTH predicates.**
>
> **AND THE READ GOES THROUGH THE BASE SLOT (`A4-R11-1`, CRITICAL, REPRODUCED).**
> `escaping.__context__` is an ORDINARY attribute lookup: a `sqlite3.OperationalError` subclass
> defining `__context__` as a data descriptor reads whatever it likes. **MEASURED on this machine,
> CPython 3.14.2** (the rows are executed in (RD-a4), not quoted here): a subclass whose getter
> returns `None` made the bare read answer **False** while the real `OperationalError` sat in the
> slot -- a **FALSE NEGATIVE** that sets `resolution = not_needed`, ADMITS the probe and rebuilds
> the `A4-R9-3` window this ruling declared closed; a subclass whose getter RAISES replaced the
> escaping exception outright. **THE SENTENCE THIS PLAN CARRIED -- that false negatives are
> "structurally impossible within its scope" -- WAS FALSE AND IS STRUCK.** The shape is the point:
> **this module documents the class one function away** (`safe_text`,
> `swing/trades/entry.py:109`, whose docstring says an exception class overriding `__repr__` to
> raise is constructible) **and it already owns the remedy** -- `_EVIDENCE_SLOTS`
> (`swing/trades/entry.py:147`, the tuple; `_EVIDENCE_FIELDS` at `:146`) is built from `BaseException.__dict__[...]` for exactly
> `("args", "__cause__", "__context__")`, above a comment reading *"`BaseException.__getattribute__`
> DOES NOT BYPASS A SUBCLASS DATA DESCRIPTOR"*. **The plan reasoned about a hostile exception's
> FORMATTING and not about its ATTRIBUTES, in the same file, twenty lines below a constant that
> exists because that read is unsafe.**

```
#: The `__context__` base getset descriptor, from the SAME source as
#: `_EVIDENCE_SLOTS` -- see the idiom at the head of this module.  A base
#: descriptor runs NO user code, which is the whole reason it is the read.
_CONTEXT_SLOT = BaseException.__dict__["__context__"]


def _exit_rollback_failed(escaping: BaseException,
                          ambient: BaseException | None) -> bool:
    """Did `sqlite3.Connection.__exit__`'s OWN rollback raise?

    CALLED ONLY when the entry body completed and the commit's return was
    NOT observed (S2.4).  Within that scope, CPython v3.14.2's
    `pysqlite_connection_exit_impl` -- the branch whose comment reads
    "Commit failed; try to rollback in order to unlock the database.  If
    rollback also fails, chain the exceptions." (SOURCE (S1), which pins the
    UPSTREAM digest and the fetch URL) -- leaves exactly two shapes:
      * rollback SUCCEEDS -> `PyErr_SetRaisedException` re-raises the
        COMMIT's exception, whose `__context__` is whatever the THREAD was
        already handling: `ambient`, captured immediately before the
        `with`, or None;
      * rollback FAILS    -> `_PyErr_ChainExceptions1` raises the ROLLBACK's
        exception with the COMMIT's chained beneath it as `__context__`,
        and the COMMIT's exception is never the ambient object.
    So within the scope, a `__context__` that is non-None AND IS NOT THE
    AMBIENT OBJECT is a link `__exit__` added.

    The slot read is contained in the ALARM direction: an unreadable
    context is treated as a rollback failure, because refusing a probe
    costs a settle that does not happen (today's behaviour) while
    admitting one on an unknown state is the direction rule (i) forbids.
    """
    try:
        context = _CONTEXT_SLOT.__get__(escaping, type(escaping))
    except BaseException:  # noqa: BLE001 -- the CLASS, and it ALARMS
        return True
    return context is not None and context is not ambient
```

**THE CAPTURE, AND WHY IT SITS WHERE IT SITS.** In `record_entry`, on the line **immediately before
the `try` that opens the guarded region** -- which is itself immediately before the
`with _entry_transaction(...)`:

```
ambient = sys.exc_info()[1]      # the THREAD's currently-handled exception
try:
    with _entry_transaction(conn, immediate=_reserve, outcome=outcome):
        ...
```

- **`sys.exc_info()[1]`, NOT `sys.exception()`.** `sys.exception()` is **Python 3.12+** and
  `pyproject.toml:9` declares `requires-python = ">=3.11"` (MEASURED by reading the file). The two
  return the same object; only one of them is inside this project's declared floor. *Recorded
  because the ruling was relayed naming `sys.exception()`, and a plan that adopted the NAME rather
  than the BEHAVIOUR would have shipped a 3.11 `AttributeError` on the money path.* `import sys` is
  already at `swing/trades/entry.py:8`.
- **BEFORE the `try`, not inside it.** The name is then unconditionally BOUND when the handler runs.
  Nothing between the capture and the `with` can change the thread's handled exception -- `try:` is
  not a handler -- so "immediately before the context manager" is satisfied and the handler cannot
  reach an unbound name.
- **The reference is HELD for the transaction's duration**, which is what makes `is` meaningful: the
  predicate compares OBJECT IDENTITY, never equality. Equality would consult a hostile `__eq__`, the
  same class of defect as the attribute read above.

**THE POST-FIX PREDICATE'S OWN NAMED RESIDUAL, DECLARED RATHER THAN LEFT TO BE DISCOVERED.** A false
NEGATIVE is now constructible in principle: if the object `__exit__` chains beneath the rollback
failure IS the captured ambient object, the predicate answers False and admits the probe. **It is
not constructible on the production path** -- the chained object is the COMMIT's exception, raised
fresh by SQLite inside `__exit__`, and a freshly-raised exception is not an object the caller was
already handling. Producing it needs a connection PROXY that re-raises the captured ambient object
as its own commit error. If it ever happened the rest of the gate still binds: a resolved
transaction, a token, and a ticker match are all still required.

**The four cases, each with the value it returns** -- and the scope excludes the first two before
the predicate is ever reached:

| what happened inside `__exit__` | what propagates | its `__context__` | predicate |
|---|---|---|---|
| body raised `E`, rollback OK | `E` | unchanged (the caller's own, or `None`) | **NEVER CALLED** -- `result is None`, and `record_entry`'s FIRST branch re-raises |
| body raised `E`, rollback FAILED with `R` | `R` | `E` | **NEVER CALLED** -- same branch, one step earlier |
| body OK, commit failed `C`, rollback OK | `C` | `ambient`, or `None` | **False** -- ambient or not, the probe is admitted, which is the design |
| body OK, commit failed `C`, rollback FAILED with `R` | `R` | `C` (never `ambient`) | **True** -- `cleanup_raised`, the probe is VOIDED |

**IT IS DELIBERATELY FAIL-OPEN TOWARD THE ALARM, AND THE ASYMMETRY IS THE ARGUMENT.** A FALSE
POSITIVE costs the settle -- exactly today's behaviour, the direction this whole arc treats as safe.
A FALSE NEGATIVE admits a read rule (i) would have refused. So the predicate is written to tolerate
false positives and to make false negatives reachable only through a construction that is named and
declared rather than through the ordinary shapes:

- **It cannot miss the case it is for.** Row 4 chains unconditionally at
  `_PyErr_ChainExceptions1`, whatever the two exceptions' types are. With the type test gone there
  is no exception class -- `MemoryError` from the C layer included -- that slips past it. **This is
  what the ruling bought: the previous version's stated residue was a type residue, and there is no
  longer a type in the predicate for a residue to hide behind.**

- **AND THE SENTENCE THAT USED TO STAND HERE -- *"false negatives are structurally impossible within
  its scope"* -- IS STRUCK, BECAUSE IT WAS FALSE (`A4-R11-1`, CRITICAL).** Two false negatives were
  REPRODUCED against the bare attribute read, and the removal of the type filter had been sold
  partly on that sentence. **What replaces it is not another adjective but a different READ** -- the
  base getset descriptor, which runs no user code -- plus a CONTAINMENT in the alarm direction, plus
  the two subclass rows in (RD-a4) that execute both. **The two remaining false-negative routes are
  now DECLARED, not asserted away:** the ambient-identity construction named above, and any
  behaviour of `BaseException`'s own descriptor, which is C.

- **THE FALSE POSITIVE THE BARE CHECK PRODUCED IS NAMED, WAS *MEASURED* RATHER THAN ARGUED, AND IS
  NOW REMOVED BY `A4-R11-2` RATHER THAN ACCEPTED.** The rationale the `A4-R10-1` ruling was relayed
  with said a cleanly-completed block means no exception was active when `__exit__` began, so row 3
  re-raises with `__context__ = None`. **THAT IS TRUE ONLY WHEN NO EXCEPTION IS BEING HANDLED
  ANYWHERE UP THE STACK, and a clean BLOCK does not establish that** -- `__context__` is set from
  the THREAD's currently-handled exception at raise time, not from the block's own outcome.
  **MEASURED, CPython 3.14.2 / sqlite3 3.50.4, rollback-journal database, commit forced to fail by a
  second connection holding the write lock, `__exit__`'s rollback SUCCEEDING in both runs:**

  | `record_entry` called... | propagated | `__context__` | bare check | old `isinstance` check | **the shipped check** |
  |---|---|---|---|---|---|
  | NOT inside an `except` | `OperationalError: database is locked` | `None` | **False** | False | **False** |
  | inside `except ValueError:` | `OperationalError: database is locked` | the `ValueError` | **True** | False | **False** |

  **So the S2.2 objection did NOT live entirely in the excluded region, and this plan says so rather
  than repeating the reason it was given.** Row 3 with an ambient handled exception was a REAL false
  positive of the bare check. **RD's `A4-R11-2` amendment removes it without restoring the type
  filter**: the ambient object is excluded by IDENTITY, so the direction argument no longer has to
  buy a cost that a cheaper discriminator can simply not incur. *The direction argument still stands
  and is still the reason the predicate fails toward the alarm; it is no longer being spent on this
  row.*

  **AND THE FALSE POSITIVE HAD ZERO PRODUCTION INSTANCES EVEN BEFORE THE AMENDMENT. THE METHOD:**
  `grep -rn 'record_entry(' --include=*.py swing/` returns **exactly two** call sites --
  `swing/cli.py:806` and `swing/web/routes/trades.py:1723` -- and **both were READ**: each sits in
  the `try:` SUITE of a `try/except`, which is NOT an exception HANDLER, so the captured ambient is
  `None` there. (The distinction is the whole point, and it is what the measurement above isolates:
  being lexically inside a `try` sets no ambient context; being inside an `except`/`finally` during
  unwinding does.) **The amendment is therefore not motivated by a live caller** -- it is motivated
  by the fact that a FUTURE caller retrying from inside an `except` would silently pay a cost this
  design does not need to charge, and **(RD-a4) drives all four cells so neither the cost nor its
  removal can change silently.**

**THE `A4-R1-3` WINDOW, AND WHY THE DEFERRED PATH NO LONGER NEEDS A `try` TO CLOSE IT.** The
window is real: an asynchronous exception delivered after `with conn:` returned -- so after the
commit was DURABLE -- but before `outcome.committed = True` executed, leaves `record_entry` holding a
non-None `result`, `committed` False, and `resolution` still `"unattempted"`. The first draft's gate
rejected `"unattempted"` and reported a durable entry as a failure; the plan's own S7.12 claimed the
window was closed while the pseudocode left it open.
**On the IMMEDIATE path the assignment sits inside `_entry_transaction`'s existing `try`**, whose
handler observes the resolution and re-raises, so the injected exception is caught where the
observation is taken.
**On the DEFERRED path the window is closed one frame out, by the SAME observation moved there.**
The injected exception propagates to `record_entry`, which observes `conn.in_transaction` -- False
after a commit that returned -- writes `resolution = "not_needed"`, and settles. **The outcome is
identical and the pre-arc branch keeps zero added statements**, which is the whole point of the
relocation. *(k3b) drives exactly this with a `sys.settrace` line hook, and (k3a) asserts the static
property on each branch separately* -- the immediate one's assignment inside a resolution-writing
`try`, and the deferred branch's ABSENCE of any `try` at all, which is the byte-lock made
mechanical rather than promised in prose.

**THE DEFERRED PATH ISSUES NO ROLLBACK, NO LOG AND NO STATEMENT -- IT ONLY OBSERVES** (`A4-R11-3`,
`A4-R11-4`). When its observation runs, `in_transaction` is normally False -- `__exit__` already
rolled back -- so `_read_resolution` writes `"not_needed"`. Where `__exit__`'s own rollback ALSO
failed and left the transaction open it writes `"still_open"`, **and that is all it does**: the
connection is left exactly as `__exit__` left it, which is the pre-arc state and is RD's rule (i)
taken literally (*"the connection is DISCARDED and NO read is attempted on it"*). The ORIGINAL
exception escapes with its identity preserved byte-for-byte.
**THE ASYMMETRY WITH THE IMMEDIATE PATH IS DELIBERATE AND IS NOW ALSO STRUCTURAL:** on the immediate
path the wrapper issues the rollback itself, so it owns the failure and raises
`cleanup_error from write_error`; on the deferred path the rollback is `__exit__`'s job, its failure
is ALREADY what escaped, and a second louder report from us would replace an exception the caller's
tests pin, for no new information.
**That last clause used to be a plausible-sounding reason and is now a MEASURED one:** *"already
reflected in what escaped"* is exactly SOURCE (S1) -- the rollback's exception IS what escaped,
with the commit's beneath it -- which is why the same fact both justifies staying quiet and
supplies `cleanup_raised`. **So on the deferred path `cleanup_raised` has EXACTLY ONE source, the
chained exception**, which is what makes (k5) a clean discriminator rather than a fixture-dependent
one. **Nothing here can clear the flag.**
**AND THE ARC NEVER REACHES THE PRE-ARC BODY-RAISE BRANCH:** both are inside
`if result is not None and not outcome.committed and not _reserve`, so a deferred entry whose BODY
raised gets no read, no retry and no log from this arc at all (`SS-9`; (RD-a5) asserts it).

*Why the resolution matters at all, given that the probe uses a FRESH connection:* the fresh
connection supplies VISIBILITY on its own (MEASURED (1)); the resolution supplies something else,
and naming it precisely is what stops this being cargo cult. **A resolved transaction is what makes
an ABSENT answer DURABLE.** With the writer's transaction still open, "absent" is a statement about
a moment: a caller that reuses the connection and commits later turns the row durable AFTER we
reported failure. Once the transaction is resolved, "absent" is a statement about the ledger. **And that is now the WHOLE
reason, on the mode the operator runs** (`A4-R9-6`). The plan used to add *"MEASURED (3) gives a
blunter reason: while the writer holds a PENDING lock the fresh reader is BLOCKED outright, so
without resolution there is frequently no read to have."* **MEASURED (3) is a ROLLBACK-JOURNAL
measurement and the live database is INFERRED-WAL** (see the label below), where MEASURED (2)
admitted a fresh reader against exactly this condition. So the blocking reason holds for
rollback-journal databases and **does NOT hold in production**.

> **"THE LIVE DATABASE IS WAL" IS INFERRED, NOT MEASURED, AND THIS PLAN NOW SAYS SO** (`A4-R11-12`).
> Global Constraints states the live database was NOT opened by this plan. The journal-mode readings
> in this section are all of `tmp_path` databases; the live file's mode is inferred from
> `open_connection(..., reaffirm_wal=True)` on the `ensure_schema` path plus `open_connection`'s own
> docstring (*"the live DB is already WAL (persistent in the file header)"*). **That is a strong
> inference and it is still an inference**, and it lands on ground this pass had just worked --
> `A4-R10-4` measured which FIXTURE shapes are WAL without noticing the LIVE claim beside them has
> the same defect one level up. **The remedy is one line in S6 step 0 and it is there**: the
> operator reports `PRAGMA journal_mode` from the live database before migrating, and the label
> stops reading INFERRED at that moment. **Nothing in the design depends on the answer** -- the
> durable-ABSENT argument holds in both modes, and every fixture that depends on blocking names and
> asserts its own mode -- so this is a labelling correction, not an open design question.

**AND WHICH TEST DATABASES ARE ROLLBACK-JOURNAL IS NOW MEASURED, BECAUSE THE PREVIOUS SENTENCE
GUESSED IT AND GUESSED WRONG** (`A4-R10-4`; the correction it replaces said *"every `tmp_path` test
database"*, and the round-10 ledger's own counter-claim -- *"only (c2)'s explicitly configured
fixture"* -- is wrong in the other direction). **MEASURED 2026-09-07, `PRAGMA journal_mode` on a
`tmp_path` database in this tree:**

| how the test database was built | journal mode |
|---|---|
| `ensure_schema(path)` -- `open_connection(..., reaffirm_wal=True)`, which runs `PRAGMA journal_mode=WAL` (`swing/data/db.py:130-131`, called from `:2214`) | **`wal`** |
| `open_connection(path)` + `run_migrations(...)`, never through `ensure_schema` -- the PRE-BARRIER shape already used at `tests/trades/test_22a_task9_entry_wiring.py:85-89` | **`delete`** |
| a bare `sqlite3.connect(path)` fixture, e.g. (c2)'s | **`delete`** |

**BOTH SHAPES ARE ALREADY IN THIS SUITE, in the same helper, on two branches of one `if`.** So the
true statement is neither "every `tmp_path` database" nor "only the explicitly configured fixture":
**it is a per-fixture property, and any test whose assertion depends on blocking MUST name and
assert its own mode.** (c2) and (RD-a3) do; (k4b) no longer makes a blocking claim at all.
The durable-ABSENT argument above stands unchanged in both modes and is the one this design rests
on. *Recorded rather than quietly deleted, because a reason that turns out to apply only to the
test environment is worth more as a correction than as a gap.*

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
    # **FAIL-CLOSED ON ABSENCE** (`A4-R11-10`): a `file:...?mode=rw` URI, so a
    # database that is not there raises instead of being CREATED.
    probe = open_connection(
        Path(db_path).resolve().as_uri() + "?mode=rw",
        uri=True,
        busy_timeout_ms=_PROBE_BUSY_TIMEOUT_MS,
    )
    try:
        return find_trade_id_by_attempt_id(probe, attempt_id)
    finally:
        <contained close>
```

- **The connection is FRESH by construction** -- `open_connection` on the path, never the writer's
  handle. This is the half of R10-02 that is closed by construction rather than by discipline, and
  **(RD-a2), in Task 4**, pins it with a test that captures the connection object the repo read
  receives and asserts it **is not** the writer's connection. *(`A4-R11-14`: this sentence said
  "Task 5 pins it", and Task 5 is documentation-only. A design decision pointed at a task that
  ships no test is a decision with no discriminator, which is the same defect `A4-R11-7` names four
  times one section down.)*
- **AND IT OPENS THROUGH A `file:...?mode=rw` URI, NOT A BARE PATH** (`A4-R11-10`, VERIFIED AT THE
  CODE). `open_connection` calls bare `sqlite3.connect(db_path_or_uri, uri=uri, ...)`
  (`swing/data/db.py:126`), **which CREATES the file when it is absent.** If the database is moved
  or renamed between the mint's path capture and the probe, the confirming READ would write an empty
  database and then answer ABSENT -- *a filesystem artifact created on an already-failing money
  path, by the mechanism whose entire purpose is to observe without acting.*
  **`open_connection`'s OWN DOCSTRING names the remedy** -- *"callers can pass a `file:...?mode=rw`
  URI and KEEP fail-closed semantics"* -- and the plan was not using it.
  **`mode=rw` and NOT `mode=ro`, deliberately:** `ro` would be tighter, but on a WAL database a
  read-only connection can need to CREATE the `-shm` file and fails when it cannot, which is a new
  failure mode on the exact path that must be reliable when things are already going wrong. `rw`
  buys the whole of the defect (no creation) at no new risk. *Tightening to `ro` is a candidate for
  a later arc and is named here rather than left as an unexamined alternative.*
  **`Path(...).resolve().as_uri()` percent-encodes**, so a path containing `?` or `#` cannot inject
  a URI parameter; the busy timeout is still passed and is pinned by (pr1).
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
        # **THE DEFERRED PATH'S TWO OBSERVATIONS ARE TAKEN HERE** (RD,
        # 2026-09-07, `A4-R10-1`, extended by `SS-9`).  This is the only frame
        # where the SCOPE is observable without writing a statement into the
        # byte-locked deferred branch: `result is not None` (one line up) says
        # the body completed, and `not outcome.committed` says the commit's
        # return was not observed.  Inside that scope a non-None `__context__`
        # on what escaped is a link `__exit__` added when its own rollback
        # failed (S2.2).
        #
        # `not _reserve` -- DEFERRED PATH ONLY.  The immediate path took both
        # observations in `_entry_transaction`, from its OWN rollback call,
        # and must not have an inference layered over a direct observation.
        # `ambient` is `sys.exc_info()[1]`, captured on the line immediately
        # BEFORE the `try` that opens this region (S2.2).  It is the object
        # `__context__` carries when `__exit__`'s rollback SUCCEEDED, and it
        # is never the object it carries when the rollback FAILED.
        if not _reserve:
            if _exit_rollback_failed(post_commit_error, ambient):
                outcome.cleanup_raised = True
            outcome.resolution = _read_resolution(conn, attempted=False)
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

1. **`result is not None`** -- the entry body ran to completion, so the failure is at or after the
   commit and not before it. **This is `record_entry`'s OWN pre-arc guard (`entry.py:884`), not a
   field of ours** (RD's PIN 1 on `A4-R10-1`, 2026-09-07): it raises before this helper is ever
   called, so the condition is enforced by the CALLER and the helper does not re-check what it
   cannot observe. *The earlier design carried an `outcome.body_completed` field for exactly this,
   and the only place to set it on the deferred path was inside `with conn:` -- a new statement in
   the one suite three sections of this plan promise is byte-identical.* **(RD-a5) asserts the
   caller-side obligation** rather than pinning the callee's absence -- gotcha #31's shape, and the
   reason the field's removal is not merely a deletion;
2. `outcome.resolution in {"not_needed", "rolled_back"}` **AND `outcome.cleanup_raised` is False** --
   RD's rule (i): *"if the rollback itself raises, the connection is DISCARDED and NO read is
   attempted on it"*, so a raising rollback refuses the read **even when the state re-read shows the
   rollback took effect** (`A4-R2-7`'s after-effect case). Both fields are checked because they are
   two different facts.
   **AND THE WORD "LITERALLY" IS RESTORED TO THIS GATE, ON BOTH PATHS** (`A4-R9-2`, ruled by RD
   2026-09-07; it replaces `A4-R8-1`'s narrower fix, which struck the word instead of earning it).
   On the IMMEDIATE path the wrapper issues the rollback itself, so `cleanup_raised` is a direct
   observation of its own call. **On the DEFERRED path `sqlite3.Connection.__exit__` issues it, and
   `record_entry` reads the failure -- one frame OUT, at the call site above -- from the exception
   that arrives** (`_exit_rollback_failed`, S2.2), grounded in SOURCE (S1) and MEASURED (6).
   **BOTH deferred-path observations moved out of `_entry_transaction`** -- the predicate on RD's
   `A4-R10-1` ruling of 2026-09-07, the state read on the sweep finding `SS-9` that
   followed from it -- and the gate is unchanged by the move: the fields are its inputs either way,
   and both are set before `_settle_by_attempt_identity` is called. **The two sequences that used to defeat the
   flag are both DETECTED now**: an internal rollback that takes effect and then raises, and one
   that raises before taking effect, propagate the SAME way -- the rollback's exception with the
   commit's chained beneath it -- because `__exit__` chains on the failure of the CALL and not on
   its effect. **A prior version of this plan declared that gap ACCEPTED and then COVERED; both
   declarations are superseded and S7.15 records the supersession** rather than leaving two
   acceptances side by side;
3. the attempt has BOTH a token and a database path;
4. the probe returns a row, and its ticker matches the request's.

**`"unattempted"` is a BELT, not an expected value.** After the `A4-R1-3` fix (S2.2),
`_read_resolution` runs on every path that can reach this gate -- `_entry_transaction`'s own
handler writes it on the immediate path (both arms of the `in_transaction` split), and
`record_entry`'s observation block writes it on the deferred one -- so `"unattempted"` should
be unreachable whenever `result is not None and not outcome.committed`. Condition 2 rejects it anyway, because the alternative
is a gate whose safety depends on an exhaustiveness argument about assignment placement -- and this
arc's subject is not trusting arguments where an observation is available. **Tests (k3a)/(k3b) are
what turn that belt into a proof** rather than leaving it as the same kind of argument.

**Honouring rule (i) forecloses nothing -- and the FIRST DRAFT'S VERSION OF THIS ARGUMENT WAS
WRONG, so here it is rebuilt on the corrected state model** (`A4-R2-7`). The draft said
`"unresolved"` is reachable only from `in_transaction == True`; `_RollbackAfterEffect` is a
counterexample already in the tree. The correct argument enumerates the THREE refusal branches
(TWO before Branch A made the third observable -- `A4-R9-2`) and
shows the row is provably absent in each:

- **`resolution == "still_open"`** (the rollback did not take effect). The handler only attempts a
  rollback when `in_transaction` was True on entry, and MEASURED (4) says `in_transaction` is False
  after a commit that RETURNED -- so on this branch the commit did not land, the row is PENDING, and
  a fresh connection would read ABSENT.
- **`cleanup_raised` with `resolution == "rolled_back"`** (the after-effect case, IMMEDIATE path).
  The rollback took effect, so the row is GONE, and a fresh connection would read ABSENT.
- **`cleanup_raised` with `resolution == "not_needed"`** -- **the THIRD branch, which exists only
  because Branch A made it observable** (`A4-R9-2`). On the DEFERRED path `__exit__`'s rollback took
  effect (so `in_transaction` reads False and the shared helper writes `not_needed`) and then
  raised, and `_exit_rollback_failed` -- called from the handler above -- reads that failure off the
  propagating exception. The rollback
  took effect, so the row is GONE and a fresh connection would read ABSENT. **Before Branch A this
  branch was not a refusal at all -- it was the admitting path `A4-R9-3` composed with the S7.7
  collision event to manufacture a false SUCCESS.** Making it a refusal is what closes that window
  structurally.

**In all three branches the refused read would have answered ABSENT, and ABSENT is what the refusal
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
>
> **AND THE ROSTER IS NOW CHECKED BY AN INSTRUMENT, NOT BY READING** (`SS-13`, 2026-09-07 --
> `A4-R10-3`'s generalisation turned into a check). `assertion_schedule_audit.py`, preserved beside
> this arc's review evidence, walks every row, collects the CODE SYMBOLS its text names, finds the
> TASK that schedules the row and the TASK that ships each symbol, and reports every row scheduled
> BEFORE something it names. **It is deliberately over-inclusive -- prose counts -- so every hit is
> READ**, and the three that survive as prose are named here so nobody re-adjudicates them:
> **(k2)**, **(k3a)** and **(k5)** each EXPLAIN why an assertion of theirs is deferred to Task 4,
> and **(r7)** names
> `_settle_by_attempt_identity` in its *why this row exists* rationale while asserting only on the
> repo function Task 1 ships. **Three rows are therefore SPLIT across two tasks and each says so in
> its own text** -- which is what the rule asks for, and is why the instrument cannot be made to
> read clean without either lying in the row or removing the explanation. **It found one real defect on its first run, in a row this same pass
> had just added** -- see (k3a).

### The full roster

| id | subject | kills |
|---|---|---|
| (m1)-(m6) | migration 0038: column, CHECK, index, gate, no-op re-run, data preserved, CHECK/Python drift | a schema that does not enforce what the design assumes |
| **(m7)** | the IMMUTABILITY trigger: a direct `UPDATE trades SET attempt_id` ABORTs (schema half) | **`A4-R4-1` -- a token re-assignable after insertion is not identity** |
| **(m8a)-(m8d)** | the corrector's TYPED refusal, its ORDER-INDEPENDENCE, its DELIVERY through unchanged CLI/web callers, and **the TIER-3 OVERRIDE path** | **`A4-R6-6`/`A4-R6-7`/`A4-R7-3`/`A4-R9-5` -- authorize-then-abort, key-order dependence, a refusal the operator never sees, and a supported operator surface the preflight never reached** |
| (r1)-(r6) | repo: write, pre-v38 drop, malformed reject, model/schema drift comparator, static INSERT closure walk, IntegrityError mapping | the mirror family (#11) and the defect the index introduces |
| **(r7)** | the PROBE is schema-aware: on v37 it returns `None` WITHOUT raising | **`A4-R8-5` -- an unconditional `WHERE attempt_id = ?` passes the whole suite while the advertised branch does not exist** |
| **(RD-a1)** | the probe is NOT CALLED when the rollback RAISED -- in BOTH its shapes | **R10-02 by assertion, not comment** |
| **(RD-a2)** | the probe NEVER receives the writer's connection | **R10-02's structural half** |
| **(RD-a3)** | rollback raises before taking effect, row PENDING -> NOT SUCCESS | **R10-02's reproduction** |
| **(RD-a4)** | the predicate's FOUR-ROW MATRIX -- {`inside_except` x `chained`}, every cell computed under BOTH predicates -- plus the TWO subclass-descriptor rows | **`A4-R11-2` + `A4-R11-1`: a one-row pin passed a false premise upward; the matrix is the repair** |
| **(RD-b)** | a concurrent insert takes our freed rowid -> NOT confirmed as ours | **R10-03** |
| **(RD-b2)** | a rolled-back token REUSED by a later committed row IS confirmed -- the declared residual, VERIFIED not asserted | a declaration nobody executed (`A4-R1-1`) |
| (c) | commit raises, row LANDED -> SUCCESS with warning, both paths | the arc's headline |
| (c2) | a REAL (unproxied) commit failure -> resolved, probe absent, re-raise | proxy-only test theatre |
| (d) | commit raises, row ABSENT -> re-raises the ORIGINAL | a settle that invents rows |
| **(w)** | ONE token flows mint -> INSERT argument -> probe argument, with a mint that returns DIFFERENT values each call | **a disconnected or double-minted identity that every constant-token test blesses** |
| **(w2)** | the MINT'S OWN CONTRACT: it calls `uuid.uuid4` once per mint, and two attempts yield two tokens | **`A4-R6-5` -- a constant mint that every `_mint_attempt_token`-level patch blesses** |
| (e) | co-durability OBSERVED AT THE TRANSACTION BOUNDARY: the writer sees the token while a fresh connection sees no row | **a post-commit stamp that the committed/rolled-back pair cannot tell from the real thing** |
| (e2) | the identity apparatus cannot FAIL an entry | a nicety that breaks the money path |
| (f) | no database path (in-memory) -> today's behaviour, no crash | an unguarded probe |
| (g) | a raising probe leaves the ORIGINAL exception untouched | the R11-03 class inside the new code |
| (h) | the probe connection reads `read_uncommitted = 0` | visibility assumed rather than pinned |
| (k) | the deferred path OBSERVES its own already-resolved lost commit | a wrapper that assumes instead of reading |
| (k2) | the deferred path's exception identity is UNCHANGED | an arc that quietly re-plumbs the pre-arc path |
| **(k3a)-(k3b)** | STATIC (AST) and RUNTIME (`sys.settrace`): the `A4-R1-3` window is closed on BOTH paths -- by a guarded `try` on the immediate one, and by `record_entry`'s own observation on the deferred one, whose branch (k3a) asserts contains **no `try` at all** | **`A4-R1-3`'s window -- (k3a) proves the property statically on each branch and pins the byte-lock; (k3b) proves the behaviour at the one line** |
| **(k7a)-(k7b)** | the `__context__` data descriptor that LIES and the one that RAISES -- the base-slot read's discriminator, IN TASK 3 where the read ships | **`A4-R11-1` reproduced; scheduled by `A4-R11-6`'s rule after the inverse check indicted the pass that wrote it** |
| **(k6a)-(k6b)** | the IMMEDIATE path's returning-arm re-read and its took-effect-then-raised ladder, discriminated IN TASK 3 with no probe and no `record_entry` | **`A4-R11-6`: Task 3 shipped the immediate path's semantics with every discriminator in Task 4** |
| **(k5)** | the chained `__context__` signal is DETECTED, with NO probe -- the Task-3 discriminator | **`A4-R10-3` -- a task that ships a predicate and schedules every test of it in the NEXT task goes green against `return False`** |
| **(k4a)-(k4b)** | the deferred path's two rollback-FAILURE sequences -- **DETECTION and OUTCOME both pinned** | **`A4-R9-2` (RD, 2026-09-07): rule (i) is literal on this path too; each row fails an implementation with no detection, which the OUTCOME-only version certified** |

**REGRESSION CONTROLS -- a separate roster, identical under both paths by design:**

| id | subject | what it protects |
|---|---|---|
| **(pr1)-(pr5)** | the probe's five design requirements, each with the assertion that would go red if it were dropped: the 2000 ms bound, a contained close AFTER a good read, the ticker corroboration S7.7 rests on, no-token-no-probe, and **the probe cannot CREATE a database** | **`A4-R11-7` + `A4-R11-10`: four decisions with no discriminator, and one that let an observe-only mechanism write to disk** |
| (i) | the belt still refuses a same-ticker retry | the belt is not mistaken for the fix, and is not weakened by it |
| **(RD-a5)** | a body that raises never reaches the probe, on BOTH paths | **the CALLER-SIDE obligation the `body_completed` removal rests on (gotcha #31)** |
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

### (m3) The backup gate -- **THREE assertions, because the first one alone proved the least**

> **STRENGTHENED 2026-09-07 (`A4-R11-8`, the round-11 MAJOR most consequential for the LIVE
> database**, which crosses this migration exactly once holding real money-bearing trades). The
> previous version of this row called the gate FUNCTION directly. **A gate that is written and never
> WIRED passes it**, and so does an expected-table set that omits one of 0037's three tables --
> and S6's live witness then compared the backup against "the expected set", which makes the check
> confirm the constant against itself rather than against the database.

**(m3a) THE GATE'S OWN BEHAVIOUR, called directly.** `_phase22_arc_a4_backup_gate` writes a
`swing-pre-22a4-migration-<ISO>.db` and verifies it when `current_version == 37 and target_version
>= 38`; it does **nothing** at `current_version == 36` (STRICT equality, the
`pre_version == (target - 1)` gotcha) and raises `MigrationBackupRequiredException` for an in-memory
source. **Pre-fix:** the function does not exist. The 36-and-target-38 case is the one that
distinguishes a `<=` gate from an `==` gate and is asserted explicitly.

**(m3b) `run_migrations` INVOKES IT -- asserted through the RUNNER, and asserted to be
LOAD-BEARING.** Build a v37 file-backed database, then call
`run_migrations(conn, target_version=38, backup_dir=tmp)` and assert exactly one
`swing-pre-22a4-migration-*.db` appears in `tmp`. **And the discriminating half, which mere
appearance does not give:** monkeypatch the gate to raise `MigrationBackupRequiredException`, call
the runner again on a fresh v37 database, and assert the exception propagates **and
`SELECT version FROM schema_version` still reads 37** -- i.e. **0038 did not run.**
**Against a gate that is defined but never called from `run_migrations`:** the first assertion fails
on the missing file, and the second fails because the migration applies anyway.
*The second is the one that matters: a gate whose failure does not STOP the migration is decoration,
and nothing in the previous row could tell the two apart.*

**(m3c) THE EXPECTED-TABLE SET IS PINNED AGAINST A REAL v37 DATABASE, NOT AGAINST ITSELF.** Assert
`PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES` **EQUALS** the table set measured off a freshly
migrated v37 database (`SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE
'sqlite_%'`). **Against a set that omits any of 0037's three tables --
`candidates_immutability_epoch`, `latch_order_mandate_links`, `fill_envelope_identity`
(`swing/data/migrations/0037_latch_order_mandate_links.sql:121`, `:289`, `:518`)** -- the equality
fails naming the missing member. *Derive the new constant as
`PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES | {the three}`, the deterministic-derivation shape the
Phase-8 set already uses (`swing/data/db.py:382`), so provenance is readable; then let this row
prove the derivation rather than trusting it.*

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

### (m8a)-(m8d) THE CORRECTOR REFUSES `attempt_id` -- typed, order-independent, DELIVERED, and on EVERY OPERATOR SURFACE

**FOUR named rows** (three from `A4-R7-3`, which caught Task 1b's test classes having no ids, no
pre-/post-fix values, no exact result shapes and no files; **the fourth added by `A4-R9-5`**). They
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

**(m8d) THE TIER-3 OVERRIDE PATH -- the surface the preflight never reached** (`A4-R9-5`). Drive
`apply_tier3_override` with an `operator_truth_value` of TWO keys, an ordinary journal field FIRST
and `attempt_id` LAST, against a correction row whose `affected_table` is `trades`.
**Post-fix:** exactly `ImmutableJournalFieldError`; on a connection instrumented with
`set_trace_callback`, **ZERO `INSERT INTO reconciliation_corrections`, ZERO `UPDATE
reconciliation_corrections`, and ZERO `UPDATE trades` statements were issued** -- the refusal
precedes step 4.
**Against a backstop-only implementation (the check in `_update_journal_field` alone -- i.e. exactly
what Task 1b shipped before this row existed):** the SAME typed error is raised and the SAME
persisted state is observed, **because the public entry point's own ROLLBACK erases the
difference** -- so a state-only assertion certifies a backstop-only implementation and this row
would be vacuous. **The statement counts are the discriminator, and they read `>= 3` there** (the
correction INSERT, the supersession UPDATE, the first field's UPDATE). *This is the counterfactual
requirement applied to a rollback: when the outcome is identical by construction, assert the work
that was done, not the state that survived.*
**A second arm, on the module's own documented composition surface:** call
`_apply_tier3_override_inner` directly inside a caller-held transaction (its docstring's invitation),
then roll back nothing and read the table. **Post-fix:** zero `reconciliation_corrections` rows.
**Against backstop-only:** a correction row EXISTS and the prior head's
`superseded_by_correction_id` has MOVED -- persisted, because on this surface nobody rolled back.
**Pre-fix (Task 1 landed, Task 1b not yet):** `sqlite3.IntegrityError` from the trigger, after the
same writes.

**Files:** `tests/trades/test_22a4_corrector_refusal.py` (m8a, m8b, **m8d**) and
`tests/web/test_routes/test_22a4_corrector_refusal_delivery.py` + the CLI half in
`tests/cli/test_22a4_corrector_refusal_cli.py` (m8c). **Task 1b's declared first red is (m8a)'s
`sqlite3.IntegrityError`.**

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
import the entry service).
**Post-fix, both variants -- AND THE ASSERTION IS WHAT THE v37 DATABASE CAN ACTUALLY ANSWER**
(`A4-R8-3`: the previous text asserted `attempt_id IS NULL` **on a v37 database, where SQL naming
that column raises `OperationalError: no such column`** -- the migration is what creates it, so the
declared post-fix value was impossible and Task 1 could not have reached its declared green):
**row count 1, the insert returned an id, and `PRAGMA table_info(trades)` does NOT contain
`attempt_id`.** If the NULL reading is wanted, it is a SECOND step -- migrate that same database to
v38 and then assert the legacy row reads NULL -- and it is written as such rather than folded into
the v37 assertion. **The alternative implementation this excludes** is one that raises: that
would make the identity apparatus able to FAIL an entry, which S2.1's whole containment posture
forbids, and the consequence of dropping is exactly today's behaviour (the probe is schema-aware and
answers ABSENT, so the caller re-raises as it does today).

### (r3) A malformed token is refused BEFORE any write

**SEVEN malformed values, and the last three are the ones `A4-R9-1` added:** `attempt_id=""`,
`attempt_id="short"`, a 37-character string, **a 36-BYTE `bytes` value**, **a 35-character string
followed by an embedded NUL (`"0" * 35 + "\x00"`)**, **a 36-character string containing a LONE
SURROGATE (`"\ud800" + "0" * 35`)**, and **an UPPERCASE canonical uuid4 string**
-> `ValueError` from the repo, and `SELECT COUNT(*) FROM trades` is **0** (the row-count half is what
distinguishes a pre-write guard from a post-write one).
**The `bytes` case pins the `isinstance`
half of the validator** (`A4-R7-1`): a 36-byte `bytes` passes a bare `len(...) == 36` in Python
exactly as a BLOB passes `length()` in SQLite, so a length-only validator would let it through to
the CHECK -- or, on a tree whose CHECK is also length-only, all the way into the index.
**THE THREE NEW CASES EACH DEFEAT A DIFFERENT LAYER, WHICH IS WHY THREE AND NOT ONE** (`A4-R9-1`):
- **NUL:** Python `len` = 36, SQLite `length()` = **35**, so the value clears the old predicate and
  is refused by the **CHECK**, as an `IntegrityError` raised from inside the money-bearing INSERT.
- **LONE SURROGATE:** Python `len` = 36 and it never reaches the CHECK at all -- `sqlite3` raises at
  **PARAMETER BINDING**, a layer BELOW the CHECK that a plan reasoning only about the CHECK cannot
  see.
- **UPPERCASE:** it satisfies the CHECK and BINDS cleanly, and is refused only by the
  canonical-round-trip clause. It is here because `'A...'` and `'a...'` are DIFFERENT text keys, so
  a mint that ever returned upper-case hex would defeat `ux_trades_attempt_id` -- the index S7.8
  says catches a live duplicate -- **silently, with every other assertion in this suite green.**
**Against the OLD `isinstance(str) and len == 36` predicate:** the first four still fail correctly
and **all three new cases PASS the validator**, then produce, respectively, an `IntegrityError` from
the CHECK, a binding error, and a silently index-defeating row. **That is the discrimination: the
row is not "more cases", it is three layers the old predicate could not reach.**
**Pre-fix, concretely rather than "n/a":** `insert_trade_with_event` has no `attempt_id` keyword, so
the call raises `TypeError` for all seven.

### (r7) THE PROBE IS SCHEMA-AWARE -- asserted directly, on a v37 database

**Why this row exists (`A4-R8-5`): nothing tested it.** `(r2)` exercises only the WRITE side's drop;
`(f)` never reaches the probe because there is no database path; every settlement row runs on v38.
**So an implementation that unconditionally executes `WHERE attempt_id = ?` passes the entire suite:**
`_settle_by_attempt_identity` contains the resulting `OperationalError`, re-raises the original
commit error, and every high-level assertion still holds -- while the advertised schema-aware ABSENT
branch does not exist and S7.5's stated consequence ("the probe answers ABSENT, so the caller
re-raises as it does today") is untested.

**Post-fix:** on a v37 database, `find_trade_id_by_attempt_id(conn, tok)` returns **`None`, WITHOUT
raising**. **Pre-fix / against the unconditional implementation:** it raises
`OperationalError: no such column: attempt_id`. **The distinction is not cosmetic:** the suite must
be able to tell ABSENCE from INTERNAL PROBE FAILURE, because those two produce the same caller-facing
outcome and only one of them is the designed behaviour.

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

### (r6) The IntegrityError mapping no longer mis-labels -- **RD's attached pin for S7.7 half A**

**THIS ROW IS LOAD-BEARING FOR A DIRECTOR'S RULING, which is why it asserts a POSITIVE TYPED SURFACE
rather than the absence of noise** (RD, 2026-09-06). S7.7 half A's "loud AND legible" holds only in
combination with S2.5's narrowing, so the narrowing gets a discriminating pin.

Two rows with the same non-NULL token through `record_entry`'s own inner path ->
**`sqlite3.IntegrityError` propagates, and the assertion is on its TYPE and its MESSAGE**
(`UNIQUE constraint failed: trades.attempt_id`) -- **NOT on the absence of
`DuplicateOpenPositionError`.** A row written as *"no `DuplicateOpenPositionError` was raised"* would
**pass an implementation that raised nothing at all**, which is the vacuous-negative shape this
project has been caught by before; asserting the typed surface cannot pass that way.
And a genuine same-ticker open duplicate still raises `DuplicateOpenPositionError` naming the ticker.

**Pre-fix (the loose match plus the new index):** the first case raises
`DuplicateOpenPositionError("Already an open position in AAA (race-detected)")` **over a ticker with
no open position** -- loud, and mislabelled as the position race S7.7 half A depends on it not being.
**MEASURED:** both SQLite messages, so the assertion is written against the real strings.

---

### (RD-a1) THE PROBE IS NOT CALLED WHEN THE ROLLBACK RAISED

**THREE fixtures, because a rollback can fail in TWO ways and RETURN-WITHOUT-EFFECT in a third, and
each admits or refuses the probe differently** (`A4-R2-7` added the second; `A4-R7-8` added the
third; `A4-R8-2` caught that this paragraph still said "TWO" and that Task 4 still scheduled only
"BOTH shapes", which would have permitted omitting the ONLY fixture that discriminates round 7's
re-read correction):
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
service no longer consults, and the capture would silently record nothing. **Task 4 additionally
requires the import to stay in that established style** (it moved there with its first consumer when
Task 2 was withdrawn -- `A4-R8-6`), so the patch target and the code style are
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

### (RD-a4) THE PREDICATE'S FOUR-ROW MATRIX, EACH CELL COMPUTED UNDER BOTH PATHS

**REBUILT 2026-09-07 FROM A ONE-ROW PIN INTO A FOUR-ROW MATRIX (RD, on `A4-R11-2`), AND THE REASON
IS AN INCIDENT RATHER THAN A PREFERENCE.** The previous version of this row pinned ONE case -- the
ambient-`except` false positive -- and asserted it as a declared COST. When the orchestrator ran
RD's validity pin for that ruling it executed the `inside_except=False` leg only and reported the
result as confirming a scope argument that was entirely about the `inside_except=True` leg. **RD's
words, kept because they name the obligation: *"That rule's violation is exactly how the one-row pin
passed a false premise to me; the repaired test is the apology that compiles."*** So the row is now
a MATRIX over the two independent axes -- `inside_except` and `chained` -- **and every cell asserts
the predicate's output under BOTH the pre-fix and the post-fix predicate**, which is the recipe's
compute-it-under-both-paths rule applied to a truth table rather than to a single number.

**THE AXES.** `inside_except`: whether `record_entry` is called with a live handled exception on the
thread (`sys.exc_info()[1] is not None`, ASSERTED ON THE FIXTURE ITSELF so a fixture that stops
establishing the ambient context fails loudly instead of turning cells green). `chained`: whether
`__exit__`'s own rollback ALSO failed -- the proxy shape (k4a)/(k4b) specify, raising the rollback
error from inside the `except` handling the commit error, so `__context__` is set by the interpreter
exactly as `_PyErr_ChainExceptions1` sets it.

**THE MATRIX. MEASURED BY EXECUTION 2026-09-07, CPython 3.14.2 / sqlite3 3.50.4** -- these are the
values the test asserts, not values derived from the source:

| # | `inside_except` | `chained` | `escaping.__context__` | is it `ambient`? | **PRE-FIX** (bare `__context__ is not None`) | **POST-FIX** (base slot, non-None, `is not ambient`) |
|---|---|---|---|---|---|---|
| 1 | False | False | `None` | -- | **False** | **False** |
| 2 | False | True | the COMMIT `OperationalError` | no | **True** | **True** |
| 3 | **True** | False | the ambient `ValueError` | **yes** | **True** -- THE FALSE POSITIVE | **False** -- the amendment's whole subject |
| 4 | **True** | True | the COMMIT `OperationalError` | no | **True** | **True** |

**READ THE MATRIX AS A DISCRIMINATOR, WHICH IS THE ONLY REASON TO HAVE ONE:** rows 1, 2 and 4 are
IDENTICAL under both predicates, so **row 3 is the entire delta** -- and a matrix in which only one
cell moves is the honest statement that the amendment is narrow. **Row 4 is the row that proves the
nested case composes without a branch:** the ambient is live AND the rollback failed, and the
predicate still answers True, because `__exit__` chains the COMMIT error at the FIRST link and the
first link is the only one the predicate reads.

**WHAT EACH ROW ASSERTS THROUGH `record_entry`, not merely on the predicate:**
- **rows 1 and 3** (rollback OK): `outcome.cleanup_raised` is **False**, `_durability_probe` is
  called **ONCE**, and `record_entry` returns SUCCESS with the lost-commit warning over the durable
  row. **Row 3 is the one that would RE-RAISE under the pre-fix predicate**, and it additionally
  asserts `COUNT(*) = 1` on a fresh connection, because the cost of getting this wrong in either
  direction is measured against the ledger and never against the warning text.
- **rows 2 and 4** (rollback failed): `outcome.cleanup_raised` is **True**, the probe call count is
  **0**, `record_entry` RE-RAISES, and a fresh connection sees **0** rows.
- **every row** asserts `sys.exc_info()[1] is not None` (rows 3-4) or `is None` (rows 1-2) INSIDE
  the fixture before `record_entry` is entered.

**THE FIXTURE.** Rows 1 and 3 use the (c) shape -- deferred path, body completes, commit's own
return LOST, the row LANDED. Rows 2 and 4 use the (k4a) proxy. The `inside_except` axis is the same
call wrapped in `try: raise ValueError(...) except ValueError:`.

**THE PREDICATE'S OTHER AXIS -- THE SUBCLASS DATA DESCRIPTOR (`A4-R11-1`) -- IS (k7a)-(k7b), IN
TASK 3, AND NOT THIS ROW.** The base-slot read SHIPS in Task 3, so its discriminator belongs there;
scheduling it here would have left Task 3 green against `escaping.__context__` (`A4-R11-6`'s class,
caught by the inverse schedule check). The measurements are recorded here because this is where the
predicate's truth table lives, and (k7a)-(k7b) execute them. **MEASURED by execution 2026-09-07 on
the same interpreter:**

| subclass of `sqlite3.OperationalError` | base-slot `__context__` | **PRE-FIX** bare read | **POST-FIX** |
|---|---|---|---|
| `__context__` is a `@property` returning `None` | the real `OperationalError` | **False** -- a FALSE NEGATIVE that ADMITS the probe | **True** |
| `__context__` is a `@property` that RAISES | the real `OperationalError` | **raises `RuntimeError`, replacing the escaping exception** | **True** |

**Against the pre-fix predicate the first row ADMITS a probe on a wounded connection** -- the
`A4-R9-3` window, rebuilt -- **and the second replaces the operator's evidence with the attacker's
exception.** (k7a)-(k7b) drive both through `record_entry`, land their no-probe halves in Task 3,
and gain their probe-call-count-of-ZERO assertions in Task 4.

### (RD-a5) THE CALLER-SIDE OBLIGATION THE `body_completed` REMOVAL RESTS ON

**Why this row exists.** Removing the field is sound *only because* `record_entry`'s
`if result is None: raise` runs first. **That is a claim about the CALLER, and gotcha #31 is
explicit that a caller-side obligation is pinned by a test rather than described in a comment** --
the callee's absence is what the deleted field's tests would have pinned, and it is the wrong half.

**Fixture:** `_record_entry_inner` raises after its INSERT (the body-raised shape), on **BOTH**
paths -- `_reserve=True` and `_reserve=False`.

**Post-fix:** `result` is None, so the handler's FIRST branch re-raises; **`_durability_probe`'s
sentinel call count is 0** and `_settle_by_attempt_identity`'s is 0; what escapes is the BODY's own
exception with its type, args and `__cause__` unchanged; a fresh connection sees **0** rows.
**Against an implementation that moved the settle above the `result is None` branch** (the shape the
removal would be unsound under): the probe is called, and on the immediate path -- where the rollback
is the wrapper's own and `resolution` reads `rolled_back` -- the gate would reach the probe on a
transaction whose body never finished. **Pre-fix:** identical to post-fix, because the guard is
PRE-ARC -- **so this row is explicitly a LOCK, listed in the regression-control roster and not
counted as evidence that clause 2 works** (`A4-R1-8`'s separation, applied to a row this pass
added).

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

**ELEVEN CONTAINED-FAILURE VARIANTS PLUS ONE INTERRUPT-PROPAGATION CONTROL -- TWELVE SCENARIOS, AND
THE COUNT IS STATED ONCE AND ONLY ONCE.** (`A4-R6-9` caught the first version saying "six" and
enumerating seven; `A4-R6-4` then appended a "NINTH" beneath a heading still reading "eight
scenarios", so the same defect was live again one round later, in the fix for it. **The lesson
applied here rather than restated: the roster below is the manifest, and the number in the heading is
derived from it -- if they ever disagree, the roster wins and the heading is the bug.**)

**The eleven contained failures.** (1) `_mint_attempt_token` RAISES. It RETURNS: (2) `""`;
(3) `"short"`; (4) a 37-character string; (5) `b"..."` (bytes of some other length); (6) `None`;
(7) a 36-BYTE BLOB (`A4-R6-4` -- passes a bare length check); (8) a 35-character string plus an
embedded NUL; (9) a 36-character string containing a lone surrogate; (10) an UPPERCASE canonical
uuid4 string (**(8)-(10) added by `A4-R9-1`; each defeats a different layer -- the CHECK, the
parameter BINDING, and the UNIQUE index's text key -- and (r3) states which**). And (11)
`_resolve_main_db_path` RAISES.
**Plus (12), a CONTROL of the opposite polarity:** a `KeyboardInterrupt` from the mint PROPAGATES
and is not swallowed.

**The malformed-RETURN variants are the ones that matter**: without result validation in
`_begin_attempt_identity` (S2.1) the value reaches the repo, trips the pre-write `ValueError` that
(r3) requires, and FAILS AN ENTRY THAT WOULD HAVE SUCCEEDED -- the exact outcome the containment
exists to prevent, arriving through the containment's own blind spot. **And (8)-(10) are why S2.1's
validator is now `uuid.UUID`-parsing rather than length-checking**: under the old predicate those
three are not contained at all, they are ADMITTED, and the entry then fails inside the INSERT.
**Post-fix, all ELEVEN contained variants:** `record_entry` SUCCEEDS; the row is
present with `attempt_id IS NULL` (the raise and the nine malformed returns) or with a valid token but
no probe available (the path variant); and a WARNING is logged in each case.

**AND EACH OF THE TWO `<contained WARNING>` SITES IN `_begin_attempt_identity` IS ALSO RUN WITH A
RAISING LOG HANDLER** (`A4-R8-5`'s sibling `A4-R8-4`). Round 7 added hostile-sink coverage for the
REPO's pre-v38 warning and **left the SERVICE-side warning arms tested only with a working
logger** -- so a plain `log.warning(...)` at either of them passes every variant above and then, when
a handler raises, **converts a contained failure into a failed entry**, which is the precise claim
S2.1 makes and this row exists to defend. **Both arms route through ONE containment helper**
(so there is one thing to get right, not two), and each is asserted with a raising handler:
the entry still SUCCEEDS with the expected degradation.
**THE COUNT WAS THREE UNTIL 2026-09-07 AND THE FIX FOR `A4-R9-1` IS WHAT MADE IT TWO**
(`A4-R10-6`). S2.1 used to carry a SEPARATE arm for a malformed mint RETURN; collapsing that check
into the `validate_attempt_id` call inside the existing `try` merged two arms into one, and this
roster went on demanding coverage of a branch that no longer exists. **Read S2.1's pseudocode, not
this sentence, if they ever disagree: the sites are the `except Exception:` after the mint-and-
validate `try`, and the `except Exception:` after `_resolve_main_db_path`. TWO.** *A count in a test
roster is a manifest of branches, so a fix that removes a branch owes this roster an edit -- which
is the residual class this arc has now paid for at every level including its own bookkeeping.*
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

### (pr1)-(pr5) THE PROBE'S FIVE DESIGN REQUIREMENTS, EACH WITH AN ASSERTION THAT DISTINGUISHES IT

**Why this block exists (`A4-R11-7`, plus `A4-R11-10`).** S2.3 states five properties of
`_durability_probe` as design decisions -- a bounded busy timeout, a contained close, ticker
corroboration, a token precondition, and (as of 2026-09-07) a fail-closed open -- **and four of them
had no row in this roster that would go red if they were dropped.** A design decision with no
discriminating assertion is a paragraph, and this plan's own standard for a paragraph is that it
does not ship.

**(pr1) THE BUSY TIMEOUT IS BOUNDED, AND THE BOUND IS CAPTURED.** Monkeypatch
`swing.trades.entry.open_connection` (the name as bound in the CONSUMING module -- (RD-a2)'s rule)
and record its kwargs. **Post-fix:** it receives `busy_timeout_ms=_PROBE_BUSY_TIMEOUT_MS`, and the
constant is **2000**. **Against an implementation that simply omits the kwarg:** the call carries
`DEFAULT_BUSY_TIMEOUT_MS`, **30000** (`swing/data/db.py:92`) -- *a lost-commit probe that hangs a
money-bearing web submit for thirty seconds, on a path whose fallback is the alarm anyway.* The row
asserts the NUMBER and not merely that some timeout was passed, because a silent restoration of the
project default is exactly the shape a value-free assertion cannot see.

**(pr2) A `close()` THAT RAISES AFTER A SUCCESSFUL READ DOES NOT DISCARD THE READ.** The
monkeypatched repo reader returns the row normally; the probe connection's `close()` then raises.
**Post-fix:** `_durability_probe` returns the row, `record_entry` settles, and SUCCESS is returned
with the lost-commit warning; the close failure is reported through `log_contained_note` on the
escaping exception rather than replacing anything. **Against a naive `finally: probe.close()` with
no containment:** the close's exception propagates out of the `finally`, the valid result is thrown
away, and `record_entry` re-raises **over a durable entry** -- which is clause 1's own subject
arriving inside the machinery built to serve it. *(g) is the neighbouring row and is NOT the same
one: (g) drives a probe that fails to READ; this one drives a probe that read SUCCESSFULLY and then
failed to tidy up, and only this ordering distinguishes "contained close" from "contained probe".*

**(pr3) THE RIGHT TOKEN ON THE WRONG TICKER IS THE ALARM -- AND S7.7's SAME-TICKER BOUND RESTS ON
THIS ROW.** Plant, by raw INSERT on a second connection, a committed row carrying OUR token with a
DIFFERENT ticker. **Premise asserted first:** the probe's returned tuple's ticker is not
`req.ticker`. **Post-fix:** `_settle_by_attempt_identity` returns `None`, `record_entry` RE-RAISES
the original, and an ERROR record names the mismatch. **Against an implementation that omits the
corroboration** (S2.4 condition 4's second half): the settle SUCCEEDS and returns a trade id for a
ticker the operator did not enter. **Every other row in this roster would pass that
implementation**, which is the finding's sharp edge: the accepted limitation at S7.7 bounds the
false-confirm probability by requiring an RNG collision **AND** the same ticker, and without this
row nothing in the suite holds up the second conjunct.

**(pr4) NO TOKEN -> NO PROBE.** Drive the (c) shape with the mint contained-failed, so
`attempt.token is None` while the database path resolved (the `e2` apparatus-cannot-fail-an-entry
path produces exactly this). **Post-fix:** `_durability_probe`'s sentinel call count is **0**,
`record_entry` re-raises. **Against an implementation whose condition 3 checks only the database
path:** the probe runs with `attempt_id = None`, and `WHERE attempt_id = ?` bound to `NULL` matches
nothing in SQL -- **so the defect is INVISIBLE in its outcome and visible only in the call count**,
which is why this row asserts the count rather than the result.

**(pr5) THE PROBE CANNOT CREATE A DATABASE** (`A4-R11-10`, VERIFIED AT THE CODE). Point the resolved
database path at a name that does not exist. **Post-fix:** the URI open raises
`sqlite3.OperationalError: unable to open database file`, the failure is CONTAINED,
`record_entry` re-raises the ORIGINAL, **and no file exists at that path afterwards**.
**Pre-fix (a bare path handed to `open_connection`):** `sqlite3.connect` CREATES the file
(`swing/data/db.py:126`), the probe answers ABSENT, and the arc has written a zero-table database
onto an already-failing money path **by the mechanism whose entire purpose is to observe without
acting.** The no-file assertion is the discriminating one; the exception type alone is not, because
a created-then-empty database also produces no row.

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
that, not this arc); `result` is not None inside `record_entry`, `outcome.committed` is False, and
**`outcome.resolution == "not_needed"`**; nothing partial is visible to a fresh connection; the
ORIGINAL exception propagated. **Pre-fix:** `_CommitOutcome` has no `resolution` field at all, so
the assertion raises `AttributeError`. **The discriminator is the OBSERVATION, not the connection
state** -- which is the honest statement, because the connection state was never this arc's to fix
on that path.

### (k2) THE DEFERRED PATH'S EXCEPTION IDENTITY IS UNCHANGED -- a LOCK assertion

> **Also rewritten after `A4-R1-2`,** and its polarity is INVERTED: the first draft declared a
> behaviour change here and routed it to CHARC. There is no change to declare, so this row now pins
> the ABSENCE of one.

> **REWRITTEN 2026-09-07 for the `_read_resolution` SPLIT** (`A4-R11-3`, `A4-R11-4`). The previous
> version drove *"the residual `_observe_resolution` rollback arm"*. **There is no such arm** -- the
> deferred path performs no rollback -- so the fixture that named it is replaced by the one that
> produces the same flag through the only route left.

Drive the pre-arc path with the (k4a) proxy: the body completes, `__exit__` raises a commit error,
performs the REAL rollback, and then raises a rollback error from inside the `except` handling the
commit error, so `__context__` is set by the interpreter.

**Post-fix:** the exception `__exit__` produced escapes UNCHANGED -- **not** re-wrapped, **not** a
chained `raise ... from ...` added by us -- with its type, args, `__cause__` and `__context__`
exactly as Python left them; `outcome.cleanup_raised` is True; **and the deferred path emitted NO
log record and issued NO rollback of its own** (assert the caplog handler saw nothing from this
module, and that the proxy's `rollback` call count did not increase after `__exit__` returned).
**Pre-fix:** the original escapes too (there is no observation at all) -- so **the discriminating
assertion is `cleanup_raised is True`**, and the other three are LOCKS. They fail an implementation
that copies the immediate path's `raise cleanup_error from write_error` onto the deferred path
(which the first draft would have shipped) **and one that keeps this sweep's retired retry arm**
(which the settling sweep DID ship, and `A4-R11-3` caught).

**THE ROW IS SPLIT ACROSS TWO TASKS, AND SAYING SO IS THE POINT** (`A4-R9-7`, generalised -- the
finding named Task 3's (k3b)/(k4a)/(k4b), and this row has the same defect one assertion deep).
The version before that also asserted *"and the probe is NOT called"*, naming a ZERO call count among
its discriminating assertions. **`_durability_probe` does not exist until Task 4**, so that
assertion cannot be written in Task 3 and the row as specified could not have gone green there.
**Task 3 ships (k2) with the observation assertions above. Task 4 ADDS the probe-call-count-of-ZERO
assertion to the same test**, where the sentinel it patches exists. Both task lists say so.

### (k5) THE CHAINED SIGNAL IS DETECTED -- the Task-3 discriminator for `_exit_rollback_failed`, with NO probe

**Why this row exists (`A4-R10-3`, and it is that finding's structural fix rather than its
workaround).** `_exit_rollback_failed` ships in Task 3, and every OTHER row that touches it --
(k4a), (k4b) -- also asserts a probe call count, so all of them need Task 4's `_durability_probe`.
**Task 3 would therefore have gone green against `def _exit_rollback_failed(e): return False`.**
This row is the assertion that does not need the probe: it asserts the SIGNAL, in the task that
ships the code producing it.

**Fixture:** the (k4a) proxy exactly -- deferred path, body completes, `__exit__` raises a commit
error, performs the REAL rollback, then raises a rollback error **from inside the `except` handling
the commit error**, so `__context__` is set by the interpreter as `_PyErr_ChainExceptions1` sets it
(SOURCE (S1)). **The fixture's own chaining is asserted first**
(`type(escaping.__context__) is sqlite3.OperationalError`), for the reason (k4a) gives.

**Post-fix:** `outcome.resolution == "not_needed"` (the rollback took effect, so `in_transaction`
reads False) **AND `outcome.cleanup_raised is True`** -- the two together are the point, and since
the `_read_resolution` split (`A4-R11-4`) the deferred path has **no rollback arm at all**, so
**the flag can only have come from the chained exception.** *That used to be a property of this
FIXTURE (the retry arm happened not to run on it); it is now a property of the CODE, which is a
strictly better thing for a discriminator to rest on.* `record_entry` re-raises; a fresh connection sees **0** rows.
**Against `return False`:** `cleanup_raised` is False with `resolution == "not_needed"` -- the
`A4-R9-3` admitting state, which in Task 4 becomes a live false-confirm window. **Against the
`isinstance(sqlite3.Error)` predicate RD removed:** identical here (the context IS a `sqlite3.Error`),
which is correct -- this row discriminates PRESENCE of the detection, and **(RD-a4) is the row that
discriminates the two predicate SHAPES.**
**Pre-fix:** `_CommitOutcome` has no `cleanup_raised` field, so the assertion raises `AttributeError`.

### (k6a)-(k6b) THE IMMEDIATE PATH'S OBSERVATIONS, DISCRIMINATED IN TASK 3, WITH NO PROBE

**Why these rows exist (`A4-R11-6`), and the reason is the sweep's own rule failing on the other
path.** Task 3 ships the IMMEDIATE path's observation semantics -- the returning-arm re-read
(`rolled_back` vs `still_open`) and `cleanup_raised` from the wrapper's own rollback -- and every
row that discriminated them, (RD-a1)'s three fixtures, was scheduled wholly in **Task 4**, because
those rows also assert a probe call count. **So a naive Task-3 implementation that assigned
`rolled_back` whenever `rollback()` returned would reach Task-3 green**, which is precisely the
condition Task 3's own scheduling rule was written to forbid: *every task ships only code for which
an assertion IN THAT TASK distinguishes the shipped implementation from its naive substitute.* The
settling sweep applied that rule to the DEFERRED path -- splitting (k5) out for exactly this reason
-- **and never asked the same question of the IMMEDIATE one.**

**These rows need NO probe and NO `record_entry`.** They drive `_entry_transaction` DIRECTLY with an
explicit `outcome=_CommitOutcome()`, which is the wrapper's own contract and is entirely Task-3
material; the connection PROXIES they use are test helpers that name no production symbol, and
(RD-a1) reuses them in Task 4. *That is the general answer to the class: when a row cannot be
scheduled with its code because its discriminator names a later symbol, look for the discriminator
that does not -- do not move the code.*

**(k6a) THE RETURNING ARM THAT DID NOT TAKE EFFECT.** `immediate=True`; a proxy whose `commit()`
raises without landing and whose `rollback()` **RETURNS NORMALLY while leaving `in_transaction`
True`**.
**Post-fix:** `outcome.resolution == "still_open"` and `outcome.cleanup_raised is False`; the write
error propagates unchanged.
**Against the naive substitute** -- assigning `"rolled_back"` whenever `rollback()` returns:
`resolution` reads `"rolled_back"`, which in Task 4 ADMITS the probe under a falsely clean label.
**Pre-fix:** `_CommitOutcome` has no `resolution` field, so the assertion raises `AttributeError`.

**(k6b) THE ROLLBACK THAT TOOK EFFECT AND THEN RAISED, AND THE LADDER THAT MUST SURVIVE IT.**
`immediate=True`; the proxy performs the REAL rollback and THEN raises.
**Post-fix:** `outcome.cleanup_raised is True` **and** `outcome.resolution == "rolled_back"` -- the
two are different facts and the row asserts both; **and what escapes is the CLEANUP error with the
WRITE error as its `__cause__`** (`raise cleanup_error from write_error`), with the existing
took-effect cleanup message present in the logs.
**Against a naive substitute that infers the state from the raise** (`"still_open"`, or the first
draft's `"unresolved"`): the resolution assertion fails on a transaction that is resolved.
**AND AGAINST THE SHAPE `A4-R11-4` IS ABOUT** -- routing the immediate path through a shared helper
that CONTAINS its rollback failure: the escaping exception is the WRITE error with no `__cause__`,
and the row goes red. **That is the assertion which makes "the shared thing is the non-mutating
read, never the rollback" a test rather than a paragraph.**
**Pre-fix:** no `cleanup_raised` field -> `AttributeError`; the chained-escape half passes pre-fix
and is therefore a **LOCK**, listed as such and not counted as evidence that the observations work.

### (k7a)-(k7b) THE SUBCLASS-DESCRIPTOR ROWS -- **the base-slot read's Task-3 discriminator**

**Why these are their OWN rows and not two lines of (RD-a4)** (`A4-R11-6`'s class, found by the
strengthened `assertion_schedule_audit.py` **on this fix leg's own edit**, 2026-09-07). `_CONTEXT_SLOT`
and the base-slot read ship in **Task 3**, and the two subclass rows that discriminate them were
written into (RD-a4), which is scheduled in **Task 4** because its four matrix cells assert probe
call counts. **So Task 3 would have gone green against `escaping.__context__`** -- the exact
`A4-R11-1` defect, in the task that ships its fix. *The instrument that caught it is the inverse
check added in the same pass: "does the task that SHIPS a symbol contain any row that NAMES it?" It
had never been asked, and its first run indicted the pass that added it.*

**The split is (k5)'s and (k2)'s, applied again:** the halves that need no probe land in Task 3; the
probe-call-count halves are ADDED to the same tests in Task 4.

**(k7a) A `__context__` DATA DESCRIPTOR THAT LIES.** A `sqlite3.OperationalError` subclass whose
`__context__` is a `@property` returning `None`, raised as the rollback failure from inside the
`except` handling the commit error, so the real `OperationalError` IS in the base slot.
**Premise asserted first:** `BaseException.__dict__["__context__"].__get__(e, type(e))` is the
commit error while `e.__context__` is `None` -- *the fixture asserts the divergence it exists to
exercise, so a future CPython that closed the hole turns this row red instead of vacuously green.*
**Post-fix (Task 3):** `outcome.cleanup_raised is True` and `outcome.resolution == "not_needed"`.
**Against the bare attribute read:** `cleanup_raised` is False -- **a FALSE NEGATIVE, and in Task 4
that state ADMITS the probe and rebuilds the `A4-R9-3` window.**
**Task 4 ADDS:** `_durability_probe`'s sentinel call count is **0**.

**(k7b) A `__context__` DATA DESCRIPTOR THAT RAISES.** The same shape with a getter that raises
`RuntimeError`.
**Post-fix (Task 3):** `outcome.cleanup_raised is True`, and **what escapes `record_entry` is the
SUBCLASS instance with its own type and args** -- not the getter's `RuntimeError`.
**Against the bare attribute read:** the getter fires, its `RuntimeError` propagates, and the
operator's evidence about what actually failed has been replaced by the hostile exception. **That
second assertion is the discriminating one**; `cleanup_raised` alone cannot distinguish the two
implementations here, because the bare read never returns at all.
**Task 4 ADDS:** the probe call count of **0**.
*Note what these rows do NOT prove: the base descriptor runs no user code, so the getter never fires
under the shipped read and the ALARM-direction `except` arm in `_exit_rollback_failed` is NOT
exercised by either row. No construction found in this pass makes
`BaseException.__dict__["__context__"].__get__` raise. The containment is kept for the direction it
costs nothing to have and is declared UNTESTED rather than counted as covered.*

### (k4a)-(k4b) THE DEFERRED PATH'S TWO ROLLBACK-FAILURE SEQUENCES -- **the SIGNAL and the OUTCOME, both pinned**

**REWRITTEN 2026-09-07 for RD's `A4-R9-2` ruling (Branch A).** These two rows were written when the
plan believed `__exit__`'s rollback failure was UNOBSERVABLE, so they pinned only the OUTCOME. It is
observable (SOURCE (S1), MEASURED (6)), rule (i) is literal on this path, and **each row now asserts
BOTH: that the failure was DETECTED and that the probe was consequently NOT RUN.** *Keeping only the
outcome assertions would leave two rows that pass against an implementation with no detection at
all -- which is precisely the shape they were written under and must no longer certify.*

**THE FIXTURE FIDELITY REQUIREMENT, STATED BEFORE THE ROWS BECAUSE IT IS THE PRECONDITION FOR BOTH.**
The commit-fail arm cannot be driven natively (MEASURED (6a): the post-commit-failure rollback makes
ZERO progress-handler callbacks, and MEASURED (5): a `factory=`-installed Python `rollback()` is
never invoked by the C `__exit__`). **So both rows use a connection PROXY whose `__exit__` stands in
for CPython's, and a proxy that does not reproduce the chaining tests the proxy rather than the
code.** The proxy's `__exit__` MUST therefore raise the rollback error **from inside an `except`
block handling the commit error**, so that `__context__` is set by the interpreter exactly as
`_PyErr_ChainExceptions1` sets it in the branch SOURCE (S1) anchors (`connection.c:2399`, a
convenience against the UPSTREAM-pinned bytes SOURCE (S1) names by digest and URL):

```
def __exit__(self, exc_type, exc, tb):
    try:
        raise sqlite3.OperationalError("commit failed")     # the COMMIT error
    except sqlite3.OperationalError:
        <perform, or do not perform, the real rollback>
        raise sqlite3.OperationalError("rollback failed")   # __context__ is set here
```

**A test asserting this shape is part of the row, not a note about it:** each row asserts
`type(escaping.__context__) is sqlite3.OperationalError` **on the fixture itself** before asserting
anything about `record_entry`, so a proxy that silently stops chaining fails loudly instead of
quietly turning both rows green against a broken predicate. *This is the synthetic-fixture-vs-real-
emitter discipline applied to an interpreter behaviour rather than to a data shape: the emitter here
is CPython, and SOURCE (S1) is what the fixture is derived FROM.*

**(k4a) THE INTERNAL ROLLBACK TAKES EFFECT AND THEN RAISES.** The proxy performs the REAL rollback
and then raises. **Post-fix:** `conn.in_transaction` reads False so `_read_resolution` records
`resolution == "not_needed"`; **`_exit_rollback_failed` returns True and `outcome.cleanup_raised` is
True**; S2.4 condition 2 refuses; **`_durability_probe`'s sentinel call count is 0**; `record_entry`
RE-RAISES, and what escapes is the ROLLBACK's exception with the COMMIT's as its `__context__`
(Python's own behaviour, unchanged by this arc). A fresh connection sees **0** rows for the ticker.
**Against the pre-ruling shape in this same plan** (`resolution="not_needed"`, `cleanup_raised=False`):
the flag is False, the probe call count is **1**, and the probe reads ABSENT -- so the OUTCOME is the
same and **only the two new assertions discriminate.** That is the whole reason they are here: the
outcome-only version of this row certified the admitting implementation.
**And it is the row that closes `A4-R9-3`:** with the probe not run, there is no window in which a
concurrently-committed colliding token can be read and confirmed.

**(k4b) THE INTERNAL ROLLBACK RAISES BEFORE TAKING EFFECT -- the WOUNDED CONNECTION.** The proxy
does NOT roll back and raises; the writer's transaction stays OPEN holding its lock.
> **REWRITTEN 2026-09-07 for the `_read_resolution` SPLIT** (`A4-R11-3`, `A4-R11-4`): the retry arm
> this row described is GONE, and with it the "either route" hedge.

**Post-fix:** `_read_resolution` sees `in_transaction` True and records `resolution ==
"still_open"`, **issuing no rollback and no statement**; `cleanup_raised` is True **from the ONE
remaining route, `_exit_rollback_failed` on the chained exception**, and the row asserts that route
by ALSO asserting the proxy's `rollback` call count is unchanged after `__exit__` returned -- *the
previous version deliberately declined to say which arm set the flag, and there is now only one, so
declining would be hiding an assertion the code can support*; the probe's call count is **0**; the
ORIGINAL error surfaces; a fresh connection sees **0** rows.

**AND THIS ROW NAMES ITS OWN JOURNAL MODE, BECAUSE IT MAKES A FRESH-CONNECTION CLAIM WHILE THE
WRITER STILL HOLDS THE LOCK** (`A4-R10-4`'s rule, applied to the one row in this suite that had
dropped its blocking claim without noticing it still had a blocking-SENSITIVE assertion; found while
rewriting the row, 2026-09-07). The fixture database is built through `ensure_schema` and the test
**asserts `PRAGMA journal_mode` reads `wal`** before the `COUNT(*)` read. In WAL the fresh reader
sees the pre-transaction snapshot and answers 0; on a `delete`-mode database the same read would
block to the busy timeout and then raise `database is locked`, and the row would be red for a reason
that has nothing to do with its subject.
**AND THE JOURNAL-MODE CLAIM IS GONE** (`A4-R9-6`). The pre-ruling version asserted that the fresh
probe *"BLOCKS OR FAILS"* against the held lock, citing MEASURED (3) -- **a ROLLBACK-JOURNAL
measurement, while the live database is INFERRED-WAL (S2.2's label, `A4-R11-12`), where
MEASURED (2) admitted a fresh reader against an
open write transaction.** Under Branch A the probe does not run, so the row makes no claim about blocking in either
mode and the generalisation disappears rather than being parameterised. **The fail-closed probe
behaviour it used to carry is not lost:** it is (g)'s subject (a raising probe leaves the original
exception untouched) and (c2)'s (a real `database is locked`, on an explicitly rollback-journal
database), and both name their mode.
**Against the pre-ruling shape:** the probe runs, and on a WAL test database it neither blocks nor
fails -- it succeeds and reads ABSENT -- so the assertion as written would have been **wrong on the
live mode and right only on the fixture's**.
**Against this sweep's retired retry arm:** the proxy's `rollback` call count is 1 rather than 0,
and the row goes red -- which is the assertion `A4-R11-3` says was missing.

**Both rows are DEFERRED-PATH ONLY** -- on the immediate path the wrapper issues the rollback itself
and `cleanup_raised` is a direct observation of its own call, which (RD-a1)'s three fixtures already
cover.

### (k3a)-(k3b) THE `committed` OBSERVATION IS INSIDE THE RESOLVING SUITE -- static AND runtime

> **Rewritten after `A4-R2-6`, which disproved this row's founding claim and then weakened its
> assertion.** The first version said the window "cannot be simulated"; it can, with a
> `sys.settrace` line hook. And its AST predicate -- "inside SOME `try` whose handlers cover
> `BaseException`" -- is satisfied by an unrelated or nested `try/except BaseException: raise` that
> records no resolution at all, so the test could have blessed the very window it was written to
> close.

**(k3a) STATIC, and it now has TWO branch-specific predicates, because the two branches close the
window in DIFFERENT places** (`SS-9`). Parse `swing/trades/entry.py` with `ast`.

- **IMMEDIATE branch:** every assignment to `outcome.committed` inside `_entry_transaction`'s
  `immediate` arm sits directly in the `Try.body` of a `try` **whose handler both (i) writes
  `outcome.resolution` (directly or through the shared `_read_resolution` call) and (ii)
  re-raises.** **Against the first draft's shape:** the assignment is outside the `Try` -> fails.
  **Against a nested-decoy shape:** the enclosing handler writes no resolution -> fails, where the
  earlier weak predicate ("inside SOME try covering `BaseException`") passed.
- **DEFERRED branch -- THE BYTE-LOCK, ASSERTED RATHER THAN PROMISED.** The `if not immediate:` arm
  contains **NO `Try` node at all**, and its `With` node's body is **exactly one `Expr` whose value
  is a bare `Yield`**. **Against every shape this plan has proposed for that branch and then
  withdrawn** -- a `body_completed` assignment inside the `with`, an enclosing `try/except`, an
  `except ... as` binding -- the assertion FAILS. *This is the one claim three separate sections
  made in prose for three rounds while the pseudocode contradicted it; it is now a test.*
- **RECORD_ENTRY's side of the deferred window, in the same walk -- AND IT IS SPLIT ACROSS THE TWO
  TASKS, BECAUSE HALF OF IT NAMES A FUNCTION TASK 3 DOES NOT SHIP** (`SS-14`; the schedule-by-
  assertion audit caught this row, added in the same pass that wrote the rule, breaking the rule).
  - **TASK 3's half:** inside `record_entry`'s post-commit handler, the `_read_resolution` call
    sits under a branch guarded by `not outcome.committed` and `not _reserve`, **after** the
    `result is None` raise. **Against an implementation that observes unconditionally:** the call is
    not under that branch -> fails, and that is the `SS-9` shape this row exists to lock out.
    **THIS HALF IS REACHABLE ONLY BECAUSE TASK 3 SPLITS THE GUARD** (`A4-R11-5`): with the shipped
    `if result is None or not outcome.committed: raise` intact there is no `not outcome.committed`
    branch for the call to sit under, so the assertion could not describe any shape Task 3 creates.
    The walk therefore ALSO asserts the split itself -- the handler's first statement is
    `If(test=Compare(result is None), body=[Raise()])` with no `or` in its test -- **which is the
    assertion that turns "the guard is split" from a checklist line into a red test.**
  - **TASK 4 ADDS:** the same walk asserts `_read_resolution` is LEXICALLY BEFORE the
    `_settle_by_attempt_identity` call. **`_settle_by_attempt_identity` does not exist in Task 3**,
    so the assertion cannot be written there -- it would either fail or, worse, pass VACUOUSLY on an
    empty match set. **Against an implementation that consults the gate before observing:**
    `resolution` reads `"unattempted"`, the gate refuses, and a durable entry
    is reported as a failure -- the `A4-R1-3` defect relocated rather than fixed, which is exactly
    what a caller-side obligation test exists to catch (gotcha #31).
  - *A vacuous PASS is why this split matters more than the earlier four instances of the class.
    (k4a)/(k4b) scheduled in Task 3 would have FAILED loudly on a missing patch target; an AST walk
    that finds no `_settle_by_attempt_identity` node finds no ordering to violate and reports
    success. **The failure mode of scheduling-by-artifact is not always a red test.**

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
| `tests/trades/test_22a4_corrector_refusal.py` | **(m8a) typed refusal, (m8b) order-independence, (m8d) the tier-3 override path** -- Task 1b |
| `tests/cli/test_22a4_corrector_refusal_cli.py` + `tests/web/test_routes/test_22a4_corrector_refusal_delivery.py` | **(m8c) delivery through the UNCHANGED callers** -- Task 1b |
| `tests/trades/test_22a4_attempt_identity.py` | (e), (e2), **(w)**, **(w2) the mint contract**, (f), (g), (h), (r1)-(r3), (r6), **(r7) the schema-aware probe** |
| `tests/trades/test_22a4_clause2_settlement.py` | (RD-a1), (RD-a2), (RD-a3), **(RD-a4)**, **(RD-a5)**, (RD-b), **(RD-b2)**, (c2), (k), (k2), **(k3a)-(k3b)**, **(k4a)-(k4b)**, **(k5)**, **(k6a)-(k6b)**, **(k7a)-(k7b)**, **(pr1)-(pr5)**. **Task 3 lands (k), (k2), (k3a), (k5) and (k6a)-(k6b) and (k7a)-(k7b); Task 4 lands (k3b), (k4a), (k4b), (RD-a4), (RD-a5) and the probe-call-count assertions ADDED to (k2), (k7a) and (k7b)** (`A4-R9-7`, `A4-R10-3`, `A4-R11-6`) |

**Edited:**

| path | what |
|---|---|
| `swing/data/db.py` | `EXPECTED_SCHEMA_VERSION` 37 -> 38; `PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES`; `_create_pre_phase22_arc_a4_migration_backup`; `_phase22_arc_a4_backup_gate` + its call in `run_migrations` |
| `swing/data/repos/trades.py` | `insert_trade_with_event(..., attempt_id=None)` + the v38 INSERT branch + the shape guard + the pre-v38 contained drop; new `find_trade_id_by_attempt_id`; `ATTEMPT_ID_LENGTH`; **new `validate_attempt_id` -- the SINGLE validation authority, also called from `entry.py` (`A4-R9-1`)** |
| `swing/trades/entry.py` | `_mint_attempt_token`, `_AttemptIdentity`, `_begin_attempt_identity`, `_durability_probe`, `_settle_by_attempt_identity`, **`_read_resolution` (NON-MUTATING -- `A4-R11-4`)**, `_CONTEXT_SLOT`, **`_exit_rollback_failed` (`A4-R9-2`; its CALL relocated to the `record_entry` frame by `A4-R10-1` + `SS-9`)**; `_CommitOutcome` +2 fields (`resolution`, `cleanup_raised`) for THREE observations total; `_entry_transaction`'s IMMEDIATE path only -- **its `if not immediate:` branch is NOT EDITED AT ALL: no `try`, no `except`, no `as` binding, and `with conn:`'s suite stays exactly `yield`, asserted by (k3a)**; the post-commit handler, which gains BOTH deferred-path observations (Task 3) and then the settle branch (Task 4); the narrowed IntegrityError match; the declaration block rewritten |
| `swing/trades/reconciliation_auto_correct.py` | **THE ONE MODULE CHARC'S CONDITION WIDENED THE ENVELOPE BY, and it was MISSING FROM THIS TABLE until the 2026-09-07 per-location audit -- the manifest-with-a-hole class this plan already paid for twice.** Task 1b ONLY: the `_IMMUTABLE_JOURNAL_FIELDS` sibling set, `ImmutableJournalFieldError(ValueError)`, one message constant, and the shared predicate at THREE call sites -- `_preflight_reserved_transitions`, `_update_journal_field`, and the head of `_apply_tier3_override_inner` (`A4-R9-5`). **No other change and no sweep.** |
| `tests/trades/test_22a_task9_entry_wiring.py` | `test_CONTRACT_a_commit_whose_own_return_was_LOST_re_raises` rewritten in place as the settled-by-identity row (test **(c)**); its declaration prose kept as the record of what changed. **AND THE THREE ROWS THAT LIVE IN THIS FILE AND MUST STAY GREEN, named because the sweep found them scheduled with no file:** **(d)** the row-ABSENT re-raise (existing, gains the probe-called-once assertions), **(i)** the belt control, **(j)** the post-commit-STEP control |
| the version mirror family, **SEVEN spellings across ~30 files -- SIX a value-grep can see, plus SEMANTIC NAMES AND COMMENTS (`A4-R7-12`) which it cannot; NO total quoted** | 26 `EXPECTED_SCHEMA_VERSION == 37`; 11 bare-literal assertions; 4 `_current_version(...) == 37` (**2 of which stay at 37**); 1 chained (overlaps row 1); **1 INEQUALITY ceiling `versions[-1] <= 37` -- the L3 authorization gate**; and **15 `target_version=37` call sites -- 12 `run_migrations(...)` calls plus 3 direct `_phase22_arc_a_backup_gate(...)` calls -- of which 8 STAY PINNED and 7 gain a SECOND call to `EXPECTED_SCHEMA_VERSION`**. Counts are FLOORS and OVERLAP (`A4-R4-10`); the manifest is the greps plus a READ of every hit. The closure check is the full suite for the assertion families and a READ for the call sites, which fail nothing. |

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
- [x] **RIDER CLAUSE 1 -- RD's S7.7 DETECTION REASON. ROUTED BACK, RULED 2026-09-06, REPLACEMENT
      CORRECTED 2026-09-07.** He attached it as load-bearing
      and instructed stop-and-route if it failed. **It failed:** *"a rolled-back token leaves no row
      to confirm"* is true at the instant of rollback and does not survive to probe time
      (REPRODUCED). **He confirmed both replacement wordings** -- half A with S2.5's mapper
      narrowing attached as a precondition, half B with his absolute replaced by a probability
      statement -- **and round 9 then found half B's replacement wrong in his favour** (`A4-R9-4`:
      an equality where only a strict bound holds). **S7.7 now reads
      **AT MOST `P(collision)` by CONTAINMENT, with no independence assumed and no strictness
      claimed** -- RD's verbatim sentence, ruled 2026-09-07 on `A4-R10-2`, the FOURTH and final
      statement of it (`A4-R9-4`'s strict bound was the third and was not established either).**
      **Scope, so it does not read stronger than it is:**
      the counterexample lives ENTIRELY INSIDE the collision branch, so it refutes the REASON without
      changing the practical weight.
- [x] **RIDER CLAUSE 2 -- the `fork` RE-OPEN TRIGGER for the banked allocator. STRUCK, RULED
      2026-09-06.**
      MEASURED from CPython 3.14 source: `uuid4` is `int.from_bytes(os.urandom(16))` per call, with
      no process-local PRNG state, so a POSIX port that acquires `fork` would fire the trigger with
      no hazard present. Bare `fork` is struck; generator-change and entropy-duplication survive,
      **with VM snapshot-resume recorded as an INSTANCE of entropy-duplication and never as an
      independent trigger.**
      **THIS SECOND BOX EXISTS BECAUSE THE CHECKLIST PREVIOUSLY SAID "ONE CLAUSE" WHILE THE FRONT
      MATTER AND S9 SAID TWO** (`A4-R7-4`) -- an authorization checklist that can be marked closed
      without disposing of a director-owned clause is the claimed-fix-not-present class applied to
      governance.
- [x] **NEITHER CLAUSE AFFECTED THE RULING**, which rests on the no-reissue-path reading and
      verifies. What was open was wording RD owns, and he ruled it.
- [x] **A FOURTH ITEM WAS ROUTED AFTER ROUND 9 AND RULED 2026-09-07: `A4-R9-2`, BRANCH A.** Round 9
      falsified the plan's premise that `__exit__`'s internal rollback failure is invisible to the
      wrapper. **RD SELECTED Branch A: `with conn:` stays byte-identical and the wrapper inspects
      what propagates and its `__context__` chain at the except site; a detected rollback failure
      VOIDS the probe exactly as on the immediate path.** Rule (i) is now literal on both paths
      (S2.2, S2.4, S7.15), CHARC's routed item 8 is closed without either of its two options being
      taken, and **the composition window `A4-R9-3` closes STRUCTURALLY** -- with RD's own
      2026-09-06 item-3 acceptance recorded as SUPERSEDED rather than left standing beside it.

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
      side of the CHECK's length half) and **`validate_attempt_id(value)` -- THE SINGLE VALIDATION
      AUTHORITY, called by BOTH this repo's pre-write guard and `entry.py`'s
      `_begin_attempt_identity`** (S2.1 carries the body and the reasoning);
      `insert_trade_with_event(conn, trade, *, event_ts, rationale=None,
      attempt_id=None)` with the shape validation BEFORE any write -- **`None`, OR
      `validate_attempt_id(attempt_id)` -> `ValueError`.**
      **THE PREDICATE IS `isinstance(str)` + exact length + `uuid.UUID` PARSE + `version == 4` +
      CANONICAL ROUND-TRIP, and each clause is load-bearing** (`A4-R7-1` gave the first two;
      **`A4-R9-1` gave the rest**): a 36-byte `bytes` value satisfies a bare length test in Python
      exactly as a BLOB satisfies `length()` in SQLite; **a 35-character string plus a NUL has
      Python length 36 and SQL `length()` 35, so it clears a length test and is refused by the
      CHECK -- inside the money-bearing INSERT; a lone surrogate clears it and fails at PARAMETER
      BINDING, a layer below the CHECK; and an uppercase canonical uuid4 clears the CHECK entirely
      and defeats the UNIQUE index, which keys on the exact text.** A length-only validator is
      therefore not a weaker mirror of the CHECK, it is a mirror of only ONE of the three layers a
      bad token can fail at. The FOURTH era branch selected by
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
      S2.1 -- `Exception`-not-`BaseException` containment AND result validation **through the SAME
      `validate_attempt_id` the repo guard calls** (`A4-R9-1`: two hand-written predicates over one
      column are a mirror pair, and the drift that matters is the one where the SERVICE side admits
      what the WRITE side refuses -- which turns a contained degradation into a failed
      money-bearing entry), not a stub to be hardened later** (`A4-R7-2`: splitting the
      helper across two commits meant Task 1 either shipped a helper that could fail an otherwise
      successful entry, or Task 2 had no genuine red) -- and the
      `record_entry` -> `_record_entry_inner` -> `insert_trade_with_event(attempt_id=...)` threading.
      **Task 1's amended LOCK-A asserts a non-NULL token on BOTH rows, so without these the task
      cannot reach its own green.**
- [ ] **(e) and (e2) ARE SCHEDULED HERE TOO**, with the complete helper they test (`A4-R7-2`).
      **(e2) is written with ALL ELEVEN contained variants PLUS the `KeyboardInterrupt`
      propagation control -- TWELVE scenarios -- ENUMERATED FROM S3's roster so the two manifests
      cannot drift, and the COUNT is read off that roster rather than copied** (`A4-R6-9`,
      `A4-R6-4`, `A4-R9-1`; the count in this line has now been wrong twice, which is why S3 says
      the roster wins).
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
        produced by running the six VALUE greps and READING every hit -- **plus this seventh
        spelling, which no value grep reaches; S1.6 counts the family as SEVEN for that reason**
        (`A4-R10-7`).
- [ ] **Tests:** (m1)-(m6), **(m7) HALF 1 ONLY -- the schema trigger, direct UPDATE, with its
      MUTATION PROOF (remove the `CREATE TRIGGER`, show it RED, restore) required before this task
      can go green.** **(m7) HALF 2 -- the corrector's TYPED refusal -- belongs to Task 1b and MUST
      NOT be required here** (`A4-R6-3`: requiring the whole of (m7) before the task that implements
      the refusal made Task 1 unreachable in its own prescribed order, the amendment-induced
      dependency error the one-cycle-per-task rule exists to prevent). Also (r1)-(r4), (r6), **(r7) the schema-aware probe on a v37 database** (`A4-R8-5`), and
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
      **SEVEN** members (`A4-R7-10`; counted at `reconciliation_auto_correct.py:178-196` -- the range read `:178-190` and was short, MEASURED 2026-09-07 per `A4-R11-13`; and they
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
- [ ] **THE CHECK GOES IN THREE PLACES, SHARING ONE PREDICATE AND ONE MESSAGE** (`A4-R6-7` gave two,
      verified at the source; `A4-R9-5` found the third and it is the one an operator can actually
      reach): `_preflight_reserved_transitions`, `_update_journal_field`, **and the head of
      `_apply_tier3_override_inner`.** The module
      applies multi-field corrections SEQUENTIALLY and preflights the whole payload for exactly that
      reason -- its own comment says a per-field-only check made refusal depend on **JSON KEY
      ORDER**. A backstop-only implementation would execute an earlier field's UPDATE before
      discovering `attempt_id` second.
- [ ] **THE THIRD SITE, AND WHY IT IS NOT A SWEEP** (`A4-R9-5`, verified by reading the module).
      `_preflight_reserved_transitions` is called from **exactly one place** --
      `_handle_multi_field_correction:2655` -- and **NOT** from `_apply_tier3_override_inner:1608`,
      which is a SUPPORTED OPERATOR SURFACE (`swing journal ... --override`). That path INSERTs the
      new correction row (step 4), advances the prior row's `superseded_by_correction_id` (step 5),
      and only then walks `operator_truth_value` field by field (step 6) -- so with `attempt_id`
      LAST, two writes and every earlier field's UPDATE have already executed when
      `_update_journal_field`'s backstop refuses. **What that costs, stated exactly rather than
      dramatised:** the PUBLIC entry point `apply_tier3_override:910` owns `BEGIN IMMEDIATE` /
      COMMIT / ROLLBACK and rolls the whole thing back, so *"Nothing was written"* stays TRUE there;
      the exposure is (a) the module's own documented composition surface -- its docstring invites
      callers to *"compose via `_apply_tier3_override_inner` inside an existing tx"*, and such a
      caller owns the rollback -- and (b) the ORDER-INDEPENDENCE property (m8b) exists to establish,
      which is simply **not established on this surface** by a backstop.
      **The fix is scoped to the NEW immutable set ONLY: a call to the same shared predicate over
      `operator_truth_value` at the head of `_apply_tier3_override_inner`, before step 4.**
      **AND THE THREE SITES ARE A CLOSURE, NOT A ROSTER -- STATED WITH ITS METHOD** (`SS-16`,
      2026-09-07; the Demand-C lesson applied before a reviewer has to apply it). A list of call
      sites is the same instrument as the count it replaced unless something establishes it is
      COMPLETE. **`_update_journal_field` IS the closure**, and here is how that was established, by
      an AST walk of the module plus a grep for raw SQL rather than by reading the call sites the
      plan already knew about:
      **(1)** the module has FIVE public functions (`apply_tier1_correction`,
      `apply_tier2_resolution`, `apply_source_direction_resolution`, `apply_tier3_override`,
      `stamp_pending_ambiguity`);
      **(2)** `_update_journal_field` has exactly FOUR callers --
      `_apply_tier1_correction_inner:1348`, `_apply_tier3_override_inner:1749`,
      `_handle_single_field_correction:2542`, `_handle_multi_field_correction:2680`;
      **(3)** it is the ONLY site in the module that writes an OPERATOR-SUPPLIED journal field --
      the module's other `UPDATE trades` / `UPDATE fills` statements (`:1419`, `:2594`, `:2734`)
      each write the fixed `reconciliation_status` column and cannot carry `attempt_id`.
      **So the backstop reaches every operator surface, which is what the (m8a)-(m8d) heading
      claims, and the two EARLY checks are ORDERING refinements on the two surfaces where ordering
      is observable.** The other two need none, and the reason is per-surface rather than general:
      `_handle_single_field_correction` writes ONE field, so ordering is vacuous; tier-1 calls
      `_update_journal_field` at its step 5 and INSERTs its correction row at step 7, so the refusal
      precedes every write it makes. *Stated because "three call sites" read as an enumeration for
      four rounds, and an enumeration is exactly what this project has a standing rule against
      trusting.*
      **Calling `_preflight_reserved_transitions` there instead is DECLINED and the reason is
      CHARC's own bound:** that would newly refuse the SEVEN pre-existing `_RESERVED_JOURNAL_FIELDS`
      members earlier on this path too -- a behaviour change to shipped functionality, i.e. the sweep
      his condition explicitly excluded. **Refusing `attempt_id` early changes the behaviour of
      nothing that exists today**, because the column does not exist today.
- [ ] **Tests: (m8a), (m8b), (m8c) and (m8d)** -- the named S3 rows for this task (`A4-R7-3`): the
      typed service refusal, the multi-field preflight asserting ZERO journal UPDATEs, DELIVERY
      through the unchanged CLI (exit 2, no traceback) and web (status 400) callers, and
      **(m8d) the TIER-3 OVERRIDE path** (`A4-R9-5`). **(m7) half 2 is
      SUPERSEDED by (m8a)** -- it belonged to a red base that no longer exists once Task 1 lands the
      trigger. **Declared first red: (m8a)'s `sqlite3.IntegrityError`.**
- [ ] **Bounded:** one sibling refusal set, one message constant, the shared predicate at three call
      sites, and the assertions above. **No other change to that module and no sweep** -- the
      widening is exactly this, and the third call site is inside it because it refuses only the
      column this arc introduces.
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

### Task 3: the THREE observations (TWO new fields) -- the immediate path in the wrapper, the deferred path in `record_entry`

> **THE SCHEDULING RULE THIS TASK IS NOW WRITTEN AGAINST -- and it is the plan's answer to a class
> that has cost four rounds** (`A4-R7-2`, `A4-R8-3`, `A4-R9-7`, `A4-R10-3`). The first three were
> each fixed by MOVING A TEST LATER, and **that is what produced the fourth**: Task 3 was left
> shipping `_exit_rollback_failed` with every test of it in Task 4, so the task would have gone green
> against a predicate that could have been `return False` throughout.
> **THE CLASS IS NOT "a task schedules a test it cannot run". IT IS "the plan schedules by ARTIFACT
> rather than by the ASSERTION each test makes."** A task list built from artifacts can put code in
> one commit and its discriminator in another and still read as complete on both.
> **THE RULE: every task ships only code for which an assertion IN THAT TASK distinguishes the
> shipped implementation from its naive substitute.** Applied here: `_exit_rollback_failed` STAYS in
> Task 3 -- because its call site (the observation block below) is in Task 3 -- and Task 3 gains
> **(k5)**, a row that discriminates it from `return False` **using no probe at all**. What moves to
> Task 4 is only the assertions that need the probe. *The naive fix -- move the code -- was tried
> first in this very pass and reversed: it left Task 3 with no deferred-path deliverable and pushed
> the discriminator problem one task along.*

- [ ] `_CommitOutcome` gains `resolution` and `cleanup_raised`, each documented
      as an OBSERVATION -- and `resolution` is RE-READ from `conn.in_transaction` after any rollback
      attempt, never inferred from the fact that the call raised (`A4-R2-7`).
      **NO `body_completed` FIELD** (RD's PIN 1 on `A4-R10-1`): `record_entry`'s shipped
      `result is not None` guard is that observation already.
- [ ] **`_read_resolution(conn, *, attempted)` -- the shared helper, NON-MUTATING** (`A4-R11-4`,
      which dissolves `A4-R11-3`): it re-reads `conn.in_transaction` and NAMES the state
      (`still_open` / `rolled_back` / `not_needed`). **It issues no SQL, performs NO rollback, and
      cannot change what escapes.** Contained in the ALARM direction (`still_open`).
      *The retired version owned a rollback; it could not both contain that failure and preserve the
      immediate ladder's `raise cleanup_error from write_error`, and on the deferred path it retried
      on a wounded connection BEFORE the failure had been detected.*
- [ ] Immediate path: set `resolution` + `cleanup_raised` in all
      arms of the existing cleanup ladder **without changing either existing message and WITHOUT
      touching `raise cleanup_error from write_error`**, naming the state through
      `_read_resolution` so the two paths cannot drift on the one thing they share.
- [ ] **`_CONTEXT_SLOT` and `_exit_rollback_failed(escaping, ambient)`** (S2.2): the
      `isinstance` filter is REMOVED (RD, `A4-R10-1`); the read goes through the BASE GETSET
      DESCRIPTOR and is contained in the ALARM direction (`A4-R11-1`, CRITICAL); the captured
      ambient exception is excluded by **`is`-identity, never equality** (RD, `A4-R11-2`).
      `_CONTEXT_SLOT` is built from `BaseException.__dict__["__context__"]`, the same source as this
      module's existing `_EVIDENCE_SLOTS`. Its docstring anchors its CPython citation on
      CONTENT (the function name and the verbatim "Commit failed; try to rollback" comment) with the
      **UPSTREAM digest + fetch URL** in SOURCE (S1), **never on bare line numbers and never on a
      local copy's hash** (Global Constraints, as amended 2026-09-07).
- [ ] **The ambient capture in `record_entry`:** `ambient = sys.exc_info()[1]` on the line
      IMMEDIATELY BEFORE the `try` that opens the guarded region. **`sys.exc_info()[1]`, not
      `sys.exception()`** -- the latter is Python 3.12+ and `pyproject.toml:9` declares `>=3.11`.
- [ ] **The ORDER is DETECT then READ** (`A4-R11-3`): `_exit_rollback_failed` first,
      `_read_resolution` second. Nothing in the deferred block mutates the connection, and the order
      states rule (i) rather than merely satisfying it.
- [ ] **THE PRE-ARC GATE IS SPLIT IN THIS TASK** (`A4-R11-5`): `if result is None or not
      outcome.committed: raise` becomes `if result is None: raise` followed by `if not
      outcome.committed:` whose body ends in the same bare `raise`. **The behaviour is unchanged --
      both arms re-raise** -- and without the split there is no branch for the observation to sit
      under, so (k3a)'s Task-3 half asserts a shape this task would not have created. *Task 4 then
      only replaces that bare `raise` with the settle; it does not split anything.*
- [ ] **The DEFERRED path's observation block, in `record_entry`'s post-commit handler** (S2.2,
      S2.4) -- inside `result is not None and not outcome.committed and not _reserve`, calling
      `_exit_rollback_failed(post_commit_error, ambient)` and then `_read_resolution(conn,
      attempted=False)`. **NO rollback, NO log, NO statement on this path** -- `__exit__` owns the
      rollback and its failure is already what escaped. The fields are written and nothing reads
      them yet.
- [ ] **`_entry_transaction`'s `if not immediate:` BRANCH IS NOT EDITED** -- no `try`, no `except`,
      no `as` binding, no statement added inside `with conn:`, whose suite stays exactly `yield`
      (`SS-9`; RD's PIN 1). **(k3a) asserts this as an AST property.** *An earlier version of this
      task put an unconditional state-observer in a new handler there, which reached the
      pre-arc BODY-RAISE branch and would have issued a rollback that path never issued -- 22-A LOCK
      clause (c)'s subject. The observation belongs in the frame that already has the scope.*
- [ ] **Tests: (k), (k2), (k3a), (k5), (k6a)-(k6b) and (k7a)-(k7b) ARE SCHEDULED HERE.**
      **(k7a)-(k7b) are here because `_CONTEXT_SLOT` and the base-slot read SHIP here**
      (`A4-R11-6`'s rule; the inverse schedule check found this on the fix leg's own edit, where
      the two subclass rows had been written into the four-row-matrix row, scheduled in Task 4, so
      Task 3 would have gone green against `escaping.__context__` -- the exact `A4-R11-1` defect, in
      the task that ships its fix). **RED first**:
      (k) asserts a `resolution` field that does not yet exist; (k3a)'s AST walk fails against any
      shape that leaves the immediate assignment unguarded, puts a `try` on the deferred branch, OR
      leaves the pre-arc gate unsplit (`A4-R11-5`);
      **(k5) fails against `return False`**, which is the assertion this task previously had none of;
      **(k6a)-(k6b) fail against a naive IMMEDIATE-path implementation** -- one that assigns
      `rolled_back` whenever `rollback()` returns, and one that routes the immediate path through a
      containing shared helper and so loses `raise cleanup_error from write_error` -- which is the
      direction this task previously had none of either (`A4-R11-6`, `A4-R11-4`).
- [ ] **WHAT IS EXPLICITLY *NOT* HERE, AND WHY EACH ITEM IS NOT** (`A4-R9-7`, `A4-R10-3`; siblings
      `A4-R7-2`, `A4-R8-3`). **(k3b)**, **(k4a)**, **(k4b)**, **(RD-a4)**, **(RD-a5)** and
      **(k2)'s probe-call-count-of-ZERO assertion** all assert what `record_entry` DOES with these
      observations -- it settles by probe, or refuses to -- and **`_durability_probe` and
      `_settle_by_attempt_identity` do not exist until Task 4.** **Every one of them is excluded for
      the SAME single reason: it names the probe.** *Stated as a checklist line rather than fixed
      silently, because the class has cost this plan four rounds and the cheap defence is a task
      list that says what it is not doing and why -- one reason, not a list of special cases.*
- [ ] Commit: `feat(trades): Task 3 -- the transaction wrapper observes resolution and cleanup failure, and record_entry observes them for the deferred path`

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
- [ ] **The settle replaces the bare `raise`** in the `if not outcome.committed:` branch **Task 3
      already split** (`A4-R11-5`), beneath the observation block Task 3 already put there. **This
      task splits nothing.** The lost-commit warning text (ASCII, naming the trade id and saying
      DO NOT RETRY).
- [ ] **Tests: (pr1)-(pr5) ARE SCHEDULED HERE** (`A4-R11-7`, `A4-R11-10`) -- the five probe
      design requirements, each with the assertion that goes red if the requirement is dropped.
      **RED first**: every one of them names `_durability_probe`, which this commit introduces.
- [ ] **Tests:** **(w)** the end-to-end token-flow row, **(RD-a1) in ALL THREE rollback shapes --
      raises-without-effect, raises-after-effect, and RETURNS-without-effect; the third is the only
      one that discriminates the returning-arm re-read** (`A4-R8-2`), (RD-a2),
      (RD-a3), (RD-b), **(RD-b2)**, (c) -- **rewriting
      `test_CONTRACT_a_commit_whose_own_return_was_LOST_re_raises` in place** -- (c2), (d), (f),
      (g), (h), plus the two regression controls (i) and (j).
- [ ] **AND THE ASSERTIONS DEFERRED OUT OF TASK 3, ALL FOR ONE REASON -- THEY NAME THE PROBE --
      Tests: (k3b), (k4a), (k4b), (RD-a4) and (RD-a5) ARE SCHEDULED HERE**
      (`A4-R9-7`, `A4-R10-3`, `A4-R10-1`): **(k3b)** the `sys.settrace` row that asserts a settled
      SUCCESS through `record_entry`'s own observation; **(k4a)** and **(k4b)** the two deferred
      rollback-failure sequences, each asserting a probe call count of **0** and the ORIGINAL
      surfacing (their DETECTION half is already pinned by (k5) in Task 3, and each row re-asserts
      it so the row stands alone); **(RD-a4)** the bare predicate's named false positive; **(RD-a5)**
      the caller-side obligation the `body_completed` removal rests on;
      **(k7a)-(k7b) each GAIN their probe-call-count-of-ZERO assertion here** (`A4-R11-6`: their
      no-probe halves shipped in Task 3 with the base-slot read they discriminate);
      and **the two assertions ADDED to rows Task 3 already shipped: (k2)'s probe-call-count-of-ZERO,
      and (k3a)'s ordering half** -- that `_read_resolution` is LEXICALLY BEFORE
      `_settle_by_attempt_identity` in `record_entry`'s handler, which **cannot be written in Task 3
      and would PASS VACUOUSLY there** on an AST walk that finds no such call (`SS-14`).
      **All of them patch `swing.trades.entry._durability_probe`, which exists only from this
      commit.**
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
     not a re-read); `SELECT COUNT(*) FROM latch_order_mandate_links`; the FULL
     `SELECT id, ticker, state FROM trades WHERE state IN ('entered','managing','partial_exited')
     ORDER BY id`; **`SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE
     'sqlite_%' ORDER BY name`** (the INDEPENDENT before-image the backup is checked against at
     step 1 -- `A4-R11-8`: comparing the backup to "the expected set" checks the constant against
     itself, and a constant is exactly the thing that can be wrong); **and `PRAGMA journal_mode`,
     which SETTLES a claim this plan has been INFERRING** (`A4-R11-12`: Global Constraints says the
     live database was not opened by this plan, so "the live database is WAL" was read off a
     `tmp_path` database built through `ensure_schema` -- that establishes CONSTRUCTION behaviour,
     not this file's current mode). Report all seven.
  0b. **`ls ~/swing-data/swing-pre-22a4-migration-*.db` BEFORE migrating and record the result**
     (normally empty). Without this, step 1's `ls` is satisfied by a leftover file from a failed or
     earlier attempt and would CERTIFY A BACKUP THE GATE DID NOT TAKE (`A4-R3-8`).
  1. `swing db-migrate` -> report the printed version and the printed GENERAL backup path, then
     `ls ~/swing-data/swing-pre-22a4-migration-*.db` again and **identify the EXACTLY ONE path that
     is new relative to step 0b**. Open THAT file read-only (a COPY -- never through `ensure_schema`,
     which would migrate the recovery artifact away) and confirm `SELECT version FROM schema_version`
     is **37** and **its table set is byte-identical to step 0's `sqlite_master` list** -- the
     LIVE before-image, not the constant, so the check cannot pass by agreeing with the thing under
     test (`A4-R11-8`). A backup nobody opened is a filename, not a pre-image.
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
   later.** The read is refused here only because RD's rule (i) is applied as ruled -- **now on
   BOTH paths, S7.15** -- and the refusal
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
   activate a materially more expensive design on the money path. **The surviving triggers, exactly two, as RULED (RD 2026-09-06,
   confirming the strike on this measurement): (a)** a GENERATOR change away from `os.urandom`;
   **(b)** a MEASURED condition that DUPLICATES THE OS ENTROPY STREAM -- with **VM snapshot-resume
   recorded as an INSTANCE of (b) and NEVER as an independent trigger**, since resumed guests
   replaying the entropy pool is the mechanism `vmgenid` exists to signal and qualifies only where
   that duplication is actually established (S2.0.1).

   **THE DETECTION STORY, VERIFIED BY EXECUTION RATHER THAN ASSERTED -- AND ONE HALF OF RD's RIDER
   DID NOT VERIFY.** He attached it as load-bearing and instructed stop-and-route on failure, so both
   halves were run against a model carrying the real CHECK, both real indexes and the real mapper:

   - **A duplicate of a COMMITTED token is REFUSED LOUDLY AND LEGIBLY -- ONLY IN COMBINATION WITH
     S2.5'S MAPPER NARROWING. CONFIRMED BY RD 2026-09-06 WITH THAT PRECONDITION ATTACHED.**
     The second INSERT raises `UNIQUE constraint failed: trades.attempt_id`, so the entry is refused
     before any confirming read exists. **But the SHIPPED mapper
     (`"UNIQUE" in msg and "trades" in msg`) matches that message and reports *"Already an open
     position in BBB (race-detected)"*** -- loud, and MISLABELLED as a position race that does not
     exist. It is truthfully loud ONLY because S2.5 narrows the match to `trades.ticker`, a fix that
     entered this plan in round 1 for an unrelated reason. **Measured both ways.**
     **S2.5 IS THEREFORE LOAD-BEARING FOR RD'S RULING** -- his own stated principle applied to his
     own rider: *a mechanism carries its preconditions and names which of them exist today.* The
     precondition EXISTS (S2.5, shipped in Task 1) and is PINNED rather than assumed: **(r6) asserts
     the TYPED SURFACE of an `attempt_id` UNIQUE failure, never merely the ABSENCE of the wrong
     message** -- a test written as *"no `DuplicateOpenPositionError` was raised"* would pass an
     implementation that raised nothing at all.
   - **The duplicate of a ROLLED-BACK token: THE FALSE-CONFIRM PATH EXISTS, AND IT LIVES ENTIRELY
     INSIDE THE COLLISION EVENT. CONFIRMED BY RD 2026-09-06, who ruled the absolute his own overclaim
     and banked it against himself.** His original wording was *"no false-confirm mechanism, because
     a rolled-back token leaves no row to confirm"*; that is true at the instant of rollback and
     **does not survive to probe time**. **REPRODUCED:** A rolls back (zero rows carry `X`), a second
     connection mints the same `X` for the SAME ticker and COMMITS, A's probe finds that row,
     **ticker corroboration PASSES**, and A would return SUCCESS naming a trade it did not write.
     **THE RULED REPLACEMENT, CORRECTED 2026-09-07 (`A4-R9-4`), and it is the sharper statement
     rather than the softer one:** the path EXISTS, it is reachable ONLY within the collision event,
     and therefore, **IN RD'S OWN WORDS, RULED 2026-09-07 ON `A4-R10-2` AND SHIPPED VERBATIM:**

     > The false-confirm event requires the conjunction of (a) a token collision, (b) same-ticker, and (c) the probe-window timing; its probability is therefore AT MOST the collision probability (containment). No independence is assumed and no strictness is claimed.

     **THIS IS THE FOURTH AND FINAL STATEMENT OF THIS SENTENCE, AND THE PREVIOUS THREE ARE THE
     REASON IT IS QUOTED RATHER THAN PARAPHRASED.** They ran: *"no false-confirm mechanism"*
     (absolute, REPRODUCED FALSE) -> *"EQUALS the collision probability"* (an equality where only a
     bound holds) -> *"`P(false confirm) < P(collision)`"* (a STRICT bound, which round 10 showed is
     not established either). **Why the strict form failed:** containment gives `<=` and nothing
     more; strictness needs a probability model assigning POSITIVE MASS to the difference, and the
     three extra conditions may not be MULTIPLIED without an independence claim -- on a
     single-ticker workload the ticker conjunct is 1, and the timing conjunct is not independent of
     the collision at all. **Each of the three previous statements was written by someone correcting
     the one before it, and each introduced a new claim in the process; the fourth introduces none.**
     Nothing about the probe, the ticker
     corroboration or the index amplifies a collision into a larger exposure; the containment bounds
     both.
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
15. **RULE (i) IS LITERAL ON BOTH PATHS. THE OBSERVABILITY GAP THIS ENTRY USED TO DECLARE IS
    CLOSED, AND THE TWO PRIOR DECLARATIONS OF IT ARE SUPERSEDED -- NOT LEFT SIDE BY SIDE.**
    **RULED BY RD, 2026-09-07 (`A4-R9-2`): BRANCH A.**

    ***THE SUPERSESSION, STATED FIRST AND EXPLICITLY, BECAUSE THE ALTERNATIVE IS TWO LIVE RULINGS
    ON ONE PATH.*** This entry has held two earlier positions and **both are RETIRED**:
    - the 2026-09-06 **ACCEPT (a)** ruling -- *the signal is unobservable; the RESULT it protects is
      enforced by the stronger mechanism of a FRESH connection (constraint 3); therefore COVERED
      risk, not accepted risk* -- **is SUPERSEDED.** It was sound on its premise. Its premise was
      *"the wrapper cannot see whether that internal rollback raised,"* and round 9 showed that
      premise is FALSE.
    - the earlier **DECLARED ASYMMETRY** (`A4-R8-1`, which struck the word "LITERALLY" from S2.4's
      gate) is superseded by the same fact.
    **ONE RULING GOVERNS THIS PATH: rule (i) is enforced literally on both.** The fresh-connection
    argument survives, but **demoted to what it now is** -- a belt over the measured residue named
    in S2.2, not the load-bearing reason for an entire path.

    *What was believed, and what is true:* `sqlite3.Connection.__exit__` owns the deferred commit
    AND its rollback, so the wrapper cannot observe the CALL. **That is where the reasoning stopped
    for two rounds, and it is one step short.** CPython does not swallow that rollback's failure: it
    **RAISES it, with the commit's exception chained beneath as `__context__`** (SOURCE (S1),
    `Modules/_sqlite/connection.c`, the `pysqlite_connection_exit_impl` commit-failed branch
    (`:2394-2403`, a convenience against the UPSTREAM-pinned bytes SOURCE (S1) names by digest and
    URL); MEASURED (6) on the sibling arm, where the failure can
    be forced natively). **A failure that propagates is observable in every frame it passes
    through**, so `cleanup_raised` is set from the exception rather than from a call nobody here
    made (S2.2's `_exit_rollback_failed`). **THE FRAME IS `record_entry`'s POST-COMMIT HANDLER, NOT
    `_entry_transaction`** (RD, `A4-R10-1`, extended by `SS-9`): that is the first frame that also
    knows whether the entry body completed, so the observation and its scope are available in the
    same place -- and `_entry_transaction`'s deferred branch is left LITERALLY UNEDITED as a result.
    **`with conn:` is untouched** -- byte-identical, suite included, no
    hand-rolled transaction plumbing -- so this is not option (b) in disguise.

    *The three facts that made the ruling, each with the method that produced it:* **(1)** a
    Python-level `rollback()` override via `sqlite3.connect(factory=...)` is **never invoked** by the
    C `__exit__` (MEASURED (5)) -- so the obvious test lever is dead and the design could not have
    been settled by that route; **(2)** a forced rollback failure on the block-error arm propagates
    `OperationalError: interrupted` with the original error as `__context__` (MEASURED (6)); **(3)**
    a FAILED commit leaves `in_transaction` **TRUE** (MEASURED (7)) -- **the fact that makes this
    whole clause non-vacuous**, because it establishes that `__exit__`'s rollback is real work with
    a real failure mode rather than a no-op nobody needs to reason about.

    *The commit-fail arm -- the one this design actually runs on -- cannot be forced natively*
    (MEASURED (6a): zero progress-handler callbacks during that rollback), **so its evidence grade
    is stated exactly rather than blurred with the arm that was measured: MEASURED-AT-SOURCE, by
    citation, at `pysqlite_connection_exit_impl` in `Modules/_sqlite/connection.c` of CPython
    v3.14.2 (`:2377-2403`, a convenience against the UPSTREAM-pinned bytes; SOURCE (S1) carries the
    upstream digest and the fetch URL)** -- the same rollback
    implementation as the block-error arm (`:2397` calls what `:2389` calls), and an EXPLICIT
    chaining branch (`:2399`) versus an explicit re-raise branch (`:2403`). It is not an inference
    from behaviour on a neighbouring path; it is the branch, read.

    *What `A4-R9-3` was, and why it needs no acceptance:* rollback-takes-effect-then-raises used to
    record `not_needed / cleanup_raised=False`, which ADMITTED the probe; combined with S7.7's
    accepted collision event, another transaction could commit the colliding token before that probe
    ran, and the settle would return a false SUCCESS naming a row it did not write. **Two separately
    ruled acceptances composed into an outcome neither covered.** Branch A removes the ADMITTING
    STEP: that sequence now sets `cleanup_raised`, the gate refuses, and the original is re-raised.
    **The window is closed STRUCTURALLY, not accepted** -- which is why nothing below declares it.

    *And the outcomes are PINNED, not argued.* **(k4a)** rollback-effective-then-raises -> detected,
    the probe is NOT called, the ORIGINAL surfaces, and a fresh reader sees **0** rows; **(k4b)**
    rollback-raises-before-effect -> detected, the probe is NOT called, the ORIGINAL surfaces, and
    a fresh reader sees **0** rows. **Each row asserts the DETECTION and the OUTCOME**, because
    either alone would pass an implementation that got the other wrong.

    *Option (b) -- owning the deferred commit and rollback explicitly -- remains **REJECTED**, and
    Branch A is why it never needed doing:* hand-rolling `with conn:` semantics on the byte-locked
    money path **buys ZERO outcome delta for a NEW FAILURE SURFACE on the one path these arcs exist
    to protect.** RD named it the **D46 direction** twice; the third option was to READ what already
    arrives.

    **AND THE ACCEPTED LIMITATION THAT USED TO SIT HERE IS GONE, BECAUSE THE THING IT ACCEPTED NO
    LONGER EXISTS -- RULED BY RD, 2026-09-07 (`A4-R10-1`).** This entry accepted that *a commit
    failure which is NOT a `sqlite3.Error`, followed by a rollback failure, is not detected*. **That
    residue was a property of the TYPE FILTER, and the filter is removed:** the predicate is a bare
    `__context__ is not None` inside a scope that already excludes the body-raised region, and
    `_PyErr_ChainExceptions1` chains unconditionally whatever the two exceptions' types are. **A
    `MemoryError` from the C layer beneath a failed rollback is now DETECTED.** *Recorded as a
    retirement rather than deleted: this acceptance was live for two rounds and was cited by
    `A4-R9-3` and `A4-R10-1` as the step that rebuilt the false-confirm composition, so a reader
    tracing either finding needs to land here and see that the step is gone.*

    **AND THE DECLARED COST THAT REPLACED IT IS ALSO GONE -- RD, 2026-09-07, `A4-R11-2`.** The
    bare check FALSE-POSITIVED for a caller invoking `record_entry` from inside an `except` handler
    (**MEASURED, S2.2**: the ambient handled exception becomes `__context__`, so the settle was
    refused and the ORIGINAL re-raised). That cost was accepted on the direction argument. **It is
    now simply not incurred:** the ambient exception is captured immediately before the transaction
    and excluded by `is`-identity, and (RD-a4)'s four-row matrix shows the amendment moves exactly
    ONE of the four cells. *Recorded as a retirement rather than deleted, for the same reason as the
    entry above: the acceptance was live and was reasoned from, so a reader tracing it must land
    here and see it discharged.* **The fail-open direction remains the standing argument** -- a
    false positive costs a settle that does not happen, a false NEGATIVE admits a read rule (i)
    refuses -- and it is what the base-slot read and the alarm-direction containment (`A4-R11-1`)
    now serve.

    **WHAT IS STILL DECLARED, narrower than what it replaces:** a false NEGATIVE remains
    constructible if the object `__exit__` chains beneath the rollback failure IS the captured
    ambient object. **Not constructible on the production path** -- the chained object is the
    COMMIT's own freshly-raised exception -- and it would take a connection proxy re-raising the
    caller's ambient exception as its commit error. S2.2 states it at the predicate.

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
4. **THE FOUR PRE-COMMIT LOGGING CALLS IN `_record_entry_inner` REMAIN UNCONTAINED** -- 22-A3's
   S7.11, unchanged and unchallenged: they run
   inside the transaction, so a raising sink aborts the write and reporting a failure is honest.
   Proposed: **DECLINED** as a change, cited to 22-A3's declaration; recorded here only so the reader
   knows it was re-examined rather than forgotten.
   **THE FOUR LINE ANCHORS THIS ENTRY CARRIED WERE ALL WRONG, AND THE SWEEP OF 2026-09-07 MEASURED
   THE RIGHT ONES (`SS-12`).** It cited `entry.py:824`, `:892`, `:903`, `:918`. **`_record_entry_inner`
   begins at `:1166`**, so all four pointed into `record_entry` -- a DIFFERENT function -- and **not
   one of them is a logging call** (`:824` is a comment; the only `log.` call in `record_entry` is
   the POST-commit `log.error` at `:920`, which is contained and is not this item's subject).
   **MEASURED by an AST walk of `swing/trades/entry.py`, not by grep:** the four are
   `log.warning` at **`:1227`**, `log.info` at **`:1295`**, `log.warning` at **`:1306`** and
   `log.warning` at **`:1321`**. The COUNT was right and every ANCHOR was wrong, which is the worst
   arrangement of the two: a reader checking the number is reassured and a reader checking the code
   is misdirected. **This is the in-repo twin of `A4-R10-5`** -- an unverifiable citation invites a
   confident wrong reading -- and the same remedy applies, stated in Global Constraints: cite the
   SYMBOL, keep the line number as a convenience.
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

8. **THE CPython SOURCE'S PROVENANCE -- `A4-R11-9`, SETTLED 2026-09-07 BY THE FETCH. NOT ROUTED,
   NOT BANKED. The entry is KEPT so the settlement is readable, and because the correction it
   forced is worth more than the finding.**
   **WHAT SETTLED IT, and it is the method this entry itself wrote down** (the entry was authored
   ROUTED, saying only a network fetch could close it; the orchestrator made that fetch at 11:36Z
   the same day, using exactly that method):
   **`https://raw.githubusercontent.com/python/cpython/v3.14.2/Modules/_sqlite/connection.c`**
   -> **80,695 bytes, sha256
   `8cc0d9df05860c0b3fe6929ff392f8f85c9e1a5ef89c0cba31ab09ba03b3369e`**, and **CONTENT-IDENTICAL to
   the preserved copy after newline normalisation.** **SOURCE (S1) HOLDS.** The
   chains-on-failure branch is confirmed at the TAGGED SOURCE, not merely at a copy. Round 11's
   counter-claim (2,532 lines, the function at `:2211-2243`) matches neither the upstream file nor
   any counting convention of it, and -- like round 10's -- was produced with `sandbox: read-only`,
   `approval: never`, and no network.
   **AND THE CORRECTION THE SETTLEMENT FORCED, WHICH LANDS AGAINST OUR OWN RULE.** The digest this
   plan had pinned (`7487db46...`) was **the hash of OUR copy**, whose LF had been converted to CRLF
   by a text-mode write while preserving it. **A hash of a local copy pins WHICH BYTES WERE READ, not
   WHOSE THEY ARE** -- the exact gap the `A4-R10-5` citation rule was adopted to close, live inside
   the rule's own worked example, verified by two readers who were each correct about the copy.
   **RD-ratified remedy, now the standing form in Global Constraints and SOURCE (S1): pin the
   UPSTREAM digest TOGETHER WITH the fetch URL.** The preserved file has been renormalised and its
   digest is now the upstream one (verified on disk here: `sha256sum` -> `8cc0d9df...`, 80,695 bytes,
   LF-only). **A line count is a convenience, never a pin:** `wc -l` and `splitlines()` both read
   **2,717** on the pinned bytes, and an editor showing a phantom line after the final newline
   reports 2,718 -- the bytes and the digest do not move either way.
   **THE NARROWING-BY-MEASUREMENT STANDS, and it is now belt-and-braces rather than the whole case.**
   SOURCE (S1) carries two claims. **The rollback-SUCCEEDS half is independently MEASURED on this
   machine** (S2.2's two-run table; (RD-a4)'s four-row matrix re-drives it): the commit's exception
   is what propagates, with the thread's ambient exception or `None` beneath it. **Only the
   rollback-FAILS-and-chains half ever rested on the C source**, and it rested there because it
   cannot be driven natively -- MEASURED (5) and (6a) show a Python `rollback()` is never invoked by
   the C `__exit__` and the post-commit-failure rollback makes zero progress-handler callbacks,
   which is why (k4a)/(k4b) use a proxy. **That half is now confirmed upstream**, and both sides of
   round 11 had always agreed on the BEHAVIOUR; the dispute was provenance, and provenance is what
   the fetch bought.

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
8. **THE THIRD ITEM IS CLOSED, AND NEITHER OF THE TWO OPTIONS IT OFFERED WAS TAKEN (`A4-R8-1`,
   then `A4-R9-2`; RULED BY RD 2026-09-07).** This item asked you to choose between (a) OWNING the
   deferred commit and rollback explicitly -- re-plumbing a byte-locked path -- and (b) ACCEPTING
   that rule (i) is only APPROXIMATED there, because *"the wrapper cannot see whether the internal
   rollback raised."*
   **THE PREMISE UNDER BOTH OPTIONS WAS FALSE.** CPython does not swallow that failure: it raises
   the rollback's exception with the commit's chained beneath it
   (the `pysqlite_connection_exit_impl` commit-failed branch of `Modules/_sqlite/connection.c`,
   `:2394-2403`, a convenience against the UPSTREAM-pinned bytes SOURCE (S1) names by digest and
   URL; MEASURED (6) on the sibling arm). **`record_entry`
   reads the failure off the exception it already receives, `_entry_transaction`'s deferred branch
   is not edited at all, and
   rule (i) is enforced LITERALLY on both paths** (S2.2, S7.15).
   **Nothing on this item needs your ruling now** -- no locked path is re-plumbed, so the concern
   that produced the routing does not arise. It is recorded rather than deleted because *"the
   choice is yours"* was written into a document you read, and a question that quietly disappears
   is indistinguishable from one that was answered. **What changed is that a third option existed
   and neither the plan nor two rounds of review looked for it.**
9. **The two JURISDICTION NOTES are written into the migration header**, not left to a reviewer:
   (A) a `BEFORE UPDATE` trigger cannot see `INSERT OR REPLACE`, and the REPLACE family was grepped
   EMPTY against `trades` -- re-run here, **zero executable REPLACE statements anywhere in `swing/`**
   (45 textual hits across 22 files, every one prose in a migration header, a trigger message or a
   docstring) -- so a future REPLACE writer is a **declared breach rather than an unknown**;
   (B) **22-B Demand A rebuilds `trades`**, and a rebuild that does not re-create the index AND the
   trigger silently drops the guard -- banked by CHARC as a 22-B precondition and recorded in the
   header so the next rebuild's author meets it in the file.

### To RD -- the admissibility gate -- **RULED 2026-09-06 AND AGAIN 2026-09-07. NOTHING IS OPEN.**

**Why it fired:** the token is admissibility machinery -- the thing that makes a durability read
EVIDENCE -- and RD's three constraints are its specification. **Constraint 2 is RULED: `uuid4`
satisfies it, because "never reusable" means the mechanism contains no path that REISSUES a token,
and `uuid4` has none.** Items 1 and 3-6 below are closed by that ruling.
**Item 2's two routed rider clauses were RULED 2026-09-06** (both replacement wordings confirmed;
`fork` struck), **and one of those replacements was itself CORRECTED TWICE -- 2026-09-07**
(`A4-R9-4`: *"EQUALS the collision probability"* -> a strict bound; then `A4-R10-2`: the strict bound
-> **AT MOST, by containment**, because strictness was never established either. **The fourth
statement is RD's own and ships verbatim in S7.7.**). **A third item was ruled 2026-09-07**
(`A4-R9-2`, Branch A -- item 3 and CHARC item 8). **AND A FOURTH WAS RULED 2026-09-07 AFTER
ROUND 11** (`A4-R11-2`): **the ambient-`except` false positive is REMOVED rather than accepted** --
`sys.exc_info()[1]` is captured immediately before the transaction context manager and excluded by
`is`-identity, with the capture POINT part of the ruling (not function entry: any except-frame
between the capture and the `with`'s exit must belong to `record_entry`, where the envelope sees
it). **Its three attached conditions are all discharged in S2.2 and (RD-a4)**: identity semantics
and capture point; **(RD-a4) rebuilt as a four-row matrix computed under BOTH predicates** -- his
words, *"That rule's violation is exactly how the one-row pin passed a false premise to me; the
repaired test is the apology that compiles"*; and the `A4-R11-1` containment covering the context
read, through the base getset descriptor. **Every box in Task 0 is checked.**

1. **S1 is the answer to your ruling's own precondition question**, and it says: the CO-DURABLE
   MECHANISM exists and its token does not; UNIQUE PER ATTEMPT does not exist at all; the
   DURABLE-VISIBILITY capability exists and is wired to nothing. Each is re-derived against the code
   with the method that produced it, and two of your constraints' supporting facts were REPRODUCED
   on this tree rather than cited (rowid reuse; a fresh connection's blindness to uncommitted rows).
2. **RULED 2026-09-06, AND ONE OF THE REPLACEMENTS CORRECTED 2026-09-07. Kept in full because the
   record of a rider that failed verification is worth more than the rider.** Your S7.7 detection
   rider did not fully verify at the code and you had instructed stop-and-route if it did not; both
   halves were run against a model carrying the real CHECK, both
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
   verified versions.**
   **BOTH REPLACEMENTS WERE CONFIRMED 2026-09-06 -- and the S7.7 one was WRONG TOO, corrected
   2026-09-07 (`A4-R9-4`).** Your absolute (*"no false-confirm mechanism"*) was replaced by
   *"its probability EQUALS the collision probability"*, and that is an equality where only a bound
   holds. **The correction to `P(false confirm) < P(collision)` was then ALSO wrong** (`A4-R10-2`):
   containment yields `<=`, and STRICTNESS requires a probability model assigning positive mass to
   the difference plus an independence claim the three conjuncts do not have -- a single-ticker
   workload makes the ticker conjunct 1. **You ruled the fourth statement on 2026-09-07 and S7.7
   carries it VERBATIM:** *"The false-confirm event requires the conjunction of (a) a token collision, (b) same-ticker, and (c) the probe-window timing; its probability is therefore AT MOST the collision probability (containment). No independence is assumed and no strictness is claimed."* *Recorded at length because
   this is the FOURTH statement about one sentence; the first three were each written by someone
   correcting the one before, and each introduced a new claim while doing it. The fourth introduces
   none, which is why it is quoted rather than paraphrased -- and the entry's value is now the
   correction history as much as the claim.*
3. **Rule (i) -- "a failed rollback VOIDS the read" -- is implemented as "no read is attempted
   whenever a rollback CALL raised", ON BOTH PATHS (RULED 2026-09-07, `A4-R9-2`; the earlier
   immediate-path-only implementation and the CHARC item-8 asymmetry are both SUPERSEDED).
   S2.4 argues the cost is ZERO** by enumerating
   the THREE refusal branches (`still_open`; `rolled_back` with `cleanup_raised`; and, since the
   2026-09-07 ruling, `not_needed` with `cleanup_raised` on the deferred path) and showing the row
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
2. `swing/trades/entry.py:628-1163` -- `record_entry` (`:628-942`), `_CommitOutcome`, the DECLARED-RESIDUAL block,
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
| AUDIT | *(deterministic self-audit, 68 probes, no Codex)* | -- | 2 real gaps | -- | -- | *no verdict* |
| **7** | `strong` / `gpt-5.6-sol` / `high` | 0 / 9 / 3 | 12 (**6 new ground, 6 residual**) | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| SWEEP | *(deterministic consistency sweep, no Codex)* | -- | 3 bookkeeping | -- | -- | *no verdict* |
| **8** | `strong` / `gpt-5.6-sol` / `high` | 0 / 5 / 1 | 6 (**2 new ground, 4 residual**) | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| 9-DQ | *(DISQUALIFIED -- provider capacity)* | -- | -- | -- | -- | **NO VERDICT; 2 anchored `^ERROR`, exit 1. 316,797 tokens spent, NOT counted.** |
| **9** | `strong` / `gpt-5.6-sol` / `high` | 0 / 9 / 0 | 9 (**6 new ground, 3 residual**) | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| AMEND | *(2026-09-07 amendment pass on RD's three rulings; sweep 41/41/41, per-location audit 38 probes)* | -- | -- | -- | -- | *no verdict; no effect on convergence* |
| 10-DEAD | *(NOT A ROUND -- MSYS path-mangling; harness exit 0, 0-byte transcript)* | -- | -- | -- | -- | **NO BANNER, NO FOOTER, NO VERDICT. 0 tokens.** |
| **10** | `strong` / `gpt-5.6-sol` / `high` | 1 / 5 / 1 | 7 (**1 new ground, 6 residual**) | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| **SETTLE** | *(2026-09-07 DEDICATED SETTLING SWEEP -- gate-holder ruled; RD's two round-10 rulings applied, then `SS-9`..`SS-16`; NO Codex, NO round number)* | -- | **8 uncounted (`SS-9`..`SS-16`)** | -- | -- | *no verdict; NO effect on convergence* |
| **11** | `strong` / `gpt-5.6-sol` / `high` | 1 / 11 / 2 | 14 (**8 new ground, 6 residual**) | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| **FIX** | *(2026-09-07 FIX LEG -- operator-authorized, **NO CODEX ROUND**; four instruments re-run, two strengthened)* | -- | **13 of round 11 FIXED, 1 ROUTED** | 0 | 0 | *no verdict; **NO effect on convergence** -- a fix leg is not a round* |
| **SETTLE-9** | *(2026-09-07 orchestrator NETWORK FETCH; **NO CODEX**)* | -- | **`A4-R11-9` CLOSED; SOURCE (S1) confirmed upstream; the citation rule amended -- pin the UPSTREAM digest, never a local copy's** | -- | -- | *no verdict; NO effect on convergence* |

**TOKEN SPEND, ELEVEN COUNTED ROUNDS:** 437,776 + 230,647 + 246,268 + 320,775 + 317,038 + 307,420 +
413,949 + 349,176 + 463,310 + 392,163 + 509,364 = **3,987,886**.
**THREE ATTEMPTS WERE DISQUALIFIED OR DEAD AND ARE EXCLUDED FROM THAT SUM, and their cost is stated
rather than hidden:** round 1's first attempt (MSYS path-mangling; no transcript, no footer, 0
tokens), round 9's first attempt (**provider capacity: exit 1, two anchored `^ERROR` lines, NO
verdict token, and a `tokens used` footer anyway -- 316,797 tokens**), and round 10's first attempt
(**MSYS path-mangling again, harness exit 0 with a 0-byte transcript -- the two-signal rule caught
it; 0 tokens**). **Total actually spent: 4,304,683.** **ROUND 11 HAD NO DEAD ATTEMPT** -- the
working invocation was applied FIRST, which this loop had failed to do twice. *The round-9
disqualification is the cleanest demonstration in this loop of why the footer alone is not a
completion signal: it was present on a round that produced no verdict at all. The round-10 dead
attempt is the second instance of a hazard already written down in this loop's own ledger and not
applied on the first try.*
**RUNNING TOTALS, RECOMPUTED FROM THE PER-ROUND ROWS AFTER `A4-R9-9` CAUGHT THEM WRONG, AND NOW
RE-DERIVABLE BY COMMAND** (the LEDGER CONVENTIONS block in `.copowers-findings.md`):
**through round 8 -- 86 findings: 4 CRITICAL, 63 MAJOR, 19 MINOR.**
**through round 9 -- 95 findings: 4 CRITICAL, 72 MAJOR, 19 MINOR.**
**through round 10 -- 102 findings: 5 CRITICAL, 77 MAJOR, 20 MINOR. ZERO reopened, ZERO reverted.**
*The previously stated "76 / 3 / 46 / 17" was wrong in two independent ways -- it disagreed with the
per-round rows above it AND its own severities summed to 66, not 76. It was carried into two return
reports as convergence evidence before a reviewer recomputed it. **A total used as evidence is
itself evidence and gets checked like evidence**; this one was not, in a document whose whole
subject is claims that outrun what supports them.*

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

**ROUNDS 7 AND 8 WERE AUTHORIZED BY THE GATE-HOLDER, each with an absolute stop-and-report rule.**
Round 7 reviewed the post-ruling shape and found that round 6's `typeof` fix **existed in prose and
in none of the five places that execute it** -- the defect a deterministic self-audit had just
missed, because that audit carried one probe per finding and could not see a partially propagated
fix. Round 8 was commissioned to review round 7's own twelve fixes, since **shipping a plan whose
last round's fixes are unreviewed is the trap this loop was told to avoid**, and it returned SIX
findings against round 7's twelve and round 6's thirteen. **Its reviewer's own judgement, asked for
directly and recorded here because it dissents from the falling count:** the plan is *"still yielding
substantive design and evidence defects, not mainly bookkeeping"* -- and it named the one that
justifies the verdict, `A4-R8-1`, the deferred path where rule (i) is claimed and not enforced
(S7.15, routed at S9 item 8).

All five mechanical assertions passed every counted round (model, effort `high`, anchored
`^ERROR` = 0, anchored `^tokens used` footer present, exactly one DISTINCT anchored verdict token
with the other at zero). One attempt-1 invocation of round 1 was DISQUALIFIED before it counted --
MSYS path-mangling produced an empty transcript while the harness reported exit 0; the two-signal
rule caught it. Per-round assertions and per-finding adjudications: `.copowers-findings.md`.

---

### THE 2026-09-07 FIX LEG -- **the round-11 dispositions, and the CAP that governed it**

**AUTHORIZATION AND ITS BOUNDARY, STATED FIRST BECAUSE IT IS THE THING A LATER READER WILL WANT.**
The operator authorized **the fix leg, then a gate with a disposition. NO twelfth counted round.**
No Codex ran in this leg; no prompt was prepared for one. **A twelfth counted round requires the
operator's written authorization and does not exist.** The settling-sweep cell that ran round 11
measured 446,282 against the 400K cap, so this leg ran in a FRESH cell off the committed plan plus
the preserved per-round evidence -- the recipe's normal outcome past the cap, not a failure.

**EVERY ROUND-11 FINDING HAS A WRITTEN DISPOSITION. Thirteen FIXED, one ROUTED AND THEN SETTLED
the same day by the orchestrator's network fetch, none banked. NOTHING IS OPEN.**

| finding | severity | disposition |
|---|---|---|
| `A4-R11-1` | CRITICAL | **FIXED** -- `_CONTEXT_SLOT`, the base-slot read, ALARM-direction containment; the "structurally impossible" sentence STRUCK; (k7a)-(k7b) added in Task 3 |
| `A4-R11-2` | MAJOR | **FIXED** -- RD's ruling adopted with all three conditions; (RD-a4) rebuilt as a four-row matrix; `sys.exc_info()[1]` (a measured premise correction to the relayed `sys.exception()`) |
| `A4-R11-3` | MAJOR | **FIXED** -- dissolved by the `_read_resolution` split; the deferred retry is GONE, which restores the pre-arc behaviour |
| `A4-R11-4` | MAJOR | **FIXED** -- the shared thing is the NON-MUTATING read; the immediate ladder keeps `raise cleanup_error from write_error`, pinned by (k6b) |
| `A4-R11-5` | MAJOR | **FIXED** -- Task 3 SPLITS the pre-arc gate (behaviour unchanged); (k3a) asserts the split itself |
| `A4-R11-6` | MAJOR | **FIXED** -- (k6a)-(k6b), the immediate path's Task-3 discriminators, no probe and no `record_entry` |
| `A4-R11-7` | MAJOR | **FIXED** -- (pr1)-(pr4), one row per unpinned Task-4 requirement |
| `A4-R11-8` | MAJOR | **FIXED** -- (m3) split into (m3a)/(m3b)/(m3c); the gate proven INVOKED and LOAD-BEARING; S6's witness compares against a live before-image, not the constant |
| `A4-R11-9` | MAJOR | **SETTLED** (S8 item 8) -- ROUTED by this leg with the settling method written down; the orchestrator then ran exactly that method. **UPSTREAM sha256 `8cc0d9df...`, 80,695 bytes, content-identical after newline normalisation. SOURCE (S1) holds.** It also FORCED A CORRECTION AGAINST OUR OWN CITATION RULE: the previously pinned `7487db46...` was the hash of OUR copy (LF->CRLF on a text-mode write) -- **a local copy's digest is provenance of the READING, never of the SOURCE.** RD-ratified remedy now standing: pin the UPSTREAM digest with the fetch URL |
| `A4-R11-10` | MAJOR | **FIXED** -- (pr5) + the `file:...?mode=rw` URI open, VERIFIED BY EXECUTION on this box |
| `A4-R11-11` | MAJOR | **FIXED** -- the below-HEAD census re-measured per file as CALL counts; the drop-path reason holds for ONE site |
| `A4-R11-12` | MAJOR | **FIXED** -- the live journal mode relabelled INFERRED at both sites; S6 step 0 asks for `PRAGMA journal_mode` |
| `A4-R11-13` | MINOR | **FIXED** -- SEVEN at `:178-196`, corrected at BOTH sites; the sweep gained CONTRADICTION probes |
| `A4-R11-14` | MINOR | **FIXED** -- (RD-a2) in Task 4, not Task 5 |
| `SS-17` | (uncounted) | **FIXED** -- the `insert_trade_with_event` grep's REAL output is nine hits, of which one is a call |

**THE INSTRUMENTS, AND WHAT THEY DID AND DID NOT SEE.** All four re-run clean:
`plan_consistency_sweep.py` **53/53/53, clean**; `per_location_audit.py` **117 probes, 0 failing**;
`assertion_schedule_audit.py` **53 rows, 0 naked symbols, 6 read-and-reasoned prose hits**;
`citecheck.py` **71 citations, 0 unresolved**.

**TWO WERE STRENGTHENED WHERE ROUND 11 FOUND THEM BLIND, and one of the strengthenings immediately
indicted this leg's own work.**
- `plan_consistency_sweep.py` checked **PRESENCE of a right value** and could not see a
  CONTRADICTING site (`A4-R11-13`: it held a probe for the very number the finding reported, and
  passed). It gained a **CONTRADICTION table** -- absence of the WRONG spellings, with any non-zero
  allowance labelled as a quoted record of superseded wording. The retired
  `escaping.__context__ is not None` probe was REMOVED rather than left to fail on a corrected plan.
- `assertion_schedule_audit.py` detects a row scheduled before a SYMBOL exists. It gained the
  **INVERSE check** -- *does the task that SHIPS a symbol contain any row that NAMES it?* -- which
  had never been asked. **Its first run found `_CONTEXT_SLOT` shipping in Task 3 with its only
  discriminator in Task 4**, i.e. `A4-R11-6`'s class inside the fix for `A4-R11-1`, in this leg's
  own edit. That is what produced (k7a)-(k7b). Two other naked symbols were READ and excluded WITH
  THE REASON, not by shortening the roster.
- **AND IT PRINTS ITS OWN BLIND SPOTS EVERY RUN**, because neither strengthening closes them:
  (1) a row scheduled against a code SHAPE its task declines to create (`A4-R11-5`) -- a shape is
  not a symbol; (2) a PATH-level discriminator gap (`A4-R11-6` itself) -- the inverse check is
  satisfied by a row on the OTHER path and the instrument has no notion of a path; (3) whether an
  assertion DISCRIMINATES at all, since it reads prose. **Declared rather than patched over: a
  green instrument standing silently over a known gap is worse than a noisy one.**
- `citecheck.py` was widened from a `.py`-only regex to `.py|.sql|.toml`, because this leg added
  citations it would have silently DECLINED to check. It then caught two of this leg's own anchors
  pointing one line and four lines off (`_EVIDENCE_SLOTS`, the immediate ladder), both corrected.

**WHAT THIS LEG DID NOT DO:** it ran no Codex round and prepared no prompt for one. **It did not
attempt a network substitute for `A4-R11-9`, and that restraint is what made the routing usable** --
the entry carried the exact method, and the orchestrator executed it the same day (the SETTLE-9 row
above). *The general form, worth keeping: an item routed WITH ITS METHOD is closed by whoever has
the capability; an item routed as a worry is closed by nobody.*

### THE 2026-09-07 SETTLING SWEEP -- **UNCOUNTED, and the uncounted status is what keeps it honest**

**Why it exists.** Rounds 8, 9 and 10 each spent most of their yield on the previous ruling's
residue: round 10 returned **6 of 7 findings RESIDUAL**, four of them residuals of the amendment pass
written the same day. The loop's shape was ruling -> amend -> review-of-the-wake, with nothing in
between. The gate-holder ruled a **DEDICATED SELF-SWEEP followed by ONE confirming round on the
settled artifact** -- the recipe's Expansion-#13 provision (`harness-architecture.md` §5.1), whose
first use on 22-A found a CRITICAL no counted round had produced.

**Findings carry `SS-N` ids: no Codex, no round number, NO effect on convergence.** `SS-1`..`SS-8`
were the post-round-4 sweep; this pass added **`SS-9`..`SS-16`**, EIGHT findings, of which **two
would have been CRITICAL or MAJOR had a review round produced them** (`SS-9`, `SS-14`) and **one
corrects a ruling's stated rationale by measurement** (`SS-9`'s sibling, recorded in S2.2 and in the
front matter rather than numbered, because it belongs to a director's text and not to this plan's).

| id | what | class |
|---|---|---|
| **`SS-9`** | applying RD's PIN 1 naively left the (then-mutating) shared observer UNCONDITIONAL in `_entry_transaction`'s deferred handler, which reaches the **pre-arc BODY-RAISE branch** and would issue a rollback that path never issued -- 22-A LOCK clause (c)'s subject, widened by a fix for something else. Both observations moved to `record_entry`; the deferred branch is now LITERALLY UNEDITED and (k3a) asserts it. | a fix that widened the blast radius of the thing it fixed |
| **`SS-10`** | S1.4 still said the arc adds "the three NEW observation fields" to the deferred path. | residual of the same pass, in a section it did not visit |
| **`SS-11`** | THREE stale in-repo line anchors, found by a script that resolves all 54 and prints what each lands on: `entry.py:1128` is `conn.rollback()` not the immediate `committed` assignment (`:1107`); `entry.py:880` is inside a comment block, not the shipped guard (`:884`) -- **and `:880` is the number this dispatch's own PIN 1 was relayed with, so it had propagated to three sites before the sweep caught it**; `entry.py:1489` is one line above the UNIQUE mapper. | citation drift |
| **`SS-12`** | S8 item 4 cited FOUR anchors for "the four pre-commit logging calls in `_record_entry_inner`". **`_record_entry_inner` begins at `:1166`; all four pointed into `record_entry`, and not one is a logging call.** MEASURED by AST walk: `:1227`, `:1295`, `:1306`, `:1321`. **The COUNT was right and every ANCHOR was wrong** -- the arrangement that reassures a reader checking the number and misdirects one checking the code. | the in-repo twin of `A4-R10-5` |
| **`SS-13`** | `A4-R10-3`'s generalisation turned into an INSTRUMENT (`assertion_schedule_audit.py`) instead of a paragraph: it walks all 44 rows, collects the symbols each names, and reports every row scheduled before something it names. | a rule with no check is a wish |
| **`SS-14`** | what `SS-13` found on its first run, in a row **this same pass had added four hours earlier**: (k3a)'s new ordering assertion named `_settle_by_attempt_identity` and was scheduled in Task 3. **Its failure mode is worse than the four counted instances:** an AST walk asserting an ORDERING finds no such node, therefore finds no ordering to violate, and reports SUCCESS. **Scheduling-by-artifact does not always produce a red test; it can produce a vacuous green one.** | the class, met inside its own fix |
| **`SS-15`** | S3's roster still described (k3a)/(k3b) as asserting the `committed` assignment is "inside the protected suite on BOTH paths" -- false one commit after `SS-9`. | residual, at the smallest scale it comes in |
| **`SS-16`** | Task 1b said "THREE call sites" for four rounds while the heading above its tests claimed **EVERY OPERATOR SURFACE**; nothing connected them. Closure established by AST walk + a raw-SQL grep: `_update_journal_field` has exactly four callers and is the ONLY site writing an operator-supplied journal field, so the backstop IS the closure and the two early checks are ordering refinements. **And the finding behind the finding:** the plan's whole argument for the tier-3 early check is that its INSERT comes first, and nobody had checked whether the other surfaces share that shape. They do not, for a DIFFERENT reason each. | a roster is the same instrument as the count it replaced |

**Instruments, all preserved at `~/swing-data/review-transcripts/22-a4-plan/`:**
`plan_consistency_sweep.py` (roster/schedule/manifest closure + fragile counts **+ the 2026-09-07
CONTRADICTION table -- absence of the WRONG value, which is the blindness `A4-R11-13` found**),
`per_location_audit.py` (**38 -> 70 -> 120 probes**), `assertion_schedule_audit.py` (`SS-13`;
**+ the 2026-09-07 INVERSE check -- does the task that SHIPS a symbol contain a row that NAMES it?
-- and a BLIND-SPOT declaration it prints every run**), `citecheck.py` (`SS-11`/`SS-12`;
**widened 2026-09-07 from `.py`-only to `.py|.sql|.toml`, because a citation checker that silently
declines a citation class is a green instrument over a known gap**). **Two of them are deliberately
OVER-INCLUSIVE and their surviving hits are named in the sections that own them**, rather than tuned
until they read clean -- an instrument tuned to be quiet is a decoration. **And the inverse check's
first run indicted the pass that added it** (`_CONTEXT_SLOT`, Task 3, discriminator in Task 4), which
is the strongest evidence available that it was worth adding.

