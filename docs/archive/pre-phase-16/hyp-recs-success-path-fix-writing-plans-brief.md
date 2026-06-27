# Hyp-recs Success-Path Coherence + Anchor-Divergence Fix — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Author an implementation plan for two follow-up fixes from the just-shipped hyp-recs trade-prep expansion executing-plans dispatch (commits `5bd496d → a29a592` on `main`). Both fixes were Codex-flagged at executing-plans R1 as plan-level gaps and ACCEPTED-with-rationale by the implementer (out of dispatch scope; surfaced for follow-up).

**Two fixes bundled in this dispatch:**

1. **R1 Major 1 (PRODUCTION-BLOCKING):** hyp-recs success-path coherence. When entry_post returns success on origin=hyp-recs, the open-positions row replaces the form `<tr>` (which was sitting in hyp-recs `<tbody>`) and the hyp-recs section is not refreshed → visually broken UX + traded ticker stays in recommendations panel.

2. **R1 Major 2:** anchor divergence between `build_hyp_recs_section` (inline `pipeline_runs WHERE state='complete' ORDER BY finished_ts DESC, id DESC` query) and `build_dashboard` (`latest_evaluation_run_id(conn)` helper with 2-step pipeline-bound → standalone-eval fallback). Drift cases: standalone-eval-only state → `/` renders hyp-recs section but `/hyp-recs/refresh` returns empty; tied `finished_ts` → could diverge. Same Bug 7 mixed-anchor family in a new surface.

**Scope: small.** ~3-5 plan tasks. Brainstorm explicitly SKIPPED — design choice for R1 M1 is operator-locked (option (a) symmetric OOB-refresh approach, see §2 below); R1 M2 is a mechanical refactor extracting a shared helper.

**Dispatch type:** `copowers:writing-plans` (NOT brainstorming, NOT executing-plans).

**Expected duration:** ~30-60 min plan-authoring + 2-4 Codex rounds via the `copowers:writing-plans` wrapper = ~2-4 hours total.

---

## §0 Read first

Read these in order before invoking the writing-plans skill:

1. **The just-shipped plan** at `docs/superpowers/plans/2026-04-29-hyp-recs-trade-prep-expansion-plan.md` — context for the bugs being fixed. Particularly Task 4 (build_hyp_recs_section + GET /hyp-recs/refresh; the R1 M2 anchor divergence is here) and Tasks 5.5-5.6 (per-row Enter button + expansion-internal "Take this trade" button; the R1 M1 success-path is the follow-on POST handling).

2. **The just-shipped spec** at `docs/superpowers/specs/2026-04-29-hyp-recs-trade-prep-expansion-design.md` — sections on Q-G (CC pivot wiring), Q-K (ToCToU handling), R4-Major-2 (anchor consistency for hyp-recs origin). The spec's silence on the success-path response shape is THE failure class this dispatch closes.

3. **`CLAUDE.md`** — project conventions, gotchas, invariants. Note especially:
   - **HTMX OOB-swap partial drift gotcha** — directly applicable to the R1 M1 fix; entry_post's OOB swaps must render content via the same `{% include %}` chain as the canonical render path. Hand-duplicated markup is the failure mode.
   - **Test-count drift** — trust pytest output, not plan-pinned counts.

4. **`docs/orchestrator-context.md`** — read these sections in full:
   - §"Currently in-flight work" — current state at HEAD (Phase 2 hyp-recs trade-prep expansion shipped to main `a29a592` but production-blocking R1-Major-1 pending; this dispatch fixes it).
   - §"Binding conventions" — 4-tier commit-message convention; observable-verification grep ERE form; ruff baseline 91; no-amend rule; no Claude footer; subject-only grep regex with `-E` flag and POSIX `[0-9]` digit class.
   - §"Anti-patterns" — particularly mid-session scope expansion; brief drafting drift; bug-fix investigation that tests plausible mechanisms.
   - §"Lessons captured" — read entire section. Particularly relevant lessons:
     - **Spec/plan silence on form-driven success-path response shape is a recurrent failure class** (just-captured 2026-04-29; this dispatch closes the gap that surfaced this lesson).
     - **Worktree protocol environmental note: Windows entry-point binary lock** (just-captured 2026-04-29; relevant if this dispatch's plan introduces any baseline-capture protocol — likely it doesn't, but stay aware).
     - HTMX OOB-swap partial drift (CLAUDE.md gotcha; load-bearing for R1 M1 fix).
     - Bug 7 mixed-anchor family (durably closed in web layer 2026-04-25 per orchestrator-context Recent decisions; R1 M2 is the same family resurfacing in a new surface — fix factors a shared helper to durably close it again).
     - Multi-path-ingestion (2026-04-29).
     - Discriminating-test discipline; compounding-confound class.

