# V2-Selection-Mechanic Compatibility Synthesis

## Categorical Compatibility: COMPATIBLE

Across 5 V2 binding variables analyzed, 0 substrate(s) showed BELOW-BASELINE filtered W-density delta vs the D2 EXPANDED bias-free reference; 5 substrate(s) showed AT-or-ABOVE-BASELINE density relative to that reference.

## Per-Variable Signal Table

| variable | sweep_point | T (tickers) | F (filtered W) | D_filt | delta_vs_baseline | regime_90d_return_median | regime_atr_pct_median | regime_52w_prox_median | dominant_sector |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| vcp.tightness_range_factor | 1.005 | 15 | 137 | 9.1333 | 8.9957 | 65.03 | 5.56 | 8.69 | UNKNOWN |
| vcp.tightness_days_required | 1.0 | 7 | 64 | 9.1429 | 9.0053 | 64.49 | 5.54 | 8.78 | UNKNOWN |
| vcp.adr_min_pct | 2.0 | 4 | 4 | 1.0000 | 0.8624 | 40.31 | 2.94 | 4.53 | UNKNOWN |
| vcp.proximity_max_pct | 7.5 | 3 | 29 | 9.6667 | 9.5291 | 42.86 | 6.42 | 8.02 | UNKNOWN |
| vcp.orderliness_max_bar_ratio | 3.75 | 1 | 3 | 3.0000 | 2.8624 | 100.56 | 8.62 | 13.04 | UNKNOWN |

## Methodological Notes

- Canonical filter held FIXED across all 5 V2 substrates + D2 EXPANDED baseline: composite >= 0.5 AND recency <= 365d (gotcha #33 third canonical application REINFORCED).
- D2 EXPANDED bias-free baseline: 71 filtered W primaries over 516 unique S&P 500 tickers (density = 0.1376 W per ticker; manifest 20260526T000409Z; Brief Amendment 2 corrected universe size from 88 to 516 at investigation greenlight 2026-05-26 PM).
- Raw W-density (D_raw) is NOT AVAILABLE in V1 because D2 baseline results.csv was not emitted at baseline-run time; Option B fallback per orchestrator greenlight emits only D_filt. Banked V2 candidate: re-run D2 EXPANDED with results.csv emission enabled to capture raw-density anchor.
- The investigation is ANALYTICAL, not a backtest. Per-ruleset P&L outcomes were established by R2-A + R2-D + D2 + D1 backtest arcs and are referenced contextually but NOT recomputed.
- Per-variable SUMMARY-TABLE vs drill-down non-watch-transition gap is documented as a methodological side-finding: vcp.tightness_range_factor +75 SUMMARY vs 67 drill-down (gap 8; ~11%); vcp.tightness_days_required +16 vs 15 (gap 1; 6%); other 3 variables show zero gap. The Sensitivity Matrix is the authoritative source for the binding signal.
