# Phase 10 Sub-bundle A — executing-plans return report

**Branch:** `phase10-bundle-A-shared-honesty-utility`
**Final HEAD:** `75dd63f` (`fix(phase10-bundle-A): Codex R3 — badges_for_n added to §A.7 binding interface + render_class_a docstring`)
**Baseline SHA:** `71eac26` (main HEAD at dispatch brief commit)
**Dispatch brief:** `docs/phase10-bundle-A-executing-plans-dispatch-brief.md`
**Plan:** `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`

---

## §1 Commit breakdown

**14 commits on top of baseline** (`71eac26..HEAD`):

| # | Type | Commit | Description |
|---|---|---|---|
| 1 | task-impl | `9a42237` | T-A.0 module skeleton |
| 2 | task-impl | `0e58a28` | T-A.1 honesty utility — Wilson CI + bootstrap CI + suppression dispatcher |
| 3 | task-impl | `cf38738` | T-A.2 risk_policy LIVE vs AT-TRADE-TIME resolver split |
| 4 | task-impl | `01bfe64` | T-A.3 live_capital_denominator_dollars resolver — PROVISIONAL/LIVE contract |
| 5 | task-impl | `122055f` | T-A.4 per-hypothesis-cohort filter + aggregation helper |
| 6 | task-impl | `b2839d3` | T-A.5 rolling-N window helper |
| 7 | task-impl | `d5c0761` | T-A.6 BaseLayoutVM mixin + shared badge dataclasses |
| 8 | task-impl | `b49046f` | T-A.7 base-layout VM coverage regression |
| 9 | task-impl | `54bdead` | T-A.7.1 discrepancies helper — count_unresolved_material |
| 10 | task-impl | `fc9317f` | T-A.8 metrics index page — GET /metrics navigator |
| 11 | task-impl | `ede9589` | T-A.9 Sub-bundle A integration sweep + verify_phase10.py |
| 12 | Codex-fix | `b1c0547` | R1 — render_class_d drawability + badges_for_n public + point NaN guard |
| 13 | Codex-fix | `e32f71c` | R2 — plan §A.7/§D amendment + ConfidenceBadgeVM cadence flag + window_n validation |
| 14 | Codex-fix | `75dd63f` | R3 — badges_for_n added to §A.7 binding interface + render_class_a docstring |
| 15 | return-report | (this commit) | Sub-bundle A return report |

Breakdown: **11 task-impl + 3 Codex-fix + 1 return-report = 15 total**.

---

## §2 Codex round chain

**4 Codex rounds → NO_NEW_CRITICAL_MAJOR convergent tapering.** ZERO Critical findings the entire chain.

| Round | Critical | Major | Minor | Verdict |
|---|---|---|---|---|
| R1 | 0 | 1 | 2 | ISSUES_FOUND |
| R2 | 0 | 1 | 2 | ISSUES_FOUND |
| R3 | 0 | 1 | 1 | ISSUES_FOUND |
| R4 | 0 | 0 | 0 | **NO_NEW_CRITICAL_MAJOR** |

**Total Codex findings across the chain:** 0 Critical + 3 Major + 5 Minor; ALL RESOLVED in-tree. **ZERO ACCEPT-WITH-RATIONALE** — every finding addressed with code or doc content fixes.

### Codex finding catalog (all resolved)

**R1 Major #1** — `render_class_d` suppressed rolling line for 5≤effective_n<N band, contradicting spec §5.4 which requires the line drawable from effective_n≥5 with a "rolling window not yet at N" badge. **Fix:** added `HonestyBadges.window_not_full_warning: bool = False` field; `render_class_d` always emits `drawability_text="rolling line drawable"` once past the effective_n<5 suppression guard; partial-window state moved to the new badge field. Discriminating regression `test_render_class_d_underlying_b_at_5_line_drawable_partial_window` pins the corrected behavior.

**R1 Minor #1** — `_badges_for_n` was private; downstream Sub-bundles B-E needed the shared composition helper. **Fix:** renamed to public `badges_for_n`; private alias preserved for backward compatibility.

**R1 Minor #2** — `render_class_d` "point" branch did not validate NaN/inf samples. **Fix:** added `_check_finite` loop before summing.

**R2 Major #1** — Plan §A.7 + §D Task A.1 text was stale relative to the R1 HonestyBadges + drawability_text amendments. Sub-bundles B-E are instructed to treat §A.7 as binding; stale plan could cause downstream agents to drop the new badge. **Fix:** updated plan §A.7 HonestyBadges block + drawability_text docstring + §D Task A.1 partial-window test description to match the shipped interface.