5. **The just-shipped executing-plans return report** (in conversation history; full report includes the exact symptoms, file paths, and recommended fix shape for both R1 M1 and R1 M2).

6. **Source files to inspect:**
   - `swing/web/routes/trades.py` `entry_post` — the function to modify for R1 M1. Already returns open-positions row + OOB swaps for `#status-strip` and `#watchlist-top5`. R1 M1 fix adds a third OOB swap of `#hypothesis-recommendations` conditional on origin=hyp-recs.
   - `swing/web/view_models/dashboard.py` — locate `build_hyp_recs_section`, `build_dashboard`, `latest_evaluation_run_id`. Locate the inline `pipeline_runs WHERE state='complete' ORDER BY finished_ts DESC, id DESC` query inside `build_hyp_recs_section`. R1 M2 fix factors a shared helper consumed by both.

If any file path doesn't resolve, surface in return report — do NOT silently proceed against a stale path.

---

## §0 Skill posture

- **INVOKE** `copowers:writing-plans` — wraps `superpowers:writing-plans` with adversarial Codex review (2-4 rounds typical).
- **DO NOT INVOKE** `superpowers:brainstorming`, `copowers:brainstorming`, `superpowers:executing-plans`, or `copowers:executing-plans`. The fixes are pre-locked (see §2). Re-litigation is out of scope. If a fix appears impossible to plan as written, STOP and surface in return report via §8 escape hatch; do NOT silently re-design.
- **DO** invoke adversarial Codex review per `copowers:writing-plans` standard cycle. Iterate to `NO_NEW_CRITICAL_MAJOR`. **Note (per the chart-pattern flag-v1 Phase 7 induced-bug pattern + 2026-04-29 hyp-recs writing-plans MAX_ROUNDS lesson):** termination requires a CLEAN round AFTER all fixes — not just "all findings resolved within MAX_ROUNDS." If R5 produces findings that resolve, run R6 to verify. Don't stop at MAX_ROUNDS with active findings.
- **Plan output target path:** `docs/superpowers/plans/2026-04-29-hyp-recs-success-path-fix-plan.md`.

---

## §1 Strategic context

**Phase 2 cleanup.** The just-shipped hyp-recs trade-prep expansion (executing-plans dispatch, commits `5bd496d → a29a592`) has broken happy-path UX. **Production verification is BLOCKED on this fix landing.** Operator's first "Take this trade" or per-row "Enter" submit produces visually-broken UX:
- Form `<tr>` (which replaced the hyp-rec row) gets replaced with an open-positions row on success.
- Open-positions row ends up INSIDE the hyp-recs `<tbody>` (visually broken).
- Hyp-recs section is not refreshed — traded ticker stays in recommendations panel until the next pipeline run.

**Sequencing.** This dispatch precedes the planned Phase 3 (OHLCV archive consolidation) of the operator sequence. Phase 3 is held until Phase 2 is fully production-verified, which requires this fix.

**R1 M2 bundled.** The anchor-divergence fix is a separate logical concern but lives in the same surface (the just-shipped hyp-recs view-model layer). Bundling avoids two surface-touching dispatches; marginal additional cost.

---

## §2 Locked decisions (DO NOT re-litigate)

Operator-locked 2026-04-29 post-executing-plans triage. The plan implements these as written; no re-design.

### R1 M1 fix: option (a) symmetric OOB-refresh approach

**Approach.** entry_post detects `origin=hyp-recs` from the form's hidden `origin` field. When origin=hyp-recs AND the POST is successful, the response includes:

1. **Primary response (unchanged):** open-positions row replacing form `<tr>` via `closest tr` swap.
2. **Existing OOB swaps (unchanged):** `#status-strip` (account card update) + `#watchlist-top5` (already removes traded ticker if it was on watchlist).
3. **NEW OOB swap (this fix):** `#hypothesis-recommendations` containing the freshly-built hyp-recs section. The OOB swap fires alongside the primary swap; HTMX applies all swaps in the response. Net effect: the open-positions row that briefly lands inside hyp-recs `<tbody>` is nuked when the `#hypothesis-recommendations` OOB swap replaces the entire section. The just-traded ticker is removed from recommendations because the rebuild operates on the post-trade state.

