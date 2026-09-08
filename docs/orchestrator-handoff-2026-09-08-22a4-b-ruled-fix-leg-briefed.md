# Orchestrator handoff — 2026-09-08 — 22-A4: Reviewer B RAN, both items RULED, the fix leg briefed and UNDISPATCHED

**Supersedes** `orchestrator-handoff-2026-09-08-22a4-b-ready.md` (same UTC date, earlier generation).
**From:** the generation that ran Reviewer B, adjudicated it, carried both director rulings into git,
and briefed the fix leg without dispatching it.
**Rolled at 370,768** (measured, `python scripts/cell_depth.py --sessions --live 1`), below the 400K
trigger, at an operator-decided boundary. **Precondition met: NO cell in flight — I dispatched none.**
**Bootstrap:** `scripts/orchestrator_bootstrap.md` → `docs/orchestrator-context.md` → this file.

**Every fact here was re-derived from disk at write time, method stated. Do the same.**

---

## 1. YOUR FIRST ACTION — spawn the fix-leg cell. The brief is committed and complete.

**`docs/22-a4-reviewer-b-fix-leg-dispatch-brief.md` @ `b10be35d`.**

**IT IS ON BRANCH `22-a4-exec` ONLY — IT IS NOT ON `main`.** Read it from the worktree
(`.worktrees/22-a4-exec/docs/...`) or `git show b10be35d:docs/22-a4-reviewer-b-fix-leg-dispatch-brief.md`.
This is deliberate (the fix lands on the arc branch) but it is also the Demand-C hazard shape — a
governing document reachable only from an unmerged branch — so **do not tear down that worktree while
this brief is the live specification.**

- **Cell: `implementer-sonnet-high`** — the 2026-09-07 executing default, no notch moved. Announced in
  chat and NOT vetoed by the operator. The design is settled by two director rulings; both changes are
  small and fully prescribed.
- The operator answered **"roll now, successor dispatches"** to a direct question about this exact
  dispatch. **The dispatch itself is authorized in substance; you are executing his answer, not
  re-opening it.** Spawn it, then QA it.
- Base SHA `2d9e4a34` verified at brief time: all five rules the brief cites were confirmed PRESENT in
  that worktree's OWN copies of `implementer-dispatch-recipe.md` and `harness-architecture.md`. You do
  not need to redo that check unless you change what the brief cites.

**The two things you must REFUSE at QA, both pre-ruled:**

1. **A `B-1` fix that also closes `B-2`.** `B-2` (every payload field after the first silently
   discarded) is PRE-EXISTING, OUT-OF-ENVELOPE and banked to CHARC's register. CHARC: *"A fix that
   closes `B-1` by closing `B-2` has widened the arc; refuse it at QA."*
2. **Any movement in a locked function other than `_durability_probe`.** See §4.

## 2. STATE, re-derived at write time

- **`main` @ `361cb364`**, tree clean, **29 commits ahead of origin, UNPUSHED** (counted). My handoff
  commit will make it 30.
- **Branch `22-a4-exec` @ `b10be35d`**, worktree `.worktrees/22-a4-exec`, **clean**. Four commits added
  this generation, all docs-only, **all trailers `[]`**:
  `c5991941` Reviewer B's ledger section · `28a9b35f` CHARC's `B-1` ruling · `0bbf825c` RD's `B-3`
  ruling · `b10be35d` the fix-leg brief.
- **ZERO production code changed this generation.** The reviewed tree is still `84e90bab`.
- **Trailer sweep over the arc:** `Co-Authored-By` key count **0**. Exactly ONE non-empty trailer —
  `b3b518f9`'s `Tests:` paragraph, the known reword item, still owed.
- **Live schema v37; migration 0038 UNAPPLIED — I MEASURED THIS MYSELF** by a read-only query
  (`select version from schema_version` on `~/swing-data/swing.db`), not inherited. Re-verify at the
  gate anyway, before the witnessed migration.
- `.worktrees/22-a4-plan` @ `f5e03921` still on disk, unused for two generations.

## 3. WHAT REVIEWER B DID, AND WHY IT MATTERS TO YOU

**B ran on `84e90bab` in the cold-audit form and returned `NEW_CRITICAL_MAJOR_FOUND`.** All five
mechanical assertions passed as measurements: `gpt-5.6-sol`, effort `high`, anchored `^ERROR` **0**
(unanchored **18** — the repo-prose false positive the anchor exists to defeat), anchored footer **1**,
`^NEW_CRITICAL_MAJOR_FOUND` **2** with `^NO_NEW_CRITICAL_MAJOR` **0**. Process confirmed EXITED before
the transcript was read. Transcript 1,832,058 bytes, preserved with its prompt and runner to
`~/swing-data/review-transcripts/22-a4-exec/` **the moment assertion 5 passed**.

Full record: the ledger's `REVIEWER B` section @ `c5991941`.

