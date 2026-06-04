# Process-Grade-Trend Chart Redesign (+ reviews-page nav-date fix) — Design Spec

**Date:** 2026-06-03 · **Phase:** 15 (third commissioned arc — the lightest; presentation-only)
**Brief:** [`docs/process-grade-trend-redesign-brainstorming-dispatch-brief.md`](../../process-grade-trend-redesign-brainstorming-dispatch-brief.md)
**Status:** brainstorming design spec (NO code; the writing-plans phase derives the plan)
**Branch base:** main HEAD `514778f3`

---

## §1 Architecture overview — the bug + the inline-SVG constraint

`GET /metrics/process-grade-trend` ([`swing/web/routes/metrics.py:216`](../../../swing/web/routes/metrics.py)) renders a single 800×360 inline `<svg>` plus a 7-row per-metric table. The SVG overlays **7 incommensurate rolling series** on ONE grade-labeled y-axis (A=4 .. F=0):

| Series | Class | True range | Honest scale |
|---|---|---|---|
| `process_grade_rolling_N` | B | grade | [0, 4] |
| `entry_grade_rolling_N` | B | grade | [0, 4] |
| `management_grade_rolling_N` | B | grade | [0, 4] |
| `exit_grade_rolling_N` | B | grade | [0, 4] |
| `disqualifying_violation_rate_rolling_N` | A | proportion | [0, 1] |
| `mistake_cost_R_rolling_N_per_trade` | B | R, ≥0 unbounded | data-driven |
| `mistake_cost_R_rolling_N_total` | point | R, ≥0 unbounded (window SUM) | data-driven |

**Root cause (verified):** [`_y_axis_bounds_for_metric`](../../../swing/web/view_models/metrics/process_grade_trend.py) returns a *per-series independent* `(y_min, y_max)` — grades `[0,4]`, rate `[0,1]`, costs `(raw_min, raw_max)` — and `_polyline_y` normalizes each series into that range. **But every polyline is then drawn into the SAME plot box**, of which only the A=4..F=0 axis is labeled ([`process_grade_trend.html.j2:31-37`](../../../swing/web/templates/metrics/process_grade_trend.html.j2)). Consequences:

1. The rate line (normalized to `[0,1]`) and the grade lines (normalized to `[0,4]`) occupy the same pixels but mean different things — reading the rate against "A=4..F=0" is meaningless.
2. The cost lines are normalized to `(raw_min, raw_max)` — **not anchored at 0** — so a cost drifting 0.30→0.50 R fills the whole panel height, making a trivial change look like a cliff ("plunge-lines").
3. The two cost lines are themselves incommensurate: `_per_trade` is a window *mean* (~0.3 R), `_total` is a window *running SUM* (~N× larger). Co-plotting them squashes one.

**The inline-SVG-only constraint (L2, HARD):** the fix MUST stay hand-rolled inline SVG + the existing server-rendered table. NO matplotlib, NO Chart.js/D3, NO client-side renderer. The route test `test_process_grade_trend_does_not_use_matplotlib_or_external_chart_lib` is the guard.

**What is NOT the bug (already honest):** the 4 grade lines are mutually commensurate on `[0,4]`; the suppression floor + per-trade markers + decoupled badges work correctly. The redesign separates the *incommensurate* series by scale; it does not re-architect the working parts.

---

## §2 Pre-locked decisions + LOCKs (L1–L6, BINDING)

