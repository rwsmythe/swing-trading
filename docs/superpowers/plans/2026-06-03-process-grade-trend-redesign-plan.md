# Process-Grade-Trend Chart Redesign (+ reviews nav-date fix) — Implementation Plan

**Date:** 2026-06-03 · **Phase:** 15 (third commissioned arc — presentation-only; the lightest yet)
**Spec (AUTHORITATIVE):** [`docs/superpowers/specs/2026-06-03-process-grade-trend-redesign-design.md`](../specs/2026-06-03-process-grade-trend-redesign-design.md) (236 lines; brainstorm merged + Codex-converged R2 `NO_NEW_CRITICAL_MAJOR`)
**Brief:** [`docs/process-grade-trend-redesign-writing-plans-dispatch-brief.md`](../../process-grade-trend-redesign-writing-plans-dispatch-brief.md)
**Branch base:** `5ab6878e` (the commit that adds the writing-plans dispatch brief, on top of brainstorm `bdde2aa5`)
**Status:** writing-plans output — TDD task list for `copowers:executing-plans`. NO code in this document.

---

## §0 Scope, LOCKs, and what this plan is NOT

Two **independent** items, **presentation-only**, in a **single small cycle, two slices** (Slice A ships first):

1. **Slice A — the nav-date fix** (one VM line + a render test): `/reviews/pending`'s shared topbar date is blank because `build_reviews_pending_vm` never sets `session_date`. Set it to `last_completed_session(datetime.now()).isoformat()` (backward-looking, matching the sibling `build_review_vm`).
2. **Slice B — the chart redesign** (4 tasks): replace the single 800×360 inline `<svg>` that overlays 7 incommensurate series on ONE grade axis with **small-multiples — three scale-separated inline-SVG panels** (GRADES `[0,4]` · RATE `[0,1]` · COST `[0,max]` 0-anchored, `_per_trade` only). Distinct theme-aware `--series-*` colors + a legend via a **two-class CSS selector** (specificity, not source order). The all-zero cost edge uses `[0,1]` (not `[0,0]`). Under-floor captions make the default state witnessable. `_total` is demoted to the (unchanged) table.

