# Hyp-recs Trade-Prep Expansion — Brainstorming Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Author a design spec for the hyp-recs trade-prep expansion via `copowers:brainstorming`. Six design decisions (Q1-Q6) are pre-locked by the operator (2026-04-28; see §2 — DO NOT re-litigate). The brainstorm's job is to resolve OPEN design questions (§3) and produce a complete spec that's ready for `copowers:writing-plans` dispatch.

**Expected duration:** ~1-2 hr brainstorm-skill execution + 3-5 Codex rounds via the `copowers:brainstorming` wrapper = ~3-5 hours total.

**Dispatch type:** `copowers:brainstorming` (NOT writing-plans, NOT executing-plans).

---

## §0 Read first

Read these in order before invoking the brainstorming skill:

1. **`CLAUDE.md`** at repo root — project conventions, gotchas, invariants. Note especially the HTMX OOB-swap partial drift gotcha (use `{% include %}` to share partials between full-page and OOB-swap render paths) and the base-layout 5-VM rule.

2. **`docs/orchestrator-context.md`** — read these sections:
   - §"Currently in-flight work" — current state at HEAD; sector dispatch (Phase 1) just shipped on 2026-04-29; this dispatch is Phase 2.
   - §"Recent decisions and framings" — particularly the 2026-04-25 Hypothesis-recommendation engine framing ("dashboard PROPOSES, operator DISPOSES"); 2026-04-25 Entry discipline for hypothesis trades ("wait for pivot, don't chase >1% above"); 2026-04-26 Watchlist sort uses four-key composite ordering; 2026-04-26 chart-pattern flag-v1 scope decisions.
   - §"Binding conventions" — 4-tier commit-message convention; observable-verification grep ERE form; ruff baseline 91.
   - §"Anti-patterns" — particularly mid-session scope expansion; brief drafting drift; operator-drives-agent-serves discipline.
   - §"Lessons captured" — particularly: discriminating-test discipline; compounding-confound class; sort-neutrality structurally guaranteed; ToCToU on form-driven workflows; Codex's contextual advantage at finding cross-feature interactions; manual visual verification is required for rendering work; multi-path-ingestion (just-captured 2026-04-29).

3. **`docs/phase3e-todo.md`** §"2026-04-28 hyp-recs trade-preparation expansion (QUEUED; brainstorm dispatch pending)"** — **THE SCOPE-OF-WORK SOURCE OF TRUTH** for this dispatch. All locked decisions (Q1-Q6) are recorded there verbatim; §2 below mirrors them. Snapshot fields list at "Snapshot fields to design" subsection.

4. **`docs/phase3e-todo.md`** §"2026-04-28 sector/industry capture + display"** — context for the just-shipped Phase 1 dispatch. Sector + Industry are now captured on `candidates` and `trades` tables; available via `candidates_by_ticker` at `swing/web/view_models/dashboard.py:552-581` for read-side consumption WITHOUT data-plumbing rework. The hyp-recs expansion can include them as context fields.

5. **`docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`** — most recent brainstorming-output spec; structural template for what this spec should look like.

