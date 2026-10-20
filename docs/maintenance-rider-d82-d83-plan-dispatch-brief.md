# Maintenance rider (D82 + D83 + shadow 900 s): WRITING-PLANS dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.

**Authority:**
- Operator-approved 2026-10-19: "maintenance rider and registered proposal is approved. Work on both may begin as conditions support."
  - Source: RD's courier record, `docs/rd-proposal-soft-stop-arc-screen-widening-rider.md` @ `b266cc97`, section 5.
  - The approval is quoted again in `comms/orchestrator/read/20261019T085849Z-rd-operator-approved-maintenance-rider-soft.md`.
- Register rows D82 and D83 in `docs/tool-director-context.md`, lines 146-147. Read both in full.
- CHARC's six cell conditions for D83: `comms/orchestrator/read/20261019T085302Z-charc-observe-warm-cohort-rd-read-confirmed-ru.md`. Read it in full. Its conditions are quoted in section 2 and are binding.
- Sequencing is the orchestrator's. D79 and D87 are merged, so this rider is next. The D84 soft-stop arc opens only after this rider is merged.

**Cell:** `implementer-opus-xhigh`. This is a writing-plans pass, and it calls for three things:
- live-artifact measurement that sets constants;
- arithmetic for discriminating tests;
- driving Codex to convergence.

**Stage:** WRITING-PLANS only. Write the plan, run Reviewer A on the plan to convergence, then STOP and return. You do not execute. After my QA, the plan goes to plan-stage director review (CHARC on the six D83 conditions; RD on the rate constants) before any executing dispatch.

**Worktree:** create `C:\Users\rwsmy\swing-trading\.worktrees\maint-rider` on a new branch `maint-rider` off main at the commit that carries this brief. The plan file is `docs/superpowers/plans/2026-10-20-maintenance-rider-d82-d83.plan.md`, committed on that branch.

## 0. Envelope (hard)

**IN (for the plan to specify):**
- `swing/monitoring/research_health.py`:
  - the `invalid_ohlc` excluded-reason check (`_INVALID_OHLC_BASELINE_COUNT` :780 and the escalation at about :981-1003);
  - the coverage-gaps thresholds (`_COVERAGE_YELLOW_GAPS` / `_COVERAGE_RED_GAPS` :1022-1023 and their use at about :1793-1815).
- `swing/pipeline/runner.py`:
  - `SHADOW_EXPECTANCY_TIMEOUT_S` :1124 (300 -> 900 s);
  - `_prewarm_evaluate_archives` (about :1457-1500): the warm cohort and its always-on cohort log line.
- Tests under `tests/` for all of the above.

**OUT:**
- any schema, migration or dependency;
- anything under `swing/data/` or `swing/trades/`;
- the observe step's own logic (`_bar_for_date`, `resolve_ohlcv_window`);
- `warm_archives_batch` internals;
- `swing/pipeline/staleness.py`; the step budget is NOT changed;
- any standing process;
- the other research-health checks.

**Docs owned by the directors:**
- `docs/research-director-watch-standard.md` is RD's.
- The register and charter are CHARC's.

The plan LISTS every place in those docs that restates a changed constant, so the owner can update it. The plan does not edit them.

**Live data:**
- Read the live DB only with `mode=ro` (`sqlite3.connect("file:...?mode=ro", uri=True)`).
- If you need a copy, make it with plain sqlite3 `backup`.
- NEVER open the live DB, or a copy of it, through `swing`'s `connect`, which can auto-migrate.
- The research-health artifact (`latest.json`, at the cfg-derived path the step writes) is read-only.

## 1. The work, per item (verbatim from the register and the rulings)

### D82: research-health constants become RATES, not counts

> Fix = RATES, not re-baselined counts: `invalid_ohlc` green ≤ 5.0% of unique signals / yellow above / red > 10%; coverage as holes per 1,000 forward observations, green at today's rounded up, yellow 2×, red 5×, measured from the live artifact; RD reads the constants against the live artifact BEFORE merge.

**What the plan must contain:**

1. **The live measurement that sets the coverage constants.**
   - holes: the count the check computes today, using the check's own code path, not a re-spelling;
   - the forward observations the rate divides by, with the definition stated (which table, which rows, which date window);
   - the rate per 1,000.

   "Rounded up" needs a stated precision. Propose one and show the arithmetic. Yellow is 2x green and red is 5x green.

   Quote:
   - the DB file's mtime;
   - the query;
   - the date of the newest observation;
   - for the artifact you read, its path, mtime and the values it holds.

2. **The `invalid_ohlc` rate today.** Today it is about 71 of 1,535 unique signals, 4.6%. That is GREEN under the ruled rate, while today's count-based check reads YELLOW. State both, from the artifact and from the check's own computation.

3. **What happens to the count-baseline machinery.**
   - `_INVALID_OHLC_BASELINE_COUNT`, CALIBRATION B and its scope lock (about :771-790), and the `excess_pct` path.
   - Removed, replaced, or kept as a belt? Propose the form and give the reason.
   - The generic `_EXCL_YELLOW_PCT` / `_EXCL_RED_PCT` (10/25) for the OTHER excluded reasons are not in scope. Say so explicitly.

4. **Coverage clause interactions.** The existing coverage logic has calibrations: the trailing grace (:1031) and CALIBRATION C, current versus historical (:1074 on).
   - State how a rate composes with each of them.
   - Say which counts become the numerator.
   - Say whether "current/ongoing failure only goes red" survives.
   - Do not silently drop a calibration. Each one is either preserved or explicitly retired, with its reason, for CHARC's read.