### LOCKs (BINDING — from spec §2 + the OQ resolutions; do NOT re-litigate)
- **L1 — presentation-only.** The metric COMPUTATIONS ([`swing/metrics/process_grade_trend.py`](../../../swing/metrics/process_grade_trend.py)) are consumed READ-ONLY. No new metrics, no other metrics surfaces. The redesign lives in the **VM coordinate-mapping + the template + CSS only**.
- **L2 — inline-SVG-only (HARD).** Hand-rolled inline `<svg>` + the existing server-rendered table. NO matplotlib, NO Chart.js/D3, NO client-side renderer. `test_process_grade_trend_does_not_use_matplotlib_or_external_chart_lib` stays green.
- **L3 — NO schema change.** v24 holds; `EXPECTED_SCHEMA_VERSION` stays 24; no migration; no `swing/data` or `swing/trades` write.
- **L4 — preserve chart invariants:** the A-6 theme-aware `var(--accent)` stroke/fill (the existing 4 CSS assertions stay green — additive `--series-*` tokens); the ≥5-effective-sample suppression floor + per-trade `process_grade` markers; the DECOUPLED badge text elements (in the *table*, lesson #23 — untouched); the per-metric table (the redesign LEANS on it for `_total`).
- **L5 — nav-date** uses `last_completed_session` + a render-assertion test.
- **L6 — binding gate = operator browser-witness:** legibility light + dark; the empty/under-floor DEFAULT state witnessed (memory `feedback_seeded_gate_masks_default_state`); `/reviews/pending` shows the date. TestClient is structural-only. **Merge blocked until the operator confirms** (§7).

### OQ resolutions reflected (operator-LOCKed 2026-06-03; all 5)
- **OQ-1** = small-multiples, 3 stacked inline-SVG panels sharing one X ordinal — §3 / Slice B.
- **OQ-2** = distinct theme-aware `--series-*` colors + legend, two-class selector — Task B1.
- **OQ-3** = chart `mistake_cost_R_rolling_N_per_trade` ONLY, 0-anchored `[0,max]` with `[0,1]` all-zero fallback; `_total` table-only — Tasks B2/B3.
- **OQ-4** = nav-date `last_completed_session(datetime.now()).isoformat()` — Task A1.
- **OQ-5** = redesign-only (no `/metrics` overview change, no adjacent affordance).

### OUT OF SCOPE (do NOT plan into V1)
Metric-computation changes (L1); matplotlib / JS chart lib (L2); schema/migration (L3); new metrics / other surfaces / the `/metrics` overview card; charting `_total`; per-trade markers in the rate/cost panels; a calendar (non-ordinal) X axis; operator-configurable window N. (V2 candidates per spec §8.)

---

## §0.5 Background for a fresh implementer (read before touching code)

You may arrive at this plan with no prior context. Here is what you need to know:

**The bug (chart).** `GET /metrics/process-grade-trend` renders ONE 800×360 inline `<svg>` that overlays **7 incommensurate rolling series** on a single grade-labeled axis (`A=4 … F=0`). The VM's `_y_axis_bounds_for_metric` normalizes each series into its own honest range — grades `[0,4]`, the disqualifying-violation rate `[0,1]`, the mistake-cost lines `(raw_min, raw_max)` — but then `_format_polyline_segments` draws **all** of them into the **same** plot box, of which only the grade axis is labeled. Three consequences: (1) the rate line (a proportion) is read against `A=4…F=0` and means nothing; (2) the cost lines are NOT 0-anchored, so a `0.30→0.50 R` drift fills the whole panel ("plunge-lines"); (3) the two cost lines are themselves incommensurate (`_per_trade` is a window *mean* ~0.3 R; `_total` is a window running *SUM* ~N× larger). Small-multiples (three panels, one scale each) is the only option that makes every series readable against a scale it actually belongs to — that is OQ-1, operator-LOCKed.

**The bug (nav-date).** `/reviews/pending`'s shared topbar `<span class="date">{{ vm.session_date }}</span>` is blank because `ReviewsPendingVM` is NOT a `BaseLayoutVM` subclass — it redefines `session_date: str = ""` with no non-empty guard (unlike `BaseLayoutVM.__post_init__`, which raises on empty), and `build_reviews_pending_vm` never sets it. Every other page's VM sets `session_date`; this one simply doesn't.

**What is already correct (do NOT re-architect):** the 4 grade lines are mutually commensurate on `[0,4]`; the ≥5-effective-sample suppression floor, the per-trade `process_grade` `<circle>` markers, the F-3 None-gap polyline segmentation, and the decoupled badge text in the table all work. The redesign **separates the incommensurate series by scale** — it does not rebuild the working parts.

**The hard constraint (L2):** the fix stays hand-rolled inline `<svg>` + the existing server-rendered table. No matplotlib, no Chart.js/D3, no client-side renderer.

### The verbatim GRADES-panel polyline fragment to PRESERVE (B3)
The current template (lines 55-65) emits, for each drawable series:
```jinja
{% for series in vm.rolling_series %}
  {% if series.is_drawable %}
    {% for seg in series.svg_polyline_segments %}
    <polyline points="{{ seg }}"
              fill="none"
              stroke-width="1.5"
              data-series="{{ series.metric_name }}"
              class="process-grade-rolling-line metric-{{ series.metric_name }}" />
    {% endfor %}
  {% endif %}
{% endfor %}
```
In B3 the GRADES panel reuses this **exact fragment shape** but loops `vm.grade_series` (4 series) instead of `vm.rolling_series` (7). The `<polyline>` attributes — `fill="none"`, `stroke-width="1.5"`, `data-series=`, `class="process-grade-rolling-line metric-…"` — are byte-identical, so the `process_grade_rolling_N` polyline assertions (route test 5) pass unchanged. The rate/cost panels reuse the same `<polyline>` attribute shape for their single lines.

---

## §1 Re-grepped surface anchors (verified at branch base `5ab6878e`; line numbers WILL shift again — re-grep at executing-plans STEP 0, discipline #2)

**Chart (Slice B):**
- Route: [`swing/web/routes/metrics.py:216-231`](../../../swing/web/routes/metrics.py) — `metrics_process_grade_trend` → `build_process_grade_trend_vm(cfg=cfg)` → `TemplateResponse(request, "metrics/process_grade_trend.html.j2", {"vm": vm})`. **UNCHANGED** by this arc.
- VM: [`swing/web/view_models/metrics/process_grade_trend.py`](../../../swing/web/view_models/metrics/process_grade_trend.py):
  - SVG constants `SVG_WIDTH=800`, `SVG_HEIGHT=360`, margins L56/R16/T24/B40 (lines ~50-56).
  - `GRADE_AXIS_LABELS` `(value, label)` tuples (lines ~60-66).
  - `RollingSeriesDisplay` dataclass (lines ~69-103): fields incl. `metric_name`, `underlying_class`, `svg_polyline_segments`, `is_drawable`, badge texts.
  - `PerTradeMarkerDisplay` (lines ~105-124).
  - `ProcessGradeTrendVM(BaseLayoutVM)` (lines ~126-161): fields `window_size`, `per_trade_markers`, `rolling_series`, `svg_*`, `grade_axis_labels`. `__post_init__` REQUIRES `{s.metric_name for s in rolling_series} == set(PROCESS_GRADE_TREND_METRIC_CLASSES)` (all 7).
  - `_GRADE_METRICS` frozenset (lines ~173-178).
  - `_polyline_x` (~225-238), `_polyline_y` (~241-259; **centers the line when `y_max==y_min`** — the [0,1] fallback rationale), `_format_polyline_segments` (~262-312; F-3 None-gap split — **INVARIANT**), `_y_axis_bounds_for_metric` (~315-335; cost branch returns `(raw_min,raw_max)` / `(raw_min-0.5,raw_max+0.5)` — NOT 0-anchored).
  - `_build_rolling_display` (~338-404): takes `layout_height` + derives bounds via `_y_axis_bounds_for_metric`.
  - `build_process_grade_trend_vm` (~454-519): builds `markers` + `rolling_displays`; returns the VM with `session_date=action_session_for_run(...)` (forward-looking — CORRECT for this metrics navigator page; **NOT touched** by the nav-date fix, which is `/reviews/pending`).
- Template: [`swing/web/templates/metrics/process_grade_trend.html.j2`](../../../swing/web/templates/metrics/process_grade_trend.html.j2):
  - lines 1-22: extends base; heading; the `&ge;5 effective samples` muted prose; `data-empty-state` guard `{% if vm.per_trade_markers|length == 0 %}`.
  - lines 24-66: the **single `<svg viewBox="0 0 {{vm.svg_width}} {{vm.svg_height}}">`** → grade-axis-labels (`data-marker="grade-axis-encoding"`), per-trade `<circle>` markers, then `{% for series in vm.rolling_series %}{% if series.is_drawable %}<polyline ... class="process-grade-rolling-line metric-{{series.metric_name}}">`. **This `<svg>` block is REPLACED with three panels.**
  - lines 68-120: the 7-row `<table>` (`{% for series in vm.rolling_series %}`). **UNCHANGED.**
- CSS: [`swing/web/static/app.css`](../../../swing/web/static/app.css):
  - `:root { --accent: #0066cc; ... }` (`--accent` @ line ~35).
  - the **combined** dark block `html.dark,` / `body.dark { --accent: #6ab0ff; ... }` (selector @ lines ~96-97; `--accent` @ ~122) — the FOUC-prevention pairing; add the `--series-*` tokens HERE (Codex R1-m2), not a standalone `body.dark`.
  - `.process-grade-rolling-line { stroke: var(--accent); }` (~338) + `.process-grade-marker { fill: var(--accent); }` (~339). **STAY (A-6 test asserts the literal strings).**
- Metric matrix (read-only, L1): [`swing/metrics/process_grade_trend.py:68-76`](../../../swing/metrics/process_grade_trend.py) — `PROCESS_GRADE_TREND_METRIC_CLASSES` (7 keys). `RollingLinePoint`, `compute_process_grade_trend` consumed read-only.

**Nav-date (Slice A):**
- [`swing/web/templates/base.html.j2:69`](../../../swing/web/templates/base.html.j2) — `<span class="date">{{ vm.session_date }}</span>` (shared topbar).
- [`swing/web/view_models/trades.py`](../../../swing/web/view_models/trades.py):
  - `ReviewsPendingVM` dataclass @ ~1454-1487: `session_date: str = ""` default @ ~1459 (NOT a `BaseLayoutVM` subclass — redefines the field, no non-empty guard, so the empty default slips through).
  - `build_reviews_pending_vm(*, cfg)` @ ~1490-1518: builds `trades` + banner counts; the `return ReviewsPendingVM(...)` @ ~1512-1518 **does NOT pass `session_date`**.
  - Sibling precedent `build_review_vm` @ ~1230: `from swing.evaluation.dates import last_completed_session` @ ~1247; `session_date = last_completed_session(_dt.now()).isoformat()` @ ~1351; `session_date=session_date` @ ~1387.
  - Module-level `from datetime import date, datetime, timedelta` @ line 6 → `datetime` is available unqualified inside `build_reviews_pending_vm`.
- `last_completed_session` lives in [`swing/evaluation/dates.py`](../../../swing/evaluation/dates.py).

---

## §2 File map (every file this arc touches)

| File | Slice / Task | Change |
|---|---|---|
| `swing/web/view_models/trades.py` | A1 | `build_reviews_pending_vm` returns `session_date=last_completed_session(datetime.now()).isoformat()` + a local import. |
| `swing/web/static/app.css` | B1 | Add 4 `--series-*` tokens under `:root` AND the combined `html.dark, body.dark` block; add the two-class per-series stroke rules + the legend-swatch fill rules. Existing rules untouched. |
| `swing/web/view_models/metrics/process_grade_trend.py` | B2 | Per-panel height constants; cost-panel 0-anchored bounds helper + `[0,1]` fallback; `_build_rolling_display` `bounds_override`; new VM fields (`grade_series`/`rate_series`/`cost_series`, panel heights, `rate_axis_labels`/`cost_axis_labels`, `cost_y_max`); additive `__post_init__` group validation. `rolling_series` (all 7) UNCHANGED. |
| `swing/web/templates/metrics/process_grade_trend.html.j2` | B3 | Replace the single `<svg>` (lines 24-66) with three `<svg>` panels + legend + under-floor captions + cost caption. Table (68-120) + empty-state guard UNCHANGED. |
| `tests/web/view_models/.../test_..._vm.py` + route + css tests | A1, B1-B4 | New assertions (additive); existing assertions preserved. See §3 + per-task. |

**No** changes to: `swing/metrics/`, `swing/data/`, `swing/trades/`, migrations, `EXPECTED_SCHEMA_VERSION`, the route handler, `_polyline_x`, `_polyline_y`, `_format_polyline_segments`, the table markup, the empty-state branch.

---

## §3 Test-preservation enumeration (§1.2 — the #1 risk; the GRADES panel keeps its exact hooks)

### 3a. Existing tests that STAY GREEN **UNTOUCHED** (the redesign must not alter their assertions)
**Route — [`tests/web/test_routes/test_metrics_process_grade_trend_route.py`](../../../tests/web/test_routes/test_metrics_process_grade_trend_route.py):**
1. `test_process_grade_trend_endpoint_returns_200` — `"Process-grade trend"` in text.
2. `test_process_grade_trend_endpoint_registered_in_app_routes` — route registered.
3. `test_process_grade_trend_extends_base_layout` — `class="topbar"` present.
4. `test_process_grade_trend_renders_empty_state_when_no_trades` — `data-empty-state="process-grade-trend"` (empty-state guard wraps all three panels; UNCHANGED).
5. `test_process_grade_trend_renders_svg_polyline_when_window_drawable` (n=5) — `"<svg viewBox"`, `data-series="process_grade_rolling_N"`, `"<polyline points="`, `class="process-grade-rolling-line metric-process_grade_rolling_N"`. → **The GRADES panel preserves all four hooks verbatim.**
6. `test_process_grade_trend_renders_per_trade_circles_always` (n=2) — `"<circle "` present AND **`"<polyline" not in r.text`**. → **TRAP: the under-floor panels + legend swatches MUST emit ZERO `<polyline>`** — captions are `<text>`, legend swatches are `<rect>`/`<line>`. At n=2 every series is under the 5-floor → no panel emits a polyline. Verified in B3.
7. `test_process_grade_trend_renders_separate_decoupled_badge_text_elements` (n=5) — table `data-marker="drawability-…/window-warning-…/floor-warning-…"`. → table UNCHANGED.
8. `test_process_grade_trend_grade_axis_encoding_labels_visible` (n=3) — `"A=4"`, `"F=0"`. → GRADES panel keeps `grade-axis-labels`.
9. `test_process_grade_trend_does_not_use_matplotlib_or_external_chart_lib` (n=5) — no `matplotlib`/`chart.js`/`d3.min.js`. → inline SVG only.

**VM — [`tests/web/test_view_models/test_process_grade_trend_vm.py`](../../../tests/web/test_view_models/test_process_grade_trend_vm.py):** all 11 stay green:
`test_vm_is_base_layout_vm`, `test_vm_carries_base_layout_fields`, `test_vm_has_seven_rolling_series_per_a21_matrix` (← **`rolling_series` MUST remain all 7** — panel groups are ADDITIVE), `test_vm_zero_trades_no_markers_all_suppressed`, `test_per_trade_markers_emit_in_review_order`, `test_per_trade_markers_render_for_disqualifying_trade`, `test_polyline_emitted_when_window_partial_drawable` (process series in `rolling_series`, bounds `[0,4]` @ height 360), `test_polyline_omitted_when_suppressed`, `test_grade_axis_labels_carry_numeric_encoding_text`, `test_decoupled_fields_are_distinct_template_targets`, `test_vm_rejects_missing_metric_key`, `test_rolling_series_display_rejects_empty_placeholder_when_suppressed`.

**Segments — [`tests/web/view_models/metrics/test_process_grade_trend_segments.py`](../../../tests/web/view_models/metrics/test_process_grade_trend_segments.py):** all 5 stay green (`_format_polyline_segments` signature + behavior INVARIANT).

**CSS — [`tests/web/test_app_css_process_grade.py`](../../../tests/web/test_app_css_process_grade.py):** `test_process_grade_css_rules_present` — `.process-grade-rolling-line`, `.process-grade-marker`, `stroke: var(--accent)`, `fill: var(--accent)` all stay (additive change).

### 3b. NEW assertions added (per spec §5.1)
- **Route (B3/B4):** three `data-panel="grades|rate|cost"` `<svg>` present when drawable; `data-marker="grades-legend"` names all 4 series ASCII `process / entry / management / exit`; `data-marker="rate-axis"` shows `0.0`/`1.0`; `data-marker="cost-axis"` shows `0.0` + the data-driven max; the rate line `data-series="disqualifying_violation_rate_rolling_N"` renders inside the rate panel; the cost line `data-series="mistake_cost_R_rolling_N_per_trade"` renders inside the cost panel; `mistake_cost_R_rolling_N_total` renders **NO** polyline but **DOES** appear as a table row; under-floor captions (`data-marker="rate-under-floor"`/`"cost-under-floor"`) render when `1 ≤ trades < 5`; cost caption `data-marker="cost-axis-caption"`.
- **VM (B2):** `grade_series`/`rate_series`/`cost_series` grouping + names; 0-anchored cost bounds (`cost_y_max`) + the `[0,1]` all-zero fallback + the baseline-Y discriminator; per-panel heights; `rate_axis_labels`/`cost_axis_labels`; additive `__post_init__` group validation.
- **CSS (B1):** the 4 `--series-*` tokens defined under BOTH `:root` and the combined `html.dark, body.dark` block (block-scoped assertions); the two-class per-series stroke rules; the legend-swatch fill rules.

---

## §4 SLICE A — the nav-date fix

> Ship first; independent of the chart; unblocks the operator's reported blank-topbar bug. One task.

### Task A1 — `build_reviews_pending_vm` stamps `session_date`

**Files:** `swing/web/view_models/trades.py`; new test in `tests/web/test_routes/test_trades_route.py` (the existing reviews-pending route test module) OR a focused `tests/web/test_view_models/test_reviews_pending_session_date.py`.

**(a) Failing test first** — render-assertion, pre-fix-vs-post-fix distinguishing (memory `feedback_regression_test_arithmetic`). **Freeze the clock** (Codex R1-M2: two independent `datetime.now()` calls can straddle a session boundary → flake; the module-level `datetime` is monkeypatchable precisely because the fix uses it unqualified):
```
test_reviews_pending_topbar_date_is_last_completed_session(seeded_db, monkeypatch):
  import re
  from datetime import datetime
  import swing.web.view_models.trades as trades_mod
  from swing.evaluation.dates import last_completed_session
  FIXED = datetime(2026, 6, 3, 21, 0, 0)          # any fixed instant
  class _FrozenDT(datetime):
      @classmethod
      def now(cls, tz=None):
          return FIXED
  monkeypatch.setattr(trades_mod, "datetime", _FrozenDT)   # build_reviews_pending_vm resolves the module-global name at call time
  expected = last_completed_session(FIXED).isoformat()     # computed from the SAME frozen instant
  app = create_app(cfg, cfg_path)
  with TestClient(app) as client:
      r = client.get("/reviews/pending")
  assert r.status_code == 200
  m = re.search(r'<span class="date">([^<]*)</span>', r.text)
  assert m is not None and m.group(1).strip() == expected
```
- **Pre-fix arithmetic:** `session_date` defaults to `""` → the span inner text is `""` → `"" == expected` (a real ISO date `2026-06-03`) is `False` → **FAILS**.
- **Post-fix arithmetic:** the route's `build_reviews_pending_vm` calls the monkeypatched module-level `datetime.now()` → `FIXED`; `session_date == last_completed_session(FIXED).isoformat() == expected` → **PASSES**.
- The test distinguishes AND is deterministic — the route and the assertion share `FIXED`, so no wall-clock race. (This is the concrete reason the fix uses the module-level `datetime`, not a local import: it must be monkeypatchable by name.) The test asserts the **requested anchor directly** — it does NOT assert "matches other pages."

**(b) Minimal implementation:**
```python
# inside build_reviews_pending_vm, add a local import (mirror build_review_vm):
from swing.evaluation.dates import last_completed_session
# ... in the return ReviewsPendingVM(...):
    session_date=last_completed_session(datetime.now()).isoformat(),
```
- `datetime` is already module-level (line 6) — use it unqualified (`build_review_vm` aliases `_dt` only because it imports `datetime as _dt` locally; the module-level `datetime` is in scope here, so no local datetime import is needed).
- `last_completed_session` — the **backward-looking** anchor (NOT `action_session_for_run`): `/reviews/pending` is backward-looking content (it lists already-closed trades awaiting review), matching the sibling `build_review_vm`, and avoids the weekend/evening silent-blank of the forward-looking anchor (the session-anchor read/write gotcha).

**(c) Commit stem:** `fix(web): stamp session_date on reviews-pending VM (last_completed_session)`

**(d) Locks / gotchas touched:** L5 (nav-date uses `last_completed_session` + render test). Session-anchor read/write gotcha (backward-looking content → backward-looking anchor). **No new `vm.foo`** → the shared-`base.html.j2` 5-VM rule is NOT triggered (sets an EXISTING field). L3 (no schema). ASCII (ISO date is ASCII).

---

## §5 SLICE B — the chart redesign (small-multiples)

> Four tasks, TDD per task. Order: B1 (CSS) → B2 (VM) → B3 (template) → B4 (structural sweep + green-bar verification). The operator browser gate (§7) runs at the end of Slice B.

### Task B1 — `--series-*` theme tokens + per-series two-class CSS (additive)

**Files:** `swing/web/static/app.css`; `tests/web/test_app_css_process_grade.py`.

**(a) Failing tests first** (additive — the existing 4 assertions stay). **Scope each token assertion to its actual selector block** (Codex R1-M4: a global `count >= 2` falsely passes on two declarations in one block; the dark selector is the COMBINED `html.dark, body.dark {…}` block — Codex R1-m2, verified at `app.css:96-97`):
```
def _block(css, selector_line):
    # return the text between `selector_line` ... and its closing '}' (first one)
    start = css.index(selector_line)
    end = css.index("}", start)
    return css[start:end]

def test_series_tokens_defined_in_both_theme_blocks():
    css = Path("swing/web/static/app.css").read_text(encoding="utf-8")
    root = _block(css, ":root {")
    dark = _block(css, "html.dark,\nbody.dark {")     # the combined FOUC-prevention dark block
    for token in ("--series-process", "--series-entry", "--series-management", "--series-exit"):
        assert (token + ":") in root, f"{token} missing from :root"
        assert (token + ":") in dark, f"{token} missing from html.dark,body.dark"

def test_per_series_two_class_stroke_rules_present():
    css = Path("swing/web/static/app.css").read_text(encoding="utf-8")
    assert ".process-grade-rolling-line.metric-entry_grade_rolling_N { stroke: var(--series-entry); }" in css
    assert ".process-grade-rolling-line.metric-management_grade_rolling_N { stroke: var(--series-management); }" in css
    assert ".process-grade-rolling-line.metric-exit_grade_rolling_N { stroke: var(--series-exit); }" in css
    assert ".process-grade-rolling-line { stroke: var(--accent); }" in css   # base rule + A-6 STAYS

def test_legend_swatch_fill_rules_present():
    # Codex R1-M3: pin the legend swatch coloring (SVG presentation attrs cannot
    # take var(); the swatch <rect> must resolve its fill via a CSS rule, NOT a
    # default/black fill). Mirror the two-class specificity pattern on fill.
    css = Path("swing/web/static/app.css").read_text(encoding="utf-8")
    assert ".process-grade-legend-swatch { fill: var(--accent); }" in css
    assert ".process-grade-legend-swatch.metric-entry_grade_rolling_N { fill: var(--series-entry); }" in css
    assert ".process-grade-legend-swatch.metric-management_grade_rolling_N { fill: var(--series-management); }" in css
    assert ".process-grade-legend-swatch.metric-exit_grade_rolling_N { fill: var(--series-exit); }" in css
```
- **Pre-fix:** tokens absent from both blocks + the two-class stroke rules + the swatch fill rules absent → **FAILS**.
- **Post-fix:** tokens declared once inside `:root` AND once inside `html.dark,\nbody.dark` + all rules present → **PASSES**.
- (The `_block` slicer assumes each token sits on its own `--token: value;` line within the first-encountered selector block — true for `app.css`'s one-declaration-per-line style. If the dark selector's exact whitespace differs at executing-plans time, re-grep and adjust the `selector_line` literal.)

**(b) Minimal implementation:**
- Under `:root` (after `--accent-hover` ~line 36) add:
  ```css
  --series-process: var(--accent);        /* the process line aliases the accent (A-6) */
  --series-entry: #1f9d55;                /* legible on light bg */
  --series-management: #b8860b;
  --series-exit: #c0392b;
  ```
- Inside the **combined** dark block `html.dark,\nbody.dark { … }` (after its `--accent-hover` ~line 123 — NOT a new standalone `body.dark` rule; the FOUC-prevention `html.dark` path must also get the colors — Codex R1-m2) add the dark-legible variants:
  ```css
  --series-process: var(--accent);
  --series-entry: #4ecb8a;
  --series-management: #e0b341;
  --series-exit: #ff7a6b;
  ```
  (Exact hexes are the implementer's legibility call at the operator browser gate, L6; the binding constraint is: tokenized, distinct, defined in BOTH the `:root` and `html.dark,body.dark` blocks, with `--series-process` aliasing `var(--accent)`.)
- After `.process-grade-marker { fill: var(--accent); }` (~line 339) add the **two-class** line-stroke rules (specificity 0,2,0 beats the single-class base 0,1,0 regardless of source order — Codex R1-M1):
  ```css
  .process-grade-rolling-line.metric-entry_grade_rolling_N { stroke: var(--series-entry); }
  .process-grade-rolling-line.metric-management_grade_rolling_N { stroke: var(--series-management); }
  .process-grade-rolling-line.metric-exit_grade_rolling_N { stroke: var(--series-exit); }
  ```
  (No rule for `process_grade_rolling_N` — it keeps the base `var(--accent)` = `--series-process`. The rate + cost panels' single lines also keep the base `var(--accent)`.)
- Add the **legend-swatch fill** rules (Codex R1-M3 — SVG presentation attributes cannot take `var()`, so the swatch `<rect>` must resolve its fill via a CSS rule keyed by the same `metric-<name>` class; mirror the two-class specificity pattern on `fill`):
  ```css
  .process-grade-legend-swatch { fill: var(--accent); }                                  /* process swatch */
  .process-grade-legend-swatch.metric-entry_grade_rolling_N { fill: var(--series-entry); }
  .process-grade-legend-swatch.metric-management_grade_rolling_N { fill: var(--series-management); }
  .process-grade-legend-swatch.metric-exit_grade_rolling_N { fill: var(--series-exit); }
  ```

**(c) Commit stem:** `feat(web): add theme-aware --series-* tokens + per-series chart stroke CSS`

**(d) Locks / gotchas:** L4 (A-6 base rules preserved — additive). OQ-2 (distinct theme-aware colors, two-class specificity). The `:root`+`body.dark` token-pairing convention (every theme color defined in both). ASCII (hex literals are ASCII).

---

### Task B2 — VM per-panel grouping + 0-anchored cost bounds + heights + axis labels

**Files:** `swing/web/view_models/metrics/process_grade_trend.py`; `tests/web/test_view_models/test_process_grade_trend_vm.py`.

**Design (additive — `rolling_series` stays all 7 for the table):**
1. **Per-panel height constants:** `GRADES_SVG_HEIGHT = 360`, `RATE_SVG_HEIGHT = 160`, `COST_SVG_HEIGHT = 160` (module constants, mirroring `SVG_HEIGHT`). New VM fields `grades_svg_height`/`rate_svg_height`/`cost_svg_height` defaulting to them. `SVG_HEIGHT`/`svg_height` stay (the grades panel reuses 360; back-compat).
2. **Cost-panel 0-anchored bounds helper** (NEW; does NOT mutate `_y_axis_bounds_for_metric`):
   ```
   _cost_panel_bounds(line_points) -> (float, float):
     finite = [v for p in line_points if (v:=p.value) is not None and math.isfinite(v)]
     m = max(finite) if finite else 0.0
     if m <= 0.0:        # no finite values OR every cost == 0.0 (perfect-process operator)
         return (0.0, 1.0)   # NOT (0.0, 0.0): _polyline_y centers when y_max==y_min → a zero
                             #   line would float mid-panel with degenerate labels.
     return (0.0, m)     # 0-anchored; margins provide top headroom so the peak isn't clipped.
   ```
3. **`_build_rolling_display` gains `bounds_override: tuple[float,float] | None = None`** — when provided, segments use it instead of `_y_axis_bounds_for_metric`. (Grades + rate pass `None`; cost passes `_cost_panel_bounds(...)`.) `layout_height` is already a parameter.
4. **New VM grouping fields** (tuples of `RollingSeriesDisplay`, ADDITIVE):
   - `grade_series` = the 4 grade metrics, built at `layout_height=GRADES_SVG_HEIGHT` (bounds `[0,4]` via existing path).
   - `rate_series` = `(disqualifying_violation_rate_rolling_N,)`, built at `layout_height=RATE_SVG_HEIGHT` (bounds `[0,1]` via existing path).
   - `cost_series` = `(mistake_cost_R_rolling_N_per_trade,)`, built at `layout_height=COST_SVG_HEIGHT` with `bounds_override=_cost_panel_bounds(per_trade_line_points)`.
   - `mistake_cost_R_rolling_N_total` is placed in NONE of the panel groups (table-only).
5. **`cost_y_max: float`** VM field (the computed cost upper bound, `1.0` in the all-zero case) — drives the cost axis labels + is the discriminating assertion target.
6. **Axis-label fields** (NEW; pre-positioned `(svg_y, text)` so the template needs no per-panel math):
   - `rate_axis_labels: tuple[tuple[float,str],...]` = for `v in (0.0, 0.5, 1.0)`: `(_polyline_y(v, y_min=0, y_max=1, layout_height=RATE_SVG_HEIGHT, margins...), text)` with text literal `"0.0"/"0.5"/"1.0"` (spec §3.3).
   - `cost_axis_labels: tuple[tuple[float,str],...]` = for `v in (0.0, cost_y_max/2, cost_y_max)`: `(_polyline_y(v, 0, cost_y_max, COST_SVG_HEIGHT, margins...), f"{v:.2f}")` — data-driven, ASCII `%.2f`. (`grade_axis_labels` keeps its `(value, label)` shape UNCHANGED — the grades panel preserves its existing inline-Y markup; the rate/cost panels use pre-positioned labels. This asymmetry is deliberate and preservation-driven.)
7. **Additive `__post_init__` group validation** (mirror-the-contract, #11): assert `{s.metric_name for s in self.grade_series} == _GRADE_METRICS`; `rate_series` names == `{"disqualifying_violation_rate_rolling_N"}`; `cost_series` names == `{"mistake_cost_R_rolling_N_per_trade"}`. Keep the existing all-7 `rolling_series` check.

**RED-sequencing for the cost-bounds helper** (Codex R2-M1 — avoid an ImportError false-fail): the cost tests below call `_cost_panel_bounds`, which does not exist pre-fix, so a bare red phase would fail by `ImportError`, not by the arithmetic. Make the RED genuine: **first add `_cost_panel_bounds` as a thin pass-through** returning the OLD behavior — `return _y_axis_bounds_for_metric("mistake_cost_R_rolling_N_per_trade", line_points)` — commit nothing yet; run the test and SEE it fail on the VALUE (`(0.3, 2.0)`≠`(0.0, 2.0)`; `(-0.5, 0.5)`≠`(0.0, 1.0)`). **Then** replace the body with the 0-anchored logic → GREEN. The test thus distinguishes the arithmetic, not the symbol's existence.

**(a) Failing tests first** (each distinguishes):
- `test_vm_groups_series_into_three_panels`: seed n=5; assert `{s.metric_name for s in vm.grade_series} == {4 grade names}`; `rate_series` names == `{rate}`; `cost_series` names == `{per_trade}`; and `mistake_cost_R_rolling_N_total` is in `vm.rolling_series` (table) but in none of the three groups. *(Pre-fix: the fields don't exist → AttributeError/fail; post-fix: pass.)*
- `test_cost_panel_bounds_zero_anchored_for_nonzero_costs` (**direct helper test**, Codex R1-m1 — NOT DB-seeded, so the max is exact): call `_cost_panel_bounds((RollingLinePoint(0,0.3), RollingLinePoint(1,2.0), RollingLinePoint(2,1.0)))` → assert `== (0.0, 2.0)` (0-anchored; min ignored). *(Pre-fix `_y_axis_bounds_for_metric` for the cost branch returns `(min, max) = (0.3, 2.0)` — NOT 0-anchored → the helper's `(0.0, 2.0)` distinguishes.)* Then assert `_polyline_y(2.0, y_min=0.0, y_max=2.0, layout_height=COST_SVG_HEIGHT, margin_top=24, margin_bottom=40) == 24.00` (the peak maps to the top margin, not clipped — the `margin_top=24` band is the headroom) and `_polyline_y(0.0, …) == 120.00` (baseline).
- `test_cost_panel_all_zero_uses_unit_fallback_not_degenerate` (**direct helper test**): `_cost_panel_bounds(())` AND `_cost_panel_bounds((RollingLinePoint(0,0.0), RollingLinePoint(1,0.0)))` both → assert `== (0.0, 1.0)` (NOT `(0.0,0.0)`). Then `_polyline_y(0.0, y_min=0.0, y_max=1.0, layout_height=160, margin_top=24, margin_bottom=40)` → assert `== 120.00` (the **baseline**), NOT the panel midpoint `72.00`. Also build the VM (n=5 perfect-process seed) and assert `vm.cost_y_max == 1.0` and `cost_axis_labels` texts are `("0.00","0.50","1.00")` (non-degenerate, NOT `"0.00"/"0.00"/"0.00"`).
  - **Arithmetic (the discriminator):** plot_height = 160−24−40 = 96; baseline Y = 24 + 96·(1−0) = **120.00**; top Y = 24 + 96·(1−1) = **24.00**; midpoint = 24 + 96·0.5 = **72.00**.
    - Pre-fix all-zero bounds (`_y_axis_bounds_for_metric` → `(raw_min-0.5, raw_max+0.5) = (-0.5, 0.5)`): value 0 → normalized = (0−(−0.5))/1.0 = 0.5 → Y = **72.00** (mid-panel) → assertion FAILS.
    - Post-fix bounds `[0,1]`: value 0 → normalized = 0 → Y = **120.00** (baseline) → assertion PASSES.
- `test_rate_axis_labels_present_and_positioned`: assert `rate_axis_labels` texts == `("0.0","0.5","1.0")` and Ys are within the 160-panel plot band.
- `test_vm_post_init_rejects_malformed_panel_groups`: constructing `ProcessGradeTrendVM` with a `cost_series` containing the wrong metric raises `ValueError`. *(Distinguishes the new guard.)*

**(b) Minimal implementation:** as the Design above. `build_process_grade_trend_vm` builds the three groups + `cost_y_max` + the axis-label tuples and passes them to the VM constructor (alongside the unchanged `rolling_series`).

**(c) Commit stem:** `feat(web): group process-grade-trend series into scale-separated panels (0-anchored cost)`

**(d) Locks / gotchas:** L1 (presentation-only — reads `compute_process_grade_trend` output, no metric change). OQ-1/OQ-3. `_polyline_y` center-on-equal-bounds → the `[0,1]` fallback (Codex R1-M2). #11 (mirror the panel-grouping contract in `__post_init__`). `_format_polyline_segments` reused unchanged (F-3 per series, per panel). `rolling_series` stays all 7 (the all-7 `__post_init__` check + the table). ASCII (`%.2f`).

---

### Task B3 — template: split the single `<svg>` into three panels + legend + under-floor captions

**Files:** `swing/web/templates/metrics/process_grade_trend.html.j2`; `tests/web/test_routes/test_metrics_process_grade_trend_route.py`.

**(a) Failing tests first** (NEW route assertions; the §3a preserved tests must ALSO stay green — run the full route module). **Assertions are PANEL-SCOPED** (Codex R2-M2: a global `in r.text` search would pass even if all 7 polylines stayed in the grades SVG with empty rate/cost panels added). A module-level helper slices each panel's SVG:
```
import re
def _panel(html, name):
    # the inner markup of the <svg data-panel="<name>"> ... </svg> block
    m = re.search(rf'<svg[^>]*data-panel="{name}"[^>]*>(.*?)</svg>', html, re.S)
    assert m is not None, f"panel {name} svg missing"
    return m.group(1)
def _legend(html):
    m = re.search(r'<g[^>]*data-marker="grades-legend"[^>]*>(.*?)</g>', html, re.S)
    assert m is not None, "grades-legend group missing"
    return m.group(1)

test_three_scale_separated_panels_present_when_drawable(seeded n=5):
    for name in ("grades", "rate", "cost"):
        assert f'data-panel="{name}"' in r.text

test_each_series_renders_in_its_own_panel(seeded n=5):   # the anti-"all in grades" guard
    grades, rate, cost = _panel(r.text,"grades"), _panel(r.text,"rate"), _panel(r.text,"cost")
    # the 4 grade lines live ONLY in the grades panel:
    for n in ("process_grade_rolling_N","entry_grade_rolling_N","management_grade_rolling_N","exit_grade_rolling_N"):
        assert f'data-series="{n}"' in grades
        assert f'data-series="{n}"' not in rate + cost   # Codex R3-m1: prove "ONLY in grades"
    # the rate line ONLY in rate; the per-trade cost line ONLY in cost:
    assert 'data-series="disqualifying_violation_rate_rolling_N"' in rate
    assert 'data-series="disqualifying_violation_rate_rolling_N"' not in grades + cost
    assert 'data-series="mistake_cost_R_rolling_N_per_trade"' in cost
    assert 'data-series="mistake_cost_R_rolling_N_per_trade"' not in grades + rate
    # _total charts in NO svg panel (table-only):
    for p in (grades, rate, cost):
        assert 'data-series="mistake_cost_R_rolling_N_total"' not in p

test_grades_legend_names_all_four_series(seeded n=5):
    leg = _legend(r.text)                       # scope to the legend group (Codex R2-m2)
    for label in ("process", "entry", "management", "exit"):
        assert f'>{label}<' in leg or f'>{label} ' in leg   # the visible <text> label, not prose/class
    assert "·" not in r.text                    # NO middle-dot (ASCII discipline #16/#32)
    for name in ("process_grade_rolling_N","entry_grade_rolling_N","management_grade_rolling_N","exit_grade_rolling_N"):
        assert f'process-grade-legend-swatch metric-{name}' in leg   # Codex R1-M3 swatch class

test_rate_panel_axis_and_line(seeded n=5):
    rate = _panel(r.text, "rate")
    assert 'data-marker="rate-axis"' in rate
    assert "0.0" in rate and "1.0" in rate

test_cost_panel_axis_line_and_caption(seeded n=5):
    cost = _panel(r.text, "cost")
    assert 'data-marker="cost-axis"' in cost
    assert 'data-marker="cost-axis-caption"' in cost
    assert "running total in table below" in cost

test_total_cost_in_table_row(seeded n=5):
    assert 'data-metric="mistake_cost_R_rolling_N_total"' in r.text   # the table row exists (table loops all 7)

test_under_floor_captions_render_for_partial_window(seeded n=3):
    rate, cost = _panel(r.text,"rate"), _panel(r.text,"cost")
    assert 'data-marker="rate-under-floor"' in rate
    assert 'data-marker="cost-under-floor"' in cost
    assert ">=5 effective samples" in rate     # literal ASCII '>=' (Codex R1-M1: static template text, NOT the &gt; entity)
    assert "<polyline" not in r.text           # under-floor: no line in ANY panel (route test 6 family)
```
- **Pre-fix:** the single `<svg>` has no `data-panel`/per-panel axes/legend/cost-caption → the new assertions FAIL.
- **Post-fix:** three panels emit them AND each series is scoped to its own panel → PASS; the §3a preserved assertions (esp. test 5's GRADES hooks + test 6's `"<polyline" not in` at n=2) still hold. The `_each_series_renders_in_its_own_panel` test is the anti-regression guard against "leave everything in grades + add empty panels."

**(b) Minimal implementation** — inside the `{% else %}` (trades exist) branch, REPLACE lines 24-66 (the single `<svg>`) with three `<svg>` blocks; the empty-state `{% if %}` guard, the heading, and the table stay:

- **GRADES panel** (`<h2>Grades</h2>` + `<svg viewBox="0 0 {{ vm.svg_width }} {{ vm.grades_svg_height }}" ... data-panel="grades">`):
  - **Preserve verbatim** the `grade-axis-labels` `<g data-marker="grade-axis-encoding">` block (the `A=4..F=0` inline-Y math, height `vm.grades_svg_height` == 360 == the old `vm.svg_height`) and the per-trade `<circle ... class="process-grade-marker">` loop (markers built at 360; unchanged).
  - Add a `<g class="legend" data-marker="grades-legend">` containing, per grade series, one `<rect class="process-grade-legend-swatch metric-{{ series.metric_name }}" ...>` swatch + one `<text>` ASCII label — `process` / `entry` / `management` / `exit` (slash separators in any visible joiner text; **never `·`**). The swatch fill resolves through the B1 `.process-grade-legend-swatch.metric-<name> { fill: var(--series-<name>) }` rules (Codex R1-M3 — SVG presentation attrs can't take `var()`, so the `metric-<name>` CLASS drives the color, never a raw `fill="var(...)"`). **Swatches are `<rect>`/`<line>`, NEVER `<polyline>`** (protects route test 6's `"<polyline" not in r.text` at n=2).
  - **Placement (Codex R1-m3 — avoid overlap):** render the legend in a reserved strip near the top of the grades panel — swatches/labels at `y ≈ 12` (inside the `margin_top=24` band, clear of the `A=4` line at `y≈24` and the grade-axis label column at `x=6`), `x` starting in the right half (e.g. `x ≥ 400`) so it does not collide with the axis labels. Exact coordinates are an implementer detail confirmed at the L6 operator gate; the binding rule is: outside the `[0,4]` plot band's left axis-label column and not on top of the top grade line.
  - The 4 grade polylines: `{% for series in vm.grade_series %}{% if series.is_drawable %}{% for seg in series.svg_polyline_segments %}<polyline points="{{ seg }}" fill="none" stroke-width="1.5" data-series="{{ series.metric_name }}" class="process-grade-rolling-line metric-{{ series.metric_name }}" />{% endfor %}{% endif %}{% endfor %}` — **identical hook shape to the current template** (preserves test 5's exact class + `data-series` for `process_grade_rolling_N`).
- **RATE panel** (`<h2>Disqualifying-violation rate</h2>` + `<svg viewBox="0 0 {{ vm.svg_width }} {{ vm.rate_svg_height }}" ... data-panel="rate">`):
  - `<g class="rate-axis-labels" data-marker="rate-axis">` rendering `{% for y, text in vm.rate_axis_labels %}<text x="6" y="{{ "%.2f"|format(y) }}" class="muted">{{ text }}</text>{% endfor %}`.
  - `{% for series in vm.rate_series %}{% if series.is_drawable %}{% for seg in series.svg_polyline_segments %}<polyline ... data-series="{{ series.metric_name }}" class="process-grade-rolling-line metric-{{ series.metric_name }}" />{% endfor %}{% else %}<text class="muted" data-marker="rate-under-floor" ...>rolling line draws once the window has >=5 effective samples</text>{% endif %}{% endfor %}`. **Write the caption with the LITERAL `>=` characters in static template text — NOT the `&gt;` entity and NOT the `≥` glyph** (Codex R1-M1): `>` is valid in element text content and Jinja emits static template text verbatim (it only escapes `{{ }}` expressions), so `r.text` contains the literal `>=5`. (Contrast: the line-12 prose uses the `&ge;` entity deliberately, and `n&lt;20` is escaped because it comes from a `{{ }}` value — neither applies to this static literal.) Caption positioned centered in the panel's plot band.
- **COST panel** (`<h2>Mistake cost (R per trade)</h2>` + `<svg viewBox="0 0 {{ vm.svg_width }} {{ vm.cost_svg_height }}" ... data-panel="cost">`):
  - `<g class="cost-axis-labels" data-marker="cost-axis">` rendering `vm.cost_axis_labels` (`%.2f` texts).
  - `{% for series in vm.cost_series %}{% if series.is_drawable %}{% for seg in series.svg_polyline_segments %}<polyline points="{{ seg }}" ... data-series="{{ series.metric_name }}" class="process-grade-rolling-line metric-{{ series.metric_name }}" />{% endfor %}{% else %}<text class="muted" data-marker="cost-under-floor" ...>rolling line draws once the window has >=5 effective samples</text>{% endif %}{% endfor %}`. Same LITERAL `>=` rule as the rate caption (Codex R1-M1).
  - `<text class="muted" data-marker="cost-axis-caption">running total in table below</text>`.
- The `<h2>Per-metric rolling window (most recent)</h2>` + table (`{% for series in vm.rolling_series %}` over all 7) stay UNCHANGED (so `_total` keeps its `data-metric=` row + the decoupled badges).

**(c) Commit stem:** `feat(web): render process-grade-trend as three scale-separated SVG panels`

**(d) Locks / gotchas:** L2 (three hand-rolled `<svg>`; no matplotlib/JS). §1.2 (GRADES hooks verbatim; `"<polyline"` absent at under-floor — captions/swatches are text/rect/line). L4 (markers + table + decoupled badges untouched; the empty-state guard still wraps all panels). ASCII #16/#32 (legend slash, `>=`, `%.2f` — NO `·`/`≥` glyphs; the route tests assert the ASCII forms + `"·" not in r.text`). The matplotlib-mathtext gotcha is N/A (inline SVG). HTMX gotchas N/A (pure server-rendered GET — the §A.9/§I.6 LOCK).

---

### Task B4 — structural sweep + zero-regression green-bar verification

**Files:** the four existing test modules (residual assertions only); no production code.

**(a) Residual structural assertions** (spec §5.1 items not yet covered by B1-B3):
- `test_empty_state_still_wraps_all_panels_when_no_trades`: with zero trades, `data-empty-state="process-grade-trend"` present AND none of `data-panel="grades|rate|cost"` present (the empty-state guard short-circuits all three panels). *(Pre-fix: trivially true with one svg; post-fix: confirms the guard still wraps the 3-panel block.)*
- `test_cost_axis_all_zero_renders_nondegenerate_labels_route`: seed n=5 perfect-process trades whose `_per_trade` cost is all `0.0`; **scope to the cost panel** `cost = _panel(r.text, "cost")` (Codex R2-m1 — avoid false-green from table/other-axis text) and assert `cost` contains `0.00`, `0.50`, AND `1.00` (the `[0,1]` fallback), NOT three identical `0.00`. *(Route-level companion to the B2 VM test — exercises the production derivation path, not stubs; per the "byte-parity insufficient" discipline.)*

**(b) Green-bar verification** (the binding evidence step, `superpowers:verification-before-completion`):
```
python -m pytest tests/web/test_routes/test_metrics_process_grade_trend_route.py \
                 tests/web/test_view_models/test_process_grade_trend_vm.py \
                 tests/web/view_models/metrics/test_process_grade_trend_segments.py \
                 tests/web/test_app_css_process_grade.py \
                 tests/web/test_routes/test_trades_route.py -q
ruff check swing/
```
Confirm: all §3a preserved tests GREEN; all §3b new tests GREEN; ruff clean. Then a fast-suite spot check (`python -m pytest -m "not slow" -q -k "process_grade or reviews_pending"`) and finally the full fast suite before the operator gate.

**(c) Commit stem:** `test(web): structural sweep for process-grade-trend small-multiples + nav-date`

**(d) Locks / gotchas:** the "byte-parity insufficient — exercise the production derivation path" discipline (the cost-axis route test hits the real VM→template path, not stubs). `feedback_no_false_green_claim` (read the actual pytest result before claiming green). L6 hand-off.

---

## §6 Slice / task summary

| Slice | Task | Production file | New/changed tests | Commit stem |
|---|---|---|---|---|
| A | A1 nav-date | `view_models/trades.py` | 1 route/VM render test | `fix(web): stamp session_date on reviews-pending VM (last_completed_session)` |
| B | B1 CSS tokens + per-series | `static/app.css` | 2 CSS tests | `feat(web): add theme-aware --series-* tokens + per-series chart stroke CSS` |
| B | B2 VM panels + cost bounds | `view_models/metrics/process_grade_trend.py` | 5 VM tests | `feat(web): group process-grade-trend series into scale-separated panels (0-anchored cost)` |
| B | B3 template 3-panel | `templates/metrics/process_grade_trend.html.j2` | 6 route tests (+ §3a preserved) | `feat(web): render process-grade-trend as three scale-separated SVG panels` |
| B | B4 sweep + verify | (tests only) | 2 residual tests + green-bar | `test(web): structural sweep for process-grade-trend small-multiples + nav-date` |

**5 tasks** (1 + 4). **Slice sequencing: A before B.** Within B: B1 → B2 → B3 → B4. ~16 new test functions; zero existing test assertions removed or weakened.

**Per-task TDD loop (every task, in order):**
1. **RED** — write the failing test(s) in part (a); run the named module; **see them fail** for the stated pre-fix reason (verify the failure message matches the arithmetic — not an import error masquerading as the assertion).
2. **GREEN** — apply the minimal implementation in part (b); re-run; **see the new test(s) pass** AND the §3a preserved tests in the same module still pass.
3. **COMMIT** — `git add` the production + test files; commit with the part-(c) stem; verify `git log -1 --format='%(trailers)'` is `[]`.

**Definition of done (whole arc, before the operator gate):**
- All §3a preserved tests GREEN, unmodified; all §3b new tests GREEN.
- `python -m pytest -m "not slow" -q` GREEN on the merged HEAD (read the actual result — `feedback_no_false_green_claim`); `ruff check swing/` clean.
- `EXPECTED_SCHEMA_VERSION == 24`; `git diff --stat` shows ZERO `swing/data`, `swing/trades`, or `migrations/` changes.
- `grep` confirms no `·`/`≥` glyph in the changed template/CSS (ASCII #16/#32).
- Zero `Co-Authored-By` across all commits.
- The §7 operator browser-witness gate is the final BINDING merge gate.

**Dependency note:** B3 (template) consumes the new VM fields from B2 (`grade_series`/`rate_series`/`cost_series`, `rate_axis_labels`/`cost_axis_labels`, panel heights) and the CSS tokens from B1 — so B1 → B2 → B3 is a hard order. A1 is fully independent and ships first.

**Commit discipline (every commit):** conventional; **NO `Co-Authored-By`**; **NO `--no-verify`**; the final `-m` paragraph is **plain prose** (never starts `Word:` — the trailer-parse hazard); verify `git log -1 --format='%(trailers)'` is `[]` before any push.

---

## §7 The operator browser gate (L6 — BINDING; merge blocked until confirmed)

TestClient asserts structure only. The operator drives a real browser (`python -m swing.cli web` against the live DB) and confirms ALL of:
1. **Legibility, light + dark:** each panel reads against its own labeled scale; no plunge-lines; the 4 grade colors are distinguishable and the legend is correct; dark mode shows every line (the `--series-*` + `--accent` tokens resolve in `body.dark`).
2. **The empty/under-floor DEFAULT state** (≤4 reviewed trades — the COMMON real-world state): axes + process-grade markers + the under-floor captions render — NOT a blank box (memory `feedback_seeded_gate_masks_default_state`; witness the UNSEEDED default, not just a seeded render).
3. **`/reviews/pending`** shows a non-empty topbar date (the `last_completed_session` ISO date), matching the other pages — no longer blank.

(Orchestrator runs DB-side probes in parallel: pytest + ruff green on the merged HEAD; `EXPECTED_SCHEMA_VERSION == 24` unchanged; no `swing/data`/`swing/trades`/migration diff; ASCII grep on the rendered SVG strings.)

---

## §8 Schema verdict

**NONE.** Schema v24 holds; `EXPECTED_SCHEMA_VERSION` stays 24. No migration; no `swing/data` or `swing/trades` write. Both items are pure presentation: a VM/template/CSS refactor (chart) + a VM one-liner reading an existing session helper (nav-date). Metric computations consumed read-only (L1). No L2 lock re-anchor (no new Schwab endpoints involved — orthogonal arc).

---

## §9 Risk register (for executing-plans + the Codex review)

1. **§1.2 hook preservation** — the GRADES panel polyline loop + class + `data-series` + axis labels + circles must be byte-identical in shape to the current template; the under-floor/legend additions must emit ZERO `<polyline>` (test 6 at n=2). *Mitigation: B3 reuses the exact existing polyline fragment for grades; captions are `<text>`, swatches `<rect>`/`<line>`; B4 runs the full route module.*
2. **`rolling_series` must stay all 7** — the panel groups are ADDITIVE; the all-7 `__post_init__` check + the table both depend on it. *Mitigation: B2 keeps `rolling_series` build untouched; groups are derived in addition.*
3. **CSS two-class specificity (R1-M1)** — a single `.metric-*` class ties the base rule; only the two-class selector wins by specificity regardless of order. *Mitigation: B1 asserts the literal two-class strings + the base rule.*
4. **Cost `[0,1]` fallback (R1-M2)** — `_polyline_y` centers on `y_max==y_min`; `[0,0]` would float a zero line mid-panel with degenerate labels. *Mitigation: `_cost_panel_bounds` returns `(0.0,1.0)` when `max<=0`; B2's baseline-Y arithmetic test (120.00 vs 72.00) discriminates.*
5. **Nav-date anchor** — must be `last_completed_session` (backward-looking), NOT `action_session_for_run`. *Mitigation: A1's test asserts the anchor directly; the metrics-page `action_session_for_run` line is correctly NOT touched.*
6. **ASCII (#16/#32)** — legend slash (not `·`), `>=` (not `≥`), `%.2f`. *Mitigation: route tests assert the ASCII forms + `"·" not in r.text`.*
7. **Day-boundary flake in A1** (Codex R1-M2) — two independent `datetime.now()` calls can straddle a session boundary. *Mitigation: A1 monkeypatches `trades.datetime` to a frozen instant; expected computed from the same instant — deterministic.*
8. **Under-floor caption raw-HTML mismatch** (Codex R1-M1) — `TestClient` sees raw HTML; the `&gt;` entity would NOT match a `">="` assertion. *Mitigation: B3 writes the caption with LITERAL `>=` static template text (emitted verbatim); the assertion matches.*
9. **Legend swatch default/black fill** (Codex R1-M3) — SVG presentation attrs can't take `var()`. *Mitigation: B1 adds `.process-grade-legend-swatch` + two-class fill rules; B3 swatches carry the `metric-<name>` class; B1+B3 tests assert both.*
10. **Weak/duplicate-tolerant CSS token test** (Codex R1-M4 / R1-m2) — a global count passes on same-block duplicates and misses the dark selector. *Mitigation: B1 test slices the `:root` and the combined `html.dark, body.dark` blocks and asserts each token once per block.*
11. **DB-seeded cost max imprecision** (Codex R1-m1) — rolling-mean max may not equal the intended value. *Mitigation: B2 cost-bounds tests call `_cost_panel_bounds`/`_polyline_y` directly with explicit `RollingLinePoint` values.*

---

## §10 Cumulative-discipline compliance checklist

- **Web/HTMX/forms gotchas:** shared-`base.html.j2` 5-VM rule **NOT triggered** (no new `vm.foo`; A1 sets an existing field; B2's new fields live only on `ProcessGradeTrendVM`, a single route's VM). Pure server-rendered GET — no HTMX OOB-swap / HX-Redirect / embedded forms (§A.9/§I.6 LOCK). Matplotlib-mathtext gotcha N/A (inline SVG).
- **Session-anchor read/write gotcha:** A1 uses the backward-looking `last_completed_session` for backward-looking content.
- **ASCII #16/#32:** all proposed rendered SVG strings ASCII (legend, `>=`, `%.2f`).
- **Regression-test-arithmetic (memory):** A1 distinguishes `""` vs ISO date; B2 distinguishes pre-fix `(raw_min,raw_max)`/`(-0.5,0.5)` (Y=72.00) vs post-fix `[0,1]` (Y=120.00).
- **A-6 / L4:** the existing `.process-grade-rolling-line`/`.process-grade-marker` + `var(--accent)` rules preserved (additive tokens); suppression floor, markers, decoupled badges, table all survive.
- **Commits:** conventional; NO `Co-Authored-By`; NO `--no-verify`; final `-m` paragraph plain prose; `%(trailers)` `[]` before push.
- **No false-green:** B4 reads the actual pytest result on the merged HEAD before any green claim.

---

*End of plan. Slice A = the `/reviews/pending` `session_date` one-liner (`last_completed_session`). Slice B = small-multiples: GRADES `[0,4]` (4 colored lines + legend + markers) / RATE `[0,1]` / COST `[0,max]` 0-anchored `_per_trade`-only with the `[0,1]` all-zero fallback; distinct `--series-*` theme colors via two-class CSS specificity; under-floor captions for the witnessable default state. The GRADES panel preserves its exact route-test hooks; `rolling_series` stays all 7; the table + decoupled badges + suppression floor are untouched. NO schema (v24 holds), NO migration, NO lock re-anchor. The binding gate is an operator browser-witness (light/dark + the empty/under-floor default + the fixed nav-date).*
