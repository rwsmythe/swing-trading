# D81 rider: coverage_gaps in-run cry-wolf -- dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.

**Mission.** The nightly `research_health` step runs INSIDE the pipeline run, before the run marks itself complete. So it cannot see its own run's `pattern_observe` skip-warnings, nor its own `data_asof_date`. After any missed night it therefore mails a `coverage_gaps` RED that reads GREEN twenty seconds later, which makes the alarm channel cry wolf. Make the in-run monitor compute the state the run WILL have at completion.

**Commissioned:** operator, 2026-10-18, verbatim: "concur with the fix." RD was the courier (`20261018T235613Z`); CHARC authored the finding and the fix shape (`20261018T235433Z`, PRIMARY: CHARC).

**Scope:**
- `swing/monitoring/research_health.py`;
- the ONE call site in `swing/pipeline/runner.py` (`_step_research_health`'s call at ~`:1069`, plus that function's call into `compute_research_health` at ~`:1395`);
- tests.

**No** schema, no new module, no dependency, no new process, no `swing/trades` or `swing/data` change. No tripwire.

**Base:** `main` @ the commit that adds this brief. **Worktree:** `.worktrees/d81-coverage-gaps`, branch `d81-coverage-gaps`.

**Cell:** `implementer-sonnet-high`, the executing default. CHARC fixed the design, and its three discriminators are given below.

## 0. Read first

- `docs/implementer-dispatch-recipe.md`, in full. It is the protocol: worktree, TDD and commits, the Codex review, the return report.
- `CLAUDE.md` gotchas. The ones that bear here:
  - **#30**: a run/batch-level stamp is not provenance for a per-row value. The live asof must come from THIS run's own row.
  - **"Session-anchor read/write mismatch"**.
  - **"Silent-skip-without-audit" (#27)**.
- In `swing/monitoring/research_health.py`, read end to end:
  - `_observe_skip_index` (`:1101`);
  - `_global_observed_sessions`;
  - `_run_observed_sessions` (`:1192`);
  - the coverage-gaps check that consumes them (clauses 1 / 2a / 2b);
  - `compute_research_health` (`:2114`).
- `swing/pipeline/runner.py`: the step call at `:1069`, `lease.step("complete")` at `:1075`, `lease.release(...)` at `:1086`, `_step_research_health` (`:1343`) in full, and `lease_data_asof` (`:1111`).

**Skill posture:** no copowers skills, because they are absent in a sub-agent. Run Codex by hand per the recipe at the **`strong`** tier: code-shipping, on a monitor that is an alarm instrument.

## 1. The fix shape: CHARC's text, block-quoted from `20261018T235433Z`

> - The in-run monitor computes the state the run WILL have at completion: pass the live run's (data_asof_date, run_warnings) into compute_research_health and merge them into the skip index under the SAME tie (observation_date == that asof) and into run_observed_sessions. Same evidence, same provenance, visible one step earlier. The step already holds run_warnings in hand; this is plumbing, not a new reader.
> - MAJOR-R2-2's intent (a non-complete run's warnings must not explain a hole) is preserved for FAILED runs: the live run is the one about to complete; if it then fails, its artifact is overwritten by the next run and the mail is a false GREEN for one night, which is the cheaper direction than a false RED every night after a holiday. State that trade in the brief as an accepted limitation with its reason.
> - REFUSED alternative: moving the step after lease.release. It would run outside the lease and lose the step's own run_warnings append (the RD 8.1(b) lease-verification entry).
> - Discriminators (three, each fails the null implementation of one clause): (i) fixture = one completed prior run, one missed session, an in-flight run whose warnings carry a tied skip for ticker T -> in-run GREEN with the hole ACCEPTED (fails today); (ii) same with the skip's observation_date NOT equal to the live asof -> stays RED (the tie must survive the merge); (iii) a live run with zero observations for its session and no skip -> stays RED (the zero-observation observe failure is never explained by mere liveness).

**CHARC's measured evidence** (live DB, `mode=ro`):
- run 191 (asof 10-09): 391 tied skips x 5 missed sessions = **1955**, the 10-11 mail's count;
- run 194 (asof 10-16): 205 x 2 = **410**, the 10-18 mail's count.

## 2. Required behaviour

- **New, optional, keyword-only inputs on `compute_research_health`.**
  - Add something like `live_run_asof: str | None = None` and `live_run_warnings: list[dict] | None = None`; choose the names and state them.
  - With both absent, the output is BYTE-IDENTICAL to today's. `scripts/research_health.py` and every existing caller pass nothing. Pin that with a test.
- **Merge, never a second reader.**
  - The live warnings go through the SAME filter `_observe_skip_index` applies: `step == 'pattern_observe'`, `reason in _OBSERVE_SKIP_REASONS`, both dates canonicalized, and `obs == asof` against the LIVE asof.
  - Factor that filter so the completed-run path and the live path share ONE implementation. A copy would drift.
  - The live asof joins `_run_observed_sessions`'s set the same way. Mind its `None` sentinel: zero completed runs plus a live asof must NOT become accept-everything. State what you do and why.
  - A non-canonical live asof merges NOTHING. That is the conservative direction, matching the existing canonicalization.
