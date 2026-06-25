# Codex review findings — coverage_gaps calibration plan (review-fast tier, run-to-convergence)

Transport: WSL-native codex-cli 0.135.0. The `review-fast` profile (gpt-5.4-mini)
returned "Selected model is at capacity" on the first attempt, so per recipe §3
fallback the review ran with `-p` OMITTED and `-c model_reasoning_effort=high`
(model gpt-5.5, effort=high — NEVER effort=none). Plan + the current
`_check_coverage_gaps` source + the commissioning brief were piped via stdin.

## Round 1 (model gpt-5.5, effort=high)

### Codex response (verbatim)
- MAJOR — Skip-warning rule is underspecified against the actual source: `ticker` is not selected. The current `_check_coverage_gaps` query selects only detection_id/data_asof_date/observation_date/status/observation_id; the (ticker, S) join needs d.ticker added to the SELECT + per_det.
- MAJOR — CALIBRATION A is not actually preserved if it runs before CALIBRATION C. `_graced_missing_count` graces only `missing == {max(expected)}`; one accepted-historical interior hole + the benign trailing-1 hole → A returns len=2, then C removes the historical hole, leaving the trailing-1 wrongly counted. Compute the residual AFTER accepting historical holes, THEN apply the trailing grace.
- MAJOR — Task 2 does not reliably distinguish bad implementations. The combined trailing-2 + never-observed fixture asserting only RED + a vague "counted summary" control could stay red via one half while the other is mis-accepted. Needs isolated tests with exact counted totals. Detail sampling is capped, so "appears in detail" is not stable unless ordering is guaranteed.
- MAJOR — Whole-session miss detection can false-green a real zero-observation observe-step failure. `S ∉ SELECT DISTINCT observation_date` also matches "the run ran but wrote zero observations for S". If intentional, call out the V1 false-green tradeoff + cover with a test or explicit RD acceptance.
- MINOR — Accepted-gap auditability is not clearly specified for the malformed-date return path. The early `if malformed:` return must also fold the accepted_historical note, else a mixed case hides accepted gaps.
- MINOR — The `_observed_sessions` empty-table note is internally inconsistent. Under `S ∉ observed_sessions`, every session satisfies the whole-session subclause on an empty table; correct the wording.

Verdict line: (no NO_NEW_CRITICAL_MAJOR — 4 MAJOR + 2 MINOR)

### Adjudication (per finding)
- MAJOR ticker-not-selected — ACCEPTED + FIXED. §2.5 now requires adding `d.ticker` to the SELECT and storing `per_det[det_id]["ticker"]`; a non-str ticker defensively fails the 2b lookup (the hole COUNTS).
- MAJOR A/C ordering — ACCEPTED + FIXED. §1 now mandates C-FIRST, A-on-the-residual (`missing_set → C partition → residual → _graced_missing_count(residual, expected)`), with the worked example. §2.5 codifies the order in both arms.
- MAJOR Task 2 distinguishing — ACCEPTED + FIXED. Split into Task 2a (trailing-≥2, isolated, exact `total_missing==16`) and Task 2b (never-observed, isolated, exact expected-count). Exact-count negative controls replace the vague detail assertion. Task 5 made order-stable.
- MAJOR whole-session false-green — ACCEPTED + FIXED (the load-bearing one). The whole-session signal is RE-KEYED off the RUN LEDGER: `S ∉ {data_asof_date of completed pipeline_runs}` (the observe step writes observation_date==data_asof_date, runner.py:2999; live-verified 06-22 ∉ completed-run data_asof_dates). A run that named S but wrote zero rows stays COUNTED. New Task 4b is the explicit false-green guard distinguishing the run-ledger predicate from the weaker observation-date predicate. Helper `_run_observed_sessions` returns None on unavailable/empty ledger (conservative-degrade; Task 6) so a degraded ledger never accept-everything-false-greens.
- MINOR malformed-branch auditability — ACCEPTED + FIXED. §2.5 folds the accepted-historical note into EVERY return path incl. the early `if malformed:` branch; new Task 5b asserts it.
- MINOR empty-table wording — ACCEPTED + FIXED (subsumed by the run-ledger re-key). The signal is no longer `observation_date`-based; the `_run_observed_sessions` None-sentinel resolves the empty-table semantics correctly (empty → None → 2a never applies).

