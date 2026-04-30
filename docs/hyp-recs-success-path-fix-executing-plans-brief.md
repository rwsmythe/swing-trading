# Hyp-recs Success-Path Coherence + Anchor-Divergence Fix — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute the implementation plan at `docs/superpowers/plans/2026-04-29-hyp-recs-success-path-fix-plan.md` (commit `844ed46`; 4 Codex rounds; terminating clean R4 NO_NEW_CRITICAL_MAJOR with verification-round confirmation). Ship the bundled fix for Codex R1 Majors 1+2 from the just-shipped hyp-recs trade-prep expansion executing-plans dispatch.

**Two fixes bundled (per the plan):**
1. **R1 Major 1 (PRODUCTION-BLOCKING):** hyp-recs success-path coherence via option (a) symmetric OOB-refresh approach. entry_post adds OOB swap of `#hypothesis-recommendations` when origin=hyp-recs.
2. **R1 Major 2:** anchor divergence — refactor `build_hyp_recs_section` to consume the existing `latest_evaluation_run_id` helper (no new helper introduced); helper gains `id DESC` tiebreaker on BOTH branches (per Codex R2 Major 1 escalation during writing-plans).

**Expected duration:** 5 tasks + 2-3 Codex rounds via `copowers:executing-plans` wrapper = ~3-5 hours of work, parallelizable to operator pacing.

**Dispatch type:** `copowers:executing-plans` (wraps `superpowers:subagent-driven-development` with adversarial Codex review post-execution). Single-subagent dispatch.

**Pre-vetted depth:** the plan went through 4 Codex rounds at writing-plans phase (R4 clean). Plan-rigor compounds — executing-plans Codex rounds should be modest (2-3 typical).

---

## §0 Read first

Read these in order before starting Task 1:

1. **The plan:** `docs/superpowers/plans/2026-04-29-hyp-recs-success-path-fix-plan.md` (commit `844ed46`) — THE CANONICAL SCOPE. Read all of it before invoking the executing-plans skill. The plan was authored via `copowers:writing-plans` (4 Codex rounds, terminating clean R4 NO_NEW_CRITICAL_MAJOR); it supersedes the writing-plans brief in case of any divergence.

2. **The just-shipped hyp-recs trade-prep expansion plan** at `docs/superpowers/plans/2026-04-29-hyp-recs-trade-prep-expansion-plan.md` — context for the parent dispatch this fix follows.

3. **The just-shipped hyp-recs trade-prep expansion spec** at `docs/superpowers/specs/2026-04-29-hyp-recs-trade-prep-expansion-design.md` — design context.

4. **`docs/hyp-recs-success-path-fix-writing-plans-brief.md`** — historical reference for plan-authoring decision context.

5. **`CLAUDE.md`** — project conventions, gotchas, invariants. Note especially:
   - **HTMX OOB-swap partial drift gotcha** — load-bearing for the R1 M1 fix; entry_post's OOB swap of `#hypothesis-recommendations` MUST render content via the same `{% include %}` chain that the canonical render path (`build_hyp_recs_section` consumed by full-page dashboard render and `/hyp-recs/refresh`) uses. Hand-duplicated markup is the failure mode.
   - Test-count drift gotcha (trust pytest output, not plan-pinned counts).

6. **`docs/orchestrator-context.md`** — read these sections in full:
   - §"Currently in-flight work" — current state at HEAD; this dispatch closes the production-blocking gap from the just-shipped Phase 2 hyp-recs trade-prep expansion.
   - §"Binding conventions" — 4-tier commit-message convention; observable-verification grep ERE form; ruff baseline 91; no-amend rule; no Claude footer.
   - §"Anti-patterns" — particularly mid-session scope expansion; vacuous regression tests.
   - §"Lessons captured" — read entire section. Particularly relevant:
     - **Spec/plan silence on form-driven success-path response shape is a recurrent failure class** (just-captured 2026-04-29; this dispatch closes the gap).
     - **HTMX OOB-swap partial drift** (CLAUDE.md gotcha; load-bearing).
     - **Bug 7 mixed-anchor family** (durably-closed-then-resurfaced; this dispatch durably closes again via shared helper).
     - **Multi-path-ingestion** (2026-04-29; the entry_post handler serves multiple origins; OOB swap behavior must be discriminated by origin).
     - Discriminating-test discipline; compounding-confound class.

7. **`docs/phase3e-todo.md`** §"2026-04-28 hyp-recs trade-preparation expansion" — backlog context.

