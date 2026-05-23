# V2 OHLCV Criterion-Evaluator Harness — Brainstorming Design Spec

**Status:** brainstorming spec (pre-writing-plans). First Applied Research arc post-Phase-13-FULLY-CLOSED. Path B LOCKED per operator decision 2026-05-23 PM at [`docs/phase13-closer-next-phase-triage.md`](../../phase13-closer-next-phase-triage.md) commit `b4d7719`.

**Branch:** `applied-research-v2-ohlcv-criterion-evaluator-brainstorm` (branched from main HEAD `acaf305`).

**Predecessor dispatch brief:** [`docs/v2-ohlcv-criterion-evaluator-brainstorming-dispatch-brief.md`](../../v2-ohlcv-criterion-evaluator-brainstorming-dispatch-brief.md) at `acaf305`.

**Lineage:** first deliverable under method-record [`research/method-records/aplus-criteria-calibration.md`](../../../research/method-records/aplus-criteria-calibration.md) per OQ-CL.3 LOCK. V2 OHLCV criterion-evaluator harness extends the V1 sensitivity-harness at [`research/harness/aplus_sensitivity/`](../../../research/harness/aplus_sensitivity/) — does NOT replace it.

**Cumulative streaks preserved through this spec write:** ~434+ ZERO `Co-Authored-By` footer trailer; baseline 5778 fast tests UNCHANGED (brainstorming docs-only); schema v21 UNCHANGED (V2 harness does NOT touch schema per §A.2); ZERO new Schwab API calls (L2 LOCK preserved through V2 design per OQ-12 disposition below).

---

## §A Status + scope

### §A.1 Research-branch positioning (V2.1 §V)

V2 OHLCV criterion-evaluator harness lives under `research/` per V2.1 §V branch posture:

- **NEW module**: `research/harness/aplus_v2_ohlcv_evaluator/` (4-6 files; see §C.1 module breakdown). NOT a fork of `research/harness/aplus_sensitivity/`; the V1 harness STAYS as the gate-variable assessment surface per §A.4.
- **NEW study writeup**: `research/studies/<date>-v2-ohlcv-criterion-evaluator.md` (companion to existing `aplus-criterion-sensitivity-2026-05-22.md`). Follows the format precedent from `research/studies/earnings-proximity-exclusion.md`.
- **Method-record EXTENSION** (not new record): append-only sections at [`research/method-records/aplus-criteria-calibration.md`](../../../research/method-records/aplus-criteria-calibration.md) (see §K). The existing 72-line record stays; V2 sections appended below the existing "V2 dependencies" section + corresponding promotion criteria bullets added to the existing "Validation notes" + "Notes" sections.
- **Tests** under `tests/research/test_aplus_v2_ohlcv_*.py` mirroring T-T4.SB.1 precedent at `tests/research/test_aplus_sensitivity_*.py`. Test count budget per §H.
- **Production `swing/` code is READ-ONLY** through this dispatch arc. V2 imports from `swing.evaluation.evaluator.evaluate_one` + `swing.evaluation.scoring.bucket_for` + `swing.evaluation.context.{CandidateContext, BatchContext, MarketContext}` + `swing.config.Config` + `swing.data.ohlcv_archive.read_or_fetch_archive` ONLY. NO writes to `swing/`, NO writes to `swing-data/swing.db` domain tables, NO schema changes.

### §A.2 Schema discipline (LOCK)

Schema v21 is the LOCKED schema. V2 SHOULD NOT touch migrations.

The brainstorming spec EXPLICITLY does NOT propose any v22 delta. Per the existing method-record V2 dependency #2 ("Structured threshold columns on `candidate_criteria`") — that V3+ work pushes value substitution into SQL and is NOT in V2 OHLCV harness scope.

Verified at brainstorming-phase pre-Codex Expansion #4 refinement (BINDING for 26th cumulative validation onwards — "every SQL skeleton's columns verified against actual migration files"): the V2 harness's SQL skeletons (§F.3) read ONLY existing columns:

- `evaluation_runs.id` + `evaluation_runs.data_asof_date` + `evaluation_runs.action_session_date` per `swing/data/migrations/0001_phase1_initial.sql:9-21`
- `candidates.id` + `candidates.evaluation_run_id` + `candidates.ticker` + `candidates.bucket` per `swing/data/migrations/0001_phase1_initial.sql:24-42`
- `candidate_criteria.candidate_id` + `candidate_criteria.criterion_name` + `candidate_criteria.layer` + `candidate_criteria.result` + `candidate_criteria.value` + `candidate_criteria.rule` per `swing/data/migrations/0001_phase1_initial.sql:48-56`

ZERO new columns referenced. ZERO new table references. ZERO CHECK enum widenings. Verified via `grep -n` against `swing/data/migrations/0001_phase1_initial.sql` at spec-write time.

### §A.3 V2.1 §IV.D + §VII.C lifecycle posture

The existing method-record `aplus-criteria-calibration` is at `status='research'`. V2 OHLCV harness output is the evidence summary that operator + research branch evaluate for promotion to `shadow` and eventually `production` per V2.1 §VII.C.

V2 harness ships at `status='research'` (no `shadow` claim at landing). Promotion criteria proposed at §K.3 (binding for downstream Applied Research arcs; NOT triggered by V2 ship itself).

### §A.4 V1 harness retention (no replacement)

The V1 aplus_sensitivity harness at `research/harness/aplus_sensitivity/` STAYS as the gate-variable quick assessment surface. The CLI `swing diagnose aplus-sensitivity` continues to invoke V1 unchanged.

V2 ships under a NEW CLI surface name `swing diagnose aplus-sensitivity-v2` per OQ-10 RECOMMEND (less invasive than renaming V1). V2 + V1 share the variable enumeration at `research/harness/aplus_sensitivity/variables.py` (V2 imports `enumerate_variables(cfg)` to inherit the 17-variable set verbatim); V2 + V1 share the cfg + ohlcv-archive read-only interfaces. V2 differs from V1 ONLY in the substitution semantics (live `evaluate_one` recompute vs persisted-bucket passthrough).

### §A.5 Non-scope (V3+ / future arc; explicitly out of V2)

- **Schema changes** — `candidate_criteria` structured threshold columns is V3+ work per existing method-record V2 dependency #2.
- **Multi-D sensitivity sweep** — pair-wise variable interaction is V3+ per V2.1 §IV.B parsimony (see §B.5 + OQ-7).
- **cfg-policy automation** — automatic cfg updates based on V2 output is POST-promotion-to-`production` lifecycle work; V2 ships at `status='research'` per §A.3.
- **Phase 14 commissioning** — deferred per OQ-CL.2 LOCK until V2 outputs inform operational scope.
- **V2.G1-G4 operator gate bug investigations** — deferred per operator decision 2026-05-23 PM (worked AFTER Applied Research tasking per operator direction; banked at `docs/phase3e-todo.md` §"Post-T4.SB-SHIPPED operator gate feedback").
- **Production `swing/` code changes** — V2 harness is research-branch only; production stack stable through V2 dispatch (per §A.1 final paragraph).
- **`cfg.trend_template.allowed_miss_names` (tuple-set) sweep** — non-numeric grid; V3+ candidate per V1 method-record §"Notes" line 70.
- **`cfg.rs.benchmark_ticker` (string identifier) sweep** — non-numeric; not a threshold; V3+ candidate per V1 method-record §"Notes" line 70.
- **Adaptive bisection sweep strategy** — V2 inherits the V1 5-point grid (OQ-3 RECOMMEND). Adaptive bisection deferred V3+ per V2.1 §IV.B parsimony.
- **Schwab API calls** — V2 OHLCV reconstruction uses yfinance-only via `prefer_source='yfinance'` on the OhlcvArchive read path per OQ-12 RECOMMEND (preserves L2 LOCK; no new Schwab API calls).

---

## §B Research question + S3 findings inheritance

### §B.1 Operator motivating question (per Path B disposition)

> Which of the 15 inert threshold variables (V1 LIMITATION at `research/harness/aplus_sensitivity/sweep.py:248-250`) are binding at the watch→A+ promotion boundary, ranked by marginal A+ count per loosening unit?

V2 harness output MUST answer this directly. The output format (§G) is designed to surface the binding-variable ranking in the top-line summary section.

### §B.2 V1 sensitivity-harness output (S3) findings inherited

Per operator-paired triage session 2026-05-23 PM (at [`docs/phase13-closer-next-phase-triage.md`](../../phase13-closer-next-phase-triage.md) §"Findings from 2026-05-23 S3 sensitivity-harness review"):

**Baseline** (5681 candidates across 63 eval_runs):
- Gate-variable view: A+ = 5 / Watch = 1184 / Skip = 4492 / Excluded = 0
- Threshold-variable view: A+ = 5 / Watch = 1186 / Skip = 4277 / Excluded = 168 (V1 path-attribution artifact; headline holds)

**Gate findings (LIVE-recompute; 2 variables)** — both NON-BINDING at the watch→A+ boundary:
- `trend_template.min_passes=7` (current) → loosening to 5/6 produces ZERO A+ delta; tightening to 8 trims 87 Watch (-7%) without changing A+; tightening to 9 collapses A+ (only 8 TT criteria exist; implicit ceiling).
- `vcp.watch_max_fails=2` (current; HARDCODED in `swing/evaluation/scoring.py:35`, NOT cfg-derived) → sweep 0→4 produces 0/234/1184/2874/3968 Watch counts with A+ UNCHANGED at 5 across all sweep points. Pure Watch-fanout dial.

**Threshold findings (15 variables — INERT under V1 per V1 LIMITATION)**:

Verbatim from S3 markdown at `exports/diagnostics/aplus-sensitivity-20260523T065514Z.md`:

| # | Variable | Kind | V1 sweep range |
|---|----------|------|----------------|
| 1 | `trend_template.rising_ma_period_days` | threshold_additive | 11..31 (21 sweep points; current 21) |
| 2 | `trend_template.high_52w_margin_pct` | threshold_multiplicative | 12.5, 18.75, 25.0, 31.25, 37.5 (current 25.0) |
| 3 | `trend_template.low_52w_min_pct` | threshold_multiplicative | 15.0, 22.5, 30.0, 37.5, 45.0 (current 30.0) |
| 4 | `vcp.prior_trend_min_pct` | threshold_multiplicative | 12.5, 18.75, 25.0, 31.25, 37.5 (current 25.0) |
| 5 | `vcp.adr_min_pct` | threshold_multiplicative | 2.0, 3.0, 4.0, 5.0, 6.0 (current 4.0) |
| 6 | `vcp.pullback_max_pct` | threshold_multiplicative | 12.5, 18.75, 25.0, 31.25, 37.5 (current 25.0) |
| 7 | `vcp.proximity_max_pct` | threshold_multiplicative | 2.5, 3.75, 5.0, 6.25, 7.5 (current 5.0) |
| 8 | `vcp.tightness_days_required` | threshold_additive | 0, 1, 2, 3, 4 (current 2) |
| 9 | `vcp.tightness_range_factor` | threshold_multiplicative | 0.335, 0.5025, 0.67, 0.8375, 1.005 (current 0.67) |
| 10 | `vcp.orderliness_max_bar_ratio` | threshold_multiplicative | 1.5, 2.25, 3.0, 3.75, 4.5 (current 3.0) |
| 11 | `vcp.orderliness_max_range_cv` | threshold_multiplicative | 0.3, 0.45, 0.6, 0.75, 0.9 (current 0.6) |
| 12 | `risk.max_risk_pct` | threshold_multiplicative | 0.0025, 0.00375, 0.005, 0.00625, 0.0075 (current 0.005) |
| 13 | `rs.horizon_weeks` | threshold_additive | 10, 11, 12, 13, 14 (current 12) |
| 14 | `rs.rs_rank_min_pass` | threshold_additive | 60..80 (21 sweep points; current 70) |
| 15 | `rs.fallback_extreme_pct` | threshold_multiplicative | 10.0, 15.0, 20.0, 25.0, 30.0 (current 20.0) |

V2 covers all 15 in one dispatch per OQ-5 RECOMMEND. Per-variable hypothesis enumeration at §B.4.

### §B.3 Headline interpretation feedback to V2 design

Per S3 review:

> The 5-A+-candidates-across-63-eval_runs constraint is therefore caused by EITHER:
> 1. The 15 untested threshold criteria — V2 OHLCV harness needed to identify which one(s) are binding.
> 2. Market conditions (no qualifying setups in the universe regardless of threshold).
> 3. Other gates not enumerated as `kind=gate` in V1 (e.g., `risk_feasibility` hard pre-filter, Stage-2 trend status that isn't part of TT8-count).

V2 design directly addresses (1). V2 design surfaces (2) via the baseline-recompute parity invariant (§E.4). V2 design partially addresses (3) by making the per-candidate per-criterion re-evaluation visible in the drill-down (§G.2) — operator can inspect WHICH criterion is failing for the watch-bucket candidates that don't promote to A+, even when the substituted threshold is loose.

### §B.4 Per-variable hypothesis (which threshold variables might be binding)

Pre-V2-run hypothesis ranking (operator + research-branch shared model). Banked to test against V2 output post-ship:

- **HIGH binding-likelihood candidates** (often-cited as overly strict in operator review):
  - `vcp.orderliness_max_bar_ratio` (3.0 default; bars-with-large-range often filter out otherwise valid setups)
  - `vcp.orderliness_max_range_cv` (0.6 default; CV is sensitive to a single outlier bar)
  - `vcp.tightness_range_factor` (0.67 default; tighter than many real-world bases)
  - `vcp.proximity_max_pct` (5.0% default; "near pivot" can exclude bases consolidating 6-8% below pivot)
  - `rs.rs_rank_min_pass` (70 default; RS<70 names with strong absolute setup are excluded)
- **MEDIUM binding-likelihood**:
  - `vcp.adr_min_pct` (4.0% default; low-vol stocks filtered out)
  - `vcp.prior_trend_min_pct` (25.0% default; mid-run setups filtered out)
  - `vcp.pullback_max_pct` (25.0% default; deeper-pullback bases filtered out)
  - `trend_template.high_52w_margin_pct` (25.0% default; TT7 strict)
- **LOW binding-likelihood** (often non-tight at the watch boundary):
  - `vcp.tightness_days_required` (2 default; usually met by valid bases)
  - `trend_template.rising_ma_period_days` (21 default; 200-MA usually rising at these scales)
  - `trend_template.low_52w_min_pct` (30% default; TT6 usually met)
  - `risk.max_risk_pct` (0.5% default; affects share count not bucket)
  - `rs.horizon_weeks` (12 default; structural parameter not boundary)
  - `rs.fallback_extreme_pct` (20.0% default; affects only outside-universe tickers)

V2 output ranks all 15 by ACTUAL marginal A+ count per loosening unit and confirms / refutes this hypothesis.

### §B.5 Null hypothesis for V2 study

> No single threshold variable substitution, within the V1 5-point sweep grid, produces a material delta in `aplus_count` against the operator's retained 5681-candidate / 63-eval_run universe.

V2 rejects the null iff ≥1 variable produces a non-zero `delta_aplus` at any sweep point. The threshold of "material" is operator-paired (banked as OQ-8 promotion-criteria sub-question; default proposed: ≥5 A+ delta on a 5681-candidate universe, i.e., doubling the A+ count).

---

## §C V2 OHLCV evaluator architecture

### §C.1 Module placement decision (Expansion #10 architecture-location BINDING applied)

Pre-Codex Expansion #10 (architecture-location audit) discipline BINDING for 31st cumulative C.C lesson #6 validation:

- **NEW module `research/harness/aplus_v2_ohlcv_evaluator/`** for cross-cutting V2 logic. Justification:
  - V1 `research/harness/aplus_sensitivity/sweep.py:run_sensitivity_sweep` is shaped around PERSISTED-bucket consumption — its data flow is `candidate_criteria` rows in / sweep-counts out. V2's data flow is fundamentally different: `candidates` + OHLCV archive in / per-candidate re-evaluated buckets out. Forking sweep.py to add V2 substitution would cross dependency-context boundaries (sweep.py has no OHLCV-cache plumbing; no `evaluate_one` invocation site).
  - The V1 `_bucket_for_substituted` function in sweep.py is a STANDALONE mirror of `bucket_for` semantics for the gate-variable resimulation path. V2 invokes the REAL production `evaluate_one` end-to-end (per §D.1); this is structurally different from a substituted-bucket mirror. Sharing a module would conflate two distinct architectural patterns.
- **Shared with V1 (READ-ONLY imports)**:
  - `research.harness.aplus_sensitivity.variables.SweepVariable` + `research.harness.aplus_sensitivity.variables.enumerate_variables` — V2 inherits the 17-variable set verbatim (3 gate + 15 threshold from V1 enumeration; V2 substitutes ALL 17 via OHLCV recompute; V1's gate-variable special-case path becomes redundant in V2, but the enumeration is shared).
  - **Architectural note on V1↔V2 variable substitution divergence**: V1 has SPECIAL-CASE `_bucket_for_substituted` for 2 gate variables (cfg-derived `trend_template.min_passes` + hardcoded `vcp.watch_max_fails`) + parity-passthrough for 15 threshold variables. V2 has UNIFORM end-to-end recompute for the cfg-derived 14 of the 15 threshold variables AND `trend_template.min_passes` — but the hardcoded `vcp.watch_max_fails` in `swing/evaluation/scoring.py:37` requires SPECIAL-CASE substitution (see OQ-11 + §E.3).

**V2 module file layout** (proposed; subject to writing-plans refinement):

```
research/harness/aplus_v2_ohlcv_evaluator/
  __init__.py
  context_builder.py        # rebuilds CandidateContext at historical data_asof_date
  cfg_substitution.py       # dataclasses.replace on Config for per-variable substitution
  sweep.py                  # V2 sweep orchestrator (per-candidate per-sweep-point evaluate_one)
  output.py                 # V2 output formatter (sensitivity matrix + per-variable drill-down)
  run.py                    # CLI entry point
```

**Dependency surface verification per Expansion #10 sub-discipline (a) architecture-location audit**:

| Module | Dependencies | Justification |
|--------|--------------|---------------|
| `context_builder.py` | `swing.data.ohlcv_archive.read_or_fetch_archive`, `swing.evaluation.context.{CandidateContext, BatchContext, MarketContext}`, `swing.config.Config`, `swing.evaluation.rs.compute_rs` | All READ-ONLY production imports. OHLCV slicing + 12-week-return computation + RS batch context reconstruction at historical asof_date. |
| `cfg_substitution.py` | `swing.config.{Config, TrendTemplate, VCP, Risk, RS}`, `dataclasses.replace` | Pure cfg-substitution via `dataclasses.replace`. No I/O. |
| `sweep.py` | `swing.evaluation.evaluator.evaluate_one`, `swing.evaluation.scoring.bucket_for` (for `vcp.watch_max_fails` special-case per §E.3), `swing.config.Config`, `research.harness.aplus_sensitivity.variables.{SweepVariable, enumerate_variables}`, `cfg_substitution.substitute_cfg`, `context_builder.build_candidate_context`, `sqlite3.Connection` (READ-ONLY for `evaluation_runs` + `candidates` + `candidate_criteria` SQL) | Per-candidate per-sweep-point orchestration. Reads candidate universe from operator DB. NO writes. |
| `output.py` | `dataclasses`, `csv`, `pathlib.Path`, V2 result dataclasses from `sweep.py` | Pure I/O formatter. ASCII-only output (Windows cp1252 safety per cumulative gotcha). |
| `run.py` | `argparse`, `sqlite3`, all V2 modules + `swing.config.Config.from_defaults` | CLI entry. Click delegation from `swing diagnose aplus-sensitivity-v2` (registered in `swing/cli.py`; V2 dispatch's only `swing/` modification is the CLI subcommand registration). |

Expansion #10 sub-discipline (c) cache-key shape + renderer-kwargs uniformity LOCK: V2 produces NO chart_renders rows. N/A.

Expansion #10 sub-discipline (d) SQL LIKE wildcard-escape: V2 produces NO LIKE-pattern SQL. N/A.

Expansion #10 sub-discipline (e) orphan-label preservation: V2 GROUP BY semantics replace V1 persisted-bucket passthrough with live recompute. Orphan-handling — candidates that V2 cannot evaluate due to OHLCV-coverage gaps — are explicitly handled per §E.5 + OQ-13 disposition (skip + per-variable count + per-study scope-reduction count surfaced in output).

### §C.2 CLI surface registration

NEW CLI subcommand `swing diagnose aplus-sensitivity-v2` registered in `swing/cli.py` (the ONLY production-`swing/` file V2 dispatch modifies — a 1-function CLI subcommand-registration block per Phase 13 T4.SB precedent for `swing diagnose aplus-sensitivity`). Delegates to `research.harness.aplus_v2_ohlcv_evaluator.run.run_harness`.

Per-flag contract:

```
swing diagnose aplus-sensitivity-v2 --db PATH [--eval-runs N] [--output-dir DIR] [--variables-filter NAME[,NAME...]] [--max-runtime-seconds N]
```

- `--db PATH` — operator's `swing-data/swing.db`. REQUIRED (mirror V1).
- `--eval-runs N` — default 20; max 100; range `[1, 100]` (mirror V1).
- `--output-dir DIR` — default `exports/diagnostics/` (mirror V1).
- `--variables-filter NAME[,NAME...]` — optional comma-separated variable-name filter for incremental runs / debugging. Default: ALL 17 variables (15 threshold + 2 gate).
- `--max-runtime-seconds N` — optional runtime cap (default UNSET = no cap). When provided, the harness emits a partial-result CSV + markdown with explicit "PARTIAL RUN — cap=N seconds — N of M variables completed" header. See OQ-9 RECOMMEND.

Per cumulative Phase 13 T-A.1.5b lesson "Service-layer ValueErrors must be wrapped at CLI boundary", the CLI subcommand wraps ALL service-layer dispatches in `try: ... except ValueError as exc: raise click.ClickException(str(exc))`.

### §C.3 Output paths

- CSV: `exports/diagnostics/aplus-sensitivity-v2-<ISO>.csv`
- Markdown: `exports/diagnostics/aplus-sensitivity-v2-<ISO>.md`

`<ISO>` is UTC `%Y%m%dT%H%M%SZ` (mirror V1 at `research/harness/aplus_sensitivity/run.py:48`).

V2 + V1 outputs coexist in `exports/diagnostics/` with distinct filename prefixes (`aplus-sensitivity-` vs `aplus-sensitivity-v2-`) for operator-side V1↔V2 comparison.

---

## §D Per-criterion evaluator design

### §D.1 Interface decision: cfg-substitution + production `evaluate_one(ctx)` end-to-end (OQ-2 RECOMMEND)

V2 substitutes ONE variable at a time via `dataclasses.replace(cfg.<sub>, <field>=<sweep_value>)` + invokes the production `swing.evaluation.evaluator.evaluate_one(ctx)` per candidate per sweep point. The end-to-end recompute preserves:

- **Cross-coupling between variables**. Example: substituting `rs.rs_rank_min_pass=60` propagates through `compute_rs(...).rank >= 60` in TT8 → flips tt8 result → may flip `tt_passes` count → may move `bucket_for` from skip to watch to aplus. V2 captures this faithfully without modeling cross-coupling explicitly (per §B.5 null + V2.1 §IV.B 1D parsimony — the cross-coupling is internal to ONE substituted variable; OQ-7 RECOMMEND stays 1D).
- **`allowed_miss_names` invariant** preserved verbatim per `swing/evaluation/scoring.py:27` (no V1 `_bucket_for_substituted` mirror needed).
- **Risk hard-filter semantics** preserved verbatim per `swing/evaluation/scoring.py:20`.
- **VCP-fails (`na` counts as fail) semantics** preserved verbatim per `swing/evaluation/scoring.py:34`.

The alternative (OQ-2 option b: explicit override-dict + per-criterion evaluator consuming `(bars, threshold, ...)`) was rejected because (a) it requires reimplementing each criterion's threshold-consumption logic in a parallel surface (HIGH drift risk vs production criteria); (b) it does NOT preserve cross-coupling without explicit modeling; (c) it scales poorly as new criteria are added (each new criterion requires V2-side adapter).

### §D.2 cfg-substitution implementation pattern

Per substitution call:

```python
# pseudo-code; actual signature TBD in writing-plans phase
def substitute_cfg(cfg: Config, variable_name: str, sweep_value: float | int) -> Config:
    """Return a NEW Config with variable_name = sweep_value; other fields unchanged.

    variable_name format: '<sub>.<field>' (e.g., 'trend_template.min_passes',
    'vcp.adr_min_pct', 'rs.rs_rank_min_pass'). The 'vcp.watch_max_fails'
    special case is NOT routed through this helper — see §E.3.
    """
    sub, field = variable_name.split(".", 1)
    if sub not in {"trend_template", "vcp", "risk", "rs"}:
        raise ValueError(f"Unknown cfg subsection: {sub!r}")
    sub_obj = getattr(cfg, sub)
    new_sub = dataclasses.replace(sub_obj, **{field: sweep_value})
    return dataclasses.replace(cfg, **{sub: new_sub})
```

**Type-preservation invariant**: `sweep_value` MUST match the field's expected type (int for additive variables; float for multiplicative; OR int for some additive thresholds like `tightness_days_required`). V1 enumerator already produces correct-typed sweep points per `_additive_sweep` (int) vs `_multiplicative_sweep` (rounded float). V2 inherits.

**Out-of-range guard**: V2 explicitly validates that the SUBSTITUTED value falls within the cfg dataclass field's documented range (e.g., `trend_template.min_passes` ∈ [0, 8] inclusive since only 8 TT criteria exist). Out-of-range sweep points are SKIPPED with a per-variable `out_of_range_skip_count` reported in the output. (See cumulative `Literal[...]` runtime-validation gotcha — discriminating test plants out-of-range substitution + asserts skip behavior.)

### §D.3 Criterion evaluation invocation flow per sweep-point

For each `(variable, sweep_point)` pair:

1. Substitute cfg → `substituted_cfg`.
2. For each `(candidate_id, ticker, data_asof_date)` in the universe:
   a. Build `CandidateContext` at `data_asof_date` per §F (OHLCV slice + reconstructed BatchContext).
   b. Invoke `evaluate_one(ctx)` with `substituted_cfg` → produces re-evaluated `Candidate` with new bucket.
   c. Accumulate counts into per-(variable, sweep_point) tallies: `aplus / watch / skip / excluded` + per-candidate drill-down `bucket_flipped: (old, new, criterion_results_summary)`.
3. Emit `SweepEntryV2` per (variable, sweep_point) with counts + delta-vs-current-value + per-variable drill-down attached at the parent level.

`SweepEntryV2` dataclass shape proposed (per Expansion #11 taxonomy propagation BINDING for 30th cumulative validation — V2 inherits the `{gate, threshold_additive, threshold_multiplicative}` kind enum from V1's `SweepVariable.kind`; NO new enum introduced; propagation surface is inherited):

```python
@dataclass(frozen=True)
class SweepEntryV2:
    variable_name: str
    kind: str  # inherits V1 enum: "gate" | "threshold_additive" | "threshold_multiplicative"
    sweep_point: float | int
    aplus_count: int
    watch_count: int
    skip_count: int
    excluded_count: int
    delta_aplus: int       # vs current_value entry's aplus_count
    delta_watch: int
    out_of_range_skip_count: int  # NEW vs V1 (per §D.2 guard)
    ohlcv_coverage_skip_count: int  # NEW vs V1 (per §F.3 coverage-failure handling)
    evaluation_error_skip_count: int  # NEW vs V1 (per-candidate try/except per cumulative lesson)
```

The 3 NEW skip-count columns vs V1 are intentional V2 additions per the increased scope of V2's recompute path. Per Expansion #11 taxonomy-propagation discipline:

- V1 `SweepEntry` has 9 fields (per `research/harness/aplus_sensitivity/sweep.py:33-49`); V2 `SweepEntryV2` adds 3 NEW fields → CSV header column list extends from 9 to 12.
- V2 `output.py:_CSV_HEADERS_V2` enumerates ALL 12 columns explicitly.
- V2 markdown matrix table extends from 9 columns (V1) to 12 columns (V2).
- Test fixtures plant non-zero values for EACH of the 3 NEW columns to verify the propagation invariant via discriminating test `test_sweep_entry_v2_serializer_round_trip_preserves_new_skip_columns`.

### §D.4 Per-candidate failure isolation

Per cumulative T2.SB5 gotcha "Bad-exemplar isolation in retrieval functions": V2's per-candidate `evaluate_one` invocation MUST be wrapped in try/except. A single candidate's exception (e.g., malformed OHLCV bar; missing 200-bar window after slice; cfg-substitution boundary case) MUST NOT poison the entire per-(variable, sweep_point) tally.

Failure isolation pattern:

```python
# pseudo-code; actual signature TBD in writing-plans
for cand in candidates_in_universe:
    try:
        ctx = build_candidate_context(cand.ticker, cand.data_asof_date, substituted_cfg, ...)
        result = evaluate_one(ctx)
        counts[result.bucket] += 1
    except OhlcvCoverageError:
        counts["ohlcv_coverage_skip"] += 1
    except OutOfRangeSubstitutionError:
        counts["out_of_range_skip"] += 1
    except Exception:
        counts["evaluation_error_skip"] += 1
        log.warning(...)
```

Discriminating test plants 3 candidates: 1 good + 1 with malformed OHLCV + 1 with cfg-out-of-range → asserts the good candidate's bucket is still tallied + the other 2 increment per-failure-mode skip counts.

---

## §E `bucket_for` recomputation end-to-end

### §E.1 Standard path (14 of 15 threshold variables + `trend_template.min_passes` gate)

For 14 of 15 threshold variables + the cfg-derived gate `trend_template.min_passes`, V2's `evaluate_one(ctx_with_substituted_cfg)` invocation re-runs ALL 8 trend_template + 9 vcp + 1 risk criterion functions against the OHLCV bars, then routes the resulting Results through `bucket_for(tt_results, vcp_results, risk_results, substituted_cfg)`. The result is the V2-recomputed bucket.

NO V2-side mirror of `bucket_for` is needed for the standard path. V2 invokes the production function verbatim.

### §E.2 Per-criterion threshold mapping (which criterion consumes which cfg-variable)

Verified via grep at spec-write time against `swing/evaluation/criteria/*.py` (Expansion #5 cross-section spec inventory grep BINDING per 25th cumulative validation):

| cfg variable | Consumed by | File:line |
|--------------|-------------|-----------|
| `trend_template.min_passes` | `bucket_for` gate (NOT a criterion) | `swing/evaluation/scoring.py:29` |
| `trend_template.rising_ma_period_days` | TT3 `200MA rising` | `swing/evaluation/criteria/trend_template.py:59-71` |
| `trend_template.high_52w_margin_pct` | TT7 `within 52w high` | `swing/evaluation/criteria/trend_template.py:111-122` |
| `trend_template.low_52w_min_pct` | TT6 `above 52w low` | `swing/evaluation/criteria/trend_template.py:96-108` |
| `vcp.prior_trend_min_pct` | `prior_trend.evaluate` | `swing/evaluation/criteria/prior_trend.py` (verified file exists; line refs in writing-plans) |
| `vcp.adr_min_pct` | `adr.evaluate` | `swing/evaluation/criteria/adr.py` |
| `vcp.pullback_max_pct` | `pullback.evaluate` | `swing/evaluation/criteria/pullback.py` |
| `vcp.proximity_max_pct` | `proximity.evaluate` | `swing/evaluation/criteria/proximity.py` |
| `vcp.tightness_days_required` | `tightness.evaluate` | `swing/evaluation/criteria/tightness.py` |
| `vcp.tightness_range_factor` | `tightness.evaluate` | `swing/evaluation/criteria/tightness.py` |
| `vcp.orderliness_max_bar_ratio` | `orderliness.evaluate` | `swing/evaluation/criteria/orderliness.py` |
| `vcp.orderliness_max_range_cv` | `orderliness.evaluate` | `swing/evaluation/criteria/orderliness.py` |
| `risk.max_risk_pct` | `risk_feasibility.evaluate` | `swing/evaluation/criteria/risk_feasibility.py` |
| `rs.horizon_weeks` | Affects `BatchContext.returns_12w_by_ticker` upstream (in §F batch reconstruction); NOT criterion-internal | `swing/evaluation/rs.py` + V2 `context_builder.py` |
| `rs.rs_rank_min_pass` | TT8 `RS rank` | `swing/evaluation/criteria/trend_template.py:124-145` |
| `rs.fallback_extreme_pct` | TT8 fallback path | `swing/evaluation/criteria/trend_template.py:146-155` |

**Special case `rs.horizon_weeks`**: this variable is CONSUMED at BatchContext construction time (12w return windowing), NOT at criterion-evaluation time. V2's `context_builder.build_batch_context(..., horizon_weeks=substituted_cfg.rs.horizon_weeks)` re-windows the returns dictionary. This is the ONE substitution that affects ALL candidates' batch context simultaneously (not just the candidate being evaluated). Documented in spec for writing-plans clarity.

### §E.3 Special case `vcp.watch_max_fails` (hardcoded in `bucket_for`)

`swing/evaluation/scoring.py:37` hardcodes `if vcp_fails <= 2:`. The value `2` is NOT cfg-derived; substituting `cfg.vcp.watch_max_fails` does NOTHING because no production code reads it.

V2 OPTIONS:
- **(a)** Promote `vcp.watch_max_fails` to cfg-derived in `swing/evaluation/scoring.py` as a 1-line production change. PROBLEM: violates §A.1 "Production `swing/` code is READ-ONLY through this dispatch arc." V2 dispatch declines this.
- **(b)** Mirror V1's `_bucket_for_substituted` pattern for this ONE variable: V2's sweep.py special-cases `variable_name == "vcp.watch_max_fails"` and threads the sweep_value into a V2-side `bucket_for_with_substituted_watch_max_fails(...)` mirror (NOT invoking production `bucket_for`). RECOMMEND (V2 ship target).
- **(c)** Drop `vcp.watch_max_fails` from V2 enumeration. PROBLEM: V1 covers it; dropping creates V2 regression. Rejected.

**V2 ship target = (b)**. V2 mirrors V1's existing `_bucket_for_substituted` watch_max_fails branch. The V2 mirror is at `research/harness/aplus_v2_ohlcv_evaluator/sweep.py` and is functionally IDENTICAL to V1's `_bucket_for_substituted` watch_max_fails branch but inputs are LIVE-recomputed Result tuples (from V2's `evaluate_one`) NOT persisted candidate_criteria rows (V1). Discriminating test asserts V2's watch_max_fails sweep produces same delta-counts as V1 against a fixture where the threshold variable substitutions are no-ops (sanity).

BANK as V2.5 (post-V2-ship, post-V2-study-output, operator-paired): "Promote `vcp.watch_max_fails` to cfg-derived in `bucket_for`" — a 1-line production-code change that closes the hardcode AND eliminates V2's special-case branch. Citation: OQ-11 disposition; dependency = operator approval + writing-plans cycle.

### §E.4 Baseline-recompute parity invariant

V2's first sanity check: when invoked with `substituted_cfg == production_cfg` (i.e., NO substitution; sweep_point == current_value for every variable), V2's bucket distribution MUST match the persisted bucket distribution from `candidates.bucket` exactly.

Failure mode (anti-pattern): V2 baseline diverges from persisted = some criterion has DRIFTED between when the persisted bucket was written (eval_run T) and when V2 re-evaluates against OHLCV at that asof_date. Discovered drift surfaces ANOTHER applied-research candidate (criterion-drift investigation) — banked as orthogonal to V2 OHLCV harness.

Acceptance criterion: `test_baseline_recompute_matches_persisted_bucket_distribution_exactly` (discriminating test, blocking landing).

Per cumulative gotcha "Session-anchor read/write mismatch": V2 reads `evaluation_runs.data_asof_date` (writer-stamped backward-looking session) to slice OHLCV — same anchor the production writer used. Verified via end-to-end discriminating test plant 1 candidate at fixture asof_date + re-evaluate → bucket matches.

### §E.5 OHLCV coverage failure handling (OQ-13 RECOMMEND)

When the OHLCV archive at `swing/data/ohlcv_archive.py` returns insufficient bars at the candidate's `data_asof_date` (most commonly: < 200 bars for trend_template's MA200 requirement at `swing/evaluation/criteria/trend_template.py:24-29`), V2 SKIPS the candidate for that variable-sweep with `OhlcvCoverageError` and increments `ohlcv_coverage_skip_count`. The skip is per-(variable, sweep_point) (NOT per-candidate-once) because a candidate might be evaluable for some variables but not others (e.g., variables whose criterion needs fewer bars are still evaluable).

V1 baseline parity is maintained even with skips: if N candidates skip at the current-value sweep point, those same N candidates skip at all sweep points, and the delta-vs-current-value math (per `delta_aplus = aplus_count - current_aplus`) correctly nets the skip-count out of the delta because the SAME candidates are skipped in both numerator and denominator.

Output reporting: V2's per-variable row in the sensitivity matrix surfaces `ohlcv_coverage_skip_count` explicitly so the operator sees coverage attrition. Study writeup's "Limitations" section enumerates skip percentage if material.

---

## §F OHLCV archive reconstruction strategy

### §F.1 Strategy decision (OQ-1 RECOMMEND)

V2 uses **production OhlcvArchive piggyback with `prefer_source='yfinance'` enforcement** (OQ-1 option c, refined for L2 LOCK preservation per OQ-12 RECOMMEND).

Rationale:
- **Reproducibility**: production OHLCV archive at `swing/data/ohlcv_archive.py` is the operator's authoritative OHLCV state. V2 reading from it ensures V2 outputs are reproducible against the operator's archive.
- **L2 LOCK preservation (OQ-12)**: passing `prefer_source='yfinance'` (per `_SOURCE_PRECEDENCE_MARKET_DATA` shape in ohlcv_archive.py — verified at spec-write time at lines 52-58) routes V2 reads to the yfinance Shape A parquet, NEVER to the schwab_api Shape A parquet. ZERO new Schwab API calls. Discriminating test mocks both Shape A files + asserts only yfinance bytes consumed.
- **No double-cache**: avoids the earnings_proximity research-cache pattern (which duplicates archive data at `%USERPROFILE%/swing-data/research-cache/ohlcv/`). For V2 OHLCV harness specifically — where the operator's archive ALREADY contains the relevant historical bars per S3's recent-eval_run coverage — double-caching adds maintenance burden without benefit.
- **Coverage failure**: when archive read returns insufficient bars (rare; historical S3 universe spans last 63 eval_runs which is well within archive retention), per §E.5 skip-and-report.

REJECTED alternatives:
- **Fetch-on-demand via live yfinance**: 5681 candidates × per-candidate fetch is rate-limit-prohibitive AND blocks reproducibility (later runs hit different yfinance-version state).
- **Limit-to-recent only**: artificially shrinks the universe + doesn't actually need to be done; the archive covers what's needed for S3's last-63-eval_runs scope.
- **Independent research-cache (earnings_proximity-style)**: dupe-storage with no offsetting benefit since V2 is operator-paired (not arc-spanning). Acknowledged as PRECEDENT but rejected for V2-specific reasons.

### §F.2 OHLCV slicing semantics

For each candidate `(ticker, data_asof_date)`:

1. Read full per-ticker parquet via `swing.data.ohlcv_archive.read_or_fetch_archive(ticker, ..., prefer_source='yfinance', ..., end_date=data_asof_date)`. Returns DataFrame indexed by date with OHLCV columns.
2. Slice to bars `<= data_asof_date` (inclusive of asof_date; OHLCV is the session that JUST closed at writer-stamp time per `data_asof_date` backward-looking semantics).
3. Verify `len(sliced) >= 200` (minimum for TT MA200 per `swing/evaluation/criteria/trend_template.py:24-29`). If insufficient, raise `OhlcvCoverageError` (caught at sweep.py per §D.4).
4. Pass sliced DataFrame to `CandidateContext(ohlcv=sliced, ...)`.

Per cumulative gotcha "Session-anchor inequality discipline depends on anchor directionality (backward-looking vs forward-looking)": `data_asof_date` is BACKWARD-looking (the session that just closed at eval_run time). Strict `>` inequality applies when stripping the in-progress bar (per the existing lesson) — but for V2 V2-time slicing the data is HISTORICAL ARCHIVE (no in-progress bar exists at the asof_date), so the strip is moot. V2 uses simple `<=` slicing per the precedent at `research/harness/earnings_proximity/replay.py:142-143`. Discriminating test plants archive at end of asof_date + verifies the asof_date bar IS included.

### §F.3 Candidate universe SQL skeleton (Expansion #4 refinement BINDING)

Per cumulative gotcha "Brief-vs-actual schema reality check + SQL skeleton column verification": every SQL skeleton's columns verified against actual migration files. Verified at spec-write time:

```sql
-- Read the last N eval_runs (mirror V1 sweep.py:60-62)
SELECT id, data_asof_date
  FROM evaluation_runs
  ORDER BY id DESC
  LIMIT :eval_runs_window;
```
Verified: `evaluation_runs.id` + `evaluation_runs.data_asof_date` exist at `swing/data/migrations/0001_phase1_initial.sql:9-12`.

```sql
-- Read all candidates in those eval_runs (V2's primary universe scan)
SELECT c.id, c.ticker, c.bucket, er.data_asof_date
  FROM candidates c
  JOIN evaluation_runs er ON er.id = c.evaluation_run_id
  WHERE c.evaluation_run_id IN (:eval_run_ids)
  ORDER BY er.id DESC, c.ticker ASC;
```
Verified: `candidates.id` + `candidates.ticker` + `candidates.bucket` + `candidates.evaluation_run_id` exist at `swing/data/migrations/0001_phase1_initial.sql:25-28+26`. `evaluation_runs.data_asof_date` already verified.

Per cumulative gotcha "SQL aggregation UNIT audit (Expansion #8 candidate)": V2's SQL does NOT use COUNT / GROUP BY / SUM — it's a pure row-fetcher. No JOIN-cardinality concerns. No DISTINCT needed (PRIMARY KEY on `candidates.id` guarantees per-row uniqueness). Verified.

**Universe size at V2 baseline (operator DB; per S3 output)**: 5681 candidates across 63 eval_runs = ~90 candidates per eval_run avg. V2 universe scan returns 5681 rows + per-row OHLCV reconstruction.

### §F.4 BatchContext reconstruction at historical asof_date

Per `swing/evaluation/context.py:14-19`, BatchContext requires:

- `returns_12w_by_ticker: dict[str, float]` — cross-sectional 12-week returns
- `universe_tickers: tuple[str, ...]`
- `universe_version: str`
- `universe_hash: str`
- `spy_return_12w: float`

V2 reconstructs at each `(eval_run_id, data_asof_date)` cohort:

1. `universe_tickers` = the set of all candidate tickers in that eval_run (from the §F.3 SQL).
2. `universe_version` = `f"v2_harness_eval_run_{eval_run_id}"` (NOT the production universe-version; V2 is a research-branch invariant per §A.1).
3. `universe_hash` = SHA-1 of the sorted `universe_tickers` tuple (deterministic; reproducible).
4. `returns_12w_by_ticker` = per-ticker 12-week return computed from the OHLCV archive slice (mirror earnings_proximity `_return_12w` at `research/harness/earnings_proximity/replay.py:146-158`). Per-ticker skip if <60 bars history available.
5. `spy_return_12w` = SPY's 12-week return at the asof_date (separate OHLCV archive read).

**The `rs.horizon_weeks` substitution** propagates here: when V2 substitutes `rs.horizon_weeks=14`, the BatchContext reconstruction MUST window returns at 70 trading days (14 × 5), NOT the default 60. V2's `context_builder.build_batch_context(..., horizon_weeks=substituted_cfg.rs.horizon_weeks)` accepts the parameter explicitly.

### §F.5 Per-eval_run batch reuse optimization

Performance optimization (post writing-plans validation): V2 caches the BatchContext per `(eval_run_id, substituted_cfg.rs.horizon_weeks)` tuple to avoid recomputing the same returns_12w dictionary across N tickers in the same eval_run. Reduces total BatchContext reconstructions from 5681 candidates × 17 variables × 5 sweep_points = ~482k to 63 eval_runs × ~5 distinct horizon_weeks values + standard horizon_weeks default = ~315 reconstructions.

This optimization is NOT load-bearing for V2 ship (writeup-time complexity acknowledged); V2 ships with simple per-candidate reconstruction if the optimization adds non-trivial code complexity. Acceptance criterion: V2 runtime under 60 minutes for the 5681 / 63 / 17 / 5 universe per OQ-9 budget.

---

## §G Output format

### §G.1 Sensitivity matrix (top-level, parity-preserving) — OQ-4 hybrid (a) component

V2 emits a CSV mirroring V1's 9-column shape PLUS 3 NEW skip-count columns per §D.3:

```
variable_name, kind, sweep_point,
aplus_count, watch_count, skip_count, excluded_count,
delta_aplus, delta_watch,
out_of_range_skip_count, ohlcv_coverage_skip_count, evaluation_error_skip_count
```

V2 markdown matrix mirrors V1's table format (12 columns instead of 9 — see §D.3 taxonomy-propagation invariant). The markdown matrix's HEADLINE summary section (placed ABOVE the matrix) directly answers operator's motivating question per §B.1:

> ## Headline: variables binding at watch→A+ boundary (V2 OHLCV recompute)
>
> Top 5 by marginal A+ count per loosening unit (sorted descending; loosening = sweep direction that grows A+):
>
> 1. `<variable>` at sweep_point=<X> → A+ delta +<N> (<+P%>)
> 2. ...
> [zero entries if no variable produces non-zero delta_aplus in the 5-point grid]

The headline answers the operator's question in ONE table at the top. The full sensitivity matrix follows for completeness.

### §G.2 Per-variable drill-down (OQ-4 hybrid (b) component)

For EACH variable with `max(|delta_aplus|) > 0` across its sweep grid, V2 emits a drill-down section in the markdown:

```
## Drill-down: <variable_name>

| Sweep point | Direction | A+ delta | Candidates flipped (watch→A+) | Candidates flipped (A+→watch) | Candidates flipped (skip→watch) | ... |
|-------------|-----------|----------|---|---|---|---|
| <pt-2>      | loosen    | +<N>     | <ticker_1, ticker_2, ...>      | ...                            | ...                              | ... |
| <pt-1>      | loosen    | +<N>     | ...                            | ...                            | ...                              | ... |
| <current>   | -         | 0        | (anchor)                       |                                |                                  |     |
| <pt+1>      | tighten   | -<N>     | ...                            | ...                            | ...                              | ... |
| <pt+2>      | tighten   | -<N>     | ...                            | ...                            | ...                              | ... |
```

Plus a per-flipped-candidate provenance block:

```
### Candidates flipped (watch→A+) at <variable>=<sweep_point>:

- <ticker> (eval_run=<id>, data_asof_date=<date>): old criterion failure = '<criterion_name>' (value=<old_value>, rule='<old_rule>'); new evaluation = 'pass' under substituted threshold.
```

This drill-down enables the OPERATOR to inspect WHICH candidates flipped + WHY they flipped (per-criterion attribution). Critical for the downstream cfg-policy threshold-loosening proposal-drafting workflow per Path B disposition.

### §G.3 V1↔V2 comparison section (NEW; not in V1)

V2 markdown emits a "V1↔V2 parity" section reporting:

- Baseline A+ count (V1 persisted) vs Baseline A+ count (V2 recompute at current_value). MUST match exactly per §E.4 invariant; if mismatch, the markdown surfaces "CRITERION DRIFT DETECTED" alert + lists divergent candidates.
- Gate-variable resimulation: V1's `_bucket_for_substituted` gate output for `trend_template.min_passes` + `vcp.watch_max_fails` vs V2's `evaluate_one`-recomputed gate output. SHOULD match per parity invariant; surfaces deltas if any.

### §G.4 Per-variable scope-reduction reporting

When V2 skips candidates per §E.5 (OHLCV coverage) OR §D.2 (out-of-range substitution) OR §D.4 (evaluation error), the per-variable row in the matrix surfaces the skip counts as explicit columns (per §G.1). Additionally, the markdown's "Notes" section enumerates per-variable scope-reduction summary:

```
## Notes

- Total V2 universe: <N> candidates across <M> eval_runs.
- Per-variable coverage: <variable_1>: <N - skip_count> evaluable / <N> total (<P%> coverage).
- ...
```

### §G.5 ASCII-only output (cumulative gotcha BINDING)

Per cumulative gotcha "Windows PowerShell stdout defaults to cp1252; non-ASCII glyphs ... will raise `UnicodeEncodeError`": V2 output (CSV + markdown) MUST be cp1252-encodable. Test verifies via `text.encode("cp1252")` mirroring V1's pattern at `tests/research/test_aplus_sensitivity_output.py` + `tests/cli/test_diagnose_subcommands.py`.

Particular discipline:
- NO `→` arrow glyphs in the drill-down "flipped" descriptions; use ASCII `-> ` or `:` syntax.
- NO `§` section markers in CLI output strings (markdown body is allowed `§` since markdown doesn't go through stdout; only `click.echo()` paths matter).
- NO em-dash `—` in CSV cells or `print()` strings; ASCII `-` substitutes.

### §G.6 Output empty-state representation

Per cumulative T3.SB3 lesson "Audit envelope empty-state representation must be uniform across emit + persist paths": V2 output empty-state (e.g., a variable with no per-candidate flips for drill-down) uses `(none)` literal string in the drill-down section, NOT empty string OR `null`. Uniform across CSV + markdown emit paths.

---

## §H Test scope projection

### §H.1 Per-task test budget (writing-plans phase will decompose)

Estimated test count for V2 OHLCV harness brainstorming → executing-plans full landing:

| Module / area | Tests | Detail |
|---------------|-------|--------|
| `context_builder.py` | ~10 | OHLCV slicing at asof_date; BatchContext reconstruction; per-ticker skip on <60 bars; rs.horizon_weeks parameter threading; OHLCV-coverage error path |
| `cfg_substitution.py` | ~6 | substitute_cfg per-subsection (4) + unknown-subsection ValueError + type-preservation invariant |
| `sweep.py` | ~12 | per-(variable, sweep_point) orchestration; baseline parity invariant (CRITICAL); cross-coupling preservation; vcp.watch_max_fails special case; per-candidate failure isolation (3 modes); out-of-range substitution skip; ohlcv-coverage skip; evaluation-error skip; multi-eval_run universe scan |
| `output.py` | ~8 | CSV header includes 3 new skip columns; markdown matrix renders 12 columns; headline section emits correctly; drill-down emits per-flipped-candidate provenance; ASCII-only output (cp1252 round-trip); V1↔V2 parity section emits CRITERION DRIFT alert on mismatch; per-variable scope-reduction notes; empty-state representation uniform |
| `run.py` / CLI | ~6 | argparse boundaries (--eval-runs range; --variables-filter parsing); ClickException wrapping ValueError; --max-runtime-seconds cap; output file path conventions; baseline smoke (operator's actual DB shape via fixture) |
| Integration / E2E | ~4 | end-to-end synthetic-universe run; V1↔V2 parity discriminating test; OHLCV coverage failure discriminating test; runtime budget smoke (5681-candidate universe completes within OQ-9 cap; fixture-based) |
| **Total** | **~46** | Within T-T4.SB.1's ~30-40 test budget magnitude; slightly larger due to V2's expanded substitution scope (15 threshold variables vs V1's 2 gate variables) |

### §H.2 Discriminating-test patterns inherited from cumulative gotcha catalog

Each pattern below is a BINDING test for V2 per the cited cumulative gotcha:

- **Schema-CHECK + Python-constant + dataclass-validator paired discipline (cumulative)** — N/A V2 (no schema change); but the propagation principle applies to V2's `SweepEntryV2` kind enum (inherited from V1's V1-level taxonomy; same enum values).
- **F6 (write-through-cache transient empty) defense (cumulative)** — N/A V2 writes no cache rows; OHLCV archive write-through is owned by production code (READ-ONLY by V2).
- **`Literal[...]` type hints are NOT runtime-enforced (cumulative)** — DIRECTLY APPLIES to V2's `SweepEntryV2.kind`; same `__post_init__` validation pattern as V1 `SweepVariable.kind` per `research/harness/aplus_sensitivity/variables.py:39-44`.
- **Service-layer ValueErrors must be wrapped at CLI boundary (cumulative)** — DIRECTLY APPLIES to V2 CLI per §C.2.
- **`date.fromisoformat()` discipline (cumulative gotcha #12)** — DIRECTLY APPLIES; `evaluation_runs.data_asof_date` is TEXT (ISO format); V2's `context_builder` MUST convert via `date.fromisoformat(row[1])` at the SQL boundary. Discriminating test: plant a row with malformed ISO date + assert `MalformedAsofDateError` (typed) NOT `TypeError` deep in stack.
- **Bad-exemplar isolation in retrieval functions (cumulative T2.SB5)** — DIRECTLY APPLIES per §D.4. Discriminating test: 3-candidate fixture (1 good + 2 failure-mode) asserts only failure-mode candidates skip + good candidate tallied.
- **External-API empty-result transient defense (cumulative F6)** — N/A direct (V2 doesn't fetch from external API; uses archive). But indirectly relevant if archive read returns empty parquet: V2 treats as OhlcvCoverageError + skip (per §E.5), NOT silent ZERO-bar evaluation.
- **Synthetic-fixture-vs-production-emitter shape drift (cumulative, 4 instances)** — DIRECTLY APPLIES to V2 test fixtures: V2 fixture data (synthetic OHLCV bars + synthetic candidate rows) MUST shape-match what `swing.data.ohlcv_archive.read_or_fetch_archive` would actually return AND what `swing.data.repos.candidates.insert_candidates` would actually persist. Discriminating test: derive fixture from a real eval_run dump (write a fixture-generator that consumes operator's DB + dumps to JSON) per the cumulative defense-in-depth pattern.

### §H.3 Test count baseline + V2 bump projection

V2 brainstorming docs-only: ZERO test delta (baseline 5778 fast tests UNCHANGED through brainstorming phase).

V2 writing-plans + executing-plans projected: +46 fast tests (~5824 total post-V2-ship).

NO slow-marked tests in V2 dispatch scope (V2 operates against OHLCV archive read-only; no live API calls).

### §H.4 Cross-bundle pin disposition (cumulative discipline)

V2 dispatch is NEW research-branch arc; NO existing cross-bundle pins exist. V2 shipping does not affect any existing pin's un-skip schedule.

Forward-binding: if V2 ship reveals criterion drift (per §E.4 baseline parity invariant fails), a NEW cross-bundle pin may be needed at the criterion-implementation point. Decision deferred to writing-plans phase post operator-triage.

---

## §I OQs surfaced for operator-paired triage

13 OQs surfaced — 8 from dispatch brief §1.1 + 5 NEW from substrate analysis. Each OQ has a RECOMMEND disposition; final disposition is operator-paired between brainstorming + writing-plans phases.

### OQ-1: OHLCV reconstruction scope

**Question**: Limit-to-recent vs fetch-on-demand vs piggyback?

**RECOMMEND**: Piggyback production OhlcvArchive with `prefer_source='yfinance'` enforcement (refinement of option (c)) per §F.1. Reuses operator's authoritative archive; preserves L2 LOCK (OQ-12); reproducible.

### OQ-2: Per-criterion evaluator interface

**Question**: Mutate cfg dataclass vs explicit override-dict?

**RECOMMEND**: (a) mutate cfg via `dataclasses.replace` + invoke production `evaluate_one(ctx)` end-to-end per §D.1. High-fidelity; cross-coupling preserved for free. Special case `vcp.watch_max_fails` per §E.3 / OQ-11.

### OQ-3: Sweep range strategy per variable

**Question**: Inherit V1 5-point grid vs adaptive bisection vs full-range?

**RECOMMEND**: (a) inherit V1 5-point grid per V2.1 §IV.B parsimony. Adaptive bisection deferred V3+.

### OQ-4: Output format

**Question**: Same V1 shape vs per-candidate granular vs hybrid?

**RECOMMEND**: (c) hybrid — V1 9-col matrix at top (+3 new skip cols) + per-variable drill-down sections + headline section + V1↔V2 parity section per §G. Answers operator's binding-variable question in headline; enables downstream cfg-policy work via drill-down.

### OQ-5: Scope discipline

**Question**: All 15 inert variables in one dispatch vs phased?

**RECOMMEND**: All 15 in one dispatch. Shared infrastructure (OHLCV reconstruction + cfg substitution + evaluate_one invocation) is identical across the 15; phasing creates orphan V2 stub state + duplicate infrastructure.

### OQ-6: Validation universe

**Question**: Reuse S3's 5681 candidates / 63 eval_runs OR fresh fetch?

**RECOMMEND**: Reuse the operator's existing S3 universe (5681 / 63). Reproducibility — direct V1↔V2 comparison of "which variables matter" against the same universe. A fresh fetch conflates threshold-substitution effects with universe-drift effects.

### OQ-7: Cross-coupling

**Question**: V2 stays 1D vs introduces pair-wise variables?

**RECOMMEND**: 1D per V2.1 §IV.B parsimony. 2D + interaction terms deferred V3+. Note that cross-coupling is preserved WITHIN a single 1D substitution per §D.1 (e.g., substituting `rs.rs_rank_min_pass` propagates through TT8 → `tt_passes` → `bucket_for`).

### OQ-8: Method-record promotion criteria

**Question**: What evidence threshold for research → shadow → production per V2.1 §IV.D?

**RECOMMEND**: 3-tier promotion ladder per §K.3:

- **research → shadow** (post V2 ship + first study output): (i) V2 OHLCV harness shipped + V2 baseline parity invariant green per §E.4; (ii) ≥1 study writeup published; (iii) AT LEAST ONE binding threshold variable identified (`max(|delta_aplus|) > 0` for ≥1 variable) OR all 15 declared NON-binding with operator-paired sign-off.
- **shadow → production** (post cfg-policy proposal evaluation): (i) ≥1 cfg-policy proposal evaluated against ≥2 disjoint validation universes (operator's 5681-candidate universe + a future operator-paired holdout); (ii) proposal's A+ delta is statistically distinguishable from baseline (default proposed: ≥5 A+ delta on a 5681-candidate universe — i.e., doubling A+ count); (iii) operator-paired ratification.
- **Anti-promotion guards**: regression on existing A+ candidates' bucket assignments; cross-coupling instability (binding threshold flips when OTHER variables are held at different values); production-cfg drift would invalidate the evidence (re-evaluation required if production cfg changed since the V2 study output).

### OQ-9 (NEW): Performance budget cap

**Question**: V2 invokes `evaluate_one` 5681 × 17 × 5 = ~482k times. At ~5ms each = ~40 min runtime (envelope; actual may be 2-3x). Cap V2 runtime at N seconds via `--max-runtime-seconds` flag?

**RECOMMEND**: Default UNSET (no cap) for operator's first run. Provide `--max-runtime-seconds N` CLI flag for partial-run capability. Acceptance target: <60 minutes on operator's hardware for the full 5681 / 63 / 17 / 5 universe. If V2 exceeds, V2.5 work targets §F.5 per-eval_run BatchContext reuse optimization.

### OQ-10 (NEW): V2 CLI surface name

**Question**: V2 CLI name — `aplus-sensitivity-v2` vs `aplus-ohlcv-evaluator` vs rename V1 to `aplus-sensitivity-gates` + V2 takes `aplus-sensitivity`?

**RECOMMEND**: `swing diagnose aplus-sensitivity-v2`. Less invasive than renaming V1; back-compat preserved; "v2" suffix is explicit about lineage. Operators familiar with V1's `swing diagnose aplus-sensitivity` find V2 via tab-complete or `swing diagnose --help` enumeration.

### OQ-11 (NEW): `vcp.watch_max_fails` hardcode handling

**Question**: Production `bucket_for` at `swing/evaluation/scoring.py:37` hardcodes `vcp_fails <= 2`. V2's `vcp.watch_max_fails` substitution — promote to cfg-derived in production (1-line change; violates §A.1 read-only invariant) OR mirror V1's special-case substitution OR drop from V2 enumeration?

**RECOMMEND**: (b) mirror V1's special-case per §E.3. V2 ship target. BANK as V2.5: "Promote `vcp.watch_max_fails` to cfg-derived in `bucket_for` (1-line production change)" — operator-paired triage post V2 ship, closes the hardcode for V3+.

### OQ-12 (NEW): Schwab API L2 LOCK preservation

**Question**: V2 OHLCV reconstruction may fall through Schwab API in the production ladder (via `swing/data/ohlcv_archive.py`'s `_SOURCE_PRECEDENCE_MARKET_DATA` shape — verified at lines 52-58: `schwab_api: 0, yfinance: 1`). V2 must explicitly enforce yfinance-only.

**RECOMMEND**: V2 invokes `read_or_fetch_archive(..., prefer_source='yfinance', ...)` (or equivalent — actual signature verification in writing-plans phase). Discriminating test: plant both schwab_api Shape A and yfinance Shape A parquet files for a synthetic ticker + assert V2 reads ONLY the yfinance bytes (e.g., via byte-checksum compare; or via mock that fails the schwab read path). L2 LOCK preserved (ZERO new Schwab API calls through V2 dispatch).

### OQ-13 (NEW): OHLCV coverage failure attribution mode

**Question**: When archive returns <200 bars at candidate's asof_date → V2 attribution? (a) skip + report; (b) substitute persisted bucket (V1 fallback); (c) abort.

**RECOMMEND**: (a) skip + report per §E.5. Clean attribution (V2 cannot recompute → V2 has no opinion). Surfaces in per-variable `ohlcv_coverage_skip_count` column + per-study scope-reduction notes per §G.4.

---

## §J Forward-binding lessons inherited

### §J.1 Cumulative gotcha set (16 cumulative)

Per CLAUDE.md updates through `2a56158`+`f1044ee` (gotchas #9-#16) + Expansion #11 candidate banked at `9b2a4db` + Expansion #12 candidate banked at `acaf305`:

Per `docs/v2-ohlcv-criterion-evaluator-brainstorming-dispatch-brief.md` §3.2 (16 cumulative gotcha enumeration):

| # | Gotcha | V2 applicability |
|---|--------|------------------|
| 9 | SQL aggregation UNIT audit | N/A (V2 SQL is pure row fetch; no GROUP BY / COUNT / SUM). Verified at §F.3. |
| 10 | Existing-field reuse audit | DIRECTLY APPLIES per §D.3 (V2 `SweepEntryV2` adds 3 NEW skip-count fields; verified V1 `SweepEntry` has no equivalents at `research/harness/aplus_sensitivity/sweep.py:33-49`; no field duplication). |
| 11 | Template-rendering surface audit | N/A (V2 has no Jinja templates; CSV + markdown emission via Python `print` / `csv.writer`). |
| 12 | `date.fromisoformat()` cross-type-boundary | DIRECTLY APPLIES per §H.2 (V2 reads `evaluation_runs.data_asof_date` TEXT → date conversion). |
| 13 | Form-render anchor lifecycle | N/A (V2 has no web routes / forms). |
| 14 | Architecture-location 5-sub-discipline (Expansion #10) | DIRECTLY APPLIES per §C.1 (NEW module placement decision documented; per-criterion evaluator location + cfg-substitution location + sweep orchestration location justified). |
| 15 | Taxonomy propagation (Expansion #11) | DIRECTLY APPLIES per §D.3 (V2 `SweepEntryV2.kind` inherits V1 enum; 3 NEW field propagation across dataclass + CSV header + markdown matrix + fixtures verified). |
| 16 | Sibling-route audit (Expansion #12) | N/A (V2 has no route handlers; single-CLI-entry-point). |

### §J.2 Pre-Codex 7-expansion + 5 NEW candidate refinements verification

Per brainstorming-phase pre-Codex review discipline (BINDING per dispatch brief §3.1; 31st cumulative C.C lesson #6 validation expected):

| # | Expansion | V2 brainstorming-phase application |
|---|-----------|-----------------------------------|
| 1 | Hardcoded-duplicate audit | `vcp.watch_max_fails = 2` hardcoded at `swing/evaluation/scoring.py:37` — V2 mirrors V1 special-case per OQ-11. NO other hardcoded duplicates of the 15 threshold variables found via `grep -n` against `swing/evaluation/criteria/*.py`. |
| 2 | Brief-vs-spec + brief-vs-actual schema verification | Dispatch brief substrate verified end-to-end vs spec; schema column references verified at §A.2. NO drift. |
| 3 | Schema-CHECK vs semantic-contract gap | N/A V2 (no schema change); semantic-contract for V2's `SweepEntryV2.kind` enum mirrors V1's runtime `__post_init__` validation. |
| 4 | Specific-scenario gotcha trace + SQL skeleton column verification | Walked: `date.fromisoformat()` boundary at `evaluation_runs.data_asof_date` per §F.2 + §H.2 → discriminating test pattern enumerated. SQL skeletons at §F.3 verified column-by-column against `swing/data/migrations/0001_phase1_initial.sql`. |
| 5 | Cross-section spec inventory grep | §E.2 cfg-variable → criterion mapping table grepped against `swing/evaluation/criteria/*.py` at spec-write time. |
| 6 | Content-completeness audit | Each spec checklist item from dispatch brief §4 mapped to a section in this spec (§A=A; §B=B; §C=C; §D=D; §E=E; §F=F; §G=G; §H=H; §I=I; §J=J; §K=K; §L=L; §M=M). NO `(n/a)` / `(TBD)` placeholders. NO V1-STUB silent ship. |
| 7 | Cross-row semantic SCOPE audit + scope-vs-unit boundary | N/A (V2 has no operator-input POST handler; pure CLI invocation). |
| 8 (cand) | Per-aggregation-function UNIT audit on SQL skeletons | V2's SQL has NO aggregation functions per §F.3. N/A this dispatch. |
| 9 (cand) | Form-render anchor lifecycle 4-dimension audit | N/A (no forms). |
| 10 (cand) | Architecture-location audit + 5 sub-disciplines | DIRECTLY APPLIED at §C.1 — module placement + dependency-surface verification + cache-key uniformity LOCK (N/A this dispatch) + SQL LIKE wildcard-escape (N/A this dispatch) + orphan-label preservation (mapped to V2's OHLCV-coverage skip handling per §C.1 sub-discipline (e)). |
| 11 (cand) | Taxonomy propagation audit | DIRECTLY APPLIED at §D.3 — V2 inherits V1's `{gate, threshold_additive, threshold_multiplicative}` enum verbatim; 3 NEW skip-count fields propagated through dataclass + CSV header + markdown matrix + test fixtures per the V2 propagation invariant. |
| 12 (cand) | Sibling-route audit when introducing single-anchor-binding discipline | N/A (no route handlers; no single-anchor invariant). |

V2 brainstorming-phase pre-Codex review = ALL 7 EXPANSIONS + 5 NEW CANDIDATE REFINEMENTS verified CLEAN at spec-write time. Awaiting Codex MCP chain for 31st cumulative C.C lesson #6 validation result capture.

### §J.3 T4.SB executing-plans forward-binding lessons (5 banked at `2a56158`)

Per dispatch brief §J reference. V2 inherits the lesson family:

- T4.SB.1 lesson — V2 enumerates ALL 15 threshold variables in one dispatch per OQ-5 (not phased).
- T4.SB.2 lesson — V2 surface dependencies verified at §C.1 architecture-location audit.
- T4.SB.3 lesson — V2 has no JIT cache; N/A.
- T4.SB.4 lesson — V2 emits ASCII-only output per §G.5.
- T4.SB.5 lesson — V2 inherits the V1 `SweepVariable.kind` enum without introducing new enum taxonomy.

---

## §K Method-record extension to `aplus-criteria-calibration.md`

The existing 72-line method-record at `research/method-records/aplus-criteria-calibration.md` extends with:

### §K.1 Updated `version` + `last_updated`

```yaml
---
key: aplus-criteria-calibration
name: A+ criteria parameter sensitivity calibration
layer: ranking
status: research
baseline_or_predecessor: internal (swing.evaluation.scoring.bucket_for current cfg)
version: 0.2.0  # bumped from 0.1.0 — V2 OHLCV harness shipped
last_updated: <V2 ship date>
---
```

### §K.2 NEW section after V2 dependencies — "V2 OHLCV harness shipped (status='research')"

Documents:
- V2 OHLCV criterion-evaluator harness module location (`research/harness/aplus_v2_ohlcv_evaluator/`)
- V2 CLI surface (`swing diagnose aplus-sensitivity-v2`)
- V2 vs V1 substitution semantic differences (per §A.4)
- V2's coverage of all 15 threshold variables + 2 gate variables (per OQ-5)
- V2-shipped V1-LIMITATION lift status (V2 closes the V1 LIMITATION per §B.1)

### §K.3 NEW section — "Promotion criteria (research → shadow → production)"

Per OQ-8 RECOMMEND + V2.1 §IV.D + §VII.C lifecycle posture:

- **research → shadow**:
  1. V2 OHLCV harness shipped + baseline parity invariant green per §E.4 of design spec.
  2. ≥1 V2 study writeup published.
  3. AT LEAST ONE binding threshold variable identified OR all 15 declared non-binding with operator-paired sign-off.
- **shadow → production**:
  1. ≥1 cfg-policy proposal evaluated against ≥2 disjoint validation universes.
  2. Proposal's A+ delta statistically distinguishable from baseline (default threshold proposed: ≥5 A+ delta on a 5681-candidate universe — doubling A+ count).
  3. Operator-paired ratification.
- **Anti-promotion guards**: regression on existing A+ candidates; cross-coupling instability; production-cfg drift.

### §K.4 Updated Validation notes section

Append:

- **V2-recompute baseline parity invariant**: V2 invoked with no substitution (sweep_point == current_value for every variable) MUST produce the same bucket distribution as V1's persisted-bucket pass per §E.4. Discriminating test: `tests/research/test_aplus_v2_ohlcv_sweep.py::test_baseline_recompute_matches_persisted_bucket_distribution_exactly`.
- **V1↔V2 gate-variable parity**: V2's gate substitution for `trend_template.min_passes` MUST produce the same delta-counts as V1's `_bucket_for_substituted` mirror path. Discriminating test: `tests/research/test_aplus_v2_ohlcv_sweep.py::test_v2_gate_substitution_matches_v1_bucket_for_substituted_output`.
- **Per-candidate failure isolation**: V2 candidates failing OHLCV coverage / out-of-range substitution / arbitrary evaluation error MUST NOT poison other candidates' tallies. Discriminating test: 3-candidate fixture per §D.4.

### §K.5 Notes section append

- V2 ships with `vcp.watch_max_fails` special-cased per §E.3 to mirror V1's `_bucket_for_substituted` semantics (production `swing/evaluation/scoring.py:37` hardcoded value `2` not cfg-derived).
- V2 BANK: Promote `vcp.watch_max_fails` to cfg-derived in `bucket_for` as V2.5 production-code change candidate (operator-paired ratification post V2 ship).
- V2 BANK: `cfg.trend_template.allowed_miss_names` tuple-set sweep + `cfg.rs.benchmark_ticker` string-identifier sweep STAY V3+ (consistent with V1 method-record §"Notes" line 70 enumeration).
- V2 NOT-scoped: schema changes (`candidate_criteria` structured threshold columns) STAY V3+ per V1 method-record V2 dependencies #2.
- V2 NOT-scoped: pair-wise cross-coupling STAYS V3+ per V1 method-record V2 dependencies #3.

---

## §L Cross-references + V2.1 governance citations

### §L.1 V2.1 governance citations

- **V2.1 §V branch posture**: V2 OHLCV harness lives under `research/` (V2.1 governing strategy at [`reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md`](../../../reference/Future%20Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md)). Production `swing/` stable through V2 dispatch.
- **V2.1 §IV.B minimum viable method-record fields**: V2 method-record extension per §K honors the minimum viable field list (key + name + layer + status + version + last_updated + Definition + Inputs + Parameters + Outputs + Operator explainability + Validation notes + Changelog). NEW V2-shipped sections + Promotion criteria sections added per §K.2 + §K.3.
- **V2.1 §IV.D + §VII.C lifecycle posture**: V2 ships at `status='research'`; promotion ladder per OQ-8 + §K.3.
- **V2.1 §IV.B parsimony**: V2 stays 1D per OQ-7; V2 inherits V1 5-point sweep grid per OQ-3 (no full-range sweep); V2 has no cross-coupling explicit modeling.
- **V2.1 §VII.F source-of-truth correction protocol**: applies only if V2 outputs surface a methodology-reference drift. NOT triggered by V2 ship itself.
- **V2.1 §X tranche progression**: V2 is the first method-record under `aplus-criteria-calibration` lineage per OQ-CL.3 LOCK; subsequent applied-research arcs follow the established pattern.

### §L.2 Repository cross-references

- Dispatch brief: [`docs/v2-ohlcv-criterion-evaluator-brainstorming-dispatch-brief.md`](../../v2-ohlcv-criterion-evaluator-brainstorming-dispatch-brief.md)
- Triage agenda (Path B LOCKED): [`docs/phase13-closer-next-phase-triage.md`](../../phase13-closer-next-phase-triage.md)
- S3 sensitivity-harness output: `exports/diagnostics/aplus-sensitivity-20260523T065514Z.md` + `.csv` (operator's actual S3 run)
- Method-record (PRIMARY substrate): [`research/method-records/aplus-criteria-calibration.md`](../../../research/method-records/aplus-criteria-calibration.md)
- V1 harness: [`research/harness/aplus_sensitivity/`](../../../research/harness/aplus_sensitivity/) (variables.py + sweep.py + output.py + run.py)
- V1 study writeup: [`research/studies/aplus-criterion-sensitivity-2026-05-22.md`](../../../research/studies/aplus-criterion-sensitivity-2026-05-22.md)
- Research-branch precedent: [`research/harness/earnings_proximity/`](../../../research/harness/earnings_proximity/) + [`research/studies/earnings-proximity-exclusion.md`](../../../research/studies/earnings-proximity-exclusion.md) + [`research/method-records/earnings-proximity-exclusion.md`](../../../research/method-records/earnings-proximity-exclusion.md)
- Production `bucket_for`: `swing/evaluation/scoring.py`
- Production `evaluate_one`: `swing/evaluation/evaluator.py`
- Production criteria: `swing/evaluation/criteria/*.py` (8 trend_template criteria + 9 vcp criteria + 1 risk criterion)
- Production OHLCV archive: `swing/data/ohlcv_archive.py`
- Production candidate_criteria repo: `swing/data/repos/candidates.py:78` (write path)
- Schema migrations: `swing/data/migrations/0001_phase1_initial.sql` (candidates + candidate_criteria + evaluation_runs) + `swing/data/migrations/*.sql` (subsequent)
- CLAUDE.md at repo root (16 cumulative gotchas; #14 + #15 + #12 most relevant to V2 design)
- T4.SB return reports (cumulative discipline lineage):
  - `docs/phase13-t4-sb-brainstorm-return-report.md`
  - `docs/phase13-t4-sb-writing-plans-return-report.md`
  - `docs/phase13-t4-sb-executing-plans-return-report.md`

---

## §M Dispatch sequence

### §M.1 Sub-bundle decomposition recommendation for executing-plans phase

V2 OHLCV criterion-evaluator harness is the FIRST research-branch arc post-Phase-13-FULLY-CLOSED. Sub-bundle decomposition recommendation (RECOMMEND; binding for writing-plans phase):

| Sub-bundle | Task | Deliverable | Estimated commits |
|------------|------|-------------|-------------------|
| **T-V2.1** | `context_builder.py` + `cfg_substitution.py` + tests | OHLCV slicing + BatchContext reconstruction + cfg substitution helpers | ~8-12 commits |
| **T-V2.2** | `sweep.py` + tests | Per-(variable, sweep_point) orchestrator + baseline parity + failure isolation | ~12-18 commits (largest sub-bundle) |
| **T-V2.3** | `output.py` + tests | CSV + markdown sensitivity matrix + headline + per-variable drill-down + V1↔V2 parity section | ~8-12 commits |
| **T-V2.4** | `run.py` + CLI subcommand registration in `swing/cli.py` + tests | CLI entry + argparse + ClickException wrapping + smoke E2E | ~6-10 commits |
| **T-V2.5** | Method-record extension + first study writeup + operator smoke run + closer | Extend `aplus-criteria-calibration.md` per §K; first study writeup at `research/studies/<date>-v2-ohlcv-criterion-evaluator.md`; operator runs V2 against operator DB + captures output; closer commit | ~6-10 commits |

**Total estimated commits**: ~40-62 across executing-plans phase. Comparable to T4.SB executing-plans scope (28+ commits per T4.SB.6 closer ship).

### §M.2 Concurrent dispatch potential

Sub-bundles T-V2.1, T-V2.2, T-V2.3 have sequential dependencies (T-V2.2 depends on T-V2.1; T-V2.3 depends on T-V2.2). Sub-bundle T-V2.4 partially depends on T-V2.3 (CLI emit paths). T-V2.5 depends on all prior + operator gate.

**RECOMMEND**: Sequential single-implementer dispatch for executing-plans phase. NO concurrent dispatch (single-implementer-driven via `copowers:subagent-driven-development` per project workflow precedent). Cross-implementer state isolation NOT a feature this arc needs.

### §M.3 Open questions deferred to writing-plans phase

- Actual function signatures + class shapes (proposed in §C.1 + §D.3 but not BINDING; writing-plans refines)
- Exact OQ-9 runtime cap default (`--max-runtime-seconds N=?`); writing-plans evaluates against operator's hardware baseline
- Per-task test-budget refinement (writing-plans decomposes the §H.1 ~46-test estimate into per-task budgets)
- Exact OQ-13 OhlcvCoverageError typed exception name + module location
- Per-sub-bundle Codex MCP round-budget expectation (informed by complexity per sub-bundle; writing-plans estimates)

### §M.4 Post executing-plans handback

V2 OHLCV harness shipping completes the FIRST applied-research arc under `aplus-criteria-calibration` lineage. Forward-binding for the NEXT applied-research arc:

- IF V2 output identifies binding threshold variables: NEXT arc drafts cfg-policy method-record + threshold-loosening evaluation against retained validation universes.
- IF V2 output declares all 15 non-binding: NEXT arc pivots to investigate market-conditions (cause 2 per §B.3) OR other-gates-not-enumerated (cause 3 per §B.3).
- THEN: Phase 14 commissioning per OQ-CL.2 disposition revisit.

---

## §N Self-review (BINDING per superpowers:brainstorming spec self-review gate)

### §N.1 Placeholder scan

- ZERO `TBD` placeholders. (Verified via grep at spec-write time; ALL `<date>` placeholders are intentional for downstream writing-plans phase + V2 ship date stamping.)
- ZERO `TODO` markers.
- ZERO incomplete sections.
- ZERO vague requirements.

### §N.2 Internal consistency

Checked sections for contradiction:
- §A.1 + §C.1: NEW module `research/harness/aplus_v2_ohlcv_evaluator/` referenced consistently.
- §A.4 + §C.2: V1 CLI `swing diagnose aplus-sensitivity` stays + V2 CLI `swing diagnose aplus-sensitivity-v2` is NEW. Consistent.
- §D.1 + §E.1 + §E.3: cfg-substitution + production `evaluate_one` invocation for 16 of 17 variables; `vcp.watch_max_fails` special-case for the 1 hardcoded variable. Consistent.
- §H.1 test count (~46) matches §H.3 baseline-bump projection (+46). Consistent.
- §I OQs (8 + 5 NEW = 13) match dispatch brief §1.1 (8 brief + 5+ new) bound. Consistent.
- §K version bump (0.1.0 → 0.2.0) matches §K.1 + V2 ship status `research`. Consistent.

### §N.3 Scope check

V2 OHLCV criterion-evaluator harness is the FIRST applied-research arc — appropriately scoped for ONE writing-plans → executing-plans cycle. Sub-bundle decomposition at §M.1 (5 sub-bundles; ~40-62 commits) is comparable to T4.SB executing-plans precedent. No over-scoping.

### §N.4 Ambiguity check

Per requirement-ambiguity check, all interpretation-ambiguous statements made explicit:

- "binding at the watch→A+ promotion boundary" (per §B.1) defined operationally as `max(|delta_aplus|) > 0` per OQ-8 disposition + per-variable hypothesis ranking at §B.4.
- "material A+ delta" (per OQ-8 + §B.5 null hypothesis) defined as ≥5 A+ delta on a 5681-candidate universe (configurable per operator-paired evidence summary).
- "VCP-fails (`na` counts as fail)" semantic preserved verbatim per cumulative V1 LOCK at `swing/evaluation/scoring.py:34`.
- "OHLCV coverage failure" defined at §E.5 as `<200 bars at candidate's data_asof_date`.

ZERO interpretation-ambiguous requirements remaining.

---

*End of V2 OHLCV criterion-evaluator harness brainstorming design spec. First Applied Research arc post-Phase-13-FULLY-CLOSED. Path B LOCKED 2026-05-23 PM. Banked V2 dependency #1 from existing `aplus-criteria-calibration` method-record is this deliverable's lifted target.*
