# D89 -- observe's per-step read memo: EXECUTING dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.

**Cell:** `implementer-opus-high`. This is measurement-chain code, the recipe section 2A exception, and both directors concur.

**Authority:**
- **Operator-approved 2026-10-20:** "D89 is approved, then soft-stop arc"; then "Yes, D90 after D89 and before soft-stop arc".
- **The plan is CLEARED for executing:**
  - RD on neutrality, with E1 confirmed: `comms/orchestrator/read/20261020T054657Z-*`;
  - CHARC on form: `comms/orchestrator/read/20261020T054835Z-*`.
  - Both clearances are block-quoted in the plan ledger, section 5.
  - The clearances attach to the plan as written at `d89-memo` `e1e1b442`, plus the K-8 ledger correction at `6bd6e347`.
- **A code-bearing change beyond the plan re-opens the clearance:** STOP and return instead.

**KEEP YOUR READING NARROW.** Read only:
1. **The plan:** `docs/superpowers/plans/2026-10-20-d89-observe-read-memo.plan.md`. It is the task ladder, and it binds.
2. **The plan ledger**, in the same folder. Read its rulings and corrections, for reasons when you need them.
3. **This brief.**
4. **`docs/implementer-dispatch-recipe.md` section 3:** the EXECUTING criterion, the per-round assertions, and the ledger-cut note.
5. **The code each task names.**

Do not read `comms/` beyond the two clearance files, director state files, or other arcs' ledgers.

**Worktree:** `C:\Users\rwsmy\swing-trading\.worktrees\d89-memo`, branch `d89-memo`, head `6bd6e347`.
- Run every test from the worktree with `PYTHONPATH=.`.
- Live DB: `mode=ro` only, and never through `swing`'s `connect`.
- Census-style replays run on COPIES of cache files in your scratchpad. The round-0 snapshot evidence is at `C:\Users\rwsmy\swing-data\review-transcripts\d89-memo\plan\round0\`.

## 1. Execution

Execute the plan's task ladder in order:
- TDD: RED, then GREEN, then the commit each task names, conventional and pathspec-only;
- `%(trailers)` empty after each commit; no final `-m` paragraph begins with `Word:`;
- no Co-Authored-By, no `--no-verify`, no amend.

Quote every RED and GREEN run, read off saved output.

**Gates before Reviewer A:**
- the FULL fast suite (`python -m pytest -m "not slow" -q -n 8 -p no:cacheprovider`) green, read off the saved output. **Use `-n 8`:** this box ran out of memory at `-n auto` earlier.
- `ruff check swing/` clean, and zero NEW findings on the touched test files (the orchestrator's standing reading of the ruff gate);
- the plan's closure greps at their stated values, including the "zero schwab" docstring grep;
- `git diff --stat 31a293b4..HEAD -- swing/data swing/trades swing/web scripts research` EMPTY;
- the plan's mutation checks, run in scratch and REVERTED, with `git diff --exit-code swing/` returning 0 afterwards. Mutation M1 ("the memo write drops `and populate_ok`") must turn T-H1 RED, quoted for the merge report.
- the W5 replay count (ii) on the copies, quoted beside the plan's expected `resolve_reads`.

**If the suite reds outside this arc's files:** classify the red by MECHANISM and reproduce it at `-n 0`. Never re-run until green; report it.

## 2. Reviewer A (executing)

Run it per recipe section 3:
- `strong`, with REPO ACCESS, on the diff `31a293b4..HEAD -- swing tests`, generated on Windows; tell Codex not to run git;
- the plan's executing-review bundle;
- all five per-round assertions.

**Prompt rules:**
- DESCRIBE the verdict tokens; never write one line-initially. Grep the prompt to prove it.
- Give the rulings INLINED, or a ledger copy CUT before any round section.
- No prior-round reads: relocate any `.codex-*` / `.copowers-findings*` out of the worktree for the loop, then restore them. Grep each transcript.
- Add a per-item CHECKLIST (holds / fails / cannot-tell, each with a file:line):
  - the C3 literal (`populate_ok` gates the write);
  - D1 (the populate runs on every call);
  - E1 (memo first);
  - the key;
  - the local memo's lifetime;
  - `resolve_reads` exactness;
  - the docstring describing both ladder branches;
  - K-4;
  - each discriminator's RED claim.
- Invite challenge.

**Evidence:** save each round to `C:\Users\rwsmy\swing-data\review-transcripts\d89-memo\exec\round<N>\`.

**Stops:**
- STOP AND RETURN at EVERY counted round gate with its ledger row, in an exec ledger beside the plan. Leave the depth column empty.
- Stop at the first clean verdict. Post-verdict minors are fixed without another round.
- The round-5 check-in binds.
- Reviewer B is the orchestrator's.

## 3. Return (chat only)

You NEVER post to a mailbox and never run `scripts/role_mail.py`. Return:
- commits, with their trailers;
- RED and GREEN results per task;
- the suite counts;
- the closure greps;
- the mutation results, M1 quoted;
- the W5 replay count;
- the round row(s) and findings, each with a proposed disposition;
- every deviation.

**If anything does not fit, STOP and return.**
