# V2-Selection-Mechanic Compatibility Synthesis

## Per-Variable 3-Axis Profile (Brief Amendment 4)

Per Brief Amendment 4 (operator-paired LOCK 2026-05-27): each V2 binding variable is profiled along three substrate-characterization axes -- per-ticker productivity (ENRICHED / TYPICAL / DEPLETED vs D2 baseline 0.138 W/ticker); substrate size (SUFFICIENT T>=20 / MARGINAL 5<=T<20 / INSUFFICIENT T<5); canonical survival quality (COMPARABLE >=10% / DEGRADED 5-10% / SUPPRESSED <5%; composite=0 denominator). These are descriptive labels, NOT verdict terminology (gotcha #33 third canonical application LOCK).

| variable | sweep_point | profile | D_filt | survival(c=0) | survival(c>=0.5) |
| --- | --- | --- | --- | --- | --- |
| vcp.tightness_range_factor | 1.005 | ENRICHED + MARGINAL(T=15) + DEGRADED(5.5%) | 9.1333 | 5.5% | 7.1% |
| vcp.tightness_days_required | 1.0 | ENRICHED + MARGINAL(T=7) + SUPPRESSED(3.9%) | 9.1429 | 3.9% | 5.1% |
| vcp.adr_min_pct | 2.0 | TYPICAL + INSUFFICIENT(T=4) + SUPPRESSED(2.3%) | 1.0000 | 2.3% | 3.0% |
| vcp.proximity_max_pct | 7.5 | ENRICHED + INSUFFICIENT(T=3) + COMPARABLE(12.0%) | 9.6667 | 12.0% | 16.8% |
| vcp.orderliness_max_bar_ratio | 3.75 | ENRICHED + INSUFFICIENT(T=1) + COMPARABLE(15.8%) | 3.0000 | 15.8% | 18.8% |

## Three Metric Families Surfaced

1. **Per-ticker productivity** (D_filt = F/T; brief Sec 1.6 LOCK): Given a V2-selected ticker, how many canonical-filtered W primaries has it produced historically?
2. **Substrate size + aggregate output** (T and F): How many actionable W patterns are available from the substrate as a whole?
3. **Survival quality** (canonical_survival_rate at composite=0 + composite>=0.5): Of raw W primaries detected on the substrate, what fraction are recent + high-composite enough to be actionable? Two denominators: composite=0 (broadest); composite>=0.5 (R2-A/R2-D findings-doc-anchor framing).

## Per-Variable Detail Table

| variable | T | R_raw(c=0) | R_raw(c>=0.5) | F | D_filt | regime_90d_ret | regime_atr_pct | regime_52w_prox | dominant_sector |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| vcp.tightness_range_factor | 15 | 2482 | 1940 | 137 | 9.1333 | 65.03 | 5.56 | 8.69 | UNKNOWN |
| vcp.tightness_days_required | 7 | 1643 | 1259 | 64 | 9.1429 | 64.49 | 5.54 | 8.78 | UNKNOWN |
| vcp.adr_min_pct | 4 | 173 | 132 | 4 | 1.0000 | 40.31 | 2.94 | 4.53 | UNKNOWN |
| vcp.proximity_max_pct | 3 | 242 | 173 | 29 | 9.6667 | 42.86 | 6.42 | 8.02 | UNKNOWN |
| vcp.orderliness_max_bar_ratio | 1 | 19 | 16 | 3 | 3.0000 | 100.56 | 8.62 | 13.04 | UNKNOWN |

## Legacy Single-Label Categorical (Pre-Amendment 4)

For backward compat the legacy F/T-only categorical label under brief Sec 1.7 yields: **COMPATIBLE**. 0 of 5 substrate(s) showed BELOW-BASELINE F/T; 5 showed AT-or-ABOVE-BASELINE. NOTE: this label is preserved for manifest backward compat ONLY; the dominant narrative is the per-variable 3-axis profile above.

## Methodological Notes

- Canonical filter held FIXED across all 5 V2 substrates + D2 EXPANDED baseline: composite >= 0.5 AND recency <= 365d (gotcha #33 third canonical application REINFORCED).
- D2 EXPANDED bias-free baseline: 71 filtered W primaries over 516 unique S&P 500 tickers (D_filt = 0.138 W per ticker; manifest 20260526T000409Z; Brief Amendment 2 corrected universe size from 88 to 516 at investigation greenlight 2026-05-26 PM).
- D2 baseline canonical_survival_rate is NOT AVAILABLE in V1 because the D2 baseline run emitted manifest.json + summary.md but NOT results.csv (Option B fallback per orchestrator greenlight). Banked V2 candidate: re-run D2 EXPANDED with results.csv emission enabled to capture the survival-rate baseline anchor for direct delta comparison.
- The investigation is ANALYTICAL, not a backtest. Per-ruleset P&L outcomes were established by R2-A + R2-D + D2 + D1 backtest arcs and are referenced contextually but NOT recomputed.
- Per-variable SUMMARY-TABLE vs drill-down non-watch-transition gap is documented as a methodological side-finding: vcp.tightness_range_factor +75 SUMMARY vs 67 drill-down (gap 8; ~11%); vcp.tightness_days_required +16 vs 15 (gap 1; 6%); other 3 variables show zero gap. The Sensitivity Matrix is the authoritative source for the binding signal.
