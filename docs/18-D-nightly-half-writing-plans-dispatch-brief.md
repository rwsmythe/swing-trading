# 18-D nightly-half + 2 calibrations — WRITING-PLANS dispatch brief

**Audience:** a fresh implementer (sub-agent via a `.claude/agents/implementer-*` cell), NO prior context.
**Phase:** copowers **writing-plans** ONLY (produce the plan; do NOT write production code). This arc is the DEFERRED 18-D nightly half + the 2 folded monitor calibrations. **CHARC sec-3 pass PASSED 2026-06-16 (conditions C-NH1-5).** Measurement-core (RD merge-blocking at executing).
**Expected duration:** one focused session (plan + adversarial Codex to convergence).

## §0 Read first (ground every line/signature against live code — anchors drift)
1. `docs/implementer-dispatch-recipe.md` (the protocol) + the repo `CLAUDE.md` (gotchas).
2. **`docs/data-collection-health-monitor-commissioning-brief.md` §6.7 — THE binding spec** (the three coherent parts below). CHARC C-NH1-5 are binding.
3. **`swing/monitoring/research_health.py`** — the shipped 18-D monitor: `compute_research_health(conn, ...) -> ResearchHealthStatus`, the §3 envelope, the 3 contract constants (imported from `stoplights.py`), and the two checks the calibrations touch: `_check_excluded_reason_breakdown` (#2 invalid_ohlc) + `_check_coverage_gaps` (#3).
4. **`scripts/research_health.py`** — the shipped operator probe; locate its **atomic `latest.json` writer** (the `tmp + os.replace` block + the accessor `stoplights.research_health_artifact_path()`) — this is what C-NH4 extracts into a single-sourced `write_research_health_artifact`.
5. **`swing/pipeline/runner.py`** — locate `_step_shadow_expectancy` (the placement anchor, ~line 1051; re-ground) and how the other best-effort steps use `step_guard`; how the runner opens its DB connection (you need a SEPARATE `mode=ro` conn, NOT the runner's read-write one — C-NH2).
6. **`swing/pipeline/step_guard.py`** — the 17-B context manager signature (`step_guard(lease, name, status_key=..., logger=...)`); confirm LeaseRevokedError propagates + all else is swallowed+logged.
7. The engine manifest shape (the shadow-expectancy `manifest.json` `funnel.per_hypothesis.*.excluded.invalid_ohlc` / `funnel.detection_level.unique_signals`) for grounding the #2 baseline value (`research/harness/shadow_expectancy/`).

## §0 Skill posture
Invoke `copowers:writing-plans` (wraps `superpowers:writing-plans` + adversarial Codex). Codex tier = **`review-fast`** (writing-plans). Run to convergence; persist every round to `.copowers-findings.md`. The bounded-scope #39 corollary applies (a finding premised SOLELY on a schema-prevented value is out-of-scope-for-V1, WITH a cited constraint). Do NOT write production code (planning phase). Return to the ORCHESTRATOR only (no mailbox).

## §1 The three coherent parts (the plan must cover all three)

### PART 1 — the nightly pipeline STEP (CHARC C-NH1-5, BINDING)
- **C-NH1:** wrap the step in `with step_guard(lease, "research_health", status_key="research_health_status", logger=log):` — `LeaseRevokedError` propagates; ALL else swallowed+logged; the step NEVER fails the run. Do NOT hand-roll a wrapper.
- **C-NH2:** open a READ-ONLY `mode=ro` URI conn (mirror `scripts/research_health.py`'s `mode=ro` connect), NOT the runner's read-write `connect()` — physically enforce the read-only LOCK.
- **C-NH3:** placement **immediately AFTER `_step_shadow_expectancy`** (runner.py ~1051; re-ground), BEFORE `complete`.
- **C-NH4 (SINGLE-SOURCE the artifact write — the #24-#26 divergence guard):** extract `write_research_health_artifact(status, out_path=None)` into `swing/monitoring/research_health.py` (resolve via `stoplights.research_health_artifact_path()` → `to_dict()` → atomic `tmp + os.replace`). **REFACTOR `scripts/research_health.py` to call it; the step calls the SAME fn. NO second copy of the writer.**
- **C-NH5:** on ANY failure write NOTHING (retain the prior `latest.json`; the 18-F staleness gate surfaces a persistent failure as grey). NEVER a partial artifact.
- **`role_mail`-on-ATTENTION is DEFERRED to 18-H.7 — do NOT add it here.**

### PART 2 — CALIBRATION A: #3 `coverage_gaps` trailing 1-session grace (monitor-internal, NO new tripwire)
Tolerate a trailing `<= 1`-session lag → not-red; **RED only on a `>= 2`-session trailing lag OR any INTERIOR gap.** (This resolves the post-close→pre-nightly session-rollover that reds #3 every evening.) **Required test:** trailing-1 → not-red; trailing-2 AND interior gap → red (both-ways distinguishing).

### PART 3 — CALIBRATION B: #2 `invalid_ohlc` baseline (monitor-internal, NO new tripwire; consistent w/ FIX 1)
A **named baseline-count constant** (~the as-of-18-D 06-10-cohort `invalid_ohlc` ≈ 23 — **GROUND the value + state the aging vs the live manifest**) → the `invalid_ohlc` arm reds ONLY ABOVE the baseline. **SCOPE LOCK:** baseline ONLY `invalid_ohlc`; `insufficient_forward_depth` + `missing_observations` keep their existing thresholds. **Required test:** known ≈23 backlog → not-red; +N above → red.

## §2 LOCKS (RD merge-blocking — carry into the plan)
1. **READ-ONLY DB:** only `latest.json` is written; NEVER the measurement DB (C-NH2 `mode=ro`).
2. **Reuse, don't re-implement:** the shipped `compute_research_health` + the single-sourced `write_research_health_artifact` (C-NH4) + the 3 contract constants. The §3 envelope / frozenset enum validation / atomic-write stay UNCHANGED.
3. **The step is best-effort (C-NH1/C-NH5):** never perturbs the run (no exception escapes except `LeaseRevokedError`; no partial artifact).
4. **Calibrations are monitor-internal:** NO schema, NO dependency, NO new tripwire; #3/#2 logic changes only.
5. **NO `role_mail`-on-ATTENTION** (deferred to 18-H.7).

## §3 What the plan must deliver
A writing-plans plan doc at `docs/superpowers/plans/2026-06-16-phase18-arc-d-nightly-half-plan.md` (or your dated equivalent), with per-task TDD slices for:
- `write_research_health_artifact` extraction + the `scripts/research_health.py` refactor to call it (with a test that the script + a direct call produce the SAME artifact; no behavior change to the script's existing surface).
- The nightly step in `runner.py` (the `step_guard` wrap, the `mode=ro` conn, the placement after `_step_shadow_expectancy`, write-nothing-on-failure) — with tests: the step runs after shadow-expectancy + writes `latest.json`; a failing `compute_research_health` does NOT fail the run AND leaves the prior artifact intact (C-NH5); `LeaseRevokedError` propagates (C-NH1).
- CALIBRATION A (#3) + its both-ways test; CALIBRATION B (#2) + its both-ways test — each with the **grounded** baseline/grace value (cite the live-manifest / coverage-logic grounding, per memory `feedback_regression_test_arithmetic` + `feedback_adversarial_review_verify_data_shapes`).
- A per-item data-grounding note (the runner placement line, the `step_guard` signature, the `mode=ro` connect pattern, the #2 baseline value from the live manifest) — cite the file:line confirmed.
- A V1-simplification ledger (anything deferred, e.g. the 18-H.7 mail-on-ATTENTION).

## §4 Adversarial review (watch items)
Run `copowers:writing-plans`'s Codex chain (`review-fast`) to convergence. Watch items:
- Does the step use `step_guard` exactly (C-NH1) — no hand-rolled wrapper — and a SEPARATE `mode=ro` conn (C-NH2), never the runner's RW conn?
- Is the writer SINGLE-SOURCED (C-NH4) — one `write_research_health_artifact`, called by BOTH the script and the step (no second copy)?
- Write-nothing-on-failure (C-NH5) — no partial artifact; the prior `latest.json` retained?
- Are the calibration values GROUNDED (the #2 ≈23 baseline vs the live manifest; the #3 trailing-grace boundary) and the both-ways tests distinguishing?
- Calibrations monitor-internal (no schema/dep/new tripwire); the §3 envelope unchanged.

## §5 Done criteria
The plan doc is committed; the Codex chain reached `NO_NEW_CRITICAL_MAJOR` (each round persisted). Every part (the step C-NH1-5, the 2 calibrations) has grounded data-notes + distinguishing-test specs. No production code written.

## §6 Return report (to the ORCHESTRATOR — final chat message; recipe §4)
Plan doc path + commit SHA(s); the per-item grounding (the runner placement line, the step_guard signature, the #2 baseline value + its live-manifest grounding, the #3 grace boundary); Codex `review-fast` rounds + verdict + `.copowers-findings.md` path; the LOCKS reflected in the plan; any bounded-scope out-of-scope adjudications WITH the cited constraint; the V1-simplification ledger; open questions / live-code-wins flags.

## §7 If you get stuck
A spec anchor (the runner line, the step_guard signature, the writer block, the manifest key) doesn't match live code → state the question + your recommended resolution; do NOT guess silently. A part that would need a schema/dep/new tripwire → STOP (that crosses the C-NH carve-out; route up).
