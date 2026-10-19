# D87 -- suite load-robustness rider: EXECUTING continuation brief, cell 2

**Audience:** a fresh implementer cell with no prior conversation context. The first D87 cell ran over its context cap after Reviewer A round 1. You continue on its worktree, from its head.

**Cell:** `implementer-opus-high`. The design is ruled. What remains is two test fixes that need care with concurrency, two comment and fixture fixes, re-measurement, and a confirming review round.

**Read first, in full:**
1. `docs/d87-load-robustness-dispatch-brief.md` (main `9845b799`). It is the original brief. Its envelope, its "never" list and its gates all still bind.
2. The exec ledger on the branch: `docs/superpowers/plans/2026-10-19-d87-load-robustness.exec-ledger.md`. It holds the per-test classification, every count so far, CHARC's fork ruling and the round-1 row.
3. CHARC's round-1 ruling, which is the ruling of record: `comms/orchestrator/read/20261019T221138Z-charc-d87-r1-ruled-r1-01-and-r1-02-upheld-max.md`, in the MAIN repo. Its operative text is quoted in section 2. Block-quote it into the ledger with CHARC as the author.
4. The round-1 evidence in `C:\Users\rwsmy\swing-data\review-transcripts\d87-load\`: `prompt-r1.md`, `review-r1.txt` and `copowers-findings.md`.

**Worktree:** `C:\Users\rwsmy\swing-trading\.worktrees\d87-load`, branch `d87-load`, head `41a16471`, base `9845b799`. Run every test from the worktree with `PYTHONPATH=.`, because the editable install resolves MAIN.

## 0. Envelope (unchanged, hard)

- **IN:** only test files and test helpers/conftest under `tests/`, plus the ledger.
- **OUT:**
  - anything under `swing/`, `scripts/` or `research/`;
  - any schema, migration or dependency;
  - pytest configuration.
- **Never:** delete, skip, `xfail`, `flaky`, add retries, or reorder tests as "the fix".

## 1. State at handover (orchestrator-QA'd against disk)

- **Done and committed:**
  - mechanism 2 (`49344b6c`) and mechanism 3 (`60ef62bd`);
  - the sentinel docstring correction (`a81d188c`);
  - F1 Shape A at 900/300/300 s (`df0d95c8`). Round 1 found these values short; section 2 re-rules them;
  - F2 Shape B, the delegating `_FrozenReplayClock` (`4447ec29`);
  - SIM105 (`4ff43a9d`);
  - lint in the A2 file (`64b621af`), which I ratified;
  - ledger commits (`08e83e62`, `41a16471`).
- **Item 9:** no code change; 600 of 600 good under the saturator, not reproduced. It is closed for D87. Do not touch it.
- **Reviewer A round 1, counted:**
  - 0 critical, 3 major, 1 minor;
  - footer 146,268; `^ERROR` 0;
  - `NEW_CRITICAL_MAJOR_FOUND`.
- **Your scratch tools:** the saturator (`saturator.py`), the mutation plugins (under `mut\`), `item9_loop.py`, and the per-run outputs (under `load\`). All of them are in the session scratchpad's `d87\` folder:
  `C:\Users\rwsmy\AppData\Local\Temp\claude\C--Users-rwsmy-swing-trading\61e4dd1e-a749-42df-a27f-b5804ea44c2a\scratchpad\d87\`
  Reuse them. Kill every saturator by PID and verify it is gone.

## 2. The round-1 rulings (binding)

**CHARC, R1-01 (upheld):**

> The basis is the MAX over every harness run measured, each run quoted at the constant with its date and box state; 5x that, rounded UP to a round figure. L2 1000 s; diagnose 450 s; v2-help 450 s. The 15 minutes in my ruling was a stated consequence of one sample, not a cap; a cap would make the rule and the number conflict at exactly the test the rule exists for, so there is no cap, and the comment says what the latency now is (about 16.7 min for L2) in those words. Two additions to the form, both because a constant measured once DECAYS (D21): (i) the comment carries the re-open condition -- any later harness measurement above budget/5 re-opens the constant, by the next arc that reads it, not by a flake wave-through; (ii) the figures are written as measured (788.25, 10.4), rounded only at the budget.

**CHARC, R1-02 (upheld; Codex's fix adopted):**

> The fix: a `set_trace_callback` on the audit connection (test-side; the test passes that connection in; nothing under `swing/`), filtered to a statement beginning `BEGIN`, sets `begun`; the holder waits on `begun` (bounded) and only THEN starts its 0.5 s. Contention is structural: the trace fires when the statement starts, before the busy wait (verified above). The 0.5 s release stays as the test's premise. FORM, three points: (a) a DID-IT-FIRE assertion after the call -- the test asserts `begun.is_set()`, so a handshake that never fired cannot pass as a green (the B-06 class); (b) the holder's wait on `begun` is bounded (60 s, the `_HELD_WAIT` figure) and on expiry it still releases and records the failure into the per-test holder-exception collection R1-04 adds, so the test fails on an assertion, never hangs; (c) the callback body only sets the event -- no SQL, no assertion, no logging inside the trace. Mutation to show RED first: a holder that starts its 0.5 s at `held` as today, with the main thread delayed 0.6 s before the call, must fail the fixed test's `begun`-gated path and pass the old one vacuously; quote both.

CHARC verified by execution that the trace fires for `BEGIN IMMEDIATE` before the busy handler gives up.

**CHARC, R1-03, pre-existing half:** banked as D88 on CHARC's register (`a700963b`). It is not D87 work. Do not write a real-token test.

**Orchestrator rulings (my gate):**
- **R1-03, in-scope half:** the module comment at `tests/integrations/test_schwab_setup_cli.py:30-33` says both Layer-1 regexes "target" the sentinel. That is false: the sentinel's underscores defeat both. Rewrite the comment to say what is true. The sentinel is redacted only through the Layer-0 registry, which is why the `sentinel_registered` fixture exists.
- **R1-04 (minor, in scope):** in `_external_lock_holder`:
  - close the connection in a `finally`;
  - collect any holder exception in a per-test list;
  - assert the list is empty after each `join()`, in all three tests.

  R1-02's bounded-wait expiry records into the same list.

## 3. Procedure

1. **R1-04, then R1-02,** in the ladder stress file. Commit them separately or together, one mechanism per commit.
   - Run CHARC's ordered mutation and quote both results: the old shape passes vacuously, and the fixed path reds.
   - Run one more mutation: a callback that never sets `begun` must red on the did-it-fire assertion, without hanging.
2. **R1-01:** set the three budgets to 1000 / 450 / 450 s.
   - Quote every harness run at each constant, with its date and box state: the pre-fix run, base `9845b799`, and the final-head run, `64b621af` (L2 182.03 s, diagnose 85.88 s, v2-help 87.97 s), plus any run you make.
   - Write the figures as measured. Add the re-open condition and the latency sentence, in CHARC's words.
   - If any run of yours measures above budget/5, STOP and return. The ruled value would then be short.
3. **R1-03 comment:** fix it. Commit.
4. **Load harness on the new head:**
   - the roster (all of `tests/scripts/test_weeknight_wrapper.py` plus the ladder file, the setup-CLI test, the A2 tests and the three child-budget tests) under the saturator at `-n 16`, 10 or more consecutive iterations, counts quoted;
   - then ONE full fast suite under the saturator, with `--durations=0`, so the three child times are measured again and quoted in the ledger.
5. **Gates on the final head:**
   - the full fast suite WITHOUT the saturator (`-m "not slow" -q -n auto -p no:cacheprovider`), read off the saved output;
   - `ruff check` clean on every touched file;
   - `git diff --stat 9845b799..HEAD -- swing/ scripts/ research/` EMPTY;
   - `%(trailers)` empty after EACH commit; no final `-m` paragraph begins with `Word:`; no Co-Authored-By, no `--no-verify`, no amend.
6. **Reviewer A, round 2:** `strong`, with repo access, per `docs/implementer-dispatch-recipe.md` section 3, all five per-round assertions included.
   - Diff `tests/` from `9845b799` to the head. Generate it on Windows, and tell Codex not to run git.
   - The prompt carries:
     - the envelope;
     - CHARC's fork ruling and these round-1 rulings verbatim;
     - each round-1 finding with its disposition and the commit that fixes it;
     - the per-test classification.
   - Invite challenge. Tell the reviewer not to read the round-1 files.
   - DESCRIBE the verdict tokens; never write one line-initially in the prompt. Grep your prompt to prove it.
   - Save `prompt-r2.md`, `review-r2.txt`, `exit-r2.txt` and the findings to `C:\Users\rwsmy\swing-data\review-transcripts\d87-load\`.
   - **STOP AND RETURN at this counted round with its ledger row,** whatever the verdict. Leave the depth column empty.

## 4. Return (chat only)

You NEVER post to a mailbox and never run `scripts/role_mail.py`. Return:
- commits in order, with their trailers;
- the R1-02 mutation results (both legs, plus the never-fires leg);
- the remeasured child times, against budget/5;
- load-harness counts;
- the full-suite counts with and without the saturator;
- the round-2 ledger row and findings, each with your proposed disposition;
- every deviation.

**If anything does not fit, STOP and return.** Do not choose for yourself.
