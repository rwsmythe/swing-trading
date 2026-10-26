# D94 (a)+(b) -- latch prompt gate + ledger-keyed cancel affordance: EXECUTING dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.

**Cell:** `implementer-opus-high`. Task 1 refactors the resolver's fill rung, which is an input to `compute_execution_parity`. CHARC accepted this as the named reason.

**Authority:**
- **Operator, 2026-10-25:** "D94 web fix first".
- **The plan is CLEARED for executing:**
  - RD on semantics: `comms/orchestrator/read/20261026T031934Z-*`;
  - CHARC on form: `comms/orchestrator/read/20261026T032305Z-*`.
  - Both are block-quoted in the plan ledger, section 7.
  - The clearances attach to the plan at `d94-cancel` `fafb92ac`, which includes CHARC's C-1/C-2 text corrections.
- **A code-bearing change beyond the plan re-opens the clearance: STOP and return.**

**KEEP YOUR READING NARROW.** Read only:
1. **The plan:** `docs/superpowers/plans/2026-10-26-d94-latch-cancel-affordance.plan.md`. It is your task ladder, and it binds.
2. **Its ledger**, for rulings and reasons.
3. **This brief.**
4. **`docs/implementer-dispatch-recipe.md` section 3:** the executing criterion, the per-round assertions, and the ledger-cut note.
5. **The code each task names.**

Do not read `comms/`, director state files, or other arcs' ledgers.

**Worktree:** `C:\Users\rwsmy\swing-trading\.worktrees\d94-cancel`, branch `d94-cancel`, head `fafb92ac`.
- Run tests with `PYTHONPATH=.`.
- Run the full suite at `-n 8`. This box ran out of memory at `-n auto`.
- Read the live DB with `mode=ro` only, never through `swing`'s `connect`.
- The Schwab token is expired on this box. The tests stub the broker, so this does not affect execution.

## 1. Execution

Execute the plan's Tasks 1-6 in order.
- **Task 1 is its OWN commit**, the refactor. `tests/latches/test_classification.py` passes UNCHANGED on it.
- **TDD:** RED, then GREEN, then the commit the task names.
- **Commits:** conventional and pathspec-only. `%(trailers)` empty; no final `-m` paragraph begins with `Word:`; no Co-Authored-By, no `--no-verify`, no amend.
- **Evidence:** quote every RED and GREEN result, read off saved output.

**Task 6 gates, before Reviewer A:**
- the FULL fast suite (`-m "not slow" -q -n 8 -p no:cacheprovider`) green, read off the saved output;
- `ruff check swing/` clean, and zero NEW findings on the touched test files;
- `git diff --stat 8acea975..HEAD -- swing/data swing/trades swing/web/routes scripts research` EMPTY. Name exactly which `swing/` files changed;
- the plan's live census probe (Task 6 step 3), on the live DB `mode=ro`, row by row against the plan's section-1 table:
  - DFTX link 2 and IMNM link 3 show the explained cancel line;
  - OII shows the explained fill line;
  - IMNM link 4 shows the unexplained state: W1 plus one ledger-keyed cancel;
  - RHI and IMNM place 12 show first-answer prompts only;
  - CADL shows nothing;
- the plan's mutation checks, run in scratch and REVERTED, with `git diff --exit-code swing/` returning 0 after each. Quote the RED that T2.1 (the OII shape) and T3.4 show against the shipped behaviour.

If the suite reds outside this arc's files: classify it by mechanism, reproduce it at `-n 0`, and never re-run until green.

## 2. Reviewer A (executing)

Run Reviewer A per recipe section 3:
- `strong` tier, with REPO ACCESS, on the diff `8acea975..HEAD -- swing tests`, generated on Windows. Tell Codex not to run git.
- All five per-round assertions.

**The prompt:**
- DESCRIBE the verdict tokens; never write one line-initially. Grep the prompt to prove it.
- Inline the rulings, or give a ledger copy cut before any round section.
- No prior-round reads. Relocate `.codex-*` and `.copowers-findings*` for the loop, then restore them. Grep each transcript.
- Carry a per-item checklist, each item answered holds / fails / cannot-tell with a file:line:
  - G1-G6 in order;
  - the ONE gate function at both sites;
  - `fill_vouches_for` as one spelling, called by the rung and the gate;
  - the Task-1 refactor byte-identical;
  - the UNKNOWN book reaching no gate;
  - the EMPTY-book anti-vacuity;
  - W1/W2 verbatim;
  - the EARLIEST cancel line with its count;
  - one `resting_order_ids` set;
  - the HTMX in-place swap contract with `hx-headers`.
- Invite challenge.

**Evidence:** save each round to `C:\Users\rwsmy\swing-data\review-transcripts\d94-cancel\exec\round<N>\`.

**Stops:**
- **STOP AND RETURN at EVERY counted round gate** with its ledger row, leaving the depth column empty.
- Stop at the first clean verdict. Post-verdict minors are fixed with no new round.
- Reviewer B and the operator's browser witness are the orchestrator's.

## 3. Return (chat only)

You NEVER post to a mailbox and never run `scripts/role_mail.py`. Return:
- commits, with their trailers;
- RED and GREEN results per task;
- suite counts;
- the envelope diff;
- the live census probe, row by row;
- mutation results;
- the round row(s) and findings, each with a proposed disposition;
- every deviation.

**If anything does not fit, STOP and return.**
