# V2 OHLCV A+ Criterion Sensitivity Analysis

Generated: 2026-05-23 23:01 UTC
Eval-runs window: 5 (ids 60..64)
Total candidates evaluated: 351
V2 universe size: 516
V2 universe hash: v2_universe_hash_85b0871b5a5e0cc5aef399eabd65cd8cd5ba656af18f127098c2bc57647e4b34
OHLCV coverage skips (global): 5
Universe skipped tickers: 0
Runtime seconds: 122.59
Truncated by runtime cap: YES

## Headline: Top Binding Variables

No binding variables found (all delta_aplus == 0).

## CRITERION DRIFT DETECTED

**BLOCKING:** V2 baseline (current-value sweep point) does NOT
match V1 persisted results for the following tier-1 candidates:

- DK:62
- DK:62
- DK:62

Action required: investigate V1/V2 divergence before trusting
V2 sensitivity results.

## V1<->V2 Baseline Parity

Tier-1 match: FAIL (see CRITERION DRIFT DETECTED section above)

Tier-2 match count: 30
Tier-2 mismatch count: 45
Tier-2 via surrogate count: 0

## WARNING: Both-Exist Archive Files Detected

WARNING: 16 tickers have both Shape A and legacy archive
files present in the cache directory. Shape A wins unconditionally
per OQ-18 LOCK. Verify no stale legacy files contaminate results.

Affected tickers (capped at 50):

- AESI
- PL
- AESI
- PL
- AESI
- PL
- DK
- AESI
- PL
- DK
- AESI
- PL
- DK
- AESI
- PL
- DK

## Sensitivity Matrix

| variable_name | kind | sweep_point | aplus_count | watch_count | skip_count | excluded_count | delta_aplus | delta_watch | out_of_range_skip_count | ohlcv_coverage_skip_count | evaluation_error_skip_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| trend_template.min_passes | gate | 5 | 0 | 66 | 280 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.min_passes | gate | 6 | 0 | 66 | 280 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.min_passes | gate | 7 | 0 | 66 | 280 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.min_passes | gate | 8 | 0 | 62 | 284 | 0 | 0 | -4 | 0 | 5 | 0 |
| trend_template.min_passes | gate | 9 | 0 | 0 | 346 | 0 | 0 | -66 | 0 | 5 | 0 |
| vcp.watch_max_fails | gate | 0 | 0 | 0 | 346 | 0 | 0 | -66 | 0 | 5 | 0 |
| vcp.watch_max_fails | gate | 1 | 0 | 12 | 334 | 0 | 0 | -54 | 0 | 5 | 0 |
| vcp.watch_max_fails | gate | 2 | 0 | 66 | 280 | 0 | 0 | 0 | 0 | 5 | 0 |
| vcp.watch_max_fails | gate | 3 | 0 | 203 | 143 | 0 | 0 | 137 | 0 | 5 | 0 |
| vcp.watch_max_fails | gate | 4 | 0 | 263 | 83 | 0 | 0 | 197 | 0 | 5 | 0 |

## Per-Variable Drill-Down

Note: old_criterion_failure is '(none)' for all entries in V1.
V2 candidate: compute from persisted candidate_criteria rows.

### trend_template.min_passes

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DHC | 64 | 2026-05-22 | 7 | excluded | skip | (none) | no |
| FPS | 64 | 2026-05-22 | 7 | skip | ohlcv_coverage_skip | (none) | no |
| PURR | 64 | 2026-05-22 | 7 | skip | ohlcv_coverage_skip | (none) | no |
| UCO | 64 | 2026-05-22 | 7 | excluded | watch | (none) | no |
| VSAT | 64 | 2026-05-22 | 7 | excluded | skip | (none) | no |
| DHC | 63 | 2026-05-21 | 7 | excluded | skip | (none) | no |
| FPS | 63 | 2026-05-21 | 7 | skip | ohlcv_coverage_skip | (none) | no |
| PURR | 63 | 2026-05-21 | 7 | skip | ohlcv_coverage_skip | (none) | no |
| UCO | 63 | 2026-05-21 | 7 | excluded | watch | (none) | no |
| VSAT | 63 | 2026-05-21 | 7 | excluded | watch | (none) | no |
| DHC | 62 | 2026-05-21 | 7 | excluded | skip | (none) | no |
| DK | 62 | 2026-05-21 | 7 | skip | watch | (none) | no |
| UCO | 62 | 2026-05-21 | 7 | excluded | watch | (none) | no |
| VSAT | 62 | 2026-05-21 | 7 | excluded | watch | (none) | no |
| DHC | 61 | 2026-05-20 | 7 | excluded | skip | (none) | no |
| UCO | 61 | 2026-05-20 | 7 | excluded | watch | (none) | no |
| VSAT | 61 | 2026-05-20 | 7 | excluded | watch | (none) | no |
| DHC | 60 | 2026-05-20 | 7 | excluded | skip | (none) | no |
| MIAX | 60 | 2026-05-20 | 7 | skip | ohlcv_coverage_skip | (none) | no |
| UCO | 60 | 2026-05-20 | 7 | excluded | watch | (none) | no |
| VSAT | 60 | 2026-05-20 | 7 | excluded | watch | (none) | no |