- **The live asof is THIS run's own.**
  - The step already receives `run_id`. Read the asof from that run's `pipeline_runs` row (via the step's `mode=ro` connection, or via `lease_data_asof` at the call site); never from a batch or latest stamp (gotcha #30).
  - The step already receives `run_warnings`. Pass it through, since the step currently uses it only to append its own entry.
- **Accepted limitation, stated in the code comment AND your return report:** a run that passes this step and then FAILS mailed a false GREEN for one night, and the next run overwrites the artifact. The reason is CHARC's, quoted above. MAJOR-R2-2 is unchanged for every NON-live run: a failed, stale or running row in `pipeline_runs` still explains nothing.
- **RD's standing gate, which binds:** the monitor's calibration semantics in watch-standard v2 must read unchanged. #3's clause-1/2a/2b accept rule and the accepted-historical surfacing stay intact. "A loosening of the admission rule re-opens the 2026-07-03 bless." The ONLY change is that this run's evidence becomes visible one step earlier.
- **Do NOT move the step** after `lease.release`. That is CHARC's refused alternative.

## 3. Tests: RED first, each discriminating

- The three discriminators (i), (ii), (iii) above, at the `compute_research_health` level.
  - (i) must FAIL on the unmodified code, so show the RED.
  - (ii) and (iii) must PASS on a correct fix and FAIL on a null merge. For each, state which null implementation it kills, e.g. a merge that ignores the tie (ii), or one that adds the live asof to the observed set without an observation or skip (iii).
- Absent-inputs byte-identity, against an existing fixture.
- One test at the step level (`_step_research_health`). It drives the real call with `run_id` + `run_warnings` over a seeded `tmp_path` DB whose live row is `state='running'`, and asserts the artifact's `coverage_gaps` is GREEN for case (i).
  - Plant any "bad" pre-existing rows by RAW INSERT; see the write-barrier gotcha.
- Build fixtures from the REAL warning shape the observe step emits. Read the emitter in `runner.py` (grep `"pattern_observe"`); do not invent keys.
- Frozen clock for anything date-touching (the R2 rider convention).

**Do NOT open or write the live DB** (`~/swing-data/swing.db`). Use tmp DBs only.

## 4. Binding conventions

The recipe governs. In brief:
- conventional commits with the id in the subject (`fix(monitoring): D81 -- ...`, `test(monitoring): D81 -- ...`);
- no `Co-Authored-By`, no `--no-verify`, no amend;
- the final `-m` paragraph is plain prose (no `Word:` opener);
- bare `git` from the worktree cwd;
- `ruff check swing/` adds nothing.

## 5. Verification

- The FULL fast suite (`python -m pytest -m "not slow" -q`) to GREEN BEFORE the Codex review, and again after it. Save both under `C:\Users\rwsmy\swing-data\review-transcripts\d81-coverage-gaps\`.
- Print the RESOLVER line from the worktree (`python -c "import swing; print(swing.__file__)"`).
- Known xdist-load reds to reproduce with `-n 0` FIRST before treating them as yours:
  - `tests/data/test_migration_0039_provenance_corrections_tier2.py::test_uncovered_barrier_absent_terminal_is_accepted_both_shapes[...]`;
  - `test_phase8_pipeline_second_same_day_run_upserts`;
  - `tests/trades/test_22a2_cohort_readers.py::test_a2_94_*`.

## 6. Adversarial review: Reviewer A, ONE counted round expected

- The recipe's review protocol, at the `strong` tier. Persist the prompt, diff, transcript, findings and exit under `...\review-transcripts\d81-coverage-gaps\r<N>\`.
- Every validity assertion binds: banner with the model, `^ERROR` 0, the anchored verdict token, the footer, exit 0.
- A second counted round only for a critical/major fix; a fourth needs the orchestrator's written authorization.
- **Reviewer B at the merge gate is the orchestrator's, not yours.**

**Watch items for the prompt:**
- Can a FAILED, stale or merely `running` row in `pipeline_runs` now explain a hole through any path other than the explicitly-passed live inputs?
- Does the merge preserve the `observation_date == asof` tie and the canonicalization?
- Does zero-completed-runs plus a live asof turn the `None` sentinel into accept-everything?
- Is the absent-inputs output byte-identical?
- Is the live asof this run's own row's?

## 7. Done criteria

- RED-first commits.
- Both suites green and saved.
- Reviewer A valid on disk.
- A clean trailer audit over `<base>..HEAD` (zero `Co-Authored-By`, and no parsed `Word:` trailers).

## 8. Return report (your final chat message, to the orchestrator only; NEVER post to any mailbox)

- Commits, each with its RED text.
- The input names chosen.
- The `None`-sentinel decision.
- The accepted-limitation wording.
- Both suite summary lines verbatim, with the RESOLVER line.
- Codex: per round, the verdict, the token footer, findings with dispositions, and the persisted paths.
- Anything outside scope: FLAG it, do not fix it.

## 9. If you get stuck

STOP and return at the stuck point with what you measured if:
- a premise here does not match the code (line numbers, the warning shape, the readers' filters);
- the fix would need a schema change, a new module, or a change to the clause-1/2a/2b accept rule itself.

Do not work around it.
