# Phase 10 Sub-bundle D — executing-plans dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Phase 10 Sub-bundle D per plan §G (Tasks T-D.0..T-D.7) on an isolated worktree branch via `copowers:executing-plans` (wraps `superpowers:subagent-driven-development` + adversarial Codex MCP review). Sub-bundle D lands the **fifth + sixth + seventh operator-visible Phase 10 dashboard surfaces**: §4.4 Capital-friction view + §4.5 Maturity-stage view + §4.6 Identification-vs-trade-funnel view. **First dispatch to introduce the PROVISIONAL/LIVE dynamic badge contract** (§A.6) + the **§A.0.1 historical-reconstruction disclosure footnote** (capital-friction + identification-funnel trend sections) + **§A.19 risk_feasibility_blocked_rate** with set-membership guard (9 discriminating tests pinning the 6-finding-deep Codex fix sequence from writing-plans).

**Expected duration:** ~10-14 hr executing-plans wall-clock + ~3-5 hr Codex convergence. Plan §G has 8 tasks T-D.0..T-D.7 (no electives in D per electives amendment §3). Estimated 3-5 Codex rounds (Sub-bundle A: 4 rounds; B: 2; C: 2; Phase 9 D had Critical findings → 4 rounds). Sub-bundle D introduces the highest Codex-value-add density of Phase 10 (PROVISIONAL/LIVE dynamic contract + §A.19 SQL set-membership guard + §A.0.1 historical disclosure + 30-trading-day window off-by-one defense). Likely toward upper end of round estimate.

---

## §0 Inputs

### §0.1 Plan
- **PLAN_PATH:** `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`
- **Plan status:** Codex R1-R6 → NO_NEW_CRITICAL_MAJOR; shipped 2026-05-13 at `a34c00d`; AMENDED in-tree during Sub-bundle A Codex R2+R3 (commits `e32f71c` + `75dd63f`). Sub-bundle D reads the AMENDED §A.7 + §D Task A.1 text. 2008+ lines.
- **Sub-bundle D scope:** plan §G (lines 1354-1550); 8 tasks T-D.0..T-D.7.
- **Cross-bundle invariants:** plan §I (lines 1665-1744); 15 invariants. Sub-bundle D exercises §I.3 (risk_policy split — N/A for D; D uses LIVE-only policy via `read_live_policy` since these are operational metrics per §A.5), **§I.4 PROVISIONAL/LIVE dynamic badge LOCK (FIRST Sub-bundle to surface this)**, §I.5 (BaseLayoutVM mixin — all 3 new VMs extend it), §I.6 (HTMX failure-surface budget — §A.9 pure server-render LOCK preserved), §I.7 (per-pipeline-run aggregation LOCK — capital-friction + funnel compute via on-the-fly JOIN NOT new schema columns), §I.8 (decoupling discipline), §I.10 (NO INSERT OR REPLACE — N/A; no writes), §I.13 (session-anchor read/write predicate alignment — capital-friction asof_date uses backward-looking `last_completed_session`), §I.14 (empty-cohort + zero-trade rendering — all 3 surfaces), §I.15 (operator-witnessed gate per surface — 4 browser + 1 inline + 1 round-trip = 5 + 1 round-trip surfaces).

### §0.2 Electives amendment
- **AMENDMENT_PATH:** `docs/phase10-electives-amendment.md`
- **Amendment status:** SHIPPED 2026-05-13 at `9525f17`; NORMATIVE supplement to plan §A.4 + §E + §F + §H.
- **Sub-bundle D impact:** **ZERO** — no electives touch Sub-bundle D scope per amendment §3 decomposition table. Sub-bundle D ships plan §G verbatim (8 tasks).

### §0.3 Spec
- **SPEC_PATH:** `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md`
- **Spec status:** Codex R1-R5 substantive + R6 confirmation; SHIPPED 2026-05-06 at `fe6cb45`; 641 lines; RESEARCH-POSTURE.
- **Sub-bundle D spec coverage:** §3.4 capital-friction metrics (Tasks D.1+D.2); §3.5 maturity-stage metrics (Tasks D.3+D.4); §3.6 identification-vs-trade-funnel metrics (Tasks D.5+D.6); §4.4 capital-friction view; §4.5 maturity-stage view; §4.6 identification-vs-trade-funnel view; §5 honesty policy applied across all surfaces; §6.1 Phase 8 capture-need rendering (maturity-stage NULL → "—" placeholder, NOT capture-pending text since Phase 8 IS shipped); §3.6 R1 Minor #2 LOCK (NO `watch_take_rate_per_run` in V1 — spec doesn't define it).

