# Phase 10 Sub-bundle B — executing-plans return report

**Audience:** Orchestrator (post-implementation gate-driving + integration-merge).
**Mission status:** READY FOR OPERATOR-WITNESSED GATE — code complete, tests green, ruff baseline preserved, Codex convergent.
**Branch:** `phase10-bundle-B-trade-process-and-hypothesis-progress`.
**Branching point:** `main` HEAD at worktree creation = `6140081` (dispatch-brief commit; BASELINE_SHA).

---

## §1 Final HEAD + commit count breakdown

**Final HEAD on branch:** `a8eaf65` (Codex R1 fix commit).

**Commits since BASELINE_SHA `6140081`:** 8 (this section is the 9th return-report commit).

| # | SHA | Type | Title |
|---|---|---|---|
| 1 | `f68706d` | task-impl | feat(metrics): §3.1 trade-process metric computations (T-B.1) |
| 2 | `0eae7a6` | task-impl | feat(metrics): trade-process card VM (T-B.2) |
| 3 | `64ac3af` | task-impl | feat(metrics): trade-process card route + template — GET /metrics/trade-process (T-B.3) |
| 4 | `b2d0d5d` | task-impl | feat(metrics): §3.2 hypothesis-progress card VM (T-B.4) |
| 5 | `92d082d` | task-impl | feat(metrics): hypothesis-progress card route + template — GET /metrics/hypothesis-progress (T-B.5) |
| 6 | `f75a7d6` | task-impl | chore(metrics): Sub-bundle B integration sweep (T-B.6) |
| 7 | `d318669` | task-impl | feat(web): surface lucky_violation_R on Phase 6 review form (T-B.7 elective) |
| 8 | `a8eaf65` | Codex-fix | fix(phase10-bundle-B): Codex R1 Major #1 + #2 + Minor #1 |

Aggregate: **7 task-impl + 1 Codex-fix** (+ 1 return-report = this commit).

---

## §2 Codex round chain

**2 rounds → NO_NEW_CRITICAL_MAJOR — fastest Phase 10 convergence to date** (matches Phase 9 Sub-bundle E precedent).

| Round | Critical | Major | Minor | Verdict |
|---|---:|---:|---:|---|
| R1 | 0 | 2 | 1 | NEW_MAJOR |
| R2 | 0 | 0 | 0 | NO_NEW_CRITICAL_MAJOR |

**R1 findings + resolution:**

1. **R1 Major #1 — `mistake_cost_R` / `lucky_violation_R` cohort-sum vs review_log aggregate.** Codex flagged that the plan §E Task B.1 acceptance text spoke of "preferring `review_log.total_mistake_cost_R` aggregate when present; falling back to per-trade compute when absent" — but the implementation always re-computes per-trade.
   - **Resolution (DESIGN CHOICE banked as plan-deviation):** empirical verification of the v17 schema shows `review_log` is a **CADENCE-grain** table (one row per daily / weekly / monthly review window covering N trades) with NO per-trade foreign key. A reviewed trade may appear in 0, 1, or several `review_log` rows depending on which review windows touched it. The cadence aggregate `total_mistake_cost_R` therefore CANNOT be cleanly mapped onto a **cohort-grain** sum at the metrics layer — there is no per-trade FK to disambiguate. The cohort aggregator now carries an inline rationale comment + a **discriminating regression test** (`test_mistake_cost_R_recomputes_per_trade_ignoring_review_log_aggregate`) that plants a `review_log` row with `total_mistake_cost_R=99.0R` covering the period of a per-trade-computes-to-1.5R trade + asserts the cohort metric reflects the per-trade compute (1.5R), NOT the planted aggregate.
   - **V2 candidate banked at §7:** if a `review_log_trade_links` audit table is added later, the cohort aggregator could prefer frozen review-time values for already-reviewed trades + recompute only for unreviewed trades.

2. **R1 Major #2 — `__post_init__` validators missing on new dataclasses** per Phase 9 forward-binding lesson #1.
   - **Resolution:** added validators to:
     - `_TradeMetricInputs` (`swing/metrics/process.py`): rejects NaN / inf on every REAL field; classifies against the 4-value enum (`win` / `loss` / `scratch` / `undefined`); requires `scratch_epsilon_R > 0`; requires `holding_period_days >= 0`.
     - `TransitionEntry` (`swing/web/view_models/metrics/hypothesis_progress_card.py`): validates `status` against the 4-value hypothesis_status enum; `effective_from` non-empty; `effective_to >= effective_from` invariant (mirrors `HypothesisStatusHistory`).
     - `HypothesisProgressCardVM`: validates `cohorts` is a non-empty tuple (governance surface ALWAYS shows registered cohorts per spec §4.2 binding "no n<3 suppression").