**R2 Minor #1** — `ConfidenceBadgeVM` did not carry the new cadence flag → metric-grid surfaces in Sub-bundles B-E would have to invent per-surface extensions. **Fix:** added `ConfidenceBadgeVM.window_not_full_warning: bool = False` field with default-False so Class A/B/C surfaces don't need to populate it.

**R2 Minor #2** — `render_class_d` accepted non-positive `window_n` without validation. **Fix:** added explicit `if window_n <= 0: raise ValueError(...)` guard mirroring `rolling_window_samples`'s `window_size` check.

**R3 Major #1** — `badges_for_n` (introduced public per R1 Minor #1) was not added to the §A.7 binding interface signature list, and §A.7 "Decoupling discipline" paragraph still said `suppress_for_n` decides badge visibility. **Fix:** added `badges_for_n` to the §A.7 signature list + rewrote the decoupling paragraph to correctly assign responsibilities: `suppress_for_n` = suppression only; `badges_for_n` = badge visibility; `render_class_d` composes badges including `window_not_full_warning`.

**R3 Minor #1** — `render_class_a` docstring still referenced private `_badges_for_n`. **Fix:** updated docstring to reference the public `badges_for_n`.

---

## §3 Test count + ruff baseline delta

| Metric | Before | After | Delta |
|---|---|---|---|
| Fast tests (passed) | 2767 | 2895 | **+128** |
| Fast tests (skipped) | 5 | 6 | +1 (cross-bundle pin per §A.18) |
| Pre-existing failures (unchanged) | 3 | 3 | 0 |
| Ruff (E501) | 18 | 18 | **0 (preserved)** |
| Schema version | 17 | 17 | **0 (per §A.0 + §I.1 LOCK)** |

**Test count overshoot:** projection was +35..+55 per dispatch brief §0.6; actual +128 (matches Phase 9 arc precedent of substantial overshoots — Phase 9 Sub-bundle A: +200..+320 projected → +147..+503 across bundles). Per-task test counts:
- T-A.1 honesty: 56 (54 initial + 2 Codex regression tests)
- T-A.2 policy: 12
- T-A.3 equity: 7
- T-A.4 cohort: 10
- T-A.5 rolling: 13
- T-A.6 shared VMs: 16 (14 initial + 2 Codex regression tests for cadence flag)
- T-A.7 coverage: 1 passing + 1 skipping (cross-bundle pin)
- T-A.7.1 discrepancies: 6
- T-A.8 metrics index: 6
- T-A.9: ~1 nav-test update (tests/web/test_base_layout_nav.py adjusted for /metrics entry)

Total new: ~128 passing + 1 skipping.

**Ruff baseline preservation:** maintained at 18 E501 (unchanged). One ruff fix was auto-applied to `swing/web/app.py` during T-A.9 (import sort I001 introduced by router registration); two E501 reformatted in `swing/metrics/honesty.py` module docstring during T-A.9.

**Pre-existing test failures unchanged:** 3 failures on `tests/integration/test_phase8_pipeline_walkthrough.py` — same set as on main HEAD `71eac26`; banked as separate-triage; NOT Sub-bundle A regressions.

---

## §4 Operator-witnessed verification gate (PENDING orchestrator-driven)

| # | Surface | Type | Status |
|---|---|---|---|
| **S1** | pytest fast-suite | Inline | ✅ PASS — 2895 passed, 6 skipped, 3 pre-existing failures unchanged |
| **S2** | Import smoke | Inline | ✅ PASS — `from swing import metrics; from swing.metrics import honesty, policy, equity_resolver, cohort, rolling, funnel, process, capital, maturity, tier, process_grade_trend, discrepancies` clean |
| **S3** | `/metrics` index | **Browser (operator-witnessed)** | ⏳ PENDING — orchestrator drives operator-witnessed gate per dispatch brief §2 (operator launches `swing web` → navigates to `http://127.0.0.1:8080/metrics` → confirms 8-tile navigator renders + base.html.j2 integration intact + 8 surface link `<a>` tags present) |
| **S4** | ruff baseline | Inline | ✅ PASS — 18 E501 unchanged |
| **S5** | verify_phase10.py | Inline | ✅ PASS — `python verify_phase10.py` exits 0 |

Per dispatch brief §1.3 budget: 4 of 5 surfaces inline-verified by implementer; only S3 (browser) requires operator session. Fits well within the ≤6-surface budget for a single operator gate session.

---

## §5 Per-task deviations from the plan (with rationale)

Three deviations from the plan as written; all preserve behavior + interface intent. Each was documented inline at the change site + folded into the V2.1 §VII.F amendment candidate list at §8.

