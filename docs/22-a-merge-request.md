# 22-A — MERGE REQUEST

**Arc:** Phase 22-A, entry-path order↔mandate binding.
**Branch:** `22-a-fix` (contains `22-a-exec`), worktree `.worktrees/22-a-fix`.
**Status:** A-loop STOPPED by operator disposition 2026-09-02, not converged-to-clean. Every finding
dispositioned below under introduced-versus-banked, which is what CHARC's gate requires.

> **This request is the gate's evidence, not its summary.** Where a number appears it is followed by the
> method that produced it, because a count without its method is the completeness half of the class this
> arc met at counts, greps, absences, a coverage meter, and twice inside instruments written to catch it.

---

## 1. REVIEWER B — CHARC's gate requirement

**B MUST HAVE RUN ON THE TREE BEING MERGED.** It did.

| | |
|---|---|
| **Transcript** | `~/swing-data/review-transcripts/22-a-fix/REVIEWER-B-postfix-2026-09-01.txt` — 3,946,669 bytes, 34,807 lines |
| **Prompt** | `~/swing-data/review-transcripts/22-a-fix/REVIEWER-B-prompt-postfix.md` |
| **Tree audited** | `22-a-fix` post-fix (the tree being merged), NOT the stale `403ea9ff` the first B pass saw |
| **Verdict** | **`NEW_CRITICAL_MAJOR_FOUND`** |

**Preserved OUTSIDE the worktree before anything else** — the first B pass was written to a session
scratchpad and would have been destroyed with it.

### B's five mechanical assertions — all pass

banner `gpt-5.6-sol` (the binding `strong` tier) · `reasoning effort: high` · `grep -c '^ERROR'` = **0** ·
anchored `^tokens used` footer **present** · exactly **one** anchored verdict token.

**The verdict is not a blocker.** CHARC's gate: *B is NOT required to return clean — requiring that would
rebuild the unreachable gate the introduced-versus-banked ruling exists to prevent. What clears is every
finding DISPOSITIONED.* All three are dispositioned in §4.

### B's independence — verified, not assumed

112 hits on the prohibited-artifact patterns, every class checked: the prompt's own prohibition line, prose
mentions inside tracked docs (`implementer-dispatch-recipe.md`, handoffs, `phase3e-todo-archive.md`), and
**B's own `rg -v` / `--glob '!'` flags EXCLUDING those artifacts from its searches.** B did not read
Reviewer A's transcripts.

### B's claims-first result — five of six CLAIM HOLDS

1. **HOLDS** — fire-inheritance end to end: latch stores the order id (`latches.py:1303`) → `0037` mints the
   accepted link (`:704`) → resolver follows envelope→link→FIRE (`latched_origin.py:2759`) → entry installs
   all three FIRE-derived values together (`entry.py:610`).
2. **FAILS** — see §4 finding B-1. The malformed-`schwab_order_id` repair itself HOLDS
   (`trades.py:1093` warns without returning; entry writes the honest-unset triple).
3. **HOLDS** — subject liveness is three-valued (`latched_origin.py:1261`).
4. **HOLDS** — **both** halves of rung 8 read stored *and* read-time tier (`latched_origin.py:1487`).
5. **HOLDS** — `0037` consumes the stored attestation (`:1214`); no JSON re-canonicalization, no cross-engine
   `round()`; nullable comparisons fail-closed via `COALESCE` or null-safe `IS`; **all 37 migrations applied
   to an in-memory DB with `integrity_check=ok`.**
6. **HOLDS** — see §3.

---

## 2. THE TWO METHOD-REPORTED ITEMS (CHARC's explicit gate instruction)

> *"The seat sweep and the two-valued-then-discard done criterion should each report their METHOD in the
> merge request, not their result."*

### 2.1 The seat sweep (open-list item 13)

**76 reason-pinning tests checked · 18 seat-relevant · 1 CHANGED (`4c-i`).**

