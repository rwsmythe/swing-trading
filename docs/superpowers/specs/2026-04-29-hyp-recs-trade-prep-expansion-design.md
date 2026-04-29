# Phase 3e — Hyp-recs trade-prep expansion V1 (design)

**Baseline:** `main` at commit `4ba9c62` (hyp-recs trade-prep expansion brainstorming dispatch brief). Fast suite ~974 tests green as of 2026-04-25 (per CLAUDE.md Quick Start; exact count pinned at writing-plans dispatch per the project's standing test-count-drift discipline). schema_version = 12 (after 2026-04-29 sector/industry capture, migration 0012).

**Goal:** Convert the hyp-recs panel from a flat 7-column read-only table into a click-to-expand surface that shows the operator's full trade-preparation context for each recommendation: order parameters (buy stop = pivot, buy limit = pivot × (1 + chase_factor), sell stop = framework's initial stop), sizing in two complementary regimes (risk-based using the $7,500 floor, cash-feasible capped at the actual current balance), context (sector, industry), and an inline chart when in chart-scope. The expansion makes the operator's pure-trigger discipline ("price is inside the buy window?") an at-a-glance check rather than an ad-hoc external lookup. Bundles a small bug fix on the watchlist `Pivot` column (renders the frozen-at-add `entry_target` under a header that says `Pivot`; the fix renders `candidates.pivot` from the latest evaluation, matching what hyp-recs already does).

**Framing (binding, from `docs/orchestrator-context.md` 2026-04-25):** *"Dashboard PROPOSES, operator DISPOSES."* The expansion adds DECISION-RELEVANT context to the proposal surface; it does NOT add new automation, does NOT change which rows surface as recommendations, and does NOT introduce a new entry-execution path. The operator continues to disposition each row manually through the existing entry surface.

---

## 1. Background & scope

### 1.1 Locked constraints (operator-set 2026-04-28; NOT re-litigated)

These are the six pre-locked decisions from the dispatch brief §2. Every spec section below is consistent with them — any apparent tension is flagged and resolved at the spec level rather than re-opening the lock.

1. **Chase factor = 1% in V1, but configurable.** A new `Config.web.chase_factor: float = 0.01` field. The 1% comes from the recorded entry-discipline framing (2026-04-25 "wait for pivot, don't chase >1% above pivot"). Phase 5 (Configuration page) surfaces an editor; this dispatch ships the storage + read path. **Toml-shadowing audit (per the 2026-04-29 multi-path-ingestion lesson + the prior `aeb2084` lesson):** clean — `chase_factor` does not appear in any tracked toml file (`swing.config.toml` grep at baseline returns 0 hits in the codebase, only in the brief documents). The introduction is fresh; no shadowed override exists.

2. **Chart in expansion uses the existing chart-access UX.** When the ticker is IN chart-scope, render the date-prefixed `<img src="/charts/{date}/{TICKER}.png">` directly via the VM's resolved scope (same pattern as `watchlist_expanded.html.j2` and `open_positions_expanded.html.j2`). When OUT of scope, render the "Chart unavailable" div with the operator-facing reason from `swing.web.chart_scope.resolve_chart_scope`. **No chart-scope policy change.**

3. **Cost display = TWO numbers, side by side.** Risk-based (sizing equity = `max(account.risk_equity_floor, current_balance)`) AND cash-feasible (sizing equity = `current_balance` only — NOT total liquidity). For each, render shares + total cost. V2 may add a risk-display for both ends; V1 ships shares + total cost for the two cases.

4. **Lightning icon stays bound to `entry_target`.** No behavior change. The visual confusion described in §3.8 is accepted as deliberate cost of preserving the current behavior as a future-decision reminder per Tier-3 #5.

5. **Hyp-recs ONLY in this dispatch.** Watchlist + open-positions snapshot extensions deferred. The watchlist's existing expansion stays chart-only-plus-Sector/Industry-rows (just shipped 2026-04-29); open-positions stays chart-only.

6. **CC pivot bug bundled.** Watchlist `Pivot` column header currently renders `WatchlistEntry.entry_target` (frozen at add time) — fix renders `candidates.pivot` for the latest pipeline-eval row. Lightning trigger logic stays bound to `entry_target` per #4 (independent code reference; only the column display changes).

### 1.2 Operator-judgment-call disclosures (surface in return report)

The dispatch brief §3.D presupposes "the hyp-recs row already has an 'Enter' button (visible in operator's earlier screenshots)." Spec investigation at baseline `4ba9c62` confirms `swing/web/templates/partials/hypothesis_recommendations.html.j2` does NOT contain an Enter button — the seven columns are Ticker, Price, Pivot, Hypothesis, Progress, Tripwire, Suggested label, with no actions cell. The closest existing Enter button is on watchlist rows (`partials/watchlist_row.html.j2:32`); operators today reach the entry form via the watchlist's `Enter` button after recognizing a hyp-rec match by ticker. Spec resolves Q-D against this corrected premise (information-only expansion; see §3.7). Surfaced in the return report under "Brief premise corrections."

### 1.3 What V1 ships

1. **`Config.web.chase_factor`** — single new config field, default 0.01, no migration (pure Python).
2. **One new VM dataclass** — `HypRecsExpandedVM` (route-local, snapshot-on-click), rendered by the new partial `partials/hypothesis_recommendations_expanded.html.j2`. **Existing `HypothesisRecommendation` is unchanged** — sizing twins, sector, industry, current_balance live ONLY on `HypRecsExpandedVM` and are computed at click time, NOT precomputed on the collapsed-table render. (R1-Major-1 resolution: keeps the §2.2 snapshot-at-render invariant honest; §1.3 and §2.3 no longer contradict it.)
3. **Two new route handlers** — `GET /hyp-recs/{ticker}/expand` returns the expansion partial; `GET /hyp-recs/refresh` returns the full hyp-recs section partial (used by the close button — see §3.5.4 / §4.6 for the rejected per-row reconstruction path).
4. **Row-target prefix extension** — `_ROW_TARGET_PREFIXES` in `swing/web/app.py:31-37` extended to include `hyp-rec-row-` so HTMX 4xx/5xx error fragments swap as `<tr>` rather than `<div>` (R1-Major-2 resolution; the current tuple covers `open-position-`, `entry-form-`, `exit-form-`, `stop-form-`, `watchlist-row-` only).
5. **Modified template** — `partials/hypothesis_recommendations.html.j2` gains a leading chevron column; the per-row markup is extracted into `hypothesis_recommendations_row.html.j2` (used only by the full-table render in V1 — see §4.6 rationale).
6. **Bundled CC pivot bug fix** — separate task in the writing-plans output (see §3.9): `partials/watchlist_row.html.j2:16` switches from `w.entry_target` to a `current_pivot` lookup. The fix touches THREE render sites: the dashboard top-5 watchlist include, the standalone watchlist page include, AND `WatchlistRowVM` (`swing/web/view_models/watchlist.py:50-64`) so the watchlist's `/watchlist/{ticker}/row` close-path doesn't revert the column to `entry_target` after expand-close (R1-Major-3 resolution). Lightning trigger at line 7 stays unchanged.
7. **Tests across four layers** — unit (sizing-twin compute), VM (HypRecsExpandedVM build + anchor), route (HTMX expand + refresh + chart-scope fallback + row-target-prefix coverage), template (regression on flat table, regression on watchlist Pivot column across all three render sites).

### 1.4 What V1 does NOT ship (deferred)