If any file path doesn't resolve, surface in return report — do NOT silently proceed against a stale path.

---

## §0 Skill posture

- **INVOKE** `copowers:executing-plans` — wraps `superpowers:subagent-driven-development` with adversarial Codex review post-execution.
- **DO NOT INVOKE** `superpowers:brainstorming`, `copowers:brainstorming`, `superpowers:writing-plans`, or `copowers:writing-plans`. The plan is locked. Re-litigation is out of scope. If a plan task appears impossible to implement as written, STOP and surface in return report via §8 escape hatch; do NOT silently re-design.
- **DO** invoke adversarial Codex review per `copowers:executing-plans` standard cycle. Iterate to `NO_NEW_CRITICAL_MAJOR`. Round budget: ~2-3 typical (plan went through 4 writing-plans rounds; structural issues already caught). **Per the chart-pattern flag-v1 Phase 7 induced-bug pattern + 2026-04-29 hyp-recs writing-plans MAX_ROUNDS lesson:** if the final round produces findings that resolve, run ONE additional verification round to confirm clean before terminating; do NOT stop at MAX_ROUNDS with active findings.
- **Single-subagent dispatch** per the 10-phase ZERO-rogue track record. NO parallel-subagent dispatch at the task level. Subagent role-partitioning WITHIN a task (implementer + internal-code-reviewer + internal-Codex-fix-implementer) is collision-safe.

---

## §1 Strategic context

**This dispatch unblocks Phase 2 production verification.** The just-shipped hyp-recs trade-prep expansion (commits `5bd496d → a29a592`, 18 commits) has broken happy-path UX: operator's first "Take this trade" or per-row "Enter" submit produces an open-positions row inside the hyp-recs `<tbody>` (visually broken) AND the just-traded ticker stays in recommendations panel until next pipeline run. **Phase 3 of the operator sequence (OHLCV archive consolidation) is held until this fix lands AND production verification of Phase 2 succeeds.**

**Sequencing.** Sector capture (Phase 1, shipped 2026-04-29) → hyp-recs trade-prep expansion (Phase 2 main, shipped 2026-04-29) → **hyp-recs success-path fix (this dispatch; Phase 2 cleanup)** → Phase 2 production verification → Phase 3 (OHLCV archive consolidation).

---

## §2 V1 Scope (per plan; LOCKED)

**The plan IS the canonical scope source-of-truth.** Plan §"V1 Scope" + §"Tasks" enumerate the work. Execute as written.

**5 plan tasks per plan:**
1. **Task 1 (R1 M2):** `latest_evaluation_run_id` gains `id DESC` tiebreaker on BOTH branches (pipeline-bound + standalone-eval fallback). Tests for deterministic resolution under tied `finished_ts` AND tied `run_ts`.
2. **Task 2 (R1 M2):** `build_hyp_recs_section` consumes `latest_evaluation_run_id` (refactor from inline query to helper). Tests for behavior-equivalence under standard pipeline-bound state + the previously-failing standalone-eval-only state.
3. **Task 3 (R1 M1 enabling):** `build_hyp_recs_section` gains `exclude_tickers: set[str] | None = None` kwarg. Tests for kwarg threading + post-write state semantics (excluding the just-traded ticker from rebuild).
4. **Task 4 (R1 M1 enabling):** any additional plumbing the plan specifies for entry_post integration (e.g., shared helper for building the OOB chunk; verify against plan).
5. **Task 5 (R1 M1 integration):** entry_post for origin=hyp-recs returns OOB swap of `#hypothesis-recommendations` alongside existing OOB swaps (`#status-strip`, `#watchlist-top5`). Tests for OOB-chunk presence by origin (discriminating: hyp-recs origin includes the OOB; non-hyp-recs origin does NOT). Manual smoke step in plan body.

Task ordering: structural changes first (Task 1+2), then enabling refactors (Task 3+4), then integration (Task 5). Plan justifies the ordering.

---

## §3 Binding conventions (excerpts; full per orchestrator-context.md)

NON-NEGOTIABLE across all task implementations:

1. **Branch:** `main`. No feature branches. No `--no-verify`. No amending; create new commits to fix.
2. **No Claude co-author footer.** Plain conventional-commits messages only.
3. **4-tier commit-message convention** (per orchestrator-context Binding conventions):
   - Task implementation: `feat(area): Task N — <description>` (flat numbering per chart-scope-policy-v2 + sector capture + hyp-recs trade-prep expansion precedent).
   - Codex review-fix: `fix(area): Codex R<round> Major <id> — <description>`.
   - Internal-Codex within-task: append `(internal)` qualifier.
   - Internal code-review: `fix(area): code-review I<id> — <description>`.
   - Format-only cleanup: no task ID required.
