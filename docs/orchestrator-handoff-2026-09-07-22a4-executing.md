# Orchestrator handoff — 2026-09-07 — 22-A4 at the executing boundary

**From:** the generation that took 22-A4 from writing-plans through eleven counted Codex rounds, four
director rulings, a settling sweep, a fix leg, the gate, the merge, and the executing dispatch.
**Rolled at the ~400K trigger** (measured 396,223 — see §6, I can measure my own depth and so can you).
**Bootstrap:** `scripts/orchestrator_bootstrap.md` → `docs/orchestrator-context.md` → this file.

**Every fact here was re-derived from disk or the live DB at handoff time.** Do the same.

---

## 1. YOUR FIRST ACTION — a live cell is mid-flight

**The 22-A4 EXECUTING cell is RUNNING and will return to you, not to me.**

- Worktree `.worktrees/22-a4-exec`, branch `22-a4-exec`, **base `9249d8da`** (verified at/above
  `ade0d3ba`; the six rules of 2026-09-07 verified present in that tree's OWN copies before dispatch).
- **Its plan of record is the EXTRACT** `docs/superpowers/plans/2026-09-06-phase22-arc-a4-EXECUTING.md`
  (1,889 lines), NOT the 4,370-line design record. CHARC's ruling; do not redirect it to the full plan.
- It was told to run **round 0 first** (premise census, no Codex) and to **STOP and route** if a
  ruling's facts fail intake.
- **QA it against disk before accepting anything** — the return report is a self-report.

## 2. STATE, re-derived

**main `0cf09eb2`, 4 commits unpushed.** **Live schema v37.** **22-A4's plan, ledger and extract are
MERGED and PUSHED** (`0fac27ff`); merged-head suite **12180 passed / 13 skipped / 0 failed**, ruff clean.

**Worktrees:** `22-a4-exec` (live, above) and `22-a4-plan` (**merged; deletable** — the plan is on main
AND its evidence is preserved at `~/swing-data/review-transcripts/22-a4-plan/`, both halves of the
preservation rule met. I left it rather than tidy on the way out).

**Open trades: 23 CADL (partial_exited), 24 RHI, 25 OII, 26 NRIX, 28 PBF (managing).** Real money.

## 3. THE ONE THING THAT NEEDS THE OPERATOR

**Migration 0038 on the live DB is an operator-witnessed POST-MERGE gate (extract §S6), step by step,
never a batched runbook.** Nobody in a worktree touches the live database.

## 4. THE RULINGS THAT WILL BITE IF YOU FORGET THEM

- **The loop is CAPPED.** A twelfth counted plan round needs the operator's WRITTEN authorization.
  22-A4 gated on a **DISPOSITION, not convergence** — last verdict `NEW_CRITICAL_MAJOR_FOUND`, all 14
  round-11 findings closed, zero open. Do not restate that as a clean verdict.
- **Spend: 3,987,886 counted / 4,304,683 including three dead attempts.** Report both; the number that
  hides the corpses is the flattering one.
- **A ruling's REASONING is binding; its FACTS are inputs**, verified by the cell at intake. Two of
  four rulings this arc were corrected on their own facts (a scope premise that failed a two-row test;
  `sys.exception()` named above the `>=3.11` floor). **Both were caught by the implementing cell, not
  by the director and not by me. The relay is a defect surface.**
- **ONE RULER PER ITEM.** A packet naming two seats for one open question is mis-addressed.
- **Base-SHA check before every dispatch** — a worktree carries the rules that existed when it was cut.

## 5. WHAT THIS GENERATION GOT WRONG, and the shape is one thing

**I reported four absences that my own instrument could not have found**, and each time the tool
returned "nothing" and I relayed it as a fact:

- `find -maxdepth 6` against a path at depth 8 → "no copies of the transcripts exist," relayed to
  another session as a ruled-out location. They were never lost.
- **`ls` without `-a` against dotfiles — THREE times.** The third I caught before speaking.
- `pytest ... ; ruff` chained → **pytest rejected an argument and never ran, and the chain reported
  exit 0 from ruff.** I nearly reported a merged-head suite green off a run that did not happen.
- A one-row experiment reported to RD as confirming a two-row premise, which he then partly ruled on.

**The rule already existed** — report an absence with the search that produced it; exit 0 is not
evidence anything ran. **Knowing it is not the same as running it against yourself.** Before you say
"there is no X," say what you searched and whether it could have found X.

## 6. YOU CAN MEASURE YOUR OWN DEPTH — I could not, until I tried

CHARC's `cell_depth.py` reads subagent transcripts, and the standing claim is that a cell cannot see
its own depth. **The MAIN session can:** sum `usage.input_tokens + cache_read_input_tokens +
cache_creation_input_tokens` on the last record of
`~/.claude/projects/<slug>/<session-id>.jsonl`. That is how I measured 396,223 and rolled on the
trigger instead of waiting to be told. **Do this periodically; do not wait for the operator to notice.**

## 7. QUEUE BEHIND 22-A4

D46 (the reduction), D45, D44/D47, the D39 sweep, D42's export failure. The admitting gate stays open:
131 post-barrier candidates, **zero A+**.

---

# ADDENDUM — 22-A4 executing round 0 returned, both forks RULED, Task 1 ready to dispatch

**Written after the original handoff. This supersedes §1: the executing cell RETURNED rather than
staying in flight, so nothing is running and your first action is a DISPATCH, not a QA.**

## Round 0's result — it stopped and routed, and it was right to

**No code, no commits, `git status` clean at `9249d8da`.** Baseline re-measured on that worktree and
READ: **12180 passed / 13 skipped**, matching. Measurement scripts durable at
`~/swing-data/review-transcripts/22-a4-exec/`.

**RULED (CHARC, PRIMARY, 2026-09-07): `(m3c)` takes BRANCH A.** The plan demanded the expected-tables
constant EQUAL a fresh v37 schema while prescribing a derivation that yields 37 against 42 real
tables. **The mechanic: `swing/data/db.py:575` is `missing = expected_tables - actual_tables` — a
SUBSET test, and the chain is 21 constants deep, every one a partial roster.** The gate's contract has
always been a FLOOR; the plan wrote a test against the instrument it imagined rather than the one on
disk. **CHARC's reason, sharper than mine:** a pre-image with MORE tables is still a valid backup, so
equality points the wrong way — B would not widen the roster, it would reverse the gate's direction.

**ENCODING for Task 1:**
- `PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES = PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES | {0037's three}` — **37**, the derivation as specified.
- `(m3c)` asserts the constant is a **SUBSET** of the fresh-v37 set (naming the offending member on failure) **AND** the three 0037 tables are **MEMBERS**.
- **Strike** the "EQUALS, never a superset check" sentence and its reason; the ledger records the supersession citing this ruling.
- Gate strictness **identical to 22-A's**. S6 step 1 unchanged in form.
- **BANKED to CHARC's register, NOT this arc:** a schema-manifest drift comparator (fresh v(HEAD) table set compared by EQUALITY against a committed manifest, updated in the same commit as any migration). That is the equality the plan wanted; it lives beside the backup gate, not inside it.

**RULED (mine, my lane): rename ALL SIX mis-named version tests, not just the one the plan names.**
Five were **already** documenting the opposite of what they check before this arc existed
(`test_migration_0036_provenance_corrections.py:56/:60` named 36 asserting 37; `test_migration_0033.py:141`;
`test_migration_0031_untracked_broker_position.py:55`; `test_migration_0030_yfinance_calls.py:33`).
This arc edits all six bodies to 38, which makes the drift worse at every one. The plan's own rule —
*the NAME must match, or the file documents the opposite of what it checks* — reads identically on all
six. One line each, zero behaviour change.

**Three intake catches, corrected against the code, no ruling needed:** `import sys` is **not in
`entry.py` at all** (zero hits in 1516 lines) → Task 3 adds it; the lone-surrogate token raises
**`UnicodeEncodeError`, not a `sqlite3.*` error** (the plan's claim held, the type was wrong); two
`_current_version == 37` sites live in a file the plan never names, though its count was right.

## YOUR FIRST ACTION

**Dispatch Task 1 into `.worktrees/22-a4-exec`** (branch `22-a4-exec`, base `9249d8da`, clean). The
round-0 report is in this session's transcript and every measurement is durable at the path above.
Re-verify the base-SHA rule against the rules the brief cites — `9249d8da` predates `c48567cc`
(the launcher fix) and `dc1b0ed3`-family additions since; **if the brief will cite a rule landed
after `9249d8da`, rebase the worktree or cut a new one.** That is the rule biting its own author.

## A COROLLARY I OWE THE ROLLOVER RULE

§6's trigger gained an in-flight precondition today because I nearly rolled over a running cell.
**The same guard has a second half I only saw afterwards: do NOT DISPATCH when you are already past
the trigger.** I dispatched executing at ~396K and was 4K from a rollover that would have killed it.
Holding to await a cell you should not have started is the same trap seen from the other side.
