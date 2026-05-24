# V2 OHLCV A+ Criterion Sensitivity Analysis

Generated: 2026-05-24 18:15 UTC
Eval-runs window: 5 (ids 60..64)
Total candidates evaluated: 351
V2 universe size: 516
V2 universe hash: v2_universe_hash_85b0871b5a5e0cc5aef399eabd65cd8cd5ba656af18f127098c2bc57647e4b34
OHLCV coverage skips (global): 5
Universe skipped tickers: 0
Runtime seconds: 121.73
Truncated by runtime cap: YES

## Headline: Top Binding Variables

No binding variables found (all delta_aplus == 0).

## V1<->V2 Baseline Parity

Tier-1 match: PASS (V1 and V2 agree on all tier-1 candidates)

Tier-2 match count: 10
Tier-2 mismatch count: 0
Tier-2 via surrogate count: 0

## WARNING: Both-Exist Archive Files Detected

WARNING: 3 tickers have both Shape A and legacy archive
files present in the cache directory. Shape A wins unconditionally
per OQ-18 LOCK. Verify no stale legacy files contaminate results.

Affected tickers (capped at 50):

- AESI
- DK
- PL

## Sensitivity Matrix

| variable_name | kind | sweep_point | aplus_count | watch_count | skip_count | excluded_count | delta_aplus | delta_watch | out_of_range_skip_count | ohlcv_coverage_skip_count | evaluation_error_skip_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| trend_template.min_passes | gate | 5 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.min_passes | gate | 6 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.min_passes | gate | 7 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.min_passes | gate | 8 | 0 | 61 | 285 | 0 | 0 | -4 | 0 | 5 | 0 |
| trend_template.min_passes | gate | 9 | 0 | 0 | 0 | 0 | 0 | -65 | 346 | 5 | 0 |
| vcp.watch_max_fails | gate | 0 | 0 | 0 | 346 | 0 | 0 | -65 | 0 | 5 | 0 |
| vcp.watch_max_fails | gate | 1 | 0 | 12 | 334 | 0 | 0 | -53 | 0 | 5 | 0 |
| vcp.watch_max_fails | gate | 2 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| vcp.watch_max_fails | gate | 3 | 0 | 202 | 144 | 0 | 0 | 137 | 0 | 5 | 0 |
| vcp.watch_max_fails | gate | 4 | 0 | 262 | 84 | 0 | 0 | 197 | 0 | 5 | 0 |
| trend_template.rising_ma_period_days | threshold_additive | 11 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.rising_ma_period_days | threshold_additive | 12 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.rising_ma_period_days | threshold_additive | 13 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.rising_ma_period_days | threshold_additive | 14 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.rising_ma_period_days | threshold_additive | 15 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.rising_ma_period_days | threshold_additive | 16 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.rising_ma_period_days | threshold_additive | 17 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.rising_ma_period_days | threshold_additive | 18 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.rising_ma_period_days | threshold_additive | 19 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.rising_ma_period_days | threshold_additive | 20 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.rising_ma_period_days | threshold_additive | 21 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.rising_ma_period_days | threshold_additive | 22 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.rising_ma_period_days | threshold_additive | 23 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.rising_ma_period_days | threshold_additive | 24 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.rising_ma_period_days | threshold_additive | 25 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.rising_ma_period_days | threshold_additive | 26 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.rising_ma_period_days | threshold_additive | 27 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.rising_ma_period_days | threshold_additive | 28 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.rising_ma_period_days | threshold_additive | 29 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.rising_ma_period_days | threshold_additive | 30 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.rising_ma_period_days | threshold_additive | 31 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.high_52w_margin_pct | threshold_multiplicative | 12.5 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.high_52w_margin_pct | threshold_multiplicative | 18.75 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.high_52w_margin_pct | threshold_multiplicative | 25.0 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.high_52w_margin_pct | threshold_multiplicative | 31.25 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.high_52w_margin_pct | threshold_multiplicative | 37.5 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.low_52w_min_pct | threshold_multiplicative | 15.0 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.low_52w_min_pct | threshold_multiplicative | 22.5 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.low_52w_min_pct | threshold_multiplicative | 30.0 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.low_52w_min_pct | threshold_multiplicative | 37.5 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |
| trend_template.low_52w_min_pct | threshold_multiplicative | 45.0 | 0 | 65 | 281 | 0 | 0 | 0 | 0 | 5 | 0 |

## Per-Variable Drill-Down