## Round 2 (model gpt-5.5, effort=high)

### Codex response (verbatim summary)
- MAJOR 1 — §1/§2.4 whole-session acceptance is too broad in the OPPOSITE direction. Keying 2a on run-ledger-absence ALONE accepts an unexplained per-detection hole when S has observations globally (detection B observed S) but the completed-run ledger lacks S. The live def is "ZERO observations globally"; the run ledger should CORROBORATE, not REPLACE it. Missing quadrant: A missing S; B observed S; no completed run for S; no skip-warning for A; later obs for A -> current 2a wrongly accepts. Not schema-prevented (no constraint guarantees every observed observation_date has a matching completed run row). Fix: require BOTH `S not in run_observed_sessions` AND `S not in global_observed_sessions` + a guard test.
- MAJOR 2 — §2.2 `_observe_skip_index` indexes warnings from arbitrary rows. No state='complete' filter and no check that the row's data_asof_date matches the warning's observation_date. A failed/stale row or a date-mismatched warning could explain a hole. warnings_json is free text -> not schema-prevented. Fix: query state+data_asof_date+warnings_json, index only state='complete' rows whose entry observation_date == data_asof_date. Add unit coverage.
- MINOR — Task 6 stale empty-set wording (both helpers "degrade to an empty set" then says run-ledger must return None). Fix the stale sentence.
- MINOR — Test helper underspecified for run-ledger seeding (`_seed_pipeline_run_warnings` aliases data_asof_date to action_session_date). Add an explicit data_asof_date param.
- Prior findings 1-6: all confirmed resolved (4 zero-obs-failure resolved via run ledger + Task 4b, but MAJOR 1 is a new remaining vector).

Verdict line: (no NO_NEW_CRITICAL_MAJOR — 2 MAJOR + 2 MINOR)

### Adjudication (per finding)
- MAJOR 1 (run-ledger too broad opposite direction) — ACCEPTED + FIXED. Clause 2a now requires BOTH `S ∉ global_observed_sessions` (new helper `_global_observed_sessions`) AND `S ∉ run_observed_sessions` (run-ledger). New helper #2b + the partition signature gains `global_observed_sessions`. New Task 4c is the explicit MAJOR-R2-1 quadrant guard (S has global obs via OTH, no run-ledger row, no skip-warning -> STILL RED). §0 signal #1 rewritten as the BOTH-signals AND.
- MAJOR 2 (skip-index from arbitrary rows) — ACCEPTED + FIXED. `_observe_skip_index` now `WHERE state='complete'` AND only indexes entries whose `observation_date == that row's data_asof_date`. Task 7 unit test asserts the non-complete-row-ignored + date-mismatched-warning-ignored cases.
- MINOR Task 6 wording — ACCEPTED + FIXED. Task 6 now states the two distinct sentinels (skip-index -> empty set; run-ledger -> None) explicitly.
- MINOR helper signature — ACCEPTED + FIXED. The Task-0 helper renamed `_seed_pipeline_run` with explicit `data_asof_date`/`state`/`warnings` params + distinct lease_token note.

## Round 3 (model gpt-5.5, effort=high)  -- CONVERGED

### Codex response (verbatim summary)
- MINOR — Task 6 does not exercise the `run_observed_sessions is None` false-green trap it describes: it reuses Task 4 where OTH is observed on 06-10 (S in global_observed_sessions), so even a bad None->empty-set integration would not accept via 2a. Use the Task 4b zero-global shape with pipeline_runs dropped, or add a direct `_calibration_c_partition(..., global_observed_sessions=set(), run_observed_sessions=None, ...)` unit.
- MINOR — Task 4c should explicitly seed completed pipeline_runs rows for the OTHER observed sessions while omitting only 06-10. Otherwise an empty completed-run ledger -> `_run_observed_sessions` returns None -> weakens the test's ability to catch a run-ledger-only impl.
- No CRITICAL/MAJOR. "The Round-2 fixes are semantically correct: the whole-session predicate now requires both zero global observations and no completed run for S, closing both false-green directions; the skip index correctly filters to completed runs and requires warning observation_date == pipeline_runs.data_asof_date; Task 7 covers the arbitrary-row/date-mismatch skip-index issue directly."