**Why option (a) over alternatives:**
- **Architectural symmetry.** Trade entry already OOB-refreshes every cross-feature container affected by the trade (`#status-strip`, `#watchlist-top5`); hyp-recs joins this pattern as the third OOB-refreshed container.
- **Discoverability.** "Every cross-feature container affected by trade entry gets an OOB refresh" is a single rule — option (b) would create per-origin special cases.
- **Implementation simplicity.** Form's `hx-target="closest tr"` stays unchanged; entry_post adds one OOB-swap chunk conditional on origin=hyp-recs. No template changes required for the form itself.
- **Lesson alignment.** Per the multi-path-ingestion lesson (2026-04-29), keeping multi-origin paths symmetric where possible reduces "this origin works, that origin breaks" failure surface.

**Operator did NOT choose:**
- Option (b) — wider hx-target (form sets `hx-target="#hypothesis-recommendations"` for hyp-recs origin). Asymmetric; rejected.

### R1 M2 fix: factor shared helper consumed by both `build_hyp_recs_section` and `build_dashboard`

**Approach.** Extract the pipeline-run-resolution logic into a shared helper. Both call sites consume the helper. Helper preserves the existing `latest_evaluation_run_id` 2-step fallback (pipeline-bound → most-recent `evaluation_runs.run_ts`). Add `id DESC` tiebreaker to the pipeline-bound branch (deterministic resolution under tied `finished_ts`).

**Why factor:**
- **Bug 7 mixed-anchor family precedent.** The 2026-04-25 closure of the mixed-anchor family in the web layer was based on a `grep -rn "MAX(run_ts) FROM evaluation_runs"` survey; that survey didn't catch the inline `pipeline_runs` query in `build_hyp_recs_section` because it's a different anchor expression. Factoring a shared helper eliminates the surface for future drift.
- **Anchor-consistency across `/` and `/hyp-recs/refresh`.** Both must produce identical anchors for hyp-recs origin. Single shared helper is the structural guarantee.

**Helper name + signature:** writing-plans implementer's design call. Suggest `latest_completed_pipeline_run(conn) -> int | None` that returns the pipeline_run_id (NOT evaluation_run_id) — but verify against existing `latest_evaluation_run_id` semantics during plan authoring. **Open design question for writing-plans phase (see §3).**

---

## §3 Open design questions for writing-plans phase

The brainstorm-skill is SKIPPED. These are minor design questions the writing-plans phase resolves while drafting the plan.

### A. Helper name + signature

Suggested: `latest_completed_pipeline_run(conn) -> int | None`. But verify:
- What does `build_hyp_recs_section` currently use? (pipeline_run_id OR evaluation_run_id?)
- What does `latest_evaluation_run_id` return? (likely evaluation_run_id; need to check).
- If the two consumers want different return shapes (pipeline_run_id vs evaluation_run_id), the helper might need to return both OR be two helpers (`latest_completed_pipeline_run` + `latest_evaluation_run_id_via_pipeline`).
- Plan resolves this by inspecting both call sites' usage patterns + picking the cleanest shared signature.

### B. id DESC tiebreaker preservation

`build_hyp_recs_section`'s inline query has `ORDER BY finished_ts DESC, id DESC`. `latest_evaluation_run_id` does NOT have the `id DESC` tiebreaker. The shared helper should add it (deterministic). Plan task body should explicitly call out the addition; existing callers of `latest_evaluation_run_id` should not break (the `id DESC` tiebreaker is a strict refinement, not a behavior change for callers that don't tie on `finished_ts`).

### C. Standalone-eval fallback policy

`latest_evaluation_run_id` has a 2-step fallback (pipeline-bound first, then most-recent `evaluation_runs.run_ts`). `build_hyp_recs_section`'s inline query is pipeline-bound only. The shared helper should preserve the 2-step fallback (otherwise the standalone-eval-only state breaks `/`). Plan task body should explicitly call out the policy choice.

### D. Test surface for R1 M1

Discriminating tests:
- entry_post for origin=hyp-recs success returns OOB swap of `#hypothesis-recommendations` (assert presence in response body).
- entry_post for origin=hyp-recs success → fresh-rendered hyp-recs section excludes the just-traded ticker (assert ticker absent from OOB chunk).
- entry_post for origin=watchlist (or other origin) does NOT return OOB swap of `#hypothesis-recommendations` (assert absence — preserves current behavior; protects against accidental over-refresh).
- entry_post error path for origin=hyp-recs returns the existing error response unchanged (no OOB swap of `#hypothesis-recommendations` on error — error path uses form re-render).

Plan defines the exact test names + the discriminating arithmetic.

### E. Test surface for R1 M2

