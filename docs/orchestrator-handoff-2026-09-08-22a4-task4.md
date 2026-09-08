# Orchestrator handoff — 2026-09-08 — 22-A4 at the Task 4 boundary

**From:** the generation that took 22-A4 from the Task-1 dispatch through Tasks 0b/1/1b/3, one
stopped-and-routed task (1c), and four director rulings.
**Rolled at 344,139** (measured, `python scripts/cell_depth.py --sessions --live 1`), at a clean
boundary: nothing in flight, no ruling outstanding.
**Bootstrap:** `scripts/orchestrator_bootstrap.md` → `docs/orchestrator-context.md` → this file.

**Every fact here was re-derived from disk at handoff time. Do the same — this arc has corrected facts
in five separate rulings and briefs, and EVERY ONE was caught by an implementing cell, never by its
author.**

---

## 1. YOUR FIRST ACTION — dispatch Task 4. Nothing is running.

- Worktree `.worktrees/22-a4-exec`, branch `22-a4-exec` @ **`39104723`**, clean. The branch is based on
  `main @ 2d9e4a34` and carries **THREE** commits: `48029a06` (Task 0b+1), `f0f0217f` (Task 1b),
  `39104723` (Task 3).
- **`main` @ `2fd1e384`**, 9 commits unpushed (counted, not estimated). Live schema **v37**; migration 0038 is UNAPPLIED.
- Plan of record: `docs/superpowers/plans/2026-09-06-phase22-arc-a4-EXECUTING.md` — the 1,889-line
  EXTRACT, **not** the 4,370-line design record. **Task 4 at `:524`, Task 5 at `:569`.**
- Ladder remaining: **Task 4 → Task 5 → the Codex loop (plan Tasks 6-7) → orchestrator QA → reviewer B
  → merge gate (both directors) → S9 step 0 (a BLOCKING live pipeline run) → the operator-witnessed
  0038 migration (extract S6, `:1761`).**

## 2. THE MECHANISM I CHANGED MID-SESSION — use it, it is not optional now

**DO NOT REBASE THE WORKTREE MID-LADDER.** I rebased twice to carry briefs in, and each rebase
rewrote a sha I had already published to the directors (`fed8e76e`→`873675fd`→`48029a06`;
`94fbc73d`→`f0f0217f`). Patches were byte-identical each time and I proved it, but a published sha
that no longer resolves is a wrong report.

**Instead:** commit the brief to `main` (the convention is *committed before dispatch*, not *present in
the worktree*), and point the cell at **main-repo absolute paths**:

- `C:/Users/rwsmy/swing-trading/docs/<brief>.md`
- `C:/Users/rwsmy/swing-trading/docs/implementer-dispatch-recipe.md`

**AND SAY WHICH COPY GOVERNS, EXPLICITLY.** The cell definitions
(`.claude/agents/implementer-*.md:9`, **five** of them) name the recipe by a RELATIVE path that
resolves to the worktree. Silence therefore defaults to the worktree copy. CHARC has taken the durable
fix (absolute path + a stale-copy warning, in the cell definitions) to the operator; **until it lands,
your per-dispatch override line is the belt and is MANDATORY.** Record the base-SHA as *"rules read
from main @ `<sha>`"*, not a worktree sha. First dispatch under this (Task 3) worked.

**But do not write my sentence.** I wrote "your worktree's copies are stale BY DESIGN"; the cell
measured the blob ids and they were **byte-identical**. Say what is true at dispatch time: point at
main's copy, say main's wins on any difference, and do not assert a drift you have not measured.

## 3. WHAT WILL BITE YOU

- **THE LADDER IS SPLIT ONE TASK PER CELL, deliberately.** Task 1's cell hit 350,147; round 0 hit
  251,009. A whole-ladder cell blows the 400K cap mid-work and returns nothing QA-able.
- **`-n auto` GETS KILLED FOR MEMORY IN THIS SEAT.** Twice. The box carries 16 workers or a deep
  orchestrator, not both — the CELLS run `-n auto` fine. So **your independent suite verification is
  systematically weaker than the cell's**; use `-n 4`, and SAY so, because it is a weaker probe of the
  xdist-load flake class. Do not report a `-n 4` green as if it re-confirmed a flake argument.
