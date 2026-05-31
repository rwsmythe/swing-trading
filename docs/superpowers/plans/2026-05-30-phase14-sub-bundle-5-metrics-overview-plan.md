# Phase 14 Sub-bundle 5 — Metrics Overview (P14.N5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the existing text-only `GET /metrics` index into a graphics-driven overview dashboard — each of the 9 metric surfaces gets a card with a headline stat (all 9) and an inline-`<polyline>` SVG sparkline (the 3 trend-bearing surfaces only), while preserving every drill-down link.

**Architecture:** Read-mostly. A new ~40-line pure sparkline helper (`build_sparkline_points`) generalises the existing `process_grade_trend` polyline algorithm to a 100×30 glyph. The index builder widens from `build_metrics_index_vm(conn)` to `build_metrics_index_vm(cfg, conn)` and, per surface, reuses the *existing* per-surface `build_*_vm` / `compute_*` outputs (zero new computation, zero data-write) to populate a headline stat + (for the 3 trend surfaces) a sparkline points string, each gated by that surface's *own* suppression threshold (capital=5, funnel=10, process-grade=line-band). The template replaces the `<ul>` with a card grid. NO schema change — sparklines render-direct inline; `EXPECTED_SCHEMA_VERSION` stays 23.

**Tech Stack:** Python 3.14, FastAPI + Starlette 1.0, Jinja2 (HTMX present but unused here — pure server-render), inline SVG `<polyline>`, pytest (`-m "not slow"`), ruff. CLI in worktree: `python -m swing.cli`.

---

## §A Goals / Non-goals

### §A.1 Goals (in scope)
1. **Sparkline helper** — a pure, suppression-aware `build_sparkline_points(values, *, width, height) -> str | None` that returns an inline-SVG `<polyline>` points string for a numeric series, or `None` when fewer than 2 points are defined. NO matplotlib, NO `_RENDER_LOCK`, ASCII-only.
2. **Headline stat on all 9 surfaces** — one at-a-glance figure per surface, read from an EXACT existing result/VM field (no re-derivation, no cross-row aggregate), reusing each surface's existing suppression semantics; honest placeholder text when suppressed (never a bare `—`/`N/A`).
3. **Sparkline on the 3 trend-bearing surfaces only** — `capital_friction` (utilization), `identification_funnel` (A+ identifications/run), `process_grade_trend` (rolling process grade), each gated by its OWN existing threshold constant; honest suppressed caption below threshold.
4. **Card grid** — replace the link-only `<ul class="metrics-tiles">` with a 9-card grid; the whole card stays the drill-down link to the existing per-surface route.
5. **Builder widening** — `build_metrics_index_vm(conn)` → `build_metrics_index_vm(cfg, conn)`; route call-site + the 3 existing unit-test call-sites updated in the same task.
6. **Per-card error isolation** — a single surface's compute failure degrades THAT card to an "unavailable" state (logged); the grid always renders 9 cards.
7. **Operator-witnessed render gate** — the rendered overview in a real browser is the BINDING visual gate (Q6/L5).
8. **Phase 14 close-out readiness note** — SB5 is the FINAL sub-bundle.

### §A.2 Non-goals (OUT of scope — do NOT plan/implement)
- Any NEW metric computation / surface; ANY change to the 9 per-surface routes' DATA logic (L1).
- A NEW data-write path / `chart_renders` write (L2).
- ANY schema change / migration / `EXPECTED_SCHEMA_VERSION` bump (L3) — render-direct inline only.
- Matplotlib sparklines (OQ-1 LOCKed inline-`<polyline>`); JS charting (Q5 no-JS).
- A new `/metrics/overview` route (OQ-3 LOCKed enhance-in-place).
- Sparklines on the other 6 surfaces (OQ-2 / L4 honesty floor — they get a headline only).
- HTMX lazy-load per card (OQ-6 LOCKed eager); sparkline hover/zoom interactivity (V2).
- Multi-series sparklines; "delta vs prior run" arrow; cached sparkline SVGs (all banked V2, §12 of spec).
- The SB1–SB4 surfaces; the v22/v23 substrate; SB5.5 (Schwab) items; the Phase 14 close-out polish batch + B-7; Phase 15+.

---

## §B File map

All paths relative to repo root. **(N)** = new, **(M)** = modify, **(R)** = reuse read-only.

### §B.1 Production
| File | Disp | Responsibility |
|------|------|----------------|
| `swing/web/view_models/metrics/sparkline.py` | **(N)** | Pure `build_sparkline_points(values, *, width=100, height=30, pad=2.0, min_points=2) -> str \| None`. The only new module. ~50 lines. |
| `swing/web/view_models/metrics/index.py` | **(M)** | Extend `MetricsIndexSurface` with 6 overview fields; widen `build_metrics_index_vm(conn)` → `(cfg, conn)`; add 9 per-surface extractor helpers (each try/except-isolated) reusing existing `build_*_vm`/`compute_*`; compose enriched surfaces. |
| `swing/web/routes/metrics.py` | **(M)** | `metrics_index` route: pass `cfg` to the widened builder (`build_metrics_index_vm(cfg, conn)`). Updated in T-5.2.d ATOMIC with the builder widening (NOT T-5.3), so `GET /metrics` never runs against the old signature. NO other route changes. |
| `swing/web/templates/metrics/index.html.j2` | **(M)** | Replace `<ul>` with the card grid: per-card label + headline stat (+ caption) or honest suppressed text + inline-`<svg><polyline></svg>` sparkline (3 surfaces) or sparkline-suppressed caption + drill-down link. ASCII-only. |
| `swing/web/static/app.css` | **(M)** | Card-grid + sparkline-glyph styling (`.metrics-overview-grid`, `.metrics-card`, `.metrics-card__headline`, `.metrics-card__sparkline`, `.metrics-card__suppressed`). The 3 `.metrics-tiles`/`.metrics-tile` classes are currently UNSTYLED (no rule references them); the new classes supersede them. |

### §B.2 Reuse (read-only — DO NOT modify the data logic)
| File | What is reused |
|------|----------------|
| `swing/web/view_models/metrics/trade_process_card.py` | `build_trade_process_card_vm(*, cfg, conn=None, active_cohort_key=None)` :123; `ALL_COHORTS_KEY="__all__"` :46; `vm.cohort_tabs` :97; `CohortTabVM.cohort_key` :68 / `.metrics` :71. |
| `swing/metrics/process.py` | `TradeProcessMetricsResult.expectancy_R: MetricCellB` :421; `MetricCellB.value: BootstrapCI \| SuppressedMetric` :347. |
| `swing/web/view_models/metrics/hypothesis_progress_card.py` | `build_hypothesis_progress_card_vm(*, cfg, conn=None)` :404; `vm.cohorts` :192. |
| `swing/web/view_models/metrics/tier_comparison.py` | `build_tier_comparison_vm(*, cfg, conn=None, exclude_unresolved_discrepancies=False)` :69; `vm.result: TierComparisonResult \| None` :58. |
| `swing/metrics/tier.py` | `APLUS_COHORT="A+ baseline"` :95; `TAXONOMY_COHORTS` :88–93; `TierComparisonResult.cohorts` :300; `CohortStatistics.cohort_name` / `.expectancy: BootstrapCI \| SuppressedMetric` :225; `DeviationOutcomeResult.rows` :419 (tuple, TAXONOMY_COHORTS order); `DeviationOutcomeRow.cohort_name` / `.expectancy_relative_to_aplus_pct: float \| None` :375 / `.row_suppressed: bool` :376. |
| `swing/web/view_models/metrics/capital_friction.py` | `build_capital_friction_vm(*, cfg, conn=None)` :75; `vm.result: CapitalFrictionResult \| None` :58. |
| `swing/metrics/capital.py` | `CapitalFrictionResult` :162; `.current_capital_utilization_pct: float \| None` :168; `.trend_runs: tuple[CapitalFrictionTrendPoint, ...]` :191; `CapitalFrictionTrendPoint.current_capital_utilization_pct` :109; `TREND_MIN_RUNS=5` :61. |
| `swing/web/view_models/metrics/maturity_stage.py` | `build_maturity_stage_vm(*, cfg, conn=None)` :52; `vm.result: MaturityStageResult \| None` :41. |
| `swing/metrics/maturity.py` | `MaturityStageResult.rows: tuple[MaturityStageRow, ...]` :125. |
| `swing/web/view_models/metrics/identification_funnel.py` | `build_identification_funnel_vm(*, cfg, conn=None)` :61; `vm.result: IdentificationFunnelResult \| None` :44. |
| `swing/metrics/funnel.py` | `IdentificationFunnelResult.trend_runs: tuple[IdentificationFunnelPoint, ...]` :118; `IdentificationFunnelPoint.aplus_identifications_per_run: int` :70; `TREND_MIN_RUNS=10` :42. |
| `swing/web/view_models/metrics/deviation_outcome.py` | `build_deviation_outcome_vm(*, cfg, conn=None, exclude_unresolved_discrepancies=False)` :69; `vm.result: DeviationOutcomeResult \| None` :58. |
| `swing/metrics/process_grade_trend.py` | `compute_process_grade_trend(conn, window_size=...)` :524; `ProcessGradeTrendResult.rolling_series: dict[str, RollingMetricSeries]` :219; `RollingMetricSeries.line_points` :172 / `.rendered_value` :174 / `.drawability_text` :176 / `.suppressed: SuppressedMetric \| None` :177; `RollingLinePoint.value: float \| None`; `PROCESS_GRADE_TREND_METRIC_CLASSES` (dict, key `"process_grade_rolling_N"`). |
| `swing/web/view_models/metrics/process_grade_trend.py` | The polyline-points ALGORITHM reference (`_format_polyline_points`/`_polyline_x`/`_polyline_y` :225–302) — generalised, NOT imported, by `sparkline.py`. |
| `swing/web/view_models/patterns/outcomes_card.py` | `build_pattern_outcomes_vm(conn, *, session_date)` :39 — **NOTE: positional `conn`, NO `cfg`**; `vm.pattern_outcome_rows` :34. |
| `swing/metrics/pattern_outcomes.py` | `PatternOutcomeRow.pattern_class: str` :47 / `.triggered_ci: WilsonCI \| None` :50 / `.triggered_pct_text: str` :51 / `.suppressed_text: str \| None` :56. |
| `swing/data/models.py` | `DETECTOR_PATTERN_CLASSES=("vcp","flat_base","cup_with_handle","high_tight_flag","double_bottom_w")` :28. |
| `swing/metrics/honesty.py` | `SuppressedMetric.placeholder_text: str` :99 (and `BootstrapCI.point`). |
| `swing/web/view_models/metrics/shared.py` | `BaseLayoutVM` :27 (8 fields — UNCHANGED; new fields go on the leaf `MetricsIndexSurface`, NOT here — L7). |