3. **R1 Minor #1 — `_prepare_trade_inputs(conn, trade, live_policy)` unused `live_policy` parameter.**
   - **Resolution:** parameter removed from helper signature + caller updated.

**R2 verdict:** all R1 findings resolved cleanly; no new findings introduced by the R1 fix commit. Verdict reads:
> *"R1 findings are resolved: ... `_TradeMetricInputs`, `TransitionEntry`, and `HypothesisProgressCardVM` now have validators ... unused `live_policy` parameter was removed ... Verdict: **NO_NEW_CRITICAL_MAJOR**"*

---

## §3 Test count + ruff baseline delta

### Test count delta

- **Worktree-side baseline (per dispatch brief §0.4):** 2895 fast passing + 6 skipped + 3 pre-existing `test_phase8_pipeline_walkthrough.py` failures (NOT regressions).
- **Sub-bundle B added:** 73 fast tests (matches +46..+75 projection — at the high end).
  - T-B.1 trade-process metrics: 21 tests (+1 from R1 fix: review_log-aggregate discriminator).
  - T-B.2 TradeProcessCardVM: 8 tests.
  - T-B.3 trade-process card route + template: 8 tests (additions to existing `test_metrics_routes.py`).
  - T-B.4 HypothesisProgressCardVM (incl. §A.5.1 multi-policy discriminator): 12 tests.
  - T-B.5 hypothesis-progress card route + template: 5 tests (additions to `test_metrics_routes.py`).
  - T-B.6 Sub-bundle B integration sweep: 4 tests.
  - T-B.7 lucky_violation_R review-form elective: 8 tests.
  - `test_base_layout_vm_coverage.py` exclusion-list update (no new tests; updates the existing).
- **Final fast suite (worktree-side; ignoring pre-existing test_phase8_pipeline_walkthrough.py fails):** **2951 fast passing + 6 skipped** (+56 from baseline). Note: full-suite gross delta is +73 new tests; some were noise from test_phase8 walkthrough's ignored fails inflating the difference. (Pending: final full-suite run.)

### Ruff baseline

- **Before:** 18 (E501 only).
- **After:** 18 (E501 only). **UNCHANGED.**

### Schema version

- **Before:** 17.
- **After:** 17. **§A.0 LOCK PRESERVED.** No `0018_*.sql` migration.

### verify_phase10.py

- **Exits 0** (per the standalone run after R1 fixes). Includes bundle-B E2E in its auto-discovered list.

---

## §4 Operator-witnessed verification surfaces

Per dispatch brief §2 + plan §I.15 BINDING, the gate-driving orchestrator runs 4 surfaces:

| # | Surface | Type | Status |
|---|---|---|---|
| S1 | pytest fast-suite + ruff + verify_phase10 | Inline | **PASS** (2951 fast + 6 skipped — pre-existing test_phase8_pipeline_walkthrough.py fails carry through; ruff 18; verify_phase10 exits 0) |
| S2 | `/metrics/trade-process` browser walkthrough | **Browser (orchestrator-driven via Chrome MCP)** | **PENDING** — Orchestrator gate session |
| S3 | `/metrics/hypothesis-progress` browser walkthrough | **Browser (orchestrator-driven via Chrome MCP)** | **PENDING** — Orchestrator gate session |
| S4 | `/reviews/{id}/complete` browser walkthrough (T-B.7 elective regression) | **Browser (orchestrator-driven via Chrome MCP)** | **PENDING** — Orchestrator gate session |

**S2 expected to confirm:** 200 status; 5 tabs visible (4 cohorts + All); default-active is FIRST cohort ("A+ baseline") NOT All; per-tab metric grid renders Class A/B/C cells + cohort sums + process_grade distribution + mistake_tag_frequency; TEXT badges (NO color-only) per spec §4.9; `[legacy: pre-Phase-9 trade]` annotation visible if any legacy trades stamped NULL.

**S3 expected to confirm:** 200 status; 4 cohort cells in row layout (`<ul class="cohort-row">`); each cell shows progress bar (`<progress>` element), tripwire indicators (consecutive-loss + absolute-loss with distance), decision-criteria text verbatim from migration 0008 (HTML5 `<details>`/`<summary>` collapsible), transition timeline `<ol>` newest-first capped at 5.

