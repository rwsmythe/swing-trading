# Method Record: Shadow-Expectancy Engine

Per V2.1 section IV.B minimum field list. ASCII-only.

## Question

Per-hypothesis mechanical expectancy (mean R-multiple) of every emitted temporal-log signal,
forward-walked through one fixed management ruleset, accumulated at signal-pace.

## Data substrate

The frozen v22 temporal log: `pattern_detection_events` (locked detection +
`structural_anchors_json` pivot) and `pattern_forward_observations` (one frozen daily OHLC
bar per session, `ohlc_today_json`, never re-fetched), joined to per-run `candidates` rows
via `pipeline_runs.evaluation_run_id`. Read-only (`mode=ro` URI); no production write path;
no schema change (v24). Source filter: `source='pipeline'` (A+ isolation).

## Ruleset (fixed; the single mechanical management path)

- Entry: first `triggered_open` + `entry_fired` observation; entry fill = `max(pivot, entry_bar.open)`.
- Initial stop (MECHANICAL): `entry_bar.low`; risk_per_share = entry_fill - entry_bar.low;
  degenerate (entry_fill <= entry_bar.low) signals are excluded per-hypothesis.
- Day-3 partial: sell 50% of the nominal 100-share unit if the session-3 close is above the
  entry fill.
- Breakeven: once running R >= +1.0 (mirrors `StopAdvisoryConfig.breakeven_r_trigger`), raise
  the stop to the entry fill.
- Maturity-staged MA trail: close-below the 20-MA (or 10-MA once running R >= +2R, mirroring
  `advisory._MATURITY_STAGE_TRAIL_MA`), computed from frozen forward closes only.
- Horizon: 126 sessions (~6 months), bounded by available bars.
- EOD precedence per bar: intrabar price-level stop test first, then MA-trail close-below,
  then Day-N partial, then breakeven raise for the next session.

## Hypothesis registry version

The four v0.1 hypotheses seeded by migration 0008 (`status='active'`): A+ baseline, Near-A+
defensible extension, Sub-A+ VCP-not-formed, Capital-blocked smaller-position. Attribution
reuses the production `swing.recommendations.hypothesis.match_candidate_to_hypotheses`
matcher (no re-seeding). A signal matching zero or more-than-one hypothesis is recorded in
the `unattributed` funnel bucket, never simulated under a hypothesis.

## Four censoring scenarios (open-at-horizon)

closed_only (open remainder dropped), mtm_at_horizon (mark to last frozen close),
forced_exit_at_horizon_open (next post-horizon open; collapses to MTM + annotated when no
post-horizon bar exists), stop_level_adverse (mark the open remainder at the current stop).
Each per-hypothesis scenario mean is taken over ALL triggered trades; a closed trade
contributes its realized R in all four, an open trade is excluded only from closed_only.

## Realistic vs favorable bracket

realistic: price-stop fills at min(stop, bar_open) (gap-down realizes the >1R loss);
MA-trail fills at the next-session open. favorable_reprice: price-stop fills at the stop
exactly; MA-trail fills at max(signal_close, next_open). favorable_reprice is a
NON-EXECUTABLE upper bound. Multi-leg R uses ONE fixed denominator
(risk_per_share * initial_shares), never per-leg.

## Reuse leaves (no forbidden imports)

`swing.trades.derived_metrics` (R math), `swing.metrics.honesty.wilson_ci` (Wilson CI),
`swing.recommendations.hypothesis` (attribution), `swing.data.repos.*` + `swing.data.models`
(read-only), `swing.config.StopAdvisoryConfig` + `swing.trades.advisory` constants
(anti-drift bindings). The harness imports NONE of: yfinance, schwabdev,
swing.integrations.schwab, swing.data.ohlcv_archive (enforced by the L2-lock test).

## Reproducibility scope

Deterministic: identical canonical manifest (funnel + scorecard, timestamps stripped) across
re-runs over the same DB. Honesty floors suppress profit-factor / expectancy below n=5.
Output: `exports/research/shadow-expectancy-<ISO>/` (summary.md + manifest.json +
results.csv + per_session.csv), all ASCII.

## Locks

L2-light: the only `swing/` change is the `swing diagnose shadow-expectancy` CLI
registration. Everything else lives under `research/harness/shadow_expectancy/`,
`tests/research/shadow_expectancy/`, `research/studies/`, `research/method-records/`, and
`.gitignore`.
