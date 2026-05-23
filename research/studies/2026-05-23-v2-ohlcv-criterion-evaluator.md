# Study: V2 OHLCV Criterion-Evaluator Sensitivity Sweep

**Method record:** `../method-records/aplus-criteria-calibration.md`
**Status:** harness shipped; implementer smoke run captured at
`exports/diagnostics/aplus-sensitivity-v2-20260523T230131Z.{csv,md}`
(5 eval_runs, partial -- 120s cap, 2/17 variables completed). Full
63-eval-run operator run pending (see phase-0-tasks.md "Next").
**Date:** 2026-05-23
**Author:** Applied Research arc (Path B LOCKED at `b4d7719`; first arc post-Phase-13-FULLY-CLOSED).

## Question

For each of the 17 A+ criterion dials, at which sweep point (if any) does the
bucket distribution shift materially -- i.e., does loosening or tightening a
threshold cause a candidate to flip from `skip` to `watch` or `watch` to
`aplus`? Which of the 15 threshold variables are **binding** (produce a real
bucket flip) vs **inert** (no candidate crosses the threshold boundary across
the V1 5-point sweep grid)?

Context: 63 evaluation runs since the v20 detector chain landed have produced
zero A+ candidates. This study uses the V2 OHLCV criterion-evaluator harness
to answer the threshold-dial question that V1 could not answer (V1 returned
parity-preserving zero deltas for all 15 threshold variables).

## Null hypothesis

Bucket distribution is invariant to any single-dial sensitivity adjustment
within the V1 5-point sweep grids -- i.e., no threshold dial materially shifts
`aplus_count` or `watch_count`.

For the 2 gate dials (`trend_template.min_passes` + `vcp.watch_max_fails`),
V1 already answered the gate-variable question (see V1 study at
`research/studies/aplus-criterion-sensitivity-2026-05-22.md`). This study
extends the answer to the 15 threshold dials via live `evaluate_one` recompute
against OHLCV bars.

## Baseline

Production cfg values at V2 ship date (2026-05-23) per tracked
`swing.config.toml`:

- `trend_template.min_passes = 7`
- `vcp.watch_max_fails = 2` (hardcoded in `swing/evaluation/scoring.py:37`)
- `trend_template.rising_ma_period_days = 21`
- `trend_template.high_52w_margin_pct = 25.0`
- `trend_template.low_52w_min_pct = 30.0`
- `vcp.prior_trend_min_pct = 25.0`
- `vcp.adr_min_pct = 4.0`
- `vcp.pullback_max_pct = 25.0`
- `vcp.proximity_max_pct = 5.0`
- `vcp.tightness_days_required = 2`
- `vcp.tightness_range_factor = 0.67`
- `vcp.orderliness_max_bar_ratio = 3.0`
- `vcp.orderliness_max_range_cv = 0.60`
- `risk.max_risk_pct = 0.005`
- `rs.horizon_weeks = 12`
- `rs.rs_rank_min_pass = 70`
- `rs.fallback_extreme_pct = 20.0`

## Methodology

**Harness**: `research/harness/aplus_v2_ohlcv_evaluator/` (V2 OHLCV
criterion-evaluator). Invoked via:

```
swing diagnose aplus-sensitivity-v2 \
    --db "$USERPROFILE/swing-data/swing.db" \
    --eval-runs 63 \
    --output-dir exports/diagnostics/
```

**Universe**: Full RS universe from `cfg.paths.rs_universe_path` (same source
as production pipeline). Required for `compute_rs` to score all candidates
correctly against their full benchmark + peer set.

**Sweep grid**: Inherited from V1 5-point grid per OQ-3 (no full-range sweep).
One variable at a time; all others held at production cfg.

**Cfg-substitution mechanism**: `dataclasses.replace` chain against frozen
`swing.config.Config`. In-memory only; no production cfg mutation.

