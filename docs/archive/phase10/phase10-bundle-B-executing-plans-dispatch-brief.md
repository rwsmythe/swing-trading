# Phase 10 Sub-bundle B — executing-plans dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Phase 10 Sub-bundle B per plan §E (Tasks T-B.0..T-B.6) + electives amendment §2 (Task T-B.7) on an isolated worktree branch via `copowers:executing-plans` (wraps `superpowers:subagent-driven-development` + adversarial Codex MCP review). Sub-bundle B lands the **first two operator-visible Phase 10 dashboard surfaces**: §4.1 Trade-process card + §4.2 Hypothesis-progress card. PLUS one elective: T-B.7 surfaces `lucky_violation_R` on the existing Phase 6 review form (§8.6 election per electives amendment).

**Expected duration:** ~8-12 hr executing-plans wall-clock + ~2-4 hr Codex convergence. Plan §E has 7 tasks + electives amendment adds T-B.7; 8 total. Estimated 3-5 Codex rounds (Sub-bundle A precedent: 4 rounds; Phase 9 Bundle B precedent: 5 rounds).

---

## §0 Inputs

### §0.1 Plan
- **PLAN_PATH:** `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`
- **Plan status:** Codex R1-R6 → NO_NEW_CRITICAL_MAJOR; shipped 2026-05-13 at `a34c00d`; AMENDED in-tree during Sub-bundle A Codex R2+R3 (commits `e32f71c` + `75dd63f`) — Sub-bundle B reads the AMENDED §A.7 + §D Task A.1 text, NOT the original. 2008+ lines.
- **Sub-bundle B scope:** plan §E (lines 1063-1254); 7 tasks T-B.0..T-B.6.
- **Cross-bundle invariants:** plan §I (lines 1665-1726); 15 invariants. Sub-bundle B exercises §I.3 (risk_policy split), §I.4 (PROVISIONAL/LIVE — N/A for §4.1 / §4.2 surfaces since those are governance metrics that use AT-TRADE-TIME capital_floor directly per §A.5), §I.5 (BaseLayoutVM mixin), §I.6 (HTMX failure-surface budget — §A.9 lock pure server-render), §I.8 (decoupling discipline), §I.13 (session-anchor read/write predicate alignment), §I.14 (empty-cohort rendering), §I.15 (operator-witnessed gate per surface).

### §0.2 Electives amendment
- **AMENDMENT_PATH:** `docs/phase10-electives-amendment.md`
- **Amendment status:** SHIPPED 2026-05-13 at `9525f17`; NORMATIVE supplement to plan §A.4 + §E + §F + §H.
- **Sub-bundle B impact:** ONE elective task — T-B.7 `lucky_violation_R` on Phase 6 review form (§8.6 election). See amendment §2 Task B.7 for full acceptance criteria. Adds 1 task + 1 gate surface to Sub-bundle B.

### §0.3 Spec
- **SPEC_PATH:** `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md`
- **Spec status:** Codex R1-R5 substantive + R6 confirmation; SHIPPED 2026-05-06 at `fe6cb45`; 641 lines; RESEARCH-POSTURE.
- **Sub-bundle B spec coverage:** §3.1 trade-process metrics (Tasks B.1-B.3); §3.2 per-cohort governance (Tasks B.4-B.5); §4.1 trade-process card surface (Task B.3); §4.2 hypothesis-progress card surface (Task B.5); §5 honesty policy applied across all surfaces; §7 mistake-cost formula (consumed via Phase 6 helpers); §8.6 lucky_violation_R surface (T-B.7 elective).

