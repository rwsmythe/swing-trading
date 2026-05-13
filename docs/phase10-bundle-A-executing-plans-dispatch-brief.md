# Phase 10 Sub-bundle A — executing-plans dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Phase 10 Sub-bundle A per plan §D (Tasks T-A.0..T-A.9 + T-A.7.1) on an isolated worktree branch via `copowers:executing-plans` (wraps `superpowers:subagent-driven-development` + adversarial Codex MCP review). Sub-bundle A is the **foundational cross-bundle dependency** — `swing/metrics/honesty.py` + `BaseLayoutVM` mixin + `swing/metrics/discrepancies.py:count_unresolved_material` are the interface contracts that Sub-bundles B/C/D/E all consume.

**Expected duration:** ~6-9 hr executing-plans wall-clock + ~2-4 hr Codex convergence. Phase 10 Sub-bundle A has 10 tasks but each is small (5 modules + 1 index page + 1 regression test + 1 integration sweep); estimated 3-5 Codex rounds (matches Phase 9 Sub-bundle A precedent of 5 rounds; Phase 10 has zero schema work which removes one common round of fixes).

---

## §0 Inputs

### §0.1 Plan
- **PLAN_PATH:** `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`
- **Plan status:** Codex R1-R6 → NO_NEW_CRITICAL_MAJOR (operator override past MAX_ROUNDS=5); shipped 2026-05-13 at `a34c00d`; 2008 lines; LOCKED.
- **Sub-bundle A scope:** plan §D (lines 740-1042); 10 tasks (T-A.0..T-A.9 + T-A.7.1 inserted after T-A.7).
- **Cross-bundle invariants:** plan §I (lines 1665-1727); 15 invariants — §I.1-§I.15. Sub-bundle A satisfies §I.1 (schema posture) + §I.2 (module placement) + §I.5 (BaseLayoutVM mixin) by-construction; sets the interface for §I.3 (risk_policy split) + §I.4 (PROVISIONAL/LIVE) + §I.8 (decoupling discipline) + §I.14 (empty-cohort rendering); all 15 invariants forward-bind to B/C/D/E.

### §0.2 Electives amendment
- **AMENDMENT_PATH:** `docs/phase10-electives-amendment.md`
- **Amendment status:** SHIPPED 2026-05-13 at `9525f17`; NORMATIVE supplement to plan §A.4 + §E + §F + §H.
- **Sub-bundle A impact:** ZERO. None of the 4 elected tasks (T-B.7, T-C.5, T-E.5, T-E.6) touch Sub-bundle A scope. §8.4 Corporate_Actions MVP defers as standalone post-Phase-10 dispatch. The amendment is informational for Sub-bundle A; do NOT scope any elective tasks into this dispatch.

### §0.3 Spec
- **SPEC_PATH:** `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md`
- **Spec status:** Codex R1-R5 substantive + R6 confirmation; SHIPPED 2026-05-06 at `fe6cb45`; 641 lines; RESEARCH-POSTURE (NO schema, NO code, NO task decomp).
- **Sub-bundle A spec coverage:** §5 honesty policy (Task A.1 implements §A.7 interface); §2 vocabulary + denominator split-policy (Task A.2 + Task A.3 implement §A.5 + §A.6); §4.9 cross-cutting surface conventions (Task A.6 + Task A.8 implement BaseLayoutVM + index page); §3.10 operator-actionability (locked at plan §A.16 + applied in B/C/D/E).