### §0.4 Project state at dispatch time
- **HEAD on `main`:** `3af36d0` (post-Sub-bundle-C-ship housekeeping; merge at `a814006`).
- **Test count (main HEAD):** **~3048 fast passing + 2 skipped on main HEAD `3af36d0`** (3045 worktree-side + 3 pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py` accounted-for; 3 pre-existing failures NOT regressions). **Worktree-side baseline:** ~3045 fast passing + 6 skipped. Implementer runs from worktree, so plan §G baseline-test-count documentation should reflect the WORKTREE-side number.
- **Test runtime concern (operator-acknowledged 2026-05-13):** fast suite at ~5:15 wall-clock; profile + pytest-xdist + fixture-scope refactor deferred as standalone post-Phase-10 dispatch per `docs/phase3e-todo.md` 2026-05-13 entry. Sub-bundle D inherits the current test-runner setup; expect S1 inline gate to take ~5-6 min at projected ~3100-3150 tests post-D.
- **Ruff baseline:** **18 (E501 only).** Unchanged across Sub-bundles A + B + C + entire Phase 9 arc.
- **Schema version:** **v17.** LOCKED since Phase 9 Sub-bundle A; Sub-bundle D introduces ZERO schema changes per §A.0 + §I.1 LOCK. `EXPECTED_SCHEMA_VERSION` stays at 17.
- **Active risk_policy:** `policy_id=5` (Option C revert post-Sub-bundle-A; `max_account_risk_per_trade_pct=0.5` cfg-aligned; `capital_floor_constant_dollars=7500.0`; `scratch_epsilon_R=0.10`). Unchanged through Sub-bundles B + C.
- **Production trades:** 8 total; 5 open (DHC/YOU/VSAT/CVGI/LAR) + 3 closed (VIR/CC/SGML).
- **Production account_equity_snapshots:** 2 manual snapshots (#1 $2000 at 2026-05-11; #2 $1800 at 2026-04-01 back-recorded). **Sub-bundle D S2 + S5 gate semantics depend on this:** capital-friction renders LIVE badge when snapshot exists on-or-before `last_completed_session(now)`. Snapshot #1 is on `2026-05-11`; if `last_completed_session(now)` ≥ `2026-05-11`, LIVE badge fires. Operator may need to record a fresh snapshot for the S5 round-trip test (orchestrator drives via plain-chat operator authorization OR via `swing account snapshot record` CLI).
- **Production pipeline_runs:** 60+ runs (some completed, some failed). Trend windows (capital-friction + identification-funnel) use 30-trading-session window ending at `last_completed_session(now)` — production has well above 30 sessions of runs.

### §0.5 Sub-bundle A interface inheritance — AMENDED plan §A.7 + Sub-bundle B + C implementation conventions

**CRITICAL:** Plan §A.7 + §D Task A.1 were AMENDED in-tree during Sub-bundle A Codex R2 + R3 fix commits (`e32f71c` + `75dd63f`). Sub-bundle D reads the AMENDED text. Specifically (verbatim from Sub-bundle C dispatch brief §0.5):

**HonestyBadges dataclass (per AMENDED §A.7):**
```python
@dataclass(frozen=True)
class HonestyBadges:
    confidence_floor_warning: bool   # spec §5 — visible when n < global_confidence_floor_n
    low_confidence_warning: bool     # spec §5 — visible when 3 ≤ n < 5
    window_not_full_warning: bool = False  # spec §5.4 — rolling-window not yet at N
```

**Public helpers in `swing/metrics/honesty.py`** (Sub-bundle D may consume per task; capital-friction uses Class A/B/D classes for some metrics, funnel uses Class A for take-rate):
- `wilson_ci`, `bootstrap_ci_mean`, `suppress_for_n`, `badges_for_n` (PUBLIC), `render_class_a/b/c/d`.

**Risk_policy resolver (per AMENDED implementation):**
- `swing/metrics/policy.py:read_live_policy(conn) -> RiskPolicy` — **Sub-bundle D primary consumer** for `current_capital_utilization_pct` + `current_portfolio_heat_pct` + `capital_feasibility_pressure_index` (operational metrics use LIVE policy per §A.5).
- `swing/metrics/policy.py:read_at_trade_time_policy(conn, *, policy_id_stamp: int | None)` — N/A for Sub-bundle D (these are operational, not governance, metrics).

**Live capital denominator resolver (per §A.6 — FIRST surfaced by D):**
- `swing/metrics/equity_resolver.py:resolve_live_capital_denominator_dollars(conn, *, asof_date: date) -> tuple[float, EquityBadge]` — returns `(denominator_dollars, badge)` where badge is the dynamic PROVISIONAL/LIVE flag.
- **PROVISIONAL contract:** when `account_equity_snapshots` has NO snapshot ≤ `asof_date`, badge = PROVISIONAL + denominator = `read_live_policy(conn).capital_floor_constant_dollars`.
- **LIVE contract:** when `account_equity_snapshots` HAS snapshot ≤ `asof_date`, badge = LIVE + denominator = `max(capital_floor_constant_dollars, snapshot.equity_dollars)`.
- **BINDING for T-D.1 (capital-friction):** every metric that uses live capital denominator MUST surface the badge from `resolve_live_capital_denominator_dollars` per-metric; the dynamic flip from PROVISIONAL → LIVE on snapshot-record is the BINDING §I.13 round-trip test.

**BaseLayoutVM mixin (per AMENDED §A.6 + §A.18):**
- Fields: `session_date: str`, `stale_banner: str | None = None`, `price_source_degraded: bool = False`, `price_source_degraded_until: str | None = None`, `ohlcv_source_degraded: bool = False`, `unresolved_material_discrepancies_count: int = 0`.
- **Sub-bundle D's `CapitalFrictionVM` + `MaturityStageVM` + `IdentificationFunnelVM` MUST extend `BaseLayoutVM`.** Constructor populates `unresolved_material_discrepancies_count=count_unresolved_material(conn)` per §A.18.

**Discrepancies helper (per §A.7.1):**
- `swing/metrics/discrepancies.py:count_unresolved_material(conn) -> int` — invoke in each VM constructor.

**Phase 8 helper inheritance (per plan §G T-D.3 + spec §6.1):**
- `swing/data/repos/daily_management.py:list_open_position_active_snapshots(conn)` — Phase 8 SHIPPED helper that returns per-open-position latest active snapshot. **Sub-bundle D T-D.3 maturity-stage compute consumes this.** Spec §3.5 R1 M5 + §6.1: per-row cells with NULL Phase-8-capture-need columns (`trail_MA_candidate_price`, `planned_target_R`) render `"—"` placeholder (NOT "[Phase 8 capture pending]" — Phase 8 IS shipped; NULL is a data-state not a capture-state).

**Phase 9 helper inheritance (per plan §G T-D.0):**
- `swing/data/repos/account_equity_snapshots.py:get_latest_snapshot_on_or_before(conn, *, asof_date)` — Phase 9 Sub-bundle C SHIPPED helper. **Consumed by `resolve_live_capital_denominator_dollars` to decide PROVISIONAL vs LIVE.**
- `swing/data/repos/risk_policy.py:get_active_policy(conn)` — Phase 9 Sub-bundle A SHIPPED. Returns `RiskPolicy` with `capital_floor_constant_dollars`.

**Risk-feasibility criterion constant (per plan §G T-D.0 + §A.19):**
- `swing/evaluation/criteria/risk_feasibility.py:NAME` — string constant `'risk_feasibility'`. **T-D.1 MUST `from swing.evaluation.criteria.risk_feasibility import NAME` and use the constant, NOT the string literal.** Codex R5 Major #1 from writing-plans pins this.

**Cross-bundle pin (still SKIPPED at T-A.7):**
- `tests/web/test_view_models/test_base_layout_vm_coverage.py::test_existing_dashboard_vm_has_unresolved_material_field` REMAINS SKIPPED with reason naming Sub-bundle E T-E.3 as the un-skip point. Sub-bundle D does NOT touch the skip.

**Sub-bundle B + C implementation conventions (BINDING for D):**

1. **Cohort-grain vs cadence-grain (lesson #18):** D primarily reads `pipeline_runs` (per-run-grain) + `daily_management_records` (cadence-grain BY DESIGN per Phase 8). **NOT applicable as a violation** — these are the right sources per spec §3.4 + §3.5 + §3.6. However: if D's implementation is tempted to short-circuit a per-run metric via a cadence aggregation (e.g., `reconciliation_runs.summary_json`), REJECT. Discriminating-test pattern: plant conflicting cadence row + assert metric reflects per-run compute.

2. **Percent-vs-proportion explicit pin (lesson #19; HIGHLY APPLICABLE):** D's percent metrics are numerous. Each MUST have explicit rendering-unit pin:
   - `current_capital_utilization_pct`: PERCENT (e.g., `45.0` = 45%; ratio of total exposure to live capital denominator × 100). Discriminating test: seed exposure=$3375 + capital=$7500 → assert 45.0 (NOT 0.45).
   - `current_portfolio_heat_pct`: PERCENT (sum of per-position heat as % of capital).
   - `risk_feasibility_blocked_rate`: BOUNDED [0, 1] PROPORTION per §A.19 + spec §3.4 (e.g., 0.25 = 25% of would-have-qualified candidates failed risk_feasibility). **Note:** this is the ONLY D metric rendered as PROPORTION (matches §A.19 plan text); template MUST render with a `%` suffix or explicit "of qualifying candidates" qualifier (operator-readability). Discriminating test: assert numeric proportion 0.25 AND assert rendered template contains `"25%"` (template multiplies for display) OR `"0.25 of qualifying"` (template renders as proportion with qualifier).
   - `aplus_take_rate_per_run`: BOUNDED [0, 1] PROPORTION per spec §3.6 + §A.20.
   - `position_capital_utilization_pct` (maturity-stage per-position): PERCENT.

3. **Sub-VM exclusion-set propagation:** D may introduce new sub-VMs (e.g., `CapitalGaugeVM`, `MaturityRowVM`, `FunnelBarVM`, `ProvisionalBadgeVM` if not already in `_SUB_VM_EXCLUSIONS`). **Verify each new sub-VM ending in `VM` that does NOT extend BaseLayoutVM is added to `_SUB_VM_EXCLUSIONS` in `tests/web/test_view_models/test_base_layout_vm_coverage.py` IN THE SAME COMMIT** (Sub-bundle B + C established this convention). **Note:** Sub-bundle A already added `ProvisionalBadgeVM` to the exclusion set; verify before adding duplicate.

4. **Toggle hrefs (lesson #21):** D has ZERO new toggles in V1 (capital-friction + maturity-stage + identification-funnel are all server-rendered read-only surfaces with no filter UI). Lesson does NOT apply at this dispatch.

5. **Filter at compute layer (lesson #22):** D has ZERO new filters in V1. Lesson does NOT apply.

### §0.6 22-lesson forward-binding catalog (Phase 9 arc + Sub-bundle A + B + C → D)

Cumulative lesson catalog. Lessons 1-19 from Sub-bundle C dispatch brief §0.6; lessons 20-22 NEW from Sub-bundle C return report §9.

| # | Lesson | Sub-bundle D applicability |
|---|---|---|
| 1 | `__post_init__` validator pattern on all new dataclasses | **YES** — `CapitalFrictionResult`, `MaturityStageResult`, `IdentificationFunnelResult`, all VMs, all sub-VMs need NaN/inf rejection + invariant assertions (e.g., percent fields ≥ 0; proportion fields ∈ [0, 1]; n ≥ 0) |
| 2 | Service-layer transaction discipline | N/A (Sub-bundle D is read-only) |
| 3 | NO `INSERT OR REPLACE` | N/A |
| 4 | Server-stamping discipline at handler entry | N/A (no new forms) |
| 5 | Composition-surface enumeration via `^def` grep | **YES** — pre-implementation recon greps Sub-bundle A + B + C surfaces + Phase 8 `daily_management.list_open_position_active_snapshots` + Phase 9 `account_equity_snapshots.get_latest_snapshot_on_or_before` |
| 6 | Empirical-verification of brief assertions | YES — verify Phase 9 helper signatures + `risk_feasibility.NAME` constant existence + `account_equity_snapshots` table contents BEFORE locking T-D.0 recon |
| 7 | Form-render hidden anchors round-trip | N/A (no new forms) |
| 8 | POST-time recompute of "latest-of-something" TOCTOU | N/A |
| 9 | Test fixtures USERPROFILE+HOME monkeypatch | N/A |
| 10 | HTMX browser-only failure surfaces | **YES** — operator-witnessed gate is BINDING for 3 new browser surfaces (S2 capital-friction + S3 maturity-stage + S4 funnel) + 1 round-trip (S5 PROVISIONAL→LIVE flip) |
| 11 | `<tr>`-leading HTMX response | N/A (per §A.9 + §I.6 — pure server-rendered HTML; no HTMX OOB-swap) |
| 12 | matplotlib mathtext | N/A (Sub-bundle D has no charts; inline SVG is Sub-bundle E only) |
| 13 | `base.html.j2` shared fields require adding to EVERY base-layout VM | **YES** — all 3 new VMs MUST extend BaseLayoutVM mixin per §A.18 |
| 14 | Session-anchor read/write predicate alignment | **YES — HIGHLY APPLICABLE** — capital-friction asof_date uses backward-looking `last_completed_session(now)`; funnel trend uses 30-trading-day window ending at backward-looking `last_completed_session(now)`. §I.13 round-trip integration test BINDING: write snapshot at session N + immediately invoke compute_capital_friction(asof_date=N) + assert LIVE badge returned |
| 15 | Discriminating-test arithmetic | **YES — HIGHLY APPLICABLE** — §A.19 risk_feasibility_blocked_rate has 9 discriminating tests required (writing-plans pinned the 6-finding-deep Codex sequence) |
| 16 | Plan §A.7 amendments flow same commit as code | YES — if implementer adds new public function / dataclass field / signature param in `swing/metrics/honesty.py` OR shipped A/B/C interfaces, plan §A.7 binding interface MUST update in-tree to match. Likely-OFF in D (interface locked at A close; B + C did not need new amendments) |
| 17 | Statistical helper formula explicit pin | YES — Sub-bundle D's bootstrap CI on multi-run trends already pinned in §A.7 + Sub-bundle A's deterministic seed pattern. Watch for any new helper D introduces |
| 18 | Cadence-grain audit tables CANNOT be cleanly mapped to cohort-grain metrics | YES — DEFENSIVE: D reads `pipeline_runs` (per-run-grain) + `daily_management_records` (cadence-grain BY DESIGN). If implementer is tempted to short-circuit a per-run metric via `reconciliation_runs.summary_json` or `review_log.total_*`, REJECT |
| 19 | Unit-semantic precision (percent vs proportion) | **YES — HIGHLY APPLICABLE** — multiple percent metrics + 2 proportion metrics. See §0.5 #2 above for the specific pin recommendations |
| 20 (NEW from C) | Body-wide unit-substring assertion is non-discriminating when seed text contains the same substring | **YES — HIGHLY APPLICABLE** — capital-friction renders the §A.0.1 historical-disclosure footnote text which may contain `%` or `R` substrings; PROVISIONAL/LIVE badge text "PROVISIONAL" / "LIVE" is short + may collide with other body text. Discriminating-test pattern: seed worked example + assert EXACT rendered substring at the cell/badge location |
| 21 (NEW from C) | Toggle/filter links use relative query href | N/A (D has zero toggles in V1) |
| 22 (NEW from C) | Per-cohort filters affecting cell suppression MUST be applied at compute layer | N/A (D has zero filters in V1) |

### §0.7 Sub-bundle D scope summary (per plan §G)

| Task | Files | Acceptance | Test count est. |
|---|---|---|---:|
| **T-D.0** recon | read-only | Phase 9 + Phase 8 helper signatures verified; `risk_feasibility.NAME` constant confirmed; production `account_equity_snapshots` rows enumerated | 0 |
| **T-D.1** §3.4 capital-friction computations + dynamic PROVISIONAL contract | `swing/metrics/capital.py` + `tests/metrics/test_capital.py` | 6 §3.4 metrics + PROVISIONAL/LIVE badge state; `risk_feasibility_blocked_rate` per §A.19 SQL with set-membership guard; `current_capital_utilization_pct` + `current_portfolio_heat_pct` use `resolve_live_capital_denominator_dollars`; §A.0.1 historical multi-run trend uses CURRENT trade state (per Codex R2 Major #4); §I.13 round-trip + §A.15 session-anchor LOCK; **9 discriminating tests for §A.19 mirror plan §G T-D.1 verbatim** (set-membership guard against missing-or-extra criterion names) | ~25-40 |
| **T-D.2** CapitalFrictionVM + route + template | `swing/web/view_models/metrics/capital_friction.py` + `swing/web/routes/metrics.py` (add `GET /metrics/capital-friction`) + `swing/web/templates/metrics/capital_friction.html.j2` + `tests/web/test_view_models/test_capital_friction_vm.py` | Extends BaseLayoutVM; renders point-in-time gauges + multi-run trend (suppressed at <5 runs per spec §4.4); PROVISIONAL badges as TEXT inline per §A.6 + spec §4.9; **historical-reconstruction disclosure footnote rendered in trend section per §A.0.1 — exact text "Trend computed from current trade state; historical points approximate where state has changed since the run."** | ~8-12 |
| **T-D.3** §3.5 maturity-stage computations | `swing/metrics/maturity.py` + `tests/metrics/test_maturity.py` | `compute_maturity_stage(conn)` returns per-position list with maturity_stage + open_MFE_R_to_date + open_MAE_R_to_date + current_stop + planned_target_R + trail_MA_eligibility_flag + position_capital_utilization_pct (with PROVISIONAL/LIVE per §A.6) + position_portfolio_heat_contribution_dollars; reads from `daily_management.list_open_position_active_snapshots` (Phase 8); NULL Phase-8-capture-need columns render `"—"` placeholder per spec §3.5 R1 M5 + §6.1 | ~8-12 |
| **T-D.4** MaturityStageVM + route + template | `swing/web/view_models/metrics/maturity_stage.py` + `swing/web/routes/metrics.py` (add `GET /metrics/maturity-stage`) + `swing/web/templates/metrics/maturity_stage.html.j2` + `tests/web/test_view_models/test_maturity_stage_vm.py` | Extends BaseLayoutVM; per-position table sorted by maturity_stage; aggregate count by stage; per-row cells with NULL Phase-8-capture-need columns render `"—"`; empty-state placeholder `"No open positions to manage."`; N/A for sample-size threshold (per-position) | ~5-8 |
| **T-D.5** §3.6 identification-vs-trade-funnel computations | `swing/metrics/funnel.py` + `tests/metrics/test_funnel.py` | `compute_identification_funnel(conn, *, run_window: int = 30)` returns per-run aggregates + 30-trading-session rolling trend; per-run aplus_identifications + aplus_trades_taken + aplus_take_rate + watch_identifications + watch_trades_taken (NO `watch_take_rate_per_run` per spec §3.6 R1 M2); aplus_take_rate zero-denominator handling per §A.20 (suppressed text); **30-trading-day window via `exchange_calendars.get_calendar('XNYS').sessions_window(pd.Timestamp(end), -30)` ending at `last_completed_session(now)` inclusive; discriminating test seeds 31 sessions + asserts only most-recent 30 in trend**; §A.0.1 historical trend uses CURRENT trade state | ~12-18 |
| **T-D.6** IdentificationFunnelVM + route + template | `swing/web/view_models/metrics/identification_funnel.py` + `swing/web/routes/metrics.py` (add `GET /metrics/identification-funnel`) + `swing/web/templates/metrics/identification_funnel.html.j2` + `tests/web/test_view_models/test_identification_funnel_vm.py` | Extends BaseLayoutVM; per-run stacked bar (count A+ identified vs taken; ratio = take rate) + 30-day rolling trend line (suppressed when <10 runs); **historical-reconstruction disclosure footnote same text as CapitalFrictionVM per §A.0.1** | ~5-8 |
| **T-D.7** Sub-bundle D integration test + ruff sweep | `tests/integration/test_phase10_bundle_d_e2e.py` + ruff sweep | E2E happy path: seed snapshot + open positions + pipeline_runs + verify all 3 surfaces render with correct PROVISIONAL/LIVE flips | ~4-6 |

**Projected test count delta: +67..+104 fast tests** (per plan §G individual task estimates summed; matches Sub-bundle A + B + C overshoot precedent — expect upper end). Post-D ~3112..~3149 worktree-side / ~3115..~3152 main HEAD.

### §0.8 BINDING semantics — PROVISIONAL/LIVE dynamic badge contract (§A.6; FIRST surface)

This is the **highest-Codex-density section** in Sub-bundle D. Plan §A.6 LOCK:

```python
# Plan §A.6 binding interface (Sub-bundle A SHIPPED)
def resolve_live_capital_denominator_dollars(
    conn: sqlite3.Connection, *, asof_date: date
) -> tuple[float, EquityBadge]:
    """Returns (denominator_dollars, badge).

    PROVISIONAL: no snapshot ≤ asof_date.
      denominator = read_live_policy(conn).capital_floor_constant_dollars.
      badge = PROVISIONAL.
    LIVE: snapshot exists ≤ asof_date.
      denominator = max(capital_floor_constant_dollars, snapshot.equity_dollars).
      badge = LIVE.
    """
```

**Sub-bundle D consumer pattern (T-D.1 capital-friction):**

```python
def compute_capital_friction(conn, *, asof_date: date) -> CapitalFrictionResult:
    denom, badge = resolve_live_capital_denominator_dollars(conn, asof_date=asof_date)
    utilization_pct = total_exposure_dollars / denom * 100.0
    portfolio_heat_pct = sum_per_position_heat_dollars / denom * 100.0
    return CapitalFrictionResult(
        current_capital_utilization_pct=utilization_pct,
        current_portfolio_heat_pct=portfolio_heat_pct,
        capital_denominator_badge=badge,  # PROVISIONAL or LIVE
        # ...
    )
```

**BINDING discriminating tests (per plan §G T-D.1 acceptance):**

1. **`test_compute_capital_friction_no_snapshot_returns_provisional_badge`:** empty `account_equity_snapshots` → all live-capital-dependent metrics carry PROVISIONAL badge; denominator = `capital_floor_constant_dollars` (production = $7500).
2. **`test_compute_capital_friction_with_snapshot_returns_live_badge`:** seed snapshot $2000 ≤ asof_date → badge = LIVE; denominator = `max($7500, $2000) = $7500` (production case at handoff time; floor wins because cash basis is below floor).
3. **§I.13 round-trip integration test:** in `tests/integration/test_phase10_bundle_d_e2e.py`, write snapshot via `record_snapshot_with_audit` at session N + immediately invoke `compute_capital_friction(conn, asof_date=N)` + assert LIVE badge returned (verifies write→read alignment of session anchor).

**Template rendering (T-D.2 BINDING):**

- PROVISIONAL badge MUST render as TEXT (per §A.6 + spec §4.9 + lesson #20). Recommended: `<span class="badge badge-provisional">PROVISIONAL</span>` with the class styled via existing dark-theme CSS variables.
- LIVE badge: `<span class="badge badge-live">LIVE</span>`.
- **NOT acceptable:** color-only badges (red dot vs green dot); icon-only badges (warning vs check); silent display without badge.
- **Discriminating template test (lesson #20):** seed snapshot present → assert response body contains `>LIVE<` (exact substring); seed snapshot absent → assert response body contains `>PROVISIONAL<` (exact substring). Body-wide `assert "LIVE" in body` is non-discriminating because the template may contain "alive" or "live data" elsewhere.

### §0.9 BINDING semantics — §A.19 `risk_feasibility_blocked_rate` set-membership guard

Plan §G T-D.1 mirrors the 9 discriminating tests verbatim from plan §A.19 (which absorbed Codex R1 M#1 + R2 M#3 + R3 M#3 + R4 M#1+M#2+M#3 from writing-plans). **This is the densest Codex-fix sequence in the plan.** All 9 tests are BINDING:

1. **`test_risk_feasibility_blocked_rate_uses_constant_not_string_literal`:** assert `from swing.evaluation.criteria.risk_feasibility import NAME` import is present in `swing/metrics/capital.py`. Avoid string-literal `'risk_feasibility'` everywhere; use the constant.
2. **`test_risk_feasibility_blocked_rate_excludes_candidates_failing_other_criteria`:** seed candidate failing risk_feasibility AND failing MA-stack → NOT in numerator; rate stays bounded.
3. **`test_risk_feasibility_blocked_rate_excludes_candidates_with_na_on_other_criteria`:** seed candidate with `result='na'` on a non-risk criterion → excluded from denominator.
4. **`test_risk_feasibility_blocked_rate_excludes_candidates_with_na_on_risk_feasibility`:** seed candidate with all-other-criteria=pass AND `risk_feasibility result='na'` → excluded from BOTH numerator AND denominator.
5. **`test_risk_feasibility_blocked_rate_excludes_candidates_with_partial_criteria_rows`:** seed candidate with only 3 of 18 `EXPECTED_CRITERIA_NAMES` rows → excluded from BOTH numerator AND denominator + WARNING log emitted naming candidate_id + missing_set.
6. **`test_risk_feasibility_blocked_rate_set_membership_guard_catches_missing_plus_extra`:** seed candidate with 18 criterion_results rows where 1 EXPECTED name is missing AND 1 UNKNOWN name is present (count matches expected = 18, but membership wrong) → excluded + WARNING log. **Discriminates set-membership guard against count-only guard** (count-only guard would let this through).
7. **`test_risk_feasibility_blocked_rate_extra_names_logs_info_not_excluded`:** seed candidate with all 18 expected names + 1 extra unknown name → INCLUDED in computation + INFO log emitted (extras are informational, not exclusion-triggering).
8. **`test_risk_feasibility_blocked_rate_expected_criteria_names_set_matches_pipeline_writer`:** assert `EXPECTED_CRITERIA_NAMES` set matches names actually written by `_step_evaluate` for a synthetic candidate. **Discriminates against `*.NAME`-only undercount** (every criterion module needs to be enumerated; pinning prevents drift).
9. **`test_risk_feasibility_blocked_rate_at_most_1`** + **`test_risk_feasibility_blocked_rate_at_zero_qualifying_returns_suppressed`:** rate bounded to [0, 1]; zero would-have-qualified → suppressed text `"N/A — 0 would-have-qualified candidates this run"` per §A.19.

**Implementer MUST pin all 9 tests in `tests/metrics/test_capital.py` per plan §G T-D.1 acceptance.** Codex will check.

### §0.10 BINDING semantics — §A.0.1 historical-reconstruction disclosure footnote

Plan §A.0.1 (Codex R2 Major #4 from writing-plans): historical multi-run trends are best-effort against CURRENT trade state (true reconstruction via per-run snapshot table OR replay deferred to V2; disclosure footnote required).

**Two surfaces require the footnote (plan §G T-D.2 + T-D.6):**

1. CapitalFrictionVM trend section.
2. IdentificationFunnelVM trend section.

**Verbatim footnote text (BINDING; same across both surfaces):**

> "Trend computed from current trade state; historical points approximate where state has changed since the run."

**Discriminating tests (BINDING per plan §G T-D.2 + T-D.6):**

- `test_capital_friction_renders_historical_disclosure_footnote_in_trend_section`: assert response body contains the EXACT footnote substring.
- `test_identification_funnel_renders_historical_disclosure_footnote_in_trend_section`: same.
- **Both tests apply lesson #20 (exact substring per worked example):** assert the exact footnote at the trend-section cell location, NOT body-wide.

### §0.11 BINDING semantics — §A.20 zero-A+ run suppression

Plan §A.20: when a pipeline_run has zero A+ identifications, `aplus_take_rate_per_run` is suppressed with text `"N/A — 0 A+ identifications this run"` (NOT NaN, NOT division-by-zero).

**Discriminating test (BINDING per plan §G T-D.5):**

- `test_compute_funnel_zero_aplus_identifications_returns_suppressed_take_rate`: seed pipeline_run with 0 A+ identifications + N≥1 trades_taken → take_rate = suppressed text; numeric field is None or sentinel.
- Template rendering: VM passes suppressed text to template; template renders verbatim; NO NaN, NO `0.0`, NO `inf`.

### §0.12 BINDING semantics — §A.15 session-anchor LOCK + §I.13 round-trip

Plan §A.15 + §I.13 LOCK: every session-keyed read predicate must align with its writer.

**Sub-bundle D session-anchor matrix:**

| Surface | Read predicate | Writer | Direction |
|---|---|---|---|
| Capital-friction asof_date | `last_completed_session(now)` | `account_equity_snapshots.snapshot_date` (backward-looking per Phase 9 Sub-bundle C) | Backward-looking — ALIGNED |
| Funnel trend window | 30 sessions ending at `last_completed_session(now)` | `pipeline_runs.started_ts.date()` (event timestamp) | Backward-looking — ALIGNED |
| Maturity-stage current snapshot | `daily_management_records.review_date` latest active | `last_completed_session(now)` (Phase 8 server-stamp at handler entry) | Backward-looking — ALIGNED |

**§I.13 round-trip integration test (BINDING in T-D.7 + plan §G T-D.1 watch items):**

```python
# tests/integration/test_phase10_bundle_d_e2e.py
def test_capital_friction_provisional_to_live_flip_on_snapshot_record(tmp_path, monkeypatch):
    # ... seed empty account_equity_snapshots
    result_before = compute_capital_friction(conn, asof_date=session_N)
    assert result_before.capital_denominator_badge == EquityBadge.PROVISIONAL
    record_snapshot_with_audit(conn, equity_dollars=2000.0, snapshot_date=session_N, ...)
    result_after = compute_capital_friction(conn, asof_date=session_N)
    assert result_after.capital_denominator_badge == EquityBadge.LIVE
```

**Forward-binding lesson family (see CLAUDE.md gotcha "Session-anchor read/write mismatch"):** if implementer is tempted to use forward-looking `action_session_for_run(now)` for trend window or asof_date, REJECT — that creates the read/write anchor mismatch family (weather lookup + Phase 8 daily-management badge + others).

### §0.13 BINDING semantics — 30-trading-day window off-by-one defense

Plan §G T-D.5 (Codex R4 Minor #2 + R5 Minor #1 + R6 Minor #1 list-mirror): the trend WINDOW spans the LAST 30 NYSE TRADING SESSIONS ending at `end = last_completed_session(datetime.now())` (inclusive of `end`; backward-looking per §A.15).

**Window derivation (BINDING per plan):**

```python
import exchange_calendars
import pandas as pd
from swing.evaluation import last_completed_session

cal = exchange_calendars.get_calendar('XNYS')
end = last_completed_session(datetime.now())  # date
# Walk BACKWARD from `end` collecting up to 30 sessions inclusive of `end`.
# Use sessions_window(pd.Timestamp(end), -30):
sessions = cal.sessions_window(pd.Timestamp(end), -30)
TRADING_DAYS_WINDOW = 30
```

**Per-run aggregation:** `pipeline_runs.started_ts.date()` matched against the session list; runs whose `started_ts.date()` falls outside the 30-session window are excluded.

**Discriminating test (BINDING per plan §G T-D.5):**

- `test_funnel_trend_30_sessions_inclusive_of_end`: seed 31 sessions of runs ending at `last_completed_session(now)` + assert the trend window contains only the most-recent 30 sessions (off-by-one defense; 31st session is excluded).

**REJECTED alternatives:**
- Using forward-looking `action_session_for_run(now)` for the trend window — shifts boundary on session transition + creates read/write anchor mismatch (§A.15 binding violation).
- Using `date.today()` for the trend window — ignores HST/ET lag; locally midnight does NOT equal session transition.
- Using count of `pipeline_runs` rows (not session-windowed) for the trend — drift on holiday/weekend gaps.

---

## §1 Worktree + binding conventions

### §1.1 Worktree
- **Branch:** `phase10-bundle-D-capital-maturity-funnel`
- **Worktree directory:** `.worktrees/phase10-bundle-D-capital-maturity-funnel/`
- **BASELINE_SHA:** `3af36d0` (current main HEAD; post-Sub-bundle-C-ship housekeeping).
- **Worktree branching point:** current HEAD of `main` at worktree-creation time (resolve via `git rev-parse main`; expected the dispatch-brief commit SHA after this brief lands).

### §1.2 Marker-file workflow
- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all task commits land + Codex chain converges + before final return-report commit: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits
- Conventional prefixes per plan §G suggested commit shapes (`feat(metrics): ...`, `test(metrics): ...`, `feat(web): ...`, `chore(metrics): ...`).
- One commit per task; Codex-fix commits as `fix(phase10-bundle-D): Codex RN <severity> #N — <description>`.
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.

### §1.4 Branch isolation + ownership
- Commits on branch only; no push to origin from worktree.
- **Implementer (you) owns:** copowers:executing-plans invocation → task-by-task TDD → Codex iteration → return-report commit.
- **Orchestrator owns:** plan-triage at dispatch time + integration merge to main + Sub-bundle E dispatch commissioning post-D-ship.

### §1.5 Verify command
```powershell
# After all tasks land + Codex chain converges:
git log --oneline HEAD~12..HEAD
python -m pytest -m "not slow" -q
ruff check swing/ --statistics
python verify_phase10.py
```

---

## §2 Operator-witnessed verification gate (Sub-bundle D)

Per plan §G + §I.15 BINDING:

| # | Surface | Type | Acceptance |
|---|---|---|---|
| **S1** | pytest fast-suite + ruff + verify_phase10 | Inline | `python -m pytest -m "not slow" -q` GREEN at ~3112..~3149 fast tests (worktree-side); 3 pre-existing `test_phase8_pipeline_walkthrough.py` failures unchanged; `ruff check swing/` baseline 18; `python verify_phase10.py` exits 0. **Expect ~5-6 min wall-clock** at projected test count. |
| **S2** | `/metrics/capital-friction` (PROVISIONAL phase) | **Browser (operator-witnessed via Chrome MCP on port 8081)** | Initial state with **no fresh snapshot for `last_completed_session(now)`** → confirm: (a) page renders 200; (b) all live-capital-dependent gauges show PROVISIONAL badge text per §A.6 LOCK; (c) `risk_feasibility_blocked_rate` renders per §A.19; (d) multi-run trend suppressed at <5 runs OR rendered with §A.0.1 historical-disclosure footnote text VERBATIM; (e) base-layout integration intact (nav, session_date, discrepancy badge); (f) no console errors. |
| **S3** | `/metrics/maturity-stage` | **Browser (operator-witnessed via Chrome MCP)** | `http://127.0.0.1:8081/metrics/maturity-stage` → confirm: (a) page renders 200; (b) **5 open positions (DHC/YOU/VSAT/CVGI/LAR) appear as per-position rows** sorted by maturity_stage; (c) NULL Phase-8-capture-need columns render `"—"` placeholder NOT "[Phase 8 capture pending]"; (d) aggregate count by stage row present; (e) base-layout integration intact; (f) no console errors. |
| **S4** | `/metrics/identification-funnel` | **Browser (operator-witnessed via Chrome MCP)** | `http://127.0.0.1:8081/metrics/identification-funnel` → confirm: (a) page renders 200; (b) per-run stacked bars render for recent pipeline_runs; (c) 30-trading-session trend renders (production has 60+ runs across many sessions; well above 10-run threshold); (d) §A.0.1 historical-disclosure footnote VERBATIM in trend section; (e) `aplus_take_rate_per_run` shows §A.20 suppressed text for runs with 0 A+ identifications (if any); (f) NO `watch_take_rate_per_run` rendered per spec §3.6 R1 M2 LOCK (V1 surfaces watch counts ONLY); (g) base-layout integration intact; (h) no console errors. |
| **S5** | PROVISIONAL → LIVE round-trip | **Browser + CLI (operator-witnessed via Chrome MCP + production-write classifier)** | (a) Operator records fresh snapshot via `swing account snapshot record --equity-dollars <value> --note "S5 gate test"` (or orchestrator drives via plain-chat operator authorization per durable preference); (b) reload `/metrics/capital-friction` → confirm badge FLIPS to LIVE per §I.13 round-trip BINDING; (c) verify `denominator = max($7500, snapshot.equity_dollars)` math correct in rendered gauge; (d) optional: revert snapshot OR leave for production state (orchestrator-decision at gate time). **Production-write classifier may soft-block on the snapshot record CLI** — surface to operator for plain-chat "yes" confirmation per durable preference. |

**Gate session ≤ 6 surfaces budget (dispatch brief §1.3):** Sub-bundle D has **5 surfaces** — 1 inline + 4 browser-driven (S2 + S3 + S4 + S5 with S5 being a write+reload exercise). Under the 6-surface budget.

**Chrome MCP availability:** orchestrator drives S2 + S3 + S4 + S5 via Chrome MCP `mcp__claude-in-chrome__*` tools at gate time (Sub-bundle A + B + C precedent). Load tools via `ToolSearch` with `select:mcp__claude-in-chrome__<tool_name>` before invoking. **Use port 8081** to avoid collision with operator's main-HEAD `swing web` session on 8080 (when running).

---

## §3 Skill posture + adversarial review

- **Invoke `copowers:executing-plans`** (NOT `superpowers:executing-plans` or `superpowers:subagent-driven-development` directly — the copowers wrapper handles Codex review automatically after task commits land).
- Skill inputs:
  - `PLAN_PATH=docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`
  - `AMENDMENT_PATH=docs/phase10-electives-amendment.md`
  - `SUB_BUNDLE=D` (Tasks T-D.0..T-D.7; NO electives in D scope)
  - `BASELINE_SHA=3af36d0`
- **Expected Codex chain:** 3-5 rounds (Sub-bundle A: 4 rounds; B: 2; C: 2; Phase 9 D had Critical findings → 4 rounds). Sub-bundle D introduces highest Codex-value-add density of Phase 10 (PROVISIONAL/LIVE dynamic + §A.19 set-membership + §A.0.1 disclosure + 30-day window); expect upper end of estimate.
- Iterate per-round fixes as `fix(phase10-bundle-D): Codex RN <severity> #N — ...` commits.
- Terminate at NO_NEW_CRITICAL_MAJOR.

### §3.1 Codex value-add concentration

Adversarial review for Sub-bundle D typically catches:

- **PROVISIONAL/LIVE badge drift** — Codex will check `resolve_live_capital_denominator_dollars` returns badge correctly for both PROVISIONAL (no snapshot) and LIVE (snapshot ≤ asof_date) paths; will check capital-friction template renders the badge as TEXT not color-only. Pre-empt with §0.8 discriminating tests.
- **§A.19 set-membership guard violations** — Codex will check the 9 discriminating tests are present + asserting correct semantics. Pre-empt with §0.9 verbatim test list.
- **§A.19 EXPECTED_CRITERIA_NAMES drift** — Codex will check `EXPECTED_CRITERIA_NAMES` set matches names actually written by `_step_evaluate` (T-D.0 recon + T-D.1 test). Pre-empt with `test_risk_feasibility_blocked_rate_expected_criteria_names_set_matches_pipeline_writer`.
- **§A.0.1 historical-disclosure footnote missing OR text drift** — Codex will check the exact footnote text appears in both capital-friction + funnel trend sections. Pre-empt with §0.10 discriminating tests asserting exact substring.
- **§A.20 zero-A+ suppression drift** — Codex will check `aplus_take_rate_per_run` returns suppressed text NOT NaN/inf when 0 A+ identifications. Pre-empt with §0.11 test.
- **§A.15 session-anchor read/write misalignment** — Codex will check capital-friction asof_date uses backward-looking `last_completed_session(now)` NOT forward-looking `action_session_for_run(now)`; same for funnel trend window. Pre-empt with §0.12 round-trip test.
- **30-trading-day window off-by-one** — Codex will check window derivation via `exchange_calendars.sessions_window(pd.Timestamp(end), -30)` matches the inclusive-of-end semantics + discriminating test seeds 31 sessions + asserts only 30 in trend. Pre-empt with §0.13 test.
- **Phase 8 capture-need NULL rendering drift** — Codex will check maturity-stage template renders `"—"` placeholder for NULL `trail_MA_candidate_price` / `planned_target_R` (NOT "[Phase 8 capture pending]"). Pre-empt with `test_compute_maturity_stage_handles_null_*` tests.
- **`watch_take_rate_per_run` accidental introduction** — Codex will check funnel result does NOT include this field (spec §3.6 R1 Minor #2 LOCK; NO derived watch take-rate in V1). Pre-empt with explicit test asserting field absent.
- **PROVISIONAL/LIVE badge text-vs-color drift** — Codex will check template uses TEXT badges per §A.6 + spec §4.9 (NOT color-only; NOT icon-only). Pre-empt with template rendering tests.
- **BaseLayoutVM field population** — Codex will check all 3 new VMs populate `unresolved_material_discrepancies_count` via `count_unresolved_material(conn)` per §A.18 cross-bundle pin.
- **`__post_init__` validators on new dataclasses** (lesson #1) — Codex will check `CapitalFrictionResult`, `MaturityStageResult`, `IdentificationFunnelResult`, all VMs, sub-VMs have NaN/inf rejection + invariant assertions.
- **Historical multi-run trend uses CURRENT trade state** (§A.0.1 + Codex R2 M#4) — Codex will check capital-friction + funnel trend computations query CURRENT trade state (not reconstruct from historical snapshots). Pre-empt with `test_compute_capital_friction_historical_trend_uses_current_trade_state` + `test_historical_funnel_uses_current_trade_state`.
- **`concurrent_open_positions` historical-run filter** (§A.0.1 + Codex R3 M#2) — Codex will check `concurrent_open_positions` at historical run uses `open_at_pre_trade_locked_at_only` filter (NOT subsequent state). Pre-empt with `test_concurrent_open_positions_at_historical_run_uses_open_at_pre_trade_locked_at_only`.
- **§A.9 + §I.6 LOCK: pure server-rendered HTML** — Codex will check all 3 new surfaces are server-rendered ONLY; no HTMX OOB-swap, no embedded forms, no HX-Redirect.

### §3.2 Per-task Codex-check pre-emption

| Task | Common Codex finding | Pre-emption |
|---|---|---|
| T-D.0 | None expected (pure recon) | Document Phase 9 + Phase 8 helper signatures + `risk_feasibility.NAME` constant + EXPECTED_CRITERIA_NAMES set matching `_step_evaluate` writer in PR description / recon note |
| T-D.1 | `risk_feasibility_blocked_rate` uses string literal | Use `from swing.evaluation.criteria.risk_feasibility import NAME` constant per §A.19 |
| T-D.1 | Set-membership guard missing or count-only | 9 §A.19 discriminating tests BINDING per §0.9 |
| T-D.1 | PROVISIONAL badge not surfaced per-metric | Each live-capital-dependent metric carries badge field; template renders per-metric |
| T-D.1 | Historical multi-run trend reconstructs state | Use CURRENT trade state per §A.0.1 + Codex R2 M#4 |
| T-D.2 | Historical-disclosure footnote missing | EXACT verbatim text per §0.10 LOCK |
| T-D.2 | PROVISIONAL badge color-only | TEXT badges per §A.6 + spec §4.9 |
| T-D.3 | NULL Phase-8-capture-need cells render "[Phase 8 capture pending]" | Render `"—"` placeholder per spec §3.5 R1 M5 + §6.1 |
| T-D.3 | `trail_MA_eligibility_flag` returns False on NULL `trail_MA_candidate_price` | Return None (NOT False) per plan §G T-D.3 discriminating test |
| T-D.4 | Empty-state placeholder missing | Render `"No open positions to manage."` per spec §4.5 |
| T-D.5 | `watch_take_rate_per_run` introduced | Spec §3.6 R1 Minor #2 LOCK; NO watch take-rate in V1 |
| T-D.5 | 30-day window uses calendar days NOT trading sessions | Use `exchange_calendars.sessions_window` per §0.13 |
| T-D.5 | Window off-by-one | Discriminating test seeds 31 sessions + asserts 30 in trend |
| T-D.5 | Forward-looking session anchor used for window | Use backward-looking `last_completed_session(now)` per §A.15 |
| T-D.5 | Zero-A+ run NaN | Use §A.20 suppressed text |
| T-D.6 | Historical-disclosure footnote missing | EXACT verbatim text per §0.10 LOCK (same as capital-friction) |
| T-D.7 | E2E test seeds insufficient diversity | Seed snapshot + open positions across stages + multiple pipeline_runs covering 30+ sessions to exercise full trend rendering |

---

## §4 Return report shape

After all task commits land + Codex chain converges + before final return-report commit, draft a return report at `docs/phase10-bundle-D-return-report.md` (mirroring `docs/phase10-bundle-C-return-report.md` shape):

1. Final HEAD on branch + commit count breakdown (task-impl + Codex-fix; expected ~8 task-impl + 3-5 Codex-fix + 1 return-report).
2. Codex round chain (e.g., "R1 0/X/Y → R2 ... → Rn NO_NEW_CRITICAL_MAJOR").
3. Test count delta + ruff baseline delta.
4. Operator-witnessed verification surfaces (PENDING orchestrator-driven gate; S1 inline OK; S2+S3+S4+S5 PENDING).
5. Per-task deviations from the plan (if any) with rationale; any spec-amendment candidates banked.
6. Codex Major findings ACCEPTED with rationale (if any).
7. Watch items for orchestrator (cross-bundle pins; un-skip-at-T-E.3 reminder; any V2 candidates banked; production snapshot state post-gate).
8. Worktree teardown status (expected ACL-locked husk; 6th in cleanup-script queue pending the `-DeregisterFirst` extension).
9. Sub-bundle E forward-binding lessons (if any new ones surfaced during executing-plans — likely PROVISIONAL/LIVE dynamic-contract testing patterns + 30-trading-day window discipline).
10. Composition-surface verification via `^def` grep (per Phase 9 + Sub-bundle A forward-binding lesson #5).
11. Any plan-text amendments applied in-tree during Codex rounds (mirror Sub-bundle A §A.7 + §D Task A.1 amendments pattern).

---

## §5 First-step paste-ready prompt for the implementer

```
You are taking over to implement Phase 10 Sub-bundle D (Capital-friction view + Maturity-stage view + Identification-vs-trade-funnel view) for swing-trading. FIRST PROVISIONAL/LIVE dynamic badge contract dispatch.

WORKING DIRECTORY (after worktree creation): c:\Users\rwsmy\swing-trading\.worktrees\phase10-bundle-D-capital-maturity-funnel
BRANCH: phase10-bundle-D-capital-maturity-funnel
BASELINE_SHA: 3af36d0  (per dispatch brief §1.1; HEAD of main BEFORE this brief commit)
WORKTREE-BRANCHING-POINT: current HEAD of main at worktree-creation time (resolve via `git rev-parse main`)

Step 0 — Create the worktree:
  cd c:\Users\rwsmy\swing-trading
  $base = git rev-parse main
  git worktree add .worktrees\phase10-bundle-D-capital-maturity-funnel -b phase10-bundle-D-capital-maturity-funnel $base
  New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active

Step 1 — Read the dispatch brief end-to-end from the worktree:
  docs/phase10-bundle-D-executing-plans-dispatch-brief.md

Step 2 — Read the Phase 10 plan §G + cross-bundle invariants §I:
  docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md  (§G lines 1354-1550 for tasks T-D.0..T-D.7; §I lines 1665-1744 for invariants; §A.0 + §A.0.1 + §A.5 + §A.6 + §A.7 + §A.15 + §A.18 + §A.19 + §A.20 + §A.21 for AMENDED interface contracts + dynamic PROVISIONAL/LIVE contract + historical disclosure + risk_feasibility SQL)

Step 3 — Read the Phase 10 brainstorm spec:
  docs/superpowers/specs/2026-05-06-phase10-metrics-design.md  (§3.4 capital-friction + §3.5 maturity-stage + §3.6 identification-funnel + §4.4 + §4.5 + §4.6 surfaces + §5 honesty policy + §6.1 Phase 8 capture-need NULL rendering; §3.6 R1 Minor #2 watch_take_rate LOCK)

Step 4 — Read binding conventions + forward-binding lessons:
  - CLAUDE.md (gotchas + project conventions; "Session-anchor read/write mismatch" gotcha family is HIGHLY APPLICABLE)
  - docs/orchestrator-context.md (orchestrator-role framing; Codex-driven discipline)
  - docs/phase10-bundle-A-return-report.md §10 (forward-binding lessons binding)
  - docs/phase10-bundle-B-return-report.md §5 + §8 (deviations + forward-binding lessons binding)
  - docs/phase10-bundle-C-return-report.md §5 + §9 (deviations + lessons #20-#22 forward-binding)

Step 5 — Verify worktree state:
  git rev-parse HEAD                       # expect current main HEAD (typically the dispatch brief commit)
  git status                               # expect clean
  python -m pytest -m "not slow" -q        # expect baseline GREEN (~3045 passed worktree-side; 6 skipped; 3 pre-existing fails NOT regressions). ~5:15 wall-clock.
  python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"  # expect 17
  ruff check swing/ --statistics            # expect 18 E501
  python verify_phase10.py                  # expect exit 0

Step 6 — Pre-implementation recon (Sub-bundle A + B + C interface + Phase 8 + Phase 9 helper verification):
  grep -rn "^def " swing/metrics/honesty.py swing/metrics/policy.py swing/metrics/cohort.py swing/metrics/discrepancies.py swing/metrics/process.py swing/metrics/tier.py swing/metrics/equity_resolver.py
  python -c "from swing.metrics.honesty import wilson_ci, bootstrap_ci_mean, suppress_for_n, badges_for_n, render_class_a, render_class_b, render_class_c, render_class_d; from swing.metrics.policy import read_live_policy, get_trade_policy_id_stamp; from swing.metrics.cohort import list_trades_for_cohort, count_per_cohort; from swing.metrics.discrepancies import count_unresolved_material; from swing.metrics.equity_resolver import resolve_live_capital_denominator_dollars; print('Sub-bundle A + B + C interface intact + equity_resolver shipped')"
  grep -rn "^def " swing/data/repos/account_equity_snapshots.py
  grep -n "get_latest_snapshot_on_or_before\|get_active_policy" swing/data/repos/
  grep -n "^NAME\|^def " swing/evaluation/criteria/risk_feasibility.py  # T-D.0 recon: confirm NAME constant
  grep -rn "^def " swing/data/repos/daily_management.py | grep -i list_open_position  # T-D.3 recon: Phase 8 helper
  swing account snapshot list  # T-D.0 recon: enumerate production snapshots
  grep -n "_SUB_VM_EXCLUSIONS" tests/web/test_view_models/test_base_layout_vm_coverage.py  # T-D.2 + T-D.4 + T-D.6 sub-VM exclusion-set update lands SAME commit

Step 7 — Invoke copowers:executing-plans:
  - PLAN_PATH: docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md
  - AMENDMENT_PATH: docs/phase10-electives-amendment.md
  - SUB_BUNDLE: D
  - BASELINE_SHA: 3af36d0

Step 8 — Execute tasks task-by-task per plan §G:
  - T-D.0 recon (no commit; document inline in PR description / return-report; capture Phase 8/9 helper signatures + risk_feasibility.NAME constant + EXPECTED_CRITERIA_NAMES set verbatim)
  - T-D.1 §3.4 capital-friction computations (commit: feat(metrics): §3.4 capital-friction computations + dynamic PROVISIONAL contract (T-D.1))
  - T-D.2 CapitalFrictionVM + route + template (commit: feat(metrics): capital-friction VM + route + template (T-D.2))
  - T-D.3 §3.5 maturity-stage computations (commit: feat(metrics): §3.5 maturity-stage computations (T-D.3))
  - T-D.4 MaturityStageVM + route + template (commit: feat(metrics): maturity-stage VM + route + template (T-D.4))
  - T-D.5 §3.6 identification-funnel computations (commit: feat(metrics): §3.6 identification-vs-trade-funnel computations (T-D.5))
  - T-D.6 IdentificationFunnelVM + route + template (commit: feat(metrics): identification-funnel VM + route + template (T-D.6))
  - T-D.7 integration sweep (commit: chore(metrics): Sub-bundle D integration sweep (T-D.7))

Step 9 — Iterate Codex rounds + land per-round-fix commits until NO_NEW_CRITICAL_MAJOR. Expected 3-5 rounds.

Step 10 — Draft return report at docs/phase10-bundle-D-return-report.md per dispatch brief §4. Commit it.

Step 11 — Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active + signal orchestrator. Orchestrator drives operator-witnessed gate (S2 + S3 + S4 + S5 browser surfaces via Chrome MCP on port 8081 if available; S5 requires production snapshot record — orchestrator drives via plain-chat operator authorization) + integration merge.

DO NOT:
  - Push to origin from inside the worktree
  - Merge to main (orchestrator action)
  - Use --amend or --no-verify
  - Add Claude co-author footer to commits
  - Skip the marker-file removal before final signal
  - Skip the Step 6 pre-implementation recon (Phase 8 + Phase 9 + Sub-bundle A/B/C interface + risk_feasibility.NAME verification)
  - Add ANY new schema (no `0018_*.sql` migration; no ALTER on existing tables); Phase 10 V1 §A.0 LOCK is BINDING per plan §I.1
  - Skip `__post_init__` validators on any new dataclass (Phase 9 + Sub-bundle A forward-binding lesson #1)
  - Use string literal 'risk_feasibility' instead of `from swing.evaluation.criteria.risk_feasibility import NAME` constant per §A.19
  - Skip the 9 §A.19 discriminating tests (BINDING per plan §G T-D.1 + dispatch brief §0.9)
  - Render PROVISIONAL/LIVE badge as color-only or icon-only (TEXT BINDING per §A.6 + spec §4.9 + forward-binding lesson #20)
  - Use historical reconstruction for multi-run trends (§A.0.1 LOCK: best-effort against CURRENT trade state; disclosure footnote required)
  - Skip the §A.0.1 historical-disclosure footnote on capital-friction + identification-funnel trend sections (EXACT verbatim text per dispatch brief §0.10)
  - Render `aplus_take_rate_per_run` as NaN / inf / 0.0 on zero-A+ runs (§A.20 suppressed text BINDING)
  - Introduce `watch_take_rate_per_run` field (spec §3.6 R1 Minor #2 LOCK; NO derived watch take-rate in V1)
  - Use forward-looking `action_session_for_run(now)` for capital-friction asof_date OR funnel trend window (§A.15 LOCK: backward-looking `last_completed_session(now)`)
  - Use calendar days OR `pipeline_runs` row count for funnel trend window (BINDING: `exchange_calendars.sessions_window(pd.Timestamp(end), -30)` per dispatch brief §0.13)
  - Render NULL `trail_MA_candidate_price` / `planned_target_R` as "[Phase 8 capture pending]" (Phase 8 IS shipped; NULL renders `"—"` placeholder per spec §3.5 R1 M5 + §6.1)
  - Un-skip `test_existing_dashboard_vm_has_unresolved_material_field` (that's Task E.3's responsibility per §I.5)
  - Add HTMX OOB-swap, embedded forms, hx-headers, or HX-Redirect on /metrics/capital-friction OR /metrics/maturity-stage OR /metrics/identification-funnel (§A.9 + §I.6 LOCK pure server-render)
  - Add chart rendering via matplotlib (§A.10 V1 LOCK = inline SVG in Sub-bundle E only)
  - Implement per-surface routes other than /metrics/capital-friction + /metrics/maturity-stage + /metrics/identification-funnel (process-grade-trend + reconciliation banner land in E per plan §A.3)
  - Implement Sub-bundle E task scope (out of D's lane)
  - Implement T-E.5 (web-form snapshot capture) / T-E.6 (per-trade discrepancy indicator) (those land in E per electives amendment)
  - Implement §8.4 Corporate_Actions MVP (deferred as standalone post-Phase-10 dispatch per electives amendment §5)
  - Bundle this with Sub-bundle E (sequencing locked A ✓ → B ✓ → C ✓ → D → E per plan §C)
  - Add color-only badges (spec §4.9 BINDING; reliability + PROVISIONAL/LIVE flags as TEXT not color-only)
  - Diverge from per-metric class matrix in plan §G Task D.1/D.3/D.5 acceptance (Codex will check)
  - Forget to update `_SUB_VM_EXCLUSIONS` in `tests/web/test_view_models/test_base_layout_vm_coverage.py` when introducing new sub-VMs (must land in SAME COMMIT as the sub-VM)
```

---

## §6 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-13 (post-Sub-bundle-C-ship).
- **Brief commit:** `<filled-in-after-commit>`.
- **Brief HEAD context:** `3af36d0` on main (post-Sub-bundle-C-ship housekeeping).
- **Worktree path (binding):** `.worktrees/phase10-bundle-D-capital-maturity-funnel/`.
- **Baseline test count (main HEAD):** ~3048 fast (2 skipped). Worktree-side: ~3045 fast (6 skipped — 4 `thinkorswim/*.csv` fixture-absent + 1 cross-bundle T-A.7 pin + 1 Task 7.3 operator-only).
- **Baseline ruff count:** 18 (E501 only).
- **Plan status:** Codex R1-R6 NO_NEW_CRITICAL_MAJOR; AMENDED in-tree during Sub-bundle A R2 + R3; LOCKED.
- **Electives amendment status:** ZERO impact on Sub-bundle D (no electives in D scope).
- **Spec status:** Codex R1-R5 substantive + R6 confirmation; shipped 2026-05-06 at `fe6cb45`; 641 lines; LOCKED.
- **Expected dispatch wall-clock:** ~10-14 hr executing-plans + ~3-5 hr Codex convergence (largest of Phase 10 — 8 tasks + densest Codex-value-add).
- **Expected test count delta:** +67..+104 fast tests; post-D ~3112..~3149 worktree-side / ~3115..~3152 main HEAD (matches Sub-bundle A + B + C overshoot precedent; expect upper end).
- **Expected ruff delta:** 0 (baseline preserved).
- **Test runtime concern:** S1 inline gate ~5-6 min wall-clock at projected test count; **deferred** xdist + fixture-scope refactor per phase3e-todo 2026-05-13 post-Phase-10 backlog. Sub-bundle D inherits current test-runner setup.
- **Next per locked sequencing 8 ✓ → 9 ✓ → 10 (A ✓ → B ✓ → C ✓ → D → E):** Sub-bundle D ships → orchestrator drives operator-witnessed gate (5 surfaces) → integration merge → orchestrator queues Sub-bundle E dispatch brief drafting (process-grade-trend chart + reconciliation banner + Phase 11 hand-off + 3 elective tasks T-E.5 + T-E.6 + cross-bundle pin un-skip at T-E.3).

---

## §7 Watch items for orchestrator (post-Sub-bundle-D-ship)

1. **Operator-witnessed gates S2 + S3 + S4 + S5** — 4 browser-side checks (orchestrator-driven via Chrome MCP on port 8081). S5 requires production snapshot record (write action; surface to operator for plain-chat "yes" if production-write classifier soft-blocks).

2. **Cross-bundle pin at T-A.7 (still SKIPPED)** — Sub-bundle D does NOT touch the skip. Un-skip lands at T-E.3.

3. **Sub-VM exclusion-set propagation** — Sub-bundle D may add new sub-VMs (e.g., `ProvisionalBadgeVM` if not already in `_SUB_VM_EXCLUSIONS`; `MaturityRowVM`; `FunnelBarVM`). Verify exclusion-set update lands SAME COMMIT as sub-VM introduction.

4. **Spec amendment candidates banked** — Sub-bundle D may surface additional plan-text divergences. Cumulative pending V2.1 §VII.F amendments stands at **17** entering Sub-bundle D; expect 0-5 new from D.

5. **§A.6 PROVISIONAL/LIVE FIRST surface** — Sub-bundle D is the first to render the dynamic badge. Sub-bundle E (process-grade-trend) does NOT reuse the dynamic badge (its data-source is per-run + per-trade aggregates, not capital-snapshot-dependent). The contract is one-off for Sub-bundle D + Sub-bundle E inherits no PROVISIONAL/LIVE rendering.

6. **§A.0.1 historical-disclosure footnote** — landed in 2 surfaces (capital-friction trend + funnel trend). Sub-bundle E (process-grade-trend) MAY need the same footnote if its multi-run aggregation also reconstructs from current trade state; verify at Sub-bundle E dispatch brief drafting time.

7. **`verify_phase10.py` may need extension** — Sub-bundle D's T-D.7 may extend with capital-friction + maturity-stage + funnel route registration assertions. Banked as orchestrator-decision for Sub-bundle D return-report.

8. **Test count overshoot precedent** — Sub-bundle A projection +35..+55 actual +128; B projection +46..+75 actual +73; C projection +34..+56 actual +84. Sub-bundle D projection +67..+104; expect upper end. Operator should not be alarmed if S1 test count is higher than projection.

9. **Worktree husk** — Sub-bundle D teardown expected to leave ACL-locked husk; 6th in cleanup-script queue (after 4 Phase 9 husks + Sub-bundle C husk). Cleanup-script `-DeregisterFirst` extension is deferred post-Phase-10 per phase3e-todo 2026-05-13 entry.

10. **Sub-bundle E dispatch dependencies** — post-Sub-bundle-D-ship the next brief drafts Sub-bundle E (Tasks T-E.0..T-E.3 per plan §H + T-E.5 + T-E.6 + T-E.4 closer per electives amendment §2 + §3). Sub-bundle E closes Phase 10. Cross-bundle pin un-skip at T-E.3 retrofit of 6 existing base-layout VMs.

11. **Production snapshot state post-S5** — orchestrator-decision at gate time: leave fresh snapshot in production (operator's actual equity reading) OR revert. Default: leave (operator can update via CLI any time).

---

## §8 Dispatch order — UNCHANGED

A ✓ → B ✓ → C ✓ → D (this dispatch) → E. Sub-bundles A + B + C are SHIPPED; Sub-bundle D is the next dispatch. Post-Sub-bundle-D-ship → Sub-bundle E (process-grade-trend chart + reconciliation banner + Phase 11 hand-off + 3 elective tasks; CLOSES Phase 10).

---

*End of dispatch brief. Sub-bundle D is the densest Phase 10 dispatch — 3 new operator-visible surfaces (§4.4 + §4.5 + §4.6) + first PROVISIONAL/LIVE dynamic badge contract + §A.0.1 historical-disclosure footnote (2 trend sections) + §A.19 risk_feasibility_blocked_rate with 9-test set-membership guard mirror + 30-trading-day window off-by-one defense. All 8 tasks use AMENDED Sub-bundle A interfaces + Sub-bundle B + C implementation conventions; ZERO new schema; ZERO new write paths (read-only V1; S5 round-trip uses existing Phase 9 Sub-bundle C `swing account snapshot record` CLI); 4 browser surfaces + 1 inline + 1 round-trip = 5 gate surfaces. Cross-bundle pin at T-A.7 stays SKIPPED for T-E.3.*
