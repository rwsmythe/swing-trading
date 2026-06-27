# Phase 10 Sub-bundle C — executing-plans dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Phase 10 Sub-bundle C per plan §F (Tasks T-C.0..T-C.4) + electives amendment §2 Task C.5 on an isolated worktree branch via `copowers:executing-plans` (wraps `superpowers:subagent-driven-development` + adversarial Codex MCP review). Sub-bundle C lands the **third + fourth operator-visible Phase 10 dashboard surfaces**: §4.3 Tier-comparison view + §4.7 Deviation-outcome view. PLUS one elective: T-C.5 per-cohort "exclude trades with unresolved discrepancies" filter (§11.2(c) election per electives amendment).

**Expected duration:** ~6-10 hr executing-plans wall-clock + ~2-4 hr Codex convergence. Plan §F has 5 tasks + electives amendment adds T-C.5; **6 total**. Estimated 2-4 Codex rounds (Sub-bundle A precedent: 4 rounds; Sub-bundle B precedent: 2 rounds; Phase 9 Bundle B precedent: 5 rounds). Sub-bundle C has slightly higher statistical complexity than B (Wilson + bootstrap CIs per cohort with overlap-descriptor text; cohort-comparison rendering) but inherits the AMENDED §A.7 interface that locks the helpers + §A.5.1 multi-policy semantics established in Sub-bundle B.

---

## §0 Inputs