- "Take this trade" action button on the expansion (Q-D) — V2 candidate (requires pre-fill plumbing + ToCToU handling for a new entry surface; out of scope per §3.7 rationale).
- Watchlist + open-positions snapshot extensions (locked OUT per §1.1 #5).
- Mobile/responsive design (Q-M; deferred per brief §3.M).
- Sort-PARTICIPATING fields (any sizing/cost/sector value never enters the hyp-recs prioritizer or `_sort_watchlist`).
- Live-update push (HTMX SSE / WebSocket for snapshot changes during pipeline run).
- Configuration-page UI for `chase_factor` (Phase 5 of the operator sequence).
- Risk-display for both ends of the cost range (Q3 in brief; V2 candidate).
- Multi-trade preview / aggregate cost across selected hyp-recs.
- Sector concentration warning (V2 follow-up of the sector capture; gated on shipping the data which is now done).
- Lightning trigger logic re-evaluation (Tier-3 #5 stays open as a separate operator-paced design conversation).

---

## 2. Architecture

### 2.1 File map

```
swing/
├── config.py                                        # MODIFY: cfg.web.chase_factor (1 new field)
├── web/
│   ├── view_models/
│   │   ├── dashboard.py                             # MODIFY: add build_hyp_recs_expanded + HypRecsExpandedVM
│   │   └── watchlist.py                             # MODIFY: WatchlistRowVM gains current_pivot field (§3.9)
│   ├── routes/
│   │   ├── recommendations.py                       # NEW: /hyp-recs/{ticker}/expand + /hyp-recs/refresh
│   │   └── watchlist.py                             # MODIFY: /watchlist/{ticker}/row populates WatchlistRowVM.current_pivot
│   ├── chart_scope.py                               # READ-ONLY: existing helper consumed
│   ├── app.py                                       # MODIFY: register router + extend _ROW_TARGET_PREFIXES (§3.5.4)
│   └── templates/
│       ├── partials/
│       │   ├── hypothesis_recommendations.html.j2          # MODIFY: chevron col + iterate row partial
│       │   ├── hypothesis_recommendations_row.html.j2      # NEW: per-row partial (extracted; §4.6)
│       │   ├── hypothesis_recommendations_expanded.html.j2 # NEW: expansion partial
│       │   ├── hyp_recs_expand_unavailable.html.j2         # NEW: 404-state row partial (§3.5.4)
│       │   └── watchlist_row.html.j2                       # MODIFY (CC pivot bug, §3.9)
│       ├── partials/watchlist_top5_section.html.j2         # MODIFY (CC pivot wiring, R2-M1):
│       │                                                    #   {% set current_pivot %} before row include
│       └── watchlist.html.j2                                # MODIFY (CC pivot wiring): same {% set %}

tests/
├── recommendations/
│   └── test_hypothesis_sizing_twins.py              # NEW (§4.1)
└── web/
    ├── view_models/
    │   ├── test_hyp_recs_expansion_vm.py            # NEW (§4.2)
    │   └── test_hyp_recs_sort_neutrality.py         # NEW (§4.4)
    ├── routes/
    │   └── test_hyp_recs_expand_route.py            # NEW (§4.3): expand + refresh + row-target-prefix coverage
    └── templates/
        ├── test_hyp_recs_table_regression.py        # NEW (§4.4)
        └── test_watchlist_pivot_column.py           # NEW (§4.5): three-render-site coverage
```

Files touched (full list):

- **Production NEW (4):** `swing/web/routes/recommendations.py`, `swing/web/templates/partials/hypothesis_recommendations_row.html.j2`, `swing/web/templates/partials/hypothesis_recommendations_expanded.html.j2`, `swing/web/templates/partials/hyp_recs_expand_unavailable.html.j2`.
- **Production MODIFY (8):**
  1. `swing/config.py` — one new `Web` field (`chase_factor`).
  2. `swing/web/view_models/dashboard.py` — add `HypRecsExpandedVM` + `build_hyp_recs_expanded`. `HypothesisRecommendation` UNCHANGED (per R1-Major-1).
  3. `swing/web/view_models/watchlist.py` — `WatchlistRowVM` gains `current_pivot: float | None = None` (R1-Major-3).
  4. `swing/web/routes/watchlist.py` — `/watchlist/{ticker}/row` populates `WatchlistRowVM.current_pivot` from `candidates_by_ticker`.
  5. `swing/web/app.py` — register the recommendations router AND extend `_ROW_TARGET_PREFIXES` to include `hyp-rec-row-` (R1-Major-2).
  6. `swing/web/templates/partials/hypothesis_recommendations.html.j2` — chevron leading column + iterate per-row partial.
  7. `swing/web/templates/partials/watchlist_row.html.j2` — CC pivot bug fix at line 16 (R1-Minor-3 dash sentinel for missing both).
  8. **TWO parent templates that iterate watchlist rows (R2-Major-1 correction):** `swing/web/templates/partials/watchlist_top5_section.html.j2` (dashboard top-5 path; `dashboard.html.j2:15` includes this section but does NOT iterate rows directly) AND `swing/web/templates/watchlist.html.j2` (standalone watchlist page). Each gains `{% set current_pivot = vm.candidates_by_ticker[w.ticker].pivot if w.ticker in vm.candidates_by_ticker else None %}` immediately before the `{% include "partials/watchlist_row.html.j2" %}`. (Counted as one MODIFY entry but two file edits — finalized at writing-plans dispatch.)
- **Test NEW (6):** the six files listed in the `tests/` block.

Total: **18 files** (4 production NEW + 8 production MODIFY + 6 test NEW). No migrations. No Phase 2 carve-outs (see §5).

### 2.2 Design invariants

- **No new data surface.** Every value rendered in the expansion derives from EXISTING tables (`candidates`, `pipeline_runs`, account state) via existing accessors (`candidates_by_ticker`, `compute_shares`, `sizing_equity`, `current_equity`, `resolve_chart_scope`). No new migration; no new repo function unless trivial composition. Phase 2 is read-only this dispatch.
- **Sort neutrality (structural).** The expansion adds zero fields to the sort-key path. `_sort_watchlist`, hyp-recs `prioritized_recommendations`, and all `_TAG_PRECEDENCE` references are byte-for-byte unchanged. Tested via the discipline established in the chart-pattern flag-v1 spec (§3.5 of `2026-04-26-chart-pattern-flag-v1-design.md`): row order MUST be identical with the expansion enabled vs disabled.
- **Snapshot-at-render.** Buy stop, buy limit, sell stop, sizing twins, and sector/industry are computed at the moment the operator clicks to expand. They are NOT persisted; they are NOT carried into a subsequent entry submission as hidden form values (Q-K is moot — see §3.7). The "as of <pipeline_finished>" footer (§3.6.5) signals when the underlying candidate data was produced.
- **Anchor consistency (Bug 7 family).** The expansion's chart-scope, candidate, and pivot/initial_stop reads bind to the SAME `pipeline_runs.evaluation_run_id` → `pipeline_run_id` already used by `build_dashboard` for `candidates_by_ticker`. The route handler (§3.5.4) re-uses `latest_completed_pipeline_run` (already used by `swing/web/routes/charts.py`) and threads the binding through to `resolve_chart_scope` and the candidate lookup. No "latest by computed_at" reads anywhere in this dispatch.
- **Base-layout shared VM gotcha (CLAUDE.md).** The expansion's data lives inside `HypothesisRecommendation` (already a member of `DashboardVM.active_recommendations`); the new partial is included from `hypothesis_recommendations.html.j2` which is itself only included from `dashboard.html.j2`. **No new top-level `vm.foo` field is introduced.** This deliberately avoids the 5-VM propagation tax that hit Phase 3c (`price_source_degraded`) and 3d (`ohlcv_source_degraded`). If implementation discovers an unexpected base-layout reference, all base-layout VMs MUST gain the field with a safe default — implementation tests should grep for `{% extends "base.html.j2" %}` and confirm the new partial isn't transitively included.
- **HTMX OOB-swap partial drift discipline (CLAUDE.md).** The new expansion partial is loaded ONLY via the HTMX route, never as part of full-page render or any prices-refresh OOB swap. The risk class (hand-duplicated full-page markup vs OOB partial) does not apply because there is no prices-refresh path that re-renders hyp-recs (`active_recommendations` is computed once per request from candidates, not refreshed on prices update). Implementation tests confirm by inspecting the full template tree for incidental includes.
- **Pure-function sizing twins.** The risk-based and cash-feasible numbers are TWO calls to the existing `compute_shares` with different `equity` arguments. No new sizing function is introduced; no semantic divergence between the existing entry-form sizing and the expansion's display.

### 2.3 Data flow (expansion render)

```
[web request: GET /]
    build_dashboard ↓                        # UNCHANGED at HypothesisRecommendation level
        candidates_by_ticker = {c.ticker: c for c in candidates}
        active_recommendations: tuple[HypothesisRecommendation, ...] = (
            HypothesisRecommendation(...)    # existing fields only — no extension
            for r in top_recommendations
        )
    DashboardVM(...)                          # no new top-level field
    ↓
    template renders hyp-recs FLAT TABLE — only the existing 7 fields plus a leading
    chevron BUTTON (no collapsed-row data plumbing changes)

[web request: GET /hyp-recs/{ticker}/expand  (HTMX)]
    handler:
        current_balance = current_equity(starting_equity=cfg.account.starting_equity,
                                         exits=list_exits(conn),
                                         cash_movements=list_cash_movements(conn))
        vm = build_hyp_recs_expanded(conn, cfg, ticker=ticker, current_balance=current_balance)
        if vm is None: return 404 partial (hyp_recs_expand_unavailable.html.j2)
        return 200 partial (hypothesis_recommendations_expanded.html.j2)

    build_hyp_recs_expanded(conn, cfg, *, ticker, current_balance):
        binding = latest_completed_pipeline_run(conn)              # SHARED anchor
        candidate = candidates_repo.get_for_evaluation(conn,
                        evaluation_run_id=binding.eval_id, ticker=ticker)
        chart_reason, chart_message = resolve_chart_scope(conn, binding=binding, ...)
        risk_equity = sizing_equity(real_equity=current_balance,
                                    floor=cfg.account.risk_equity_floor)
        sizing_risk = compute_shares(entry=candidate.pivot, stop=candidate.initial_stop,
                                     equity=risk_equity, ...)
        sizing_cash = compute_shares(entry=candidate.pivot, stop=candidate.initial_stop,
                                     equity=current_balance, ...)
        return HypRecsExpandedVM(
            buy_stop=candidate.pivot,
            buy_limit=candidate.pivot * (1 + cfg.web.chase_factor),
            sell_stop=candidate.initial_stop,
            chase_factor=cfg.web.chase_factor,
            current_balance=current_balance,
            risk_equity=risk_equity,
            sizing_risk=sizing_risk, sizing_cash=sizing_cash,
            sector=candidate.sector, industry=candidate.industry,
            data_asof_date=binding.data_asof_date,
            chart_reason=chart_reason, chart_reason_message=chart_message,
            pipeline_finished_at=binding.finished_ts,
        )

[web request: GET /hyp-recs/refresh  (HTMX, fired by close button)]
    handler:
        # Equivalent to the hyp-recs slice of build_dashboard. Returns the
        # rendered hypothesis_recommendations.html.j2 section.
        # Acceptable simplification per R1-Major-4 — see §4.6 for the
        # rejected per-row reconstruction path.
        return render hypothesis_recommendations.html.j2 with the same
            active_recommendations build_dashboard would compute right now
```

The expansion VM is **route-local snapshot-at-click**. The collapsed table renders only the existing seven fields (no precomputed sizing or sector data on `HypothesisRecommendation`). The close button issues a full-section refresh rather than a per-row reconstruction (R1-Major-4 resolution; §4.6 rationale).

---

## 3. Components

### 3.1 Configuration: `Config.web.chase_factor`

Add one field to the existing `Web` dataclass at `swing/config.py:141-162`:

```python
@dataclass(frozen=True)
class Web:
    # ... existing fields ...
    chase_factor: float = 0.01
    # Operator's pure-trigger discipline (2026-04-25): wait for pivot,
    # don't chase >1% above pivot. The hyp-recs trade-prep expansion
    # renders buy_limit = pivot × (1 + chase_factor); the watchlist
    # lightning trigger remains bound to entry_target per Tier-3 #5.
    # Phase 5 surfaces an editor for this value.
```

**Toml-shadowing audit — clean.** `swing.config.toml` baseline at `4ba9c62` does NOT contain a `chase_factor` key; baseline-wide grep finds the string only in the brief and phase3e-todo documents. The implementation MUST NOT introduce a `chase_factor = 0.01` line in `swing.config.toml` as part of this dispatch — adding a toml row converts the field from "code default with no shadow" to "code default with operator-shadowed override", which is exactly the failure class the multi-path-ingestion lesson captured. The toml row is a Phase 5 (configuration page) concern; until then, operators who want to override write the value into their local toml as a deliberate opt-in, and the spec / phase3e-todo document calls out this asymmetry. (Adversarial-watch item: if a reviewer flags the missing toml row as inconsistent with other `Web` fields like `flag_pattern_display_threshold` which also has no toml row, the same rationale applies — Phase 5 surfaces ALL `Web`-scoped operator-tunable fields together rather than piecemeal.)

**Default rationale (0.01 = 1%).** Per locked decision §1.1 #1, sourced from the 2026-04-25 entry discipline. Field is `float`, accepts any value in `[0.0, 1.0]`; spec does NOT add a CHECK / runtime validator (consistent with sibling fields like `flag_pattern_display_threshold` whose 0.0–1.0 valid range is also implicit). Phase 5's editor adds explicit range validation when the operator-facing surface ships.

### 3.2 Sell stop source

**Source:** `Candidate.initial_stop` (column `initial_stop REAL` on `candidates`, migration `0001_phase1_initial.sql:31`). This is the framework-computed initial stop already used by the trade-entry form's auto-fill (`swing/web/view_models/trades.py:152` calls `compute_shares(entry=..., stop=candidate.initial_stop, ...)`) and by the pipeline's evaluation step.

**Rejected alternative:** computing fresh via `compute_shares` at render time. The framework's initial stop is set by the evaluator at pipeline time and is the same value the entry form would propose if the operator hit Enter; a fresh computation would either return the same value (no benefit) or risk drifting from the entry-form's auto-fill (creating a confusing "sell stop here, different sell stop on entry form" experience). Spec choice keeps the expansion's "Sell stop" identical to what the operator sees on the entry form for the same ticker.

**Plumbing:** Read directly from `Candidate.initial_stop` inside `build_hyp_recs_expanded` — no `HypothesisRecommendation` extension. The route handler fetches the candidate via `candidates_repo.get_for_evaluation(conn, evaluation_run_id, ticker)` against the SAME `pipeline_runs.evaluation_run_id` binding `latest_completed_pipeline_run` returned. The route's per-click resolver is the only producer of expansion data; the collapsed table never needs `initial_stop`.

### 3.3 Sizing twins (Q-I cost display)

**Two calls to `compute_shares` with different `equity` arguments. No new sizing logic.**

```python
risk_equity  = sizing_equity(
    real_equity=current_balance,
    floor=cfg.account.risk_equity_floor,    # $7,500 from config
)
cash_equity  = current_balance               # NOT total liquidity

sizing_risk  = compute_shares(
    entry=candidate.pivot, stop=candidate.initial_stop,
    equity=risk_equity,
    max_risk_pct=cfg.risk.max_risk_pct,
    position_pct_cap=cfg.sizing.position_pct_cap,
)
sizing_cash  = compute_shares(
    entry=candidate.pivot, stop=candidate.initial_stop,
    equity=cash_equity,
    max_risk_pct=cfg.risk.max_risk_pct,
    position_pct_cap=cfg.sizing.position_pct_cap,
)
```

Each `SizingResult` carries shares + notional + feasibility + binding constraint. The expansion renders:

```
Sizing
  Risk-based   (eq $7,500): 31 sh × $30.00 = $930.00     (constraint: risk)
  Cash-feasible (eq $1,200):  8 sh × $30.00 = $240.00    (constraint: position_cap)
```

**Visualization (Q-I resolution):** **two-row layout with a "Sizing" group header**, each row reading `<label> (eq $<equity>): <shares> sh × $<entry> = $<notional> (constraint: <constraint>)`. Rejected alternatives:
- Inline pair (`Total cost: $930 / $240`) — too dense; loses constraint annotation that operators use to spot risk-vs-cap binding cases.
- Three-line "Sizing: 31 sh × $30 = $930 (risk-based) | 8 sh × $30 = $240 (cash-feasible cap)" — collapses to one visual line in narrow viewports and forces double-parsing.
- Two rows is one visual scan, preserves equity context (so the operator can sanity-check the floor logic), and exposes the binding constraint (which informs whether a tighter stop or higher chase factor would change the outcome).

**Infeasibility handling.** If `compute_shares` returns `feasible=False` (no equity, or 1 share exceeds max risk), the row renders `"infeasible (—)"` instead of `0 sh × ... = $0.00`; the constraint annotation carries the reason (`constraint="no_equity"` or `constraint="infeasible"`). This is a discriminating-test boundary in §4.

**Current balance source.** `current_balance` is computed identically to the existing dashboard equity displays — `current_equity(starting_equity=cfg.account.starting_equity, exits=exits, cash_movements=cash_movements)`. The implementation MUST reuse the same accessor `build_dashboard` already invokes for its existing equity display so the two surfaces never disagree. (Adversarial-watch item §6: same-source check for the balance value across the dashboard's existing equity strip and the expansion's cash-feasible label.)

### 3.4 Sector + Industry (Q-L)

**Include in the expansion as context fields.** Operator confirmed sector is part of decision-making (orchestrator-context lines 156–157). Per the locked decision in the brief, Sector + Industry are now persisted on `candidates` (migration 0012) and available via `candidates_by_ticker` without any new plumbing.

**Display:** rendered in a `Context` group below the chart, mirroring `watchlist_expanded.html.j2:33-34`:

```
Context
  Sector:   Technology
  Industry: Software—Application
```

Empty-string values (unknown/missing from Finviz) render as `"—"` to mirror the existing dashboard convention. The sector dispatch's NOT-NULL-DEFAULT-empty-string semantic carries through (spec adheres to migration 0012's design choice).

### 3.5 VM and route

#### 3.5.1 `HypothesisRecommendation` — UNCHANGED

(R1-Major-1 resolution.) `HypothesisRecommendation` at `swing/web/view_models/dashboard.py` is NOT extended. The collapsed hyp-recs table renders only the existing seven fields plus a leading chevron BUTTON column (button is template-only — no VM data needed). All expansion-only data lives on `HypRecsExpandedVM` (§3.5.2) and is computed at click time inside `build_hyp_recs_expanded` (§3.5.3). This eliminates the §1.3-vs-§2.2 contradiction R1 caught and removes a class of "stale precomputed value rendered into the freshly-clicked expansion" bugs.

#### 3.5.2 New `HypRecsExpandedVM`

```python
@dataclass(frozen=True)
class HypRecsExpandedVM:
    ticker: str
    # Order params
    buy_stop: float                       # = candidate.pivot
    buy_limit: float                      # = pivot × (1 + chase_factor)
    sell_stop: float | None               # = candidate.initial_stop (None if missing)
    chase_factor: float                   # echo for footer / tooltip
    # Sizing (two regimes)
    current_balance: float
    risk_equity: float
    sizing_risk: SizingResult
    sizing_cash: SizingResult
    # Context
    sector: str
    industry: str
    # Chart
    data_asof_date: str | None            # for `/charts/{date}/{TICKER}.png` URL
    chart_reason: str | None              # None → in scope; else key into CHART_REASON_MESSAGES
    chart_reason_message: str | None
    # Freshness
    pipeline_finished_at: str | None      # ISO timestamp of the binding pipeline run
```

Lives in `swing/web/view_models/dashboard.py` adjacent to `HypothesisRecommendation`. The dataclass is `frozen=True` consistent with sibling VMs.

#### 3.5.3 `build_hyp_recs_expanded` helper

```python
def build_hyp_recs_expanded(
    conn, cfg, *, ticker: str, current_balance: float,
) -> HypRecsExpandedVM | None:
    """Resolve a hyp-recs expansion VM at request time. Returns None if the
    ticker has no candidate row in the latest completed pipeline run (the
    operator's expansion request races a candidate rotation; the route
    handler returns 404 with a 'not currently a candidate' message).
    """
    binding = latest_completed_pipeline_run(conn)
    if binding is None:
        return None
    candidate = candidates_repo.get_for_evaluation(conn, evaluation_run_id=binding.eval_id, ticker=ticker)
    if candidate is None or candidate.pivot is None:
        return None
    chart_reason, chart_message = resolve_chart_scope(
        conn, binding=binding, ticker=ticker,
        charts_dir=cfg.paths.charts_dir,
        chart_top_n_watch=cfg.pipeline.chart_top_n_watch,
    )
    risk_equity = sizing_equity(real_equity=current_balance, floor=cfg.account.risk_equity_floor)
    sizing_risk = compute_shares(
        entry=candidate.pivot, stop=candidate.initial_stop,
        equity=risk_equity,
        max_risk_pct=cfg.risk.max_risk_pct,
        position_pct_cap=cfg.sizing.position_pct_cap,
    )
    sizing_cash = compute_shares(
        entry=candidate.pivot, stop=candidate.initial_stop,
        equity=current_balance,
        max_risk_pct=cfg.risk.max_risk_pct,
        position_pct_cap=cfg.sizing.position_pct_cap,
    )
    return HypRecsExpandedVM(
        ticker=ticker,
        buy_stop=candidate.pivot,
        buy_limit=candidate.pivot * (1.0 + cfg.web.chase_factor),
        sell_stop=candidate.initial_stop,
        chase_factor=cfg.web.chase_factor,
        current_balance=current_balance,
        risk_equity=risk_equity,
        sizing_risk=sizing_risk,
        sizing_cash=sizing_cash,
        sector=candidate.sector or "",
        industry=candidate.industry or "",
        data_asof_date=binding.data_asof_date,
        chart_reason=chart_reason,
        chart_reason_message=chart_message,
        pipeline_finished_at=binding.finished_ts,
    )
```

Failure modes (returning `None`) are handled by the route as 404 with an operator-facing message — see §3.5.4.

**`compute_shares` precondition (`stop < entry`):** the sizing call raises `ValueError` when `candidate.initial_stop >= candidate.pivot`. In normal pipeline state this never holds (the evaluator's stop is below pivot by construction), but a degenerate pipeline run could in principle produce one. The helper wraps the two `compute_shares` calls in `try`/`except ValueError` and returns `None` on either failure (route returns 404 with the `"degenerate sizing parameters"` message). This is a defensive-at-boundary acceptance — the spec does NOT add a stronger-typed constraint at the `Candidate` layer because that would expand scope into evaluator validation.

#### 3.5.4 Routes: `GET /hyp-recs/{ticker}/expand` and `GET /hyp-recs/refresh`

```python
# swing/web/routes/recommendations.py

router = APIRouter()

@router.get("/hyp-recs/{ticker}/expand")
def hyp_recs_expand(request: Request, ticker: str):
    cfg = request.app.state.cfg
    ticker_upper = ticker.upper()
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            current_balance = current_equity(
                starting_equity=cfg.account.starting_equity,
                exits=list_exits(conn),
                cash_movements=list_cash_movements(conn),
            )
            vm = build_hyp_recs_expanded(
                conn, cfg, ticker=ticker_upper, current_balance=current_balance,
            )
            if vm is None:
                return templates.TemplateResponse(
                    request,
                    "partials/hyp_recs_expand_unavailable.html.j2",
                    {"ticker": ticker_upper, "message": "Not a current candidate or pivot data missing."},
                    status_code=404,
                )
            return templates.TemplateResponse(
                request, "partials/hypothesis_recommendations_expanded.html.j2",
                {"expanded": vm}, status_code=200,
            )
    finally:
        conn.close()


@router.get("/hyp-recs/refresh")
def hyp_recs_refresh(request: Request):
    """Close-button target. Returns the freshly-rendered hyp-recs section so
    the closing operator sees the same values the page would render right
    now. Per §4.6, the alternative — per-row reconstruction — is rejected
    because hyp-recs rows are prioritizer + top-N output, not stable
    projections of one persisted record."""
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    ohlcv_cache = getattr(request.app.state, "ohlcv_cache", None)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=executor, ohlcv_cache=ohlcv_cache)
    return templates.TemplateResponse(
        request, "partials/hypothesis_recommendations.html.j2",
        {"vm": vm}, status_code=200,
    )
```

**Row-target prefix extension (R1-Major-2).** `swing/web/app.py:31-37` `_ROW_TARGET_PREFIXES` MUST gain `hyp-rec-row-`:

```python
_ROW_TARGET_PREFIXES = (
    "open-position-", "entry-form-", "exit-form-", "stop-form-",
    "watchlist-row-",
    "hyp-rec-row-",      # NEW — see swing/web/routes/recommendations.py
)
```

Without this addition, an HTMX request whose `HX-Target` is `hyp-rec-row-XYZ` would NOT be detected by `_is_row_swap_target`, and the global exception handler at `swing/web/app.py` would render the generic `<div>` error fragment into a `<tbody>`, breaking the table DOM. The 404 partial (`hyp_recs_expand_unavailable.html.j2`) and any 500 from the route MUST swap as a `<tr>`. Tested in §4.3 with both a 404 path and a forced-500 path.

**HTMX 4xx semantics.** Per the CLAUDE.md gotcha, `base.html.j2` already overrides HTMX 2.x default to swap on 4xx. The 404 path renders an `<tr>` fragment that swaps in place of the row, displaying the unavailable message. The unavailable partial is `partials/hyp_recs_expand_unavailable.html.j2` (one `<tr><td colspan="8">` with the message + close button).

**Anchor consistency.** All reads (`latest_completed_pipeline_run`, `candidates_repo.get_for_evaluation`, `resolve_chart_scope`) bind to the SAME `pipeline_runs.id` resolved at the start of the handler — no "latest" by `started_ts` race. Mirrors the established pattern in `swing/web/routes/charts.py:43-89`.

**Refresh-route shared-state caveat.** `GET /hyp-recs/refresh` calls `build_dashboard` to re-resolve `active_recommendations` consistent with what the page would render right now. This means the close button sees an up-to-date snapshot, NOT a frozen reconstruction of the expand-time row set. If a pipeline run completed between expand and close, the close render reflects the new state — operator sees the latest data on dismiss, which is the safer default (R1-Major-4 disposition).

#### 3.5.5 Template: `hypothesis_recommendations.html.j2` modification

Current state: 7-column table, no row interactivity. Modified state: 8 columns (chevron added as the LEADING column), each `<tr>` becomes an HTMX trigger:

```jinja
<thead>
  <tr>
    <th aria-label="Expand"></th>     {# NEW: chevron column #}
    <th>Ticker</th>
    <th>Price</th>
    <th>Pivot</th>
    <th>Hypothesis</th>
    <th>Progress</th>
    <th>Tripwire</th>
    <th>Suggested label</th>
  </tr>
</thead>
<tbody>
  {% for rec in vm.active_recommendations %}
    <tr id="hyp-rec-row-{{ rec.ticker }}"
        {% if rec.tripwire_fired %}class="tripwire-fired"{% endif %}>
      <td>
        <button type="button" class="expand-toggle"
                hx-get="/hyp-recs/{{ rec.ticker }}/expand"
                hx-target="closest tr"
                hx-swap="outerHTML"
                hx-headers='{"HX-Request": "true"}'
                aria-label="Expand {{ rec.ticker }}">▸</button>
      </td>
      <td>{{ rec.ticker }}</td>
      ...
    </tr>
  {% endfor %}
</tbody>
```

**HTMX expansion mechanics (Q-C resolution):** **dedicated chevron column with explicit button click.**

Rejected alternative: row-level `hx-get` (mirroring watchlist's pattern at `partials/watchlist_row.html.j2:3-5`). Rationale for rejection:
1. **Existing architectural concern.** The orchestrator-context "Bug 1 follow-up: Watchlist row HTMX trigger architecture refactor" notes that interactive children inside row-click rows require `event.stopPropagation()` on every nested control. The watchlist row already has this complexity for its `Enter` button at `:31`.
2. **Future "Take this trade" button.** Per Q-D resolution (§3.7) information-only is V1, but V2 will likely add an action button to the expansion. A row-level click would force `stopPropagation()` to be retrofitted to that future button; an explicit chevron sidesteps the retrofit.
3. **Affordance clarity.** A leading chevron is a stronger visual cue ("this row expands") than a hover-state on the whole row. The hyp-recs panel's framing ("dashboard PROPOSES, operator DISPOSES") is well-served by an explicit operator-action surface.
4. **Accessibility.** The button is keyboard-focusable and screen-reader-labelled (`aria-label="Expand {ticker}"`); a row-level click is not.

Cost accepted: an additional 8th column. Hyp-recs is a narrow table (7 cells of mostly-numeric content); one more column does not push the table past readable width. The chevron column is intentionally narrow (`width:1.5em`) to minimize layout disruption.

#### 3.5.6 New partial: `hypothesis_recommendations_expanded.html.j2`

```jinja
{#- Expects: expanded (HypRecsExpandedVM) -#}
<tr id="hyp-rec-row-{{ expanded.ticker }}" class="expanded">
  <td colspan="8">
    <button class="close-expanded" type="button"
            hx-get="/hyp-recs/refresh"
            hx-target="#hypothesis-recommendations" hx-swap="outerHTML"
            hx-headers='{"HX-Request": "true"}'
            aria-label="Close expanded row for {{ expanded.ticker }}"
            title="Close">✕</button>
    <h3>{{ expanded.ticker }}</h3>

    <h4>Order parameters</h4>
    <ul class="order-params">
      <li>Buy stop:  ${{ '%.2f' | format(expanded.buy_stop) }} <span class="muted">(pivot)</span></li>
      <li>Buy limit: ${{ '%.2f' | format(expanded.buy_limit) }}
          <span class="muted">(pivot × {{ '%.1f' | format(expanded.chase_factor * 100) }}%)</span></li>
      <li>Sell stop: {% if expanded.sell_stop is not none %}${{ '%.2f' | format(expanded.sell_stop) }}
                     {% else %}—{% endif %}
          <span class="muted">(framework initial stop)</span></li>
    </ul>

    <h4>Sizing</h4>
    <ul class="sizing-twins">
      <li>Risk-based <span class="muted">(eq ${{ '%.0f' | format(expanded.risk_equity) }})</span>:
        {% if expanded.sizing_risk.feasible %}
          {{ expanded.sizing_risk.shares }} sh × ${{ '%.2f' | format(expanded.buy_stop) }}
            = ${{ '%.2f' | format(expanded.sizing_risk.notional) }}
            <span class="muted">(constraint: {{ expanded.sizing_risk.constraint }})</span>
        {% else %}
          infeasible <span class="muted">({{ expanded.sizing_risk.constraint }})</span>
        {% endif %}
      </li>
      <li>Cash-feasible <span class="muted">(eq ${{ '%.0f' | format(expanded.current_balance) }})</span>:
        {% if expanded.sizing_cash.feasible %}
          {{ expanded.sizing_cash.shares }} sh × ${{ '%.2f' | format(expanded.buy_stop) }}
            = ${{ '%.2f' | format(expanded.sizing_cash.notional) }}
            <span class="muted">(constraint: {{ expanded.sizing_cash.constraint }})</span>
        {% else %}
          infeasible <span class="muted">({{ expanded.sizing_cash.constraint }})</span>
        {% endif %}
      </li>
    </ul>

    {% if expanded.chart_reason is none and expanded.data_asof_date %}
      <img src="/charts/{{ expanded.data_asof_date }}/{{ expanded.ticker }}.png"
           alt="Chart {{ expanded.ticker }}">
    {% elif expanded.chart_reason_message %}
      <div class="chart-unavailable" data-chart-reason="{{ expanded.chart_reason }}">
        {{ expanded.chart_reason_message }}
      </div>
    {% endif %}

    <h4>Context</h4>
    <p>Sector: {{ expanded.sector or "—" }}</p>
    <p>Industry: {{ expanded.industry or "—" }}</p>

    {% if expanded.pipeline_finished_at %}
      <p class="freshness muted">As of pipeline finished {{ expanded.pipeline_finished_at }}</p>
    {% endif %}
  </td>
</tr>
```

**Layout (Q-B resolution):** **grouped-by-category vertical layout — Order parameters / Sizing / Chart / Context / Freshness.** Rejected alternatives:
- Single-column flat list — loses semantic grouping; operator scanning for "what's the buy limit?" walks the whole list.
- Multi-column grid — tight on a desktop browser at typical zoom; charts are wide-aspect and need full row width.
- The grouped vertical layout puts Order parameters at the top (most decision-relevant), Sizing immediately below (operator's next question after "is the price in the buy window?" is "how big a position?"), Chart in the visual-prominence middle position, Context at the bottom (decision-informing but not gating), and Freshness as a footer signal.

**Layout mirrors `watchlist_expanded.html.j2`** at the structural level (`<h4>` section headers, `<ul>` lists, chart between sections) so an operator landing on either expansion uses the same visual scan pattern. Diverges by adding the Order parameters and Sizing groups (which watchlist doesn't have) in front of Context.

**Cache freshness signal (Q-J resolution):** **inline footer "As of pipeline finished <ISO>".** Rejected alternatives:
- Pipeline_run_id integer footer — operator-unfriendly; a number tells the operator nothing about staleness without a mental lookup.
- Nothing — the dashboard's "Last pipeline" indicator is at the top of the page; on a long page with the expansion at the bottom, the indicator is several scroll-heights away. The expansion's snapshot values (especially `current_balance`) drift fast enough during active trading that at-a-glance staleness assessment matters.
- Inline `pipeline_finished_at` ISO is the cheapest answer that doesn't require a layout shift; the existing dashboard's `prices_generated_at` precedent uses the same format.

**Chart inline rendering (Q-E resolution):** **mirror the chart-scope server-side resolution pattern from `watchlist_expanded.html.j2:36-43` and `open_positions_expanded.html.j2:32-39`.** The `<img>` URL is the SAME date-prefixed `/charts/{date}/{TICKER}.png` already mounted as StaticFiles; in-scope tickers render directly. Out-of-scope tickers render the `chart-unavailable` div with the operator-facing reason from `CHART_REASON_MESSAGES`. The `/charts/{TICKER}.png` (date-less) Tier-2 #2 redirect is NOT used here because we already know the date at VM build time — the redirect's purpose is for URLs operators paste into the address bar, not internal template references.

### 3.7 Action button decision (Q-D + Q-K)

**Resolution: Information-only V1 expansion. No "Take this trade" button.**

**Brief premise correction (surfaced in return report):** the dispatch brief states "the hyp-recs row already has an 'Enter' button (visible in operator's earlier screenshots)" but inspection of `swing/web/templates/partials/hypothesis_recommendations.html.j2` at baseline `4ba9c62` shows seven columns with no actions cell. The operator's current path from a hyp-rec to the entry form is via the watchlist's `Enter` button at `swing/web/templates/partials/watchlist_row.html.j2:32` (matching by ticker between the hyp-recs row and the watchlist row). Spec resolves Q-D against this corrected premise.

**Rationale for information-only:**
1. **Simplest first step.** The expansion's whole purpose is decision-quality (in/out of buy window, sizing math, chart visual). After the operator's mental "yes," they navigate to entry via the existing watchlist Enter button. Adding a parallel "Take this trade" button doubles the entry-surface count and forces a decision about pre-fill semantics + ToCToU handling for a NEW surface.
2. **Q-K becomes moot.** With no action button, the snapshot-at-render values are display-only; nothing carries them into a subsequent entry submission. The existing entry-form's snapshot-at-entry-surface ToCToU pattern (chart-pattern flag-v1 §3.6) is unchanged.
3. **Reversibility / V2 path.** Adding a button later is a one-template change; removing one is the same. V2 can either add a button to this expansion OR add an Enter button directly to the hyp-recs row (cleaner: matches the watchlist's row-level Enter button). The operator can choose at V2 dispatch time.

**Operator workflow (V1):** scan hyp-recs flat table → click chevron on row of interest → review buy window / sizing / chart → close expansion → cross-reference watchlist by ticker → click watchlist Enter button → entry form (which already pre-fills hypothesis_label from the matching recommendation, per existing logic). Adds one extra cognitive step (matching ticker between two rows on the same dashboard); the expansion's at-a-glance benefit is preserved.

### 3.8 Lightning icon coexistence (Q-H)

**Resolution: accept as deliberate cost. No tooltip, no annotation.**

**Disposition:**
- Lightning trigger fires when `price ≥ 0.99 × entry_target` (`partials/watchlist_row.html.j2:7`). `entry_target` is the operator's frozen-at-add value.
- The fixed-by-this-dispatch watchlist `Pivot` column will show `candidates.pivot` (current evaluation pivot).
- The hyp-recs expansion will show `buy_stop = candidate.pivot` and `buy_limit = pivot × (1 + chase_factor)`.
- These three reference points may differ — for example, after a rebase or pivot shift, `entry_target ≠ current_pivot`.
- An operator could see lightning fire (price within 1% of `entry_target`) while the expansion shows price below `buy_stop` (current pivot). Both are CONSISTENT under their respective semantics.

The dispatch brief locks Q4 to "no behavior change on lightning"; the spec adds NO informational tooltip or annotation in V1 (a tooltip would still be a behavior-change-adjacent surface that the brief flags as Tier-3 #5's territory). The operator preserves lightning's `entry_target` binding deliberately as a future-decision reminder. The visual confusion is real but acceptable for a personal-use single-operator tool.

V2 candidates if confusion proves operationally costly:
- Hover tooltip on lightning explaining the `entry_target` binding (informational only).
- Visual distinction between "entry_target" and "current_pivot" in the watchlist row (which would push this dispatch into a wider scope; Tier-3 #5 conversation territory).
- Repurposing lightning entirely (Tier-3 #5).

### 3.9 CC pivot bug fix (Q-G)

**Resolution: separate task in the writing-plans output, scoped to a single template change + a discriminating regression test.**

**Bug:** `partials/watchlist_row.html.j2:16` renders `{{ '%.2f' | format(w.entry_target or 0) }}` under a header that says "Pivot." `WatchlistEntry.entry_target` is the value frozen when the operator added the ticker to the watchlist; `candidates.pivot` is the current pipeline-eval pivot. A ticker whose pivot has shifted (rebase / VCP re-evaluation) shows a stale value under "Pivot" — operator decoding "Pivot" reads stale, while hyp-recs and trade-entry already render the current value (cross-surface inconsistency).

**Fix scope** — the partial `watchlist_row.html.j2` is rendered from THREE distinct call sites; the fix touches all three (R1-Major-3 resolution; R2-Major-1 correction on the parent-template site identification).

- **File 1: `swing/web/templates/partials/watchlist_row.html.j2:16`.** Change `{{ '%.2f' | format(w.entry_target or 0) }}` → `{% if current_pivot is not none %}${{ '%.2f' | format(current_pivot) }}{% elif w.entry_target %}${{ '%.2f' | format(w.entry_target) }}{% else %}—{% endif %}`. (R1-Minor-3 sentinel: render `—` rather than `$0.00` when both `current_pivot` and `entry_target` are absent.) New required template-context variable: `current_pivot: float | None`.
- **File 2: `swing/web/templates/partials/watchlist_top5_section.html.j2`** (rendered by `dashboard.html.j2:15` via `{% include "partials/watchlist_top5_section.html.j2" %}`; this partial is where the `<tbody>` iteration over `vm.watchlist_top5` happens — confirmed at `watchlist_top5_section.html.j2:7-12`). The dashboard does NOT iterate rows directly. Insert `{% set current_pivot = vm.candidates_by_ticker[w.ticker].pivot if w.ticker in vm.candidates_by_ticker else None %}` inside the `{% for w in vm.watchlist_top5 %}` block, immediately before `{% include "partials/watchlist_row.html.j2" %}`. (R2-Major-1 correction: `dashboard.html.j2` is the WRONG site; this partial is the right one.)
- **File 3: `swing/web/templates/watchlist.html.j2`** (standalone watchlist page; iterates rows at `watchlist.html.j2:13`). Same `{% set current_pivot = ... %}` insertion immediately before the row include.
- **File 4: `WatchlistRowVM` at `swing/web/view_models/watchlist.py:50-64`.** Add `current_pivot: float | None = None` trailing-default field. The `/watchlist/{ticker}/row` close-path route handler in `swing/web/routes/watchlist.py` must populate it via `candidates_by_ticker[ticker].pivot if ticker in candidates_by_ticker else None`. Without this, the watchlist's expand-then-close cycle would revert the Pivot column to `entry_target` exactly when the operator most needs the current value, recreating the bug post-close.

The `watchlist_row.html.j2` partial reads `current_pivot` from its template scope. Two callers (Files 2 and 3) provide it via `{% set %}`; the third caller (Watchlist row-collapse route via `WatchlistRowVM`) provides it via `current_pivot=row_vm.current_pivot` in the template context dict, or by extending the existing `{% include %}` invocation in the row-collapse route handler to set the variable before include.

Lightning trigger at line 7 stays unchanged: `{% if price and w.entry_target and price.price >= w.entry_target * 0.99 %}⚡{% endif %}` — `entry_target` binding preserved per Q4. Tests verify the unchanged trigger after the column-display change (§4.5 includes the discriminating fixture for this).

**Fallback semantics.** When `candidates_by_ticker` does NOT contain the watchlist ticker (rare: rotated out of finviz this run; not an open trade so `_step_evaluate`'s `bucket='excluded'` carve-out doesn't fire), the column falls back to `entry_target` if available, else "—". UX impact: when a current pivot exists, operator sees it (the new behavior); when not, falls back to the prior behavior (`entry_target`); when even that's missing, "—" instead of `$0.00` (clearer signal of missing data).

**Why a separate task and not bundled into expansion task:**
1. **Clean revert path.** If the fix turns out to break a test surface or expose a regression in the standalone watchlist view, a single-task revert touches one file and one test. Bundled with the expansion, a revert pulls in all the expansion machinery.
2. **Independent semantic concern.** The expansion is a NEW surface; the CC bug fix is a CHANGE to an existing surface. Different code-review cognitive load.
3. **Easier discriminating test.** The fix's discriminating test verifies `current_pivot=None` falls back to `entry_target` and `current_pivot=42.50` overrides; bundling forces the test to also exercise the expansion path.

**Cross-surface consistency invariant (done criteria item):** after the fix, all three surfaces (hyp-recs row, hyp-recs expansion, watchlist row) render the SAME `candidates.pivot` value when one exists for the ticker; only `WatchlistEntry.entry_target` is shown when no candidate row exists. Spec's adversarial-review watch item §6 includes this consistency check.

---

## 4. Tests

Three layers + bundled-bug regression. All in fast suite (no network).

### 4.1 Layer 1 — Sizing twin unit tests (`tests/recommendations/test_hypothesis_sizing_twins.py`)

Discriminating-test discipline (per the `feedback_regression_test_arithmetic` memory). Each pair differs by ONE feature crossing a threshold; values computed under both pre- and post-fix paths so the test distinguishes.

- `test_risk_based_uses_max_floor_when_balance_below_floor`: balance = $1,200, floor = $7,500, entry = $30, stop = $28, max_risk_pct = 0.005. Risk-based equity = $7,500. Expected: `shares_by_risk = floor(0.005 × 7500 / 2) = floor(18.75) = 18`; `shares_by_cap = floor(0.15 × 7500 / 30) = 37`. Result: `shares=18, constraint='risk', notional = 18 × 30 = $540`. Pre-fix path (using $1,200 instead of $7,500) would yield `shares_by_risk = floor(0.005 × 1200 / 2) = 3`; the test distinguishes. (Per the regression-test arithmetic memory: under-floor balance must NOT collapse risk-based to balance.)
- `test_cash_feasible_uses_balance_only_not_floor`: same inputs as above. Cash-feasible equity = $1,200. Expected: `shares_by_risk = 3`; `shares_by_cap = floor(0.15 × 1200 / 30) = 6`. Result: `shares=3, constraint='risk'`. Discriminating value: a fresh failure mode where the implementation accidentally re-applied `sizing_equity` to cash-feasible would yield 18 shares, not 3.
- `test_balance_above_floor_uses_balance_for_both`: balance = $10,000, floor = $7,500. Both regimes use $10,000. Risk-based and cash-feasible should match exactly.
- `test_infeasible_when_one_share_exceeds_max_risk`: entry = $1000, stop = $999, balance = $1,200, max_risk_pct = 0.0001 (so max_risk_dollars = $0.12 < $1 risk-per-share). Expected: `feasible=False, constraint='infeasible'`. Both regimes infeasible.
- `test_no_equity_path`: balance = $0, floor = $0. Expected: both regimes `feasible=False, constraint='no_equity'`.
- `test_position_cap_binds_when_pivot_high`: entry = $500, stop = $470, balance = $7,500. `shares_by_risk = floor(0.005 × 7500 / 30) = 1`; `shares_by_cap = floor(0.15 × 7500 / 500) = 2`. Result: `shares=1, constraint='risk'`. Discriminates from the entry-form's existing sizing call (which uses identical inputs).

### 4.2 Layer 2 — VM build tests (`tests/web/view_models/test_hyp_recs_expansion_vm.py`)

- `test_build_hyp_recs_expanded_happy_path`: in-scope ticker, valid candidate row. VM populated with all fields; chart_reason None.
- `test_build_hyp_recs_expanded_out_of_chart_scope`: ticker present in candidates but not in chart-scope. VM populated; `chart_reason` set; `chart_reason_message` non-None; `data_asof_date` populated (the date is always known when a binding exists; chart_reason captures the in/out distinction).
- `test_build_hyp_recs_expanded_ticker_not_in_latest_run`: ticker absent from candidates (rotated out). Helper returns `None`. Discriminating: a parallel test asserts the case where the ticker IS in candidates but `pivot IS NULL` ALSO returns None.
- `test_build_hyp_recs_expanded_no_completed_pipeline_run`: empty `pipeline_runs` table. Helper returns `None`.
- `test_build_hyp_recs_expanded_anchor_consistency`: simulate a pipeline run starting (pipeline_runs row with `finished_ts=NULL`) AFTER the binding's evaluation. Helper's `latest_completed_pipeline_run` MUST return the prior completed run; chart_scope, candidate, pivot all bind to the SAME run_id. Mirrors the established `pipeline_runs ORDER BY` discipline (CLAUDE.md gotcha).
- `test_buy_limit_arithmetic`: chase_factor = 0.01, candidate.pivot = $50. `buy_limit = $50.50`. Discriminating: chase_factor = 0.02 yields $51.00.
- `test_chase_factor_threads_from_config`: helper picks up `cfg.web.chase_factor` (not a hardcoded value).
- `test_degenerate_stop_above_pivot_returns_none`: candidate with `initial_stop > pivot` causes `compute_shares` to raise; helper catches and returns None.
- `test_sector_industry_threaded_through`: candidate.sector = "Technology"; VM.sector = "Technology". Empty string preserved (not coerced to None) so the template's `or "—"` fallback fires consistently.

### 4.3 Layer 3 — Route tests (`tests/web/routes/test_hyp_recs_expand_route.py`)

Use `TestClient(app)` with lifespan context per CLAUDE.md TestClient convention.

- `test_expand_route_returns_partial_html_for_in_scope_ticker`: GET `/hyp-recs/AAPL/expand` with HX-Request header + `HX-Target: hyp-rec-row-AAPL` → 200, body contains `<tr id="hyp-rec-row-AAPL" class="expanded">` and the order-params + sizing markup.
- `test_expand_route_returns_404_partial_for_unknown_ticker`: GET `/hyp-recs/ZZZZ/expand` with `HX-Target: hyp-rec-row-ZZZZ` → 404 with `partials/hyp_recs_expand_unavailable.html.j2` body containing the operator-facing message.
- `test_expand_route_404_swaps_as_tr_via_row_target_prefix` (R1-Major-2 regression): GET `/hyp-recs/ZZZZ/expand` with `HX-Target: hyp-rec-row-ZZZZ` → response body opens with `<tr` (NOT `<div`); confirms `_ROW_TARGET_PREFIXES` covers the new prefix. Discriminating: a parallel test omits the `hyp-rec-row-` prefix from `_ROW_TARGET_PREFIXES` (via patched tuple) and asserts the response body opens with `<div`, proving the prefix entry is load-bearing.
- `test_expand_route_500_swaps_as_tr_via_row_target_prefix`: a forced 500 (e.g., `monkeypatch.setattr` on `build_hyp_recs_expanded` to raise) with `HX-Target: hyp-rec-row-AAPL` returns a body opening with `<tr`. Closes the gap that caused the watchlist drift family.
- `test_expand_route_chart_unavailable_renders_message`: ticker out of chart-scope → 200 with `chart-unavailable` div, NOT the chart `<img>`.
- `test_expand_route_uses_latest_completed_pipeline_run_anchor`: insert a NEW `pipeline_runs` row with `finished_ts=NULL` after a completed run. Route MUST resolve against the completed run's binding (no race on `started_ts DESC`).
- `test_close_button_emits_full_section_refresh`: rendered expansion HTML contains `hx-get="/hyp-recs/refresh"` and `hx-target="#hypothesis-recommendations"` on the close button (NOT `/hyp-recs/{ticker}/row`). Confirms the R1-Major-4 mechanism shipped.
- `test_refresh_route_returns_section_partial`: GET `/hyp-recs/refresh` returns 200 with the rendered `hypothesis_recommendations.html.j2` section (root element `<section id="hypothesis-recommendations">`). Renders with the same flat-table chevron column.
- `test_refresh_route_reflects_current_state_not_expand_time_state`: capture `active_recommendations` snapshot A; insert a new pipeline run completing with a different snapshot B; GET `/hyp-recs/refresh` returns the section reflecting B. Documents the R1-Major-4 disposition (close shows current state, not expand-time state).

### 4.4 Layer 4 — Template + sort-neutrality regression

- `tests/web/templates/test_hyp_recs_table_regression.py` — `test_collapsed_table_renders_8_columns_with_chevron`: full-page render with `vm.active_recommendations` populated → 8 `<th>` elements; chevron button per row; close-button NOT present (tr is not yet expanded).
- `test_hyp_recs_collapsed_does_not_render_expansion_partial`: ensure the expansion partial is NOT pulled in via incidental include (HTMX OOB-swap drift discipline).
- `tests/web/view_models/test_hyp_recs_sort_neutrality.py` — `test_sort_unchanged_with_extended_recommendation_fields`: `prioritized_recommendations` order must be byte-for-byte identical between the pre-extension and post-extension `HypothesisRecommendation` shapes (snapshot test; covers compounding-confound regression).

### 4.5 CC pivot bug discriminating regression (`tests/web/templates/test_watchlist_pivot_column.py`)

The fix touches THREE render sites (per §3.9 R1-Major-3 resolution); each gets its own discriminating test.

- `test_dashboard_top5_pivot_column_renders_current_pivot`: full-page dashboard render with `WatchlistEntry(entry_target=42.00)` + `candidates_by_ticker={ticker: Candidate(pivot=44.50)}`. Rendered cell = `$44.50`. Discriminating against pre-fix: pre-fix path renders `$42.00`.
- `test_standalone_watchlist_pivot_column_renders_current_pivot`: standalone `/watchlist` page render — same fixture and assertion. (Standalone watchlist uses a different template wiring, so independent verification.)
- `test_watchlist_row_close_path_pivot_column_renders_current_pivot` (R1-Major-3 regression): GET `/watchlist/AAPL/row` (the close-button target) with `WatchlistEntry(entry_target=42.00)` + the candidate row present. Rendered cell = `$44.50`. Without the `WatchlistRowVM.current_pivot` extension, this would revert to `$42.00`, recreating the bug post-close.
- `test_pivot_column_falls_back_to_entry_target_when_no_candidate`: candidates_by_ticker = {}, entry_target = $42.00. Cell = `$42.00`.
- `test_pivot_column_dash_when_both_absent` (R1-Minor-3 regression): candidates_by_ticker = {}, entry_target = None. Cell = `—` (NOT `$0.00`).
- `test_lightning_trigger_unchanged_uses_entry_target`: discriminating fixture chosen so the trigger fires under `entry_target` binding but would NOT fire under `current_pivot` binding — `entry_target=$42.00`, `current_pivot=$100.00`, `price=$41.60`. Under entry_target binding: `41.60 ≥ 0.99 × 42 = 41.58` → lightning fires. Under current_pivot binding: `41.60 ≥ 0.99 × 100 = 99` → would NOT fire. Test asserts lightning DOES fire, proving the trigger binding survives the column-display change.

### 4.6 Close-button mechanism: full-section refresh (R1-Major-4 resolution)

**Decision: full-section refresh on close. NO per-row reconstruction route.**

Rejected alternative — symmetric `/hyp-recs/{ticker}/row` route mirroring `/watchlist/{ticker}/row` and `/trades/open/{trade_id}/row`. R1 review caught the asymmetry: a watchlist row is a stable projection of one persisted `WatchlistEntry`; a hyp-rec row is the output of matcher + prioritizer + top-N truncation + live-price fetch during `build_dashboard`. The set of recommendations and their ordering can change between expand and close (price tick crosses a tripwire threshold; pipeline completes; candidate rotates). A per-row reconstruction route would either:
1. **Re-run the prioritizer** (correct but expensive; close-button UX feels heavy on a long-running operation), OR
2. **Reconstruct from a frozen-at-expand snapshot** (cheap but stale; operator sees a value the rest of the page no longer agrees with).

Both fail the operator-clarity bar. Full-section refresh is the third option and the V1 choice:

- Close button on the expansion fires `hx-get="/hyp-recs/refresh"` with `hx-target="#hypothesis-recommendations"` and `hx-swap="outerHTML"`.
- The route handler (§3.5.4) calls `build_dashboard(...)` and renders `hypothesis_recommendations.html.j2` against the fresh result.
- The closing operator sees the page's current truth — same data the full-page reload would produce.

**Cost accepted:** one extra HTTP round-trip per close, and a re-render of the entire hyp-recs section (typically ≤ top-N rows, where N is small). On a small table this is imperceptible.

**Row-partial extraction.** The per-row markup is still extracted into `partials/hypothesis_recommendations_row.html.j2` so `hypothesis_recommendations.html.j2`'s `<tbody>` iterates via `{% include %}` instead of hand-duplicating row markup inline. This anticipates a V2 per-row close path (if the operator decides the full-section refresh's UX cost is too high after operational use) without requiring a template re-shape at that time.

**Implementation note.** `build_dashboard` requires `cache`, `executor`, and optional `ohlcv_cache` from `request.app.state` — the refresh route handler reuses the same accessors the full-page render path uses. No new caching layer; no new lifespan-scoped resource.

---

## 5. Phase 2 carve-outs

**None.** This dispatch is read-only with respect to `swing/data/` and `swing/trades/`:

- No new migrations (sector + industry already on `candidates`/`trades` from migration 0012; sizing twins reuse existing config + accessors).
- No `swing/data/repos/` changes beyond a possible `get_for_evaluation(conn, evaluation_run_id, ticker)` accessor on `swing/data/repos/candidates.py`. **Verification deferred to writing-plans dispatch:** if such an accessor already exists, no Phase 2 touch; if not, adding it is a Phase 2 carve-out with justification "single-row read against existing table; mirrors the dashboard's bulk-load pattern."
- No `swing/trades/` changes; no `EntryRequest` extension; no canonicalization.

The expansion is purely a NEW VM + NEW route + MODIFIED templates + NEW config field — Phase 3 territory throughout.

---

## 6. Adversarial-review watch items (for the wrapper)

Per the brief and the established chart-pattern flag-v1 §6 pattern. Surface these to the Codex critic during `copowers:brainstorming`'s adversarial round:

- **Locked-constraint violations.** Any spec text that adds an action button to V1, extends the watchlist or open-positions snapshots, hardcodes the chase factor, or changes the lightning trigger.
- **Toml-shadowing audit.** `chase_factor` field is fresh in `Web`; no row in `swing.config.toml` is added (Phase 5 surfaces all `Web` overrides together). Any spec text suggesting "add `chase_factor = 0.01` to swing.config.toml" introduces the multi-path-ingestion failure class.
- **Anchor consistency.** All three reads in the route handler (`latest_completed_pipeline_run`, `candidates_repo.get_for_evaluation`, `resolve_chart_scope`) MUST share one binding. No "latest by computed_at"; no "ORDER BY started_ts DESC" mid-pipeline-run masking.
- **Sort neutrality.** `prioritized_recommendations` and `_sort_watchlist` byte-for-byte unchanged. New fields on `HypothesisRecommendation` are trailing-default and never read by sort code paths.
- **Base-layout shared VM gotcha.** No new `vm.foo` field on `DashboardVM`. The new `HypRecsExpandedVM` is route-scoped, not part of `base.html.j2` references.
- **HTMX OOB-swap partial drift.** Flat-table row extracted to a shared partial (`hypothesis_recommendations_row.html.j2`); close-button `/row` endpoint and full-page `<tbody>` iteration both `{% include %}` the same target. No hand-duplicated row markup anywhere.
- **CLAUDE.md `os.replace` / yfinance gotchas.** Not applicable — this dispatch adds no filesystem-replace flows and no yfinance call sites.
- **Cross-surface pivot consistency.** After the CC bug fix, `candidates.pivot` is the value rendered on (a) hyp-recs flat table "Pivot" column, (b) hyp-recs expansion "Buy stop", (c) watchlist row "Pivot" column rendered from the dashboard top-5, (d) watchlist row "Pivot" column rendered from the standalone watchlist page, AND (e) watchlist row "Pivot" column rendered via the `/watchlist/{ticker}/row` close-path (R1-Major-3 — the close-path was missing in R0 and would have reverted to `entry_target` after every expand-close cycle). Lightning trigger stays bound to `entry_target` per Q4.
- **HTMX row-target prefix coverage.** `_ROW_TARGET_PREFIXES` includes `hyp-rec-row-` so that 4xx/5xx error fragments from the new route swap as `<tr>` rather than the generic `<div>` (R1-Major-2). Tested with both the 404 and forced-500 paths.
- **Snapshot-vs-precompute consistency.** No precomputation of expansion-only data on `HypothesisRecommendation` (R1-Major-1). All sizing, sector, industry, current_balance flow through the route-local `build_hyp_recs_expanded` helper. The "snapshot-at-render" invariant in §2.2 has no carve-outs.
- **Close-button mechanism.** Full-section refresh via `/hyp-recs/refresh` (R1-Major-4). The route returns the page's CURRENT hyp-recs section, not a frozen-at-expand reconstruction. Operator who closes after a pipeline run completes sees the new state.
- **Sizing same-source check.** `current_balance` value used by the expansion is computed from the SAME `current_equity` accessor `build_dashboard` already invokes for its existing equity strip. The dashboard's equity display and the expansion's cash-feasible label agree by construction.
- **Discriminating tests.** Each test in §4 differs from its pair / regression target by ONE feature; lightning-trigger discriminator constructs price-fixture values explicitly between `0.99 × entry_target` and `0.99 × current_pivot`.
- **Snapshot-at-render purity.** Expansion VM is computed on the route handler thread, never persisted, never carried into a subsequent entry submission as hidden form values. Q-K (ToCToU) is moot under §3.7 information-only resolution.
- **Operator-judgment-call escalations.** The brief's premise about an existing Enter button on hyp-recs is empirically wrong. Spec resolves Q-D against the corrected premise (information-only); flagged in §1.2 and the return report. Codex round may surface this as a finding — disposition is "operator-judgment-call corrections handled at brief level; spec proceeds on the empirical evidence."

---

## 7. Migration / rollout

1. **No migration.** Schema unchanged; first deploy after merge takes effect immediately.
2. **First page-render after deploy** shows the new chevron column on the flat hyp-recs table. Operator click triggers the route handler.
3. **Configuration default** — `cfg.web.chase_factor = 0.01` ships as code default. Operators who want a different chase factor in V1 add a `[web]` row to their local `swing.config.toml` (deliberate opt-in until Phase 5 ships the editor). Spec calls out this asymmetry in §3.1.
4. **CC pivot bug fix** lands as a separate task in the same merge; watchlist `Pivot` column starts rendering current-eval pivot on the next page load.

**Residual integrity acceptances:**
- **Snapshot-at-render staleness.** A user keeps the expansion open through a pipeline run; the displayed values become stale. Mitigation: the "As of pipeline finished <ISO>" footer signals when the snapshot was captured. V2 candidate: HTMX SSE/polling to invalidate open expansions on pipeline-run completion.
- **Pivot rotation between full-page and expansion request.** A ticker shown in `active_recommendations` at full-page render may have rotated out by the time the operator clicks expand (rare; would require a pipeline run completing in that window). The route handler returns 404 with the operator-facing "Not a current candidate or pivot data missing." message; operator re-loads the dashboard.

---

## 8. Open follow-ups (V2 candidates, NOT in V1 scope)

- "Take this trade" action button on the expansion (with explicit pre-fill plumbing + ToCToU handling per chart-pattern flag-v1 §3.6). Operator may instead prefer adding an Enter button directly to the hyp-recs row (cleaner; matches watchlist's row-level Enter button).
- Configuration-page UI for `chase_factor` (Phase 5 of the operator sequence).
- Risk-display on cost numbers — show `risk_dollars` and `risk_pct` for both the risk-based and cash-feasible regimes.
- Multi-trade preview: select multiple hyp-recs, see aggregate cost and total risk exposure across the selection.
- Sector concentration warning (V2 follow-up of the sector dispatch; gated on shipping the data which is now done).
- Lightning trigger logic re-evaluation (Tier-3 #5 — operator-paced design conversation; this dispatch preserves current behavior per Q4).
- HTMX SSE/polling to invalidate open expansions on pipeline-run completion (snapshot-at-render staleness mitigation).
- Mobile/responsive design (Q-M).
- Tooltip on the lightning icon explaining the `entry_target` binding (only if the visual confusion described in §3.8 proves operationally costly).
- Sort-PARTICIPATING fields from the expansion (any sizing/cost/sector value entering the prioritizer or `_sort_watchlist`). V2 only after the operator validates that snapshot-derived values should influence ordering.

---

## 9. Done criteria

- [ ] `Config.web.chase_factor: float = 0.01` field added; no toml row introduced.
- [ ] `HypothesisRecommendation` extended with eight trailing-default fields; existing call sites unchanged.
- [ ] `HypRecsExpandedVM` dataclass exists; `build_hyp_recs_expanded` returns it on the happy path and `None` on rotation / no-run / degenerate-sizing.
- [ ] `GET /hyp-recs/{ticker}/expand` returns the expansion partial; 404 for unknown / rotated tickers; chart-unavailable div for out-of-scope tickers.
- [ ] `GET /hyp-recs/{ticker}/row` returns the collapsed-row partial (close-button target).
- [ ] Hyp-recs flat table gains the chevron column; full-page render is otherwise byte-for-byte identical to baseline (regression test §4.4).
- [ ] Watchlist `Pivot` column renders `candidates.pivot` when the ticker has a candidate row; falls back to `WatchlistEntry.entry_target` when not.
- [ ] Lightning trigger on watchlist row stays bound to `entry_target` (regression test §4.5).
- [ ] Sizing twins (risk-based + cash-feasible) computed and rendered with two-row layout; infeasibility path renders the `infeasible (constraint)` annotation.
- [ ] Sector + Industry rendered in the Context group; empty strings render as `"—"`.
- [ ] "As of pipeline finished <ISO>" footer present on the expansion.
- [ ] All four test layers green; sort-neutrality regression confirmed; CC pivot discriminating regression confirmed.
- [ ] Adversarial Codex review reaches `NO_NEW_CRITICAL_MAJOR`.
- [ ] No new migration; no new repo function beyond a single optional `get_for_evaluation` accessor (verified at writing-plans).
- [ ] Toml-shadowing audit recorded clean for `chase_factor` (no row added; phase3e-todo retains the asymmetry note).

---

## 10. References

- Brief: `docs/hyp-recs-trade-prep-expansion-brainstorming-brief.md`
- Phase 3e backlog source-of-truth: `docs/phase3e-todo.md` §"2026-04-28 hyp-recs trade-preparation expansion"
- Precedent spec structure: `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`
- Phase 1 sector dispatch (just shipped 2026-04-29): `docs/superpowers/plans/2026-04-28-sector-industry-capture-plan.md`; spec at `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md` (precedent structure); brief at `docs/sector-industry-capture-writing-plans-brief.md`.
- Tier-2 #2/#3 chart-access UX (2026-04-27): commit chain `772d69b..a5fdc75`; `swing/web/routes/charts.py`; `swing/web/templates/partials/open_positions_expanded.html.j2`.
- Watchlist row expand: `swing/web/templates/partials/watchlist_expanded.html.j2` (Sector/Industry rows added 2026-04-29).
- Hypothesis-recommendation engine framing (2026-04-25): `docs/orchestrator-context.md` "Recent decisions and framings" — "dashboard PROPOSES, operator DISPOSES."
- Entry discipline (2026-04-25): "wait for pivot, don't chase >1% above pivot" — the empirical source of the chase_factor default.
- Capital risk floor convention: project memory `project_capital_risk_floor.md`.
- Multi-path-ingestion lesson (2026-04-29): `docs/orchestrator-context.md` "Lessons captured."
- Toml-shadowing prior lesson (`aeb2084`): `docs/orchestrator-context.md` "Lessons captured."
- HTMX OOB-swap partial drift gotcha: `CLAUDE.md` "Gotchas" section.
- Base-layout 5-VM rule: `CLAUDE.md` "Gotchas" — `DashboardVM`, `PipelineVM`, `JournalVM`, `WatchlistVM`, `PageErrorVM` propagation.
- Pipeline_runs ORDER BY discipline: `CLAUDE.md` "Gotchas" — most-recent-completed vs most-recent-started two-read pattern.
- Sort-neutrality structurally guaranteed precedent: chart-pattern flag-v1 spec §3.5 (`_pattern_tags` sibling-helper architecture).
- Discriminating-test arithmetic discipline: `feedback_regression_test_arithmetic` memory.
- Sizing pipeline: `swing/recommendations/sizing.py`; `swing/trades/equity.py:sizing_equity`, `current_equity`.
- Candidates schema: `swing/data/migrations/0001_phase1_initial.sql:24-46` (pivot, initial_stop columns).
- Sector/Industry schema: `swing/data/migrations/0012_sector_industry.sql` (NOT-NULL DEFAULT '' semantic).
