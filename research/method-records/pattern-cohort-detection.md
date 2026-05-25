---
key: pattern-cohort-detection
name: Chart-shape pattern cohort detector-confirmation harness
layer: detection
status: research
baseline_or_predecessor: production swing.pipeline.runner._step_pattern_detect (aplus-only)
version: 0.1.0
last_updated: 2026-05-24
---

# Chart-shape pattern cohort detector-confirmation harness

## Definition

Cohort-input-driven invocation surface for the 5 Phase 13 chart-shape detectors
(`vcp`, `flat_base`, `cup_with_handle`, `high_tight_flag`, `double_bottom_w`).
Given an operator-supplied cohort of `(ticker, asof_date)` tuples (CSV Mode (b)
or inline Mode (a)), the harness reads Shape A OHLCV via re-export of V2 OHLCV
evaluator's reader (OQ-3 LOCK), generates candidate windows via
`generate_candidate_windows(bars, "zigzag_pivot", ...)` (OQ-4 LOCK — production
parity), invokes each detector via `_pattern_detect_registry()` (OQ-1 LOCK), and
emits per-`(cohort_entry, pattern_class, window)` verdicts as 24-column CSV +
analyst-readable markdown summary + manifest JSON. Designed to answer the
research question that gotcha #27 surfaced: *production `_step_pattern_detect`
gates on `bucket == 'aplus'` by design — do the detectors confirm candidates
that V1 sensitivity analysis identifies as binding at the watch→A+ boundary?*

## Inputs

- Cohort substrate: operator-supplied CSV (Mode (b)) OR inline `TICKER:ISO` list
  (Mode (a)). Required columns: `ticker`, `asof_date`. Optional columns:
  `candidate_id`, `eval_run_id`, `bucket`, `pivot`, `initial_stop`,
  `pattern_class_filter`, `cohort_label`.
- Read-only operator DB at `~/swing-data/swing.db` (URI `mode=ro`).
- Shape A parquet under `cfg.paths.prices_cache_dir`.

## Parameters

- `--window-mode` ∈ `{last-only, per-window}`, default `per-window`
  (NON-production-default; deliberate analytical bias per OQ-7 LOCK).
- `--template-match` ∈ `{on, off}`, default `on` (production-parity per OQ-6).
- `--pattern-class-filter` comma-separated subset of the 5 detectors; default
  None (all 5).

## Outputs

- 24-column CSV (`results.csv`) — one row per `(cohort_entry, pattern_class, window)`
  with `geometric_score` + `template_match_score` + `composite_score` + skip
  reason (where applicable).
- Analyst markdown (`summary.md`) — headline per-pattern-class summary table +
  per-class drill-down (capped at first 50 by composite_score) + skip-reason
  summary + conditional both-exist diagnostic banner + Notes + manifest summary.
- Manifest JSON (`manifest.json`) — cohort SHA-256 + corpus sizes + detector
  registry + window/template-match modes + runtime + counter envelope + L2 LOCK
  sentinel.

## Operator explainability

- **One-sentence rationale:** "Did the detectors confirm the watch-promoted
  candidates that the sensitivity sweep flagged as binding?"
- **One-paragraph explanation:** Production `_step_pattern_detect` only
  evaluates candidates with `bucket='aplus'`. When V1 sensitivity analysis
  identifies a threshold variable that flips N candidates `watch → aplus`, those
  candidates have NO detector verdict on the V1 persisted record (they were
  never aplus when production ran). This harness re-evaluates them: if the
  detector confirms the chart shape, the threshold relaxation has orthogonal
  signal; if it does not, classification and detection are independently
  calibrated and the relaxation buys no actionable trades.
- **FAQ:** *Why is `--window-mode` default `per-window` when production uses
  last-only?* Per OQ-7 LOCK: the analytical purpose is "find the best window
  across the candidate's history" not "did the most recent window pass" —
  reusing production's last-only would discard most of the diagnostic signal.

## Promotion criteria

### Research → shadow

1. First-cohort smoke artifact published (`exports/research/pattern-cohort-detection-<ISO>/`)
   with non-empty `results.csv` + ASCII-clean `summary.md` + valid `manifest.json`.
2. ZERO new Schwab API calls verified via `manifest.json[l2_lock_preserved] == true`
   AND `tests/research/test_pattern_cohort_evaluator_reader.py` 5 BINDING L2 LOCK
   tests green.