### vcp.watch_max_fails

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DHC | 64 | 2026-05-22 | 2 | excluded | skip | (none) | no |
| FPS | 64 | 2026-05-22 | 2 | skip | ohlcv_coverage_skip | (none) | no |
| PURR | 64 | 2026-05-22 | 2 | skip | ohlcv_coverage_skip | (none) | no |
| UCO | 64 | 2026-05-22 | 2 | excluded | watch | (none) | no |
| VSAT | 64 | 2026-05-22 | 2 | excluded | skip | (none) | no |
| DHC | 63 | 2026-05-21 | 2 | excluded | skip | (none) | no |
| FPS | 63 | 2026-05-21 | 2 | skip | ohlcv_coverage_skip | (none) | no |
| PURR | 63 | 2026-05-21 | 2 | skip | ohlcv_coverage_skip | (none) | no |
| UCO | 63 | 2026-05-21 | 2 | excluded | watch | (none) | no |
| VSAT | 63 | 2026-05-21 | 2 | excluded | watch | (none) | no |
| DHC | 62 | 2026-05-21 | 2 | excluded | skip | (none) | no |
| DK | 62 | 2026-05-21 | 2 | skip | watch | (none) | no |
| UCO | 62 | 2026-05-21 | 2 | excluded | watch | (none) | no |
| VSAT | 62 | 2026-05-21 | 2 | excluded | watch | (none) | no |
| DHC | 61 | 2026-05-20 | 2 | excluded | skip | (none) | no |
| UCO | 61 | 2026-05-20 | 2 | excluded | watch | (none) | no |
| VSAT | 61 | 2026-05-20 | 2 | excluded | watch | (none) | no |
| DHC | 60 | 2026-05-20 | 2 | excluded | skip | (none) | no |
| MIAX | 60 | 2026-05-20 | 2 | skip | ohlcv_coverage_skip | (none) | no |
| UCO | 60 | 2026-05-20 | 2 | excluded | watch | (none) | no |
| VSAT | 60 | 2026-05-20 | 2 | excluded | watch | (none) | no |

## Notes

### Per-Variable Skip Counts

| variable_name | ohlcv_coverage_skip_count | out_of_range_skip_count | evaluation_error_skip_count |
| --- | --- | --- | --- |
| trend_template.min_passes | 5 | 0 | 0 |
| vcp.watch_max_fails | 5 | 0 | 0 |

### OQ-15 Tier-2 Surrogate Caveat

Tier-2 candidates use current_equity from the most-recent snapshot available on or before the eval_run asof_date. When no snapshot exists, the capital_floor surrogate is used; bucket_via_surrogate=True in the drill-down above.

### OQ-18 Both-Exist Policy Caveat

When both a yfinance Shape A parquet and a legacy parquet exist for a ticker, Shape A wins unconditionally per OQ-18 LOCK. Results may differ from a pure-legacy run. See WARNING banner above if any tickers were affected.

### V1 Simplification: old_criterion_failure

old_criterion_failure is '(none)' for all entries in this V1 release. V2 candidate: compute per-criterion attribution from persisted candidate_criteria rows (deferred; see return report section 6).

## Manifest

both_exist_shape_a_wins_count: 16
accepted_ticker_count: 516
total_candidates: 351
eval_runs_window: 5
v2_universe_hash: v2_universe_hash_85b0871b5a5e0cc5aef399eabd65cd8cd5ba656af18f127098c2bc57647e4b34
tier_1_count: 963
tier_2_count: 75
tier_2_via_surrogate_count: 0
memory_peak_bytes: 13638513
memory_peak_mib: 13.01
runtime_seconds: 122.59
truncated_by_runtime_cap: YES