### §0.4 Project state at dispatch time
- **HEAD on `main`:** `11ce75f` (post-Sub-bundle-A-ship housekeeping commit; merge at `096de83`).
- **Test count (main HEAD):** **2899 fast passing + 2 skipped** (1 cross-bundle pin from Sub-bundle A T-A.7 + 1 Task 7.3 operator-only) + 3 pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py` failures NOT regressions. **Worktree-side baseline:** 2895 fast passing + 6 skipped (adds 4 fixture-absent skips for `thinkorswim/*.csv` not in worktree dir). Implementer runs from worktree, so plan §A baseline-test-count documentation should reflect the WORKTREE-side number (2895/6).
- **Ruff baseline:** **18 (E501 only).** Unchanged across Sub-bundle A + entire Phase 9 arc.
- **Schema version:** **v17.** LOCKED since Phase 9 Sub-bundle A; Sub-bundle B introduces ZERO schema changes per §A.0 + §I.1 LOCK. `EXPECTED_SCHEMA_VERSION` stays at 17.
- **Active risk_policy:** `policy_id=5` (Option C revert; `max_account_risk_per_trade_pct=0.5` cfg-aligned; `capital_floor_constant_dollars=7500.0`; `scratch_epsilon_R=0.10`; ratified post-Sub-bundle-A operator decision). Chain: 1 (seed) → 2 (S3-test) → 3 (S2.bis-divergence) → 4 (S2.bis-revert) → **5 (ACTIVE)**.
- **Production trades:** 8 trades (5 open: DHC/YOU/VSAT/CVGI/LAR; 3 closed/reviewed: VIR/CC/SGML). All 8 have `risk_policy_id_at_lock IS NULL` (pre-Phase-9 legacy stamps; §A.5 NULL-stamp fallback applies — they render with `[legacy: pre-Phase-9 trade]` annotation). 2 of 11 review_log rows stamped (`risk_policy_id_at_review_completion=4`); 9 NULL.

### §0.5 Sub-bundle A interface inheritance — AMENDED plan §A.7

**CRITICAL:** Plan §A.7 + §D Task A.1 were AMENDED in-tree during Sub-bundle A Codex R2 + R3 fix commits (`e32f71c` + `75dd63f`). Sub-bundle B reads the AMENDED text. Specifically:

**HonestyBadges dataclass (per AMENDED §A.7):**
```python
@dataclass(frozen=True)
class HonestyBadges:
    confidence_floor_warning: bool   # spec §5 — visible when n < global_confidence_floor_n
    low_confidence_warning: bool     # spec §5 — visible when 3 ≤ n < 5
    window_not_full_warning: bool = False  # spec §5.4 — rolling-window not yet at N (Codex R1 Major #1 fix)
```

**Public helpers in `swing/metrics/honesty.py`** (Sub-bundle B consumes):
- `wilson_ci(*, k, n, alpha)` — STANDARD Wilson score interval (per Wikipedia primary formula; matches statsmodels' `proportion_confint(method='wilson')`; NOT continuity-correction). Plan §D Task A.1 reference value `[0.094, 0.901]` for k=2,n=4 was wrong — standard yields `[0.150, 0.850]`. Banked as V2.1 §VII.F amendment candidate (phase3e-todo 2026-05-13 entry).
- `bootstrap_ci_mean(*, samples, resample_count, alpha, rng_seed)` — `random.Random(rng_seed)` for determinism in tests.
- `suppress_for_n(*, metric_name, n, klass, policy)` — returns `SuppressedMetric | None`.
- `badges_for_n(*, n, policy) -> HonestyBadges` — **PUBLIC** (per R1 Minor #1 + R3 Major #1; private `_badges_for_n` aliased for back-compat but new code uses public). Sub-bundle B should compose badges via this helper.
- `render_class_a(*, k, n, policy, metric_name)` → `WilsonCI | SuppressedMetric`
- `render_class_b(*, samples, policy, metric_name)` → `BootstrapCI | SuppressedMetric`
- `render_class_c(*, value, n, n_wins, n_losses, policy, metric_name)` → `tuple[float | None, HonestyBadges] | SuppressedMetric`
- `render_class_d(*, samples_in_window, window_n, policy, metric_name, underlying_class, events_in_window=None, n_wins=None, n_losses=None)` → `tuple[..., HonestyBadges, str] | SuppressedMetric` (3-tuple with drawability_text per spec §5.4 cadence-vs-confidence decoupling)

**Risk_policy resolver (per AMENDED implementation, not plan §A.5 original):**
- `swing/metrics/policy.py:read_live_policy(conn) -> RiskPolicy`
- `swing/metrics/policy.py:read_at_trade_time_policy(conn, *, policy_id_stamp: int | None) -> tuple[RiskPolicy, bool]` — takes `policy_id_stamp` directly, NOT `Trade` object. Returns `(policy, fallback_flag)` where fallback_flag=True means "NULL or orphan stamp; used LIVE policy".
- `swing/metrics/policy.py:read_at_review_time_policy(conn, *, policy_id_stamp: int | None) -> tuple[RiskPolicy, bool]` — same shape.
- **Accessor helpers (consume these to fetch the stamp from DB):**
  - `swing/metrics/policy.py:get_trade_policy_id_stamp(conn, *, trade_id: int) -> int | None`
  - `swing/metrics/policy.py:get_review_policy_id_stamp(conn, *, review_id: int) -> int | None`
- Pattern: `stamp = get_trade_policy_id_stamp(conn, trade_id=trade.id); policy, is_legacy = read_at_trade_time_policy(conn, policy_id_stamp=stamp)`.

**BaseLayoutVM mixin (per AMENDED §A.6 + §A.18):**
- `swing/web/view_models/metrics/shared.py:BaseLayoutVM` is a `@dataclass(frozen=True)` mixin with fields: `session_date: str`, `stale_banner: str | None = None` (NOT `bool = False`; matches existing base-layout pattern), `price_source_degraded: bool = False`, `price_source_degraded_until: str | None = None`, `ohlcv_source_degraded: bool = False`, `unresolved_material_discrepancies_count: int = 0`.
- Sub-bundle B's `TradeProcessCardVM` + `HypothesisProgressCardVM` MUST extend `BaseLayoutVM` (or mirror all fields). Constructor populates `unresolved_material_discrepancies_count=count_unresolved_material(conn)` per §A.18.

**Discrepancies helper (per §A.7.1):**
- `swing/metrics/discrepancies.py:count_unresolved_material(conn) -> int` — thin wrapper over Phase 9 helpers; read-only; returns 0 when both lists empty. Sub-bundle B VMs invoke this in their constructors.

**Cohort helpers (per §A.4):**
- `swing/metrics/cohort.py:list_trades_for_cohort(conn, *, hypothesis_label, state_filter)` — uses `swing.trades.entry.canonicalize_hypothesis_label` for label-matching.
- `swing/metrics/cohort.py:list_closed_trades_for_cohort(conn, *, hypothesis_label)` — shorthand for `state_filter=('closed', 'reviewed')`.
- `swing/metrics/cohort.py:count_per_cohort(conn) -> dict[str, int]` — all 4 hypothesis_registry cohorts; returns 0 when cohort empty.

**Cross-bundle pin (still SKIPPED at T-A.7):**
- `tests/web/test_view_models/test_base_layout_vm_coverage.py::test_existing_dashboard_vm_has_unresolved_material_field` is `@pytest.mark.skip(reason="Sub-bundle E T-E.3 adds field to existing base-layout VMs")`. Sub-bundle B does NOT touch this skip; it remains pinned for Sub-bundle E.

### §0.6 Phase 9 + Sub-bundle A forward-binding lessons (BINDING for Sub-bundle B)

In addition to the 15 forward-binding lessons enumerated in Sub-bundle A's dispatch brief §0.5 (Phase 9 arc), **2 NEW lessons from Sub-bundle A** are forward-binding for Sub-bundle B:

**1. Plan §A.7 binding-interface amendments flow into plan text in SAME commit as code change** (Sub-bundle A Codex R2 Major #1 + R3 Major #1 caught the same failure-mode TWICE). When Sub-bundle B's implementation changes ANY §A.7 element (HonestyBadges fields, function signatures, Decoupling discipline assignment), update plan §A.7 IN THE SAME COMMIT that changes the code. Sub-bundle B is unlikely to introduce new §A.7 elements (the interface is locked at Sub-bundle A close); but the LESSON FAMILY extends to plan §E task acceptance criteria — if Sub-bundle B's implementation needs to add a new field to `TradeProcessMetricsResult` or similar consumer-side aggregator, update the plan §E acceptance text in the same commit.

**2. Statistical helpers with multiple textbook-correct variants need explicit spec pin at writing-plans time with citation.** Sub-bundle A's Wilson CI choice was implicit; standard-vs-continuity-correction divergence required a return-report explanation. Sub-bundle B's bootstrap CI is the next textbook-ambiguous helper — `bootstrap_ci_mean` is already shipped with percentile-method tail-handling (per §A.7), but if any Sub-bundle B metric needs a different variant (e.g., BCa for skewed distributions; bias-corrected for ratio metrics like profit_factor — but Class C is point-only in V1), the implementer's choice MUST be cited explicitly in the plan §E task acceptance criteria.

Phase 9 + Sub-bundle A LESSON CATALOG (re-enumerated for completeness; from Sub-bundle A brief §0.5):

| # | Lesson | Sub-bundle B applicability |
|---|---|---|
| 1 | `__post_init__` validator pattern on all new dataclasses | YES — `TradeProcessMetricsResult`, `CohortTabVM`, `CohortProgressVM`, `TradeProcessCardVM`, `HypothesisProgressCardVM` all need NaN/inf rejection + invariant assertions |
| 2 | Service-layer transaction discipline | N/A (Sub-bundle B is read-only) |
| 3 | NO `INSERT OR REPLACE` | N/A |
| 4 | Server-stamping discipline at handler entry | N/A (no new forms in Sub-bundle B; T-B.7 modifies existing review form — that surface is already Phase 6 server-stamped; T-B.7 only ADDS a display field) |
| 5 | Composition-surface enumeration via `^def` grep | **YES — re-grep `swing/metrics/honesty.py` + `swing/metrics/cohort.py` + `swing/metrics/policy.py` for AMENDED public surfaces; do NOT memory-enumerate** |
| 6 | Empirical-verification of brief assertions | YES — verify spec §3.1 metric formulas against Phase 6 `swing/trades/review.py` helpers before locking |
| 7 | Form-render hidden anchors round-trip through soft-warn confirm | N/A (no new forms) |
| 8 | POST-time recompute of "latest-of-something" TOCTOU | N/A |
| 9 | Test fixtures USERPROFILE+HOME monkeypatch | N/A (Sub-bundle B tests don't exercise `write_user_overrides`) |
| 10 | HTMX browser-only failure surfaces | YES — operator-witnessed gate is BINDING for 3 browser surfaces in Sub-bundle B (§4.1 + §4.2 + Phase 6 review form post-T-B.7) |
| 11 | `<tr>`-leading HTMX response | N/A (per §A.9 + §I.6 — pure server-rendered HTML; no HTMX OOB-swap) |
| 12 | matplotlib mathtext | N/A (Sub-bundle B has no charts) |
| 13 | `base.html.j2` shared fields require adding to EVERY base-layout VM | **YES — new VMs MUST extend BaseLayoutVM mixin per §A.18** |
| 14 | Session-anchor read/write predicate alignment | YES — Sub-bundle B's hypothesis-progress card reads `hypothesis_status_history.effective_from` (timestamp) + `last_completed_session(now)` only IF the operator-facing card surfaces "active-this-session" indicators; per spec §3.2 + §A.11 transition timeline is timestamp-ordered, no session anchor |
| 15 | Discriminating-test arithmetic | YES — every acceptance test must distinguish correct from buggy implementations (per §A.5.1 multi-policy cumulative_R_pct_of_capital test pattern) |
| 16 (NEW) | Plan §A.7 amendments flow same commit as code | See §0.6 above |
| 17 (NEW) | Statistical helper formula explicit pin | See §0.6 above |

### §0.7 Sub-bundle B scope summary (per plan §E + electives amendment §2)

| Task | Files | Acceptance | Test count est. |
|---|---|---|---:|
| **T-B.0** recon | read-only | Sub-bundle A interface intact; document 4 cohort `decision_criteria` seed text verbatim | 0 |
| **T-B.1** §3.1 trade-process computations | `swing/metrics/process.py` + `tests/metrics/test_process.py` | 22 metrics from §3.1 inventory; per-metric class matrix (plan §E binding); AT-TRADE-TIME policy resolution per-trade; mistake_cost_R + lucky_violation_R prefer review_log aggregate, fall back to per-trade compute via Phase 6 helpers | ~15-25 |
| **T-B.2** TradeProcessCardVM | `swing/web/view_models/metrics/trade_process_card.py` + tests | 5 tabs (4 cohorts + "all"); default-active = first cohort; extends BaseLayoutVM; populates `unresolved_material_discrepancies_count` | ~6-10 |
| **T-B.3** trade-process card route + template | `swing/web/routes/metrics.py` (add `GET /metrics/trade-process`) + 3 templates (page + 2 partials) + tests | TestClient smoke; base-layout integration; per-tab visibility; suppression placeholder rendering | ~5-8 |
| **T-B.4** §3.2 hypothesis-progress card VM | `swing/web/view_models/metrics/hypothesis_progress_card.py` + tests | `HypothesisProgressCardVM` extends BaseLayoutVM; per-cohort governance metrics; full transition history (§A.11 supersedes spec §3.2 V1-limitation); §A.5.1 multi-policy cumulative_R_pct_of_capital semantics | ~10-15 |
| **T-B.5** hypothesis-progress card route + template | `swing/web/routes/metrics.py` (add `GET /metrics/hypothesis-progress`) + template + tests | 4 cohorts in row layout; transition timeline `<ol>`; decision_criteria text rendered | ~4-7 |
| **T-B.6** Sub-bundle B integration test + ruff sweep | `tests/integration/test_phase10_bundle_b_e2e.py` + ruff sweep | E2E happy path: 4 cohorts + 6 trades + both surfaces render coherently | ~3-5 |
| **T-B.7** (elective) lucky_violation_R on Phase 6 review form | `swing/web/view_models/trades.py` (modify `ReviewVM` at L:629 + `build_review_vm` at L:651) + `swing/web/templates/review.html.j2` + tests | `lucky_violation_R_display: float | None` field; symmetric rendering alongside `mistake_cost_R`; both-zero → "—" placeholder; existing fields unaffected | ~3-5 |

**Projected test count delta: +46..+75 fast tests** (per plan §E +40..+65 projection + electives amendment T-B.7 +3..+5). Above-projection precedent likely per Sub-bundle A's +128 overshoot.

### §0.8 §A.5.1 Cohort-aggregate `cumulative_R_pct_of_capital` BINDING semantics

This is the highest-Codex-density section in Sub-bundle B per plan §A.5.1 (Codex R1 Major #2 fix in writing-plans). Plan §A.5.1 LOCK:

```
cumulative_R_pct_of_capital(cohort) =
    sum over trades t in cohort of:
        ( t.realized_pnl_dollars / at_trade_time_policy(t).capital_floor_constant_dollars )
```

**Per-trade contribution divided by ITS at-trade-time floor; contributions then summed.**

**REJECTED alternatives** (would silently re-classify historical state):
1. Naive sum-then-divide using LIVE policy: `sum(realized_pnl_dollars) / live_policy.capital_floor` — re-classifies every prior trade's contribution under policy supersession.
2. Average policies across trades + single-divide: `sum(realized_pnl_dollars) / mean(at_trade_time_floors)` — algebraic identity broken; result depends on trade ordering at boundary epsilons.

**Discriminating regression test pattern (binding in Task B.4):**

`test_vm_cumulative_R_uses_per_trade_at_trade_time_capital_floor`:
- Seed trade A: stamped `risk_policy_id_at_lock=1` (capital_floor=$7500), realized P&L -$50.
- Seed trade B: stamped `risk_policy_id_at_lock=2` (capital_floor=$10000), realized P&L -$100.
- Supersede active policy to policy_id=3 (capital_floor=$5000).
- Assert `cumulative_R_pct_of_capital = (-50/7500) + (-100/10000) = -0.667% + -1.000% = -1.667%`.
- Discriminates against: `-150/5000 = -3.000%` (naive-live-policy) + `-150/8750 = -1.714%` (average-policy).

`test_vm_cumulative_R_pre_phase9_legacy_trade_uses_live_floor_with_annotation`:
- Seed legacy trade with `risk_policy_id_at_lock=NULL`.
- Assert per-trade contribution uses LIVE policy floor; annotation flag is set.

### §0.9 §A.11.1 Cohort-temporal-filter inclusion policy (BINDING)

Per plan §A.11.1 (Codex R1 Major #4 fix in writing-plans): cohort metrics include ALL trades labeled with the cohort regardless of cohort status at trade-time. **Locked V1 policy** (binding for Tasks B.1 + B.4):

- Trades stamped during a paused interval count toward cohort metrics.
- Rationale: operator-intent-at-entry semantics; pausing the cohort does not retroactively un-classify trades.

**Discriminating tests** (binding in Task B.1):
- `test_cohort_metrics_include_trades_during_paused_interval`: seed cohort with status history active@t0 → paused@t1 → active@t2; seed trade stamped at `pre_trade_locked_at=t1.5` (during paused interval); assert trade IS in cohort_n_closed + contributes to expectancy_R.
- `test_hypothesis_progress_card_renders_paused_status_history_alongside_metrics`: timeline shows the active→paused→active transitions; metric cells reflect ALL trades.

**V2 candidate banked** (NOT V1 scope; per §A.11.1): operator-elective per-cohort filter "Exclude trades stamped during paused intervals" — same UI shape as Sub-bundle C T-C.5 "exclude trades with unresolved discrepancies" filter family. Reuse opportunity.

### §0.10 §A.11 Full transition history supersedes spec §3.2 V1-limitation

Plan §A.11 supersedes spec §3.2's "single most-recent transition only" V1-limitation note (Phase 9 Sub-bundle C closed the audit-table capture gap). Sub-bundle B's hypothesis-progress card renders FULL transition timeline as a small inline `<ol>` ordered by `effective_from DESC`, capped at the last 5 transitions per cohort (V1 cap; UI brevity).

Banked as spec amendment pending V2.1 §VII.F routing (same recon-doc-supersession pattern as Phase 9 Sub-bundle D §7 sector_industry anchor + Sub-bundle E §6.2 multi-line parser).

### §0.11 T-B.7 elective spec (per electives amendment §2)

**Scope:** modifies existing route `GET /reviews/{id}/complete` + template (`swing/web/templates/review.html.j2`). NO new Phase 10 surface; touches Phase 6 review surface.
**Est. impl:** ~1-2hr.
**Schema impact:** ZERO — `lucky_violation_R` is computed at `swing/trades/review.py:compute_lucky_violation_R` (Phase 6) + persisted on `review_log.total_lucky_violation_R`.

**Acceptance criteria (verbatim from electives amendment §2):**
- `ReviewVM` (existing at `swing/web/view_models/trades.py:629` + builder at `swing/web/view_models/trades.py:651`) gains a derived `lucky_violation_R_display: float | None` field surfacing the per-trade computed value (NOT the review_log aggregate — that's already on the cohort surfaces). Field is computed from the trade's `realized_R_if_plan_followed` + `actual_realized_R_effective` at VM build time via the existing helper.
- `review.html.j2` template renders the field symmetrically alongside the existing `mistake_cost_R` display: same label-row + numeric-cell pattern; field labeled "Lucky violation (R)" with the same precision (2 decimal places) as `mistake_cost_R`.
- Suppression: when both `mistake_cost_R` and `lucky_violation_R` are 0 (plan-followed-exactly), render "—" placeholder for both.
- TestClient regression: `tests/web/test_routes/test_review_complete_form.py` extends existing test fixture with a trade that has `realized_R_if_plan_followed > actual_realized_R_effective` (mistake-cost positive) + a separate trade with `actual_realized_R_effective > realized_R_if_plan_followed` (lucky-violation positive); assert template rendering surfaces both values.

**Watch items:**
- Existing review form is operator-witnessed-gate-validated as of Phase 6 ship (`51c79ed`). Task B.7 gate surface = re-verify the review form still loads + the new field renders + the existing mistake-cost field is unaffected.
- The Phase 10 spec §7.4 + §8.6 open question framed this as a small standalone follow-up; bundling into Sub-bundle B is operator's election, NOT a spec deviation.

**Cross-bundle pin:** none (purely additive to a pre-Phase-10 surface).

---

## §1 Worktree + binding conventions

### §1.1 Worktree
- **Branch:** `phase10-bundle-B-trade-process-and-hypothesis-progress`
- **Worktree directory:** `.worktrees/phase10-bundle-B-trade-process-and-hypothesis-progress/`
- **BASELINE_SHA:** `11ce75f` (current main HEAD; post-Sub-bundle-A-ship housekeeping).
- **Worktree branching point:** current HEAD of `main` at worktree-creation time (resolve via `git rev-parse main`; expected the brief commit SHA after this brief lands).

### §1.2 Marker-file workflow
- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all task commits land + Codex chain converges + before final return-report commit: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits
- Conventional prefixes per plan §E + electives amendment §2 suggested commit shapes (`feat(metrics): ...`, `test(metrics): ...`, `feat(web): ...` for T-B.7, `chore(metrics): ...`).
- One commit per task; Codex-fix commits as `fix(phase10-bundle-B): Codex RN <severity> #N — <description>`.
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.

### §1.4 Branch isolation + ownership
- Commits on branch only; no push to origin from worktree.
- **Implementer (you) owns:** copowers:executing-plans invocation → task-by-task TDD → Codex iteration → return-report commit.
- **Orchestrator owns:** plan-triage at dispatch time + integration merge to main + Sub-bundle C dispatch commissioning post-B-ship.

### §1.5 Verify command (basic; copowers:executing-plans handles full task execution + Codex review)
```powershell
# After all tasks land + Codex chain converges:
git log --oneline HEAD~12..HEAD
python -m pytest -m "not slow" -q
ruff check swing/ --statistics
python verify_phase10.py
```

---

## §2 Operator-witnessed verification gate (Sub-bundle B)

Per plan §E + electives amendment §2 + §I.15 BINDING:

| # | Surface | Type | Acceptance |
|---|---|---|---|
| **S1** | pytest fast-suite + ruff + verify_phase10 | Inline | `python -m pytest -m "not slow" -q` GREEN at ~2941..2970 fast tests (worktree-side); 3 pre-existing `test_phase8_pipeline_walkthrough.py` failures unchanged; `ruff check swing/` baseline 18; `python verify_phase10.py` exits 0. |
| **S2** | `/metrics/trade-process` | **Browser (operator-witnessed)** | `swing web` → navigate to `http://127.0.0.1:8080/metrics/trade-process` → confirm: (a) page renders 200; (b) 5 tabs visible (4 cohorts + "all"); (c) default-active tab is first cohort (NOT "all"); (d) per-tab metric grid renders 22 §3.1 metrics; (e) per spec §4.1 sample-size threshold: each cohort with n<3 shows SUPPRESSION placeholder for the entire tab; n=3..4 point-estimate-with-warning; n≥5 Wilson/bootstrap CI; (f) ConfidenceBadgeVM + SuppressionRowVM render as TEXT badges (NOT color-only); (g) no console errors; (h) `[legacy: pre-Phase-9 trade]` annotation visible on metrics derived from the 8 legacy production trades. |
| **S3** | `/metrics/hypothesis-progress` | **Browser (operator-witnessed)** | `http://127.0.0.1:8080/metrics/hypothesis-progress` → confirm: (a) page renders 200; (b) 4 cohorts in row layout; (c) per-cohort cell shows progress bar, status badge, tripwire indicator, decision_criteria text verbatim from `swing/data/migrations/0008_hypothesis_registry.sql`, transition timeline `<ol>` (capped at last 5 entries); (d) tripwire indicators present even at n=0 trades (§4.2 ALWAYS shown); (e) `cumulative_R_pct_of_capital` computed via §A.5.1 multi-policy semantics (per-trade contribution divided by ITS at-trade-time floor); (f) no console errors. |
| **S4** | `/reviews/{review_id}/complete` (T-B.7 elective) | **Browser (operator-witnessed)** | `http://127.0.0.1:8080/reviews/{review_id}/complete` (pick any existing review — e.g., `review_id=11` weekly per production state) → confirm: (a) page renders 200 (Phase 6 regression check); (b) existing `mistake_cost_R` display unchanged; (c) NEW `lucky_violation_R` field renders symmetrically alongside `mistake_cost_R`; (d) "Lucky violation (R)" label visible; (e) 2-decimal-place precision matches `mistake_cost_R`; (f) for trades with both fields=0, both render as "—" placeholder. |

**Gate session ≤ 6 surfaces budget (dispatch brief §1.3):** Sub-bundle B has 4 surfaces — 1 inline + 3 browser. Well under budget.

**Chrome MCP availability:** orchestrator drives S2 + S3 + S4 via Chrome MCP `mcp__claude-in-chrome__*` tools at gate time (Sub-bundle A precedent). If Chrome MCP is unavailable at gate time, operator drives manually.

---

## §3 Skill posture + adversarial review

- **Invoke `copowers:executing-plans`** (NOT `superpowers:executing-plans` or `superpowers:subagent-driven-development` directly — the copowers wrapper handles Codex review automatically after task commits land).
- Skill inputs:
  - `PLAN_PATH=docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`
  - `AMENDMENT_PATH=docs/phase10-electives-amendment.md`
  - `SUB_BUNDLE=B` (Tasks T-B.0..T-B.6 + T-B.7 elective)
  - `BASELINE_SHA=11ce75f`
- **Expected Codex chain:** 3-5 rounds (Sub-bundle A: 4 rounds; Phase 9 Bundle B: 5 rounds; Phase 10 has zero schema work + Sub-bundle A locked the foundational interfaces, expected slightly faster).
- Iterate per-round fixes as `fix(phase10-bundle-B): Codex RN <severity> #N — ...` commits.
- Terminate at NO_NEW_CRITICAL_MAJOR.

### §3.1 Codex value-add concentration

Adversarial review for Sub-bundle B typically catches:

- **§A.5.1 cumulative_R_pct_of_capital semantics violation** — Codex will check that Task B.4's implementation does per-trade-divide-then-sum, NOT sum-then-divide-by-live-policy. Pre-empt with the multi-policy discriminating test from §0.8.
- **§A.11.1 paused-interval inclusion violation** — Codex will check that cohort metrics include trades stamped during paused intervals. Pre-empt with the active→paused→active fixture test from §0.9.
- **§A.11 transition timeline cap-at-5 + ordering** — Codex will check that `<ol>` renders newest-first (effective_from DESC) and caps at 5 entries.
- **Suppression cascading** — Codex will check that cohort with n<3 → all 22 §3.1 metrics return SuppressedMetric (NOT some passing, some failing).
- **Class assignment drift** — Codex will check that each §3.1 metric matches plan §E per-metric class matrix (e.g., `profit_factor` is Class C with `n_wins` + `n_losses` params; `process_grade` is Class A as DISTRIBUTION not single rate).
- **mistake_cost_R + lucky_violation_R aggregation source** — Codex will check that VMs prefer `review_log.total_mistake_cost_R` / `total_lucky_violation_R` aggregate when present, fall back to per-trade compute via Phase 6 helpers when absent.
- **BaseLayoutVM field population** — Codex will check that `TradeProcessCardVM` + `HypothesisProgressCardVM` populate `unresolved_material_discrepancies_count` via `count_unresolved_material(conn)` (§A.18 cross-bundle pin). The cross-bundle pin test stays SKIPPED at Sub-bundle B (only un-skipped at T-E.3).
- **T-B.7 ReviewVM symmetric rendering** — Codex will check that `lucky_violation_R_display` is structurally symmetric to `mistake_cost_R_display`: same precision (2 decimal places), same suppression rule (both-zero → "—"), same label/value cell pattern in template.
- **T-B.7 Phase 6 regression** — Codex will check that existing `mistake_cost_R` field continues to render correctly (no template structural change that breaks the existing Phase 6 surface).
- **Empty-cohort + zero-trade rendering** (§A.16 + §I.14) — Codex will check every surface renders gracefully at n=0/1/2.
- **At-trade-time policy resolution per-trade** — Codex will check Task B.1 uses `get_trade_policy_id_stamp` + `read_at_trade_time_policy(..., policy_id_stamp=stamp)` per-trade for scratch_epsilon classification.

### §3.2 Per-task Codex-check pre-emption

| Task | Common Codex finding | Pre-emption |
|---|---|---|
| T-B.0 | None expected (pure recon) | Document the 4 cohort `decision_criteria` seed text values verbatim in PR description |
| T-B.1 | Class C `profit_factor` / `payoff_ratio` missing diversity check | Pass `n_wins` + `n_losses` to `render_class_c`; both must be ≥1 for ratio rendering |
| T-B.1 | mistake_cost_R fallback to per-trade compute missing for unreviewed-closed trades | Test both branches; check `review_log` for non-NULL aggregate FIRST, fall back to `compute_mistake_cost_R` per-trade |
| T-B.2 | Default-active tab is "all" instead of first cohort | Test asserts first cohort is active; "all" toggle is NON-default |
| T-B.3 | Color-only badges (HTML5 `<span style="color:red">`) | Use TEXT badges per §A.9 + spec §4.9 |
| T-B.3 | Per-tab navigation uses HTMX OOB-swap | Use simple `<a>` anchors with query-string `?cohort=...` per §A.9 lock |
| T-B.4 | cumulative_R_pct_of_capital uses LIVE policy or averaged policies | §A.5.1 multi-policy discriminating test BINDING; per-trade-divide-then-sum |
| T-B.4 | Transition timeline reads via wrong helper | Use `swing.data.repos.hypothesis_status_history.list_history_for_hypothesis` |
| T-B.4 | Cap-at-5 missing | Slice `[:5]` after `ORDER BY effective_from DESC`; test asserts seed of 7 returns 5 |
| T-B.5 | Decision_criteria text drift from seed | Test reads seed text from `swing/data/migrations/0008_hypothesis_registry.sql` |
| T-B.6 | E2E test seeds insufficient diversity | Seed 6 trades across 4 cohorts mixed states: covers per-metric branches |
| T-B.7 | New field present but template renders ahead-of-mistake-cost (or other ordering drift from Phase 6) | Append AFTER mistake_cost row in template; visual parity |
| T-B.7 | Both-zero suppression returns numeric "0.00" instead of "—" | Discriminating test: trade with plan_followed=0R AND actual=0R → both fields render "—" |

---

## §4 Return report shape

After all task commits land + Codex chain converges + before final return-report commit, draft a return report at `docs/phase10-bundle-B-return-report.md` (mirroring `docs/phase10-bundle-A-return-report.md` shape):

1. Final HEAD on branch + commit count breakdown (task-impl + Codex-fix; expected ~8 task-impl + 3-5 Codex-fix + 1 return-report).
2. Codex round chain (e.g., "R1 0/X/Y → R2 ... → Rn NO_NEW_CRITICAL_MAJOR").
3. Test count delta + ruff baseline delta.
4. Operator-witnessed verification surfaces (PENDING orchestrator-driven gate; S1 inline OK; S2+S3+S4 PENDING).
5. Per-task deviations from the plan (if any) with rationale; any spec-amendment candidates banked.
6. Codex Major findings ACCEPTED with rationale (if any).
7. Watch items for orchestrator (cross-bundle pins; un-skip-at-T-E.3 reminder; any V2 candidates banked).
8. Worktree teardown status (expected ACL-locked husk; 11th pending operator cleanup-script).
9. Sub-bundle C forward-binding lessons (if any new ones surfaced during executing-plans).
10. Composition-surface verification via `^def` grep (per Phase 9 + Sub-bundle A forward-binding lesson #5).
11. Any plan-text amendments applied in-tree during Codex rounds (mirror Sub-bundle A §A.7 + §D Task A.1 amendments pattern).

---

## §5 First-step paste-ready prompt for the implementer

```
You are taking over to implement Phase 10 Sub-bundle B (Trade-process card + Hypothesis-progress card + lucky_violation_R review form elective) for swing-trading.

WORKING DIRECTORY (after worktree creation): c:\Users\rwsmy\swing-trading\.worktrees\phase10-bundle-B-trade-process-and-hypothesis-progress
BRANCH: phase10-bundle-B-trade-process-and-hypothesis-progress
BASELINE_SHA: 11ce75f  (per dispatch brief §1.1; HEAD of main BEFORE this brief commit)
WORKTREE-BRANCHING-POINT: current HEAD of main at worktree-creation time (resolve via `git rev-parse main`)

The Codex diff (11ce75f → worktree HEAD) will include one or more doc-only commits (the dispatch brief + per-task code + Codex fixes). All harmless; Codex evaluates the CODE content against the PLAN §E + ELECTIVES AMENDMENT §2.

Step 0 — Create the worktree:
  cd c:\Users\rwsmy\swing-trading
  $base = git rev-parse main
  git worktree add .worktrees\phase10-bundle-B-trade-process-and-hypothesis-progress -b phase10-bundle-B-trade-process-and-hypothesis-progress $base
  New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active

Step 1 — Read the dispatch brief end-to-end from the worktree:
  docs/phase10-bundle-B-executing-plans-dispatch-brief.md

Step 2 — Read the Phase 10 plan §E + electives amendment §2 + cross-bundle invariants §I:
  docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md  (§E lines 1063-1254 for tasks T-B.0..T-B.6; §I lines 1665-1726 for invariants; §A.5 + §A.5.1 + §A.7 + §A.11 + §A.11.1 + §A.18 for AMENDED interface contracts)
  docs/phase10-electives-amendment.md  (§2 Task B.7 for elective task spec)

Step 3 — Read the Phase 10 brainstorm spec for §3.1 + §3.2 + §5 reference:
  docs/superpowers/specs/2026-05-06-phase10-metrics-design.md  (§3.1 trade-process metrics + §3.2 per-cohort governance + §4.1 + §4.2 surfaces + §5 honesty policy + §7 mistake-cost formula + §8.6 lucky_violation_R)

Step 4 — Read binding conventions + forward-binding lessons:
  - CLAUDE.md (gotchas + project conventions; "Lessons captured" + Phase 9 arc + Sub-bundle A gotcha promotions are forward-binding)
  - docs/orchestrator-context.md (orchestrator-role framing; Codex-driven discipline)
  - docs/phase10-bundle-A-return-report.md (Sub-bundle A close; §10 forward-binding lessons binding here; §5 deviations banked)

Step 5 — Verify worktree state:
  git rev-parse HEAD                       # expect current main HEAD (typically the dispatch brief commit)
  git status                               # expect clean
  python -m pytest -m "not slow" -q        # expect baseline GREEN (~2895 passed worktree-side after thinkorswim/*.csv accounting; 6 skipped — 1 cross-bundle T-A.7 pin + 1 Task 7.3 + 4 fixture-absent; 3 pre-existing fails in tests/integration/test_phase8_pipeline_walkthrough.py NOT regressions)
  python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"  # expect 17
  ruff check swing/ --statistics            # expect 18 E501
  python verify_phase10.py                  # expect exit 0

Step 6 — Pre-implementation recon (Sub-bundle A interface inheritance verification):
  grep -rn "^def " swing/metrics/honesty.py swing/metrics/policy.py swing/metrics/cohort.py swing/metrics/discrepancies.py
  python -c "from swing.metrics.honesty import wilson_ci, bootstrap_ci_mean, suppress_for_n, badges_for_n, render_class_a, render_class_b, render_class_c, render_class_d; from swing.metrics.policy import read_live_policy, read_at_trade_time_policy, read_at_review_time_policy, get_trade_policy_id_stamp, get_review_policy_id_stamp; from swing.metrics.cohort import list_trades_for_cohort, list_closed_trades_for_cohort, count_per_cohort; from swing.metrics.discrepancies import count_unresolved_material; print('Sub-bundle A interface intact')"
  grep -rn "^def " swing/web/view_models/metrics/shared.py swing/web/view_models/metrics/index.py
  grep -n "^class \|^def " swing/web/view_models/trades.py | grep -i 'review\|exit_form'  # ReviewVM at L:629; build_review_vm at L:651 — T-B.7 modifies these
  cat swing/data/migrations/0008_hypothesis_registry.sql | grep -A 1 "decision_criteria"  # 4 cohort seed text verbatim for T-B.0 recon doc
  grep -n "^def compute_lucky_violation_R\|^def compute_mistake_cost_R" swing/trades/review.py  # T-B.1 + T-B.7 consume both
  python -c "from swing.trades.review import compute_lucky_violation_R, compute_mistake_cost_R; print('Phase 6 helpers available')"

Step 7 — Invoke copowers:executing-plans (the skill wraps superpowers:subagent-driven-development + Codex review):
  - PLAN_PATH: docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md
  - AMENDMENT_PATH: docs/phase10-electives-amendment.md
  - SUB_BUNDLE: B
  - BASELINE_SHA: 11ce75f

Step 8 — Execute tasks task-by-task per plan §E + electives amendment §2:
  - T-B.0 recon (no commit; document inline in PR description / return-report)
  - T-B.1 §3.1 trade-process computations (commit: feat(metrics): §3.1 trade-process metric computations (T-B.1))
  - T-B.2 TradeProcessCardVM (commit: feat(metrics): trade-process card VM (T-B.2))
  - T-B.3 trade-process card route + template (commit: feat(metrics): trade-process card route + template — GET /metrics/trade-process (T-B.3))
  - T-B.4 §3.2 hypothesis-progress card VM (commit: feat(metrics): §3.2 hypothesis-progress card VM (T-B.4))
  - T-B.5 hypothesis-progress card route + template (commit: feat(metrics): hypothesis-progress card route + template — GET /metrics/hypothesis-progress (T-B.5))
  - T-B.6 integration sweep (commit: chore(metrics): Sub-bundle B integration sweep (T-B.6))
  - T-B.7 lucky_violation_R on review form (commit: feat(web): surface lucky_violation_R on Phase 6 review form (T-B.7 elective))

Step 9 — Iterate Codex rounds + land per-round-fix commits until NO_NEW_CRITICAL_MAJOR. Expected 3-5 rounds.

Step 10 — Draft return report at docs/phase10-bundle-B-return-report.md per dispatch brief §4. Commit it.

Step 11 — Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active + signal orchestrator. Orchestrator drives operator-witnessed gate (S2 + S3 + S4 browser surfaces via Chrome MCP if available) + integration merge.

DO NOT:
  - Push to origin from inside the worktree
  - Merge to main (orchestrator action)
  - Use --amend or --no-verify
  - Add Claude co-author footer to commits
  - Skip the marker-file removal before final signal
  - Skip the Step 6 pre-implementation recon (Sub-bundle A interface verification)
  - Add ANY new schema (no `0018_*.sql` migration; no ALTER on existing tables); Phase 10 V1 §A.0 LOCK is BINDING per plan §I.1
  - Skip `__post_init__` validators on any new dataclass (Phase 9 + Sub-bundle A forward-binding lesson #1)
  - Use cumulative_R_pct_of_capital naive sum-then-divide or averaged-policy semantics; §A.5.1 BINDING per-trade-divide-then-sum
  - Drop paused-interval trades from cohort metrics; §A.11.1 BINDING include-all-labeled
  - Drop trades during paused cohort intervals from cohort metrics; §A.11.1 BINDING include-all-labeled
  - Render only the latest hypothesis transition (per spec §3.2 V1-limitation); §A.11 BINDING full transition timeline capped at 5
  - Un-skip `test_existing_dashboard_vm_has_unresolved_material_field` (that's Task E.3's responsibility per §I.5)
  - Add HTMX OOB-swap, embedded forms, or HX-Redirect on /metrics/trade-process or /metrics/hypothesis-progress (§A.9 + §I.6 LOCK)
  - Add chart rendering via matplotlib (§A.10 V1 LOCK = inline SVG in Sub-bundle E only)
  - Implement per-surface routes other than /metrics/trade-process + /metrics/hypothesis-progress (those land in C/D/E per plan §A.3)
  - Implement Sub-bundle C/D/E task scope (out of B's lane)
  - Implement T-C.5 / T-E.5 / T-E.6 elective tasks (those land in their respective sub-bundles per electives amendment)
  - Implement §8.4 Corporate_Actions MVP (deferred as standalone post-Phase-10 dispatch per electives amendment §5)
  - Bundle this with Sub-bundle C (sequencing locked A ✓ → B → C → D → E per plan §C)
  - Add color-only badges (spec §4.9 BINDING; reliability flags + PROVISIONAL badges as TEXT not color-only)
  - Diverge from per-metric class matrix in plan §E Task B.1 acceptance (Codex will check)
  - Use Trade dataclass to pass risk_policy_id_at_lock (Sub-bundle A signature is policy_id_stamp: int | None directly via get_trade_policy_id_stamp accessor)
  - Use Wilson-with-continuity-correction (Sub-bundle A locked standard Wilson; matches statsmodels default)
  - Change T-B.7 to render lucky_violation_R as cohort aggregate instead of per-trade derived (per electives amendment §2: per-trade derived from realized_R_if_plan_followed + actual_realized_R_effective; cohort aggregate is already on Phase 10 §4.1 surfaces)
  - Change ordering of mistake_cost_R + lucky_violation_R rows in review.html.j2 such that existing field moves (Phase 6 regression check binds)
```

---

## §6 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-13 (post-Sub-bundle-A-ship).
- **Brief commit:** `<filled-in-after-commit>`.
- **Brief HEAD context:** `11ce75f` on main (post-Sub-bundle-A-ship housekeeping).
- **Worktree path (binding):** `.worktrees/phase10-bundle-B-trade-process-and-hypothesis-progress/`.
- **Baseline test count (main HEAD):** 2899 fast (2 skipped). Worktree-side: 2895 fast (6 skipped — 4 `thinkorswim/*.csv` fixture-absent + 1 cross-bundle T-A.7 pin + 1 Task 7.3 operator-only).
- **Baseline ruff count:** 18 (E501 only).
- **Plan status:** Codex R1-R6 NO_NEW_CRITICAL_MAJOR; AMENDED in-tree during Sub-bundle A R2 + R3; LOCKED.
- **Electives amendment status:** SHIPPED 2026-05-13 at `9525f17`; NORMATIVE; T-B.7 binding for Sub-bundle B.
- **Spec status:** Codex R1-R5 substantive + R6 confirmation; shipped 2026-05-06 at `fe6cb45`; 641 lines; LOCKED.
- **Expected dispatch wall-clock:** ~8-12 hr executing-plans + ~2-4 hr Codex convergence.
- **Expected test count delta:** +46..+75 fast tests; post-B ~2941..2970 worktree-side / ~2945..2974 main HEAD (matches Sub-bundle A overshoot precedent — actual may run higher).
- **Expected ruff delta:** 0 (baseline preserved).
- **Next per locked sequencing 8 ✓ → 9 ✓ → 10 (A ✓ → B → C → D → E):** Sub-bundle B ships → orchestrator drives operator-witnessed gate → integration merge → orchestrator queues Sub-bundle C dispatch brief drafting (which will propagate T-C.5 per-cohort discrepancy filter elective).

---

## §7 Watch items for orchestrator (post-Sub-bundle-B-ship)

1. **Operator-witnessed gates S2 + S3 + S4** — 3 browser-side checks. Orchestrator drives via Chrome MCP if available; operator drives manually otherwise. S2 + S3 verify Phase 10's first 2 dashboard surfaces; S4 verifies T-B.7 lucky_violation_R rendering on the Phase 6 review form WITHOUT regression on mistake_cost_R.

2. **Cross-bundle pin at T-A.7 (still SKIPPED)** — Sub-bundle B does NOT touch the skip on `test_existing_dashboard_vm_has_unresolved_material_field`. The un-skip lands at T-E.3 retrofit of the 6 existing base-layout VMs. Verify the skip remains in place at integration merge.

3. **Spec amendment candidates** banked from Sub-bundle A (3 candidates in phase3e-todo 2026-05-13 entry) — Sub-bundle B may surface additional plan-text divergences requiring banking. Return-report §11 enumerates.

4. **§A.11 transition timeline V1 supersession** — Sub-bundle B exercises the supersession. If Codex flags the spec §3.2 V1-limitation note as a divergence, point to plan §A.11 + return-report §6 for the rationale.

5. **`verify_phase10.py` may need extension for Sub-bundle B** — Sub-bundle A landed the cross-platform verification script at worktree root. Sub-bundle B's T-B.6 may extend it with additional sanity checks (e.g., assert `/metrics/trade-process` route registered; assert `compute_trade_process_metrics` callable). Banked as orchestrator-decision for Sub-bundle B return-report.

6. **Test count overshoot precedent** — Sub-bundle A projection was +35..+55, actual +128. Sub-bundle B projection is +46..+75; expected overshoot likely brings final to 2960..3010 worktree-side. Operator should not be alarmed if S1 test count is higher than projection.

7. **Worktree husk** — Sub-bundle B teardown expected to leave ACL-locked husk; 11th in operator cleanup-script queue.

---

## §8 Dispatch order — UNCHANGED

A ✓ → B (this dispatch) → C → D → E. Sub-bundle A is SHIPPED; Sub-bundle B is the next dispatch. Post-Sub-bundle-B-ship → Sub-bundle C (propagates T-C.5 per-cohort discrepancy filter elective).

---

*End of dispatch brief. Sub-bundle B is the first operator-visible Phase 10 dashboard surface bundle. §4.1 trade-process card + §4.2 hypothesis-progress card + T-B.7 lucky_violation_R review form elective. All 8 tasks use AMENDED Sub-bundle A interfaces; ZERO new schema; ZERO new write paths (T-B.7 modifies existing Phase 6 surface display only). 3 browser gate surfaces + 1 inline. Cross-bundle pin at T-A.7 stays SKIPPED for T-E.3.*