### §B.3 Tests (N)
| File | Covers |
|------|--------|
| `tests/web/view_models/metrics/test_sparkline.py` | The pure helper (T-5.1). |
| `tests/web/view_models/metrics/test_index_overview.py` | The widened builder + 9 extractors + error isolation (T-5.2). |
| `tests/web/test_routes/test_metrics_index_overview.py` | The route + template render (T-5.3). |

### §B.4 Tests to UPDATE (call-site widening — same task as the widening, T-5.2)
- `tests/web/test_base_layout_vm_recent_multi_leg_field.py:459` — `build_metrics_index_vm(conn)` → `build_metrics_index_vm(cfg, conn)`.
- `tests/web/test_routes/test_metrics_routes.py:78` — same.
- `tests/web/test_routes/test_metrics_pattern_outcomes.py:235` — same.

---

## §C Surface integration

### §C.1 Request flow (unchanged shape; widened call)
```
GET /metrics
  → metrics_index(request)                         # routes/metrics.py
      cfg  = request.app.state.cfg
      conn = sqlite3.connect(cfg.paths.db_path)
      vm   = build_metrics_index_vm(cfg, conn)      # WIDENED (was conn-only)
      conn.close()
  → TemplateResponse(request, "metrics/index.html.j2", {"vm": vm})
```

### §C.2 The builder's internal fan-out (read-only; single shared `conn`)
`build_metrics_index_vm(cfg, conn)` keeps its existing BaseLayoutVM population (discrepancy helpers on `conn`, `session_date` via `action_session_for_run`) and adds, per registry surface, a try/except-isolated extractor that reuses the existing per-surface builder/compute on the SAME `conn`:

| # | Surface (registry path) | Reuses | Headline accessor (verified) | Sparkline? |
|---|---|---|---|---|
| 1 | `/metrics/trade-process` | `build_trade_process_card_vm(cfg=cfg, conn=conn)` | `next(t for t in vm.cohort_tabs if t.cohort_key==ALL_COHORTS_KEY).metrics.expectancy_R.value` → `BootstrapCI.point` else `SuppressedMetric.placeholder_text` | no |
| 2 | `/metrics/hypothesis-progress` | `build_hypothesis_progress_card_vm(cfg=cfg, conn=conn)` | `len(vm.cohorts)` | no |
| 3 | `/metrics/tier-comparison` | `build_tier_comparison_vm(cfg=cfg, conn=conn)` | `next(c for c in vm.result.cohorts if c.cohort_name==APLUS_COHORT).expectancy` → `.point` else `.placeholder_text` | no |
| 4 | `/metrics/capital-friction` | `build_capital_friction_vm(cfg=cfg, conn=conn)` | `vm.result.current_capital_utilization_pct` | **YES** utilization |
| 5 | `/metrics/maturity-stage` | `build_maturity_stage_vm(cfg=cfg, conn=conn)` | `len(vm.result.rows)` | no |
| 6 | `/metrics/identification-funnel` | `build_identification_funnel_vm(cfg=cfg, conn=conn)` | `vm.result.trend_runs[-1].aplus_identifications_per_run` | **YES** A+ ident/run |
| 7 | `/metrics/deviation-outcome` | `build_deviation_outcome_vm(cfg=cfg, conn=conn)` | `next(r for r in vm.result.rows if r.cohort_name==DEVIATION_HEADLINE_COHORT).expectancy_relative_to_aplus_pct` (gated on `not r.row_suppressed`) | no |
| 8 | `/metrics/process-grade-trend` | `compute_process_grade_trend(conn)` | `series=result.rolling_series["process_grade_rolling_N"]`; `series.suppressed.placeholder_text` if suppressed else `f"{series.rendered_value.point:.2f}"` | **YES** rolling grade |
| 9 | `/metrics/pattern-outcomes` | `build_pattern_outcomes_vm(conn, session_date=session_date)` | `next(r for r in vm.pattern_outcome_rows if r.pattern_class==PATTERN_HEADLINE_CLASS)` → `.triggered_pct_text` if `.triggered_ci is not None` else `.suppressed_text` | no |

**Connection sharing:** every reused builder accepts the shared `conn` (surfaces 1–7 via `conn=conn`; 9 positionally; 8 via `compute_*(conn)`), so the whole overview runs on ONE connection (the one the route opened). NO builder opens a new connection when `conn` is passed.

**Why surface 8 calls `compute_*` directly (not the VM):** `build_process_grade_trend_vm` exposes only a pre-scaled-to-800×360 `svg_polyline_points` string, NOT the raw rolling-mean values — it cannot be re-scaled to 100×30. The raw `line_points` (each `.value: float | None`) live on the `compute_process_grade_trend` result. A single `compute_process_grade_trend(conn)` call yields BOTH the headline (`series.rendered_value`/`series.suppressed`) and the sparkline values (`series.line_points`) and the gate (`series.drawability_text`), so there is no double-compute and no re-implementation of the gate (we read its output). See §G T-5.2 for the exact extractor.

### §C.3 Sparkline series + per-surface threshold (NON-uniform — L4)
| Surface | Sparkline values | Gate (its OWN threshold) | Suppressed caption (ASCII) |
|---|---|---|---|
| capital_friction | `[p.current_capital_utilization_pct for p in vm.result.trend_runs]` | `len(vm.result.trend_runs) >= TREND_MIN_RUNS` (=5, capital.py:61) | `"trend needs >=5 runs (have N)"` |
| identification_funnel | `[p.aplus_identifications_per_run for p in vm.result.trend_runs]` | `len(vm.result.trend_runs) >= TREND_MIN_RUNS` (=10, funnel.py:42) | `"trend needs >=10 runs (have N)"` |
| process_grade_trend | `[p.value for p in series.line_points]` | `series.suppressed is None and series.drawability_text == "rolling line drawable"` AND `build_sparkline_points(...) is not None` | `"rolling grade line not yet drawable"` |

After the gate passes, `build_sparkline_points` applies its OWN `<2-defined-points → None` degenerate guard (a polyline needs ≥2 vertices); if it returns `None` despite the gate, the surface falls back to the sparkline-suppressed caption (belt-and-suspenders, no fabricated line).

### §C.4 OQ-4 fixed-selector constants (operator-confirmable; defaulted in this plan)
Two surfaces read ONE row of a collection by a fixed, hard-coded selector (never a "worst"/"overall" aggregate — that would be new computation, L2). The plan defaults them; the operator may override at executing-plans:
- **`DEVIATION_HEADLINE_COHORT = "Near-A+ defensible: extension test"`** (the primary non-A+ cohort; the first TAXONOMY_COHORTS entry after "A+ baseline" — most operator-meaningful Δ-vs-A+).
- **`PATTERN_HEADLINE_CLASS = "vcp"`** (the headline detector pattern class; first in DETECTOR_PATTERN_CLASSES).

Both are module-level constants in `index.py` so the operator can re-point them in one place. (Surface 1 uses `ALL_COHORTS_KEY`; surface 3 uses `APLUS_COHORT`; surface 8 uses `"process_grade_rolling_N"` — all canonical, not OQ-4-open.)

---

## §D Out-of-scope (re-statement — HOLD THE LINE)
Identical to §A.2. Specifically the executing engineer MUST NOT: add a migration / bump `EXPECTED_SCHEMA_VERSION`; introduce matplotlib or a `_RENDER_LOCK` call on this path; add a `chart_renders` write; add sparklines to the 6 non-trend surfaces; compute any cross-row aggregate for a headline; introduce a new `/metrics/overview` route; add HTMX to the overview; touch the per-surface routes' data logic or the v22/v23 substrate. If any of these appears necessary, STOP and escalate.

---

## §E LOCK reverification (Sec 9.1 + L1–L9 + §1.3 OQ dispositions)

| LOCK | Disposition in this plan | Where enforced |
|------|--------------------------|----------------|
| **Q1** sequencing (metrics LAST) | SB5 is final; §O close-out note | §O |
| **Q2** SERIAL | single executing-plans bundle | §G |
| **Q5** no-JS static graphics | inline `<polyline>`, no JS | §G T-5.1/T-5.3 |
| **Q6** operator render gate | binding browser gate | §I |
| **Q7** SINGLE Codex chain | one chain to convergence | §J |
| **L1** scope = P14.N5 only | no new metric/route; per-surface DATA logic untouched | §A.2 / §D |
| **L2** read-mostly | reuse `build_*_vm`/`compute_*`; ZERO write; ZERO new compute | §C.2 / §G |
| **L3** NO schema | `EXPECTED_SCHEMA_VERSION` stays 23; no migration | §K / §G T-5.4 |
| **L4** honesty floor | sparklines on 3 surfaces ONLY; each its OWN threshold; no fabricated line | §C.3 / §G T-5.1/T-5.2 |
| **L5** visual-gate discipline | rendered card is binding; ASCII-only strings | §I / §H |
| **L6** render-lock (inline → none) | pure string build; no `_RENDER_LOCK`, no matplotlib | §G T-5.1 |
| **L7** BaseLayoutVM contract | new fields on `MetricsIndexSurface` (leaf), NOT `BaseLayoutVM` | §G T-5.2 |
| **L8** HTMX disciplines | overview stays pure server-render (no HTMX) | §G T-5.3 |
| **L9** close-out readiness | §O note | §O |
| **OQ-1** inline-`<polyline>` | the ONLY sparkline tech; no matplotlib | §G T-5.1 |
| **OQ-2** 3 trend surfaces only | capital/funnel/process-grade | §C.3 |
| **OQ-3** enhance `/metrics` in place | no new route | §C.1 |
| **OQ-4** headline selectors | spec §6 exact accessors, re-grepped (§C.2); fixed selectors §C.4 | §C.2/§C.4 |
| **OQ-5** render-direct, no cache/schema | inline per-request; nothing persists | §K |
| **OQ-6** eager | no lazy-load | §G T-5.3 |
| **OQ-7** single chain | §J | §J |

---

## §F Discipline hooks (cumulative gotchas applied)

