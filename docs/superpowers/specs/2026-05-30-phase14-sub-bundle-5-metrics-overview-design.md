# Phase 14 Sub-bundle 5 — Metrics Overview (P14.N5) — Design Spec

**Status:** Brainstorm draft (pre-Codex). **Date:** 2026-05-30.
**Sub-bundle:** Phase 14 SB5 — the **FINAL** Phase 14 sub-bundle. Phase 14 close-out (Sec 9.1 Q6) follows.
**Branch:** `phase14-sub-bundle-5-metrics-overview-brainstorming` (from main `f55065e`).
**Brief:** `docs/phase14-sub-bundle-5-metrics-overview-brainstorming-dispatch-brief.md`.
**Scope class:** read-mostly UX enhancement; reuses existing metric computations + SB3/SB4 chart precedent; **NO schema change** (recommended); single Codex chain to convergence.

---

## §1 Architecture overview

### §1.1 What this is

P14.N5 turns the existing **text-only** `/metrics` index into a **graphics-driven overview dashboard**.
The operator framing (`docs/phase3e-todo.md`, 2026-05-27 PM #2): *"Metrics page needs to show some
kind of overall dashboard so the pages don't need to be navigated to except as a drill down. Ideally
some kind of graphics would help display the information better rather than the current pure text."*

Each of the **9 metric surfaces** gets a card carrying:
1. its label (existing),
2. a clickthrough to the existing drill-down route (existing — preserved),
3. a **headline stat** (the single at-a-glance number — NEW), and
4. a **sparkline** *only where genuine multi-run/multi-trade trend data exists* (NEW; honesty-gated).

### §1.2 The load-bearing finding — `/metrics` ALREADY EXISTS; only 3 of 9 surfaces carry series data

**Brief-vs-production correction #1 (CONFIRMED):** `/metrics` is **not greenfield**. It already renders a
text navigator: `GET /metrics` → `metrics_index` (`swing/web/routes/metrics.py:45`) →
`build_metrics_index_vm(conn)` (`swing/web/view_models/metrics/index.py:97`) → `MetricsIndexVM`
(`:90`, a `BaseLayoutVM`) → `metrics/index.html.j2` (a `<ul class="metrics-tiles">` over the
hand-maintained `_SURFACES` tuple of `MetricsIndexSurface{path,label,description}` at `index.py:36`).
**P14.N5 is an ENHANCEMENT of this index**, not a new route.

**Brief-vs-production correction #2 (CONFIRMED — the central data-shape finding):** ONLY **3 of the 9**
surfaces expose a renderable time/sequence SERIES:

| # | Surface | compute_* | Series field | Series element | Suppression threshold |
|---|---------|-----------|--------------|----------------|------------------------|
| 1 | capital_friction | `compute_capital_friction` (`capital.py:509`) | `trend_runs: tuple[CapitalFrictionTrendPoint,…]` | per `pipeline_runs` row (30-session window) | `TREND_MIN_RUNS = 5` (`capital.py:61`) |
| 2 | identification_funnel | `compute_identification_funnel` (`funnel.py:206`) | `trend_runs: tuple[IdentificationFunnelPoint,…]` | per `pipeline_runs` row (30-session window) | `TREND_MIN_RUNS = 10` (`funnel.py:42`) |
| 3 | process_grade_trend | `compute_process_grade_trend` (`process_grade_trend.py:524`) | `rolling_series: dict[str, RollingMetricSeries]` | 7 metric classes × N-trade rolling window | line-band ≥ effective-samples gate (`is_drawable`) |

The OTHER **6** surfaces — `trade_process`, `hypothesis_progress`, `tier_comparison`, `maturity_stage`,
`deviation_outcome`, `pattern_outcomes` — are **point estimates / per-row tables with NO multi-run
trend**. Per the **honesty floor (L4)** they get a **headline stat only** + an honest empty/suppressed
state. **They do NOT get a fabricated sparkline.**

**Brief-vs-production correction #3 (NEW — material; the brief understated it):** the n<5 suppression is
**NOT uniform**. capital_friction suppresses below **5** runs; identification_funnel below **10** runs;
process_grade_trend uses a **window/effective-sample line-band** gate (`is_drawable`, ≥ ~5 effective
samples). The overview sparkline for each surface MUST reuse that surface's **own existing threshold
constant** (do not impose a single `n<5`). Re-grep these constants at writing-plans (#2).

**Brief-vs-production correction #4 (NEW — minor):** the brief's read-list cited the process-grade
compute as living near "`swing/metrics/process_grade.py`". The actual module is
**`swing/metrics/process_grade_trend.py`** (the VM is `swing/web/view_models/metrics/process_grade_trend.py`).
Line `:524` for `compute_process_grade_trend` is correct.

**Brief-vs-production correction #5 (NEW — load-bearing for the module touch list):** the index builder
signature is `build_metrics_index_vm(conn)` — **conn-only**. But the per-surface builders the overview
must reuse take **`(cfg, conn)`** (e.g. `build_capital_friction_vm(cfg, conn)`,
`build_trade_process_vm(cfg, conn)`) or `(conn)` (e.g. `build_hypothesis_progress_vm(conn)`). To
populate per-card headline+series the overview builder MUST widen to **`build_metrics_index_vm(cfg, conn)`**
and the route call at `metrics.py:52` updates from `build_metrics_index_vm(conn)` →
`build_metrics_index_vm(cfg, conn)`. This is a real, in-scope edit (route + builder + every existing
unit test that constructs the index VM).

### §1.3 The sparkline-tech precedent (the OQ-1 anchor)

The `process_grade_trend` surface **already** renders an **inline hand-built `<polyline>` SVG, NOT
matplotlib** — under a prior "NO matplotlib" lock for that surface. The full apparatus exists and is
directly reusable:
- VM helpers `_polyline_x` / `_polyline_y` / `_format_polyline_points` (`view_models/metrics/process_grade_trend.py:225–302`)
  produce a `"x1,y1 x2,y2 …"` points string, contiguous over defined segments, `""` when not drawable.
- `RollingSeriesDisplay.svg_polyline_points` (`:93`) + `is_drawable` (`:95`) carry it to the template.
- The template emits `<polyline points="…" fill="none" …/>` inside an `<svg viewBox="0 0 W H">`
  (`templates/metrics/process_grade_trend.html.j2:54–62`) — **no JS, no `chart_renders`, no render lock.**

That precedent is a **full chart (800×360)**, not a tiny sparkline; the *algorithm* generalizes to a
~`100×30` sparkline, but the overview needs its own small helper (it cannot import the grade-axis /
per-trade-marker machinery wholesale). This is the heart of **OQ-1** (§7).

---

## §2 Pre-locked decisions (Sec 9.1 + L1–L9) — verbatim compliance

### §2.1 Sec 9.1 LOCKs
- **Q1** sequencing: charts → review+journal (SHIPPED) → **metrics overview (THIS, LAST)**. **Q2** SERIAL.
- **Q5** graphics = **matplotlib SVG; NO JS charting library.** Binding constraint = **no-JS, static
  server-rendered graphics.** Both OQ-1 candidates (matplotlib-SVG and inline-`<polyline>`) satisfy
  no-JS; the existing precedent for *this exact problem* is inline-`<polyline>`. The spec **does not
  unilaterally pick matplotlib** — see §7 / OQ-1, HELD for operator.
- **Q6** operator browser-witnessed verification at merge — the **rendered overview is the BINDING
  visual gate**.
- **Q7** Codex chain count = orchestrator discretion → **SINGLE chain** for this brainstorming.

### §2.2 Sub-bundle 5 LOCKs
- **L1 Scope** = P14.N5 metrics overview ONLY. NO change to the 9 per-surface routes' DATA logic; NO new
  metric computations/algorithms; NO SB1–SB4 surfaces; NO Phase 15+.
- **L2 Read-mostly** = reuse the post-wiring-fix `build_*_vm`/`compute_*` outputs; ZERO new computation;
  ZERO `chart_renders`/domain writes. The overview is a pure read/aggregate surface.
- **L3 NO schema (recommended)** = sparklines render-direct (inline-SVG or matplotlib-SVG-direct) → no
  `chart_renders` rows. A new `chart_renders` surface enum (only if cached matplotlib sparklines, NOT
  recommended) is the sole v24 trigger (STRICT `pre_version == 23`; gotchas #11 paired + #9). **Verdict
  recommended: NO schema change** (§11).
- **L4 Honesty floor** = NO fabricated sparkline. ONLY the 3 trend-bearing surfaces get sparklines; the
  other 6 get a headline stat + honest suppressed/empty state. Each sparkline reflects REAL series the
  drill-down also shows, and respects that surface's OWN suppression threshold (5 / 10 / line-band — §1.2).
- **L5 Visual-gate discipline** = IF matplotlib: byte/string tests INSUFFICIENT → operator-witnessed
  rendered gate; ASCII annotation text only (no mathtext `$ ^ _ \`); reuse `_svg_bytes_from_fig` /
  `_render_candles_fig` / `_RENDER_LOCK` — no re-implementation. IF inline-SVG: the rendered card is
  still the binding visual gate; reuse the polyline-points algorithm shape.
- **L6 Render-lock contention** = IF matplotlib, every overview load renders up to 3 figures serialized
  through `_RENDER_LOCK` → latency / render-storm risk; mitigate (cache / lazy-load / prefer inline).
  Inline-`<polyline>` has ZERO render-lock contention (assessment in §7).
- **L7 BaseLayoutVM contract** = the enhanced `MetricsIndexVM` stays a `BaseLayoutVM` (session_date +
  banner/discrepancy/auto-correction fields). Any NEW field added to a *base-layout* VM needs a safe
  default on EVERY base VM — but the overview's per-card data lives on `MetricsIndexVM` (a leaf VM), NOT
  on `BaseLayoutVM`, so **no base-contract fan-out is required** (see §4.3).
- **L8 HTMX disciplines** = apply ONLY if the overview lazy-loads/interactive cards (the trinity:
  `hx-headers HX-Request`; `204`+`HX-Redirect` not `303`; target-route-exists). The existing metrics
  pages are pure server-rendered HTML with no HTMX. **Recommended: keep SB5 pure server-render (no
  HTMX)** → L8 does not bind (see OQ-6, §7).
- **L9 Close-out readiness** = SB5 is LAST. Spec/return-report note Phase 14 close-out readiness +
  banked Phase 14 follow-ups to sequence (§15).

---

## §3 Module touch list

All paths relative to repo root. "(R)" = reuse/read-only; "(M)" = modify; "(N)" = new.

**Production:**
- `swing/web/view_models/metrics/index.py` **(M)** — extend `MetricsIndexSurface` with the overview
  fields; widen `build_metrics_index_vm(conn)` → `(cfg, conn)`; populate per-card headline+series by
  calling the existing per-surface builders/compute_* (read-only).
- `swing/web/routes/metrics.py` **(M)** — `metrics_index` route: `build_metrics_index_vm(conn)` →
  `build_metrics_index_vm(cfg, conn)` (the `cfg` dependency is already injected). NO other route changes.
- `swing/web/templates/metrics/index.html.j2` **(M)** — replace the link-only `<ul>` with the card grid
  (headline stat + sparkline-or-suppressed + drill-down link).
- `swing/web/view_models/metrics/sparkline.py` **(N)** — the small sparkline helper
  (`build_sparkline_points(values, *, width, height) -> str | None`, suppression-aware). **IF OQ-1 =
  inline-polyline:** a ~40-line pure helper generalizing the `process_grade_trend` polyline algorithm.
  **IF OQ-1 = matplotlib:** instead a thin wrapper over `swing/web/charts.py:_svg_bytes_from_fig`
  serialized under `_RENDER_LOCK` (no new render primitive — reuse only).
- `swing/web/static/app.css` (or the existing metrics stylesheet) **(M)** — card-grid + sparkline
  styling (the surface stroke colors; reuse the Okabe-Ito palette tokens if matplotlib parity wanted).

**Reuse (read-only — DO NOT modify the data logic):**
- `swing/metrics/capital.py` **(R)** — `compute_capital_friction` / `CapitalFrictionResult.trend_runs` /
  `TREND_MIN_RUNS=5`.
- `swing/metrics/funnel.py` **(R)** — `compute_identification_funnel` / `IdentificationFunnelResult.trend_runs` /
  `TREND_MIN_RUNS=10`.
- `swing/metrics/process_grade_trend.py` **(R)** — `compute_process_grade_trend` / `rolling_series`.
- `swing/web/view_models/metrics/{capital,funnel,process_grade_trend,process_metrics,cohort,tier,
  maturity,deviation,pattern_outcomes}.py` **(R)** — the existing `build_*_vm` outputs supply the
  headline stats.
- `swing/web/view_models/metrics/process_grade_trend.py` **(R)** — the polyline-points algorithm
  reference (`_format_polyline_points`, `_polyline_x/y`) for the inline-SVG option.
- `swing/web/charts.py` **(R, only if matplotlib)** — `_svg_bytes_from_fig:111`, `_RENDER_LOCK:83`,
  `@_serialized_render:86`, `_MA_COLORS`. `swing/web/trade_charts.py` **(R)** —
  `render_trade_window_thumbnail_svg:87` (tiny-figure precedent).

**Tests (N):** `tests/web/view_models/metrics/test_sparkline.py`,
`tests/web/view_models/metrics/test_index_overview.py`, `tests/web/routes/test_metrics_index_overview.py`.

---

## §4 Overview dashboard design

### §4.1 Route shape — enhance `/metrics` in place (recommended; OQ-3)

Keep `GET /metrics` as the dashboard landing (it already is the landing + the nav target). The card
grid replaces the `<ul>` list; drill-down links are preserved on each card. **No new `/metrics/overview`
route** (rejected: forks the landing, duplicates the registry, two surfaces to keep in sync). HELD as
OQ-3 but strongly recommended.

### §4.2 The card grid

One card per `_SURFACES` entry, in the existing registry order (stable, hand-maintained). Each card:

```
┌──────────────────────────────────────────────┐
│ <a href="/metrics/capital-friction">          │  ← whole card is the drill-down link
│   Capital-friction                            │  ← label (existing)
│   42.0%  utilization                          │  ← headline stat + unit caption (NEW)
│   ╱╲__╱‾╲_  (inline sparkline, 100×30)        │  ← sparkline IFF trend-bearing & ≥threshold
│ </a>                                          │
└──────────────────────────────────────────────┘
```

Trend-bearing surface, below threshold → the sparkline slot renders an honest suppressed caption
(e.g. *"trend needs ≥5 runs (have 3)"*), NEVER a flat/fabricated line. Point-estimate surface → no
sparkline slot at all (headline stat only). Suppressed headline (n below the surface's own floor) →
the existing suppression placeholder text (reuse `SuppressionRowVM`-style italic placeholder; never a
bare `—`/`N/A`).

### §4.3 The VM enhancement

Extend the per-card dataclass (do NOT touch `BaseLayoutVM` — L7):

```python
@dataclass(frozen=True)
class MetricsIndexSurface:
    path: str
    label: str
    description: str
    headline_stat_text: str | None = None      # formatted, display-ready (e.g. "42.0%"); None when unavailable
    headline_caption: str | None = None        # unit/label caption (e.g. "utilization")
    headline_suppressed_text: str | None = None # honest placeholder when the stat is suppressed
    sparkline_points: str | None = None         # inline-SVG points string; None ⇒ no sparkline slot
    sparkline_suppressed_text: str | None = None# trend-bearing but below threshold
    sparkline_kind: str = "none"                # "none" | "inline_svg" | "matplotlib_svg" (OQ-1)
```

`MetricsIndexVM` keeps `surfaces: tuple[MetricsIndexSurface, …]` and its existing `BaseLayoutVM` fields
unchanged. `build_metrics_index_vm(cfg, conn)`:
1. opens nothing new (uses the passed `conn`),
2. for each surface, calls the existing per-surface `compute_*`/`build_*_vm` (read-only) to extract the
   headline value + (for the 3 trend surfaces) the series,
3. formats the headline display-ready (display-precision parity per the price-precision gotcha; ASCII
   only per #16/#32),
4. builds the sparkline points string via the §5 contract (suppression-aware),
5. composes the `_SURFACES` registry's static `{path,label,description}` with the computed fields.

**Performance note (per L2/#27):** the overview calls up to 9 `compute_*` paths on one request. These
are the same computations the per-surface routes already run individually; the overview runs them
together. Assess at writing-plans whether any single compute is heavy enough to warrant a per-card
HTMX lazy-load (OQ-6) — default recommendation is eager server-render (the operator's box already runs
each per-surface page in well under interactive latency). Emit nothing to the DB.

### §4.4 Error isolation (per bad-exemplar-isolation discipline)

Wrap each per-surface extraction in its own try/except: a single surface's compute failure degrades
THAT card to a suppressed/"unavailable" state (logged), it does NOT 500 the whole overview. The card
grid always renders 9 cards.

---

## §5 Sparkline contract (the 3 trend-bearing surfaces)

Each sparkline is a tiny inline `<svg viewBox="0 0 100 30">` containing one `<polyline>` (the inline
option) OR one `<img src="data:image/svg+xml;base64,…">` / inline `<svg>` from matplotlib (the
matplotlib option). The **series selection + suppression** below is identical regardless of OQ-1.

### §5.1 capital_friction
- **Series:** `current_capital_utilization_pct` across `trend_runs` (ordered by `run_date`). One value
  per `pipeline_runs` row in the 30-session window.
- **Suppression:** render the line only when `len(trend_runs) >= TREND_MIN_RUNS` (=5). Below → suppressed
  caption. Drop `None` points; if fewer than 2 defined points remain → suppress (a polyline needs ≥2).
- **Rationale:** utilization is the surface's primary operator-readable gauge; heat is the alternate
  (OQ-4). Single series only (a sparkline is one line).

### §5.2 identification_funnel
- **Series:** `aplus_identifications_per_run` across `trend_runs` (ordered by `run_date`).
- **Suppression:** render only when `len(trend_runs) >= TREND_MIN_RUNS` (=**10**, note the higher floor).
  Below → suppressed caption *"trend needs ≥10 runs (have N)"*.
- **Alternate (OQ-4):** `aplus_trades_taken_per_run`, or the take-rate (but take-rate is itself
  suppressed at 0 A+ — would compound suppression; prefer the raw count).

### §5.3 process_grade_trend
- **Series:** `rolling_series` is a **`dict[str, RollingMetricSeries]` of 7 metric classes** — pick ONE
  for the overview sparkline. Recommend the headline grade series (`process_grade` rolling grade score,
  matching the drill-down's primary line). The chosen key is an OQ-4 sub-decision.
- **Suppression:** reuse the surface's existing `is_drawable` / line-band gate (≥ effective-samples).
  Below → suppressed caption. Do NOT re-implement the gate — read it from the existing per-metric
  display logic.
- **Note:** the drill-down renders all 7 lines at 800×360; the overview shows ONLY the one headline line
  at 100×30. The overview line is a strict subset of what the drill-down shows (honesty preserved).

### §5.4 The sparkline helper (`build_sparkline_points`)

Pure function, suppression-aware:
```python
def build_sparkline_points(
    values: Sequence[float | None],
    *, width: int = 100, height: int = 30, min_points: int = 2,
) -> str | None:
    # X is positioned over the ORIGINAL sequence index (i / (len(values)-1) * width),
    #   NOT over the compacted list — so a None gap leaves a horizontal gap in spacing
    #   and does NOT compress time (Codex R1 MAJOR fix: dropping None compresses the
    #   axis and visually hides missing middle runs).
    # Y normalized over [min..max] of the DEFINED values, inverted (SVG y-down) into
    #   [pad, height-pad]; flat series (max==min) ⇒ mid-line.
    # None points: omit their (x,y) vertex; the single polyline therefore CONNECTS
    #   across a gap (same behavior as the process_grade_trend precedent, which the
    #   drill-down already accepts). If gaps are common for a surface, writing-plans may
    #   elect to emit multiple polylines split at gaps (V2 candidate).
    # If < min_points DEFINED values ⇒ return None (caller renders the suppressed caption).
    # Returns "x1,y1 x2,y2 …" (2-dp) or None.
```
This mirrors `_format_polyline_points`/`_polyline_x`/`_polyline_y` (the precedent likewise positions x
over the sequence index and skips undefined y) but is standalone, tiny, and free of the grade-axis/marker
machinery. The **threshold gating lives in the builder** (per §5.1–§5.3), not in this helper — this
helper only refuses to draw a degenerate (<2-point) line. **Gap semantics (single connected polyline)
are an accepted V1 simplification matching the existing drill-down; per-gap splitting is banked V2.**

---

## §6 Headline-stat contract (all 9) — OQ-4

Single at-a-glance figure per surface, pulled from an EXACT EXISTING result/VM field (no re-derivation,
no cross-row aggregate — L2). **Fixed-selector discipline (Codex R1 MAJOR fixes):** where a surface
returns a *collection* (cohort tabs, tier cohorts, deviation rows, pattern rows, the 7 rolling-series
metrics), the overview picks ONE row/cell by a **fixed, hard-coded selector** (a named cohort key /
pattern class / metric key) and reads its already-computed field — it MUST NOT compute a "worst"/"delta"
/"overall" across the collection (that would be new computation). All are OQ-4 (operator confirms the
selector + figure); the table below is the recommendation with the EXACT accessor.

| # | Surface | Headline stat (recommended) | EXACT source accessor | Caption | Suppressed when |
|---|---------|------------------------------|------------------------|---------|-----------------|
| 1 | trade_process | overall expectancy (R) | `next(t for t in vm.cohort_tabs if t.cohort_key == ALL_COHORTS_KEY).metrics.expectancy_R` (a metric obj; if `SuppressedMetric` → its placeholder) | "expectancy R (all)" | metric is `SuppressedMetric` |
| 2 | hypothesis_progress | active cohorts count | `len(vm.<cohort rows>)` (count of the registry cohorts the VM already lists) | "active cohorts" | 0 cohorts |
| 3 | tier_comparison | A+ cohort expectancy (point) | the A+ cohort's existing expectancy point on `TierComparisonResult.cohorts[<A+ key>]` (NOT a delta) | "A+ expectancy R" | A+ cohort n<5 (existing CI suppression) |
| 4 | capital_friction | current utilization % | `CapitalFrictionResult.current_capital_utilization_pct` (renders with LIVE/PROVISIONAL badge — PROVISIONAL is a VALID fallback, NOT suppression) | "utilization" | value is `None` / compute fails |
| 5 | maturity_stage | open positions count | `len(vm.<position rows>)` | "open positions" | 0 open |
| 6 | identification_funnel | latest-run A+ identifications | `trend_runs[-1].aplus_identifications_per_run` (a real field) | "A+ ident. (latest run)" | 0 runs |
| 7 | deviation_outcome | one fixed cohort's relative-pct | `DeviationOutcomeResult.rows[<fixed cohort key>].expectancy_relative_to_aplus_pct` (a fixed row, NOT "worst") | "Δ vs A+ (<cohort>)" | that row's n<5 placeholder |
| 8 | process_grade_trend | latest rolling grade (numeric) | the headline metric's `RollingSeriesDisplay.point_value_text` (a NUMERIC value, e.g. rolling grade score; a numeric→letter map would be presentation-only, flagged as such) | "rolling grade" | the metric's `is_suppressed` |
| 9 | pattern_outcomes | one fixed pattern class's trigger rate | `PatternOutcomesVM.pattern_outcome_rows[<fixed pattern class>]` trigger-rate cell (NOT an "overall" row — none exists) | "trigger rate (<class>)" | that row's n<5 (existing Wilson) |

**Discipline:** every headline reuses the surface's EXISTING suppression semantics (the per-surface VMs
already encode n<5 / Wilson / provisional-badge / `SuppressedMetric` placeholder behavior). The overview
never invents a number the drill-down wouldn't show, never computes a cross-row aggregate (L2), and never
renders a bare `—`/`N/A` (uses the honest placeholder text). **The fixed selectors for rows 3, 7, 9 (and
the metric key for row 8) are OQ-4 items the operator confirms at writing-plans** — pick a cohort/class
that is meaningful at a glance (e.g. the primary registry cohort, the headline pattern class).

---

## §7 Sparkline-tech decision (OQ-1) — matplotlib-SVG vs inline-`<polyline>`

**This is THE decision of SB5. The spec presents the tradeoff and HOLDS for operator triage. It does
NOT pre-pick matplotlib merely because Q5 says "matplotlib SVG" — Q5's binding intent is no-JS, and the
existing precedent for this exact problem (`process_grade_trend`) is inline-`<polyline>`.**

| Dimension | Inline-`<polyline>` SVG (recommended) | Matplotlib-SVG |
|-----------|----------------------------------------|----------------|
| No-JS (Q5) | ✅ static SVG in the HTML | ✅ static SVG bytes |
| Precedent | ✅ exact precedent (`process_grade_trend`) | partial (full charts, not sparklines) |
| Render-lock (L6) | ✅ none — pure string build | ❌ up to 3 figures/load serialized through `_RENDER_LOCK` |
| Per-load cost | trivial (string formatting) | matplotlib figure construct/teardown ×3 |
| mathtext risk (#) | none (no text in a sparkline) | low (sparklines carry no annotation text) but discipline still applies |
| Visual fidelity | adequate for a 100×30 trend glyph | richer (axes/fills) — overkill at 100×30 |
| Reuse (L5) | reuse the polyline-points algorithm shape | reuse `_svg_bytes_from_fig`/`_RENDER_LOCK` |
| New code | ~40-line pure helper | thin wrapper, but pulls the render-lock onto the index hot path |

**Recommendation: inline-`<polyline>`** — it matches the existing precedent, carries zero render-lock
contention on the index hot path (which renders up to 3 sparklines per load), and is the right weight
for a 100×30 glyph. Matplotlib's richness is wasted at sparkline size and imports a serialized
render-storm onto the most-visited metrics page. **HELD for operator at writing-plans dispatch.**

If the operator chooses matplotlib for cross-surface consistency: L6 mitigation is **OQ-6 (HTMX
lazy-load per card so the 3 serialized renders don't block first paint)** — caching in `chart_renders`
is NOT available (the table is ticker/run-keyed; §8). With only 3 sparklines per load the render-lock
cost is bounded but non-zero; inline-`<polyline>` avoids it entirely.

---

## §8 Render path / schema

- **Recommended:** render-direct / inline → NO `chart_renders` writes → **NO migration** (L3).
- The sparkline points string (inline option) is computed per-request and embedded in the HTML; nothing
  persists.
- The matplotlib option, if chosen render-direct (SVG bytes inlined per request), ALSO needs no schema.
- **Cached matplotlib via `chart_renders` is NOT a viable SB5 cache target (Codex R1 MAJOR fix).** The
  `chart_renders` table is structurally **ticker-and-run keyed**: `ChartRender.ticker` is REQUIRED
  (`models.py:1942`), and any surface other than `position_detail`/`theme2_annotated` is treated as
  *run-bound* and REQUIRES a non-NULL `pipeline_run_id` (`models.py:~1981`); the surface enum is the 5
  values at `models.py:96`. A metrics-overview sparkline has **no ticker and no pipeline_run binding** —
  it does not fit the cache-key shape. Caching it would require NOT just a new enum value but a new
  nullable-ticker/nullable-run cache-key class + the cross-column CHECK rework + new partial index +
  every `_row_to_*` mapper + dataclass `__post_init__` (gotcha #11) + the migration runner (gotcha #9).
  That is disproportionate to a 100×30 glyph. **Cached matplotlib is therefore REMOVED from the viable
  option set** (it was already not recommended); OQ-5 collapses to "render-direct" for BOTH OQ-1 options.
- If a v24 were ever taken for an unrelated reason: STRICT backup-gate `pre_version == 23` (NOT `<=`);
  gotcha #11 (schema-CHECK + Python-constant + dataclass-validator + every `_row_to_*` mapper in ONE
  task) + #9 (explicit BEGIN/COMMIT migration runner). **Not in SB5 scope.**

---

## §9 Sub-bundle decomposition recommendation

SB5 is small (read-mostly, one surface). A single executing-plans bundle, decomposed into ~4 tasks:

1. **T1 — sparkline helper** (`sparkline.py` + tests): pure `build_sparkline_points`, TDD; suppression
   (<2 points → None), normalization, flat-series mid-line. No web wiring.
2. **T2 — VM enhancement** (`index.py` + tests): extend `MetricsIndexSurface`; widen
   `build_metrics_index_vm(cfg, conn)`; per-card extraction with per-surface error isolation; headline +
   series population reusing existing builders; the 3 sparklines gated by each surface's own threshold.
3. **T3 — route + template** (`metrics.py` + `index.html.j2` + tests): route call-site update; card grid;
   drill-down preservation; honest suppressed states; ASCII-only.
4. **T4 — operator-witnessed visual gate** (no code): render `/metrics` in a real browser; confirm 9
   cards, 3 sparklines (capital/funnel/process-grade), 6 headline-only cards, honest suppressed states,
   working drill-down. The BINDING gate (Q6/L5).

Single Codex chain at end (Q7), run to convergence.

---

## §10 Test fixture strategy + visual-gate enumeration

### §10.1 Fixtures
- **Sparkline helper:** pure unit tests — empty, all-None, 1 point (→None), 2 points, flat series,
  monotone, mixed None gaps. Assert the points-string shape + 2-dp formatting + viewBox bounds.
- **VM:** seed a fixture DB with (a) ≥10 `pipeline_runs` (so funnel's 10-run floor clears) with
  candidates/buckets so capital + funnel `trend_runs` populate, and ≥5 reviewed closed trades so
  process-grade `rolling_series` draws; AND (b) a below-threshold DB (3 runs) to assert each sparkline
  suppresses with the correct caption. Assert headline-stat text per surface and per-surface error
  isolation (inject one compute failure → that card degrades, others render).
- **Route:** `with TestClient(app) as client:` (lifespan); assert 200, 9 cards present, `data-*` markers
  for sparkline-present vs suppressed, drill-down hrefs unchanged.

### §10.2 The byte/string-test insufficiency caveat (per the test-discipline gotcha)
String/`data-*` assertions confirm the points string is EMITTED; they do NOT confirm the rendered glyph
reads correctly. The **operator-witnessed browser render is the binding gate** (L5/Q6). IF matplotlib:
also visually verify no mathtext mangling (though sparklines carry no annotation text).

### §10.3 Operator-witnessed gate (S-steps)
- **S1** fast suite (`pytest -m "not slow"`) green on the branch + `ruff check swing/` clean.
- **S2** schema: assert `EXPECTED_SCHEMA_VERSION == 23` unchanged (NO migration) — unless OQ-5 lands
  cached-matplotlib (then v24 STRICT `pre_version==23`).
- **S3** browser: `/metrics` renders 9 cards; the 3 trend surfaces show sparklines; the 6 point-estimate
  surfaces show headline-only; below-threshold trend surfaces show honest suppressed captions; every
  drill-down link resolves to its existing surface route.
- **S4** L2 Schwab source-grep still passes (no new Schwab calls). **S5** ASCII-only in all user-facing
  strings. **S6** `git log -1 --format='%(trailers)'` == `[]` (zero Co-Authored-By).

---

## §11 Schema impact — VERDICT: NO change (v23 held)

Recommended path (inline-`<polyline>`, render-direct) writes nothing and adds no enum → **schema stays
v23**. No `chart_renders` rows, no migration, no v24. **BOTH OQ-1 options (inline AND matplotlib) are
render-direct → both are schema-free** — because the cached-matplotlib variant is structurally
incompatible with the ticker/run-keyed `chart_renders` table and is REMOVED from scope (§8). There is
therefore **no in-scope v24 trigger at all.** v22/v23 substrate untouched (L3).

---

## §12 V1 simplifications + V2 candidates

**V1 simplifications:**
- Inline-`<polyline>` sparklines (no matplotlib, no render lock, no schema) — pending OQ-1.
- Eager server-render (no HTMX lazy-load) — pending OQ-6.
- One series per trend surface (utilization / A+ ident / rolling grade) — the others are V2.
- No sparkline interactivity (no hover tooltips, no zoom) — the drill-down route carries the detail.

**V2 candidates (banked, NOT in V1):**
- Per-card HTMX lazy-load if any compute proves heavy on the operator's box.
- Multi-series sparklines (utilization + heat overlaid; A+ + watch).
- Cached sparkline SVGs — would need a NEW non-ticker/non-run cache table (NOT `chart_renders`, which is
  ticker/run-keyed; §8). Only if profiling ever shows the render-direct path is too slow. Out of SB5.
- A "headline delta vs prior run" arrow on the trend cards.
- Sparkline for additional surfaces IF they later gain a series (would require new computation — out of
  scope here per L1/L2).

---

## §13 Operator decision items (OQs) — for writing-plans triage

- **OQ-1 (THE decision):** sparkline tech — **inline-`<polyline>` (recommended)** vs matplotlib-SVG. §7.
- **OQ-2:** sparkline breadth — **3 trend-bearing surfaces only (recommended)** vs all 9 (rejected:
  fabricates 6 sparklines, violates L4).
- **OQ-3:** route shape — **enhance `/metrics` in place (recommended)** vs new `/metrics/overview`.
- **OQ-4:** headline stat per surface — confirm the §6 table (esp. which series for the 3 sparklines:
  utilization vs heat; A+ ident vs taken; which of the 7 process-grade metric keys).
- **OQ-5:** render path — **render-direct, no schema** (the ONLY viable path; cached `chart_renders` is
  REMOVED as structurally incompatible — §8). Both OQ-1 options are render-direct. (OQ-5 is effectively
  resolved; retained for the record.)
- **OQ-6:** lazy-load — **eager inline (recommended)** vs HTMX per-card (matters mainly if matplotlib).
- **OQ-7:** Codex chain count at writing-plans — **single (pure-UX, recommended)** vs two-chain
  (unlikely — no analytical artifact).

---

## §14 Cumulative discipline compliance

- **#11/#9 schema:** N/A in the recommended path (no migration); guards documented for the v24 escape
  hatch only (§8).
- **base.html.j2 shared / L7:** new fields live on `MetricsIndexSurface`/`MetricsIndexVM` (leaf), NOT
  `BaseLayoutVM` → no base-VM fan-out.
- **matplotlib mathtext (#):** sparklines carry NO annotation text; if matplotlib chosen, the ASCII /
  no-mathtext discipline + manual visual verification still apply (L5).
- **PowerShell cp1252 (#16/#32):** all headline/caption/suppressed strings ASCII-only.
- **session-anchor read/write:** the overview reuses each surface's EXISTING anchor (the per-surface
  computes already encode the correct backward-looking `last_completed_session` vs forward-looking
  `action_session_for_run` choice). The overview does NOT introduce a new anchor predicate — it consumes
  the post-T-T4.SB.2 (delimiter-aware, wiring-correct) outputs as-is (no re-derivation).
- **cache/executor race:** no new executor writes (the overview is synchronous read-only); IF HTMX
  lazy-load (OQ-6) is later chosen, the cache-write-on-deadline discipline applies.
- **bad-exemplar isolation:** per-card try/except (§4.4).
- **L2 Schwab:** no new Schwab calls (the metric computes are DB-read-only).
- **Co-Authored-By / trailer-parse:** no co-author footer; final `-m` paragraph plain prose; verify
  `%(trailers)` empty (S6).

---

## §15 Phase 14 close-out readiness note (L9)

SB5 is the **FINAL** Phase 14 sub-bundle. On SB5 ship, all 5 sub-bundles are merged:
SB1 (data-wiring `e323339`) · SB2 (temporal log v22 `27f8007`) · SB3 (chart uniformity v23 `edd098d`) ·
SB4 (review+journal `31da4a5`) · SB5 (metrics overview).

**Close-out (Sec 9.1 Q6) requires:**
1. The operator-witnessed **cross-sub-bundle integration review** (charts + review/journal + metrics
   overview rendering coherently together in one browser session).
2. Sequencing the **banked Phase 14 follow-ups** (NOT in SB5 scope):
   - Schwab daily-bar wiring (SB3 banked: `price_history` minute-default footgun for daily bars).
   - `market_weather` 200MA fetch-window (SB3 banked).
   - theme2 vcp 5-contraction cosmetic crowding (SB3 banked).
   - `_bulz_*` → general row-expand rename (SB4 banked).
3. CLAUDE.md status-line refresh to "Phase 14 CLOSED" once the close-out review passes.

Schema verdict for close-out: Phase 14 lands at **v23** (SB5 adds no schema in the recommended path).

---

*End of design spec. Recommended path: enhance `/metrics` in place; inline-`<polyline>` sparklines on
the 3 trend-bearing surfaces only (capital_friction utilization / identification_funnel A+ ident /
process_grade_trend rolling grade), each gated by that surface's own existing threshold (5 / 10 /
line-band); headline stat on all 9; honest suppressed states; NO schema change; single Codex chain to
convergence; operator browser render is the binding gate.*