4. **Observable-verification subject-only grep BEFORE each task implementation commit:**
   ```
   git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task <N>'
   ```
   ERE flag REQUIRED; POSIX `[0-9]` for digit class. **Cross-plan grep aliasing** is expected — grep output may include commits from prior plans (chart-scope-policy-v2 Tasks 1-10; sector capture Tasks 1-9; hyp-recs trade-prep expansion Tasks 1-9). Disambiguate within THIS dispatch's chain by commit subject; note cross-plan aliasing in return report.
5. **TDD discipline (per task):** failing test first → minimal implementation → passing test → commit. One red-green cycle per logical change.
6. **Discriminating-test discipline (HARD requirement per plan task bodies):**
   - **Task 1 (id DESC):** test setup must construct two completed pipeline_runs with identical `finished_ts` and DIFFERENT `id` values; assertion verifies the helper returns the higher `id`. Vacuous test that passes regardless of `id` values would be a discriminating-test failure.
   - **Task 2 (consumer refactor):** behavior-equivalence test must use a state where the OLD inline query and the NEW helper-routed query would have BOTH returned the same answer (sanity check), AND a separate test where the OLD query would have returned NULL (standalone-eval-only state) but the NEW helper-routed query returns the standalone eval id (the actual bug fix discriminator).
   - **Task 3 (exclude_tickers):** test setup must construct a hyp-recs candidate set INCLUDING a ticker, then call `build_hyp_recs_section(..., exclude_tickers={ticker})` and assert the returned section EXCLUDES it. Sentinel ticker MUST NOT match any default test-helper ticker (per the canonical compounding-confound failure modes).
   - **Task 5 (OOB swap):** test for hyp-recs origin entry_post success asserts presence of `<div id="hypothesis-recommendations" hx-swap-oob="...">` (or equivalent structural marker) in response body. Test for non-hyp-recs origin asserts ABSENCE — discriminating: vacuous test that passes regardless of origin would mask the bug.
7. **Ruff baseline 91 errors** (pre-existing in legacy code). Tasks must NOT introduce new violations; do NOT incidentally fix the baseline.
8. **Test discipline:** `python -m pytest -m "not slow" -q` is the fast suite; must stay green throughout. Slow suite is not required.

---

## §4 Adversarial review watch items (for Codex during executing-plans cycle)

These are the high-likelihood failure modes Codex should specifically check post-execution. Pre-empt by self-checking BEFORE each task commit:

1. **HTMX OOB-swap partial drift on Task 5.** Per CLAUDE.md gotcha + plan §"OOB swap rendering". The OOB chunk for `#hypothesis-recommendations` MUST render via `build_hyp_recs_section` (the canonical builder); hand-duplicated markup is the failure mode. Discriminating test must catch drift if the OOB chunk and `/hyp-recs/refresh` route diverge.

2. **`exclude_tickers` kwarg correctness in Task 5 integration.** Per plan + writing-plans phase implementer's catch — without `exclude_tickers={just_traded_ticker}` in the entry_post OOB rebuild call, the just-traded ticker would still appear in the freshly-rendered hyp-recs section (because `match_candidate_to_hypotheses` operates on Candidate rows, not on trade state). Verify the entry_post integration call passes the kwarg correctly.

3. **Multi-origin entry_post coverage** per plan + multi-path-ingestion lesson. Test for hyp-recs origin: OOB swap present. Test for watchlist origin: OOB swap absent (preserves current behavior). Test for URL-direct-entry origin (defaults watchlist; per the writing-plans forward-looking flag): OOB swap absent. Each origin path covered.

4. **id DESC tiebreaker on BOTH branches** (Task 1). Per Codex R2 Major 1 escalation during writing-plans. The pipeline-bound branch AND the standalone-eval fallback branch must BOTH have deterministic ordering. Test setups must construct tied states for BOTH branches separately.

5. **Behavior-equivalence regression** (Task 2). The helper-consumer refactor must produce identical anchor values to the inline query under standard pipeline-bound state. Discriminating test asserts equivalence under multiple state shapes.

6. **Standalone-eval-only state coverage** (Task 2). The bug fix discriminator: `/hyp-recs/refresh` was returning empty under standalone-eval-only state. Test must construct that state and assert the NEW behavior (helper-routed) returns the standalone eval id, NOT NULL.