**Method — and the method is itself a test, not a report of one** (`tests/trades/test_22a_seat_sweep.py`):
a static AST walk finds every module-level test that COMPARES `.decline_reason` to a string literal; a seat
ambiguity is possible ONLY where the world holds more than one accepted order, counted from the arc's order
builders **plus raw `latch_order_mandate_links` INSERTs**; the multi-order set is held against a declared
roster in BOTH directions, keyed by `(module, function)`.
`test_the_sweep_numbers_and_the_method_that_produced_them` asserts the walk still finds ≥76 and ≥18 — **as
floors, not equalities**, so a new reason-pinning test is not a false red while a COLLAPSING count (the
direction that would make both roster directions vacuous) fails loudly.

**Three corrections to the sweep's own numbers, all found by review, all recorded in the module:**
57→74 (a source-text regex counted its own matcher control inside a string literal) · 8→16 (eight became
multi-order from THIS leg's own twin/ticker repairs — the sweep demanding seats for its own output) · 16→18
(the builder roster missed a raw link insert — **a roster failure inside the module whose subject is roster
failure**).

### 2.2 The two-valued-then-discard criterion (open-list item 12)

**Method: the two-valued implementation was WRITTEN, RUN, and the discriminating case observed RED, then
discarded.** Not asserted — executed:

```
E  AssertionError: an UNPROVABLE subject was reported DEAD; the selection is
   two-valued and has reintroduced R3-03's inversion one rung over
E  assert 'frozen_value_unavailable' == 'ambiguous_ticker_orders'
```

`_subject_death_if_proven` returns the subject's own probe VERDICT (never a re-spelled reason) only when it
is `mandate_not_alive`; **proven-LIVE and UNPROVABLE both return `None`** and fall through to
`ambiguous_ticker_orders`, per CHARC's binding three-valued addition.

---

## 3. THE CASE-BINDING NUMBER — with G4's precision requirement honoured

> **G4 is binding on every restatement (CHARC): the gate UNDERSTATES what is TESTED and OVERSTATES what is
> BOUND, so any number must state WHICH it means.**

**146 of 146 case ids are BOUND. 146 of 146 are TESTED at the grain their specification names.**

- **BOUND** is the closure gate's own measure and it is purely lexical — a test function *named*
  `..._case_<slug>`, or the id appearing in a `*_CASE_IDS` list literal.
- **TESTED** is the semantic re-audit's measure: the audit graded **124 FAITHFUL / 20 WEAKER / 1 CONTRADICTS
  / 0 ABSENT / 1 UNVERIFIABLE**, and this leg repaired all 22 non-FAITHFUL.
- **Independently confirmed:** Reviewer B **reimplemented the binding gate's AST rules from scratch** and
  found 146 registry ids, 146 bound, **zero missing, zero phantom**, reading each formerly-weak binding to
  confirm it now exercises its named specification grain, and finding no self-derived expected value and no
  bound-but-non-measuring case. That is a second implementation agreeing, not a relayed count.
- **The two sets still differ, and the gate still understates TESTED:** many rows added this leg (seam
  properties, closure checks, the sweeps) carry no case id and are invisible to the gate. RD's own
  `test_a_recognised_and_refused_entry_is_written_not_refused` remains the standing proof.

**The prior claim of "146 of 146 implemented, each traced to a passing node id" was FALSE** — it was name
coverage, and case 4's test asserted the OPPOSITE of its specification (a broker-ACCEPTED order asserting
ADMISSION where S3.4 specifies place-without-validity falling through). Both directors narrowed their own
clearances rather than receive that correction.

---

## 4. EVERY FINDING, DISPOSITIONED

### 4.1 Reviewer B's three

