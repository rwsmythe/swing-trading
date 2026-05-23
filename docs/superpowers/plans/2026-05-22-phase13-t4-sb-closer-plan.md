# Phase 13 T4.SB Closer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close Phase 13 by addressing the operator-supplied 7-item usability triage list — diagnostic instruments for false-zero failure-mode family (Items 1, 7), JIT cache-miss chart architecture (Item 5), labeler subagent contract widening (Item 2), cosmetic/UX bundle (Items 3, 4, 6) — landing 6 sub-bundles T-T4.SB.1..T-T4.SB.6 and flipping the Phase 13 sub-bundle ship count from 11 of 11 to 12 of 12 / FULLY CLOSED.

**Architecture:** Investigation-first sequencing — Items 1 and 7 ship diagnostic CLI subcommands under `swing diagnose` AND a research-branch parameter-sweep sensitivity harness (§1.5.1 amendment placing T-T4.SB.1 Item 1 under `research/harness/aplus_sensitivity/`). Item 5 introduces a NEW `swing/web/chart_jit.py` module wired into route handlers and VM builders; `swing/web/chart_scope.py` LOCKED read-only. Item 7 broader audit canonicalizes hypothesis-label cohort matching at read-time via a shared SQL helper (3-rule delimiter-aware predicate) preserving operator's per-trade suffix. Item 2 additively extends the labeler subagent contract (`rule_criteria` array) AND adds a persistence-envelope `"narrative"` ALIAS key so the existing `_parse_narrative_text` parser lights up. Items 3+4+6 cosmetic/UX work bundled as one Codex round.

**Tech Stack:** Python 3.11+ (3.14 dev); FastAPI + HTMX; SQLite (schema v21 UNCHANGED); matplotlib + mplfinance; Click CLI; pytest with xdist; Codex MCP for adversarial review; copowers:writing-plans skill.

---

## §A Status + scope

### §A.1 Substrate and inputs

- **Brainstorming spec (BINDING):** `docs/superpowers/specs/2026-05-22-phase13-t4-sb-closer-design.md` at main HEAD `f7dec0e` — 1045 lines; 13 sections §A-§M; Codex R5 NO_NEW_CRITICAL_MAJOR; 17 MAJOR ALL RESOLVED in-place.
- **Dispatch brief (BINDING):** `docs/phase13-t4-sb-writing-plans-dispatch-brief.md` at `4690933` — encodes 18 OQ dispositions (ALL operator-locked) + 4 §1.5 amendments.
- **Operator triage substrate:** `docs/phase3e-todo.md:15-101` — 7 items with operator-confirmed severity + verbatim framings (Items 1-7).
- **Baseline:** main HEAD `637f156` (post handoff brief); ~5670 fast tests; schema v21 UNCHANGED; ruff 0 E501; ZERO Co-Authored-By footer drift (~378+ cumulative streak).

### §A.2 18-OQ dispositions (operator-locked verbatim per dispatch brief §1)

**Item 1 (4 OQs):**
- OQ-1.1: CLI subcommand emitting markdown + CSV sidecar to `exports/diagnostics/` (LOCKED concur).
- OQ-1.2: `--eval-runs N` parameter, default N=20, max N=100 (LOCKED concur).
- OQ-1.3: **REVISED §1.5.1** — 1D parameter-sweep sensitivity harness (NOT snapshot diagnostic).
- OQ-1.4: **REVISED §1.5.4** — research-branch placement (`research/harness/aplus_sensitivity/`).

**Item 2 (3 OQs):**
- OQ-2.1: LOCKED `rule_criteria` shape `{name, status, evidence_value, threshold, tolerance}`; `geometric_evidence_narrative` PRESERVED VERBATIM; envelope adds `"narrative"` ALIAS key.
- OQ-2.2: two-pronged ship + operator decides at execution time.
- OQ-2.3: KEEP Path C backfill script as fallback.

**Item 5 (5 OQs):**
- OQ-5.1: R4 (manual prune CLI) + R1 default unbounded; defer R2/R3 to V2.
- OQ-5.2: Synchronous-JIT-no-timeout V1 default; measured-timing diagnostic ships in T-T4.SB.3.
- OQ-5.3: Pre-gen scope LOCKED to "market_weather + position_detail + dashboard-top-5 watchlist ONLY".
- OQ-5.4: **Option A LOCKED §1.5.3** — dashboard reader binds to one pipeline_run anchor; JIT writes match anchor.
- OQ-5.5: KEEP chart-unavailable banner as fallback for genuine errors.

**Item 7 (3 OQs):**
- OQ-7.1: Diagnostic FIRST (T-T4.SB.1) + fix SECOND (T-T4.SB.2). Sequential.
- OQ-7.2: Broader audit enumerates `swing/metrics/` + `swing/web/view_models/metrics/` + `swing/journal/stats.py` + dashboard cards.
- OQ-7.3: Option 7C (READ-time delimiter-aware prefix-match; NO schema change; preserves per-trade suffix).

**Phase 13 closure (3 OQs):**
- OQ-CL.1: CLAUDE.md + orchestrator-context updates at T-T4.SB.6 closer announcing "Phase 13 FULLY CLOSED — 12 of 12 sub-bundles SHIPPED".
- OQ-CL.2: **REVISED §1.5.2** — Phase 14 trigger deferred until T-T4.SB.1 diagnostic ships; T-T4.SB.6 closer emits triage-agenda artifact stub at `docs/phase13-closer-next-phase-triage.md`.
- OQ-CL.3: Schedule research-branch first-method-record selection immediately post-T4.SB-SHIPPED.

**Cross-item (1 OQ):**
- OQ-X.1: Items 3+4+6 bundled in ONE Codex round (T-T4.SB.5).

### §A.3 Strict NON-scope

- **Phase 14 dispatch** — deferred per §1.5.2; T-T4.SB.6 closer ships triage-agenda artifact, NOT Phase 14 commissioning.
- **Research-branch first-method-record selection meeting** — OQ-CL.3 schedules this post-T4.SB-SHIPPED as separate operator-paired session.
- **Schema changes** — T4.SB SHOULD NOT touch schema per spec §A.2 LOCK. v21 LOCKED.
- **ZERO new Schwab API calls** (L2 LOCK preserved).
- **14 V1 simplifications + V2 candidates banked at brainstorming** (per return report §4.1).

### §A.4 File map

NEW production files:
- `swing/diagnostics/__init__.py` — package marker.
- `swing/diagnostics/metrics_wiring_audit.py` — Item 7 Phase 1 diagnostic (~120 LOC).
- `swing/web/chart_jit.py` — Item 5 JIT cache-miss helper (~100 LOC).
- (Conditional) `swing/diagnostics/prune_chart_cache.py` — Item 5 OQ-5.1 R4 manual prune.