### Verdict line: NO_NEW_CRITICAL_MAJOR

### Adjudication
- MINOR Task 6 None-trap — ACCEPTED + FIXED. Task 6 re-specced on the Task-4b ZERO-GLOBAL-observation shape (so the None vs empty-set degrade is actually exercised) + a direct `_calibration_c_partition(global_observed_sessions=set(), run_observed_sessions=None)` unit asserting accepted==set().
- MINOR Task 4c empty-ledger — ACCEPTED + FIXED. Task 4c now explicitly seeds completed pipeline_runs rows for 06-05/06-08/06-09/06-11/06-12 (omitting ONLY 06-10) so `_run_observed_sessions` is a non-empty set, preserving the run-ledger-ALONE-impl distinction.

CONVERGENCE: round 3 returned NO_NEW_CRITICAL_MAJOR. The only post-convergence edits are the two MINOR test-robustness fixes above (no design change); a confirmation round 4 follows to verify the MINOR edits are clean.

## Round 4 (model gpt-5.5, effort=high) -- CONFIRMATION, CONVERGED

### Codex response (verbatim)
"No new critical/major found. The two Round 4 edits are correct: Task 6 now actually exercises the run_observed_sessions is None conservative-degrade path because 06-10 has zero global observations. The added direct _calibration_c_partition(... run_observed_sessions=None ...) unit is the right minimal lock against the empty-set false-green. Task 4c now seeds completed runs for the other observed sessions, so the run ledger is present and non-empty while omitting only 2026-06-10. That correctly distinguishes 'missing run-ledger row alone' from the required BOTH-signals whole-session miss predicate. No new issue introduced by either edit."

### Verdict line: NO_NEW_CRITICAL_MAJOR

CONVERGENCE CONFIRMED across rounds 3 + 4 (NO_NEW_CRITICAL_MAJOR both). Total: 6 MAJOR + 4 MINOR found and resolved across rounds 1-2; rounds 3-4 clean.

---

# EXECUTING REVIEW

## Round 1 (review-strong, repo-access, cwd=worktree, base=plan commit 96b582ff)

### Codex response (verbatim, the final findings block)
MAJOR [swing/monitoring/research_health.py:1181]: Calibration C compares raw date strings after `date.fromisoformat()` validation. Python accepts compact/week ISO forms like `20260611` / `2026-W24-4`, but `expected` sessions are canonical `YYYY-MM-DD`. A degraded row can therefore be treated as a "later observation" while not matching the expected session, and `_global_observed_sessions` / `_run_observed_sessions` also carry raw strings. With noncanonical completed-run / observation rows, a zero-global whole-session miss can be accepted instead of counted, creating a false green on unconstrained date text.
Concrete fix: canonicalize every parsed session before set membership/comparison, or reject noncanonical as malformed. (per-detection observed; _global_observed_sessions; _run_observed_sessions -> None if ledger unparseable; _observe_skip_index both dates.)

(NOTE: an EARLIER round-1 invocation mis-ran -- the `cd` used a Git-Bash `/c/...` path WSL could not resolve, so `cat` ran from $HOME and Codex reviewed the stale PLAN doc, surfacing 4 plan-era MAJORs (ticker-not-selected, A/C order, Task-2-not-isolated, zero-obs-false-green) that the SHIPPED diff already resolves: d.ticker IS selected (research_health.py SELECT), CALIBRATION A IS C-first-then-A-on-residual, Task 2 IS split isolated 2a/2b with exact counts, and the zero-obs false-green IS closed by the run-ledger BOTH-signals AND + Task 4b. Those are out-of-scope-already-resolved; the re-run with the correct /mnt/c path + repo access produced the single real MAJOR above.)