- **base.html.j2 shared / L7:** new fields land on `MetricsIndexSurface` (leaf VM) + `MetricsIndexVM` already inherits BaseLayoutVM unchanged → NO base-VM fan-out. Verify `BaseLayoutVM` (shared.py:27) is untouched.
- **PowerShell cp1252 (#16/#32) — TWO sources of non-ASCII (Codex R1 CRITICAL #1):** (a) strings THIS plan authors (`>=` not `≥`, `delta` not `Δ`, `-` not em-dash) — keep ASCII; AND (b) **REUSED metric text** — `SuppressedMetric.placeholder_text` is built with a real `≥` glyph (`honesty.py:42`), so reusing it verbatim leaks non-ASCII the source-grep gate would miss. FIX: a central `_ascii()` chokepoint in `_enrich_surface` coerces every reused text field (`≥`->`>=` etc., then `encode("ascii","replace")`) so the overview's ASCII guarantee holds end-to-end. Verified by a rendered-`body.isascii()` route test (T-5.3) on a LOW-sample DB where suppression text appears — NOT just a source grep.
- **matplotlib mathtext (#):** N/A — inline `<polyline>` carries no text; OQ-1 LOCKed inline. If ANY matplotlib appears, STOP (OQ-1 violation).
- **session-anchor read/write:** the overview introduces NO new anchor predicate. Each reused builder already encodes its correct backward-looking `last_completed_session` vs forward-looking `action_session_for_run` choice (capital/funnel trends are backward-looking; the index `session_date` stays forward-looking `action_session_for_run` as today). Consume the post-T-T4.SB.2 (delimiter-aware, wiring-correct) outputs as-is — NO re-derivation.
- **bad-exemplar isolation (#):** each per-surface extractor wrapped in its own try/except → a single compute failure degrades THAT card only (logged via `logging.getLogger(__name__).warning(...)`); the grid always renders 9 cards (§C.2 / §G T-5.2).
- **`vm.result is None` guard:** tier/capital/maturity/funnel/deviation VMs expose `result: ... | None`. Each extractor guards `if vm.result is None` → headline-unavailable (NOT a crash). Folded into the try/except but asserted explicitly by test.
- **Empty-collection guards:** `vm.result.trend_runs[-1]` (funnel headline) and `next(...)` (surfaces 1/3/7/9) must guard empty/StopIteration → suppressed text, not IndexError/StopIteration.
- **`... or None` vs `... or ""`:** N/A — no nullable CHECK-constrained text columns written (no DB write at all). Headline/caption fields default to `None` on the dataclass and the template branches on `is not none`.
- **L2 Schwab source-grep:** the reused capital computation reads equity from DB snapshots (the same path the per-surface page uses) — NO NEW Schwab API call is introduced. T-5.4 re-runs the L2 Schwab source-grep to confirm zero new calls.
- **Co-Authored-By / trailer-parse:** NO co-author footer; final `-m` paragraph of every commit is plain prose (no leading `Word:`); `git log -1 --format='%(trailers)'` == `[]` verified at T-5.4.
- **TestClient lifespan:** route tests use `with TestClient(app) as client:` (the metrics index does not touch `price_fetch_executor`, but the project convention + base-layout safety favours the lifespan-entered client; mirror existing `test_metrics_routes.py`).
- **#27 silent-skip audit:** N/A (no pipeline step); but the per-card degrade path LOGS a warning (not a silent swallow) so an extractor failure is observable.

---

## §G Per-task implementation tasks

### §G.0 Commit cadence preface
- Conventional commits only; stems `feat(web):` / `test(web):` / `style(web):` (CSS). **NO `Co-Authored-By`. NO `--no-verify`.** Final `-m` paragraph plain prose (no leading `Word:` token — trailer-parse hazard).
- TDD per step: write failing test -> run, see it fail for the RIGHT reason -> minimal impl -> run, see pass -> commit.
- **Cascade audit each task** (gotcha #11 spirit): after each task, grep for any other call-site of a changed signature (esp. `build_metrics_index_vm`) and confirm none was missed. After T-5.2, re-grep `build_metrics_index_vm(` across `swing/` + `tests/` — only the route + the 3 listed tests should call it.
- Run `python -m pytest -m "not slow" -q tests/web/view_models/metrics/ tests/web/test_routes/` after each task; full fast suite at T-5.4.
- 3-5 commits per task target.

---

### Task T-5.1: inline-`<polyline>` sparkline helper

**Files:**
- Create: `swing/web/view_models/metrics/sparkline.py`
- Test: `tests/web/view_models/metrics/test_sparkline.py`

**Acceptance criteria:** a pure `build_sparkline_points(values, *, width=100, height=30, pad=2.0, min_points=2) -> str | None`; X over the ORIGINAL sequence index (None gaps do NOT compress time); Y normalised over defined-values min/max, inverted (SVG y-down), flat series -> mid-line; returns `None` when `< min_points` DEFINED values; 2-dp formatting; ASCII-only; NO matplotlib / NO `_RENDER_LOCK`. Preserves L4/L6/OQ-1.

- [ ] **Step 1: Write the failing tests**

```python
# tests/web/view_models/metrics/test_sparkline.py
"""T-5.1 — pure inline-SVG sparkline points helper (P14.N5)."""
from __future__ import annotations

import pytest

from swing.web.view_models.metrics.sparkline import build_sparkline_points


def _coords(points: str) -> list[tuple[float, float]]:
    return [tuple(float(c) for c in pair.split(",")) for pair in points.split(" ")]


def test_two_points_emits_two_vertices_spanning_width():
    out = build_sparkline_points([0.0, 10.0], width=100, height=30, pad=2.0)
    assert out is not None
    coords = _coords(out)
    assert len(coords) == 2
    assert coords[0][0] == pytest.approx(2.0)
    assert coords[1][0] == pytest.approx(98.0)
    assert coords[0][1] > coords[1][1]  # 0.0 lower on screen than 10.0 (y-down)


def test_empty_returns_none():
    assert build_sparkline_points([]) is None


def test_all_none_returns_none():
    assert build_sparkline_points([None, None, None]) is None


def test_single_defined_returns_none():
    assert build_sparkline_points([5.0]) is None
    assert build_sparkline_points([None, 5.0, None]) is None


def test_flat_series_is_mid_line():
    out = build_sparkline_points([5.0, 5.0, 5.0], width=100, height=30, pad=2.0)
    assert out is not None
    ys = {round(y, 2) for _, y in _coords(out)}
    assert ys == {pytest.approx(15.0)}  # height/2 mid-line


def test_none_gap_does_not_compress_x_axis():
    out = build_sparkline_points([5.0, None, 7.0], width=100, height=30, pad=2.0)
    assert out is not None
    coords = _coords(out)
    assert len(coords) == 2  # None vertex omitted (single connected line)
    assert coords[0][0] == pytest.approx(2.0)   # index 0
    assert coords[1][0] == pytest.approx(98.0)  # index 2, NOT compressed to index 1


def test_two_dp_formatting():
    out = build_sparkline_points([1.0, 2.0, 3.0])
    assert out is not None
    for pair in out.split(" "):
        x, y = pair.split(",")
        assert len(x.split(".")[1]) == 2
        assert len(y.split(".")[1]) == 2


def test_non_positive_dimensions_raise():
    with pytest.raises(ValueError):
        build_sparkline_points([1.0, 2.0], width=0)
    with pytest.raises(ValueError):
        build_sparkline_points([1.0, 2.0], height=-1)


def test_ascii_only_output():
    out = build_sparkline_points([1.0, 2.0, 3.0])
    assert out is not None and out.isascii()
```

- [ ] **Step 2: Run the tests; verify they fail**

Run: `python -m pytest tests/web/view_models/metrics/test_sparkline.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'swing.web.view_models.metrics.sparkline'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# swing/web/view_models/metrics/sparkline.py
"""Inline-SVG sparkline points helper for the /metrics overview (P14.N5).

Pure + suppression-aware. Generalises the process_grade_trend polyline
algorithm (``view_models/metrics/process_grade_trend.py:_format_polyline_points``)
down to a tiny ~100x30 glyph. NO matplotlib, NO render lock, ASCII-only
(OQ-1 / L6 LOCK).

X is positioned over the ORIGINAL sequence index ``i / (len(values) - 1)``
so a ``None`` gap leaves a horizontal gap in spacing and does NOT compress
time. Y is normalised over [min..max] of the DEFINED values, inverted for
SVG's y-down axis. A flat series (max == min) maps to the mid-line. A single
connected polyline draws across ``None`` gaps (omitting their vertices) —
matching the existing process_grade_trend drill-down precedent. Returns
``None`` when fewer than ``min_points`` values are defined (the caller renders
an honest suppressed caption; never a fabricated/flat line — L4).
"""
from __future__ import annotations

from collections.abc import Sequence


def build_sparkline_points(
    values: Sequence[float | None],
    *,
    width: int = 100,
    height: int = 30,
    pad: float = 2.0,
    min_points: int = 2,
) -> str | None:
    """Return an SVG ``<polyline>`` points string ``"x1,y1 x2,y2 ..."`` (2-dp)
    for ``values``, or ``None`` when fewer than ``min_points`` are defined."""
    if width <= 0 or height <= 0:
        raise ValueError(f"width/height must be > 0; got {width!r}x{height!r}")
    n = len(values)
    if n < min_points:
        return None
    defined = [(i, float(v)) for i, v in enumerate(values) if v is not None]
    if len(defined) < min_points:
        return None

    ys = [v for _, v in defined]
    y_min, y_max = min(ys), max(ys)
    plot_w = float(width) - 2.0 * pad
    plot_h = float(height) - 2.0 * pad
    denom = n - 1  # n >= min_points >= 2 -> denom >= 1, no ZeroDivision

    pieces: list[str] = []
    for i, v in defined:
        x = pad + plot_w * (i / denom)
        if y_max == y_min:
            y = pad + plot_h / 2.0
        else:
            norm = (v - y_min) / (y_max - y_min)
            y = pad + plot_h * (1.0 - norm)
        pieces.append(f"{x:.2f},{y:.2f}")
    return " ".join(pieces)


__all__ = ["build_sparkline_points"]
```

- [ ] **Step 4: Run the tests; verify they pass**

Run: `python -m pytest tests/web/view_models/metrics/test_sparkline.py -q`
Expected: PASS (9 tests). Then `ruff check swing/web/view_models/metrics/sparkline.py` — clean.

- [ ] **Step 5: Commit**

```bash
git add swing/web/view_models/metrics/sparkline.py tests/web/view_models/metrics/test_sparkline.py
git commit -m "feat(web): pure inline-SVG sparkline points helper for the metrics overview

Generalises the process_grade_trend polyline algorithm to a 100x30 glyph;
suppression-aware (returns None below 2 defined points); ASCII-only; no
matplotlib and no render lock per the OQ-1 inline-polyline lock."
```

---

### Task T-5.2: `MetricsIndexVM` enhancement (headline + sparkline extractors)

**Files:**
- Modify: `swing/web/view_models/metrics/index.py`
- Test: `tests/web/view_models/metrics/test_index_overview.py`
- Update (call-site widening): `tests/web/test_base_layout_vm_recent_multi_leg_field.py:459`, `tests/web/test_routes/test_metrics_routes.py:78`, `tests/web/test_routes/test_metrics_pattern_outcomes.py:235`

**Acceptance criteria:** `MetricsIndexSurface` gains 6 overview fields (leaf VM — L7, no `BaseLayoutVM` change); `build_metrics_index_vm` widens to `(cfg, conn)`; 9 per-surface extractors reuse the EXISTING `build_*_vm`/`compute_*` on the shared `conn` (L2 — zero new compute/write); the 3 trend surfaces get sparklines via T-5.1 each gated by its OWN threshold (capital=5, funnel=10, process-grade line-band); the 6 others get a headline + honest suppressed state (no sparkline slot); per-card try/except isolation (one failure degrades that card only); `vm.result is None` + empty-collection guards; the 3 existing call-site tests updated.

#### §G.T-5.2.a — dataclass + `_OverviewCard` + metric formatter

- [ ] **Step 1: Write the failing test**

```python
# tests/web/view_models/metrics/test_index_overview.py (part 1)
"""T-5.2 — metrics overview VM enhancement (P14.N5)."""
from __future__ import annotations

from dataclasses import fields

from swing.web.view_models.metrics.index import MetricsIndexSurface


def test_surface_has_overview_fields_with_safe_defaults():
    names = {f.name for f in fields(MetricsIndexSurface)}
    assert {
        "headline_stat_text", "headline_caption", "headline_suppressed_text",
        "sparkline_points", "sparkline_suppressed_text", "sparkline_kind",
    } <= names
    s = MetricsIndexSurface(path="/x", label="X", description="d")
    assert s.headline_stat_text is None
    assert s.sparkline_kind == "none"
```

- [ ] **Step 2: Run; verify fail** — `python -m pytest tests/web/view_models/metrics/test_index_overview.py -q` -> FAIL (fields absent).

- [ ] **Step 3: Extend the dataclass + add the card holder + formatter** (top of `index.py`, after imports)

```python
from dataclasses import dataclass, field, replace  # add `replace`
import logging

from swing.config import Config
from swing.metrics.honesty import BootstrapCI, SuppressedMetric

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class MetricsIndexSurface:
    """One overview card. Static {path,label,description} from the registry;
    the rest are populated per-request from existing per-surface outputs."""

    path: str
    label: str
    description: str
    headline_stat_text: str | None = None       # display-ready, e.g. "42.0%"
    headline_caption: str | None = None          # unit caption, e.g. "utilization"
    headline_suppressed_text: str | None = None  # honest placeholder when unavailable
    sparkline_points: str | None = None          # inline-SVG points; None => no line
    sparkline_suppressed_text: str | None = None # trend-bearing but below threshold
    sparkline_kind: str = "none"                 # "none" | "inline_svg"


@dataclass(frozen=True)
class _OverviewCard:
    """The 6 per-request overview fields an extractor returns."""

    headline_stat_text: str | None = None
    headline_caption: str | None = None
    headline_suppressed_text: str | None = None
    sparkline_points: str | None = None
    sparkline_suppressed_text: str | None = None
    sparkline_kind: str = "none"


# Reused metric strings (placeholder_text/suppressed_text/triggered_pct_text)
# may embed NON-ASCII — e.g. honesty.py:42 builds "need: >=N" with a real
# U+2265 glyph. Coerce to ASCII at the overview boundary (#16/#32 cp1252).
_ASCII_SUBSTITUTIONS = {
    "≥": ">=", "≤": "<=", "–": "-", "—": "-",
    "→": "->", "±": "+/-", "Δ": "delta",
}


def _ascii(text: str | None) -> str | None:
    if text is None:
        return None
    for src, dst in _ASCII_SUBSTITUTIONS.items():
        text = text.replace(src, dst)
    return text.encode("ascii", "replace").decode("ascii")


def _format_metric_value(value: object) -> tuple[str | None, str | None]:
    """Map a metric value to (headline_text, suppressed_text), reusing the
    metric's OWN suppression placeholder (never fabricates a number — L2/L4).
    The suppressed text is ASCII-coerced (it may carry a non-ASCII glyph)."""
    if isinstance(value, SuppressedMetric):
        return (None, _ascii(value.placeholder_text))
    if isinstance(value, BootstrapCI):
        return (f"{value.point:.2f}", None)
    if value is None:
        return (None, "unavailable")
    return (f"{float(value):.2f}", None)
```

Add a sanitizer test to Step 1 above:

```python
from swing.web.view_models.metrics.index import _ascii


def test_ascii_sanitizer_coerces_geq_glyph():
    # honesty.py emits "need: >=N" with a real U+2265; the overview must ASCII it.
    assert _ascii("[grade: n too low (current: 3, need: ≥5)]").isascii()
    assert ">=5" in _ascii("need: ≥5")
    assert _ascii(None) is None
```

- [ ] **Step 4: Run; verify pass.** `ruff check` clean. The central application of `_ascii` to every card text field lands in T-5.2.d's `_enrich_surface` (so EVERY extractor's output is sanitized in one chokepoint, not per-extractor).

- [ ] **Step 5: Commit**

```bash
git add swing/web/view_models/metrics/index.py tests/web/view_models/metrics/test_index_overview.py
git commit -m "feat(web): add overview fields to MetricsIndexSurface plus card holder and metric formatter

Leaf-VM fields only; BaseLayoutVM is untouched so no shared base.html.j2
fan-out is needed. The formatter reuses each metric's own suppression
placeholder rather than inventing a number."
```

#### §G.T-5.2.b — the 3 trend-surface extractors (sparklines)

- [ ] **Step 1: Write the failing tests** (append to `test_index_overview.py`)

Reuse the fixture-DB seeding utilities the per-surface metric tests already use (mirror `tests/web/test_routes/test_metrics_routes.py`). Provide fixtures: `high_data_cfg_conn` (>=10 `pipeline_runs` populating capital+funnel `trend_runs`; >=5 reviewed closed trades so process-grade draws), `low_data_cfg_conn` (3 runs / <5 reviewed), `borderline_7_runs_cfg_conn` (7 runs — capital draws, funnel must not).

```python
from swing.web.view_models.metrics.index import (
    _extract_capital_friction,
    _extract_identification_funnel,
    _extract_process_grade_trend,
)


def test_capital_sparkline_present_when_runs_at_or_above_5(high_data_cfg_conn):
    cfg, conn = high_data_cfg_conn
    card = _extract_capital_friction(cfg, conn, "2026-05-30")
    assert card.sparkline_kind == "inline_svg"
    assert card.sparkline_points is not None
    assert card.sparkline_suppressed_text is None
    assert card.headline_caption == "utilization"


def test_capital_sparkline_suppressed_below_5(low_data_cfg_conn):
    cfg, conn = low_data_cfg_conn  # 3 runs
    card = _extract_capital_friction(cfg, conn, "2026-05-30")
    assert card.sparkline_kind == "inline_svg"
    assert card.sparkline_points is None
    assert "needs >=5 runs" in card.sparkline_suppressed_text


def test_funnel_sparkline_threshold_is_10_not_5(borderline_7_runs_cfg_conn):
    cfg, conn = borderline_7_runs_cfg_conn
    funnel_card = _extract_identification_funnel(cfg, conn, "2026-05-30")
    assert funnel_card.sparkline_points is None
    assert "needs >=10 runs" in funnel_card.sparkline_suppressed_text


def test_process_grade_sparkline_uses_line_band_gate(high_data_cfg_conn):
    cfg, conn = high_data_cfg_conn
    card = _extract_process_grade_trend(cfg, conn, "2026-05-30")
    assert card.sparkline_kind == "inline_svg"
    assert (card.sparkline_points is not None) ^ (card.sparkline_suppressed_text is not None)
    assert card.headline_caption == "rolling grade"
```

> **Test-arithmetic note (memory `feedback_regression_test_arithmetic`):** the `borderline_7_runs` fixture is the discriminating case — it PASSES capital's `>=5` gate and FAILS funnel's `>=10` gate, so it distinguishes a correct per-surface threshold from a single hardcoded `n<5`. Verify capital draws AND funnel suppresses on the SAME 7-run DB.

- [ ] **Step 2: Run; verify fail** — extractors not defined yet (`ImportError`).

- [ ] **Step 3: Implement the 3 trend extractors** (in `index.py`)

```python
from swing.metrics.capital import TREND_MIN_RUNS as _CAPITAL_TREND_MIN_RUNS
from swing.metrics.funnel import TREND_MIN_RUNS as _FUNNEL_TREND_MIN_RUNS
from swing.metrics.process_grade_trend import compute_process_grade_trend
from swing.web.view_models.metrics.capital_friction import build_capital_friction_vm
from swing.web.view_models.metrics.identification_funnel import (
    build_identification_funnel_vm,
)
from swing.web.view_models.metrics.sparkline import build_sparkline_points

_PROCESS_GRADE_HEADLINE_METRIC = "process_grade_rolling_N"


def _extract_capital_friction(cfg: Config, conn, session_date: str) -> _OverviewCard:
    vm = build_capital_friction_vm(cfg=cfg, conn=conn)
    result = vm.result
    if result is None:
        return _OverviewCard(
            headline_suppressed_text="unavailable",
            sparkline_kind="inline_svg",
            sparkline_suppressed_text="trend unavailable",
        )
    util = result.current_capital_utilization_pct
    headline = None if util is None else f"{util:.1f}%"
    headline_supp = "utilization unavailable" if util is None else None
    runs = result.trend_runs
    points: str | None = None
    if len(runs) >= _CAPITAL_TREND_MIN_RUNS:
        points = build_sparkline_points(
            [p.current_capital_utilization_pct for p in runs]
        )
    if points is None:
        supp = (
            f"trend needs >={_CAPITAL_TREND_MIN_RUNS} runs (have {len(runs)})"
            if len(runs) < _CAPITAL_TREND_MIN_RUNS
            else "trend not drawable (insufficient defined points)"
        )
    else:
        supp = None
    return _OverviewCard(
        headline_stat_text=headline,
        headline_caption="utilization",
        headline_suppressed_text=headline_supp,
        sparkline_points=points,
        sparkline_suppressed_text=supp,
        sparkline_kind="inline_svg",
    )


def _extract_identification_funnel(cfg: Config, conn, session_date: str) -> _OverviewCard:
    vm = build_identification_funnel_vm(cfg=cfg, conn=conn)
    result = vm.result
    if result is None:
        return _OverviewCard(
            headline_suppressed_text="unavailable",
            sparkline_kind="inline_svg",
            sparkline_suppressed_text="trend unavailable",
        )
    runs = result.trend_runs
    if runs:
        headline = str(runs[-1].aplus_identifications_per_run)
        headline_supp = None
    else:
        headline = None
        headline_supp = "no pipeline runs yet"
    points: str | None = None
    if len(runs) >= _FUNNEL_TREND_MIN_RUNS:
        points = build_sparkline_points(
            [float(p.aplus_identifications_per_run) for p in runs]
        )
    if points is None:
        supp = (
            f"trend needs >={_FUNNEL_TREND_MIN_RUNS} runs (have {len(runs)})"
            if len(runs) < _FUNNEL_TREND_MIN_RUNS
            else "trend not drawable (insufficient defined points)"
        )
    else:
        supp = None
    return _OverviewCard(
        headline_stat_text=headline,
        headline_caption="A+ ident. (latest run)",
        headline_suppressed_text=headline_supp,
        sparkline_points=points,
        sparkline_suppressed_text=supp,
        sparkline_kind="inline_svg",
    )


def _extract_process_grade_trend(cfg: Config, conn, session_date: str) -> _OverviewCard:
    result = compute_process_grade_trend(conn)
    series = result.rolling_series[_PROCESS_GRADE_HEADLINE_METRIC]
    if series.suppressed is not None:
        headline = None
        headline_supp = series.suppressed.placeholder_text
    else:
        rv = series.rendered_value  # BootstrapCI for the class-"B" headline metric
        point = getattr(rv, "point", rv)
        headline = None if point is None else f"{float(point):.2f}"
        headline_supp = None if headline is not None else "unavailable"
    points: str | None = None
    drawable = (
        series.suppressed is None
        and series.drawability_text == "rolling line drawable"
    )
    if drawable:
        points = build_sparkline_points([p.value for p in series.line_points])
    supp = None if points is not None else "rolling grade line not yet drawable"
    return _OverviewCard(
        headline_stat_text=headline,
        headline_caption="rolling grade",
        headline_suppressed_text=headline_supp,
        sparkline_points=points,
        sparkline_suppressed_text=supp,
        sparkline_kind="inline_svg",
    )
```

- [ ] **Step 4: Run; verify pass.** `ruff check` clean.

- [ ] **Step 5: Commit**

```bash
git add swing/web/view_models/metrics/index.py tests/web/view_models/metrics/test_index_overview.py
git commit -m "feat(web): trend-surface overview extractors with per-surface sparkline thresholds

Capital uses its own 5-run floor, funnel its 10-run floor, process-grade its
line-band drawable gate; each reuses the existing per-surface output
read-only and falls back to an honest suppressed caption rather than a
fabricated line."
```

#### §G.T-5.2.c — the 6 headline-only extractors

- [ ] **Step 1: Write the failing tests** (append) — assert headline text/caption per surface, the honest suppressed path, and `sparkline_kind == "none"` (no slot).

```python
from swing.web.view_models.metrics.index import (
    _extract_trade_process, _extract_hypothesis_progress, _extract_tier_comparison,
    _extract_maturity_stage, _extract_deviation_outcome, _extract_pattern_outcomes,
    DEVIATION_HEADLINE_COHORT, PATTERN_HEADLINE_CLASS,
)


def test_hypothesis_progress_headline_counts_registered_cohorts(high_data_cfg_conn):
    cfg, conn = high_data_cfg_conn
    card = _extract_hypothesis_progress(cfg, conn, "2026-05-30")
    assert card.sparkline_kind == "none"
    assert card.headline_caption == "registered cohorts"
    assert card.headline_stat_text == "4"  # 4 TAXONOMY_COHORTS registered


def test_maturity_headline_is_open_position_count(high_data_cfg_conn):
    cfg, conn = high_data_cfg_conn
    card = _extract_maturity_stage(cfg, conn, "2026-05-30")
    assert card.headline_caption == "open positions"
    assert card.headline_stat_text is not None  # "0" is a valid honest value


def test_pattern_outcomes_uses_fixed_class_and_existing_suppression(low_data_cfg_conn):
    cfg, conn = low_data_cfg_conn
    card = _extract_pattern_outcomes(cfg, conn, "2026-05-30")
    assert card.sparkline_kind == "none"
    assert f"({PATTERN_HEADLINE_CLASS})" in card.headline_caption
    assert (card.headline_stat_text is not None) or (card.headline_suppressed_text is not None)


def test_deviation_headline_uses_fixed_cohort(high_data_cfg_conn):
    cfg, conn = high_data_cfg_conn
    card = _extract_deviation_outcome(cfg, conn, "2026-05-30")
    assert "delta vs A+" in card.headline_caption
    assert DEVIATION_HEADLINE_COHORT
```

- [ ] **Step 2: Run; verify fail.**

- [ ] **Step 3: Implement the 6 extractors + the 2 OQ-4 constants** (in `index.py`)

```python
from swing.metrics.tier import APLUS_COHORT
from swing.web.view_models.metrics.deviation_outcome import build_deviation_outcome_vm
from swing.web.view_models.metrics.hypothesis_progress_card import (
    build_hypothesis_progress_card_vm,
)
from swing.web.view_models.metrics.maturity_stage import build_maturity_stage_vm
from swing.web.view_models.metrics.tier_comparison import build_tier_comparison_vm
from swing.web.view_models.metrics.trade_process_card import (
    ALL_COHORTS_KEY,
    build_trade_process_card_vm,
)
from swing.web.view_models.patterns.outcomes_card import build_pattern_outcomes_vm

# OQ-4 fixed selectors (operator-confirmable at executing-plans; §C.4).
DEVIATION_HEADLINE_COHORT: str = "Near-A+ defensible: extension test"
_DEVIATION_HEADLINE_SHORT: str = "Near-A+"
PATTERN_HEADLINE_CLASS: str = "vcp"


def _extract_trade_process(cfg: Config, conn, session_date: str) -> _OverviewCard:
    vm = build_trade_process_card_vm(cfg=cfg, conn=conn)
    tab = next((t for t in vm.cohort_tabs if t.cohort_key == ALL_COHORTS_KEY), None)
    if tab is None:
        return _OverviewCard(headline_suppressed_text="unavailable")
    stat, supp = _format_metric_value(tab.metrics.expectancy_R.value)
    return _OverviewCard(
        headline_stat_text=stat,
        headline_caption="expectancy R (all)",
        headline_suppressed_text=supp,
    )


def _extract_hypothesis_progress(cfg: Config, conn, session_date: str) -> _OverviewCard:
    vm = build_hypothesis_progress_card_vm(cfg=cfg, conn=conn)
    n = len(vm.cohorts)
    if n == 0:
        return _OverviewCard(headline_suppressed_text="no registered cohorts")
    return _OverviewCard(headline_stat_text=str(n), headline_caption="registered cohorts")


def _extract_tier_comparison(cfg: Config, conn, session_date: str) -> _OverviewCard:
    vm = build_tier_comparison_vm(cfg=cfg, conn=conn)
    if vm.result is None:
        return _OverviewCard(headline_suppressed_text="unavailable")
    cohort = next((c for c in vm.result.cohorts if c.cohort_name == APLUS_COHORT), None)
    if cohort is None:
        return _OverviewCard(headline_suppressed_text="A+ cohort unavailable")
    stat, supp = _format_metric_value(cohort.expectancy)
    return _OverviewCard(
        headline_stat_text=stat,
        headline_caption="A+ expectancy R",
        headline_suppressed_text=supp,
    )


def _extract_maturity_stage(cfg: Config, conn, session_date: str) -> _OverviewCard:
    vm = build_maturity_stage_vm(cfg=cfg, conn=conn)
    if vm.result is None:
        return _OverviewCard(headline_suppressed_text="unavailable")
    return _OverviewCard(
        headline_stat_text=str(len(vm.result.rows)),
        headline_caption="open positions",
    )


def _extract_deviation_outcome(cfg: Config, conn, session_date: str) -> _OverviewCard:
    vm = build_deviation_outcome_vm(cfg=cfg, conn=conn)
    caption = f"delta vs A+ ({_DEVIATION_HEADLINE_SHORT})"
    if vm.result is None:
        return _OverviewCard(headline_suppressed_text="unavailable", headline_caption=caption)
    row = next(
        (r for r in vm.result.rows if r.cohort_name == DEVIATION_HEADLINE_COHORT), None
    )
    if row is None:
        return _OverviewCard(headline_suppressed_text="cohort unavailable", headline_caption=caption)
    if row.row_suppressed or row.expectancy_relative_to_aplus_pct is None:
        return _OverviewCard(headline_suppressed_text="n too low", headline_caption=caption)
    return _OverviewCard(
        headline_stat_text=f"{row.expectancy_relative_to_aplus_pct:+.1f}%",
        headline_caption=caption,
    )


def _extract_pattern_outcomes(cfg: Config, conn, session_date: str) -> _OverviewCard:
    vm = build_pattern_outcomes_vm(conn, session_date=session_date)
    caption = f"trigger rate ({PATTERN_HEADLINE_CLASS})"
    row = next(
        (r for r in vm.pattern_outcome_rows if r.pattern_class == PATTERN_HEADLINE_CLASS),
        None,
    )
    if row is None:
        return _OverviewCard(headline_suppressed_text="pattern unavailable", headline_caption=caption)
    if row.triggered_ci is not None:
        return _OverviewCard(headline_stat_text=row.triggered_pct_text, headline_caption=caption)
    return _OverviewCard(headline_suppressed_text=row.suppressed_text, headline_caption=caption)
```

> **Note (#16/#32 ASCII):** `"delta vs A+"`, `"A+"`, `"expectancy R"` are all ASCII. Do NOT use `Δ`, `≥`, em-dash, or any glyph in these strings.

- [ ] **Step 4: Run; verify pass.** `ruff check` clean.

- [ ] **Step 5: Commit**

```bash
git add swing/web/view_models/metrics/index.py tests/web/view_models/metrics/test_index_overview.py
git commit -m "feat(web): headline-only overview extractors for the six point-estimate surfaces

Each reads one fixed row or count from the existing per-surface output and
reuses that surface's own suppression text; no sparkline slot for the six
non-trend surfaces per the honesty floor."
```

#### §G.T-5.2.d — widen the builder + dispatch + isolation + ROUTE + call-sites (ALL ATOMIC)

> **Codex R1 MAJOR #2 fix:** the route call-site MUST be widened in the SAME commit as the builder signature — otherwise `GET /metrics` 500s while T-5.2's route tests run. The route update (formerly T-5.3 Step 3a) moves HERE. T-5.3 becomes template + CSS only.

- [ ] **Step 1: Write the failing tests** (append)

```python
from swing.web.view_models.metrics.index import build_metrics_index_vm, _SURFACES


def test_builder_widened_signature_populates_nine_cards(high_data_cfg_conn):
    cfg, conn = high_data_cfg_conn
    vm = build_metrics_index_vm(cfg, conn)
    assert len(vm.surfaces) == len(_SURFACES) == 9
    assert vm.session_date
    assert hasattr(vm, "unresolved_material_discrepancies_count")
    trend = [s for s in vm.surfaces if s.sparkline_kind == "inline_svg"]
    assert {s.path for s in trend} == {
        "/metrics/capital-friction",
        "/metrics/identification-funnel",
        "/metrics/process-grade-trend",
    }


def test_one_surface_failure_degrades_only_that_card(high_data_cfg_conn, monkeypatch):
    cfg, conn = high_data_cfg_conn

    def _boom(*a, **k):
        raise RuntimeError("synthetic compute failure")

    monkeypatch.setattr(
        "swing.web.view_models.metrics.index.build_capital_friction_vm", _boom
    )
    vm = build_metrics_index_vm(cfg, conn)
    assert len(vm.surfaces) == 9  # grid still renders all 9
    cap = next(s for s in vm.surfaces if s.path == "/metrics/capital-friction")
    assert cap.headline_suppressed_text == "unavailable"
```

- [ ] **Step 2: Run; verify fail** — `build_metrics_index_vm` still `(conn)`-only.

- [ ] **Step 3: Widen the builder + add the dispatch + isolation** (replace the existing `build_metrics_index_vm`)

```python
_EXTRACTORS = {
    "/metrics/trade-process": _extract_trade_process,
    "/metrics/hypothesis-progress": _extract_hypothesis_progress,
    "/metrics/tier-comparison": _extract_tier_comparison,
    "/metrics/capital-friction": _extract_capital_friction,
    "/metrics/maturity-stage": _extract_maturity_stage,
    "/metrics/identification-funnel": _extract_identification_funnel,
    "/metrics/deviation-outcome": _extract_deviation_outcome,
    "/metrics/process-grade-trend": _extract_process_grade_trend,
    "/metrics/pattern-outcomes": _extract_pattern_outcomes,
}

_OVERVIEW_FIELD_NAMES = (
    "headline_stat_text", "headline_caption", "headline_suppressed_text",
    "sparkline_points", "sparkline_suppressed_text", "sparkline_kind",
)


_TEXT_FIELDS = (
    "headline_stat_text", "headline_caption",
    "headline_suppressed_text", "sparkline_suppressed_text",
)


def _enrich_surface(base, cfg: Config, conn, session_date: str) -> MetricsIndexSurface:
    extractor = _EXTRACTORS.get(base.path)
    if extractor is None:  # defensive — every registry path has an extractor
        return base
    try:
        card = extractor(cfg, conn, session_date)
    except Exception:  # noqa: BLE001 - per-card isolation: one fail != whole-page 500
        _LOG.warning(
            "metrics overview extractor failed for %s", base.path, exc_info=True
        )
        card = _OverviewCard(headline_suppressed_text="unavailable")
    values = {name: getattr(card, name) for name in _OVERVIEW_FIELD_NAMES}
    # CENTRAL ASCII chokepoint (Codex R1 CRITICAL #1): every reused text field
    # is coerced to ASCII here, so no extractor can leak honesty.py's U+2265.
    for name in _TEXT_FIELDS:
        values[name] = _ascii(values[name])
    return replace(base, **values)


def build_metrics_index_vm(cfg: Config, conn: sqlite3.Connection) -> MetricsIndexVM:
    """Build the enhanced overview VM. ``session_date`` stays forward-looking
    ``action_session_for_run(now)`` (the navigator topbar date, as before).
    Each surface card is enriched read-only from the existing per-surface
    output; a single surface's failure degrades only that card."""
    session_date = action_session_for_run(datetime.now()).isoformat()
    enriched = tuple(
        _enrich_surface(base, cfg, conn, session_date) for base in _SURFACES
    )
    return MetricsIndexVM(
        session_date=session_date,
        unresolved_material_discrepancies_count=count_unresolved_material(conn),
        recent_multi_leg_auto_correction_count=(
            count_recent_multi_leg_auto_corrections(conn)
        ),
        banner_resolve_link=fetch_first_pending_ambiguity_resolve_link_path(conn),
        surfaces=enriched,
    )
```

- [ ] **Step 4: Update the production route in the SAME commit** (`swing/web/routes/metrics.py`, `metrics_index`) — Codex R1 MAJOR #2:

```python
@router.get("/metrics", response_class=HTMLResponse)
def metrics_index(request: Request):
    """9-card overview navigator for Phase 10 metrics surfaces (P14.N5)."""
    cfg = request.app.state.cfg
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        vm = build_metrics_index_vm(cfg, conn)
    finally:
        conn.close()
    return request.app.state.templates.TemplateResponse(
        request, "metrics/index.html.j2", {"vm": vm},
    )
```

- [ ] **Step 5: Update the 3 existing call-site tests** — NOT all are mechanical (Codex R1 MAJOR #3). Read context at each first:
  - `tests/web/test_routes/test_metrics_routes.py:~78` — has `cfg, _ = seeded_db` in scope -> mechanical: `build_metrics_index_vm(cfg, conn)`.
  - `tests/web/test_routes/test_metrics_pattern_outcomes.py:~235` — has `cfg, _ = seeded_db` in scope -> mechanical: `build_metrics_index_vm(cfg, conn)`.
  - `tests/web/test_base_layout_vm_recent_multi_leg_field.py:452-462` — **has ONLY `tmp_path`, NO `cfg`** (`test_metrics_index_vm_populates_recent_multi_leg_field`). Construct a Config pointing at the temp DB BEFORE the call:

```python
def test_metrics_index_vm_populates_recent_multi_leg_field(tmp_path):
    import dataclasses
    from swing.config import load as load_cfg
    from swing.web.view_models.metrics.index import build_metrics_index_vm
    db = tmp_path / "swing.db"
    _create_empty_db(db)
    base_cfg = load_cfg(Path(__file__).resolve().parents[2] / "swing.config.toml")
    cfg = dataclasses.replace(
        base_cfg, paths=dataclasses.replace(base_cfg.paths, db_path=db)
    )
    conn = _open_conn(db)
    try:
        _seed_multi_leg_auto_correction(conn)
        vm = build_metrics_index_vm(cfg, conn)
    finally:
        conn.close()
    assert vm.recent_multi_leg_auto_correction_count == 1
```
  (Confirm the `Config`/`paths` field names by reading the dataclass before editing; mirror the neighbouring `test_journal_vm_populates_recent_multi_leg_field` at :465, which already loads a cfg from the repo toml. If `dataclasses.replace` on `paths` is awkward, mirror that neighbour's monkeypatch approach instead.)

- [ ] **Step 6: Run; verify pass** — `python -m pytest tests/web/view_models/metrics/test_index_overview.py tests/web/test_base_layout_vm_recent_multi_leg_field.py tests/web/test_routes/test_metrics_routes.py tests/web/test_routes/test_metrics_pattern_outcomes.py -q`. Cascade-audit: `git grep -n "build_metrics_index_vm(" -- swing tests` shows only the route + these 3 tests. `ruff check swing/` clean.

- [ ] **Step 7: Commit**

```bash
git add swing/web/view_models/metrics/index.py swing/web/routes/metrics.py tests/
git commit -m "feat(web): widen build_metrics_index_vm to (cfg, conn), update the route, and enrich nine cards

Dispatches each registry surface to its read-only extractor on the shared
connection with per-card try/except isolation and a central ASCII chokepoint;
updates the route call-site and the three existing test call-sites in the
same change so GET /metrics never runs against the old signature."
```

---

### Task T-5.3: template + CSS (route already widened in T-5.2.d)

**Files:**
- Modify: `swing/web/templates/metrics/index.html.j2`
- Modify: `swing/web/static/app.css`
- Test: `tests/web/test_routes/test_metrics_index_overview.py`

**Acceptance criteria:** the template renders 9 cards (label + headline-or-suppressed + drill-down link); the 3 trend cards emit an inline `<svg><polyline points="..."/></svg>` when points present else the sparkline-suppressed caption; the 6 non-trend cards render NO `<polyline>`; drill-down hrefs unchanged; rendered body ASCII-only (incl. reused suppression text — Codex R1 CRITICAL #1); pure server-render (no HTMX — L8). The route was already widened in T-5.2.d.

> **Codex R1 MAJOR #4 fix — deterministic render tests via a monkeypatched builder.** The route/template test asserts TEMPLATE behaviour, so it builds a known `MetricsIndexVM` directly and monkeypatches `swing.web.routes.metrics.build_metrics_index_vm` to return it — NO heavy/fragile multi-surface DB seeding (that is covered against real seeded DBs in the T-5.2 VM tests). This makes the "exactly 3 polylines / 0 polylines / body.isascii()" assertions deterministic. `seeded_app`/`low_seeded_app` are NOT used (they do not exist globally).

- [ ] **Step 1: Write the failing route/render tests**

```python
# tests/web/test_routes/test_metrics_index_overview.py
"""T-5.3 — /metrics overview template render (P14.N5)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from swing.web.app import create_app
from swing.web.view_models.metrics.index import (
    MetricsIndexSurface,
    MetricsIndexVM,
    _SURFACES,
)
# `seeded_db` is the existing global fixture (tests/web/conftest.py) yielding
# (cfg, cfg_path) for an empty schema-only DB — enough to build the app.


def _vm_from(trend_points: str | None, suppressed: str | None) -> MetricsIndexVM:
    """Hand-build a 9-card VM: the 3 trend surfaces carry inline_svg, the rest
    are headline-only. ``trend_points`` None + ``suppressed`` set => suppressed."""
    trend_paths = {
        "/metrics/capital-friction",
        "/metrics/identification-funnel",
        "/metrics/process-grade-trend",
    }
    surfaces = tuple(
        MetricsIndexSurface(
            path=s.path, label=s.label, description=s.description,
            headline_stat_text="1.23", headline_caption="x",
            sparkline_points=(trend_points if s.path in trend_paths else None),
            sparkline_suppressed_text=(suppressed if s.path in trend_paths else None),
            sparkline_kind=("inline_svg" if s.path in trend_paths else "none"),
        )
        for s in _SURFACES
    )
    return MetricsIndexVM(session_date="2026-05-30", surfaces=surfaces)


def test_overview_renders_nine_cards_with_three_polylines(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    monkeypatch.setattr(
        "swing.web.routes.metrics.build_metrics_index_vm",
        lambda cfg, conn: _vm_from("2.00,28.00 98.00,2.00", None),
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    for s in _SURFACES:
        assert f'href="{s.path}"' in body
    assert body.count("<polyline") == 3  # exactly the 3 trend surfaces
    assert body.isascii()


def test_overview_below_threshold_shows_suppressed_caption_no_polyline(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    monkeypatch.setattr(
        "swing.web.routes.metrics.build_metrics_index_vm",
        lambda cfg, conn: _vm_from(None, "trend needs >=5 runs (have 3)"),
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert "<polyline" not in body
    assert "needs >=5 runs" in body
    assert body.isascii()
```

> Confirm `seeded_db`'s yield shape (`(cfg, cfg_path)`) and `create_app(cfg, cfg_path)` by mirroring `tests/web/test_routes/test_metrics_routes.py:13-18`. If `MetricsIndexVM` requires more BaseLayoutVM kwargs than `session_date`, supply their safe defaults (they already default — shared.py:42-64).

- [ ] **Step 2: Run; verify fail** — `tests/web/test_routes/test_metrics_index_overview.py` -> FAIL: the template still emits the old `<ul class="metrics-tiles">` (no `<polyline>`, count 0 != 3).

- [ ] **Step 3b: Rewrite the template** (`swing/web/templates/metrics/index.html.j2`)

```jinja
{% extends "base.html.j2" %}
{% block content %}
<section class="metrics-index">
  <h1>Metrics dashboard</h1>
  <p class="muted">
    Per-surface overview. Each card links through to its full drill-down.
  </p>
  <ul class="metrics-overview-grid">
    {% for surface in vm.surfaces %}
    <li class="metrics-card">
      <a class="metrics-card__link" href="{{ surface.path }}">
        <h3 class="metrics-card__label">{{ surface.label }}</h3>
        {% if surface.headline_stat_text %}
        <p class="metrics-card__headline">
          <span class="metrics-card__stat">{{ surface.headline_stat_text }}</span>
          {% if surface.headline_caption %}
          <span class="metrics-card__caption">{{ surface.headline_caption }}</span>
          {% endif %}
        </p>
        {% else %}
        <p class="metrics-card__suppressed">
          <em>{{ surface.headline_suppressed_text or "unavailable" }}</em>
          {% if surface.headline_caption %}
          <span class="metrics-card__caption">{{ surface.headline_caption }}</span>
          {% endif %}
        </p>
        {% endif %}
        {% if surface.sparkline_kind == "inline_svg" %}
          {% if surface.sparkline_points %}
          <svg class="metrics-card__sparkline" viewBox="0 0 100 30"
               width="100" height="30" preserveAspectRatio="none"
               role="img" aria-label="{{ surface.label }} trend">
            <polyline points="{{ surface.sparkline_points }}"
                      fill="none" stroke="currentColor" stroke-width="1.5"/>
          </svg>
          {% else %}
          <small class="metrics-card__spark-suppressed">
            {{ surface.sparkline_suppressed_text or "trend not available" }}
          </small>
          {% endif %}
        {% endif %}
        <p class="metrics-card__desc">{{ surface.description }}</p>
      </a>
    </li>
    {% endfor %}
  </ul>
</section>
{% endblock %}
```

- [ ] **Step 3c: Add CSS** (append to `swing/web/static/app.css`)

```css
/* P14.N5 metrics overview card grid + sparkline glyph */
.metrics-overview-grid {
  list-style: none; margin: 0; padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.75rem;
}
.metrics-card { border: 1px solid #d0d4da; border-radius: 6px; background: #fff; }
.metrics-card__link {
  display: block; padding: 0.75rem 0.9rem; text-decoration: none; color: inherit;
}
.metrics-card__link:hover { background: #f5f7fa; }
.metrics-card__label { margin: 0 0 0.35rem; font-size: 0.95rem; }
.metrics-card__headline { margin: 0.2rem 0; }
.metrics-card__stat { font-size: 1.5rem; font-weight: 600; }
.metrics-card__caption { color: #5a6472; font-size: 0.8rem; margin-left: 0.35rem; }
.metrics-card__suppressed { margin: 0.2rem 0; color: #6a7280; }
.metrics-card__sparkline { display: block; margin: 0.35rem 0; color: #2b6cb0; }
.metrics-card__spark-suppressed { color: #8a929e; font-style: italic; }
.metrics-card__desc { margin: 0.35rem 0 0; color: #6a7280; font-size: 0.8rem; }
```

- [ ] **Step 4: Run; verify pass.** `ruff check swing/` clean. No non-ASCII bytes: `git grep -nP "[^\x00-\x7F]" -- swing/web/templates/metrics/index.html.j2 swing/web/static/app.css` returns nothing.

- [ ] **Step 5: Commit**

```bash
git add swing/web/templates/metrics/index.html.j2 swing/web/static/app.css tests/web/test_routes/test_metrics_index_overview.py
git commit -m "feat(web): render the metrics overview card grid with inline sparklines

The template emits a nine-card grid with headline stats, inline polyline
sparklines on the three trend surfaces, honest suppressed captions, and the
preserved drill-down links; pure server-render with no HTMX. The route was
already widened with the builder in the prior task."
```

---

### Task T-5.4: closer — full suite + gates + operator render gate + close-out note

**Files:** none (verification + the §I runbook + return report). No production code.

**Acceptance criteria:** full fast suite + ruff green on the branch; `EXPECTED_SCHEMA_VERSION == 23` (NO migration); L2 Schwab source-grep continues passing; ASCII-only; `%(trailers)` empty; operator-witnessed browser render gate (§I) PASS; the §O close-out readiness note drafted.

- [ ] **Step 1: Full fast suite** — `python -m pytest -m "not slow" -q`. Expected green (prior baseline ~6905 + the new tests). READ the actual result; do NOT carry a branch/older count forward (memory `feedback_no_false_green_claim`).
- [ ] **Step 2: ruff** — `ruff check swing/` -> clean (0 E501).
- [ ] **Step 3: Schema gate** — `git grep -n "EXPECTED_SCHEMA_VERSION" swing/data/db.py` shows `= 23`; `git status` shows NO new `swing/data/migrations/00XX_*.sql`.
- [ ] **Step 4: L2 Schwab source-grep** — run the project's L2 grep gate; confirm zero NEW Schwab API call-sites on this branch.
- [ ] **Step 5: ASCII gate** — `git grep -nP "[^\x00-\x7F]" -- swing/web/view_models/metrics/sparkline.py swing/web/view_models/metrics/index.py swing/web/templates/metrics/index.html.j2 swing/web/static/app.css` returns nothing.
- [ ] **Step 6: Trailer gate** — `git log -1 --format='%(trailers)'` == `[]`; spot-check the last commits have no `Co-Authored-By` and a plain-prose final paragraph.
- [ ] **Step 7: Operator render gate** — run the §I runbook; operator confirms in a real browser.
- [ ] **Step 8: Draft the §O close-out note** + return report (run §N self-review first).

---

## §H Test surface (sum-check)

| Task | New test file | Tests (count) | Discriminating assertions |
|------|---------------|---------------|---------------------------|
| T-5.1 | `test_sparkline.py` | 9 | 2-vertex span; empty/all-None/single-defined -> None; flat -> mid-line; **None-gap does NOT compress X** (the Codex R1 geometry fix); 2-dp; dimension-guard raise; ASCII. |
| T-5.2.a | `test_index_overview.py` (+) | 2 | 6 overview fields present with safe defaults (leaf-VM; no BaseLayoutVM change); **`_ascii()` coerces the U+2265 glyph** (Codex R1 CRITICAL #1). |
| T-5.2.b | `test_index_overview.py` (+) | 4 | capital sparkline present >=5 / suppressed <5; **funnel 10-run floor vs capital 5-run floor on the SAME 7-run DB** (the NON-uniform-threshold discriminator); process-grade line-band gate (drawn XOR suppressed). |
| T-5.2.c | `test_index_overview.py` (+) | 4 | hypothesis count == 4; maturity open-count present; pattern fixed-class + existing suppression; deviation fixed-cohort caption. |
| T-5.2.d | `test_index_overview.py` (+) | 2 | widened `(cfg, conn)` -> 9 cards + exactly the 3 trend paths inline_svg; **one-surface failure degrades only that card (grid still 9)**. |
| T-5.3 | `test_metrics_index_overview.py` | 2 | **monkeypatched builder** (deterministic, no DB seed); route 200; 9 drill-down hrefs preserved; **exactly 3 `<polyline>`**; `body.isascii()`; below-threshold -> 0 polylines + honest `"needs >=5 runs"` caption + `body.isascii()`. |
| — | updated call-sites | 3 (edits) | route + `test_metrics_routes.py` + `test_metrics_pattern_outcomes.py` mechanical; `test_base_layout_vm_recent_multi_leg_field.py` needs a constructed Config (Codex R1 MAJOR #3). |

**Total new tests: ~23** across 3 new files (+1 route edit, +3 call-site edits). Net suite delta ~ +23.

**Insufficiency caveat (L5):** these string/`data-*` assertions confirm the points string is EMITTED and the polyline COUNT is right; they do NOT confirm the rendered glyph reads correctly. The operator-witnessed browser render (§I) is the BINDING gate.

---

## §I Operator-witnessed render gate (the BINDING gate — Q6 / L5)

The rendered overview in a real browser is the binding gate. Re-confirm the orchestrator/operator split at executing-plans (memory `feedback_visual_gate_both_render_and_browser`); the prior sub-bundles' split applies (operator drives the browser; orchestrator runs DB-side probes — OR the orchestrator renders the page and reads it back).

**S1 — suite + lint (orchestrator/DB-side):** `python -m pytest -m "not slow" -q` green; `ruff check swing/` clean. READ the actual numbers (no false-green).

**S2 — schema unchanged (orchestrator/DB-side):** `EXPECTED_SCHEMA_VERSION == 23`; no new migration file; operator DB still v23 (no migration runs on `swing web` start beyond the existing no-op).

**S3 — browser (operator-driven; BINDING):** `swing web`; open `http://127.0.0.1:8080/metrics`:
1. **9 cards** render in the registry order.
2. The **3 trend cards** (Capital-friction, Identification-funnel, Process-grade-trend) show an inline sparkline glyph when data is sufficient; below threshold they show the honest suppressed caption (e.g. *"trend needs >=5 runs (have N)"*), NEVER a flat/fabricated line.
3. The **6 non-trend cards** show a headline stat (or honest suppressed text) and NO sparkline slot.
4. **Every drill-down link** resolves to its existing per-surface route (click through each; each returns its existing page).
5. Headline figures match what the drill-down shows (no invented numbers).
6. No mojibake / no `UnicodeEncodeError` in the `swing web` console (ASCII-only strings).

**S4 — L2 Schwab source-grep (orchestrator):** no new Schwab call-sites.
**S5 — ASCII (orchestrator):** the §G T-5.4 Step-5 grep returns nothing AND the T-5.3 rendered-`body.isascii()` tests pass (covers reused suppression text coerced by `_ascii()`, which a source grep would miss).
**S6 — trailers (orchestrator):** `git log -1 --format='%(trailers)'` == `[]`.

**Teardown (memory `feedback_taskstop_does_not_kill_detached_server`):** after S3, find the `swing web` PID via `Get-NetTCPConnection -LocalPort 8080`, `Stop-Process -Force`, and VERIFY the port is free + no straggler `python ... swing ... web` processes before claiming the gate is torn down.

Merge is BLOCKED until the operator confirms S3.

---

## §J Codex single-chain placement (OQ-7)

- **ONE** adversarial Codex chain, run AFTER the plan is written + internally chunk-reviewed, BEFORE executing-plans dispatch. **Run to CONVERGENCE** (zero new crit/major; the ~5-round cap is suspended — memory `feedback_codex_round_limit_suspended`; may exceed 5 rounds; do NOT pad after convergence).
- Transport: copowers v2.0.2 WSL Codex CLI fallback (reads the worktree from disk; MCP tools DEAD in the VS Code extension). `wsl.exe bash -ilc` (INTERACTIVE login for the node22 PATH). R1: `codex exec -s read-only --skip-git-repo-check -C <worktree> - < <promptfile>`. R2+: `codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check -` (NOTE: `resume` REJECTS `-s` AND `-C`/`--cd`; pre-generate the diff on Windows). Memory `feedback_wsl_native_codex_invocation` + `feedback_copowers_codex_mcp_windows_launcher`.
- **Codex watch items (this plan):** (1) the spec §6 accessors re-grepped against production (esp. the corrections this plan logged: `MetricCellB.value` wrapping, `vm.result` indirection, `build_hypothesis_progress_card_vm`/`build_trade_process_card_vm` names, pattern_outcomes' non-cfg `(conn, *, session_date)` signature); (2) NON-uniform thresholds (5/10/line-band) each from its own constant; (3) the process_grade single-`compute_*` path (not the pre-scaled VM points string); (4) L2 zero-write/zero-new-compute; (5) L3 no schema; (6) OQ-1 inline only (no matplotlib/`_RENDER_LOCK`); (7) L7 leaf-VM fields (BaseLayoutVM untouched); (8) honesty floor (3 sparklines, no fabrication); (9) per-card error isolation; (10) ASCII + trailer hygiene.

---

## §K Schema impact — VERDICT: NO change (v23 held)

- The recommended path (inline-`<polyline>`, render-direct) writes NOTHING and adds NO enum -> **schema stays v23**. No `chart_renders` rows, no migration, no v24.
- `EXPECTED_SCHEMA_VERSION` stays `23` (`swing/data/db.py:51`). Assert ZERO `swing/data/migrations/00XX_*.sql` added.
- The sparkline points string is computed per-request and embedded in the HTML; nothing persists. The render-direct/inline linkage is what keeps it schema-free (a cached sparkline would need a NEW non-`chart_renders` cache table — `chart_renders` is ticker/run-keyed — and is REMOVED from SB5 scope per spec §8).
- Were a v24 ever taken for an unrelated reason (NOT in SB5): STRICT backup-gate `pre_version == 23` (NOT `<=`); gotcha #11 (schema-CHECK + Python-constant + dataclass-validator + every `_row_to_*` mapper in ONE task) + #9 (explicit BEGIN/COMMIT migration runner). Out of scope here.

---

## §L Fixtures

- **Sparkline helper (T-5.1):** pure unit values — empty, all-None, 1 defined, 2 defined, flat, monotone, mixed None gaps. No DB.
- **VM (T-5.2):** three seeded fixture DBs, reusing the EXISTING per-surface seeders (do NOT hand-roll new schema fixtures — derive from the production emitter shape). Concrete seeder sources to copy/adapt:
  - capital/funnel trend (`pipeline_runs` + candidates/buckets): `tests/metrics/test_capital.py`, `tests/metrics/test_funnel.py`, `tests/web/test_view_models/test_capital_friction_vm.py`, `tests/web/test_view_models/test_identification_funnel_vm.py`, `tests/integration/test_phase10_bundle_d_e2e.py`.
  - process-grade reviewed-trade seeding: `tests/web/test_routes/test_metrics_process_grade_trend_route.py`.
  - The fixtures:
    - `high_data_cfg_conn` — >=10 `pipeline_runs` with candidates/buckets so capital + funnel `trend_runs` populate >=10; >=5 reviewed closed trades so process-grade `rolling_series` draws. Asserts sparklines present + headline values.
    - `low_data_cfg_conn` — 3 runs / <5 reviewed. Asserts each sparkline suppresses with the correct per-surface caption.
    - `borderline_7_runs_cfg_conn` — exactly 7 runs (the discriminator: capital draws at >=5, funnel suppresses at <10 on the SAME DB).
- **Route (T-5.3):** NO DB seeding — the route/template test monkeypatches `swing.web.routes.metrics.build_metrics_index_vm` to return a hand-built `MetricsIndexVM` (deterministic), then asserts via `with TestClient(app) as client:` 200, 9 cards, exactly 3 `<polyline>` (and 0 in the suppressed case), drill-down hrefs unchanged, `body.isascii()`. The real-data extraction is covered by the T-5.2 VM tests against the seeded DBs above (Codex R1 MAJOR #4).
- **Fixture-shape discipline:** the T-5.2 DBs must match the PRODUCTION insert shape exactly (gotcha: synthetic-fixture-vs-emitter drift). Construct rows via the existing per-surface seeders above, not hand-written SQL.

---

## §M Forward-binding lessons (for executing-plans)

1. **Re-grep accessors at IMPLEMENT time, not just plan time** — production may drift between plan and execute. The spec's §6 candidates contained name drift this plan corrected (`build_*_card_vm`, `MetricCellB.value`, `vm.result.*`, pattern_outcomes' non-cfg signature). The executing engineer re-confirms each `file:line` before writing the extractor.
2. **`vm.result` is `... | None`** on tier/capital/maturity/funnel/deviation VMs — ALWAYS guard `is None` before `.cohorts`/`.rows`/`.trend_runs`. Empty collections (`trend_runs[-1]`, `next(...)`) need their own guard.
3. **The process_grade VM points string is pre-scaled to 800x360** — it CANNOT be reused at 100x30. Use a single `compute_process_grade_trend(conn)` for both headline + raw `line_points` + the drawability gate (`series.drawability_text == "rolling line drawable"`). Do NOT call the VM for the sparkline.
4. **NON-uniform thresholds** — import each constant (`capital.TREND_MIN_RUNS=5`, `funnel.TREND_MIN_RUNS=10`) by name; never hardcode a single `n<5`. The 7-run discriminator test guards this.
5. **Per-card try/except** wraps each extractor; one failure degrades that card to `"unavailable"`, never 500s the page. The `except Exception` is intentional (`# noqa: BLE001`) and LOGS (not a silent swallow).
6. **Shared connection** — pass the route's `conn` to all 9 reused builders (surfaces 1-7 via `conn=conn`, 9 positionally, 8 via `compute_*(conn)`). One connection per request.
7. **ASCII-only** every user-facing string AND every REUSED metric string — `SuppressedMetric.placeholder_text` carries a real `≥` (honesty.py:42). A source-grep gate misses imported non-ASCII; coerce reused text via the central `_ascii()` chokepoint in `_enrich_surface` and assert `body.isascii()` on a rendered low-sample page. (Codex R1 CRITICAL.)
8. **Leaf-VM fields only** — never add a field to `BaseLayoutVM` (shared.py); the overview data lives on `MetricsIndexSurface`.

---

## §N Self-review (run against the spec before Codex)

**1. Spec coverage:** every spec section maps to a task — §1 (load-bearing finding) -> §C; §4 overview design -> T-5.2/T-5.3; §5 sparkline contract -> T-5.1 + T-5.2.b; §6 headline contract (all 9) -> T-5.2.c + the 3 trend headlines in T-5.2.b; §7 OQ-1 inline -> T-5.1; §8/§11 no schema -> §K; §9 decomposition -> 4 tasks; §10 fixtures/gate -> §L/§I; §13 OQs -> §E + §C.4; §14 disciplines -> §F; §15 close-out -> §O. No gap.
**2. Placeholder scan:** every code step shows complete code; no "TBD"/"handle edge cases"/"similar to". The 3 call-site edits show the exact replacement line.
**3. Type/name consistency:** `build_sparkline_points` signature identical across T-5.1/T-5.2/§C; `_OverviewCard` field names identical to `MetricsIndexSurface`'s 6 overview fields and to `_OVERVIEW_FIELD_NAMES`; `sparkline_kind` values `"none"`/`"inline_svg"` consistent VM<->template; `DEVIATION_HEADLINE_COHORT`/`PATTERN_HEADLINE_CLASS`/`_PROCESS_GRADE_HEADLINE_METRIC` referenced consistently.

---

## §O Phase 14 close-out readiness note (L9)

SB5 is the **FINAL** Phase 14 sub-bundle. On SB5 ship, all 5 sub-bundles are merged:
SB1 (data-wiring `e323339`) · SB2 (temporal log v22 `27f8007`) · SB3 (chart uniformity v23 `edd098d`) · SB4 (review+journal `31da4a5`) · SB5 (metrics overview, this plan).

**Close-out (Sec 9.1 Q6) — NOT in SB5 scope; sequenced after merge:**
1. Operator-witnessed **cross-sub-bundle integration review** — charts + review/journal + metrics overview rendering coherently together in one browser session.
2. Sequence the **banked Phase 14 follow-ups** (per `docs/phase3e-todo.md` punch-list): SB5.5 (Schwab A-3 daily-bar web wiring + P14.N7 checker-thread resilience); `market_weather` 200MA fetch-window (SB3 banked); theme2 vcp 5-contraction cosmetic crowding (SB3 banked); `_bulz_*` -> general row-expand rename (SB4 banked); the close-out polish batch + B-7.
3. CLAUDE.md status-line refresh to "Phase 14 CLOSED" once the close-out review passes.

**Schema verdict for close-out:** Phase 14 lands at **v23** (SB5 adds no schema). v23 = `hyprec_detail`->`ticker_detail` rename (SB3); L2 LOCK preserved.

**Executing-plans dispatch-readiness:** this plan is a single executing-plans bundle (T-5.1 -> T-5.4, serial), ~22 new tests, read-mostly, no schema, one Codex chain to convergence after the plan converges. The operator render gate (§I) is the merge-blocking BINDING gate.

---

*End of plan. Enhance `/metrics` in place: a pure inline-`<polyline>` sparkline helper, a widened `build_metrics_index_vm(cfg, conn)` that reuses the existing per-surface outputs read-only to emit a headline stat on all 9 cards + sparklines on the 3 trend-bearing surfaces (each gated by its OWN threshold 5/10/line-band), and a card-grid template — NO schema (v23 held), NO new computation, the rendered overview is the binding operator gate.*