**The finding that matters: `B-1`, MAJOR, INTRODUCED, IN ENVELOPE.** `operator_alternative` does not
refuse a trailing `attempt_id` — `_handle_single_field_correction` selects
`next(iter(payload.keys()))` and only that key reaches the guard, while the whole-payload preflight is
called from exactly ONE site (`_handle_multi_field_correction`), measured by an AST walk over the call
graph. **I reproduced it** on a database built by the real migration runner through 0038: no exception
at all, `CorrectionResult(correction_id=1)` returned, the stop written, the token untouched, **the
discrepancy terminalized**. Keys reversed, the guard fires. It falsifies arc claim 7 — CHARC's attached
condition and the sole ground for the envelope widening.

**Why this is the lesson of the generation:** four counted A rounds and a director ruling passed over
that module. B found the third path because it did the one thing the roster never does — hand
`operator_alternative` a payload with TWO keys. The `(m8b)` rows are *named* for order-independence and
exercise `operator_truth`, a different route. **The tests are not wrong about what they assert; the
roster has a hole where a fourth surface should be.** 18-H.4's disjoint-finding-set pattern at N+1,
and the reason B is run by different hands.

`B-3` MINOR/introduced (the probe URI + a test whose header claims what its assertion cannot measure) ·
`B-2` MAJOR/pre-existing/out-of-envelope, banked · `B-4` MINOR/pre-existing, already the queued rename
rider whose trigger is AFTER merge.

## 4. LOCK-A — AND IT IS ABOUT TO MOVE, DELIBERATELY

**`git diff --stat` on `entry.py` reads ~123 insertions across this arc and IS NOT a lock breach.**
Measure the three locked functions by **AST source segment sha256**, never by file diff. I measured
`a32ea9d5` → `84e90bab` myself: **all three IDENTICAL.**