### Adjudication
- MAJOR (canonicalize session sets): IN SCOPE and VALID -- a false-green vector on a genuinely-unconstrained input (observation_date / data_asof_date are TEXT with NO format CHECK; the runner writes canonical strings in production but the DB does not PREVENT non-canonical text, and this monitor's purpose is detecting degraded data). CALIBRATION C amplifies the pre-existing raw-string latency into an ACCEPT path. FIXED in 60f33189: added `_canonical_session`, canonicalized the per-detection `observed` set, `_global_observed_sessions`, `_run_observed_sessions` (returns None on ANY unparseable completed-run date -> conservative clause-2a disable), and `_observe_skip_index` (canonicalize both the warning observation_date and the row data_asof_date before the date-match + index). Regression test `test_calib_c_session_sets_canonicalize_iso_forms` asserts the canonicalization and distinguishes the raw-string impl (verified: reverting to raw-string FAILS the test).

## Round 2 (review-strong, repo-access, base=plan commit 96b582ff, after R1 fix)

### Codex response (verbatim)
CRITICAL: None.
MAJOR: [swing/monitoring/research_health.py:1288]: `observed` is canonicalized, but latest-status selection still filters raw `obs` rows with `oc[0] in observed`. A parseable non-canonical row like `20260611` becomes `2026-06-11` in `observed`, then is excluded here. If all valid rows are non-canonical, `max()` raises; if mixed, the wrong older status can be chosen and a terminal older row can suppress a still-open tail. The schema does not CHECK canonical date shape (0022_phase14_temporal_log.sql:68 is TEXT NOT NULL only), so this is in scope. Fix by carrying canonical observation dates alongside status, build valid_obs: list[tuple[str,int,str]] and compute latest_status = max(valid_obs, key=lambda x:(x[0],x[1]))[2].
MINOR: None.

### Adjudication
- MAJOR (latest-status raw-filter): IN SCOPE and VALID -- a direct consequence of the R1 canonicalization fix (observation_date is TEXT NOT NULL with NO format CHECK -> genuinely-unconstrained; the bug is reachable on degraded data). FIXED in 6a4678ae: build a canonical `valid_obs: list[tuple[str, int, status]]` during the parse loop (seq = enumerate index, mirroring the SQL ORDER BY observation_id ASC) and select `latest_status = max(valid_obs, key=lambda x: (x[0], x[1]))[2]`. valid_obs is non-empty when reached (the not-observed arm handles the zero-valid case). Regression test `test_coverage_calib_c_latest_status_uses_canonical_dates`: a terminal stopped-early detection (max_obs 06-08 < last_completed) whose newest terminal row carries a non-canonical date string -> under the bug the terminal row is excluded -> older OPEN status wins -> spurious 4-session tail -> yellow; under the fix terminal -> upper=max_obs -> green. Verified the test FAILS on the buggy raw-filter impl and PASSES on the fix.

## Round 3 (review-strong, repo-access, base=plan commit 96b582ff, after R2 fix)

### Codex response (verbatim)
MINOR [swing/monitoring/research_health.py:1287]: Accepted-gap detail gives only `det{id}: N accepted`, not a concrete gap sample. The invariant asks accepted gaps to surface in detail as count + sample; without session dates, the operator cannot tell which historical session was accepted. Fix both accepted-sample append sites to include sampled sessions, e.g. det{det_id}: {len(accepted)} accepted ({", ".join(sorted(accepted)[:3])}).

No new critical/major findings found. The None sentinel, BOTH-signals AND, zero-observation failure guard, skip-warning filters, C-before-A order, and compute/write envelope boundaries all look intact.

NO_NEW_CRITICAL_MAJOR

### Adjudication
- CONVERGED at R3: zero new critical/major. The MINOR (accepted-gap detail naming the sessions) is a legitimate auditability improvement aligned with the brief sec3 + #27 "count + sample" lock -- ADOPTED in 6511f891: both accepted-sample append sites now include up to three sorted accepted session dates; Task 5 test asserts the concrete 06-10 session surfaces. (Found+fixed that the writing-plans replace_all had only updated ONE of the two indentation-distinct append sites.)

## Round 4 (review-strong, repo-access, base=plan commit 96b582ff, after R3 MINOR fix -- confirming round)

### Codex response (verbatim)
Findings: none.
I did not run `git` or mutate files. Review was read-only against `swing/monitoring/research_health.py` plus surrounding schema/write-path context.
NO_NEW_CRITICAL_MAJOR

### Adjudication
- CONVERGED. The R3 MINOR fix introduced no new findings. Two consecutive clean rounds (R3 zero crit/major + R4 zero findings). Review-strong converged at NO_NEW_CRITICAL_MAJOR.