### §0.4 Project state at dispatch time
- **HEAD on `main`:** `9525f17` (post-electives-amendment housekeeping).
- **Test count (main):** 2771 fast passing + 1 skipped + 3 pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py` failures NOT regressions.
- **Test count (worktree-side):** **2767 fast passing + 5 skipped** (4 fixture-absent for `thinkorswim/*.csv` not in worktree + 1 Task 7.3 operator-only). This is the baseline the implementer will see.
- **Ruff baseline:** **18 (E501 only).** Unchanged across the entire Phase 9 arc.
- **Schema version:** **v17.** Locked since Phase 9 Sub-bundle A `6c8f3a9` 2026-05-12. **Phase 10 V1 INTRODUCES ZERO SCHEMA CHANGES** per plan §A.0 + §I.1 LOCK. `EXPECTED_SCHEMA_VERSION` stays at 17. NO `0018_*.sql` migration in Sub-bundle A (or any other Phase 10 V1 sub-bundle).

### §0.5 Phase 9 arc forward-binding lessons (BINDING for Sub-bundle A)

The following Codex-caught lessons banked at `CLAUDE.md` "Gotchas" + `docs/orchestrator-context.md` "Lessons captured" are forward-binding for Sub-bundle A. Pre-empt at acceptance-criteria time, NOT at Codex-round-fix time:

1. **`__post_init__` validator pattern on all new dataclasses** (Phase 9 A+B+C+D+E lock). Sub-bundle A introduces `WilsonCI`, `BootstrapCI`, `SuppressedMetric`, `HonestyBadges`, `BaseLayoutVM`, `ConfidenceBadgeVM`, `ProvisionalBadgeVM`, `SuppressionRowVM`, `MetricsIndexVM`. Each MUST have `__post_init__` rejecting NaN/inf on float fields + invariant assertions (e.g., `WilsonCI.__post_init__` asserts `lower ≤ point ≤ upper`).

2. **Service-layer transaction discipline** (Phase 8 + Phase 9 lock). Sub-bundle A has ZERO new write paths (read-only module foundation). §I.11 by-construction satisfied. Lock applies forward to Sub-bundle E's T-E.5 if §8.2 election survives (it does per electives amendment).

3. **NO `INSERT OR REPLACE`** (Phase 8 + 9 lock). §I.9 by-construction satisfied at Sub-bundle A (no writes).

4. **Server-stamping discipline at handler entry** (Phase 8 lock). §I.12 by-construction satisfied at Sub-bundle A (no forms). Lock applies forward to Sub-bundle E's T-E.5.

5. **Composition-surface enumeration via `^def` grep, NOT memory-enumerate** (Phase 9 lock). Sub-bundle A interface contracts (§A.7) are consumed by B/C/D/E at specific call sites. When acceptance-criteria-checking, use `grep -rn "^def " swing/metrics/` to enumerate the actual function definitions, NOT memory.

6. **Empirical-verification of brief assertions about column-vs-derived state** (Phase 9 Sub-bundle C R1 M#1 precedent). Before locking any acceptance-criteria value, re-grep against current code; do NOT memory-summarize.

7. **Form-render hidden anchors round-trip** (Phase 9 D R3 lock). By-construction satisfied at Sub-bundle A (no forms).

8. **POST-time recompute TOCTOU** (Phase 9 D R2 lock). By-construction satisfied at Sub-bundle A.

9. **Test fixtures `USERPROFILE+HOME` monkeypatch** (Phase 9 A R1 incident). By-construction satisfied at Sub-bundle A (tests do NOT exercise `swing/config_user.py:write_user_overrides`). Lock applies forward to ALL tests authored in B/C/D/E IF they touch user-config writes (none expected per plan §I.10).

10. **HTMX browser-only failure surfaces** (Phase 5/6/Phase 9 D family). Sub-bundle A's T-A.8 `/metrics` index page is a static-rendered HTML route — NO HTMX OOB-swap, NO HX-Redirect, NO embedded forms (per plan §A.9 + §I.6 LOCK). Operator-witnessed gate surface S3 verifies the static render works in browser.

11. **`<tr>`-leading HTMX response** (Bug B 2026-04-29). By-construction satisfied at Sub-bundle A (no `<tr>` at any fragment root).

12. **matplotlib mathtext** (commit `29c93f5`). By-construction satisfied at Sub-bundle A (no chart rendering).

13. **`base.html.j2` shared fields require adding to EVERY base-layout VM** (CLAUDE.md gotcha — Phase 3c + 3d + Phase 10 §A.18 precedent). **Sub-bundle A's T-A.6 + T-A.7 ESTABLISH the discipline** by introducing `BaseLayoutVM` mixin with `unresolved_material_discrepancies_count` field. The discriminating regression test at T-A.7 (`test_existing_dashboard_vm_has_unresolved_material_field`) is SKIPPED at Sub-bundle A landing (Phase 10 has not yet retrofit the 6 existing base-layout VMs — that lands at T-E.3). Mark the test as `@pytest.mark.skip(reason="Sub-bundle E T-E.3 adds DashboardVM/PipelineVM/JournalVM/WatchlistVM/ConfigVM/PageErrorVM field per §A.18")`. **The skip is the cross-bundle pin** — Sub-bundle E's T-E.3 un-skips + verifies pass. Sub-bundle A landing leaves the skip in place.

14. **Session-anchor read/write predicate alignment** (Phase 8 polish bundle 2026-05-09 + Phase 10 §A.15 lock). By-construction satisfied at Sub-bundle A (no session-keyed reads; Task A.3 equity_resolver is anchor-agnostic — callers in Sub-bundle D pass the anchor).

15. **Discriminating-test arithmetic** (operator preference + Phase 9 forward-binding). Every acceptance criterion test must distinguish the correct behavior from a plausible bug. Plan §D acceptance criteria already enumerate these; ensure each test fails under the inverted/buggy implementation.

### §0.6 Sub-bundle A scope-summary (per plan §D)

| Task | Files | Acceptance | Test count est. |
|---|---|---|---:|
| **T-A.0** module skeleton | Create `swing/metrics/__init__.py` + 12 empty submodules + `swing/web/view_models/metrics/__init__.py` + `swing/web/view_models/metrics/shared.py` placeholder. | Skeleton import smoke test passes. | 0 |
| **T-A.1** honesty utility | Full `swing/metrics/honesty.py` + `tests/metrics/test_honesty.py`. Implements §A.7 interface verbatim. | Wilson CI matches reference values; bootstrap deterministic with seed; suppression dispatcher honors `policy.global_confidence_floor_n`; §5.1/§5.2/§5.3/§5.4 class dispatchers covered. | ~12-15 |
| **T-A.2** risk_policy resolver | Full `swing/metrics/policy.py` + `tests/metrics/test_policy.py`. | LIVE-policy reader + AT-TRADE-TIME reader + NULL-stamp fallback returning `(policy, bool)` flag for legacy. | ~4-6 |
| **T-A.3** equity resolver | Full `swing/metrics/equity_resolver.py` + `tests/metrics/test_equity_resolver.py`. | `resolve_live_capital_denominator_dollars` returns `(value, "LIVE"\|"PROVISIONAL")`; PROVISIONAL fallback to `at_trade_time_policy.capital_floor_constant_dollars`. | ~5-6 |
| **T-A.4** cohort filter | Full `swing/metrics/cohort.py` + `tests/metrics/test_cohort.py`. | `list_trades_for_cohort` + `list_closed_trades_for_cohort` + `count_per_cohort`; canonicalization via `swing.trades.entry.canonicalize_hypothesis_label`. | ~5-7 |
| **T-A.5** rolling-N helper | Full `swing/metrics/rolling.py` + `tests/metrics/test_rolling.py`. | `rolling_window_samples` + `rolling_mean_series` with `min_n_for_mean=3` suppression; HARDCODED `N=10` is NOT enforced here (generic helper). | ~3-5 |
| **T-A.6** BaseLayoutVM + shared dataclasses | Full `swing/web/view_models/metrics/shared.py` + `tests/web/test_view_models/test_metrics_shared_vms.py`. | `BaseLayoutVM` with 5 base-layout fields + `unresolved_material_discrepancies_count` field (Codex R2 Major #6 restructure); `ConfidenceBadgeVM`, `ProvisionalBadgeVM`, `SuppressionRowVM`; `__post_init__` validators. | ~4-5 |
| **T-A.7** base-layout VM coverage regression | Create `tests/web/test_view_models/test_base_layout_vm_coverage.py`. | `test_all_metrics_vms_have_base_layout_fields` enumerates via `pkgutil.iter_modules`; `test_existing_dashboard_vm_has_unresolved_material_field` is SKIPPED (un-skipped at T-E.3). | ~2 |
| **T-A.7.1** discrepancies helper | Full `swing/metrics/discrepancies.py` + `tests/metrics/test_discrepancies.py`. | `count_unresolved_material(conn)` thin wrapper over Phase 9 helpers; read-only. | ~4 |
| **T-A.8** metrics index page | `swing/web/view_models/metrics/index.py` + `swing/web/routes/metrics.py` + `swing/web/templates/metrics/index.html.j2` + register router in `swing/web/app.py` + `tests/web/test_routes/test_metrics_routes.py`. | `MetricsIndexVM` extends `BaseLayoutVM`; populates `unresolved_material_discrepancies_count` per §A.18. Route `GET /metrics` returns 200 + 8-tile navigator. | ~3 |
| **T-A.9** integration sweep | Create `verify_phase10.py` at worktree root (per §J.2); ruff sweep + fix any new issues. | `python verify_phase10.py` exits 0; `python -m pytest -m "not slow" -q` GREEN at ~2802..2822 fast tests; ruff baseline UNCHANGED at 18. | 0 |

**Projected test count delta: +35..+55 fast tests** (per plan §D Task A.9 acceptance). Post-A baseline: ~2802..2822 worktree-side.

### §0.7 Verify_phase10.py contract (per plan §J.2)

This is referenced in plan §J.2; the implementer reads + reproduces the spec from there. Sub-bundle A's T-A.9 lands the initial version; subsequent sub-bundles extend with their own sanity grep checks. The script is the cross-platform Python equivalent of a bash-based verify script; runs from worktree root.

---

## §1 Worktree + binding conventions

### §1.1 Worktree
- **Branch:** `phase10-bundle-A-shared-honesty-utility`
- **Worktree directory:** `.worktrees/phase10-bundle-A-shared-honesty-utility/`
- **BASELINE_SHA:** `9525f17` (current main HEAD; post-electives-amendment housekeeping).
- **Worktree branching point:** current HEAD of `main` at worktree-creation time (resolve via `git rev-parse main`; expected the brief commit SHA after this brief lands).

### §1.2 Marker-file workflow
- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all task commits land + Codex chain converges + before final return-report commit: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits
- Conventional prefixes per plan §D suggested commit shapes (`feat(metrics): ...`, `test(metrics): ...`, `chore(metrics): ...`).
- One commit per task per plan §D pattern; Codex-fix commits as `fix(phase10-bundle-A): Codex RN <severity> #N — <description>`.
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.

### §1.4 Branch isolation + ownership
- Commits on branch only; no push to origin from worktree.
- **Implementer (you) owns:** copowers:executing-plans invocation → task-by-task TDD → Codex iteration → return-report commit.
- **Orchestrator owns:** plan-triage at dispatch time + integration merge to main + Sub-bundle B dispatch commissioning post-A-ship.

### §1.5 Verify command (basic; copowers:executing-plans handles full task execution + Codex review)
```powershell
# After all tasks land + Codex chain converges:
git log --oneline HEAD~15..HEAD
python -m pytest -m "not slow" -q
ruff check swing/ --statistics
python verify_phase10.py
```

---

## §2 Operator-witnessed verification gate (Sub-bundle A)

Per plan §D Task A.9 + §I.15 BINDING + dispatch brief §0.4:

| # | Surface | Type | Acceptance |
|---|---|---|---|
| **S1** | pytest fast-suite | Inline | `python -m pytest -m "not slow" -q` GREEN at ~2802..2822 fast tests (worktree-side); 3 pre-existing `test_phase8_pipeline_walkthrough.py` failures unchanged (NOT regressions). |
| **S2** | Import smoke | Inline | `python -c "from swing import metrics; from swing.metrics import honesty, policy, equity_resolver, cohort, rolling, funnel, process, capital, maturity, tier, process_grade_trend, discrepancies"` clean import. |
| **S3** | `/metrics` index | **Browser (operator-witnessed)** | `swing web` → navigate to `http://127.0.0.1:8080/metrics` → confirm: (a) page renders 200 (not 500); (b) 8-tile navigator visible with surface labels matching plan §A.3 endpoint table; (c) base.html.j2 header + footer integration intact (logo + nav + dark-theme toggle); (d) no console errors; (e) `<a>` link to each surface present (even though 7 of 8 are 404 at Sub-bundle A landing — operator confirms link is correct, NOT that the destination renders). |
| **S4** | ruff baseline | Inline | `ruff check swing/ --statistics` reports 18 E501 unchanged. |
| **S5** | verify_phase10.py | Inline | `python verify_phase10.py` exits 0. |

**Gate session ≤ 6 surfaces budget (dispatch brief §1.3):** Sub-bundle A has 5 surfaces but 4 are inline (implementer-runs-immediately; operator sees pass-confirmation); only S3 requires the operator to drive a browser session. Fits well within budget.

**S3 specifics for the implementer:** Sub-bundle A lands the `/metrics` index navigator. The 8 tile-link destinations (`/metrics/trade-process`, `/metrics/hypothesis-progress`, `/metrics/tier-comparison`, `/metrics/capital-friction`, `/metrics/maturity-stage`, `/metrics/identification-funnel`, `/metrics/deviation-outcome`, `/metrics/process-grade-trend`) are NOT registered routes until Sub-bundles B/C/D/E land. Operator's S3 gate confirms the index renders + links exist; clicking any tile is EXPECTED to 404 at Sub-bundle A landing. This is a non-issue for the gate.

---

## §3 Skill posture + adversarial review

- **Invoke `copowers:executing-plans`** (NOT `superpowers:executing-plans` or `superpowers:subagent-driven-development` directly — the copowers wrapper handles Codex review automatically after task commits land).
- Skill inputs:
  - `PLAN_PATH=docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`
  - `SUB_BUNDLE=A` (Tasks T-A.0..T-A.9 + T-A.7.1)
  - `BASELINE_SHA=9525f17`
- **Expected Codex chain:** 3-5 rounds (Phase 9 Sub-bundle A precedent: 5 rounds; Phase 10 has zero schema work + smaller scope, expected slightly faster).
- Iterate per-round fixes as `fix(phase10-bundle-A): Codex RN <severity> #N — ...` commits.
- Terminate at NO_NEW_CRITICAL_MAJOR.

### §3.1 Codex value-add concentration

Adversarial review for Sub-bundle A typically catches:

- **`__post_init__` validator coverage gaps** — Codex will check each new dataclass for NaN/inf rejection + invariant assertion. Pre-empt by enumerating every dataclass in `swing/metrics/` + `swing/web/view_models/metrics/shared.py` + `swing/web/view_models/metrics/index.py` and confirming validator coverage.

- **§A.7 interface drift** — Codex will compare actual signatures in `swing/metrics/honesty.py` against §A.7 specification. Subagent-discipline: copy the §A.7 block verbatim into the implementation; do NOT paraphrase parameter names or return types.

- **§A.18 cross-bundle pin** — Codex will check that `MetricsIndexVM` constructor populates `unresolved_material_discrepancies_count=count_unresolved_material(conn)` (NOT deferred to E). Pre-empt by ensuring `MetricsIndexVM` is built via a factory function that takes `conn` + populates the field eagerly.

- **Skip-marker on `test_existing_dashboard_vm_has_unresolved_material_field`** — Codex may flag the skip as incomplete coverage. Defense: the test IS the cross-bundle pin; the reason-string explains the un-skip schedule. If Codex flags this, point to plan §A.7 + §A.18 + return-report §6 for the un-skip pattern.

- **§I.6 HTMX-discipline at T-A.8** — Codex will check that `/metrics` index page is pure server-rendered (no HTMX OOB-swap; no embedded forms). Pre-empt by NOT importing `htmx` JS bundle on the index page (base.html.j2 already does the global include — confirm the index template doesn't add a second).

- **§A.4.1 helper canonicalization** — Codex will check `list_trades_for_cohort` uses `swing.trades.entry.canonicalize_hypothesis_label` (existing helper) for label-matching, NOT a custom lowercase-and-strip. Re-grep before locking the implementation.

- **§A.5 NULL-stamp fallback semantics** — Codex will verify `read_at_trade_time_policy` returns `(policy, True)` flag on NULL stamp + `(policy, False)` when stamp resolves. The bool is the `[legacy: pre-Phase-9 trade]` annotation flag downstream surfaces use.

- **§I.13 session-anchor matrix** — Codex may check `equity_resolver` is anchor-agnostic (caller-supplied `asof_date`). Pre-empt: the helper signature takes `asof_date: date` as a parameter — no `datetime.now()` calls inside.

- **§A.16 empty-cohort rendering coverage** — Codex may check the `count_per_cohort` helper handles n=0 cohorts gracefully (returns the cohort with count=0, NOT omits). Pre-empt by seeding empty `trades` table + 4 `hypothesis_registry` rows + asserting `{name: 0}` for all 4.

### §3.2 Per-task Codex-check pre-emption

| Task | Common Codex finding | Pre-emption |
|---|---|---|
| T-A.0 | None expected (pure scaffolding) | Skeleton imports without circular references. |
| T-A.1 | Wilson CI off-by-one on edge cases (k=0 or k=n) | Test the asymmetric Wilson bounds for k=0,n=20 + k=20,n=20 explicitly. |
| T-A.2 | NULL stamp fallback returns wrong flag | Test both NULL and orphan-id (stamp=999) cases return `(policy, True)`. |
| T-A.3 | Anchor coupling to `datetime.now()` | Helper signature MUST take `asof_date` parameter; no internal `now()` call. |
| T-A.4 | Label canonicalization missing | Reuse `swing.trades.entry.canonicalize_hypothesis_label` (existing helper). |
| T-A.5 | `effective_n<3` suppression off-by-one | `min_n_for_mean=3` constant; test `samples=[1,2]` returns None for both windows. |
| T-A.6 | BaseLayoutVM field mismatch with existing `DashboardVM` field-set | Re-grep `DashboardVM` definition + match field names exactly. |
| T-A.7 | Skip-reason string drift from un-skip schedule | Reason string explicitly names Task E.3 as the un-skip point. |
| T-A.7.1 | Helper not read-only / opens own transaction | NO `with conn:` block in helper; pure SELECT. |
| T-A.8 | `MetricsIndexVM` constructor signature inconsistent with §A.18 | Factory function takes `conn` + builds VM with field populated. |
| T-A.9 | verify_phase10.py path semantics on Windows | Use `pathlib.Path` for path arithmetic; test on Windows-style paths. |

---

## §4 Return report shape

After all task commits land + Codex chain converges + before final return-report commit, draft a return report at `docs/phase10-bundle-A-return-report.md` (mirroring `docs/phase9-bundle-A-return-report.md` shape):

1. Final HEAD on branch + commit count breakdown (task-impl + Codex-fix).
2. Codex round chain (e.g., "R1 0/X/Y → R2 ... → Rn NO_NEW_CRITICAL_MAJOR").
3. Test count delta + ruff baseline delta.
4. Operator-witnessed verification surfaces (PENDING orchestrator-driven gate; S1+S2+S4+S5 inline OK; S3 PENDING).
5. Per-task deviations from the plan (if any) with rationale.
6. Codex Major findings ACCEPTED with rationale (if any).
7. Watch items for orchestrator (cross-bundle pins; un-skip-at-E reminders; any V2 candidates banked).
8. Worktree teardown status (expected ACL-locked husk per Phase 6/7/8/9 pattern; will be the 10th husk pending operator cleanup-script).
9. Sub-bundle B forward-binding lessons (if any new ones surfaced during executing-plans).
10. Composition-surface verification via `^def` grep (per Phase 9 forward-binding lesson §0.5 #5).

---

## §5 First-step paste-ready prompt for the implementer

```
You are taking over to implement Phase 10 Sub-bundle A (shared honesty utility + metric infrastructure) for swing-trading.

WORKING DIRECTORY (after worktree creation): c:\Users\rwsmy\swing-trading\.worktrees\phase10-bundle-A-shared-honesty-utility
BRANCH: phase10-bundle-A-shared-honesty-utility
BASELINE_SHA: 9525f17  (per dispatch brief §1.1; HEAD of main BEFORE this brief commit)
WORKTREE-BRANCHING-POINT: current HEAD of main at worktree-creation time (resolve via `git rev-parse main`)

The Codex diff (9525f17 → worktree HEAD) will include one or more doc-only commits (the dispatch brief + per-task code + Codex fixes). All harmless; Codex evaluates the CODE content against the PLAN §D.

Step 0 — Create the worktree:
  cd c:\Users\rwsmy\swing-trading
  $base = git rev-parse main
  git worktree add .worktrees\phase10-bundle-A-shared-honesty-utility -b phase10-bundle-A-shared-honesty-utility $base
  New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active

Step 1 — Read the dispatch brief end-to-end from the worktree:
  docs/phase10-bundle-A-executing-plans-dispatch-brief.md

Step 2 — Read the Phase 10 plan §D end-to-end + the cross-bundle invariants §I:
  docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md  (§D for tasks T-A.0..T-A.9 + T-A.7.1; §I for invariants; §A.7 for honesty interface; §B for file map)

Step 3 — Read the Phase 10 brainstorm spec for §5 honesty policy reference:
  docs/superpowers/specs/2026-05-06-phase10-metrics-design.md  (§5 honesty policy + §3 metric inventory + §4.9 surface conventions)

Step 4 — Read binding conventions + forward-binding lessons:
  - CLAUDE.md (gotchas + project conventions; "Lessons captured" + Phase 9 arc gotcha promotions are forward-binding)
  - docs/orchestrator-context.md (orchestrator-role framing; Codex-driven discipline)
  - docs/phase10-electives-amendment.md (informational only; ZERO Sub-bundle A impact)

Step 5 — Verify worktree state:
  git rev-parse HEAD                       # expect current main HEAD (typically the dispatch brief commit)
  git status                               # expect clean
  python -m pytest -m "not slow" -q        # expect baseline GREEN (~2767 passed, 5 skipped — 4 fixture-absent + 1 Task 7.3; 3 pre-existing fails in tests/integration/test_phase8_pipeline_walkthrough.py NOT regressions)
  python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"  # expect 17
  ruff check swing/ --statistics            # expect 18 E501

Step 6 — Pre-implementation recon (Phase 9 arc forward-binding lessons):
  grep -rn "^def " swing/data/repos/risk_policy.py swing/data/repos/account_equity_snapshots.py swing/data/repos/hypothesis_status_history.py swing/data/repos/reconciliation.py
  grep -rn "^def " swing/trades/review.py swing/trades/equity.py swing/trades/derived_metrics.py
  grep -rn "^def canonicalize_hypothesis_label" swing/trades/
  cat swing/data/migrations/0017_phase9_risk_policy_and_reconciliation.sql | head -100
  python -c "from swing.data.repos.risk_policy import get_active_policy, get_policy_by_id; print('repo OK')"
  python -c "from swing.data.models import RiskPolicy; import dataclasses; print(len(dataclasses.fields(RiskPolicy)), 'fields')"  # expect 34

Step 7 — Invoke copowers:executing-plans (the skill wraps superpowers:subagent-driven-development + Codex review):
  - PLAN_PATH: docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md
  - SUB_BUNDLE: A
  - BASELINE_SHA: 9525f17

Step 8 — Execute tasks task-by-task per plan §D:
  - T-A.0 module skeleton (commit: feat(metrics): scaffold swing/metrics module skeleton)
  - T-A.1 honesty utility (commit: feat(metrics): honesty utility — Wilson CI + bootstrap CI + suppression dispatcher)
  - T-A.2 risk_policy resolver (commit: feat(metrics): risk_policy LIVE vs AT-TRADE-TIME resolver split)
  - T-A.3 equity resolver (commit: feat(metrics): live_capital_denominator_dollars resolver — PROVISIONAL/LIVE contract)
  - T-A.4 cohort filter (commit: feat(metrics): per-hypothesis-cohort filter + aggregation helper)
  - T-A.5 rolling-N helper (commit: feat(metrics): rolling-N window helper)
  - T-A.6 BaseLayoutVM + shared dataclasses (commit: feat(metrics): BaseLayoutVM mixin + shared badge dataclasses)
  - T-A.7 base-layout VM coverage regression (commit: test(metrics): base-layout VM coverage regression)
  - T-A.7.1 discrepancies helper (commit: feat(metrics): discrepancies helper — count_unresolved_material)
  - T-A.8 metrics index page (commit: feat(metrics): metrics index page — GET /metrics navigator)
  - T-A.9 integration sweep (commit: chore(metrics): Sub-bundle A integration sweep + verify_phase10.py)

Step 9 — Iterate Codex rounds + land per-round-fix commits until NO_NEW_CRITICAL_MAJOR. Expected 3-5 rounds.

Step 10 — Draft return report at docs/phase10-bundle-A-return-report.md per dispatch brief §4. Commit it.

Step 11 — Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active + signal orchestrator. Orchestrator drives operator-witnessed gate (S3 browser surface) + integration merge.

DO NOT:
  - Push to origin from inside the worktree
  - Merge to main (orchestrator action)
  - Use --amend or --no-verify
  - Add Claude co-author footer to commits
  - Skip the marker-file removal before final signal
  - Skip the Step 6 pre-implementation grep recon (Phase 9 forward-binding lesson)
  - Add ANY new schema (no `0018_*.sql` migration; no ALTER on existing tables); Phase 10 V1 §A.0 LOCK is BINDING per plan §I.1
  - Skip `__post_init__` validators on any new dataclass (Phase 9 forward-binding lesson §0.5 #1)
  - Implement honesty.py with paraphrased signatures — copy §A.7 verbatim (avoids Codex interface-drift findings)
  - Un-skip `test_existing_dashboard_vm_has_unresolved_material_field` (that's Task E.3's responsibility per §I.5)
  - Add HTMX OOB-swap, embedded forms, or HX-Redirect on `/metrics` index page (§I.6 LOCK)
  - Add chart rendering via matplotlib (§A.10 V1 LOCK = inline SVG in Sub-bundle E; Sub-bundle A has no charts)
  - Implement per-surface routes other than `/metrics` (those land in B/C/D/E per plan §A.3)
  - Implement Sub-bundle B/C/D/E task scope (out of A's lane)
  - Implement any of the 4 elective tasks (T-B.7, T-C.5, T-E.5, T-E.6) — those land in their respective sub-bundles per electives amendment
  - Implement §8.4 Corporate_Actions MVP (deferred as standalone post-Phase-10 dispatch per electives amendment §5)
  - Bundle this with Sub-bundle B (sequencing locked A → B → C → D → E per plan §C)
```

---

## §6 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-13 (post-electives-amendment).
- **Brief commit:** `<filled-in-after-commit>`.
- **Brief HEAD context:** `9525f17` on main (post-electives-amendment housekeeping).
- **Worktree path (binding):** `.worktrees/phase10-bundle-A-shared-honesty-utility/`.
- **Baseline test count (worktree-side):** 2767 fast (5 skipped — 4 fixture-absent + 1 Task 7.3); 3 pre-existing failures on `tests/integration/test_phase8_pipeline_walkthrough.py` NOT regressions.
- **Baseline test count (main HEAD):** 2771 fast (1 skipped).
- **Baseline ruff count:** 18 (E501 only).
- **Plan status:** Codex R1-R6 NO_NEW_CRITICAL_MAJOR; shipped 2026-05-13 at `a34c00d`; 2008 lines; LOCKED.
- **Spec status:** Codex R1-R5 substantive + R6 confirmation; shipped 2026-05-06 at `fe6cb45`; 641 lines; LOCKED.
- **Electives amendment status:** SHIPPED 2026-05-13 at `9525f17`; NORMATIVE; Sub-bundle A unaffected (ZERO new tasks).
- **Expected dispatch wall-clock:** ~6-9 hr executing-plans + ~2-4 hr Codex convergence.
- **Expected test count delta:** +35..+55 fast tests; post-A ~2802..2822 worktree-side.
- **Expected ruff delta:** 0 (baseline preserved).
- **Next per locked sequencing 8 ✓ → 9 ✓ → 10 (A → B → C → D → E):** Sub-bundle A ships → orchestrator drives operator-witnessed gate → integration merge → orchestrator queues Sub-bundle B dispatch brief drafting (which will propagate T-B.7 lucky_violation_R elective).

---

## §7 Watch items for orchestrator (post-Sub-bundle-A-ship)

1. **Operator-witnessed gate S3** (browser /metrics page) is the only browser-side check in Sub-bundle A. Operator's gate session is short (~5 min); confirm 8-tile navigator renders + base-layout integration intact.

2. **Cross-bundle pin** at T-A.7: `test_existing_dashboard_vm_has_unresolved_material_field` is SKIPPED with reason naming Task E.3 as the un-skip point. Verify the skip is still in place at integration merge; un-skip happens at Sub-bundle E's T-E.3.

3. **Risk_policy reset (Option C)** queued post-Sub-bundle-A dispatch per operator decision 2026-05-13. Orchestrator runs `swing config policy reset` post-merge to revert active policy to cfg-seed baseline. Affects no Sub-bundle A behavior; only the live risk_policy chain.

4. **verify_phase10.py** lands at worktree root (NOT in `swing/`); subsequent sub-bundles extend with their own sanity checks. Lock the cross-platform Python pattern at Sub-bundle A; future sub-bundles inherit.

5. **9 worktree husks** pending operator cleanup-script as of pre-Sub-bundle-A dispatch; expected 10th after Sub-bundle A ship.

6. **Sub-bundle B forward-binding lessons** — if Sub-bundle A's Codex chain surfaces any new lessons (e.g., a `swing/metrics/`-specific testing pattern), bank in CLAUDE.md gotchas + the return report's §9. Sub-bundle B's dispatch brief will inherit.

---

## §8 Dispatch order — UNCHANGED

A (this dispatch) → B → C → D → E. Sub-bundle A is the foundational cross-bundle dependency; B/C/D/E all consume its interface. Sub-bundle A ships → orchestrator-witnessed gate → integration merge → Sub-bundle B dispatch (which will propagate the T-B.7 lucky_violation_R elective).

---

*End of dispatch brief. Sub-bundle A is the foundational cross-bundle dependency for Phase 10. Sub-bundles B/C/D/E ALL consume the §A.7 honesty interface + the BaseLayoutVM mixin + the discrepancies helper from this bundle. ZERO new schema; ZERO operator-witnessed gate cost beyond S3 (5-min browser check).*