### §5.1 Wilson CI formula choice (T-A.1)

**Plan §D Task A.1 acceptance:** "Wilson CI computed pure-Python (no scipy); matches reference values for k=2,n=4 → [0.094, 0.901] (within 1e-3); k=0,n=20 → [0.000, 0.161]; k=20,n=20 → [0.839, 1.000]."

**Implementation:** uses standard Wilson score interval (the Wikipedia primary formula, no continuity correction). For k=2,n=4 this gives [0.150, 0.850] — NOT plan's [0.094, 0.901]. Plan's k=2,n=4 reference value corresponds to **Wilson-with-continuity-correction** (which yields [0.092, 0.908]); the plan's other two reference values (k=0,n=20 + k=20,n=20) match standard Wilson exactly.

**Rationale:**
1. Standard Wilson is what "Wilson score interval" conventionally means in statistics literature + matches the primary Wikipedia formula the plan §A.7 cites ("pure-Python per Wikipedia formula").
2. The plan's two-of-three matching reference values suggests the author intended standard Wilson; the k=2,n=4 reference appears to be an inadvertent mix of formulas.
3. Standard Wilson is what statsmodels' default `proportion_confint(method='wilson')` uses — downstream comparison expectations align.

**Test impact:** `test_wilson_ci_known_values_k2_n4_standard` asserts [0.150, 0.850] (standard) with a docstring noting the plan-text divergence + rationale.

**Spec amendment candidate:** banked at §8 #1 — plan §D Task A.1 reference value [0.094, 0.901] should be corrected to standard Wilson [0.150, 0.850], OR the plan should explicitly require Wilson-with-continuity-correction. V2.1 §VII.F routing.

### §5.2 T-A.2 resolver signature shape

**Plan §A.5 wording:** "Function `read_at_trade_time_policy(conn, *, trade: Trade) -> RiskPolicy` resolves `trade.risk_policy_id_at_lock`; falls back ... `(RiskPolicy, bool)`."

**Implementation:** signature is `read_at_trade_time_policy(conn, *, policy_id_stamp: int | None) -> tuple[RiskPolicy, bool]` — takes the stamp `int | None` directly instead of a `Trade` object. Same for `read_at_review_time_policy`.

