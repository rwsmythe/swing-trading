# Phase 3e — Hyp-recs trade-prep expansion V1 (design)

**Baseline:** `main` at commit `4ba9c62` (hyp-recs trade-prep expansion brainstorming dispatch brief). Fast suite ~974 tests green as of 2026-04-25 (per CLAUDE.md Quick Start; exact count pinned at writing-plans dispatch per the project's standing test-count-drift discipline). schema_version = 12 (after 2026-04-29 sector/industry capture, migration 0012).

**Goal:** Convert the hyp-recs panel from a flat 7-column read-only table into a click-to-expand surface that shows the operator's full trade-preparation context for each recommendation: order parameters (buy stop = pivot, buy limit = pivot × (1 + chase_factor), sell stop = framework's initial stop), sizing in two complementary regimes (risk-based using the $7,500 floor, cash-feasible capped at the actual current balance), context (sector, industry), and an inline chart when in chart-scope. Adds **two action surfaces** per Q7 + Q8 (operator-locked 2026-04-29): a per-row "Enter" button (mirrors watchlist's pattern; serves the "I'm already convinced, commit immediately" workflow) AND a "Take this trade" button inside the expansion (serves the "let me verify the snapshot first" workflow). Bundles a small bug fix on the watchlist `Pivot` column (renders the frozen-at-add `entry_target` under a header that says `Pivot`; the fix renders `candidates.pivot` from the latest evaluation, matching what hyp-recs already does).

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

7. **Per-row Enter button on hyp-recs table.** Operator-locked 2026-04-29 (commit `427ef95`). Each hyp-rec row gains an "Enter" action that takes the operator to the entry form for the row's ticker, mirroring the existing watchlist Enter button at `partials/watchlist_row.html.j2:32`. The pre-fill pipeline (commit chain `b24506b → fe270a6`, 2026-04-25) auto-populates `hypothesis_label`, `chart_pattern_*`, `sector`, and `industry` on entry-form render. Closes the workflow gap that the prior brief draft mistakenly referred to as "an existing Enter button" — verified pre-Q7, the partial had zero in-row action affordances. (Spec resolves D.1 + D.5 per §3.7.)

8. **"Take this trade" button INSIDE the expansion.** Operator-locked 2026-04-29 (same commit). IN ADDITION TO Q7 (not instead of). When the operator expands a row to verify the snapshot, the action button is right there — no need to close the expansion to commit. Visual treatment + pre-fill semantics resolved in §3.7 (D.2-D.4); existence of the button is locked.

### 1.3 What V1 ships

1. **`Config.web.chase_factor`** — single new config field, default 0.01, no migration (pure Python).
2. **One new VM dataclass** — `HypRecsExpandedVM` (route-local, snapshot-on-click), rendered by the new partial `partials/hypothesis_recommendations_expanded.html.j2`. **Existing `HypothesisRecommendation` is unchanged** — sizing twins, sector, industry, current_balance live ONLY on `HypRecsExpandedVM` and are computed at click time, NOT precomputed on the collapsed-table render. (R1-Major-1 resolution: keeps the §2.2 snapshot-at-render invariant honest; §1.3 and §2.3 no longer contradict it.)
3. **Two new route handlers** — `GET /hyp-recs/{ticker}/expand` returns the expansion partial; `GET /hyp-recs/refresh` returns the freshly-rendered hyp-recs section (used by the close button — see §3.5.4 / §4.6 for the rejected per-row reconstruction path; R2-Major-2 resolution scopes the refresh handler to a hyp-recs-only builder, NOT a full `build_dashboard` rebuild).
4. **Row-target prefix extension** — `_ROW_TARGET_PREFIXES` in `swing/web/app.py:31-37` extended to include `hyp-rec-row-` so HTMX 4xx/5xx error fragments swap as `<tr>` rather than `<div>` (R1-Major-2 resolution; the current tuple covers `open-position-`, `entry-form-`, `exit-form-`, `stop-form-`, `watchlist-row-` only).
5. **Modified template** — `partials/hypothesis_recommendations.html.j2` gains a leading chevron column AND a trailing Enter-button column; the per-row markup is extracted into `hypothesis_recommendations_row.html.j2` (used only by the full-table render in V1 — see §4.6 rationale).
6. **Per-row "Enter" button on each hyp-recs row** (Q7) — mirrors the watchlist Enter button at `partials/watchlist_row.html.j2:32` exactly: HTMX `hx-get="/trades/entry/form?ticker={ticker}"`, `hx-target="closest tr"`, `hx-swap="outerHTML"`. Reuses the existing `entry-form-` row-target prefix; reuses the existing per-ticker pre-fill pipeline (auto-populates `hypothesis_label`, `chart_pattern_*`, `sector`, `industry` at form render). NO `event.stopPropagation()` needed because the row itself is NOT an HTMX trigger (Q-C resolution made the chevron column the expand trigger). See §3.7 D.1 + D.5.
7. **"Take this trade" button INSIDE the expansion** (Q8) — uses the SAME query-param mechanism as the per-row Enter button (D.2 = option (a) per §3.7 rationale): HTMX `hx-get="/trades/entry/form?ticker={ticker}"`, `hx-target="closest tr"`, `hx-swap="outerHTML"`. Visually differentiated from the per-row Enter button per D.3 (different label "Take this trade"; positioned with the Order parameters group; primary-action styling). The expanded-row-replaced-by-entry-form swap implicitly closes the expansion. ToCToU window is identical-class to the per-row Enter button (D.4); no new ToCToU class introduced.
8. **Bundled CC pivot bug fix** — separate task in the writing-plans output (see §3.9): `partials/watchlist_row.html.j2:16` switches from `w.entry_target` to a `current_pivot` lookup. The fix touches THREE render sites: `partials/watchlist_top5_section.html.j2` (dashboard top-5), `watchlist.html.j2` (standalone page), AND `WatchlistRowVM` (`swing/web/view_models/watchlist.py:50-64`) so the watchlist's `/watchlist/{ticker}/row` close-path doesn't revert the column to `entry_target` after expand-close (R1-Major-3 + R2-Major-1 resolution). Lightning trigger at line 7 stays unchanged.
9. **Tests across four layers** — unit (sizing-twin compute), VM (HypRecsExpandedVM build + anchor), route (HTMX expand + scoped refresh + chart-scope fallback + row-target-prefix coverage + per-row Enter button + expansion Take-this-trade button), template (regression on flat table, per-row Enter markup mirrors watchlist, regression on watchlist Pivot column across all three render sites).

### 1.4 What V1 does NOT ship (deferred)

- Extended-snapshot pre-fill (D.2 option (b)) — carrying `buy_stop`, `sell_stop`, `shares`, `notional` into the entry form via hidden inputs / POST body to eliminate the ToCToU window between expansion render and form render. V1 picks the simpler query-param mechanism (D.2 = option (a)); V2 candidate if operators report ToCToU pain in operational use.
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
- **Production MODIFY (12):**
  1. `swing/config.py` — one new `Web` field (`chase_factor`).
  2. `swing/web/view_models/dashboard.py` — add `HypRecsExpandedVM` + `build_hyp_recs_expanded` + `HypRecsSectionVM` + `build_hyp_recs_section` + `_build_active_recommendations` shared helper (R2-Major-2). `HypothesisRecommendation` UNCHANGED (per R1-Major-1).
  3. `swing/web/view_models/watchlist.py` — `WatchlistRowVM` gains `current_pivot: float | None = None` (R1-Major-3).
  4. `swing/web/view_models/trades.py` — `TradeEntryFormVM` gains `origin: Literal["watchlist","hyp-recs"] = "watchlist"` + `pipeline_finished_at: str | None`; `build_entry_form_vm` accepts `origin`, applies anchor-consistency logic per origin (R4-Major-2), extends candidate-row SELECT to fetch `pivot` + `initial_stop`, falls back to candidate values when `wl_entry` is None (R3-Major-1 + R3-Major-2 + R4-Major-2).
  5. `swing/web/routes/watchlist.py` — `/watchlist/{ticker}/row` populates `WatchlistRowVM.current_pivot` from `candidates_by_ticker`.
  6. `swing/web/routes/trades.py` — GET entry-form handler reads `?origin=` query param (whitelist-validated); POST `/trades/entry` handler reads form-payload `origin`; threads through `_rerender_entry_form_with_error()`, `DuplicateOpenPositionException` re-render, and soft-warn `form_values` (R3-Major-1 + R4-Major-1).
  7. `swing/web/app.py` — register the recommendations router AND extend `_ROW_TARGET_PREFIXES` to include `hyp-rec-row-` (R1-Major-2).
  8. `swing/web/templates/partials/hypothesis_recommendations.html.j2` — chevron leading column + Enter-button trailing column + iterate per-row partial.
  9. `swing/web/templates/partials/trade_entry_form.html.j2` — parameterize `colspan` + Cancel button `hx-get`/`hx-target` based on `vm.origin` (R3-Major-1) + hidden `origin` form field (R4-Major-1) + freshness footer when `vm.origin == 'hyp-recs'` (R4-Major-2).
  10. `swing/web/templates/partials/soft_warn_confirm.html.j2` — hidden `origin` form field + parameterized Cancel button so the soft-warn round-trip preserves the discriminator (R4-Major-1).
  11. `swing/web/templates/partials/watchlist_row.html.j2` — CC pivot bug fix at line 16 (R1-Minor-3 dash sentinel for missing both).
  12. **TWO parent templates that iterate watchlist rows (R2-Major-1 correction):** `swing/web/templates/partials/watchlist_top5_section.html.j2` (dashboard top-5 path; `dashboard.html.j2:15` includes this section but does NOT iterate rows directly) AND `swing/web/templates/watchlist.html.j2` (standalone watchlist page). Each gains `{% set current_pivot = vm.candidates_by_ticker[w.ticker].pivot if w.ticker in vm.candidates_by_ticker else None %}` immediately before the `{% include "partials/watchlist_row.html.j2" %}`. (Counted as one MODIFY entry but two file edits — finalized at writing-plans dispatch.)
- **Test NEW (6):** the six files listed in the `tests/` block.

Total: **22 files** (4 production NEW + 12 production MODIFY + 6 test NEW; the test count expands at writing-plans dispatch as the entry-form-integration tests in §3.8b.2-§3.8b.4 + §4.3 land). No migrations. No Phase 2 carve-outs (see §5).

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
    """Close-button target. Returns ONLY the freshly-rendered hyp-recs section
    so the closing operator sees current hyp-recs values without rebuilding
    open-trades, watchlist top-5, prices for non-recommended tickers, or
    OHLCV (R2-Major-2 — scoped builder, NOT a full build_dashboard call).

    Cross-panel snapshot consistency caveat: the swap target is
    #hypothesis-recommendations only — other dashboard sections retain
    their full-page-render snapshot. This is inherent to the partial-swap
    UX and is the intentional V1 trade: cheap close action, accept that
    other panels remain at their last full-render snapshot.
    """
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    section_vm = build_hyp_recs_section(cfg=cfg, cache=cache, executor=executor)
    return templates.TemplateResponse(
        request, "partials/hypothesis_recommendations.html.j2",
        {"vm": section_vm}, status_code=200,
    )
```

**Scoped section builder (`build_hyp_recs_section`)** lives in `swing/web/view_models/dashboard.py` adjacent to `build_dashboard` and is constructed by extracting the existing recommendation-construction logic into a shared helper. R2-Major-2 motivation: the refresh route MUST NOT depend on subsystems unrelated to hyp-recs (open-positions ohlcv, watchlist top-5 sorting, advisories computation) — those are unrelated failure modes that would couple a simple close-button click to the entire dashboard's wellness.

```python
@dataclass(frozen=True)
class HypRecsSectionVM:
    """Sub-VM shaped exactly as the hypothesis_recommendations.html.j2
    partial expects (`vm.active_recommendations`). Returned by
    GET /hyp-recs/refresh; renders the same flat-table chevron + Enter
    column markup the full-page render produces."""
    active_recommendations: tuple[HypothesisRecommendation, ...]


def _build_active_recommendations(
    *, conn, cfg, prices: Mapping[str, PriceSnapshot],
    candidates_by_ticker: Mapping[str, Candidate],
) -> tuple[HypothesisRecommendation, ...]:
    """Shared helper extracted from build_dashboard. Constructs the
    active_recommendations tuple given the prerequisites. Both
    build_dashboard (full page) and build_hyp_recs_section (refresh
    route) call this — single source of truth for recommendation
    construction logic."""
    # ... (existing top_recommendations + progress_by_id + tripwire_reason
    # logic, unchanged from build_dashboard's current implementation at
    # swing/web/view_models/dashboard.py:540-581) ...


def build_hyp_recs_section(*, cfg, cache, executor) -> HypRecsSectionVM:
    """Refresh-route VM builder. Resolves ONLY the data needed for the
    hyp-recs section: candidates_by_ticker (for pivot_price), prices for
    the recommended tickers (subset, NOT the full watchlist), and the
    progress/registry data the prioritizer needs. Does NOT touch
    open-trade ohlcv, watchlist top-5, advisories, status strip."""
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            candidates = fetch_candidates_for_run_via_pipeline_binding(conn)
            candidates_by_ticker = {c.ticker: c for c in candidates}
            top_recommendations = prioritize_recommendations(conn)
            recommended_tickers = sorted({r.candidate_ticker for r in top_recommendations})
            prices = cache.get_prices(recommended_tickers, executor=executor)
            active_recommendations = _build_active_recommendations(
                conn=conn, cfg=cfg, prices=prices,
                candidates_by_ticker=candidates_by_ticker,
            )
            return HypRecsSectionVM(active_recommendations=active_recommendations)
    finally:
        conn.close()
```

The `cache.get_prices(recommended_tickers, ...)` scope keeps the price fetch narrow (typically 1–10 tickers vs the full watchlist's 20–50). PriceCache's existing graceful-degradation path (last-close fallback when fetch deadline misses) applies unchanged. The refresh route inherits zero new failure modes from open-positions / watchlist / advisories paths.

**`build_dashboard` refactor:** `build_dashboard` is updated to call `_build_active_recommendations` instead of inlining the loop — single source of truth. The existing recommendation-construction logic at `swing/web/view_models/dashboard.py:540-581` is moved into the new helper without semantic change.

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

Current state: 7-column read-only table, no row interactivity. Modified state: **9 columns** — leading chevron, the seven existing columns, and a trailing Enter-button column (Q7):

```jinja
<thead>
  <tr>
    <th aria-label="Expand"></th>     {# NEW: chevron column (col 1) #}
    <th>Ticker</th>
    <th>Price</th>
    <th>Pivot</th>
    <th>Hypothesis</th>
    <th>Progress</th>
    <th>Tripwire</th>
    <th>Suggested label</th>
    <th aria-label="Action"></th>     {# NEW: per-row Enter button (col 9) #}
  </tr>
</thead>
<tbody>
  {% for rec in vm.active_recommendations %}
    {% include "partials/hypothesis_recommendations_row.html.j2" %}
  {% endfor %}
</tbody>
```

The per-row partial (`hypothesis_recommendations_row.html.j2`):

```jinja
{#- Expects: rec (HypothesisRecommendation) -#}
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
  <td>{% if rec.current_price is not none %}${{ "%.2f"|format(rec.current_price) }}{% else %}—{% endif %}</td>
  <td>{% if rec.pivot_price is not none %}${{ "%.2f"|format(rec.pivot_price) }}{% else %}—{% endif %}</td>
  <td>{{ rec.hypothesis_name }}</td>
  <td>{{ rec.hypothesis_progress_n }} / {{ rec.hypothesis_progress_target }}</td>
  <td>{% if rec.tripwire_fired %}<strong>FIRED</strong>: {{ rec.tripwire_reason or "" }}{% else %}—{% endif %}</td>
  <td title="{{ rec.suggested_label }}">{{ rec.suggested_label[:60] }}{% if rec.suggested_label|length > 60 %}…{% endif %}</td>
  <td>
    {#- Per-row Enter button (Q7). Mirrors watchlist_row.html.j2:31-35 markup
        for operator muscle memory. NO event.stopPropagation needed because
        the <tr> itself is NOT an HTMX trigger — only the chevron and Enter
        buttons are (Q-C / D.5 resolution). -#}
    <button type="button"
            hx-get="/trades/entry/form?ticker={{ rec.ticker }}"
            hx-target="closest tr"
            hx-swap="outerHTML"
            hx-headers='{"HX-Request": "true"}'>Enter</button>
  </td>
</tr>
```

**HTMX expansion mechanics (Q-C resolution):** **dedicated chevron column with explicit button click — NOT row-level `hx-get`.**

Rejected alternative: row-level `hx-get` (mirroring watchlist's pattern at `partials/watchlist_row.html.j2:3-5`). Rationale for rejection:
1. **Existing architectural concern (Bug 1 follow-up).** Watchlist's row-level click pattern means EVERY interactive child (the existing `Enter` button at `:31`) needs `event.stopPropagation()`. With Q7 + Q8 adding two MORE buttons (per-row Enter + expansion Take-this-trade), choosing row-level click would force `stopPropagation` on three buttons. Chevron-as-trigger sidesteps this entirely (D.5 resolution: row is NOT a trigger; no stopPropagation anywhere on the hyp-recs surface).
2. **Affordance clarity.** A leading chevron is a stronger visual cue ("this row expands") than a hover-state on the whole row.
3. **Accessibility.** Both the chevron and the Enter button are keyboard-focusable, screen-reader-labelled, and operate via explicit click — a row-level click is not.

Cost accepted: nine columns total (chevron + 7 existing + Enter). Hyp-recs is a narrow table (mostly numeric content); two narrow control columns at column-1 and column-9 do not push the table past readable width. The chevron column is `width:1.5em`; the Enter-button column is `width:5em` (matches watchlist).

**Entry-form colspan compatibility (writing-plans concern, surfaced for tracking):** the per-row Enter button's HTMX swap replaces the `<tr>` with the entry form `<tr>`. The entry form template's `colspan` must accommodate the 9-cell hyp-recs row. Watchlist row is 7 cells; if the entry-form template hardcodes 7, writing-plans dispatch determines whether to (a) parameterize the colspan or (b) accept a visual quirk (colspan mismatch in HTML degrades to "extra/missing trailing cell"). Ditto for the expansion's "Take this trade" swap (replacing the 9-colspan expanded `<tr>`).

#### 3.5.6 New partial: `hypothesis_recommendations_expanded.html.j2`

```jinja
{#- Expects: expanded (HypRecsExpandedVM) -#}
<tr id="hyp-rec-row-{{ expanded.ticker }}" class="expanded">
  <td colspan="9">
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

    <p class="action-row">
      {#- Q8: "Take this trade" button (D.2 = option (a) query-param mechanism;
          D.3 differentiated label + primary-action styling). HTMX swap
          replaces the expanded <tr> with the entry form <tr> — the swap
          implicitly closes the expansion. NO stopPropagation needed
          (D.5: row is not a trigger). -#}
      <button type="button" class="take-this-trade primary"
              hx-get="/trades/entry/form?ticker={{ expanded.ticker }}"
              hx-target="closest tr"
              hx-swap="outerHTML"
              hx-headers='{"HX-Request": "true"}'>Take this trade</button>
    </p>

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

### 3.7 Action-button design (Q-D, post Q7 + Q8 update)

The dispatch brief was updated 2026-04-29 (commit `427ef95`) to lock both a per-row Enter button (Q7) AND a "Take this trade" button inside the expansion (Q8). §3.D in the brief now is a 5-sub-question section (D.1–D.5) on implementation details. Resolutions:

#### D.1 — Per-row Enter button styling + structure

**Resolution: mirror the watchlist Enter button exactly.** Markup verified at `partials/watchlist_row.html.j2:31-35` is `<button hx-get="/trades/entry/form?ticker={ticker}" hx-target="closest tr" hx-swap="outerHTML" hx-headers='{"HX-Request": "true"}'>Enter</button>`. Hyp-recs row's per-row button is byte-equivalent except the `event.stopPropagation()` is dropped — the watchlist needs it because the row itself is an HTMX trigger (`<tr hx-get="/watchlist/{ticker}/expand">` at `:3-5`); the hyp-recs row's chevron-button-driven expansion (Q-C resolution; §3.5.5) means the `<tr>` is NOT a trigger and the button click does not need to stop bubbling. Operator muscle memory (label "Enter", trailing column, primary-default styling) is preserved across surfaces.

**Rejected alternatives:**
- Differentiate label ("Take this trade" / "Buy") on the per-row button — defeats the muscle-memory goal. The per-row Enter is the immediate-commit affordance; the differentiated label belongs ONLY on the expansion-internal button (D.3).
- Place the Enter button in a different column position (e.g., column 2 next to ticker) — increases visual-density confusion vs the established Action-column pattern.

#### D.2 — Expansion-internal button: pre-fill semantics

**Resolution: option (a) — same query-param mechanism as the per-row Enter button.** Both buttons fire `hx-get="/trades/entry/form?ticker={rec.ticker}"` and rely on the existing per-ticker pre-fill pipeline (`hypothesis_label`, `chart_pattern_*`, `sector`, `industry` auto-populated at form-render time from the candidate row).

**Rejected alternative — option (b) extended snapshot pre-fill via hidden inputs / POST body:**
1. **Plumbing cost.** Carrying `buy_stop`, `buy_limit`, `sell_stop`, `shares`, `notional` would require: (i) extending the entry-form route to accept these as request params; (ii) wiring them into `EntryRequest` / `TradeEntryFormVM`; (iii) extending the soft-warn round-trip to preserve them across confirmation reload (Phase 5 R1 Major 2 lesson); (iv) extending the form's hidden-input set so a POST submit re-presents them. That's a four-touchpoint plumbing change for a single optimization.
2. **Threat model surface area.** Hidden-input snapshot carry is operator-claimed input, not server-verified provenance — the chart-pattern flag-v1 §3.6 threat model already accepts this for `chart_pattern_*` and the `pipeline_run_id` audit anchor. Adding more hidden-input fields broadens the surface area of "operator can submit any value they like by manipulating the form."
3. **ToCToU pain unconfirmed.** The brief flags ToCToU as the rationale for option (b), but operationally the operator's click → form-render path completes within 100ms typically. A pipeline run completing in that window is a rare event class. V1 ships the cheap path; if operators report ToCToU pain in operational use, V2 can tighten with option (b) — the spec captures this as the V1.4 deferred item.
4. **Consistency with per-row Enter button.** Choosing (a) makes BOTH buttons use the SAME mechanism. Choosing (b) for the expansion button only would create two distinct entry-form-render code paths (one query-param-only, one extended-snapshot). One mechanism is easier to reason about and easier to test.

**Q-D.2.i (which shares figure carries) is moot under option (a)** — neither figure is carried; the entry form uses its existing sizing recomputation (`compute_shares` at form-render) and the operator manually selects the desired figure if they want to override.

#### D.3 — Visual differentiation between per-row Enter and expansion-internal button

**Resolution: differentiate by label and styling.**
- **Per-row Enter button:** label "Enter", default-button styling (matches watchlist exactly).
- **Expansion-internal button:** label "Take this trade", primary-action styling (visual weight: bolder, full-width inside the Order-parameters group, accent-color background). Positioned immediately below the Order-parameters list — the operator's eye flow is "verify the buy window → click Take this trade."

Rationale: the two buttons serve different operator workflows:
- The per-row Enter is the "I already know what I want; commit immediately" path. The default-button visual treatment is correct — Don't Make Me Think; predictable.
- The expansion's Take this trade is the "I just verified the snapshot; commit with confidence" path. Primary-action styling reinforces the workflow intent ("you've earned this click").

**Rejected alternative: visually identical buttons.** Same label and styling would create the wrong cognitive frame — "is this a duplicate of the per-row button or something different?" Differentiation eliminates the moment of confusion.

#### D.4 — ToCToU class implication

**Under D.2 = option (a), no NEW ToCToU class is introduced.** Both buttons inherit the existing per-ticker entry-form ToCToU window (the entry form re-resolves from candidate at form-render; if the candidate row changed between operator click and form-render, the form shows the new value). This is the SAME ToCToU class as the existing watchlist Enter button — V1 does not add a third ToCToU surface.

The spec's existing snapshot-at-render purity invariant (§2.2) is preserved: the expansion's display values are computed at click-to-expand time, NOT carried into the subsequent entry-form-render. The Take this trade button's behavior is "navigate to the standard entry form for this ticker"; the operator cannot accidentally submit stale snapshot values.

**Soft-warn round-trip compatibility (Phase 5 R1 Major 2):** since neither button carries new hidden inputs, the existing soft-warn confirm round-trip is unchanged; no new fields need to survive the re-render.

If V2 adopts option (b) (extended snapshot pre-fill), §3.7 D.4 is the natural extension point; the threat model + hidden-input survival across soft-warn would require explicit treatment at that time.

#### D.5 — Per-row Enter button accessibility / `stopPropagation` cross-coupling

**Cross-coupled with §3.5.5 Q-C resolution: chevron column expansion mechanism.** Because the hyp-recs `<tr>` is NOT itself an HTMX trigger (only the chevron button and the Enter button are), the per-row Enter button does NOT need `event.stopPropagation()`. The watchlist's `stopPropagation` is needed because watchlist's `<tr>` IS a trigger; copying it on the hyp-recs Enter button would be defensive cargo-cult (no harmful effect, but signals a pattern that doesn't apply here).

**This is a genuine architectural improvement over the watchlist's pattern.** The Bug-1-follow-up "Watchlist row HTMX trigger architecture refactor" (orchestrator-context recent-decisions) flags the watchlist's row-trigger + child-button pattern as an architectural smell to be revisited. Hyp-recs ships the cleaner pattern from V1, demonstrating an alternative path forward — relevant for the future watchlist refactor.

#### Cross-cutting workflow summary

Two operator workflows the dual-button design serves:

| Operator state | Action | Outcome |
|---|---|---|
| "I'm convinced; commit immediately" | Click per-row "Enter" button (column 9). | Row swaps with entry form via HTMX. |
| "Let me verify the snapshot first" | Click chevron (column 1) → review expansion → click "Take this trade" button. | Expanded row swaps with entry form via HTMX. |
| "Let me verify but not commit yet" | Click chevron → review → click ✕ close. | Section refresh via `/hyp-recs/refresh`; operator continues scanning. |

All three use the SAME entry-form route + pre-fill pipeline; only the entry surface (per-row vs expansion vs none) differs.

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

### 3.8b Origin-aware entry-form integration (R3-Major-1 + R3-Major-2)

The Q7/Q8 buttons reuse the existing `/trades/entry/form?ticker=...` route, which renders `partials/trade_entry_form.html.j2`. R3 review caught two product gaps that this reuse exposes — neither was triggered pre-Q7/Q8 because the watchlist Enter button is the only existing caller and it always returns to the watchlist surface.

#### 3.8b.1 Colspan + Cancel-target parameterization (R3-Major-1)

Verified at baseline `4ba9c62`:
- `partials/trade_entry_form.html.j2:4` hardcodes `<td colspan="8">`.
- `partials/trade_entry_form.html.j2:72-74` hardcodes Cancel button `hx-get="/watchlist/{{ vm.ticker }}/expand"`.

Two failure modes when reused from hyp-recs:
1. **Colspan mismatch.** A 9-column hyp-recs row swapped to a colspan-8 entry form leaves a stray cell at column 9 (the entry form's right edge ends one column shy of the table's right edge); cosmetic but visually broken.
2. **Cancel target dead-link.** Cancel from a hyp-recs-originated form fires `/watchlist/{ticker}/expand`. If the ticker is on the watchlist, the operator is teleported to a watchlist row that they weren't viewing — disorienting. If the ticker is NOT on the watchlist, the route 404s.

**Resolution: parameterize `colspan` + `cancel_hx_get` + `cancel_hx_target` on `TradeEntryFormVM` via an `origin` discriminator.**

`TradeEntryFormVM` gains:

```python
origin: Literal["watchlist", "hyp-recs"] = "watchlist"   # NEW (default preserves existing behavior)
```

The template at `partials/trade_entry_form.html.j2` parameterizes:

```jinja
<tr id="entry-form-{{ vm.ticker }}">
  <td colspan="{{ 9 if vm.origin == 'hyp-recs' else 8 }}">
    ...
    <button type="button"
            hx-get="{{ '/hyp-recs/refresh' if vm.origin == 'hyp-recs' else '/watchlist/' ~ vm.ticker ~ '/expand' }}"
            hx-target="{{ '#hypothesis-recommendations' if vm.origin == 'hyp-recs' else 'closest tr' }}"
            hx-swap="outerHTML"
            hx-headers='{"HX-Request": "true"}'>Cancel</button>
```

Server-side validation: the route handler accepts `?origin={watchlist,hyp-recs}` as a query param. Unknown values default to `"watchlist"` (the safe default — preserves existing behavior for any caller that doesn't send the param). The validation is whitelist (server-controlled enum), NOT pass-through string — closes the URL-injection threat surface that would otherwise let an operator submit `?origin=javascript:...` and have the template emit it as a Cancel `hx-get` target.

The hyp-recs per-row Enter and Take-this-trade buttons append `&origin=hyp-recs` to their `hx-get`:
```jinja
hx-get="/trades/entry/form?ticker={{ rec.ticker }}&origin=hyp-recs"
```

The watchlist Enter button is unchanged (no `origin` param → defaults to `watchlist`).

**Cancel behavior for hyp-recs origin:** Cancel fires `/hyp-recs/refresh` with `hx-target="#hypothesis-recommendations"` `hx-swap="outerHTML"` — same mechanism as the expansion's close button (§3.5.4). The Cancel target is the same regardless of whether the entry form was reached via per-row Enter (collapsed-row swap) or Take-this-trade (expanded-row swap); both unwind to the flat-table state. (R3-Minor-1 disposition: documented explicitly.)

#### 3.8b.2 Off-watchlist `initial_stop` + `entry_target` fallback (R3-Major-2)

Verified at baseline `4ba9c62`, `swing/web/view_models/trades.py:142`:
```python
initial_stop = wl_entry.initial_stop_target if wl_entry and wl_entry.initial_stop_target else 0.0
```

When the operator clicks Enter or Take-this-trade on a hyp-recs row whose ticker is NOT on the active watchlist, `wl_entry` is `None` and `initial_stop` falls back to `0.0`. The form renders a stop field of `$0.00`, defeating the point of having just verified the snapshot in the expansion.

**Resolution: extend `build_entry_form_vm` to fall back to `candidates_by_ticker[ticker]` when `wl_entry` is `None`.**

The existing candidate fetch at `swing/web/view_models/trades.py:121-129` already reads `sector` and `industry` from the latest evaluation's candidate row. Extend the SELECT to also fetch `pivot` and `initial_stop`. Then:

```python
# After the existing wl_entry / candidate-row reads:
if wl_entry is not None and wl_entry.initial_stop_target:
    initial_stop = wl_entry.initial_stop_target
elif cand_initial_stop is not None:
    initial_stop = cand_initial_stop
else:
    initial_stop = 0.0

if wl_entry is not None and wl_entry.entry_target:
    entry_target_for_form = wl_entry.entry_target
elif cand_pivot is not None:
    entry_target_for_form = cand_pivot
else:
    entry_target_for_form = None
# entry_price field uses the live PriceCache snap as today; if neither
# snap nor wl_entry.last_close exists, fall back to cand_pivot as a
# best-effort default (operator can override).
if snap is not None:
    entry_price = snap.price
elif wl_entry is not None and wl_entry.last_close:
    entry_price = wl_entry.last_close
elif cand_pivot is not None:
    entry_price = cand_pivot     # NEW fallback
else:
    entry_price = 0.0
```

The `watchlist_entry_target` and `watchlist_initial_stop` hidden inputs (template lines 37-44) remain BOUND TO `wl_entry` ONLY (they exist for watchlist-bookkeeping purposes; their POST-side meaning is "the value the watchlist had at form-render"). When the form is hyp-recs-originated and `wl_entry` is None, both hidden inputs are absent — preserving the semantic that they refer to watchlist state.

**Test coverage** (added to §4.3):
- `test_hyp_recs_entry_form_off_watchlist_uses_candidate_pivot_for_target`: hyp-recs Enter on a ticker that's NOT on the watchlist; the rendered form's entry_price = candidate.pivot (or live price if available); initial_stop = candidate.initial_stop. Pre-fix path would render `$0.00` for both.
- `test_hyp_recs_entry_form_on_watchlist_prefers_watchlist_values`: hyp-recs Enter on a ticker that IS on the watchlist with watchlist values DIFFERENT from candidate values; the form prefers watchlist values (preserves existing semantic).
- `test_origin_param_validation`: GET `/trades/entry/form?ticker=AAPL&origin=javascript:alert(1)` → form renders with origin defaulted to "watchlist" (whitelist validation), NOT the malicious string passed through to the template.

#### 3.8b.3 `origin` survival across POST round-trips (R4-Major-1)

GET-time threading of `origin` is necessary but NOT sufficient. The entry POST flow has multiple re-render paths that pre-date the discriminator and would silently revert to watchlist defaults if `origin` is lost. Spec requires `origin` to be carried as a HIDDEN FORM FIELD and threaded through every re-render path:

- **Hidden form field on `partials/trade_entry_form.html.j2`:**
  ```jinja
  <input type="hidden" name="origin" value="{{ vm.origin }}">
  ```
  Persists `origin` from the GET-time render through every POST submission.

- **`POST /trades/entry` handler (`swing/web/routes/trades.py`):** reads `origin` from form payload (whitelist-validated; unknown → "watchlist"). Threads to:
  - `_rerender_entry_form_with_error()` — current implementation rebuilds the VM from `ticker` only; spec requires it to also accept and propagate `origin`.
  - `DuplicateOpenPositionException` re-render branch — same VM rebuild path; same `origin` propagation.
  - `soft_warn_confirm.html.j2` `form_values` dict — `origin` MUST be among the keys round-tripped to the confirmation partial. The confirmation partial's hidden inputs include `origin` so that a subsequent confirm-submit POSTs the same value back; on cancel, the partial's Cancel button uses `vm.origin` to choose the right unwind target (`/hyp-recs/refresh` for hyp-recs, `/watchlist/{ticker}/expand` for watchlist).

- **`soft_warn_confirm.html.j2` template:** gains `<input type="hidden" name="origin" value="{{ vm.origin }}">` and parameterizes its Cancel button per the same logic as `trade_entry_form.html.j2:72-74` does post-R3-Major-1.

**Failure mode this closes:** without `origin` survival, an operator clicks Take this trade on a hyp-recs row → form renders correctly with `origin=hyp-recs` → submit triggers a validation error → form re-renders with `origin` lost → form now has colspan=8 and Cancel pointing to `/watchlist/{ticker}/expand` — the operator sees the form layout shift on resubmit, and Cancel teleports them to a watchlist row that's irrelevant (or 404 if ticker isn't on the watchlist). The hidden field + threading discipline closes this regression class.

**Test coverage** (added to §4.3):
- `test_validation_error_rerender_preserves_origin`: POST `/trades/entry` with `origin=hyp-recs` and a deliberate validation error (e.g., `entry_price=-1`) → response body still contains `colspan="9"` and Cancel `hx-get="/hyp-recs/refresh"`. Discriminating: pre-fix path would render colspan=8 + watchlist Cancel.
- `test_duplicate_open_position_rerender_preserves_origin`: POST with `origin=hyp-recs` for a ticker that already has an open position → re-render preserves origin.
- `test_soft_warn_confirm_round_trips_origin`: POST that triggers soft-warn → confirm partial includes hidden `origin=hyp-recs`; confirm-submit threads it back; Cancel from confirm fires `/hyp-recs/refresh`.

#### 3.8b.4 Anchor consistency for off-watchlist candidate fallback (R4-Major-2)

`build_entry_form_vm` currently reads candidate data from TWO different anchors:
- Chart-pattern classification: `latest_completed_pipeline_run` (`pipeline_runs ORDER BY finished_ts DESC LIMIT 1`).
- Sector/industry: `latest_evaluation_run_id()` (which can pick a standalone-eval row newer than the latest pipeline-bound eval).

Pre-Q7/Q8, the form was always reached from the watchlist surface, where this anchor split was an existing accepted residual (the `wl_entry`'s frozen target/stop dominated the form's order-related fields, so the candidate-derived sector/industry only contributed metadata). Post-Q7/Q8 the candidate now contributes ORDER-RELATED fields too (entry_price, initial_stop) for off-watchlist tickers — and a mixed-anchor form would show "entry price from eval run N, chart-pattern from pipeline run M" with no disclosure. The hyp-recs expansion uses `latest_completed_pipeline_run` consistently (per §3.5.3 anchor consistency invariant); the entry form must agree with the expansion when the operator just clicked Take this trade.

**Resolution: when `origin=hyp-recs`, bind ALL candidate-derived reads to `latest_completed_pipeline_run`'s `evaluation_run_id`.** The entry form mirrors the hyp-recs expansion's anchor exactly. For `origin=watchlist`, preserve the existing behavior (sector/industry from `latest_evaluation_run_id`; chart-pattern from `latest_completed_pipeline_run`) — backward compat for the watchlist surface.

```python
def build_entry_form_vm(*, ticker, cfg, cache, executor, origin="watchlist"):
    ...
    if origin == "hyp-recs":
        # Single binding for ALL candidate-derived reads (sector, industry,
        # pivot, initial_stop) AND chart-pattern classification.
        binding = latest_completed_pipeline_run(conn)
        if binding is not None:
            anchor_eval_id = binding.eval_id
            anchor_pipeline_run_id = binding.run_id
        else:
            anchor_eval_id = None
            anchor_pipeline_run_id = None
    else:
        # origin == "watchlist" — existing behavior (anchor split preserved).
        anchor_eval_id = latest_evaluation_run_id(conn)
        anchor_pipeline_run_id = (latest_completed_pipeline_run(conn) or NullBinding).run_id
    # Chart-pattern + candidate (sector/industry/pivot/initial_stop) reads
    # use anchor_eval_id and anchor_pipeline_run_id appropriately.
```

**Visible "as of" disclosure on the form when `origin=hyp-recs`** (mirrors §3.5.6 expansion's freshness signal): the form template gains a freshness footer when `vm.origin == "hyp-recs"` showing `Candidate context as of pipeline finished {{ vm.pipeline_finished_at }}`. Wording deliberately scoped to "candidate context" (R5-Minor-2): the entry form's `entry_price` field still comes from the live `PriceCache` (or the `wl_entry.last_close` fallback), NOT the pipeline snapshot — only the candidate-derived fields (sector, industry, pivot, initial_stop, chart-pattern) are bound to the pipeline anchor. The wording avoids implying live-price freshness, preventing the operator from over-trusting a stale `entry_price` field that's actually fresh.

**Test coverage** (added to §4.3):
- `test_hyp_recs_form_anchor_matches_expansion_anchor`: insert a pipeline_run completing with eval_id N; insert a standalone eval N+1 newer; build the hyp-recs expansion VM and the hyp-recs-origin entry form VM. Both reads bind to eval_id N; their pivot/initial_stop/sector/industry values agree byte-for-byte. Discriminating: pre-fix path (sector/industry from latest_evaluation_run_id) would yield N+1 in the form vs N in the expansion.
- `test_watchlist_origin_form_preserves_existing_anchor_split`: same fixture; build watchlist-origin entry form. Sector/industry come from N+1 (existing behavior); chart-pattern from N (existing behavior). Backward-compat preserved.

#### 3.8b.5 Plumbing summary

The Q7+Q8 + R3 + R4 resolution adds these to the dispatch's MODIFY list:
- `swing/web/templates/partials/trade_entry_form.html.j2` — parameterize colspan + Cancel target (R3-Major-1) + hidden `origin` form field (R4-Major-1) + freshness footer when origin=hyp-recs (R4-Major-2).
- `swing/web/templates/partials/soft_warn_confirm.html.j2` — hidden `origin` form field + parameterized Cancel button (R4-Major-1 round-trip).
- `swing/web/view_models/trades.py` — `TradeEntryFormVM` gains `origin: Literal["watchlist", "hyp-recs"]` + `pipeline_finished_at: str | None` fields; `build_entry_form_vm` accepts `origin` param + applies anchor-consistency logic per origin (R3-Major-1 + R3-Major-2 + R4-Major-2).
- `swing/web/routes/trades.py` — GET handler reads `?origin=` query param (whitelist); POST handler reads form-payload `origin`; threads to `_rerender_entry_form_with_error()` and `DuplicateOpenPositionException` re-render; soft-warn `form_values` includes `origin` (R3-Major-1 + R4-Major-1).

These are 4 additional MODIFY files NOT in the original §2.1 file map; updated below in the consolidated map and §9 done criteria.

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
- `test_refresh_route_returns_section_partial`: GET `/hyp-recs/refresh` returns 200 with the rendered `hypothesis_recommendations.html.j2` section (root element `<section id="hypothesis-recommendations">`). Renders with the same flat-table chevron + Enter columns.
- `test_refresh_route_reflects_current_state_not_expand_time_state`: capture `active_recommendations` snapshot A; insert a new pipeline run completing with a different snapshot B; GET `/hyp-recs/refresh` returns the section reflecting B. Documents the R1-Major-4 disposition (close shows current state, not expand-time state).
- `test_refresh_route_does_not_invoke_full_dashboard_build` (R2-Major-2 regression): patch a sentinel into the open-trades / watchlist / OHLCV builder paths and assert they are NOT called during `GET /hyp-recs/refresh`. Discriminating: a parallel test on `GET /` (full dashboard) confirms those sentinels ARE called there. Catches a regression where a future change accidentally re-routes the refresh handler back through `build_dashboard`.
- `test_refresh_route_isolated_from_unrelated_subsystem_failure` (R2-Major-2 regression): force the open-trades query path to raise, then GET `/hyp-recs/refresh` — assert 200 (refresh succeeds because it doesn't depend on open-trades). Discriminating: GET `/` returns 500 with the same monkeypatch (full dashboard does depend on open-trades).
- `test_per_row_enter_button_swap` (Q7): rendered hyp-recs row HTML contains `hx-get="/trades/entry/form?ticker={ticker}"`, `hx-target="closest tr"`, `hx-swap="outerHTML"`, `hx-headers='{"HX-Request": "true"}'`, label "Enter". GET the per-row Enter URL with `HX-Target: hyp-rec-row-AAPL` and assert the response body is the entry form `<tr>` (replaces the hyp-recs row). The same /trades/entry/form route that watchlist Enter uses; no new route.
- `test_per_row_enter_button_no_stoppropagation` (D.5): the per-row Enter button's `<button>` element has NO `onclick="event.stopPropagation()"` attribute (contrasts with watchlist's `:31` attribute). Discriminating: a parallel watchlist test verifies watchlist's button DOES have `stopPropagation`, confirming the architectural difference is intentional.
- `test_take_this_trade_button_swap` (Q8): rendered expansion HTML contains the "Take this trade" button with same HTMX attrs as per-row Enter (D.2 = option (a)). HTMX response replaces the expanded `<tr>` with the entry form `<tr>`.
- `test_per_row_enter_button_mirrors_watchlist_markup` (D.1 regression): assert byte-equivalent HTMX attribute set between watchlist row Enter and hyp-recs row Enter (modulo `stopPropagation`, which is intentionally absent on hyp-recs per D.5). Operator muscle-memory invariant.
- `test_take_this_trade_button_visual_differentiation` (D.3): rendered expansion's button has class containing `take-this-trade` and/or `primary`; per-row Enter button does NOT carry those classes. Confirms visual differentiation per D.3 lock.

### 4.4 Layer 4 — Template + sort-neutrality regression

- `tests/web/templates/test_hyp_recs_table_regression.py` — `test_collapsed_table_renders_9_columns_chevron_and_enter`: full-page render with `vm.active_recommendations` populated → 9 `<th>` elements (chevron + 7 existing + Enter); chevron button on column 1; Enter button on column 9; close-button NOT present (tr is not yet expanded).
- `test_hyp_recs_collapsed_does_not_render_expansion_partial`: ensure the expansion partial is NOT pulled in via incidental include (HTMX OOB-swap drift discipline).
- `tests/web/view_models/test_hyp_recs_sort_neutrality.py` — `test_sort_unchanged`: `prioritized_recommendations` order is byte-for-byte identical to the pre-V1 baseline. (Per R1-Major-1, `HypothesisRecommendation` is unchanged in V1, so the sort path has zero new inputs; the test is still committed as a regression guard against future churn.)

### 4.5 CC pivot bug discriminating regression (`tests/web/templates/test_watchlist_pivot_column.py`)

The fix touches THREE render sites (per §3.9 R1-Major-3 resolution); each gets its own discriminating test.

- `test_dashboard_top5_pivot_column_renders_current_pivot`: full-page dashboard render with `WatchlistEntry(entry_target=42.00)` + `candidates_by_ticker={ticker: Candidate(pivot=44.50)}`. Rendered cell = `$44.50`. Discriminating against pre-fix: pre-fix path renders `$42.00`.
- `test_standalone_watchlist_pivot_column_renders_current_pivot`: standalone `/watchlist` page render — same fixture and assertion. (Standalone watchlist uses a different template wiring, so independent verification.)
- `test_watchlist_row_close_path_pivot_column_renders_current_pivot` (R1-Major-3 regression): GET `/watchlist/AAPL/row` (the close-button target) with `WatchlistEntry(entry_target=42.00)` + the candidate row present. Rendered cell = `$44.50`. Without the `WatchlistRowVM.current_pivot` extension, this would revert to `$42.00`, recreating the bug post-close.
- `test_pivot_column_falls_back_to_entry_target_when_no_candidate`: candidates_by_ticker = {}, entry_target = $42.00. Cell = `$42.00`.
- `test_pivot_column_dash_when_both_absent` (R1-Minor-3 regression): candidates_by_ticker = {}, entry_target = None. Cell = `—` (NOT `$0.00`).
- `test_lightning_trigger_unchanged_uses_entry_target`: discriminating fixture chosen so the trigger fires under `entry_target` binding but would NOT fire under `current_pivot` binding — `entry_target=$42.00`, `current_pivot=$100.00`, `price=$41.60`. Under entry_target binding: `41.60 ≥ 0.99 × 42 = 41.58` → lightning fires. Under current_pivot binding: `41.60 ≥ 0.99 × 100 = 99` → would NOT fire. Test asserts lightning DOES fire, proving the trigger binding survives the column-display change.

### 4.6 Close-button mechanism: scoped section refresh (R1-Major-4 + R2-Major-2 resolution)

**Decision: full-section refresh on close, served by a SCOPED hyp-recs builder. NO per-row reconstruction route. NO full `build_dashboard` rebuild.**

**Rejected alternative #1 — symmetric `/hyp-recs/{ticker}/row` route mirroring `/watchlist/{ticker}/row` and `/trades/open/{trade_id}/row` (R1-Major-4 disposition).** A watchlist row is a stable projection of one persisted `WatchlistEntry`; a hyp-rec row is the output of matcher + prioritizer + top-N truncation + live-price fetch. Per-row reconstruction would either re-run the prioritizer expensively or render a stale frozen snapshot.

**Rejected alternative #2 — section refresh that calls `build_dashboard` (R2-Major-2 disposition).** `build_dashboard` rebuilds open trades, watchlist top-5, advisories, status strip, and OHLCV-backed open-position context — far more than the refresh swap target needs. Two failure modes:
1. **Cross-panel inconsistency.** The swap is `#hypothesis-recommendations` only; other dashboard sections keep their full-page-render snapshot. With `build_dashboard` the refresh would compute a NEW snapshot for those other sections too, but discard it — wasted work.
2. **Failure coupling.** A subsystem failure unrelated to hyp-recs (yfinance breaker tripped, OHLCV cache failure on an open-trade ticker) could break the close action.

**V1 choice — scoped `build_hyp_recs_section`.** §3.5.4 specifies the helper. The refresh handler resolves ONLY: `candidates_by_ticker` (for pivot_price), prices for the recommended tickers (typically 1–10, NOT the full watchlist), and the progress/registry data the prioritizer needs. Open-trade OHLCV, watchlist top-5, advisories, status strip are all UNTOUCHED on refresh.

Cross-panel snapshot consistency: the partial-swap UX is partial by design. The operator who closes a hyp-recs expansion sees current hyp-recs data; the rest of the dashboard reflects its last full-render snapshot. This is the same property as every other partial-swap surface on the page (watchlist row close, open-position row close, etc.).

**Cost accepted:** one extra HTTP round-trip per close + a section re-render scoped to ≤ top-N rows. Imperceptible on a small table.

**`build_dashboard` is refactored to call the same shared helper (`_build_active_recommendations`) so both the full-page render path and the refresh route construct recommendations identically (single source of truth).** No drift between full-page and refresh-route output.

**Row-partial extraction.** The per-row markup is extracted into `partials/hypothesis_recommendations_row.html.j2` so `hypothesis_recommendations.html.j2`'s `<tbody>` iterates via `{% include %}`. The per-row partial is the SAME markup whether rendered by the full-page path or the refresh-route path — drift impossible.

**Future per-row close (V2).** If operational use shows the full-section refresh has too much UX cost (e.g., a flicker when many rows re-render), V2 can add a `/hyp-recs/{ticker}/row` per-row route. The infrastructure is in place: the per-row partial is already extracted, the row-target prefix already covers `hyp-rec-row-`, and the per-row route would just need a stable per-row reconstruction strategy (likely "fetch the SAME `HypothesisRecommendation` from a request-scoped cache populated when the page was rendered").

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
- **Close-button mechanism.** Scoped section refresh via `/hyp-recs/refresh` (R1-Major-4 + R2-Major-2). The route uses a hyp-recs-only `build_hyp_recs_section` builder, NOT the full `build_dashboard`. Open-trades, watchlist, advisories, OHLCV are untouched on refresh — failure isolation + zero wasted work. Cross-panel snapshot consistency is the inherent partial-swap UX trade.
- **Action-button design (Q7 + Q8 + D.1-D.5).** Per-row Enter button mirrors watchlist exactly (D.1) without `stopPropagation` (D.5 — row is not a trigger). Take-this-trade button uses query-param mechanism (D.2 = option (a); ToCToU window same class as per-row Enter, no new ToCToU surface per D.4). Visual differentiation by label + styling (D.3). Both buttons fire the SAME `hx-get="/trades/entry/form?ticker={ticker}"` HTMX swap; the entry-form route handles all pre-fill via existing per-ticker mechanism.
- **Entry-form colspan compatibility (writing-plans concern).** The entry form `<tr>` colspan must accommodate either the 9-cell hyp-recs row (per-row Enter) OR the 9-cell expanded `<tr>` (Take this trade) when swap fires. Watchlist row is 7 cells; if the entry-form template hardcodes 7, writing-plans dispatch decides whether to parameterize the colspan or accept a visual quirk. Either choice is valid for V1 — flagged here so writing-plans doesn't silently inherit a broken layout.
- **Sizing same-source check.** `current_balance` value used by the expansion is computed from the SAME `current_equity` accessor `build_dashboard` already invokes for its existing equity strip. The dashboard's equity display and the expansion's cash-feasible label agree by construction.
- **Discriminating tests.** Each test in §4 differs from its pair / regression target by ONE feature; lightning-trigger discriminator constructs price-fixture values explicitly between `0.99 × entry_target` and `0.99 × current_pivot`.
- **Snapshot-at-render purity.** Expansion VM is computed on the route handler thread, never persisted, never carried into a subsequent entry submission as hidden form values. With D.2 = option (a), Q-K (ToCToU) is the SAME class as the existing per-row Enter button — no new ToCToU surface is introduced. The expansion's display values are at-click snapshots, NOT carried into the entry form.
- **Brief premise history.** Earlier brief drafts (pre-Q7) erroneously asserted an existing Enter button on hyp-recs. The 2026-04-29 brief update (commit `427ef95`) closed that gap by locking Q7 — every hyp-recs row gains a per-row Enter button as part of this dispatch. Spec resolves D.1-D.5 on top of the locked Q7 + Q8 decisions; no operator-judgment-call escalation outstanding for V1.

---

## 7. Migration / rollout

1. **No migration.** Schema unchanged; first deploy after merge takes effect immediately.
2. **First page-render after deploy** shows the new chevron column + Enter button on the flat hyp-recs table. Operator click triggers the route handler.
3. **Configuration default** — `cfg.web.chase_factor = 0.01` ships as code default. Operators who want a different chase factor in V1 add a `[web]` row to their local `swing.config.toml` (deliberate opt-in until Phase 5 ships the editor). Spec calls out this asymmetry in §3.1.
4. **CC pivot bug fix** lands as a separate task in the same merge; watchlist `Pivot` column starts rendering current-eval pivot on the next page load.

### 7.1 Recommended implementation sequencing (R5-Minor-1)

The dispatch has grown materially through R1-R4 (single expansion → multi-surface integration touching hyp-recs UI, watchlist pivot semantics, shared entry-form origin handling, soft-warn confirm behavior, anchor policy). Writing-plans dispatch should sequence the work to minimize cross-task interference and preserve a clean revert path at each milestone. Recommended ordering:

1. **CC pivot fix (independent; revertible).** Touches `partials/watchlist_row.html.j2`, `partials/watchlist_top5_section.html.j2`, `watchlist.html.j2`, `view_models/watchlist.py`, `routes/watchlist.py`. No coupling to the rest of this dispatch. Land + verify cross-surface consistency before any hyp-recs work begins. Single-task revert if anything breaks.
2. **`Config.web.chase_factor` field (atomic; no UX impact).** Pure config addition. Lands without any template change; consumed only by §3.5.3's `build_hyp_recs_expanded`.
3. **Hyp-recs expansion (Q-A through Q-J + Q-L; route + VM + templates).** Includes chevron column, expansion partial, `/hyp-recs/{ticker}/expand` + `/hyp-recs/refresh` routes, `_ROW_TARGET_PREFIXES` extension. Excludes the per-row Enter button (Q7) + Take-this-trade button (Q8); those land at step 5. Verify expansion + close cycle works end-to-end.
4. **Scoped `build_hyp_recs_section` extraction (R2-Major-2).** Move the existing recommendation-construction loop in `build_dashboard` into the shared `_build_active_recommendations` helper. Refresh route uses the new builder. Sentinel-based isolation tests confirm refresh doesn't trigger open-trades / watchlist / OHLCV builds.
5. **Per-row Enter button + Take-this-trade button (Q7 + Q8).** Adds the Enter column to the flat-table row partial; adds the Take-this-trade button to the expansion partial. Reuses the existing entry-form route via `?origin=hyp-recs` (which lands at step 6).
6. **Origin-aware entry form (R3 + R4).** `TradeEntryFormVM.origin` field; template parameterization (colspan + Cancel target + freshness footer + hidden form field); route handler GET + POST origin handling; soft-warn round-trip; anchor consistency for hyp-recs origin; off-watchlist candidate fallback. Largest task; lands last so any defects don't block the simpler steps.

Each step is atomically revertable. Steps 3-6 are sequentially dependent (later steps assume the earlier scaffolding); steps 1 + 2 are independently revertable from each other and from the rest. Writing-plans dispatch may further subdivide step 6 into validation-error / soft-warn / candidate-fallback sub-tasks.

**Residual integrity acceptances:**
- **Snapshot-at-render staleness.** A user keeps the expansion open through a pipeline run; the displayed values become stale. Mitigation: the "As of pipeline finished <ISO>" footer signals when the snapshot was captured. V2 candidate: HTMX SSE/polling to invalidate open expansions on pipeline-run completion.
- **Pivot rotation between full-page and expansion request.** A ticker shown in `active_recommendations` at full-page render may have rotated out by the time the operator clicks expand (rare; would require a pipeline run completing in that window). The route handler returns 404 with the operator-facing "Not a current candidate or pivot data missing." message; operator re-loads the dashboard.

---

## 8. Open follow-ups (V2 candidates, NOT in V1 scope)

- **Extended-snapshot pre-fill (D.2 option (b)) for the expansion's Take-this-trade button** — carrying `buy_stop`, `sell_stop`, shares, notional via hidden inputs to eliminate the ToCToU window between expansion-render and form-render. Adds plumbing complexity + threat-model surface (per chart-pattern flag-v1 §3.6). V1 ships option (a) (query-param mechanism) per §3.7 D.2; V2 candidate if operators report ToCToU pain in operational use.
- **Per-row close (V2 candidate)** — if operational use shows the full-section refresh's flicker / repaint cost is too high, V2 can add `/hyp-recs/{ticker}/row` per-row close. Infrastructure prepared in V1 (per-row partial extracted; row-target prefix already covers `hyp-rec-row-`).
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
- [ ] `HypothesisRecommendation` UNCHANGED (per R1-Major-1); existing call sites byte-for-byte identical.
- [ ] `HypRecsExpandedVM` dataclass exists; `build_hyp_recs_expanded` returns it on the happy path and `None` on rotation / no-run / degenerate-sizing.
- [ ] `HypRecsSectionVM` + `build_hyp_recs_section` exist (R2-Major-2); refresh route uses scoped builder NOT full `build_dashboard`.
- [ ] `_build_active_recommendations` shared helper exists; `build_dashboard` and `build_hyp_recs_section` both call it (single source of truth for recommendation construction).
- [ ] `GET /hyp-recs/{ticker}/expand` returns the expansion partial; 404 for unknown / rotated tickers; chart-unavailable div for out-of-scope tickers.
- [ ] `GET /hyp-recs/refresh` returns the scoped section partial; row-target prefix `hyp-rec-row-` covers 4xx/5xx swaps; refresh does NOT trigger open-trades / watchlist / OHLCV builds.
- [ ] **Per-row Enter button (Q7) on each hyp-rec row** renders with byte-equivalent HTMX attrs to watchlist Enter button; NO `stopPropagation` (D.5); HTMX swap to entry form `<tr>` works.
- [ ] **Take this trade button (Q8) inside the expansion** renders with same HTMX attrs (D.2 = option (a)) but differentiated label + styling (D.3); HTMX swap replaces the expanded `<tr>` with entry form.
- [ ] Hyp-recs flat table renders 9 columns (chevron + 7 existing + Enter); chevron column on col 1, Enter on col 9.
- [ ] Watchlist `Pivot` column renders `candidates.pivot` across ALL THREE render sites (dashboard top-5 via `watchlist_top5_section.html.j2`, standalone watchlist page via `watchlist.html.j2`, watchlist `/watchlist/{ticker}/row` close-path via `WatchlistRowVM.current_pivot`); falls back to `entry_target`; "—" when both absent.
- [ ] Lightning trigger on watchlist row stays bound to `entry_target` (regression test §4.5).
- [ ] Sizing twins (risk-based + cash-feasible) computed and rendered with two-row layout; infeasibility path renders the `infeasible (constraint)` annotation.
- [ ] Sector + Industry rendered in the Context group; empty strings render as `"—"`.
- [ ] "As of pipeline finished <ISO>" footer present on the expansion.
- [ ] All test layers green: sizing twins; expansion VM (anchor consistency, degenerate-sizing); route (expand 200 + 404 + chart-scope + 500 row-target-prefix coverage; refresh 200 + scoped-builder isolation; per-row Enter swap; Take-this-trade swap; muscle-memory mirror); template (9-column regression; per-row Enter mirrors watchlist; visual differentiation); CC pivot (3-render-site coverage + dash sentinel + lightning binding preserved).
- [ ] **Origin-aware entry form (R3-Major-1):** colspan + Cancel target parameterized via `vm.origin`; whitelist-validated query param; hyp-recs-originated forms render colspan=9 + Cancel `hx-get="/hyp-recs/refresh"`; watchlist-originated forms preserve existing colspan=8 + Cancel `hx-get="/watchlist/{ticker}/expand"` behavior.
- [ ] **Off-watchlist candidate fallback (R3-Major-2):** `build_entry_form_vm` for off-watchlist tickers populates `entry_price` and `initial_stop` from candidate row; on-watchlist tickers preserve existing watchlist-priority semantics.
- [ ] **Origin survives POST round-trips (R4-Major-1):** hidden form field on entry form + soft-warn confirm; threaded through `_rerender_entry_form_with_error`, duplicate-position re-render, and soft-warn confirm; validation-error and soft-warn round-trip tests confirm survival.
- [ ] **Anchor consistency for hyp-recs origin (R4-Major-2):** when `origin=hyp-recs`, ALL candidate-derived reads (sector, industry, pivot, initial_stop, chart-pattern) bind to the SAME `latest_completed_pipeline_run` evaluation_run_id — matches the hyp-recs expansion's anchor (§3.5.3); freshness footer "As of pipeline finished <ISO>" present on the form. Watchlist-origin forms preserve existing anchor split for backward compat.
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
