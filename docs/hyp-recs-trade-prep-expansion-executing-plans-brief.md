# Hyp-recs Trade-Prep Expansion — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute the implementation plan at `docs/superpowers/plans/2026-04-29-hyp-recs-trade-prep-expansion-plan.md` (commit `3dcb8db`; 8 Codex rounds; terminating `NO_NEW_CRITICAL_MAJOR`). Ship V1 of the hyp-recs trade-prep expansion via 9 top-level tasks (15 atomic units; sub-tasks 5.1-5.7 inside Task 5). The plan IS the spec; this dispatch is plan-faithful execution.

**Expected duration:** 9 top-level tasks (15 atomic) + 2-4 Codex rounds via `copowers:executing-plans` wrapper = ~10-15 hours of work, parallelizable to operator pacing.

**Dispatch type:** `copowers:executing-plans` (wraps `superpowers:subagent-driven-development` with adversarial Codex review post-execution). Single-subagent dispatch.

**Pre-vetted depth:** the plan went through 8 Codex rounds at writing-plans phase (5 standard + 3 verification). Plan-rigor compounds — executing-plans Codex rounds should be modest (2-4 typical).

---

## §0 Read first

Read these in order before starting Task 1:

1. **The plan:** `docs/superpowers/plans/2026-04-29-hyp-recs-trade-prep-expansion-plan.md` — THE CANONICAL SCOPE. Read all of it before invoking the executing-plans skill. The plan was authored via `copowers:writing-plans` (8 Codex rounds, terminating `NO_NEW_CRITICAL_MAJOR`); it supersedes the writing-plans brief in case of any divergence.

2. **The spec:** `docs/superpowers/specs/2026-04-29-hyp-recs-trade-prep-expansion-design.md` (1,158 lines; 5 brainstorm Codex rounds). The plan implements the spec; reference the spec when a plan task body is terse. The spec's §7.1 implementation sequencing was followed by the plan with one documented Task 3↔4 swap.

3. **`docs/hyp-recs-trade-prep-expansion-writing-plans-brief.md`** — historical reference for plan-authoring decision context. Plan §"Goal" + per-task bodies supersede where they differ.

4. **`CLAUDE.md`** — project conventions, gotchas, invariants. Note especially:
   - Test-count drift gotcha (trust pytest output, not plan-pinned counts).
   - HTMX OOB-swap partial drift gotcha — apply to `/hyp-recs/refresh` route per plan tasks; `build_hyp_recs_section` MUST produce content via the same `{% include %}` chain as the full-page dashboard render. Hand-duplicated markup is the failure mode.
   - Base-layout 5-VM rule — verify each VM modification against `base.html.j2` references; plan should NOT blanket-require all 5 VMs to gain new fields if `base.html.j2` doesn't dereference them.
   - Manual visual verification is required for rendering work — applies to the new chevron-button + expansion partial; PNG-style visual is not relevant here, but operator-witnessed verification of the rendered HTML is the final acceptance gate.

5. **`docs/orchestrator-context.md`** — read these sections in full:
   - §"Currently in-flight work" — current state at HEAD; sector dispatch (Phase 1) shipped 2026-04-29; this dispatch is Phase 2.
   - §"Binding conventions" — 4-tier commit-message convention; observable-verification grep ERE form; ruff baseline 91; no-amend rule; no Claude co-author footer; subject-only grep regex with `-E` flag and POSIX `[0-9]` digit class.
   - §"Anti-patterns to avoid" — vacuous regression tests; mid-session scope expansion; brief drafting drift; bug-fix investigation that tests plausible mechanisms instead of operator's actual reproduction.
   - §"Lessons captured" — read entire section. Multiple lessons apply; particularly:
     - Discriminating-test discipline (Phase 4 + chart-scope-policy-v2 + chart-pattern flag-v1 Phase 6 monkeypatch-capture failure).
     - Compounding-confound class.
     - Subsequent-phase tests can surface earlier-phase contract bugs (Phase 3 R3 Major 1).
     - ToCToU on form-driven workflows is easy to overlook when "centralizing" looks elegant (chart-pattern brainstorm R3).
     - Codex's contextual advantage at finding cross-feature interactions (Phase 5 lesson — directly applicable to the multi-origin entry form).
     - Multi-path-ingestion (2026-04-29 — directly applicable to entry form serving multiple origins).
     - Snapshot-semantic claims at spec/plan time should explicitly address transaction isolation (chart-scope-policy-v2 R1 M1).
     - HTMX OOB-swap partial drift (CLAUDE.md gotcha).
     - Cross-plan grep aliasing (sector dispatch lesson).