| id | sev | disposition |
|---|---|---|
| **B-1** — `PatternEvaluationAnchorError` refuses a money-bearing entry (`entry.py:601` → HTTP 400 at `trades.py:1869`) | P1 | **BANKED — PRE-EXISTING, ruled by RD 2026-09-02. NO CODE CHANGE.** Evidence meeting the citation standard: **`main:swing/web/routes/trades.py:1269-1276` already refuses that exact case with the IDENTICAL message.** The arc RELOCATED the refusal to the single authority that judges the value the row is written with; surface behaviour identical, pinned by case 37c. **RD's ruling: a PE anchor plus a derived origin is NOT "cohort bookkeeping" within the meaning of NEVER** — the guard fires only when the request ASSERTS an anchor the server-derived world REFUTES, and for a contradicted explicit claim there is no honest row to write (NULL silently overrules the request's own assertion; non-NULL mints a refuted citation). **This is a stated discriminator, NOT "a live exception"** — an exception invites more exceptions. |
| **B-2** — `BEGIN IMMEDIATE` outside the protected region (`entry.py:471`) | P2 | **INTRODUCED → FIXED.** See §4.4. |
| **B-3** — failed rollback suppressed while the transaction can remain live (`entry.py:481`) | P2 | **INTRODUCED → FIXED.** See §4.4. |

### 4.2 Round 9's six

**FIXED — the two direct residuals of fixes made an hour earlier:**
- **`R9-05`** — the new cleanup warning INFERRED transaction state from the fact that `rollback()` raised; an
  after-effect exception leaves the transaction CLOSED and the row GONE, and it still announced *"STILL OPEN
  with a partial row in it."* Re-derived from `conn.in_transaction`, both branches pinned, **fixed at BOTH
  twin sites** — fixing one of two identical twins is the asymmetry this arc has now paid for twice.
- **`R9-06`** — the SS-2 closure check, written an hour earlier, **was a ROSTER OF TWO STRINGS**: regressing
  the handler to `except Exception` left it green. Now an AST walk asserting every handler catches exactly
  `BaseException`, **proven by mutation over the real source** (string scan `[]` vs AST `['Exception']`).

**DECLARED — three at the AL-10 raw-writer boundary, ZERO live incidence:**

> **The citation, and it is load-bearing for all three: migration `0037` is UNAPPLIED on the live database.**
> Verified read-only at gate time: `schema_version = 36`, and `fill_envelope_identity`,
> `latch_order_mandate_links` and `candidates_immutability_epoch` are **ABSENT**. These tables do not exist
> in production, so a raw-write-only defect against them has no live reachability today.

- **`R9-01`** (major) — duplicate operand keys in the snapshot: `json_extract` reads the FIRST, `json.loads`
  keeps the LAST. The `R8-01` divergence class on a new surface. Needs a service half and a SQL half with the
  subset relationship preserved — a wave on the `0037` operand binding, which is scope this gate does not open.
- **`R9-02`** (major) — the trigger accepts a BLOB `entry_fill_snapshot_json` the Python model rejects, so a
  raw writer can create an audit row the repo cannot reconstruct.
- **`R9-04`** (minor) — the digest branches can raise `malformed JSON` instead of evaluating false.
  **Integrity stays FAIL-CLOSED**; a legibility defect, not an authorize-then-abort.

**`R9-03`** (major) — **RULED AS A CONTRACT by CHARC and IMPLEMENTED.** See §4.4.

### 4.3 The `R15` seven (carried from the exec leg, operator-dispositioned 2026-09-01)

FIXED: `R15-01` (operand keys required and bound at the `0037` insert trigger — done while the migration was
still editable in place), `R15-03` (the rollback leak contradicting `AL-15`), `R15-05` (`SEEDING_INSERT` was
blind to bare `REPLACE INTO` — **CLAUDE.md's own `REPLACE` gotcha inside the arc's own instrument**).
NARROW-FIXED + CLASS ROUTED: `R15-02`. DECLARED: `R15-04` (reproduction required LOWERING
`SQLITE_LIMIT_LENGTH`; production envelopes are ~200 bytes against a 1e9 default; direction is a wrong
REFUSAL). DECLARATIONS COMPLETED, walks NOT widened: `R15-06`, `R15-07`.

### 4.4 The entry-path contract (`R9-03` + B-2 + B-3)

**CHARC's contract, ruled 2026-09-02:** *`record_entry`'s result is a statement about the DURABLE STATE OF
THE LEDGER, never about whether every subsequent step succeeded.*

