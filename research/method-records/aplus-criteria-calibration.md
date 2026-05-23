<!--
Method record: A+ criteria parameter sensitivity calibration.
Phase 13 T4.SB Item 1; shipped under T-T4.SB.1.
-->

---
key: aplus-criteria-calibration
name: A+ criteria parameter sensitivity calibration
layer: ranking
status: research
baseline_or_predecessor: internal (swing.evaluation.scoring.bucket_for current cfg)
version: 0.1.0
last_updated: 2026-05-22
---

# A+ criteria parameter sensitivity calibration

## Definition

1D parameter-sweep against persisted `candidate_criteria` rows. The harness enumerates 17 variables across two semantic classes:

- **Gate variables** (`trend_template.min_passes`, `vcp.watch_max_fails`) -- substituted at each sweep point with full `bucket_for` resimulation per `swing/evaluation/scoring.py` semantics (risk hard filter + tt_passes + allowed_miss_names + vcp fail count).
- **Threshold variables** (3 trend_template numerics + 8 vcp + 1 risk + 3 rs = 15 vars) -- sweep points are enumerated but V1 returns the PERSISTED bucket per row (parity-preserving). True per-criterion bucket resimulation against the substituted threshold requires the V2 OHLCV criterion-evaluator harness (see V2 dependencies below).

The harness operates against the operator's `swing-data/swing.db` `candidate_criteria` table over the last N eval_runs (default N=20; max N=100). Output is a 9-column CSV + analyst-readable markdown analysis report. The markdown surfaces the gate-vs-threshold distinction via a `Kind` column on every row + a standalone V1 LIMITATION paragraph in the Notes section.

## Inputs

- `candidate_criteria` rows for the last N eval_runs (default N=20). Each row carries `layer` IN ('trend_template', 'vcp', 'risk') + `result` IN ('pass', 'fail', 'na') + criterion-name string.
- `candidates.bucket` (persisted IN ('aplus', 'watch', 'skip', 'error', 'excluded')) -- read-through to threshold-variable rows (parity-preserving).
- `Config` per `swing/config.py` -- TrendTemplate + VCP + Risk + RS dataclasses supply the variable-enumeration source + the production gate values.

## Parameters

- `eval_runs_window: int` -- default `20`; range `[1, 100]`.
- The 17 variables themselves are enumerated from cfg; no per-variable parameter knobs in V1 (sweep grids are first-order heuristics keyed off variable kind).

## Outputs

- **CSV**: `exports/diagnostics/aplus-sensitivity-<ISO>.csv` -- 9 columns:
  `variable_name, kind, sweep_point, aplus_count, watch_count, skip_count, excluded_count, delta_aplus, delta_watch`.
- **Markdown**: `exports/diagnostics/aplus-sensitivity-<ISO>.md` -- header (generated time + eval_runs window + total candidates) + `Sensitivity matrix` table (one row per (variable, sweep_point)) + `Notes` section including the binding V1 LIMITATION paragraph.

Gate-variable rows DO produce real `delta_aplus` / `delta_watch` values via faithful `bucket_for` resimulation. Threshold-variable rows have `delta_aplus == delta_watch == 0` by V1 design (parity-preserving).

## Operator explainability

- **One-sentence rationale:** Quantifies bucket-distribution sensitivity to per-criterion threshold adjustments so the operator + research branch can decide which dials to recalibrate.
- **One-paragraph explanation:** The harness runs a 1D parameter sweep over the 17 A+-criteria dials, substituting each one across a small grid while holding the others at production cfg. For the 2 gate variables it walks the production `bucket_for` semantics to emit a real bucket-redistribution count; for the 15 threshold variables it returns the persisted bucket (parity-preserving V1) because per-criterion bucket resimulation requires re-running the criterion evaluator harness against original OHLCV bars (V2). Output is a sensitivity matrix CSV + markdown report under `exports/diagnostics/`.
- **FAQ:** *Why are the threshold-variable deltas always zero?* Because V1 does not resimulate per-criterion buckets against substituted thresholds -- it returns the persisted bucket. Lifting this is the V2 OHLCV criterion-evaluator harness banked in this record's V2 dependencies. Gate variables (the 2 enum-style dials) are resimulated end-to-end.

## Validation notes

- **Parity invariant at current_value:** the sweep point matching a variable's `current_value` MUST reproduce the persisted bucket distribution exactly (both gate AND threshold rows). Discriminating test: `tests/research/test_aplus_sensitivity_sweep.py::test_sweep_at_current_value_matches_persisted_distribution`.
- **Threshold-variable delta invariant:** for all sweep points of any `kind ∈ {threshold_additive, threshold_multiplicative}`, the persisted bucket is returned unchanged so `delta_aplus == delta_watch == 0` is the V1 invariant. Discriminating test: `tests/research/test_aplus_sensitivity_sweep.py::test_threshold_variables_have_zero_deltas_in_sweep_result`.
- **Gate-variable bucket-redistribution:** planted divergent fixture (multiple watch candidates with `vcp_fail_count=2`) verifies that sweeping `vcp.watch_max_fails` to `0` redistributes watch candidates into skip. Discriminating test: `tests/research/test_aplus_sensitivity_sweep.py::test_sweep_gate_variable_redistributes_buckets_at_non_current_points`.
- **ASCII-only output:** all emitted text is cp1252-encodable (Windows stdout safety). Verified via `text.encode("cp1252")` in `tests/research/test_aplus_sensitivity_output.py` + `tests/cli/test_diagnose_subcommands.py`.
- **`allowed_miss_names` invariant preserved across gate substitution:** the `bucket_for` mirror in `_bucket_for_substituted` walks the same `allowed_miss_names` set membership the production gate enforces.
- Cross-coupling between variables NOT modeled (first-order; one variable at a time, others held at production cfg).

## V2 dependencies

- **OHLCV criterion-evaluator harness** consuming original bars at candidate's `data_asof_date` + substituting per-criterion thresholds + recomputing `bucket_for` end-to-end. Lifts the V1 threshold-variable limitation so the 15 threshold-rows produce real `delta_aplus` / `delta_watch` counts.
- **Structured threshold columns** on `candidate_criteria` for the 15 threshold variables (so the value substitution can happen at the SQL layer rather than re-fetching OHLCV).
- **Richer cross-variable exploration** (2D + interaction terms) -- V2 if/when operator + research-branch evidence summary calls for it.

## Notes

- Sweep is 1D only (one variable at a time; others held at production cfg). Cross-coupling is acknowledged but not modeled in V1.
- `cfg.trend_template.allowed_miss_names` (tuple-set; not a numeric grid) + `cfg.rs.benchmark_ticker` (string identifier) explicitly EXCLUDED from V1 enumeration.
- Margin-of-failure for non-numeric criteria folds to boolean-fail counts.
- Promotion from `research` to `shadow` / `production` per V2.1 §IV.D requires operator-paired evidence summary AND lift of the V1 threshold-variable limitation (i.e., bucket resimulation for the 15 threshold variables).