5. **The mirror family (CLAUDE.md #11).**
   - Grep EACH constant name SEPARATELY, and each threshold value too, across `swing/`, `tests/`, `scripts/` and `docs/`.
   - Every test that pins an old value is listed, together with the new assertion it gets.
   - Rewriting an assertion to a ruled new value is legitimate. Weakening one is not.
   - Name the comparator: the test that would fail if a code constant and its stated rule diverged. If none exists, propose one.

### Shadow timeout

> `SHADOW_EXPECTANCY_TIMEOUT_S` 300 → 900 (`runner.py:1124`, CHARC-ruled: 37 s today, ~5 min at 8× signals, 3× headroom) rides with it.

The plan names the tests that pin 300 s, if any, and the warning text that interpolates the value.

### D83: the open detection set joins the evaluate warm cohort

> RULING: the open detection set's distinct tickers join `warm_set` before `warm_archives_batch`. One cohort change, no new mechanism, no new module, no dependency, no schema, no standing process: no tripwire. Measurement-neutral by construction: same archive, same 18-B trailing-ragged trim at both sites, same `resolve_ohlcv_window` read; the warm is a pure accelerator and a miss falls through to today's serial path unchanged.

## 2. CHARC's six cell conditions (binding; each one RED first)

> (i) ONE anchor. The observation_date used to list the open set for the warm is computed the SAME way observe computes it (the same helper, the same `run_now`), not a second spelling; a unit test builds the cohort with a seeded open detection on a ticker absent from candidates and asserts the ticker is in the list handed to the warm, and that a detection NOT yet observable for that date is not. Null implementation killed: a cohort that warms today's screen twice.
> (ii) DEPTH. The warm's `archive_history_days` must cover observe's 400-calendar-day window, or the hit is a shallow archive and observe refetches anyway; assert the relation in a test against the live config value, not a fixture constant. Null implementation killed: a warm that fills a 200-day archive for a 400-day reader.
> (iii) BEST-EFFORT PRESERVED. If the detections read raises, `warm_set` falls back to today's cohort and evaluate proceeds; the existing wholesale-failure #27 audit path is unchanged; a test raises from the reader and asserts evaluate still runs and the warning row names the cause. Null implementation killed: a warm that can sink evaluate.
> (iv) TELEMETRY. The always-on cohort log line (runner.py:1477 on) gains the open-detection count as its own field so a misbucketing is visible as a distribution, the Arc-6 R1 Minor #1 reason; observe's `observe_load` row is unchanged and is the before/after witness: fetch_window on the first post-merge nightly, quoted in the merge report against run 194's 239.
> (v) NEUTRALITY. The merge report quotes observation rows written for one fixture with and without the warm equal in count and values (the same archive feeds both); any difference is a regression, not a supersession.
> (vi) The single-ticker path stays `threads=False`; the batch is the only parallelism (the gotcha stands).

**The plan must also cover:**
- **The anchor:** read observe's call to `list_observable_detections` (`swing/data/repos/pattern_detection_events.py:113`) and the `observation_date` it passes. The plan cites the exact helper the warm will share.
- **The connection:** the plan names the connection the warm reads detections on and states its transaction posture. A read inside evaluate's own transaction is the CLAUDE.md "writer quoting itself" class, and must be ruled out or justified.
- **Dedupe:** the plan defines how open-detection tickers dedupe against the candidates and the universe, and what the count in (iv) counts: distinct tickers added, or detections.

## 3. Plan form

Use copowers writing-plans. The plan has:
- tasks in TDD order, with a failing test for each;
- every discriminating test's arithmetic computed under BOTH the pre-fix and the post-fix path (memory: verify regression-test arithmetic);
- assumption locks (ALs) for each design choice, with reasons;
- an explicit "not changed" list;
- a merge-report checklist that carries (iv) and (v).

## 4. Reviewer A on the plan

Run it per `docs/implementer-dispatch-recipe.md` section 3, `strong`, with repo access, with all five per-round assertions:
1. banner/model;
2. `^ERROR` 0;
3. the footer;
4. exactly one distinct anchored verdict token, read from the model's region;
5. the exit file written after codex returned.

**Rules for the prompt:**
- The prompt DESCRIBES the verdict tokens and never writes one line-initially. Grep the prompt to prove it.
- The prompt carries the envelope, the rulings above verbatim, and the live measurements with their queries.
- Codex must verify the load-bearing data claims against the live DB shape (`mode=ro`), not only against the plan's prose.
- Challenge is invited.

**Evidence:** save each round's prompt, transcript, exit file and findings to `C:\Users\rwsmy\swing-data\review-transcripts\maint-rider\plan\`. Also copy there any measurement output the plan cites, so nothing it relies on lives only in a scratchpad.

**Stops:**
- STOP AND RETURN at EVERY counted round gate, with its ledger row (in a plan ledger beside the plan; leave the depth column empty).
- Stop at the first clean verdict.
- The round-5 check-in (recipe section 3) binds: it judges the COMPOSITION of the findings, not their count.

## 5. Gates before return

- Commits are conventional, pathspec-only. No Co-Authored-By, no `--no-verify`, no amend.
- `%(trailers)` is empty after each commit. No final `-m` paragraph begins with `Word:`.
- No change under `swing/` on the branch: this is planning.

## 6. Return (chat only)

You NEVER post to a mailbox and never run `scripts/role_mail.py`. Return:
- the plan path and head;
- the live measurements, with their queries and sources;
- the proposed constants, with their arithmetic;
- the mirror list;
- the round ledger rows;
- every deviation;
- every place you had to choose.

**If anything does not fit, STOP and return.** Do not choose for yourself.
