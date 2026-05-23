# A+ criteria parameter-sweep sensitivity harness

1D sensitivity harness for `research/studies/aplus-criterion-sensitivity-2026-05-22.md`.
Operationalizes the OQ-1.3 + OQ-1.4 amendment (§1.5.1 + §1.5.4) -- places the
diagnostic instrument under `research/` per V2.1 §V branch posture rather than
production `swing/`.

## Run

Against operator DB (default window N=20 eval_runs):

```bash
swing diagnose aplus-sensitivity --db "$USERPROFILE/swing-data/swing.db" --eval-runs 20
```

Standalone invocation (bypassing `swing` CLI):

```bash
python -m research.harness.aplus_sensitivity.run \
    --db "$USERPROFILE/swing-data/swing.db" \
    --eval-runs 20 \
    --output-dir exports/diagnostics/
```

## Modules

- `variables.py` -- variable enumeration from `cfg.trend_template` / `cfg.vcp` / `cfg.risk` / `cfg.rs`.
- `sweep.py` -- 1D sweep machinery; consumes persisted `candidate_criteria`.
- `output.py` -- sensitivity matrix CSV (9 cols) + markdown analysis.
- `run.py` -- CLI orchestration.

## Outputs

- `exports/diagnostics/aplus-sensitivity-<ISO>.csv` -- 9-column matrix.
- `exports/diagnostics/aplus-sensitivity-<ISO>.md` -- analyst-readable report.

## Variable inventory (17 dials)

- 2 **gate** variables -- `trend_template.min_passes`, `vcp.watch_max_fails`.
  Bucket-level resimulation via faithful `bucket_for` mirror.
- 3 trend_template **threshold** variables -- `rising_ma_period_days`,
  `high_52w_margin_pct`, `low_52w_min_pct`.
- 8 vcp **threshold** variables -- `prior_trend_min_pct`, `adr_min_pct`,
  `pullback_max_pct`, `proximity_max_pct`, `tightness_days_required`,
  `tightness_range_factor`, `orderliness_max_bar_ratio`,
  `orderliness_max_range_cv`.
- 1 risk **threshold** variable -- `max_risk_pct`.
- 3 rs **threshold** variables -- `horizon_weeks`, `rs_rank_min_pass`,
  `fallback_extreme_pct`.

V1 limitation: **threshold** variables sweep their numeric grids but emit
`delta_aplus == delta_watch == 0` because per-criterion bucket resimulation
against the substituted threshold requires the V2 OHLCV criterion-evaluator
harness. Banked in `research/method-records/aplus-criteria-calibration.md`
V2 dependencies. **Gate** variables DO produce real bucket-redistribution
counts.

## Limits

- 1D sweep only; cross-coupling between variables is acknowledged and NOT modeled.
- Margin-of-failure for non-numeric criteria folds to boolean-fail counts.
- V2 candidates banked: structured threshold columns; richer cross-variable
  exploration; OHLCV-aware re-evaluation against original bars.
