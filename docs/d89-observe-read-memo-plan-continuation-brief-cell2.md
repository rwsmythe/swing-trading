# D89: WRITING-PLANS continuation brief, cell 2 (write the plan on the rulings, then the fast-tier rounds)

**Audience:** a fresh cell with no prior context. Cell 1 ran the Round-0 census. Both directors have ruled on it, and no D89 ruling is outstanding.

**Cell:** `implementer-opus-xhigh`.

**KEEP YOUR READING NARROW.** Read ONLY these:
1. `docs/d89-observe-read-memo-plan-dispatch-brief.md` (main `31a293b4`). Its envelope, live-data rules and gates still bind. This brief supersedes its section 3.
2. **RD's ruling** (the ruling of record): `comms/orchestrator/read/20261020T041614Z-rd-d89-r0-rd-rules-c3-memo-after-non-raisin.md`.
3. **CHARC's ruling** (the ruling of record): the `comms/orchestrator/read/` file whose name starts `20261020T052004Z-charc-d89-r0`. Its rulings also live in the register, rows D89, D90 and D91 in `docs/tool-director-context.md`.
4. **The census evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\d89-memo\plan\round0\` (p00-p12 with outputs, `iters195.json`, the replay row files). Reuse it. Re-measure only what may have moved.
5. `docs/implementer-dispatch-recipe.md` section 3: the PLAN-STAGE PROTOCOL, and the note at main `db9ab223` on giving reviewers a ledger cut, never the round history.
6. **For form only:** the maintenance rider's converged plan, `docs/superpowers/plans/2026-10-20-maintenance-rider-d82-d83.plan.md`. Its N-V test `tests/pipeline/test_step_evaluate_warm_neutrality.py` is the neutrality precedent.
7. **The code those rulings name:**
   - `swing/pipeline/runner.py`: `_bar_for_date` at :3073-3140, the observe loop at :3161-3330, and `observe_load` at :3313-3326;
   - `swing/web/ohlcv_cache.py`: `get_or_fetch` at :175-245;
   - `swing/data/ohlcv_archive.py`: `resolve_ohlcv_window` at :971-1056, read only;
   - the observe tests that patch `resolve_ohlcv_window`.

Do NOT read other comms, director state files, or other arcs' ledgers.

**Worktree:** `C:\Users\rwsmy\swing-trading\.worktrees\d89-memo`, branch `d89-memo`, base `31a293b4`, with no commits yet.
- Fast-forward it to main at the commit that carries this brief: `git merge --ff-only main` inside the worktree.
- Run everything with `PYTHONPATH=.`.
- Read the live DB with `mode=ro` only, and never through `swing`'s `connect`.

## 1. What the plan encodes (the rulings, summarised; block-quote the rulings in full from the two mail files into the plan LEDGER, authors named)

- **Memo rule (RD, C3, literal):**
  - The memo is written ONLY on the path where THIS detection's `get_or_fetch` returned without raising.
  - On that path the result is memoized, bar or no bar.
  - A raising populate memoizes nothing, every time.
- **D1 (CHARC):** the per-detection `get_or_fetch` stays, and `observe_load` stays byte-identical except for the W5 addition.
- **B1 (CHARC):**
  - Memoize the `(df, provenance)` pair inside `_bar_for_date`, after its populate, on the non-raising path.
  - Each detection selects its own row.
  - An empty frame IS the memoized None, so no sentinel is needed.
- **Key (CHARC):** `(ticker, observation_date)`.
- **Envelope (CHARC):** `runner.py` only.
  - A LOCAL `memo = {}` in `_step_pattern_observe`.
  - `_bar_for_date(..., memo=None)`, where the default is today's path exactly.
  - The in-function import of `resolve_ohlcv_window` STAYS.
  - No new module, no `swing/data` change, no tripwire.
- **#31 addition (CHARC):** rewrite `_bar_for_date`'s docstring at :3077-3079 ("archive-first; zero Schwab") to describe what the code does TODAY:
  - the pipeline ladder hook is installed (runner.py:509);
  - a store miss reaches Schwab.

  Say nothing about D90.
- **H (CHARC, (ii)):** no production knob. The neutrality test builds the no-memo world by wrapping `_bar_for_date` to drop `memo`.
- **W5 (CHARC, (iii) beside (ii)):**
  - ADD `resolve_reads` to the `observe_load` entry. Re-state, by grep, that nothing in `swing/` reads the entry.
  - The merge report quotes the replay count (ii) beside it.
- **Required discriminators (RD):**
  - **T-H1:** the populate raises, then a later populate heals it. Later detections observe. Kills "memoize the miss on a raise".
  - **T-H2:** yfinance 9.0 is archived; the populate raises; a later populate writes Schwab 9.5. Detection 2 carries schwab/9.5. Kills C1.
  - **T-C3:** a no-bar ticker with 3 detections after a non-raising populate. 1 read under C3, 3 under C2, counted through `resolve_reads`.
  - The two-world row equality on the N-V column set: `detection_id`, `observation_date`, `ohlc_today_json`, `status`, `status_change_event`, `sessions_since_detection`. `created_at` and `observation_id` are excluded BY NAME.
  - T-lifetime, from the census: two step calls with the archive changed in between; the second reads fresh data.
- **One quoted mutation (RD):** write the memo on the raising path too, and T-H1 goes RED.
- **Accepted limitations (RD):**
  - **H3, a cache TTL expiry mid-step.** The re-open trigger, stated in the merge report: any observe wall above 1800 s on the merged code.
  - **H4, a concurrent prices-cache writer,** at its TRUE width: today the race is per detection; with the memo it is per ticker per step.
- **Witness W1-W7 (CHARC):** in F8's form, with W4 quoted against **62.24 ms** per iteration over 7,139 iterations for run 195.
- **NOT D89:** D90 (detach the ladder from observe's populate), D91 (stuck detections), and Fork G (declined).

## 2. Plan protocol (recipe section 3, plan-stage)

- **Form:** a task ladder plus a test roster, about 1,000 lines or fewer. The reasoning lives in the LEDGER beside the plan.
- **TDD:** every discriminating test's arithmetic computed under BOTH the pre-fix and the post-fix path.
- **Plan rounds:** at the `fast` tier, at most THREE counted rounds. Stop at the first with zero task-bearing findings, then run the uncounted self-sweep.
- **The reviewer's inputs:**
  - rulings INLINED in the prompt, or a ledger copy cut before its round section, never the ledger file itself;
  - a prompt that DESCRIBES the verdict tokens and never writes one line-initially;
  - an explicit per-item CHECKLIST, each item answered holds / fails / cannot-tell with a file:line. A response without per-item verdicts is a thin round, not a clean one.
- **Per-round checks:** every per-round assertion, plus the no-prior-read grep.
- **Evidence:** save each round to `C:\Users\rwsmy\swing-data\review-transcripts\d89-memo\plan\round<N>\`.
- **Stops:** STOP AND RETURN at EVERY counted round gate with its ledger row; leave the depth column empty.
- **Commit:** the plan is committed ONCE, at convergence.

After convergence I route the plan to CHARC (form) and RD (neutrality) for the plan-stage read before executing.

**Gates:**
- conventional, pathspec-only commits;
- `%(trailers)` empty; no final `-m` paragraph begins with `Word:`;
- no Co-Authored-By, no `--no-verify`, no amend;
- no `swing/` change.

**Return in chat only.** You NEVER post to a mailbox and never run `scripts/role_mail.py`. **If anything does not fit, STOP and return.**
