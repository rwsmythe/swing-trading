# Phase 10 Sub-bundle E — executing-plans dispatch brief (CLOSES Phase 10)

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Phase 10 Sub-bundle E per plan §H (Tasks T-E.0..T-E.4) + electives amendment §2 (Tasks T-E.5 + T-E.6) on an isolated worktree branch via `copowers:executing-plans` (wraps `superpowers:subagent-driven-development` + adversarial Codex MCP review). **Sub-bundle E CLOSES Phase 10.** Lands the **eighth (and final) operator-visible Phase 10 dashboard surface** (§4.8 Process-grade-trend with inline SVG chart) + **the cross-bundle reconciliation discrepancy banner integration** (retrofits the 6 EXISTING base-layout VMs + un-skips the cross-bundle T-A.7 pin) + **2 elective surfaces** (T-E.5 web-form manual snapshot capture + T-E.6 per-trade discrepancy indicator on trade detail page) + **Phase 11 hand-off documentation**.

**Expected duration:** ~10-14 hr executing-plans wall-clock + ~2-4 hr Codex convergence. Plan §H has 4 surface-tasks + 1 closer-task (T-E.0..T-E.4) + electives amendment §2 adds T-E.5 + T-E.6 = **7 tasks total**. Estimated 2-4 Codex rounds (Sub-bundle A: 4 rounds; B: 2; C: 2; D: 3). Sub-bundle E has moderate Codex-value-add density: process-grade-trend Class D rendering per §A.21 + banner retrofit cross-bundle pin un-skip + new web-form (T-E.5 introduces HTMX failure-surface budget hit; only new write path in Phase 10 V1).

---

## §0 Inputs

