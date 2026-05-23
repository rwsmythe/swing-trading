# Study: A+ Criterion Sensitivity Sweep

**Method record:** `../method-records/aplus-criteria-calibration.md`
**Status:** designed; not yet run against operator DB.
**Target duration:** one evening's work for operator to invoke + capture; one for analysis.

## Question

What is the bucket-distribution sensitivity of `swing.evaluation.scoring.bucket_for` to per-criterion threshold adjustments? Specifically, for the 17 dials enumerated in `research/harness/aplus_sensitivity/variables.py`, how do `aplus` / `watch` / `skip` counts shift across each dial's V1 sweep grid?

Context: 63 evaluation runs since the v20 detector chain landed have produced zero A+ candidates. The open question is whether (a) the gates are too tight (this study answers for the 2 gate dials); AND/OR (b) the 15 threshold dials would benefit from recalibration (this study enumerates the dials but V1 cannot answer the threshold question; lifted by the V2 OHLCV criterion-evaluator harness banked in the method record).

## Null hypothesis

Bucket distribution is invariant to any single-dial sensitivity adjustment within the V1 sweep grids -- i.e., no dial materially shifts `aplus_count` / `watch_count`.

For the 2 gate dials, the harness can reject this null directly via bucket-level resimulation. For the 15 threshold dials, V1 cannot answer (parity-preserving stub); V2 dependency.

## Baseline

Current production cfg values for each of the 17 dials (per tracked `swing.config.toml`):

- `trend_template.min_passes = 7`
- `vcp.watch_max_fails = 2` (hardcoded in `swing/evaluation/scoring.py:35`)
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

## Method

Per `../method-records/aplus-criteria-calibration.md`. Implementation under `research/harness/aplus_sensitivity/`. Invoked via:

```bash
swing diagnose aplus-sensitivity --db "$USERPROFILE/swing-data/swing.db" --eval-runs 20
```

Output written to `exports/diagnostics/aplus-sensitivity-<ISO>.{csv,md}`.

## Data

- Operator's `swing-data/swing.db` `candidate_criteria` rows over the last 20--63 eval_runs (operator picks the window via `--eval-runs`). Default 20; max 100.
- No external data sources; pure read against persisted state.

## Findings

**TO BE POPULATED post-T4.SB-SHIPPED** when the operator runs the harness against their DB. Expected output structure (per the method record's `Outputs` section):

- 17 variables x ~5 sweep points each = ~85 SweepEntry rows in the matrix.
- Gate-variable rows (2 of 17) carry real `delta_aplus` / `delta_watch` values.
- Threshold-variable rows (15 of 17) carry `delta_aplus == delta_watch == 0` by V1 design.

Brainstorming spec acknowledges Item 1 diagnostic OUTPUT feeds research-branch first-method-record selection (per `research/phase-0-tasks.md` "Next" entry). T-T4.SB.1 ships the instrument + this stub; operator post-merge runs + populates findings.

## Next steps

- Operator runs the harness against `swing-data/swing.db` post-T4.SB-SHIPPED. Captures CSV + markdown.
- Threshold-loosening cfg-policy proposals BANKED V2 pending operator review of the gate-variable findings.
- Per `research/phase-0-tasks.md` "Next" entry: pick 1--3 A+-like indicators to advance to method-record + study based on this sensitivity outcome.

## Limitations (V1)

- 1D sweep only; cross-coupling NOT modeled.
- Threshold dials (15 of 17) report parity-preserving deltas (always 0) because per-criterion bucket resimulation against substituted thresholds requires the V2 OHLCV criterion-evaluator harness.
- Margin-of-failure semantics for non-numeric criteria fold to boolean-fail counts.