- **Baseline on `39104723`: 12247 passed / 13 skipped / 0 failed** (mine, `-n 4`; the cell's `-n auto`
  agrees). Re-measure; do not carry mine forward as the cell's baseline without saying whose it is.
- **`git ... | grep -c` returns exit 1 on zero matches**, so an `&&` chain silently skips the rest. It
  ate my trailer audit and I noticed only because an echo was missing. Use `;` in verification chains.
- **Plan line anchors have DRIFTED** by Tasks 1/1b/3 (`entry.py:884`→`:1012`, the immediate ladder
  `:1126-1163`→`:1253-1291`, and more). **Symbols are correct; numbers are not.** Ground on symbols.
- **The DESIGN RECORD is wrong where the plan is right** on at least one point (S2.2 claims
  `import sys` is already in `entry.py:8`; it was absent, now added by Task 3). Prefer the extract.

## 4. THE TASK 4 HAZARD, KNOWN BEFORE YOU START — put it in the brief

Task 3's cell hit this inside its own `(k7b)` row and flagged it for Task 4 rather than fixing
someone else's task: **a hostile `__context__` subclass reaching pytest's `TracebackException`
formatter produces a session-aborting `INTERNALERROR`, not a red.** An INTERNALERROR aborts the
session and can MASK OTHER RESULTS — strictly worse than a failure. Plan `(RD-a4)` schedules the same
two subclasses in Task 4's four-row matrix. **Remedy, one line:** `pytest.raises(BaseException)` plus
an explicit `type(x) is <Subclass>` assertion beside the `is`-identity one. Discrimination is
preserved. Write this into the Task 4 brief; it is the cheapest thing in this file.

## 5. RULINGS AND AUTHORITIES GRANTED — the record, because a cell message is not one

- **(m3c) BRANCH A** (CHARC): the expected-tables constant is a SUBSET assertion + membership of
  0037's three, NOT equality. `db.py:575` is `expected - actual`, a floor. The schema-manifest drift
  comparator is **banked to CHARC, deliberately not built**.
- **Version-test naming** (CHARC): name-matches-assertion wins; canonical form `_is_head`; a version
  NUMBER only for migration-specific assertions. "Grep-history continuity" is **not** a convention —
  zero hits in every live rule doc. Banked as a CLAUDE.md gotcha at `ad067031`. **A tests-only rename
  rider is QUEUED for AFTER the merge** (`docs/phase3e-todo.md`, entry at `5038f79f`), `sonnet-med`;
  its scope includes deleting the false citation at its three sites.
- **Task 1c: the `ReservedJournalFieldError` re-base is DECLINED — shape 3** (CHARC, superseding his
  own extension ruling). The type stays on `Exception`. **No commit exists for 1c and none should.**
  Banked as D34's third instance with the reachability map.
- **Scope grants I made:** Tasks 0b+1 as one cell; 1b, 1c, 3 each as their own. All returned; all QA'd
  against disk; all posted to both directors. **No fourth-round authorizations, no envelope widenings,
  no mid-round fix authorizations were granted by me.** Nothing is outstanding.

## 6. THE POSTURE THAT IS ACTUALLY EARNING ITS KEEP

Five cells; **one of them committed nothing and was the most valuable** — Task 1c stopped on a
finding that a re-base would silently re-route two nightly reconciliation paths, which CHARC's own
module-scoped check could not have found and which would otherwise have shipped green.

**Write the stop-and-route instruction into every brief, and mean it.** Also: **where a check is
scoped to one module or file, ask whether the question is actually about a module.** That single
distinction is what the 1c stop turned on, and it is now in the Task 3 brief's §3 verbatim.

Corollary for you personally: my briefs added facts to the plan **three times, and all three times the
added fact was the defect** (a mis-anchored strike line; a sibling-symmetry argument that carried shape
but not reachability; a stale-by-design claim that was false). **The plan is the spec. A brief's job is
the things the plan cannot carry — scope, conventions, gates, the baseline, and who rules what.**

## 7. QUEUE BEHIND 22-A4

The post-merge rename rider (§5). Then D46, D45, D44/D47, the D39 sweep, D42's export failure. The
admitting gate stays open: 131 post-barrier candidates, **zero A+**. Open trades: 23 CADL
(partial_exited), 24 RHI, 25 OII, 26 NRIX, 28 PBF. Real money.