Note: old_criterion_failure is '(none)' for all entries in V1.
V2 candidate: compute from persisted candidate_criteria rows.

### trend_template.min_passes

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| YOU | 64 | 2026-05-22 | 8 | watch | skip | (none) | no |
| UCTT | 63 | 2026-05-21 | 8 | watch | skip | (none) | no |
| UCTT | 62 | 2026-05-21 | 8 | watch | skip | (none) | no |
| UCTT | 61 | 2026-05-20 | 8 | watch | skip | (none) | no |

### vcp.watch_max_fails

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AESI | 64 | 2026-05-22 | 0 | watch | skip | (none) | no |
| BKSY | 64 | 2026-05-22 | 0 | watch | skip | (none) | no |
| BULZ | 64 | 2026-05-22 | 0 | watch | skip | (none) | no |
| CNTA | 64 | 2026-05-22 | 0 | watch | skip | (none) | no |
| CVE | 64 | 2026-05-22 | 0 | watch | skip | (none) | no |
| DBO | 64 | 2026-05-22 | 0 | watch | skip | (none) | no |
| GSG | 64 | 2026-05-22 | 0 | watch | skip | (none) | no |
| PL | 64 | 2026-05-22 | 0 | watch | skip | (none) | no |
| PTEN | 64 | 2026-05-22 | 0 | watch | skip | (none) | no |
| SATL | 64 | 2026-05-22 | 0 | watch | skip | (none) | no |
| SEI | 64 | 2026-05-22 | 0 | watch | skip | (none) | no |
| UCTT | 64 | 2026-05-22 | 0 | watch | skip | (none) | no |
| YOU | 64 | 2026-05-22 | 0 | watch | skip | (none) | no |
| BKSY | 63 | 2026-05-21 | 0 | watch | skip | (none) | no |
| BULZ | 63 | 2026-05-21 | 0 | watch | skip | (none) | no |
| CNTA | 63 | 2026-05-21 | 0 | watch | skip | (none) | no |
| CODI | 63 | 2026-05-21 | 0 | watch | skip | (none) | no |
| CVE | 63 | 2026-05-21 | 0 | watch | skip | (none) | no |
| DBO | 63 | 2026-05-21 | 0 | watch | skip | (none) | no |
| PL | 63 | 2026-05-21 | 0 | watch | skip | (none) | no |
| PTEN | 63 | 2026-05-21 | 0 | watch | skip | (none) | no |
| SATL | 63 | 2026-05-21 | 0 | watch | skip | (none) | no |
| SEI | 63 | 2026-05-21 | 0 | watch | skip | (none) | no |
| UCTT | 63 | 2026-05-21 | 0 | watch | skip | (none) | no |
| YOU | 63 | 2026-05-21 | 0 | watch | skip | (none) | no |
| BULZ | 62 | 2026-05-21 | 0 | watch | skip | (none) | no |
| CNTA | 62 | 2026-05-21 | 0 | watch | skip | (none) | no |
| CODI | 62 | 2026-05-21 | 0 | watch | skip | (none) | no |
| CVE | 62 | 2026-05-21 | 0 | watch | skip | (none) | no |
| DBO | 62 | 2026-05-21 | 0 | watch | skip | (none) | no |
| PL | 62 | 2026-05-21 | 0 | watch | skip | (none) | no |
| PTEN | 62 | 2026-05-21 | 0 | watch | skip | (none) | no |
| SATL | 62 | 2026-05-21 | 0 | watch | skip | (none) | no |
| UCTT | 62 | 2026-05-21 | 0 | watch | skip | (none) | no |
| UMC | 62 | 2026-05-21 | 0 | watch | skip | (none) | no |
| BULZ | 61 | 2026-05-20 | 0 | watch | skip | (none) | no |
| CNTA | 61 | 2026-05-20 | 0 | watch | skip | (none) | no |
| CODI | 61 | 2026-05-20 | 0 | watch | skip | (none) | no |
| CVE | 61 | 2026-05-20 | 0 | watch | skip | (none) | no |
| DBO | 61 | 2026-05-20 | 0 | watch | skip | (none) | no |
| DK | 61 | 2026-05-20 | 0 | watch | skip | (none) | no |
| GFS | 61 | 2026-05-20 | 0 | watch | skip | (none) | no |
| PL | 61 | 2026-05-20 | 0 | watch | skip | (none) | no |
| PTEN | 61 | 2026-05-20 | 0 | watch | skip | (none) | no |
| SATL | 61 | 2026-05-20 | 0 | watch | skip | (none) | no |
| UCTT | 61 | 2026-05-20 | 0 | watch | skip | (none) | no |
| CNTA | 60 | 2026-05-20 | 0 | watch | skip | (none) | no |
| CODI | 60 | 2026-05-20 | 0 | watch | skip | (none) | no |
| CVE | 60 | 2026-05-20 | 0 | watch | skip | (none) | no |
| DBO | 60 | 2026-05-20 | 0 | watch | skip | (none) | no |
| DK | 60 | 2026-05-20 | 0 | watch | skip | (none) | no |
| IRDM | 60 | 2026-05-20 | 0 | watch | skip | (none) | no |
| PL | 60 | 2026-05-20 | 0 | watch | skip | (none) | no |
| PTEN | 60 | 2026-05-20 | 0 | watch | skip | (none) | no |
| SATL | 60 | 2026-05-20 | 0 | watch | skip | (none) | no |
| YOU | 60 | 2026-05-20 | 0 | watch | skip | (none) | no |
| AESI | 64 | 2026-05-22 | 1 | watch | skip | (none) | no |
| BKSY | 64 | 2026-05-22 | 1 | watch | skip | (none) | no |
| BULZ | 64 | 2026-05-22 | 1 | watch | skip | (none) | no |
| CNTA | 64 | 2026-05-22 | 1 | watch | skip | (none) | no |
| CVE | 64 | 2026-05-22 | 1 | watch | skip | (none) | no |
| DBO | 64 | 2026-05-22 | 1 | watch | skip | (none) | no |
| GSG | 64 | 2026-05-22 | 1 | watch | skip | (none) | no |
| PL | 64 | 2026-05-22 | 1 | watch | skip | (none) | no |
| SATL | 64 | 2026-05-22 | 1 | watch | skip | (none) | no |
| UCTT | 64 | 2026-05-22 | 1 | watch | skip | (none) | no |
| BKSY | 63 | 2026-05-21 | 1 | watch | skip | (none) | no |
| BULZ | 63 | 2026-05-21 | 1 | watch | skip | (none) | no |
| CNTA | 63 | 2026-05-21 | 1 | watch | skip | (none) | no |
| CODI | 63 | 2026-05-21 | 1 | watch | skip | (none) | no |
| CVE | 63 | 2026-05-21 | 1 | watch | skip | (none) | no |
| DBO | 63 | 2026-05-21 | 1 | watch | skip | (none) | no |
| PL | 63 | 2026-05-21 | 1 | watch | skip | (none) | no |
| SATL | 63 | 2026-05-21 | 1 | watch | skip | (none) | no |
| SEI | 63 | 2026-05-21 | 1 | watch | skip | (none) | no |
| YOU | 63 | 2026-05-21 | 1 | watch | skip | (none) | no |
| BULZ | 62 | 2026-05-21 | 1 | watch | skip | (none) | no |
| CNTA | 62 | 2026-05-21 | 1 | watch | skip | (none) | no |
| CODI | 62 | 2026-05-21 | 1 | watch | skip | (none) | no |
| CVE | 62 | 2026-05-21 | 1 | watch | skip | (none) | no |
| DBO | 62 | 2026-05-21 | 1 | watch | skip | (none) | no |
| PL | 62 | 2026-05-21 | 1 | watch | skip | (none) | no |
| SATL | 62 | 2026-05-21 | 1 | watch | skip | (none) | no |
| UMC | 62 | 2026-05-21 | 1 | watch | skip | (none) | no |
| BULZ | 61 | 2026-05-20 | 1 | watch | skip | (none) | no |
| CNTA | 61 | 2026-05-20 | 1 | watch | skip | (none) | no |
| CODI | 61 | 2026-05-20 | 1 | watch | skip | (none) | no |
| CVE | 61 | 2026-05-20 | 1 | watch | skip | (none) | no |
| DBO | 61 | 2026-05-20 | 1 | watch | skip | (none) | no |
| DK | 61 | 2026-05-20 | 1 | watch | skip | (none) | no |
| GFS | 61 | 2026-05-20 | 1 | watch | skip | (none) | no |
| PL | 61 | 2026-05-20 | 1 | watch | skip | (none) | no |
| PTEN | 61 | 2026-05-20 | 1 | watch | skip | (none) | no |
| SATL | 61 | 2026-05-20 | 1 | watch | skip | (none) | no |
| UCTT | 61 | 2026-05-20 | 1 | watch | skip | (none) | no |
| CNTA | 60 | 2026-05-20 | 1 | watch | skip | (none) | no |
| CODI | 60 | 2026-05-20 | 1 | watch | skip | (none) | no |
| CVE | 60 | 2026-05-20 | 1 | watch | skip | (none) | no |
| DBO | 60 | 2026-05-20 | 1 | watch | skip | (none) | no |
| DK | 60 | 2026-05-20 | 1 | watch | skip | (none) | no |
| IRDM | 60 | 2026-05-20 | 1 | watch | skip | (none) | no |
| PL | 60 | 2026-05-20 | 1 | watch | skip | (none) | no |
| PTEN | 60 | 2026-05-20 | 1 | watch | skip | (none) | no |
| SATL | 60 | 2026-05-20 | 1 | watch | skip | (none) | no |
| YOU | 60 | 2026-05-20 | 1 | watch | skip | (none) | no |
| AMDL | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| APLS | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| BNO | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| BTE | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| BW | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| CMPS | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| CODI | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| CORZ | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| DINO | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| GSAT | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| HIMX | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| HPE | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| KALV | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| KGS | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| LION | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| LQDA | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| NOK | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| PUMP | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| QLD | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| RIOT | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| RLMD | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| SEDG | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| SYRE | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| TQQQ | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| TVTX | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| TXG | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| VIRT | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| VSTS | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| XMAX | 64 | 2026-05-22 | 3 | skip | watch | (none) | no |
| AESI | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| AMDL | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| APLS | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| ATEN | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| AVNS | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| BNO | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| BTE | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| BW | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| CMPS | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| COCO | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| CORZ | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| DINO | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| GSAT | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| GSG | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| HIMX | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| HPE | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| KALV | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| KGS | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| LION | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| LQDA | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| NOK | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| PUMP | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| QLD | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| RIOT | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| RLMD | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| SEDG | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| SYRE | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| TQQQ | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| TVTX | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| VIRT | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| VSTS | 63 | 2026-05-21 | 3 | skip | watch | (none) | no |
| AESI | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| APLS | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| AVNS | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| BB | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| BNO | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| BTE | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| CMPS | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| COCO | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| DINO | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| GFS | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| GSAT | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| GSG | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| HPE | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| KALV | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| KGS | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| LION | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| MRX | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| NN | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| NVTS | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| PUMP | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| QLD | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| RIOT | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| STM | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| SYRE | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| TQQQ | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| VIRT | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| VSTS | 62 | 2026-05-21 | 3 | skip | watch | (none) | no |
| AESI | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| APLS | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| AVNS | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| BAI | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| BB | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| BTE | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| CMPS | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| DINO | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| GSAT | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| GSG | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| HPE | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| KGS | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| MRX | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| NN | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| NVTS | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| QLD | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| RIOT | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| STM | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| SYRE | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| TQQQ | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| UMC | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| VSTS | 61 | 2026-05-20 | 3 | skip | watch | (none) | no |
| AESI | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| APLS | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| ATEN | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| AVNS | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| BB | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| BTE | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| BW | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| DINO | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| GSAT | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| GSG | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| HIMX | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| HPE | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| KGS | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| NN | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| NOK | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| QLD | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| SEI | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| STM | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| TQQQ | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| UMC | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| VSH | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| VSTS | 60 | 2026-05-20 | 3 | skip | watch | (none) | no |
| AMDL | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| APLS | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| ATEN | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| AVNS | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| BAI | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| BNO | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| BTE | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| BW | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| CMPS | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| CNC | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| COCO | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| CODI | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| CORZ | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| DINO | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| GSAT | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| HIMX | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| HPE | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| KALV | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| KGS | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| LION | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| LQDA | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| NOK | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| OSS | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| PUMP | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| QLD | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| RIOT | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| RLMD | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| SEDG | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| SOXQ | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| SSL | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| SYRE | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| TH | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| TQQQ | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| TVTX | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| TXG | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| VIRT | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| VSTS | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| WTTR | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| XMAX | 64 | 2026-05-22 | 4 | skip | watch | (none) | no |
| AESI | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| AMDL | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| APLS | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| ASX | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| ATEN | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| AVNS | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| BAI | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| BNO | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| BTE | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| BTSG | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| BW | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| CMPS | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| CNC | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| COCO | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| CORZ | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| DINO | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| GSAT | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| GSG | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| HIMX | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| HPE | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| KALV | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| KGS | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| LION | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| LQDA | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| NOK | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| OSS | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| PUMP | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| QLD | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| RIOT | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| RLMD | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| SEDG | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| SOXQ | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| SSL | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| SYRE | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| TH | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| TQQQ | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| TVTX | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| VIRT | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| VSTS | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| WTTR | 63 | 2026-05-21 | 4 | skip | watch | (none) | no |
| AESI | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| APLS | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| AVNS | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| BAI | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| BB | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| BNO | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| BTE | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| BTSG | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| CMPS | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| CNC | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| COCO | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| DINO | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| GFS | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| GSAT | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| GSG | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| GTX | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| HPE | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| KALV | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| KGS | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| LION | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| MRX | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| NN | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| NVTS | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| OSS | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| PUMP | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| QLD | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| RIOT | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| SOXQ | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| SSL | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| ST | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| STM | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| SYRE | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| TH | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| TQQQ | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| VIRT | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| VSTS | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| WTTR | 62 | 2026-05-21 | 4 | skip | watch | (none) | no |
| AESI | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| APLS | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| AVNS | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| BAI | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| BB | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| BNO | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| BTE | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| BTSG | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| CMPS | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| CNC | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| COCO | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| DINO | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| GSAT | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| GSG | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| GTX | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| HPE | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| KALV | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| KGS | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| LION | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| MRX | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| NN | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| NVTS | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| OSS | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| PUMP | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| QLD | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| RIOT | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| SOXQ | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| SSL | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| ST | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| STM | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| SYRE | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| TH | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| TQQQ | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| UMC | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| VIRT | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| VSTS | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| WTTR | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| XMAX | 61 | 2026-05-20 | 4 | skip | watch | (none) | no |
| AESI | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| APLS | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| ATEN | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| AVNS | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| BB | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| BNO | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| BTE | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| BTSG | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| BW | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| CNC | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| COCO | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| DINO | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| EQNR | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| GSAT | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| GSG | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| GTX | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| HIMX | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| HPE | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| KALV | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| KGS | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| LION | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| NN | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| NOK | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| PUMP | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| QLD | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| SEI | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| SOXQ | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| SSL | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| STM | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| TH | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| TQQQ | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| UMC | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| VIRT | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| VIST | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| VSH | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| VSTS | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |
| XMAX | 60 | 2026-05-20 | 4 | skip | watch | (none) | no |

