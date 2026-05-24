# Pattern Cohort Detector Evaluator Research Harness -- Brainstorming Design Spec

**Status:** brainstorming spec (pre-writing-plans). SECOND Applied Research arc post-Phase-13-FULLY-CLOSED, following the V2 OHLCV criterion-evaluator arc precedent (3-phase brainstorming -> writing-plans -> executing-plans). Option D LOCKED per operator decision 2026-05-24 PM at [`docs/applied-research-pattern-cohort-detector-evaluator-dispatch-brief.md`](../../applied-research-pattern-cohort-detector-evaluator-dispatch-brief.md) commit `8ba87cd`.

**Branch:** `applied-research-pattern-cohort-detector-evaluator-brainstorm` (branched from main HEAD `8ba87cd`).

**Predecessor:** Phase 13 `_step_pattern_detect` silent no-op investigation at [`docs/phase13-pattern-detect-step-silent-noop-investigation-2026-05-24.md`](../../phase13-pattern-detect-step-silent-noop-investigation-2026-05-24.md) (merge `54bd9c6`) -- the architectural insight that motivates this harness: production `_step_pattern_detect` gates on `bucket == 'aplus'` by design (per `swing/pipeline/runner.py:1481-1483` + recon LOCK at runner.py:1407 docstring); cannot answer the loosened-cohort detector-confirmation research question via production pipeline. This harness is Option D from the investigation findings §5.4 (now LOCKED as the architectural answer per operator decision).

**Structural template:** V2 OHLCV criterion-evaluator harness at [`research/harness/aplus_v2_ohlcv_evaluator/`](../../../research/harness/aplus_v2_ohlcv_evaluator/) (7 modules). This spec adapts that structure to the chart-shape detector domain: `cohort_reader.py` replaces V2's `context_builder.py`; `detector_invoker.py` replaces V2's `cfg_substitution.py` + `sweep.py` orchestration; `ohlcv_reader.py` is reused verbatim in pattern (same L2 LOCK BINDING contract). Output emits per-(cohort_entry, detector) verdicts rather than per-(variable, sweep_point) buckets.

**Cumulative streaks preserved through this spec write:** ~516+ ZERO `Co-Authored-By` footer trailer; baseline ~5893 fast tests UNCHANGED (brainstorming docs-only); schema v21 UNCHANGED (harness does NOT touch schema per §A.2); ZERO new Schwab API calls (L2 LOCK preserved per §F.1 + §D.2 BINDING tests).

