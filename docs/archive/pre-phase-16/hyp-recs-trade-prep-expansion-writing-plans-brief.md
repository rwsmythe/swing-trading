# Hyp-recs Trade-Prep Expansion — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Author an implementation plan for the hyp-recs trade-prep expansion via `copowers:writing-plans`. The spec at `docs/superpowers/specs/2026-04-29-hyp-recs-trade-prep-expansion-design.md` (1,158 lines, 5 Codex rounds, terminating `NO_NEW_CRITICAL_MAJOR`) is the canonical scope source-of-truth. This dispatch consumes the spec and produces a plan ready for `copowers:executing-plans` dispatch.

**Expected duration:** ~30-45 min spec reading + ~1-2 hr plan-authoring + 3-5 Codex rounds via the `copowers:writing-plans` wrapper = ~5-7 hours total.

**Dispatch type:** `copowers:writing-plans` (NOT brainstorming, NOT executing-plans).

---

## §0 Read first

Read these in order before invoking the writing-plans skill:

1. **The spec:** `docs/superpowers/specs/2026-04-29-hyp-recs-trade-prep-expansion-design.md` — **THE CANONICAL SCOPE SOURCE-OF-TRUTH** for this dispatch. 1,158 lines; read all of it. The spec was authored via a `copowers:brainstorming` cycle (5 Codex rounds, terminating `NO_NEW_CRITICAL_MAJOR`); it supersedes the brainstorming brief in case of any divergence.

2. **`docs/hyp-recs-trade-prep-expansion-brainstorming-brief.md`** — historical reference for design-decision context. Spec §"Goal" + §"V1 Scope" supersede where they differ.