### trend_template.rising_ma_period_days

(none)

### trend_template.high_52w_margin_pct

(none)

### trend_template.low_52w_min_pct

(none)

## V1<->V2 Baseline Parity Drift

Flips detected during baseline-parity pass (no variable substitution; cfg used unmodified). These indicate bucket divergence between persisted V1 evaluation and live V2 recompute at the same cfg.

(none)

## Notes

### Per-Variable Skip Counts

| variable_name | ohlcv_coverage_skip_count | out_of_range_skip_count | evaluation_error_skip_count |
| --- | --- | --- | --- |
| trend_template.min_passes | 5 | 0 | 0 |
| vcp.watch_max_fails | 5 | 0 | 0 |
| trend_template.rising_ma_period_days | 5 | 0 | 0 |
| trend_template.high_52w_margin_pct | 5 | 0 | 0 |
| trend_template.low_52w_min_pct | 5 | 0 | 0 |

### OQ-15 Tier-2 Surrogate Caveat

Tier-2 candidates use current_equity from the most-recent snapshot available on or before the eval_run asof_date. When no snapshot exists, the capital_floor surrogate is used; bucket_via_surrogate=True in the drill-down above.

### OQ-18 Both-Exist Policy Caveat

When both a yfinance Shape A parquet and a legacy parquet exist for a ticker, Shape A wins unconditionally per OQ-18 LOCK. Results may differ from a pure-legacy run. See WARNING banner above if any tickers were affected.

### V1 Simplification: old_criterion_failure

old_criterion_failure is '(none)' for all entries in this V1 release. V2 candidate: compute per-criterion attribution from persisted candidate_criteria rows (deferred; see return report section 6).

## Manifest

both_exist_shape_a_wins_count: 3
accepted_ticker_count: 516
total_candidates: 351
eval_runs_window: 5
v2_universe_hash: v2_universe_hash_85b0871b5a5e0cc5aef399eabd65cd8cd5ba656af18f127098c2bc57647e4b34
tier_1_count: 321
tier_2_count: 10
tier_2_via_surrogate_count: 0
memory_peak_bytes: 20079517
memory_peak_mib: 19.15
runtime_seconds: 121.73
truncated_by_runtime_cap: YES

