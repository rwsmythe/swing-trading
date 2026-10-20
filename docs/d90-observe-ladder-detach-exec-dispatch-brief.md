# D90 -- observe ladder detach: EXECUTING dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.

**Cell:** `implementer-opus-high`. `_bar_for_date`'s populate feeds the append-only observation log, so this is measurement-chain code. RD concurs.

**Authority:**
- Operator, 2026-10-20: "Yes, D90 after D89 and before soft-stop arc".
- The plan is CLEARED for executing:
  - RD on neutrality: `comms/orchestrator/read/20261020T075410Z-*`;
  - CHARC on form: `comms/orchestrator/read/20261020T075500Z-*`. Its rulings are also recorded in the D90 row at main `ebbc9158`.
- The clearances attach to the plan at `d90-detach` `d256bdfa`.
- **A code-bearing change beyond the plan re-opens the clearance: STOP and return instead.**

**MERGE SEQUENCING (yours to know, not to act on):** D90 does NOT merge until at least one post-D89 nightly has run on main. RD and CHARC concur. You execute and review; the orchestrator holds the merge.

**KEEP YOUR READING NARROW.** Read only:
1. the plan: `docs/superpowers/plans/2026-10-20-d90-observe-ladder-detach.plan.md` on the branch (the task ladder; it binds);
2. its ledger, beside it;
3. the two clearance mails above, for transcription;
4. this brief;
5. `docs/implementer-dispatch-recipe.md` section 3: the executing criterion, the per-round assertions, and the ledger-cut note;
6. the code each task names.

Do not read other comms, director state files, or other arcs' ledgers.

**Worktree:** `C:\Users\rwsmy\swing-trading\.worktrees\d90-detach`, branch `d90-detach`, head `d256bdfa`.
- Run tests with `PYTHONPATH=.`.
- Run the full suite at `-n 8`. This box ran out of memory at `-n auto`.
- Live DB: `mode=ro` only, never through `swing`'s `connect`.
- Use COPIES of cache files only.

## 1. Additions the clearances make (no task changes)

- **Ledger:** block-quote both clearances, each with its author, into an exec ledger beside the plan. Commit it.
- **W0 is SHARPENED (CHARC).** The witness night must show BOTH of these. Run 195 satisfies both; quote them for it as the baseline.
  - at least one `marketdata.pricehistory` row with the run id OUTSIDE observe's window;
  - `observe_load.fetch_window > 0`.
- **I-2 (CHARC).** T2 step 2 re-runs the p20 stub-reachability census on HEAD and QUOTES its output in the exec ledger. Re-measure it after the change; never inherit the base measurement.
- **C-1 (RD).** The superseded test's hazard is guarded by:
  - `needExtendedHoursData=False` (`marketdata.py:403`);
  - `OhlcvBar`'s finite-OHLC check (`models.py:561-582`).

  The site comment cites both.

## 2. Execution

Execute the plan's tasks in order:
- TDD: RED, then GREEN, then the commit each task names;
- pathspec-only commits; `%(trailers)` empty; no final `-m` paragraph begins with `Word:`;
- no Co-Authored-By, no `--no-verify`, no amend;
- quote every RED and GREEN result, read off saved output.

**Gates before Reviewer A:**
- The FULL fast suite (`-m "not slow" -q -n 8 -p no:cacheprovider`) green, read off the saved output.
- `ruff check swing/` clean. Zero NEW ruff findings on the touched test files.
- The plan's closure checks:
  - both `resolve_ohlcv_window` callers unchanged;
  - the AST single-keyword check;
  - the diff stat naming exactly the planned `swing/` files;
  - the text greps;
  - the head census (I-2).
- `git diff --stat e7f91d80..HEAD -- swing/data swing/trades scripts research` EMPTY. Name exactly which `swing/` files changed.
- The plan's mutation checks, in scratch and REVERTED; `git diff --exit-code swing/` returns 0 after each. Quote **M1** for the merge report: observe passes `use_ladder=True`, and T-NS goes RED.
- The two-pair neutrality test's outputs, quoted:
  - ordinary pair: rows equal;
  - carry pair: rows differ exactly on the observe-only ticker's provider label, with the values equal;
  - the store-miss pre-assertion holds.

**If the suite reds outside this arc's files:** classify the red by mechanism and reproduce it at `-n 0`. Never re-run until green.

## 3. Reviewer A (executing)

Run it per recipe section 3:
- `strong`, with REPO ACCESS, on the diff `e7f91d80..HEAD -- swing tests`, generated on Windows; tell Codex not to run git;
- all five per-round assertions.

**The prompt:**
- DESCRIBE the verdict tokens; never write one line-initially. Grep the prompt to prove it.
- Give the rulings INLINED, or the ledger CUT before any round section.
- No prior-round reads: relocate `.codex-*` / `.copowers-findings*` out of the worktree for the loop, then restore them. Grep each transcript.
- Add a per-item CHECKLIST (holds / fails / cannot-tell, each with a file:line):
  - observe passes `use_ladder=False` on every call;
  - the five other pipeline callers and the web hook are unchanged;
  - the bundle worker is untouched;
  - the `_bars_store` key is unchanged and both branches store the same read;
  - the two-pair test's anti-vacuity (the store miss);
  - T-NS RED without the flag;
  - every stub records the keyword;
  - the docstrings are replaced, not appended;
  - D89's `populate_ok` is unaffected: a stub `TypeError` cannot silently un-memoize.
- Invite challenge.

**Evidence:** save each round to `C:\Users\rwsmy\swing-data\review-transcripts\d90-detach\exec\round<N>\`.

**Stops:**
- **STOP AND RETURN at EVERY counted round gate with its ledger row.** Leave the depth column empty.
- Stop at the first clean verdict. Post-verdict minors are fixed without another round.
- Reviewer B is the orchestrator's.

## 4. Return (chat only)

You NEVER post to a mailbox and never run `scripts/role_mail.py`. Return:
- commits, with their trailers;
- RED and GREEN results per task;
- the suite counts;
- the closure outputs;
- the mutation results, M1 quoted;
- the two-pair outputs;
- the W0 baseline for run 195;
- the round row(s) and findings, each with a proposed disposition;
- every deviation.

**If anything does not fit, STOP and return.**