Discriminating tests:
- The new shared helper returns the same value for both consumers under standard pipeline-bound state.
- Under tied `finished_ts` (two completed runs same second), helper returns the higher `id` deterministically.
- Under standalone-eval-only state, helper returns the standalone eval id (preserves fallback).
- `build_hyp_recs_section` and `build_dashboard` both consume the helper (assert via grep or import-path check OR via behavior-equivalence test).

### F. Discriminating-test discipline applied

Per the canonical compounding-confound failure modes:
- R1 M1 OOB swap test setup must use a hyp-recs ticker that's DIFFERENT from any default ticker the entry-form might emit on its OOB chunks (CC pivot bug's `entry_target=$24.13, candidates.pivot=$26.98` is a useful sentinel pair that survives across the test suite).
- R1 M2 helper test setup must construct distinct `finished_ts` values that exercise the deterministic-tiebreaker AND the fallback policies separately.

---

## §4 Plan acceptance criteria

The plan output (at `docs/superpowers/plans/2026-04-29-hyp-recs-success-path-fix-plan.md`) MUST satisfy:

1. **Per-task TDD discipline.** Each task: failing test first → minimal implementation → passing test → commit.
2. **Discriminating-test discipline.** Per §3.F above + the canonical compounding-confound discipline. Each task with a discriminating test includes a "would this test fail if the implementation never actually called the new code?" sanity-check sentence in the task body.
3. **Sequential single-subagent execution.** Plan tasks are SEQUENTIAL; no parallel-subagent collision risk.
4. **Observable-verification subject-only grep pattern** per binding conventions. Each task includes the `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task <N>'` step in body. Cross-plan grep aliasing is expected (per the sector dispatch lesson + the just-shipped hyp-recs executing-plans).
5. **4-tier commit-message convention** — flat `Task N` numbering per chart-scope-policy-v2 + sector capture + just-shipped hyp-recs precedent.
6. **R1 M2 helper extraction is the FIRST plan task** — it's a structural change others may consume; lands first to allow R1 M1 task to use the new helper if needed for the OOB-section build.
7. **R1 M1 fix tasks** come second. Likely 1-2 tasks (one for the entry_post change, one for tests if not bundled with TDD red-green).
8. **Test count baseline pinned at plan-time:** plan should note the current fast-test count (`python -m pytest -m "not slow" -q`). Just-shipped baseline was 1294; this dispatch starts from there or HEAD at plan-authoring time.
9. **Plan passes copowers:writing-plans Codex review cycle:** iterate to `NO_NEW_CRITICAL_MAJOR`. Major findings RESOLVED-by-fix; ACCEPTED-with-rationale only if genuinely out-of-scope.

---

## §5 Adversarial review watch items (for Codex during writing-plans cycle)

1. **HTMX OOB-swap drift.** Per CLAUDE.md gotcha. The R1 M1 fix's OOB swap of `#hypothesis-recommendations` MUST render content via the same `{% include %}` chain that `/hyp-recs/refresh` and the full-page render use. Plan task body must specify reuse of `build_hyp_recs_section` (NOT hand-duplicated markup).

2. **R1 M2 helper signature consistency across consumers.** Both `build_hyp_recs_section` and `build_dashboard` consume the helper. If the helper returns different shapes (pipeline_run_id vs evaluation_run_id), the consumers must adapt cleanly. Plan task body must specify the signature + the per-consumer adaptation.

3. **Standalone-eval fallback regression risk.** If the new shared helper drops the 2-step fallback that `latest_evaluation_run_id` has, the dashboard breaks under standalone-eval-only state. Plan task body must explicitly specify the fallback policy + a test that exercises it.

4. **id DESC tiebreaker introduction.** Adding the tiebreaker is a refinement; verify existing callers of `latest_evaluation_run_id` don't rely on the absence of `id DESC` for some load-bearing reason (extremely unlikely but verify).

5. **Discriminating-test setup for OOB-chunk-presence assertions.** Test must use a setup where the OOB swap of `#hypothesis-recommendations` would NOT fire under the bug (origin=hyp-recs entry_post pre-fix returns no such swap). Vacuous tests that pass under any entry_post response shape would be a discriminating-test failure.