7. **Form-render context for the OOB chunk.** When entry_post builds the OOB `#hypothesis-recommendations` chunk, the rebuild must use post-write state (the just-traded ticker is now in `trades` table). Verify ordering: write trade FIRST, then rebuild section. If the rebuild happens before the trade insert, the just-traded ticker is still in the candidate set without being filtered by `exclude_tickers`.

8. **Cross-plan grep aliasing** per binding conventions. Disambiguate within THIS dispatch's chain by commit subject; note in return report.

9. **Task 5 manual smoke step** (per plan §"Manual smoke"). Implementer must execute the smoke step + report observed behavior in return report. If smoke fails, surface immediately; do NOT proceed to Codex review until smoke passes.

10. **URL direct-entry surface forward-flag** (per writing-plans return §"Forward-looking flag"). The URL `/trades/entry/form?ticker=...` defaults origin="watchlist"; OOB swap won't fire. Consistent with current behavior; structurally correct. Codex may flag this; respond ACCEPTED-with-rationale citing the writing-plans return forward-flag.

---

## §5 Done criteria

- All 5 plan tasks complete.
- Each task implementation commit follows the 4-tier convention with observable-verification grep output in commit body.
- Final fast-test count documented and reconciled against plan's projection (test baseline pinned at HEAD `3c43757` was 1294 fast tests).
- Adversarial Codex review reaches `NO_NEW_CRITICAL_MAJOR` with verification round if final round produced findings.
- All commits pushed to `origin/main`.
- Manual smoke step (Task 5) executed and observed behavior reported in return report.
- Operator-runnable: hyp-recs success-path fix verifiable via:
  1. `swing pipeline run` → hyp-recs panel populated.
  2. Click "Take this trade" or per-row "Enter" on a hyp-rec row → form replaces row.
  3. Submit form → open-positions row appears in open-positions table; hyp-recs panel refreshes (just-traded ticker removed); no visual breakage.
- Return report posted per §6.

---

## §6 Return report format

Post as final message:

```
## Hyp-recs Success-Path Fix — Executing-Plans Return Report

**Plan executed:** docs/superpowers/plans/2026-04-29-hyp-recs-success-path-fix-plan.md (commit 844ed46)
**Commit chain:** <first SHA> → <last SHA> on origin/main
**Total commits:** N (M task implementations + K review-fix commits + L cleanup)
**Codex rounds:** N rounds, terminating at NO_NEW_CRITICAL_MAJOR (with verification round if applicable)
**Fast-test count:** <count> at HEAD <SHA> (delta: +N from baseline 1294)

**Tasks completed:**
1. Task 1 — id DESC tiebreaker on latest_evaluation_run_id (commit <SHA>)
2. Task 2 — build_hyp_recs_section consumes latest_evaluation_run_id (commit <SHA>)
3. Task 3 — exclude_tickers kwarg on build_hyp_recs_section (commit <SHA>)
4. Task 4 — <whatever Task 4 specifies in plan> (commit <SHA>)
5. Task 5 — entry_post OOB swap for hyp-recs origin (commit <SHA>)

**Codex findings dispositioned:**
- R1: <count> Critical, <count> Major, <count> Minor — <breakdown>
- R2: ...
... (per round)

**Manual smoke (Task 5):**
- <observed behavior in plan §"Manual smoke" step; PASS or FAIL with details>

**Forward-looking flag from writing-plans (per Appendix B):**
- URL direct-entry surface origin=watchlist default: held / surfaced if violated.
- Cross-plan grep aliasing: noted per task X.

**Operator-action items:**
- Phase 2 production verification (deferred until this fix landed):
  1. Restart `swing web`.
  2. Run `swing pipeline run`.
  3. Click "Take this trade" or per-row "Enter" on a hyp-rec row.
  4. Submit form; verify open-positions row appears in open-positions table; hyp-recs panel refreshes (just-traded ticker removed); no visual breakage.
  5. Verify watchlist Pivot column renders candidates.pivot value (CC pivot bug fix).
  6. Verify origin survival on validation error (submit with bad rationale; form re-renders with hyp-recs colspan + Cancel target).

**Open questions for orchestrator triage:**
- <any items the implementer flagged as needing operator/orchestrator decision>

**Recommended next dispatch:** Phase 3 of operator sequence — OHLCV archive consolidation brainstorm or writing-plans (operator's call on whether to brainstorm).
```

---

## §7 If you get stuck