NEW research-branch files (per §1.5.4):
- `research/harness/aplus_sensitivity/__init__.py` — package marker.
- `research/harness/aplus_sensitivity/README.md` — harness usage notes (mirror earnings_proximity precedent).
- `research/harness/aplus_sensitivity/variables.py` — variable enumeration helper (read `cfg.trend_template` + `cfg.vcp` + `cfg.risk` thresholds; emit list of `Variable(name, current_value, sweep_range, kind)`).
- `research/harness/aplus_sensitivity/sweep.py` — 1D sweep machinery (consume persisted `candidate_criteria`; substitute each variable's sweep points; recompute `bucket_for` semantics; aggregate counts).
- `research/harness/aplus_sensitivity/output.py` — sensitivity matrix CSV + markdown analysis formatters.
- `research/harness/aplus_sensitivity/run.py` — CLI entrypoint orchestrating sweep + output.
- `research/method-records/aplus-criteria-calibration.md` — V2.1 §IV.B minimum viable record (per `_template.md`).
- `research/studies/aplus-criterion-sensitivity-2026-05-22.md` — first study (mirror `earnings-proximity-exclusion.md` shape).

NEW test files:
- `tests/diagnostics/__init__.py` — package marker.
- `tests/diagnostics/test_metrics_wiring_audit.py` — Item 7 Phase 1 audit tests.
- `tests/web/test_chart_jit.py` — Item 5 JIT helper tests.
- `tests/web/routes/test_watchlist_jit_collapse.py` — Items 5+6 watchlist collapse JIT round-trip.
- `tests/web/templates/test_expanded_chart_suppress_banner.py` — Item 5 inline-SVG suppresses PNG/banner.
- `tests/metrics/test_phase13_t4_sb_cross_bundle_pin_row_13.py` — Item 7 invariant pin (parametrized 4 surfaces).
- `tests/metrics/test_hypothesis_label_match_helper.py` — Item 7 shared helper (Python + SQL).
- `tests/integration/test_phase13_t4_sb_closer_e2e.py` — T-T4.SB.6 fast E2E.
- `tests/research/test_aplus_sensitivity_variables.py` — variable enumeration.
- `tests/research/test_aplus_sensitivity_sweep.py` — sweep machinery.
- `tests/research/test_aplus_sensitivity_output.py` — output formatters.

MODIFY existing files:
- `swing/cli.py` — register `diagnose` subcommand group + 3 subcommands (`aplus-sensitivity`, `metrics-wiring`, optional `prune-chart-cache`).
- `swing/patterns/labeling.py` — extend `SilverLabelResponse` dataclass; envelope persistence (T-T4.SB.4).
- `.claude/agents/pattern-labeler.md` — subagent prompt extension (T-T4.SB.4).
- `swing/metrics/cohort.py` — rewrite `list_trades_for_cohort` + `count_per_cohort` for delimiter-aware match (T-T4.SB.2).
- `swing/recommendations/hypothesis.py` — rewrite `_label_matches_hypothesis` to 3-rule delimiter-aware; add `_label_matches_hypothesis_sql` companion (T-T4.SB.2).
- `swing/web/charts.py` — `render_market_weather_svg` + `render_hyprec_detail_svg` volume y-tick strip (T-T4.SB.5 Item 3).
- `swing/web/templates/partials/watchlist_row.html.j2` — remove lightning glyph + partial-rewire `chart_svg_bytes_for_row` param (T-T4.SB.5 Items 4+6).
- `swing/web/templates/watchlist.html.j2` — pass `chart_svg_bytes_for_row` to include (T-T4.SB.5 Item 6).
- `swing/web/templates/dashboard.html.j2` (or top-5 include site) — same (T-T4.SB.5 Item 6).
- `swing/web/templates/partials/hypothesis_recommendations_expanded.html.j2` — inline-SVG suppresses PNG/banner cascade (T-T4.SB.3).
- `swing/web/templates/partials/watchlist_expanded.html.j2` — symmetric cascade (T-T4.SB.3).
- `swing/web/routes/watchlist.py` — wire JIT into `watchlist_row` + `watchlist_expand` (T-T4.SB.3 + T-T4.SB.5 Item 6).
- `swing/web/view_models/dashboard.py` — `build_hyp_recs_expanded` falls back to JIT on cache miss (T-T4.SB.3).
- `swing/web/view_models/watchlist.py` — extend `WatchlistExpandedVM` with `watchlist_expanded_chart_svg_bytes`; populate via JIT (T-T4.SB.3).
- `swing/pipeline/runner.py:_step_charts` — reduce pre-gen scope (T-T4.SB.3).
- `research/phase-0-tasks.md` — move A+-like-indicators entry from "Later (deferred)" to "Next"; cite T-T4.SB.1 harness as first piece (T-T4.SB.1).
- `CLAUDE.md` — closer line update (T-T4.SB.6).
- `docs/orchestrator-context.md` — Phase 13 SHIPPED current-state refresh (T-T4.SB.6).
- `docs/cycle-checklist.md` — quarterly diagnostic re-run reminders (T-T4.SB.6).
- `docs/phase3e-todo.md` — Phase 13 closure entry (T-T4.SB.6).
- `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` — append row 13 to §H.3 cross-bundle pin table (T-T4.SB.6).

NEW docs artifact:
- `docs/phase13-closer-next-phase-triage.md` — post-T4.SB triage agenda stub per §1.5.2 (T-T4.SB.6).

### §A.5 Per-task scope summary (BINDING per spec §G)

| Task | Spec §G ref | Brief description | §1.5 amendments |
|---|---|---|---|
| T-T4.SB.1 | §G.1.1 | Item 1 sensitivity harness (research/) + Item 7 specific-defect diagnostics combined | §1.5.1 EXPANDS Item 1 to sensitivity harness + §1.5.4 PLACES under research/ |
| T-T4.SB.2 | §G.1.2 | Item 7 broader metrics audit + canonical wiring fix + cross-bundle pin row 13 (4 surfaces) | None |
| T-T4.SB.3 | §G.1.3 | Item 5 architecture (NEW `swing/web/chart_jit.py` + expanded-view inline-SVG + pre-gen scope reduction) | §1.5.3 LOCKS Option A for OQ-5.4 |
| T-T4.SB.4 | §G.1.4 | Item 2 additive `rule_criteria` + envelope alias `narrative` key | None |
| T-T4.SB.5 | §G.1.5 | Items 3+4+6 cosmetic/UX bundled (ONE Codex round per OQ-X.1) | None |
| T-T4.SB.6 | §G.1.6 | Closer + Phase 13 FULLY CLOSED marker + post-T4.SB triage agenda stub | §1.5.2 ADDS triage-agenda artifact requirement |

---

## §B Per-task design (bite-sized TDD steps)

Each task below lists: (i) files touched; (ii) bite-sized step list (2-5 min per step) following TDD discipline; (iii) discriminating tests; (iv) commit message templates. Per-task acceptance criteria are lifted to §G; cross-task dependencies to §C; investigation outputs format to §D.

### §B.1 T-T4.SB.1 — Item 1 sensitivity harness + Item 7 specific-defect diagnostic (combined investigation task)

**Files:**
- Create: `swing/diagnostics/__init__.py`
- Create: `swing/diagnostics/metrics_wiring_audit.py`
- Create: `research/harness/aplus_sensitivity/__init__.py`
- Create: `research/harness/aplus_sensitivity/README.md`
- Create: `research/harness/aplus_sensitivity/variables.py`
- Create: `research/harness/aplus_sensitivity/sweep.py`
- Create: `research/harness/aplus_sensitivity/output.py`
- Create: `research/harness/aplus_sensitivity/run.py`
- Create: `research/method-records/aplus-criteria-calibration.md`
- Create: `research/studies/aplus-criterion-sensitivity-2026-05-22.md`
- Modify: `swing/cli.py` — register `diagnose` subcommand group + `aplus-sensitivity` + `metrics-wiring` subcommands.
- Modify: `research/phase-0-tasks.md` — promote A+-like-indicators entry.
- Test: `tests/diagnostics/__init__.py`
- Test: `tests/diagnostics/test_metrics_wiring_audit.py`
- Test: `tests/research/test_aplus_sensitivity_variables.py`
- Test: `tests/research/test_aplus_sensitivity_sweep.py`
- Test: `tests/research/test_aplus_sensitivity_output.py`
- Test: `tests/cli/test_diagnose_subcommands.py` (or extend an existing CLI test module)

**Sub-task 1A — Sensitivity harness variable enumeration**

- [ ] **Step 1A.1: Write failing test `test_enumerate_sweep_variables_from_config`** at `tests/research/test_aplus_sensitivity_variables.py`:

```python
from research.harness.aplus_sensitivity.variables import (
    SweepVariable,
    enumerate_variables,
)
from swing.config import Config


def test_enumerate_sweep_variables_from_config():
    cfg = Config.from_defaults()
    variables = enumerate_variables(cfg)
    # Per spec §1.5.1 + R2 LOCK: 2 gate + 15 threshold = 17 variables.
    assert len(variables) == 17
    names = {v.name for v in variables}
    expected_names = {
        # 2 gate
        "trend_template.min_passes",
        "vcp.watch_max_fails",
        # 3 trend_template threshold (allowed_miss_names + min_passes excluded)
        "trend_template.rising_ma_period_days",
        "trend_template.high_52w_margin_pct",
        "trend_template.low_52w_min_pct",
        # 8 vcp threshold
        "vcp.prior_trend_min_pct",
        "vcp.adr_min_pct",
        "vcp.pullback_max_pct",
        "vcp.proximity_max_pct",
        "vcp.tightness_days_required",
        "vcp.tightness_range_factor",
        "vcp.orderliness_max_bar_ratio",
        "vcp.orderliness_max_range_cv",
        # 1 risk threshold
        "risk.max_risk_pct",
        # 3 rs threshold
        "rs.horizon_weeks",
        "rs.rs_rank_min_pass",
        "rs.fallback_extreme_pct",
    }
    assert names == expected_names, f"missing: {expected_names - names}; extra: {names - expected_names}"
    # Each variable carries valid kind + sweep anchor present.
    gate_count = 0
    for v in variables:
        assert isinstance(v, SweepVariable)
        assert v.kind in {"gate", "threshold_additive", "threshold_multiplicative"}
        if v.kind == "gate":
            gate_count += 1
        assert v.current_value is not None
        assert len(v.sweep_points) >= 3
        assert v.current_value in v.sweep_points
    assert gate_count == 2  # invariant from R2 LOCK
```

- [ ] **Step 1A.2: Run test to verify it fails**

Run: `python -m pytest tests/research/test_aplus_sensitivity_variables.py -v`
Expected: FAIL with `ModuleNotFoundError: research.harness.aplus_sensitivity.variables`.

- [ ] **Step 1A.3: Create package + module skeletons**

Write `research/harness/aplus_sensitivity/__init__.py`:

```python
"""A+-criteria parameter-sweep sensitivity harness.

See `research/studies/aplus-criterion-sensitivity-2026-05-22.md` for the
study and `research/method-records/aplus-criteria-calibration.md` for the
method record. README.md documents how to run the harness.

Per V2.1 §V research-branch posture: this harness lives under `research/`
because its output answers an applied-research question (which A+-like
indicators warrant calibration) rather than a production-operational one.
"""
```

Write `research/harness/aplus_sensitivity/variables.py`:

```python
"""Variable enumeration for the A+ criteria sensitivity sweep.

Surveys `swing.config.Config` for all per-criterion thresholds gated by
`bucket_for` (`swing/evaluation/scoring.py`) and emits one `SweepVariable`
per dial. Sweep ranges follow first-order heuristics keyed off the
variable's kind (multiplicative for ratios/percentages; additive for
counts; discrete for enum-like).
"""
from __future__ import annotations

from dataclasses import dataclass

from swing.config import Config


@dataclass(frozen=True)
class SweepVariable:
    name: str
    kind: str  # "gate" | "threshold_additive" | "threshold_multiplicative"
    current_value: float | int
    sweep_points: tuple[float | int, ...]

    _ALLOWED_KINDS = frozenset(
        {"gate", "threshold_additive", "threshold_multiplicative"}
    )

    def __post_init__(self) -> None:
        if self.kind not in self._ALLOWED_KINDS:
            raise ValueError(
                f"SweepVariable.kind must be one of {sorted(self._ALLOWED_KINDS)}, "
                f"got {self.kind!r}"
            )


_MULTIPLICATIVE_FACTORS = (0.5, 0.75, 1.0, 1.25, 1.5)


def _multiplicative_sweep(current: float) -> tuple[float, ...]:
    return tuple(round(current * f, 6) for f in _MULTIPLICATIVE_FACTORS)


def _additive_sweep(current: int, delta: int = 2) -> tuple[int, ...]:
    return tuple(sorted({max(0, current + d) for d in range(-delta, delta + 1)}))


def enumerate_variables(cfg: Config) -> tuple[SweepVariable, ...]:
    """Enumerate all 17 sweep variables against the cfg shape at
    `swing/config.py` (TrendTemplate, VCP, Risk, RS dataclasses).

    Includes 2 gate variables (`trend_template.min_passes`;
    `vcp.watch_max_fails`) + 15 threshold variables:
        - 3 trend_template numerics (rising_ma_period_days +
          high_52w_margin_pct + low_52w_min_pct)
        - 8 vcp numerics
        - 1 risk numeric
        - 3 rs numerics

    NOT enumerated (V1):
        - `trend_template.allowed_miss_names` (tuple-set; sweeping over
          set-membership is V2 because it's not a numeric/additive grid)
        - `rs.benchmark_ticker` (string identifier, not a threshold)

    For threshold variables under V1, sweep_points are ENUMERATED but
    `_bucket_for_substituted` returns persisted_bucket for them (parity-
    preserving). Output formatter MUST surface this distinction explicitly
    via the `kind` column + per-row notes.
    """
    variables: list[SweepVariable] = [
        # Two gate variables (V1 full bucket-level resimulation supported).
        SweepVariable(
            name="trend_template.min_passes",
            kind="gate",  # full bucket resimulation
            current_value=cfg.trend_template.min_passes,
            sweep_points=_additive_sweep(cfg.trend_template.min_passes),
        ),
        SweepVariable(
            name="vcp.watch_max_fails",
            kind="gate",
            current_value=2,  # bucket_for at swing/evaluation/scoring.py:35
            sweep_points=_additive_sweep(2, delta=2),
        ),
        # Trend-template numeric thresholds (3; not 4 — `min_passes` is a
        # gate variable above; `allowed_miss_names` is V2 set-sweep).
        SweepVariable(
            name="trend_template.rising_ma_period_days",
            kind="threshold_additive",
            current_value=cfg.trend_template.rising_ma_period_days,
            sweep_points=_additive_sweep(
                cfg.trend_template.rising_ma_period_days, delta=10,
            ),
        ),
        SweepVariable(
            name="trend_template.high_52w_margin_pct",
            kind="threshold_multiplicative",
            current_value=cfg.trend_template.high_52w_margin_pct,
            sweep_points=_multiplicative_sweep(
                cfg.trend_template.high_52w_margin_pct,
            ),
        ),
        SweepVariable(
            name="trend_template.low_52w_min_pct",
            kind="threshold_multiplicative",
            current_value=cfg.trend_template.low_52w_min_pct,
            sweep_points=_multiplicative_sweep(
                cfg.trend_template.low_52w_min_pct,
            ),
        ),
        # VCP numeric thresholds (8).
        SweepVariable(
            name="vcp.prior_trend_min_pct", kind="threshold_multiplicative",
            current_value=cfg.vcp.prior_trend_min_pct,
            sweep_points=_multiplicative_sweep(cfg.vcp.prior_trend_min_pct),
        ),
        SweepVariable(
            name="vcp.adr_min_pct", kind="threshold_multiplicative",
            current_value=cfg.vcp.adr_min_pct,
            sweep_points=_multiplicative_sweep(cfg.vcp.adr_min_pct),
        ),
        SweepVariable(
            name="vcp.pullback_max_pct", kind="threshold_multiplicative",
            current_value=cfg.vcp.pullback_max_pct,
            sweep_points=_multiplicative_sweep(cfg.vcp.pullback_max_pct),
        ),
        SweepVariable(
            name="vcp.proximity_max_pct", kind="threshold_multiplicative",
            current_value=cfg.vcp.proximity_max_pct,
            sweep_points=_multiplicative_sweep(cfg.vcp.proximity_max_pct),
        ),
        SweepVariable(
            name="vcp.tightness_days_required", kind="threshold_additive",
            current_value=cfg.vcp.tightness_days_required,
            sweep_points=_additive_sweep(cfg.vcp.tightness_days_required),
        ),
        SweepVariable(
            name="vcp.tightness_range_factor", kind="threshold_multiplicative",
            current_value=cfg.vcp.tightness_range_factor,
            sweep_points=_multiplicative_sweep(cfg.vcp.tightness_range_factor),
        ),
        SweepVariable(
            name="vcp.orderliness_max_bar_ratio", kind="threshold_multiplicative",
            current_value=cfg.vcp.orderliness_max_bar_ratio,
            sweep_points=_multiplicative_sweep(cfg.vcp.orderliness_max_bar_ratio),
        ),
        SweepVariable(
            name="vcp.orderliness_max_range_cv", kind="threshold_multiplicative",
            current_value=cfg.vcp.orderliness_max_range_cv,
            sweep_points=_multiplicative_sweep(cfg.vcp.orderliness_max_range_cv),
        ),
        # Risk numeric threshold (1).
        SweepVariable(
            name="risk.max_risk_pct", kind="threshold_multiplicative",
            current_value=cfg.risk.max_risk_pct,
            sweep_points=_multiplicative_sweep(cfg.risk.max_risk_pct),
        ),
        # RS numeric thresholds (3 — note: cfg.rs ALSO read at recon).
        SweepVariable(
            name="rs.horizon_weeks", kind="threshold_additive",
            current_value=cfg.rs.horizon_weeks,
            sweep_points=_additive_sweep(cfg.rs.horizon_weeks),
        ),
        SweepVariable(
            name="rs.rs_rank_min_pass", kind="threshold_additive",
            current_value=cfg.rs.rs_rank_min_pass,
            sweep_points=_additive_sweep(cfg.rs.rs_rank_min_pass, delta=10),
        ),
        SweepVariable(
            name="rs.fallback_extreme_pct", kind="threshold_multiplicative",
            current_value=cfg.rs.fallback_extreme_pct,
            sweep_points=_multiplicative_sweep(cfg.rs.fallback_extreme_pct),
        ),
    ]
    return tuple(variables)
```

The enumeration is concrete (no placeholders): **2 gate vars + 3 trend_template + 8 vcp + 1 risk + 3 rs = 17 variables.** Per R2 LOCK the exact 17-name set is asserted via `expected_names` set-equality at Sub-task 1A.1 test, NOT the loose `>=10` of the original R1 draft. Excluded explicitly:
- `cfg.trend_template.allowed_miss_names` (tuple-set; sweeping over set-membership is V2 because it's not a numeric grid).
- `cfg.rs.benchmark_ticker` (string identifier, not a threshold).
- `cfg.trend_template.min_passes` counted ONCE (as a gate var; NOT also under trend_template thresholds).

- [ ] **Step 1A.4: Run test to verify it passes**

Run: `python -m pytest tests/research/test_aplus_sensitivity_variables.py -v`
Expected: PASS (exact 17-name set asserted via set-equality; `gate_count == 2` invariant satisfied; each variable carries valid `kind` ∈ {gate, threshold_additive, threshold_multiplicative} + current_value in sweep_points anchor).

- [ ] **Step 1A.5: Commit**

```bash
git add research/harness/aplus_sensitivity/__init__.py \
        research/harness/aplus_sensitivity/variables.py \
        tests/research/test_aplus_sensitivity_variables.py
git commit -m "feat(research): aplus_sensitivity sweep variable enumeration (Item 1; T-T4.SB.1)"
```

(Commit message MUST NOT include Co-Authored-By footer per cumulative discipline.)

**Sub-task 1B — Sweep machinery against persisted candidate_criteria**

- [ ] **Step 1B.1: Write failing test `test_sweep_recomputes_buckets_per_variable`** at `tests/research/test_aplus_sensitivity_sweep.py`:

```python
import sqlite3
from research.harness.aplus_sensitivity.sweep import (
    SweepResult,
    run_sensitivity_sweep,
)
from research.harness.aplus_sensitivity.variables import SweepVariable


def test_sweep_recomputes_buckets_per_variable(tmp_path):
    db_path = tmp_path / "sweep.db"
    conn = sqlite3.connect(str(db_path))
    _plant_minimal_eval_run_fixture(conn)  # helper plants 5 candidates with criteria
    var = SweepVariable(
        name="trend_template.min_passes",
        kind="gate",
        current_value=7,
        sweep_points=(5, 6, 7, 8, 9),
    )
    result = run_sensitivity_sweep(
        conn, variables=(var,), cfg=Config.from_defaults(), eval_runs_window=20,
    )
    assert isinstance(result, SweepResult)
    # One matrix entry per variable per sweep point.
    entries = [e for e in result.entries if e.variable_name == "trend_template.min_passes"]
    assert len(entries) == 5
    # The current-value entry MUST reproduce the persisted bucket distribution
    # (counts derived from actual candidates.bucket column).
    current = next(e for e in entries if e.sweep_point == 7)
    assert current.aplus_count + current.watch_count + current.skip_count == 5
```

(Implementer writes `_plant_minimal_eval_run_fixture` helper inline; plants 1 aplus + 2 watch + 2 skip candidates with associated `candidate_criteria` rows. Uses `swing.data.db.init_schema` to set up tables.)

- [ ] **Step 1B.2: Run test to verify it fails**

Run: `python -m pytest tests/research/test_aplus_sensitivity_sweep.py -v`
Expected: FAIL with `ModuleNotFoundError: research.harness.aplus_sensitivity.sweep`.

- [ ] **Step 1B.3: Write sweep machinery**

Write `research/harness/aplus_sensitivity/sweep.py`:

```python
"""Sensitivity sweep: 1D parameter-sweep over `candidate_criteria` rows.

For each (variable, sweep_point) pair, substitute the variable's value
into the per-candidate criterion evaluation and recompute bucket counts
across the last N eval_runs.

This is a first-order approximation — cross-coupling between variables
is acknowledged but NOT modeled (one variable at a time; others held at
current). Per spec §1.5.1 amendment for OQ-1.3.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from research.harness.aplus_sensitivity.variables import SweepVariable


@dataclass(frozen=True)
class SweepEntry:
    variable_name: str
    kind: str  # "gate" | "threshold_additive" | "threshold_multiplicative"
    sweep_point: float | int
    aplus_count: int
    watch_count: int
    skip_count: int
    excluded_count: int
    delta_aplus: int  # vs current_value entry's aplus_count
    delta_watch: int


@dataclass(frozen=True)
class SweepResult:
    eval_runs_window: int
    eval_run_id_range: tuple[int, int]
    total_candidates: int
    entries: tuple[SweepEntry, ...]


_LAST_N_EVAL_RUNS_SQL = (
    "SELECT id FROM evaluation_runs "
    "ORDER BY id DESC LIMIT ?"
)


def run_sensitivity_sweep(
    conn: sqlite3.Connection,
    *,
    variables: tuple[SweepVariable, ...],
    cfg,  # swing.config.Config — for allowed_miss_names + production min_passes
    eval_runs_window: int = 20,
) -> SweepResult:
    eval_run_ids = [
        row[0] for row in conn.execute(_LAST_N_EVAL_RUNS_SQL, (eval_runs_window,))
    ]
    if not eval_run_ids:
        return SweepResult(
            eval_runs_window=eval_runs_window,
            eval_run_id_range=(0, 0),
            total_candidates=0,
            entries=(),
        )

    # Pre-fetch all (candidate_id, layer, criterion_name, result, value, rule)
    # rows JOINed to candidates.bucket for the window. Pure SELECT; no writes.
    placeholders = ",".join("?" for _ in eval_run_ids)
    sql = (
        f"SELECT c.id, c.bucket, cc.layer, cc.criterion_name, "
        f"       cc.result, cc.value, cc.rule "
        f"FROM candidates c "
        f"LEFT JOIN candidate_criteria cc ON cc.candidate_id = c.id "
        f"WHERE c.evaluation_run_id IN ({placeholders})"
    )
    rows = list(conn.execute(sql, eval_run_ids))

    candidate_ids = {r[0] for r in rows}
    total_candidates = len(candidate_ids)

    # Per-variable sweep: for each sweep point, recompute buckets per
    # candidate using the variable's value substituted in.
    entries: list[SweepEntry] = []
    for var in variables:
        current_aplus = current_watch = 0
        sub_entries: list[SweepEntry] = []
        for point in var.sweep_points:
            counts = _recompute_counts_at(
                rows=rows,
                variable_name=var.name,
                sweep_value=point,
                cfg=cfg,
            )
            sub_entries.append(SweepEntry(
                variable_name=var.name,
                kind=var.kind,
                sweep_point=point,
                aplus_count=counts["aplus"],
                watch_count=counts["watch"],
                skip_count=counts["skip"],
                excluded_count=counts["excluded"],
                delta_aplus=0,  # filled below
                delta_watch=0,
            ))
            if point == var.current_value:
                current_aplus = counts["aplus"]
                current_watch = counts["watch"]
        # Fill deltas
        for e in sub_entries:
            entries.append(SweepEntry(
                variable_name=e.variable_name,
                kind=e.kind,
                sweep_point=e.sweep_point,
                aplus_count=e.aplus_count,
                watch_count=e.watch_count,
                skip_count=e.skip_count,
                excluded_count=e.excluded_count,
                delta_aplus=e.aplus_count - current_aplus,
                delta_watch=e.watch_count - current_watch,
            ))

    return SweepResult(
        eval_runs_window=eval_runs_window,
        eval_run_id_range=(min(eval_run_ids), max(eval_run_ids)),
        total_candidates=total_candidates,
        entries=tuple(entries),
    )


def _recompute_counts_at(
    *,
    rows: list[tuple],
    variable_name: str,
    sweep_value: float | int,
    cfg: Config,
) -> dict[str, int]:
    """Recompute (aplus, watch, skip, excluded) counts under the
    hypothetical that `variable_name` = `sweep_value`.

    V1 substitution semantics support TWO classes of variables:
      - **Gate variables** (`trend_template.min_passes`, `vcp.watch_max_fails`):
        full bucket-level resimulation — substitute the gate value + walk
        `bucket_for` semantics including the `allowed_miss_names` invariant.
      - **Threshold variables** (15 = 3 trend_template + 8 vcp + 1 risk + 3 rs):
        V1 LIMITATION — per-criterion bucket resimulation requires the
        criterion evaluator harness to re-run against original OHLCV bars
        with the substituted threshold, which is V2 (depends on OHLCV
        cache validity at original data_asof_date). For these, V1 returns
        `persisted_bucket` (parity-preserving). Output formatter calls
        this out explicitly per spec §1.5.1 cross-coupling caveat.
    """
    counts = {"aplus": 0, "watch": 0, "skip": 0, "excluded": 0}
    by_candidate: dict[int, dict] = {}
    for cid, bucket, layer, name, result, value, rule in rows:
        cand = by_candidate.setdefault(cid, {
            "bucket": bucket,
            "tt": [],
            "vcp": [],
            "risk": [],
        })
        if layer is None:
            continue
        cand[layer].append({"name": name, "result": result, "value": value, "rule": rule})

    allowed_miss = set(cfg.trend_template.allowed_miss_names)
    prod_min_passes = cfg.trend_template.min_passes
    for cid, c in by_candidate.items():
        new_bucket = _bucket_for_substituted(
            tt=c["tt"], vcp=c["vcp"], risk=c["risk"],
            variable_name=variable_name, sweep_value=sweep_value,
            persisted_bucket=c["bucket"],
            allowed_miss_names=allowed_miss,
            prod_trend_template_min_passes=prod_min_passes,
        )
        counts[new_bucket] = counts.get(new_bucket, 0) + 1
    return counts


def _bucket_for_substituted(
    *,
    tt: list[dict],
    vcp: list[dict],
    risk: list[dict],
    variable_name: str,
    sweep_value: float | int,
    persisted_bucket: str,
    allowed_miss_names: set[str],
    prod_trend_template_min_passes: int,
) -> str:
    """Mirror of `swing.evaluation.scoring.bucket_for` for the 2 gate
    variables. For threshold variables, returns `persisted_bucket`
    (V1 limitation per `_recompute_counts_at` docstring).

    Faithfully encodes the bucket_for semantics:
      1. Risk hard filter — any non-pass = skip.
      2. Trend-template gate — `tt_passes >= min_passes` AND every TT
         failing name is in `allowed_miss_names`.
      3. VCP gate — `vcp_fails == 0` → aplus; `<= watch_max_fails` → watch;
         else skip.
    """
    # 1. Risk hard filter.
    if any(r["result"] != "pass" for r in risk):
        return "skip"

    tt_passes = sum(1 for r in tt if r["result"] == "pass")
    tt_fails = [r["name"] for r in tt if r["result"] != "pass"]

    if variable_name == "trend_template.min_passes":
        # Substituted min_passes; allowed_miss_names invariant preserved.
        if tt_passes < int(sweep_value):
            return "skip"
        if not all(n in allowed_miss_names for n in tt_fails):
            return "skip"
        return _vcp_to_bucket(vcp, watch_max_fails=2)

    if variable_name == "vcp.watch_max_fails":
        # Production trend-template gate (passed from cfg via caller,
        # NOT a module global — avoids order/concurrency hazards).
        if tt_passes < prod_trend_template_min_passes:
            return "skip"
        if not all(n in allowed_miss_names for n in tt_fails):
            return "skip"
        return _vcp_to_bucket(vcp, watch_max_fails=int(sweep_value))

    # Threshold-variable sweep entry — V1 returns persisted_bucket
    # (resimulation requires V2 criterion evaluator harness).
    return persisted_bucket


def _vcp_to_bucket(vcp: list[dict], *, watch_max_fails: int) -> str:
    vcp_fails = sum(1 for r in vcp if r["result"] in ("fail", "na"))
    if vcp_fails == 0:
        return "aplus"
    if vcp_fails <= watch_max_fails:
        return "watch"
    return "skip"
```

**V1 limitation contract (BINDING; encoded in BOTH the formatter AND a discriminating test):**

The markdown output's `## Sensitivity matrix` table MUST include a `Kind` column rendered immediately after `Variable`. Cell values are the `SweepVariable.kind` tag verbatim: `gate` for the 2 bucket-resimulating variables; `threshold_additive` / `threshold_multiplicative` for the 15 V1-parity-preserving rows.

The `## Notes` section MUST contain a STANDALONE paragraph (asserted by test in §1C.1 with substring `"Threshold variables (kind = threshold_*)"`):

> "V1 LIMITATION: threshold variables (kind = threshold_additive | threshold_multiplicative — 15 of 17 rows) report the persisted bucket distribution at each sweep point; their `delta_aplus` and `delta_watch` columns are intentionally ZERO. True per-criterion bucket resimulation against the substituted threshold requires the V2 OHLCV criterion-evaluator harness (banked at `research/method-records/aplus-criteria-calibration.md` V2 dependencies). Gate variables (kind = gate — 2 of 17 rows: `trend_template.min_passes`, `vcp.watch_max_fails`) DO produce real bucket-redistribution counts via faithful `bucket_for` resimulation."

The method record at `research/method-records/aplus-criteria-calibration.md` MUST cite the same gate-vs-threshold distinction in its `Outputs` section AND its `Validation` section ("threshold-variable deltas asserted == 0 in V1 discriminating test; gate-variable deltas asserted non-zero on planted divergent fixture").

Discriminating test pattern at `tests/research/test_aplus_sensitivity_output.py`:

```python
def test_markdown_output_distinguishes_gate_from_threshold():
    result = _build_synthetic_result_with_mixed_kinds()
    md_path = Path(tmp_path) / "out.md"
    write_sensitivity_markdown(result, md_path)
    text = md_path.read_text(encoding="utf-8")
    # Header includes Kind column.
    assert "| Variable | Kind | Sweep point" in text
    # V1 limitation paragraph present verbatim.
    assert "Threshold variables (kind = threshold_*)" in text or \
           "Threshold variables (kind = threshold_additive | threshold_multiplicative" in text
    assert "delta_aplus` and `delta_watch` columns are intentionally ZERO" in text

def test_threshold_variables_have_zero_deltas_in_sweep_result():
    """Invariant: threshold-variable sweep entries have delta_aplus ==
    delta_watch == 0 (parity-preserving V1 behavior). Gate variables
    may have non-zero deltas."""
    conn = sqlite3.connect(":memory:")
    _plant_eval_runs_with_known_distribution(conn, aplus=1, watch=2, skip=4)
    cfg = Config.from_defaults()
    variables = enumerate_variables(cfg)
    result = run_sensitivity_sweep(
        conn, variables=variables, cfg=cfg, eval_runs_window=10,
    )
    for entry in result.entries:
        var = next(v for v in variables if v.name == entry.variable_name)
        if var.kind.startswith("threshold_"):
            assert entry.delta_aplus == 0, f"{entry.variable_name}@{entry.sweep_point}"
            assert entry.delta_watch == 0
```

For T-T4.SB.1 Sub-task 1B.5 (parity invariant test), the test continues to work because `prod_trend_template_min_passes` is now an explicit kwarg threaded from `cfg.trend_template.min_passes` through `_recompute_counts_at` → `_bucket_for_substituted` (no module-global state per R2 Minor #1 LOCK); the test invokes `run_sensitivity_sweep(conn, variables=(var,), cfg=Config.from_defaults(), eval_runs_window=20)` against an in-memory cfg + DB so the gate value matches the planted rows.
```

- [ ] **Step 1B.4: Run test to verify it passes**

Run: `python -m pytest tests/research/test_aplus_sensitivity_sweep.py -v`
Expected: PASS (5 sweep entries for `trend_template.min_passes`; current-point entry sums to 5 candidates).

- [ ] **Step 1B.5: Add discriminating test for sweep-vs-persisted parity at current_value**

Append to `tests/research/test_aplus_sensitivity_sweep.py`:

```python
def test_sweep_at_current_value_matches_persisted_distribution(tmp_path):
    """The sweep point matching current_value MUST reproduce the persisted
    bucket counts exactly (no substitution applied at current_value)."""
    conn = sqlite3.connect(":memory:")
    _plant_eval_runs_with_known_distribution(conn, aplus=2, watch=3, skip=4)
    var = SweepVariable(
        name="vcp.watch_max_fails",
        kind="gate",
        current_value=2,
        sweep_points=(0, 1, 2, 3, 4),
    )
    result = run_sensitivity_sweep(
        conn, variables=(var,), cfg=Config.from_defaults(), eval_runs_window=20,
    )
    current_entry = next(
        e for e in result.entries
        if e.variable_name == "vcp.watch_max_fails" and e.sweep_point == 2
    )
    assert current_entry.aplus_count == 2
    assert current_entry.watch_count == 3
    assert current_entry.skip_count == 4
    assert current_entry.delta_aplus == 0
    assert current_entry.delta_watch == 0
```

Run: `python -m pytest tests/research/test_aplus_sensitivity_sweep.py -v`
Expected: PASS (parity-at-current-value invariant holds).

- [ ] **Step 1B.6: Commit**

```bash
git add research/harness/aplus_sensitivity/sweep.py \
        tests/research/test_aplus_sensitivity_sweep.py
git commit -m "feat(research): aplus_sensitivity 1D sweep machinery (Item 1; T-T4.SB.1)"
```

**Sub-task 1C — Output formatters (CSV + markdown)**

- [ ] **Step 1C.1: Write failing test `test_output_formatter_emits_csv_and_markdown`** at `tests/research/test_aplus_sensitivity_output.py`:

```python
from research.harness.aplus_sensitivity.output import (
    write_sensitivity_csv,
    write_sensitivity_markdown,
)
from research.harness.aplus_sensitivity.sweep import SweepResult, SweepEntry


def test_output_formatter_emits_csv_and_markdown(tmp_path):
    result = SweepResult(
        eval_runs_window=20,
        eval_run_id_range=(101, 120),
        total_candidates=5000,
        entries=(
            SweepEntry("trend_template.min_passes", "gate", 5, 12, 80, 4908, 0, 11, 70),
            SweepEntry("trend_template.min_passes", "gate", 6, 4, 70, 4926, 0, 3, 60),
            SweepEntry("trend_template.min_passes", "gate", 7, 1, 10, 4989, 0, 0, 0),
            # Threshold variable — delta columns must serialize as 0 per V1.
            SweepEntry("vcp.adr_min_pct", "threshold_multiplicative",
                       2.5, 1, 10, 4989, 0, 0, 0),
        ),
    )
    csv_path = tmp_path / "sweep.csv"
    md_path = tmp_path / "sweep.md"
    write_sensitivity_csv(result, csv_path)
    write_sensitivity_markdown(result, md_path)

    csv_text = csv_path.read_text(encoding="utf-8")
    # CSV must include all 9 columns (kind appended after variable_name) +
    # all data rows (3 gate + 1 threshold).
    assert "variable_name,kind,sweep_point,aplus_count,watch_count" in csv_text
    assert "trend_template.min_passes,gate,5,12,80,4908" in csv_text
    assert "trend_template.min_passes,gate,7,1,10,4989" in csv_text
    assert "vcp.adr_min_pct,threshold_multiplicative,2.5,1,10,4989" in csv_text

    md_text = md_path.read_text(encoding="utf-8")
    # ASCII-only (Windows cp1252 stdout safety).
    md_text.encode("cp1252")
    # Markdown must surface the sensitivity matrix table with Kind column.
    assert "| Variable | Kind | Sweep point | A+ | Watch | Skip" in md_text
    assert "**Eval-runs window:**" in md_text
    assert "**Total candidates:** 5000" in md_text
    # V1 limitation paragraph present + threshold-variable distinction visible.
    assert "V1 LIMITATION:" in md_text
    assert "Threshold variables (kind = threshold_additive |" in md_text
    assert "intentionally ZERO" in md_text
    # Per-row kind value rendered in the matrix cells.
    assert "| trend_template.min_passes | gate | 5 |" in md_text
    assert "| vcp.adr_min_pct | threshold_multiplicative | 2.5 |" in md_text
```

- [ ] **Step 1C.2: Run test to verify it fails**

Run: `python -m pytest tests/research/test_aplus_sensitivity_output.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 1C.3: Write output formatters**

Write `research/harness/aplus_sensitivity/output.py`:

```python
"""Sensitivity-sweep output formatters: CSV + markdown analysis.

ASCII-only output per Windows cp1252 stdout safety lesson.
"""
from __future__ import annotations

import csv
from pathlib import Path
from datetime import datetime, timezone

from research.harness.aplus_sensitivity.sweep import SweepResult


_CSV_HEADERS = (
    "variable_name", "kind", "sweep_point",
    "aplus_count", "watch_count", "skip_count", "excluded_count",
    "delta_aplus", "delta_watch",
)


def write_sensitivity_csv(result: SweepResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(_CSV_HEADERS)
        for e in result.entries:
            writer.writerow([
                e.variable_name, e.kind, e.sweep_point,
                e.aplus_count, e.watch_count, e.skip_count, e.excluded_count,
                e.delta_aplus, e.delta_watch,
            ])


def write_sensitivity_markdown(result: SweepResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = [
        "# A+ Criteria Sensitivity Sweep",
        "",
        f"**Generated:** {iso}",
        f"**Eval-runs window:** last N={result.eval_runs_window} runs (range "
        f"{result.eval_run_id_range[0]}..{result.eval_run_id_range[1]})",
        f"**Total candidates:** {result.total_candidates}",
        "",
        "## Sensitivity matrix",
        "",
        "| Variable | Kind | Sweep point | A+ | Watch | Skip | Excluded | dA+ | dWatch |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for e in result.entries:
        lines.append(
            f"| {e.variable_name} | {e.kind} | {e.sweep_point} | "
            f"{e.aplus_count} | {e.watch_count} | {e.skip_count} | "
            f"{e.excluded_count} | {e.delta_aplus:+d} | {e.delta_watch:+d} |"
        )
    lines.extend([
        "",
        "## Notes",
        "",
        "- Sweep is 1D (one variable at a time); cross-coupling NOT modeled.",
        "- Counts at current_value match the persisted bucket distribution",
        "  (parity invariant); delta_aplus / delta_watch are relative to that anchor.",
        "- **V1 LIMITATION: Threshold variables (kind = threshold_additive |",
        "  threshold_multiplicative — 15 of 17 rows) report the persisted bucket",
        "  distribution at each sweep point; their `delta_aplus` and `delta_watch`",
        "  columns are intentionally ZERO. True per-criterion bucket resimulation",
        "  against the substituted threshold requires the V2 OHLCV criterion-",
        "  evaluator harness (banked at `research/method-records/",
        "  aplus-criteria-calibration.md` V2 dependencies). Gate variables",
        "  (kind = gate — 2 of 17 rows: `trend_template.min_passes`,",
        "  `vcp.watch_max_fails`) DO produce real bucket-redistribution counts",
        "  via faithful `bucket_for` resimulation.**",
        "- Margin-of-failure semantics for non-numeric criteria fold to",
        "  boolean-fail counts; see study writeup at",
        "  `research/studies/aplus-criterion-sensitivity-2026-05-22.md`.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
```

- [ ] **Step 1C.4: Run test to verify it passes**

Run: `python -m pytest tests/research/test_aplus_sensitivity_output.py -v`
Expected: PASS (CSV row format + markdown headers verified; cp1252-encodability asserted).

- [ ] **Step 1C.5: Commit**

```bash
git add research/harness/aplus_sensitivity/output.py \
        tests/research/test_aplus_sensitivity_output.py
git commit -m "feat(research): aplus_sensitivity CSV + markdown output formatters (Item 1; T-T4.SB.1)"
```

**Sub-task 1D — Harness CLI entrypoint + run.py orchestration**

- [ ] **Step 1D.1: Write `research/harness/aplus_sensitivity/run.py`**

```python
"""CLI entrypoint for the A+ sensitivity sweep harness.

Invoke via `python -m research.harness.aplus_sensitivity.run --db PATH
--eval-runs N --output-dir DIR` OR via `swing diagnose aplus-sensitivity`
which delegates here.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from swing.config import Config
from research.harness.aplus_sensitivity.variables import enumerate_variables
from research.harness.aplus_sensitivity.sweep import run_sensitivity_sweep
from research.harness.aplus_sensitivity.output import (
    write_sensitivity_csv,
    write_sensitivity_markdown,
)


def run_harness(*, db_path: Path, eval_runs: int, output_dir: Path) -> tuple[Path, Path]:
    cfg = Config.from_defaults()
    variables = enumerate_variables(cfg)
    conn = sqlite3.connect(str(db_path))
    try:
        result = run_sensitivity_sweep(
            conn, variables=variables, cfg=cfg, eval_runs_window=eval_runs,
        )
    finally:
        conn.close()
    iso = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    csv_path = output_dir / f"aplus-sensitivity-{iso}.csv"
    md_path = output_dir / f"aplus-sensitivity-{iso}.md"
    write_sensitivity_csv(result, csv_path)
    write_sensitivity_markdown(result, md_path)
    return md_path, csv_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--eval-runs", type=int, default=20)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("exports/diagnostics"),
    )
    args = parser.parse_args(argv)
    if not 1 <= args.eval_runs <= 100:
        parser.error("--eval-runs must be between 1 and 100 inclusive")
    md_path, csv_path = run_harness(
        db_path=args.db, eval_runs=args.eval_runs, output_dir=args.output_dir,
    )
    print(f"Markdown: {md_path}")
    print(f"CSV:      {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 1D.2: Add README for the harness**

Write `research/harness/aplus_sensitivity/README.md`:

```markdown
# A+ criteria parameter-sweep sensitivity harness

1D sensitivity harness for `research/studies/aplus-criterion-sensitivity-2026-05-22.md`.
Operationalizes the OQ-1.3 + OQ-1.4 amendment (§1.5.1 + §1.5.4) — places the
diagnostic instrument under `research/` per V2.1 §V branch posture rather than
production `swing/`.

## Run

Against operator DB (default window N=20 eval_runs):

```bash
swing diagnose aplus-sensitivity --eval-runs 20
```

Standalone invocation (bypassing `swing` CLI):

```bash
python -m research.harness.aplus_sensitivity.run \
    --db "$USERPROFILE/swing-data/swing.db" \
    --eval-runs 20 \
    --output-dir exports/diagnostics/
```

## Modules

- `variables.py` — variable enumeration from `cfg.trend_template` / `cfg.vcp` / `cfg.risk`.
- `sweep.py` — 1D sweep machinery; consumes persisted `candidate_criteria`.
- `output.py` — sensitivity matrix CSV + markdown analysis.
- `run.py` — CLI orchestration.

## Limits

- 1D sweep only; cross-coupling between variables is acknowledged and NOT modeled.
- Margin-of-failure for non-numeric criteria folds to boolean-fail counts.
- V2 candidates banked: structured threshold columns; richer cross-variable
  exploration; OHLCV-aware re-evaluation against original bars.
```

- [ ] **Step 1D.3: Write smoke test invoking run_harness end-to-end**

Append to `tests/research/test_aplus_sensitivity_sweep.py`:

```python
def test_run_harness_emits_csv_and_markdown_to_output_dir(tmp_path):
    from research.harness.aplus_sensitivity.run import run_harness
    db_path = tmp_path / "harness.db"
    conn = sqlite3.connect(str(db_path))
    _plant_eval_runs_with_known_distribution(conn, aplus=1, watch=2, skip=2)
    conn.close()
    out_dir = tmp_path / "out"
    md_path, csv_path = run_harness(
        db_path=db_path, eval_runs=10, output_dir=out_dir,
    )
    assert md_path.exists()
    assert csv_path.exists()
    # Markdown is non-empty + ASCII-safe.
    md_path.read_text(encoding="utf-8").encode("cp1252")
```

Run: `python -m pytest tests/research/test_aplus_sensitivity_sweep.py -v`
Expected: PASS.

- [ ] **Step 1D.4: Commit**

```bash
git add research/harness/aplus_sensitivity/run.py \
        research/harness/aplus_sensitivity/README.md \
        tests/research/test_aplus_sensitivity_sweep.py
git commit -m "feat(research): aplus_sensitivity harness CLI entrypoint + README (Item 1; T-T4.SB.1)"
```

**Sub-task 1E — Method record + study stubs (research-branch artifacts)**

- [ ] **Step 1E.1: Write `research/method-records/aplus-criteria-calibration.md`**

Use `research/method-records/_template.md` shape verbatim. Frontmatter:

```yaml
key: aplus-criteria-calibration
name: A+ criteria parameter sensitivity calibration
layer: ranking
status: research
baseline_or_predecessor: internal (swing.evaluation.scoring.bucket_for current cfg)
version: 0.1.0
last_updated: 2026-05-22
```

Body sections (per `_template.md`) — content MUST encode the gate-vs-threshold split per R4 LOCK:

- **Definition** — paragraph: "1D parameter-sweep against persisted `candidate_criteria` rows. The harness enumerates 17 variables across two semantic classes: (a) **gate variables** (`trend_template.min_passes`, `vcp.watch_max_fails`) — substituted at each sweep point with full `bucket_for` resimulation per `swing/evaluation/scoring.py` semantics (risk hard filter + tt_passes + allowed_miss_names + vcp fail count); (b) **threshold variables** (3 trend_template numerics + 8 vcp + 1 risk + 3 rs = 15 vars) — sweep points are enumerated but V1 returns the PERSISTED bucket per row (parity-preserving). True per-criterion bucket resimulation against the substituted threshold requires the V2 OHLCV criterion-evaluator harness banked in this record's V2 dependencies."
- **Inputs** — `candidate_criteria` rows (last N eval_runs; default N=20, max N=100); `Config` (variable enumeration source via `swing/config.py` TrendTemplate / VCP / Risk / RS dataclasses).
- **Outputs** — sensitivity matrix CSV (9 cols including Kind) + markdown analysis with explicit Kind column + V1-limitation paragraph. Gate-variable rows DO produce real `delta_aplus` / `delta_watch`; threshold-variable rows have `delta_aplus == delta_watch == 0` by V1 design.
- **Validation** — current-value sweep point reproduces persisted distribution (parity invariant: both gate and threshold rows); gate-variable sweep points at non-current values produce real bucket-redistribution counts (planted-fixture discriminating test); threshold-variable rows at ALL sweep points have zero deltas (invariant test). Discriminating tests at `tests/research/test_aplus_sensitivity_sweep.py` + `tests/research/test_aplus_sensitivity_output.py`.
- **Notes** — Cross-coupling between variables NOT modeled (first-order; one variable at a time, others held at production cfg). `cfg.trend_template.allowed_miss_names` (set-membership) + `cfg.rs.benchmark_ticker` (string identifier) explicitly EXCLUDED from V1 enumeration. Promotion from `research` to `shadow` / `production` per V2.1 §IV.D requires operator-paired evidence summary AND lift of the V1 threshold-variable limitation (i.e., bucket resimulation for the 15 threshold variables).
- **V2 dependencies** — OHLCV criterion-evaluator harness consuming original bars at candidate's `data_asof_date` + substituting per-criterion thresholds + recomputing `bucket_for` end-to-end. Allows the 15 threshold variables to produce real delta_aplus / delta_watch.

- [ ] **Step 1E.2: Write `research/studies/aplus-criterion-sensitivity-2026-05-22.md`**

Mirror `research/studies/earnings-proximity-exclusion.md` structural shape. Sections:
- **Question** — What is the bucket-distribution sensitivity to per-criterion threshold adjustments?
- **Method** — Reference `research/method-records/aplus-criteria-calibration.md` + `research/harness/aplus_sensitivity/`.
- **Data** — Operator's `swing-data/swing.db` `candidate_criteria` rows; last 20-63 eval_runs.
- **Findings** — TO BE POPULATED post-T4.SB-SHIPPED when operator runs the harness against their DB. Brainstorming spec acknowledges Item 1 diagnostic OUTPUT feeds research-branch first-method-record selection; T-T4.SB.1 ships the instrument + stub, operator post-merge runs + populates findings.
- **Next steps** — Threshold-loosening cfg-policy proposals BANKED V2 pending operator review of findings.

- [ ] **Step 1E.3: Update `research/phase-0-tasks.md`**

Move the "Evaluate which A+-like indicators warrant calibration" entry from "Later (deferred)" to "Next" section. Add citation: "the sensitivity harness shipped under T4.SB (T-T4.SB.1) is the first piece of this work; see `research/harness/aplus_sensitivity/` + study `research/studies/aplus-criterion-sensitivity-2026-05-22.md`."

- [ ] **Step 1E.4: Commit**

```bash
git add research/method-records/aplus-criteria-calibration.md \
        research/studies/aplus-criterion-sensitivity-2026-05-22.md \
        research/phase-0-tasks.md
git commit -m "docs(research): method-record + study stub + phase-0-tasks promotion (Item 1; T-T4.SB.1)"
```

**Sub-task 1F — Item 7 Phase 1 metrics-wiring-audit module**

- [ ] **Step 1F.1: Write failing test `test_audit_enumerates_known_metric_surfaces`** at `tests/diagnostics/test_metrics_wiring_audit.py`:

```python
from swing.diagnostics.metrics_wiring_audit import (
    SurfaceAuditRow,
    enumerate_metric_surfaces,
    audit_surface_match_strategy,
)


def test_audit_enumerates_known_metric_surfaces():
    rows = enumerate_metric_surfaces()
    names = {r.surface_name for r in rows}
    # Per spec §B.7.2 + OQ-7.2: at minimum these are audited.
    assert "Dashboard hyp-progress card" in names
    assert "CLI compute_hypothesis_progress_breakdown" in names
    assert "list_trades_for_cohort" in names
    assert "count_per_cohort" in names
    # Each row carries file:line + match strategy + state filter.
    for r in rows:
        assert isinstance(r, SurfaceAuditRow)
        assert r.file_path
        assert r.match_strategy in (
            "exact_equality", "prefix_match", "delimiter_aware",
            "sql_like", "unknown",
        )
```

- [ ] **Step 1F.2: Run test to verify it fails**

Run: `python -m pytest tests/diagnostics/test_metrics_wiring_audit.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 1F.3: Write `swing/diagnostics/__init__.py` + `swing/diagnostics/metrics_wiring_audit.py`**

`swing/diagnostics/__init__.py`:

```python
"""Diagnostic tooling: read-only audit + analysis CLIs.

Per Phase 13 T4.SB §B.1 + §B.7: each subcommand under `swing diagnose`
emits a deterministic markdown report (+ CSV sidecar where applicable)
to `exports/diagnostics/` and writes ZERO domain rows.
"""
```

`swing/diagnostics/metrics_wiring_audit.py`:

```python
"""Item 7 metrics-wiring audit (Phase 13 T4.SB T-T4.SB.1 Phase 1).

Enumerates every metric surface in `swing/metrics/`, `swing/web/view_models/metrics/`,
`swing/journal/stats.py`, and dashboard cards. For each, identifies the
match strategy + state filter + join keys + current operator-DB count +
audit disposition (LIVE / V1 STUB / V1 PLACEHOLDER / WIRING DEFECT / FALSE-ZERO RISK).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone


@dataclass(frozen=True)
class SurfaceAuditRow:
    surface_name: str
    file_path: str           # "swing/.../file.py:line"
    match_strategy: str      # exact_equality | prefix_match | delimiter_aware | sql_like | unknown
    state_filter: str        # e.g., "state IN ('closed','reviewed')" or "n/a"
    join_keys: str           # e.g., "hypothesis_label = ?" or "n/a"
    operator_db_count: int | None  # populated when conn supplied; None for stub
    disposition: str         # LIVE | V1 STUB | V1 PLACEHOLDER | WIRING DEFECT | FALSE-ZERO RISK
    notes: str


_KNOWN_SURFACES: tuple[SurfaceAuditRow, ...] = (
    SurfaceAuditRow(
        surface_name="Dashboard hyp-progress card",
        file_path="swing/web/view_models/metrics/hypothesis_progress_card.py:404",
        match_strategy="exact_equality",
        state_filter="state IN ('closed','reviewed')",
        join_keys="hypothesis_label = ?",
        operator_db_count=None,
        disposition="WIRING DEFECT",
        notes="Suffix-bearing labels exact-mismatch; Option 7C fix in T-T4.SB.2.",
    ),
    SurfaceAuditRow(
        surface_name="CLI compute_hypothesis_progress_breakdown",
        file_path="swing/journal/stats.py:325",
        match_strategy="prefix_match",
        state_filter="state IN ('closed','reviewed')",
        join_keys="_label_matches_hypothesis",
        operator_db_count=None,
        disposition="LIVE",
        notes="Existing bare-startswith helper; widens to 3-rule delimiter-aware in T-T4.SB.2.",
    ),
    SurfaceAuditRow(
        surface_name="list_trades_for_cohort",
        file_path="swing/metrics/cohort.py:40",
        match_strategy="exact_equality",
        state_filter="(via state_filter param)",
        join_keys="hypothesis_label = ?",
        operator_db_count=None,
        disposition="WIRING DEFECT",
        notes="Pivots to delimiter-aware SQL helper in T-T4.SB.2.",
    ),
    SurfaceAuditRow(
        surface_name="count_per_cohort",
        file_path="swing/metrics/cohort.py:99",
        match_strategy="exact_equality",
        state_filter="state IN closed-states",
        join_keys="GROUP BY hypothesis_label",
        operator_db_count=None,
        disposition="WIRING DEFECT",
        notes="Suffix-bearing labels create orphan cohorts; delimiter-aware GROUP BY in T-T4.SB.2 preserves orphan fallback.",
    ),
    # T-T4.SB.1 ships the audit; T-T4.SB.2 extends with audit-derived
    # WIRING DEFECT entries (e.g., outcome distribution V1 STUB rows).
)


def enumerate_metric_surfaces() -> tuple[SurfaceAuditRow, ...]:
    """Return the BASE audit registry. Per-row operator-DB counts are
    None unless `audit_surface_match_strategy` is invoked with a conn.

    V1 simplifications acknowledged: this list is hand-maintained; future
    metric-tile surfaces require a manual append. V2 candidate: codegen
    the registry from a decorator-marked surface registry.
    """
    return _KNOWN_SURFACES


def audit_surface_match_strategy(
    conn: sqlite3.Connection, row: SurfaceAuditRow,
) -> SurfaceAuditRow:
    """Populate `operator_db_count` for the given row by issuing a
    discriminating query against `conn`. Returns a NEW dataclass instance
    (rows are frozen). The query for each surface_name is hard-coded;
    augmentation requires a paired test under tests/diagnostics/.
    """
    # Implementer fills per-surface query logic at execution time; the
    # generic shape is: count trades / candidates / records matching the
    # surface's match strategy against the operator DB.
    return row


def write_metrics_wiring_audit_markdown(
    conn: sqlite3.Connection, output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = [audit_surface_match_strategy(conn, r) for r in enumerate_metric_surfaces()]
    lines = [
        "# Metrics Wiring Audit",
        "",
        f"**Generated:** {iso}",
        f"**Surfaces audited:** {len(rows)}",
        "",
        "## Per-surface table",
        "",
        "| Surface | File:line | Match strategy | State filter | Join keys | Operator DB count | Disposition |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        count = r.operator_db_count if r.operator_db_count is not None else "n/a"
        lines.append(
            f"| {r.surface_name} | {r.file_path} | {r.match_strategy} | "
            f"{r.state_filter} | {r.join_keys} | {count} | {r.disposition} |"
        )
    lines.extend(["", "## Notes per surface", ""])
    for r in rows:
        lines.extend([f"### {r.surface_name}", "", r.notes, ""])
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path
```

- [ ] **Step 1F.4: Run test to verify it passes**

Run: `python -m pytest tests/diagnostics/test_metrics_wiring_audit.py -v`
Expected: PASS (4 known surfaces enumerated; types match).

- [ ] **Step 1F.5: Add audit markdown emit test**

Append to `tests/diagnostics/test_metrics_wiring_audit.py`:

```python
import sqlite3
from swing.diagnostics.metrics_wiring_audit import (
    write_metrics_wiring_audit_markdown,
)


def test_write_audit_markdown_is_ascii_clean(tmp_path):
    conn = sqlite3.connect(":memory:")
    out_path = tmp_path / "audit.md"
    written = write_metrics_wiring_audit_markdown(conn, out_path)
    assert written == out_path
    text = out_path.read_text(encoding="utf-8")
    text.encode("cp1252")  # ASCII-safe
    assert "| Surface | File:line |" in text
    assert "Dashboard hyp-progress card" in text
    assert "count_per_cohort" in text
```

Run: `python -m pytest tests/diagnostics/test_metrics_wiring_audit.py -v`
Expected: PASS.

- [ ] **Step 1F.6: Commit**

```bash
git add swing/diagnostics/__init__.py \
        swing/diagnostics/metrics_wiring_audit.py \
        tests/diagnostics/__init__.py \
        tests/diagnostics/test_metrics_wiring_audit.py
git commit -m "feat(diagnostics): metrics-wiring-audit module + audit registry (Item 7 Phase 1; T-T4.SB.1)"
```

**Sub-task 1G — `swing diagnose` CLI subcommand group**

- [ ] **Step 1G.1: Write failing CLI test `test_diagnose_aplus_sensitivity_invokes_harness`** at `tests/cli/test_diagnose_subcommands.py`:

```python
import sqlite3
from click.testing import CliRunner

from swing.cli import cli


def test_diagnose_aplus_sensitivity_invokes_harness(tmp_path, monkeypatch):
    db_path = tmp_path / "harness.db"
    conn = sqlite3.connect(str(db_path))
    # Plant minimal eval_run + candidate rows so the harness has data.
    _plant_minimal_db(conn)
    conn.close()
    out_dir = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(cli, [
        "diagnose", "aplus-sensitivity",
        "--db", str(db_path),
        "--eval-runs", "10",
        "--output-dir", str(out_dir),
    ])
    assert result.exit_code == 0, result.output
    csvs = list(out_dir.glob("aplus-sensitivity-*.csv"))
    mds = list(out_dir.glob("aplus-sensitivity-*.md"))
    assert len(csvs) == 1
    assert len(mds) == 1


def test_diagnose_aplus_sensitivity_rejects_eval_runs_out_of_range(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, [
        "diagnose", "aplus-sensitivity",
        "--db", str(tmp_path / "x.db"),
        "--eval-runs", "0",
    ])
    assert result.exit_code != 0
    assert "between 1 and 100" in (result.output + (result.stderr or ""))


def test_diagnose_metrics_wiring_emits_markdown(tmp_path):
    runner = CliRunner()
    out_path = tmp_path / "audit.md"
    result = runner.invoke(cli, [
        "diagnose", "metrics-wiring",
        "--db", str(tmp_path / "empty.db"),
        "--output", str(out_path),
    ])
    assert result.exit_code == 0, result.output
    text = out_path.read_text(encoding="utf-8")
    text.encode("cp1252")
    assert "| Surface | File:line |" in text
```

- [ ] **Step 1G.2: Run test to verify it fails**

Run: `python -m pytest tests/cli/test_diagnose_subcommands.py -v`
Expected: FAIL — `Error: No such command 'diagnose'`.

- [ ] **Step 1G.3: Register `diagnose` subcommand group in `swing/cli.py`**

Add to `swing/cli.py` (locate near other `@cli.group()` registrations):

```python
@cli.group()
def diagnose() -> None:
    """Diagnostic CLIs: aplus sensitivity sweep + metrics-wiring audit."""


@diagnose.command("aplus-sensitivity")
@click.option("--db", "db_path", required=True, type=click.Path(path_type=Path))
@click.option("--eval-runs", type=click.IntRange(1, 100), default=20, show_default=True)
@click.option(
    "--output-dir", type=click.Path(path_type=Path),
    default=Path("exports/diagnostics"), show_default=True,
)
def diagnose_aplus_sensitivity(db_path: Path, eval_runs: int, output_dir: Path) -> None:
    """1D sensitivity sweep over A+ criteria thresholds.

    Reads persisted candidate_criteria from `--db` (last `--eval-runs`
    runs); substitutes each variable across a sweep range; writes
    `aplus-sensitivity-<ISO>.csv` + `.md` to `--output-dir`.
    """
    try:
        from research.harness.aplus_sensitivity.run import run_harness
        md_path, csv_path = run_harness(
            db_path=db_path, eval_runs=eval_runs, output_dir=output_dir,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Markdown: {md_path}")
    click.echo(f"CSV:      {csv_path}")


@diagnose.command("metrics-wiring")
@click.option("--db", "db_path", required=True, type=click.Path(path_type=Path))
@click.option(
    "--output", "output_path", required=True, type=click.Path(path_type=Path),
)
def diagnose_metrics_wiring(db_path: Path, output_path: Path) -> None:
    """Enumerate metric surfaces + audit match strategy / state filter /
    join keys / operator-DB count / disposition. Writes markdown table.
    """
    import sqlite3
    from swing.diagnostics.metrics_wiring_audit import (
        write_metrics_wiring_audit_markdown,
    )
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            write_metrics_wiring_audit_markdown(conn, output_path)
        finally:
            conn.close()
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Audit:    {output_path}")
```

- [ ] **Step 1G.4: Run test to verify it passes**

Run: `python -m pytest tests/cli/test_diagnose_subcommands.py -v`
Expected: PASS (3 tests).

- [ ] **Step 1G.5: Add subprocess-stdout-encoding test (Windows cp1252 safety per cumulative discipline)**

Append to `tests/cli/test_diagnose_subcommands.py`:

```python
import subprocess
import sys


def test_diagnose_aplus_sensitivity_stdout_is_ascii_safe(tmp_path):
    db_path = tmp_path / "harness.db"
    conn = sqlite3.connect(str(db_path))
    _plant_minimal_db(conn)
    conn.close()
    out_dir = tmp_path / "out"
    proc = subprocess.run(
        [sys.executable, "-m", "swing.cli",
         "diagnose", "aplus-sensitivity",
         "--db", str(db_path),
         "--eval-runs", "5",
         "--output-dir", str(out_dir)],
        capture_output=True, text=True, check=False, timeout=120,
    )
    assert proc.returncode == 0, (proc.stdout + proc.stderr)
    # Stdout must be cp1252-encodable (Windows safety).
    proc.stdout.encode("cp1252")
    proc.stderr.encode("cp1252")
```

Run: `python -m pytest tests/cli/test_diagnose_subcommands.py -v`
Expected: PASS.

- [ ] **Step 1G.6: Commit**

```bash
git add swing/cli.py tests/cli/test_diagnose_subcommands.py
git commit -m "feat(cli): swing diagnose subcommand group + aplus-sensitivity + metrics-wiring (Item 1 + Item 7 Phase 1; T-T4.SB.1)"
```

**T-T4.SB.1 discriminating tests summary:**
- Variable enumeration: `>= 10` variables; current-value among sweep points.
- Sweep parity at current_value: persisted bucket counts reproduced exactly.
- Output formatters: CSV format + markdown headers + cp1252-encodable.
- Harness CLI end-to-end: CSV + markdown written; rejects `--eval-runs 0`.
- Metrics-wiring audit: 4 known surfaces enumerated; markdown emit ASCII-safe.
- CLI subprocess stdout: cp1252-encodable.

**T-T4.SB.1 commit message templates (≥6 commits):**
- `feat(research): aplus_sensitivity sweep variable enumeration (Item 1; T-T4.SB.1)`
- `feat(research): aplus_sensitivity 1D sweep machinery (Item 1; T-T4.SB.1)`
- `feat(research): aplus_sensitivity CSV + markdown output formatters (Item 1; T-T4.SB.1)`
- `feat(research): aplus_sensitivity harness CLI entrypoint + README (Item 1; T-T4.SB.1)`
- `docs(research): method-record + study stub + phase-0-tasks promotion (Item 1; T-T4.SB.1)`
- `feat(diagnostics): metrics-wiring-audit module + audit registry (Item 7 Phase 1; T-T4.SB.1)`
- `feat(cli): swing diagnose subcommand group + aplus-sensitivity + metrics-wiring (T-T4.SB.1)`

**T-T4.SB.1 test budget:** +30-40 fast tests (per §1.5.5 amendment).

---

### §B.2 T-T4.SB.2 — Item 7 broader metrics audit + canonical wiring fix + cross-bundle pin row 13

**Files:**
- Create: `swing/metrics/label_match.py` — shared 3-rule delimiter-aware match helper (Python + SQL).
- Modify: `swing/recommendations/hypothesis.py:_label_matches_hypothesis` — pivot to helper.
- Modify: `swing/metrics/cohort.py:list_trades_for_cohort` — use SQL helper; keep `state_filter` API.
- Modify: `swing/metrics/cohort.py:count_per_cohort` — iterate registry + delimiter-aware count + orphan-fallback second query.
- Modify: `swing/diagnostics/metrics_wiring_audit.py` — extend rows per audit findings.
- Test: `tests/metrics/test_hypothesis_label_match_helper.py` — Python + SQL parity + escape-wildcard correctness.
- Test: `tests/metrics/test_cohort_delimiter_aware.py` — `list_trades_for_cohort` + `count_per_cohort` delimiter-aware + orphan-preservation.
- Test: `tests/metrics/test_hypothesis_progress_card_suffix_labels.py` — dashboard card non-zero on suffix-bearing labels.
- Test: `tests/recommendations/test_label_matches_hypothesis.py` — existing tests adjusted for 3-rule delimiter contract.
- Test: `tests/metrics/test_phase13_t4_sb_cross_bundle_pin_row_13.py` — parametrized 4 surfaces (planted SKIPped pre-fix; un-SKIPped post-fix).

**Sub-task 2A — Shared label-match helper (Python + SQL)**

- [ ] **Step 2A.1: Write failing test `test_label_matches_hypothesis_three_rule_delimiter_aware`** at `tests/metrics/test_hypothesis_label_match_helper.py`:

```python
from swing.metrics.label_match import (
    label_matches_hypothesis,
    label_matches_hypothesis_sql,
    sql_escape_wildcard,
)


def test_label_matches_hypothesis_three_rule_delimiter_aware():
    # Rule 1: exact equality (case-insensitive)
    assert label_matches_hypothesis("A+ baseline", "A+ baseline") is True
    assert label_matches_hypothesis("a+ baseline", "A+ baseline") is True
    # Rule 2: space delimiter
    assert label_matches_hypothesis(
        "Sub-A+ VCP-not-formed (watch); failed: proximity_20ma",
        "Sub-A+ VCP-not-formed",
    ) is True
    # Rule 3: semicolon delimiter
    assert label_matches_hypothesis(
        "Sub-A+ VCP-not-formed;extra",
        "Sub-A+ VCP-not-formed",
    ) is True
    # Rejected: bare prefix extension (no delimiter)
    assert label_matches_hypothesis(
        "Sub-A+ VCP-not-formedness",
        "Sub-A+ VCP-not-formed",
    ) is False
    # Rejected: empty label
    assert label_matches_hypothesis("", "A+ baseline") is False
    assert label_matches_hypothesis(None, "A+ baseline") is False


def test_sql_escape_wildcard_replaces_backslash_percent_underscore():
    assert sql_escape_wildcard("plain_name") == r"plain\_name"
    assert sql_escape_wildcard("90%up") == r"90\%up"
    assert sql_escape_wildcard(r"path\to") == r"path\\to"


def test_label_matches_hypothesis_sql_returns_fragment_and_three_bindings():
    fragment, params = label_matches_hypothesis_sql("cohort_X%")
    # Three predicates joined by OR.
    assert "LOWER(hypothesis_label) = LOWER(?)" in fragment
    assert "LOWER(hypothesis_label) LIKE LOWER(?) || ' %' ESCAPE '\\'" in fragment
    assert "LOWER(hypothesis_label) LIKE LOWER(?) || ';%' ESCAPE '\\'" in fragment
    # Raw lowercased name for equality + escaped lowercased for LIKE predicates.
    assert params[0] == "cohort_x%"
    assert params[1] == r"cohort\_x\%"
    assert params[2] == r"cohort\_x\%"
```

- [ ] **Step 2A.2: Run test → expect FAIL** (`ModuleNotFoundError`).

- [ ] **Step 2A.3: Write `swing/metrics/label_match.py`**

```python
"""Shared hypothesis-label match helpers (Python + SQL).

Three-rule delimiter-aware match contract — a label MATCHES a hypothesis
name when (and only when) one of these holds:
  1. label == name (after case-fold; exact equality).
  2. label.lower().startswith(name.lower() + " ") (space delimiter).
  3. label.lower().startswith(name.lower() + ";") (semicolon delimiter).

This is the SHARED canonicalization both the Python helper at
swing.recommendations.hypothesis._label_matches_hypothesis AND the SQL
predicate at swing.metrics.cohort.list_trades_for_cohort consume. The
two helpers MUST produce identical match sets on any test corpus.
"""
from __future__ import annotations


def label_matches_hypothesis(label: str | None, name: str) -> bool:
    if not label:
        return False
    lo_label = label.lower()
    lo_name = name.lower()
    if lo_label == lo_name:
        return True
    if lo_label.startswith(lo_name + " "):
        return True
    if lo_label.startswith(lo_name + ";"):
        return True
    return False


def sql_escape_wildcard(name: str) -> str:
    """Escape SQL LIKE wildcards in a registered cohort name.

    Order matters: backslash FIRST (otherwise subsequent backslash
    insertions get re-escaped).
    """
    out = name.replace("\\", "\\\\")
    out = out.replace("%", r"\%")
    out = out.replace("_", r"\_")
    return out


def label_matches_hypothesis_sql(name: str) -> tuple[str, list[object]]:
    """Return (WHERE fragment, binding params).

    Three predicates joined by OR. Param 1 (equality) receives RAW
    lowercased name; params 2-3 (LIKE) receive WILDCARD-ESCAPED
    lowercased name. Mixing the two would either over-escape equality
    or under-escape LIKE (per spec §B.7.1 Codex R4 M#2 LOCK).
    """
    raw = name.lower()
    escaped = sql_escape_wildcard(raw)
    fragment = (
        "("
        "LOWER(hypothesis_label) = LOWER(?) "
        "OR LOWER(hypothesis_label) LIKE LOWER(?) || ' %' ESCAPE '\\' "
        "OR LOWER(hypothesis_label) LIKE LOWER(?) || ';%' ESCAPE '\\'"
        ")"
    )
    return fragment, [raw, escaped, escaped]
```

- [ ] **Step 2A.4: Run test → expect PASS.**

- [ ] **Step 2A.5: Pivot existing Python helper to share the contract**

Edit `swing/recommendations/hypothesis.py:_label_matches_hypothesis` to delegate:

```python
from swing.metrics.label_match import label_matches_hypothesis as _shared


def _label_matches_hypothesis(label: str | None, hypothesis_name: str) -> bool:
    """Trade's `hypothesis_label` matches a hypothesis via 3-rule
    delimiter-aware contract. See swing.metrics.label_match.label_matches_hypothesis.

    Phase 13 T-T4.SB.2: replaces the prior bare-startswith implementation
    to close the per-trade-suffix false-positive defect family. Companion
    SQL helper at swing.metrics.label_match.label_matches_hypothesis_sql.
    """
    return _shared(label, hypothesis_name)
```

- [ ] **Step 2A.6: Update `tests/recommendations/test_label_matches_hypothesis.py` for 3-rule contract**

(Implementer reads existing test file; updates assertions where bare-prefix was previously assumed. Existing matched cases like `"sub-A+ VCP-not-formed VIR backfill"` continue to match via space-delimiter rule. Previously-matched cases like `"Sub-A+ VCP-not-formedness"` now correctly fail.)

- [ ] **Step 2A.7: Run full helper-related test suite**

Run: `python -m pytest tests/metrics/test_hypothesis_label_match_helper.py tests/recommendations/test_label_matches_hypothesis.py -v`
Expected: PASS.

- [ ] **Step 2A.8: Commit**

```bash
git add swing/metrics/label_match.py \
        swing/recommendations/hypothesis.py \
        tests/metrics/test_hypothesis_label_match_helper.py \
        tests/recommendations/test_label_matches_hypothesis.py
git commit -m "feat(metrics): shared 3-rule delimiter-aware label-match helper (Python + SQL) (Item 7; T-T4.SB.2)"
```

**Sub-task 2B — Rewire `list_trades_for_cohort` to delimiter-aware SQL**

- [ ] **Step 2B.1: Write failing test `test_list_trades_for_cohort_matches_suffix_bearing_labels`** at `tests/metrics/test_cohort_delimiter_aware.py`:

```python
import sqlite3

from swing.data.db import init_schema
from swing.metrics.cohort import list_trades_for_cohort
from swing.trades.entry import canonicalize_hypothesis_label


def test_list_trades_for_cohort_matches_suffix_bearing_labels(tmp_path):
    db = tmp_path / "cohort.db"
    conn = sqlite3.connect(str(db))
    init_schema(conn)
    _plant_trade(conn, ticker="AAA",
        hypothesis_label="Sub-A+ VCP-not-formed (watch); failed: proximity_20ma",
        state="closed")
    _plant_trade(conn, ticker="BBB",
        hypothesis_label="Sub-A+ VCP-not-formed",
        state="reviewed")
    _plant_trade(conn, ticker="CCC",
        hypothesis_label="A+ baseline",
        state="closed")
    _plant_trade(conn, ticker="DDD",
        hypothesis_label="Sub-A+ VCP-not-formedness extended",
        state="closed")

    rows = list_trades_for_cohort(
        conn, hypothesis_label="Sub-A+ VCP-not-formed",
        state_filter=("closed", "reviewed"),
    )
    tickers = {r.ticker for r in rows}
    assert tickers == {"AAA", "BBB"}  # Not CCC (different name); not DDD (prefix extension)


def test_list_trades_for_cohort_handles_wildcard_chars_in_registered_name(tmp_path):
    db = tmp_path / "cohort.db"
    conn = sqlite3.connect(str(db))
    init_schema(conn)
    _plant_trade(conn, ticker="X1", hypothesis_label="cohort_X%", state="closed")
    _plant_trade(conn, ticker="X2",
        hypothesis_label="cohort_X% (watch); failed: x", state="closed")
    _plant_trade(conn, ticker="X3", hypothesis_label="cohortQX9", state="closed")

    rows = list_trades_for_cohort(
        conn, hypothesis_label="cohort_X%",
        state_filter=("closed", "reviewed"),
    )
    tickers = {r.ticker for r in rows}
    assert tickers == {"X1", "X2"}  # NOT X3 (would match if `_` and `%` were unescaped)
```

- [ ] **Step 2B.2: Run test → expect FAIL** (exact-equality query returns AAA only or BBB only).

- [ ] **Step 2B.3: Rewrite `swing/metrics/cohort.py:list_trades_for_cohort`**

```python
from swing.metrics.label_match import label_matches_hypothesis_sql


def list_trades_for_cohort(
    conn: sqlite3.Connection,
    *,
    hypothesis_label: str | None,
    state_filter: tuple[str, ...] | None = None,
) -> list[Trade]:
    """Return trades matching the cohort filter via 3-rule delimiter-aware
    match (per Phase 13 T-T4.SB.2 Option 7C LOCK).

    hypothesis_label is the REGISTERED cohort name (post-canonicalization).
    Match contract: exact equality OR space-delimited prefix OR
    semicolon-delimited prefix.
    """
    canonical = (
        canonicalize_hypothesis_label(hypothesis_label)
        if hypothesis_label is not None
        else None
    )
    where_clauses: list[str] = []
    params: list[object] = []
    if canonical is not None:
        fragment, fragment_params = label_matches_hypothesis_sql(canonical)
        where_clauses.append(fragment)
        params.extend(fragment_params)
    if state_filter:
        placeholders = ",".join("?" for _ in state_filter)
        where_clauses.append(f"state IN ({placeholders})")
        params.extend(state_filter)

    cols = _trade_select_cols(conn)
    sql = f"SELECT {cols} FROM trades"  # noqa: S608
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    sql += " ORDER BY entry_date, ticker, id"
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_trade(r) for r in rows]
```

- [ ] **Step 2B.4: Run test → expect PASS.**

- [ ] **Step 2B.5: Commit**

```bash
git add swing/metrics/cohort.py tests/metrics/test_cohort_delimiter_aware.py
git commit -m "fix(metrics): list_trades_for_cohort 3-rule delimiter-aware match (Item 7 Option 7C; T-T4.SB.2)"
```

**Sub-task 2C — Rewrite `count_per_cohort` with orphan-fallback preservation**

- [ ] **Step 2C.1: Write failing test `test_count_per_cohort_delimiter_aware_with_orphan_preservation`** at `tests/metrics/test_cohort_delimiter_aware.py`:

```python
def test_count_per_cohort_delimiter_aware_with_orphan_preservation(tmp_path):
    db = tmp_path / "count.db"
    conn = sqlite3.connect(str(db))
    init_schema(conn)
    # Plant registry entries.
    conn.execute(
        "INSERT INTO hypothesis_registry "
        "(id, name, statement, target_sample_size, decision_criteria, "
        " consecutive_loss_tripwire, absolute_loss_tripwire_pct, created_at) "
        "VALUES "
        "(1, 'A+ baseline', 's', 30, 'd', 5, 10.0, '2026-05-22T00:00:00Z'), "
        "(2, 'Sub-A+ VCP-not-formed', 's', 30, 'd', 5, 10.0, '2026-05-22T00:00:00Z')"
    )
    # Plant trades — 1 matching A+ baseline (exact); 1 matching Sub-A+
    # VCP-not-formed via suffix; 1 orphan (no registered match).
    _plant_trade(conn, ticker="EX", hypothesis_label="A+ baseline", state="closed")
    _plant_trade(conn, ticker="SF",
        hypothesis_label="Sub-A+ VCP-not-formed (watch); failed: x",
        state="closed")
    _plant_trade(conn, ticker="OR",
        hypothesis_label="Free-text experimental",
        state="closed")
    conn.commit()

    counts = count_per_cohort(conn)
    assert counts["A+ baseline"] == 1
    assert counts["Sub-A+ VCP-not-formed"] == 1
    # Orphan label preserved as its own entry (per Codex R4 M#1 LOCK).
    assert counts["Free-text experimental"] == 1
```

- [ ] **Step 2C.2: Run test → expect FAIL** (exact-equality GROUP BY yields 3 keys but cohort name "Sub-A+ VCP-not-formed" missing the suffix-bearing trade).

- [ ] **Step 2C.3: Rewrite `count_per_cohort`**

```python
from swing.metrics.label_match import label_matches_hypothesis_sql


def count_per_cohort(conn: sqlite3.Connection) -> dict[str, int]:
    """Return ``{cohort_name: closed_trade_count}`` via 3-rule delimiter-aware
    match per registered hypothesis, PLUS orphan-label rows for any label
    that delimiter-matches NONE of the registered hypotheses.
    """
    cohort_counts: dict[str, int] = {}
    registered_names: list[str] = []
    for (name,) in conn.execute(_HYPOTHESIS_REGISTRY_NAMES_SQL):
        registered_names.append(name)
        cohort_counts[name] = 0

    # Per-cohort count via the shared SQL helper.
    for name in registered_names:
        fragment, params = label_matches_hypothesis_sql(name)
        sql = (
            f"SELECT COUNT(*) FROM trades "
            f"WHERE state IN {_CLOSED_STATES_SQL} "
            f"  AND hypothesis_label IS NOT NULL "
            f"  AND {fragment}"
        )
        (count,) = conn.execute(sql, params).fetchone()
        cohort_counts[name] = int(count)

    # Orphan-label preservation: a SECOND query selects closed trades
    # with hypothesis_label NOT NULL that match NONE of the registered
    # hypotheses (per Codex R4 M#1 LOCK).
    if registered_names:
        # Build a NOT (any-of) predicate by AND-NOT chaining per-name
        # delimiter-aware fragments.
        not_clauses: list[str] = []
        not_params: list[object] = []
        for name in registered_names:
            fragment, params = label_matches_hypothesis_sql(name)
            not_clauses.append(f"NOT {fragment}")
            not_params.extend(params)
        orphan_sql = (
            f"SELECT hypothesis_label, COUNT(*) FROM trades "
            f"WHERE state IN {_CLOSED_STATES_SQL} "
            f"  AND hypothesis_label IS NOT NULL "
            f"  AND {' AND '.join(not_clauses)} "
            f"GROUP BY hypothesis_label"
        )
        for label, count in conn.execute(orphan_sql, not_params):
            cohort_counts[label] = int(count)
    else:
        # Empty-registry branch (production seeds registry rows; defensive
        # for test DBs / future startup transient states). EVERY non-NULL
        # label is an orphan; surface raw labels per orphan contract.
        orphan_sql_empty = (
            f"SELECT hypothesis_label, COUNT(*) FROM trades "
            f"WHERE state IN {_CLOSED_STATES_SQL} "
            f"  AND hypothesis_label IS NOT NULL "
            f"GROUP BY hypothesis_label"
        )
        for label, count in conn.execute(orphan_sql_empty):
            cohort_counts[label] = int(count)
    return cohort_counts
```

- [ ] **Step 2C.4: Run test → expect PASS.**

- [ ] **Step 2C.5: Commit**

```bash
git add swing/metrics/cohort.py tests/metrics/test_cohort_delimiter_aware.py
git commit -m "fix(metrics): count_per_cohort delimiter-aware + orphan-fallback preservation (Item 7; T-T4.SB.2)"
```

**Sub-task 2D — Dashboard hyp-progress card integration test**

- [ ] **Step 2D.1: Write failing test `test_hypothesis_progress_card_non_zero_on_suffix_labels`** at `tests/metrics/test_hypothesis_progress_card_suffix_labels.py`:

```python
import sqlite3

from swing.data.db import init_schema
from swing.web.view_models.metrics.hypothesis_progress_card import (
    build_hypothesis_progress_card_vm,
)


def test_hypothesis_progress_card_non_zero_on_suffix_labels(tmp_path):
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    conn.execute(
        "INSERT INTO hypothesis_registry "
        "(id, name, statement, target_sample_size, decision_criteria, "
        " consecutive_loss_tripwire, absolute_loss_tripwire_pct, created_at) "
        "VALUES (1, 'Sub-A+ VCP-not-formed', 's', 30, 'd', 5, 10.0, "
        "        '2026-05-22T00:00:00Z')"
    )
    for ticker, state in (
        ("AAA", "closed"), ("BBB", "closed"),
        ("CCC", "reviewed"), ("DDD", "reviewed"),
    ):
        _plant_trade(conn, ticker=ticker,
            hypothesis_label="Sub-A+ VCP-not-formed (watch); failed: x",
            state=state)
    conn.commit()
    vm = build_hypothesis_progress_card_vm(conn)
    cohort = next(c for c in vm.cohorts if c.name == "Sub-A+ VCP-not-formed")
    assert cohort.n_closed == 4  # Was 0 pre-fix (exact-equality mismatch)
```

- [ ] **Step 2D.2: Run test → expect FAIL pre-fix; PASS post-Sub-task-2B fix.**

The fix from Sub-task 2B + 2C transitively makes this assertion pass because the dashboard card calls `list_closed_trades_for_cohort` which wraps `list_trades_for_cohort`.

- [ ] **Step 2D.3: Commit**

```bash
git add tests/metrics/test_hypothesis_progress_card_suffix_labels.py
git commit -m "test(metrics): dashboard hyp-progress card non-zero on suffix labels (Item 7; T-T4.SB.2)"
```

**Sub-task 2E — Registered-name non-overlap invariant (Codex R5 MIN#2 LOCK)**

- [ ] **Step 2E.1: Write test `test_registered_hypothesis_names_do_not_delimiter_overlap`** at `tests/metrics/test_hypothesis_label_match_helper.py`:

```python
import sqlite3

from swing.data.db import init_schema
from swing.metrics.label_match import label_matches_hypothesis


def test_registered_hypothesis_names_do_not_delimiter_overlap():
    """Invariant: no registered hypothesis name delimiter-matches another's
    canonical form (prefix-overlap would cause double-counting on cohorts)."""
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    rows = list(conn.execute("SELECT name FROM hypothesis_registry"))
    names = [r[0] for r in rows]
    for a in names:
        for b in names:
            if a == b:
                continue
            assert label_matches_hypothesis(b, a) is False, (
                f"Registered hypothesis '{b}' delimiter-matches '{a}' "
                f"— would double-count cohort metrics."
            )
```

- [ ] **Step 2E.2: Run test → expect PASS** (current registry has 4 non-overlapping names).

- [ ] **Step 2E.3: Commit**

```bash
git add tests/metrics/test_hypothesis_label_match_helper.py
git commit -m "test(metrics): registered-hypothesis-name non-overlap invariant (Codex R5 MIN#2; T-T4.SB.2)"
```

**Sub-task 2F — Cross-bundle pin row 13 (4-surface parametrize)**

- [ ] **Step 2F.1: Write planted pin `test_phase13_t4_sb_cross_bundle_pin_row_13`** at `tests/metrics/test_phase13_t4_sb_cross_bundle_pin_row_13.py`:

```python
"""Phase 13 T4.SB cross-bundle pin row 13 — hypothesis-label delimiter-aware
match invariant across 4 metric surfaces.

Per spec §E recommendation: PLANT at T-T4.SB.2; promote GREEN at T-T4.SB.6.

Parametrize set: 4 surfaces (per dispatch brief §1.4 OQ-7.2 LOCK +
spec §B.7.2 R2 M#4 closure).
"""
from __future__ import annotations

import sqlite3

import pytest

from swing.data.db import init_schema
from swing.metrics.cohort import list_trades_for_cohort, count_per_cohort
from swing.web.view_models.metrics.hypothesis_progress_card import (
    build_hypothesis_progress_card_vm,
)
from swing.journal.stats import compute_hypothesis_progress_breakdown


def _plant_db():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    conn.execute(
        "INSERT INTO hypothesis_registry "
        "(id, name, statement, target_sample_size, decision_criteria, "
        " consecutive_loss_tripwire, absolute_loss_tripwire_pct, created_at) "
        "VALUES (1, 'Sub-A+ VCP-not-formed', 's', 30, 'd', 5, 10.0, "
        "        '2026-05-22T00:00:00Z')"
    )
    # Plant 1 suffix-bearing trade.
    _plant_trade(conn, ticker="ZZZ",
        hypothesis_label="Sub-A+ VCP-not-formed (watch); failed: proximity_20ma",
        state="closed")
    conn.commit()
    return conn


def _surface_list_trades_for_cohort():
    conn = _plant_db()
    rows = list_trades_for_cohort(
        conn, hypothesis_label="Sub-A+ VCP-not-formed",
        state_filter=("closed", "reviewed"),
    )
    return len(rows)


def _surface_count_per_cohort():
    conn = _plant_db()
    counts = count_per_cohort(conn)
    return counts["Sub-A+ VCP-not-formed"]


def _surface_hyp_progress_card():
    conn = _plant_db()
    vm = build_hypothesis_progress_card_vm(conn)
    cohort = next(c for c in vm.cohorts if c.name == "Sub-A+ VCP-not-formed")
    return cohort.n_closed


def _surface_cli_breakdown():
    conn = _plant_db()
    breakdown = compute_hypothesis_progress_breakdown(conn)
    for entry in breakdown:
        if entry.hypothesis_name == "Sub-A+ VCP-not-formed":
            return entry.n_closed
    return 0


@pytest.mark.parametrize(
    "surface_fn,surface_name", [
        (_surface_list_trades_for_cohort, "list_trades_for_cohort"),
        (_surface_count_per_cohort, "count_per_cohort"),
        (_surface_hyp_progress_card, "hyp_progress_card_vm"),
        (_surface_cli_breakdown, "cli_compute_hypothesis_progress_breakdown"),
    ],
)
def test_delimiter_aware_match_invariant_holds_at_surface(surface_fn, surface_name):
    """Per spec §E: when GREEN-promoted at T-T4.SB.6, all 4 surfaces MUST
    return 1 for the suffix-bearing trade against the canonical cohort
    name 'Sub-A+ VCP-not-formed'."""
    assert surface_fn() == 1, (
        f"Surface '{surface_name}' returned 0 — delimiter-aware match "
        f"invariant violated. See spec §B.7.1 LOCK."
    )
```

- [ ] **Step 2F.2: Run test → expect PASS post-fix** (all 4 surfaces return 1).

If any surface still returns 0, the fix has not reached that surface — implementer iterates until all 4 PASS. CLI path's `_label_matches_hypothesis` now uses 3-rule contract (Sub-task 2A.5); `list_trades_for_cohort` + `count_per_cohort` use SQL helper (Sub-tasks 2B + 2C); dashboard VM transitively uses `list_closed_trades_for_cohort`.

- [ ] **Step 2F.3: Commit**

```bash
git add tests/metrics/test_phase13_t4_sb_cross_bundle_pin_row_13.py
git commit -m "test(phase13): cross-bundle pin row 13 — delimiter-aware match invariant 4 surfaces (T-T4.SB.2)"
```

**Sub-task 2G — V2-bank FALSE-ZERO RISK entries from audit findings**

- [ ] **Step 2G.1: Read audit output from T-T4.SB.1 metrics-wiring step**

After Sub-tasks 2A-2F land, re-run `swing diagnose metrics-wiring --db <operator_db> --output exports/diagnostics/metrics-wiring-audit-postfix.md` to confirm WIRING DEFECT entries flip to LIVE. Any remaining FALSE-ZERO RISK entries (e.g., outcome distribution V1 STUB per T2.SB6c §4.1) get a brief notes-paragraph in the audit markdown; no code change.

- [ ] **Step 2G.2: Update `swing/diagnostics/metrics_wiring_audit.py:_KNOWN_SURFACES`** disposition column for the 4 surfaces fixed in Sub-tasks 2A-2F (WIRING DEFECT → LIVE).

- [ ] **Step 2G.3: Commit**

```bash
git add swing/diagnostics/metrics_wiring_audit.py
git commit -m "chore(diagnostics): audit registry dispositions post-Item-7-fix (T-T4.SB.2)"
```

**T-T4.SB.2 discriminating tests summary:**
- Python helper 3-rule contract: exact / space-delim / semicolon-delim; rejects bare-prefix extension.
- SQL helper: 3 predicates joined OR; param[0]=raw lowercased, params[1,2]=escaped lowercased.
- `sql_escape_wildcard`: backslash + percent + underscore replacement.
- `list_trades_for_cohort`: suffix-bearing labels matched; bare-prefix extension rejected; wildcard chars in registered name correctly escaped.
- `count_per_cohort`: registered cohorts count via SQL helper; orphan-fallback preserved.
- Dashboard hyp-progress card: non-zero `n_closed` on suffix-bearing labels.
- Registry non-overlap invariant: no name delimiter-matches another.
- Cross-bundle pin row 13: parametrized over 4 surfaces; PASS post-fix.

**T-T4.SB.2 commit message templates (≥7 commits):**
- `feat(metrics): shared 3-rule delimiter-aware label-match helper (Python + SQL) (Item 7; T-T4.SB.2)`
- `fix(metrics): list_trades_for_cohort 3-rule delimiter-aware match (Item 7 Option 7C; T-T4.SB.2)`
- `fix(metrics): count_per_cohort delimiter-aware + orphan-fallback preservation (Item 7; T-T4.SB.2)`
- `test(metrics): dashboard hyp-progress card non-zero on suffix labels (Item 7; T-T4.SB.2)`
- `test(metrics): registered-hypothesis-name non-overlap invariant (Codex R5 MIN#2; T-T4.SB.2)`
- `test(phase13): cross-bundle pin row 13 — delimiter-aware match invariant 4 surfaces (T-T4.SB.2)`
- `chore(diagnostics): audit registry dispositions post-Item-7-fix (T-T4.SB.2)`

**T-T4.SB.2 test budget:** +15-25 fast tests.

---

### §B.3 T-T4.SB.3 — Item 5 architecture (JIT cache-miss helper + expanded-view inline-SVG + pre-gen scope reduction)

**Files:**
- Create: `swing/web/chart_jit.py` — `get_or_render_surface` helper.
- Modify: `swing/web/view_models/dashboard.py:build_hyp_recs_expanded` — JIT fallback on cache miss.
- Modify: `swing/web/view_models/watchlist.py:WatchlistExpandedVM` — add `watchlist_expanded_chart_svg_bytes`; populate via JIT.
- Modify: `swing/web/templates/partials/hypothesis_recommendations_expanded.html.j2:81-92` — if-else cascade.
- Modify: `swing/web/templates/partials/watchlist_expanded.html.j2:36-43` — symmetric cascade.
- Modify: `swing/web/routes/watchlist.py:watchlist_row` + `:watchlist_expand` — wire JIT helper.
- Modify: `swing/pipeline/runner.py:_step_charts` — pre-gen scope reduction.
- Test: `tests/web/test_chart_jit.py` — JIT helper unit tests.
- Test: `tests/web/templates/test_expanded_chart_suppress_banner.py` — inline-SVG suppresses PNG/banner.
- Test: `tests/web/routes/test_watchlist_jit_integration.py` — route-level JIT wiring.
- Test: `tests/pipeline/test_step_charts_pregen_scope_reduction.py` — pre-gen scope assertions.

**Sub-task 3A — `swing/web/chart_jit.py:get_or_render_surface` helper**

- [ ] **Step 3A.1: Write failing test `test_get_or_render_surface_cache_hit_returns_cached_bytes`** at `tests/web/test_chart_jit.py`:

```python
import sqlite3
from unittest.mock import MagicMock

from swing.data.db import init_schema
from swing.web.chart_jit import get_or_render_surface


def test_get_or_render_surface_cache_hit_returns_cached_bytes(tmp_path):
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _plant_chart_render_row(
        conn, surface="hyprec_detail", ticker="UCTT",
        pipeline_run_id=42, chart_svg_bytes=b"<svg>cached</svg>",
    )
    ohlcv_cache = MagicMock()
    result = get_or_render_surface(
        conn=conn, ohlcv_cache=ohlcv_cache,
        surface="hyprec_detail", ticker="UCTT", pipeline_run_id=42,
        data_asof_date="2026-05-22",
    )
    assert result == b"<svg>cached</svg>"
    # On cache hit, OHLCV cache is NOT consulted.
    ohlcv_cache.get_or_fetch.assert_not_called()


def test_get_or_render_surface_cache_miss_renders_via_ohlcv_and_writes_through(tmp_path):
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    ohlcv_cache = MagicMock()
    ohlcv_cache.get_or_fetch.return_value = _planted_bars_df()
    # Inject a renderer mock to avoid matplotlib in the unit test.
    import swing.web.chart_jit as mod

    def fake_renderer(*, ticker, bars, pattern_evaluation):
        assert ticker == "UCTT"
        return b"<svg>rendered</svg>"

    monkeypatch_renderer = MagicMock(side_effect=fake_renderer)
    mod._RENDERERS["hyprec_detail"] = monkeypatch_renderer
    try:
        result = get_or_render_surface(
            conn=conn, ohlcv_cache=ohlcv_cache,
            surface="hyprec_detail", ticker="UCTT", pipeline_run_id=42,
            data_asof_date="2026-05-22",
        )
    finally:
        # restore real renderer registry between tests
        import importlib
        importlib.reload(mod)
    assert result == b"<svg>rendered</svg>"
    # Write-through populated cache.
    cached = conn.execute(
        "SELECT chart_svg_bytes FROM chart_renders "
        "WHERE surface = 'hyprec_detail' AND ticker = 'UCTT' "
        "  AND pipeline_run_id = 42"
    ).fetchone()
    assert cached is not None
    assert cached[0] == b"<svg>rendered</svg>"


def test_get_or_render_surface_returns_none_on_empty_ohlcv(tmp_path):
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    ohlcv_cache = MagicMock()
    ohlcv_cache.get_or_fetch.return_value = None  # no bars available
    result = get_or_render_surface(
        conn=conn, ohlcv_cache=ohlcv_cache,
        surface="hyprec_detail", ticker="UCTT", pipeline_run_id=42,
        data_asof_date="2026-05-22",
    )
    assert result is None
    # No cache row written (F6 construction-barrier defense).
    cached = conn.execute(
        "SELECT 1 FROM chart_renders WHERE ticker = 'UCTT'"
    ).fetchone()
    assert cached is None


def test_get_or_render_surface_cache_collision_renderer_called_once(tmp_path):
    """Two callers (e.g., hyprec route + watchlist expanded route) request
    the SAME (surface, ticker, pipeline_run_id) — renderer fires ONCE;
    second caller reads from cache."""
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    ohlcv_cache = MagicMock()
    ohlcv_cache.get_or_fetch.return_value = _planted_bars_df()
    import swing.web.chart_jit as mod
    renderer = MagicMock(return_value=b"<svg>once</svg>")
    mod._RENDERERS["hyprec_detail"] = renderer
    try:
        r1 = get_or_render_surface(
            conn=conn, ohlcv_cache=ohlcv_cache,
            surface="hyprec_detail", ticker="UCTT", pipeline_run_id=42,
            data_asof_date="2026-05-22",
        )
        r2 = get_or_render_surface(
            conn=conn, ohlcv_cache=ohlcv_cache,
            surface="hyprec_detail", ticker="UCTT", pipeline_run_id=42,
            data_asof_date="2026-05-22",
        )
    finally:
        import importlib
        importlib.reload(mod)
    assert r1 == r2 == b"<svg>once</svg>"
    assert renderer.call_count == 1
    cached_count = conn.execute(
        "SELECT COUNT(*) FROM chart_renders "
        "WHERE surface = 'hyprec_detail' AND ticker = 'UCTT' "
        "  AND pipeline_run_id = 42"
    ).fetchone()[0]
    assert cached_count == 1
```

- [ ] **Step 3A.2: Run tests → expect FAIL.**

- [ ] **Step 3A.3: Write `swing/web/chart_jit.py`**

```python
"""JIT cache-miss chart-render hook (Phase 13 T4.SB Item 5).

Architecture LOCK per spec §B.5:
  - `swing/web/chart_scope.py` LOCKED read-only (does NOT invoke JIT).
  - JIT invocation lives at route handlers / VM builders that carry the
    necessary dependency context (`conn`, `ohlcv_cache`, surface-specific
    render kwargs).
  - Cache key shape preserved: run-bound surfaces (`watchlist_row`,
    `hyprec_detail`, `market_weather`) write pipeline_run_id non-NULL;
    `position_detail` writes NULL.
  - F6 construction-barrier defense: `ChartRender(...)` construction
    raises on empty bytes; helper catches + returns None + WARN-logs.
  - Renderer-kwargs uniformity LOCK across callsites for cache-collision
    avoidance (per Codex R4 M#3): both hyprec_detail callers (hyp-recs
    route + watchlist expanded) pass identical kwargs.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Callable

from swing.data.repos.chart_renders import (
    get_cached_chart_svg,
    refresh_chart_render,
)
from swing.data.models import ChartRender
from swing.web.charts import (
    render_hyprec_detail_svg,
    render_market_weather_svg,
    render_position_detail_svg,
    render_watchlist_thumbnail_svg,
)


logger = logging.getLogger(__name__)


_RENDERERS: dict[str, Callable] = {
    "hyprec_detail": render_hyprec_detail_svg,
    "market_weather": render_market_weather_svg,
    "position_detail": render_position_detail_svg,
    "watchlist_row": render_watchlist_thumbnail_svg,
}


# Conservative default for watchlist thumbnail MA overlays (mirrors current
# `_step_charts` invocation pattern + spec §C.5 line 449 thumbnail design).
_WATCHLIST_THUMBNAIL_MA_LINES: list[int] = [20, 50]


def get_or_render_surface(
    *,
    conn: sqlite3.Connection,
    ohlcv_cache,
    surface: str,
    ticker: str,
    pipeline_run_id: int | None,
    pattern_class: str | None = None,
    data_asof_date: str,
    source_data_hash: str = "chart_jit_v1",
    **renderer_kwargs,
) -> bytes | None:
    """Return cached SVG bytes if present; otherwise live-render via the
    surface's matplotlib helper, write-through, and return bytes.

    Returns None on render-failure / OHLCV-missing / construction-barrier
    rejection. Caller emits chart-unavailable banner per spec §B.5 OQ-5.5.
    """
    # Step 1: cache read
    cached = get_cached_chart_svg(
        conn,
        surface=surface,
        ticker=ticker,
        pipeline_run_id=pipeline_run_id,
        pattern_class=pattern_class,
    )
    if cached is not None:
        return cached

    # Step 2: fetch OHLCV via cache (per `_step_charts._bars_or_none` precedent)
    try:
        bars = ohlcv_cache.get_or_fetch(ticker=ticker, window_days=200)
    except Exception as exc:  # noqa: BLE001 — log + degrade
        logger.warning("chart_jit ohlcv_cache failure for %s: %s", ticker, exc)
        return None
    if bars is None or len(bars) == 0:
        return None

    renderer = _RENDERERS.get(surface)
    if renderer is None:
        logger.warning("chart_jit: no renderer for surface=%s", surface)
        return None

    # Step 3: render. Renderer-kwargs match the actual signatures at
    # `swing/web/charts.py:render_*` (verified at writing-plans phase):
    #   - render_watchlist_thumbnail_svg(*, ticker, bars, ma_lines)
    #   - render_hyprec_detail_svg(*, ticker, bars, pattern_evaluation)
    #   - render_market_weather_svg(*, bars, trend_template_state)
    #   - render_position_detail_svg(*, ticker, bars, trade, fills, current_stop)
    # Uniformity LOCK: for hyprec_detail, both callsites pass
    # pattern_evaluation=None (V1). For watchlist_row, both callsites
    # pass the SAME ma_lines tuple (cache-collision avoidance).
    try:
        if surface == "hyprec_detail":
            svg_bytes = renderer(
                ticker=ticker, bars=bars,
                pattern_evaluation=renderer_kwargs.get("pattern_evaluation"),
            )
        elif surface == "watchlist_row":
            svg_bytes = renderer(
                ticker=ticker, bars=bars,
                ma_lines=renderer_kwargs.get("ma_lines", _WATCHLIST_THUMBNAIL_MA_LINES),
            )
        elif surface == "market_weather":
            svg_bytes = renderer(
                bars=bars,
                trend_template_state=renderer_kwargs.get("trend_template_state"),
            )
        elif surface == "position_detail":
            svg_bytes = renderer(
                ticker=ticker, bars=bars,
                trade=renderer_kwargs["trade"],
                fills=renderer_kwargs["fills"],
                current_stop=renderer_kwargs.get("current_stop"),
            )
        else:
            return None
    except Exception as exc:  # noqa: BLE001 — log + degrade
        logger.warning("chart_jit render failure for %s/%s: %s", surface, ticker, exc)
        return None

    # Step 4: F6 construction-barrier defense — ChartRender(...) raises
    # on empty bytes; catch + WARN + return None (cache row not blanked).
    # ChartRender dataclass at swing/data/models.py:1907-1924 requires:
    #   id, ticker, surface, chart_svg_bytes, source_data_hash,
    #   rendered_at, data_asof_date, [pipeline_run_id=None, pattern_class=None]
    from datetime import datetime, timezone
    try:
        chart_render = ChartRender(
            id=None,
            ticker=ticker,
            surface=surface,
            chart_svg_bytes=svg_bytes,
            source_data_hash=source_data_hash,
            rendered_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            data_asof_date=data_asof_date,
            pipeline_run_id=pipeline_run_id,
            pattern_class=pattern_class,
        )
    except ValueError as exc:
        logger.warning(
            "chart_jit construction-barrier rejected %s/%s (likely empty bytes): %s",
            surface, ticker, exc,
        )
        return None

    # Step 5: write-through cache
    try:
        refresh_chart_render(conn, chart_render)
    except Exception as exc:  # noqa: BLE001 — degrade + still return bytes
        logger.warning("chart_jit write-through failure for %s/%s: %s", surface, ticker, exc)
    return svg_bytes
```

- [ ] **Step 3A.4: Run tests → expect PASS.**

- [ ] **Step 3A.5: Commit**

```bash
git add swing/web/chart_jit.py tests/web/test_chart_jit.py
git commit -m "feat(web): JIT cache-miss chart-render hook at swing/web/chart_jit.py (Item 5; T-T4.SB.3)"
```

**Sub-task 3B — Wire JIT into watchlist routes**

- [ ] **Step 3B.1: Write failing test `test_watchlist_row_collapse_uses_jit_to_repopulate_thumbnail`** at `tests/web/routes/test_watchlist_jit_integration.py`:

```python
from fastapi.testclient import TestClient

from swing.web.app import create_app


def test_watchlist_row_collapse_uses_jit_to_repopulate_thumbnail(tmp_path, monkeypatch):
    """Per spec §B.6 Item 6 + §B.5 Item 5: collapse-route renders the
    thumbnail via JIT helper (cache hit OR live render); thumbnail never
    silently absent post-expand."""
    app = create_app(...)  # implementer wires test app with planted DB
    with TestClient(app) as client:
        # Plant a chart_renders row for ticker UCTT at pipeline_run_id N.
        _plant_chart_render(app, ticker="UCTT", surface="watchlist_row",
                            pipeline_run_id=N, chart_svg_bytes=b"<svg>x</svg>")
        # Expand then collapse the row.
        client.get("/watchlist/UCTT/expand")
        resp = client.get("/watchlist/UCTT/row")
        assert resp.status_code == 200
        assert b"watchlist-thumbnail" in resp.content
        assert b"<svg>x</svg>" in resp.content
```

- [ ] **Step 3B.2: Edit `swing/web/routes/watchlist.py`**

Update `watchlist_row` collapse handler:

```python
from swing.web.chart_jit import get_or_render_surface


@router.get("/watchlist/{ticker}/row", response_class=HTMLResponse)
def watchlist_row(request: Request, ticker: str):
    cfg = apply_overrides(request.app.state.cfg)
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    row_vm = build_watchlist_row(
        cfg=cfg, cache=cache, ticker=ticker.upper(), executor=executor,
    )
    if row_vm is None:
        raise HTTPException(status_code=404, detail=f"ticker {ticker} not on watchlist")

    # JIT cache lookup + live render on miss (Item 6 fix via Item 5 helper).
    # DB connection pattern mirrors swing/web/routes/account.py + charts.py:
    # acquire a fresh sqlite3 connection from cfg.paths.db_path per-request
    # (NOT app.state.db_conn — that attribute does not exist on app.state).
    chart_bytes = None
    ohlcv_cache = getattr(request.app.state, "ohlcv_cache", None)
    if ohlcv_cache is not None:
        import sqlite3
        from swing.web.chart_scope import latest_completed_pipeline_run
        conn = sqlite3.connect(str(cfg.paths.db_path))
        try:
            anchor = latest_completed_pipeline_run(conn)  # Option A LOCK
            if anchor is not None:
                chart_bytes = get_or_render_surface(
                    conn=conn, ohlcv_cache=ohlcv_cache,
                    surface="watchlist_row", ticker=ticker.upper(),
                    pipeline_run_id=anchor.run_id,
                    data_asof_date=anchor.data_asof_date,
                    ma_lines=[20, 50],  # uniformity LOCK with pipeline pre-gen
                )
        finally:
            conn.close()

    return request.app.state.templates.TemplateResponse(
        request, "partials/watchlist_row.html.j2",
        {
            "w": row_vm.w,
            "price": row_vm.price,
            "tags": row_vm.tags,
            "pattern_tag": row_vm.pattern_tag,
            "current_pivot": row_vm.current_pivot,
            "chart_svg_bytes_for_row": chart_bytes,
        },
    )
```

Update `watchlist_expand` to populate `WatchlistExpandedVM.watchlist_expanded_chart_svg_bytes` via the same JIT helper using `surface='hyprec_detail'` (per spec §B.5 LOCK).

- [ ] **Step 3B.3: Run test → expect PASS.**

- [ ] **Step 3B.4: Commit**

```bash
git add swing/web/routes/watchlist.py tests/web/routes/test_watchlist_jit_integration.py
git commit -m "feat(web): watchlist routes wire JIT chart-render hook (Item 5 + Item 6; T-T4.SB.3)"
```

**Sub-task 3C — Hyp-recs expanded VM JIT fallback**

- [ ] **Step 3C.1: Edit `swing/web/view_models/dashboard.py:build_hyp_recs_expanded`**

Add JIT fallback on cache miss:

```python
from swing.web.chart_jit import get_or_render_surface


def build_hyp_recs_expanded(
    conn: sqlite3.Connection, *, ohlcv_cache, ticker: str,
    pipeline_run_id: int | None, data_asof_date: str | None, ...
) -> HypRecsExpandedVM:
    # ... existing logic ...
    hyprec_detail_chart_svg_bytes = get_cached_chart_svg(
        conn,
        surface="hyprec_detail", ticker=ticker,
        pipeline_run_id=pipeline_run_id, pattern_class=None,
    )
    if (hyprec_detail_chart_svg_bytes is None and ohlcv_cache is not None
            and pipeline_run_id is not None and data_asof_date is not None):
        # JIT fallback: live render + cache write-through.
        hyprec_detail_chart_svg_bytes = get_or_render_surface(
            conn=conn, ohlcv_cache=ohlcv_cache,
            surface="hyprec_detail", ticker=ticker,
            pipeline_run_id=pipeline_run_id,
            data_asof_date=data_asof_date,
            pattern_evaluation=None,  # uniformity LOCK with watchlist expanded path
        )
    # ... continue building VM ...
```

- [ ] **Step 3C.2: Write discriminating test `test_build_hyp_recs_expanded_jit_fallback_on_cache_miss`**

```python
def test_build_hyp_recs_expanded_jit_fallback_on_cache_miss(tmp_path):
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    ohlcv_cache = MagicMock()
    ohlcv_cache.get_or_fetch.return_value = _planted_bars_df()
    import swing.web.chart_jit as mod
    renderer = MagicMock(return_value=b"<svg>jit</svg>")
    mod._RENDERERS["hyprec_detail"] = renderer
    try:
        vm = build_hyp_recs_expanded(
            conn, ohlcv_cache=ohlcv_cache, ticker="UCTT",
            pipeline_run_id=42, data_asof_date="2026-05-22", ...
        )
    finally:
        import importlib
        importlib.reload(mod)
    assert vm.hyprec_detail_chart_svg_bytes == b"<svg>jit</svg>"
    # ChartRender requires data_asof_date — verify it was threaded through to
    # the JIT helper (read-back from cache row written via refresh_chart_render).
    cached_row = conn.execute(
        "SELECT data_asof_date FROM chart_renders "
        "WHERE surface='hyprec_detail' AND ticker='UCTT' AND pipeline_run_id=42"
    ).fetchone()
    assert cached_row is not None
    assert cached_row[0] == "2026-05-22"


def test_build_hyp_recs_expanded_skips_jit_when_data_asof_date_missing(tmp_path):
    """Per R3 LOCK: JIT helper requires data_asof_date (ChartRender column);
    VM builder gates the fallback on data_asof_date is not None."""
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    ohlcv_cache = MagicMock()
    import swing.web.chart_jit as mod
    renderer = MagicMock(return_value=b"<svg>jit</svg>")
    mod._RENDERERS["hyprec_detail"] = renderer
    try:
        vm = build_hyp_recs_expanded(
            conn, ohlcv_cache=ohlcv_cache, ticker="UCTT",
            pipeline_run_id=42, data_asof_date=None, ...
        )
    finally:
        import importlib
        importlib.reload(mod)
    # No JIT fallback fires; no cache row written; bytes are None.
    assert vm.hyprec_detail_chart_svg_bytes is None
    renderer.assert_not_called()
```

- [ ] **Step 3C.3: Run test → expect PASS.**

- [ ] **Step 3C.4: Commit**

```bash
git add swing/web/view_models/dashboard.py tests/web/view_models/test_dashboard_hyp_recs_jit.py
git commit -m "feat(web): build_hyp_recs_expanded JIT fallback on cache miss (Item 5; T-T4.SB.3)"
```

**Sub-task 3D — Expanded-view template inline-SVG-suppresses-PNG-banner cascade**

- [ ] **Step 3D.1: Write failing test `test_hyprec_expanded_inline_svg_suppresses_banner`** at `tests/web/templates/test_expanded_chart_suppress_banner.py`:

```python
def test_hyprec_expanded_inline_svg_suppresses_banner(test_client):
    """Plant a hyp-rec with SVG bytes AND chart_reason='out-of-scope'.
    Response MUST contain SVG inline AND MUST NOT contain chart-unavailable banner."""
    _plant_hyp_rec_with_svg_and_out_of_scope_reason(...)
    resp = test_client.get("/hyp-recs/UCTT/expand")
    assert resp.status_code == 200
    assert b"<svg" in resp.content
    assert b'class="chart-unavailable"' not in resp.content


def test_watchlist_expanded_inline_svg_suppresses_banner(test_client):
    _plant_watchlist_expanded_with_svg(...)
    resp = test_client.get("/watchlist/UCTT/expand")
    assert resp.status_code == 200
    assert b"<svg" in resp.content
    assert b'class="chart-unavailable"' not in resp.content
```

- [ ] **Step 3D.2: Edit `swing/web/templates/partials/hypothesis_recommendations_expanded.html.j2:81-92`**

Replace the independent `{% if hyprec_detail_chart_svg_bytes %}...{% endif %}` block + independent `{% if chart_reason is none %}...{% endif %}` block with a single if-else cascade:

```jinja
{% if expanded.hyprec_detail_chart_svg_bytes %}
  <div class="hyprec-detail-chart">{{ expanded.hyprec_detail_chart_svg_bytes.decode('utf-8') | safe }}</div>
{% elif expanded.chart_reason is none and expanded.data_asof_date %}
  <img src="/charts/{{ expanded.data_asof_date }}/{{ expanded.ticker }}.png" alt="Chart {{ expanded.ticker }}">
{% elif expanded.chart_reason_message %}
  <div class="chart-unavailable" data-chart-reason="{{ expanded.chart_reason }}">{{ expanded.chart_reason_message }}</div>
{% endif %}
```

- [ ] **Step 3D.3: Edit `swing/web/templates/partials/watchlist_expanded.html.j2:36-43`** with symmetric cascade reading `expanded.watchlist_expanded_chart_svg_bytes`.

- [ ] **Step 3D.4: Extend `swing/web/view_models/watchlist.py:WatchlistExpandedVM`**

Add field:

```python
@dataclass(frozen=True)
class WatchlistExpandedVM:
    # ... existing fields ...
    watchlist_expanded_chart_svg_bytes: bytes | None = None
```

`build_watchlist_expanded` populates via JIT (mirrors Sub-task 3C).

- [ ] **Step 3D.5: Run tests → expect PASS.**

- [ ] **Step 3D.6: Commit**

```bash
git add swing/web/templates/partials/hypothesis_recommendations_expanded.html.j2 \
        swing/web/templates/partials/watchlist_expanded.html.j2 \
        swing/web/view_models/watchlist.py \
        tests/web/templates/test_expanded_chart_suppress_banner.py
git commit -m "refactor(web): expanded-view templates inline-SVG suppresses PNG fallback (Item 5; T-T4.SB.3)"
```

**Sub-task 3E — Pipeline `_step_charts` pre-gen scope reduction**

- [ ] **Step 3E.1: Write failing test `test_step_charts_pregen_scope_reduced_to_top5_no_hyprec_detail`** at `tests/pipeline/test_step_charts_pregen_scope_reduction.py`:

```python
def test_step_charts_pregen_scope_reduced_to_top5_no_hyprec_detail(tmp_path, monkeypatch):
    """Per spec §B.5 + OQ-5.3 LOCK: pre-gen writes ONLY market_weather +
    position_detail + dashboard-top-5 watchlist. NOT hyprec_detail. NOT
    top-10 watchlist."""
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _plant_pipeline_run_with_aplus_watchlist_top_10_open_positions(conn, ...)
    _step_charts(conn, ...)  # invoke pipeline step

    surfaces = list(conn.execute(
        "SELECT surface, COUNT(*) FROM chart_renders "
        "WHERE pipeline_run_id = ? GROUP BY surface",
        (run_id,),
    ))
    surface_counts = dict(surfaces)
    assert surface_counts.get("hyprec_detail", 0) == 0
    assert surface_counts.get("market_weather", 0) >= 1
    assert surface_counts.get("position_detail", 0) >= 1
    # Watchlist limited to top-5 (NOT top-10).
    assert surface_counts.get("watchlist_row", 0) <= 5
```

- [ ] **Step 3E.2: Edit `swing/pipeline/runner.py:_step_charts`**

Reduce pre-gen scope: REMOVE hyprec_detail loop (was A+-gated at line 2371; now JIT'd on expand). REDUCE watchlist_row loop from top-10 tag-aware to dashboard-top-5 visible-by-default.

Identify the existing top-10 selection (likely `tag_aware_top_n(watchlist, n=10)` or similar); change to `n=5`. The `top-5 visible-by-default` is the same set the dashboard renders without expand.

- [ ] **Step 3E.3: Run test → expect PASS.**

- [ ] **Step 3E.4: Commit**

```bash
git add swing/pipeline/runner.py tests/pipeline/test_step_charts_pregen_scope_reduction.py
git commit -m "refactor(pipeline): _step_charts pre-gen scope reduction to top-5 + drop hyprec_detail (Item 5 OQ-5.3; T-T4.SB.3)"
```

**Sub-task 3F — Option A re-run collision discriminating test (§1.5.3 amendment)**

- [ ] **Step 3F.1: Write `test_jit_writes_pipeline_run_id_matching_dashboard_anchor`** at `tests/web/test_chart_jit.py`:

```python
def test_jit_writes_pipeline_run_id_matching_dashboard_anchor(tmp_path):
    """Per spec §1.5.3 Option A LOCK: dashboard reader binds to one
    pipeline_run anchor (N); JIT writes match anchor N even if a fresher
    run (N+1) lands mid-session."""
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _plant_pipeline_run(conn, run_id=100, state="complete")
    # Dashboard render anchors to run_id=100.
    ohlcv_cache = MagicMock()
    ohlcv_cache.get_or_fetch.return_value = _planted_bars_df()
    import swing.web.chart_jit as mod
    mod._RENDERERS["hyprec_detail"] = MagicMock(return_value=b"<svg>v100</svg>")
    try:
        bytes_v100 = get_or_render_surface(
            conn=conn, ohlcv_cache=ohlcv_cache,
            surface="hyprec_detail", ticker="UCTT",
            pipeline_run_id=100,
        )
        # New pipeline_run lands; dashboard re-renders against run_id=101.
        _plant_pipeline_run(conn, run_id=101, state="complete")
        bytes_v101 = get_or_render_surface(
            conn=conn, ohlcv_cache=ohlcv_cache,
            surface="hyprec_detail", ticker="UCTT",
            pipeline_run_id=101,
        )
    finally:
        import importlib
        importlib.reload(mod)
    # Cache holds TWO rows — one per run_id. Old run_id NOT clobbered.
    rows = list(conn.execute(
        "SELECT pipeline_run_id, chart_svg_bytes FROM chart_renders "
        "WHERE surface='hyprec_detail' AND ticker='UCTT' "
        "ORDER BY pipeline_run_id"
    ))
    assert len(rows) == 2
    assert rows[0][0] == 100
    assert rows[1][0] == 101
```

- [ ] **Step 3F.2: Run test → expect PASS** (Option A semantic already encoded in helper's `pipeline_run_id` parameter).

- [ ] **Step 3F.3: Commit**

```bash
git add tests/web/test_chart_jit.py
git commit -m "test(web): Option A re-run collision invariant — JIT writes match dashboard anchor (Item 5; T-T4.SB.3)"
```

**Sub-task 3G — (Conditional per OQ-5.1 R4) Prune-chart-cache CLI**

- [ ] **Step 3G.1: Decision gate** — OQ-5.1 disposition is "R4 manual prune CLI + R1 default unbounded". Implementer ships the CLI as a `swing diagnose prune-chart-cache --older-than DAYS` subcommand. If the gate decision is to defer (acceptable per "if growth observed"), skip Sub-task 3G entirely and bank V2.

- [ ] **Step 3G.2: Write failing test + implementation + commit** (mirror Sub-task 1G pattern).

```python
# tests/cli/test_diagnose_prune_chart_cache.py
def test_diagnose_prune_chart_cache_deletes_rows_older_than_days(tmp_path):
    runner = CliRunner()
    db_path = tmp_path / "db.db"
    conn = sqlite3.connect(str(db_path))
    init_schema(conn)
    _plant_chart_render(conn, surface="hyprec_detail", ticker="OLD",
                        rendered_at="2025-01-01T00:00:00Z")
    _plant_chart_render(conn, surface="hyprec_detail", ticker="NEW",
                        rendered_at="2026-05-22T00:00:00Z")
    conn.close()
    result = runner.invoke(cli, [
        "diagnose", "prune-chart-cache",
        "--db", str(db_path), "--older-than", "365",
    ])
    assert result.exit_code == 0
    conn = sqlite3.connect(str(db_path))
    remaining = list(conn.execute("SELECT ticker FROM chart_renders"))
    assert remaining == [("NEW",)]
```

- [ ] **Step 3G.3: Implement + commit `feat(diagnostics): prune-chart-cache subcommand (Item 5 OQ-5.1 R4; T-T4.SB.3)`**.

**T-T4.SB.3 discriminating tests summary:**
- JIT helper: cache hit / cache miss + write-through / OHLCV-empty None / cache-collision renderer-once.
- Watchlist routes: collapse path uses JIT to repopulate thumbnail.
- Hyp-recs expanded VM: JIT fallback on cache miss.
- Templates: inline-SVG suppresses PNG + banner (both hyp-rec + watchlist expanded).
- Pipeline: `_step_charts` pre-gen scope reduced (no hyprec_detail; watchlist top-5).
- Option A invariant: JIT writes pipeline_run_id matching dashboard anchor.
- (Conditional) Prune-chart-cache CLI: deletes rows older than threshold.

**T-T4.SB.3 commit message templates (≥6 commits):**
- `feat(web): JIT cache-miss chart-render hook at swing/web/chart_jit.py (Item 5; T-T4.SB.3)`
- `feat(web): watchlist routes wire JIT chart-render hook (Item 5 + Item 6; T-T4.SB.3)`
- `feat(web): build_hyp_recs_expanded JIT fallback on cache miss (Item 5; T-T4.SB.3)`
- `refactor(web): expanded-view templates inline-SVG suppresses PNG fallback (Item 5; T-T4.SB.3)`
- `refactor(pipeline): _step_charts pre-gen scope reduction to top-5 + drop hyprec_detail (OQ-5.3; T-T4.SB.3)`
- `test(web): Option A re-run collision invariant — JIT writes match dashboard anchor (Item 5; T-T4.SB.3)`
- (Conditional) `feat(diagnostics): prune-chart-cache subcommand (Item 5 OQ-5.1 R4; T-T4.SB.3)`

**T-T4.SB.3 test budget:** +25-40 fast tests.

---

### §B.4 T-T4.SB.4 — Item 2 labeler subagent contract widening (additive `rule_criteria` + envelope `narrative` alias)

**Files:**
- Modify: `.claude/agents/pattern-labeler.md` — extend subagent prompt with `rule_criteria` array contract + 5 per-pattern-class example JSONs.
- Modify: `swing/patterns/labeling.py` — `SilverLabelResponse` dataclass + `__post_init__` validation + envelope persistence.
- Modify: `swing/cli.py:patterns_label_silver` — parse new key from subagent JSON.
- (Conditional OQ-2.2) Modify: `swing/cli.py` — `--corpus-all` flag for operator-paired relabel.
- Test: `tests/patterns/test_silver_label_response_rule_criteria.py` — new dataclass field + validation.
- Test: `tests/patterns/test_silver_label_envelope_narrative_alias.py` — alias key persistence.
- Test: `tests/web/view_models/patterns/test_exemplars_renders_new_rule_criteria.py` — VM parser → template integration.

**Sub-task 4A — Extend `SilverLabelResponse` dataclass + validation**

- [ ] **Step 4A.1: Write failing test `test_silver_label_response_validates_rule_criteria_shape`** at `tests/patterns/test_silver_label_response_rule_criteria.py`:

```python
import pytest
from swing.patterns.labeling import SilverLabelResponse


def _base(**overrides):
    base = dict(
        evaluation="confirmed", confidence="high",
        structural_evidence_json={"x": 1},
        geometric_evidence_narrative="A clean cup with a defined handle.",
    )
    base.update(overrides)
    return base


def test_silver_label_response_accepts_well_formed_rule_criteria():
    resp = SilverLabelResponse(**_base(rule_criteria=[
        {"name": "depth_pct_in_range", "status": "pass",
         "evidence_value": "22.5", "threshold": "15-35", "tolerance": None},
        {"name": "handle_duration_min", "status": "fail",
         "evidence_value": "3", "threshold": ">=5", "tolerance": None},
    ]))
    assert len(resp.rule_criteria) == 2


def test_silver_label_response_defaults_rule_criteria_to_none():
    assert SilverLabelResponse(**_base()).rule_criteria is None


def test_silver_label_response_rejects_rule_criteria_missing_name():
    with pytest.raises(ValueError, match="name"):
        SilverLabelResponse(**_base(rule_criteria=[
            {"status": "pass", "evidence_value": "x", "threshold": "y", "tolerance": None},
        ]))


def test_silver_label_response_rejects_rule_criteria_invalid_status():
    with pytest.raises(ValueError, match="status"):
        SilverLabelResponse(**_base(rule_criteria=[
            {"name": "x", "status": "maybe", "evidence_value": "x",
             "threshold": "y", "tolerance": None},
        ]))


def test_silver_label_response_rejects_rule_criteria_non_list():
    with pytest.raises(ValueError, match="rule_criteria"):
        SilverLabelResponse(**_base(rule_criteria={"not": "a list"}))
```

- [ ] **Step 4A.2: Run test → expect FAIL.**

- [ ] **Step 4A.3: Edit `swing/patterns/labeling.py:SilverLabelResponse`**

Add field + validation:

```python
@dataclass(frozen=True)
class SilverLabelResponse:
    evaluation: Literal["confirmed", "rejected"]
    confidence: Literal["high", "medium", "low"]
    structural_evidence_json: dict
    geometric_evidence_narrative: str
    rule_criteria: list[dict] | None = None  # NEW T-T4.SB.4

    _ALLOWED_STATUS: ClassVar[frozenset[str]] = frozenset({"pass", "fail"})

    def __post_init__(self) -> None:
        # ... existing validation preserved ...
        if self.rule_criteria is not None:
            if not isinstance(self.rule_criteria, list):
                raise ValueError(
                    "rule_criteria must be a list of dicts when provided "
                    f"(got {type(self.rule_criteria).__name__})"
                )
            for i, elem in enumerate(self.rule_criteria):
                if not isinstance(elem, dict):
                    raise ValueError(
                        f"rule_criteria[{i}] must be a dict (got {type(elem).__name__})"
                    )
                name = elem.get("name")
                if not (isinstance(name, str) and name):
                    raise ValueError(
                        f"rule_criteria[{i}].name must be a non-empty string"
                    )
                status = elem.get("status")
                if status not in self._ALLOWED_STATUS:
                    raise ValueError(
                        f"rule_criteria[{i}].status must be one of "
                        f"{sorted(self._ALLOWED_STATUS)} (got {status!r})"
                    )
```

- [ ] **Step 4A.4: Run test → expect PASS.**

- [ ] **Step 4A.5: Commit**

```bash
git add swing/patterns/labeling.py tests/patterns/test_silver_label_response_rule_criteria.py
git commit -m "feat(patterns): SilverLabelResponse.rule_criteria additive field + __post_init__ validation (Item 2; T-T4.SB.4)"
```

**Sub-task 4B — Envelope persistence + `narrative` alias key**

- [ ] **Step 4B.1: Write failing test `test_envelope_persists_rule_criteria_and_narrative_alias`** at `tests/patterns/test_silver_label_envelope_narrative_alias.py`:

```python
import json, sqlite3
from swing.patterns.labeling import SilverLabelResponse, _persist_silver_label


def test_envelope_persists_rule_criteria_and_narrative_alias(tmp_path):
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _plant_pattern_exemplar(conn, exemplar_id=1, ticker="AAA")
    response = SilverLabelResponse(
        evaluation="confirmed", confidence="high",
        structural_evidence_json={"base": "data"},
        geometric_evidence_narrative="A textbook cup with handle on AAA.",
        rule_criteria=[
            {"name": "cup_depth_pct", "status": "pass",
             "evidence_value": "22.0", "threshold": "15-35", "tolerance": None},
        ],
    )
    _persist_silver_label(conn, exemplar_id=1, response=response)
    (envelope_text,) = conn.execute(
        "SELECT labeler_evidence_json FROM pattern_exemplars WHERE id = 1"
    ).fetchone()
    envelope = json.loads(envelope_text)
    # Both keys per Codex R3 M#2 LOCK.
    assert envelope["narrative"] == "A textbook cup with handle on AAA."
    assert envelope["geometric_evidence_narrative"] == "A textbook cup with handle on AAA."
    assert envelope["rule_criteria"][0]["name"] == "cup_depth_pct"


def test_envelope_omits_rule_criteria_when_none_but_keeps_narrative_alias(tmp_path):
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _plant_pattern_exemplar(conn, exemplar_id=2, ticker="BBB")
    response = SilverLabelResponse(
        evaluation="confirmed", confidence="high",
        structural_evidence_json={"x": 1},
        geometric_evidence_narrative="Narrative.",
    )
    _persist_silver_label(conn, exemplar_id=2, response=response)
    (envelope_text,) = conn.execute(
        "SELECT labeler_evidence_json FROM pattern_exemplars WHERE id = 2"
    ).fetchone()
    envelope = json.loads(envelope_text)
    assert "rule_criteria" not in envelope
    # Narrative alias STILL populated.
    assert envelope["narrative"] == "Narrative."
    assert envelope["geometric_evidence_narrative"] == "Narrative."
```

- [ ] **Step 4B.2: Run test → expect FAIL.**

- [ ] **Step 4B.3: Edit `swing/patterns/labeling.py:_fire_claude_silver_label` envelope assembly (~lines 294-298)**

```python
labeler_evidence_json = {
    "evaluation": response.evaluation,
    "confidence": response.confidence,
    "structural_evidence_json": response.structural_evidence_json,
    # Preserved verbatim (back-compat regression anchor).
    "geometric_evidence_narrative": response.geometric_evidence_narrative,
    # NEW T-T4.SB.4: alias key per Codex R3 M#2 LOCK so existing
    # _parse_narrative_text reader lights up.
    "narrative": response.geometric_evidence_narrative,
}
if response.rule_criteria is not None:
    labeler_evidence_json["rule_criteria"] = response.rule_criteria
```

- [ ] **Step 4B.4: Run test → expect PASS.**

- [ ] **Step 4B.5: Commit**

```bash
git add swing/patterns/labeling.py tests/patterns/test_silver_label_envelope_narrative_alias.py
git commit -m "feat(patterns): labeler envelope persists rule_criteria + narrative alias key (Item 2 Codex R3 M#2; T-T4.SB.4)"
```

**Sub-task 4C — Subagent prompt extension at `.claude/agents/pattern-labeler.md`**

- [ ] **Step 4C.1: Read existing prompt** at `.claude/agents/pattern-labeler.md`.

- [ ] **Step 4C.2: Append `rule_criteria` contract section**

```markdown
### Output schema (UPDATED Phase 13 T4.SB)

In addition to the existing 4 fields (`evaluation`, `confidence`,
`structural_evidence_json`, `geometric_evidence_narrative`), emit an
OPTIONAL `rule_criteria` array. One element per criterion the labeler
evaluated; each element matches the VM-parser-pinned shape:

  {
    "name": "<criterion_name>",      // non-empty string (required)
    "status": "pass" | "fail",         // required
    "evidence_value": "<string>",    // optional
    "threshold": "<string>",         // optional
    "tolerance": "<string> | null"   // optional
  }

Example per pattern_class (implementer fills 5 examples — vcp,
flat_base, cup_with_handle, high_tight_flag, double_bottom_w — at
execution time by reading the detector criterion list at
`swing/patterns/<class>.py`).
```

- [ ] **Step 4C.3: Commit**

```bash
git add .claude/agents/pattern-labeler.md
git commit -m "feat(patterns): pattern-labeler subagent prompt — rule_criteria contract (Item 2; T-T4.SB.4)"
```

**Sub-task 4D — VM parser → template integration test (back-compat + fresh)**

- [ ] **Step 4D.1: Write `test_exemplars_template_renders_rule_criteria_for_fresh_silver`** + `test_legacy_exemplars_render_placeholder` at `tests/web/view_models/patterns/test_exemplars_renders_new_rule_criteria.py`:

```python
def test_exemplars_template_renders_rule_criteria_for_fresh_silver(tmp_path):
    """Per spec §B.2: VM parser + template already do the right thing;
    Item 2 fix is on the EMIT side. After Sub-tasks 4A + 4B land, a
    fresh-labeled exemplar's envelope has rule_criteria + narrative alias
    populated, so the template renders criterion_rows + narrative_text."""
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _plant_pattern_exemplar_with_silver_envelope(
        conn, exemplar_id=1, ticker="AAA",
        envelope={
            "rule_criteria": [
                {"name": "cup_depth_pct", "status": "pass",
                 "evidence_value": "22.0", "threshold": "15-35", "tolerance": None},
                {"name": "handle_dur_min", "status": "fail",
                 "evidence_value": "3", "threshold": ">=5", "tolerance": None},
            ],
            "narrative": "Cup with handle on AAA.",
        },
    )
    vm = build_exemplars_vm(conn)
    rendering = next(r for r in vm.renderings if r.ticker == "AAA")
    assert len(rendering.criterion_rows) == 2
    assert rendering.criterion_rows[0].name == "cup_depth_pct"
    assert rendering.narrative_text == "Cup with handle on AAA."


def test_legacy_exemplars_without_rule_criteria_render_placeholder(tmp_path):
    """Back-compat regression: 34 existing exemplars unchanged."""
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    _plant_pattern_exemplar_with_silver_envelope(
        conn, exemplar_id=1, ticker="OLD",
        envelope={"geometric_evidence_narrative": "Legacy narrative."},
    )
    vm = build_exemplars_vm(conn)
    rendering = next(r for r in vm.renderings if r.ticker == "OLD")
    assert rendering.criterion_rows == ()
    assert rendering.narrative_text is None
```

- [ ] **Step 4D.2: Run tests → expect PASS** (VM parser already reads `rule_criteria` + `narrative` keys; Sub-task 4B made the EMIT side match).

- [ ] **Step 4D.3: Commit**

```bash
git add tests/web/view_models/patterns/test_exemplars_renders_new_rule_criteria.py
git commit -m "test(patterns): exemplars template renders rule_criteria + narrative_text (Item 2 fresh + back-compat; T-T4.SB.4)"
```

**Sub-task 4E — (Conditional per OQ-2.2) `--corpus-all` operator-paired relabel CLI flag**

- [ ] **Step 4E.1: Decision gate** — OQ-2.2 LOCKED "two-pronged ship; operator decides at execution". Ship the flag.

- [ ] **Step 4E.2: Extend `swing/cli.py:patterns_label_silver`**

```python
@patterns.command("label-silver")
# ... existing options ...
@click.option("--corpus-all", is_flag=True, default=False,
    help="Relabel ALL existing pattern_exemplars rows via Path A labeler.")
def patterns_label_silver(corpus_all: bool, ...) -> None:
    # ... existing logic ...
    if corpus_all:
        click.echo("Relabel-corpus path: invoking Path A labeler against "
                   "all existing pattern_exemplars rows. This is slow + "
                   "operator-paired; CTRL-C is safe (per-exemplar commit).")
        # iterate pattern_exemplars rows; invoke Path A per exemplar
        # implementer fills loop body at execution time
```

- [ ] **Step 4E.3: Write smoke test (subagent mocked)**

```python
def test_patterns_label_silver_corpus_all_iterates_exemplars(monkeypatch, tmp_path):
    invocations = []
    def fake_fire(exemplar_id, **kwargs):
        invocations.append(exemplar_id)
        return SilverLabelResponse(
            evaluation="confirmed", confidence="high",
            structural_evidence_json={}, geometric_evidence_narrative="x",
            rule_criteria=[{"name": "c", "status": "pass",
                            "evidence_value": "", "threshold": "",
                            "tolerance": None}],
        )
    monkeypatch.setattr(
        "swing.patterns.labeling._fire_claude_silver_label", fake_fire,
    )
    runner = CliRunner()
    # Plant 3 exemplars in test DB ...
    result = runner.invoke(cli, ["patterns", "label-silver", "--corpus-all", ...])
    assert result.exit_code == 0
    assert len(invocations) == 3
```

- [ ] **Step 4E.4: Run test → expect PASS.**

- [ ] **Step 4E.5: Commit**

```bash
git add swing/cli.py tests/cli/test_patterns_label_silver_corpus_all.py
git commit -m "feat(cli): patterns-label-silver --corpus-all operator-paired relabel flag (Item 2 OQ-2.2; T-T4.SB.4)"
```

**T-T4.SB.4 discriminating tests summary:**
- Dataclass validation: well-formed accepted; missing `name` / invalid `status` (must be in `{"pass", "fail"}`) / non-list rejected; default `rule_criteria=None`.
- Envelope persistence: `narrative` alias + `rule_criteria` populated when present; alias still populated when rule_criteria absent.
- Template integration: fresh silver renders criterion_rows + narrative_text; legacy exemplars render placeholder unchanged.
- (Conditional) `--corpus-all` flag iterates exemplars.

**T-T4.SB.4 commit message templates (≥4 commits + 1 conditional):**
- `feat(patterns): SilverLabelResponse.rule_criteria additive field + __post_init__ validation (Item 2; T-T4.SB.4)`
- `feat(patterns): labeler envelope persists rule_criteria + narrative alias key (Item 2 Codex R3 M#2; T-T4.SB.4)`
- `feat(patterns): pattern-labeler subagent prompt — rule_criteria contract (Item 2; T-T4.SB.4)`
- `test(patterns): exemplars template renders rule_criteria + narrative_text (Item 2 fresh + back-compat; T-T4.SB.4)`
- (Conditional) `feat(cli): patterns-label-silver --corpus-all operator-paired relabel flag (OQ-2.2; T-T4.SB.4)`

**T-T4.SB.4 test budget:** +10-15 fast tests.

---

### §B.5 T-T4.SB.5 — Items 3 + 4 + 6 cosmetic/UX bundle (ONE Codex round per OQ-X.1)

**Files:**
- Modify: `swing/web/charts.py:render_market_weather_svg` + `:render_hyprec_detail_svg` — strip volume y-tick labels (Item 3).
- Modify: `swing/web/templates/partials/watchlist_row.html.j2:14` — delete lightning glyph (Item 4).
- Modify: `swing/web/templates/partials/watchlist_row.html.j2:9` — pivot to `chart_svg_bytes_for_row` param (Item 6 Option 6B).
- Modify: `swing/web/templates/watchlist.html.j2` — pass `chart_svg_bytes_for_row` to include (Item 6).
- Modify: `swing/web/templates/dashboard.html.j2` (or top-5 include site) — same (Item 6).
- Modify: `swing/web/routes/watchlist.py:watchlist_row` — passes `chart_svg_bytes_for_row` (OVERLAPS with T-T4.SB.3 Sub-task 3B; if T-T4.SB.5 dispatches BEFORE T-T4.SB.3, include the change here verbatim).
- Test: `tests/web/test_charts_volume_yticks_stripped.py` — Item 3.
- Test: `tests/web/test_watchlist_row_no_lightning_glyph.py` — Item 4.
- Test: `tests/web/test_watchlist_expand_collapse_preserves_thumbnail.py` — Item 6.

**Sub-task 5A — Item 3: strip volume y-tick labels**

- [ ] **Step 5A.1: Write failing test `test_render_market_weather_volume_y_ticks_stripped`** at `tests/web/test_charts_volume_yticks_stripped.py`:

```python
import matplotlib.pyplot as plt
from unittest.mock import patch
from swing.web.charts import render_market_weather_svg, render_hyprec_detail_svg


def test_render_market_weather_volume_y_ticks_stripped(planted_bars):
    """Per spec §B.3 + Codex R1 MINOR #1 LOCK: volume subplot y-tick
    LABELS empty list. Volume ylabel ("Volume") intentionally preserved.

    Note actual signature is `render_market_weather_svg(*, bars,
    trend_template_state)` — no `ticker` parameter."""
    captured = {}
    original_subplots = plt.subplots

    def spy(*args, **kwargs):
        fig, axes = original_subplots(*args, **kwargs)
        captured["axes"] = axes
        return fig, axes

    with patch("matplotlib.pyplot.subplots", side_effect=spy):
        render_market_weather_svg(bars=planted_bars, trend_template_state="stage_2")

    ax_vol = captured["axes"][1] if hasattr(captured["axes"], "__getitem__") else None
    if ax_vol is not None:
        labels = [t.get_text() for t in ax_vol.get_yticklabels()]
        assert labels == [] or all(not lbl for lbl in labels)


def test_render_hyprec_detail_volume_y_ticks_stripped(planted_bars):
    """Symmetric assertion. Signature:
    `render_hyprec_detail_svg(*, ticker, bars, pattern_evaluation=None)`."""
    captured = {}
    original_subplots = plt.subplots

    def spy(*args, **kwargs):
        fig, axes = original_subplots(*args, **kwargs)
        captured["axes"] = axes
        return fig, axes

    with patch("matplotlib.pyplot.subplots", side_effect=spy):
        render_hyprec_detail_svg(ticker="UCTT", bars=planted_bars,
                                 pattern_evaluation=None)

    ax_vol = captured["axes"][1] if hasattr(captured["axes"], "__getitem__") else None
    if ax_vol is not None:
        labels = [t.get_text() for t in ax_vol.get_yticklabels()]
        assert labels == [] or all(not lbl for lbl in labels)
```

Alternative assertion (if spy-on-`plt.subplots` proves brittle): grep the rendered SVG bytes near the volume subplot for absence of `<text>0</text>` / `<text>1e8</text>` substrings.

- [ ] **Step 5A.2: Run test → expect FAIL.**

- [ ] **Step 5A.3: Edit `swing/web/charts.py`**

In `render_market_weather_svg` after the existing `ax_vol.set_xticks([])` (~ line 364), add:

```python
    ax_vol.set_yticks([])
```

Similarly in `render_hyprec_detail_svg` after volume bar rendering (~ line 267-274):

```python
    ax_vol.set_yticks([])
```

- [ ] **Step 5A.4: Run test → expect PASS.**

- [ ] **Step 5A.5: Operator-witnessed gate flag** — visual verification of `/dashboard` post-fix (S2 gate); record in return report.

- [ ] **Step 5A.6: Commit**

```bash
git add swing/web/charts.py tests/web/test_charts_volume_yticks_stripped.py
git commit -m "fix(web): strip volume y-tick labels on market_weather + hyprec_detail charts (Item 3; T-T4.SB.5)"
```

**Sub-task 5B — Item 4: delete lightning glyph**

- [ ] **Step 5B.1: Write failing test `test_watchlist_row_omits_lightning_glyph`** at `tests/web/test_watchlist_row_no_lightning_glyph.py`:

```python
def test_watchlist_row_omits_lightning_glyph(test_client):
    """Plant ticker within 1% of entry_target (prior condition that
    triggered glyph). Assert glyph absent from response."""
    _plant_watchlist_entry(ticker="UCTT", entry_target=10.0)
    _plant_price(ticker="UCTT", price=9.95)
    resp = test_client.get("/watchlist/UCTT/row")
    assert resp.status_code == 200
    # Glyph absent in response text.
    assert "⚡" not in resp.text  # lightning bolt code point
```

- [ ] **Step 5B.2: Run test → expect FAIL** (glyph still rendered).

- [ ] **Step 5B.3: Edit `swing/web/templates/partials/watchlist_row.html.j2`**

Delete line 14 (the `{% if price and w.entry_target and price.price >= w.entry_target * 0.99 %}` block containing the glyph).

- [ ] **Step 5B.4: Run test → expect PASS.**

- [ ] **Step 5B.5: Commit**

```bash
git add swing/web/templates/partials/watchlist_row.html.j2 \
        tests/web/test_watchlist_row_no_lightning_glyph.py
git commit -m "fix(web): remove lightning glyph from watchlist row (Item 4; T-T4.SB.5)"
```

**Sub-task 5C — Item 6: partial-rewire (`chart_svg_bytes_for_row` explicit param; Option 6B)**

- [ ] **Step 5C.1: Write failing test `test_watchlist_expand_collapse_preserves_thumbnail`** at `tests/web/test_watchlist_expand_collapse_preserves_thumbnail.py`:

```python
def test_watchlist_expand_collapse_preserves_thumbnail(test_client):
    """Per spec §B.6: full-page render shows thumbnail; expand swaps to
    expanded view; collapse swaps back; thumbnail PERSISTS across all
    three render paths."""
    _plant_chart_render(surface="watchlist_row", ticker="UCTT",
                        pipeline_run_id=N, chart_svg_bytes=b"<svg>thumb</svg>")
    page = test_client.get("/watchlist")
    assert b"<svg>thumb</svg>" in page.content
    expand = test_client.get("/watchlist/UCTT/expand")
    assert expand.status_code == 200
    collapse = test_client.get("/watchlist/UCTT/row")
    assert collapse.status_code == 200
    assert b"<svg>thumb</svg>" in collapse.content
    assert b"watchlist-thumbnail" in collapse.content
```

- [ ] **Step 5C.2: Run test → expect FAIL pre-fix.**

- [ ] **Step 5C.3: Edit `swing/web/templates/partials/watchlist_row.html.j2` line 9**

Replace:

```jinja
{% set _thumb_bytes = vm.watchlist_chart_svg_bytes.get(w.ticker) if vm is defined and vm.watchlist_chart_svg_bytes else None %}
```

with:

```jinja
{% set _thumb_bytes = chart_svg_bytes_for_row if chart_svg_bytes_for_row is defined else None %}
```

- [ ] **Step 5C.4: Edit `swing/web/templates/watchlist.html.j2`**

In the loop that iterates `vm.entries` and includes the row partial:

```jinja
{% for w in vm.entries %}
  {% set chart_svg_bytes_for_row = vm.watchlist_chart_svg_bytes.get(w.ticker) if vm.watchlist_chart_svg_bytes else None %}
  {% include "partials/watchlist_row.html.j2" %}
{% endfor %}
```

- [ ] **Step 5C.5: Edit `swing/web/templates/dashboard.html.j2` (or the dashboard top-5 watchlist include site)** with the same `{% set chart_svg_bytes_for_row %}` pattern.

- [ ] **Step 5C.6: Verify `swing/web/routes/watchlist.py:watchlist_row`** passes `chart_svg_bytes_for_row` in its template context dict (T-T4.SB.3 Sub-task 3B already does this; if T-T4.SB.5 dispatches first, include the route change verbatim here).

- [ ] **Step 5C.7: Run test → expect PASS.**

- [ ] **Step 5C.8: Commit**

```bash
git add swing/web/templates/partials/watchlist_row.html.j2 \
        swing/web/templates/watchlist.html.j2 \
        swing/web/templates/dashboard.html.j2 \
        tests/web/test_watchlist_expand_collapse_preserves_thumbnail.py
git commit -m "fix(web): watchlist row partial-rewire — chart_svg_bytes_for_row explicit param (Item 6 Option 6B; T-T4.SB.5)"
```

**T-T4.SB.5 discriminating tests summary:**
- Volume y-tick labels stripped (market_weather + hyprec_detail).
- Lightning glyph absent from watchlist row HTML.
- Expand-collapse-expand sequence preserves thumbnail bytes verbatim.

**T-T4.SB.5 commit message templates (3 commits):**
- `fix(web): strip volume y-tick labels on market_weather + hyprec_detail charts (Item 3; T-T4.SB.5)`
- `fix(web): remove lightning glyph from watchlist row (Item 4; T-T4.SB.5)`
- `fix(web): watchlist row partial-rewire — chart_svg_bytes_for_row explicit param (Item 6 Option 6B; T-T4.SB.5)`

**T-T4.SB.5 test budget:** +8-12 fast tests.

---

### §B.6 T-T4.SB.6 — Closer + Phase 13 FULLY CLOSED marker + triage-agenda artifact (§1.5.2)

**Files:**
- Create: `tests/integration/test_phase13_t4_sb_closer_e2e.py` — 1 fast E2E.
- Create: `docs/phase13-closer-next-phase-triage.md` — post-T4.SB triage agenda stub per §1.5.2.
- Modify: `tests/metrics/test_phase13_t4_sb_cross_bundle_pin_row_13.py` — un-SKIP (if planted SKIPped at T-T4.SB.2).
- Modify: `CLAUDE.md` — current-state line refresh (Phase 13 12 of 12 SHIPPED).
- Modify: `docs/orchestrator-context.md` — "Currently in-flight work" Phase 13 SHIPPED + "Recent decisions and framings" T4.SB closure entry.
- Modify: `docs/cycle-checklist.md` — quarterly diagnostic re-run reminders.
- Modify: `docs/phase3e-todo.md` — Phase 13 closure top entry; promote any deferred items.
- Modify: `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` — append row 13 to §H.3 cross-bundle pin table.

**Sub-task 6A — Fast E2E covering operator-witnessed flow**

- [ ] **Step 6A.1: Write `tests/integration/test_phase13_t4_sb_closer_e2e.py`**

```python
"""Phase 13 T4.SB closer fast E2E.

Covers: pipeline run + dashboard render + hyp-rec expand (JIT chart hit)
+ watchlist collapse (thumbnail preserved) + hyp-progress card non-zero
on suffix-bearing labels.
"""
from fastapi.testclient import TestClient


def test_phase13_t4_sb_closer_full_dashboard_flow(test_app, planted_db):
    # Plant: 1 hypothesis registry entry, N closed trades with suffix
    # labels, 1 watchlist entry UCTT, market_weather + hyprec_detail
    # chart_renders rows for current pipeline_run.
    _plant_phase13_closer_fixture(planted_db)
    with TestClient(test_app) as client:
        # 1. Dashboard render — top-level OK
        dash = client.get("/dashboard")
        assert dash.status_code == 200
        # 2. Hyp-progress card non-zero (Item 7 fix)
        assert b"Sub-A+ VCP-not-formed" in dash.content
        assert b">0<" not in _hyp_progress_n_closed_section(dash.content)
        # 3. Hyp-rec expand triggers JIT chart hit (Item 5)
        expand = client.get("/hyp-recs/UCTT/expand")
        assert expand.status_code == 200
        assert b"<svg" in expand.content
        assert b'class="chart-unavailable"' not in expand.content
        # 4. Watchlist collapse preserves thumbnail (Item 6)
        client.get("/watchlist/UCTT/expand")
        collapse = client.get("/watchlist/UCTT/row")
        assert collapse.status_code == 200
        assert b"watchlist-thumbnail" in collapse.content
        # 5. Item 3: dashboard market_weather chart has no volume y-tick labels
        #    (asserted by absence of '<text>1e8' fragment in serialized SVG)
        assert b"<text>1e8</text>" not in dash.content
        # 6. Item 4: no lightning glyph anywhere on dashboard.
        assert "⚡".encode() not in dash.content
```

Run: `python -m pytest tests/integration/test_phase13_t4_sb_closer_e2e.py -v`
Expected: PASS.

- [ ] **Step 6A.2: Commit**

```bash
git add tests/integration/test_phase13_t4_sb_closer_e2e.py
git commit -m "test(integration): Phase 13 T4.SB closer E2E — pipeline + dashboard + JIT + Item 7 fix (T-T4.SB.6)"
```

**Sub-task 6B — Cross-bundle pin row 13 promotion**

- [ ] **Step 6B.1: Verify pin file at `tests/metrics/test_phase13_t4_sb_cross_bundle_pin_row_13.py` is GREEN.**

Run: `python -m pytest tests/metrics/test_phase13_t4_sb_cross_bundle_pin_row_13.py -v`
Expected: PASS for all 4 parametrized surfaces (per §B.2 Sub-task 2F).

- [ ] **Step 6B.2: Append row 13 to Phase 13 main plan §H.3**

Edit `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` §H.3 cross-bundle pin table, append:

```
| 13 | hypothesis_label delimiter-aware match invariant 4 surfaces | tests/metrics/test_phase13_t4_sb_cross_bundle_pin_row_13.py | T-T4.SB.2 plant + T-T4.SB.6 promote | GREEN |
```

- [ ] **Step 6B.3: Commit**

```bash
git add docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md
git commit -m "docs(phase13): plan §H.3 row 13 — delimiter-aware match invariant cross-bundle pin (T-T4.SB.6)"
```

**Sub-task 6C — Triage-agenda artifact stub (§1.5.2)**

- [ ] **Step 6C.1: Write `docs/phase13-closer-next-phase-triage.md`**

```markdown
# Phase 13 Closer — Next-Phase Triage Agenda

**Status:** STUB landed at T-T4.SB.6 SHIPPED. Operator-paired triage
session driven by T-T4.SB.1 sensitivity-harness OUTPUT.

## Decision points

1. **Path selection per OQ-CL.2 (§1.5.2 deferred disposition):**
   - **Path A** — Phase 14 (operator-defined operational scope).
   - **Path B** — Applied Research focus per V2.1 §X tranche progression
     (first method-record selection from `research/phase-0-tasks.md`
     "Next" section, now containing the A+-like-indicators entry
     promoted at T-T4.SB.1).
   - **Path C** — Combination (Phase 14 + research-branch concurrent
     per V2.1 §V branch posture).

2. **Inputs:**
   - Operator runs `swing diagnose aplus-sensitivity --eval-runs 63`
     against own DB → reviews CSV + markdown at `exports/diagnostics/`.
   - Findings answer: "which A+ criterion thresholds, if loosened, would
     materially increase A+ pipeline volume?"
   - If concentration in 1-2 criteria → threshold-loosening cfg-policy
     proposals candidate for Phase 14 (or for a research-branch method
     record validating the loosening).
   - If distributed → broader research-branch sweep warranted.

3. **OQ-CL.3 — research-branch first-method-record selection meeting:**
   - Scheduled separately post-T4.SB-SHIPPED (operator-paired session).
   - Inputs: sensitivity-harness output + 8 candidate A+-like indicators
     in `research/phase-0-tasks.md`.

## Cross-references

- T-T4.SB.1 deliverables:
  - `research/harness/aplus_sensitivity/` (harness modules).
  - `research/studies/aplus-criterion-sensitivity-2026-05-22.md` (study writeup; findings TBD).
  - `research/method-records/aplus-criteria-calibration.md` (method record stub).
  - `exports/diagnostics/aplus-sensitivity-<ISO>.{md,csv}` (operator-run output).
- T-T4.SB.2 deliverables: metrics wiring audit live; Option 7C fix at 4 surfaces.
- T-T4.SB.3/4/5/6: see T4.SB return report at `docs/phase13-t4-sb-return-report.md`.
```

- [ ] **Step 6C.2: Commit**

```bash
git add docs/phase13-closer-next-phase-triage.md
git commit -m "docs(phase13): closer next-phase triage agenda stub (§1.5.2; T-T4.SB.6)"
```

**Sub-task 6D — CLAUDE.md + orchestrator-context + cycle-checklist + phase3e-todo updates**

- [ ] **Step 6D.1: Edit CLAUDE.md current-state line**

Replace `Phase 13 sub-bundle ship count: 11 of 11 SHIPPED — T4.SB closer arc IN-FLIGHT` with `Phase 13 sub-bundle ship count: 12 of 12 SHIPPED — Phase 13 FULLY CLOSED 2026-05-22 PM #2`.

Update the `*Note 2026-05-22 PM #N` paragraph with the T4.SB closer announcement, citing the closer commit + the triage-agenda stub.

Add any NEW gotchas surfaced by Codex chains during T-T4.SB.1..T-T4.SB.5.

- [ ] **Step 6D.2: Edit `docs/orchestrator-context.md`**

- "Currently in-flight work" → "T4.SB SHIPPED 2026-05-22; Phase 13 FULLY CLOSED. Next-phase triage agenda at `docs/phase13-closer-next-phase-triage.md`."
- "Recent decisions and framings" → append entry: "Phase 13 closure at T-T4.SB.6 ship; sensitivity harness placed under `research/harness/aplus_sensitivity/` per §1.5.4; Item 7 Option 7C delimiter-aware match landed at 4 surfaces; Item 5 JIT cache-miss helper at `swing/web/chart_jit.py`."
- "Lessons captured" → append any new gotchas from Codex chains.

- [ ] **Step 6D.3: Edit `docs/cycle-checklist.md`**

Add entry under quarterly diagnostics:

```markdown
## Quarterly diagnostics (Phase 13 T4.SB)

- Re-run `swing diagnose aplus-sensitivity --eval-runs 63 --output-dir exports/diagnostics/`
  to detect criterion calibration drift. Archive prior outputs to
  `exports/diagnostics/archive/` before re-running.
- Re-run `swing diagnose metrics-wiring --output exports/diagnostics/metrics-wiring-audit-<ISO>.md`
  to detect wiring drift on metric surfaces.
- Operator reviews output + banks V2 candidates if drift surfaces.
```

- [ ] **Step 6D.4: Edit `docs/phase3e-todo.md`**

- Add top entry: "Phase 13 SHIPPED 2026-05-22; FULLY CLOSED. T4.SB closer at <commit_sha>. Next: post-T4.SB triage agenda at `docs/phase13-closer-next-phase-triage.md`."
- Mark the 7 T4.SB items 1-7 as `[x] SHIPPED at T-T4.SB.N (commit <sha>)`.

- [ ] **Step 6D.5: Run ruff sweep**

Run: `ruff check swing/ research/`
Expected: 0 E501 violations.

If any new violations, fix them inline.

- [ ] **Step 6D.6: Run full fast suite to verify baseline**

Run: `python -m pytest -m "not slow" -q`
Expected: PASS with ~5750-5795 fast tests (per §F projection).

- [ ] **Step 6D.7: Commit**

```bash
git add CLAUDE.md docs/orchestrator-context.md docs/cycle-checklist.md docs/phase3e-todo.md
git commit -m "docs(phase13): T4.SB SHIPPED — Phase 13 FULLY CLOSED (12 of 12 sub-bundles) (T-T4.SB.6)"
```

**T-T4.SB.6 discriminating tests summary:**
- Fast E2E: dashboard render + hyp-progress card non-zero + JIT chart hit + collapse preserves thumbnail + Items 3/4 cosmetic + Item 7 fix all live in one flow.
- Cross-bundle pin row 13: GREEN at all 4 parametrized surfaces.

**T-T4.SB.6 commit message templates (4 commits):**
- `test(integration): Phase 13 T4.SB closer E2E — pipeline + dashboard + JIT + Item 7 fix (T-T4.SB.6)`
- `docs(phase13): plan §H.3 row 13 — delimiter-aware match invariant cross-bundle pin (T-T4.SB.6)`
- `docs(phase13): closer next-phase triage agenda stub (§1.5.2; T-T4.SB.6)`
- `docs(phase13): T4.SB SHIPPED — Phase 13 FULLY CLOSED (12 of 12 sub-bundles) (T-T4.SB.6)`

**T-T4.SB.6 test budget:** +1-3 fast tests + 1 fast E2E.

---

## §C Cross-task dependencies + concurrent-dispatch graph

```
T-T4.SB.1  ──── T-T4.SB.2  ──── T-T4.SB.6
   ↓                              ↑
T-T4.SB.3 ─────────────────────────┤
   ↓                              │
T-T4.SB.5 ─────────────────────────┤
                                  │
T-T4.SB.4 ─────────────────────────┘ (concurrent with .2/.3/.5)
```

**Sequential dependencies (BINDING):**
- T-T4.SB.2 consumes T-T4.SB.1's `swing diagnose metrics-wiring` audit output → SEQUENTIAL after T-T4.SB.1.
- T-T4.SB.5 Item 6 invokes T-T4.SB.3's `get_or_render_surface` JIT helper → SEQUENTIAL after T-T4.SB.3.
- T-T4.SB.6 consumes pin row 13 (planted at T-T4.SB.2) + closer-arc artifacts → SEQUENTIAL last.

**Concurrent-dispatch potential:**
- T-T4.SB.4 (labeler contract widening) is independent of all others → CAN dispatch concurrent with T-T4.SB.2, T-T4.SB.3, T-T4.SB.5 once T-T4.SB.1 ships.
- T-T4.SB.3 (Item 5 architecture) is independent of T-T4.SB.2 → CAN dispatch concurrent (but T-T4.SB.5 Sub-task 5C depends on T-T4.SB.3 Sub-task 3A; do not interleave).

**Recommended dispatch sequence (conservative, sequential):**

1. T-T4.SB.1 (Item 1 sensitivity harness + Item 7 Phase 1 diagnostic).
2. T-T4.SB.2 (Item 7 broader audit + canonical fix + cross-bundle pin row 13 plant).
3. T-T4.SB.3 (Item 5 architecture).
4. T-T4.SB.4 (Item 2 labeler contract widening) — OR concurrent with .2 or .3.
5. T-T4.SB.5 (Items 3+4+6 cosmetic/UX bundle).
6. T-T4.SB.6 (Closer + Phase 13 FULLY CLOSED marker).

**Wall-clock savings estimate:** If T-T4.SB.4 dispatches concurrent with .2 + .3, ~1-2 hours saved on a 6-hour total. Conservative sequential ~6 hours; concurrent (.2 || .3 || .4 + then .5 + .6) ~4.5 hours. Operator decides per implementer-capacity at dispatch time.

**Verification ordering note (per spec §G.2 Codex R1 MINOR #3):** code dependencies as above. Operator-witnessed gate verification of Item 5's hyp-rec chart wiring is EASIER to validate after Item 7's hypothesis-progress fix lands (suffix-bearing labels easier to debug with a working progress card). Recommend: sequence operator-witnessed gate verification of Item 5 chart wiring AFTER Item 7 hyp-progress fix is verified GREEN.

---

## §D Investigation outputs format

### §D.1 Item 1 sensitivity harness output

**Files:**
- `exports/diagnostics/aplus-sensitivity-<ISO>.csv` — sensitivity matrix.
- `exports/diagnostics/aplus-sensitivity-<ISO>.md` — markdown analysis.

**CSV schema (9 columns; per R3 + R4 LOCK with Kind in position 2):**
```
variable_name,kind,sweep_point,aplus_count,watch_count,skip_count,excluded_count,delta_aplus,delta_watch
trend_template.min_passes,gate,5,12,80,4908,0,+11,+70
trend_template.min_passes,gate,6,4,70,4926,0,+3,+60
trend_template.min_passes,gate,7,1,10,4989,0,+0,+0
vcp.adr_min_pct,threshold_multiplicative,2.5,1,10,4989,0,+0,+0
vcp.adr_min_pct,threshold_multiplicative,5.0,1,10,4989,0,+0,+0
...
```

(Threshold-kind rows always carry `delta_aplus=0` + `delta_watch=0` per V1 parity-preserving semantic; only gate-kind rows produce non-zero deltas.)

**Markdown layout** (see Sub-task 1C.3 output formatter):
- Title + ISO timestamp.
- Eval-runs window + range + total candidates.
- Sensitivity matrix table: `| Variable | Kind | Sweep point | A+ | Watch | Skip | Excluded | dA+ | dWatch |`.
- Notes section MUST contain (a) cross-coupling caveat (1D only), (b) parity-at-current-value invariant, (c) V1 LIMITATION paragraph explicitly stating threshold-variable deltas are intentionally ZERO and gate-variable deltas are real, (d) study writeup pointer.

### §D.2 Item 7 metrics-wiring-audit output

**File:** `exports/diagnostics/metrics-wiring-audit-<ISO>.md`.

**Markdown layout:**
- Title + ISO timestamp + count of surfaces audited.
- Per-surface table (Surface | File:line | Match strategy | State filter | Join keys | Operator DB count | Disposition).
- Per-surface notes section (reproduction recipe / fix path for WIRING DEFECT; V2 dependency citation for FALSE-ZERO RISK).

### §D.3 Output retention + cycle-checklist integration

Outputs committed to `exports/diagnostics/` (not under `docs/` — operational artifacts). Cycle-checklist gets quarterly re-run reminder (per Sub-task 6D.3); operator archives prior outputs to `exports/diagnostics/archive/` pre-merge.

---

## §E Cross-bundle pin row 13 (per spec §E recommendation)

**Pin row 13b — hypothesis-label delimiter-aware-match-strategy invariant** (planted at T-T4.SB.2; promoted GREEN at T-T4.SB.6).

**Pin file:** `tests/metrics/test_phase13_t4_sb_cross_bundle_pin_row_13.py`.

**Parametrize over 4 surfaces:**
1. `swing.metrics.cohort.list_trades_for_cohort`
2. `swing.metrics.cohort.count_per_cohort`
3. `swing.web.view_models.metrics.hypothesis_progress_card.build_hypothesis_progress_card_vm` (transitive via `list_closed_trades_for_cohort`)
4. `swing.journal.stats.compute_hypothesis_progress_breakdown` (CLI path; transitive via shared `_label_matches_hypothesis`)

**Plant/promote schedule:**
- **T-T4.SB.2 Sub-task 2F**: PLANT pin file with all 4 parametrizations. After T-T4.SB.2 Sub-tasks 2A-2D land (helper + cohort rewires + dashboard test), the pin SHOULD PASS already (no SKIP needed). If timing forces a stub-then-fill pattern, the pin starts `@pytest.mark.skip(reason='planted; promoted at T-T4.SB.6')` and un-SKIPs at T-T4.SB.6.
- **T-T4.SB.6 Sub-task 6B**: verify GREEN; append row 13 to Phase 13 main plan §H.3.

**Pin invariant (BINDING contract):** for a trade with `hypothesis_label = 'Sub-A+ VCP-not-formed (watch); failed: proximity_20ma'`, every one of the 4 surfaces MUST count it as 1 toward the cohort named `'Sub-A+ VCP-not-formed'` and MUST NOT count it toward `'A+ baseline'` or any prefix-extension name like `'Sub-A+ VCP-not-formedness'`.

**Candidate pin row 13a — chart_renders retention policy invariant** — DO NOT PLANT (per spec §E.1; R4 manual prune CLI disposition is operator-triage-deferred; banked V2).

---

## §F Test scope projection

### §F.1 Baseline + projected delta

Baseline: ~5670 fast tests at main HEAD `637f156`. Projected T4.SB delta:

| Task | Fast tests | Slow tests | Fast E2E | Cumulative |
|---|---|---|---|---|
| T-T4.SB.1 | +30-40 | 0 | 0 | ~5700-5710 |
| T-T4.SB.2 | +15-25 | 0 | 0 | ~5715-5735 |
| T-T4.SB.3 | +25-40 | 0 | 0 | ~5740-5775 |
| T-T4.SB.4 | +10-15 | 0 | 0 | ~5750-5790 |
| T-T4.SB.5 | +8-12 | 0 | 0 | ~5758-5802 |
| T-T4.SB.6 | +1-3 | 0 | +1 | ~5760-5805 + 1 E2E |

**Projected baseline at T4.SB SHIPPED: ~5760-5805 fast + 1 fast E2E** (within brief §1.5.5 +60-160 range).

### §F.2 Slow-test discipline

Slow tests UNCHANGED. ZERO new Schwab API calls (L2 LOCK preserved). No slow yfinance E2E added. The 1 new fast E2E at T-T4.SB.6 mirrors T2.SB6c precedent.

### §F.3 Ruff discipline

Baseline 0 E501 violations. T4.SB preserves; per-task verification at execution time. T-T4.SB.6 Sub-task 6D.5 runs final sweep.

### §F.4 Test marker convention

New tests under:
- `tests/diagnostics/` (NEW; Items 1 + 7 diagnostics).
- `tests/research/` (NEW; sensitivity harness).
- `tests/cli/` (existing; `diagnose` subcommand tests).
- `tests/web/` + `tests/web/routes/` + `tests/web/templates/` + `tests/web/view_models/patterns/` (existing).
- `tests/metrics/` (existing; cohort + helper + pin row 13).
- `tests/patterns/` (existing; labeler contract).
- `tests/pipeline/` (existing; `_step_charts` scope reduction).
- `tests/integration/` (existing; closer E2E).

No marker drift; all new tests default to fast suite.

---

## §G Per-task acceptance criteria (lift from §B per-task summaries)

### §G.1 T-T4.SB.1
- `swing diagnose aplus-sensitivity` runs end-to-end against operator DB; emits CSV + markdown to `exports/diagnostics/`.
- `swing diagnose metrics-wiring` emits audit table; ASCII-clean.
- Variable enumeration >= 10 variables; current-value parity invariant holds.
- 30-40 new fast tests GREEN.
- `research/harness/aplus_sensitivity/` complete (variables + sweep + output + run); method record + study stubs + phase-0-tasks promotion committed.

### §G.2 T-T4.SB.2
- 3-rule delimiter-aware match helper (Python + SQL) shipped at `swing/metrics/label_match.py`; SQL helper returns `(fragment, [raw_lowered, escaped, escaped])`.
- `list_trades_for_cohort` + `count_per_cohort` consume helper; orphan-fallback preserved.
- Dashboard hyp-progress card shows non-zero `n_closed` for suffix-bearing cohorts.
- Cross-bundle pin row 13 GREEN at all 4 parametrized surfaces.
- Registered-hypothesis-name non-overlap invariant test added (Codex R5 MIN#2).
- 15-25 new fast tests GREEN.

### §G.3 T-T4.SB.3
- `swing/web/chart_jit.py:get_or_render_surface` shipped; cache hit / miss / OHLCV-empty / F6 / cache-collision contracts upheld.
- Expanded views inline-SVG suppresses PNG + banner.
- `_step_charts` pre-gen scope reduced (no `hyprec_detail`; watchlist top-5).
- Option A re-run collision invariant test GREEN.
- (Conditional) Prune-chart-cache CLI shipped if OQ-5.1 R4 elected at execution time.
- 25-40 new fast tests GREEN.

### §G.4 T-T4.SB.4
- `SilverLabelResponse.rule_criteria` field added; `__post_init__` validation against the VM-parser-pinned per-element shape `{name: non-empty str, status: 'pass'|'fail'}` (plus optional `evidence_value`, `threshold`, `tolerance`).
- Envelope persists `rule_criteria` + `narrative` alias key.
- `geometric_evidence_narrative` PRESERVED VERBATIM (back-compat anchor test passes).
- Subagent prompt extended with `rule_criteria` contract + 5 per-pattern-class examples.
- Template renders criterion_rows + narrative_text for fresh silver; legacy exemplars render placeholder.
- (Conditional) `--corpus-all` flag shipped.
- 10-15 new fast tests GREEN.

### §G.5 T-T4.SB.5
- Volume y-tick labels stripped on `market_weather` + `hyprec_detail` SVGs.
- Lightning glyph absent from watchlist row HTML.
- Watchlist expand-collapse preserves thumbnail bytes (Option 6B partial-rewire).
- 8-12 new fast tests GREEN.

### §G.6 T-T4.SB.6
- Fast E2E covering operator-witnessed flow PASSES.
- Cross-bundle pin row 13 GREEN (un-SKIPped if planted SKIPped at .2).
- Phase 13 main plan §H.3 row 13 appended.
- Triage-agenda artifact at `docs/phase13-closer-next-phase-triage.md` committed.
- CLAUDE.md / orchestrator-context / cycle-checklist / phase3e-todo updated.
- Phase 13 sub-bundle ship count = 12 of 12 announced.
- Full fast suite GREEN (~5760-5805 fast).
- Ruff 0 E501.

---

## §H Dispatch sequence + concurrent-dispatch graph

### §H.1 Recommended dispatch sequence (sequential, conservative)

```
T-T4.SB.1 → T-T4.SB.2 → T-T4.SB.3 → T-T4.SB.4 → T-T4.SB.5 → T-T4.SB.6
```

Per spec §G.2 + §H — 6 sub-bundles in sequence; ~6 hours operator-paced.

### §H.2 Concurrent-dispatch alternative

```
T-T4.SB.1  ─┐
            ├─ T-T4.SB.2  ─┐
            ├─ T-T4.SB.3  ─┼─→ T-T4.SB.5 → T-T4.SB.6
            └─ T-T4.SB.4  ─┘
```

T-T4.SB.4 + T-T4.SB.3 + T-T4.SB.2 dispatchable concurrent after T-T4.SB.1; T-T4.SB.5 sequential after T-T4.SB.3 (Item 6 invokes JIT helper); T-T4.SB.6 sequential last.

Wall-clock savings: ~1.5 hours on a 6-hour total.

### §H.3 Codex chain expectations per task

Per spec §H.2-3 + brief §H.2 — writing-plans chain expected 3-5 rounds; executing-plans chain expected 3-5 rounds per task. Pre-Codex 7-expansion + 4 NEW candidate refinements (Expansions #4 SQL column + #8 SQL unit + #9 form-render anchor lifecycle + #10 NEW architecture-location 5-sub-discipline) BINDING for 29th cumulative C.C lesson #6 validation.

### §H.4 Operator-witnessed gate (post-merge)

**S1 (inline):** fast pytest + ruff + schema-unchanged-at-v21.
**S2 (browser):** `/dashboard` confirm:
- Market-weather chart has no volume y-axis labels (Item 3).
- No lightning glyph on watchlist (Item 4).
- Watchlist expand-collapse preserves thumbnail (Item 6).
- Sub-A+ hyp-rec expand renders chart inline (Item 5 JIT).
- Hyp-progress card non-zero for "Sub-A+ VCP-not-formed" cohort (Item 7 fix).
**S3 (CLI):** `swing diagnose aplus-sensitivity --eval-runs 63` produces sensitivity matrix; operator reviews + decides next-phase path per `docs/phase13-closer-next-phase-triage.md` (Item 1).
**S4 (CLI):** `swing diagnose metrics-wiring` audit table; operator reviews dispositions (Item 7 broader audit).
**S5 (CLI):** `swing patterns label-silver --pattern-class vcp ...` invocation with new contract; new keys persisted (Item 2; operator-paired re-label-corpus V2-banked).

### §H.5 Post-merge housekeeping (orchestrator-side)

Mirrors T2.SB6c precedent:
- `--no-ff` merge of `phase13-t4-sb-closer` (or per-task branches) to `main`.
- Return report at `docs/phase13-t4-sb-return-report.md`.
- CLAUDE.md current-state line refresh.
- Orchestrator-context current-state + recent-decisions refresh.
- Phase 13 main plan §H.3 row 13 GREEN.
- Cycle-checklist updated.

---

## §I Forward-binding lessons inherited (BINDING for executing-plans phase)

### §I.1 Cumulative gotchas (CLAUDE.md) applicable to T4.SB

ESPECIALLY relevant — per dispatch brief §0 + §3.2:

1. **Architecture-location audit + 4 sub-disciplines (NEW gotcha #14; Expansion #10 candidate BINDING)** — T4.SB brainstorming banking. Apply per task: T-T4.SB.3 chart_jit.py NEW module (sub-discipline a wrong-module placement); T-T4.SB.4 envelope alias (sub-discipline b template-VM-emit triangulation); T-T4.SB.3 hyprec_detail surface name LOCK + renderer-kwargs uniformity (sub-discipline c cache-key+kwargs); T-T4.SB.2 SQL LIKE binding asymmetry (sub-discipline d); T-T4.SB.2 count_per_cohort orphan-preservation (sub-discipline e).
2. **SQL aggregation UNIT audit (Expansion #8 BINDING)** — T-T4.SB.2 SQL skeletons must enumerate per-aggregation unit + DISTINCT need + LIMIT correctness.
3. **Form-render anchor lifecycle audit (Expansion #9 BINDING)** — T4.SB introduces NO new hidden form anchors; gotcha applies if Item 5 surfaces a need (e.g., a chart-scope POST handler — V1 NOT scoped).
4. **HTMX OOB-swap partials drift gotcha** — DIRECTLY APPLIES to Item 6. The Option 6B partial-rewire uses an EXPLICIT `chart_svg_bytes_for_row` template parameter rather than `vm.foo` dereference; sub-task 5C closes the drift family.
5. **Matplotlib mathtext gotcha** — applies to Item 3 chart-rendering work. The fix REMOVES tick labels (no new mathtext characters introduced); verification = string-equality on absence.
6. **Windows cp1252 stdout safety** — applies to Item 1 + Item 7 + Item 5 diagnostic CLI subcommands. ASCII-only output enforced via subprocess-stdout-capture test.
7. **F6 transient-empty defense at construction barrier** — applies to Item 5 JIT helper (Sub-task 3A); `ChartRender(...)` raises on empty bytes; helper catches + returns None; cache row never blank-overwritten.
8. **`Literal[...]` runtime-enforcement gotcha** — applies to Item 2 `_SilverLabelResponse` extension (Sub-task 4A `__post_init__` validates `status` against frozenset).
9. **Service-layer ValueError wrap at CLI boundary** — applies to all `diagnose` CLI subcommands (Sub-task 1G wraps via `click.ClickException`).
10. **Read-path mapping keeps pace with write-path** — T4.SB introduces NO new dataclass-vs-row mapper changes; gotcha applies if Sub-task 4A `rule_criteria` field requires extending an existing mapper (it does not — `pattern_exemplars.labeler_evidence_json` is a JSON blob; no row-to-dataclass mapper).
11. **Synthetic-fixture-vs-production-emitter shape drift** — applies to Item 1 + Item 7 diagnostic tests + Item 2 labeler tests. Discriminating tests MUST plant production-shape fixtures (real `candidates` + `trades` + `pattern_exemplars` rows).
12. **Existing-field reuse audit before claiming new dataclass fields (NEW gotcha #10)** — applied to Item 2 (`rule_criteria` is genuinely new on `SilverLabelResponse`; no existing field served the purpose).
13. **Template-rendering surface audit (NEW gotcha #11)** — applied to Item 2 (template at `swing/web/templates/patterns/exemplars.html.j2:33-90` already renders `criterion_rows` + `narrative_text`; emit-side fix only).
14. **`date.fromisoformat()` cross-type-boundary discipline (NEW gotcha #12)** — does not apply (no new TEXT-to-date conversions).
15. **Server-recompute at POST** — does not apply (no new POST handlers under T4.SB V1 scope).
16. **§A.14 paired discipline** — does not apply (schema v21 UNCHANGED).
17. **Audit envelope empty-state uniformity** — applies to Item 2 envelope persistence (Sub-task 4B asserts `rule_criteria` ABSENT from envelope when None; alias `narrative` ALWAYS populated).

### §I.2 Pre-Codex review expansions BINDING

All 7 expansions + 4 NEW candidate refinements (per dispatch brief §3.1):

1. Expansion #1 — hardcoded-duplicate audit.
2. Expansion #2 — brief-vs-spec source-of-truth + brief-vs-actual schema reality check.
3. Expansion #3 — schema-CHECK-vs-semantic-contract gap audit.
4. Expansion #4 + SQL column verification — specific-scenario gotcha trace + SQL skeleton column verification.
5. Expansion #5 — cross-section spec inventory grep.
6. Expansion #6 — content-completeness audit.
7. Expansion #7 + cross-row scope/unit boundary — cross-row semantic SCOPE audit.
8. Expansion #8 — per-aggregation-function UNIT audit on SQL skeletons.
9. Expansion #9 — form-render anchor lifecycle audit 4-dimension.
10. Expansion #10 NEW BINDING — architecture-location audit + 5 sub-disciplines.

29th cumulative C.C lesson #6 validation expected at writing-plans phase + executing-plans phase.

### §I.3 Process discipline BINDING

- **NO Co-Authored-By footer** on any commit (~378+ cumulative streak). Cite per fresh forward-binding lesson #7 from Phase 12 Sub-sub-bundle C.B 2026-05-15 in every commit message.
- **`python -m swing.cli` from worktree cwd** for implementer-side test invocations (NOT bare `swing` — `pip install -e` from main HEAD's entry point is NOT guaranteed to point at the worktree's copy). Operator-facing examples in this plan (e.g., `swing diagnose aplus-sensitivity --eval-runs 20`) intentionally use the operator-installed CLI form because that is what the operator types after merge.
- **ASCII-only on stdout-flowing CLI paths** + template narrative text (Windows cp1252 stdout safety).
- **TDD per task** (failing test → minimal impl → see pass → commit).
- **Edit tool for per-file edits**; Write tool reserved for net-new files.
- **Cite the discipline in commit messages** per cumulative precedent.

---

## §J §1.5 amendments encoded

### §J.1 §1.5.1 OQ-1.3 SCOPE EXPANSION (parameter-sweep sensitivity harness)

**Encoded at:** T-T4.SB.1 Sub-tasks 1A-1E (variable enumeration + 1D sweep + CSV/markdown formatters + harness CLI + method record + study stub).

**Scope:** Item 1 diagnostic expanded from snapshot shape to 1D parameter-sweep sensitivity harness. Per-variable kind taxonomy (3 values): `gate` (full bucket_for resimulation; 2 vars) + `threshold_additive` (sweep heuristic = ±delta around current; parity-preserving V1) + `threshold_multiplicative` (sweep heuristic = current × {0.5, 0.75, 1, 1.25, 1.5}; parity-preserving V1). Output: sensitivity matrix CSV + markdown analysis with explicit Kind column + V1-limitation paragraph.

**Compute cost (V1):** 17 variables split as:
- **Gate** (2 vars × 5 sweep points × ~5000 candidate_criteria rows × N=20 eval_runs) = ~1M `_bucket_for_substituted` calls — real bucket-redistribution arithmetic.
- **Threshold** (15 vars × 5 sweep points × ~5000 rows × 20 runs) = ~7.5M parity-preserving rows — each row is a constant-time `return persisted_bucket` short-circuit (no real resimulation).

Total: ~seconds-to-minutes pure Python. No DB writes; no yfinance fetches; no full pipeline runs. The threshold-row compute is essentially a count + format pass; cost is dominated by markdown emission, not arithmetic.

**Discriminating tests** (per Sub-tasks 1A.1 + 1B.1 + 1B.5 + 1C.1):
- variable enumeration produces >= 10 variables; current_value among sweep_points.
- sweep at current_value reproduces persisted bucket distribution exactly (parity invariant).
- CSV format has 8 columns; markdown is cp1252-encodable.

### §J.2 §1.5.2 OQ-CL.2 deferred-until-diagnostic disposition

**Encoded at:** T-T4.SB.6 Sub-task 6C (triage-agenda artifact stub).

**Scope:** Phase 14 trigger decision deferred until T-T4.SB.1 sensitivity harness ships output. T-T4.SB.6 closer ships `docs/phase13-closer-next-phase-triage.md` artifact stub.

**Closer commit message** MUST cite the deferred-decision artifact + the dependency chain (T-T4.SB.1 diagnostic → triage agenda → next-phase decision).

### §J.3 §1.5.3 OQ-5.4 Option A LOCKED

**Encoded at:** T-T4.SB.3 Sub-tasks 3A (JIT helper accepts `pipeline_run_id` parameter) + 3F (discriminating invariant test).

**Scope:** Dashboard reader binds to ONE pipeline_run anchor; JIT writes match anchor. Re-run during dashboard view: dashboard sees stable cache for the run_id it anchored to; subsequent dashboard render picks up newer run_id + may JIT-render against newer run. Old run_id cache rows accumulate (per OQ-5.1 R4 manual prune CLI; bounded growth acceptable V1).

**Discriminating test** (Sub-task 3F.1):
- Plant pipeline_run_id=100 + render via JIT; plant pipeline_run_id=101 + render via JIT; assert chart_renders contains TWO rows (one per run_id); old run_id NOT clobbered.

### §J.4 §1.5.4 OQ-1.4 REVISED to research-branch placement

**Encoded at:** T-T4.SB.1 Sub-tasks 1A-1E (research-branch placement under `research/harness/aplus_sensitivity/`).

**Scope:** Item 1 diagnostic implements under `research/harness/aplus_sensitivity/` mirroring `research/harness/earnings_proximity/` precedent. Production CLI `swing diagnose aplus-sensitivity` delegates to the research module (via `from research.harness.aplus_sensitivity.run import run_harness`).

**Method-record + study stub:**
- `research/method-records/aplus-criteria-calibration.md` — V2.1 §IV.B minimum viable record (status=research).
- `research/studies/aplus-criterion-sensitivity-2026-05-22.md` — first study writeup; findings TBD post-merge when operator runs harness.

**`research/phase-0-tasks.md` update:** A+-like-indicators entry promoted from "Later (deferred)" to "Next" with citation to T-T4.SB.1 harness.

### §J.5 §1.5.5 Test count impact

T-T4.SB.1 budget bumped to ~30-40 tests per §1.5.1 (was ~15-20). Total T4.SB projection: ~5760-5805 fast + 1 fast E2E (per §F.1).

Schema v21 UNCHANGED (sensitivity harness consumes existing `candidate_criteria` schema; no migration).

---

## §K Research-branch coordination

### §K.1 T-T4.SB.1 deliverables (research/)

Per §1.5.4 amendment, T-T4.SB.1 ships:
- `research/harness/aplus_sensitivity/__init__.py` + `README.md` + `variables.py` + `sweep.py` + `output.py` + `run.py`.
- `research/method-records/aplus-criteria-calibration.md` — V2.1 §IV.B minimum viable record (status=research; baseline_or_predecessor=internal current cfg).
- `research/studies/aplus-criterion-sensitivity-2026-05-22.md` — first study; findings TBD.
- `research/phase-0-tasks.md` — A+-like-indicators entry promoted to "Next" section.

### §K.2 V2.1 §IV.D + §VII.C lifecycle posture

The method record `status` field starts at `research`. Promotion to `shadow` or `production` requires:
- Evidence summary (operator-paired triage of sensitivity-harness output).
- New `version` value + changelog entry per V2.1 §IV.B.

This promotion is OUT OF T4.SB SCOPE — deferred per §1.5.2 + OQ-CL.3.

### §K.3 Cross-branch read-only invariant

The harness imports READ-ONLY from `swing.config` and `swing.evaluation` (mirrors `research/harness/earnings_proximity/` discipline). NO production schema writes; NO `swing.data.repos.*` mutations.

### §K.4 OQ-CL.3 — first-method-record selection meeting

Scheduled separately post-T4.SB-SHIPPED. T-T4.SB.6 closer artifact `docs/phase13-closer-next-phase-triage.md` enumerates: (i) the 8 candidate A+-like indicators banked in `research/phase-0-tasks.md`; (ii) the sensitivity-harness output as primary input; (iii) operator-paired triage gate.

---

## §L Phase 13 closure procedure (T-T4.SB.6 acceptance criteria)

### §L.1 At T-T4.SB.6 SHIPPED + integration-merge

Updates landed by Sub-task 6D:

1. **CLAUDE.md current-state line** — replace `Phase 13 sub-bundle ship count: 11 of 11 SHIPPED — T4.SB closer arc IN-FLIGHT` with `Phase 13 sub-bundle ship count: 12 of 12 SHIPPED — Phase 13 FULLY CLOSED 2026-05-22 PM`.

2. **`docs/orchestrator-context.md`**:
   - "Currently in-flight work" → "T4.SB SHIPPED; Phase 13 FULLY CLOSED. Next-phase triage agenda at `docs/phase13-closer-next-phase-triage.md`."
   - "Recent decisions and framings" → append T4.SB closer entry citing 6 sub-bundles SHIPPED + commit shas.
   - "Lessons captured" → append any NEW gotchas from Codex chains during T-T4.SB.1..T-T4.SB.5.

3. **`docs/cycle-checklist.md`** — quarterly `swing diagnose aplus-sensitivity` + `swing diagnose metrics-wiring` re-run reminders; archive prior outputs to `exports/diagnostics/archive/`.

4. **`docs/phase3e-todo.md`** — Phase 13 closure top entry + 7-item checkboxes marked SHIPPED.

5. **`docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md`** — §H.3 cross-bundle pin table append row 13.

6. **`docs/phase13-closer-next-phase-triage.md`** — triage-agenda artifact stub committed per §1.5.2.

### §L.2 Phase 14 / research-branch transition

T4.SB SHIPPED transitions the project to **post-Phase-13 state**. The next dispatch decision is operator-driven per OQ-CL.2 + §1.5.2:

- **Path A** — Phase 14 dispatch (operator-defined; no commitment in T4.SB scope).
- **Path B** — Research-branch advancement (first-method-record selection per `research/phase-0-tasks.md` "Next" section).
- **Path C** — Combination (Phase 14 + research-branch concurrent per V2.1 §V branch posture).

Sensitivity-harness output (Item 1 deliverable) is the primary input to this decision.

### §L.3 Phase 13 main plan §H.3 row 13 appendage

Entry: `test_phase13_t4_sb_hypothesis_label_match_strategy_invariant` — cross-bundle pin row 13; GREEN-promoted at T-T4.SB.6.

### §L.4 Return report

At T-T4.SB.6 ship, write `docs/phase13-t4-sb-return-report.md` per cumulative precedent. Required sections:
- §1 Status (SHIPPED at commit sha; Phase 13 12 of 12 sub-bundles SHIPPED).
- §2 Codex chain shape per sub-bundle.
- §3 Per-task summary (commits + tests + key decisions).
- §4 V1 simplifications + V2 candidates banked.
- §5 Forward-binding lessons.
- §6 Cumulative streaks (Co-Authored-By footer; C.C lesson #6 validations).
- §7 References.

### §L.5 Streaks preserved

- **ZERO Co-Authored-By footer trailer drift** — ~378+ cumulative through T4.SB closer.
- **C.C lesson #6 cumulative validations** — 29th expected NOTABLE at writing-plans + 30th expected at executing-plans.
- **Phase 13 sub-bundle ship count** — 11 of 11 → 12 of 12 / FULLY CLOSED at T-T4.SB.6 SHIPPED.

---

## §M References

### §M.1 Primary substrate
- Spec: `docs/superpowers/specs/2026-05-22-phase13-t4-sb-closer-design.md` at HEAD `f7dec0e`.
- Dispatch brief: `docs/phase13-t4-sb-writing-plans-dispatch-brief.md` at `4690933`.
- T4.SB triage items: `docs/phase3e-todo.md:15-101`.

### §M.2 Phase 13 cumulative
- Phase 13 main spec: `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`.
- Phase 13 main plan: `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md`.
- T2.SB6c return report: `docs/phase13-t2-sb6c-executing-plans-return-report.md`.
- T4.SB brainstorming return report: `docs/phase13-t4-sb-brainstorm-return-report.md`.

### §M.3 Architecture references
- `swing/evaluation/scoring.py:13-39` — `bucket_for` (Item 1).
- `swing/journal/stats.py:325` — `compute_hypothesis_progress_breakdown` (Item 7 CLI path).
- `swing/web/view_models/metrics/hypothesis_progress_card.py:404` — dashboard card (Item 7 fix target).
- `swing/metrics/cohort.py` — list_trades_for_cohort + count_per_cohort (Item 7 SQL).
- `swing/trades/entry.py:184-209` — canonicalize_hypothesis_label (Item 7 normalization helper).
- `swing/recommendations/hypothesis.py:259-285` — _descriptive_label (suffix builder).
- `swing/recommendations/hypothesis.py:416-435` — _label_matches_hypothesis (existing helper).
- `swing/web/chart_scope.py` — LOCKED read-only (Item 5).
- `swing/pipeline/runner.py:_step_charts` — chart_renders write-through (Item 5).
- `swing/web/charts.py:render_*` — chart helpers (Item 3 + Item 5).
- `swing/web/templates/partials/watchlist_row.html.j2` (Items 4, 6).
- `swing/web/routes/watchlist.py` (Items 5, 6).
- `swing/patterns/labeling.py:SilverLabelResponse` (Item 2).
- `.claude/agents/pattern-labeler.md` (Item 2 subagent prompt).
- `swing/web/templates/patterns/exemplars.html.j2:33-90` (Item 2 template; already correct).
- `swing/web/view_models/patterns/exemplars.py:110-160` (Item 2 VM parser; already correct).

### §M.4 Cross-branch references
- `research/harness/earnings_proximity/` — harness precedent (mirror for `aplus_sensitivity`).
- `research/method-records/_template.md` — method record template.
- `research/studies/earnings-proximity-exclusion.md` — study writeup precedent.
- `research/phase-0-tasks.md` — applied-research backlog.

### §M.5 Cumulative gotchas + lessons
- `CLAUDE.md` at repo root — 14+ cumulative gotchas; #14 Architecture-location audit (Expansion #10 candidate BINDING).
- `docs/orchestrator-context.md` — Lessons captured.

### §M.6 Cross-bundle pin precedents
- `tests/data/test_phase13_t2_sb6c_cross_bundle_pin_row_12.py` — T2.SB6c precedent for parametrized cross-bundle pin file structure.

---

## §N Self-review

Per superpowers:writing-plans skill self-review checklist:

**1. Spec coverage:** verified each spec section §A-§M maps to a task or §-section in this plan.
- §A status + scope → §A here.
- §B per-item investigation → §B per-task (1-6) here.
- §C cross-item couplings → §C here.
- §D investigation outputs → §D here.
- §E cross-bundle pin → §E here.
- §F test scope → §F here.
- §G sub-bundle decomposition → §B + §G here.
- §H dispatch sequence → §H here.
- §I forward-binding lessons → §I here.
- §J OQs → §A.2 (18 OQs locked) + §J (4 amendments) here.
- §K Phase 13 closure marker → §L here.
- §M closing notes → §A.4 file map + §F test budget.

**2. Placeholder scan:** searched for "TBD", "TODO", "implement later" — none present in step bodies. **POST-R2 UPDATE:** R1 removed the `_emit_*_thresholds` placeholder triple; R2 corrected the count to 17 (NOT 18) — 2 gate + 3 trend_template + 8 vcp + 1 risk + 3 rs — and introduced the `kind` taxonomy distinguishing gate (full resimulation) from threshold variables (parity-preserving V1 limitation). The Sub-task 1A.1 test now asserts the exact 17-name set via set-equality (NOT a loose `>=10`). The 3 remaining "TBD" references in §K + §L are explicit deferral citations for the post-merge study writeup findings (operator-populated when running the harness against operator DB); these are NOT implementation-step placeholders.

**3. Type consistency:**
- `SweepVariable.kind` ∈ `{"gate", "threshold_additive", "threshold_multiplicative"}` consistent across enumeration + sweep + output (per R2 + R3 LOCK; the earlier R1 taxonomy of multiplicative/additive/discrete was retired). `SweepEntry.kind` carries the same value verbatim so the CSV/markdown formatter can render the Kind column without an extra lookup.
- `SilverLabelResponse.rule_criteria: list[dict] | None = None` consistent across dataclass + envelope + test.
- `get_or_render_surface` signature consistent across helper + watchlist routes + dashboard VM.
- `label_matches_hypothesis_sql(name) -> tuple[str, list[object]]` consistent across helper + cohort module.
- `surface` enum values consistent: `"hyprec_detail"`, `"market_weather"`, `"position_detail"`, `"watchlist_row"`.

**4. Bite-sized step granularity:** each step is 2-5 min (write test / run test / write code / run test / commit). Larger sub-tasks split into 4-8 steps each.

**5. Process discipline:** every commit message template free of Co-Authored-By footer; every CLI invocation example uses `python -m swing.cli` per worktree cwd discipline.

End of plan.