**Production `evaluate_one` end-to-end**: Each candidate is re-evaluated from
OHLCV bars at its `data_asof_date` via the production
`swing.evaluation.evaluator.evaluate_one(ctx)` path. The full criterion chain
fires (8 trend_template criteria + 9 VCP criteria + 1 risk criterion +
RS scoring) under the substituted cfg.

**V1-parity baseline**: At sweep_point == current_value for every variable,
V2 MUST reproduce the persisted bucket distribution exactly (tier-1 EXACT
match; tier-2 conditional with surrogate-flag). This invariant is verified at
runtime and surfaced as `## CRITERION DRIFT DETECTED` alert if violated.

**current_equity surrogate (per OQ-15)**: `current_equity` injected from
`account_equity_snapshots` closest-on-or-before snapshot for each eval-run
cohort. When no snapshot exists (no equity history for the eval-run's
`data_asof_date`), the operator's `cfg.risk.capital_floor_constant_dollars`
floor serves as surrogate. `bucket_via_surrogate=True` flagged per-candidate
in the drill-down output.

**eval_runs window**: 63 (all evaluation runs since v20 detector chain landed;
5681 candidates per S3 universe per OQ-6).

**Shape A parquet**: V2 reads from `cfg.paths.prices_cache_dir` (the operator's
`~/swing-data/prices-cache/` directory). L2 LOCK preserved: no yfinance,
schwabdev, schwab integration, or ohlcv_archive imports in the V2 module set.

## Baseline parity verification

**Tier-1 EXACT match (BINDING)**: V2 at sweep_point == current_value for all
17 variables MUST produce the same bucket distribution as V1's persisted
bucket for the SAME candidates. The tier-1 exact match is a blocking invariant:
if it fails, V2 is surfacing a criterion-drift regression (the production
`evaluate_one` path produces different results from what was persisted at
pipeline time -- likely a cfg or code change between the pipeline run and the
V2 harness invocation).

