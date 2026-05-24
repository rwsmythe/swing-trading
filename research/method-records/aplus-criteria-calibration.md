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
version: 0.2.0
last_updated: 2026-05-23
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
- **V2-recompute baseline parity invariant**: V2 invoked with no substitution (sweep_point == current_value for every variable) MUST produce the same bucket distribution as V1's persisted-bucket pass per spec §E.4. Discriminating test: `tests/research/test_aplus_v2_ohlcv_sweep.py::test_baseline_recompute_matches_persisted_bucket_distribution_exactly`.
- **V1<->V2 gate-variable parity**: V2's gate substitution for `trend_template.min_passes` MUST produce the same delta-counts as V1's `_bucket_for_substituted` mirror path. Discriminating test: `tests/research/test_aplus_v2_ohlcv_sweep.py::test_v2_gate_substitution_matches_v1_bucket_for_substituted_output`.
- **Per-candidate failure isolation**: V2 candidates failing OHLCV coverage / out-of-range substitution / arbitrary evaluation error MUST NOT poison other candidates' tallies. Discriminating test: 3-candidate fixture per spec §D.4.
- **L2 LOCK**: V2 module set (`ohlcv_reader.py`, `cfg_substitution.py`, `context_builder.py`, `sweep.py`, `output.py`, `run.py`) MUST NOT import `yfinance`, `schwabdev`, `swing.integrations.schwab`, or `swing.data.ohlcv_archive`. 4-module import sentinel + 4-boundary file-open mock + byte-checksum discriminating tests per `tests/research/test_aplus_v2_ohlcv_reader.py` (5 BINDING discriminating tests per spec §F.1-§F.3 + §K.4-§K.5).

## V2 dependencies

- **OHLCV criterion-evaluator harness** consuming original bars at candidate's `data_asof_date` + substituting per-criterion thresholds + recomputing `bucket_for` end-to-end. Lifts the V1 threshold-variable limitation so the 15 threshold-rows produce real `delta_aplus` / `delta_watch` counts.
- **Structured threshold columns** on `candidate_criteria` for the 15 threshold variables (so the value substitution can happen at the SQL layer rather than re-fetching OHLCV).
- **Richer cross-variable exploration** (2D + interaction terms) -- V2 if/when operator + research-branch evidence summary calls for it.

## Notes

- Sweep is 1D only (one variable at a time; others held at production cfg). Cross-coupling is acknowledged but not modeled in V1.
- `cfg.trend_template.allowed_miss_names` (tuple-set; not a numeric grid) + `cfg.rs.benchmark_ticker` (string identifier) explicitly EXCLUDED from V1 enumeration.
- Margin-of-failure for non-numeric criteria folds to boolean-fail counts.
- Promotion from `research` to `shadow` / `production` per V2.1 §IV.D requires operator-paired evidence summary AND lift of the V1 threshold-variable limitation (i.e., bucket resimulation for the 15 threshold variables).
- **V2 shipped 2026-05-23**: `vcp.watch_max_fails` special-cased per spec §E.3 to mirror V1's `_bucket_for_substituted` semantics (production `swing/evaluation/scoring.py:37` hardcoded value `2` not cfg-derived).
- **V2 BANK**: Promote `vcp.watch_max_fails` to cfg-derived in `bucket_for` as V2.5 production-code change candidate (operator-paired ratification post V2 ship).
- **V2 BANK**: `cfg.trend_template.allowed_miss_names` tuple-set sweep + `cfg.rs.benchmark_ticker` string-identifier sweep STAY V3+ (consistent with V1 method-record §"Notes" line 70 enumeration).
- **V2 NOT-scoped**: schema changes (`candidate_criteria` structured threshold columns) STAY V3+ per V1 method-record V2 dependencies #2.
- **V2 NOT-scoped**: pair-wise cross-coupling STAYS V3+ per V1 method-record V2 dependencies #3.

## V2 OHLCV harness shipped (status='research')

Shipped 2026-05-23 as first Applied Research arc post-Phase-13-FULLY-CLOSED (Path B LOCKED at `b4d7719`).

**Module location**: `research/harness/aplus_v2_ohlcv_evaluator/` (7 modules: `exceptions.py`, `ohlcv_reader.py`, `cfg_substitution.py`, `context_builder.py`, `sweep.py`, `output.py`, `run.py`).

**CLI surface**: `swing diagnose aplus-sensitivity-v2 --db PATH --eval-runs N --output-dir DIR [--variables-filter NAME,...] [--min-universe-size N] [--max-runtime-seconds N]`.