6. **Existing expansion patterns in the codebase** (precedents to mirror or diverge from):
   - `swing/web/templates/partials/watchlist_expanded.html.j2` — watchlist row expansion (HTMX click-to-expand pattern; "Chart unavailable" message handling; Sector/Industry display rows just shipped 2026-04-29).
   - `swing/web/templates/partials/open_positions_row.html.j2` + `swing/web/templates/partials/open_positions_expanded.html.j2` — open positions click-to-expand (chart-access UX pattern from Tier-2 #3 dispatch 2026-04-27).
   - `swing/web/templates/partials/hypothesis_recommendations.html.j2` — current hyp-recs flat 7-column read-only table (THE FILE THIS DISPATCH MODIFIES).

7. **Existing chart-access UX** (Tier-2 #2 + #3 commit chain `772d69b..a5fdc75`, 2026-04-27):
   - `swing/web/routes/charts.py` — date-less `/charts/<TICKER>.png` route; 303 redirect to existing date-prefixed StaticFiles URL or chart_scope-aware 404 with operator-facing reason.
   - This is the canonical "chart in expansion" pattern. Reuse, don't reinvent.

8. **Existing sizing pipeline** (where sell stop comes from):
   - `swing/recommendations/compute_shares.py` — `compute_shares()` → `SizingResult` with `stop_loss` field. Verify fields available; spec the canonical source for "sell stop" snapshot value.

If any file path doesn't resolve, surface in return report — do NOT silently proceed against a stale path.

---

## §0 Skill posture

- **INVOKE** `copowers:brainstorming` — wraps `superpowers:brainstorming` with adversarial Codex review (3-5 rounds typical).
- **DO NOT INVOKE** `superpowers:writing-plans`, `copowers:writing-plans`, `superpowers:executing-plans`, `copowers:executing-plans`. The brainstorm produces a spec, NOT a plan, NOT shipped code. Future writing-plans + executing-plans dispatches consume this spec.
- **DO NOT re-litigate locked decisions (§2).** Q1-Q6 are operator-locked from 2026-04-28; the brainstorm builds a spec ON TOP OF them, not around them. If a locked decision appears impossible to specify cleanly, STOP and surface in return report; do NOT silently re-design.
- **Spec output target path:** `docs/superpowers/specs/2026-04-29-hyp-recs-trade-prep-expansion-design.md`. Commit the spec as part of the standard cycle (mirroring 2026-04-26-chart-pattern-flag-v1-design.md naming + structure).

---

## §1 Strategic context

**Why this work.** Operator surfaced workflow gap during chart-pattern flag-v1 manual verification round 1 + CC pivot bug triage (2026-04-28): hyp-rec rows are evaluated row-by-row against chart pattern + buy-window proximity before pulling the trigger; current dashboard surface lacks at-a-glance trade-preparation snapshot. The hyp-recs panel ("dashboard PROPOSES, operator DISPOSES" per 2026-04-25 framing) currently shows ticker/price/pivot/hypothesis/progress/tripwire/suggested-label — informative for hypothesis context but missing the trade-execution-decision context (buy window, sizing, stop, cost).

**Operator's pure-trigger discipline** (2026-04-28): pure-trigger conditional on price being inside the buy window — formal version of "wait for pivot, don't chase >1% above pivot" entry discipline (2026-04-25). The expansion makes "in-window?" check at-a-glance rather than ad-hoc external lookup.

**Sequencing context.** This dispatch is Phase 2 of a 6-phase post-2026-04-28 sequence: sector (SHIPPED 2026-04-29) → **hyp-recs expansion (this dispatch)** → OHLCV archive → noise queue → configuration page → Tier-3 design. Sector + Industry are now captured on `candidates`; the brainstorm can include them as context fields without any data-plumbing rework. Configuration page (Phase 5) consumes `chase_factor` introduced as a configurable field by this dispatch.

**Bundled bug fix.** This dispatch bundles the CC pivot bug fix (Option C: watchlist `Pivot` column header renders `candidates.pivot` instead of `WatchlistEntry.entry_target`) per Q6. Cross-surface consistency on what "Pivot" means becomes part of this dispatch's done-criteria.

---

## §2 Locked decisions (DO NOT re-litigate)

Operator-locked 2026-04-28. The spec implements these as written; no re-design.

1. **Chase factor.** 1% per recorded discipline for V1, but MUST be configurable — not hard-coded. Implementation hooks into the future configuration-page work (Phase 5; separate dispatch); for V1 the 1% lives in a config field with a sensible default. **Toml-shadowing audit applies** (per `aeb2084` lesson + 2026-04-29 multi-path-ingestion lesson) — if a tracked toml override exists at ship time, must update in the same commit OR explicitly accept as operator opt-in.

2. **Chart in expansion when ticker is out-of-chart-scope.** "Chart unavailable" message reusing the chart-access UX pattern — same behavior as current `/charts/<TICKER>.png` handler when ticker not in chart-scope. NO chart-scope policy change for this dispatch. Operator will give explicit direction if/when chart-scope rules need adjustment.

3. **Cost-display semantics.** Show TWO cost numbers: risk-based (using $7,500 floor sizing per `project_capital_risk_floor.md` memory) AND cash-feasible (capped at actual balance). **Cash-feasible cap uses CURRENT ACCOUNT BALANCE ONLY**, NOT total liquidity (balance + open positions). May add a risk display for both ends in V2; V1 ships shares + total cost for the two cases.

4. **Lightning icon.** Keep as-is for now. Do NOT hide or strip in this dispatch. Operator may repurpose later (Tier-3 #5 stays open as a separate conversation); the explicit reason is so the icon remains visible as a reminder for that future decision rather than evaporating. **Lightning trigger logic stays bound to `entry_target` unchanged** — this dispatch does NOT touch the lightning trigger expression in `partials/watchlist_row.html.j2:7`.

5. **Cross-surface scope.** Hyp-recs ONLY in this dispatch. Watchlist + open-positions snapshot extensions deferred. Watchlist's existing expand stays chart-only-plus-Sector/Industry-rows (just shipped 2026-04-29); open-positions' existing expand stays chart-only.

6. **CC pivot bug bundled into this dispatch (Option C).** Watchlist `Pivot` column header currently renders `WatchlistEntry.entry_target` (frozen at add time) under a header that says "Pivot." Fix renders `candidates.pivot` (current eval-run pivot) instead — matches what hyp-recs already does. Cross-surface consistency on what "Pivot" means becomes part of this dispatch's done-criteria. **Lightning trigger logic stays bound to entry_target separately per Q4** — column display semantic change AND lightning trigger field are independent code references; the fix touches column display only.

---

## §3 Open design questions for the brainstorm to resolve

The brainstorm-skill's job is to resolve these and bake answers into the spec. If any answer surfaces a need to revisit a locked decision (§2), STOP and surface in return report; do NOT silently re-design.

### A. Sell stop source identification

The "Sell stop" snapshot field is "framework-computed initial stop." Verify the canonical source:
- Field on `candidates` row? (e.g., `stop_loss` or `initial_stop`).
- Computed via existing sizing pipeline at request time? (`swing.recommendations.compute_shares` → `SizingResult.stop_loss`).
- Both available? Brainstorm grep + report; spec specifies the chosen source AND the rationale.

### B. Layout / visual hierarchy

The expansion contains 9+ snapshot fields:
1. Buy stop (= pivot)
2. Buy limit (= pivot × (1 + chase_factor))
3. Sell stop (per A above)
4. # shares (risk-based)
5. # shares (cash-feasible)
6. Total cost (risk-based)
7. Total cost (cash-feasible)
8. Chart (inline if in scope; "Chart unavailable" otherwise)
9. Sector + Industry (just shipped Phase 1; available via candidates_by_ticker)

Brainstorm proposes a layout. Considerations:
- Single column vs multi-column grid vs grouped-by-category (Order params / Sizing / Context).
- Mirror watchlist_expanded.html.j2 / open_positions_expanded.html.j2 pattern OR diverge with rationale.
- Visual hierarchy: which fields are MOST decision-relevant (likely Buy stop / Buy limit / Sell stop / Total cost) vs CONTEXT (Sector, Industry).

### C. HTMX expansion mechanics

How does the expansion mount?
- Click target on the row: row-level `hx-get` (mirrors current watchlist pattern; introduces the same architectural concern as Bug 1 follow-up "Watchlist row HTMX trigger architecture refactor" — interactive children need stopPropagation), OR
- Dedicated chevron column / "Expand" button (more explicit affordance).

Brainstorm picks one with rationale.

### D. "Take this trade" action button

Does the expansion include an action button that pre-fills `/trades/entry?ticker=...`? Or information-only?

The hyp-recs row already has an "Enter" button (visible in operator's earlier screenshots). If the expansion adds a redundant action button, that's UX clutter. If it omits one, the operator's flow is "expand → mentally verify → click row's existing Enter button" — extra interaction.

Brainstorm proposes:
- Information-only expansion (operator uses row's existing Enter button), OR
- Expansion includes "Take this trade" button that pre-fills the snapshot values into the entry form.

If the latter: how does pre-fill work? Current Enter button already pre-fills hypothesis_label + chart_pattern via the existing hypothesis-recommendation pre-fill. Adding buy_stop / buy_limit / sell_stop pre-fill is incremental.

### E. Chart inline rendering

When ticker IS in chart-scope, render inline using `/charts/<TICKER>.png` (Tier-2 #2 pattern). When NOT in scope, show "Chart unavailable" with chart_scope reason (mirroring open_positions_expanded.html.j2). Confirm by reference — likely no surprises.

### F. Configuration scaffolding for chase_factor

Where does the configurable chase_factor live in `Config`?
- `Config.web.chase_factor` (matches `chart_top_n_watch` location pattern).
- `Config.trades.chase_factor` (closer to entry domain).
- `Config.recommendations.chase_factor` (closer to hyp-recs surface).

Spec picks one with rationale. Default value: 0.01 (1% per Q1).

Toml-shadowing audit (per the multi-path-ingestion lesson): grep tracked config files for the chosen field name BEFORE declaring spec complete.

### G. CC pivot bug fix integration

Per Q6, watchlist column rendering changes from `entry_target` → `candidates.pivot`. The fix scope is:
- `partials/watchlist_row.html.j2:16` — `{{ '%.2f' | format(w.entry_target or 0) }}` → `{{ '%.2f' | format(current_pivot or 0) }}` (or similar).
- Watchlist VM joins candidates by ticker to provide `current_pivot` field, OR template directly accesses `expanded.candidate.pivot`.

Spec specifies whether the CC fix is:
- A separate task in the eventual writing-plans (recommended; cleaner scope), OR
- Bundled into one of the hyp-recs expansion tasks (more expedient; harder to revert if problem found).

Either is fine; spec picks one with rationale.

### H. Lightning icon coexistence with new buy-window display

Per Q4, lightning trigger stays bound to `entry_target`. Per Q6, watchlist column shows current pivot. The expansion shows current pivot AND buy_limit AND price. Operator may see:
- Lightning fires (price ≥ 0.99 × entry_target).
- Expansion shows price < buy_stop (current pivot).
- These are CONSISTENT (different reference points) but visually confusing.

Spec proposes: nothing (accept as deliberate cost of preserving lightning behavior; document in spec rationale section); OR: hover/tooltip that explains the entry_target binding; OR: visual annotation on the lightning icon. **Q4 is locked to "no behavior change"** — any tooltip/annotation is informational only, not a behavior change.

### I. Cost-display visualization

Per Q3, two cost numbers (risk-based + cash-feasible). Visual treatment:
- Inline pair: "Total cost: $930 (risk-based) / $1,200 (cash-feasible)".
- Two rows: "Risk-based cost: $930" / "Cash-feasible cost: $1,200".
- Grouped block: "Sizing: 31 shares × $30 = $930 (risk-based) | 8 shares × $30 = $240 (cash-feasible cap)".

Spec picks one with rationale. Operator-readability is the criterion (operator's bandwidth for visual-density-decoding is finite).

### J. Cache + freshness signal

Snapshot values are point-in-time at expansion-render. Pivot may change on the next pipeline run. How is staleness communicated?

Options:
- "As of <pipeline_run_id>" footer on the expansion.
- "Last evaluated: <timestamp>" inline.
- Nothing (operator infers from the fact that the dashboard's "Last pipeline" indicator shows when data was last refreshed).

Spec picks one with rationale.

### K. Snapshot-at-render vs ToCToU

If the expansion includes a "Take this trade" button (per D), the existing snapshot-at-entry-surface ToCToU pattern (spec §3.6 of chart-pattern flag-v1; Phase 5 lesson) applies. Spec must address:
- Does the expansion's snapshot get carried INTO the entry form via hidden inputs?
- OR does the entry form re-resolve from candidate at form-render time?
- If the latter, the values shown in the expansion may differ from what's persisted at entry — that's the existing ToCToU class.

If D resolves to "information-only expansion (no action button)", K becomes moot.

### L. Sector + Industry display

Just shipped Phase 1. Available via `candidates_by_ticker`. Brainstorm proposes:
- Include in the expansion as context fields (operator can scan sector/industry at-a-glance during decision).
- OR keep them in trade-entry only since the hyp-recs row already shows hypothesis label.

Recommendation: include. Operator confirmed sector is part of decision-making (orchestrator-context lines 156-157); having it in the expansion reduces cognitive load.

### M. Mobile/responsive

Operator workflow is desktop browser. Brainstorm explicitly defers mobile/responsive to V2.

---

## §4 V1 scope (binding)

**The spec produces V1 design covering:**
1. All snapshot fields enumerated in §3 B (9+ fields).
2. HTMX expansion mechanics (per §3 C resolution).
3. Action-button decision (per §3 D resolution).
4. Chart inline + "Chart unavailable" handling (per §3 E).
5. Configuration scaffolding for `chase_factor` (per §3 F).
6. CC pivot bug fix (per §3 G — bundled in this dispatch's scope).
7. Sector + Industry inclusion (per §3 L recommendation).
8. Lightning icon rationale (per §3 H).
9. Discriminating-test discipline + sort-neutrality (per the existing patterns).

**The spec defines:**
- File map (which files change in writing-plans phase).
- VM additions (whatever's needed for the expansion).
- Template additions (the new expansion partial).
- Route additions (if any — likely none; existing dashboard route already serves hyp-recs).
- Test surface (per-task discriminating-test patterns).

**Test count projection** is plan-phase concern; spec just notes "tests added; exact count pinned at writing-plans dispatch."

---

## §5 V1 out-of-scope (DEFER; V2+ candidates)

- Mobile/responsive design (per §3 M).
- Sort-PARTICIPATING fields from the expansion (sort discipline: `_sort_watchlist` and hyp-recs prioritizer untouched).
- Watchlist + open-positions snapshot extensions (locked OUT per Q5).
- Live-update push (HTMX SSE / WebSocket for snapshot field changes during pipeline run).
- Configuration-page UI for `chase_factor` (Phase 5 of operator sequence; this dispatch ships the config field, future Phase 5 surfaces the editor).
- Tier-3 #5 lightning icon trigger logic re-evaluation (operator-paced design conversation; this dispatch preserves current behavior per Q4).
- Risk-display for both ends of the cost range (Q3 mentioned as V2 candidate).
- Multi-trade preview (selecting multiple hyp-recs and seeing aggregate cost / total exposure).
- Sector concentration warning (V2 follow-up of the sector dispatch; gated on shipping the data-capture which is now done).

---

## §6 Done criteria

- Spec committed at `docs/superpowers/specs/2026-04-29-hyp-recs-trade-prep-expansion-design.md`.
- Spec passes `copowers:brainstorming` Codex review cycle: 3-5 rounds, terminating at `NO_NEW_CRITICAL_MAJOR`.
- All §3 design questions resolved (answer baked into spec) OR explicitly deferred with rationale.
- Spec is structurally similar to `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md` (compare structure; do not blindly mirror — the hyp-recs expansion is a UI feature; chart-pattern was a classifier feature; structure should fit the work).
- Spec is ready for `copowers:writing-plans` dispatch (next phase of the cycle).
- Toml-shadowing audit (per the multi-path-ingestion lesson) for the chosen `chase_factor` config field name documented in spec.

---

## §7 Return report format

Post as final message:

```
## Hyp-recs Trade-Prep Expansion Spec — Brainstorming Return Report

**Spec committed at:** docs/superpowers/specs/2026-04-29-hyp-recs-trade-prep-expansion-design.md (commit <SHA>)
**Codex rounds:** N rounds, terminating at NO_NEW_CRITICAL_MAJOR
**Spec line count:** <N>
**Open design questions resolved:** <N>/13 (per §3); deferred: <list of deferred + rationale>

**Codex findings dispositioned:**
- R1: <count> Critical, <count> Major, <count> Minor — <breakdown>
- R2: ...
... (per round)

**Locked decisions held:** Q1-Q6 implemented as written; no re-litigation.

**Major design choices made:**
1. Sell stop source: <answer>
2. Layout: <answer>
3. HTMX expansion mechanics: <answer>
4. Action button: <answer>
5. CC pivot bug integration: <answer>
6. chase_factor config location: <answer>
7. Lightning coexistence rationale: <answer>
8. Cost-display visualization: <answer>
9. Cache/freshness signal: <answer>
10. ToCToU handling: <answer>
11. Sector/Industry inclusion: <answer>
(annotate any that diverged from brief recommendations.)

**Open questions for orchestrator triage:**
- <any items the brainstorm flagged as needing operator decision before writing-plans dispatch>

**Recommended next dispatch:** copowers:writing-plans on this spec.
```

---

## §8 If you get stuck

- **If a locked decision (§2) appears impossible to specify cleanly:** STOP, surface in return report. Do NOT silently re-design.
- **If a precedent file path doesn't resolve:** Use `Glob` / `Grep` to find the actual current path. Pre-dispatch survey may have stale references.
- **If Codex round count exceeds 5 without convergence:** STOP, surface in return report with the unresolved finding. Do NOT iterate indefinitely.
- **If §3 design question requires operator-input that the brief hasn't pre-locked:** STOP, surface in return report. Do NOT silently choose; the brainstorm makes design decisions on TECHNICAL grounds, but operator-judgment-call decisions must escalate.

---

## Appendix A: Cross-references

- **Phase 1 sector dispatch (just shipped 2026-04-29):** spec at `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md` (precedent structure); plan at `docs/superpowers/plans/2026-04-28-sector-industry-capture-plan.md` (how a writing-plans output looks); brief at `docs/sector-industry-capture-writing-plans-brief.md`.
- **Tier-2 #2/#3 chart-access UX (2026-04-27):** commit chain `772d69b..a5fdc75`; introduces `/charts/<TICKER>.png` route + open-positions click-to-expand. Template precedents: `swing/web/templates/partials/open_positions_expanded.html.j2`.
- **Watchlist row expand (existing):** `swing/web/templates/partials/watchlist_expanded.html.j2`. Sector/Industry rows added 2026-04-29 by Phase 1.
- **Hypothesis-recommendation engine framing (2026-04-25):** orchestrator-context "Recent decisions and framings" — "dashboard PROPOSES, operator DISPOSES."
- **Entry discipline (2026-04-25):** orchestrator-context "Recent decisions and framings" — "wait for pivot, don't chase >1% above pivot."
- **Capital risk floor convention:** project memory `project_capital_risk_floor.md` — risk uses max($7,500, balance); cash-feasibility uses balance only.
- **CC pivot mismatch bug:** investigation captured in conversation 2026-04-28 + `docs/phase3e-todo.md` 2026-04-28 hyp-recs trade-prep expansion section "CC pivot mismatch bug" subsection. Root cause: watchlist row partial renders `entry_target` (frozen at add time) under a header that says "Pivot." Fix path Option C: render `candidates.pivot`.