1. **After a successful commit, nothing may convert the result to failure.** Post-commit steps are
   BEST-EFFORT; exceptions are caught, logged at ERROR with the `trade_id` and failing step, and SUCCESS
   returns carrying `post_commit_warnings`. *"Reporting a durable write as a failure is not conservative — it
   is a wrong answer in the direction that causes a double entry, which is the expensive direction."*
2. **If `commit()` itself raises, RESOLVE BY READ** — present → SUCCESS with a warning that the commit's own
   return was lost; absent → re-raise. *"The fact is in the table, and the exception is not evidence about it
   either way."*
3. **The both-paths rule** — the `immediate=False` path has identical exposure, *"or the pre-arc path becomes
   the one that double-enters."*

**The structural belt, named so it is not mistaken for the fix:** `ux_trades_one_open_per_ticker` means a
retry against a durable entry hits the index and REFUSES rather than duplicating — **so the worst case
before this contract was a confusing retry error, not a double position.** It does not cover a ticker closed
between attempts. RD endorsed the contract from his lane: resolve-by-read is admissibility logic.

**THE CONTRACT WAS IMPLEMENTED FAITHFULLY, AND IMPLEMENTING IT CLOSED ONE DEFECT AND OPENED FOUR — two of them FALSE-SUCCESS paths on the money-bearing path. THE SPLIT IS RULED (CHARC + RD, 2026-09-02).**

**Why clause 2 was never implementable as ruled.** *"Resolve by read"* decomposes into two admissibility preconditions neither director stated at ruling time:

- **VISIBILITY** — the confirming read must observe DURABLE state. A read on the writer's own connection inside an unresolved transaction observes the writer's own uncommitted view: **the writer quoting itself.** A failed rollback VOIDS the read; it does not license "read anyway."
- **IDENTITY** — the read must identify OUR attempt. `SELECT 1 FROM trades WHERE id = ?` establishes only that *a* row with that id exists, and **a rolled-back rowid is REUSABLE** (`sqlite_sequence` rolls back with the insert, so `AUTOINCREMENT` does not pin it). **This precondition does not exist in the schema today.**

RD's sharpest observation on `R10-02`: the rollback-failure branch logs *"it MUST BE DISCARDED rather than reused"* and **the next line reuses it for the confirming read** — the site's own comment states the invariant and the except branch walks past it.

**THE RULING:**

1. **CLAUSES 1 AND 3 STAND.** Post-commit best-effort with `post_commit_warnings`; both paths bound. **`R10-01` and `R10-04` are boundary defects INSIDE clause 1's own contract and are FIXED in this leg** (the guard covers the generator's unwind; the log call becomes best-effort as clause 1 already says it is). Neither needs attempt identity.
2. **CLAUSE 2 REVERTS TO RE-RAISE** — pre-contract behaviour, belt-mitigated, and **HONEST: it never claims a row exists.** Now canon (RD): **alarm-never-assert at the transaction boundary — the function may RAISE the alarm (indeterminate) but may never ASSERT durability from evidence that cannot identify the attempt.** The residual is **DECLARED** with the `R10` reproductions on record, in the one direction the belt covers.
3. **The attempt-identity primitive is a FOLLOW-ON** with its constraints already ruled: **CO-DURABLE** (written in the same transaction as the row it identifies; anything else is a stamp — gotcha #30), **UNIQUE PER ATTEMPT** (survives rollback-and-retry without collision; rowid fails by construction), **DURABLE-VISIBILITY READ** (a fresh connection, or after a PROVEN resolution). CHARC's preferred shape, to be *verified not inherited* at commissioning: a client-generated `attempt_id` on the entry row written in the same INSERT, nullable for legacy rows, UNIQUE partial index `WHERE NOT NULL` — additive, no rebuild; a §3 schema tripwire getting its own pass. Clause 2 returns on top of it, gated by RD's two discriminators: **rollback-raises-then-read must NOT return SUCCESS**, and **a concurrent insert taking the same id must NOT be confirmed as ours.**

**THE PRECONDITION CANON, landed at `bf403b05` — this arc's most transferable output:**

> **A RULING THAT PRESCRIBES A MECHANISM STATES THE PRECONDITIONS THAT MAKE ITS EVIDENCE ADMISSIBLE, AND NAMES WHICH OF THEM EXIST TODAY.** A precondition that does not yet exist converts the mechanism into a follow-on with a primitive to build first, not a clause to implement now.

**Three instances in one week, across both directors, each self-reported:** RD's P1 ruled without its reason (cost: B re-finding it); RD's clause-2 endorsement taking "present" as a primitive; CHARC's clause 2 itself. **Two SQLite facts are now CLAUDE.md gotchas** rather than discoveries: the reusable rolled-back rowid, and the writer quoting itself.

---

## 5. DECLARED LIMITATIONS SHIPPING WITH THIS ARC

1. **A BLOB digest's VALUE is unverified in the trigger** — SQLite has no `sha256`, so only the SHAPE (64
   lower-case hex) and type tag are checked. AL-10's boundary (the trigger verifies CONSISTENCY, never
   TRUTH); strictly smaller than the any-object branch it replaced. Declared in `0037` and in the tests.
