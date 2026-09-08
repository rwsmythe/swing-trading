# Orchestrator handoff — 2026-09-08 — 22-A4 with the fork RULED and the fix leg briefed

**Supersedes** `orchestrator-handoff-2026-09-08-22a4-task4.md` (same UTC date, earlier generation).
**From:** the generation that took 22-A4 from the Task 4 dispatch through Tasks 4, 5 and the Codex
A-loop, and routed the loop's design fork to a ruling.
**Rolled at 362,057** (measured, `python scripts/cell_depth.py --sessions --live 1`), at a clean
boundary: nothing in flight, no ruling outstanding, the next dispatch written and committed.
**Bootstrap:** `scripts/orchestrator_bootstrap.md` → `docs/orchestrator-context.md` → this file.

**Every fact here was re-derived from disk at handoff time. Do the same.** This arc has now corrected
facts in TEN rulings, briefs, plan rows and handoffs. **Two of those were mine, and one was in the
handoff I inherited** — the class is not other people's.

---

## 1. YOUR FIRST ACTION — dispatch the fork-fix leg. Nothing is running.

- **The brief is written and committed: `docs/22-a4-fork-fix-leg-dispatch-brief.md` (`dcbcae3d`).**
  It is dispatchable as-is. I stopped at the brief rather than dispatching because the QA it will
  generate did not fit my remaining budget — the rollover mirror, applied.
- **Recommended cell: `implementer-opus-high`.** Named reason: it implements a containment change to
  the arc's most safety-critical function plus a confirming Codex round; mis-adjudication ships.
- Worktree `.worktrees/22-a4-exec`, branch `22-a4-exec` @ **`a32ea9d5`**, clean, **10 commits above
  `2d9e4a34`**. **`main` @ `dcbcae3d`, 17 commits unpushed** (counted).
- Live schema **v37**; migration **0038 is UNAPPLIED**. Re-verify at the merge gate.
- **Ladder remaining:** the fix leg (R2/R3/R4) → **round 3, the confirming round** → orchestrator QA
  → **reviewer B (your own second eye)** → the merge gate where both directors wait → **S9 step 0, a
  BLOCKING live pipeline run** → the operator-witnessed 0038 migration (extract S6).

## 2. THE RULING IS IN GIT BECAUSE `comms/` IS NOT — read this before you trust any inbox

**`comms/` is gitignored (`.gitignore:21`).** A director ruling that arrives by role-mail exists on
ONE machine, in ONE directory, and **does not survive a handoff**. That is the Phase-21 close-audit
class exactly. So RD's ruling on the fork is **transcribed verbatim into §2 of the fix-leg brief**,
with RD named as the author of every clause and the orchestrator as courier.

**Do this whenever a ruling lands.** A ruling that only exists in `comms/` is a ruling you are one
rollover away from losing. The four obligations I could not act on are likewise banked in
`docs/phase3e-todo.md` (`86f92b43`) rather than carried in context.

## 3. THE RULING, IN ONE PARAGRAPH — do not re-open it, implement it

The loop stopped on `A4X-R2-01` (CRITICAL): at `_settle_by_attempt_identity`'s `return found` the
probe has returned a row and the ticker has matched — durability is **proven** — yet that `return`
sits inside the helper's own `except BaseException`, so a fault discards the proof and the caller
re-raises over a durable entry. RD **rejected branch A** (a re-probe is a regress — its own return is
the same window one frame later), **reframed the class as IRREDUCIBLE** (no branch closes it; the
question is which DIRECTION is reported), and decided it on the precedent that **clause 1 already
treats a post-`commit()` fault as a degraded SUCCESS** — so the arc today handles two identical
situations oppositely. **Window 1 → branch B in its MINIMAL capture-then-return form, `except` scope
UNCHANGED** (narrowing would change which exception escapes — the R11-03 identity property).
**Window 2 → DECLARED** as one more member of an alarm family the declaration already prices, **with
the composition stated once for the WHOLE family.** Three RED-first rows pin it; the middle one pins
the DECLARED direction rather than a fix.

## 4. WHAT WILL BITE YOU

- **`-n auto` GETS KILLED FOR MEMORY IN THIS SEAT.** Use `-n 4` and SAY SO — it is a weaker probe of
  the xdist-load flake class. **Every suite number in this arc since Task 4 is an `-n 4` number**, so
  none of them re-confirms that class. **The binding merged-head run is still OWED and is yours.**
- **THE LOOP CELL FINISHED AT 510,944 — OVER THE 400K CAP.** It returned safely only because it
  stopped on the fork. Keep the ladder split one leg per cell; do not hand a cell the fix leg AND a
  long loop and expect a QA-able return.