| function | sha256 at `a32ea9d5` == `84e90bab` | after the fix leg |
|---|---|---|
| `_entry_transaction` | `c53b2786e3a7518d5c1341af399eeac9d4d8e16cc615c28d093e631c56240d69` (10,990) | **UNCHANGED** |
| `_durability_probe` | `c16ea4656c1c2e415beb04f3a04f141719cfc60a793465eb5d9b4e70616c4914` (4,113) | **MOVES** (RD's `B-3`) — diff must be the URI literal + one docstring paragraph ONLY |
| `record_entry` | `5b6aa7466175ff4c91448bf8dbb6f18f19b6a2974e12dfab20d2e1aa41710fb7` (25,939) | **UNCHANGED** |

**One precision the PREVIOUS handoff did not carry and you should:** `a32ea9d5` is a **MID-ARC** commit
(the rounds 1–2 ledger). So "identical to `a32ea9d5`" proves *unchanged since the lock was SET*, **not**
*untouched by the arc*. Both directors said they re-measure at their gates; so should you.

My measuring script is at
`<scratchpad>/lockcheck.py` — session-scoped and therefore **gone when you read this**; it is ~40 lines
(`git show <rev>:<path>` → `ast.parse` → `ast.get_source_segment` → sha256) and faster to rewrite than
to hunt for.

## 5. AUTHORITIES I GRANTED — the record, because a cell message is not one

**I GRANTED NONE. I dispatched no cell this generation, so there is no envelope widening, no scope
grant, no mid-round fix authorization and no round authorization outstanding from this seat.**

- **NO fifth counted A round is authorized, by anyone.** CHARC ruled it out and RD concurred for his
  own item. **If the fix leg's return, or B's re-run, surfaces a NEW in-envelope introduced major, that
  is the moment to reconsider — and it needs YOUR fresh written authorization naming the finding.**
- **One inline verification by me, not a grant:** the `B-1` reproduction. I added a temporary test
  file, ran it, **deleted it, and verified the tree clean** (`git status --porcelain -uall` empty).
- **One premise answered by me rather than left to the cell:** `open_connection` does not re-encode or
  validate URIs, so RD's flagged risk does not materialize and the leg is one leg. See §6 for the
  caveat that goes with it.

**Landed rulings this generation, both transcribed into git as LITERAL BLOCK QUOTES built mechanically
from the message files and verified byte-for-byte by containment** (so "verbatim" is earned, not
claimed, and neither director is being asked to verify a re-setting):

- **CHARC on `B-1`** (`28a9b35f`): INTRODUCED, IN ENVELOPE — completing the condition is the widening's
  own content. Five-part shape (a)–(e). No fifth A round. **B RE-RUNS on the post-fix tree**, because a
  clearance attaches to the tree its holder verified. `B-2` banked to his register.
- **RD on `B-3`** (`0bbf825c`): fix BEFORE merge, inside the B-1 leg, minor scope. His deciding reason:
  the property holds today by WRITER-ABSENCE, *"a claim with a shelf life"*; `cache=private` makes it a
  construction-time guarantee for nine characters. He measured the mechanism by execution and found
  `sqlite3.enable_shared_cache` **does not exist on this runtime** (removed in 3.12).

Both rulings arrived as `fyi` and both explicitly left the dispatch to the operator. Neither trod on
the other's item — one ruler per item, honoured on both sides.

## 6. WHAT I GOT WRONG, AND ONE THING I ALMOST LET STAND

1. **My negative control for RD's flagged premise was NOT DISCRIMINATING, and I nearly reported the
   result as if it were.** I opened `?mode=rw&cache=private` through the real `open_connection`, got a
   clean open and `read_uncommitted == 0` — then ran a bogus `?nonsense=1` as a control and **SQLite
   ACCEPTED IT TOO.** So my open proves only that nothing REJECTS or MANGLES the parameter; it does
   **not** prove the parameter took effect. What proves the mechanism is **RD's** execution, cited as
   his in the ledger and in my post back to him. **The bounded-search-reported-as-a-total class is this
   arc's most-repeated failure, from four different seats now, and this was the fifth instance
   avoided rather than a sixth committed.** Report a control that failed to discriminate AS such.
2. **I read the operator's "proceed" as authorizing the dispatch, and it did — but I could not have
   QA'd it.** I had the brief written before I checked my own depth against what a QA costs. The order
   should be: measure the budget, THEN decide whether the next action is mine. The gauge is a
   precondition, not a caveat, and I ran it late.

## 7. WHAT WILL BITE YOU

- **The harness expands `$VAR` inside `wsl.exe bash -lc '...'` — CONFIRMED LIVE this generation.**
  `$PATH` expanded to the *Windows* PATH and the shell died on a paren. Every Codex invocation goes in
  an **LF-verified script file with LITERAL paths only**, run as `bash /mnt/c/.../run.sh` (never a
  PATH-initial argument), with relative redirect targets after one `cd`, and both output files
  **pre-created Windows-side**. The working B runner is preserved at
  `~/swing-data/review-transcripts/22-a4-exec/run_b_22a4.sh` with all five hazards commented.
- **`role_mail.py` caps the subject at 80 chars** and refuses the post outright (nothing written) — it
  bit me once. Use `--body-file` always; `cd` to the MAIN repo in the SAME invocation; **verify
  delivery on disk**, the `posted ->` line reads identical on a misdelivery.
- **The Bash tool's PATH on this box lacks `/usr/bin`** — `cat`, `ls`, `sed`, `grep` all fail with
  "command not found" until you `export PATH="/usr/bin:/bin:$PATH"`. PowerShell is unaffected.
- **`-p no:xdist` breaks the suite** (`addopts` carries `-n auto`, which then becomes an unrecognized
  argument). Use **`-n 0`** for a single-file run, `-n 4` for the suite. `-n auto` is memory-killed in
  this seat; **the binding merged-head run is the OPERATOR'S**, in his shell, and is still owed.
- **`Add-Content -Encoding utf8` on PowerShell 5.1 can inject a BOM mid-file.** I checked for one after
  each ledger append (zero hits) — keep checking, or append via Python with `newline="\n"`.
- **Reviewer B's own scratch must be relocated out of the worktree for B's pass** and restored after —
  the recipe mandates both repo read-access and keeping the transcripts at the worktree root, which
  puts the review's output inside its input. I moved all 13 A-loop files out and back; the restore is
  done and the tree is clean.

## 8. THE LADDER FROM HERE

**fix leg (§1)** → **full fast suite on that head** → **B RE-RUN on the post-fix head** (CHARC's
ruling; same form, same five assertions, same durable path — and it is YOURS, not the cell's) → **the
`b3b518f9` trailer reword** (recipe §2 assigns it to this seat; amend, the branch is unpushed so no
force is needed; keep the final `-m` paragraph plain prose and re-run the sweep after) → **the
merged-head `-n auto` suite run IN THE OPERATOR'S SHELL** → **the merge request** (carry the summed
per-round `tokens used` spend, recipe §4) → **both director gates** (CHARC nine checks; RD seven, three
merge-blocking on measurement integrity) → **S9 step 0, a BLOCKING live pipeline run** → **the
operator-witnessed 0038 migration**.

## 9. QUEUE BEHIND 22-A4

In `docs/phase3e-todo.md`: the version-mirror rename rider (**trigger: AFTER the merge** — `B-4`
independently rediscovered it, trigger unchanged), the round-4 out-of-scope catches. **New this
generation: `B-2`**, banked to CHARC's register (he will write the D-row when the operator directs file
edits) — the silent discard of every payload field after the first, on BOTH operator surfaces,
pre-existing, the enabling condition of `B-1` and wider than it; its fix is corrector-semantics and its
own item. The backup-gate formula class is **discharged** (CLAUDE.md corrected at `25870c42`, compressed
at `07bd904e`).

Then D46, D45, D44/D47, the D39 sweep, D42's export failure, and `ReservedJournalFieldError`'s
bare-`Exception` base (D34's third instance).

**The admitting gate stays open: 131 post-barrier candidates, zero A+. Open trades: 23 CADL
(partial_exited), 24 RHI, 25 OII, 26 NRIX, 28 PBF. Real money.**