### §0.1 Plan
- **PLAN_PATH:** `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`
- **Plan status:** Codex R1-R6 → NO_NEW_CRITICAL_MAJOR; shipped 2026-05-13 at `a34c00d`; AMENDED in-tree during Sub-bundle A Codex R2+R3 (commits `e32f71c` + `75dd63f`). Sub-bundle E reads the AMENDED §A.7 + §D Task A.1 text. 2008+ lines.
- **Sub-bundle E scope:** plan §H (lines 1552-1681); 4 tasks T-E.0..T-E.4 (plan-native) + 2 elective tasks T-E.5 + T-E.6 (per electives amendment §2). **7 tasks total**.
- **Cross-bundle invariants:** plan §I (lines 1665-1744); 15 invariants. Sub-bundle E exercises **§I.5 BaseLayoutVM mixin LOCK — un-skip-at-T-E.3 closes the cross-bundle pin** (the binding completion of A's foundational dependency); §I.6 (HTMX failure-surface budget — T-E.5 introduces ONE new HTMX form surface; only new failure-surface budget hit in Phase 10 V1); §I.8 (decoupling discipline — process-grade-trend Class D rendering uses `render_class_d` with `underlying_class` parameter per §A.21); §I.9 (NO `INSERT OR REPLACE` — T-E.5 uses Phase 9 Sub-bundle C `record_snapshot_with_audit` service which already follows SELECT-then-UPDATE-or-INSERT); §I.10 (test fixture USERPROFILE+HOME monkeypatch — T-E.5 may exercise paths near user-config but does NOT write user-config; verify); §I.11 (service-layer transaction discipline — T-E.5 form handler MUST NOT hold open transaction when calling `record_snapshot_with_audit` which owns BEGIN IMMEDIATE / COMMIT / ROLLBACK); §I.12 (form-render hidden-anchor round-trip — T-E.5 has NO hidden anchors per electives amendment §2 watch items; banner-form is HX-Redirect target); §I.13 (session-anchor read/write predicate alignment — T-E.5 server-stamps `snapshot_date = last_completed_session(now)` at handler entry per Phase 8 server-stamping discipline); §I.14 (empty-cohort + zero-trade rendering — process-grade-trend renders cleanly at n=0); §I.15 (operator-witnessed gate per surface — 5-6 surfaces + 1 banner inline-bundled per electives amendment).

### §0.2 Electives amendment
- **AMENDMENT_PATH:** `docs/phase10-electives-amendment.md`
- **Amendment status:** SHIPPED 2026-05-13 at `9525f17`; NORMATIVE supplement to plan §A.4 + §E + §F + §H.
- **Sub-bundle E impact:** TWO elective tasks — T-E.5 web-form manual snapshot capture (§8.2 election) + T-E.6 per-trade discrepancy indicator on trade detail page (§11.2(b) election). See amendment §2 Task E.5 + Task E.6 for full acceptance criteria. Adds 2 tasks + 2 gate surfaces to Sub-bundle E (going from 3+1 banner to 5+1 banner = 6 surfaces — AT the ≤6 budget per dispatch brief §1.3).

### §0.3 Spec
- **SPEC_PATH:** `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md`
- **Spec status:** Codex R1-R5 substantive + R6 confirmation; SHIPPED 2026-05-06 at `fe6cb45`; 641 lines; RESEARCH-POSTURE.
- **Sub-bundle E spec coverage:** §3.8 process-grade-trend metrics (Task T-E.1); §4.8 process-grade-trend view surface (Task T-E.2); §5.4 Class D rendering — partial-window + confidence-floor decoupling (BINDING for T-E.1); §8.5 N=10 hardcoded window-size LOCK (per §A.4); §A.10 inline-SVG default-disposition LOCK (NO matplotlib in V1; avoids the mathtext gotcha entirely); §A.21 per-metric Class assignment matrix — `mistake_cost_R_rolling_N_total` is "point" class only (spec-conformance deviation banked at writing-plans; carries forward as V2.1 §VII.F amendment candidate); §6.1 Phase 8 capture-need rendering (already shipped per Sub-bundle D inheritance; not re-exercised in E).

### §0.4 Project state at dispatch time
- **HEAD on `main`:** `70e109b` (post-Sub-bundle-D-ship housekeeping; merge at `a71cc24`).
- **Test count (main HEAD):** **~3150 fast passing + 2 skipped on main HEAD `70e109b`** (3147 worktree-side + 3 pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py` failures unchanged; 3 pre-existing failures NOT regressions; cross-bundle T-A.7 pin still SKIPPED + Task 7.3 operator-only). **Worktree-side baseline:** ~3147 fast passing + 6 skipped.
- **Test runtime concern (operator-acknowledged 2026-05-13):** fast suite at ~6:00 wall-clock at 3147 tests; **deferred** xdist + fixture-scope refactor per phase3e-todo 2026-05-13 entry. Sub-bundle E inherits the current test-runner setup; expect S1 inline gate to take ~6-7 min at projected ~3170-3200 tests post-E.
- **Ruff baseline:** **18 (E501 only).** Unchanged across entire Phase 9 + 10 arcs.
- **Schema version:** **v17.** LOCKED since Phase 9 Sub-bundle A; Sub-bundle E introduces ZERO schema changes per §A.0 + §I.1 LOCK. `EXPECTED_SCHEMA_VERSION` stays at 17.
- **Active risk_policy:** `policy_id=5` (unchanged through Sub-bundles A+B+C+D).
- **Production trades:** 8 total; 5 open (DHC/YOU/VSAT/CVGI/LAR) + 3 closed (VIR/CC/SGML). 3 closed trades may exercise process-grade-trend at limited n; expect aggressive suppression on most metrics.
- **Production account_equity_snapshots:** 2 manual snapshots (#1 $2000 at 2026-05-11; #2 $1800 at 2026-04-01 back-recorded). T-E.5 web-form will create a third snapshot when operator-witnessed at gate time (S6).
- **Production reconciliation_discrepancies:** 30 discrepancies all resolved as `acknowledged_immaterial`. T-E.3 banner currently shows count=0; S3/S4 gate requires planting an unresolved discrepancy temporarily.
- **6 worktree husks pending cleanup-script** (4 Phase 9 still-registered + 1 Sub-bundle C orphan + 1 Sub-bundle D orphan). Cleanup-script `-DeregisterFirst` extension deferred post-Phase-10 per phase3e-todo.

### §0.5 Sub-bundle A interface inheritance — AMENDED plan §A.7 + Sub-bundle B + C + D implementation conventions

**CRITICAL:** Plan §A.7 + §D Task A.1 were AMENDED in-tree during Sub-bundle A Codex R2 + R3. Sub-bundle E reads the AMENDED text:

**HonestyBadges + public helpers** (per Sub-bundle C dispatch brief §0.5 — unchanged through D):
- `swing/metrics/honesty.py:wilson_ci`, `bootstrap_ci_mean`, `suppress_for_n`, `badges_for_n` (PUBLIC), `render_class_a/b/c/d`.
- **`render_class_d(*, samples_in_window, window_n, policy, metric_name, underlying_class, events_in_window=None, n_wins=None, n_losses=None) -> tuple[..., HonestyBadges, str] | SuppressedMetric`** — 3-tuple with `drawability_text` per spec §5.4 cadence-vs-confidence decoupling. **CRITICAL for T-E.1: `underlying_class` parameter per §A.21 matrix; pass `events_in_window=count(disqualifying=1)` for `disqualifying_violation_rate_rolling_N` per Codex R2 Minor #1.**

**Risk_policy resolver:** Sub-bundle E surfaces are governance-class (process-grade-trend is per-reviewed-trade aggregation). Use `read_live_policy(conn)` for the rolling-window `policy.global_confidence_floor_n` reference; AT-TRADE-TIME resolution NOT needed.

**BaseLayoutVM mixin (per AMENDED §A.6 + §A.18):**
- Fields: `session_date: str`, `stale_banner: str | None = None`, `price_source_degraded: bool = False`, `price_source_degraded_until: str | None = None`, `ohlcv_source_degraded: bool = False`, `unresolved_material_discrepancies_count: int = 0`.
- **Sub-bundle E's `ProcessGradeTrendVM` MUST extend `BaseLayoutVM`** + populate `unresolved_material_discrepancies_count=count_unresolved_material(conn)` per §A.18.
- **T-E.3 CRITICAL:** retrofits the 6 EXISTING base-layout VMs (`DashboardVM`, `PipelineVM`, `JournalVM`, `WatchlistVM`, `ConfigVM`, `PageErrorVM`) with the same field + populates via the helper. **Un-skips `test_existing_dashboard_vm_has_unresolved_material_field`** (the cross-bundle T-A.7 pin since Sub-bundle A close).

**Discrepancies helper (per §A.7.1):**
- `swing/metrics/discrepancies.py:count_unresolved_material(conn) -> int` — invoked in every VM constructor.
- **NEW T-E.6 helper:** `swing/metrics/discrepancies.py:list_unresolved_material_for_trade(conn, trade_id) -> list[Discrepancy]` per electives amendment §2 Task E.6 (reuses Phase 9 Sub-bundle B repo helpers; does NOT duplicate query).

**Phase 9 Sub-bundle C `account_equity_snapshots` service (per T-E.5 electives §2):**
- `swing/trades/account_equity_snapshots.py:record_snapshot_with_audit(conn, *, equity_dollars, snapshot_date, source='manual', note=None)` — Phase 9 SHIPPED service that owns BEGIN IMMEDIATE / COMMIT / ROLLBACK per Phase 9 transactional discipline + reject-caller-held-tx contract. **T-E.5 web-form handler MUST NOT hold open transaction when calling this.**

**Phase 9 Sub-bundle B `reconciliation_discrepancies` helpers (per T-E.6 electives §2):**
- `swing/data/repos/reconciliation.py:list_unresolved_material_for_active_trades` + closed-trade companion — Phase 9 SHIPPED. T-E.6 helper consumes these.

**Cross-bundle pin (currently SKIPPED — un-skipped by T-E.3):**
- `tests/web/test_view_models/test_base_layout_vm_coverage.py::test_existing_dashboard_vm_has_unresolved_material_field` is `@pytest.mark.skip(reason="Sub-bundle E T-E.3 adds field to existing base-layout VMs")`. **T-E.3 SAME COMMIT removes the `@pytest.mark.skip` decorator** + verifies the test passes against the 6 retrofitted VMs.

**Sub-bundle B + C + D implementation conventions (BINDING for E):**

1. **Lesson #18 cadence-grain rejection** — Sub-bundle E reads `review_log` for process-grade aggregation (Phase 6 shipped table). `review_log` is cadence-grain (one row per review window) but spec §3.8 explicitly defines process_grade_trend at the trade-grain via Phase 6 helpers (per-reviewed-trade aggregation). T-E.1 implementation should iterate per-reviewed-closed-trade ordered by review date and use Phase 6 `compute_*_grade(conn, trade_id)` helpers, NOT `review_log` aggregated columns. **If implementer is tempted to read `review_log.total_*` for cohort-grain sums, REJECT.**

2. **Lesson #19 unit-semantic precision** — process-grade rolling lines render grades as numeric encoding (A=4, B=3, C=2, D=1, F=0) per plan §H T-E.1. The Y-axis of the SVG chart MUST be labeled with this encoding visible (operator readability). Discriminating test: assert chart legend/axis text contains "A=4" or equivalent encoding hint.

3. **Lesson #20 exact-substring discrimination** — process-grade-trend renders confidence-floor warnings + partial-window badges as TEXT per spec §4.9. Discriminating tests assert EXACT rendered text substrings, NOT body-wide containment.

4. **Lesson #21 relative href** — T-E.5 GET `/account/snapshot` form posts to `/account/snapshot` (same URL); HX-Redirect target on success = `/metrics/capital-friction` (absolute path per electives amendment §2 — correct for HX-Redirect; relative-href LOCK from C applies to filter toggles, NOT route redirects).

5. **Lesson #22 filter at compute layer** — N/A for Sub-bundle E (no filters introduced).

6. **Lesson #23 plan-prescribed verbatim text → dedicated dataclass FIELD + template rendering target** (NEW from Sub-bundle D R1 M#1) — **HIGHLY APPLICABLE for T-E.2:** process-grade-trend confidence-floor warning text + partial-window badge text + drawability_text from `render_class_d` 3-tuple MUST surface through dedicated dataclass fields + template rendering targets (NOT title= hover-only). Discriminating-test pattern: assert `data-{marker}=` substring + `title=` absence.

7. **Lesson #24 session-anchor read/write mismatch family** (NEW from Sub-bundle D R1 M#2) — T-E.5 server-stamps `snapshot_date = last_completed_session(datetime.now())` at handler entry per Phase 8 server-stamping discipline; **MUST NOT use forward-looking `action_session_for_run(now)`.** Discriminating test: tamper with caller-supplied snapshot_date in POST body + assert server-stamp wins.

8. **Lesson #25 bounded-range distinguishing** (NEW from Sub-bundle D R1 M#3) — process-grade rolling means (A=4..F=0) are mathematically bounded [0, 4]; clamping is safe. `disqualifying_violation_rate_rolling_N` is bounded [0, 1] by construction (k/n where k ≤ n). NO lessons-#25 traps in Sub-bundle E V1.

9. **Lesson #26 SQL ORDER BY tiebreaker** (NEW from Sub-bundle D R3 m#1) — process-grade-trend iterates closed-and-reviewed trades ordered by `review_date`. **Discriminating-test pattern:** SQL `ORDER BY review_date, id` (deterministic tiebreaker on ties).

### §0.6 26-lesson forward-binding catalog (Phase 9 arc + Sub-bundle A + B + C + D → E)

Cumulative lesson catalog. Lessons 1-22 from Sub-bundle D dispatch brief §0.6; lessons 23-26 NEW from Sub-bundle D return report §9.

| # | Lesson | Sub-bundle E applicability |
|---|---|---|
| 1 | `__post_init__` validator pattern on all new dataclasses | **YES** — `ProcessGradeTrendResult`, `ProcessGradeTrendVM`, `DiscrepancyDisplay` (T-E.6), `AccountSnapshotForm` (T-E.5) need NaN/inf rejection + invariant assertions |
| 2 | Service-layer transaction discipline | **YES** — T-E.5 handler MUST NOT hold open transaction when calling `record_snapshot_with_audit` |
| 3 | NO `INSERT OR REPLACE` | N/A (T-E.5 uses Phase 9 service which already follows SELECT-then-UPDATE-or-INSERT) |
| 4 | Server-stamping discipline at handler entry | **YES** — T-E.5 server-stamps `snapshot_date` + `recorded_at` per Phase 8 R2/R3/R4 |
| 5 | Composition-surface enumeration via `^def` grep | **YES** — pre-implementation recon greps Sub-bundle A + B + C + D surfaces + Phase 6 `compute_*_grade` helpers + Phase 9 `record_snapshot_with_audit` + `list_unresolved_material_*` |
| 6 | Empirical-verification of brief assertions | YES — verify Phase 6 `compute_process_grade` + `compute_entry_grade` + `compute_management_grade` + `compute_exit_grade` helper signatures exist BEFORE locking T-E.1 recon; verify base.html.j2 + 6 base-layout VM signatures BEFORE locking T-E.3 |
| 7 | Form-render hidden anchors round-trip | **YES — T-E.5** has NO hidden anchors per electives amendment §2 — explicit watch item; verify the form does not introduce any |
| 8 | POST-time recompute of "latest-of-something" TOCTOU | N/A (T-E.5 has no POST-time recompute; server-stamp at handler entry) |
| 9 | Test fixtures USERPROFILE+HOME monkeypatch | N/A (T-E.5 writes to `account_equity_snapshots` table, NOT `user-config.toml`; explicit electives amendment §2 watch item) |
| 10 | HTMX browser-only failure surfaces | **YES — HIGHLY APPLICABLE** — T-E.5 is the only new HTMX form surface in Phase 10 V1: (a) `hx-headers='{"HX-Request": "true"}'` on form element under OriginGuard strict-mode; (b) success-path `204 + HX-Redirect: /metrics/capital-friction`; (c) HX-Redirect target route registered (verified at S5 round-trip — should be live since Sub-bundle D shipped) |
| 11 | `<tr>`-leading HTMX response | N/A (T-E.5 response is 204 No Content with no body) |
| 12 | matplotlib mathtext | **N/A by §A.10 LOCK** — Sub-bundle E uses inline SVG NOT matplotlib (avoids the gotcha entirely) |
| 13 | `base.html.j2` shared fields require adding to EVERY base-layout VM | **YES — T-E.3 IS THIS LESSON** — retrofits 6 EXISTING base-layout VMs with `unresolved_material_discrepancies_count` field per §A.18 |
| 14 | Session-anchor read/write predicate alignment | **YES — T-E.5** uses backward-looking `last_completed_session(now)` at server-stamp |
| 15 | Discriminating-test arithmetic | YES — every acceptance test must distinguish correct from buggy implementations |
| 16 | Plan §A.7 amendments flow same commit as code | Likely-OFF in E (interface locked since A close; B + C + D did not need new amendments) |
| 17 | Statistical helper formula explicit pin | YES — `render_class_d` Class D rendering per §A.21 BINDING per-metric class matrix |
| 18 | Cadence-grain audit tables CANNOT be cleanly mapped to cohort-grain | **YES — DEFENSIVE for T-E.1:** process-grade-trend reads `review_log` cadence-grain BUT spec §3.8 is per-trade-grain via Phase 6 helpers; iterate per-reviewed-closed-trade ordered by `review_date` |
| 19 | Unit-semantic precision (percent vs proportion) | YES — grades A=4..F=0 encoding visible on chart axis; `disqualifying_violation_rate_rolling_N` rendered as bounded [0,1] proportion or percent |
| 20 | Body-wide unit-substring assertion non-discriminating | YES — process-grade-trend confidence-floor warning + partial-window badge tests should assert EXACT rendered text substring |
| 21 | Toggle/filter links use relative query href | N/A (no toggles in E) |
| 22 | Per-cohort filters at compute layer | N/A (no filters in E) |
| 23 (NEW) | Plan-prescribed verbatim text → dedicated FIELD + rendering target | **YES — HIGHLY APPLICABLE for T-E.2:** confidence-floor warning + partial-window badge + drawability_text from `render_class_d` 3-tuple |
| 24 (NEW) | Session-anchor read/write mismatch family — `pipeline_runs.started_ts.date()` discipline | N/A for E surfaces (process-grade-trend iterates trades, not runs); T-E.5 uses backward-looking `last_completed_session(now)` |
| 25 (NEW) | Bounded-range distinguishing (math-bounded vs two-source) | YES — disqualifying_violation_rate is math-bounded by k/n construction; clamping safe |
| 26 (NEW) | SQL ORDER BY deterministic tiebreaker (`id DESC`) | **YES — T-E.1** iterates closed-reviewed trades; ORDER BY `review_date, id` for determinism |

### §0.7 Sub-bundle E scope summary (per plan §H + electives amendment §2)

| Task | Files | Acceptance | Test count est. |
|---|---|---|---:|
| **T-E.0** recon | read-only | Sub-bundle A + B + C + D interface verified intact; `swing/data/repos/reconciliation.py:list_unresolved_material_for_active_trades` + closed-trade companion shipped; all 6 EXISTING base-layout VM constructor signatures captured verbatim (Codex R3 Minor #3 count fix: 6 = `build_dashboard`, `build_pipeline`, `build_journal`, `build_watchlist`, `build_config_vm`, `PageErrorVM`); Phase 6 `compute_process_grade` + `compute_entry_grade` + `compute_management_grade` + `compute_exit_grade` helpers + `compute_disqualifying_violation_count_per_trade` (or similar) signatures captured | 0 |
| **T-E.1** §3.8 process-grade-trend computations | `swing/metrics/process_grade_trend.py` + `tests/metrics/test_process_grade_trend.py` | `compute_process_grade_trend(conn, *, window_size: int = 10)`; iterates closed-and-reviewed trades ordered by `review_date, id` (deterministic tiebreaker per lesson #26); N=10 HARDCODED per spec §8.5 + §A.4; numeric encoding A=4..F=0; per-metric Class D rendering via `render_class_d(..., underlying_class=X)` per §A.21 matrix (B for grade rollings + mistake_cost_R_per_trade; A for disqualifying_violation_rate; "point" for mistake_cost_R_total) | ~15-25 |
| **T-E.2** ProcessGradeTrendVM + route + template (inline SVG) | `swing/web/view_models/metrics/process_grade_trend.py` + `swing/web/routes/metrics.py` (add `GET /metrics/process-grade-trend`) + `swing/web/templates/metrics/process_grade_trend.html.j2` + `tests/web/test_view_models/test_process_grade_trend_vm.py` | Extends BaseLayoutVM; carries x/y point series + rolling line series + badges per series; template renders inline SVG `<svg viewBox><polyline points/></svg>` per line + `<circle>` per-trade markers; NO matplotlib (§A.10 LOCK); confidence-floor warning + partial-window badge as TEXT inline per spec §4.9 + lesson #20 + lesson #23 | ~6-10 |
| **T-E.3** Reconciliation discrepancy banner + 6 base-layout VM retrofit + cross-bundle pin un-skip | `swing/web/templates/base.html.j2` + `swing/web/view_models/dashboard.py` + `pipeline.py` + `journal.py` + `watchlist.py` + `config.py` + `error.py` + `tests/web/test_view_models/test_base_layout_vm_coverage.py` (un-skip `test_existing_dashboard_vm_has_unresolved_material_field`) + `tests/web/test_routes/test_metrics_routes.py` (assert all 9 metrics surfaces + 6 base-layout pages render with banner field; banner-fires-when-count>0 / banner-absent-when-count=0) | ALL 6 EXISTING VMs gain `unresolved_material_discrepancies_count: int = 0` field + populate via `count_unresolved_material(conn)` in their builders; `base.html.j2` renders banner block per §A.18 snippet; cross-bundle T-A.7 pin UN-SKIPPED + passing | ~12-18 |
| **T-E.4** Phase 10 closer (integration sweep + Phase 11 hand-off + ruff sweep) | `tests/integration/test_phase10_metrics_e2e.py` + `docs/phase3e-todo.md` (add "Phase 10 closer" section per plan §H) + ruff sweep | E2E test seeds full happy-path (4 cohorts + 6+ trades + 1 snapshot + 1 unresolved discrepancy) + verifies all 9 metrics surfaces + 6 base-layout pages + banner; ruff baseline preserved; Phase 11 hand-off section enumerates capture-needs + operator-decision items pending + Schwab API Phase A coordination notes + the 2 pre-existing Phase 9 spec amendments + any new Phase 10 amendments | ~4-6 |
| **T-E.5** (elective) web-form manual snapshot capture (§8.2 election) | `swing/web/routes/account.py` (NEW route module) + `swing/web/templates/account_snapshot_form.html.j2` (NEW) + `tests/web/test_routes/test_account_snapshot_form.py` | `GET /account/snapshot` renders form with `equity_dollars` numeric input + display-only `snapshot_date` (server-computed `last_completed_session(now)` per Phase 8 server-stamping; rendered as `<span class="muted">`) + optional `note`; `POST /account/snapshot` server-stamps + calls `record_snapshot_with_audit` (Phase 9 service) + returns 204 + `HX-Redirect: /metrics/capital-friction`; HTMX header propagation per CLAUDE.md gotcha lesson family (hx-headers + HX-Redirect-vs-303 + target-route-verified) | ~6-10 |
| **T-E.6** (elective) per-trade discrepancy indicator (§11.2(b) election) | `swing/metrics/discrepancies.py` (add `list_unresolved_material_for_trade(conn, trade_id)`) + `swing/web/view_models/trades.py` (modify existing `TradeDetailVM` at L:629 or equivalent to gain `unresolved_material_discrepancies: list[DiscrepancyDisplay]` field) + `swing/web/templates/trades/detail.html.j2` (modify) + `tests/web/test_routes/test_trade_detail_discrepancy_indicator.py` | Helper returns trade-scoped unresolved material discrepancies (consumes Phase 9 Sub-bundle B repo helpers); TradeDetailVM gains the field; template renders `<details>/<summary>` collapsible discrepancy indicator section when non-empty + hides entirely when empty; orphan-discrepancy attribution per electives amendment §2 watch item (sum of per-trade ≤ global banner) | ~5-8 |

**Projected test count delta: +48..+77 fast tests** (per plan §H ~25-45 + electives amendment T-E.5 +5-10 + T-E.6 +5-8 + T-E.3 retrofit ~12-15). Post-E ~3195..~3224 worktree-side / ~3198..~3227 main HEAD. Matches Sub-bundle A + B + C + D overshoot precedent — expect upper end. **Phase 10 arc total: ~1240..~1270 cumulative fast tests** (from pre-Phase-9 baseline 1957).

### §0.8 BINDING semantics — §A.21 per-metric Class assignment matrix

This is the highest-Codex-density section in Sub-bundle E per plan §H T-E.1. **§A.21 matrix (BINDING per Codex R2 Major #1):**

```python
PROCESS_GRADE_TREND_METRIC_CLASSES = {
    "process_grade_rolling_N":             "B",      # BootstrapCI on window samples
    "entry_grade_rolling_N":               "B",
    "management_grade_rolling_N":          "B",
    "exit_grade_rolling_N":                "B",
    "mistake_cost_R_rolling_N_per_trade":  "B",
    "disqualifying_violation_rate_rolling_N": "A",   # WilsonCI; pass events_in_window=count(disqualifying=1)
    "mistake_cost_R_rolling_N_total":      "point",  # point estimate only; §A.21 spec-conformance deviation
}
```

**T-E.1 BINDING per plan §H + dispatch brief §0.5:**

```python
# Per-metric render call pattern
result = render_class_d(
    samples_in_window=window_grades,  # numeric encoding A=4..F=0
    window_n=10,                       # N=10 HARDCODED per spec §8.5
    policy=read_live_policy(conn),
    metric_name=metric_name,
    underlying_class=PROCESS_GRADE_TREND_METRIC_CLASSES[metric_name],
    events_in_window=count(disqualifying=1) if metric_name == "disqualifying_violation_rate_rolling_N" else None,
    n_wins=None,
    n_losses=None,
)
# result is tuple[(BootstrapCI | WilsonCI | float), HonestyBadges, drawability_text] | SuppressedMetric
```

**Discriminating tests (BINDING per plan §H T-E.1):**

1. `test_process_grade_rolling_N_value_slot_carries_BootstrapCI`: assert `underlying_class="B"` → `BootstrapCI` in value slot.
2. `test_disqualifying_violation_rate_rolling_N_value_slot_carries_WilsonCI`: assert `underlying_class="A"` + `events_in_window=k` → `WilsonCI` in value slot.
3. `test_mistake_cost_R_rolling_N_total_value_slot_carries_float_only`: assert `underlying_class="point"` → bare float in value slot (no CI; per §A.21 spec-conformance deviation).
4. `test_mistake_cost_R_rolling_N_per_trade_value_slot_carries_BootstrapCI`: assert spec §5.2 Class B rendering applied per §A.21.

**§A.21 spec-conformance deviation banked at writing-plans:** `mistake_cost_R_rolling_N_total` is "point" only (spec §3.8 implies sum-class with bootstrap CI; deferred to V2). Carries forward as pre-existing V2.1 §VII.F amendment candidate (NOT new from E).

### §0.9 BINDING semantics — spec §5.4 Class D 3-tuple decoupling

Plan §A.7 + spec §5.4 LOCK: `render_class_d` returns a 3-tuple decoupling window-fullness from confidence-floor (per Sub-bundle A R1 Major #1 fix).

**Tuple semantics:**
- Slot 0: value (BootstrapCI | WilsonCI | float, depending on `underlying_class`).
- Slot 1: `HonestyBadges` (carries `confidence_floor_warning` + `window_not_full_warning`).
- Slot 2: `drawability_text` (e.g., `"rolling line drawable"` once past effective_n<5 suppression guard).

**T-E.2 BINDING:** template MUST render BOTH badges separately + drawability_text as 3 distinct text elements (NOT combined; NOT one suppressing the other). Per spec §5.4 + plan §A.7 amended Decoupling discipline paragraph.

**Discriminating tests (BINDING per plan §H T-E.1 acceptance):**
1. `test_compute_process_grade_trend_5_trades_window_10_partial_window_render`: per spec §5.4 5≤effective_n<N → line drawable + window-narrowing badge + confidence-floor warning ALL TRUE.
2. `test_compute_process_grade_trend_10_trades_window_10_full_window_below_floor`: full window + confidence-floor warning persists (window_not_full_warning=False; confidence_floor_warning=True).
3. `test_compute_process_grade_trend_20_trades_drops_confidence_floor_warning`: both False; line cleanly drawable.

### §0.10 BINDING semantics — §A.10 inline-SVG LOCK (NO matplotlib)

Plan §A.10 LOCK: process-grade-trend chart renders as **inline SVG**, NOT matplotlib PNG. Rationale: avoids the CLAUDE.md matplotlib mathtext gotcha entirely + simplifies template testing (assert SVG element structure).

**T-E.2 BINDING:**

```jinja2
{# swing/web/templates/metrics/process_grade_trend.html.j2 #}
<svg viewBox="0 0 800 400" xmlns="http://www.w3.org/2000/svg">
  {# Per-trade markers — always rendered when there is at least one trade #}
  {% for point in vm.per_trade_markers %}
    <circle cx="{{ point.x }}" cy="{{ point.y }}" r="3" />
  {% endfor %}
  {# Per-metric rolling line — rendered when window has effective_n ≥ 5 per spec §5.4 #}
  {% if vm.process_grade_rolling.is_drawable %}
    <polyline points="{{ vm.process_grade_rolling.svg_points }}" />
    <title>{{ vm.process_grade_rolling.drawability_text }}</title>
  {% endif %}
  {# ... repeat for other rollings ... #}
</svg>
```

**REJECTED alternatives:**
- matplotlib PNG generation — V1 LOCK rejects; gotcha-laden.
- Client-side chart library (Chart.js, D3) — V1 LOCK § 4.9 "No client-side compute".
- HTMX OOB-swap chart updates — §A.9 LOCK pure server-render.

### §0.11 BINDING semantics — T-E.3 cross-bundle pin un-skip + 6 VM retrofit

Plan §H T-E.3 + plan §I.5 LOCK: Task E.3 SAME COMMIT:

1. Modifies all 6 EXISTING base-layout VMs:
   - `swing/web/view_models/dashboard.py:DashboardVM` + `build_dashboard`.
   - `swing/web/view_models/pipeline.py:PipelineVM` + `build_pipeline`.
   - `swing/web/view_models/journal.py:JournalVM` + `build_journal`.
   - `swing/web/view_models/watchlist.py:WatchlistVM` + `build_watchlist`.
   - `swing/web/view_models/config.py:ConfigVM` + `build_config_vm`.
   - `swing/web/view_models/error.py:PageErrorVM`.

2. Each VM gains `unresolved_material_discrepancies_count: int = 0` field. Each builder populates via `count_unresolved_material(conn)`.

3. `swing/web/templates/base.html.j2` adds the unresolved-material banner block per §A.18 rendering snippet.

4. **Un-skips** `tests/web/test_view_models/test_base_layout_vm_coverage.py::test_existing_dashboard_vm_has_unresolved_material_field` — removes the `@pytest.mark.skip(reason="Sub-bundle E T-E.3 ...")` decorator. **Test MUST pass** against the retrofitted VMs in the same commit.

5. New banner tests: `test_dashboard_vm_carries_unresolved_material_count` + 5 others (per builder).

6. New cross-page tests: `test_base_layout_renders_banner_when_count_gt_0` + `test_base_layout_omits_banner_when_count_eq_0` (TestClient + seed discrepancy + assert banner string in response body across all 6 + 9 = 15 base-layout pages).

### §0.12 BINDING semantics — T-E.5 HTMX form discipline (per CLAUDE.md gotcha family)

Per CLAUDE.md gotcha catalog + electives amendment §2 Task E.5 watch items, T-E.5 web-form MUST honor 3 binding browser-only failure surfaces:

1. **`hx-headers='{"HX-Request": "true"}'` on form element** under OriginGuard strict-mode (Phase 5 R1 M1 lesson). Without this, real browser submissions get 403.

2. **Success-path response = `204` + `HX-Redirect: /metrics/capital-friction`** (NOT `303` + swap-target; Phase 5 R1 M2 lesson). Real browsers using htmx.js swallow 303 transparently.

3. **HX-Redirect target route MUST be registered** (Phase 6 I3 lesson). `/metrics/capital-friction` was shipped in Sub-bundle D — verify at recon time + add `assert any(r.path == "/metrics/capital-friction" for r in app.routes)` to a test.

**Server-stamp discipline (lesson #4 + Phase 8 R2/R3/R4):**
- `snapshot_date = last_completed_session(datetime.now())` at handler entry.
- `recorded_at = datetime.now(timezone.utc)` at handler entry.
- Form has NO hidden inputs for these — rendered as display-only `<span class="muted">`.
- Tampered POST body (caller-supplied snapshot_date) → IGNORED; server-stamp wins. **Discriminating test BINDING.**

**Transaction discipline (lesson #2 + Phase 9 Sub-bundle A reject-caller-held-tx contract):**
- Handler MUST NOT hold open transaction when calling `record_snapshot_with_audit`.
- Service owns `BEGIN IMMEDIATE / COMMIT / ROLLBACK`.

### §0.13 BINDING semantics — T-E.6 per-trade discrepancy indicator orphan-handling

Per electives amendment §2 Task E.6 + Sub-bundle A T-A.7.1 forward-binding lesson:

**Orphan-discrepancy attribution (BINDING):**
- `count_unresolved_material(conn)` (global banner) excludes orphans (sector_tamper / equity_delta / cash_movement_mismatch with NULL trade_id) per Sub-bundle A T-A.7.1 implementation.
- `list_unresolved_material_for_trade(conn, trade_id)` (per-trade indicator) ALSO excludes orphans (no trade_id by definition).
- **Sum of per-trade indicator counts ≤ global banner count** when orphans exist. Discriminating test required.

**Template rendering (BINDING per electives amendment §2):**

```jinja2
{% if vm.unresolved_material_discrepancies %}
  <details>
    <summary>⚠ Unresolved reconciliation discrepancies ({{ vm.unresolved_material_discrepancies | length }})</summary>
    <ul>
      {% for d in vm.unresolved_material_discrepancies %}
        <li>{{ d.type }} on {{ d.field_name }}: expected {{ d.expected }}; actual {{ d.actual }} ({{ d.period_end }})</li>
      {% endfor %}
    </ul>
  </details>
{% endif %}
```

**Discriminating tests (BINDING per electives amendment §2 Task E.6 acceptance):**
1. Trade with 0 discrepancies → no indicator section in response.
2. Trade with 1 unresolved material → indicator renders with type/field/expected/actual.
3. Trade with 1 RESOLVED material → no indicator (resolution clears it).
4. Trade with 1 NON-material → no indicator (material_to_review=0 clears it).

---

## §1 Worktree + binding conventions

### §1.1 Worktree
- **Branch:** `phase10-bundle-E-process-grade-trend-and-polish`
- **Worktree directory:** `.worktrees/phase10-bundle-E-process-grade-trend-and-polish/`
- **BASELINE_SHA:** `70e109b` (current main HEAD; post-Sub-bundle-D-ship housekeeping).
- **Worktree branching point:** current HEAD of `main` at worktree-creation time (resolve via `git rev-parse main`; expected the dispatch-brief commit SHA after this brief lands).

### §1.2 Marker-file workflow
- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all task commits land + Codex chain converges + before final return-report commit: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits
- Conventional prefixes per plan §H + electives amendment §2 suggested commit shapes.
- One commit per task; Codex-fix commits as `fix(phase10-bundle-E): Codex RN <severity> #N — <description>`.
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.

### §1.4 Branch isolation + ownership
- Commits on branch only; no push to origin from worktree.
- **Implementer (you) owns:** copowers:executing-plans invocation → task-by-task TDD → Codex iteration → return-report commit.
- **Orchestrator owns:** plan-triage at dispatch time + integration merge to main + post-merge housekeeping + **drafts Phase 10 closer aggregate at integration merge time** (per plan §H T-E.4 + Phase 9 Sub-bundle E precedent).

### §1.5 Verify command
```powershell
# After all tasks land + Codex chain converges:
git log --oneline HEAD~12..HEAD
python -m pytest -m "not slow" -q
ruff check swing/ --statistics
python verify_phase10.py
```

---

## §2 Operator-witnessed verification gate (Sub-bundle E)

Per plan §H + electives amendment §2 + §I.15 BINDING:

| # | Surface | Type | Acceptance |
|---|---|---|---|
| **S1** | pytest fast-suite + ruff + verify_phase10 | Inline | `python -m pytest -m "not slow" -q` GREEN at ~3195..~3224 fast tests (worktree-side); 3 pre-existing `test_phase8_pipeline_walkthrough.py` failures unchanged; `ruff check swing/` baseline 18; `python verify_phase10.py` exits 0. **Expect ~6-7 min wall-clock** at projected test count. |
| **S2** | `/metrics/process-grade-trend` | **Browser (operator-witnessed via Chrome MCP on port 8081)** | `http://127.0.0.1:8081/metrics/process-grade-trend` → confirm: (a) page renders 200; (b) inline SVG chart renders with per-trade `<circle>` markers + per-metric `<polyline>` rolling lines (suppressed when effective_n<5 per spec §5.4); (c) Class D 3-tuple decoupling — confidence-floor warning + partial-window badge rendered as SEPARATE TEXT elements per lesson #23; (d) drawability_text rendered as separate text element OR `<title>` on the polyline (NOT replacing badges); (e) numeric grade encoding visible in chart axis legend (A=4..F=0 hint); (f) base-layout integration intact; (g) no console errors. **Production state expectation:** 3 closed-reviewed trades; most rolling metrics will be aggressively suppressed (n<5); per-trade markers should render for the 3 trades with grade=letter encoding mapped to numeric Y values. |
| **S3** | Reconciliation banner FIRES (count > 0) | **Browser (operator-witnessed via Chrome MCP) + production-write classifier** | (a) Operator (or orchestrator via plain-chat authorization) plants ONE unresolved-material discrepancy via SQL or CLI (e.g., `swing journal discrepancy unresolve <discrepancy_id>` if CLI exists, OR direct SQLite UPDATE `reconciliation_discrepancies SET resolution='unresolved'` on one row); (b) reload ANY base-layout page (e.g., `/`, `/journal`, `/pipeline`, `/metrics`) → confirm: banner FIRES with text "⚠ 1 unresolved material reconciliation discrepancy" (or equivalent §A.18 snippet text); (c) verify banner renders on ALL 6 base-layout pages + 9 metrics pages (15 total). |
| **S4** | Reconciliation banner CLEARS (count → 0) | **Browser (operator-witnessed via Chrome MCP) + production-write classifier** | (a) Resolve the planted discrepancy back to `acknowledged_immaterial` via CLI `swing journal discrepancy resolve <id> --resolution acknowledged_immaterial --reason "gate-test cleanup"`; (b) reload any base-layout page → confirm banner is ABSENT (count back to 0). |
| **S5** | `/metrics` umbrella + tile-click smoke check | **Browser (operator-witnessed via Chrome MCP)** | Navigate `http://127.0.0.1:8081/metrics` → click each of the 8 tiles → confirm each surface renders 200 + ZERO console errors. This is the Phase 10 closer verification — all 8 surfaces shipped by A through E render coherently together. |
| **S6** | T-E.5 web-form `GET /account/snapshot` + POST → HX-Redirect | **Browser (operator-witnessed via Chrome MCP on port 8081) + production-write classifier** | (a) Navigate to `http://127.0.0.1:8081/account/snapshot` → confirm form renders 200 with: `equity_dollars` numeric input + display-only `snapshot_date` (server-computed `last_completed_session(now)` = `2026-05-13` or similar at gate time) + optional `note`; (b) submit form with `equity_dollars=<operator's current cash basis>` (orchestrator drives via plain-chat authorization OR operator clicks submit); (c) verify HX-Redirect navigates to `/metrics/capital-friction`; (d) verify the new snapshot appears in `/metrics/capital-friction` LIVE badge denominator; (e) **production-write classifier may soft-block** — surface to operator for plain-chat "yes" confirmation. Production gains 3rd snapshot post-gate. |
| **S7** | T-E.6 trade detail discrepancy indicator | **Browser (operator-witnessed via Chrome MCP)** | (a) Navigate to a trade detail page (e.g., `/trades/<id>/detail` for one of DHC/YOU/VSAT/CVGI/LAR); (b) confirm: when no unresolved material discrepancies exist for the trade, NO indicator section in response; (c) plant 1 unresolved discrepancy attributed to the trade via direct SQLite + reload → confirm indicator section renders with `<details>/<summary>` collapsible + discrepancy details; (d) revert the planted discrepancy. Production-write classifier may soft-block on the planted-discrepancy step — surface to operator. |

**Gate session ≤ 6 surfaces budget (dispatch brief §1.3):** Sub-bundle E has **7 surfaces** — 1 inline + 6 browser. **AT the budget ceiling** (electives amendment §3 table says 5 surfaces + 1 banner; my count is 7 because S3 + S4 are separate banner-fires + banner-clears verifications). **Operator-decision at gate time:** consolidate S3+S4 into a single "banner round-trip" surface OR split the gate into two sessions if 7 is too long. Orchestrator drives the choice.

**Chrome MCP availability:** orchestrator drives all browser surfaces via Chrome MCP on port 8081. Production-write authorizations (S3 banner plant; S6 snapshot record; S7 banner plant on trade) require plain-chat operator authorization per durable preference + production-write classifier soft-block awareness.

---

## §3 Skill posture + adversarial review

- **Invoke `copowers:executing-plans`** (wraps `superpowers:subagent-driven-development` + Codex review).
- Skill inputs:
  - `PLAN_PATH=docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`
  - `AMENDMENT_PATH=docs/phase10-electives-amendment.md`
  - `SUB_BUNDLE=E` (Tasks T-E.0..T-E.4 + T-E.5 + T-E.6 electives)
  - `BASELINE_SHA=70e109b`
- **Expected Codex chain:** 2-4 rounds. Sub-bundle E has moderate Codex-value-add density (lower than D which had §A.19 set-membership + §A.6 dynamic contract). Likely closer to B/C 2-round pattern than A/D 3-4-round pattern.
- Iterate per-round fixes as `fix(phase10-bundle-E): Codex RN <severity> #N — ...` commits.
- Terminate at NO_NEW_CRITICAL_MAJOR.

### §3.1 Codex value-add concentration

Adversarial review for Sub-bundle E typically catches:

- **§A.21 per-metric Class assignment drift** — Codex will check `render_class_d` is called with correct `underlying_class` per metric per §0.8 matrix. Pre-empt with 4 BINDING discriminating tests.
- **§5.4 Class D 3-tuple decoupling drift** — Codex will check render_class_d returns 3-tuple with separately-renderable badges + drawability_text. Pre-empt with 3 BINDING tests at §0.9.
- **Lesson #18 cadence-grain rejection** — Codex will check T-E.1 reads per-trade via Phase 6 helpers, NOT cadence-grain `review_log.total_*`. Pre-empt with discriminating test that plants conflicting cadence row + asserts metric reflects per-trade compute.
- **Lesson #23 dedicated FIELD + rendering target** — Codex will check confidence-floor warning + partial-window badge + drawability_text surface as 3 distinct text elements (NOT `title=` hover-only). Pre-empt with `data-{marker}=` substring assertions.
- **Lesson #26 SQL ORDER BY tiebreaker** — Codex will check process-grade-trend iterates closed-reviewed trades with deterministic ORDER BY (`review_date, id`). Pre-empt with discriminating test on tied review_dates.
- **N=10 HARDCODED window** — Codex will check `window_size=10` is the production default + spec §8.5 LOCK preserved.
- **§A.10 inline-SVG LOCK** — Codex will check template renders `<svg>` + `<polyline>` + `<circle>`, NOT matplotlib PNG or client-side chart library. Pre-empt with template structure test.
- **T-E.3 cross-bundle pin un-skip** — Codex will check `@pytest.mark.skip(reason=...)` is REMOVED in the SAME COMMIT that retrofits the 6 VMs + the test passes. Pre-empt by removing the decorator + asserting all 6 VMs gain the field.
- **T-E.3 all 6 VMs retrofitted** — Codex will check ALL 6 base-layout VMs gain the field + ALL 6 builders populate via the helper. Pre-empt by enumerating in §0.11 + per-VM discriminating tests.
- **T-E.5 HTMX failure surfaces** — Codex will check the 3 binding browser-only failure surfaces (hx-headers; HX-Redirect-vs-303; target-route-verified). Pre-empt with §0.12 + TestClient tests.
- **T-E.5 server-stamp tampering defense** — Codex will check tampered POST body for `snapshot_date` is IGNORED (server-stamp wins). Pre-empt with discriminating test.
- **T-E.5 transaction discipline** — Codex will check handler does NOT hold open transaction when calling `record_snapshot_with_audit`.
- **T-E.6 orphan-discrepancy attribution** — Codex will check `list_unresolved_material_for_trade` excludes orphans (no trade_id by definition). Pre-empt with discriminating test.
- **T-E.6 4-branch coverage** — Codex will check (zero / unresolved-material / resolved / non-material) branches per electives amendment §2 Task E.6.
- **§A.0 + §I.1 ZERO-new-schema LOCK** — Codex will check no `0018_*.sql` migration; no ALTER on existing tables.
- **`__post_init__` validators** (lesson #1) — Codex will check all new dataclasses (`ProcessGradeTrendResult`, `ProcessGradeTrendVM`, `DiscrepancyDisplay`, etc.) have validators.
- **BaseLayoutVM extension** — Codex will check `ProcessGradeTrendVM` extends `BaseLayoutVM` + populates `unresolved_material_discrepancies_count`.

### §3.2 Per-task Codex-check pre-emption

| Task | Common Codex finding | Pre-emption |
|---|---|---|
| T-E.0 | None expected (pure recon) | Document all 6 base-layout VM constructor signatures + Phase 6 grade helpers + Phase 9 helpers verbatim |
| T-E.1 | `render_class_d` called without `underlying_class` or with wrong class | §0.8 matrix BINDING; 4 discriminating tests |
| T-E.1 | `disqualifying_violation_rate_rolling_N` missing `events_in_window` param | Pass `events_in_window=count(disqualifying=1)` per Codex R2 Minor #1 fix |
| T-E.1 | Cadence-grain short-circuit via `review_log.total_*` | REJECT; iterate per-trade via Phase 6 helpers per lesson #18 |
| T-E.1 | Non-deterministic ORDER BY on tied review_dates | ORDER BY `review_date, id` per lesson #26 |
| T-E.1 | `mistake_cost_R_rolling_N_total` returns CI instead of point | Spec §A.21 conformance deviation: "point" class only; banked V2.1 §VII.F |
| T-E.2 | matplotlib used instead of inline SVG | §A.10 LOCK; template renders `<svg><polyline/><circle/></svg>` |
| T-E.2 | Confidence-floor warning + partial-window badge merged into one display | Separate text elements per spec §5.4 + lesson #23 |
| T-E.2 | Drawability_text rendered as `title=` only | Surface as dedicated text element per lesson #23 |
| T-E.3 | Cross-bundle pin still SKIPPED after retrofit | Remove `@pytest.mark.skip` decorator IN SAME COMMIT |
| T-E.3 | Fewer than 6 base-layout VMs retrofitted | Per-VM discriminating tests cover all 6 |
| T-E.3 | banner block missing from base.html.j2 | §A.18 rendering snippet integration |
| T-E.4 | E2E test seeds insufficient surfaces | Cover all 9 metrics + 6 base-layout pages |
| T-E.4 | Phase 11 hand-off section missing capture-needs enumeration | Mirror Phase 9 Sub-bundle E pattern; enumerate operator-decision items |
| T-E.5 | `hx-headers` missing on form | Add per Phase 5 R1 M1 lesson |
| T-E.5 | Returns 303 instead of 204 + HX-Redirect | Per Phase 5 R1 M2 lesson |
| T-E.5 | HX-Redirect target `/metrics/capital-friction` not verified to exist | Add route-table assertion per Phase 6 I3 lesson |
| T-E.5 | Caller-supplied `snapshot_date` accepted | Server-stamp at handler entry per lesson #4 + Phase 8 R2/R3/R4 |
| T-E.5 | Handler holds open transaction when calling `record_snapshot_with_audit` | Service owns BEGIN IMMEDIATE per lesson #2 + Phase 9 reject-caller-held-tx |
| T-E.6 | Helper includes orphan discrepancies | WHERE trade_id IS NOT NULL filter per electives amendment §2 |
| T-E.6 | Indicator renders for resolved or non-material discrepancies | 4-branch coverage per electives amendment §2 acceptance |
| T-E.6 | Indicator section rendered when empty | Hide entirely when no unresolved material discrepancies for trade |

---

## §4 Return report shape

After all task commits land + Codex chain converges + before final return-report commit, draft a return report at `docs/phase10-bundle-E-return-report.md`:

1. Final HEAD on branch + commit count breakdown.
2. Codex round chain.
3. Test count delta + ruff baseline delta.
4. Operator-witnessed verification surfaces (PENDING orchestrator-driven gate; S1 inline OK; S2 + S3 + S4 + S5 + S6 + S7 PENDING).
5. Per-task deviations from the plan (if any) with rationale.
6. Codex Major findings ACCEPTED with rationale (if any).
7. Watch items for orchestrator.
8. Worktree teardown status (7th in cleanup-script queue).
9. **Phase 10 arc closer aggregate (NEW — Sub-bundle E pattern from Phase 9 Sub-bundle E):** commits across A+B+C+D+E; Codex rounds total; cumulative fast tests; Critical-resolved + Major-resolved counts; ACCEPT-WITH-RATIONALE total; CLAUDE.md gotchas promoted; V2.1 §VII.F amendments pending; V2 candidates banked; schema progression.
10. Phase 11 hand-off pointer.
11. Composition-surface verification via `^def` grep.
12. Any plan-text amendments applied in-tree during Codex rounds (likely none).

---

## §5 First-step paste-ready prompt for the implementer

```
You are taking over to implement Phase 10 Sub-bundle E (Process-grade-trend + Reconciliation banner + Phase 11 hand-off + T-E.5 web-form snapshot capture + T-E.6 trade detail discrepancy indicator). CLOSES Phase 10.

WORKING DIRECTORY (after worktree creation): c:\Users\rwsmy\swing-trading\.worktrees\phase10-bundle-E-process-grade-trend-and-polish
BRANCH: phase10-bundle-E-process-grade-trend-and-polish
BASELINE_SHA: 70e109b  (per dispatch brief §1.1; HEAD of main BEFORE this brief commit)
WORKTREE-BRANCHING-POINT: current HEAD of main at worktree-creation time (resolve via `git rev-parse main`)

Step 0 — Create the worktree:
  cd c:\Users\rwsmy\swing-trading
  $base = git rev-parse main
  git worktree add .worktrees\phase10-bundle-E-process-grade-trend-and-polish -b phase10-bundle-E-process-grade-trend-and-polish $base
  New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active

Step 1 — Read the dispatch brief end-to-end:
  docs/phase10-bundle-E-executing-plans-dispatch-brief.md

Step 2 — Read the Phase 10 plan §H + electives amendment §2 + cross-bundle invariants §I:
  docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md  (§H lines 1552-1681 for tasks T-E.0..T-E.4; §I lines 1665-1744 for invariants; §A.6 + §A.7 + §A.10 + §A.18 + §A.21 for AMENDED interface contracts + inline-SVG LOCK + per-metric Class assignment matrix)
  docs/phase10-electives-amendment.md  (§2 Task E.5 + Task E.6 for elective task specs)

Step 3 — Read the Phase 10 brainstorm spec:
  docs/superpowers/specs/2026-05-06-phase10-metrics-design.md  (§3.8 process-grade-trend + §4.8 surface + §5.4 Class D rendering + §8.5 N=10 hardcoded + §A.21 spec-conformance deviation banked)

Step 4 — Read binding conventions + forward-binding lessons:
  - CLAUDE.md (gotchas; "HTMX form-driven endpoints" + "HX-Redirect target route must be verified" + "session-anchor read/write mismatch" + "server-stamp at handler entry" gotcha families ALL APPLY)
  - docs/orchestrator-context.md
  - docs/phase10-bundle-A-return-report.md §10 (forward-binding lessons binding)
  - docs/phase10-bundle-B-return-report.md §5 + §8
  - docs/phase10-bundle-C-return-report.md §5 + §9
  - docs/phase10-bundle-D-return-report.md §5 + §9 (NEW lessons #23-#26)

Step 5 — Verify worktree state:
  git rev-parse HEAD                       # expect current main HEAD (typically the dispatch brief commit)
  git status                               # expect clean
  python -m pytest -m "not slow" -q        # expect baseline GREEN (~3147 passed worktree-side; 6 skipped — 1 cross-bundle T-A.7 pin + 1 Task 7.3 + 4 fixture-absent; 3 pre-existing fails NOT regressions). ~6:00 wall-clock.
  python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"  # expect 17
  ruff check swing/ --statistics            # expect 18 E501
  python verify_phase10.py                  # expect exit 0

Step 6 — Pre-implementation recon:
  grep -rn "^def " swing/metrics/honesty.py swing/metrics/policy.py swing/metrics/cohort.py swing/metrics/discrepancies.py swing/metrics/process.py swing/metrics/tier.py swing/metrics/capital.py swing/metrics/maturity.py swing/metrics/funnel.py swing/metrics/equity_resolver.py
  grep -rn "^def " swing/trades/review.py | grep -i 'compute_.*_grade\|compute_disqualifying'  # Phase 6 helpers for T-E.1
  grep -rn "^def " swing/trades/account_equity_snapshots.py  # Phase 9 helper for T-E.5
  grep -rn "^def " swing/data/repos/reconciliation.py | grep -i 'list_unresolved'  # Phase 9 helpers for T-E.6
  grep -n "^class \|^def " swing/web/view_models/dashboard.py swing/web/view_models/pipeline.py swing/web/view_models/journal.py swing/web/view_models/watchlist.py swing/web/view_models/config.py swing/web/view_models/error.py  # 6 base-layout VMs for T-E.3
  grep -n "^class \|^def " swing/web/view_models/trades.py | grep -i 'TradeDetail\|build_trade_detail'  # T-E.6 target VM
  grep -n "_SUB_VM_EXCLUSIONS\|@pytest.mark.skip" tests/web/test_view_models/test_base_layout_vm_coverage.py  # T-E.3 un-skip target
  cat swing/web/templates/base.html.j2 | head -50  # T-E.3 banner block integration point

Step 7 — Invoke copowers:executing-plans:
  - PLAN_PATH: docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md
  - AMENDMENT_PATH: docs/phase10-electives-amendment.md
  - SUB_BUNDLE: E
  - BASELINE_SHA: 70e109b

Step 8 — Execute tasks task-by-task per plan §H + electives amendment §2:
  - T-E.0 recon (no commit; document inline)
  - T-E.1 §3.8 process-grade-trend computations (commit: feat(metrics): §3.8 process-grade-trend computations (T-E.1))
  - T-E.2 ProcessGradeTrendVM + route + template (commit: feat(metrics): process-grade-trend VM + route + template — inline SVG (T-E.2))
  - T-E.3 Reconciliation discrepancy banner + 6 base-layout VM retrofit + cross-bundle pin un-skip (commit: feat(metrics): unresolved-material discrepancy banner — base.html.j2 + 6 existing base-layout VMs (T-E.3))
  - T-E.4 Phase 10 closer + final integration test + ruff sweep (commit: docs(phase10): Phase 10 closer — Phase 11 hand-off + final integration sweep (T-E.4))
  - T-E.5 web-form snapshot capture elective (commit: feat(web): manual snapshot capture web form (T-E.5 elective))
  - T-E.6 per-trade discrepancy indicator elective (commit: feat(web): per-trade unresolved-material indicator on trade detail (T-E.6 elective))

Step 9 — Iterate Codex rounds until NO_NEW_CRITICAL_MAJOR. Expected 2-4 rounds.

Step 10 — Draft return report at docs/phase10-bundle-E-return-report.md per dispatch brief §4 (INCLUDES Phase 10 arc closer aggregate per Phase 9 Sub-bundle E pattern). Commit it.

Step 11 — Remove-Item .copowers-subagent-active + signal orchestrator. Orchestrator drives operator-witnessed gate (S2 through S7 surfaces via Chrome MCP; S3/S4/S6/S7 require production-write authorization for plant-and-revert pattern) + integration merge + Phase 10 closer housekeeping commit.

DO NOT:
  - Push to origin from inside the worktree
  - Merge to main (orchestrator action)
  - Use --amend or --no-verify
  - Add Claude co-author footer
  - Skip the marker-file removal
  - Skip the Step 6 pre-implementation recon
  - Add ANY new schema (§A.0 LOCK; EXPECTED_SCHEMA_VERSION stays at 17 through Phase 10 V1 close)
  - Skip __post_init__ validators on new dataclasses
  - Render confidence-floor warning + partial-window badge + drawability_text combined (separate text elements per spec §5.4 + lesson #23)
  - Aggregate process-grade-trend via cadence-grain `review_log.total_*` (lesson #18; iterate per-trade via Phase 6 helpers)
  - Use non-deterministic SQL ORDER BY on review_date (lesson #26; add `id` tiebreaker)
  - Use matplotlib for the chart (§A.10 LOCK; inline SVG ONLY)
  - Render badges as `title=` hover-only (lesson #23; dedicated FIELD + rendering target)
  - Skip the T-E.3 cross-bundle pin un-skip — MUST remove `@pytest.mark.skip` IN SAME COMMIT
  - Retrofit fewer than 6 base-layout VMs (all 6 named in plan §H T-E.3 + dispatch brief §0.11)
  - Skip the T-E.5 HTMX failure-surface defenses (hx-headers + HX-Redirect + target-route-verified)
  - Accept caller-supplied `snapshot_date` in T-E.5 POST body (server-stamp at handler entry)
  - Hold open transaction in T-E.5 handler when calling `record_snapshot_with_audit` (Phase 9 reject-caller-held-tx contract)
  - Include orphan discrepancies in T-E.6 helper (WHERE trade_id IS NOT NULL)
  - Render T-E.6 indicator when no unresolved material discrepancies for trade (hide entirely when empty)
  - Add HTMX OOB-swap or embedded forms anywhere in Phase 10 surfaces (§A.9 + §I.6 LOCK)
  - Bundle this with a post-Phase-10 standalone dispatch (cleanup-script -DeregisterFirst + test-runtime are SEPARATE post-Phase-10 dispatches per phase3e-todo)
  - Add color-only badges (spec §4.9 BINDING)
  - Forget to update `_SUB_VM_EXCLUSIONS` in `tests/web/test_view_models/test_base_layout_vm_coverage.py` if any new sub-VM is introduced (likely none in E — verify)
```

---

## §6 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-13 (post-Sub-bundle-D-ship).
- **Brief commit:** `<filled-in-after-commit>`.
- **Brief HEAD context:** `70e109b` on main (post-Sub-bundle-D-ship housekeeping).
- **Worktree path (binding):** `.worktrees/phase10-bundle-E-process-grade-trend-and-polish/`.
- **Baseline test count (main HEAD):** ~3150 fast (2 skipped). Worktree-side: ~3147 fast (6 skipped — 4 `thinkorswim/*.csv` fixture-absent + 1 cross-bundle T-A.7 pin + 1 Task 7.3 operator-only).
- **Baseline ruff count:** 18 (E501 only).
- **Plan status:** Codex R1-R6 NO_NEW_CRITICAL_MAJOR; AMENDED in-tree during Sub-bundle A R2 + R3; LOCKED.
- **Electives amendment status:** SHIPPED 2026-05-13 at `9525f17`; NORMATIVE; T-E.5 + T-E.6 binding for Sub-bundle E.
- **Spec status:** Codex R1-R5 substantive + R6 confirmation; shipped 2026-05-06 at `fe6cb45`; 641 lines; LOCKED.
- **Expected dispatch wall-clock:** ~10-14 hr executing-plans + ~2-4 hr Codex convergence. 7 tasks total — largest task count in Phase 10 (matches A's 10-task scope but A had foundational dependencies).
- **Expected test count delta:** +48..+77 fast tests; post-E ~3195..~3224 worktree-side / ~3198..~3227 main HEAD.
- **Expected ruff delta:** 0 (baseline preserved).
- **Test runtime concern:** S1 inline gate ~6-7 min wall-clock at projected test count; **deferred** xdist + fixture-scope refactor per phase3e-todo 2026-05-13 post-Phase-10 backlog. Sub-bundle E inherits current test-runner setup.
- **Phase 10 arc closer:** Sub-bundle E ships → orchestrator drives operator-witnessed gate (7 surfaces) → integration merge → **Phase 10 closer housekeeping commit** drafted by orchestrator (mirror Phase 9 Sub-bundle E closer pattern) → Phase 11 candidate triage UNBLOCKED + 3 post-Phase-10 standalone dispatches UNBLOCKED (cleanup-script `-DeregisterFirst` extension; test-runtime analysis; §8.4 Corporate_Actions MVP).

---

## §7 Watch items for orchestrator (post-Sub-bundle-E-ship)

1. **Operator-witnessed gates S2 through S7** — 6 browser-side checks (orchestrator-driven via Chrome MCP on port 8081). S3 + S4 + S6 + S7 require production-write authorizations for plant-and-revert pattern.

2. **Cross-bundle pin at T-A.7 UN-SKIPPED** — T-E.3 SAME COMMIT removes `@pytest.mark.skip` decorator + the test PASSES. Verify at integration merge.

3. **Phase 10 closer housekeeping** — orchestrator drafts the closer entry in CLAUDE.md status line + the Phase 10 arc-aggregate entry in phase3e-todo.md per Phase 9 Sub-bundle E closer pattern (cumulative test count + cumulative Codex rounds + cumulative Major-all-resolved count + cumulative ACCEPT-WITH-RATIONALE count + cumulative spec amendments pending + cumulative V2 candidates banked).

4. **Phase 11 candidate triage UNBLOCKED post-merge** — operator + orchestrator triage Phase 11 scope from the 22+ banked V2.1 §VII.F amendment candidates + 4+ V2 candidates banked + 3 post-Phase-10 standalone dispatches (cleanup-script extension + test-runtime analysis + §8.4 Corporate_Actions MVP).

5. **Production snapshot state post-S6** — S6 creates a 3rd production snapshot. Orchestrator-decision at gate time: leave as fresh equity reading OR revert. Default: leave.

6. **Test count overshoot precedent** — Phase 10 cumulative: +387 cumulative fast tests at D close. Sub-bundle E projection +48..+77; expect upper end. Phase 10 arc total projected to land ~1240..1270 cumulative.

7. **Worktree husk** — Sub-bundle E teardown expected to leave ACL-locked husk; 7th in cleanup-script queue. Cleanup-script `-DeregisterFirst` extension still deferred (becomes the FIRST post-Phase-10 standalone dispatch).

8. **No Sub-bundle F** — Phase 10 has 5 sub-bundles (A→B→C→D→E); E closes. Next dispatch is Phase 11 candidate triage OR one of the 3 post-Phase-10 standalone dispatches (operator-driven choice).

---

## §8 Dispatch order — UNCHANGED

A ✓ → B ✓ → C ✓ → D ✓ → E (this dispatch; **CLOSES Phase 10**). Sub-bundles A + B + C + D are SHIPPED; Sub-bundle E is the final dispatch.

Post-Sub-bundle-E-ship → Phase 10 closer housekeeping → 3 post-Phase-10 standalone dispatches available (cleanup-script `-DeregisterFirst` extension; test-runtime analysis; §8.4 Corporate_Actions MVP) + Phase 11 candidate triage.

---

*End of dispatch brief. Sub-bundle E is the closer for Phase 10. 7 tasks total: 1 final operator-visible Phase 10 surface (§4.8 process-grade-trend with inline SVG chart per §A.10 LOCK) + cross-bundle reconciliation banner integration (retrofits 6 EXISTING base-layout VMs + un-skips cross-bundle T-A.7 pin) + 2 elective surfaces (T-E.5 web-form snapshot capture introducing ONE new HTMX form failure-surface budget hit; T-E.6 per-trade discrepancy indicator) + Phase 11 hand-off documentation. All 7 tasks inherit AMENDED Sub-bundle A interfaces + Sub-bundle B + C + D implementation conventions; ZERO new schema; ONE new write path (T-E.5 via Phase 9 Sub-bundle C `record_snapshot_with_audit` service); 6 browser surfaces + 1 inline = 7 gate surfaces (AT the ≤6 budget ceiling; operator-decision at gate time on consolidation).*