2. **The authorize-then-abort closure check does not prove predicate EQUIVALENCE** for a clause both sides
   name — that needs a solver over two languages. Both directions of MEMBERSHIP are enforced on both sides,
   with the SQL side read out of the migration rather than from a roster.
3. **The bound-input migration walk is a DECLARED HEURISTIC** with its exact residual set asserted and one
   reasoned exclusion.
4. **The cohort-guard declaration walk is a heuristic over the arc's own citation token** — a guard written
   without citing `0036:26-38` is invisible to it, which is why two properties exist and why the surface
   none of the three covers is named.
5. **`AL-12` / `AL-14` gained four DECLARED blind spots rather than wider walks**, per the standing
   declare-versus-widen ruling, each verified by execution before being declared.
6. **`22A-R15-04`** and the **`-1` REPLACE residual** — both declared and confirmed accurate by Reviewer B.
7. **The seat sweep's completeness rests on a builder roster**, which failed once this leg and is now backed
   by a raw-INSERT matcher with its own control.

**Registry edit flagged for RD, not silently taken:** case `15e`'s ownership moved task 1 → task 8 (registry
N11) on the implementer's judgment, because S5.1's reason view assigns it `no_envelope` — a RESOLVER verdict
task 1's cell can only ever assert the reader for. **This is the measured agent editing the instrument that
measures it**, surfaced rather than buried.

---

## 6. THE ARC'S REVIEW HISTORY

| leg | A rounds | findings | reopened | reverted | dismissed |
|---|---|---|---|---|---|
| exec (`22-a-exec`) | 15, none clean | 102 | 0 | 0 | 0 |
| fix (`22-a-fix`) | 9 (round 8 CLEAN; round 9 not) | 45 | 0 | 0 | 0 |
| **Reviewer B** | 2 passes (the second on this tree) | 5 across both | — | — | — |

**Every round in both legs passed all five mechanical assertions, verified by the orchestrator from the
transcripts rather than from any agent's claim.**

**Why the A loop stopped rather than converged (operator disposition, 2026-09-02):** three consecutive
rounds had their sharpest catches be instruments the leg had just written — `R9-06` (a closure check that was
a roster of two strings, one hour old), `R8-01` (a vacuous test arm, one hour old), `R15-05` (a pin blind to
`REPLACE`). The remaining findings are raw-write-only against tables that do not exist in production.
Continuing generates more instrument findings, not more safety.

---

## 7. GATE STATE

*(Final numbers land here when the `R9-03` delta returns; everything above is settled.)*

**To re-verify at the gate, not to carry forward from this document:**
- `schema_version = 36` on the live DB and `0037` UNAPPLIED — **this is the fact that kept the migration
  editable in place all arc, and three fixes depended on it.**
- Zero `Co-Authored-By` trailers, filtered on the trailer KEY.
- Full fast suite green on the MERGED head, re-run after the merge, never carried from the branch.

**This arc corrects NEITHER trade 24 NOR trade 25.** Both carry as named pending rows into RD's September
read.
