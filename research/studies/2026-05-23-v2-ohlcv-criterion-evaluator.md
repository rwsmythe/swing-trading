# Study: V2 OHLCV Criterion-Evaluator Sensitivity Sweep

**Method record:** `../method-records/aplus-criteria-calibration.md` (v0.3.0; SHADOW status since 2026-05-24 PM)
**Status:** harness shipped; **operator full 63-eval-run reproduction SHIPPED 2026-05-24 PM** at `exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.{csv,md}` (86 min runtime / not truncated / 63 eval_runs / 5666 candidates / 516 universe). **5 binding variables identified** (all VCP-family). Method-record SHADOW promoted per operator decision D1. **3 architectural limitations** documented (L4 parallel-archive freshness desync; L5 sentinel-bucket parity-comparison discipline; L6 archive bar-content TEMPORAL mutation); V2 evaluator correctness verified 3x via decisive counter-tests across DK:62 + DHC/UCO/VSAT + full-reproduction investigations.
**Date:** 2026-05-23 (initial); 2026-05-24 PM (amended post-full-reproduction)
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

**CRITERION DRIFT alert semantics**: When tier-1 mismatch is detected, V2
emits a `## CRITERION DRIFT DETECTED` alert section in the markdown output
and sets `baseline_parity.tier1_match = False` in the manifest. This is a
REPORTED ALERT, NOT an exit-code blocker: the harness completes the full sweep
and returns all partial results with the alert prominently surfaced. Operator
action is required (see "Implementer smoke run findings" below for a real
example: DK:62 drift). The CLI exits with code 0 regardless of drift status
so the operator can inspect the full output before deciding whether the drift
is a known cfg/code divergence or a real regression requiring investigation.