6. **`docs/phase3e-todo.md`** §"2026-04-28 hyp-recs trade-preparation expansion" — backlog context. Plan implements this section + the Q7+Q8 brief addendum from 2026-04-29.

If any file path doesn't resolve, surface in return report — do NOT silently proceed against a stale path.

---

## §0 Skill posture

- **INVOKE** `copowers:executing-plans` — wraps `superpowers:subagent-driven-development` with adversarial Codex review post-execution. The wrapper skill handles the Codex cycle internally; do not invoke `copowers:adversarial-critic` separately.
- **DO NOT INVOKE** `superpowers:brainstorming`, `copowers:brainstorming`, `superpowers:writing-plans`, or `copowers:writing-plans`. The plan is locked. Re-litigation is out of scope. If a plan task appears impossible to implement as written, STOP and surface in return report via §8 escape hatch; do NOT silently re-design.
- **DO** invoke adversarial Codex review per `copowers:executing-plans` standard cycle. Iterate to `NO_NEW_CRITICAL_MAJOR`. Round budget: ~2-4 typical for a plan that already had 8 writing-plans Codex rounds. If Codex round count exceeds 5 without convergence, surface in return report — do NOT iterate indefinitely.
- **Single-subagent dispatch** per the 9-phase ZERO-rogue track record (chart-pattern flag-v1 Phases 4-7 + Tier-1 mathtext + Tier-2 #2/#3 + chart-scope-policy-v2 writing-plans + chart-scope-policy-v2 executing-plans + sector capture executing-plans). NO parallel-subagent dispatch at the task level. Subagent role-partitioning WITHIN a task (implementer + internal-code-reviewer + internal-Codex-fix-implementer) is collision-safe per the chart-pattern Phase 6 lesson; only task-level partitioning is the binding constraint.

---

## §1 Strategic context

**This dispatch ships hyp-recs trade-prep expansion + per-row Enter button + expansion-internal "Take this trade" button + bundled CC pivot bug fix.** Operator has been waiting for this since the 2026-04-28 brief drafting; sector capture (Phase 1, shipped 2026-04-29) provides the captured `Candidate.sector` / `.industry` fields that the expansion's Context group consumes without any data-plumbing rework.

**Operator's pure-trigger discipline** (2026-04-28): pure-trigger conditional on price being inside the buy window — formal version of "wait for pivot, don't chase >1% above pivot" entry discipline (2026-04-25). The expansion makes "in-window?" check at-a-glance rather than ad-hoc external lookup.

**Sequencing context.** Phase 2 of a 6-phase post-2026-04-28 sequence. Phase 3 (OHLCV archive) follows; configuration page (Phase 5) consumes the `chase_factor` config field introduced by this dispatch.

**Bundled bug fix.** CC pivot bug fix at THREE render sites (`watchlist_top5_section.html.j2`, `watchlist.html.j2`, `WatchlistRowVM.current_pivot` for `/watchlist/{ticker}/row` close-path). Cross-surface consistency on what "Pivot" means becomes part of this dispatch's done-criteria.

---

## §2 V1 Scope (per plan; LOCKED)

**The plan IS the canonical scope source-of-truth.** Plan §"V1 Scope" + §"File Map" + §"Implementation Sequencing" enumerate the work. Execute as written.

**File map: 22 files total** per spec §"File Map":
- 4 production NEW
- 12 production MODIFY
- 6 test NEW
- No migrations.
- No Phase 2 carve-outs (conditional — see §6 forward-looking flags).

**Implementation sequencing per plan (refines spec §7.1 with Task 3↔4 swap):**
1. Task 1: CC pivot wiring (foundational column-rendering at 3 sites).
2. Task 2: `chase_factor` config field (`Config.web.chase_factor: float = 0.01`).
3. Task 3: Extract `_build_active_recommendations` shared helper (BEFORE the refresh route consumes it).
4. Task 4: Hyp-recs expansion partial + `/hyp-recs/refresh` route + scoped `build_hyp_recs_section` builder.
5. Task 5 (sub-tasks 5.1-5.7): Per-row Enter button + expansion-internal "Take this trade" button + sort-neutrality regression + pinned-baseline capture (5.7 uses temporary git-worktree).
6. Task 6: Origin-aware entry form template parameterization (colspan + Cancel).
7. Task 7: `TradeEntryFormVM.origin` discriminator + hidden form field for POST round-trip survival.
8. Task 8: Anchor-consistency logic for hyp-recs origin (uses `latest_completed_pipeline_run` for ALL candidate-derived reads).
9. Task 9: Origin-aware off-watchlist candidate fallback for `entry_price` / `initial_stop`.

Per-task TDD discipline + observable-verification grep + 4-tier commit-message convention all binding per plan task bodies.

---

## §3 Binding conventions (excerpts; full per orchestrator-context.md)

NON-NEGOTIABLE across all task implementations:

1. **Branch:** `main`. No feature branches. No `--no-verify`. No amending; create new commits to fix.
2. **No Claude co-author footer.** Plain conventional-commits messages only.
3. **4-tier commit-message convention** (per orchestrator-context Binding conventions):
   - Task implementation: `feat(area): Task N — <description>` (flat numbering per chart-scope-policy-v2 + sector capture precedent)
   - Sub-task implementation: `feat(area): Task 5.X — <description>` (Task 5 only — has 7 sub-tasks)
   - Codex review-fix: `fix(area): Codex R<round> Major <id> — <description>`
   - Internal-Codex within-task: append `(internal)` qualifier — `fix(area): Codex R1 Major 1 (internal) — <description>`
   - Internal code-review: `fix(area): code-review I<id> — <description>`
   - Format-only cleanup: no task ID required
4. **Observable-verification subject-only grep BEFORE each task implementation commit:**
   ```
   git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task <N>'
   ```
   Note: `-E` flag is REQUIRED (BRE chokes on `+`); POSIX `[0-9]` for digit class if matching round IDs. **Cross-plan grep aliasing** is expected per the sector capture lesson — grep output may include commits from prior plans (chart-scope-policy-v2 Tasks 1-10; sector capture Tasks 1-9). Disambiguate within THIS dispatch's chain by commit subject; note the cross-plan aliasing in the return report. Plan §"Per-Task Observable-Verification Subject-Only Grep" specifies the exact regex per task.
5. **TDD discipline (per task):** failing test first → minimal implementation → passing test → commit. One red-green cycle per logical change.
6. **Discriminating-test discipline (HARD requirement per plan task bodies):**
   - **Action-button URL distinction:** per-row Enter URL = `/trades/entry?ticker=<X>&origin=hyp-recs-row` (or similar — verify plan §"Q-D resolution"); expansion-internal "Take this trade" URL = `/trades/entry?ticker=<X>&origin=hyp-recs-expansion`. Tests must use ticker setups that produce DIFFERENT URLs pre-fix and post-fix; vacuous tests that pass under any URL would be a discriminating-test failure.
   - **CC pivot three-site fix:** test setup must use a candidate where `entry_target ≠ candidates.pivot` so the test discriminates "rendered the right field" from "rendered either field." Per the plan, `entry_target=$24.13, candidates.pivot=$26.98` is the canonical sentinel pair (CC bug values from operator's screenshot).
   - **Origin-aware entry form:** tests for each origin (watchlist, hyp-recs-row, hyp-recs-expansion, URL-param) must use distinct origin values; assertions must assert on the specific origin value, NOT just "origin field is present."
   - **Sort-neutrality regression** (Task 5.6 or wherever the plan places it): test ordering with sentinel sector/industry values that vary across rows must NOT change the hyp-recs prioritized order.
7. **Ruff baseline 91 errors** (pre-existing in legacy code; documented in orchestrator-context Binding conventions). Tasks must NOT introduce new violations; do NOT incidentally fix the baseline.
8. **Test discipline:** `python -m pytest -m "not slow" -q` is the fast suite; must stay green throughout. Slow suite is not required for this dispatch.

---

## §4 Adversarial review watch items (for Codex during executing-plans cycle)

These are the high-likelihood failure modes Codex should specifically check post-execution. Pre-empt by self-checking BEFORE each task commit:

1. **Three-site CC pivot wiring completeness.** Per plan Task 1 + spec §"Q-G resolution". The third site (`WatchlistRowVM.current_pivot` for `/watchlist/{ticker}/row` close-path) is the easiest to miss. Verify all three render sites implement the fix; close-path test included.

2. **Origin-aware entry-form POST round-trip coverage.** Per plan Task 7 + spec §"R4-Major-1 resolution". Entry form serves multiple origins; the `origin` field must survive ALL POST-error paths (`_rerender_entry_form_with_error`, `DuplicateOpenPositionException`, `soft_warn_confirm`). Tests cover each round-trip path. Per the multi-path-ingestion lesson (2026-04-29), enumerate ALL origin paths.

3. **HTMX OOB-swap drift on `/hyp-recs/refresh`.** Per plan Task 4 + CLAUDE.md gotcha. The route renders content via the same `{% include %}` chain as the full-page dashboard render — `build_hyp_recs_section` is the shared callable. Discriminating test must catch drift if the route's output and the full-page render diverge.

4. **Action-button URL distinction in tests.** Per plan Task 5.X + §3 above. Per-row Enter button and expansion-internal "Take this trade" button must produce DIFFERENT rendered URLs (different `origin` query param). Tests must use ticker setups that exercise this distinction.

5. **Chevron-button HTMX trigger correctness.** Per plan Task 4 + spec §"Q-C resolution". Chevron BUTTON in column 1 is the HTMX trigger; `<tr>` is NOT. Test confirms clicking the chevron (NOT the row) triggers the expansion. Test setup must include row content OUTSIDE the chevron button; if clicking elsewhere triggers expansion, the trigger is mis-configured.

6. **Anchor-consistency for hyp-recs origin.** Per plan Task 8 + spec §"R4-Major-2 resolution". Uses `latest_completed_pipeline_run` for ALL candidate-derived reads when origin=hyp-recs. Verify the helper is called consistently across the entry-form VM build, candidate-row reads, and any joins.

7. **`chase_factor` toml-shadowing audit.** Per plan Task 2 + spec §"Q-F resolution" + 2026-04-28 `aeb2084` lesson. Task body MUST verify `grep -rn "chase_factor" .` returns zero hits in tracked toml files BEFORE the implementation commits.

8. **Sort-neutrality regression discipline.** Per plan Task 5.6 + chart-pattern flag-v1 R1 M2 lesson. Hyp-recs sort untouched (hypothesis-aware prioritizer; sector/industry/etc. NOT in sort tuple). Sort-neutrality test verifies the sort order is unchanged when new fields vary across rows.

9. **Task 5 transient state acceptance** (plan R1 Major 3). During intra-dispatch commits, Task 5 ships per-row Enter / Take-this-trade buttons emitting `?origin=hyp-recs` while form GET handler still defaults to watchlist origin until Tasks 6-9 land. **This is intentional + accepted-with-rationale per the plan.** Codex may flag as inconsistency; respond ACCEPTED-with-rationale citing plan §"R1 Major 3 acceptance" — transient state is invisible to operator runtime because the dispatch ships as a unit (no intermediate operator-pulled state between intra-dispatch commits).

10. **Sub-task 5.7 capture protocol (worktree usage).** Per plan Task 5.7 + spec §"R5 verification chain (R5→R6→R7→R8 induced-bug discovery)". Capture protocol uses temporary git-worktree at HEAD `a492b84`. If the executing-plans environment somehow blocks worktree creation, surface in return report — the plan's R6/R7/R8 verification rounds verified the protocol on standard Windows file system. Path portability + bootstrap + import-resolution gaps are all addressed in the plan; do NOT re-introduce.

---

## §5 Done criteria

- All 9 top-level plan tasks complete (15 atomic units; sub-tasks 5.1-5.7 within Task 5).
- Each task implementation commit follows the 4-tier convention with observable-verification grep output in commit body.
- Final fast-test count documented and reconciled against plan's projection (test baseline pinned at HEAD `a492b84` was 1228 fast tests; plan §"Test Count Projection" gives the expected post-dispatch number).
- Adversarial Codex review reaches `NO_NEW_CRITICAL_MAJOR`.
- All commits pushed to `origin/main`.
- Operator-runnable: `swing web` restarted + `swing pipeline run` produces hyp-recs panel showing the new chevron + Enter buttons; expansion renders the trade-prep snapshot; `/hyp-recs/refresh` works; CC pivot bug verified fixed by visual comparison.
- Return report posted per §6.

---

## §6 Return report format

Post as final message:

```
## Hyp-recs Trade-Prep Expansion — Executing-Plans Return Report

**Plan executed:** docs/superpowers/plans/2026-04-29-hyp-recs-trade-prep-expansion-plan.md (commit 3dcb8db)
**Commit chain:** <first SHA> → <last SHA> on origin/main
**Total commits:** N (M task implementations + K review-fix commits + L cleanup)
**Codex rounds:** N rounds, terminating at NO_NEW_CRITICAL_MAJOR
**Fast-test count:** <count> at HEAD <SHA> (delta: +N from baseline 1228)

**Tasks completed:**
1. <Task 1 summary + commit SHA>
2. <Task 2 summary + commit SHA>
... (per task; sub-tasks within Task 5 enumerated separately)

**Codex findings dispositioned:**
- R1: <count> Critical, <count> Major, <count> Minor — <breakdown>
- R2: ...
... (per round)

**Forward-looking flags from writing-plans return (per Appendix B):**
- R1 Major 3 transient state: held / surfaced if violated.
- Phase 2 carve-out conditional: not invoked / invoked with rationale: <X>.
- Sub-task 5.7 worktree protocol: succeeded / failed at: <X>.
- Cross-plan grep aliasing: noted per task X.Y.

**Operator-action items:**
- Restart `swing web`.
- Run `swing pipeline run`.
- Operator-witnessed verification of the hyp-recs panel:
  1. Chevron button in column 1; click expands the row to show snapshot.
  2. Per-row Enter button (column 9 or wherever plan puts it) navigates to /trades/entry with origin=hyp-recs-row.
  3. Expansion-internal "Take this trade" button (or whatever differentiated label) navigates with origin=hyp-recs-expansion.
  4. /hyp-recs/refresh button (if shipped) updates only the hyp-recs section.
  5. CC pivot bug verified fixed: watchlist Pivot column now renders candidates.pivot value (matches hyp-recs); collapsed and expanded watchlist row both show consistent value.

**Open questions for orchestrator triage:**
- <any items the implementer flagged as needing operator/orchestrator decision>

**Recommended next dispatch:** Phase 3 of operator sequence — OHLCV archive consolidation brainstorm or writing-plans (operator's call on whether to brainstorm).
```

---

## §7 If you get stuck

- **If a plan task appears impossible to implement as written:** STOP, surface in return report. Do NOT silently re-design.
- **If a precedent file path doesn't resolve:** Use `Glob` / `Grep` to find the actual current path. Plan was authored at HEAD `a492b84` which is recent — file paths should be stable but verify if any task seems off.
- **If Codex round count exceeds 5 without convergence:** STOP, surface in return report with the unresolved finding. Do NOT iterate indefinitely. Plan-rigor compounds; executing-plans rounds should be modest.
- **If discriminating-test sanity check reveals vacuousness on a primary-key assertion:** STOP, restructure the test setup to invert the symmetry per Phase 4 lesson, then resume.
- **If you find a scope-deviation opportunity** (e.g., a refactor that would make Task X cleaner but isn't in the plan): SURFACE in return report as a follow-up; do NOT in-line-implement. Per orchestrator-context anti-pattern: "Mid-session scope expansion."
- **If sub-task 5.7 worktree protocol fails:** the plan's R6/R7/R8 chain verified path portability + bootstrap + import-resolution; if a NEW environment-specific failure arises, surface immediately. Do NOT reintroduce the issues that R6-R8 already fixed.

---

## Appendix A: Plan-history awareness

The plan went through 8 writing-plans Codex rounds before this dispatch (5 standard + 3 verification). Major findings already addressed:

- R1: 4 Major + 2 Minor — 3M resolved (snapshot-purity, _ROW_TARGET_PREFIXES, watchlist /row close-path CC pivot, full-section refresh decision); 1M ACCEPTED (Task 5 transient state); 2m resolved.
- R2: 2 Major + 1 Minor — both M resolved (correct CC pivot wiring sites; scoped build_hyp_recs_section).
- R3: 2 Major + 1 Minor — both M resolved (origin-aware entry form parameterization; off-watchlist candidate fallback).
- R4: 2 Major + 0 Minor — both M resolved (origin survives POST round-trips; anchor consistency for hyp-recs origin).
- R5: 1 Major + 0 Minor — resolved (capture-then-write protocol via temporary worktree).
- R6 (verification): 2 Major — resolved (path portability + bootstrap gap induced by R5).
- R7 (verification): 1 Major — resolved (import-resolution gap induced by R6).
- R8 (verification): clean — NO_NEW_CRITICAL_MAJOR.

Plan-history is durable in `docs/superpowers/plans/2026-04-29-hyp-recs-trade-prep-expansion-plan.md` commit chain. Implementer should NOT re-iterate on resolved findings; if a Codex round in THIS dispatch raises a finding that already has a plan-history fix, cite the plan and the fix commit, then proceed.

---

## Appendix B: Forward-looking flags from writing-plans return report

These were surfaced by the writing-plans implementer for executing-plans awareness; they are NOT orchestrator-blocking but should be tracked in this dispatch's return report:

1. **R1 Major 3 acceptance (Task 5 transient state)** — orchestrator-validated; transient state is intra-dispatch-invisible to operator runtime. Hold; do NOT re-litigate.
2. **Test count drift gotcha** — standard discipline. Trust pytest output, not plan-pinned counts.
3. **Phase 2 carve-out conditional** — plan reuses existing `fetch_candidates_for_run` + in-Python ticker filter (typical 20-50 candidates; single-ticker lookup is fast). If executing-plans profiling shows slowness, may add `get_for_evaluation(conn, evaluation_run_id, ticker)` accessor at `swing/data/repos/candidates.py` as Phase 2 carve-out. Surface in return report if invoked.
4. **Sub-task 5.7 worktree protocol** — requires git-worktree access at HEAD `a492b84`. Standard worktree functionality on operator's Windows; if executing-plans environment somehow blocks, surface in return report. R6-R8 verified path portability + bootstrap + import-resolution on standard environment; do NOT re-introduce those issues.

---

## Appendix C: Cross-references

- **Plan:** `docs/superpowers/plans/2026-04-29-hyp-recs-trade-prep-expansion-plan.md` (commit `3dcb8db`; 8 Codex rounds; HEAD `a492b84` at writing-plans dispatch baseline).
- **Spec:** `docs/superpowers/specs/2026-04-29-hyp-recs-trade-prep-expansion-design.md` (1,158 lines; 5 brainstorm Codex rounds; HEAD `ade2b41` at brainstorming dispatch baseline).
- **Brainstorming brief:** `docs/hyp-recs-trade-prep-expansion-brainstorming-brief.md` (mid-dispatch updated to add Q7+Q8 at commit `427ef95`).
- **Writing-plans brief:** `docs/hyp-recs-trade-prep-expansion-writing-plans-brief.md`.
- **Phase 1 sector dispatch precedents:** plan `docs/superpowers/plans/2026-04-28-sector-industry-capture-plan.md`; executing-plans brief `docs/sector-industry-capture-executing-plans-brief.md` — the executing-plans brief structure mirrored here.
- **Operator decisions Q1-Q6 (2026-04-28):** `docs/phase3e-todo.md` §"2026-04-28 hyp-recs trade-preparation expansion" subsection "Locked decisions".
- **Operator decisions Q7+Q8 (2026-04-29):** brainstorming brief §2.
- **Capital risk floor convention:** project memory `project_capital_risk_floor.md`. Drives the dual-cost-display logic.
- **Hypothesis-recommendation engine framing (2026-04-25):** orchestrator-context — "dashboard PROPOSES, operator DISPOSES."
- **Multi-path-ingestion lesson (2026-04-29):** orchestrator-context "Lessons captured" — applies to multi-origin entry-form coverage requirement.
- **Cross-plan grep aliasing lesson** (sector capture writing-plans return): expected; disambiguate within THIS dispatch's chain.
