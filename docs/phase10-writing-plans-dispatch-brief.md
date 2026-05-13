# Phase 10 — writing-plans dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Convert the Phase 10 (Metrics Dashboard) brainstorm spec into an executable implementation plan via `copowers:writing-plans`. The skill wraps `superpowers:writing-plans` + adversarial Codex MCP review. Output is a single plan file (per the writing-plans convention) that the orchestrator subsequently dispatches via `copowers:executing-plans` — typically as multiple sub-bundles given Phase 10's 8-metric-category + 8-dashboard-surface scope.

**Expected duration:** ~5-9 hr planning + ~2-3 hr Codex convergence. Total ~6-9 hr (matches Phase 9 writing-plans precedent: 5 Codex rounds + 2257-line plan).

---

## §0 Inputs

### §0.1 Spec
- **SPEC_PATH:** `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md`
- **Spec status:** Codex R1-R5 substantive + R6 confirmation → NO_NEW_CRITICAL_MAJOR; SHIPPED 2026-05-06 at `fe6cb45`. 641 lines. RESEARCH-POSTURE (intentionally NO schema, NO code, NO task decomposition).
- **Spec produces** (per §1.1): a locked set of metric DEFINITIONS (§3, 8 metric categories spanning ~50+ metrics); dashboard SURFACE SKETCHES (§4, 8 surfaces); a SINGLE low-sample-size honesty POLICY (§5, applied uniformly across all metrics + surfaces); capture-needs feedback for Phase 8 + Phase 9 (§6, MOST SATISFIED — see §0.5 below); the mistake-cost formula determination (§7 — affirms Phase 6's shipped formula, no code change required); 7 open questions for orchestrator triage (§8).
- **Spec deliberately does NOT produce** (per §1.2): schema layouts, table definitions, CHECK constraints, indexes, view-model classes, query implementations, Jinja templates, route handlers, task decompositions, dispatch briefs. THAT IS WRITING-PLANS' JOB.

### §0.2 Project state at dispatch time
- **HEAD on `main`:** `cd9e266` (post-Phase-9-arc-close housekeeping + orchestrator handoff brief).
- **Test count:** **2771 fast passing on main** (1 skipped — Task 7.3 operator-only flag-classifier fixture); 3 pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py` failures NOT regressions (banked separately). Verified inline at brief drafting time. **Worktree-baseline differs:** in a fresh worktree the 4 `thinkorswim/*.csv` real-world fixtures are NOT present (untracked on main; not branched into worktree), so the worktree-side test count is **2767 passing + 5 skipped** (the 4 fixture-absent skips + 1 Task 7.3). Plan §A baseline-test-count documentation should reflect the WORKTREE-side number since the implementer runs from the worktree.
- **Ruff baseline:** **18** (E501 only; unchanged across the entire Phase 9 arc).
- **Schema version:** **v17.** Locked since Phase 9 Sub-bundle A `6c8f3a9` 2026-05-12; Phase 9 consumer-side bundles (B/C/D/E) did NOT advance.
- **Phase 9 arc SHIPPED ENTIRELY** (all 5 sub-bundles A→B→C→D→E merged + integrated). 53 commits / 19 Codex rounds / +503 cumulative fast tests / ZERO unresolved Critical+Major findings.

### §0.3 Phase 9 arc lessons inherited (BINDING for Phase 10 writing-plans)

The following Codex-caught lessons banked at `CLAUDE.md` "Gotchas" section + `docs/orchestrator-context.md` "Lessons captured" are forward-binding. Phase 10's writing-plans chain WILL test whether the plan respects these:

1. **`__post_init__` validator pattern on all new dataclasses** (LOCKED across Phase 9 A+B+C+D+E). Any new metric-VM dataclass or shared utility config dataclass must reject NaN/inf/out-of-range values at construction time. The pattern is `swing/data/models.py:RiskPolicy.__post_init__` (Phase 9 Sub-bundle A).

2. **Service-layer transaction discipline** (Phase 8 + Phase 9 arc lock). Caller MUST NOT hold open transaction; service owns BEGIN IMMEDIATE / COMMIT / ROLLBACK; reject-don't-auto-detect. Phase 10 is READ-SIDE dominant so this likely affects ONLY any new write-side scope (e.g., manual `account_equity_snapshots` web form per §8.2). If Phase 10 introduces ZERO new write paths, this lesson banks for V2.

3. **NO `INSERT OR REPLACE` on FK-referenced or audit-trail tables** (Phase 8 + 9 lock). Phase 10 is read-side dominant; applies only if new schema lands.

4. **Server-stamping discipline at handler entry for all hidden audit fields** (Phase 8 R2.M2 + R3.M2 + R4.M2 lock). If Phase 10 surfaces ANY form (e.g., a "supersede policy from dashboard" shortcut, or manual snapshot capture per §8.2), server-stamp timestamps at handler entry, NOT hidden inputs.

5. **Composition-surface enumeration via `^def` grep, NOT memory-enumerate** (Bundle 2+3 + Phase 9 A+B+C+D+E codification). Phase 10 introduces multiple new view-model entry points; plan must enumerate ALL call sites for each new VM helper via `grep -rn "^def " swing/web/view_models/` when surfacing acceptance criteria.

6. **Empirical-verification of brief assertions about column-vs-derived state** (Phase 9 Sub-bundle C R1 M#1 sign-convention precedent). Before locking any metric-formula in the plan, READ the spec section + verify against current code; do NOT memory-summarize.

7. **Form-render hidden anchors driving POST-time validation MUST round-trip through soft-warn confirm `form_values` dict** (Phase 9 Sub-bundle D R3 family; CLAUDE.md gotcha at `6ba1925`). Applies ONLY if Phase 10 introduces a form-driven write path that touches a soft-warn confirm fragment (e.g., manual snapshot capture per §8.2).

8. **POST-time recompute of "latest-of-something" creates GET/POST TOCTOU window** (Phase 9 Sub-bundle D R2 family; CLAUDE.md gotcha at `6ba1925`). For any form that depends on "latest pipeline_run" / "latest evaluation_run" / etc., the form-render-emitted hidden anchor MUST be the source of truth, NOT a POST-time recompute. Same scope as #7.

9. **Test fixtures exercising `write_user_overrides` MUST monkeypatch USERPROFILE + HOME** (Phase 9 Sub-bundle A R1 incident; CLAUDE.md gotcha at `de10601`). Applies to any new test fixture that exercises user-config writes (e.g., updating metric-config defaults).

10. **HTMX browser-only failure surfaces** (Phase 5 R1 M1+M2 + Phase 6 I3 + Phase 9 Sub-bundle D R3; cumulative CLAUDE.md gotcha family). Every new HTMX-form endpoint requires operator-witnessed browser verification — TestClient passes are necessary but not sufficient. Three known failure modes: HX-Request header propagation; HX-Redirect-vs-303-swap; HX-Redirect-target-unrouted. Phase 10 spec §4.9 enforces operator-witnessed gate per surface as BINDING.

11. **`<tr>`-leading HTMX response triggers `makeFragment` table-wrap** (Bug B 2026-04-29; CLAUDE.md gotcha). Any new HTMX endpoint returning multiple swap chunks must keep the response's primary content table-row-free. Phase 10's dashboard surfaces are likely HTMX OOB-swap-driven (per the dashboard.py precedent); this lesson applies directly.

12. **Matplotlib mathtext fires on `$ ^ _ \` characters** (commit `29c93f5`; CLAUDE.md gotcha). Phase 10 §4 surfaces are explicitly STATIC-RENDERED HTML (per §4.9 "No client-side compute"); BUT any chart-rendering work (e.g., process-grade-trend line chart in §4.8 via matplotlib + chart sub-skill) inherits this lesson.

### §0.4 Open questions disposition

Spec §8 enumerates 7 open questions. Writing-plans MAY default to brainstorm recommendations OR surface a divergence:

| Question | Brainstorm recommendation | Writing-plans posture |
|---|---|---|
| §8.1 fills.action 'add' enum gap | DEFER (capital-floor convention; theoretical at $7,500) | Accept defer. Phase 10 scope unchanged. |
| §8.2 Daily account equity capture — manual entry vs Schwab API Phase A | WAIT for Schwab API as primary; re-evaluate manual entry if PROVISIONAL fallback is misleading at scale | **OPEN — orchestrator decides.** Phase 9 already shipped: (a) `account_equity_snapshots` table + (b) `swing account snapshot record` CLI + (c) source-ladder `get_latest_snapshot_on_or_before`. What is NOT shipped: a WEB-form capture surface. If Phase 10 V1 should include a "capture today's equity" web form, surface in plan §A; if not, plan §A documents the CLI-only V1 disposition + flags web-form surface as V2. Default recommendation: CLI-only V1 (CLI is shipped + operator-paced; web form is +1 task with HTMX failure-surface budget). |
| §8.3 Benchmark series capture location | DEFER until ≥60 trading days threshold | Accept defer. Phase 10 V1 does NOT include benchmark-relative metrics (§3.9 explicit deferral). |
| §8.4 Corporate actions MVP — defensive vs deferred | DEFENSIVE (log + manual-reconcile) recommended | **OPEN — orchestrator decides.** Recommended posture: DEFER to Phase 10+ follow-up dispatch (not Phase 10 scope). If operator elects to roll into Phase 10, plan §A documents the +1 table scope + manual-reconcile CLI shape. Default: defer; flag in plan as Phase 10+ follow-up. |
| §8.5 `process_grade_rolling_N` window size — V1 hardcode vs config | HARDCODE N=10 | Accept. Plan §A locks `N=10` as constant; defers risk_policy-based externalization to V2. |
| §8.6 Surface `lucky_violation_R` on Phase 6 review form? | YES, but as small standalone follow-up (not Phase 10 scope) | **OPEN — orchestrator decides.** Recommended posture: small standalone follow-up post-Phase-10; banks in `docs/phase3e-todo.md`. Plan §A documents the deferral. If operator elects to roll into Phase 10, plan §A bundles into Sub-bundle B (the §4.1 trade-process card sub-bundle that owns the review-derived metrics surface). |
| §8.7 Hypothesis-cohort decision-criteria automation | MANUAL text-rendering only | Accept manual posture. V1 `cohort_decision_criterion_evaluation_text` per spec §3.7 R1 M4. |

**Plan posture:** If writing-plans agrees with all brainstorm recommendations on §8.1, §8.3, §8.5, §8.7, document acceptance per question in plan §A (resolved-during-planning). For §8.2, §8.4, §8.6 (the 3 OPEN questions), plan §A surfaces the orchestrator-decision-pending state explicitly + carries the default-posture recommendation. The plan should NOT block on these — default to the recommended posture; the orchestrator can revise per operator preference at integration triage.

### §0.5 Phase 8 + Phase 9 capture-needs SATISFIED for Phase 10 (binding inputs)

Per `docs/phase3e-todo.md` Phase 10 hand-off note (T-E.2 landing at `78e7555`):

**§11.1 Risk_Policy as the source for metric defaults at dashboard read-time.** Phase 9 ships `risk_policy` table (34 fields per `swing config policy show`) + per-row stamp on `trades.risk_policy_id_at_lock` + `review_log.risk_policy_id_at_review_completion`. Phase 10 dashboard reads:
- **LIVE policy** (`risk_policy.is_active=1`) for: `low_sample_size_threshold_class_*_n`, `global_confidence_floor_n`, `bootstrap_resample_count`, `process_grade_weight_entry/management/exit`.
- **AT-TRADE-TIME policy** (`trades.risk_policy_id_at_lock` JOIN to `risk_policy.policy_id`) for: `capital_floor_constant_dollars`, `scratch_epsilon_R`, trade-grain metrics requiring policy-as-of-trade-time semantics.

The per-row stamp on trades + review_log enables this at-trade-time vs live-time distinction. **Schema ready; Phase 10 wires the queries.**

**§11.2 Reconciliation discrepancy surface.** Phase 9 ships `reconciliation_runs` + `reconciliation_discrepancies` + canonical query `list_unresolved_material_for_active_trades` (closed-trade companion also shipped). Phase 10 surfaces (optional, V1 or V2): (a) dashboard "N unresolved material discrepancies" badge; (b) per-trade detail "Trade X has unresolved reconciliation discrepancies" indicator; (c) per-cohort metrics view optional "exclude trades with unresolved discrepancies" filter.

**Plan §A question:** Should Phase 10 V1 include reconciliation-status surfaces (a/b/c), OR defer to Phase 10+ follow-up? Default recommendation: include surface (a) [global badge] in Phase 10 V1 Sub-bundle E (polish); defer (b)+(c) to Phase 10+ follow-up.

**§11.3 Hypothesis status history surfaces.** Phase 9 ships `hypothesis_status_history` audit table + `list_history_for_hypothesis` + `list_all_history` queries. Phase 10 §3.2 spec section currently surfaces "single most-recent transition only" in V1 (per spec note). Plan §A should decide: does Phase 10 V1 SUPERSEDE the spec's V1-limitation and surface full transition history? Default recommendation: YES — spec's V1 limitation was written when the audit table didn't exist; Phase 9 closed that gap.

**§11.4 account_equity_snapshots resolution for `live_capital_denominator_dollars`.** Phase 9 ships the table + source-ladder discipline (schwab_api > tos_csv > manual). Phase 10 metric layer resolves the canonical query per the hand-off note's SQL pattern:

```sql
live_capital_denominator_dollars(asof_date) :=
  COALESCE(
    (SELECT equity_dollars FROM account_equity_snapshots
       WHERE snapshot_date <= asof_date
       ORDER BY snapshot_date DESC,
                CASE source WHEN 'schwab_api' THEN 1
                            WHEN 'tos_csv' THEN 2
                            WHEN 'manual' THEN 3 END ASC
       LIMIT 1),
    (SELECT capital_floor_constant_dollars FROM risk_policy WHERE is_active = 1)
  )
```

`get_latest_snapshot_on_or_before` already implements the source-ladder. **Phase 10 consumes the existing helper; the PROVISIONAL fallback semantics from spec §2 + §3.4 + §3.5 may now resolve to ACTUAL live denominator (when snapshots exist) OR continue to use `capital_floor_constant_dollars` (when none).**

**Phase 10 plan §A binding decision:** The spec §2 split-policy currently mandates PROVISIONAL badges on operational metrics. With Phase 9's `account_equity_snapshots` shipped, the PROVISIONAL badge logic now becomes "PROVISIONAL when fallback hit (no snapshot ≤ asof_date); LIVE when snapshot exists". Plan §A locks this dynamic-badge contract. Operator-facing impact: once operator records a snapshot (CLI or web), the PROVISIONAL badge clears on operational metrics for sessions ≥ snapshot_date.

**§11.5 Capture-needs already accommodated.** Per hand-off note: Phase 8 satisfies `maturity_stage`, `open_MFE_R/MAE_R`, `position_capital_utilization`, `position_portfolio_heat_contribution`, `trail_MA_candidate_price`, `planned_target_R`. Phase 9 satisfies risk_policy externalization + reconciliation discrepancies + hypothesis_status_history + account_equity_snapshots. Phase 10 §6.3 enumerated capture-needs beyond Phase 8/9:
- (a) per-pipeline-run capital-utilization aggregate — **Phase 10+ writing-plans territory; could be in scope OR deferred.** Default recommendation: derive on-the-fly via JOIN from existing tables (`pipeline_runs` + `account_equity_snapshots` + open `trades` at run timestamp); do NOT add new columns to `pipeline_runs` unless multi-run trend queries become prohibitively slow. Plan §A locks the derivation approach.
- (b) benchmark series capture — OUT of Phase 10 V1 scope (per §3.9 + §8.3 deferral).
- (c) Corporate_Actions MVP — see §0.4 §8.4 disposition (orchestrator-decides).
- (d) daily account equity capture — SATISFIED by Phase 9 `account_equity_snapshots` table; see §8.2 disposition (CLI shipped; web-form scope orchestrator-decides).

### §0.6 Empirical schema verification (plan §A locks)

The plan §A pre-plan recon (Step 5 of paste-ready prompt) MUST verify the following empirically before locking the schema posture:

1. **Phase 10 V1 introduces ZERO new tables** by default. Verify: every metric input in §3 has a corresponding shipped column/table (re-grep against `swing/data/migrations/*.sql` + `swing/data/models.py`).
2. **Phase 10 V1 introduces ZERO new ALTERs on shipped tables** by default. Verify: every aggregation in §3 + §4 can be computed via SELECT JOIN + window functions against the v17 schema as-shipped.
3. **If verification fails on any metric/surface,** plan §A surfaces the gap explicitly with one of: (a) defer the metric/surface to Phase 10+ follow-up; (b) propose a minimal schema add with `0018_*.sql` migration filename + EXPECTED_SCHEMA_VERSION bump v17→v18. Default recommendation: DEFER, do NOT add schema unless absolutely required by a primary surface.

**Expected outcome of §0.6 verification:** Phase 10 V1 is purely read-side aggregation + new view-models + new templates + new routes. Schema unchanged at v17. Migration filename `0018_*` is RESERVED but NOT used in Phase 10 V1 (it remains available for the first post-Phase-10 schema-adding work).

### §0.7 Operator-driven manual snapshot capture state (for plan §A awareness)

Per CLAUDE.md status line + Phase 9 Sub-bundle C ship: production `account_equity_snapshots` table contains 2 manual snapshots from Sub-bundle C gate (snapshot #1 $2000 at 2026-05-11; snapshot #2 $1800 at 2026-04-01 back-recorded). Operator may want to record fresh snapshots before Phase 10 V1 ship (so PROVISIONAL → LIVE flip is operator-visible during the gate). Plan §A flags this as operator-paced action item; NOT a writing-plans blocker.

---

## §1 Output

### §1.1 Plan file
- **PLAN_PATH:** `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`
- **Format:** mirrors prior plan files (e.g., `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md`):
  - Goal + Architecture + Tech Stack header
  - §A Resolved-during-planning (empirical-audit findings; spec ambiguity disposition; orchestrator-pending OPEN questions per §0.4)
  - §B-onward: Per-task breakdown with checkbox-tracked steps (`- [ ]`)
  - Per-task: acceptance criteria, suggested tests, suggested commit shape, watch items
  - §I Cross-bundle invariants (carrying forward Phase 9 plan §I pattern)
  - §J Cross-references + grep verifications

### §1.2 Plan task decomposition expectation

Phase 10 scope is LARGE READ-SIDE (8 metric categories + 8 dashboard surfaces + 1 shared honesty utility module). Writing-plans anticipated to decompose into **4-6 sub-bundles** for executing-plans dispatch:

**Suggested decomposition (non-binding; writing-plans makes the final call):**

- **Sub-bundle A — Shared utility module + metric-aggregation infrastructure.** §5 honesty policy as a shared module (`swing/metrics/honesty.py` — Wilson CI + bootstrap CI + suppression-text format + PROVISIONAL badge component); per-cohort filter helper; rolling-window helper. Hardens against the Phase 9 forward-binding lessons (§0.3) at the foundation. No new dashboard surfaces in this bundle. (~6-10 hr executing-plans.)
- **Sub-bundle B — Trade-process card (§4.1) + hypothesis-progress card (§4.2).** §3.1 trade-process metric definitions as view-model functions; §3.2 per-cohort aggregations; extends Phase 4.5 hypothesis-progress card (already shipped) with the §3.2 metric inventory. Operator-witnessed gate per surface. (~8-12 hr executing-plans.)
- **Sub-bundle C — Tier-comparison view (§4.3) + deviation-outcome view (§4.7).** §3.3 + §3.7 metric definitions; CI-overlap descriptor (text-only per spec §3.3 R1 M3); cohort decision-criterion evaluation text (per spec §3.7 R1 M4). 4-cohort side-by-side comparison surface. (~6-10 hr executing-plans.)
- **Sub-bundle D — Capital-friction view (§4.4) + maturity-stage view (§4.5) + identification-vs-trade-funnel view (§4.6).** §3.4 + §3.5 + §3.6 metric definitions; PROVISIONAL fallback dynamic-badge logic per §0.5 §11.4 binding decision; per-pipeline-run capital-utilization aggregate via on-the-fly JOIN per §0.5 §11.5. Operational/live-state surfaces with the highest browser-visible interactivity. (~8-12 hr executing-plans.)
- **Sub-bundle E — Process-grade-trend view (§4.8) + Phase 11 hand-off prep + reconciliation-discrepancy badge.** §3.8 rolling-N metric definitions; §5.4 Class-D trend rendering; reconciliation badge per §0.5 §11.2 [(a) global badge default]; Phase 11 hand-off notes (whatever Phase 11 turns out to be — operator-decision-pending; brief notes "TBD-orchestrator" in plan). (~4-8 hr executing-plans.)

Writing-plans MAY recommend a different decomposition (e.g., fewer larger bundles, or different ordering). Plan should explain decomposition rationale + flag any cross-bundle dependencies. Critically: Sub-bundle A's honesty utility module is a CROSS-BUNDLE DEPENDENCY for B/C/D/E — all later bundles consume it for CI rendering + suppression. Plan should lock A's interface contract (function signatures + return shapes) early so B-E can mock-against-interface where helpful.

### §1.3 Operator-witnessed verification gate budget

Per spec §4.9 BINDING: each Phase 10 surface, on first deploy, requires operator-witnessed browser verification. Sub-bundle B + C + D + E each ship multiple surfaces — verification gate budget is meaningful. Plan should enumerate per-bundle gate-surface count + suggest grouping that keeps each gate session under ~6 surfaces (Phase 9 Sub-bundle A pattern: 7 surfaces was at the upper limit operator could complete in one session).

---

## §2 Worktree + binding conventions

### §2.1 Worktree
- **Branch:** `phase10-writing-plans`
- **Worktree directory:** `.worktrees/phase10-writing-plans/`
- **BASELINE_SHA:** `cd9e266` (current main HEAD; post-Phase-9-arc-close housekeeping + orchestrator handoff brief).
- **Worktree branching point:** current HEAD of `main` at worktree-creation time (resolve via `git rev-parse main`; expected the brief commit SHA after this brief lands).

### §2.2 Marker-file workflow
- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After plan + Codex chain converges + before final commit: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §2.3 Commits
- Conventional prefix:
  - `docs(phase10): Phase 10 writing-plans — <description>` for the plan file
  - `docs(phase10): Phase 10 writing-plans — Codex RN fix — <description>` for Codex-driven plan refinements
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.
- Final commit: the plan file at `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md` + the return report.

### §2.4 Branch isolation + ownership
- Commits on branch only; no push to origin from worktree.
- **Implementer (you) owns:** copowers:writing-plans invocation → Codex iteration → plan commit → return report.
- **Orchestrator owns:** plan triage + integration merge to main + executing-plans dispatch commissioning (one or more bundles).

### §2.5 Verify command (basic; the writing-plans skill handles full Codex review)
```powershell
# After plan landed:
git log --oneline HEAD~5..HEAD
git diff --stat HEAD~1..HEAD
ls docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md
```

---

## §3 Skill posture + adversarial review

- **Invoke `copowers:writing-plans`** (NOT `superpowers:writing-plans` directly — the copowers wrapper handles Codex review automatically).
- Skill inputs:
  - `SPEC_PATH=docs/superpowers/specs/2026-05-06-phase10-metrics-design.md`
  - `PLAN_PATH=docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`
  - `BASELINE_SHA=cd9e266`
- **Expected Codex chain:** 3-6 rounds (Phase 9 writing-plans hit 5 rounds with a 2257-line plan; Phase 10 spec is smaller (641 lines vs 1090) but the plan must address ~50 metrics + 8 surfaces + 1 utility module — comparable plan complexity).
- Iterate per-round fixes as `docs(phase10): Phase 10 writing-plans — Codex RN fix — ...` commits.
- Terminate at NO_NEW_CRITICAL_MAJOR.

### §3.1 Codex value-add concentration

Adversarial review for writing-plans typically catches:

- **Spec-metric-formula divergence** — plan's task-spec metric formulas differ from spec §3.x in subtle ways (wrong denominator, missed scratch_epsilon resolution path, wrong Class assignment per §5).
- **Honesty-policy coverage gaps** — plan's metric tasks miss a §5 Class-A/B/C/D assignment for a metric.
- **Capital-denominator split-policy violations** — plan locks `live_capital_denominator_dollars` for a governance metric (or vice versa) — spec §2 split-policy is binding.
- **Dynamic PROVISIONAL badge logic mishandled** — plan locks badge as static even when account_equity_snapshots covers the asof_date (§0.5 §11.4 binding decision).
- **At-trade-time vs live-time policy resolution** — plan reads `risk_policy.is_active=1` for a metric that should read `trades.risk_policy_id_at_lock` (or vice versa); per §0.5 §11.1 binding lists.
- **Sample-size threshold integration with cohort target** — plan conflates `target_sample_size` (cohort governance) with `global_confidence_floor_n` (statistical maturity); §5 R3 M2 lock requires DECOUPLED signals.
- **Cohort temporal filter when status was paused** — plan misses `hypothesis_status_history` JOIN for cohort-level "active period" metrics (per §0.5 §11.3 plan §A decision).
- **Hidden-anchor TOCTOU on POST forms** — if Phase 10 introduces any form (e.g., manual snapshot capture), plan must enumerate form-render hidden anchors per Sub-bundle D R3 lesson.
- **HTMX OOB-swap `<tr>`-leading regression** — plan must call out OOB-swap response shape constraints per Bug B 2026-04-29 family.
- **Operator-witnessed verification gate per surface** — plan must enumerate gate surfaces (likely 6-12 surfaces total across all sub-bundles).

### §3.2 Plan task decomposition Codex check

Codex should specifically verify:

- Each new metric in §3 has its own dedicated task or task-cluster (no half-mixed metric work spanning unrelated dashboard surfaces).
- Each new view-model has explicit acceptance criteria (CRUD shapes — actually READ shapes since Phase 10 is read-side; transaction boundary; reject-caller-held-tx for any new write path).
- Each new route handler has explicit gate criteria (operator-witnessed surface + TestClient response shape + DOM verification).
- The shared utility module (§5 honesty policy) has explicit interface contracts that downstream sub-bundles can mock against.
- §0.4 OPEN questions (§8.2 / §8.4 / §8.6 / §11.2-(a)/(b)/(c) / §11.3 V1 supersession) each have a default-disposition surfaced + an orchestrator-decision-pending tag.

### §3.3 RESEARCH-POSTURE preservation discipline

Phase 10 spec was deliberately RESEARCH-POSTURE (no schema / no code / no task decomp). Writing-plans is where research-posture transitions to implementation-decomposition. The Codex chain WILL test whether the plan:

- **Stays inside the spec's metric definitions** — no new metrics added beyond §3; if writing-plans wants to add one, it requires explicit V2.1 §VII.F justification in plan §A.
- **Stays inside the spec's surface sketches** — no new dashboard surfaces beyond §4; same V2.1 §VII.F discipline for additions.
- **Respects the §5 honesty-policy class boundaries** — every metric assigned to exactly one of A/B/C/D; no new classes.
- **Does NOT add schema unless §0.6 verification fails** — default posture is read-side-only.
- **Does NOT re-litigate §8 open questions resolved as "DEFER"** (§8.1, §8.3, §8.5, §8.7 — those are settled per spec).

---

## §4 Return report shape

After Codex chain converges + plan committed on worktree branch, draft a return report at `docs/phase10-writing-plans-return-report.md` (mirroring `docs/phase9-writing-plans-return-report.md` shape):

1. Final HEAD on branch.
2. Commit count breakdown (plan-write + Codex-fix).
3. Codex round chain (e.g., "R1 0/X/Y → R2 ... → Rn NO_NEW_CRITICAL_MAJOR").
4. Plan task decomposition rationale (number of sub-bundles, ordering, cross-bundle dependencies).
5. §8 open-questions disposition + §0.5 binding-decisions disposition (per question/decision: accept-default OR diverge-with-rationale).
6. Codex Major findings ACCEPTED with rationale (if any).
7. §A resolved-during-planning summary (empirical findings discovered during writing-plans).
8. Watch items for orchestrator (anything the orchestrator must lock before executing-plans dispatch).
9. Worktree teardown status (expected ACL-locked husk per Phase 6/7/8/9 pattern).
10. Phase 11 hand-off note candidates surfaced during planning (if any).

---

## §5 First-step paste-ready prompt for the implementer

```
You are taking over to draft the Phase 10 (Metrics Dashboard) implementation plan for swing-trading.

WORKING DIRECTORY (after worktree creation): c:\Users\rwsmy\swing-trading\.worktrees\phase10-writing-plans
BRANCH: phase10-writing-plans
BASELINE_SHA: cd9e266  (per dispatch brief §2.1; HEAD of main BEFORE this brief commit)
WORKTREE-BRANCHING-POINT: current HEAD of main at worktree-creation time (resolve via `git rev-parse main`)

The Codex diff (cd9e266 → worktree HEAD) will include one or more doc-only commits (the dispatch brief + plan + Codex fixes). All harmless; Codex evaluates the PLAN content against the SPEC.

Step 0 — Create the worktree:
  cd c:\Users\rwsmy\swing-trading
  $base = git rev-parse main
  git worktree add .worktrees\phase10-writing-plans -b phase10-writing-plans $base
  New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active

Step 1 — Read the dispatch brief end-to-end from the worktree:
  docs/phase10-writing-plans-dispatch-brief.md

Step 2 — Read the Phase 10 brainstorm spec end-to-end:
  docs/superpowers/specs/2026-05-06-phase10-metrics-design.md
  (641 lines; Codex R1-R5 substantive + R6 confirmation; locked metric definitions + dashboard surfaces + honesty policy + capture-needs feedback)

Step 3 — Read binding conventions + Phase 9 arc-close inputs:
  - CLAUDE.md (gotchas + project conventions; "Lessons captured" + recent gotcha promotions are forward-binding)
  - docs/orchestrator-context.md (orchestrator-role framing; binding conventions)
  - docs/phase3e-todo.md sections "2026-05-12 Phase 9 closer: Sub-bundle E lessons banked + Phase 10 writing-plans hand-off note" (binding inputs §11.1-§11.5)
  - docs/phase9-bundle-{A,B,C,D,E}-return-report.md §7 (watch items) + §10/§11 (hand-off notes) — most carry forward into Phase 10

Step 4 — Verify worktree state:
  git rev-parse HEAD                       # expect current main HEAD (typically the dispatch brief commit)
  git status                               # expect clean
  python -m pytest -m "not slow" -q        # expect worktree-baseline GREEN (~2767 passed, 5 skipped — 4 fixture-absent + 1 Task 7.3; main has 2771/1 because thinkorswim/*.csv fixtures present; 3 pre-existing fails in tests/integration/test_phase8_pipeline_walkthrough.py NOT regressions)
  python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"   # expect 17

Step 5 — Pre-plan recon (orchestrator-applied lessons from Phase 9 arc):
  grep -rn "^def " swing/data/repos/        # enumerate existing repo functions; Phase 10 reads from these
  grep -rn "^def " swing/web/view_models/   # enumerate existing VMs; Phase 10 extends or adds new VMs
  grep -rn "^def " swing/web/routes/        # enumerate existing routes; Phase 10 adds new routes
  grep -rn "with conn:" swing/trades/       # enumerate Phase 7+8+9 transactional services (DO NOT call from inside outer txn if Phase 10 adds new write paths)
  grep -rn "INSERT OR REPLACE\|REPLACE INTO" swing/data/   # confirm zero usage post-Phase-9 (gotcha discipline)
  ls swing/data/migrations/                 # confirm 0017 is current; Phase 10 V1 likely does NOT add 0018
  python -c "from swing.data.repos.risk_policy import get_active_policy; ..."  # spot-check Phase 9 repo interface for plan-task acceptance criteria
  Capture any divergences from the spec's design assumptions; surface in plan §A.

Step 6 — Empirical schema verification (per dispatch brief §0.6):
  For each metric in spec §3, verify the inputs are present in shipped schema (v17):
    grep on column names across swing/data/migrations/*.sql
    spot-check swing/data/models.py for dataclass field coverage
  Lock plan §A finding: Phase 10 V1 introduces ZERO new tables + ZERO ALTERs (default), OR enumerate gap with proposed minimal schema add.

Step 7 — Invoke copowers:writing-plans (the skill wraps superpowers:writing-plans + Codex review):
  - SPEC_PATH: docs/superpowers/specs/2026-05-06-phase10-metrics-design.md
  - PLAN_PATH: docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md
  - BASELINE_SHA: cd9e266

Step 8 — Iterate Codex rounds + land plan-refinement commits until NO_NEW_CRITICAL_MAJOR. Expected 3-6 rounds.

Step 9 — Draft return report at docs/phase10-writing-plans-return-report.md per dispatch brief §4. Commit it.

Step 10 — Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active + signal orchestrator. Orchestrator triages the plan + commissions executing-plans (typically multiple bundles per §1.2 decomposition).

DO NOT:
  - Push to origin from inside the worktree
  - Merge to main (orchestrator action)
  - Use --amend or --no-verify
  - Add Claude co-author footer to commits
  - Skip the marker-file removal before final signal
  - Skip the Step 5 + Step 6 pre-plan grep + schema-verification recon (Phase 9 lesson)
  - Write any code drafts (view-models, routes, templates, queries) — those are executing-plans territory, NOT writing-plans
  - Diverge from spec §3 metric definitions or §4 surface sketches without explicit Codex justification in plan §A
  - Re-litigate spec §1 strategic context (accepted as binding per spec §1.2)
  - Add Schwab API code or auth design (orthogonal to Phase 10 V1 scope; §8.2 references it but plan should NOT scope it)
  - Bundle this with Phase 11+ (Phase 10 ships first per locked sequencing 8 ✓ → 9 ✓ → 10)
  - Add benchmark series capture (§8.3 deferred)
  - Add corporate-actions handling (§8.4 default-defer; orchestrator may override at integration triage)
  - Add `fills.action='add'` enum (§8.1 deferred)
  - Add metric externalization for `process_grade_rolling_N` (§8.5 hardcoded N=10)
  - Add automated decision-criteria evaluation (§8.7 manual text-only)
  - Add new schema (table or ALTER) unless §0.6 verification finds a gap that CANNOT be deferred
```

---

## §6 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-13 (post-Phase-9-arc-close).
- **Brief commit:** `<filled-in-after-commit>`.
- **Brief HEAD context:** `cd9e266` on main (post-Phase-9-arc-close housekeeping + orchestrator handoff brief).
- **Worktree path (binding):** `.worktrees/phase10-writing-plans/`.
- **Baseline test count (main HEAD):** 2771 fast (1 skipped). Worktree-side baseline: 2767 fast (5 skipped — 4 `thinkorswim/*.csv` fixture-absent + 1 Task 7.3 operator-only). 3 pre-existing failures on `tests/integration/test_phase8_pipeline_walkthrough.py` NOT regressions.
- **Baseline ruff count:** 18 (E501 only).
- **Spec status:** Codex R1-R5 substantive + R6 confirmation; shipped 2026-05-06 at `fe6cb45`; 641 lines; LOCKED.
- **Expected plan size:** 1500-2500 lines (Phase 10 has more metric-definitions + dashboard-surfaces than Phase 9's 5-tables-lifecycle scope; comparable plan complexity; Phase 9 plan was 2257 lines).
- **Expected sub-bundle count for executing-plans dispatch:** 4-6 (orchestrator-decision after plan triage).
- **Next per locked sequencing 8 ✓ → 9 ✓ → 10:** Phase 10 plan ships → orchestrator dispatches Sub-bundle A (shared utility module) → ... → Sub-bundle N → Phase 11 (TBD-orchestrator).

---

## §7 Lessons forward-bound from prior dispatches (CRITICAL — DO NOT skip)

Re-emphasized from §0.3 because the Codex chain on Phase 10 writing-plans WILL test whether the plan respects these:

| Lesson | Bundle source | Phase 10 application |
|---|---|---|
| Composition surface enumeration via `^def` grep | Bundle 2+3 + Phase 9 arc | Plan must grep new VM/repo/route signature definitions; not memory-enumerate. |
| Price-independent vs price-dependent advisory split | Bundle 3 | Phase 10 metric surfaces are DB-sourced (NOT PriceCache-dependent); classify accordingly. PROVISIONAL fallback is the analog (snapshot-present vs snapshot-absent). |
| `__post_init__` validator pattern | Bundle 2+3 + Phase 9 A | If new metric-config dataclass exposed (e.g., per-cohort filter config), apply pattern. |
| Service-layer `with conn:` opens its own transaction | Phase 8 + Phase 9 arc | Plan MUST enumerate transaction-ownership contract per new write-side service (if any); reject-caller-held-tx for single-transaction services. |
| `executescript()` discipline | Phase 7 hotfix | Plan inherits via `swing/data/db.py:_apply_migration`; no carve-out (Phase 10 V1 likely no new migration). |
| `INSERT OR REPLACE` is DELETE+INSERT not UPDATE | Phase 8 gotcha 2026-05-06 | Append-only / FK-referenced tables MUST use INSERT + SELECT-then-UPDATE-or-INSERT. Applies to any new write path. |
| Session-anchor read/write mismatch | Phase 8 polish bundle 2026-05-09 | Plan must enumerate `last_completed_session(now)` vs `action_session_for_run(now)` per session-keyed query. Metric "asof_date" semantics MUST be locked per surface. |
| Server-stamping hidden audit fields | Phase 8 R2.M2 + R3.M2 + R4.M2 | Any new form (e.g., manual snapshot capture per §8.2 if elected): created_at + session anchor MUST be server-stamped. |
| Form-render hidden anchors round-trip through soft-warn confirm | Phase 9 Sub-bundle D R3 | Any new form-driven write path with soft-warn fragment MUST include all hidden anchors in the `form_values` dict. |
| POST-time recompute of "latest-of-something" creates TOCTOU | Phase 9 Sub-bundle D R2 | Any form-render hidden-anchor design MUST be form-render-emitted, NOT POST-time recompute. |
| Test fixtures: USERPROFILE + HOME monkeypatch | Phase 9 Sub-bundle A R1 | Any new test that exercises `write_user_overrides` (e.g., updating metric-config defaults) MUST monkeypatch both env vars. |
| HTMX browser-only failure surfaces | Phase 5/6/Phase 9 D family | Each new HTMX surface requires operator-witnessed gate; TestClient passes are necessary but not sufficient. Plan §A enumerates per-surface gate. |
| `<tr>`-leading HTMX response triggers `makeFragment` | Bug B 2026-04-29 | Plan's OOB-swap partials must keep primary content table-row-free. |
| Matplotlib mathtext fires on `$ ^ _ \` | commit `29c93f5` | §4.8 process-grade-trend chart (if matplotlib-rendered): visual verification non-optional; string-equality test insufficient. |
| Migration filename collision check | Phase 8/9 plan §A | Plan §A MUST verify Phase 10 V1 does NOT add a migration (default); if it does, filename `0018_*` matches `EXPECTED_SCHEMA_VERSION = 17 → 18`. |
| Empirical-verification of brief assertions | Phase 9 Sub-bundle C R1 M#1 | Plan must verify spec metric definitions against current code before locking task acceptance criteria. |

All of these are FAILURE-MODE-CATALOGUED. The Codex chain will catch any plan omission against this list; the implementer's pre-plan grep + schema-verification recon (Step 5 + Step 6) is the structural defense.

---

## §8 Phase 10 design questions surfaced for orchestrator-decision (banked in plan §A)

Per §0.4 + §0.5, the following OPEN questions sit at orchestrator-decision-pending state at writing-plans time. Writing-plans should lock a default disposition + flag for integration-triage:

1. **§8.2 — Web-form manual snapshot capture surface in Phase 10 V1?** Default: NO (CLI-only). Operator may elect at integration triage. Cost: +1 task, +1 HTMX gate-surface, ~30min impl.
2. **§8.4 — Corporate_Actions MVP in Phase 10 V1?** Default: DEFER. Operator may elect at integration triage. Cost: +1 table, +1 CLI surface, +1 manual-reconcile flow, ~3-6hr impl.
3. **§8.6 — Surface `lucky_violation_R` on Phase 6 review form in Phase 10 V1?** Default: DEFER (standalone small follow-up). Operator may elect bundling with Phase 10 Sub-bundle B (which owns the review-derived metrics). Cost: +1 task in Sub-bundle B, ~1hr impl.
4. **§11.2(a) — Reconciliation "N unresolved material discrepancies" badge on dashboard in Phase 10 V1?** Default: YES in Sub-bundle E (polish). Operator may elect deferral.
5. **§11.2(b)+(c) — Per-trade discrepancy indicator + per-cohort discrepancy filter in Phase 10 V1?** Default: DEFER to Phase 10+ follow-up. Operator may elect inclusion (+2 surfaces).
6. **§11.3 V1 supersession — Full transition history on hypothesis-progress card?** Default: YES (Phase 9 closed the gap). Operator may elect spec-V1-respecting "latest transition only".
7. **§0.5 §11.4 dynamic PROVISIONAL badge contract** — Lock as "PROVISIONAL when fallback hit; LIVE when snapshot covers asof_date". Default: YES. Spec §2 split-policy compatible.

These are NOT writing-plans blockers. Plan §A documents each + recommends the default. Operator-decision at integration-triage of the plan.

---

## §9 Sequencing — what comes after Phase 10

Per locked sequencing 8 ✓ → 9 ✓ → 10 (this dispatch) → 11 (TBD).

Phase 11 candidates banked in `docs/phase3e-todo.md` (orchestrator-paced):

1. **Schwab API Phase A** — broker integration; replaces TOS-CSV reconciliation primary path with live API + `account_equity_snapshots` populated from broker authority. Sequenced after Phase 10 V1 ships per phase3e-todo 2026-05-04 entry.
2. **Schwab "since-inception" Account Statement ingestion** (V2 candidate banked 2026-05-12) — could backfill `cash_movements` + `account_equity_snapshots` historical series + reconcile fills.
3. **`account_equity_snapshots.equity_dollars` semantic formalization** (V2 candidate banked 2026-05-12) — cash-basis vs net-liq disambiguator.
4. **2 spec amendments pending V2.1 §VII.F routing** — Phase 9 Sub-bundle D §7 (chart_pattern-mirror hidden-anchor) + Sub-bundle E §6.2 (multi-line parser). Could land via spec amendment OR defer.

Phase 10 writing-plans MUST NOT scope any of these. Plan §10 (Phase 11 hand-off) drafts a fresh hand-off note enumerating Phase 10 capture-needs (if any) for downstream phases — analogous to Phase 9's spec §11 / Phase 8's hand-off block.