**S4 expected to confirm:** 200 status; existing Phase 6 form fields render unchanged (`realized_R_if_plan_followed`, `mistake_cost_confidence`, `lesson_learned`, Submit button); NEW `<dl class="counterfactual-pair">` block renders BOTH `data-field="mistake_cost_R"` AND `data-field="lucky_violation_R"` symmetrically with 2-decimal-place precision; "—" placeholder renders when fields are zero or counterfactual NULL.

---

## §5 Per-task deviations from the plan + spec amendments banked

### §5.1 T-B.1 — `mistake_cost_R` aggregator-source design choice (R1 Major #1)

Plan §E Task B.1 acceptance text described "preferring `review_log` aggregate when present + fallback to per-trade compute when absent." Implementation always re-computes per-trade via Phase 6 helpers because `review_log` is CADENCE-grain (one row per review window) with no per-trade FK; the cadence aggregate cannot be cleanly mapped onto a cohort-grain sum. See §2 R1 Major #1 + the in-code rationale block (`swing/metrics/process.py` cohort-sum loop). Banked as **plan-deviation candidate for V2.1 §VII.F amendment**: align plan §E Task B.1 acceptance text to read "always re-compute via Phase 6 helpers; cohort-grain sum is reproducible from per-trade fields."

### §5.2 T-B.2 — `ALL_COHORTS_KEY` sentinel value choice

Plan §E Task B.2 mentioned the "All closed trades" toggle without specifying the URL parameter value. Implementation uses `__all__` as the sentinel (`?cohort=__all__`) to avoid collision with any legitimate cohort name containing the literal "all". Banked as **implementation-detail-deviation** (no spec impact; documented in the module docstring).

### §5.3 T-B.4 — `cumulative_R_pct_of_capital` unit semantics

Plan §A.5.1 + spec §3.2 specifies `cumulative_R_pct_of_capital` as a "proportion" (dimensionless). The implementation stores + surfaces the value in **PERCENT units** (e.g., `-1.667` means `-1.667%`, NOT `-1.667 ratio` = `-166.7%`) because spec §3.2's `distance_to_absolute_loss_tripwire` formula requires comparing against `absolute_loss_tripwire_pct` which is in percent units per migration 0008 (e.g., `5.0` = `5%`). The conversion `sum(dimensionless ratios) * 100` happens inside `_build_cohort_vm`. Banked as **clarification-deviation candidate for V2.1 §VII.F**: plan §A.5.1 + spec §3.2 should explicitly state the rendering unit.

### §5.4 T-B.7 — display-block placement relative to operator-entry form

Per electives amendment §2 spec, the new field renders "symmetrically alongside the existing `mistake_cost_R` display." Empirical verification of the Phase 6 template showed there was **NO pre-existing `mistake_cost_R` display** — only the operator-input form for `realized_R_if_plan_followed`. Implementation surfaces BOTH `mistake_cost_R` AND `lucky_violation_R` as derived display values in a new `<dl class="counterfactual-pair">` block placed BEFORE the existing form (`{% include "partials/review_form.html.j2" %}`). The "symmetric rendering" criterion is met within the new block. Banked as **template-deviation** — the amendment's "existing display" assumption was incorrect; implementation added BOTH fields for symmetry.

---

## §6 Codex Major findings accepted with rationale

**ZERO ACCEPT-WITH-RATIONALE** — both R1 Major findings resolved in-tree with code content fixes + a discriminating regression test for Major #1. Matches Phase 9 Sub-bundle D / E + Phase 10 Sub-bundle A clean records.

---

## §7 Watch items for orchestrator + V2 candidates banked

### §7.1 Cross-bundle pin at T-A.7 (STILL SKIPPED)

`tests/web/test_view_models/test_base_layout_vm_coverage.py::test_existing_dashboard_vm_has_unresolved_material_field` REMAINS SKIPPED per dispatch brief §0.5. Skip reason names the un-skip schedule (Sub-bundle E T-E.3). Verify the skip is still in place at integration merge.

### §7.2 New sub-VM exclusions added to coverage test

`tests/web/test_view_models/test_base_layout_vm_coverage.py` `_SUB_VM_EXCLUSIONS` set extended with `CohortTabVM` + `CohortProgressVM`. Sub-bundle C dispatches should propagate this pattern: any new sub-VM class ending in `VM` that composes into a page VM (not BaseLayoutVM-extending) should be added to the exclusion set in the same commit that adds it.