### §0.1 Plan
- **PLAN_PATH:** `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`
- **Plan status:** Codex R1-R6 → NO_NEW_CRITICAL_MAJOR; shipped 2026-05-13 at `a34c00d`; AMENDED in-tree during Sub-bundle A Codex R2+R3 (commits `e32f71c` + `75dd63f`). Sub-bundle C reads the AMENDED §A.7 + §D Task A.1 text, NOT the original. 2008+ lines.
- **Sub-bundle C scope:** plan §F (lines 1257-1334); 5 tasks T-C.0..T-C.4. + Electives amendment §2 Task C.5 (1 task).
- **Cross-bundle invariants:** plan §I (lines 1665-1744); 15 invariants. Sub-bundle C exercises §I.3 (risk_policy split — N/A for tier/deviation since governance metrics use AT-TRADE-TIME `capital_floor_constant_dollars` directly per §A.5; tier-comparison's Wilson + bootstrap CIs are statistical-honesty only), §I.5 (BaseLayoutVM mixin — both new VMs extend it), §I.6 (HTMX failure-surface budget LOCK; §A.9 pure server-render — T-C.5 toggle uses `<a href="?exclude_discrepancies=1">` static-render NOT HTMX OOB-swap), §I.8 (decoupling discipline), §I.14 (empty-cohort rendering — discriminating tests required for n=0/1/2 per surface), §I.15 (operator-witnessed gate per surface — 3 browser + 1 inline).

### §0.2 Electives amendment
- **AMENDMENT_PATH:** `docs/phase10-electives-amendment.md`
- **Amendment status:** SHIPPED 2026-05-13 at `9525f17`; NORMATIVE supplement to plan §A.4 + §E + §F + §H.
- **Sub-bundle C impact:** ONE elective task — T-C.5 per-cohort "exclude trades with unresolved discrepancies" filter (§11.2(c) election). See amendment §2 Task C.5 for full acceptance criteria. Adds 1 task + 1 gate surface to Sub-bundle C (Sub-bundle C goes from 2 to 3 browser surfaces + 1 inline = 4 total; under ≤6 budget).

### §0.3 Spec
- **SPEC_PATH:** `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md`
- **Spec status:** Codex R1-R5 substantive + R6 confirmation; SHIPPED 2026-05-06 at `fe6cb45`; 641 lines; RESEARCH-POSTURE.
- **Sub-bundle C spec coverage:** §3.3 tier-comparison metrics (Tasks C.1+C.2); §3.7 deviation-outcome metrics (Tasks C.1+C.3); §4.3 tier-comparison view surface (Task C.2); §4.7 deviation-outcome view surface (Task C.3); §5 honesty policy applied across all surfaces (cohort n<5 individual suppression; descriptor suppressed until BOTH A+ AND Sub-A+ ≥5); §3.3 R1 M3 BINDING LOCK (`cohort_ci_overlap_descriptor` is TEXT, NOT a boolean significance flag); §3.7 R1 M4 BINDING LOCK (`cohort_decision_criterion_evaluation_text` is operator-manual-only — Sub-bundle C renders the seed text + accepts that V1 has no automated evaluation).

### §0.4 Project state at dispatch time
- **HEAD on `main`:** `5bddb02` (mid-Phase-10 orchestrator handoff brief commit; post-Sub-bundle-B-ship housekeeping at `2d01890` + handoff brief).
- **Test count (main HEAD):** **2964 fast passing + 2 skipped on main HEAD `5bddb02`** (1 cross-bundle pin from Sub-bundle A T-A.7 + 1 Task 7.3 operator-only). 3 pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py` failures NOT regressions; banked separately. **Worktree-side baseline:** ~2960 fast passing + 6 skipped (adds 4 fixture-absent skips for `thinkorswim/*.csv` not in worktree dir). Implementer runs from worktree, so plan §F baseline-test-count documentation should reflect the WORKTREE-side number.
- **Ruff baseline:** **18 (E501 only).** Unchanged across Sub-bundle A + B + entire Phase 9 arc.
- **Schema version:** **v17.** LOCKED since Phase 9 Sub-bundle A; Sub-bundle C introduces ZERO schema changes per §A.0 + §I.1 LOCK. `EXPECTED_SCHEMA_VERSION` stays at 17.
- **Active risk_policy:** `policy_id=5` (Option C revert post-Sub-bundle-A; `max_account_risk_per_trade_pct=0.5` cfg-aligned; `capital_floor_constant_dollars=7500.0`; `scratch_epsilon_R=0.10`). Chain: 1 (seed) → 2 (S3-test) → 3 (S2.bis-divergence) → 4 (S2.bis-revert) → **5 (ACTIVE)**. Unchanged through Sub-bundle B.
- **Production trades:** 8 total; 5 open (DHC/YOU/VSAT/CVGI/LAR) + 3 closed (VIR/CC/SGML). All 8 have `risk_policy_id_at_lock IS NULL` (pre-Phase-9 legacy; §A.5 NULL-stamp fallback applies — they render with `[legacy: pre-Phase-9 trade]` annotation in cohort metrics). 2 orphan-labeled closed-trade cohorts surfaced at Sub-bundle B's S2 gate: "inaugural trade test" (VIR) + "Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness" (CC + SGML). Sub-bundle C's tier-comparison surface should treat these as visible cohort columns (consistent with B's enumeration).

### §0.5 Sub-bundle A interface inheritance — AMENDED plan §A.7 + Sub-bundle B implementation conventions

**CRITICAL:** Plan §A.7 + §D Task A.1 were AMENDED in-tree during Sub-bundle A Codex R2 + R3 fix commits (`e32f71c` + `75dd63f`). Sub-bundle C reads the AMENDED text. Specifically:

**HonestyBadges dataclass (per AMENDED §A.7):**
```python
@dataclass(frozen=True)
class HonestyBadges:
    confidence_floor_warning: bool   # spec §5 — visible when n < global_confidence_floor_n
    low_confidence_warning: bool     # spec §5 — visible when 3 ≤ n < 5
    window_not_full_warning: bool = False  # spec §5.4 — rolling-window not yet at N (Codex R1 Major #1 fix)
```

**Public helpers in `swing/metrics/honesty.py`** (Sub-bundle C consumes):
- `wilson_ci(*, k, n, alpha)` — STANDARD Wilson score interval (per Wikipedia primary formula; matches statsmodels' `proportion_confint(method='wilson')`; NOT continuity-correction). Plan §D Task A.1 reference value `[0.094, 0.901]` for k=2,n=4 was wrong — standard yields `[0.150, 0.850]`. Banked as V2.1 §VII.F amendment candidate.
- `bootstrap_ci_mean(*, samples, resample_count, alpha, rng_seed)` — `random.Random(rng_seed)` for determinism in tests.
- `suppress_for_n(*, metric_name, n, klass, policy)` — returns `SuppressedMetric | None`.
- `badges_for_n(*, n, policy) -> HonestyBadges` — **PUBLIC** (per R1 Minor #1 + R3 Major #1; new code uses public).
- `render_class_a(*, k, n, policy, metric_name)` → `WilsonCI | SuppressedMetric`
- `render_class_b(*, samples, policy, metric_name)` → `BootstrapCI | SuppressedMetric`
- `render_class_c(*, value, n, n_wins, n_losses, policy, metric_name)` → `tuple[float | None, HonestyBadges] | SuppressedMetric`
- `render_class_d(*, samples_in_window, window_n, policy, metric_name, underlying_class, events_in_window=None, n_wins=None, n_losses=None)` → `tuple[..., HonestyBadges, str] | SuppressedMetric`

**Risk_policy resolver (per AMENDED implementation, not plan §A.5 original):**
- `swing/metrics/policy.py:read_live_policy(conn) -> RiskPolicy` — Sub-bundle C may consume for read-side tie-breakers (e.g., live `global_confidence_floor_n` for suppression dispatch).
- `swing/metrics/policy.py:read_at_trade_time_policy(conn, *, policy_id_stamp: int | None) -> tuple[RiskPolicy, bool]` — takes `policy_id_stamp` directly, NOT `Trade` object. Sub-bundle C tier/deviation metrics are governance-class — per §A.5, they use AT-TRADE-TIME policy for any per-trade-policy-dependent computation. In Sub-bundle C, tier-comparison's cohort_win_rate + cohort_expectancy are policy-independent (counts + R-multiples); cohort_relative_to_aplus is a ratio of these. **AT-TRADE-TIME policy resolution is unlikely to be needed in Tasks C.1-C.3**, but pattern is available via `get_trade_policy_id_stamp` if needed.
- **Accessor helpers:**
  - `swing/metrics/policy.py:get_trade_policy_id_stamp(conn, *, trade_id: int) -> int | None`
  - `swing/metrics/policy.py:get_review_policy_id_stamp(conn, *, review_id: int) -> int | None`

**BaseLayoutVM mixin (per AMENDED §A.6 + §A.18):**
- `swing/web/view_models/metrics/shared.py:BaseLayoutVM` fields: `session_date: str`, `stale_banner: str | None = None`, `price_source_degraded: bool = False`, `price_source_degraded_until: str | None = None`, `ohlcv_source_degraded: bool = False`, `unresolved_material_discrepancies_count: int = 0`.
- **Sub-bundle C's `TierComparisonVM` + `DeviationOutcomeVM` MUST extend `BaseLayoutVM`.** Constructor populates `unresolved_material_discrepancies_count=count_unresolved_material(conn)` per §A.18.

**Discrepancies helper (per §A.7.1):**
- `swing/metrics/discrepancies.py:count_unresolved_material(conn) -> int` — Sub-bundle C VMs invoke this in their constructors. T-C.5 ALSO consumes `swing/data/repos/reconciliation.py:list_unresolved_material_for_active_trades` + closed-trade companion to build the filter helper.

**Cohort helpers (per §A.4 + Sub-bundle B):**
- `swing/metrics/cohort.py:list_trades_for_cohort(conn, *, hypothesis_label, state_filter)` — canonicalizes hypothesis_label.
- `swing/metrics/cohort.py:list_closed_trades_for_cohort(conn, *, hypothesis_label)` — shorthand for `state_filter=('closed', 'reviewed')`.
- `swing/metrics/cohort.py:count_per_cohort(conn) -> dict[str, int]` — all distinct hypothesis_label values seen on closed trades.
- **Sub-bundle B established cohort-tab enumeration convention** (per phase3e-todo amendment #5): render ALL distinct `hypothesis_label` values across closed trades (registered + orphan); default-active = FIRST registered cohort. Sub-bundle C's tier-comparison surface should follow this convention — cohort columns are the 4 registered cohorts (per spec §4.3 "4-cohort table" wording); orphan-labeled trades are EXCLUDED from tier-comparison + deviation-outcome (these surfaces compare against the 4 registered taxonomy, not orphan ad-hoc labels). The B convention applies on the trade-process surface (tab enumeration); C surfaces are taxonomy-locked to the 4 registered cohorts. Discriminating test required (see §0.7 T-C.2 + T-C.3).

**Cross-bundle pin (still SKIPPED at T-A.7):**
- `tests/web/test_view_models/test_base_layout_vm_coverage.py::test_existing_dashboard_vm_has_unresolved_material_field` is `@pytest.mark.skip(reason="Sub-bundle E T-E.3 adds field to existing base-layout VMs")`. Sub-bundle C does NOT touch this skip; it remains pinned for Sub-bundle E.

**Sub-bundle B sub-VM exclusion convention (per Sub-bundle B return report §7.2):**
- `tests/web/test_view_models/test_base_layout_vm_coverage.py::_SUB_VM_EXCLUSIONS` set was extended at Sub-bundle B integration with `CohortTabVM` + `CohortProgressVM`. Sub-bundle C MUST extend the same set with any new sub-VM class ending in `VM` that composes into a page VM without extending BaseLayoutVM (e.g., `TierCellVM`, `DeviationRowVM`, `CohortOverlapDescriptorVM` — whatever C's implementation surfaces). **Forward-binding lesson: exclusion-list update lands in the SAME COMMIT that introduces the new sub-VM.**

**Sub-bundle B implementation conventions (BINDING for C):**

Per Sub-bundle B return report §5 + §8 + the 5 banked V2.1 §VII.F amendment candidates:

1. **`mistake_cost_R` / `lucky_violation_R` aggregator pattern (NEW forward-binding lesson #18):** ALWAYS recompute per-trade via Phase 6 helpers. `review_log` is CADENCE-grain (no per-trade FK); cadence aggregate CANNOT be cleanly mapped onto cohort-grain sum. **Sub-bundle C applicability:** if T-C.1 tier/deviation computations reference `mistake_cost_R` or `lucky_violation_R` aggregates (unlikely per spec §3.3 + §3.7 — those surfaces are win-rate + expectancy + relative-to-A+, NOT mistake-cost), MUST follow the same per-trade-recompute pattern. Inspection of spec §3.3 + §3.7 inventories shows NO mistake_cost_R / lucky_violation_R fields in tier-comparison or deviation-outcome; this lesson is "watch for spec-creep, don't introduce new mistake-cost references". **More broadly:** any cadence-grain audit-table column (`reconciliation_runs.summary_json`; `review_log.total_*`) MUST NOT be aggregated to cohort-grain without per-trade FK.

2. **`ALL_COHORTS_KEY='__all__'` sentinel** (Sub-bundle B URL convention for "all closed trades" toggle on trade-process card). Sub-bundle C surfaces 4-cohort comparisons (tier + deviation) — there is no "all" toggle on these surfaces per spec §4.3 + §4.7. NOT directly applicable, but pattern available if Sub-bundle C introduces additional toggles (e.g., T-C.5 `?exclude_discrepancies=1` is a separate URL parameter, NOT a cohort selector).

3. **`cumulative_R_pct_of_capital` rendered in PERCENT units (NEW forward-binding lesson #19):** Sub-bundle B chose PERCENT (NOT proportion) to match `absolute_loss_tripwire_pct` comparison. **Forward-binding for Sub-bundle C percent-vs-proportion metrics:**
   - `cohort_relative_to_aplus`: ratio of cohort_expectancy / aplus_expectancy. Could be rendered as proportion (e.g., `0.75`), percent (e.g., `75%`), or "relative to A+" delta (e.g., `-25%`). **Pin at T-C.1:** rendering unit MUST be explicit in VM + template + discriminating test. **Recommended:** percent (e.g., `75.0%` or `-25.0%` depending on whether absolute fraction or delta-from-100%), matching spec §3.3 wording "expressed as percentage of A+ baseline". **Implementer MUST select + cite + add discriminating test.**
   - `cohort_expectancy_relative_to_aplus_pct`: spec §3.7 field name has `_pct` suffix → PERCENT units implied (e.g., `-25.0` for "Sub-A+ expectancy is 25% below A+ baseline"). **Pin at T-C.1:** percent units with sign convention `(sub_aplus - aplus) / aplus * 100`; discriminating test required (NaN handling when aplus expectancy = 0).

4. **Cohort-tab enumeration scope (Sub-bundle B precedent; BINDING):** Sub-bundle B surfaced 7 tabs at production gate (4 pre-registered + 2 orphan + "All"). Sub-bundle C surfaces are **TAXONOMY-LOCKED to 4 registered cohorts only** per spec §4.3 (tier-comparison) + §4.7 (deviation-outcome). Orphan-labeled trades are NOT rendered as additional columns/rows on these surfaces. Rationale: tier-comparison is "A+ vs the 3 other registered hypothesis classes per the taxonomy"; orphan ad-hoc labels are observational metadata for trade-process card (which is per-cohort EDA), NOT comparison metadata for tier/deviation (which is taxonomy-locked decision support).

5. **Sub-VM exclusions added to `_SUB_VM_EXCLUSIONS` in `tests/web/test_view_models/test_base_layout_vm_coverage.py`:** existing `ConfidenceBadgeVM` / `ProvisionalBadgeVM` / `SuppressionRowVM` + Sub-bundle B added `CohortTabVM` + `CohortProgressVM`. **Sub-bundle C's new sub-VMs MUST be added to the same exclusion set IN THE SAME COMMIT** (per forward-binding lesson surfaced in §7.2 of Sub-bundle B return report).

### §0.6 19-lesson forward-binding catalog (Phase 9 arc + Sub-bundle A + B → C)

Cumulative lesson catalog for Sub-bundle C dispatch. Lessons 1-17 from Sub-bundle B dispatch brief §0.6; lessons 18-19 NEW from Sub-bundle B return report §8.

| # | Lesson | Sub-bundle C applicability |
|---|---|---|
| 1 | `__post_init__` validator pattern on all new dataclasses | **YES** — `TierComparisonResult`, `DeviationOutcomeResult`, `TierComparisonVM`, `DeviationOutcomeVM`, any sub-VMs (TierCellVM, DeviationRowVM, etc.) need NaN/inf rejection + invariant assertions (e.g., n≥0; CI lower ≤ upper) |
| 2 | Service-layer transaction discipline | N/A (Sub-bundle C is read-only; no new writes — T-C.5 toggle is GET query parameter) |
| 3 | NO `INSERT OR REPLACE` | N/A |
| 4 | Server-stamping discipline at handler entry | N/A (no new forms) |
| 5 | Composition-surface enumeration via `^def` grep | **YES** — pre-implementation recon greps Sub-bundle A interface + Sub-bundle B `swing/metrics/process.py` + cohort helpers; do NOT memory-enumerate |
| 6 | Empirical-verification of brief assertions | YES — verify spec §3.3 + §3.7 metric formulas + cohort_ci_overlap_descriptor text-only lock (§3.3 R1 M3) before locking |
| 7 | Form-render hidden anchors round-trip | N/A (no new forms; T-C.5 toggle is `<a href="?exclude_discrepancies=1">` static-render) |
| 8 | POST-time recompute of "latest-of-something" TOCTOU | N/A |
| 9 | Test fixtures USERPROFILE+HOME monkeypatch | N/A (Sub-bundle C tests don't exercise `write_user_overrides`) |
| 10 | HTMX browser-only failure surfaces | **YES** — operator-witnessed gate is BINDING for 2 new browser surfaces (S2 `/metrics/tier-comparison` + S3 `/metrics/deviation-outcome`) + 1 toggle verification (S4 T-C.5 on both surfaces). Even though §A.9 locks pure server-render (no HTMX OOB-swap), the toggle href + base-layout integration still need browser-side validation. |
| 11 | `<tr>`-leading HTMX response | N/A (per §A.9 + §I.6 — pure server-rendered HTML; no HTMX OOB-swap) |
| 12 | matplotlib mathtext | N/A (Sub-bundle C has no charts; inline SVG is Sub-bundle E only) |
| 13 | `base.html.j2` shared fields require adding to EVERY base-layout VM | **YES** — both new VMs MUST extend BaseLayoutVM mixin per §A.18; cross-bundle T-A.7 pin stays SKIPPED |
| 14 | Session-anchor read/write predicate alignment | N/A (Sub-bundle C surfaces are not session-keyed; queries are all-time cohort aggregates) |
| 15 | Discriminating-test arithmetic | **YES** — every acceptance test must distinguish correct from buggy implementations (per spec §4.3 + §4.7 binding worked examples; per §A.5.1 multi-policy patterns from Sub-bundle B) |
| 16 | Plan §A.7 amendments flow same commit as code (Sub-bundle A R2 M#1 + R3 M#1) | YES — if Sub-bundle C's implementation adds new public function / dataclass field / signature param in `swing/metrics/honesty.py` OR shipped Sub-bundle B interface, plan §A.7 binding interface MUST update in-tree to match. Likely-OFF in C (interface locked at A close; B did not need new amendments). |
| 17 | Statistical helper formula explicit pin (Sub-bundle A Wilson CI ambiguity) | **YES** — `cohort_ci_overlap_descriptor` text-only-vs-boolean (spec §3.3 R1 M3 LOCK; verbatim format pinned in T-C.1 acceptance); bootstrap_ci_mean tail-handling already pinned in §A.7. Watch for any new helper Sub-bundle C introduces. |
| **18 (NEW from Sub-bundle B)** | Cadence-grain audit tables CANNOT be cleanly mapped to cohort-grain metrics without per-trade FK | **YES — APPLY DEFENSIVELY:** spec §3.3 + §3.7 fields do NOT reference `review_log` aggregates by name, but if implementer is tempted to short-circuit a cohort sum via `reconciliation_runs.summary_json` or any cadence-grain column, REJECT. Discriminating-test pattern: plant a conflicting cadence row + assert metric reflects per-trade compute, NOT planted aggregate. |
| **19 (NEW from Sub-bundle B)** | Unit-semantic precision (percent vs proportion) needs explicit rendering pin in VM + template + discriminating test | **YES — DIRECTLY APPLICABLE:** `cohort_relative_to_aplus` and `cohort_expectancy_relative_to_aplus_pct` are the two C metrics where this lesson binds. See §0.5 #3 above for the specific pin recommendation. Discriminating test pattern: assert numeric value AND assert rendered text contains the unit string ("75.0%" not "0.75"). |

### §0.7 Sub-bundle C scope summary (per plan §F + electives amendment §2 Task C.5)

| Task | Files | Acceptance | Test count est. |
|---|---|---|---:|
| **T-C.0** recon | read-only | Sub-bundle A interface intact; Sub-bundle B `swing/metrics/process.py` + cohort helpers intact; document 4 cohort `decision_criteria` seed text + `target_sample_size` + `consecutive_loss_tripwire` + `absolute_loss_tripwire_pct` verbatim from `swing/data/migrations/0008_hypothesis_registry.sql` | 0 |
| **T-C.1** §3.3 + §3.7 tier-comparison + deviation-outcome computations | `swing/metrics/tier.py` + `tests/metrics/test_tier.py` | `compute_tier_comparison(conn) -> TierComparisonResult` (per-cohort Wilson win-rate CI + bootstrap expectancy CI + per-non-A+ cohort_relative_to_aplus + `cohort_ci_overlap_descriptor` text; spec §3.3 R1 M3 TEXT-ONLY LOCK); `compute_deviation_outcome(conn) -> DeviationOutcomeResult` (per-cohort `doctrine_deviation_class` + `expectancy_relative_to_aplus_pct` when both n≥5 + `decision_criterion_evaluation_text` from seed; spec §3.7 R1 M4 manual-text LOCK); suppression cascades per spec §4.3 + §4.7; UNIT PINS per §0.5 #3 binding for percent metrics | ~15-25 |
| **T-C.2** TierComparisonVM + route + template | `swing/web/view_models/metrics/tier_comparison.py` + `swing/web/routes/metrics.py` (add `GET /metrics/tier-comparison`) + `swing/web/templates/metrics/tier_comparison.html.j2` + `tests/web/test_view_models/test_tier_comparison_vm.py` | `TierComparisonVM` extends BaseLayoutVM; 4-cohort side-by-side table (taxonomy-locked, NO orphan columns); per-cohort cells render WilsonCI + bootstrap CI + relative-to-A+ when both n≥5; `cohort_ci_overlap_descriptor` rendered as single text block (NOT per-cohort, NOT boolean); template extends `base.html.j2`; new sub-VMs (e.g., TierCellVM) added to `_SUB_VM_EXCLUSIONS` in SAME commit | ~6-10 |
| **T-C.3** DeviationOutcomeVM + route + template | `swing/web/view_models/metrics/deviation_outcome.py` + `swing/web/routes/metrics.py` (add `GET /metrics/deviation-outcome`) + `swing/web/templates/metrics/deviation_outcome.html.j2` + `tests/web/test_view_models/test_deviation_outcome_vm.py` | `DeviationOutcomeVM` extends BaseLayoutVM; per-cohort table (4 rows, taxonomy-locked); each row shows doctrine_deviation_class + expectancy_relative_to_aplus_pct (when both n≥5) + decision_criterion_evaluation_text from seed; per spec §4.7 cohort row suppressed at n<5 with "n too low" placeholder; new sub-VMs added to exclusion set in SAME commit | ~5-8 |
| **T-C.4** Sub-bundle C integration test + ruff sweep | `tests/integration/test_phase10_bundle_c_e2e.py` + ruff sweep | E2E happy path: seed varied per-cohort sample sizes (e.g., A+ n=6 + Near-A+ n=4 + Sub-A+ VCP n=8 + Capital-blocked n=2); verify suppression ↔ rendering transitions (cohort with n<5 shows individual suppression; both A+ AND Sub-A+ ≥5 unlocks `cohort_ci_overlap_descriptor` text; descriptor format matches `"A+ CI [a, b] vs Sub-A+ CI [c, d] — overlap: yes"` per spec §4.3 worked example) | ~3-5 |
| **T-C.5** (elective) per-cohort "exclude trades with unresolved discrepancies" filter | `swing/metrics/cohort.py` (add `filter_trades_without_unresolved_material_discrepancies(conn, trades) -> list[Trade]`) + modify TierComparisonVM + DeviationOutcomeVM constructors + modify route handlers + modify templates + `tests/metrics/test_cohort_filter.py` | Helper consumes Phase 9 Sub-bundle B repo (`list_unresolved_material_for_active_trades` + closed-trade companion) via single subquery on trade_id; VMs accept `exclude_unresolved_discrepancies: bool = False` (default OFF); route handlers accept `?exclude_discrepancies=1` query parameter; template renders toggle link; suppression text formatting includes "(excluded N trades with unresolved discrepancies)" when filter active; filter-active brings cohort below n<5 → re-suppress per §5 thresholds (discriminating test) | ~5-8 |

**Projected test count delta: +34..+56 fast tests** (per plan §F +27..+48 projection + electives amendment T-C.5 +5..+8). Above-projection precedent likely per Sub-bundle A's +128 + Sub-bundle B's +73 overshoots; expected final ~2998..3020 worktree-side / ~3002..3024 main HEAD.

### §0.8 BINDING semantics — cadence-grain rejection (Sub-bundle B forward-binding lesson #18)

If during T-C.1 implementation any cohort-grain metric appears to short-circuit via a cadence-grain column (`reconciliation_runs.summary_json`, `review_log.total_*`, or any future cadence-grain JSON blob), **REJECT and recompute per-trade**. Spec §3.3 + §3.7 fields are all per-trade-derivable (win/loss/scratch counts, R-multiples, expectancy means). No legitimate cohort-grain field in Sub-bundle C requires cadence-grain aggregation. **Discriminating-test pattern (binding when applicable):** plant a conflicting cadence-grain row + assert the cohort metric reflects per-trade compute, NOT the planted aggregate. T-C.5 specifically reads `reconciliation_discrepancies` (per-trade attribution; NOT cadence) — that is the correct posture.

### §0.9 BINDING semantics — percent-vs-proportion explicit pin (Sub-bundle B forward-binding lesson #19)

Two Sub-bundle C metrics require explicit rendering-unit pin:

**`cohort_relative_to_aplus` (spec §3.3 field; surfaces on §4.3):**
- **Definition:** ratio of `cohort_expectancy / aplus_expectancy` for non-A+ cohorts.
- **Rendering unit choice (LOCK at T-C.1):** PERCENT, with sign convention `cohort_expectancy / aplus_expectancy * 100` (e.g., `75.0` means "Sub-A+ expectancy is 75% of A+ baseline expectancy"). NaN when `aplus_expectancy == 0` (division-by-zero defense per plan §F T-C.1 discriminating-test `test_cohort_relative_to_aplus_when_aplus_has_zero_trades_returns_suppressed`).
- **Discriminating test (BINDING):** seed A+ cohort expectancy=2.0R + Sub-A+ cohort expectancy=0.5R; assert `cohort_relative_to_aplus == 25.0` (percent); assert rendered template contains "25.0%" string OR "25%" depending on precision choice. Implementer chooses precision (recommend 1 decimal place to match Sub-bundle B `cumulative_R_pct_of_capital` convention).
- **NOT acceptable:** `0.25` (proportion) — silently ambiguous when displayed alongside percent-unit fields.

**`cohort_expectancy_relative_to_aplus_pct` (spec §3.7 field; surfaces on §4.7):**
- **Definition:** `_pct` suffix in field name implies PERCENT units. Delta-from-A+: `(cohort_expectancy - aplus_expectancy) / aplus_expectancy * 100`.
- **Rendering unit choice (LOCK at T-C.1):** PERCENT delta, sign-preserving (negative = cohort below A+ baseline). E.g., A+ expectancy=2.0R, Sub-A+ expectancy=0.5R → `cohort_expectancy_relative_to_aplus_pct == -75.0` (Sub-A+ is 75% below A+).
- **Discriminating test (BINDING):** seed expectations above; assert numeric `-75.0`; assert rendered template contains "-75.0%" string with explicit minus sign and percent sign.
- **NOT acceptable:** rendering as ratio `0.25` OR as percentage-of-baseline `25.0` (loses delta semantics).

**Both metrics' tests MUST verify the rendered text contains the unit substring** (e.g., `assert "%" in response.text`) per the lesson #19 discriminating-test pattern.

### §0.10 §3.3 R1 M3 BINDING LOCK — `cohort_ci_overlap_descriptor` is TEXT, NOT boolean

Spec §3.3 R1 M3 LOCK: at our sample size (cohorts of 4-20 trades), Wilson CI overlap as a binary significance test is statistically meaningless. Spec mandates rendering the descriptor as TEXT showing both CIs + an overlap qualifier word.

**Verbatim format (LOCK):** `"A+ CI [a, b] vs Sub-A+ CI [c, d] — overlap: yes"` (or `"no"`). The 4 numeric values are the Wilson CI bounds for win_rate per cohort, formatted to 2 decimal places (e.g., `[0.40, 0.85]`). The overlap qualifier is computed by interval-intersection: `max(a, c) <= min(b, d) → "yes"`.

**Suppression (LOCK):** descriptor is suppressed (rendered as "n too low" placeholder) until **BOTH** A+ AND Sub-A+ cohorts have n≥5. Suppression cascades per spec §4.3 (cohort with n<5 suppresses ITS cells; descriptor needs both A+ AND Sub-A+ ≥5).

**Per spec §3.3 R1 M3 + plan §F Task C.1 acceptance:** NO boolean significance flag. NO p-value. NO confidence-interval-test. Text-only descriptor. Codex will check.

### §0.11 §3.7 R1 M4 BINDING LOCK — `cohort_decision_criterion_evaluation_text` is MANUAL ONLY in V1

Spec §3.7 R1 M4 LOCK: the per-cohort decision-criterion evaluation in V1 is operator-manual — Sub-bundle C renders the seed text verbatim from `swing/data/migrations/0008_hypothesis_registry.sql` (`decision_criteria` column). NO automated evaluation in V1. Operator reads the seed text + manually decides whether the cohort's actual metrics meet the criterion.

**Verbatim 4-cohort `decision_criteria` seed text (from Sub-bundle B return report §9 + migration 0008 lines 49-67):**

| Cohort name | `decision_criteria` seed text |
|---|---|
| `A+ baseline` | `Mean R-multiple > 0; lower-bound Wilson CI on win rate > 30%` |
| `Near-A+ defensible: extension test` | `Mean R-multiple within 25% of A+ baseline mean` |
| `Sub-A+ VCP-not-formed` | `Confirm negative mean R-multiple` |
| `Capital-blocked: smaller-position test` | `Mean R-multiple positive; defensibility of smaller-position approach` |

Sub-bundle C's deviation-outcome surface renders these verbatim per row. Discriminating test required (`test_deviation_outcome_decision_criterion_text_renders_seed_text` per plan §F T-C.1). Sub-bundle B already established the rendering pattern for hypothesis-progress card; Sub-bundle C re-uses the seed text on the deviation-outcome surface.

### §0.12 T-C.5 elective spec (per electives amendment §2 Task C.5)

**Scope:** adds a per-cohort filter toggle that excludes trades with unresolved material reconciliation discrepancies from cohort aggregates. Surface lives on tier-comparison + deviation-outcome views (Sub-bundle C scope); helper is reusable in Sub-bundle B's trade-process card + Sub-bundle D's surfaces (V2 candidate).
**Est. impl:** ~1-2hr.
**Schema impact:** ZERO — Phase 9 Sub-bundle B's `swing/data/repos/reconciliation.py:list_unresolved_material_for_active_trades` + closed-trade companion are shipped.

**Acceptance criteria (verbatim from electives amendment §2):**
- New helper `swing/metrics/cohort.py:filter_trades_without_unresolved_material_discrepancies(conn, trades) -> list[Trade]` returns the subset of trades that have ZERO unresolved material discrepancies. Single-query: SELECT `trade_id` from `reconciliation_discrepancies` WHERE `material_to_review=1 AND resolution IS NULL`; exclude those `trade_id`s.
- `CohortFilter` enum extended (or new bool param) in tier + deviation VMs: `exclude_unresolved_discrepancies: bool = False` (default OFF; operator opts in via query string `?exclude_discrepancies=1`).
- Route handlers for `GET /metrics/tier-comparison` + `GET /metrics/deviation-outcome` accept the query parameter + thread it through to VM construction.
- Template renders a toggle link/checkbox: `<a href="/metrics/tier-comparison?exclude_discrepancies=1">Hide trades with unresolved discrepancies</a>` (or HTMX-OOB toggle if cleaner; static-render is acceptable per spec §4.9 "No client-side compute"). **§A.9 LOCK: static-render `<a>` href is the V1 pattern; NO HTMX OOB-swap.**
- TestClient regression: `tests/metrics/test_cohort_filter.py` covers (a) helper returns full list when no discrepancies; (b) helper excludes trades with unresolved material discrepancies; (c) helper INCLUDES trades whose discrepancies are resolved (resolution NOT NULL); (d) helper INCLUDES trades whose discrepancies are non-material (material_to_review=0); (e) route handler with `?exclude_discrepancies=1` produces a smaller cohort denominator than without; (f) suppression-text formatting includes "(excluded N trades with unresolved discrepancies)" when filter is active.

**Watch items:**
- When filter is active and reduces cohort sample size below the §5 suppression threshold, the metric must re-suppress per the smaller `n`. **Discriminating test (BINDING):** seed cohort with 5 closed trades + 3 of them have unresolved material discrepancies → filter brings cohort to n=2 → assert suppression (n<3 per Class A).
- Operator-witnessed gate surface: T-C.5 is verified at S4 (toggle on tier-comparison + deviation-outcome browser surfaces).
- V2 candidate banked: extend the helper to support the spec §A.11.1 "exclude trades stamped during paused intervals" filter family — same UI shape, same VM pattern.

**Cross-bundle pin:** none in V1 (helper is shared but each VM constructs independently).

---

## §1 Worktree + binding conventions

### §1.1 Worktree
- **Branch:** `phase10-bundle-C-tier-and-deviation`
- **Worktree directory:** `.worktrees/phase10-bundle-C-tier-and-deviation/`
- **BASELINE_SHA:** `5bddb02` (current main HEAD; mid-Phase-10 orchestrator handoff brief commit).
- **Worktree branching point:** current HEAD of `main` at worktree-creation time (resolve via `git rev-parse main`; expected to be the dispatch-brief commit SHA after this brief lands).

### §1.2 Marker-file workflow
- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all task commits land + Codex chain converges + before final return-report commit: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits
- Conventional prefixes per plan §F + electives amendment §2 suggested commit shapes (`feat(metrics): ...`, `test(metrics): ...`, `feat(web): ...`, `chore(metrics): ...`).
- One commit per task; Codex-fix commits as `fix(phase10-bundle-C): Codex RN <severity> #N — <description>`.
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.

### §1.4 Branch isolation + ownership
- Commits on branch only; no push to origin from worktree.
- **Implementer (you) owns:** copowers:executing-plans invocation → task-by-task TDD → Codex iteration → return-report commit.
- **Orchestrator owns:** plan-triage at dispatch time + integration merge to main + Sub-bundle D dispatch commissioning post-C-ship.

### §1.5 Verify command (basic; copowers:executing-plans handles full task execution + Codex review)
```powershell
# After all tasks land + Codex chain converges:
git log --oneline HEAD~10..HEAD
python -m pytest -m "not slow" -q
ruff check swing/ --statistics
python verify_phase10.py
```

---

## §2 Operator-witnessed verification gate (Sub-bundle C)

Per plan §F + electives amendment §2 + §I.15 BINDING:

| # | Surface | Type | Acceptance |
|---|---|---|---|
| **S1** | pytest fast-suite + ruff + verify_phase10 | Inline | `python -m pytest -m "not slow" -q` GREEN at ~2994..3020 fast tests (worktree-side); 3 pre-existing `test_phase8_pipeline_walkthrough.py` failures unchanged; `ruff check swing/` baseline 18; `python verify_phase10.py` exits 0. |
| **S2** | `/metrics/tier-comparison` | **Browser (operator-witnessed via Chrome MCP on port 8081 to avoid collision with operator's 8080 session)** | `swing web --port 8081` → navigate to `http://127.0.0.1:8081/metrics/tier-comparison` → confirm: (a) page renders 200; (b) 4-cohort side-by-side table (taxonomy-locked: A+ baseline / Near-A+ / Sub-A+ VCP-not-formed / Capital-blocked); (c) per-cohort cells render Wilson win-rate CI + bootstrap expectancy CI when n≥5; "n too low" placeholder when n<5; (d) cohort_relative_to_aplus rendered as PERCENT for non-A+ cohorts when both A+ AND that cohort have n≥5 (per §0.9 LOCK); (e) `cohort_ci_overlap_descriptor` rendered as TEXT block (single block, not per-cohort) when BOTH A+ AND Sub-A+ have n≥5; format `"A+ CI [a, b] vs Sub-A+ CI [c, d] — overlap: yes|no"` per §0.10 LOCK; (f) base-layout integration intact (nav, session date, dark-theme toggle, discrepancy badge); (g) no console errors. **Production state expectation:** all 4 registered cohorts have small samples (most likely n<5); descriptor will be suppressed; cohort cells will mostly render "n too low" placeholders. Verify the suppression text + the fallback rendering. |
| **S3** | `/metrics/deviation-outcome` | **Browser (operator-witnessed via Chrome MCP)** | `http://127.0.0.1:8081/metrics/deviation-outcome` → confirm: (a) page renders 200; (b) 4-cohort rows (taxonomy-locked, NO orphan rows); (c) each row shows `doctrine_deviation_class` text + `expectancy_relative_to_aplus_pct` rendered as PERCENT delta with sign (e.g., "-75.0%") when both that cohort AND A+ have n≥5; (d) decision_criterion_evaluation_text renders seed text verbatim from migration 0008 (the 4 seed strings in §0.11); (e) per spec §4.7 cohort row suppressed at n<5 → "n too low" placeholder; (f) no console errors. **Production state expectation:** decision-criterion text always renders (seed-text-verbatim is unconditional); per-cohort metric cells mostly suppressed due to low n. |
| **S4** | T-C.5 toggle verification on both surfaces | **Browser (operator-witnessed via Chrome MCP)** | (a) Navigate to `http://127.0.0.1:8081/metrics/tier-comparison` (no query param) → note cohort denominators; (b) click "Hide trades with unresolved discrepancies" toggle (URL becomes `?exclude_discrepancies=1`) → page reloads → cohort denominators should equal or decrease (zero if no unresolved discrepancies exist in production state); (c) suppression text formatting includes "(excluded N trades with unresolved discrepancies)" when filter is active AND N>0; (d) repeat for `/metrics/deviation-outcome?exclude_discrepancies=1`; (e) verify toggle href on the page (with filter active) points back to the no-filter URL OR a toggle-off variant. **Production state expectation:** at handoff, 30 reconciliation_discrepancies all resolved as `acknowledged_immaterial`; filter-active state should equal filter-inactive state (no trades excluded). The test still validates the URL plumbing + suppression-text formatting + base-layout integration. |

**Gate session ≤ 6 surfaces budget (dispatch brief §1.3):** Sub-bundle C has 4 surfaces — 1 inline + 3 browser (S2 + S3 + S4 with S4 being a 2-page toggle exercise). Well under budget.

**Chrome MCP availability:** orchestrator drives S2 + S3 + S4 via Chrome MCP `mcp__claude-in-chrome__*` tools at gate time (Sub-bundle A + B precedent). Load tools via `ToolSearch` with `select:mcp__claude-in-chrome__<tool_name>` before invoking. **Use port 8081** to avoid collision with operator's main-HEAD `swing web` session on 8080.

---

## §3 Skill posture + adversarial review

- **Invoke `copowers:executing-plans`** (NOT `superpowers:executing-plans` or `superpowers:subagent-driven-development` directly — the copowers wrapper handles Codex review automatically after task commits land).
- Skill inputs:
  - `PLAN_PATH=docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`
  - `AMENDMENT_PATH=docs/phase10-electives-amendment.md`
  - `SUB_BUNDLE=C` (Tasks T-C.0..T-C.4 + T-C.5 elective)
  - `BASELINE_SHA=5bddb02`
- **Expected Codex chain:** 2-4 rounds (Sub-bundle A: 4 rounds; Sub-bundle B: 2 rounds — Phase 10 has zero schema work + Sub-bundle A locked the foundational interfaces; Sub-bundle B + C reuse the same patterns).
- Iterate per-round fixes as `fix(phase10-bundle-C): Codex RN <severity> #N — ...` commits.
- Terminate at NO_NEW_CRITICAL_MAJOR.

### §3.1 Codex value-add concentration

Adversarial review for Sub-bundle C typically catches:

- **§3.3 R1 M3 `cohort_ci_overlap_descriptor` boolean-vs-text drift** — Codex will check the descriptor is TEXT (not a boolean flag, not a p-value). Pre-empt with the verbatim format-string test from §0.10.
- **Suppression cascading** — Codex will check that descriptor is suppressed until BOTH A+ AND Sub-A+ have n≥5 (NOT just one cohort).
- **`cohort_relative_to_aplus` division-by-zero** — Codex will check that when A+ has 0 trades, non-A+ ratios are suppressed (not NaN/inf). Pre-empt with `test_cohort_relative_to_aplus_when_aplus_has_zero_trades_returns_suppressed` from plan §F T-C.1.
- **Percent-vs-proportion unit drift (forward-binding lesson #19)** — Codex will check that `cohort_relative_to_aplus` and `cohort_expectancy_relative_to_aplus_pct` render as percent with explicit unit string in templates; discriminating tests assert both numeric value AND unit substring per §0.9.
- **§3.7 R1 M4 `decision_criterion_evaluation_text` automation drift** — Codex will check there is NO automated evaluation logic; the surface renders seed-text-verbatim ONLY. If implementer adds even rudimentary "evaluation" (e.g., "criterion met: yes" based on win-rate threshold), reject — V1 is manual-only per spec LOCK.
- **BaseLayoutVM field population** — Codex will check that `TierComparisonVM` + `DeviationOutcomeVM` populate `unresolved_material_discrepancies_count` via `count_unresolved_material(conn)` (§A.18 cross-bundle pin). The cross-bundle pin test stays SKIPPED at Sub-bundle C (only un-skipped at T-E.3).
- **`__post_init__` validators on new dataclasses** (lesson #1) — Codex will check `TierComparisonResult`, `DeviationOutcomeResult`, `TierComparisonVM`, `DeviationOutcomeVM`, and any sub-VMs have NaN/inf rejection + invariant assertions (CI lower ≤ upper; n≥0; expectancy real).
- **Cohort enumeration scope** — Codex will check that tier-comparison + deviation-outcome surfaces are **taxonomy-locked to 4 registered cohorts** (NOT 7 like trade-process card; NOT orphan-inclusive). Discriminating test: seed 2 orphan-labeled closed trades + assert they do NOT appear as additional columns/rows on these surfaces.
- **T-C.5 helper boundary conditions** — Codex will check: filter excludes trades with material+unresolved discrepancies ONLY; trades with resolved discrepancies INCLUDED; trades with non-material discrepancies INCLUDED; trades with zero discrepancies INCLUDED. Pre-empt with the 4-branch test fixture from electives amendment §2.
- **T-C.5 suppression re-cascade** — Codex will check that filter-active reducing cohort to n<3 re-triggers Class A suppression. Discriminating test seeds cohort with 5 trades, 3 with unresolved discrepancies → filter brings cohort to n=2 → assert suppression.
- **Empty-cohort + zero-trade rendering** (§A.16 + §I.14) — Codex will check every surface renders gracefully at n=0/1/2.
- **Sub-VM exclusion-set update in same commit** — Codex will check new sub-VMs (e.g., TierCellVM, DeviationRowVM, descriptor sub-VM if introduced) are added to `_SUB_VM_EXCLUSIONS` in `tests/web/test_view_models/test_base_layout_vm_coverage.py` in the SAME COMMIT.
- **§A.9 + §I.6 LOCK: pure server-rendered HTML** — Codex will check the T-C.5 toggle is `<a href="?exclude_discrepancies=1">` (or unchecked `<form method="GET">`), NOT HTMX OOB-swap or embedded form with hx-headers.

### §3.2 Per-task Codex-check pre-emption

| Task | Common Codex finding | Pre-emption |
|---|---|---|
| T-C.0 | None expected (pure recon) | Document the 4 cohort `decision_criteria` seed text values + `target_sample_size` + `consecutive_loss_tripwire` + `absolute_loss_tripwire_pct` verbatim in PR description / recon note |
| T-C.1 | `cohort_ci_overlap_descriptor` rendered as boolean instead of text | Use exact format-string from §0.10 LOCK; discriminating test asserts substring presence |
| T-C.1 | `cohort_relative_to_aplus` returns NaN/inf when A+ n=0 | Suppress-when-aplus-zero discriminating test; return `SuppressedMetric` |
| T-C.1 | `cohort_expectancy_relative_to_aplus_pct` sign convention drift | Pin: `(cohort - aplus) / aplus * 100` (negative = below baseline); discriminating test asserts -75.0 for A+=2R, Sub-A+=0.5R |
| T-C.1 | Decision-criterion text drift from seed | Test reads seed text from `swing/data/migrations/0008_hypothesis_registry.sql` |
| T-C.1 | Suppression NOT cascading: descriptor renders even when only one of A+/Sub-A+ has n≥5 | Test seeds A+ n=6, Sub-A+ n=4 → descriptor suppressed; A+ n=6, Sub-A+ n=5 → descriptor rendered |
| T-C.2 | Orphan cohorts appear as additional columns | Test seeds 2 orphan-labeled closed trades + asserts only 4 registered cohort columns on tier-comparison |
| T-C.2 | Per-tab navigation uses HTMX OOB-swap | Use simple page rendering; no HTMX (per §A.9 lock) |
| T-C.3 | Decision-criterion text has automated evaluation logic | V1 is manual-only per §3.7 R1 M4 LOCK; render seed-text verbatim |
| T-C.3 | Cohort row visibility when n<5 | "n too low" placeholder per spec §4.7; do NOT hide the row entirely (operator needs to see the registered cohort even at n<5) |
| T-C.4 | E2E test seeds insufficient diversity | Seed varied per-cohort sample sizes covering: cohort below n=3 (full suppression); cohort at n=3..4 (point-with-warning); cohort at n=5+ (full CIs); some cohorts with both n≥5 to verify descriptor unlock |
| T-C.5 | Filter helper has wrong SQL — joins on something other than `trade_id` | Single SELECT `trade_id` from `reconciliation_discrepancies` WHERE `material_to_review=1 AND resolution IS NULL`; exclude those `trade_id`s |
| T-C.5 | Filter-active suppression-text formatting missing "(excluded N trades...)" | Discriminating test asserts substring present when filter active AND N>0; absent when filter inactive or N=0 |
| T-C.5 | Resolved-discrepancy trades incorrectly excluded | Test (c) from electives amendment §2: trade with resolution NOT NULL → INCLUDED |
| T-C.5 | Non-material discrepancy trades incorrectly excluded | Test (d): trade with material_to_review=0 → INCLUDED |
| T-C.5 | Filter route handler missing query parameter parsing | Route accepts `?exclude_discrepancies=1` (truthy) + `?exclude_discrepancies=0` (falsy) + missing (falsy) |

---

## §4 Return report shape

After all task commits land + Codex chain converges + before final return-report commit, draft a return report at `docs/phase10-bundle-C-return-report.md` (mirroring `docs/phase10-bundle-B-return-report.md` shape):

1. Final HEAD on branch + commit count breakdown (task-impl + Codex-fix; expected ~6 task-impl + 1-3 Codex-fix + 1 return-report).
2. Codex round chain (e.g., "R1 0/X/Y → R2 ... → Rn NO_NEW_CRITICAL_MAJOR").
3. Test count delta + ruff baseline delta.
4. Operator-witnessed verification surfaces (PENDING orchestrator-driven gate; S1 inline OK; S2+S3+S4 PENDING).
5. Per-task deviations from the plan (if any) with rationale; any spec-amendment candidates banked.
6. Codex Major findings ACCEPTED with rationale (if any).
7. Watch items for orchestrator (cross-bundle pins; un-skip-at-T-E.3 reminder; any V2 candidates banked).
8. Worktree teardown status (expected ACL-locked husk; 12th pending operator cleanup-script).
9. Sub-bundle D forward-binding lessons (if any new ones surfaced during executing-plans).
10. Composition-surface verification via `^def` grep (per Phase 9 + Sub-bundle A forward-binding lesson #5).
11. Any plan-text amendments applied in-tree during Codex rounds (mirror Sub-bundle A §A.7 + §D Task A.1 amendments pattern; Sub-bundle B had NONE).

---

## §5 First-step paste-ready prompt for the implementer

```
You are taking over to implement Phase 10 Sub-bundle C (Tier-comparison view + Deviation-outcome view + per-cohort discrepancy-filter elective) for swing-trading.

WORKING DIRECTORY (after worktree creation): c:\Users\rwsmy\swing-trading\.worktrees\phase10-bundle-C-tier-and-deviation
BRANCH: phase10-bundle-C-tier-and-deviation
BASELINE_SHA: 5bddb02  (per dispatch brief §1.1; HEAD of main BEFORE this brief commit)
WORKTREE-BRANCHING-POINT: current HEAD of main at worktree-creation time (resolve via `git rev-parse main`)

The Codex diff (5bddb02 → worktree HEAD) will include one or more doc-only commits (the dispatch brief + per-task code + Codex fixes). All harmless; Codex evaluates the CODE content against the PLAN §F + ELECTIVES AMENDMENT §2.

Step 0 — Create the worktree:
  cd c:\Users\rwsmy\swing-trading
  $base = git rev-parse main
  git worktree add .worktrees\phase10-bundle-C-tier-and-deviation -b phase10-bundle-C-tier-and-deviation $base
  New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active

Step 1 — Read the dispatch brief end-to-end from the worktree:
  docs/phase10-bundle-C-executing-plans-dispatch-brief.md

Step 2 — Read the Phase 10 plan §F + electives amendment §2 + cross-bundle invariants §I:
  docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md  (§F lines 1257-1334 for tasks T-C.0..T-C.4; §I lines 1665-1744 for invariants; §A.5 + §A.7 + §A.18 for AMENDED interface contracts; §A.9 LOCK pure server-render; §A.0 LOCK zero-new-schema)
  docs/phase10-electives-amendment.md  (§2 Task C.5 for elective task spec)

Step 3 — Read the Phase 10 brainstorm spec for §3.3 + §3.7 + §4.3 + §4.7 + §5 reference:
  docs/superpowers/specs/2026-05-06-phase10-metrics-design.md  (§3.3 tier-comparison + §3.7 deviation-outcome + §4.3 + §4.7 surfaces + §5 honesty policy; §3.3 R1 M3 text-only LOCK; §3.7 R1 M4 manual-text LOCK)

Step 4 — Read binding conventions + forward-binding lessons:
  - CLAUDE.md (gotchas + project conventions; "Lessons captured" + Phase 9 arc + Sub-bundle A + B gotcha promotions are forward-binding)
  - docs/orchestrator-context.md (orchestrator-role framing; Codex-driven discipline)
  - docs/phase10-bundle-A-return-report.md (Sub-bundle A close; §10 forward-binding lessons binding here; §5 deviations banked)
  - docs/phase10-bundle-B-return-report.md (Sub-bundle B close; §5 deviations + §8 forward-binding lessons binding here)

Step 5 — Verify worktree state:
  git rev-parse HEAD                       # expect current main HEAD (typically the dispatch brief commit)
  git status                               # expect clean
  python -m pytest -m "not slow" -q        # expect baseline GREEN (~2960 passed worktree-side; 6 skipped — 1 cross-bundle T-A.7 pin + 1 Task 7.3 + 4 fixture-absent; 3 pre-existing fails in tests/integration/test_phase8_pipeline_walkthrough.py NOT regressions)
  python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"  # expect 17
  ruff check swing/ --statistics            # expect 18 E501
  python verify_phase10.py                  # expect exit 0

Step 6 — Pre-implementation recon (Sub-bundle A + B interface inheritance verification):
  grep -rn "^def " swing/metrics/honesty.py swing/metrics/policy.py swing/metrics/cohort.py swing/metrics/discrepancies.py swing/metrics/process.py
  python -c "from swing.metrics.honesty import wilson_ci, bootstrap_ci_mean, suppress_for_n, badges_for_n, render_class_a, render_class_b, render_class_c, render_class_d; from swing.metrics.policy import read_live_policy, read_at_trade_time_policy, read_at_review_time_policy, get_trade_policy_id_stamp, get_review_policy_id_stamp; from swing.metrics.cohort import list_trades_for_cohort, list_closed_trades_for_cohort, count_per_cohort; from swing.metrics.discrepancies import count_unresolved_material; print('Sub-bundle A interface intact')"
  python -c "from swing.metrics.process import compute_trade_process_metrics; print('Sub-bundle B aggregator intact')"
  grep -rn "^def " swing/web/view_models/metrics/shared.py swing/web/view_models/metrics/trade_process_card.py swing/web/view_models/metrics/hypothesis_progress_card.py
  cat swing/data/migrations/0008_hypothesis_registry.sql | grep -A 1 "decision_criteria\|target_sample_size\|consecutive_loss_tripwire\|absolute_loss_tripwire_pct"  # T-C.0 recon: 4-cohort governance config verbatim
  grep -rn "^def " swing/data/repos/reconciliation.py  # T-C.5 helper recon: list_unresolved_material_for_active_trades + closed-trade companion shipped at Phase 9 Sub-bundle B
  grep -n "_SUB_VM_EXCLUSIONS" tests/web/test_view_models/test_base_layout_vm_coverage.py  # T-C.2 + T-C.3 sub-VM exclusion-set update lands SAME commit

Step 7 — Invoke copowers:executing-plans (the skill wraps superpowers:subagent-driven-development + Codex review):
  - PLAN_PATH: docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md
  - AMENDMENT_PATH: docs/phase10-electives-amendment.md
  - SUB_BUNDLE: C
  - BASELINE_SHA: 5bddb02

Step 8 — Execute tasks task-by-task per plan §F + electives amendment §2 Task C.5:
  - T-C.0 recon (no commit; document inline in PR description / return-report; capture the 4-cohort governance config verbatim)
  - T-C.1 §3.3 + §3.7 tier-comparison + deviation-outcome computations (commit: feat(metrics): §3.3 + §3.7 tier-comparison + deviation-outcome computations (T-C.1))
  - T-C.2 TierComparisonVM + route + template (commit: feat(metrics): tier-comparison VM + route + template — GET /metrics/tier-comparison (T-C.2))
  - T-C.3 DeviationOutcomeVM + route + template (commit: feat(metrics): deviation-outcome VM + route + template — GET /metrics/deviation-outcome (T-C.3))
  - T-C.4 Sub-bundle C integration test + ruff sweep (commit: chore(metrics): Sub-bundle C integration sweep (T-C.4))
  - T-C.5 per-cohort discrepancy filter elective (commit: feat(metrics): per-cohort discrepancy-filter elective (T-C.5))

Step 9 — Iterate Codex rounds + land per-round-fix commits until NO_NEW_CRITICAL_MAJOR. Expected 2-4 rounds.

Step 10 — Draft return report at docs/phase10-bundle-C-return-report.md per dispatch brief §4. Commit it.

Step 11 — Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active + signal orchestrator. Orchestrator drives operator-witnessed gate (S2 + S3 + S4 browser surfaces via Chrome MCP on port 8081 if available) + integration merge.

DO NOT:
  - Push to origin from inside the worktree
  - Merge to main (orchestrator action)
  - Use --amend or --no-verify
  - Add Claude co-author footer to commits
  - Skip the marker-file removal before final signal
  - Skip the Step 6 pre-implementation recon (Sub-bundle A + B interface verification)
  - Add ANY new schema (no `0018_*.sql` migration; no ALTER on existing tables); Phase 10 V1 §A.0 LOCK is BINDING per plan §I.1
  - Skip `__post_init__` validators on any new dataclass (Phase 9 + Sub-bundle A forward-binding lesson #1)
  - Render `cohort_ci_overlap_descriptor` as boolean or p-value; §3.3 R1 M3 BINDING LOCK is TEXT-only with verbatim format "A+ CI [a, b] vs Sub-A+ CI [c, d] — overlap: yes|no"
  - Render `cohort_relative_to_aplus` or `cohort_expectancy_relative_to_aplus_pct` as proportion (must be PERCENT with explicit unit string in template per forward-binding lesson #19 + §0.9 LOCK)
  - Add automated evaluation logic to `decision_criterion_evaluation_text`; §3.7 R1 M4 BINDING LOCK is manual-text-only (render seed verbatim from migration 0008)
  - Include orphan-labeled trades in tier-comparison or deviation-outcome surfaces (taxonomy-locked to 4 registered cohorts per spec §4.3 + §4.7)
  - Aggregate any cadence-grain audit-table column (review_log.total_*, reconciliation_runs.summary_json) to cohort-grain (forward-binding lesson #18; recompute per-trade)
  - Un-skip `test_existing_dashboard_vm_has_unresolved_material_field` (that's Task E.3's responsibility per §I.5)
  - Add HTMX OOB-swap, embedded forms, hx-headers, or HX-Redirect on /metrics/tier-comparison or /metrics/deviation-outcome or T-C.5 toggle (§A.9 + §I.6 LOCK pure server-render)
  - Add chart rendering via matplotlib or SVG (§A.10 V1 LOCK = inline SVG in Sub-bundle E only)
  - Implement per-surface routes other than /metrics/tier-comparison + /metrics/deviation-outcome (those land in D/E per plan §A.3)
  - Implement Sub-bundle D/E task scope (out of C's lane)
  - Implement T-E.5 (web-form snapshot capture) / T-E.6 (per-trade discrepancy indicator) (those land in E per electives amendment)
  - Implement §8.4 Corporate_Actions MVP (deferred as standalone post-Phase-10 dispatch per electives amendment §5)
  - Bundle this with Sub-bundle D (sequencing locked A ✓ → B ✓ → C → D → E per plan §C)
  - Add color-only badges (spec §4.9 BINDING; reliability flags as TEXT not color-only)
  - Diverge from per-metric class matrix in plan §F Task C.1 acceptance (Codex will check)
  - Use Trade dataclass to pass risk_policy_id_at_lock (Sub-bundle A signature is policy_id_stamp: int | None directly via get_trade_policy_id_stamp accessor)
  - Use Wilson-with-continuity-correction (Sub-bundle A locked standard Wilson; matches statsmodels default)
  - Use HTMX OOB-swap for the T-C.5 toggle (static-render `<a href="?exclude_discrepancies=1">` is the V1 pattern per §A.9 LOCK + electives amendment §2)
  - Forget to update `_SUB_VM_EXCLUSIONS` in `tests/web/test_view_models/test_base_layout_vm_coverage.py` when introducing new sub-VMs (must land in SAME COMMIT as the sub-VM)
```

---

## §6 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-13 (post-Sub-bundle-B-ship + post-mid-Phase-10-handoff).
- **Brief commit:** `<filled-in-after-commit>`.
- **Brief HEAD context:** `5bddb02` on main (mid-Phase-10 orchestrator handoff brief).
- **Worktree path (binding):** `.worktrees/phase10-bundle-C-tier-and-deviation/`.
- **Baseline test count (main HEAD):** 2964 fast (2 skipped). Worktree-side: ~2960 fast (6 skipped — 4 `thinkorswim/*.csv` fixture-absent + 1 cross-bundle T-A.7 pin + 1 Task 7.3 operator-only).
- **Baseline ruff count:** 18 (E501 only).
- **Plan status:** Codex R1-R6 NO_NEW_CRITICAL_MAJOR; AMENDED in-tree during Sub-bundle A R2 + R3; LOCKED.
- **Electives amendment status:** SHIPPED 2026-05-13 at `9525f17`; NORMATIVE; T-C.5 binding for Sub-bundle C.
- **Spec status:** Codex R1-R5 substantive + R6 confirmation; shipped 2026-05-06 at `fe6cb45`; 641 lines; LOCKED.
- **Expected dispatch wall-clock:** ~6-10 hr executing-plans + ~2-4 hr Codex convergence.
- **Expected test count delta:** +34..+56 fast tests; post-C ~2994..3020 worktree-side / ~2998..3020 main HEAD (matches Sub-bundle A + B overshoot precedent — actual may run higher).
- **Expected ruff delta:** 0 (baseline preserved).
- **Next per locked sequencing 8 ✓ → 9 ✓ → 10 (A ✓ → B ✓ → C → D → E):** Sub-bundle C ships → orchestrator drives operator-witnessed gate → integration merge → orchestrator queues Sub-bundle D dispatch brief drafting (capital-friction + maturity-stage + identification-vs-trade-funnel; first PROVISIONAL/LIVE dynamic badge contract surface).

---

## §7 Watch items for orchestrator (post-Sub-bundle-C-ship)

1. **Operator-witnessed gates S2 + S3 + S4** — 3 browser-side checks. Orchestrator drives via Chrome MCP on port 8081 (worktree-side `swing web --port 8081` to avoid collision with operator's 8080 session); operator drives manually otherwise. S2 + S3 verify Phase 10's third + fourth dashboard surfaces; S4 verifies T-C.5 toggle URL plumbing on both surfaces.

2. **Cross-bundle pin at T-A.7 (still SKIPPED)** — Sub-bundle C does NOT touch the skip on `test_existing_dashboard_vm_has_unresolved_material_field`. The un-skip lands at T-E.3 retrofit of the 6 existing base-layout VMs. Verify the skip remains in place at integration merge.

3. **Sub-VM exclusion-set propagation** — Sub-bundle C is expected to add 1-3 new sub-VMs to `_SUB_VM_EXCLUSIONS` (e.g., TierCellVM, DeviationRowVM, CohortOverlapDescriptorVM). Verify exclusion-set update lands in SAME COMMIT as sub-VM introduction.

4. **Spec amendment candidates** banked from Sub-bundle A (3 candidates) + Sub-bundle B (5 candidates) — Sub-bundle C may surface additional plan-text divergences requiring banking. Return-report §11 enumerates. Cumulative pending V2.1 §VII.F amendments stand at **12** entering Sub-bundle C dispatch (per phase3e-todo 2026-05-13 entry); any new divergences increment this count.

5. **§3.3 R1 M3 + §3.7 R1 M4 spec LOCKs** — both surfaces have explicit spec locks (descriptor text-only + decision-criterion manual-only). If Codex finds either lock violated, the implementer MUST fix in-tree, NOT bank as ACCEPT-WITH-RATIONALE.

6. **`verify_phase10.py` may need extension for Sub-bundle C** — Sub-bundle A landed the cross-platform verification script at worktree root. Sub-bundle C's T-C.4 may extend it with additional sanity checks (e.g., assert `/metrics/tier-comparison` route registered; assert `compute_tier_comparison` callable; assert `filter_trades_without_unresolved_material_discrepancies` callable). Banked as orchestrator-decision for Sub-bundle C return-report.

7. **Test count overshoot precedent** — Sub-bundle A projection was +35..+55, actual +128. Sub-bundle B projection was +46..+75, actual +73. Sub-bundle C projection is +34..+56; expected overshoot likely brings final to 2998..3030 worktree-side. Operator should not be alarmed if S1 test count is higher than projection.

8. **Worktree husk** — Sub-bundle C teardown expected to leave ACL-locked husk; 12th in operator cleanup-script queue.

9. **Sub-bundle D dispatch dependencies** — post-Sub-bundle-C-ship the next brief drafts Sub-bundle D (Tasks T-D.0..T-D.7; capital-friction + maturity-stage + identification-vs-trade-funnel). Sub-bundle D consumes Sub-bundle A's `resolve_live_capital_denominator_dollars` (PROVISIONAL/LIVE contract per §A.6) + introduces dynamic-badge rendering surface. T-C.5's filter helper is a V2-candidate reuse point on Sub-bundle D surfaces but NOT a hard dependency. Sub-bundle D is the first surface introducing PROVISIONAL/LIVE distinction; Codex value-add concentration moves there.

---

## §8 Dispatch order — UNCHANGED

A ✓ → B ✓ → C (this dispatch) → D → E. Sub-bundle A + B are SHIPPED; Sub-bundle C is the next dispatch. Post-Sub-bundle-C-ship → Sub-bundle D (capital-friction + maturity-stage + identification-funnel; first PROVISIONAL/LIVE dynamic badge contract surface).

---

*End of dispatch brief. Sub-bundle C is the third + fourth operator-visible Phase 10 dashboard surfaces (§4.3 tier-comparison + §4.7 deviation-outcome) + the T-C.5 per-cohort discrepancy-filter elective. All 6 tasks use AMENDED Sub-bundle A interfaces + Sub-bundle B implementation conventions; ZERO new schema; ZERO new write paths (T-C.5 is GET query parameter only); 2 new browser surfaces + 1 toggle verification = 3 browser surfaces + 1 inline = 4 total gate surfaces. Cross-bundle pin at T-A.7 stays SKIPPED for T-E.3.*