- **If a plan task appears impossible to implement as written:** STOP, surface in return report. Do NOT silently re-design.
- **If a precedent file path doesn't resolve:** Use `Glob` / `Grep` to find the actual current path. Plan was authored at HEAD `3c43757`; the just-shipped hyp-recs trade-prep expansion chain ended at `a29a592`. File paths should be stable but verify if any task seems off.
- **If Codex round count exceeds 5 without convergence:** STOP, surface in return report with the unresolved finding. Do NOT iterate indefinitely.
- **If the final Codex round produces findings that resolve:** run ONE verification round to confirm clean before terminating. Do NOT stop at MAX_ROUNDS with active findings (per the chart-pattern flag-v1 Phase 7 induced-bug pattern lesson).
- **If discriminating-test sanity check reveals vacuousness:** STOP, restructure the test setup to invert the symmetry per Phase 4 lesson, then resume.
- **If you find a scope-deviation opportunity:** SURFACE in return report as a follow-up; do NOT in-line-implement. Per orchestrator-context anti-pattern: "Mid-session scope expansion." (One exception: if the deviation is required to make a plan task actually work — e.g., the writing-plans phase's `exclude_tickers` kwarg catch — surface AND implement minimally; this dispatch's plan should already address such cases.)
- **If Task 5 manual smoke FAILS:** STOP, surface in return report with details. Do NOT proceed to Codex review until smoke passes.

---

## Appendix A: Plan-history awareness

The plan went through 4 writing-plans Codex rounds before this dispatch. Major findings already addressed:

- R1: 2 Major + 2 Minor — all RESOLVED (post-write-state discriminator + shared-anchor test + empty-state UX policy + URL ticker= smoke).
- R2: 2 Major + 1 Minor — all RESOLVED (id DESC on fallback branch + structural-guard pytest + hidden attribute on empty oob).
- R3: 2 Major + 1 Minor — all RESOLVED (pytest port of structural guard + transition test + class-drop rationale).
- R4: 0 Critical / 0 Major / 0 Minor — clean termination.

Plan-history is durable in `docs/superpowers/plans/2026-04-29-hyp-recs-success-path-fix-plan.md` commit chain (`40c7181 → 57ce65c → 6a633d2 → 844ed46`). Implementer should NOT re-iterate on resolved findings; if a Codex round in THIS dispatch raises a finding that already has a plan-history fix, cite the plan + the fix commit, then proceed.

---

## Appendix B: Forward-looking flag from writing-plans return

**URL `/trades/entry/form?ticker=...` direct-entry surface defaults origin="watchlist".** If operators ever land on hyp-recs tickers via this URL (bookmarked deeplinks), the OOB hyp-recs refresh won't fire. Consistent with current behavior and structurally correct (the URL has no hyp-recs context). **NOT a blocker for this dispatch.** Codex may flag; respond ACCEPTED-with-rationale citing this Appendix.

If operator workflow later exposes the gap (operator reports landing on hyp-recs tickers via direct URL surface), surface in noise queue as a follow-up.

---

## Appendix C: Cross-references

- **Plan:** `docs/superpowers/plans/2026-04-29-hyp-recs-success-path-fix-plan.md` (commit `844ed46`; 4 Codex rounds).
- **Writing-plans brief:** `docs/hyp-recs-success-path-fix-writing-plans-brief.md`.
- **Just-shipped Phase 2 plan:** `docs/superpowers/plans/2026-04-29-hyp-recs-trade-prep-expansion-plan.md` (commit `3dcb8db`; 18-commit chain `5bd496d → a29a592` at executing-plans).
- **Just-shipped Phase 2 spec:** `docs/superpowers/specs/2026-04-29-hyp-recs-trade-prep-expansion-design.md` (1,158 lines; 5 brainstorm Codex rounds).
- **Spec/plan-silence-on-success-path lesson:** orchestrator-context "Lessons captured" (just-captured 2026-04-29; this dispatch closes the gap).
- **HTMX OOB-swap partial drift:** CLAUDE.md gotchas — load-bearing for Task 5.
- **Bug 7 mixed-anchor family:** orchestrator-context "Recent decisions and framings" 2026-04-25 — durably-closed-then-resurfaced; this dispatch durably closes again via shared helper.
- **Multi-path-ingestion lesson:** orchestrator-context "Lessons captured" 2026-04-29 — applies to multi-origin entry_post coverage.
- **Hypothesis-recommendation engine framing:** orchestrator-context "Recent decisions and framings" 2026-04-25 — "dashboard PROPOSES, operator DISPOSES."
