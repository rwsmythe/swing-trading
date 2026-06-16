# 18-D nightly-half + 2 calibrations — EXECUTING-PLANS dispatch brief

**Audience:** a dispatched implementer (sub-agent via a `.claude/agents/implementer-*` cell), NO prior context.
**Phase:** copowers **executing-plans** — implement the merged plan task-by-task via TDD, then hand-run Codex (`review-strong`) to convergence. Measurement-core (RD merge-blocking). **CHARC sec-3-passed (C-NH1-5); O1 ruled (A) — bare B-shape.**
**Expected duration:** one focused session.

## §0 Read first
1. `docs/implementer-dispatch-recipe.md` (the protocol) + the repo `CLAUDE.md` (gotchas).
2. **`docs/superpowers/plans/2026-06-16-phase18-arc-d-nightly-half-plan.md` — THE binding implementation spec.** Execute its tasks EXACTLY (each carries its files, the failing tests with arithmetic, the implementation sketch, the acceptance + commit message). Do not redesign; if a task anchor diverges from live code, STOP-and-ask.
3. `docs/data-collection-health-monitor-commissioning-brief.md` §6.7 (the binding spec) + **the CHARC O1 ruling on record (`283ef878`): the nightly step uses the BARE B-shape `step_guard(lease, "research_health", logger=log)` — NO `status_key`** (the literal `status_key="research_health_status"` was an over-spec; it would trip `update_status_columns`' allowed-set raise + need a schema column → a never-perturb violation + a carve-out breach). The step's health stays observable via `warnings_json` + the `latest.json` artifact.
4. Re-ground against live code (anchors drift): `swing/monitoring/research_health.py` (`compute_research_health`; `_check_excluded_reason_breakdown` [#2]; `_check_coverage_gaps` [#3]), `scripts/research_health.py` (the atomic writer to extract — C-NH4), `swing/pipeline/runner.py` (`_step_shadow_expectancy` ~1051 → place the new step immediately after, before `lease.step("complete")`; the `mode=ro` connect pattern), `swing/pipeline/step_guard.py` (the bare B-shape signature).

## §0 Skill posture
Execute the plan task-by-task via **TDD**. After all task-commits land, **run the FULL fast suite to GREEN BEFORE the Codex review** (recipe §2 — the plan flags this explicitly), THEN hand-run the WSL-Codex review at the **`review-strong`** tier to `NO_NEW_CRITICAL_MAJOR`; persist every round to `.copowers-findings.md`. The bounded-scope #39 corollary applies (a finding premised SOLELY on a value the write boundary verifiably prevents is out-of-scope-for-V1, WITH a cited constraint). **Do NOT run `codex exec review` / the codex-auto-review A/B** (it stays on 18-H.4). Return to the ORCHESTRATOR only (no mailbox).

## §1 Binding constraints (RD merge-blocking — carry into every task)
- **C-NH1 (bare B-shape, per the O1 ruling):** `with step_guard(lease, "research_health", logger=log):` — `LeaseRevokedError` propagates; ALL else swallowed+logged; the step NEVER fails the run. NO `status_key`. Do NOT hand-roll a wrapper.
- **C-NH2 (read-only):** the step opens a SEPARATE `mode=ro` URI conn (mirror `scripts/research_health.py`'s `mode=ro`), NOT the runner's read-write `connect()`. Only `latest.json` is written; NEVER the measurement DB.
- **C-NH3 (placement):** immediately AFTER `_step_shadow_expectancy` (runner.py ~1051; re-ground), BEFORE `complete`.
- **C-NH4 (single-source the writer):** `write_research_health_artifact(status, out_path=None)` lives in `swing/monitoring/research_health.py` (resolve via `stoplights.research_health_artifact_path()` → `to_dict()` → atomic `tmp + os.replace`); `scripts/research_health.py` is REFACTORED to call it; the step calls the SAME fn. NO second copy of the writer (the plan's Task-1 SPY test locks this — keep it).
- **C-NH5 (write-nothing-on-failure):** on ANY failure write NOTHING (retain the prior `latest.json`); NEVER a partial artifact.
- **Calibrations are monitor-internal:** NO schema, NO dependency, NO new tripwire. CALIBRATION A (#3 trailing-≤1 grace; RED only on ≥2 trailing OR any interior). CALIBRATION B (#2 `invalid_ohlc` named baseline ≈23, the SCOPE LOCK: baseline ONLY `invalid_ohlc`; the above-baseline curve PINNED per the plan). NO `role_mail`-on-ATTENTION (deferred to 18-H.7).
- The §3 envelope / frozenset enum validation / atomic-write / the 3 contract constants stay UNCHANGED.

## §2 The two deferred-to-executing actions the plan flagged (do them)
1. **Grep the FULL Task-3 excluded suite** for every `invalid_ohlc`-driven assertion and re-ground each to the pinned post-calibration curve — the plan identified two known flips (`test_excluded_red_over_threshold` red→yellow, `test_excluded_yellow_at_threshold` yellow→green); confirm there are no others.
2. Run the FULL fast suite to green BEFORE the Codex loop (the 18-F lesson; the cross-arc/global-invariant catch — and note the **18-B.1×18-D write-barrier-vs-seeding gotcha now in CLAUDE.md**: any test planting non-finite rows must use raw insert, not `insert_observation`).

## §3 Dispatch metadata
- **Worktree:** fresh `.worktrees/18-d-nightly-exec` off the `BASELINE_SHA` the orchestrator gives you (current `main` HEAD, which contains this brief + the plan). Do NOT use Agent isolation. Review diff base = that `BASELINE_SHA`.
- **Codex tier:** `review-strong` to `NO_NEW_CRITICAL_MAJOR`. Leave the worktree intact (the orchestrator rebases + ff-merges).
- **Diff fence:** `swing/monitoring/research_health.py` + `scripts/research_health.py` + `swing/pipeline/runner.py` + `tests/`. NO schema/migration, NO new dependency, NO new tripwire, NO `swing/data`/`swing/trades` touch.

## §4 Verification
- BOTH full-suite runs (before the review + on the final post-convergence HEAD; no-false-green). `ruff check swing/` clean. The plan's tests (the SPY single-source lock, `test_step_uses_readonly_conn`, the no-status-column test, the never-perturb/write-nothing-on-failure test, the revoke-propagates test, the two calibration both-ways tests) all pass. Diff fence honored.
- **The operator gate is a POST-RETURN orchestrator/operator step** (a real pipeline run executes the step after `_step_shadow_expectancy` → `latest.json` refreshes; on the merged head #3 reads its calibrated state, #2 `invalid_ohlc` reads not-red on the baselined backlog). Document the exact run command in your return.

## §5 Return report (to the ORCHESTRATOR — final chat message; recipe §4)
Per-task commits (SHA + task id); the bare B-shape + each C-NH condition stated honored-on-disk (file:line); the calibration values (the #2 baseline=23, the #3 grace) reflected; the two §2 actions done; Codex `review-strong` rounds + verdict + `.copowers-findings.md` path; before+after suite counts + ruff; the diff fence; the operator-gate run command; deviations / bounded-scope adjudications (with cited constraint).

## §6 If you get stuck
A plan anchor doesn't match live code → STOP-and-ask. A change would need a schema/dep/new tripwire (crossing the C-NH carve-out) → STOP (route up). WSL Codex unreachable/capped → flag NOT-CONVERGED (never fabricate). A forbidden trailer slipped in → STOP-and-flag (no amend / `--no-verify`).
