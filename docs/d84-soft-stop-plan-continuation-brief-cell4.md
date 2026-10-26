# D84 -- the capital soft-stop arc: WRITING-PLANS continuation brief, cell 4

**Audience:** a fresh implementer cell with no prior conversation context.
- Cell 3 encoded the plan.
- Reviewer A round 1 found 3 majors, and every one is ruled.
- **You apply the round-1 fixes, then run Reviewer A round 2 (and round 3 if needed) to convergence, then the self-sweep.**

**Authority:** plans-only. The operator said "Stop before executing (Recommended)" on 2026-10-25. You write no `swing/` or `tests/` code.

**Cell:** `implementer-opus-high`.

## 0. Read ONLY these

1. `docs/d84-soft-stop-plan-continuation-brief-cell3.md` on main. Its section 2 (rounds and gates) binds you unchanged.
2. **The plan ledger (BINDING),** branch `d84-plan` at `37b37b66` or later. Start at the section headed `## Round-1 gate rulings of record`; read earlier rulings only where a task needs them.
3. **The plan** `docs/superpowers/plans/2026-10-26-d84-soft-stop.md` at `122eb740` (unchanged since). It carries file:line. **Do not re-survey the codebase;** open code only to apply a specific fix.
4. Round 1's findings: `C:\Users\rwsmy\swing-data\review-transcripts\d84-soft-stop\plan\round1\findings-r1.md`.
5. `docs/implementer-dispatch-recipe.md` section 3.

Do NOT read `comms/`, the director state files, or other arcs' ledgers.

**Worktree:** the EXISTING `C:\Users\rwsmy\swing-trading\.worktrees\d84-plan`, clean at `37b37b66`. Use `PYTHONPATH=.`.

## 1. The round-1 fixes (the ledger rulings govern)

- **R1-01 (CHARC C1 (a)):** keep `aplus_sensitivity/output.py:93` in T11. Restate the scope sentence as CHARC wrote it: prose and tests may move; what a harness computes does not.
- **R1-02 (CHARC C2):** path-scoped placeholder greps.
  - At the merge gate, `git grep -n "D84-MERGE-DATE" -- swing/ tests/ research/` returns nothing.
  - T12 checks `-- swing/` for exactly one history line, and `-- research/` for exactly the era-pin rows.
  - After the merge, `git grep -n "<D84 merge sha>" -- research/` returns nothing.
  - The `docs/` hits are expected.
- **R1-03 (the orchestrator):** add the empty-risk-layer test at the three tag sites: a `_risk_flags` unit test, plus a no-risk-row case in R-E3(2)b, d and e.
- **C3:** five manifest entries, said in T4 step 5 and section 7.
- **RD D1:** the era-pin set is SEVEN.
  - Add `research/harness/aplus_sensitivity/README.md:40` and `research/method-records/aplus-criteria-calibration.md:45` with RD's texts.
  - Before T11 closes, read `research/` once more for the CLAIM, including paraphrases ("production gating order", "canonical"). Name your method beside the count.
- **RD D2:** the 73 fixtures each gain a risk `pass` row, with the assertion unchanged, in T4's single commit. **Condition:** any test whose NAME or docstring claims the empty-layer case is INVERTED to the E-d pin (matches nothing) and RENAMED, not fixture-fixed. Sort the 73 by reading name and docstring. List the inverted ones by node id, and say so if there are none.

## 2. Rounds

- Cell 3's section 2 binds.
- Commit the fixes before round 2.
- **STOP AND RETURN at EVERY counted round gate** with the ledger row (depth empty) and your proposed dispositions.
- **Round 3 is the last counted round.** A fourth needs the orchestrator's written authorization. After convergence, run the uncounted self-sweep (SS-N ids), commit, and return.
- **Return in chat only;** never post to a mailbox or run `scripts/role_mail.py`. If a ruling cannot be carried as written, or a new fork appears, STOP and return with both branches.