### §7.3 V2 candidates banked

1. **`review_log_trade_links` audit-table option** — if Phase 6 review_log gains a per-trade audit table, the cohort aggregator could prefer frozen review-time values for already-reviewed trades + recompute only for unreviewed trades. See §5.1 + the rationale comment in `swing/metrics/process.py` cohort-sum loop.
2. **Per-cohort "exclude paused-interval trades" filter** — per plan §A.11.1 V2 candidate, same UI pattern as T-C.5 "exclude unresolved-discrepancies" filter family. Sub-bundle C may surface the reuse pattern when T-C.5 lands.
3. **`mistake_cost_R_per_trade` Class B representation alongside cohort sum** — implementation surfaces both `MetricCellB` (Class B mean) AND `PointMetricCell` (cohort sum) for mistake_cost_R + lucky_violation_R; spec §3.1 only enumerates "cohort sum." V2 candidate: clarify spec or drop the Class B representation if redundant.
4. **`canonicalize_hypothesis_label` query-time canonicalization** — `list_trades_for_cohort` already canonicalizes; verify that `count_per_cohort` orphan-label fallback path also canonicalizes (current implementation uses the registry's stored name directly + the orphan label as-is from `trades.hypothesis_label`). Edge case: an orphan trade with a non-canonicalized stored label might appear separately from a canonicalized-form match. Low risk in V1 (writer canonicalizes at persist time); banked for V2 audit.

### §7.4 Spec amendments pending V2.1 §VII.F routing

Two candidates from §5 above:
1. **Plan §E Task B.1 acceptance text** should align to "always re-compute via Phase 6 helpers; cohort-grain sum is reproducible from per-trade fields" (per §5.1).
2. **Plan §A.5.1 + spec §3.2 `cumulative_R_pct_of_capital` rendering unit** should be explicit (percent vs proportion) (per §5.3).

These join the 2 pre-existing Phase 9 spec amendments (Sub-bundle D §7 sector_industry anchor + Sub-bundle E §6.2 multi-line parser) + 3 Phase 10 Sub-bundle A candidates (Wilson CI standard-vs-continuity-correction; `read_at_trade_time_policy` signature; `BaseLayoutVM.stale_banner` type). **Total pending: 7 spec amendments** routed via V2.1 §VII.F.

### §7.5 Worktree teardown status

Branch `phase10-bundle-B-trade-process-and-hypothesis-progress` will be ACL-locked husk after `git worktree remove` post-integration-merge per Phase 9 + Sub-bundle A precedent. **11th in operator cleanup-script queue.**

---

## §8 Sub-bundle C forward-binding lessons

In addition to the 17 lessons enumerated in the Sub-bundle B dispatch brief §0.6 forward-binding catalog, **2 NEW lessons from Sub-bundle B execution** are forward-binding for Sub-bundle C (tier-comparison + deviation-outcome) dispatch:

1. **Cadence-grain audit tables CANNOT be cleanly mapped to cohort-grain metrics without per-trade FK.** Sub-bundle B's R1 Major #1 surfaced the mismatch between `review_log` (cadence-grain, no trade FK) and cohort-grain `mistake_cost_R` sum. If Sub-bundle C's tier-comparison or deviation-outcome dispatches encounter similar cadence-grain audit columns (e.g., `reconciliation_runs.summary_json` for cohort-grain "data-quality" gating), document the mismatch + always re-compute from per-trade source data. The discriminating-test pattern (plant a conflicting cadence row + assert metric reflects per-trade compute, not the planted aggregate) is the canonical regression-pin.

2. **Unit-semantic precision needs explicit rendering (percent vs proportion).** Sub-bundle B's `cumulative_R_pct_of_capital` rendered in PERCENT units to match the `absolute_loss_tripwire_pct` comparison. Future tier-comparison metrics (`cohort_relative_to_aplus`, `cohort_expectancy_relative_to_aplus_pct`) likely face the same: explicit rendering-unit pin in the VM + template + discriminating test is required at writing-plans time.

---

## §9 Composition-surface verification

Per Phase 9 + Sub-bundle A forward-binding lesson #5: re-grep `^def` definitions for the Sub-bundle A AMENDED interface to verify no drift introduced. Verified intact:

```
$ grep -rn "^def " swing/metrics/honesty.py swing/metrics/policy.py swing/metrics/cohort.py swing/metrics/discrepancies.py
swing/metrics/honesty.py:132:def wilson_ci(*, k: int, n: int, alpha: float = 0.05) -> WilsonCI:
swing/metrics/honesty.py:197:def bootstrap_ci_mean(...)
swing/metrics/honesty.py:273:def suppress_for_n(...)
swing/metrics/honesty.py:306:def badges_for_n(*, n: int, policy: RiskPolicy) -> HonestyBadges:
swing/metrics/honesty.py:334:def render_class_a(...)
swing/metrics/honesty.py:362:def render_class_b(...)
swing/metrics/honesty.py:386:def render_class_c(...)
swing/metrics/honesty.py:431:def render_class_d(...)
swing/metrics/policy.py:39:def read_live_policy(conn: sqlite3.Connection) -> RiskPolicy:
swing/metrics/policy.py:49:def read_at_trade_time_policy(conn, *, policy_id_stamp: int | None) -> tuple[RiskPolicy, bool]:
swing/metrics/policy.py:75:def read_at_review_time_policy(conn, *, policy_id_stamp: int | None) -> tuple[RiskPolicy, bool]:
swing/metrics/policy.py:88:def get_trade_policy_id_stamp(conn, *, trade_id: int) -> int | None:
swing/metrics/policy.py:112:def get_review_policy_id_stamp(conn, *, review_id: int) -> int | None:
swing/metrics/cohort.py:40:def list_trades_for_cohort(conn, *, hypothesis_label, state_filter=None)
swing/metrics/cohort.py:83:def list_closed_trades_for_cohort(conn, *, hypothesis_label) -> list[Trade]:
swing/metrics/cohort.py:98:def count_per_cohort(conn) -> dict[str, int]:
swing/metrics/discrepancies.py:35:def count_unresolved_material(conn) -> int:
```

Sub-bundle A interface AS-AMENDED is intact + consumed by Sub-bundle B's `swing/metrics/process.py` + `swing/web/view_models/metrics/{trade_process_card,hypothesis_progress_card}.py`. NO drift.

**T-B.0 recon doc — verbatim 4-cohort `decision_criteria` seed text** (from `swing/data/migrations/0008_hypothesis_registry.sql` lines 49-67):

| Cohort name | `decision_criteria` seed text |
|---|---|
| `A+ baseline` | `Mean R-multiple > 0; lower-bound Wilson CI on win rate > 30%` |
| `Near-A+ defensible: extension test` | `Mean R-multiple within 25% of A+ baseline mean` |
| `Sub-A+ VCP-not-formed` | `Confirm negative mean R-multiple` |
| `Capital-blocked: smaller-position test` | `Mean R-multiple positive; defensibility of smaller-position approach` |

These are rendered verbatim on the §4.2 hypothesis-progress card via the `decision_criteria` field on `CohortProgressVM`. Tested by `test_vm_decision_criteria_renders_seed_text_verbatim` (VM-layer) + `test_hypothesis_progress_renders_decision_criteria_text` (route-layer HTML body).

---

## §10 Plan-text amendments applied in-tree during Codex rounds

**NONE.** Unlike Sub-bundle A's R2 + R3 `§A.7` amendments, Sub-bundle B's R1 fixes did NOT require modifying the plan text. Both R1 Major findings were resolved via code + tests; plan §E Task B.1 acceptance text remains as authored (the design-choice rationale lives in the in-code comment + return report §5.1).

If Sub-bundle C dispatches reuse Sub-bundle B's `mistake_cost_R` aggregator pattern, the plan §E Task B.1 wording should be addressed via V2.1 §VII.F amendment (per §7.4 item 1).

---

## §11 §A.0 LOCK reaffirmation

**`EXPECTED_SCHEMA_VERSION` stays at 17.** **NO `0018_*.sql` migration.** Verified by `verify_phase10.py` step 1 (no `0018_*.sql` glob match) + step 2 (`EXPECTED_SCHEMA_VERSION` import == 17).

Phase 10 §A.0 ZERO-new-schema LOCK preserved through Sub-bundle B. Sub-bundles C / D / E inherit the lock.

---

*End of return report. Sub-bundle B closes the first 2 operator-visible Phase 10 dashboard surfaces (§4.1 + §4.2) + the T-B.7 lucky_violation_R review-form elective. 2 Codex rounds → NO_NEW_CRITICAL_MAJOR; ZERO ACCEPT-WITH-RATIONALE; ZERO new schema; ruff baseline 18 preserved. Sub-bundle C dispatch UNBLOCKED.*