- **L1 — presentation-only.** Do NOT touch the metric COMPUTATIONS ([`swing/metrics/process_grade_trend.py`](../../../swing/metrics/process_grade_trend.py) consumed read-only); no new metrics; no other metrics surfaces. The redesign lives in the VM coordinate-mapping + the template + CSS only.
- **L2 — inline-SVG-only (HARD).** Hand-rolled inline SVG + the existing table. The no-matplotlib / no-JS-chart-lib route test stays green.
- **L3 — NO schema change.** v24 holds; `EXPECTED_SCHEMA_VERSION` stays 24; no migration; no `swing/data` or `swing/trades` write. (Confirmed at brainstorm — §6.)
- **L4 — preserve chart invariants:** the A-6 theme-aware `var(--accent)` stroke/fill (dark-mode); the ≥5-effective-sample suppression floor + per-trade markers; the DECOUPLED badge text elements (drawability / window-not-full / confidence-floor as SEPARATE elements, lesson #23 — these live in the *table*, untouched); the per-metric table (it already shows all 7 — the redesign LEANS on it for `_total`).
- **L5 — nav-date fix:** `build_reviews_pending_vm` sets `session_date = last_completed_session(datetime.now()).isoformat()` (the backward-looking anchor — correct for backward-looking review content, matching the sibling `build_review_vm`; §4), NOT `action_session_for_run`. One-line VM change + a render-assertion test.
- **L6 — binding gate = operator browser-witness:** the redesigned chart is legible (no plunge-lines; each series readable against a meaningful scale) in BOTH light + dark mode; the empty/under-floor DEFAULT state is witnessed (memory `feedback_seeded_gate_masks_default_state`); `/reviews/pending` shows the date matching the other pages. TestClient is structural-only; the legibility judgment is the operator's.

---

## §3 The chart redesign (the design decision — OQ-1)

### §3.1 Options weighed

| Option | Fixes incommensurability? | Keeps trend lines? | Cognitive load | Verdict |
|---|---|---|---|---|
| **(a) Small-multiples** — separate inline-SVG panels by scale (GRADES [0,4] · RATE [0,1] · COST [0,max]) | **Yes, fully** | Yes (all meaningful trends) | Low (one scale per panel) | **RECOMMENDED** |
| (b) Primary grade chart + demote rate/costs to table | Yes (by removal) | Grades only | Lowest | Loses cost/rate trend-as-a-line |
| (c) Secondary right-axis + dashing in one SVG | Partial (still 3 scales: rate + 2 costs) | Yes | High (busy) | Weakest at the actual fix |
| (d) Table-only (drop the chart) | Yes (by removal) | None | Lowest | Loses all trend viz — the page's purpose |

### §3.2 Recommendation: **(a) small-multiples, three stacked inline-SVG panels**

The page's purpose is "is my process improving over time" — an inherently *trend* question, so dropping lines (b/d) discards the headline value. (c) keeps the busy overlay. Small-multiples is the only option that makes each series readable against a scale it actually belongs to, and it establishes a small-multiples precedent (none exists today). **Operator-binding — flagged OQ-1.**

**The three panels (top to bottom), sharing ONE X scale (trade ordinal):**

1. **GRADES panel** — the headline. The 4 grade lines (`process` / `entry` / `management` / `exit`) on a shared `[0,4]` axis with the existing `A=4 B=3 C=2 D=1 F=0` labels. Per-trade `process_grade` `<circle>` markers live here (already on `[0,4]`). Distinct theme-aware per-series colors + a legend (§3.4).
2. **RATE panel** — the `disqualifying_violation_rate_rolling_N` line on `[0,1]`, axis labeled `0.0 / 0.5 / 1.0` (proportion). Single line → `var(--accent)`.
3. **COST panel** — the `mistake_cost_R_rolling_N_per_trade` line (the per-trade *mean*) on a data-driven, **0-anchored** `[0, max]` R axis (§3.5). Single line → `var(--accent)`. `mistake_cost_R_rolling_N_total` (the running SUM) is **demoted to the table** (it already lives there) — OQ-3.

**Shared X scale (key design point):** all three panels reuse the existing `_polyline_x(ordinal, total_points=…)` so the same trade ordinal sits at the same X across panels. The operator can scan a single trade index straight down through grade → violation-rate → mistake-cost. (Vertical gridline alignment is the small-multiples honesty payoff.)

### §3.3 SVG structure (per panel)

Three **separate `<svg>` elements** (each its own `viewBox` + independent Y coordinate system — simplest to reason about and to test; avoids one giant viewBox with manual panel offsets):

```
<section class="metrics-process-grade-trend">
  <h2>Grades</h2>
  <svg viewBox="0 0 800 360" class="process-grade-trend-chart" data-panel="grades" ...>
    <g class="grade-axis-labels" data-marker="grade-axis-encoding"> A=4 B=3 C=2 D=1 F=0 </g>
    <g class="legend" data-marker="grades-legend"> process / entry / management / exit </g>
    {circles: process_grade markers}            <!-- always, when grade letter present -->
    {polylines: 4 grade series, per-series class + color}
  </svg>

  <h2>Disqualifying-violation rate</h2>
  <svg viewBox="0 0 800 160" class="process-grade-trend-chart" data-panel="rate" ...>
    <g class="rate-axis-labels" data-marker="rate-axis"> 0.0 / 0.5 / 1.0 </g>
    {polyline: disqualifying_violation_rate_rolling_N}
  </svg>

  <h2>Mistake cost (R per trade)</h2>
  <svg viewBox="0 0 800 160" class="process-grade-trend-chart" data-panel="cost" ...>
    <g class="cost-axis-labels" data-marker="cost-axis"> 0.0 / mid / max (data-driven) </g>
    {polyline: mistake_cost_R_rolling_N_per_trade}
    <text class="muted" data-marker="cost-axis-caption">running total in table below</text>
  </svg>

  <h2>Per-metric rolling window (most recent)</h2>
  <table ...> {all 7 metrics - UNCHANGED} </table>
</section>
```

- The GRADES panel keeps `viewBox="0 0 800 360"` (the headline keeps its area); RATE + COST are shorter (≈160) since each holds one line. Heights are SVG-layout constants on the VM (§3.6), not hardcoded in the template.
- Each panel carries a `data-panel="grades|rate|cost"` hook + per-axis `data-marker` so TestClient can assert structure.
- The GRADES panel preserves the EXACT existing hooks the current route tests assert: `<svg viewBox`, `data-series="process_grade_rolling_N"`, `<polyline points=`, `class="process-grade-rolling-line metric-process_grade_rolling_N"`, `A=4`, `F=0`, `<circle `. So those tests stay green untouched.

### §3.4 Series identification / legend / theme-aware coloring (OQ-2)

The 4 grade lines in ONE panel cannot all be `var(--accent)` (indistinguishable). **Recommendation: distinct theme-aware colors + a legend** (OQ-2 — recommend distinct colors over dashing; dashing 4 ways is hard to tell apart at 1.5px).

- Introduce **4 theme-aware CSS custom properties** — `--series-process` (alias `var(--accent)`), `--series-entry`, `--series-management`, `--series-exit` — defined in BOTH `:root` (light) and `body.dark` (dark) in `app.css`, chosen for legibility on each background (mirrors how `--accent` already shifts `#0066cc`→`#6ab0ff`). This **preserves L4 theme-awareness** — colors stay tokenized, never hardcoded hex in the SVG.
- Per-series stroke is **additive** on top of the existing rule, using a **TWO-class selector so specificity (not source order) enforces the override** (Codex R1 Major #1 — `.metric-entry_grade_rolling_N` alone is *equal* specificity to `.process-grade-rolling-line`, so a later-declared base rule would silently win):
  - `.process-grade-rolling-line { stroke: var(--accent); }` **stays** (the A-6 test asserts its literal presence → green) and is the default / process-line color.
  - Add `.process-grade-rolling-line.metric-entry_grade_rolling_N { stroke: var(--series-entry); }` (two classes → higher specificity → wins regardless of order), and likewise for `_management_` / `_exit_`. (The `process` line keeps `var(--accent)` = `--series-process`.)
  - `.process-grade-marker { fill: var(--accent); }` **stays** (markers are process-grade only).
- The legend is inline SVG `<text>` + a short colored `<line>`/`<rect>` swatch per grade series, **ASCII labels only** — `process / entry / management / exit` (slash separators, NOT `·`). The matplotlib-mathtext gotcha is N/A for inline SVG, but ASCII discipline applies to all proposed rendered SVG strings (§10).
- RATE + COST panels each have one line → keep `var(--accent)` (no legend needed; the `<h2>` names them).

### §3.5 Cost-panel scale (OQ-3)

- **Chart `_per_trade` only; demote `_total` to the table.** Co-plotting a window *mean* and a window *running SUM* on one axis re-creates the incommensurability inside the cost panel. `_total`'s "trend as a line" is low-value (a running sum); it already appears in the table (L4) — that is sufficient. **Operator-binding — flagged OQ-3.**
- **0-anchor the cost axis:** the cost panel uses `[0, pad(max_finite_per_trade_value)]`, NOT `(raw_min, raw_max)`. Anchoring at 0 makes magnitude honest (a 0.30→0.50 move no longer fills the panel).
- **The all-zero / no-data edge case (Codex R1 Major #2):** when `max_finite_per_trade_value <= 0` (no finite cost values OR every cost is exactly 0.0 — common early, e.g. a perfect-process operator), use bounds **`[0, 1]`**, NOT `[0, 0]`. Reason: the existing `_polyline_y` centers the line when `y_max == y_min` ([`process_grade_trend.py` `_polyline_y`](../../../swing/web/view_models/metrics/process_grade_trend.py)), so `[0,0]` would float a zero-cost line in the panel middle with degenerate `0.0 / 0.0 / 0.0` labels. With `[0,1]`, a 0.0 cost maps to the **bottom baseline** and the axis labels (`0.0 / 0.5 / 1.0`) are non-degenerate. A discriminating test asserts: zero-cost line at the baseline (max Y), non-degenerate labels.
- The cost axis labels are data-driven: `0.0`, a midpoint, and the computed `max` (formatted `%.2f`, ASCII) — except the all-zero case above, which renders the fixed `0.0 / 0.5 / 1.0`.

### §3.6 VM changes (presentation layer only)

- Replace the per-series `_y_axis_bounds_for_metric` "draw-all-in-one-box" mapping with **per-panel** bounds:
  - GRADES: `[0,4]` shared by all 4 grade lines (already commensurate — no change to bounds, only to which SVG they render into).
  - RATE: `[0,1]`.
  - COST: `[0, pad(max)]` 0-anchored over the charted `_per_trade` line, falling back to `[0, 1]` when `max <= 0` (§3.5).
- Add a **panel discriminator** so the template routes each series to its panel — e.g. a `panel: str` field on `RollingSeriesDisplay` (values `"grades" | "rate" | "cost" | "table_only"`), OR the VM emits three grouped tuples (`grade_series`, `rate_series`, `cost_series`). Recommend the grouped-tuples shape (the template stays a simple per-panel loop; `_total` is simply not placed in any panel group but still flows to the table loop). `mistake_cost_R_rolling_N_total` → `table_only`.
- Per-panel SVG layout constants (height per panel) become VM fields (`grades_svg_height=360`, `rate_svg_height=160`, `cost_svg_height=160`), mirroring the existing `svg_*` constants. X mapping (`_polyline_x`) is shared/unchanged.
- The `is_drawable` gate + segmented-polyline (F-3 None-gap splitting) logic is **unchanged per series** — it just runs within each panel's bounds.

### §3.7 Suppression floor / decoupled badges / empty-state in the new layout (L4, L6)

- **Empty state (no trades):** the single `data-empty-state="process-grade-trend"` `<em>` wraps ALL three panels (unchanged) — no panels render. Existing test stays green.
- **Under-floor (trades exist, <5 effective samples):** the GRADES panel renders its axis + the `process_grade` `<circle>` markers (markers always render) + NO grade polylines; the RATE + COST panels render their axes + NO line + a small `data-marker="<panel>-under-floor"` caption — rendered string `rolling line draws once the window has >=5 effective samples` (ASCII `>=`, not the glyph). This makes the DEFAULT state honest and **witnessable** (L6 / `feedback_seeded_gate_masks_default_state`) — the operator sees axes + markers, not a blank box.
- **Decoupled badges (lesson #23):** UNCHANGED — they live in the per-metric *table* rows (`data-marker="drawability-…"` / `window-warning-…` / `floor-warning-…`), not in the SVG. The redesign does not touch them; `test_…_renders_separate_decoupled_badge_text_elements` stays green.
- **Per-trade markers:** unchanged — `process_grade` circles in the GRADES panel only.

---

## §4 The nav-date fix (§0.3 / L5)

**Bug:** `/reviews/pending`'s shared topbar `<span class="date">{{ vm.session_date }}</span>` ([`base.html.j2:69`](../../../swing/web/templates/base.html.j2)) renders blank because [`build_reviews_pending_vm`](../../../swing/web/view_models/trades.py) never sets `session_date`. `ReviewsPendingVM` is **not** a `BaseLayoutVM` subclass — it redefines the field with `session_date: str = ""` and has no non-empty guard (unlike `BaseLayoutVM.__post_init__`, which *raises* on empty), so the empty default silently slips through. (Every page's VM is expected to set `session_date`; this one simply doesn't.)

**Fix (one line + a local import):** in `build_reviews_pending_vm`'s `return ReviewsPendingVM(...)`, add:
```python
session_date=last_completed_session(datetime.now()).isoformat(),
```
- `last_completed_session` — the **backward-looking anchor** (NOT `action_session_for_run`). Topbar anchors are a MIX across the app: forward-looking/navigator pages (dashboard, watchlist, metrics-index) use `action_session_for_run`; backward-looking content pages use `last_completed_session`. `/reviews/pending` is backward-looking content (it lists already-*closed* trades awaiting review), so it should match its sibling review page [`build_review_vm`](../../../swing/web/view_models/trades.py) (`session_date = last_completed_session(...).isoformat()`, ~line 1351), NOT the forward-looking navigator anchor. `last_completed_session` also avoids the weekend/evening silent-blank that `action_session_for_run` would cause for backward-looking content (the session-anchor read/write gotcha). OQ-4 confirms. The test (below) asserts the requested anchor *directly* — it does not assert "matches other pages."
- Imports: `datetime` is already module-level in `trades.py` (`from datetime import … datetime …`); add the local `from swing.evaluation.dates import last_completed_session` inside the function (mirrors `build_review_vm:1351`).
- **No schema/base-VM impact:** this sets an EXISTING field; the shared-`base.html.j2` 5-VM rule is NOT triggered (no new `vm.foo`).

**Test:** a render-assertion test — GET `/reviews/pending` with `TestClient`, assert the topbar `<span class="date">` is non-empty and equals `last_completed_session(now).isoformat()` (compute the expected value the same way, per the regression-test-arithmetic discipline: under the pre-fix path the span is empty `""`; under the post-fix path it is the ISO date — the test distinguishes).

---

## §5 Test strategy + the operator browser gate

### §5.1 Structural tests (TestClient — adapt/add)
- **Stay green untouched** (GRADES panel preserves the exact hooks): `endpoint_returns_200`, `registered_in_app_routes`, `extends_base_layout`, `renders_empty_state_when_no_trades`, `renders_svg_polyline_when_window_drawable` (process_grade polyline + class), `renders_per_trade_circles_always` (n=2 → circles, no polyline), `renders_separate_decoupled_badge_text_elements` (table), `grade_axis_encoding_labels_visible` (`A=4`/`F=0`), `does_not_use_matplotlib_or_external_chart_lib`.
- **New assertions:** three `data-panel="grades|rate|cost"` `<svg>` elements present when drawable; the rate axis labels (`0.0`/`1.0`) and cost axis labels (`0.0`/data-driven max) present; the grades legend (`data-marker="grades-legend"`) names all 4 series; the rate line `data-series="disqualifying_violation_rate_rolling_N"` renders in the rate panel; the cost line `data-series="mistake_cost_R_rolling_N_per_trade"` renders in the cost panel; `mistake_cost_R_rolling_N_total` does NOT render a polyline (table-only) but DOES still appear as a table row; the under-floor captions render when 1 ≤ trades < 5 (witness the default state structurally).
- **VM tests** (`tests/web/test_view_models/test_process_grade_trend_vm.py`): update for the new per-panel grouping + 0-anchored cost bounds; the metric-name set / suppression / segmented-polyline contracts are unchanged.
- **CSS test** (`tests/web/test_app_css_process_grade.py`): the existing 4 assertions (`.process-grade-rolling-line`, `.process-grade-marker`, `stroke: var(--accent)`, `fill: var(--accent)`) stay green (additive); add assertions that the 4 `--series-*` tokens are defined under BOTH `:root` and `body.dark`.
- **nav-date test:** §4.

### §5.2 The operator browser gate (L6 — BINDING)
TestClient asserts structure only. The operator drives a real browser and confirms:
1. **Legibility, light + dark:** each panel reads against its own labeled scale; no plunge-lines; the 4 grade colors are distinguishable and the legend is correct; dark mode shows all lines (the `--series-*` + `--accent` tokens resolve).
2. **The empty/under-floor DEFAULT state** (≤4 reviewed trades): axes + process-grade markers + the under-floor captions render — no blank box (the seeded-gate-masks lesson).
3. **`/reviews/pending`** shows a non-empty topbar date (the `last_completed_session` ISO date), no longer blank.
Merge is blocked until the operator confirms all three.

---

## §6 Schema impact

**NONE.** Schema v24 holds; `EXPECTED_SCHEMA_VERSION` stays 24. No migration, no `swing/data` or `swing/trades` write. Both items are pure presentation: a VM/template/CSS refactor (chart) + a VM one-liner reading an existing session helper (nav-date). The metric computations are consumed read-only (L1).

---

## §7 Slice recommendation (for writing-plans)

A single small cycle, two independent slices:
- **Slice A — the nav-date fix** (trivial, ship first): the one-line VM change + the render test. Independent of the chart; lowest risk; unblocks the operator's reported topbar bug immediately.
- **Slice B — the chart redesign:** (B1) introduce the `--series-*` theme tokens + per-series CSS (additive); (B2) VM per-panel grouping + 0-anchored cost bounds + panel SVG-height constants; (B3) template: split the one `<svg>` into three panels + legend + under-floor captions; (B4) adapt/add the structural + VM + CSS tests. TDD per task. The operator browser gate (§5.2) runs at the end of Slice B (chart) and a quick check at Slice A (nav-date).

---

## §8 V1 simplifications + V2 candidates

**V1 simplifications:**
- Cost panel charts `_per_trade` only; `_total` is table-only (OQ-3).
- No per-trade markers in the rate/cost panels (grades panel keeps process-grade markers).
- Three separate `<svg>` elements (not one composite viewBox with manual offsets).
- X axis = trade ordinal (no calendar-date X axis), unchanged from today.

**V2 candidates:**
- Disqualifying-violation markers on the rate panel (per-trade dots like the grades panel).
- A calendar/date X axis (today it is ordinal-spaced).
- Operator-configurable window N (today hardcoded N=10 per the computation LOCK).
- A composite `<svg>` with shared vertical gridlines drawn across panels (stronger visual ordinal alignment).
- Charting `_total` in its own 4th panel if the operator wants its trend after all.

---

## §9 Operator decision items (the OQs)

1. **OQ-1 — the layout (BINDING, the core UX call).** Recommend **(a) small-multiples** (three scale-separated inline-SVG panels). Alternatives: primary-grade-chart + table-for-the-rest (b); secondary-axis (c); table-only (d). → §3.
2. **OQ-2 — per-series color.** Recommend **distinct theme-aware colors per grade line + a legend** (4 new `--series-*` tokens, light+dark) over single-`--accent`-with-dashing. → §3.4.
3. **OQ-3 — cost-panel scale.** Recommend **chart `_per_trade` only, 0-anchored `[0,max]`; `_total` table-only.** → §3.5.
4. **OQ-4 — nav-date anchor.** Confirm **`last_completed_session`** (backward-looking; correct for backward-looking review content; matches the sibling `build_review_vm`). Recommend yes. → §4.
5. **OQ-5 — scope.** Recommend **redesign-only** — no adjacent metrics-card affordance, no `/metrics` overview change.

---

## §10 Cumulative-discipline compliance

- **Web/HTMX/forms gotchas:** shared-`base.html.j2` 5-VM rule NOT triggered (neither item adds a new `vm.foo`; nav-date sets an existing field). Pure server-rendered HTML — no HTMX OOB-swap / HX-Redirect / embedded forms on this surface (the §A.9/§I.6 LOCK). Matplotlib-mathtext gotcha N/A (inline SVG, not matplotlib).
- **Session-anchor read/write gotcha:** nav-date uses the backward-looking `last_completed_session` (L5/OQ-4) — the writer-anchor family fix.
- **ASCII (#16/#32):** all PROPOSED rendered SVG strings are ASCII (Codex R1 Minor #1) — legend `process / entry / management / exit` (slash, not `·`); axis labels `A=4 B=3 C=2 D=1 F=0`, `0.0 / 0.5 / 1.0`, data-driven `%.2f`; under-floor caption `... >=5 effective samples` (`>=`, not the glyph). (Browser SVG is UTF-8 so a glyph would not crash like a CLI cp1252 path, but the discipline is honored for consistency with the existing surface's intent.)
- **Regression-test-arithmetic (memory):** the nav-date test distinguishes pre-fix (`""`) vs post-fix (ISO date); the cost-axis test distinguishes pre-fix `(raw_min,raw_max)` vs post-fix 0-anchored bounds.
- **A-6 / L4:** the existing `.process-grade-rolling-line`/`.process-grade-marker` + `var(--accent)` CSS rules are preserved (additive `--series-*` tokens); the suppression floor, per-trade markers, decoupled badges, and table all survive.
- **Commits:** conventional; NO `Co-Authored-By`; NO `--no-verify`; final `-m` paragraph plain prose; verify `git log -1 --format='%(trailers)'` is `[]` before any push (trailer-parse-hazard memory).

---

## §11 Position note

This is the THIRD commissioned Phase-15 arc (after the schwabdev-v3 upgrade `#20` + B-7 failure-mode `#21`, both CLOSED) and the **lightest yet**: presentation-only, NO schema change, NO migration, NO lock, NO live cutover, NO live-DB touch. It resolves the operator-reported plunge-line incommensurability on `/metrics/process-grade-trend` and the blank topbar date on `/reviews/pending` (both reported 2026-06-03). The binding gate is an operator browser-witness (both light/dark + the empty/under-floor default + the fixed nav-date). Output of this brainstorming phase: this design spec, from which the writing-plans phase derives the implementation plan.

---

*End of design spec. Process-grade-trend chart redesign (small-multiples: GRADES [0,4] · RATE [0,1] · COST [0,max] 0-anchored, per_trade-only) + the reviews-page nav-date one-liner (`last_completed_session`), within the inline-SVG-only LOCK, preserving the A-6 theme-aware stroke + suppression floor + decoupled badges + the existing table.*