**Rationale:** Phase 9 Sub-bundle A added the `trades.risk_policy_id_at_lock` column via ALTER but **did not extend the `Trade` dataclass** (`_TRADE_SELECT_COLS` in `swing/data/repos/trades.py` doesn't include the column). The plan §A.5 spec assumed the dataclass would carry the stamp; it doesn't.

**Mitigation:** added two convenience accessors in `swing/metrics/policy.py`:
- `get_trade_policy_id_stamp(conn, *, trade_id: int) -> int | None`
- `get_review_policy_id_stamp(conn, *, review_id: int) -> int | None`

Sub-bundle B consumers call the accessor to fetch the stamp from the DB, then pass the result into the resolver. Functional equivalence preserved.

**Spec amendment candidate:** banked at §8 #2 — V2 may extend `Trade` dataclass to include `risk_policy_id_at_lock` so the plan's original signature works directly. Trade-off: every existing consumer of `Trade` dataclass needs to accept the new field. Defer.

### §5.3 T-A.6 BaseLayoutVM.stale_banner type

**Plan §A.6 wording:** "`BaseLayoutVM` `@dataclass(frozen=True)` mixin with all 5 base-layout fields (... `stale_banner: bool = False` ...)."

**Implementation:** `stale_banner: str | None = None` instead of `bool = False`.

**Rationale:** `base.html.j2` renders `{% if vm.stale_banner %}{% include "partials/stale_banner.html.j2" %}{% endif %}` and the included partial does `{{ vm.stale_banner }}` (substitutes the actual banner text). All existing base-layout VMs (DashboardVM/PipelineVM/JournalVM/WatchlistVM/ConfigVM) use `str | None`. Setting `bool = False` on the new `BaseLayoutVM` mixin would yield Jinja-rendered `True`/`False` text in the banner area when a metrics surface is stale-bannered.

**Test impact:** field name preserved (regression test `test_all_metrics_vms_have_base_layout_fields` checks names, not types per plan §A.7 wording). Discriminating test `test_base_layout_vm_default_values` asserts `vm.stale_banner is None` (default).

**Spec amendment candidate:** banked at §8 #3 — plan §A.6 should be amended to `stale_banner: str | None = None` to match existing pattern. V2.1 §VII.F routing.

---

## §6 Codex Major findings ACCEPTED with rationale

**None.** All 3 Major findings across the 4-round chain were resolved with code or doc content fixes. **ZERO ACCEPT-WITH-RATIONALE positions banked** — matches Phase 9 Sub-bundle D's clean record.

---

## §7 Watch items for orchestrator (post-Sub-bundle-A-ship)

1. **Operator-witnessed gate S3 PENDING** — only browser-side surface for Sub-bundle A. Orchestrator should drive operator's `swing web` → `/metrics` gate session (~5 min). Tile links to `/metrics/{trade-process,hypothesis-progress,...}` will 404 at this stage; that is by-design (Sub-bundles B/C/D/E land the destinations).

2. **Cross-bundle pin at T-A.7 (still SKIPPED)** — `test_existing_dashboard_vm_has_unresolved_material_field` is skipped with reason naming Sub-bundle E T-E.3 as the un-skip point. Verify the skip is still in place at integration merge; un-skip lands at T-E.3 retrofit of the 6 existing base-layout VMs.

3. **V2 candidate: orphan-emit discrepancy counts** — `count_unresolved_material` returns ONLY trade-attributed discrepancies (underlying repo helpers JOIN on trades). Orphan-emit discrepancies (sector_tamper / equity_delta / cash_movement_mismatch with NULL trade_id) are EXCLUDED from the count. Phase 9 Sub-bundle D's sector_tamper audit emits + Sub-bundle C's equity_delta could produce orphans the badge would silently miss. Discriminating regression test in `tests/metrics/test_discrepancies.py::test_count_unresolved_material_excludes_orphan_emit_no_trade` pins V1 behavior. V2 could widen via separate sub-query.

4. **V2 candidate: render_class_d "point" branch returns sum, not mean** — implementation hardcodes sum semantics per §A.21 + §J.1.1 for `mistake_cost_R_rolling_N_total`. Other future "point" callers (if any) needing mean semantics would need a new helper or a parameter to switch aggregation. Banked at the §A.21 V2.1 §VII.F amendment candidate.

5. **Plan §A.7 binding interface amended in-tree** — Sub-bundle A's R1 + R2 + R3 fixes amended the plan §A.7 HonestyBadges field set + drawability_text docstring + Decoupling discipline paragraph + signature list (`badges_for_n` added) + §D Task A.1 partial-window test description. Sub-bundles B-E inherit the AMENDED plan. The amendments are local to plan §A.7 + §D Task A.1; no spec amendment needed (spec §5.4 is the authority + already specifies the corrected behavior — only the plan text was stale).

6. **`badges_for_n` is public per R1 Minor #1 + R3 Major #1** — Sub-bundles B-E should consume the shared helper for badge composition; private alias `_badges_for_n` preserved for backward compatibility but new code should use `badges_for_n`.

---

## §8 V2.1 §VII.F amendment candidates banked

1. **Plan §D Task A.1 Wilson CI reference value** — [0.094, 0.901] for k=2,n=4 is Wilson-with-continuity-correction; standard Wilson (the implemented form) yields [0.150, 0.850]. Plan should pick one formula + correct the reference value accordingly. (See §5.1.)

2. **Plan §A.5 resolver signature** — `read_at_trade_time_policy` spec'd to take `trade: Trade`; Trade dataclass lacks the `risk_policy_id_at_lock` field. Either extend the dataclass (V2-disruptive) or amend §A.5 to take `policy_id_stamp: int | None` directly (matches implementation). (See §5.2.)

3. **Plan §A.6 stale_banner type** — `bool = False` spec; `str | None = None` actual to match existing base-layout VM pattern + render `{{ vm.stale_banner }}` text correctly. (See §5.3.)

4. **Plan §A.7 honesty interface amendments** — already applied in-tree via Codex R1+R2+R3 fix commits; spec §5 unchanged. Future plan revisions should fold these into the canonical plan text or supersede via amendment doc.

---

## §9 Worktree teardown status

**Worktree expected to be ACL-locked husk** at `c:/Users/rwsmy/swing-trading/.worktrees/phase10-bundle-A-shared-honesty-utility/` post-integration-merge per Phase 6/7/8/9 pattern. Will be the 10th husk pending operator cleanup-script (per dispatch brief §7 #5 enumeration of 9 pre-existing husks).

Operator can detach + remove the worktree after orchestrator drives the integration merge via:
```powershell
git worktree remove .worktrees/phase10-bundle-A-shared-honesty-utility --force
git branch -D phase10-bundle-A-shared-honesty-utility   # only after merge confirmation
```

---

## §10 Sub-bundle B forward-binding lessons

Two NEW lessons surfaced during Sub-bundle A executing-plans Codex chain, both worth promoting to dispatch brief §0.5 forward-binding for Sub-bundle B:

### §10.1 Plan §A.7 binding-interface amendments need to flow into the plan text immediately

Codex R2 Major #1 + R3 Major #1 caught the SAME failure mode twice: code-level interface changes (adding `HonestyBadges.window_not_full_warning` in R1; making `badges_for_n` public in R1) were NOT reflected in the binding plan §A.7 text, even though Sub-bundles B-E read §A.7 as binding. The Codex chain auto-detected via cross-referencing plan vs code; in-tree fix amends both the code AND the plan §A.7 simultaneously.

**Pre-emption for Sub-bundle B+ dispatch:** when an implementer changes any §A.7-listed interface element (HonestyBadges fields, function signatures, the Decoupling discipline assignment), update plan §A.7 in the SAME commit. Add a writing-plans §5 watch item: "if implementer adds new public function / dataclass field / signature param in `swing/metrics/honesty.py`, plan §A.7 binding interface MUST update in-tree to match."

### §10.2 Wilson CI formula choice matters; pin the spec at writing-plans time

The Wilson CI standard-vs-continuity-correction divergence in §5.1 above is a textbook ambiguity. The plan §A.7 cited "Wikipedia formula" but Wikipedia documents BOTH variants; the plan's reference values mixed the two. Without a strict spec pin at writing-plans time, the implementer makes a choice that may diverge from the operator's mental model.

**Pre-emption for Sub-bundle B+ dispatch:** any statistical helper that has multiple textbook-correct implementations (Wilson CI, bootstrap CI tail-handling, bias-correction etc.) needs an EXPLICIT formula pin in the plan with a citation. Add to writing-plans §5 watch items: "for statistical helpers, plan §A.7 names the SPECIFIC variant + cites Wikipedia/scipy/statsmodels function name to disambiguate."

---

## §11 Composition-surface verification via `^def` grep (per Phase 9 forward-binding lesson §0.5 #5)

Verified via `grep -rn "^def " swing/metrics/`:

- `swing/metrics/honesty.py`: `wilson_ci`, `_z_for_alpha`, `bootstrap_ci_mean`, `_class_threshold`, `suppress_for_n`, `badges_for_n`, `render_class_a`, `render_class_b`, `render_class_c`, `render_class_d`
- `swing/metrics/policy.py`: `read_live_policy`, `read_at_trade_time_policy`, `read_at_review_time_policy`, `get_trade_policy_id_stamp`, `get_review_policy_id_stamp`
- `swing/metrics/equity_resolver.py`: `resolve_live_capital_denominator_dollars`
- `swing/metrics/cohort.py`: `list_trades_for_cohort`, `list_closed_trades_for_cohort`, `count_per_cohort`
- `swing/metrics/rolling.py`: `rolling_window_samples`, `rolling_mean_series`
- `swing/metrics/discrepancies.py`: `count_unresolved_material`

Verified via `grep -rn "^def " swing/web/view_models/metrics/`:
- `swing/web/view_models/metrics/shared.py`: (dataclasses; no module-level functions)
- `swing/web/view_models/metrics/index.py`: `build_metrics_index_vm`

Verified via `grep -rn "^def " swing/web/routes/metrics.py`:
- `swing/web/routes/metrics.py`: `metrics_index`

All composition surfaces present + match plan §B file map. No orphan helpers; no missing helpers.

---

## §12 Integration-merge handoff

Marker file removed (`Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`). Orchestrator owns:
1. Operator-witnessed S3 gate (browser `/metrics` walkthrough).
2. Integration merge to `main` via `git merge --no-ff phase10-bundle-A-shared-honesty-utility`.
3. Post-merge worktree teardown OR banking as 10th husk pending operator cleanup-script.
4. Post-merge housekeeping: CLAUDE.md status-line update; phase3e-todo cross-reference if applicable.
5. Sub-bundle B dispatch brief drafting (which inherits §10 forward-binding lessons + the AMENDED plan §A.7 interface).

**Sub-bundle B dispatch UNBLOCKED upon S3 PASS + integration merge.**

---

*End of return report. Sub-bundle A landed the foundational cross-bundle dependency for Phase 10: `swing/metrics/honesty.py` (§A.7 interface verbatim with R1+R2+R3 corrections), `BaseLayoutVM` mixin, `count_unresolved_material` discrepancies helper, GET /metrics navigator. Sub-bundles B/C/D/E now consume the SHIPPED + AMENDED §A.7 interface.*