**V2 vs V1 substitution semantic differences** (per spec §A.4):

- V1 (15 threshold variables): returns persisted bucket unchanged (parity-preserving stub; `delta_aplus == delta_watch == 0` always). No per-criterion recompute.
- V2 (ALL 17 variables, threshold + gate): invokes production `evaluate_one(ctx)` end-to-end against OHLCV bars at the candidate's `data_asof_date` with the substituted cfg. True per-criterion bucket resimulation.
- V2 cfg-substitution mechanism: `dataclasses.replace` chain (`swing.config.Config` is a frozen dataclass; nested subsections replaced via typed `dataclasses.replace`). Substitution is PURELY in-memory; no production cfg mutation.
- V2 RS universe: full RS universe loaded from `cfg.paths.rs_universe_path` (same source as production pipeline). The full benchmark + peer set is required for `compute_rs` to score all candidates correctly. V1 read only `candidate_criteria` rows; V2 also fetches the live RS universe to populate `BatchContext.returns_12w_by_ticker`.
- V2 current_equity surrogate: `current_equity` injected per eval-run cohort from `account_equity_snapshots` closest-on-or-before snapshot (per OQ-15 disposition). When no snapshot exists, the operator's `cfg.risk.capital_floor_constant_dollars` floor serves as surrogate; `bucket_via_surrogate=True` is flagged in the drill-down per-candidate row.
- V2 OQ-17 carve-out: sole production `swing/` change at ship is `swing/cli.py` subcommand registration (35-60 lines mirroring V1 pattern). ZERO other production code changes; all new code under `research/`.

**V2 coverage**: All 15 threshold variables + 2 gate variables. Lifts the V1 LIMITATION per §B.1 of the spec. The 15 threshold variables now produce real `delta_aplus` / `delta_watch` counts via live `evaluate_one` recompute.

**V1 simplifications shipped in V2** (per cumulative V1-simplification-banking discipline):

| Simplification | Module | V2 dependency |
|---|---|---|
| `old_criterion_failure="(none)"` always emitted; real per-criterion attribution not threaded | `sweep.py:FlippedCandidate` | V2.5: thread `evaluate_one` result through `_record_flip`; requires per-criterion value access from `CriteriaResult` |
| `_precompute_ohlcv_coverage_skips` catches `OhlcvCoverageError + FileNotFoundError + OSError` (widened beyond spec `OhlcvCoverageError`); test only exercises `OhlcvCoverageError` branch | `sweep.py` | V2.5 discriminating test for FileNotFoundError + OSError branches (defense-in-depth coverage) |
| `tracemalloc` stopped in `run.py` finally block; peak captured on sweep success only (sweep exception path gets `peak=0`) | `run.py:db6b45f` fix | V2.5: always call `tracemalloc.get_traced_memory()` before stop for accurate failure-path peak reporting |

## Promotion criteria (research -> shadow -> production)

Per OQ-8 RECOMMEND + V2.1 §IV.D + §VII.C lifecycle posture:

**research -> shadow**:

1. V2 OHLCV harness shipped + baseline parity invariant green per spec §E.4 (SATISFIED at V2 ship 2026-05-23).
2. At least 1 V2 study writeup published (SATISFIED: `research/studies/2026-05-23-v2-ohlcv-criterion-evaluator.md`).
3. AT LEAST ONE binding threshold variable identified OR all 15 declared non-binding with operator-paired sign-off (PENDING: operator must run V2 against `~/swing-data/swing.db` and review findings).

**shadow -> production**:

1. At least 1 cfg-policy proposal evaluated against at least 2 disjoint validation universes.
2. Proposal's A+ delta statistically distinguishable from baseline (default threshold proposed: at least 5 A+ delta on a 5681-candidate universe -- doubling A+ count).
3. Operator-paired ratification.

**Anti-promotion guards**: regression on existing A+ candidates; cross-coupling instability (V1 is 1D; V2 inherits); production-cfg drift between study run and ratification.

## Promotion ladder (research -> shadow -> production) per OQ-8

The 3-tier promotion ladder follows V2.1 §IV.D (research) -> §VII.C (shadow) -> production per the governing strategy. The V2 ship satisfies the research tier entry criteria above. Shadow promotion is gated on operator-witnessed binding-variable identification; production promotion additionally requires multi-universe validation + operator-paired ratification. This is the canonical example for future Applied Research Tranche 1 arcs per V2.1 §X tranche progression.