- **Plan line anchors into `entry.py` have DRIFTED HARD** — Task 5's target moved ~600 lines from the
  plan's `:973-1030` to `:1575`. **Symbols and content are correct; numbers are not.** Ground on
  symbols and re-locate at read time.
- **`git … | grep -c` returns exit 1 on zero matches**, silently skipping the rest of an `&&` chain.
  Use `;` in verification chains.
- **A heredoc carrying prose with apostrophes broke `role_mail` mid-post** once this session (nothing
  was written — it failed loudly). Write long message bodies with the Write tool, then
  `--body-file`. **Subject cap is 80 chars** and the tool refuses above it.
- **The design record is wrong where the extract is right on at least one point** (its S2.2 claims
  `import sys` was already in `entry.py`; Task 3 added it). **Prefer the extract** — EXCEPT that the
  extract does not carry S2.3/S2.4 at all, which Task 4 needed. Both facts are live.

## 5. AUTHORITIES I GRANTED — the record, because a cell message is not one

- **Scope grants:** Task 4, Task 5, and the Codex A-loop (plan Tasks 6-7) each as its OWN cell. All
  three returned, all three QA'd against disk, all three posted to both directors.
- **NO fourth-round authorization was granted. NO envelope widening. NO mid-round fix authorization.
  Nothing is outstanding from me.**
- **Cells used:** Task 4 `implementer-opus-high` (operator-approved, against the sonnet default);
  Task 5 `implementer-sonnet-high` (the default, no notch moved); the loop `implementer-opus-high`
  (the recipe's own must-converge-Codex exception). Review tier `strong` throughout.
- **Landed rulings this session:** CHARC — the handoff-fact rule (a handoff carries pointers and
  state, never a plan or code fact restated from memory; facts re-verified at the artifact at WRITE
  time, method stated); CHARC — the accepted-limitations prompt CITES the declaration by path and
  clause, never restates it; CHARC — concurrence that the condition-3 limitation belongs in the Task
  5 declaration, not a review-round note. RD — the fork ruling in §3.
- **My own ruling, marked as mine in the brief that carried it:** routing the condition-3 limitation
  into the Task 5 declaration. The cell verified it at the code and REFINED it — the unreachable
  state is "token `None` WITH a resolved path", not "either field `None`."

## 6. WHAT THIS SESSION IS WORTH REMEMBERING FOR

**The instruments caught things, and they caught them from the inside.** Task 4's cell measured its
OWN first draft passing the mutant `(pr4)` exists to exclude, and repaired it. The loop's cell
REJECTED its own round-1 CRITICAL after finding the over-broad paraphrase that produced it was **its
own round-1 prompt**, then quoted the lock clause verbatim in round 2. Its first mutant PASSED because
migration 0038's header comment contains the literal `BEGIN;`/`COMMIT;`, so a string replace edited
prose and never built the mutant.

**And the QA earned its keep twice.** I proved Task 5's "no behaviour change" by comparing ASTs with
docstrings stripped — identical, so the claim stopped being a claim. I performed the red step on Task
4's central assertion rather than reading it, and got exactly the promised discrimination: row 3
alone, rows 1/2/4 green.

**The thing I got wrong:** my Task-4 brief said the arc diff was "six commits"; it is five. A cell
caught it at intake. That is the second brief-fact error of mine in this arc, landing in my own text
within a day of CHARC banking the rule against exactly it. **Verify the number you are about to
write, including the ones that feel like bookkeeping.**

## 7. QUEUE BEHIND 22-A4

Banked in `docs/phase3e-todo.md` at `86f92b43`, so they survive this handoff: **(1)** the
accepted-limitations citation requirement for the confirming round; **(2)** the declared condition-3
limitation's own text; **(3)** **AT THE MERGE GATE, reword `b3b518f9`'s final commit paragraph** — it
begins `Tests:` and git parses it as a trailer (`Co-Authored-By` is **0**; the streak is NOT at risk;
recipe §2 assigns this to the orchestrator, which is why the cell stopped rather than self-fixing);
**(4)** the version-mirror rename rider, whose scope now also names
`test_CONTRACT_a_commit_whose_own_return_was_LOST_re_raises` — rewritten in place by Task 4 and now
asserting SUCCESS, a claim falsified in normative position.

**Named, not fixed, and probably CHARC's D34 register rather than this arc:**
`ReservedJournalFieldError` derives from bare `Exception`, so EVERY non-byte-exact column name on the
corrector path — not just `attempt_id` — surfaces as a CLI traceback or a web 500 instead of exit 2 /
400. `74cb2815` closes it only for the immutable set.

Then D46, D45, D44/D47, the D39 sweep, D42's export failure. **The admitting gate stays open: 131
post-barrier candidates, zero A+. Open trades: 23 CADL (partial_exited), 24 RHI, 25 OII, 26 NRIX,
28 PBF. Real money.**