**Tier-2 CONDITIONAL (surrogate-flagged)**: Tier-2 candidates are those where
the `current_equity` surrogate was used (no historical equity snapshot for the
eval-run's date). Tier-2 mismatches are reported as non-blocking audit items
(`tier2_mismatch_count`) and do not trigger the CRITERION DRIFT alert.

**OQ-18 both-exist caveat**: When both a Shape A (`.yfinance.parquet`) and a
legacy (`.schwab_api.parquet` or other source) parquet exist for a ticker, V2
reads Shape A (wins per V2 design). The `both_exist_shape_a_wins_count` in the
manifest enumerates affected tickers. When non-zero, the operator should
verify the Shape A archive is the authoritative source for those tickers.

**Operator full 63-eval-run reproduction findings (AUTHORITATIVE; supersedes prior partial-smoke artifacts):**

Smoke artifact: `exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.{csv,md}`.

- Runtime: 5172.96s (~86 minutes; under 90-min `--max-runtime-seconds 5400` cap; **not truncated**).
- Eval-runs window: 63 (ids 2..64; full S3 universe range since v20 detector chain landed).
- Total candidates evaluated: 5666.
- V2 universe size: 516 tickers (current S&P 500 snapshot per OQ-14 LOCK).
- OHLCV coverage skips (global): 88.
- Tier-2 match count: **120 / Tier-2 mismatch count: 0** (clean; tier-2 baseline parity fully consistent).
- Tier-2 via surrogate count: 0.
- Tier-1 match: **FAIL — 14 CRITERION DRIFT entries** (CNTA × 2 + ECVT + APLS × 3 + FTI × 2 + STNG × 3 + PL × 3; spanning eval_runs 6-43; NOT clustered at recent boundary). **Root-caused at investigation merge `c8f9612` (2026-05-24 PM)**: NEW H6 = OHLCV archive bar-content TEMPORAL mutation between V1's persistence time + V2's current-archive read time. V2 evaluator CORRECT given inputs; drift is data-input divergence at the ~0.5%-3% volume/range bar-mutation level. Investigation findings doc at `docs/v2-full-reproduction-drift-investigation-2026-05-24.md`. Characterized as **Limitation L6** in method-record v0.3.0 §"Known limitations of V2 baseline-parity claims".
- Both-exist banner: 3 tickers (AESI, DK, PL) — unchanged from prior smokes; orthogonal to this study's binding-variable findings.

**Critical caveat — V1↔V2 baseline parity at the criterion level**: V1's `candidate_criteria` rows are a frozen snapshot of OHLCV archive contents at original eval_run persistence time; V2 reads the CURRENT archive. Three architectural limitations characterize the V1↔V2 parity gap, each independently verified non-blocking for the sensitivity-analysis goal:

- **L4** (parallel-archive freshness desync): cross-archive asymmetry between Shape A and legacy paths; remediated for the recent boundary via D.1 Shape A refresh 2026-05-24. CLAUDE.md gotcha #24.
- **L5** (sentinel-bucket parity-comparison discipline): V1 short-circuit excluded/error buckets V2's `bucket_for` cannot reproduce; remediated via Option A filter at merge `b7f70ff` 2026-05-24. CLAUDE.md gotcha #25.
- **L6** (archive bar-content TEMPORAL mutation): intervening pipeline runs overwrite historical bars when yfinance returns slightly different values; remediation = characterize as method-record limitation (this writeup includes caveat language; ZERO V1 code changes). CLAUDE.md gotcha #26. Banked V2.5/V3 candidate: immutable archive snapshot before V2 run.

All 3 limitations independently verified non-blocking via decisive counter-tests confirming V2 evaluator correctness given inputs.

## Per-variable findings

**Source:** operator's full 63-eval-run reproduction at `exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.csv` (authoritative; supersedes prior partial-smoke entries). 17 variables × 5 sweep points = 85 SweepEntryV2 rows in the matrix; 5666 candidates / 516 universe.

**Caveat per L4 + L5 + L6**: the 14 tier-1 baseline-parity drift entries (0.25% of candidates) trace to OHLCV archive bar-content TEMPORAL mutation (L6); V2 evaluator is CORRECT given inputs (verified 3x via decisive counter-tests). The 14 candidates flip V1=watch / V2=skip — they contribute to `delta_watch` but NOT `delta_aplus`. The headline `max_delta_aplus` column below is therefore UNAFFECTED by the drift class. Binding-variable identification is V2-internal arithmetic and is robust under the architectural limitations.

Findings table (full 63-eval-run reproduction):

| Variable | Kind | Binding? | Sweep point of first flip | Delta aplus at flip | Delta watch at flip | Notes |
|----------|------|----------|--------------------------|---------------------|---------------------|-------|
| `vcp.tightness_range_factor` | threshold_multiplicative | **YES (aplus + watch)** | 1.005 (loosen from baseline 0.67) | **+75** | **+527** | **TOP BINDING VARIABLE.** 5 → 80 aplus when loosened to 1.005; 34 aplus at intermediate 0.8375. Tightening to 0.335 / 0.5025 drops aplus to 0 (-5). Strongly bidirectional. |
| `vcp.tightness_days_required` | threshold_additive | **YES (aplus + watch)** | 1 (loosen from baseline 2) | **+16** | **+246** | 5 → 21 aplus when loosened to 1 day; tightening to 3-4 drops aplus to 3. Sweep_point 0 catastrophic (out_of_range_skip 5578). |
| `vcp.adr_min_pct` | threshold_multiplicative | **YES (aplus + watch)** | 2.0 (loosen from baseline 4.0) | **+11** | **+569** | 5 → 16 aplus when loosened to 2.0; 12 aplus at 3.0. Tightening to 5.0 / 6.0 drops aplus to 3 (-2). |
| `vcp.proximity_max_pct` | threshold_multiplicative | **YES (aplus + watch)** | 7.5 (loosen from baseline 5.0) | **+5** | **+234** | 5 → 10 aplus when loosened to 7.5; 9 aplus at 6.25. Tightening to 2.5 / 3.75 drops aplus to 0 (-5). |
| `vcp.orderliness_max_bar_ratio` | threshold_multiplicative | **YES (aplus + watch)** | 3.75 / 4.5 (loosen from baseline 3.0) | **+1** | **+98 to +113** | 5 → 6 aplus when loosened; marginal effect. Tightening to 1.5 catastrophic (343 watch / 5235 skip). |
| `trend_template.min_passes` | gate | YES (watch only) | 8 (tighten from baseline 7) | 0 | -91 | Loosening 5-7 has no effect (cumulative gate); tightening to 8 drops 91 watch; to 9 catastrophic cascade (-5 aplus / -1321 watch / +5578 out-of-range). Zero aplus impact when loosening from current. |
| `vcp.watch_max_fails` | gate | YES (watch only) | 3 (loosen from baseline 2) | 0 | +1749 | Loosening to 3 adds 1749 watch; to 4 adds 2867. Tightening to 0 drops all 1321 watch. Zero aplus impact (aplus requires vcp_fails=0; sweep doesn't reach). |
| `trend_template.rising_ma_period_days` | threshold_additive | NOT BINDING | (none) | 0 | 0 (max -1 at 30-31) | 5 aplus / 1321 watch invariant across full 11-31 sweep grid except marginal -1 watch at edges. |
| `trend_template.high_52w_margin_pct` | threshold_multiplicative | NOT BINDING | (none) | 0 | 0 (max -10 at 12.5) | Invariant from 18.75-37.5; marginal -10 watch when tightened to 12.5. |
| `trend_template.low_52w_min_pct` | threshold_multiplicative | NOT BINDING | (none) | 0 | 0 | Invariant across 15.0-45.0 sweep grid. |
| `vcp.prior_trend_min_pct` | threshold_multiplicative | NOT BINDING | (none) | 0 | -12 to -24 (tighten only) | No aplus impact; tightening to 31.25 / 37.5 drops 12-24 watch. |
| `vcp.pullback_max_pct` | threshold_multiplicative | NOT BINDING | (none) | 0 | 0 (max -5 at 12.5) | Invariant from 18.75-37.5; marginal -5 watch at 12.5. |
| `vcp.orderliness_max_range_cv` | threshold_multiplicative | NOT BINDING | (none) | 0 | 0 (max +4 at 0.75-0.9) | Marginal +4 watch when loosened; no aplus impact. Tightening to 0.3 catastrophic (-886 watch / 5143 skip). |
| `risk.max_risk_pct` | threshold_multiplicative | NOT BINDING | (none) | 0 | -155 to +19 | No aplus impact across sweep; watch shifts -155 to +19 by sweep direction. |
| `rs.horizon_weeks` | threshold_additive | NOT BINDING | (none) | 0 | 0 | Invariant across 10-14 sweep grid. |
| `rs.rs_rank_min_pass` | threshold_additive | NOT BINDING | (none) | 0 | 0 | Invariant across 60-80 sweep grid. RS rank distribution of current universe doesn't intersect the sweep boundary. |
| `rs.fallback_extreme_pct` | threshold_multiplicative | NOT BINDING | (none) | 0 | 0 | Invariant. (Not surfaced in headline because all sweep deltas == 0.) |

**Binding-variable summary**: 5 of 17 binding for aplus-flip semantics (all in VCP family + zero in TT / risk / RS). 7 of 17 binding for watch-flip semantics (the 5 VCP + 2 gate variables). The remaining 10 of 17 are NOT BINDING within the V1 5-point sweep grids (RS / TT / risk / non-tightness VCP all show zero or marginal aplus delta).

## Conclusion

**5 binding variables identified — all in the VCP family** (rank by `max_delta_aplus` headline):

1. `vcp.tightness_range_factor` +75 aplus at sweep_point 1.005 (loosen from baseline 0.67) — **clearly the most binding lever**.
2. `vcp.tightness_days_required` +16 aplus at sweep_point 1 (loosen from baseline 2).
3. `vcp.adr_min_pct` +11 aplus at sweep_point 2.0 (loosen from baseline 4.0).
4. `vcp.proximity_max_pct` +5 aplus at sweep_point 7.5 (loosen from baseline 5.0).
5. `vcp.orderliness_max_bar_ratio` +1 aplus at sweep_point 4.5 (loosen from baseline 3.0) — marginal.

**Substantive finding**: the operator's actionable A+ surface (current 5 A+ candidates across 5666 evaluated) is most sensitive to VCP-family threshold relaxation, with `vcp.tightness_range_factor` leading by a wide margin (+75 vs next +16). Trend-template thresholds, risk, and RS-related dials are all NON-BINDING within the V1 5-point sweep grids — meaning the current candidate universe has no candidates clustered near those thresholds. This points toward VCP-pattern detection sensitivity rather than ranking-layer (TT / risk / RS) calibration as the most-actionable lever for the next cfg-policy proposal.

**Bidirectional sensitivity**: `vcp.tightness_range_factor` and `vcp.proximity_max_pct` are both strongly bidirectional — tightening drops aplus to 0; loosening adds 5-75 aplus. The 5-A+-baseline finding is sensitive at both edges.

**Catastrophic gate behavior**: `trend_template.min_passes=9` (tighten from baseline 7 by +2) is a cliff edge — drops 5 aplus + all 1321 watch to zero (out_of_range_skip 5578). `vcp.watch_max_fails=0` similarly catastrophic. Both expected per gate semantics; document for operator awareness.

**Forward action sequence (post-promotion-gate decision D1)**:

1. **Method-record promoted research → shadow** 2026-05-24 PM (v0.2.2 → v0.3.0; operator decision D1 LOCKED). Treats baseline-parity invariant as "green to the extent V2 evaluator's correctness is verifiable against V1, with 3 documented L4 + L5 + L6 architectural limitations." V2 evaluator correctness verified 3x via decisive counter-tests.
2. **Next-arc decision OPERATOR-PAIRED**: (a) cfg-policy proposal for `vcp.tightness_range_factor` shadow → production pathway per V2.1 §VII.C (most binding; clearest evidence); OR (b) market-conditions / other-gates investigation per V2.1 §III scope; OR (c) Phase 14 commissioning consideration per Path B sequencing.
3. **L6 V2.5/V3 candidate banked**: immutable archive snapshot before V2 run to eliminate temporal-mutation drift class (would also unblock strict baseline-parity invariant interpretation if operator preference shifts).

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
4. **RS universe duplicate detection is defense-in-depth (inert today)**:
   `load_validated_rs_universe` performs an explicit duplicate-detection pass
   after `load_universe` (which already calls `sorted(set(...))` internally).
   The V2 duplicate pass is defense-in-depth against a future contract change
   in `load_universe`; it is inert on current production files because
   `load_universe` pre-deduplicates. V2.5 candidate: validate raw file rows
   before `load_universe` to surface duplicates at the CSV-read boundary
   rather than post-load.

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

**Amendment 1 (2026-05-23, post-ship QA):** Three Issues reconciled:

1. **findings table gate rows populated from partial smoke** -- 2 gate-variable
   rows (`trend_template.min_passes` + `vcp.watch_max_fails`) updated with
   actual data from 5-eval-run partial smoke CSV. Caveat added; 15 threshold
   variables remain TBD pending operator full run.

2. **both-exist banner deduplication fix** -- `output.py` now emits
   `sorted(set(affected_tickers))` instead of raw list at banner emit time.
   Same ticker was appended once per eval_run per variable per sweep_point;
   partial smoke showed "16 entries for 3 unique tickers" which was misleading.
   Discriminating test added (test_aplus_v2_ohlcv_output.py test 14).

3. **L2 LOCK test count reconciliation** -- closer commit `737c589` body
   cited "3 BINDING discriminating tests" (undercount). Canonical count is
   **5 L2 LOCK discriminating tests (3 BINDING + 2 defensive) per spec §F + §K**
   as documented in: (a) test_aplus_v2_ohlcv_reader.py module docstring;
   (b) method-record aplus-criteria-calibration.md line 63; (c) plan §F + §K.
   Closer commit is immutable; this amendment serves as the visible correction.

**Amendment 2 (2026-05-24 PM, post-full-reproduction + 3-investigation arc completion):**

The full 63-eval-run operator reproduction SHIPPED at `exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.{csv,md}` (86 min runtime / not truncated / 5666 candidates) supersedes the prior partial-smoke artifacts. The findings table + Conclusion section have been populated with authoritative full-reproduction data.

**5 binding variables identified — all VCP-family** with `vcp.tightness_range_factor` leading at +75 max_delta_aplus.

**3 architectural V1↔V2 baseline-parity limitations characterized** across three sequential investigations (2026-05-23 → 2026-05-24 PM):

1. **L4 — Parallel-archive freshness desync** (DK:62 investigation at merge `4afab36` 2026-05-23): cross-archive asymmetry between Shape A and legacy. Remediated for recent boundary via D.1 Shape A refresh 2026-05-24. CLAUDE.md gotcha #24.
2. **L5 — Sentinel-bucket parity-comparison discipline** (DHC/UCO/VSAT × 60-64 investigation at merge `d7cdd51` 2026-05-24): V1 short-circuits criterion evaluation for `bucket='excluded'` (held_set + ETF blocklist) + `bucket='error'` (OHLCV fetch failure); V2's `bucket_for` cannot reproduce. Remediated via Option A 1-line filter at merge `b7f70ff` 2026-05-24. CLAUDE.md gotcha #25.
3. **L6 — Archive bar-content TEMPORAL mutation** (full-reproduction investigation at merge `c8f9612` 2026-05-24 PM): intervening pipeline runs progressively overwrite historical bars via `swing/data/ohlcv_archive.py:write_window:358-360` drop_duplicates `keep='last'` semantics when yfinance returns slightly different values (late-reporting + retroactive adjustments). V1's persisted criteria reflect old archive bars; V2 reads current. **Characterized as L6 limitation per Option A; ZERO V1 code changes; immutable-archive-snapshot V2.5/V3 candidate banked.** CLAUDE.md gotcha #26.

**V2 evaluator correctness verified 3x** via decisive counter-tests across all three investigations (DK:62 / DHC/UCO/VSAT / full-reproduction). Each investigation independently confirmed that V2's `evaluate_one` produces the expected bucket given the inputs it actually reads; the divergence in all three cases was architectural (data path / comparison logic / temporal mutation), NOT a V2 evaluator bug.

**Drift class L4-style** (data-input divergence; V2 evaluator correct given inputs) for the L6 surface: the 14 drift candidates (0.25% of 5666) flip V1=watch / V2=skip — they contribute to `delta_watch` but NOT `delta_aplus`. The headline `max_delta_aplus` column is therefore UNAFFECTED. **All 5 binding variables ROBUST** — top 2 (`vcp.tightness_range_factor` +75, `vcp.tightness_days_required` +16) strongly robust; bottom 3 (`vcp.adr_min_pct` +11, `vcp.proximity_max_pct` +5, `vcp.orderliness_max_bar_ratio` +1) marginally robust but +1 to +11 holds.

**Method-record promoted research → shadow** 2026-05-24 PM (v0.2.2 → v0.3.0) per operator decision D1: treat baseline-parity invariant as "green to the extent V2 evaluator's correctness is verifiable against V1, with 3 documented L4 + L5 + L6 architectural limitations". Shadow tier achieved per V2.1 §IV.D + OQ-8 ladder gate conditions (V2 shipped + ≥1 study writeup published + ≥1 binding threshold variable identified — all 3 SATISFIED).

**Next operator-paired decision**: cfg-policy proposal (likely `vcp.tightness_range_factor` per binding-variable headline) for shadow → production pathway per V2.1 §VII.C; OR market-conditions investigation per spec §B.3; OR Phase 14 commissioning per Path B sequencing.

## Walk-forward backtest validation (vcp.tightness_range_factor=1.005)

**Dispatch brief:** [docs/v2-tightness-range-factor-backtest-dispatch-brief.md](../../docs/v2-tightness-range-factor-backtest-dispatch-brief.md)
**Findings doc:** [docs/v2-tightness-range-factor-backtest-findings-2026-05-24.md](../../docs/v2-tightness-range-factor-backtest-findings-2026-05-24.md)
**Backtest artifact:** `exports/research/tightness-range-factor-backtest-<ISO>/`
**Date:** 2026-05-24.

### Question

Does loosening `vcp.tightness_range_factor` from baseline 0.67 to 1.005 (the V2 sensitivity sweep's `max_delta_aplus = +75` headline) generate profitable trades under realistic exit rulesets, OR does it merely classify non-breakout patterns as A+ candidates?

### Method

- **Cohort:** 67 watch→aplus flips at sweep_point=1.005 (per V2 full-reproduction smoke `aplus-sensitivity-v2-20260524T205849Z.{csv,md}`); 15 unique tickers; 17 unique VCP patterns post-dedup (consecutive eval_runs collapsed within 5 business days).
- **Control:** V1 baseline A+ candidates from `candidates` table where `bucket='aplus'` (5 rows; 2 unique patterns post-dedup; SLDB + YOU).
- **Entry rule:** first close > pivot triggers entry at NEXT session's Open. Pivot = V1-persisted `candidates.pivot` at FIRST eval_run in pattern group; initial_stop = V1-persisted `candidates.initial_stop`.
- **Three exit rulesets:** A (Minervini trail-MA per TLSMW M.2 + DST D.3 — initial stop, +2R extension arms 50d SMA trail, hard exit at close-below-50d); B (Fixed R-multiple — +1R BE, +3R target, 21d SMA trail post-BE); C (Close-below-50d-SMA — trail arms when close > rising 50d, hard exit at first close < 50d).
- **OHLCV source:** V2 Shape A reader (`research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader`) — L2 LOCK preserved; ZERO new Schwab API calls; ZERO yfinance calls.

### Results

| Cohort | Patterns | Triggered | Closed | Open | Untriggered | No-data |
|--------|----------|-----------|--------|------|-------------|---------|
| vcp.tightness_range_factor=1.005 | 17 | 5 (29.4%) | 0 | 5 | 10 | 2 |
| V1 baseline A+ (sweep_point=0.67) | 2 | 1 (50.0%) | 0 | 1 | 1 | 0 |

**Per-ruleset stats:** all three rulesets emit IDENTICAL pattern-level outcomes — none of the 5 triggered patterns progressed far enough for the rulesets' post-trigger divergence (+2R / +1R BE / 50d-cross arm) to fire. The 3 rulesets are indistinguishable on this cohort.

**Triggered patterns at data tail (cohort):**

| Pattern | Ticker | Entry date | Days held | R-multiple |
|---------|--------|------------|-----------|------------|
| FRO-r19 | FRO | 2026-05-11 | 3 | -0.34R |
| PTEN-r40 | PTEN | 2026-05-19 | 3 | -0.18R |
| RNG-r22 | RNG | 2026-05-04 | 8 | -0.28R |
| YOU-r22 | YOU | 2026-05-07 | 15 | +0.04R |
| YOU-r55 | YOU | 2026-05-21 | 1 | -0.13R |

Mean unrealized R across 5 open positions: **-0.18R**.

**Untriggered near-miss diagnostic (max forward close as % of pivot):**

The 10 untriggered patterns with non-zero forward bars came close but never crossed: max close ranges 86.3% to 99.0% of pivot. Even patterns with 21 forward bars (RLMD-r13) or 13 forward bars (FRO-r19 baseline window before triggering) failed to break above pivot. This is the signature of *marginal A+ flips* — candidates that trip the loosened criterion but never produce a launch move.

### Conclusion

**INSUFFICIENT POSITIVE EVIDENCE for the cfg-policy proposal** at `vcp.tightness_range_factor=1.005`.

- 70.6% non-breakout rate (12 / 17 patterns; max forward close 86-99% of pivot).
- 0% closed-trade rate under any of the 3 exit rulesets.
- 4 / 5 triggered patterns unrealized-negative; 1 marginally positive (+0.04R after 15 days).
- No cross-ruleset edge (all 3 rulesets emit identical outcomes on this cohort).
- Control cohort (2 patterns) inherits the same data-tail constraints; provides no positive signal.

**Interpretation:** the V2 sensitivity sweep's +75 max_delta_aplus headline at sweep_point=1.005 measures candidate-classification deltas, NOT realized-trade profitability. Loosening the tightness threshold materially increases the A+ surface by ~16x (5 → 80) — but the marginal candidates added by loosening are predominantly NON-BREAKOUT-DURING-EVAL-WINDOW patterns. The threshold relaxation captures noise more than it captures missed signal.

**Limitations:**

- **OHLCV cache freshness (L4-related):** 14 of 15 cohort tickers fall through to legacy archive (no Shape A); 7 tickers' legacy archives extend less than 5 business days past their first eval_run asof. This is an operator-cache state, not a V2 reader issue.
- **Walk-forward window asymmetry:** patterns with later first_data_asof_date have fewer forward bars. Mitigated by the near-miss diagnostic — long-window patterns (RLMD-r13 at 21 bars) also fail to break out.
- **L6 archive temporal-mutation drift:** ZERO overlap between the 14 L6-drifted candidates from the V2 full-reproduction smoke and this cohort's 15 tickers. L6 has zero direct impact on this backtest.
- **N=5 triggered + N=0 closed:** sample size too small for statistical confidence intervals; verdict is structural (70.6% non-breakout) rather than statistical.

### Forward action

Operator-paired triage:

- **Option A (recommended immediate):** abandon `vcp.tightness_range_factor` as the next cfg-policy substrate. Pivot to a different binding variable's backtest — e.g., `vcp.tightness_days_required` (+16 max_delta_aplus; next-most-binding).
- **Option B (operator-paired follow-up):** refresh OHLCV Shape A archives for the 14 stale-cache tickers via production pipeline runs; re-run the backtest with full data tail through 2026-05-22. Low-cost archive-state recovery; closes the data-sparsity caveat.
- **Option C (V2.5/V3):** multi-quarter walk-forward window (e.g., VCP breakouts triggered 2024 + 2025 with full forward-walk to 2026). Provides statistical power for variable-by-variable backtest claims; substantially larger dispatch.

