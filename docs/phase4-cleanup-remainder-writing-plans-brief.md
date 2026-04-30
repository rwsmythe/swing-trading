# Phase 4 Cleanup-Remainder Bundle — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Author an implementation plan for the Phase 4 cleanup-remainder bundle (post-2026-04-28 operator sequence Phase 4) via `copowers:writing-plans`. This dispatch bundles 5 deferred follow-up items across Phase 1, 2, and 3 dispatches into a single coherent cleanup. Brainstorm is EXPLICITLY SKIPPED — design decisions pre-locked by operator history; remaining decisions in this brief.

**Expected duration:** ~30-60 min plan-authoring + 3-5 Codex rounds via `copowers:writing-plans` wrapper = ~3-5 hours total.

**Dispatch type:** `copowers:writing-plans` (NOT brainstorming, NOT executing-plans).

---

## §0 Read first

1. **`docs/orchestrator-context.md`** — read these sections:
   - §"Currently in-flight work" — current state at HEAD (Phase 3 OHLCV archive shipped 2026-04-30 commit `3335d6c`; this dispatch is Phase 4).
   - §"Recent decisions and framings" — particularly the 2026-04-25 "Bug 7 mixed-anchor family confirmed closed in web layer" (closure was scoped; this dispatch closes the family DURABLY via centralization per the just-captured 2026-04-29 "Bug-class durability vs scope-of-closure" lesson).
   - §"Binding conventions" — 4-tier commit-message convention; observable-verification grep ERE form; ruff baseline 91; no-amend; no Claude footer.
   - §"Anti-patterns" — particularly mid-session scope expansion; brief drafting drift; vacuous regression tests.
   - §"Lessons captured" — read entire section. Particularly relevant:
     - **Bug-class durability vs scope-of-closure** (2026-04-29) — DIRECTLY applicable; this dispatch IS the durable closure of Bug 7 mixed-anchor.
     - **Helper-internal anchoring of side-effecting boundaries** (just-captured 2026-04-30) — applies to the shared-helper design.
     - **Multi-path-ingestion** (2026-04-29) — applies to the 5+ inline-query sites that all consume the same anchor concept.
     - **MAX_ROUNDS-vs-NO_NEW_CRITICAL_MAJOR** — verification round if final round had findings.
     - **Spec/plan silence on form-driven success-path response shape** (2026-04-29) — not directly applicable (this dispatch isn't form-driven), but the underlying "enumerate ALL paths" discipline is.
     - **External-API empty-result must be treated as transient** (just-captured 2026-04-30) — relevant context for the test additions on the cold-start path.

2. **`docs/phase3e-todo.md`** §"From Session 2 (watchlist sort-by-tags)" + §"2026-04-29 production-verification investigation dispatch follow-up" + §"2026-04-30 OHLCV archive Phase 3 follow-up" — backlog source for the 5 cleanup items bundled in this dispatch.

3. **`CLAUDE.md`** — particularly:
   - **External-API empty-result transient** (just-added 2026-04-30) — context for the cold-start test addition.
   - **HTMX OOB-swap partial drift** — relevant to the Phase 2 multi-rebuild drift item.

4. **Source files to inspect:**
   - **5 inline `pipeline_runs` query sites** (per Phase 2 hyp-recs success-path-fix executing-plans return report):
     - `swing/web/view_models/dashboard.py:555-559` (today_decisions / classifications query).
     - `swing/web/view_models/dashboard.py:595-609` (last_pipeline_ts / stale-banner query).
     - `swing/web/view_models/watchlist.py:103, 190` (two query sites).
     - `swing/cli.py:449` (CLI consumer).
   - **Two shared helpers** (existing precedents):
     - `swing/web/view_models/dashboard.py latest_evaluation_run_id(conn) -> int | None` — pipeline-bound first, then standalone-eval fallback.
     - `swing/web/view_models/dashboard.py latest_completed_pipeline_run` (or similar; verify exact name) — pipeline-bound only; from R4-Major-2 of hyp-recs trade-prep expansion.
   - **`research/parity/run.py:178`** — references removed `_cache_path` method on `PriceFetcher` (Phase 3 refactor removed this method).
   - **`swing/web/templates/partials/watchlist_top5_section.html.j2`** + `swing/web/view_models/dashboard.py _sort_watchlist` — for the sort-neutrality fixture diversification.
   - **`tests/web/conftest.py`** + 3 test files duplicating `_seed_watchlist_and_candidate` (per Task 1 reviewer note from sector capture executing-plans):
     - Identify which 3 test files via grep; lift the helper to conftest.py.
   - **`swing/web/routes/trades.py entry_post`** — for the multi-rebuild cross-fragment drift (Phase 2 R1 Minor 2 pre-existing concern; theoretical drift if pipeline run lands mid-POST).

5. **Precedent plans** for structural reference:
   - `docs/superpowers/plans/2026-04-29-ohlcv-archive-consolidation-plan.md` (most-recent; 7 tasks; bundle-style scope).
   - `docs/superpowers/plans/2026-04-29-hyp-recs-success-path-fix-plan.md` (5 tasks; tight focus).

If any file path doesn't resolve, surface in return report — do NOT silently proceed against a stale path.

---

## §0 Skill posture

- **INVOKE** `copowers:writing-plans` — wraps `superpowers:writing-plans` with adversarial Codex review (3-5 rounds typical).
- **DO NOT INVOKE** `superpowers:brainstorming`, `copowers:brainstorming`, `superpowers:executing-plans`, or `copowers:executing-plans`. Design decisions are pre-locked (see §2). Re-litigation is out of scope. If a locked decision is impossible to implement as written, STOP and surface in return report via §10 escape hatch; do NOT silently re-design.
- **DO** invoke adversarial Codex review per `copowers:writing-plans` standard cycle. Iterate to `NO_NEW_CRITICAL_MAJOR`. **Per the chart-pattern flag-v1 Phase 7 induced-bug pattern + 2026-04-29 hyp-recs writing-plans MAX_ROUNDS lesson:** if the final round produces findings that resolve, run ONE additional verification round to confirm clean before terminating. Do NOT stop at MAX_ROUNDS with active findings.
- **Plan output target path:** `docs/superpowers/plans/2026-04-30-phase4-cleanup-remainder-plan.md`. Commit the plan as part of the standard cycle.

---

## §1 Strategic context

**Why this dispatch.** Phase 4 of the post-2026-04-28 operator sequence bundles deferred follow-ups from Phase 1 (sector capture), Phase 2 (hyp-recs trade-prep + success-path fix), and Phase 3 (OHLCV archive consolidation). Individual items are small + mechanical; bundling them into one cleanup-remainder dispatch is more efficient than dispatching each separately (one writing-plans cycle, one executing-plans cycle, one operator-witnessed verification).

**Sequencing context.** Phase 4 of the 6-phase post-2026-04-28 sequence (sector → hyp-recs trade-prep + success-path-fix → OHLCV archive → **cleanup-remainder (this dispatch)** → configuration page → Tier-3 design).

**Key durable closure:** Bug 7 mixed-anchor family was "durably closed in web layer 2026-04-25" but has resurfaced TWICE since (Phase 2 hyp-recs trade-prep expansion R1 M2; Phase 2 hyp-recs success-path fix). Per the just-captured "Bug-class durability vs scope-of-closure" lesson (2026-04-29), the right fix is centralization at chokepoint. **This dispatch closes Bug 7 durably via factor-shared-helper-then-route-all-consumers-through-it.**

---

## §2 Locked decisions (DO NOT re-litigate)

Five items bundled; design pre-locked.

### Item 1: Bug 7 mixed-anchor family — durable closure via two-helper-per-contract pattern

**Architecture: KEEP TWO SHARED HELPERS** (NOT consolidate into one). Each helper has a distinct contract:

- **`latest_evaluation_run_id(conn) -> int | None`** — pipeline-bound first; falls back to standalone-eval. Contract: "give me the latest available eval-run-id, even if it came from standalone eval." Consumers that need this: full dashboard render path (`/`), hyp-recs section panel rebuild (must render in standalone-eval-only state).
- **`latest_completed_pipeline_run(conn) -> int | None`** (or whatever exact name exists; verify at plan-time) — pipeline-bound only; NO fallback to standalone-eval. Contract: "give me the latest completed pipeline run; absent if none." Consumers that need this: hyp-recs expand/form surfaces (must operate on pipeline-bound data per the R4-Major-2 contract from hyp-recs trade-prep expansion).

**Why keep two:** consolidating into one would either (a) break the standalone-eval-only state for full dashboard render OR (b) make pipeline-bound surfaces silently accept standalone-eval data. Both are wrong. The two contracts are fundamentally different and must remain distinct.

**Refactor scope:** the 5 inline `pipeline_runs` query sites must each be classified by their consumer's contract and routed through the matching shared helper:
- `swing/web/view_models/dashboard.py:555-559` (today_decisions / classifications) — likely pipeline-bound contract; verify at plan-time.
- `swing/web/view_models/dashboard.py:595-609` (last_pipeline_ts / stale-banner) — likely with-fallback contract (stale-banner should show even in standalone-eval-only state); verify at plan-time.
- `swing/web/view_models/watchlist.py:103` — verify which contract.
- `swing/web/view_models/watchlist.py:190` — verify which contract.
- `swing/cli.py:449` — verify which contract.

**`id DESC` tiebreaker:** both helpers MUST have it on BOTH branches (per Codex R2 escalation in hyp-recs success-path-fix plan; deterministic resolution under tied `finished_ts`).

**Tests:** for each refactored site, add a discriminating test that (a) fixes the inline-query mixed-anchor failure mode AND (b) exercises the contract distinction (with-fallback vs pipeline-bound). Vacuous tests that don't exercise the standalone-eval-only state would miss the bug.

### Item 2: research/parity/run.py:178 _CountingPriceFetcher rewrite

`research/parity/run.py:178` references the removed `PriceFetcher._cache_path` method. The `_CountingPriceFetcher` wrapper was the parity comparator's instrumentation hook for cache-stat introspection. **Rewrite to use the new archive directory shape:** per-ticker file-existence check (`{TICKER}.parquet` + `{TICKER}.meta.json` in `cfg.paths.prices_cache_dir`); meta-staleness check via reading `last_full_refresh_date` from the JSON sidecar.

**Scope:** research-branch CLI; not in fast suite. Add a single unit test in `tests/research/` (create dir if absent) that exercises the rewritten `_CountingPriceFetcher` with a synthetic archive fixture. NOT live yfinance.

### Item 3: Parallel cold-start test with today-aligned archive

Add a parallel cold-start test in `tests/web/test_ohlcv_cache.py` (or wherever the existing OhlcvCache cold-start test lives) using a today-aligned archive (`last_full_refresh_date = today`; archive contains today's bar OR bar matching FIXED_TODAY). The test asserts TRUE zero-yfinance behavior — `helper_calls == ["AAPL"]` AND no `yf.download` call AT ALL (instrument via mocking `yfinance` module-level + asserting no calls). Discriminating: vacuous test would still pass under the existing weakness (where empty `yf.download` mock satisfies the contract); this test must FAIL under that weakness.

### Item 4: Test gaps from Phase 2

Three additive tests (per phase3e-todo "From Session 2 (watchlist sort-by-tags)" + earlier hyp-recs follow-ups):

- **<tbody>-shape check** in `test_refresh_route_renders_drift_equivalent_html_to_full_page` (per Phase 2 R1 Minor 1 advisory) — supplements the existing `<thead>` byte-equivalence with a `<tbody>` shape match. Closes the drift-equivalence gap.
- **Non-equal-priority sort-neutrality fixture** in `tests/evaluation/patterns/test_sort_neutrality.py` (per Phase 2 R1 Minor 2 advisory) — current pinned BASELINE_TUPLE uses alphabetical-tiebreak fixture (NVDA pivot=100, AMD pivot=200, TSLA pivot=300 yields equal priority_hint → alphabetical). Add a non-equal-priority fixture to catch regressions perturbing non-tie prioritization inputs.
- **Lift `_seed_watchlist_and_candidate` to `tests/web/conftest.py`** (per sector capture Task 1 reviewer note) — three test files duplicate the seed pattern; lift to conftest. Plan task body identifies the 3 files via grep + the lift.

### Item 5: Multi-rebuild cross-fragment drift discipline (informational; partial action)

`entry_post` assembles 3 OOB chunks from independent connection lifecycles (per Phase 2 hyp-recs success-path-fix R1 Minor 2 advisory). Theoretical drift if a pipeline run lands mid-POST. Pre-existing concern; out-of-scope to FIX in this dispatch (would require rewrite of entry_post's response-composition pattern), but **plan should add a single discriminating test** that constructs the mid-POST-pipeline-run scenario AND asserts the current behavior (whatever it is). The test pins current behavior; future change to fix the drift would explicitly update the test. NOT a fix; a behavior-pin.

If the test reveals current behavior is broken (drift produces operator-visible inconsistency), surface in return report; do NOT silently fix mid-dispatch (that's mid-session scope expansion).

---

## §3 Open design questions for writing-plans phase

Mechanical questions the writing-plans implementer resolves while drafting the plan.

### A. Helper naming consistency

If the existing pipeline-bound-only helper is named something other than `latest_completed_pipeline_run`, plan should specify the exact existing name. If both helpers exist, plan refers to both by current name. If only `latest_evaluation_run_id` exists and the pipeline-bound-only helper needs to be created, plan task adds it.

Verify at plan-time via grep:
```
grep -rn "latest_evaluation_run_id\|latest_completed_pipeline_run\|def latest_" swing/
```

### B. Per-site contract classification

For each of the 5 inline-query sites, plan determines which contract (with-fallback vs pipeline-bound) is correct. This is per-site-per-consumer judgment based on the surface's UX semantics (does it need to render in standalone-eval-only state?). Plan task body documents the classification rationale per site.

### C. Test surface for Bug 7 durable closure

Plan defines per-site discriminating tests. Each test must:
- Construct standalone-eval-only state (no completed pipeline_runs).
- Assert the site's expected behavior (renders for with-fallback consumers; absent/empty for pipeline-bound consumers).
- Vacuous test that passes under the pre-fix inline-query OR under either-helper consumption would fail the discriminating-test discipline.

Plan also adds a structural-guard test (per the chart-scope policy v2 + sector capture precedent) that asserts NO inline `pipeline_runs WHERE state='complete'` queries exist OUTSIDE the two shared helpers (grep-based test).

### D. Test count baseline

Plan pins current fast-test count (`python -m pytest -m "not slow" -q` output). Current baseline (post-Phase-3): 1341 fast tests at HEAD `3335d6c`. Plan baselines at HEAD at plan-authoring time.

---

## §4 V1 Scope (binding)

5 bundled items per §2:

1. Bug 7 mixed-anchor family durable closure — refactor 5 inline-query sites to consume two shared helpers; add `id DESC` tiebreaker to both branches of both helpers; add structural-guard test.
2. `research/parity/run.py:178` `_CountingPriceFetcher` rewrite for new archive directory shape.
3. Parallel cold-start test with today-aligned archive (true zero-yfinance verification).
4. Phase 2 test additions: `<tbody>`-shape check; non-equal-priority sort-neutrality fixture; lift `_seed_watchlist_and_candidate` to conftest.py.
5. Multi-rebuild cross-fragment drift discipline — single discriminating test pinning current behavior (NOT a fix).

**File map (tentative; plan refines):**
- 4-6 production files modified (the inline-query consumers + helper module if a new helper is added).
- 1 production file modified (`research/parity/run.py`).
- 5-8 test files modified or added.

**Plan task count: ~5-8 tasks** (small bundle; each item is its own task or bundled where they share files).

---

## §5 V1 out-of-scope

- Fixing the multi-rebuild cross-fragment drift (item 5; only pin current behavior; defer fix to future dispatch when operator workflow surfaces drift).
- Centralizing `latest_evaluation_run_id` and `latest_completed_pipeline_run` into a single `latest_run_id(contract)` helper (would obscure the two contracts; explicit two-helper pattern is locked per §2).
- Migrating `research/` branch tests to share fixture infrastructure with production tests (research/production isolation per V2.1 architecture; defer).
- Performance optimization of the shared helpers (current implementations are fine at project scale).
- Browser-driven test harness (per the 2026-04-29 JS-test-harness-weighting lesson follow-up; out-of-scope for this dispatch).

---

## §6 Plan acceptance criteria

The plan output (at `docs/superpowers/plans/2026-04-30-phase4-cleanup-remainder-plan.md`) MUST satisfy:

1. **Per-task TDD discipline.** Each task: failing test first → minimal implementation → passing test → commit.
2. **Discriminating-test discipline** per §2 + the canonical compounding-confound failure modes. Each task with a discriminating test includes a "would this test fail if the implementation never actually called the new code?" sanity-check sentence in the task body.
3. **Multi-path-ingestion lesson application** (2026-04-29) — Bug 7 fix MUST cover all 5 inline-query sites; per-site tests; structural-guard test.
4. **Sequential single-subagent execution.** Plan tasks are SEQUENTIAL; no parallel-subagent collision risk.
5. **Observable-verification subject-only grep pattern** per binding conventions: `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task <N>'` before each task implementation commit. Cross-plan grep aliasing expected.
6. **4-tier commit-message convention.** Task implementations: `feat(<area>): Task N — <description>`. Codex review-fix: `fix(<area>): Codex R<round> Major <id> — <description>`. Internal-Codex: `(internal)` qualifier. Internal code-review: `code-review I<id>`. Format-only: no task ID.
7. **Bug 7 helpers + tests is the FIRST plan task** — structural foundation; subsequent tasks reuse the helpers.
8. **Plan passes copowers:writing-plans Codex review cycle:** iterate to `NO_NEW_CRITICAL_MAJOR` with verification round if final round had findings.

---

## §7 Adversarial review watch items (for Codex during writing-plans cycle)

1. **Bug 7 multi-path coverage.** All 5 inline-query sites refactored; per-site tests; structural-guard test. Vacuous "happy-path passes" tests would miss the standalone-eval-only state failure mode.

2. **Per-site contract classification rationale.** Each site's contract (with-fallback vs pipeline-bound) must be documented in the plan task body. Codex will check that the rationale is concrete + UX-justified, not arbitrary.

3. **`id DESC` tiebreaker on BOTH branches of BOTH helpers.** Per the hyp-recs success-path-fix plan precedent. Tests must construct tied `finished_ts` AND tied `run_ts` separately for each helper.

4. **Structural-guard test for inline queries.** Test asserts NO inline `pipeline_runs WHERE state='complete'` queries exist outside the two shared helpers (grep-based). Mirrors the chart-scope policy v2 + sector capture precedent. If a future contributor adds an inline query, this test fails.

5. **research/parity rewrite uses new archive shape.** Test must construct a synthetic per-ticker parquet + meta JSON archive; rewritten `_CountingPriceFetcher` must correctly count cache-stat operations against the new shape. Vacuous test that doesn't exercise the meta-staleness check would miss the contract.

6. **True zero-yfinance cold-start test.** Mocking `yfinance` module-level (NOT `yf.download` specifically) AND asserting NO calls to ANY yfinance method. Vacuous test that mocks only `yf.download` would still satisfy the existing weakness.

7. **Sort-neutrality non-equal-priority fixture.** Fixture must produce DIFFERENT priority_hint values for the test tickers (NOT equal); discriminating test must perturb one ticker's prioritization input and verify the sort order changes accordingly. Pre-fix vacuous (alphabetical tiebreak masks the perturbation) → post-fix exercises priority_hint distinction.

8. **`<tbody>`-shape check assertion.** Existing `<thead>` byte-equivalence test asserts header structural match; new `<tbody>` shape check asserts row structure (count + per-row column count). NOT byte-equivalence (rows can vary by data); structural shape only.

9. **`_seed_watchlist_and_candidate` lift correctness.** All 3 test files updated to consume the conftest fixture; old per-file definitions removed; existing tests still pass.

10. **Multi-rebuild drift behavior-pin.** Test constructs mid-POST-pipeline-run scenario (probably via threading.Event or similar concurrency primitive); asserts CURRENT behavior. Plan task body explicitly notes "pin current behavior, NOT fix; future dispatch addresses drift if operator workflow surfaces inconsistency."

---

## §8 Done criteria

- Plan committed to `docs/superpowers/plans/2026-04-30-phase4-cleanup-remainder-plan.md`.
- Plan passes `copowers:writing-plans` Codex review cycle, terminating at `NO_NEW_CRITICAL_MAJOR` with verification round if final round had findings.
- All Major findings RESOLVED-by-fix; ACCEPTED-with-rationale only if genuinely out-of-scope.
- Test count baseline pinned in plan body.
- Per-task observable-verification step included in each task body.
- Per-task discriminating-test sanity-check sentence included where applicable.
- 5 cleanup items (per §4) all mapped to plan tasks; no orphans.

---

## §9 Return report format

Post as final message:

```
## Phase 4 Cleanup-Remainder Plan — Writing-Plans Return Report

**Plan committed at:** docs/superpowers/plans/2026-04-30-phase4-cleanup-remainder-plan.md (commit <SHA>)
**Codex rounds:** N rounds, terminating at NO_NEW_CRITICAL_MAJOR (with verification round if applicable)
**Test baseline pinned:** <count> fast tests at HEAD <SHA>
**Plan task count:** <N tasks>

**Codex findings dispositioned:**
- R1: <count> Critical, <count> Major, <count> Minor — <breakdown>
- R2: ...
... (per round)

**Major design choices made (per §3 open design questions):**
- A. Helper names: <answer>
- B. Per-site contract classification: <summary>
- C. Test surface for Bug 7: <summary>
- D. Test baseline: <count> at HEAD <SHA>

**5 cleanup items mapped to tasks:**
1. Bug 7 durable closure: <Task N+M>
2. research/parity rewrite: <Task X>
3. Parallel cold-start test: <Task Y>
4. Phase 2 test additions: <Task Z>
5. Multi-rebuild drift behavior-pin: <Task W>

**Open questions for orchestrator triage:**
- <any items the implementer flagged as needing operator/orchestrator decision before executing-plans dispatch>

**Recommended next dispatch:** copowers:executing-plans on this plan.
```

---

## §10 If you get stuck

- **If a locked decision (§2) appears impossible to plan as written:** STOP, surface in return report. Do NOT silently re-design.
- **If a precedent file path doesn't resolve:** Use `Glob` / `Grep` to find the actual current path. The 5 inline-query line numbers were captured at the time of Phase 2 hyp-recs success-path-fix executing-plans (post-`a29a592`); subsequent Phase 3 commits may have shifted line numbers — verify by grep, not by line number.
- **If Codex round count exceeds 5 without convergence:** STOP, surface in return report with the unresolved finding. Do NOT iterate indefinitely.
- **If the final Codex round produces findings that resolve:** run ONE verification round to confirm clean before terminating.
- **If discriminating-test sanity check reveals vacuousness:** STOP, restructure the test setup, then resume.
- **If multi-rebuild drift test (item 5) reveals current behavior is BROKEN:** surface in return report; operator decides whether to fix in this dispatch (mid-session scope expansion; usually NO) or defer to follow-up.
- **If per-site contract classification (§3.B) for a specific site is genuinely ambiguous:** surface in return report; operator decides which contract that site should consume.

---

## Appendix A: Cross-references

- **Backlog source:** `docs/phase3e-todo.md` §"From Session 2 (watchlist sort-by-tags)" + §"2026-04-29 production-verification investigation dispatch follow-up" + §"2026-04-30 OHLCV archive Phase 3 follow-up".
- **Just-shipped Phase 3:** `docs/superpowers/plans/2026-04-29-ohlcv-archive-consolidation-plan.md` (commit `00aa6f4`); commit chain `0a5d2d9 → 3335d6c` on origin/main.
- **Bug 7 history:** orchestrator-context.md "Recent decisions" 2026-04-25 (closure scoped to web-layer grep) + Phase 2 hyp-recs trade-prep R1 M2 (resurfaced) + Phase 2 hyp-recs success-path-fix plan history (id DESC tiebreaker added; partial closure) + this dispatch (durable closure).
- **Bug-class durability vs scope-of-closure lesson** (orchestrator-context.md 2026-04-29) — directly applicable.
- **Helper-internal anchoring lesson** (orchestrator-context.md 2026-04-30) — pattern complement for the helper design.
- **Multi-path-ingestion lesson** (orchestrator-context.md 2026-04-29) — applies to the 5+ inline-query sites.