**Tier-2 CONDITIONAL (surrogate-flagged)**: Tier-2 candidates are those where
the `current_equity` surrogate was used (no historical equity snapshot for the
eval-run's date). Tier-2 mismatches are reported as non-blocking audit items
(`tier2_mismatch_count`) and do not trigger the CRITERION DRIFT alert.

**OQ-18 both-exist caveat**: When both a Shape A (`.yfinance.parquet`) and a
legacy (`.schwab_api.parquet` or other source) parquet exist for a ticker, V2
reads Shape A (wins per V2 design). The `both_exist_shape_a_wins_count` in the
manifest enumerates affected tickers. When non-zero, the operator should
verify the Shape A archive is the authoritative source for those tickers.

**Implementer smoke run findings (partial; 5 eval_runs, 120s cap):**

- Tier-1 match: FAIL (CRITERION DRIFT DETECTED at DK:62 -- 3 occurrences
  across sweep points. DK was persisted as `aplus` or `watch` but V2
  evaluate_one recomputed a different bucket. Operator action required:
  verify whether DK's classification at eval_run 62 reflects a real
  production criteria-drift or a known cfg/code divergence at that date.)
- Tier-2 match count: 30 / Tier-2 mismatch count: 45 (non-blocking)
- Tier-2 via surrogate count: 0 (all eval-runs had equity snapshots)
- Both-exist: 16 occurrences (AESI + PL + DK -- accumulated across 5
  eval_runs and 2 variables sweep. Operator should clean up stale
  legacy parquet files for AESI, PL, DK from prices-cache directory.)
- OHLCV coverage skips (global): 5 (FPS, PURR missing sufficient history)
- Universe size: 516 tickers

Full 63-eval-run findings pending operator manual re-run
(see `exports/diagnostics/aplus-sensitivity-v2-<ISO>.md` after operator run).

## Per-variable findings

**TO BE POPULATED** when the operator runs the V2 harness against
`~/swing-data/swing.db` and captures the output files under
`exports/diagnostics/aplus-sensitivity-v2-<ISO>.{csv,md}`.

Expected output structure:
- 17 variables x 5 sweep points each = 85 SweepEntryV2 rows in the matrix.
- Gate-variable rows (2 of 17: `trend_template.min_passes` + `vcp.watch_max_fails`):
  real `delta_aplus` / `delta_watch` values via live `evaluate_one` recompute.
- Threshold-variable rows (15 of 17): real `delta_aplus` / `delta_watch` values
  (V2 lifts the V1 zero-delta stub).

Findings table (fill in post-run):

| Variable | Kind | Binding? | Sweep point of first flip | Delta aplus at flip | Notes |
|----------|------|----------|--------------------------|---------------------|-------|
| trend_template.min_passes | gate | TBD | TBD | TBD | V1 answer already in V1 study |
| vcp.watch_max_fails | gate | TBD | TBD | TBD | V1 answer already in V1 study |
| trend_template.rising_ma_period_days | threshold_additive | TBD | TBD | TBD | |
| trend_template.high_52w_margin_pct | threshold_additive | TBD | TBD | TBD | |
| trend_template.low_52w_min_pct | threshold_additive | TBD | TBD | TBD | |
| vcp.prior_trend_min_pct | threshold_additive | TBD | TBD | TBD | |
| vcp.adr_min_pct | threshold_additive | TBD | TBD | TBD | |
| vcp.pullback_max_pct | threshold_additive | TBD | TBD | TBD | |
| vcp.proximity_max_pct | threshold_additive | TBD | TBD | TBD | |
| vcp.tightness_days_required | threshold_additive | TBD | TBD | TBD | |
| vcp.tightness_range_factor | threshold_multiplicative | TBD | TBD | TBD | |
| vcp.orderliness_max_bar_ratio | threshold_multiplicative | TBD | TBD | TBD | |
| vcp.orderliness_max_range_cv | threshold_multiplicative | TBD | TBD | TBD | |
| risk.max_risk_pct | threshold_multiplicative | TBD | TBD | TBD | |
| rs.horizon_weeks | threshold_additive | TBD | TBD | TBD | |
| rs.rs_rank_min_pass | threshold_additive | TBD | TBD | TBD | |
| rs.fallback_extreme_pct | threshold_multiplicative | TBD | TBD | TBD | |

## Conclusion

*To be populated post operator DB run.*

Expected conclusion forms:
- **Binding variables identified**: list which threshold variables cause
  bucket flips; rank by marginal A+ per loosening unit; propose cfg-policy
  candidates for shadow promotion.
- **All 15 declared non-binding**: if no threshold variable causes a bucket
  flip across the V1 5-point grids, the conclusion is that the current
  candidate universe has no candidates near the threshold boundaries. This
  would suggest the issue is not threshold calibration but candidate-universe
  composition (see V2.1 §III scope).
- **Gate variables**: V1 already answered; confirm V2 parity at gate-variable
  sweep points.

## Limitations

**OQ-14 -- current-universe RS snapshot caveat**: The RS universe loaded by V2
is the CURRENT universe (from `cfg.paths.rs_universe_path` at invocation time).
The universe at each historical eval-run's `data_asof_date` may have differed
(constituent changes, new tickers added, delistings). This is the same
fixed-universe concession acknowledged in V1; it is minimum-viable per V2.1
§V.E bootstrap-first. Consequence: RS rank scores for historical candidates
may differ from what was originally computed if the universe composition has
changed materially since the eval-run date. The survivorship bias this
introduces is common-mode across variables (all threshold variables use the
same universe snapshot), so cross-variable comparisons are direction-trustworthy
but absolute RS rank values carry the fixed-universe caveat.

**OQ-15 -- current_equity surrogate fallback caveat**: `current_equity` injected
per eval-run cohort from `account_equity_snapshots` closest-on-or-before
snapshot. When no snapshot exists for an eval-run's date range, the
`cfg.risk.capital_floor_constant_dollars` floor is used as surrogate. This
floor may not match the operator's actual equity at the historical eval-run
date. `bucket_via_surrogate=True` is flagged per-candidate in the drill-down.
Tier-2 (surrogate-flagged) mismatches at baseline are non-blocking but
enumerated in the manifest. Operator should verify the `tier2_via_surrogate_count`
at baseline and confirm equity floor is a reasonable proxy for the affected
eval-runs.

**OQ-18 -- legacy/Shape A both-exist policy caveat**: When both a Shape A
(`.yfinance.parquet`) and a legacy-source parquet exist for a ticker, V2 reads
Shape A per V2 design. The `both_exist_shape_a_wins_count` in the manifest
enumerates affected tickers (capped at 50 in the affected_tickers list). For
those tickers, the OHLCV bars used by V2 may differ from what the production
pipeline used at the original eval-run date (if the pipeline used the legacy
source). The `## BOTH-EXIST WARNING` banner in the markdown output enumerates
the count and the first 50 affected tickers.

**1D sweep only**: Cross-coupling between variables is NOT modeled. A candidate
that needs BOTH `rs.rs_rank_min_pass` loosened AND `vcp.adr_min_pct` loosened
to become `aplus` will not be surfaced by either variable's sweep in isolation.
V3+ candidate: 2D + interaction terms per V2.1 §IV.B parsimony relaxation.

## V1 simplifications enumerated (per V1-simplification-banking discipline)

These V1 simplifications ship in the V2 harness and are tracked for V2.5+
resolution:

1. **`old_criterion_failure="(none)"` always emitted**: The per-flipped-candidate
   provenance field `old_criterion_failure` is always `"(none)"` in V2. Computing
   the real attribution requires threading the `evaluate_one` criterion-level
   result through `_record_flip` -- V2.5 candidate.
2. **`_precompute_ohlcv_coverage_skips` widened-except**: The coverage-skip
   precompute catches `OhlcvCoverageError + FileNotFoundError + OSError` (wider
   than spec's `OhlcvCoverageError`). Test exercises only `OhlcvCoverageError`
   branch. Defense-in-depth is correct behavior; discriminating tests for
   `FileNotFoundError` + `OSError` branches are V2.5.
3. **tracemalloc peak on exception path**: `run.py` captures `peak=0` when the
   sweep raises an exception before `tracemalloc.get_traced_memory()`. The
   `tracemalloc.stop()` fires in the `finally` block; peak would be available
   there. Accurate failure-path peak reporting is V2.5.

## Forward-binding (V2.5 / V3+ recommendations)

Per spec §M.4 + brainstorming return report §4:

- **Promote `vcp.watch_max_fails` to cfg-derived** (V2.5): `swing/evaluation/scoring.py:37`
  has hardcoded `2`; making it cfg-derived enables the sweep to explore values
  without the special-case branch in `sweep.py`. Operator-paired ratification
  required before production-cfg promotion.
- **`old_criterion_failure` per-criterion attribution** (V2.5): Thread
  `evaluate_one` result through `_record_flip` for real attribution strings.
- **Parquet bulk-read via pyarrow** (V2.5): If V2 runtime exceeds 60 min on
  operator hardware (OQ-9 acceptance target), switch from per-ticker `pd.read_parquet`
  to `pyarrow.parquet.read_table` bulk-read for throughput.
- **concurrent.futures parallelism** (V2.5): Per-candidate `evaluate_one`
  calls are embarrassingly parallel across eval-run cohorts. Parallelism capped
  by yfinance quota is not a concern for V2 (L2 LOCK: no yfinance calls).
- **`cfg.trend_template.allowed_miss_names` sweep** (V3+): Tuple-set; not a
  numeric grid. Requires combinatorial enumeration logic (V3+).
- **`cfg.rs.benchmark_ticker` sweep** (V3+): String identifier; requires
  universe-reload per substitution (V3+).
- **2D cross-coupling sweep** (V3+): Interaction terms between threshold
  variables (V3+).

## Amendments

*(None at V2 ship. To be appended post operator review of findings.)*