**Brief-framing accuracy verification** (per CLAUDE.md gotcha #27 sub-lesson BINDING): the dispatch brief §7 cites "+67 watch->aplus flips at vcp.tightness_range_factor=1.005" as the first-cohort target. Verified against the V2 OHLCV sensitivity backtest dispatch brief at `docs/v2-tightness-range-factor-backtest-dispatch-brief.md:60-62`: the sensitivity matrix `delta_aplus[sweep_point=1.005] = +75` (aplus_count 5 -> 80; net +75) and the drill-down section enumerates 67 `watch->aplus` flips (15 unique tickers); the discrepancy of 8 is noted in the backtest brief as candidate-explanation territory. This spec adopts the **67 flip-entries (15 unique tickers)** framing for the first-cohort target -- it is the operator-input-level number that maps directly to cohort entries.

---

## §A Status + scope

### §A.1 Research-branch positioning (V2.1 §V)

The pattern-cohort detector-evaluator harness lives under `research/` per V2.1 §V branch posture:

- **NEW module**: `research/harness/pattern_cohort_evaluator/` (7 files; see §B.1 module breakdown). NOT a fork of the production `_step_pattern_detect` at `swing/pipeline/runner.py:1396-2104`; the production step STAYS as the aplus-only canonical write path to `pattern_evaluations` table. Harness output emits to `exports/research/` only.
- **NEW study writeup**: `research/studies/<date>-pattern-cohort-detection.md` (companion to existing V2 OHLCV criterion-evaluator study). Follows the format precedent from `research/studies/2026-05-23-v2-ohlcv-criterion-evaluator.md`.
- **NEW method-record**: `research/method-records/pattern-cohort-detection.md` (NOT an extension of `aplus-criteria-calibration.md` -- a sibling method-record under V2.1 §X tranche progression). Follows V2.1 §IV.B minimum-viable-field-list shape per existing precedent at `aplus-criteria-calibration.md`. See §K for proposed content.
- **Tests** under `tests/research/test_pattern_cohort_evaluator_*.py` mirroring V2 OHLCV evaluator test layout at `tests/research/test_aplus_v2_ohlcv_*.py`. Test count budget per §H.
- **Production `swing/` code is READ-ONLY through this dispatch arc EXCEPT for ONE explicit minimal carve-out** (per OQ-13 RECOMMEND below): a CLI subcommand registration in `swing/cli.py` registers `swing diagnose pattern-cohort-detect` (or alternative name per OQ-10). Scope of the carve-out is described by SURFACE / RESPONSIBILITY rather than line count per the V2 OHLCV OQ-17 precedent: subcommand handler + `@diagnose.command` group attachment + Click options + ClickException wrapping + delegation. Realistic line count: 35-60 lines (per V2 OHLCV V1 precedent at `swing/cli.py` for V2 evaluator's diagnose-subcommand registration).

  Harness imports (READ-ONLY usage) from `swing.patterns.foundation.{generate_candidate_windows, CandidateWindow, current_stage}` + `swing.patterns.{vcp, flat_base, cup_with_handle, high_tight_flag, double_bottom_w}.detect_*` + `swing.patterns.composite.compute_composite_score` + `swing.patterns.template_matching.match_forward` + `swing.data.repos.pattern_exemplars.list_exemplars` (for template-match corpus parity with production) + `swing.config.Config`. NO imports of `swing.data.ohlcv_archive` (L2 LOCK preserved per V2 OHLCV precedent).

### §A.2 Schema discipline (LOCK)

Schema v21 is the LOCKED schema. Harness MUST NOT touch migrations.

The brainstorming spec EXPLICITLY does NOT propose any v22 delta. The harness output is research-branch CSV + markdown only; the production `pattern_evaluations` table is untouched.

Verified at brainstorming-phase pre-Codex Expansion #4 refinement (BINDING per cumulative gotcha #18 -- "every SQL skeleton's columns verified against actual migration files"): the harness's SQL skeletons (§C.3) read ONLY existing columns:

- `evaluation_runs.id` + `evaluation_runs.data_asof_date` per `swing/data/migrations/0001_phase1_initial.sql:9-12` (used only for the optional Mode-(c) SQL-cohort input per OQ-2).
- `candidates.id` + `candidates.evaluation_run_id` + `candidates.ticker` + `candidates.bucket` + `candidates.pivot` + `candidates.initial_stop` per `swing/data/migrations/0001_phase1_initial.sql:24-42` (used only for the optional Mode-(c) SQL-cohort input).
- `candidate_criteria.candidate_id` + `candidate_criteria.layer` + `candidate_criteria.criterion_name` + `candidate_criteria.result` per `swing/data/migrations/0001_phase1_initial.sql:48-56` (used only for the optional Mode-(c) SQL-cohort input; e.g., "all candidates where vcp_tightness criterion failed at margin within X").
- `pattern_exemplars.id` + `pattern_exemplars.ticker` + `pattern_exemplars.start_date` + `pattern_exemplars.end_date` + `pattern_exemplars.proposed_pattern_class` + `pattern_exemplars.final_decision` (per migration `0020_phase13_charts_patterns_autofill_usability.sql` -- the canonical exemplar corpus; identical SELECT as production `_step_pattern_detect` Pass 2 at runner.py:1848).

ZERO new columns referenced. ZERO new table references. ZERO CHECK enum widenings. Verified via `grep -n` against `swing/data/migrations/*.sql` at spec-write time.

### §A.3 V2.1 §IV.D + §VII.C lifecycle posture

The pattern-cohort-detection method-record is NEW. It ships at `status='research'` (no `shadow` claim at landing).

Promotion criteria proposed at §K.3 (BINDING for downstream Applied Research arcs that consume the harness output; NOT triggered by harness ship itself):

- **research -> shadow**: harness ships + baseline parity invariant green per §E + at least one cohort study writeup published + at least one operator-paired ratification of an actionable finding (e.g., "detector-pass cohort has differentiated breakout-trigger rate" OR "detector-pass and detector-fail cohorts are indistinguishable so chart-shape detection adds no orthogonal signal at the loosened threshold").
- **shadow -> production**: at least one cfg-policy proposal OR pool-predicate-widening proposal evaluated against at least 2 disjoint validation universes + statistically distinguishable expectancy delta + operator-paired ratification.

### §A.4 Production `_step_pattern_detect` retention (no replacement)

Production `_step_pattern_detect` at `swing/pipeline/runner.py:1396-2104` STAYS as the aplus-only canonical write path to `pattern_evaluations`. The harness is a PARALLEL research-branch read-only invocation surface; it does NOT modify production semantics.

The harness invocation NEVER writes to `pattern_evaluations`. The harness output lives ONLY in `exports/research/pattern-cohort-detection-<ISO>/` per §A.5 + §I.2.

V2.G operator-paired follow-up candidate (banked separately; NOT this dispatch): production `_step_pattern_detect` pool-predicate widening from `bucket == 'aplus'` to `bucket IN ('aplus', 'watch')` -- the architectural alternative to this research harness. Per the predecessor investigation §5.3 Option C, this is "non-trivial; separate dispatch" and operator decision 2026-05-24 PM LOCKED Option D (this harness) instead, with Option C banked.

### §A.5 Non-scope (V2.5 / V3+ / future arc; explicitly out of this dispatch)

- **Schema changes** -- production `pattern_evaluations` is untouched; no migrations.
- **Production `_step_pattern_detect` modifications** -- the pool-predicate widening (Option C from the predecessor investigation) is V2.G candidate; not this dispatch.
- **Stage 3 AI second-opinion eval** -- gated on harness producing data + backtest producing winners (per operator's earlier methodology proposal). Banked per dispatch brief §1.6.
- **Production-pipeline backfill via this harness** -- separate operational dispatch; out of research-branch scope.
- **Bootstrap / Monte Carlo statistical confidence intervals** -- banked per dispatch brief §1.6.
- **Cohort-stratified analysis** (sector / market-cap / regime decomposition) -- V2.5 candidate per dispatch brief §1.6.
- **SQL-cohort input mode** (Mode (c) per §C.2) -- V2.5+ candidate per dispatch brief §1.2. V1 ships Mode (a) inline + Mode (b) CSV; Mode (c) gated on operator validation that the first two modes adequately cover the analytical workflow.
- **Multi-anchor-mode invocation** -- production uses `zigzag_pivot` only; harness mirrors. Multi-mode (zigzag_pivot + ma_crossover + high_low_breakout per `generate_candidate_windows` enum) is V2.5+ candidate per OQ-4.
- **Schwab API calls** -- harness reads OHLCV via the V2 OHLCV evaluator's existing `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py` (preserves L2 LOCK; no new Schwab API calls; no fetch path; no archive mutation). Per OQ-3 RECOMMEND.
- **Pattern-evaluations table writes** -- harness output is research CSV + markdown only.
- **Phase 14 commissioning** -- deferred per operator decision; harness is research-branch infrastructure.

---

## §B File map (module breakdown)

### §B.1 NEW research module layout

```
research/harness/pattern_cohort_evaluator/
    __init__.py
    exceptions.py             # PatternCohortEvaluatorError + sub-classes
    cohort_reader.py          # Read operator-specified cohort (CSV or inline tuple list)
    ohlcv_reader.py           # Per OQ-3 RECOMMEND: thin re-export of V2 OHLCV evaluator's reader
                              # OR a new minimal reader matching its L2 LOCK contract
    detector_invoker.py       # Wrap swing/patterns/* detectors with cohort-iteration shell
    output.py                 # Emit results CSV + markdown summary
    run.py                    # CLI entry point + orchestration
```

7 files total per dispatch brief §1.1 enumeration.

**Dependency surface verification per Expansion #10 sub-discipline (a) architecture-location audit** (BINDING per cumulative gotcha #14):

| Module | Dependencies | Justification |
|--------|--------------|---------------|
| `exceptions.py` | stdlib only | Typed exception class hierarchy; mirrors V2 OHLCV `exceptions.py` pattern verbatim. |
| `cohort_reader.py` | `pathlib.Path`, `csv`, `dataclasses`, NO yfinance / schwabdev / swing imports | Pure-Python cohort row parser. Validates required fields (ticker + asof_date); optional fields (candidate_id + eval_run_id + bucket + pivot + initial_stop + pattern_class) per §C.1. ASCII-only + cp1252-safe per cumulative gotcha. |
| `ohlcv_reader.py` (per OQ-3 RECOMMEND) | `research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader` -- re-export `read_yfinance_shape_a` + `read_yfinance_shape_a_sliced` + `BothExistDiagnostic` | Re-export the V2 OHLCV evaluator's reader verbatim. Preserves L2 LOCK identically (NEVER opens `{ticker}.schwab_api.parquet`; NO fetch). Discriminating tests asserted independently per §F. ALTERNATIVE per OQ-3 (b): build a new minimal reader if dependency from one research module on another is undesirable. RECOMMEND (a) re-export to avoid drift between two read-only-Shape-A readers. |
| `detector_invoker.py` | `swing.patterns.foundation.{generate_candidate_windows, CandidateWindow, current_stage}`, `swing.patterns.{vcp, flat_base, cup_with_handle, high_tight_flag, double_bottom_w}.detect_*` + `DETECTOR_VERSION`, `swing.patterns.composite.compute_composite_score`, `swing.patterns.template_matching.match_forward`, `swing.data.repos.pattern_exemplars.list_exemplars`, `swing.config.Config`, `sqlite3.Connection` (READ-ONLY for `current_stage` + exemplar corpus + optional Mode-(c) cohort SQL), `pandas`, `numpy`. | Per-(cohort_entry, detector) orchestration. Builds the CandidateWindow per the cohort entry's asof_date; invokes all 5 detectors (or operator-filtered subset per OQ-5); optionally runs template-matching Pass 2 per OQ-6; composes per-entry verdict tuple. Per-entry try/except per cumulative T2.SB5 lesson. |
| `output.py` | `dataclasses`, `csv`, `pathlib.Path`, V2 result dataclasses from `detector_invoker.py` | Pure I/O formatter. ASCII-only (Windows cp1252 safety per cumulative gotcha). Emits per-(cohort_entry, pattern_class) row CSV + markdown summary with headline + per-pattern-class detector-pass / detector-fail counts + per-entry drill-down. |
| `run.py` | `argparse`, `sqlite3`, all harness modules + `swing.config.Config.from_defaults` | CLI entry. Click delegation from `swing diagnose pattern-cohort-detect` (registered in `swing/cli.py` per OQ-13 carve-out). DB opened via URI `mode=ro` per V2 OHLCV precedent + defense-in-depth at `research/harness/aplus_v2_ohlcv_evaluator/run.py:93-95`. |

Expansion #10 sub-discipline (c) cache-key shape + renderer-kwargs uniformity LOCK: harness produces NO `chart_renders` rows. N/A.

Expansion #10 sub-discipline (d) SQL LIKE wildcard-escape: harness Mode-(c) SQL (V2.5+) may produce LIKE patterns; V1 dispatch declines Mode (c) so N/A this dispatch. Banked for V2.5+ writing-plans phase.

Expansion #10 sub-discipline (e) orphan-label preservation: cohort entries that fail OHLCV coverage / current_stage lookup / detector invocation are explicitly handled per §C.4 + §D.4 per-failure-mode skip counts (no silent drop; surfaced in per-cohort-entry drill-down).

### §B.2 Repository cross-references

- Dispatch brief: [`docs/applied-research-pattern-cohort-detector-evaluator-dispatch-brief.md`](../../applied-research-pattern-cohort-detector-evaluator-dispatch-brief.md)
- Predecessor investigation: [`docs/phase13-pattern-detect-step-silent-noop-investigation-2026-05-24.md`](../../phase13-pattern-detect-step-silent-noop-investigation-2026-05-24.md)
- V2 OHLCV evaluator (STRUCTURAL TEMPLATE): [`research/harness/aplus_v2_ohlcv_evaluator/`](../../../research/harness/aplus_v2_ohlcv_evaluator/) (7 modules)
- V2 OHLCV evaluator brainstorming spec (STRUCTURAL TEMPLATE for spec authoring): [`docs/superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md`](2026-05-23-v2-ohlcv-criterion-evaluator-design.md)
- V2 OHLCV evaluator brainstorming return report (STRUCTURAL TEMPLATE for return report): [`docs/v2-ohlcv-criterion-evaluator-brainstorm-return-report.md`](../../v2-ohlcv-criterion-evaluator-brainstorm-return-report.md)
- V2 OHLCV criterion-evaluator method-record (PRECEDENT for method-record shape): [`research/method-records/aplus-criteria-calibration.md`](../../../research/method-records/aplus-criteria-calibration.md) (v0.3.0; SHADOW)
- V2 OHLCV evaluator study writeup (PRECEDENT for study writeup): [`research/studies/2026-05-23-v2-ohlcv-criterion-evaluator.md`](../../../research/studies/2026-05-23-v2-ohlcv-criterion-evaluator.md)
- V2 tightness backtest dispatch brief (FIRST-COHORT substrate): [`docs/v2-tightness-range-factor-backtest-dispatch-brief.md`](../../v2-tightness-range-factor-backtest-dispatch-brief.md) §1 (+67 watch->aplus flips at vcp.tightness_range_factor=1.005; 15 unique tickers)
- V2 tightness backtest findings (NEGATIVE-cfg-policy substrate for context): [`docs/v2-tightness-range-factor-backtest-findings-2026-05-24.md`](../../v2-tightness-range-factor-backtest-findings-2026-05-24.md) (17 patterns / 5 triggered / 0 closed / -0.18R mean unrealized; NEGATIVE verdict)
- Production detector registry + invocation: [`swing/pipeline/runner.py:1280-1303`](../../../swing/pipeline/runner.py) (`_pattern_detect_registry`) + [`swing/pipeline/runner.py:1396-2104`](../../../swing/pipeline/runner.py) (`_step_pattern_detect`)
- Phase 13 detector modules: [`swing/patterns/`](../../../swing/patterns/) (vcp.py + flat_base.py + cup_with_handle.py + high_tight_flag.py + double_bottom_w.py + foundation.py + composite.py + template_matching.py)
- Phase 13 design spec (criterion + composite formulae LOCK source): `docs/superpowers/specs/<phase13-spec-path>` per orchestrator-context (cross-ref skipped for brevity; recon docs at `docs/phase13-*.md`)
- Production `pattern_evaluations` schema: [`swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql:230-254`](../../../swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql)

---

## §C Architecture

### §C.1 Cohort entry shape (operator-input contract)

A cohort entry is a tuple `(ticker, asof_date, [optional metadata])`. Minimum required fields:

- `ticker: str` -- canonical uppercase symbol per V2 OHLCV reader's normalization (e.g., `"DK"`, `"RLMD"`).
- `asof_date: date` -- ISO YYYY-MM-DD; backward-looking boundary (the session that just closed at evaluation time). Inclusive `<=` per cumulative gotcha "Session-anchor inequality discipline depends on anchor directionality (backward-looking vs forward-looking)".

Optional metadata fields (operator may supply; harness surfaces in output for back-link / cross-tabulation):

- `candidate_id: int | None` -- the production `candidates.id` row this cohort entry derives from (V1 sensitivity matrix drill-down provides this).
- `eval_run_id: int | None` -- the production `evaluation_runs.id` this cohort entry derives from.
- `bucket: str | None` -- the persisted bucket per V1 (`'aplus'` | `'watch'` | `'skip'` | `'error'` | `'excluded'`); useful for partitioning the cohort by V1 verdict.
- `pivot: float | None` -- the persisted pivot price per V1 (`candidates.pivot`); useful for backtest joinability.
- `initial_stop: float | None` -- the persisted initial stop per V1 (`candidates.initial_stop`); useful for backtest joinability.
- `pattern_class_filter: str | None` -- if set, the harness invokes ONLY this detector for this entry (e.g., `"vcp"` for a VCP-only cohort). If unset, all 5 detectors are invoked. See OQ-5.
- `cohort_label: str | None` -- operator-supplied free-form tag (e.g., `"tightness_1.005_flip"`); surfaced in output for multi-cohort aggregation.

The cohort_reader normalizes all input shapes to a frozen `CohortEntry` dataclass per §C.2 + §C.3.

### §C.2 Cohort input modes

Per dispatch brief §1.2, three modes are proposed:

#### Mode (a) -- inline tuple list (small cohorts; smoke / debugging)

Operator passes a comma-separated list of `(ticker:asof_date)` pairs on the CLI:

```
swing diagnose pattern-cohort-detect \
    --cohort-inline "RLMD:2026-04-15,DNTH:2026-04-15,RNG:2026-04-15" \
    --output-dir exports/research/
```

Each pair must be parseable as `ticker:asof_date_iso`; optional metadata via Mode (a) is NOT supported (use Mode (b) for full-shape cohorts).

#### Mode (b) -- CSV input (RECOMMEND for first-cohort target; analytical workflow)

Operator passes a CSV path:

```
swing diagnose pattern-cohort-detect \
    --cohort-csv exports/research/cohorts/tightness_1.005_flips_67.csv \
    --output-dir exports/research/
```

Required CSV columns: `ticker`, `asof_date`. Optional CSV columns (per §C.1): `candidate_id`, `eval_run_id`, `bucket`, `pivot`, `initial_stop`, `pattern_class_filter`, `cohort_label`.

CSV header validation per cumulative gotcha "Synthetic-fixture-vs-production-emitter shape drift" (T-A.1.5b + T-A.1.8 pattern): missing required columns -> typed `CohortInputSchemaError` with the missing column names enumerated in the message.

#### Mode (c) -- SQL query against operator DB (V2.5+ candidate; OUT OF SCOPE V1)

Per dispatch brief §1.6 V2.5+ banked. Out of scope for V1 ship. Gated on operator validation that Mode (a) + (b) adequately cover the analytical workflow.

### §C.3 First-cohort target (operator-paired in OQ-12 RECOMMEND)

The first-cohort target for the V1 smoke run is the **67 watch->aplus flip entries at vcp.tightness_range_factor=1.005** documented in the V2 OHLCV sensitivity backtest dispatch brief §1 (`docs/v2-tightness-range-factor-backtest-dispatch-brief.md:60-62`).

Source: drill-down section `### vcp.tightness_range_factor` (lines 9725-10866) of the full-reproduction smoke artifact at `exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md`. Filter to rows with `sweep_point=1.005` AND `to_bucket=aplus`.

- 67 entries total
- 15 unique tickers (RLMD 12 / DNTH 10 / RNG 9 / KOD 8 / YOU 7 / FRO 6 / TROX 4 / PTEN 2 / OII 2 / DK 2 / WULF 1 / UCTT 1 / TSHA 1 / SSRM 1 / NAT 1)
- All entries carry persisted `candidate_id` + `eval_run_id` + `bucket=watch` + `pivot` + `initial_stop`

Cohort CSV generation discipline: the operator-side cohort-CSV generator MUST be a reproducible script (likely added as a one-off `tmp/` artifact during executing-plans phase; NOT shipped to `swing/` or `research/`). The CSV itself is committed to `exports/research/cohorts/` (or operator-equivalent path) as the canonical first-cohort substrate.

### §C.4 Harness data flow

For each cohort entry `(ticker, asof_date, [metadata])`:

1. **Read OHLCV bars** via `ohlcv_reader.read_yfinance_shape_a(ticker, cache_dir)` per OQ-3 RECOMMEND (re-export of V2 OHLCV evaluator's L2-LOCK-preserving reader). Slice to bars `<= asof_date` (inclusive; backward-looking per cumulative gotcha).
2. **Coverage gate**: verify `len(sliced_bars) >= 200` (minimum for any detector's MA200 + 200-bar context). If insufficient, raise `OhlcvCoverageError` -> per-entry skip with `coverage_skip` reason.
3. **Generate candidate windows** via `swing.patterns.foundation.generate_candidate_windows(bars, "zigzag_pivot", ticker=ticker, timeframe="daily")` per OQ-4 RECOMMEND (mirror production anchor mode). If no windows generated, per-entry skip with `no_windows` reason.
4. **Per-entry detector invocation** -- two sub-modes per OQ-7:
   - **Mode (i) `last-window-only`** (mirrors production `_step_pattern_detect`): use `windows[-1]` (most-recent-anchor); invoke each of 5 detectors (or operator-filtered subset per `pattern_class_filter`) against the single window. Emits ONE row per (cohort_entry, pattern_class).
   - **Mode (ii) `per-window-emit`** (RECOMMEND for first cohort): iterate ALL windows; invoke detectors against each. Emits N rows per (cohort_entry, pattern_class, window_index). Surfaces multi-anchor verdicts the operator may need for older-anchor base recognition.
5. **Detector invocation** per `(cohort_entry, pattern_class, window)`:
   - Build typed call signature per detector: `detect_<pattern_class>(bars, window, conn=detector_read_conn, ticker=ticker, asof_date=asof_date)` -- mirrors production at `swing/pipeline/runner.py:1668-1675`.
   - `conn` is a READ-ONLY connection to the operator DB; required because `current_stage(conn, ticker, asof_date)` consumes it for the Stage-2-gate criterion (#1 in VCP, flat_base, cup_with_handle, high_tight_flag, double_bottom_w per `swing/patterns/foundation.py:745-790` + each detector module's criterion #1 LOCK).
   - `asof_date` is the cohort entry's `asof_date` (NOT wall-clock now() per cumulative gotcha "Session-anchor read/write mismatch" + per Codex R1 Major #2 LOCK at production runner.py:1499 -- detectors require a canonical run-anchored asof_date; wall-clock leaks future evaluation_runs into `current_stage` lookups).
   - Per-detector failure isolation per cumulative T2.SB5 gotcha "Bad-exemplar isolation in retrieval functions": catch ALL exceptions; log WARNING; increment `detector_error_count` per (cohort_entry, pattern_class); continue with next detector.
6. **Compose verdict** per (cohort_entry, pattern_class, window):
   - `geometric_score: float` (from detector evidence)
   - `template_match_score: float | None` (per OQ-6 RECOMMEND: harness MIRRORS production Pass 2 template matching against the persisted `pattern_exemplars` corpus; same gate at `geometric_score >= GEOMETRIC_SCORE_PREGATE_THRESHOLD` (0.4) per `swing/patterns/template_matching.py:52`)
   - `composite_score: float` (via `compute_composite_score(geometric=geom, template_match=tm)` per `swing/patterns/composite.py:40`; clamped at 1.0 per L5 LOCK)
   - `criteria_pass_json: str` (per-criterion pass flags from evidence)
   - `structural_evidence_json: str` (full evidence dataclass via `dataclasses.asdict`)
   - `window_start_date / window_end_date: ISO`
   - `detector_version: str` (from `DETECTOR_VERSION` constant per detector module)
   - `stage_observed: str` (the `current_stage` lookup result per cohort entry; surfaces Stage-2-gate outcome for operator visibility)
7. **Emit row** to results CSV + accumulate row in markdown summary tallies.

### §C.5 CLI surface registration

NEW CLI subcommand registered in `swing/cli.py` per OQ-13 RECOMMEND (the SOLE production-`swing/` file modified). Delegates to `research.harness.pattern_cohort_evaluator.run.run_harness`.

Per-flag contract (proposed; subject to writing-plans refinement):

```
swing diagnose pattern-cohort-detect [--cohort-csv PATH | --cohort-inline TICKER:DATE[,TICKER:DATE...]] --db PATH [--output-dir DIR] [--pattern-class-filter NAME[,NAME...]] [--window-mode {last-only,per-window}] [--max-runtime-seconds N] [--template-match {on,off}]
```

- `--cohort-csv PATH` -- Mode (b) CSV path.
- `--cohort-inline LIST` -- Mode (a) comma-separated `ticker:asof_date` pairs.
- Exactly ONE of `--cohort-csv` / `--cohort-inline` MUST be supplied; both supplied OR neither supplied -> CLI ValueError + ClickException per cumulative T-A.1.5b lesson.
- `--db PATH` -- operator's `swing-data/swing.db`. REQUIRED (for `current_stage` reads + `pattern_exemplars` corpus reads per §C.4 step 5 + step 6).
- `--output-dir DIR` -- default `exports/research/`.
- `--pattern-class-filter NAME[,NAME...]` -- optional global override of per-entry `pattern_class_filter`. Default: ALL 5 detectors. Per-entry override (CSV column) takes precedence if supplied. See OQ-5.
- `--window-mode {last-only,per-window}` -- default `per-window` per OQ-7 RECOMMEND. `last-only` mirrors production `_step_pattern_detect` semantics.
- `--max-runtime-seconds N` -- optional runtime cap; default UNSET. Mirrors V2 OHLCV evaluator's runtime cap per OQ-9 V2 OHLCV precedent.
- `--template-match {on,off}` -- default `on` per OQ-6 RECOMMEND. `off` skips Pass 2 template matching (geometric_score-only output; faster for cohorts where template-match parity with production is not needed).

Per cumulative Phase 13 T-A.1.5b lesson "Service-layer ValueErrors must be wrapped at CLI boundary", the CLI subcommand wraps ALL service-layer dispatches in `try: ... except ValueError as exc: raise click.ClickException(str(exc))`.

### §C.6 Output paths

- CSV: `exports/research/pattern-cohort-detection-<ISO>/results.csv`
- Markdown: `exports/research/pattern-cohort-detection-<ISO>/summary.md`
- Manifest: `exports/research/pattern-cohort-detection-<ISO>/manifest.json` (cohort-input metadata + runtime + harness version + L2 LOCK + counter summary)

`<ISO>` is UTC `%Y%m%dT%H%M%SZ` mirroring V2 OHLCV evaluator at `research/harness/aplus_v2_ohlcv_evaluator/run.py:117`.

Each harness invocation creates a fresh timestamped subdirectory. No overwrites. No append semantics.

---

## §D Detector-invocation shell (replaces V2 OHLCV's §D cfg-substitution)

### §D.1 Interface decision: direct production-detector invocation (OQ-1 RECOMMEND)

The harness invokes the PRODUCTION detector functions (`detect_vcp`, `detect_flat_base`, `detect_cup_with_handle`, `detect_high_tight_flag`, `detect_double_bottom_w`) end-to-end. NO V2-side mirror; NO cfg substitution.

This is structurally simpler than the V2 OHLCV evaluator's `cfg_substitution.py` + `sweep.py` per-(variable, sweep_point) orchestration because the chart-shape detector domain does NOT have per-detector cfg knobs in the same way criterion thresholds do. Detector behavior is governed by hardcoded LOCKs in `swing/patterns/*.py` (criterion-pass thresholds + composite formula + template-match Sakoe-Chiba band ratio per `swing/patterns/template_matching.py:46-61` LOCKs).

If a future arc surfaces a detector threshold V2.5 candidate (e.g., "loosen high_tight_flag pole_pct threshold from 100% to 80%"), THAT cycle would extend this harness with a cfg-substitution layer mirroring V2 OHLCV evaluator's pattern. NOT this dispatch.

### §D.2 Detector registry adoption

The harness inherits the detector registry from production at `swing/pipeline/runner.py:1280-1303` (`_pattern_detect_registry`). Rather than re-import (cross-bundle pin risk), the harness MAY:

- **(a) Re-import** `_pattern_detect_registry()` from `swing.pipeline.runner` (the function is module-level + side-effect-free; safe to import). RECOMMEND for V1 ship: zero drift risk vs production.
- **(b) Re-derive** the 5-tuple registry from individual detector module imports (mirror the production function body verbatim in `detector_invoker.py`). REJECT: drift risk if production adds a 6th detector OR removes one.

V1 ship target = (a). Discriminating test: `test_harness_detector_registry_matches_production` asserts `harness_registry == swing.pipeline.runner._pattern_detect_registry()` (tuple equality).

### §D.3 Per-entry try/except discipline

Per cumulative T2.SB5 gotcha + production `_step_pattern_detect` at runner.py:1601-1685 per-ticker + per-detector try/except, the harness MUST isolate per-(cohort_entry, pattern_class, window) failures:

```python
# pseudo-code; actual signature TBD in writing-plans
for entry in cohort_entries:
    try:
        bars = ohlcv_reader.read_yfinance_shape_a(entry.ticker, cache_dir)
        sliced = bars.loc[bars.index.date <= entry.asof_date]
        if len(sliced) < 200:
            raise OhlcvCoverageError(...)
    except OhlcvCoverageError:
        skip_counts["coverage_skip"] += 1
        record_skipped_entry(entry, reason="coverage_skip")
        continue
    except (FileNotFoundError, OSError) as exc:
        skip_counts["archive_missing_skip"] += 1
        record_skipped_entry(entry, reason="archive_missing_skip")
        continue

    try:
        windows = generate_candidate_windows(sliced, "zigzag_pivot", ticker=entry.ticker, timeframe="daily")
    except Exception as exc:
        skip_counts["window_generation_error"] += 1
        record_skipped_entry(entry, reason="window_generation_error", error=str(exc)[:200])
        continue

    if not windows:
        skip_counts["no_windows"] += 1
        record_skipped_entry(entry, reason="no_windows")
        continue

    for window in (windows[-1:] if window_mode == "last-only" else windows):
        for detector_fn, pattern_class, version in detector_registry:
            if entry.pattern_class_filter and entry.pattern_class_filter != pattern_class:
                continue
            try:
                evidence = detector_fn(sliced, window, conn=read_conn, ticker=entry.ticker, asof_date=entry.asof_date)
            except Exception as exc:
                detector_error_counts[(entry, pattern_class)] += 1
                log.warning("detector %s failed for %s: %s", pattern_class, entry.ticker, str(exc)[:200])
                continue
            # ... compose verdict + template match (per §C.4 step 6) ...
            emit_row(entry, pattern_class, window, evidence, ...)
```

Discriminating test plants 3 cohort entries: 1 good + 1 with archive missing + 1 with all detectors raising synthetic exceptions -> asserts only failure-mode entries skip + good entry's detector verdicts are tallied.

### §D.4 Template-matching Pass 2 (per OQ-6 RECOMMEND)

For parity with production `_step_pattern_detect` composite_score derivation, the harness MIRRORS Pass 2 template matching:

1. After Pass 1 collects per-(cohort_entry, pattern_class, window) detector evidence + geometric_score, the harness:
2. Loads the `pattern_exemplars` corpus via `swing.data.repos.pattern_exemplars.list_exemplars(conn)` (READ-ONLY) -- identical SELECT as production runner.py:1848.
3. Filters to `final_decision IN ('confirmed', 'watch')` per production at runner.py:1860.
4. For each (cohort_entry, pattern_class, window) emit with `geometric_score >= GEOMETRIC_SCORE_PREGATE_THRESHOLD` (0.4) AND non-empty exemplar bundle for the pattern_class:
   - Slice the candidate's close-price series from the window (mirrors production at runner.py:1707-1729).
   - Invoke `match_forward(candidate_close_prices=..., candidate_pattern_class=..., candidate_ticker=..., exemplar_corpus=..., top_k=3, geometric_score=...)` per production at runner.py:1928-1935.
   - `template_match_score = max(h.similarity_score for h in hits)` if hits else None.
5. `composite_score = compute_composite_score(geometric=geom, template_match=tm)` per production at runner.py:1953-1956.

If `--template-match=off` (per CLI), the harness skips Pass 2 entirely; `template_match_score = None`; `composite_score = compute_composite_score(geometric=geom, template_match=None) = min(1.0, geom)` per L5 LOCK fallback.

Per-(cohort_entry, pattern_class, window) failure isolation per cumulative T2.SB5 lesson: catch `match_forward` exceptions; log WARNING; continue with template_match_score=None.

**Pattern-exemplar corpus drift caveat**: the operator's `pattern_exemplars` corpus may have grown / shrunk between cohort-input-time and harness-invocation-time. The harness reads the CURRENT corpus at invocation; documented in study writeup `Limitations` section per cumulative gotcha #26 family (TEMPORAL mutation of canonical corpus surfaces). V2.5+ candidate: corpus-version pinning (analogous to OQ-14 historical universe snapshot from V2 OHLCV).

### §D.5 Stage-2 gate semantic (`current_stage` lookup)

The harness's per-detector invocation passes the cohort entry's `asof_date` to `current_stage(conn, ticker, asof_date)` per `swing/patterns/foundation.py:745-790`. The lookup queries `candidates` JOIN `evaluation_runs` for the most-recent candidate row at the ticker with `er.action_session_date <= asof_date`, then checks the count of TT criteria that passed.

**Semantic consequence**: if the cohort entry's ticker has no candidate row in the operator DB at the asof_date (e.g., the operator constructed a synthetic cohort from external data; or the eval_run was pruned), `current_stage` returns `'undefined'` -> detector criterion #1 (Stage-2-gate) fails -> detector emits zero-evidence verdict.

For the first-cohort target (67 watch->aplus flips), all 15 unique tickers HAVE candidate rows in the operator DB (sourced from the V2 OHLCV sensitivity drill-down). So `current_stage` will return real Stage-2 verdicts.

For future cohorts sourced from external data, OQ-8 RECOMMEND surfaces the per-entry `stage_override` field (V2.5+ candidate) that bypasses `current_stage` lookup and supplies a synthetic Stage-2 verdict; OUT OF SCOPE V1.

### §D.6 Idempotency

Re-running the harness against the SAME cohort + same OHLCV archive + same `pattern_exemplars` corpus MUST produce byte-identical results CSV (modulo the timestamped output subdirectory). This is the canonical reproducibility invariant for research-branch harnesses.

Per cumulative gotcha #26 (archive bar-content TEMPORAL mutation): if intervening pipeline runs mutate historical OHLCV bars between two harness invocations, results may drift. Documented in study writeup `Limitations` section; same family as V2 OHLCV evaluator's L6 limitation.

Discriminating test: `test_harness_idempotent_against_static_fixture` invokes the harness twice against the same fixture cohort + same fixture OHLCV archive; asserts CSV byte-equality.

---

## §E Baseline parity invariant

### §E.1 Production-parity invariant (RECOMMEND for V1 ship)

The harness's per-(cohort_entry, pattern_class, window) verdict MUST match production `_step_pattern_detect`'s persisted `pattern_evaluations` row for the SAME (ticker, asof_date) combo IF such a row exists for that pipeline_run.

**Scoping**: the parity claim applies ONLY when:

1. The cohort entry's `(ticker, asof_date)` has a corresponding `pattern_evaluations` row written by production (i.e., the ticker was in `bucket='aplus'` at the matching pipeline_run -- per the production pool predicate).
2. The harness invocation uses `--window-mode=last-only` (matches production's `windows[-1]` discipline at runner.py:1646).
3. The harness invocation uses `--template-match=on` (matches production's Pass 2 template matching).
4. The `pattern_exemplars` corpus is identical between production-write-time and harness-invocation-time (per §D.4 corpus drift caveat).
5. The OHLCV archive is bit-identical between production-write-time and harness-invocation-time (per cumulative gotcha #26).

Under these scopings, the harness's `geometric_score` + `composite_score` + `structural_evidence_json` MUST match the persisted row's columns exactly.

**Failure mode (anti-pattern)**: harness verdict diverges from production for a (ticker, asof_date) that satisfies the scoping invariant -> EITHER harness has a wiring defect (V2 evaluator parity bug; the analogous V2 OHLCV evaluator situation surfaced via R1.C1 + R1.C2 + R1.M1+M2+M3+M4+M5+M6+R2-R5 Codex chain) OR canonical drift between production + research detection paths.

Acceptance criteria:

- `test_harness_per_entry_verdict_matches_persisted_pattern_evaluations_when_aplus` (discriminating; blocking landing). Plants a cohort entry derived from a known persisted `pattern_evaluations` row + asserts byte-equality of `geometric_score` + `composite_score` + `structural_evidence_json`.
- `test_harness_per_entry_verdict_is_emitted_for_non_aplus_cohort_entry_without_failure` (discriminating; landing). Plants a cohort entry with `bucket='watch'` (NO persisted `pattern_evaluations` row); asserts harness emits a verdict row + does NOT raise + the verdict's geometric_score reflects the synthetic OHLCV fixture's pattern shape (NOT just zero-evidence from a missing Stage-2 gate).

### §E.2 Stage-2 gate parity (per OQ-8 + §D.5)

For cohort entries where the V1 sensitivity drill-down already verified Stage-2 status via `current_stage(conn, ticker, asof_date) == 'stage_2'`, the harness MUST observe the same stage. Discriminating test: plant a 15-ticker fixture (the first-cohort target) + invoke `current_stage` per entry + assert each ticker returns `'stage_2'` (anti-pattern: 0/15 returning stage_2 indicates the test fixture's eval_run / candidate snapshot does not match the operator's actual DB state).

### §E.3 L2 LOCK preservation invariant (BINDING per dispatch brief §1.4)

The harness MUST NOT import yfinance / schwabdev / swing.integrations.schwab / swing.data.ohlcv_archive at runtime AND MUST NOT open `{ticker}.schwab_api.parquet` under any code path.

5 BINDING discriminating tests at `tests/research/test_pattern_cohort_evaluator_reader.py` per dispatch brief §1.4 + V2 OHLCV precedent at `tests/research/test_aplus_v2_ohlcv_reader.py`:

1. **File-open boundary check (4 file-open call surfaces)**: monkeypatch `pd.read_parquet` + `pathlib.Path.open` + `builtins.open` + `pyarrow.parquet.read_table` to spy on every call; invoke harness against a synthetic cohort; assert NO call opens `{ticker}.schwab_api.parquet`.
2. **Module import sentinel graph**: invoke the harness in a subprocess; assert `yfinance`, `schwabdev`, `swing.integrations.schwab`, and `swing.data.ohlcv_archive` are absent from `sys.modules` post-invocation.
3. **Byte-checksum compare**: plant a synthetic ticker with BOTH `{T}.schwab_api.parquet` AND `{T}.yfinance.parquet` (different byte contents); invoke harness; assert harness's bar values byte-match the yfinance shape A (NOT schwab).
4. **Signature lock**: `inspect.signature(ohlcv_reader.read_yfinance_shape_a)` asserts no `source` / `prefer_source` / `fetch` kwargs (defense-in-depth against future-version drift).
5. **Source-grep test**: `grep -rE 'yfinance|schwabdev|swing\.integrations\.schwab|swing\.data\.ohlcv_archive' research/harness/pattern_cohort_evaluator/` returns 0 matches OR returns only the re-export line per OQ-3 (a) which itself MUST NOT trigger any of the above 4 tests when invoked.

These 5 tests are BINDING -- failure to land any of them blocks executing-plans merge per the operator-witnessed gate (per V2 OHLCV evaluator L2 LOCK precedent).

### §E.4 Empty-cohort + empty-coverage handling

Per cumulative T3.SB3 lesson "Audit envelope empty-state representation must be uniform across emit + persist paths":

- Empty cohort input -> harness emits CSV header-only + markdown with `"0 entries"` note + manifest with `entries_processed=0`. NOT an exception.
- All entries fail OHLCV coverage -> harness emits CSV with skip-row entries + markdown with `"0 entries evaluable; N entries skipped"` note + per-reason skip counters.
- All detectors emit zero-evidence verdicts -> harness emits CSV rows with `geometric_score=0.0` + `composite_score=0.0` + per-entry stage_observed; markdown headline reports "0 entries with composite_score > 0.5" (or similar threshold).

Empty-state representation: literal `(none)` string in markdown drill-down sections; `None` in JSON-serialized fields per cumulative T3.SB3 gotcha.

---

## §F Discriminating tests (per dispatch brief §1.4 + cumulative discipline)

### §F.1 L2 LOCK 5 BINDING tests

Enumerated at §E.3. BINDING; failure blocks merge.

### §F.2 Per-detector-failure isolation tests

Per cumulative T2.SB5 gotcha. 3-entry-fixture pattern:

- `test_per_entry_archive_missing_does_not_poison_other_entries` -- 3 cohort entries; 1 with archive missing; assert the other 2 yield verdict rows + the missing entry is recorded in skip CSV / drill-down.
- `test_per_entry_window_generation_failure_does_not_poison_others` -- 3 entries; 1 with bars that trip `extract_zigzag_swings` NaN guard at `swing/patterns/foundation.py:233-241`; assert the other 2 yield verdicts.
- `test_per_detector_exception_does_not_poison_other_detectors` -- 1 cohort entry; monkeypatch one detector to raise; assert the other 4 detectors yield verdicts for the same entry.

### §F.3 Production-parity tests

Enumerated at §E.1. Plants cohort entries derived from KNOWN persisted `pattern_evaluations` rows; asserts harness verdict matches.

### §F.4 Idempotency test

Enumerated at §D.6. Two-invocation byte-equality test against a static fixture.

### §F.5 Cohort-input shape tests

- `test_cohort_csv_missing_required_columns_raises_typed_exception` -- omits `ticker` column; asserts `CohortInputSchemaError` (typed; column names in message).
- `test_cohort_csv_optional_columns_round_trip` -- supplies all 7 optional columns; asserts each is parsed correctly + surfaced in output.
- `test_cohort_csv_malformed_asof_date_raises_typed_exception` -- supplies `asof_date='not-a-date'`; asserts `MalformedAsofDateError` (per cumulative gotcha #12).
- `test_cohort_inline_mode_parses_comma_separated_pairs` -- supplies `--cohort-inline RLMD:2026-04-15,DNTH:2026-04-15`; asserts 2 entries parsed.
- `test_cohort_inline_and_csv_supplied_raises_click_exception` -- both flags supplied; asserts ClickException per CLI boundary discipline.

### §F.6 Output schema tests

- `test_output_csv_header_columns_match_spec_section_I_2` -- asserts CSV header is verbatim the §I.2 column list.
- `test_output_markdown_ascii_only` -- asserts `summary.md` bytes are cp1252-decodable per cumulative Windows stdout safety gotcha.
- `test_output_manifest_json_round_trip` -- asserts manifest JSON is valid + contains all required keys per §I.3.
- `test_output_empty_cohort_emits_well_formed_csv_and_markdown` -- per §E.4 empty-state discipline.

### §F.7 Brief-framing accuracy regression test

Per cumulative gotcha #27 sub-lesson (brief-framing accuracy):

- `test_first_cohort_target_size_matches_documented_drill_down` -- if the first-cohort CSV is committed to `exports/research/cohorts/`, this test asserts row count == 67 (per V2 OHLCV sensitivity backtest brief §1 BINDING text); ticker-unique-count == 15. Locks the brief-framing accuracy claim at test time.

### §F.8 Total discriminating-test count budget

Per §H below: ~50-80 fast tests total (per dispatch brief §3 Phase 3). Most are §F.1-§F.7 enumerated above plus per-module unit tests in §H.

---

## §G Commit cadence (executing-plans phase preface)

### §G.0 Commit-cadence preface (per cumulative V2 OHLCV plan §G.0 + return report §3 deviation banking)

Per V2 OHLCV evaluator plan §G.0 + Codex R1.M6 RESOLVED precedent: per-task commits target the 35-60 line range. Mega-consolidation deviations BANKED in return report §3 with explicit "why" (e.g., T-V2.2 mega-consolidation precedent at V2 OHLCV executing-plans return report §3).

For this harness's executing-plans phase, the proposed commit cadence is **~30-50 commits** across 5 sub-bundles per §M.1 below:

| Sub-bundle | Estimated commits | Notes |
|-----------|--------------------|-------|
| T-PC.1 (exceptions.py + cohort_reader.py + ohlcv_reader.py re-export + tests) | ~6-10 | Smallest sub-bundle; mostly parsers + re-exports. |
| T-PC.2 (detector_invoker.py + tests) | ~10-16 | Largest sub-bundle; detector orchestration + template-match + per-entry try/except discipline. |
| T-PC.3 (output.py + tests) | ~6-10 | CSV + markdown emitters + manifest. |
| T-PC.4 (run.py + CLI subcommand registration in swing/cli.py + tests) | ~4-8 | CLI entry + arg parsing + ClickException wrapping. |
| T-PC.5 (method-record + first study writeup + first-cohort smoke run + closer) | ~4-8 | Documentation + operator smoke + closer. |

**Total estimated commits**: ~30-52 across executing-plans phase. Smaller than V2 OHLCV evaluator's 44-commit ship (which had ~10 Codex MCP fix bundles) because this harness has SIMPLER orchestration (no cfg substitution; no per-(variable, sweep_point) sweep loop).

### §G.1 Codex MCP round-budget expectation

V2 OHLCV evaluator brainstorming converged at R5 NO_NEW_CRITICAL_MAJOR (3 CRITICAL + 17 MAJOR + 13 MINOR cumulative). The executing-plans phase converged at R5 too.

For this harness, the expected Codex round budget is **R3-R5** to convergence:

- Lower than V2 OHLCV evaluator at brainstorming because the architecture is structurally simpler (no cfg substitution; no per-(variable, sweep_point) baseline parity; reusing V2 OHLCV's reader re-export).
- Comparable to V2 OHLCV evaluator at executing-plans because the per-detector failure isolation + template-match Pass 2 + production-parity discipline introduce new failure surfaces.

### §G.2 NO Co-Authored-By footer discipline

Per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15): all commits authored WITHOUT `Co-Authored-By` trailer. ~516+ cumulative streak preserved through this brainstorming phase + extended through writing-plans + executing-plans phases.

---

## §H Test scope projection

### §H.1 Per-module test budget (writing-plans phase will decompose)

Estimated test count for the harness brainstorming -> executing-plans full landing:

| Module / area | Tests | Detail |
|---------------|-------|--------|
| `exceptions.py` | ~2 | Typed exception class hierarchy + message-shape regression tests. |
| `cohort_reader.py` | ~10 | CSV mode required columns; CSV mode optional columns round-trip; inline mode parsing; malformed asof_date raises typed exception; empty cohort returns empty list; CSV mode + inline mode mutual exclusion at CLI boundary; cohort_label tagging round-trip; pattern_class_filter per-entry override. |
| `ohlcv_reader.py` (re-export per OQ-3 (a)) | ~5 | Re-export signature check (passes through V2 OHLCV evaluator's reader); L2 LOCK 5 BINDING tests REUSED from V2 OHLCV's test suite OR copied. Reader behavior tests live in V2 OHLCV's test suite; this harness's tests focus on L2 LOCK + re-export integrity. |
| `detector_invoker.py` | ~15-20 | Per-(cohort_entry, pattern_class) verdict shape; 5-detector registry parity with production; per-entry try/except isolation (3 modes: archive_missing, window_generation_error, detector_error); template-match Pass 2 ON / OFF semantics; composite_score formula matches production; stage_observed surface; window-mode last-only vs per-window; pattern_class_filter per-entry override + CLI override priority; conn=None test-stub path. |
| `output.py` | ~8 | CSV header + row shape; markdown headline + per-pattern-class summary + per-entry drill-down; ASCII-only output (cp1252 round-trip); manifest JSON round-trip; empty-state (`(none)` literal + `None` in JSON); per-skip-reason counter surfaces; first-cohort-target metadata round-trip via cohort_label. |
| `run.py` / CLI | ~8 | argparse boundaries (cohort-csv + cohort-inline mutual exclusion; pattern-class-filter parsing; window-mode enum; template-match toggle; max-runtime-seconds cap); ClickException wrapping ValueError per T-A.1.5b; output dir creation; baseline smoke (synthetic 5-entry cohort end-to-end). |
| `swing/cli.py` (subcommand registration) | ~3 | Diagnose group attachment; help-text; integration smoke. |
| Integration / E2E + L2 LOCK | ~10 | First-cohort smoke (synthetic 15-ticker cohort end-to-end against fixture archive + fixture exemplar corpus); production-parity test (cohort entry derived from KNOWN persisted pattern_evaluations row; asserts byte-equality of geometric_score + composite_score + structural_evidence_json); idempotency test (two invocations byte-equal results CSV); 5 BINDING L2 LOCK tests per §E.3 + §F.1; brief-framing accuracy regression test per §F.7. |
| **Total** | **~55-71** | Per dispatch brief §3 Phase 3 estimate "~50-80 tests". Smaller than V2 OHLCV evaluator's 115 tests because the orchestration scope is smaller (no cfg substitution; no per-(variable, sweep_point) sweep loop; no tier-1/tier-2 parity scoping). |

### §H.2 Discriminating-test patterns inherited from cumulative gotcha catalog (16+ cumulative through #27)

Each pattern below is a BINDING test for the harness per the cited cumulative gotcha:

- **#1-#5 (process discipline)**: applied at orchestrator level (CLAUDE.md gotcha cumulative). Brainstorming + writing-plans + executing-plans phases inherit.
- **#9 SQL aggregation UNIT audit**: N/A V1 dispatch (Mode (c) SQL is V2.5+; Mode (a) + (b) inputs are file-driven). Banked for Mode (c) writing-plans phase if/when V2.5+ lands.
- **#10 Existing-field reuse audit**: APPLIES at §C.1 cohort entry shape (optional fields candidate_id + eval_run_id + bucket + pivot + initial_stop mirror production schema columns; NO field duplication; no V2-specific aliases).
- **#11 Template-rendering surface audit**: N/A (no Jinja templates; CSV + markdown via Python `print` / `csv.writer`).
- **#12 `date.fromisoformat()` cross-type-boundary**: APPLIES at cohort_reader's asof_date parsing per §C.1 + §F.5 typed exception test.
- **#13 Form-render anchor lifecycle**: N/A (no web routes / forms).
- **#14 Architecture-location 5-sub-discipline (Expansion #10)**: APPLIES at §B.1 (NEW module placement decision documented per sub-discipline (a); orphan-label preservation per sub-discipline (e) handled via per-skip-reason counters).
- **#15 Taxonomy propagation (Expansion #11)**: APPLIES at §I.2 (CSV column enumeration MUST propagate through dataclass + CSV header + markdown matrix + test fixtures per V2 OHLCV evaluator's `SweepEntryV2` precedent). The harness's per-entry verdict dataclass adds ~14 columns vs production's 15-column `pattern_evaluations` row (drops pipeline_run_id; adds cohort_entry_id + cohort_label + stage_observed + window_index).
- **#16 Sibling-route audit (Expansion #12)**: N/A (no route handlers; single-CLI-entry-point).
- **#17 Expansion #2 refinement (brief-vs-actual-production-function-signature)**: APPLIES -- verified at §C.4 step 5 against actual `detect_*` function signatures from `swing/patterns/*.py:detect_<class>(bars, candidate_window, *, conn, ticker, asof_date)` shape. Grep verified at spec-write time.
- **#18 Expansion #4 refinement (SQL JOIN-cardinality + downstream-sufficiency)**: N/A this dispatch (no Mode (c) SQL). Banked for V2.5+.
- **#19 Expansion #2 sub-refinement (cascade-call-graph verification)**: APPLIES at §D.2 detector registry import decision -- the harness re-imports `_pattern_detect_registry()` from production; verified the function body invokes the 5 detector module imports + returns a 5-tuple; no cascade-call-graph drift risk.
- **#20 Expansion #4 sub-refinement (runtime-binding-shape + empty-result-set audit)**: N/A this dispatch (no parameterized SQL). Banked for V2.5+ Mode (c).
- **#21 Expansion #13 candidate (cumulative regression cascade audit)**: APPLIES at executing-plans phase post-Codex-fix discipline. Brainstorming-phase: no fix loops yet.
- **#22 Expansion #8 promotion (per-counter-accumulation audit)**: APPLIES at output.py per-skip-reason counters + per-(pattern_class, verdict_category) headline counters; writing-plans phase enumerates the per-counter unit explicitly.
- **#23 Expansion #11 promotion (dataclass attribution metadata audit)**: APPLIES at §I.2 CSV row dataclass; every attribution field (window_index + cohort_label + stage_observed + detector_version) explicitly enumerated with required-vs-optional semantics.
- **#24 Parallel-archive freshness desync**: APPLIES via re-export of V2 OHLCV evaluator's reader (inherits the both-exist Shape A wins LOCK + diagnostic surface per OQ-3 RECOMMEND).
- **#25 Sentinel-bucket parity-comparison discipline**: N/A this dispatch -- the harness output emits per-(cohort_entry, pattern_class) verdicts directly; no V1-vs-V2 parity comparison at the bucket level. (Production-parity test at §E.1 compares geometric_score + composite_score + structural_evidence_json at the per-verdict level; sentinel buckets do not apply.)
- **#26 OHLCV archive bar-content TEMPORAL mutation**: APPLIES at §D.6 idempotency caveat + study writeup `Limitations` section template at §L.2; same family as V2 OHLCV evaluator's L6 limitation.
- **#27 Silent-skip-without-audit pattern in pipeline steps**: APPLIES at §C.4 + §D.3 per-skip-reason counters + per-entry skip-row CSV emission + markdown drill-down -- the harness MUST surface every skipped cohort entry with reason + counter, NOT silent stderr-log-only skip per the gotcha #27 banking.

### §H.3 Test count baseline + harness bump projection

Brainstorming docs-only: ZERO test delta (baseline ~5893 fast tests UNCHANGED through brainstorming phase).

Writing-plans + executing-plans projected: +55-71 fast tests (~5948-5964 total post-harness-ship).

NO slow-marked tests in harness dispatch scope (harness operates against OHLCV archive read-only + persisted DB read-only; no live API calls).

### §H.4 Cross-bundle pin disposition

Harness dispatch is NEW research-branch arc; NO existing cross-bundle pins exist. Harness shipping does not affect any existing pin's un-skip schedule.

Forward-binding: if production `_step_pattern_detect` evolves (Option C pool-predicate widening per §A.4 V2.G candidate), a NEW cross-bundle pin may be needed at the harness-vs-production parity point. Decision deferred to V2.G triage.

---

## §I Integration points + output schema

### §I.1 Inputs

- **Cohort input** -- Mode (a) inline tuple list OR Mode (b) CSV path per §C.2.
- **Operator DB** -- `~/swing-data/swing.db` opened via URI `mode=ro` per V2 OHLCV precedent. READ-ONLY consumption of:
  - `candidates` + `evaluation_runs` (via `current_stage` lookup per detector criterion #1)
  - `candidate_criteria` (via `current_stage` for TT-pass count)
  - `pattern_exemplars` (via `list_exemplars` for template-match Pass 2 corpus)
- **OHLCV archive** -- `~/swing-data/prices_cache/{ticker}.yfinance.parquet` (with legacy `{ticker}.parquet` fallback per V2 OHLCV evaluator's reader contract). NEVER `{ticker}.schwab_api.parquet` per L2 LOCK BINDING.
- **Config** -- `swing.config.Config.from_defaults()` (READ-ONLY; for cache_dir + other paths).

### §I.2 Output CSV schema (per-entry verdict; per-(cohort_entry, pattern_class, window) row)

```
cohort_entry_id, cohort_label, ticker, asof_date,
candidate_id, eval_run_id, persisted_bucket, persisted_pivot, persisted_initial_stop,
window_index, window_start_date, window_end_date, anchor_date, anchor_reason,
pattern_class, detector_version, stage_observed,
geometric_score, template_match_score, composite_score,
template_match_nearest_exemplar_ids_json, criteria_pass_json, structural_evidence_json,
skip_reason
```

24 columns. Each cohort entry produces 5 rows under `--window-mode=last-only` + `--pattern-class-filter=ALL` (one per detector). Under `--window-mode=per-window`, the row count is (windows_per_entry x 5).

Skipped entries produce ONE row per cohort entry with `pattern_class=null`, `geometric_score=null`, `composite_score=null`, `skip_reason='coverage_skip' | 'archive_missing_skip' | 'window_generation_error' | 'no_windows' | 'detector_error_all'`, etc. (NOT 5 rows per entry; entries that skip at the bars-fetch or window-generation phase have no per-detector verdict to emit.)

**Per Expansion #11 taxonomy-propagation BINDING**: `skip_reason` enum values are enumerated explicitly in `cohort_reader.py` (or `detector_invoker.py`) as a module-level frozenset; output rendering + test fixtures + dataclass `__post_init__` validator all reference this single source-of-truth per cumulative gotcha #15 family.

### §I.3 Output manifest JSON schema

```json
{
  "harness_version": "0.1.0",
  "cohort_input_mode": "csv" | "inline",
  "cohort_input_path": "<resolved path or null>",
  "cohort_input_sha256": "<sha256 hex of cohort input bytes>",
  "cohort_entries_count": <int>,
  "cohort_unique_tickers_count": <int>,
  "cohort_unique_asof_dates_count": <int>,
  "db_path": "<resolved DB path>",
  "cache_dir": "<resolved cache dir>",
  "ohlcv_reader_module": "research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader",
  "ohlcv_reader_signature_hash": "<sha256 of inspect.signature.return_annotation + parameter names>",
  "pattern_exemplars_corpus_size_at_invocation": <int>,
  "pattern_exemplars_corpus_filter": "final_decision IN ('confirmed','watch')",
  "pattern_exemplars_filtered_size": <int>,
  "detectors_invoked": ["vcp", "flat_base", "cup_with_handle", "high_tight_flag", "double_bottom_w"],
  "window_mode": "last-only" | "per-window",
  "template_match_mode": "on" | "off",
  "started_at_utc": "<ISO>",
  "finished_at_utc": "<ISO>",
  "runtime_seconds": <float>,
  "entries_processed": <int>,
  "verdicts_emitted": <int>,
  "skipped_entries": {
    "coverage_skip": <int>,
    "archive_missing_skip": <int>,
    "window_generation_error": <int>,
    "no_windows": <int>,
    "detector_error_all": <int>
  },
  "both_exist_diagnostic": {
    "count": <int>,
    "affected_tickers": [<sorted unique ticker list; capped at 50>]
  },
  "l2_lock_preserved": true
}
```

`both_exist_diagnostic` re-exported from V2 OHLCV evaluator's `BothExistDiagnostic` per OQ-3 (a). `l2_lock_preserved: true` is a static assertion; the BINDING discriminating tests per §E.3 verify it at test time.

### §I.4 Output markdown structure

Sections (in order):

1. **Header** -- generated time + cohort input mode + cohort size + harness version + L2 LOCK preserved.
2. **Headline** -- per-pattern-class summary table:
   - `pattern_class | entries_evaluated | composite >= 0.5 | composite >= 0.7 | composite >= 0.9 | max composite`
   - Answers operator's motivating question: "of the cohort, how many entries pass each detector's composite threshold?"
3. **Per-pattern-class drill-down** -- one subsection per pattern_class with per-entry composite_score + geometric_score + template_match_score (top-N if cohort large).
4. **Skip-reason summary** -- per-skip-reason counter table + per-entry skip listing (capped at first 50 per skip reason).
5. **Both-exist warning banner** (conditional; only when count > 0) -- per V2 OHLCV evaluator output.py pattern.
6. **Notes** -- per-pattern-class scope-reduction caveat + cumulative gotcha #26 caveat (archive bar-content TEMPORAL mutation) + pattern_exemplars corpus drift caveat.
7. **Manifest** -- summary of `manifest.json` fields for analyst-readable reference.

ASCII-only output per cumulative Windows cp1252 stdout safety gotcha (§G.5 of V2 OHLCV evaluator spec).

### §I.5 Downstream consumption pathway (analyst workflow)

The harness CSV is designed for direct join with backtest output:

- Cohort entry's `(candidate_id, eval_run_id)` joins to backtest trade rows (per `tightness_range_factor=1.005` backtest at `docs/v2-tightness-range-factor-backtest-findings-2026-05-24.md` Section 6 table).
- Per-(cohort_entry, pattern_class) verdict row joins via `(ticker, asof_date)` to backtest pattern groups (the backtest dedups consecutive eval_runs into ~17 unique patterns from the 67 flip entries).
- Cross-tabulation: detector-pass (composite >= 0.5 OR 0.7) vs backtest-triggered vs backtest-closed-positive-R + backtest-closed-negative-R + backtest-untriggered.

Operator workflow (per dispatch brief §7):
1. Run harness against the 67-entry first-cohort target.
2. Cross-tabulate detector-pass cohort vs backtest-trigger outcomes (already shipped at merge `e0a9edd`).
3. Answer the binding research question: "do detector-passed candidates have higher breakout-trigger rate than detector-failed candidates?"
4. If YES (differentiated): next-arc drafts cfg-policy proposal that overlays detector-pass on the loosened threshold.
5. If NO (indistinguishable): architectural insight = numeric A+ classification + chart-shape detection are independently calibrated layers that don't compose simply; pivot to alternate research arcs.

---

## §J Open questions (OQs) surfaced for operator-paired triage

13 OQs surfaced -- 8 from dispatch brief (implicitly per §1.2-§1.6 enumerated below) + 5 NEW from substrate analysis at spec-write time. Each OQ has a RECOMMEND disposition; final disposition is operator-paired between brainstorming + writing-plans phases.

### OQ-1: Detector invocation interface

**Question**: Direct production detector function invocation vs V2-side mirror with substituted thresholds?

**RECOMMEND**: Direct production detector function invocation per §D.1. Detector behavior LOCKs are intentional; V2-side mirror would introduce drift risk. If a future arc needs threshold loosening (e.g., "loosen high_tight_flag pole_pct from 100% to 80%"), that arc extends this harness with a cfg-substitution layer. NOT this dispatch.

### OQ-2: Cohort input mode

**Question**: Mode (a) inline tuple list vs Mode (b) CSV vs Mode (c) SQL query against operator DB?

**RECOMMEND**: V1 ships Mode (b) CSV as primary + Mode (a) inline as smoke fallback per dispatch brief §1.2. Mode (c) SQL deferred V2.5+ per dispatch brief §1.6 banking. V1 first-cohort target (67 flips) uses Mode (b).

### OQ-3: OHLCV reader source

**Question**: (a) Re-export V2 OHLCV evaluator's `ohlcv_reader.py` verbatim from `research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader` vs (b) build a new minimal reader matching its L2 LOCK contract?

**RECOMMEND**: (a) re-export. Strict zero-drift between two read-only Shape-A readers; both readers' L2 LOCK 5 BINDING discriminating tests share the same backing implementation. The harness's own L2 LOCK tests at §E.3 + §F.1 verify the re-export integrity. If V2 OHLCV evaluator's reader changes shape in a future version, the harness immediately inherits. Cross-bundle drift risk acceptable because both readers serve research-branch purposes + the L2 LOCK BINDING tests catch any regression.

ALTERNATIVE (b): build a new minimal reader at `research/harness/pattern_cohort_evaluator/ohlcv_reader.py` -- avoids cross-research-module dependency but doubles the L2 LOCK BINDING test surface (10 tests instead of 5 if both readers need to be independently verified). Operator-paired triage.

### OQ-4: Anchor mode (window generation)

**Question**: Mirror production `zigzag_pivot` only vs allow multi-mode (zigzag_pivot + ma_crossover + high_low_breakout per `generate_candidate_windows` enum at `swing/patterns/foundation.py:428-432`)?

**RECOMMEND**: Mirror production `zigzag_pivot` only for V1 ship per dispatch brief §1.3. Multi-mode banked V2.5+ candidate. Production at runner.py:1619 hardcodes `zigzag_pivot` per recon section 5 + per the detector contract docstrings (per `swing/patterns/vcp.py:478` mode-specific anchor semantic). Multi-mode would surface different anchor semantics per mode + complicate the per-window verdict shape; deferred.

### OQ-5: Pattern-class filter scope

**Question**: Per-entry `pattern_class_filter` (CSV column) vs CLI global `--pattern-class-filter` vs both?

**RECOMMEND**: BOTH per §C.5. Per-entry filter (CSV column) takes precedence; CLI flag is a global override applied when CSV column is null. Use case: a VCP-only cohort can omit per-entry filter + pass `--pattern-class-filter=vcp` once; a mixed-class cohort uses per-entry filter. Discriminating test: 3-entry CSV with mixed per-entry filter + CLI override; assert per-entry takes precedence.

### OQ-6: Template-match Pass 2 mode

**Question**: Default `--template-match=on` (mirrors production) vs `--template-match=off` (geometric-only)?

**RECOMMEND**: Default `--template-match=on` for production-parity per §D.4. Operator can disable via `--template-match=off` for faster smoke runs OR for cohorts where production-parity is not the analytical goal (e.g., investigating detector behavior independently of corpus drift).

### OQ-7: Window-mode (last-only vs per-window)

**Question**: Default `--window-mode=last-only` (mirrors production `_step_pattern_detect` at runner.py:1646) vs `--window-mode=per-window` (emit verdicts for ALL generated windows)?

**RECOMMEND**: Default `--window-mode=per-window` for the harness's analytical purpose. Production uses last-only to honor the `pattern_evaluations` unique-index constraint at `(pipeline_run_id, ticker, pattern_class)`; the harness has no such constraint and the operator may benefit from multi-anchor visibility (e.g., "this ticker had a watch-bucket setup 5 days BEFORE today's anchor; does that window pass the detector too?"). Operator can force `--window-mode=last-only` to match production semantics for parity testing.

### OQ-8: `current_stage` Stage-2-gate override

**Question**: Default `current_stage(conn, ticker, asof_date)` per production semantics vs allow operator-supplied `stage_override` per cohort entry?

**RECOMMEND**: Default `current_stage` per production. Per-entry `stage_override` deferred V2.5+ candidate (out of scope V1). Rationale: V1 first-cohort target has all entries sourced from operator DB with real Stage-2 status; no override needed. Future cohorts sourced from external data (e.g., synthetic tickers; cross-symbol research) would benefit from override; banked for V2.5+ executing-plans triage.

### OQ-9: First-cohort target

**Question**: Confirm the +67 watch->aplus flip cohort at vcp.tightness_range_factor=1.005 as the V1 first-cohort target?

**RECOMMEND**: YES per dispatch brief §7. The cohort is small (67 entries / 15 unique tickers), is already documented in V2 OHLCV sensitivity backtest dispatch brief, and joins cleanly with the existing backtest output for cross-tabulation analysis. Alternative cohorts (e.g., the +16 `vcp.tightness_days_required` cohort OR all 5 binding-variable cohorts) deferred for second / third smoke runs after V1 ship.

### OQ-10: V1 harness CLI subcommand name

**Question**: `swing diagnose pattern-cohort-detect` vs `swing diagnose pattern-evaluate-cohort` vs `swing diagnose pattern-detection-cohort` vs other?

**RECOMMEND**: `swing diagnose pattern-cohort-detect` -- consistent with V2 OHLCV evaluator's `swing diagnose aplus-sensitivity-v2` naming pattern (verb-noun-modifier), highlights cohort-input nature, brief enough for tab-complete. Operator-paired; alternatives are valid.

### OQ-11: Both-exist diagnostic surface

**Question**: Inherit V2 OHLCV evaluator's `BothExistDiagnostic` surface (manifest field + markdown warning banner + per-ticker WARNING log per Codex R4.M1 V2 OHLCV precedent)?

**RECOMMEND**: YES per §I.3 manifest schema. Mirrors V2 OHLCV evaluator pattern; if the harness re-exports the V2 OHLCV reader (per OQ-3 (a)), the `BothExistDiagnostic` flows through naturally.

### OQ-12: Empty-state representation in output

**Question**: Per cumulative T3.SB3 gotcha "Audit envelope empty-state representation must be uniform"; what's the canonical empty-state across CSV + markdown + manifest?

**RECOMMEND**: Per §E.4 + cumulative T3.SB3 LOCK: literal `(none)` string in markdown drill-down sections; `null` in CSV cells (NOT empty string); `None` in JSON-serialized fields (NOT `[]` or `""`). Uniform across all output paths per cumulative discipline.

### OQ-13: CLI subcommand registration as the production-`swing/`-write carve-out

**Question**: §A.1 originally claimed "Production `swing/` code is READ-ONLY through this dispatch arc." But V1 must register the new CLI subcommand. This is an explicit carve-out (per V2 OHLCV evaluator OQ-17 precedent)?

**RECOMMEND**: YES per V2 OHLCV evaluator OQ-17 precedent. Explicit carve-out per §A.1. The CLI subcommand registration is the SOLE production-`swing/` modification this dispatch arc makes. Realistic line count: 35-60 lines (per V2 OHLCV evaluator OQ-17 V1 precedent at `swing/cli.py:4748-4787`).

---

## §K Method-record proposal (NEW; not an extension)

### §K.1 NEW method-record at `research/method-records/pattern-cohort-detection.md`

Frontmatter:

```yaml
---
key: pattern-cohort-detection
name: Chart-shape pattern cohort detector-confirmation harness
layer: detection
status: research
baseline_or_predecessor: production swing.pipeline.runner._step_pattern_detect (aplus-only)
version: 0.1.0
last_updated: <harness ship date>
---
```

### §K.2 Definition

Cohort-input-driven invocation surface for the Phase 13 chart-shape detectors (`vcp`, `flat_base`, `cup_with_handle`, `high_tight_flag`, `double_bottom_w`). Operator supplies a cohort of `(ticker, asof_date)` tuples (CSV or inline list); harness invokes each detector against each entry; emits per-(cohort_entry, pattern_class, window) verdict CSV + analyst-readable markdown summary + manifest JSON.

Operates independently of the production `_step_pattern_detect`'s `bucket == 'aplus'` pool predicate; designed to answer: *do Phase 13 detectors filter loosened-A+ candidates productively?*

### §K.3 Promotion criteria (research -> shadow -> production)

**research -> shadow**:

1. Harness shipped + L2 LOCK 5 BINDING discriminating tests green per §E.3.
2. Baseline parity invariant green per §E.1 (production-persisted `pattern_evaluations` rows reproduce byte-equality on per-detector verdict).
3. At least 1 cohort study writeup published (first-cohort = the 67 watch->aplus flips at vcp.tightness_range_factor=1.005).
4. At least 1 operator-paired ratification of an actionable finding (e.g., "detector-pass cohort has differentiated breakout-trigger rate" OR "detector-pass and detector-fail cohorts are indistinguishable; chart-shape detection adds no orthogonal signal at the loosened threshold").

**shadow -> production**:

1. At least 1 cfg-policy proposal OR pool-predicate-widening proposal evaluated against at least 2 disjoint cohorts.
2. Proposal's expectancy delta statistically distinguishable from baseline.
3. Operator-paired ratification.

**Anti-promotion guards**: harness verdict regression against production-persisted `pattern_evaluations` (parity invariant); pattern_exemplars corpus drift between study + ratification; OHLCV archive temporal mutation per cumulative gotcha #26 invalidates baseline parity.

### §K.4 Validation notes

- **L2 LOCK preservation**: 5 BINDING discriminating tests at `tests/research/test_pattern_cohort_evaluator_reader.py` (or per-test-file enumerated per §F.1). ZERO new Schwab API calls.
- **Production-parity invariant**: per §E.1 + acceptance test `test_harness_per_entry_verdict_matches_persisted_pattern_evaluations_when_aplus`.
- **Per-entry failure isolation**: per cumulative T2.SB5 gotcha; 3-mode discriminating tests per §F.2.
- **Idempotency**: byte-equality on two-invocation against static fixture per §D.6 + §F.4.
- **ASCII-only output**: cp1252-encodable per cumulative Windows stdout safety gotcha.
- **Both-exist Shape A wins (per cumulative gotcha #24)**: inherited via OQ-3 (a) re-export of V2 OHLCV evaluator's reader.
- **Archive bar-content TEMPORAL mutation caveat (per cumulative gotcha #26)**: documented in study writeup `Limitations` section template at §L.

### §K.5 Notes section

- V1 ships with `--window-mode=per-window` default per OQ-7 RECOMMEND; operator can force `last-only` to match production semantics for parity testing.
- V1 ships with `--template-match=on` default per OQ-6 RECOMMEND for production-parity.
- V1 ships with `--pattern-class-filter=ALL` default per OQ-5 RECOMMEND.
- V2.5+ BANK per dispatch brief §1.6 + OQ enumeration:
  - Mode (c) SQL query cohort input.
  - Stage 3 AI second-opinion eval on winners-without-detection cell.
  - Cohort-stratified analysis (sector / market-cap / regime).
  - Bootstrap / Monte Carlo statistical confidence intervals.
  - Multi-anchor-mode (zigzag_pivot + ma_crossover + high_low_breakout).
  - Per-entry `stage_override` for synthetic-cohort use cases.
  - Per-entry `pattern_exemplars_corpus_snapshot_hash` field for corpus drift pinning.

---

## §L Study writeup template

### §L.1 Proposed first-cohort study writeup

NEW study writeup at `research/studies/<harness-ship-date>-pattern-cohort-detection.md` -- companion to V2 OHLCV criterion-evaluator study.

Section structure (proposed):

1. **Question** -- Per dispatch brief §7: do Phase 13 detectors confirm candidates that V1 sensitivity analysis identifies as binding at the watch->A+ boundary?
2. **Null hypothesis** -- Detector confirmation rate is invariant to V1 sensitivity binding-variable classification (i.e., detector-pass rate on watch->aplus-flip cohort is statistically indistinguishable from detector-pass rate on baseline aplus cohort).
3. **Baseline** -- Production cfg values at harness ship date + sensitivity binding variables (5 identified at full-63-eval-run reproduction).
4. **Methodology**:
   - Harness: `research/harness/pattern_cohort_evaluator/` (this method-record's deliverable)
   - First cohort: 67 watch->aplus flips at vcp.tightness_range_factor=1.005 (per V2 OHLCV sensitivity backtest brief §1)
   - Comparison cohort: baseline 5 aplus candidates at vcp.tightness_range_factor=0.67 (the V2 OHLCV evaluator's headline)
   - Cross-tabulation pivots: detector-pass (composite >= 0.5 OR 0.7) x backtest-triggered x backtest-closed-positive-R per the join pathway at §I.5.
5. **Results**:
   - Per-pattern-class detector-pass count + percentage on the 67-cohort vs the 5-cohort.
   - Per-entry composite_score distribution.
   - Cross-tabulation against backtest output.
6. **Interpretation**:
   - IF detector-pass + backtest-triggered cells diverge from detector-pass + backtest-untriggered cells: chart-shape detection adds orthogonal signal at the loosened threshold.
   - IF detector-pass and detector-fail cohorts have indistinguishable backtest outcomes: detection-vs-classification are independently calibrated; no orthogonal signal at this threshold.
7. **Limitations** (per §L.2 template).
8. **Conclusion** + Forward-binding next-arc recommendation.

### §L.2 Limitations section template (per cumulative discipline)

```
## Limitations

### L1: pattern_exemplars corpus drift between cohort-input-time and harness-invocation-time

The harness reads the CURRENT `pattern_exemplars` corpus at invocation time
via `swing.data.repos.pattern_exemplars.list_exemplars(conn)`. If the corpus
grew or shrunk between when the cohort was constructed and when the harness
ran, the template-match Pass 2 verdicts may differ from a temporally-aligned
read. Mitigation: capture `pattern_exemplars_corpus_size_at_invocation` in
manifest; pinned-corpus V2.5+ candidate per K.5 banking.

### L2: OHLCV archive bar-content TEMPORAL mutation (cumulative gotcha #26)

Production pipeline runs progressively overwrite historical bars via
`drop_duplicates(subset=['asof_date'], keep='last')` semantics when yfinance
returns slightly different historical values (late-reported volume corrections;
split/dividend retroactive adjustments). Harness reads the CURRENT archive
at invocation time. Per-entry verdict may drift if intervening pipeline runs
mutated the asof_date bar between cohort-input-time and harness-invocation-time.

Mitigation: documented caveat (no V1 fix); same family as V2 OHLCV evaluator
limitation L6. V2.5+ candidate: immutable archive snapshot.

### L3: `current_stage` lookup uses CURRENT operator DB state

The harness's per-detector invocation passes `conn` to `current_stage(conn,
ticker, asof_date)` per `swing/patterns/foundation.py:745`. The lookup
queries `candidates` JOIN `evaluation_runs` for the most-recent candidate
at the ticker with `er.action_session_date <= asof_date`. If the operator
DB has been pruned (eval_runs deleted) between cohort-input-time and
harness-invocation-time, `current_stage` may return `'undefined'` for
entries that PREVIOUSLY had `'stage_2'` status. This would zero-out
detector criterion #1 + return zero-evidence verdicts.

Mitigation: documented caveat; per-entry `stage_observed` column in
output CSV surfaces the actual stage at harness invocation for operator
audit.

### L4: Parallel-archive freshness desync (cumulative gotcha #24)

Inherited from V2 OHLCV evaluator (via OHLCV reader re-export per OQ-3 (a)).
When both `{ticker}.yfinance.parquet` (Shape A) and `{ticker}.parquet`
(legacy) exist with desynchronized refresh times, Shape A wins unconditionally
per OQ-18 V2 OHLCV LOCK. Per-ticker affected list surfaced in both-exist
warning banner per §I.4.
```

---

## §M Dispatch sequence

### §M.1 Sub-bundle decomposition recommendation for executing-plans phase

Per V2 OHLCV evaluator executing-plans precedent (5 sub-bundles; ~44 commits including 10 Codex MCP fix bundles + 1 return report). For this harness, the proposed decomposition:

| Sub-bundle | Task | Deliverable | Estimated commits |
|-----------|------|-------------|-------------------|
| **T-PC.1** | `exceptions.py` + `cohort_reader.py` + `ohlcv_reader.py` re-export + tests | Typed exception hierarchy + cohort CSV/inline parser + L2 LOCK reader re-export + 5 BINDING discriminating tests | ~6-10 commits |
| **T-PC.2** | `detector_invoker.py` + tests | Per-(cohort_entry, pattern_class, window) detector orchestration + template-match Pass 2 + per-entry failure isolation + composite_score formula parity | ~10-16 commits (largest sub-bundle) |
| **T-PC.3** | `output.py` + tests | CSV + markdown summary + manifest JSON + ASCII-only output + per-skip-reason counters + both-exist warning banner | ~6-10 commits |
| **T-PC.4** | `run.py` + CLI subcommand registration in `swing/cli.py` + tests | CLI entry + argparse + ClickException wrapping + smoke E2E | ~4-8 commits |
| **T-PC.5** | Method-record + first study writeup + first-cohort smoke run + closer | NEW method-record at `research/method-records/pattern-cohort-detection.md` per §K; first study writeup at `research/studies/<date>-pattern-cohort-detection.md`; operator-paired smoke run against the 67-entry first-cohort target; closer commit | ~4-8 commits |

**Total estimated commits**: ~30-52 across executing-plans phase. Smaller than V2 OHLCV evaluator's 44-commit ship.

### §M.2 Concurrent dispatch potential

Sub-bundles T-PC.1, T-PC.2, T-PC.3 have sequential dependencies (T-PC.2 depends on T-PC.1; T-PC.3 depends on T-PC.2). Sub-bundle T-PC.4 partially depends on T-PC.3 (CLI emit paths). T-PC.5 depends on all prior + operator gate.

**RECOMMEND**: Sequential single-implementer dispatch for executing-plans phase. NO concurrent dispatch (single-implementer-driven via `superpowers:subagent-driven-development` per project workflow precedent).

### §M.3 Open questions deferred to writing-plans phase

- Actual function signatures + class shapes (proposed in §B.1 + §C.4 + §D.3 but not BINDING; writing-plans refines).
- Exact CLI flag naming + default value tuning (per OQ-5 / OQ-6 / OQ-7 / OQ-10 / OQ-13).
- Per-task test-budget refinement (writing-plans decomposes the §H.1 ~55-71-test estimate into per-task budgets).
- Per-sub-bundle Codex MCP round-budget expectation.

### §M.4 Post executing-plans handback

Harness shipping completes the SECOND applied-research arc post-Phase-13-FULLY-CLOSED (V2 OHLCV evaluator was the first). Forward-binding for the NEXT applied-research arc:

- IF first-cohort study identifies orthogonal detector signal (detector-pass + backtest-triggered cells diverge): NEXT arc drafts cfg-policy proposal that overlays detector-pass on the loosened threshold OR widens production pool predicate to invoke detectors on watch-bucket candidates.
- IF first-cohort study finds detection-classification independence (no orthogonal signal): NEXT arc pivots to investigate market-conditions OR alternate gates (e.g., RS percentile gating; sector-rotation overlays).
- THEN: Phase 14 commissioning per operator-paired triage.

---

## §N Self-review (BINDING per superpowers:brainstorming spec self-review gate)

### §N.1 Placeholder scan

- ZERO `TBD` placeholders in BINDING-text sections. (Verified via grep at spec-write time. The single `TBD in writing-plans` marker in a §D.3 pseudo-code comment block is a deferred-to-writing-plans signature-refinement note, NOT a placeholder for spec content; mirrors V2 OHLCV evaluator spec's `actual signature TBD in writing-plans phase` precedent at `docs/superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md:285`. The `<harness ship date>` + `<date>` + `<resolved path>` etc. literal-text placeholders are intentional for downstream writing-plans phase + executing-plans ship date stamping.)
- ZERO `TODO` markers.
- ZERO incomplete sections.
- ZERO vague requirements.

### §N.2 Internal consistency

Checked sections for contradiction:

- §A.1 + §B.1: NEW module `research/harness/pattern_cohort_evaluator/` (7 modules) referenced consistently.
- §A.4 + §D.1 + §E.1: Production `_step_pattern_detect` STAYS as aplus-only canonical write; harness is parallel read-only research surface; production-parity invariant per §E.1 only applies when production wrote a row (aplus-bucket entries).
- §B.1 + §D.2: detector registry re-imported from `swing.pipeline.runner._pattern_detect_registry` per OQ-1 + OQ-direct production invocation; consistent.
- §C.4 + §D.3 + §D.4: per-entry try/except discipline + template-match Pass 2 + composite_score formula all mirror production runner.py:1670-2104.
- §H.1 test count (~55-71) matches §H.3 baseline-bump projection (+55-71 fast tests). Consistent.
- §I.2 CSV schema (24 columns) matches §I.3 manifest schema fields + §I.4 markdown structure references.
- §K version (0.1.0) matches §K.1 status (research) + §K.3 promotion criteria (V1 ship satisfies "harness shipped + L2 LOCK green"). Consistent.
- §J OQ count (13 = 8 brief-implicit + 5 substrate-NEW) matches §M.3 forward-deferred subset. Consistent.

### §N.3 Scope check

The harness is the SECOND applied-research arc post-Phase-13-FULLY-CLOSED -- appropriately scoped for ONE brainstorming -> writing-plans -> executing-plans cycle following the V2 OHLCV evaluator precedent. Sub-bundle decomposition at §M.1 (5 sub-bundles; ~30-52 commits) is comparable-but-smaller than V2 OHLCV evaluator's 44-commit ship. No over-scoping.

### §N.4 Ambiguity check

All interpretation-ambiguous statements made explicit:

- "Detector-pass" defined operationally per §I.4 headline: `composite_score >= 0.5` (loose) + `>= 0.7` (medium) + `>= 0.9` (tight); operator selects the threshold appropriate for the analytical question.
- "Production-parity invariant" defined operationally at §E.1 with 5 explicit scoping conditions.
- "Cohort input" defined at §C.1 with explicit required-vs-optional field list.
- "Window mode last-only vs per-window" defined operationally at §C.4 step 4.
- "Skip reason" enumerated at §I.2 as a 5-value frozenset.
- "First-cohort target" defined at §C.3 as 67 entries / 15 unique tickers from the V2 OHLCV sensitivity drill-down per the V2 tightness backtest dispatch brief §1.
- "Brief-framing accuracy verification" at the header documents the +75 vs +67 numeric reconciliation explicitly.

ZERO interpretation-ambiguous requirements remaining.

### §N.5 Cumulative gotcha catalog application

All 27 cumulative CLAUDE.md gotchas (per project-level catalog through gotcha #27 banked at merge `54bd9c6`) referenced where applicable:

- Process discipline gotchas (#1-#8) applied at orchestrator level.
- Schema + Python-side discipline (#9-#16 + #19-#20): N/A this dispatch (no schema change; no parameterized SQL; no Mode (c) SQL).
- Architecture-location (#14 / Expansion #10): applied at §B.1.
- Taxonomy propagation (#15 / Expansion #11): applied at §I.2.
- Brief-vs-actual-production-function-signature (#17 / Expansion #2 refinement): applied at §C.4 + §D.2 grep verification.
- Cascade-call-graph (#19 / Expansion #2 sub-refinement): applied at §D.2 detector registry import.
- Cumulative regression cascade (#21 / Expansion #13 candidate): banked for executing-plans phase post-Codex-fix discipline.
- Per-counter-accumulation (#22 / Expansion #8 promotion): applied at §I.3 manifest counters + writing-plans phase per-counter unit enumeration.
- Dataclass attribution metadata (#23 / Expansion #11 promotion): applied at §I.2 CSV row dataclass field enumeration.
- Parallel-archive freshness desync (#24): inherited via OQ-3 (a) reader re-export.
- Sentinel-bucket parity-comparison (#25): N/A this dispatch (no V1-vs-V2 bucket comparison).
- Archive bar-content TEMPORAL mutation (#26): applied at §L.2 limitation L2 + study writeup template.
- Silent-skip-without-audit (#27): applied at §C.4 + §D.3 per-skip-reason counter + per-entry skip-row CSV emission (this gotcha is the architectural motivation for the harness's own audit-row discipline).

---

*End of pattern cohort detector evaluator research harness brainstorming design spec. SECOND Applied Research arc post-Phase-13-FULLY-CLOSED following V2 OHLCV criterion-evaluator arc precedent. Option D LOCKED 2026-05-24 PM via dispatch brief at `8ba87cd`. Architecturally-correct answer to operator's standing research question about Phase 13 detector filtering performance on loosened-A+ cohorts. ~516+ ZERO Co-Authored-By footer streak preserved through this spec commit. Structural scope (~30-52 commits projected for executing-plans phase; ~55-71 fast tests projected) appropriate for SECOND-tier research infrastructure investment following the V2 OHLCV evaluator's 44-commit precedent.*
