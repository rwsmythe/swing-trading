# Phase 3e — Chart-Pattern Flag-V1: Phase 1 Execution Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Execute **Phase 1 ONLY** (Tasks 1.0 through 1.14) of the chart-pattern flag-v1 implementation plan via `copowers:executing-plans`. Produce the algorithm core (`swing/evaluation/patterns/flag_classifier.py`), config namespace (`cfg.classifier.*`), and ≥12 unit tests on synthetic data. Stop at the Phase 1 checkpoint — do NOT proceed to Phase 2 or beyond.
**Expected duration:** ~1 session (~13 tasks per writing-plans implementer's estimate).
**Output:** Phase 1 commits landed on `main`, fast suite green, ≥12 unit tests covering each gate threshold + classifier-error pattern=NULL distinction; adversarial Codex review on the combined Phase 1 diff reaches `NO_NEW_CRITICAL_MAJOR`.

---

## §0 Read first

In this order:

1. **`docs/superpowers/plans/2026-04-26-chart-pattern-flag-v1-plan.md`** — THE plan. Phase 1 is at lines 36-952 (Tasks 1.0 through 1.14). Read Phase 1 in full; skim later phases for context but DO NOT execute them.
2. **`docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`** — the source-of-truth design. Phase 1 implements spec §3.1 (algorithm), §3.1.4 (config thresholds), §4.1 (Layer 1 unit tests). Spec passed 5 adversarial Codex rounds; design is settled.
3. **`docs/orchestrator-context.md`** — project framing, copowers workflow, anti-patterns, lessons captured (especially the 6 chart-pattern brainstorm lessons + the 3 plan-drafting lessons). TDD discipline is rigid.
4. **`CLAUDE.md`** at repo root — gotchas, conventions. Phase 1 is in-isolation (no DB, no web, no pipeline); most gotchas don't apply, but: pandas/numpy version drift potential, Python 3.14 dev-box, ruff baseline 81 errors (no new violations), no Claude co-author footer, no `--no-verify`, no amending.
5. **`docs/phase3e-chart-pattern-writing-plans-brief.md`** (briefly) — context for why the plan structure landed as it did.

---

## §0 Skill posture

**INVOKE:**

- `copowers:executing-plans` — wraps `superpowers:subagent-driven-development` with adversarial Codex review on the combined Phase 1 diff after task commits land. Iterates rounds to `NO_NEW_CRITICAL_MAJOR`.

**DO NOT INVOKE:**

- `copowers:writing-plans` / `superpowers:writing-plans` — plan is settled.
- `copowers:brainstorming` / `superpowers:brainstorming` — design is settled.
- `superpowers:executing-plans` directly — use the copowers wrapper for adversarial review per project standing convention ("Adversarial review on every code-shipping session").

The execution wrapper drives task-by-task implementation per the plan's TDD discipline, then runs Codex review on the cumulative Phase 1 diff. Fix findings as new commits (no amending).

---

## §1 Scope (Phase 1 ONLY)

**EXECUTE these tasks (in order, per plan):**

- Task 1.0 — Config: `cfg.classifier.*` threshold namespace (foundation; lands first to enable dependency injection in 1.3+)
- Task 1.1 — Package skeleton (`swing/evaluation/patterns/__init__.py` + module stubs)
- Task 1.2 — `data_window` gate (gate 1)
- Task 1.3 — Synthetic flag fixture builder + first detection
- Task 1.4 — `pole_gain` gate threshold pair
- Task 1.5 — `pullback_depth` gate threshold pair
- Task 1.6 — `tightness_ratio` gate threshold pair
- Task 1.7 — `volume_contraction` gate threshold pair
- Task 1.8 — `ma_structure` gate (binary: stacked + rising)
- Task 1.9 — `flag_floor_holds` gate
- Task 1.10 — confidence min-aggregation
- Task 1.11 — search picks best fit; tie-break
- Task 1.12 — best-attempted candidate (max-min soft clearance)
- Task 1.13 — `pattern=NULL` adapter for classifier-error path
- Task 1.14 — Phase 1 checkpoint (fast suite green; ≥12 unit tests)

**DO NOT EXECUTE (out of scope; STOP here):**

- Phase 2 (persistence migrations + repos)
- Phase 3 (pipeline integration)
- Phase 4 (watchlist / dashboard read paths)
- Phase 5 (trade-entry form + CLI)
- Phase 6 (chart overlay)
- Phase 7 (integration tests + operator-labeled fixtures)
- ANY modification to `swing/data/`, `swing/web/`, `swing/pipeline/`, `swing/trades/`, `swing/cli.py`, `swing/rendering/`

If Phase 1 reveals a problem that requires touching out-of-scope code, STOP and surface to orchestrator under "OPEN QUESTIONS" in the return report.

---

## §2 Locked constraints (do NOT re-litigate)

The spec's six locked constraints (spec §1.1) and the plan's settled design decisions are binding. Phase 1 in particular must respect:

- **Pure-function classifier.** `classify_flag(bars: DataFrame, cfg: ClassifierConfig) -> FlagClassificationResult`. No DB, no web, no IO. No global state. Deterministic.
- **Rule-based geometric algorithm.** ALL 11 gates required for `detected=True`. Search over (M, N) ∈ [5,30] × [5,21]. No ML, no LLM, no hybrid.
- **Confidence = `min(four continuous-gate clearances)`** on [0.0, 1.0]. Geometric clearance score, NOT calibrated probability.
- **Best-attempted ranking.** When no (M, N) window passes all gates, return the candidate with max(min-of-soft-clearances) over the 4 continuous gates. Deterministic baseline.
- **Classifier-error path.** Internal exception → return `FlagClassificationResult(pattern=None, ...)` with error key in components. Distinguishable from `pattern='none'` (evaluated negative).

If anything in Phase 1 conflicts with these, STOP and surface to orchestrator. Do NOT redesign.

---

## §3 Conventions

- **Branch:** `main`. No feature branches.
- **TDD discipline (rigid):** failing test → run to see RED → minimal implementation → run to see GREEN → commit. One red-green cycle per logical change. Per-task commit boundaries per the plan.
- **Commits:** Conventional Commits (`feat(patterns):`, `test(patterns):`, etc.). **No Claude co-author footer. No `--no-verify`. No amending — every fix is a NEW commit.**
- **Discriminating-test discipline:** every threshold test uses a ±epsilon pair (just-above + just-below) so the test under post-fix code distinguishes from pre-fix code.
- **Compounding-confound discipline:** Phase 1's compounding-confound risk is low (no UI, no sort, no state) but maintain the principle for any test asserting on a primary key behavior.
- **Tests:** `python -m pytest -m "not slow" -q` MUST be green at the Phase 1 checkpoint. Plan does NOT require it green between every task, but Task 1.14 checkpoint is mandatory.
- **Ruff:** baseline 81 errors per CLAUDE.md. Phase 1 must NOT introduce new violations in `swing/evaluation/patterns/`. Run `ruff check swing/evaluation/patterns/` after Task 1.13 and before Task 1.14 commit.

---

## §4 Adversarial review (handled by copowers wrapper)

The `copowers:executing-plans` wrapper invokes Codex MCP review on the combined Phase 1 diff after Task 1.14 lands. Pass these specific watch items:

- **Spec fidelity.** Algorithm matches spec §3.1.3 gate definitions; confidence formula matches spec §3.1.4. Any deviation from the spec is a finding.
- **Plan fidelity.** Tasks executed in plan order; no skipped tasks; no tasks added beyond the plan.
- **TDD integrity.** Each implementation commit has a preceding failing-test commit. No "implement first, test after" ordering.
- **Discriminating tests.** Every threshold test pair (just-above + just-below the threshold) actually distinguishes pre-fix vs post-fix behavior.
- **Vacuous-test risk.** No test passes against an unimplemented method (e.g., test against `assert classify_flag(bars).detected == False` when classifier returns False unconditionally would pass even if the gate isn't implemented). Each gate test must have BOTH a True case and a False case that flip with implementation.
- **Best-attempted determinism.** Task 1.12's max-min ranking must be deterministic — if two candidates tie on the soft-clearance score, the tiebreaker must be specified and tested.
- **Classifier-error path correctness.** Task 1.13's exception handler must return a `FlagClassificationResult` that downstream code (Phase 2 persistence) can distinguish from `pattern='none'`. Components dict has an `"error"` key.
- **Pure-function discipline.** Classifier must not mutate input DataFrame; must not depend on module-level state; must not do IO. Test should verify the input DataFrame is unchanged after classifier returns.
- **Config-injection correctness.** Task 1.0's `ClassifierConfig` is consumed by `classify_flag(bars, cfg=...)` per Task 3.2's call signature. Defaults from `ClassifierConfig()` match spec §3.1.4.

---

## §5 Done criteria

Phase 1 execution is done when ALL of the following hold:

- [ ] All 15 tasks (1.0 through 1.14) have landed commits on `main`.
- [ ] `python -m pytest tests/evaluation/patterns/test_flag_classifier.py -v` green; ≥12 tests covering each gate threshold + classifier-error path + best-attempted ranking.
- [ ] `python -m pytest -m "not slow" -q` green (full fast suite).
- [ ] `ruff check swing/evaluation/patterns/` clean (no new violations).
- [ ] Adversarial Codex review on combined Phase 1 diff reaches `NO_NEW_CRITICAL_MAJOR`.
- [ ] Phase 1 implementation does NOT touch `swing/data/`, `swing/web/`, `swing/pipeline/`, `swing/trades/`, `swing/cli.py`, or `swing/rendering/`.

---

## §6 Return report format

Final message to orchestrator (via operator) MUST include:

```
PHASE: 1 (Algorithm core) of chart-pattern flag-v1 plan
COMMIT CHAIN: <first SHA>..<last SHA> (N commits)
FAST SUITE: <previous count> → <new count> tests (Δ +<unit-test count>)
ADVERSARIAL ROUNDS: <N>; FINAL VERDICT: NO_NEW_CRITICAL_MAJOR

TASKS COMPLETED:
- Task 1.0 — <one-line summary, commit SHA>
- Task 1.1 — <one-line summary, commit SHA>
- ... (all 15 tasks)

ALGORITHM SUMMARY:
- Detection gates implemented: <list 11 gates>
- Confidence formula: min(<list 4 continuous-gate clearances>)
- Search range: (M, N) ∈ [5,30] × [5,21]
- Best-attempted ranking: <one line on tiebreaker>
- Classifier-error path: <one line on error key + return shape>

ADVERSARIAL FINDINGS (each with disposition):
- <finding>: FIXED in commit <SHA> / ACCEPTED with rationale: <text>

OPEN QUESTIONS FOR ORCHESTRATOR:
- <any plan/spec contradiction surfaced; otherwise "None">

LESSONS WORTH CAPTURING (process insights from execution):
- <bullet list, if any>

PHASE 1 → PHASE 2 HANDOFF NOTES:
- <anything Phase 2 implementer needs to know that isn't in the plan>
```

---

## §7 If you get stuck

- **Plan/spec contradictions.** Surface in return report under "OPEN QUESTIONS." Do NOT amend the plan or spec; do NOT re-design. The orchestrator handles amendments via a separate dispatch.
- **TDD ordering uncertainty.** When in doubt, failing-test-first. The plan task structure already encodes this; follow it.
- **Codex finding contradicts plan.** Apply receiving-code-review discipline. If finding correct AND plan wrong, surface to orchestrator. If finding wrong, document why with rationale.
- **Out-of-scope pull.** If a Phase 1 task seems to require touching out-of-scope code (Phase 2-7 territory), STOP. Surface as "OPEN QUESTIONS." Do NOT silently expand scope.
- **Yfinance / pandas API drift.** Phase 1 uses synthetic-data DataFrames (no live yfinance). If pandas behavior surprises you, log it in lessons captured.
- **Test-discrimination uncertainty.** Implement the gate, mutate the threshold by ±epsilon, re-run. If both directions still pass, the test is vacuous — fix per the discriminating-test discipline.

---

## §8 Anti-patterns specific to this execution

- **Scope creep into Phase 2.** Persistence is a deliberate next-session boundary. Even small "while I'm here" persistence work is out of scope.
- **Skipping Task 1.0 config foundation.** Task 1.0 lands FIRST per the plan to avoid forward-reference issues. Do NOT inline thresholds into the classifier and "wire config later."
- **Shortcutting the synthetic-fixture builder (Task 1.3).** The fixture builder is reused by every later gate test. Build it carefully; subsequent tasks save effort.
- **Skipping the best-attempted ranking determinism check.** Task 1.12's tiebreaker behavior must be deterministic AND tested. Non-determinism here corrupts Phase 7 calibration analysis.
- **Treating the classifier-error path as a happy-path return.** Task 1.13's exception path returns `pattern=None` (NOT `pattern='none'`). The distinction is load-bearing — Phase 2 persistence schema relies on it.
- **Vacuous regression tests.** Every test must produce different outcomes pre-fix vs post-fix. Per `feedback_regression_test_arithmetic` memory and 2026-04-26 compounding-confound lesson.