3. **`CLAUDE.md`** — project conventions, gotchas, invariants. Note especially:
   - Test-count drift gotcha (trust pytest output, not plan-pinned counts).
   - HTMX OOB-swap partial drift gotcha — `{% include %}` to share partials between full-page and OOB-swap render paths; never hand-duplicate markup. **Specifically applies to the new `/hyp-recs/refresh` scoped builder** (per spec §"R2-Major-2 fix"); the `build_hyp_recs_section` helper must produce content that's rendered via the same `{% include %}` chain as the full-page dashboard render.
   - Base-layout 5-VM rule — verify each VM modification against `base.html.j2` references; plan should NOT blanket-require all 5 VMs to gain new fields if `base.html.j2` doesn't dereference them.
   - yfinance gotchas (not directly relevant — this dispatch doesn't fetch prices).

4. **`docs/orchestrator-context.md`** — read these sections in full:
   - §"Currently in-flight work" — current state at HEAD; sector dispatch (Phase 1) shipped 2026-04-29; this dispatch is Phase 2 of the operator sequence.
   - §"Recent decisions and framings" — particularly the 2026-04-25 Hypothesis-recommendation engine framing ("dashboard PROPOSES, operator DISPOSES"); 2026-04-25 Entry discipline for hypothesis trades; 2026-04-26 Watchlist sort uses four-key composite ordering (hyp-recs sort untouched per spec); 2026-04-26 chart-pattern flag-v1 scope decisions; 2026-04-27 brainstorm-pattern decision.
   - §"Binding conventions" — 4-tier commit-message convention; observable-verification grep ERE form; ruff baseline 91; no-amend rule; no Claude footer.
   - §"Anti-patterns" — particularly mid-session scope expansion; brief drafting drift; vacuous regression tests.
   - §"Lessons captured" — read entire section. Multiple lessons apply; particularly: discriminating-test discipline; compounding-confound class; canonical-template references win over prose count assertions; subsequent-phase tests can surface earlier-phase contract bugs; manual visual verification is required for rendering work; multi-path-ingestion (2026-04-29; same lesson class applies to multi-origin entry-form work in this dispatch); snapshot-semantic claims at spec/plan time should explicitly address transaction isolation; ToCToU on form-driven workflows is easy to overlook when "centralizing" looks elegant; audit anchors must be PERSISTED to be audit anchors; symmetric refusal across entry surfaces.

5. **`docs/phase3e-todo.md`** §"2026-04-28 hyp-recs trade-preparation expansion (QUEUED; brainstorm dispatch pending)"** — backlog context that informs scope. Spec implements this section + Q7+Q8 added 2026-04-29.

6. **Precedent plans** (structural references for what a writing-plans output looks like):
   - `docs/superpowers/plans/2026-04-28-sector-industry-capture-plan.md` — most-recent writing-plans output (Phase 1 of operator sequence). Shows the per-task TDD discipline, observable-verification grep usage, 4-tier commit-message convention application, discriminating-test discipline framing.
   - `docs/superpowers/plans/2026-04-27-chart-scope-policy-v2-plan.md` — larger plan (10 tasks); shows how cross-cutting concerns are sequenced.

7. **Precedent code** for the new patterns the spec introduces:
   - **Chevron-button HTMX trigger pattern** — spec §"Q-C resolution" specifies a NEW pattern (chevron column 1 BUTTON; `<tr>` not an HTMX trigger). Verify no existing template has this pattern; it's new to this dispatch. Cross-references the watchlist-row-trigger-architecture-refactor follow-up.
   - **Scoped section builder + extracted helper pattern** — `build_hyp_recs_section` + `_build_active_recommendations`. Existing precedent: `build_dashboard` + `build_watchlist` + `build_watchlist_row` (single-row variant) all in `swing/web/view_models/dashboard.py`. The new helper extracts the recommendation-construction logic from `build_dashboard` into a shared callable consumed by both full-page render and `/refresh` route.
   - **Origin-aware entry form** — spec §"R3+R4 resolutions" introduces `TradeEntryFormVM.origin` discriminator + hidden form field for POST round-trip survival. Existing precedent: `chart_pattern_*` snapshot-at-entry-surface fields (Phase 5 of chart-pattern flag-v1; ToCToU pattern). The origin field is similar (frozen at form-render; survives POST round-trip via hidden input).
   - **Three-site CC pivot wiring** — `partials/watchlist_top5_section.html.j2`, `partials/watchlist.html.j2`, `WatchlistRowVM.current_pivot`. The third site (`/watchlist/{ticker}/row` close-path) was caught by Codex R1+R2 in brainstorm; do NOT miss it in plan tasks.

If any file path doesn't resolve, surface in return report — do NOT silently proceed against a stale path.

---

## §0 Skill posture

- **INVOKE** `copowers:writing-plans` — wraps `superpowers:writing-plans` with adversarial Codex review (3-5 rounds typical).
- **DO NOT INVOKE** `superpowers:brainstorming`, `copowers:brainstorming`, `superpowers:executing-plans`, or `copowers:executing-plans`. The spec is locked. Re-litigation is out of scope. If a spec section appears impossible to plan as written, STOP and surface in return report via §7 escape hatch; do NOT silently re-design.
- **DO** invoke adversarial Codex review per `copowers:writing-plans` standard cycle. Iterate to `NO_NEW_CRITICAL_MAJOR`.
- **Plan output target path:** `docs/superpowers/plans/2026-04-29-hyp-recs-trade-prep-expansion-plan.md`. Commit the plan as part of the standard cycle (mirroring `2026-04-28-sector-industry-capture-plan.md` structure).

---

## §1 Strategic context

**Why this work.** Operator surfaced workflow gaps during chart-pattern flag-v1 manual verification + CC pivot bug triage (2026-04-28) + brief-review (2026-04-29). The hyp-recs panel ("dashboard PROPOSES, operator DISPOSES" per 2026-04-25 framing) currently shows ticker/price/pivot/hypothesis/progress/tripwire/suggested-label — informative for hypothesis context but missing trade-execution-decision context (buy window, sizing, stop, cost) AND missing per-row action affordance. This dispatch ships the trade-prep expansion + per-row Enter button + expansion-internal "Take this trade" button + bundled CC pivot bug fix.

**Sequencing context.** This dispatch is Phase 2 of a 6-phase post-2026-04-28 sequence: sector (SHIPPED 2026-04-29) → **hyp-recs expansion (this dispatch's plan + future executing-plans dispatch)** → OHLCV archive → noise queue → configuration page → Tier-3 design.

**Bundled bug fix.** This dispatch bundles the CC pivot bug fix (Option C: watchlist column header renders `candidates.pivot` instead of `entry_target` at THREE render sites). Cross-surface consistency on what "Pivot" means becomes part of this dispatch's done-criteria.

---

## §2 Spec is the canonical scope (DO NOT re-litigate)

The spec at `docs/superpowers/specs/2026-04-29-hyp-recs-trade-prep-expansion-design.md` is authoritative. Q1-Q8 (operator-locked decisions) and the 13 §3 design questions (resolved by the brainstorm phase) are LOCKED. The plan IMPLEMENTS the spec; it does NOT re-design.

If during plan-drafting the implementer discovers a spec section is impossible to plan cleanly (e.g., a referenced file doesn't exist, a precedent the spec cites isn't actually in the codebase, an assumption about existing data structure is incorrect), STOP and surface in return report via §7 escape hatch. Do NOT silently re-design.

---

## §3 V1 Scope (per spec; mirrored here for plan-author convenience)

**File map: 22 files total** per spec §"File Map":
- 4 production NEW
- 12 production MODIFY
- 6 test NEW
- No migrations (zero schema-version bump).
- No Phase 2 carve-outs.

**Implementation sequencing recommended in spec §7.1:**
1. CC pivot wiring (foundational column-rendering change at 3 sites).
2. `chase_factor` config field (`Config.web.chase_factor: float = 0.01`).
3. Hyp-recs expansion partial + `/hyp-recs/refresh` route + scoped `build_hyp_recs_section` builder + `_build_active_recommendations` extracted helper.
4. Per-row Enter button + expansion-internal "Take this trade" button.
5. Origin-aware entry form (template parameterization + `TradeEntryFormVM.origin` discriminator + hidden form field for POST round-trip survival + anchor-consistency logic for hyp-recs origin).

The plan can refine sequencing if there's a concrete reason; deviating from spec §7.1 should be justified in plan-task-body rationale.

**13 resolved design questions (per spec §3 → §"Design choices made"):** Q-A through Q-M. Spec specifies exact resolutions; plan tasks implement them.

---

## §4 Plan acceptance criteria

The plan output (at `docs/superpowers/plans/2026-04-29-hyp-recs-trade-prep-expansion-plan.md`) MUST satisfy:

1. **Per-task TDD discipline.** Each task: failing test first → minimal implementation → passing test → commit. One red-green cycle per logical change.

2. **Discriminating-test discipline (per orchestrator-context lessons).** Every task with a discriminating test includes a "would this test fail if the implementation never actually called the new code?" sanity-check sentence in the task body. Per the canonical compounding-confound failure modes:
   - **Specifically applicable here:** action-button tests must use sentinel values that distinguish per-row Enter from expansion-internal "Take this trade" rendered URLs. If both buttons navigate to `/trades/entry?ticker=...&origin=<X>` with different `origin` values, the test setup must use ticker values where pre-fix and post-fix rendering produce DIFFERENT URLs — otherwise the test is vacuous.
   - **CC pivot three-site fix:** test setup must use a candidate where `entry_target` ≠ `candidates.pivot` so the test can discriminate "rendered the right field" from "rendered either field." `entry_target=$24.13, candidates.pivot=$26.98` (the canonical CC bug values from operator's screenshot) is the natural sentinel.
   - **Origin-aware entry form:** tests for each origin (watchlist, hyp-recs-row, hyp-recs-expansion, URL-param) must use distinct origin values; assertions must assert on the specific origin value, NOT just "origin field is present."

3. **Compounding-confound class avoidance** (Phase 4 + chart-scope-policy-v2 + chart-pattern flag-v1 lessons). Tests that assert on a primary key must NOT have secondary keys (alphabetical tiebreakers, default sort orders) that mask the bug. Plan tasks must INVERT setups so the bug's output diverges from the correct output's secondary-key path.

4. **Multi-path-ingestion lesson application** (2026-04-29). The entry form serves multiple origins (per spec §"Origin-aware entry form"). Plan tasks must enumerate ALL origin paths (watchlist, hyp-recs-row, hyp-recs-expansion, URL-param) and verify each one threads the `origin` field correctly. If a plan task tests one origin, the corresponding task or test extension must cover the others.

5. **Sequential single-subagent execution discipline.** Plan tasks are SEQUENTIAL; no parallel-subagent collision risk at this scale. Plan task IDs follow the convention (flat `Task N` per chart-scope-policy-v2 + sector capture precedent).

6. **Observable-verification subject-only grep pattern** per binding conventions: `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task <N>'` before each task implementation commit. ERE flag required (BRE chokes on `+`); POSIX `[0-9]` for digit class. Each task includes this verification step in its body.

7. **Commit-message convention (4-tier per binding conventions).**
   - Task implementations: `feat(area): Task N — <description>` (flat numbering; matches chart-scope-policy-v2 + sector-capture precedent).
   - Codex review-fix commits: `fix(area): Codex R1 Major 2 — <description>`.
   - Internal-Codex within-task: `(internal)` qualifier.
   - Internal code-review: `fix(area): code-review I1 — <description>`.
   - Format-only cleanup: no task ID.

8. **CC pivot wiring is the FIRST set of plan tasks** per spec §7.1. All subsequent tasks depend on the column-rendering foundation landing. The three render sites (`watchlist_top5_section.html.j2`, `watchlist.html.j2`, `WatchlistRowVM.current_pivot`) can be one task or three tasks; plan-author judgment.

9. **`chase_factor` config task** comes second per spec §7.1. **Toml-shadowing audit (binding):** plan task body MUST include a step verifying `grep -rn "chase_factor" .` returns zero hits in tracked toml files BEFORE the implementation commits. Per spec §"Q-F resolution" the field has Python default 0.01 and NO toml override; toml-shadowing audit closes the gap from the `aeb2084` lesson (2026-04-28).

10. **HTMX OOB-swap drift discipline.** Per CLAUDE.md gotcha + `build_hyp_recs_section` requirement. The `/hyp-recs/refresh` route must render content via the same `{% include %}` chain as the full-page dashboard render. Plan task for `/hyp-recs/refresh` must include a discriminating test that asserts the OOB-swap response includes the same hyp-recs-section HTML as the full-page render (substring or structural match).

11. **Origin-aware entry-form coverage.** Per spec §"R3+R4 resolutions" + §"R4-Major-1 resolution" (POST round-trip survival). Plan tasks must cover:
    - Origin field renders in entry form via hidden input for ALL origins.
    - Origin field survives `_rerender_entry_form_with_error` round-trip.
    - Origin field survives `DuplicateOpenPositionError` round-trip.
    - Origin field survives `soft_warn_confirm` round-trip.
    - Anchor-consistency for hyp-recs origin uses `latest_completed_pipeline_run` for ALL candidate-derived reads.
    
    Each round-trip path is its own discriminating test OR is bundled into a parametrized test with origin-specific assertions.

12. **Test count baseline pinned at plan-time.** Plan should note the current fast-test count (`python -m pytest -m "not slow" -q` to get exact number) and project per-task test additions. Sector dispatch baseline was 1227 at HEAD `09ad4bd`; this dispatch starts from there or whatever HEAD is at plan-authoring time.

13. **Plan passes copowers:writing-plans Codex review cycle:** iterate to `NO_NEW_CRITICAL_MAJOR`. Major findings RESOLVED-by-fix; ACCEPTED-with-rationale only if genuinely out-of-scope per §3.

---

## §5 Adversarial review watch items (for Codex during writing-plans cycle)

These are the high-likelihood failure modes Codex should specifically check. Pre-empt by self-checking BEFORE each plan-task draft:

1. **Three-site CC pivot wiring completeness.** Per spec §"Q-G resolution" + brainstorm R1+R2 history. The third site (`WatchlistRowVM.current_pivot` for `/watchlist/{ticker}/row` close-path) is the easiest to miss. Plan tasks must cover all three sites; verify by enumeration.

2. **Origin-aware entry-form POST round-trip coverage.** Per spec §"R4-Major-1 resolution". Entry form serves multiple origins; the `origin` field must survive ALL POST-error paths (`_rerender_entry_form_with_error`, `DuplicateOpenPositionError`, `soft_warn_confirm`). Plan tests must cover each round-trip path.

3. **HTMX OOB-swap drift on `/hyp-recs/refresh`.** Per CLAUDE.md gotcha. Plan task for the route must include a discriminating test that catches drift if `build_hyp_recs_section` and the full-page render diverge in produced HTML.

4. **Discriminating-test setup for action-button URL distinction.** Per-row Enter button URL = `/trades/entry?ticker=<X>&origin=hyp-recs-row`; expansion-internal "Take this trade" URL = `/trades/entry?ticker=<X>&origin=hyp-recs-expansion` (or similar — verify spec §"D.3 resolution"). Tests must use ticker setups that produce DIFFERENT URLs pre-fix and post-fix; vacuous tests that pass under any URL would be a discriminating-test failure.

5. **Chevron-button HTMX pattern correctness.** Per spec §"Q-C resolution". Chevron BUTTON in column 1 is the HTMX trigger; `<tr>` is NOT. Plan task for the chevron must include a test that confirms clicking the chevron (NOT the row) triggers the expansion. Test setup must include a row with NO chevron-clickable elements OUTSIDE the chevron button itself; if clicking elsewhere on the row triggers expansion, the trigger is mis-configured.

6. **Anchor-consistency for hyp-recs origin.** Per spec §"R4-Major-2 resolution" (anchor consistency uses `latest_completed_pipeline_run` for ALL candidate-derived reads when origin=hyp-recs). Plan task must specify the helper used + verify it's called consistently across the entry-form VM build, the candidate-row reads, and any joins.

7. **`chase_factor` toml-shadowing audit.** Per spec §"Q-F resolution" + 2026-04-28 `aeb2084` lesson. Plan task body must include the audit step (`grep -rn "chase_factor" .` against tracked config files) BEFORE the implementation commits.

8. **Test fixture ticker uniqueness.** Multi-origin tests are easy to alphabetically-collide if ticker selection is not deliberate. Per the chart-pattern flag-v1 Phase 4 ticker-symmetry-vacuousness lesson — invert setups so default-sort doesn't accidentally produce the correct-output by coincidence.

9. **Plan-task partitioning is DISJOINT.** Per Phase 2 self-collision lesson + 9-phase ZERO-rogue track record. Each plan task assigned to exactly one notional subagent (this dispatch is single-subagent so partitioning is trivial; verify the partitioning is documented).

10. **Sort-neutrality regression discipline.** Per chart-pattern flag-v1 R1 M2 lesson. The spec specifies hyp-recs sort untouched (hypothesis-aware prioritizer; sector/industry/etc. NOT in sort tuple). Plan task for any field added to the hyp-recs row must include a sort-neutrality regression test verifying the sort order is unchanged when the new field varies across rows.

---

## §6 Done criteria

- Plan committed to `docs/superpowers/plans/2026-04-29-hyp-recs-trade-prep-expansion-plan.md`.
- Plan passes `copowers:writing-plans` Codex review cycle: 3-5 rounds, terminating at `NO_NEW_CRITICAL_MAJOR`.
- All Major findings RESOLVED-by-fix; ACCEPTED-with-rationale only if genuinely out-of-scope.
- Test count baseline pinned in plan body.
- Per-task observable-verification step included in each task body.
- Per-task discriminating-test sanity-check sentence included where applicable.
- 22 files (per spec File Map) all mapped to plan tasks; no orphaned files.
- Implementation sequencing follows spec §7.1 OR plan justifies divergence in task-body rationale.

---

## §7 Return report format

Post as final message:

```
## Hyp-recs Trade-Prep Expansion Plan — Writing-Plans Return Report

**Plan committed at:** docs/superpowers/plans/2026-04-29-hyp-recs-trade-prep-expansion-plan.md (commit <SHA>)
**Codex rounds:** N rounds, terminating at NO_NEW_CRITICAL_MAJOR
**Test baseline pinned:** <count> fast tests at HEAD <SHA>
**Plan task count:** <N tasks>
**Files mapped:** 22/22 per spec File Map (or note any divergence)
**Implementation sequencing:** matches spec §7.1 / diverges with rationale

**Codex findings dispositioned:**
- R1: <count> Critical, <count> Major, <count> Minor — all RESOLVED / <N> ACCEPTED with rationale
- R2: <count> Critical, <count> Major, <count> Minor — all RESOLVED / <N> ACCEPTED with rationale
- ... (per round)

**Open questions for orchestrator triage:**
- <any items the implementer flagged as needing operator/orchestrator decision before executing-plans dispatch>

**Recommended next dispatch:** copowers:executing-plans on this plan, OR <alternative if implementer surfaces a concern>
```

---

## §8 If you get stuck

- **If a spec section appears impossible to plan as written:** STOP, surface in return report. Do NOT silently re-design. Examples: a precedent file the spec cites doesn't exist; a referenced route is structurally different than the spec assumed; a fixture pattern the spec relies on isn't in the codebase.
- **If a precedent file path doesn't resolve:** Use `Glob` / `Grep` to find the actual current path. The spec was authored at HEAD `ade2b41` which should be very recent; file paths should be stable but verify if any plan-task reference seems off.
- **If Codex round count exceeds 5 without convergence:** STOP, surface in return report with the unresolved finding. Do NOT iterate indefinitely.
- **If discriminating-test sanity check reveals vacuousness on a primary-key assertion:** STOP, restructure the test setup to invert the symmetry per Phase 4 lesson, then resume Codex cycle.
- **If you find a scope-deviation opportunity** (e.g., a refactor that would make Task X cleaner but isn't in the spec): SURFACE in return report as a follow-up; do NOT in-line-include in the plan. Per orchestrator-context anti-pattern: "Mid-session scope expansion."

---

## Appendix A: Spec-history awareness

The spec went through 5 brainstorming Codex rounds before this dispatch. Major findings already addressed:

- R1: 4 Major + 3 Minor — snapshot-purity, `_ROW_TARGET_PREFIXES` extension, watchlist /row close-path CC pivot fix, full-section refresh decision; field-count churn, scope-accounting, dash sentinel.
- R2: 2 Major + 1 Minor — correct CC pivot wiring sites (`watchlist_top5_section.html.j2` not `dashboard.html.j2`); scoped `build_hyp_recs_section` builder for `/refresh` instead of full `build_dashboard`.
- R3: 2 Major + 1 Minor — origin-aware entry form (colspan + Cancel parameterized); off-watchlist candidate fallback for `entry_price`/`initial_stop`.
- R4: 2 Major + 1 Minor — origin survives POST round-trips via hidden form field threaded through `_rerender_entry_form_with_error`/`DuplicateOpenPositionError`/`soft_warn_confirm`; anchor consistency for hyp-recs origin uses `latest_completed_pipeline_run` for ALL candidate-derived reads.
- R5: 0 Major + 2 Minor — implementation sequencing in §7.1; freshness-footer wording clarified to "Candidate context as of pipeline finished" to avoid implying live-price freshness.

Spec-history is durable in `docs/superpowers/specs/2026-04-29-hyp-recs-trade-prep-expansion-design.md` commit chain (`2bafde5` → `ff69143` → `70eea8c` → `51ffb07` → `622dc81` → `327b2b4` → `ade2b41`). Plan implementer should NOT re-iterate on resolved findings; if a Codex round in THIS dispatch raises a finding that already has a spec-history fix, cite the spec section + the brainstorm-fix commit, then proceed.

---

## Appendix B: Cross-plan grep aliasing awareness

Per the sector capture writing-plans return report, flat `Task N` numbering creates cross-plan grep aliasing — `git log -E --grep='^[a-z]+\([a-z]+\): Task 1'` matches commits across BOTH the sector capture plan's Task 1 AND this plan's Task 1. This is expected per the chart-scope-policy-v2 + sector-capture precedent.

The executing-plans phase implementer (NOT this writing-plans phase) handles the cross-plan disambiguation: each task's plan-specific commit subject is unique within the dispatch chain, and the implementer notes the aliasing in their return report.

This writing-plans phase just specifies the observable-verification grep pattern in each plan task; the executing-plans phase invokes it. No mitigation needed in the plan itself.

---

## Appendix C: Cross-references

- **Spec:** `docs/superpowers/specs/2026-04-29-hyp-recs-trade-prep-expansion-design.md` (1,158 lines; 5 Codex rounds; HEAD `ade2b41` at dispatch time).
- **Brainstorming brief:** `docs/hyp-recs-trade-prep-expansion-brainstorming-brief.md` (mid-dispatch updated to add Q7+Q8 at commit `427ef95`).
- **Phase 1 sector dispatch (just shipped 2026-04-29):** plan precedent at `docs/superpowers/plans/2026-04-28-sector-industry-capture-plan.md`; brief precedent at `docs/sector-industry-capture-writing-plans-brief.md`.
- **Phase 1 sector executing-plans brief:** `docs/sector-industry-capture-executing-plans-brief.md` — for context on what the eventual executing-plans dispatch consumes.
- **Operator decisions Q1-Q6 (2026-04-28):** `docs/phase3e-todo.md` §"2026-04-28 hyp-recs trade-preparation expansion" subsection "Locked decisions (operator, 2026-04-28; brainstorm uses these as framing input)".
- **Operator decisions Q7+Q8 (2026-04-29):** brainstorming brief §2 (latest commit `427ef95`).
- **Capital risk floor convention:** project memory `project_capital_risk_floor.md` — risk uses max($7,500, balance); cash-feasibility uses balance only. Drives the dual-cost-display logic in spec §"Q-I resolution".
- **Hypothesis-recommendation engine framing (2026-04-25):** orchestrator-context "Recent decisions and framings" — "dashboard PROPOSES, operator DISPOSES." Drives the action-button design (Q7+Q8).
- **Multi-path-ingestion lesson (2026-04-29):** orchestrator-context "Lessons captured" — input-side analog of multi-resolver-output lesson; applies to the multi-origin entry-form coverage requirement (§5 watch item 2).