3. ZERO production swing/ writes beyond OQ-13 CLI carve-out (verified by
   `git diff main -- swing/ --stat` showing only `swing/cli.py`).
4. Operator-paired review of cross-tabulation against V2 OHLCV
   `vcp.tightness_range_factor=1.005` backtest output at merge `e0a9edd`.

### Shadow → production

1. Multi-cohort validation: at least 2 additional cohort smoke artifacts from
   distinct V2 OHLCV binding variables (e.g., `vcp.tightness_days_required`,
   `vcp.adr_min_pct`) with consistent detector-confirmation signal direction.
2. Operator-paired AB test: cohort-bound detector-pass verdicts vs current
   production `bucket='aplus'` detector verdicts on the SAME tickers; expected
   parity within tolerance per spec §E.1.
3. Method-record amendment to `version: 1.0.0` + status `shadow → production`
   with full validation-notes update.

### Anti-promotion guards

- Stage 3 AI second-opinion eval scope explicitly BANKED V2 (spec §B.3) — DO NOT
  promote with AI eval inferred from harness output alone.
- Bootstrap / Monte Carlo / sector-stratified analysis BANKED V2 — single-cohort
  result MUST NOT be promoted production status without bootstrap.
- V1-to-V2 cohort divergence > 5% on detector-confirmation rate blocks
  promotion pending root-cause investigation.

## Validation notes

- 5 BINDING L2 LOCK discriminating tests at
  `tests/research/test_pattern_cohort_evaluator_reader.py` (re-export identity +
  file-open boundary spy + import-graph sentinel + byte-checksum + signature
  lock) verify ZERO Schwab API surface contamination.
- Production function signatures verified at
  `tests/research/test_pattern_cohort_evaluator_detector_invoker.py::test_production_function_signatures_unchanged`
  for all 6 production callsites + `typing.get_type_hints` resolution per
  Expansion #2 sub-refinement BINDING.
- Per-skip-reason counter discipline (5 enumerated reasons) per cumulative
  gotcha #27: the harness IS the architectural answer to silent-skip
  invisibility AND models that discipline via its own per-entry skip CSV rows
  + per-reason markdown summary.

## Limitations

- **L1 — pattern_exemplars corpus drift.** The corpus is read at harness
  invocation time. If the operator's labeling effort lands new exemplars between
  cohort-input-time and harness-invocation-time, template-match Pass 2 verdicts
  shift. Cohort smoke artifacts should be re-runnable for reproducibility, but
  the corpus state is NOT immutable.
- **L2 — OHLCV archive bar-content TEMPORAL mutation.** Per cumulative gotcha
  #26: intervening pipeline runs may overwrite historical bars between
  cohort-input-time and harness-invocation-time. Detector verdicts on the
  affected entries may drift skip→watch or shift composite_score. V2.5+
  candidate: immutable-archive-snapshot V2.
- **L3 — current_stage lookup uses CURRENT operator DB state.** If
  `evaluation_runs` have been pruned between cohort-input-time and
  harness-invocation-time, `stage_observed` may shift to `'undefined'` for
  entries that were `'stage_2'` at the time the cohort was sampled.
- **L4 — Parallel-archive freshness desync** per cumulative gotcha #24. The
  harness inherits V2 OHLCV evaluator's Shape A wins LOCK + both-exist
  diagnostic surface. When legacy `{T}.parquet` is fresher than Shape A
  `{T}.yfinance.parquet`, the diagnostic counter increments and the operator
  should treat the affected tickers as drift-bearing.

## Notes

- L2 LOCK preservation REINFORCED via 5 BINDING discriminating tests + manifest
  sentinel `l2_lock_preserved: true`. Re-export via OQ-3 LOCK keeps the OHLCV
  reader's L2 LOCK invariants single-source-of-truth at V2 OHLCV evaluator's
  module + tests.
- The harness emits 24-column CSV per spec §I.2 LOCK; column count asserted at
  module load in `output.py`.
- ASCII-only output enforced via `body.encode("cp1252")` round-trip at write
  time (Windows stdout safety per cumulative gotcha).

## Changelog

- 2026-05-24 — v0.1.0 — initial record. Status `research`. Harness shipped at
  applied-research-pattern-cohort-detector-evaluator-executing-plans branch.