6. **Cross-feature interaction surface (per Codex's contextual advantage lesson).** entry_post is invoked via multiple paths (watchlist Enter, hyp-recs Enter, hyp-recs expansion "Take this trade", URL ticker= param via direct navigation). The R1 M1 fix's `if origin == "hyp-recs"` branch must be exercised by tests for ALL hyp-recs-origin paths (per the multi-path-ingestion lesson, 2026-04-29). Plan tasks must cover each path OR explicitly accept coverage gap.

7. **Form-render context for the OOB chunk.** When entry_post builds the OOB `#hypothesis-recommendations` chunk, what state does it use? Post-trade state (the just-traded ticker is now in `trades` table) means the rebuild excludes that ticker. Verify by inspecting the recommendation logic; plan task body specifies the rebuild ordering (write trade first, then rebuild section).

8. **Anchor-consistency post-refactor.** Once the shared helper lands, `build_hyp_recs_section` and `build_dashboard` should produce identical anchor values for hyp-recs origin under all states. Plan task body specifies a behavior-equivalence test.

---

## §6 Done criteria

- Plan committed to `docs/superpowers/plans/2026-04-29-hyp-recs-success-path-fix-plan.md`.
- Plan passes `copowers:writing-plans` Codex review cycle, terminating at `NO_NEW_CRITICAL_MAJOR` (with verification round if final round produced findings).
- All Major findings RESOLVED-by-fix; ACCEPTED-with-rationale only if genuinely out-of-scope.
- Test count baseline pinned in plan body.
- Per-task observable-verification step included in each task body.
- Per-task discriminating-test sanity-check sentence included where applicable.

---

## §7 Return report format

Post as final message:

```
## Hyp-recs Success-Path Fix Plan — Writing-Plans Return Report

**Plan committed at:** docs/superpowers/plans/2026-04-29-hyp-recs-success-path-fix-plan.md (commit <SHA>)
**Codex rounds:** N rounds, terminating at NO_NEW_CRITICAL_MAJOR
**Test baseline pinned:** <count> fast tests at HEAD <SHA>
**Plan task count:** <N tasks> (typical 3-5)

**Codex findings dispositioned:**
- R1: <count> Critical, <count> Major, <count> Minor — <breakdown>
- R2: ...
... (per round)

**Major design choices made:**
- Helper name + signature (Q-A): <answer>
- id DESC tiebreaker policy (Q-B): <answer>
- Standalone-eval fallback policy (Q-C): <answer>

**Open questions for orchestrator triage:**
- <any items the implementer flagged as needing operator/orchestrator decision before executing-plans dispatch>

**Recommended next dispatch:** copowers:executing-plans on this plan.
```

---

## §8 If you get stuck

- **If a locked decision (§2) appears impossible to plan as written:** STOP, surface in return report. Do NOT silently re-design.
- **If a precedent file path doesn't resolve:** Use `Glob` / `Grep` to find the actual current path. The just-shipped chain ended at HEAD `a29a592`; file paths should be stable but verify if any task seems off.
- **If Codex round count exceeds 5 without convergence:** STOP, surface in return report with the unresolved finding. Do NOT iterate indefinitely. **However:** if the FINAL round produced findings that all resolved, run ONE additional verification round to confirm clean before terminating (per the chart-pattern flag-v1 Phase 7 induced-bug pattern + 2026-04-29 hyp-recs writing-plans MAX_ROUNDS-vs-NO_NEW_CRITICAL_MAJOR lesson).
- **If a fix surfaces an UNANTICIPATED bug:** SURFACE in return report; do NOT inline-add a third fix to this dispatch's scope. Per orchestrator-context anti-pattern: "Mid-session scope expansion."

---

## Appendix A: Cross-references

- **Just-shipped plan:** `docs/superpowers/plans/2026-04-29-hyp-recs-trade-prep-expansion-plan.md` (commit `3dcb8db` at writing-plans phase; 18 commit chain `5bd496d → a29a592` at executing-plans phase).
- **Just-shipped spec:** `docs/superpowers/specs/2026-04-29-hyp-recs-trade-prep-expansion-design.md`.
- **Executing-plans return report:** in conversation history; full bug symptoms, file paths, and recommended fix shape for both R1 M1 and R1 M2.
- **Bug 7 mixed-anchor family precedent:** orchestrator-context "Recent decisions and framings" 2026-04-25 — closure was scoped to `MAX(run_ts) FROM evaluation_runs` grep; the inline `pipeline_runs` query in `build_hyp_recs_section` is the same family in a new surface.
- **Spec/plan-silence-on-success-path lesson:** orchestrator-context "Lessons captured" — just-captured 2026-04-29; this dispatch closes the gap that surfaced the lesson.
- **HTMX OOB-swap partial drift:** CLAUDE.md gotchas — load-bearing for the R1 M1 fix.
- **Hypothesis-recommendation engine framing:** orchestrator-context "Recent decisions and framings" 2026-04-25 — "dashboard PROPOSES, operator DISPOSES." Drives the success-path response design.
