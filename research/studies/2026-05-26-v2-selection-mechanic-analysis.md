# V2-Selection-Mechanic Analysis -- W-Pattern-Density + Regime-Fingerprint Investigation

**Investigation type:** ANALYTICAL / EXPLORATORY (NOT a backtest)
**Dispatch brief:** [`docs/v2-selection-mechanic-investigation-dispatch-brief.md`](../../docs/v2-selection-mechanic-investigation-dispatch-brief.md) at main HEAD `55d0f48` 2026-05-26
**Investigation greenlight:** operator-paired 2026-05-26 PM; Brief Amendments 1-4 applied 2026-05-26 PM through 2026-05-27 AM
**Smoke artifact:** [`exports/research/v2-selection-mechanic-analysis-20260527T084319Z/`](../../exports/research/v2-selection-mechanic-analysis-20260527T084319Z/) (canonical source SHA `b25bcde9...e27a143`; D2 baseline manifest `20260526T000409Z`)

---

## Sec 1 Headline Finding

V2 OHLCV binding-variable cohort selection produces substrates that are systematically ENRICHED for W-pattern productivity on a per-ticker basis (D_filt = 7-70x the D2 EXPANDED bias-free baseline of 0.138 W per ticker), but substrate SIZE is too small for defensible per-ruleset evaluation under the canonical filter (T<=15 in all 5 cases; T<5 in 3 of 5; baseline T=516). The cross-cohort "substrate thinness" framing in R2-A and R2-D findings docs was a function of small substrate size T, not low per-ticker W-pattern incidence.

Across the 5 V2 binding variables, the per-variable 3-axis profile (productivity / substrate-size / survival quality) per Brief Amendment 4 yields:

| Variable | sweep_point | Profile |
|---|---|---|
| vcp.tightness_range_factor | 1.005 | **ENRICHED + MARGINAL(T=15) + DEGRADED(5.5%)** |
| vcp.tightness_days_required | 1.0 | **ENRICHED + MARGINAL(T=7) + SUPPRESSED(3.9%)** |
| vcp.adr_min_pct | 2.0 | **TYPICAL + INSUFFICIENT(T=4) + SUPPRESSED(2.3%)** |
| vcp.proximity_max_pct | 7.5 | **ENRICHED + INSUFFICIENT(T=3) + COMPARABLE(12.0%)** |
| vcp.orderliness_max_bar_ratio | 3.75 | **ENRICHED + INSUFFICIENT(T=1) + COMPARABLE(15.8%)** |

The R2-A rejecting Ruleset E verdict on the tightness_days_required substrate (N=65 historical W primaries) and the R2-D insufficient-sample finding on the adr_min_pct substrate (N=4) are NOT consequences of V2 substrates being W-pattern-depleted -- V2 substrates produce W patterns in materially greater per-ticker abundance than the unbiased reference cohort. Rather they reflect: (a) too few V2-selected tickers to amortize per-ruleset evaluation noise, and (b) DEGRADED-to-SUPPRESSED canonical survival rates on the tightness-family V2 variables that may indicate the surviving W patterns have systematically different quality profiles than the baseline cohort's surviving patterns.

V2 selection for production deployment of Ruleset E would benefit from substrate-size augmentation (broader watch->aplus flip aggregation across multiple binding variables; longer recency window; or composite-threshold relaxation) before per-ruleset evaluation can discriminate cohort-specific rejecting outcomes from substrate-size-driven sampling noise.

---

## Sec 2 Methodology

### Sec 2.1 Cohort enumeration

5 V2 binding variables identified from the V2 OHLCV A+ Criterion Sensitivity Analysis smoke artifact at [`exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md`](../../exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md) (canonical SHA-256 `b25bcde9...e27a143`; 830034 bytes; 5172s runtime; 63 eval_runs; 5666 candidates; V2 universe 516 unique tickers). The SUMMARY TABLE at lines 13-22 enumerates the 5 binding signals by `max_delta_aplus`; the Sensitivity Matrix at lines 66-145 enumerates per-sweep-point `delta_aplus` breakdowns. Per CLAUDE.md cumulative gotcha #34 (brief-prescription cross-table verification; FIRST CANONICAL APPLICATION at this investigation), the binding `(variable, max_delta_aplus, binding_sweep_point)` tuples are LOCKED via runtime cross-table verification at [`tests/research/v2_selection_mechanic/test_binding_signals_table_cross_check.py`](../../tests/research/v2_selection_mechanic/test_binding_signals_table_cross_check.py):

| Variable | max_delta_aplus (SUMMARY) | sweep_point (Matrix) | First-crossing convention? |
|---|---|---|---|
| vcp.tightness_range_factor | 75 | 1.005 | n/a (single crossing) |
| vcp.tightness_days_required | 16 | 1.0 | n/a |
| vcp.adr_min_pct | 11 | 2.0 | n/a |
| vcp.proximity_max_pct | 5 | 7.5 | n/a |
| vcp.orderliness_max_bar_ratio | 1 | 3.75 | YES (sp=3.75 first; sp=4.5 identical flip set; LOCK chooses lower per "first crossing" convention) |

### Sec 2.2 SUMMARY-TABLE vs drill-down accounting (gotcha #34 SECOND canonical application)

Per Brief Amendment (operator greenlight 2026-05-26 PM), the V2 sensitivity emitter's SUMMARY TABLE `max_delta_aplus` and the drill-down section's strict watch->aplus row count have small per-variable gaps for 2 of 5 variables (the +75 vs 67 / +16 vs 15 discrepancies). The gap reflects aplus-bucket churn beyond strict watch->aplus transitions (aplus-baseline rows that stay aplus + are counted in the Matrix delta but absent from the drill-down's transition-only rows). LOCKed table:

| Variable | SUMMARY max_delta_aplus | drill-down watch->aplus count | gap | gap as % of max_delta |
|---|---|---|---|---|
| vcp.tightness_range_factor | 75 | 67 | 8 | ~11% |
| vcp.tightness_days_required | 16 | 15 | 1 | ~6% |
| vcp.adr_min_pct | 11 | 11 | 0 | 0% |
| vcp.proximity_max_pct | 5 | 5 | 0 | 0% |
| vcp.orderliness_max_bar_ratio | 1 | 1 | 0 | 0% |

The drill-down filter is the authoritative source for cohort identification (these are the actual transition-rows emitted to the V2 sensitivity drill-down). The SUMMARY TABLE's max_delta_aplus is the authoritative source for the binding signal headline. These are two different surfaces measuring related but non-identical quantities.

### Sec 2.3 Canonical evaluation filter (held FIXED per gotcha #33 third canonical application)

Per dispatch brief Sec 1.3 + cumulative gotcha #33 LOCK, the canonical evaluation filter is `composite_score >= 0.5 AND recency <= 365 days` (5-BD adjacency-merge applied post-filter). This filter is held FIXED across all 5 V2 substrates + the D2 EXPANDED bias-free baseline. Alternative scopes (composite>=0.7 + recency<=120d; composite>=0.5 + no recency; etc.) are NOT used to substitute the canonical density measurement or the compatibility narrative.

### Sec 2.4 Bias-free D2 EXPANDED N=71 baseline (Brief Amendment 2)

D2 EXPANDED Amendment 5 cohort (manifest [`exports/research/pattern-cohort-detection-20260526T000409Z/manifest.json`](../../exports/research/pattern-cohort-detection-20260526T000409Z/manifest.json)) is the unbiased reference:

- Universe size: 516 unique S&P 500 tickers (Brief Amendment 2 corrected from "88" in dispatch brief Sec 1.4 at operator greenlight 2026-05-26 PM)
- Input entries scanned: 2064 (= 516 tickers x 4 asof_date snapshots)
- Filtered W primary count: 71 (composite>=0.5 + recency<=365d + 5-BD adjacency-merged)
- Filtered density: 71 / 516 = 0.1376 W per ticker (the D_filt anchor)
- Source CSV SHA-256: `98214d29...e998de`

D_raw and canonical_survival_rate for the D2 baseline are NOT available in V1 because the D2 baseline run emitted manifest.json + summary.md but NOT results.csv (Option B fallback per operator greenlight 2026-05-26 PM). Banked V2 candidate: re-run D2 EXPANDED with results.csv emission enabled.

### Sec 2.5 Three metric families (Brief Amendment 3)

Per operator greenlight 2026-05-27 post-Slice-5 (resolution of methodological ambiguity between brief Sec 1.6 LOCK and brief Sec 0/1.7 narrative-anchor framing):

1. **Per-ticker productivity**: `D_filt = F / T` (brief Sec 1.6 LOCK). Given a V2-selected ticker, how many canonical-filtered W primaries has it produced historically?
2. **Substrate size + aggregate output**: T (unique substrate tickers) + F (canonical-filtered W primary count). How many actionable W patterns are available from the substrate as a whole?
3. **Survival quality**: `canonical_survival_rate = F / R_raw` at TWO denominators:
   - `canonical_survival_rate_c_0 = F / R_raw(c=0.0)` -- broadest denominator; all double_bottom_w primaries the detector emits via `pattern_cohort_evaluator` post-(ticker, trough_1_date)-highest-composite dedup
   - `canonical_survival_rate_c_0_5 = F / R_raw_c_0_5` -- R2-A/R2-D findings-doc-anchor framing; composite>=0.5 raw + 5-BD adjacency-merged denominator

Of raw W primaries detected on the substrate, what fraction are recent + high-composite enough to be actionable?

### Sec 2.6 Per-variable 3-axis profile tags (Brief Amendment 4)

Per operator-paired LOCK 2026-05-27 post-Slice-5: the investigation replaces the brief Sec 1.7 single-label compatibility verdict (COMPATIBLE / PARTIALLY-COMPATIBLE / INCOMPATIBLE) with per-variable 3-axis profile tags:

| Axis | Tag values | Thresholds |
|---|---|---|
| Per-ticker productivity | ENRICHED / TYPICAL / DEPLETED | ENRICHED: D_filt >= 10x baseline; TYPICAL: 2-10x; DEPLETED: <2x |
| Substrate size | SUFFICIENT / MARGINAL / INSUFFICIENT | SUFFICIENT: T>=20; MARGINAL: 5<=T<20; INSUFFICIENT: T<5 |
| Survival quality | COMPARABLE / DEGRADED / SUPPRESSED | COMPARABLE: c=0 survival >=10%; DEGRADED: 5-10%; SUPPRESSED: <5% |

These are descriptive substrate-characterization labels and are NOT verdict terminology. The investigation is ANALYTICAL not verdict-producing per cumulative gotcha #33 third canonical application REINFORCED; banned verdict terms `(PARTIAL POSITIVE, POSITIVE, NEGATIVE, INSUFFICIENT SAMPLE)` are NOT emitted by `synthesis.py` (BINDING discriminating test).

### Sec 2.7 Substrate characterization metrics (per dispatch brief Sec 1.5)

Per V2 substrate, computed at each cohort's (ticker, asof_date) snapshots:

- 90-day price return: pct change between (asof - 90 BD) close and asof close
- ATR%: mean trailing-20-BD ATR / asof close, expressed as percentage
- 52w high proximity (pct below): `(52w_high - asof_close) / 52w_high * 100`
- Sector: best-effort from finviz CSV (UNKNOWN fallback per V1 simplification; banked V2 candidate)

Per-cohort aggregates: median + IQR of each metric across the cohort + sector mix counts + unique ticker/pair counts.

OHLCV reads use `pd.read_parquet` directly on the legacy `.parquet` cache path; sidesteps the V2 reader's Shape A logic + fetch-on-miss path per gotcha #28 OHLCV cache discipline + brief Sec 6(d) "CLEAR ERROR + halt rather than fetch" prescription. `AsofDateMissingError` (Codex chain #1 R3-R4 hardening) raises if asof_date is not in the archive's DatetimeIndex.

---

## Sec 3 Cohort Detail

Per V2 substrate (LOCKED in [`research/harness/v2_selection_mechanic/__init__.py:BINDING_SIGNALS_TABLE`](../harness/v2_selection_mechanic/__init__.py)):

| Variable | Cohort CSV | Tickers (T) | (T, asof) unique pairs |
|---|---|---|---|
| vcp.tightness_range_factor | [`v2_tightness_range_factor_sp1_005.csv`](../../exports/research/cohorts/v2_tightness_range_factor_sp1_005.csv) | 15 (YOU / DK / SSRM / WULF / TSHA / NAT / RLMD / UCTT / PTEN / KOD / RNG / TROX / FRO / DNTH / OII) | 29 |
| vcp.tightness_days_required (REUSE R2-A) | [`r2a_tightness_days_required_sp1.csv`](../../exports/research/cohorts/r2a_tightness_days_required_sp1.csv) | 7 (FRO / KOD / NAT / OII / RLMD / SEI / TROX) | 7 |
| vcp.adr_min_pct (REUSE R2-D) | [`r2d_adr_min_pct_sp2_0.csv`](../../exports/research/cohorts/r2d_adr_min_pct_sp2_0.csv) | 4 (AMX / GLNG / STNG / XENE) | 4 |
| vcp.proximity_max_pct | [`v2_proximity_max_pct_sp7_5.csv`](../../exports/research/cohorts/v2_proximity_max_pct_sp7_5.csv) | 3 (SEI / YOU / SLDB) | 3 |
| vcp.orderliness_max_bar_ratio | [`v2_orderliness_max_bar_ratio_sp3_75.csv`](../../exports/research/cohorts/v2_orderliness_max_bar_ratio_sp3_75.csv) | 1 (LASR) | 1 |

Pre-flight archive refresh provenance per operator greenlight 2026-05-26 PM:
- SSRM refreshed 2026-05-26 20:00:47 via yfinance `period='max'` (was 11-day stale)
- SLDB refreshed 2026-05-26 20:00:48 via yfinance `period='max'` (was 27-day stale)
- 16 other unique tickers across the 18-ticker substrate set were within 1-4 day freshness window (no refresh applied per R2-A precedent)
- DK both-exist Shape A staleness left as-is per gotcha #24 L4 caveat (investigation uses legacy reader)

ZERO new Schwab API calls during the investigation; ZERO yfinance fetches at runtime; all OHLCV reads route through `read_legacy_archive` against the local cache.

---

## Sec 4 Substrate Characterization

Per-cohort regime fingerprint (median values; full per-(variable, ticker) detail in [`substrate_characterization.csv`](../../exports/research/v2-selection-mechanic-analysis-20260527T084319Z/substrate_characterization.csv)):

| Variable | 90d return median (%) | ATR%(20d) median | 52w prox median (%) | Dominant sector |
|---|---|---|---|---|
| vcp.tightness_range_factor | 65.03 | 5.56 | 8.69 | UNKNOWN (V1 sector resolution gap) |
| vcp.tightness_days_required | 64.49 | 5.54 | 8.78 | UNKNOWN |
| vcp.adr_min_pct | 40.31 | 2.94 | 4.53 | UNKNOWN |
| vcp.proximity_max_pct | 42.86 | 6.42 | 8.02 | UNKNOWN |
| vcp.orderliness_max_bar_ratio | 100.56 | 8.62 | 13.04 | UNKNOWN |

Observations:

- **Strong-uptrend bias across 4 of 5 V2 substrates** (90d returns 40-100%; well above broad-market norms). The V2 binding-variable selection is structurally biased toward tickers in strong recent uptrends -- these are the tickers most likely to be classified `watch` at baseline (their composite scores are near the A+ threshold; small criterion relaxation pushes them to aplus).
- **adr_min_pct substrate has materially LOWER volatility** (ATR% median 2.94% vs 5.5-8.6% for other substrates). The adr_min_pct binding variable selects low-ADR tickers by construction; this propagates to a low-volatility substrate where W amplitudes are likely structurally smaller + W detection rates lower (confirmed downstream by D_filt=1.0 vs 9-9.7 for other substrates).
- **orderliness_max_bar_ratio substrate** has the most-extreme 90d return (100.56% on the single LASR ticker; +106% over 90 BD) and 52w-high proximity (13.0% below high). Single-ticker substrate; interpretation is anecdotal.
- **Sector resolution UNKNOWN across all substrates** per V1 simplification (no finviz CSV passed to `--finviz-csv`). Banked V2 candidate: extend sector resolution to query the candidates table directly (per dispatch brief Sec 1.5 multi-source fallback).

---

## Sec 5 W-Density Analysis (per Brief Amendment 3 three-metric framing)

Per-cohort dual-density measurement from [`per_variable_signals.csv`](../../exports/research/v2-selection-mechanic-analysis-20260527T084319Z/per_variable_signals.csv) + [`w_density_detail.csv`](../../exports/research/v2-selection-mechanic-analysis-20260527T084319Z/w_density_detail.csv):

| Variable | T | R_raw (c=0) | R_raw (c>=0.5) | F | D_filt = F/T | survival (c=0) | survival (c>=0.5) | delta vs baseline (D_filt) |
|---|---|---|---|---|---|---|---|---|
| **D2 baseline** | **516** | **(n/a V1)** | **(n/a V1)** | **71** | **0.138** | **(n/a V1)** | **(n/a V1)** | **0.000** |
| vcp.tightness_range_factor | 15 | 2482 | 1940 | 137 | 9.13 | 5.5% | 7.1% | +8.996 |
| vcp.tightness_days_required | 7 | 1643 | 1259 | 64 | 9.14 | 3.9% | 5.1% | +9.005 |
| vcp.adr_min_pct | 4 | 173 | 132 | 4 | 1.00 | 2.3% | 3.0% | +0.862 |
| vcp.proximity_max_pct | 3 | 242 | 173 | 29 | 9.67 | 12.0% | 16.8% | +9.529 |
| vcp.orderliness_max_bar_ratio | 1 | 19 | 16 | 3 | 3.00 | 15.8% | 18.8% | +2.862 |

### Sec 5.1 Per-ticker productivity (D_filt) framing

Under D_filt = F/T (brief Sec 1.6 LOCK), ALL 5 V2 substrates dwarf the D2 baseline. The D_filt ratios vs baseline:

| Variable | D_filt | D_filt / baseline | Tag |
|---|---|---|---|
| vcp.tightness_range_factor | 9.13 | 66x | ENRICHED |
| vcp.tightness_days_required | 9.14 | 66x | ENRICHED |
| vcp.adr_min_pct | 1.00 | 7.2x | TYPICAL |
| vcp.proximity_max_pct | 9.67 | 70x | ENRICHED |
| vcp.orderliness_max_bar_ratio | 3.00 | 21.7x | ENRICHED |

Interpretation: V2-binding-variable selection systematically targets tickers that are HIGHLY W-pattern-productive on a historical-per-ticker basis. The adr_min_pct substrate is the only V2 cohort that lands in the TYPICAL band (still 7.2x baseline; just less extreme than the other 4 V2 substrates), consistent with its low-ADR substrate having structurally smaller W amplitudes + fewer detectable W structures per ticker over time.

### Sec 5.2 Substrate size + aggregate output framing

Under T + F absolute counts, ALL 5 V2 substrates are SMALL relative to the D2 baseline (T=516). In 3 of 5 cases T<5 (INSUFFICIENT). The aggregate F is correspondingly small:

| Variable | T | F | Size tag |
|---|---|---|---|
| vcp.tightness_range_factor | 15 | 137 | MARGINAL (5<=T<20) |
| vcp.tightness_days_required | 7 | 64 | MARGINAL |
| vcp.adr_min_pct | 4 | 4 | INSUFFICIENT (T<5) |
| vcp.proximity_max_pct | 3 | 29 | INSUFFICIENT |
| vcp.orderliness_max_bar_ratio | 1 | 3 | INSUFFICIENT |

Interpretation: substrate-size augmentation is required before per-ruleset evaluation (whether E or alternative) can achieve statistical defensibility. The aggregate F values are within an order of magnitude of D2's F=71 only for tightness_range_factor (F=137) and tightness_days_required (F=64); the other 3 V2 substrates have F in the single digits to 29, well below the statistical defensibility threshold typical for backtest classification.

### Sec 5.3 Survival quality framing

Under canonical_survival_rate = F / R_raw, V2 substrates are MIXED across the SUPPRESSED-COMPARABLE spectrum:

| Variable | survival (c=0) | survival (c>=0.5) | Survival tag |
|---|---|---|---|
| vcp.tightness_range_factor | 5.5% | 7.1% | DEGRADED |
| vcp.tightness_days_required | 3.9% | 5.1% | SUPPRESSED |
| vcp.adr_min_pct | 2.3% | 3.0% | SUPPRESSED |
| vcp.proximity_max_pct | 12.0% | 16.8% | COMPARABLE |
| vcp.orderliness_max_bar_ratio | 15.8% | 18.8% | COMPARABLE |

The two tightness-family variables (tightness_range_factor + tightness_days_required) and adr_min_pct have DEGRADED-to-SUPPRESSED survival; proximity_max_pct + orderliness_max_bar_ratio have COMPARABLE survival. This is methodologically interesting: the V2 binding variables that gate W-pattern visibility through tightness/volatility filters appear to select tickers where historical W patterns are MORE often disqualified by the canonical filter (composite>=0.5 + recency<=365d) than V2 binding variables that gate on proximity or orderliness. The R2-A rejecting Ruleset E verdict on the tightness_days_required substrate may be at least partially explained by this survival suppression: the surviving W patterns on those tickers may have systematically different quality profiles than the surviving W patterns on the baseline cohort.

### Sec 5.4 Cross-arc consistency check against R2-A/R2-D narrative anchors

R2-A findings doc Sec 2.1 cited the tightness_days_required substrate as "~13% substrate density" using the F/R_raw_c_0_5 framing. My measurement: F/R_raw_c_0_5 = 5.1% (about 2.5x lower than the narrative anchor). R2-D findings doc Sec 2.1 cited adr_min_pct as "~3%". My measurement: 3.0%. Match.

The tightness_days_required discrepancy (5.1% measured vs ~13% narrative) likely reflects extraction-parameter divergence between this investigation's `extract_primary_verdicts_from_csv(composite_threshold=0.5)` invocation and R2-A's underlying raw_w_count counting methodology. R2-A may have used a different upstream cohort scope or post-merge denominator. Banked V2 candidate: reconcile R2-A's denominator definition + recompute against the unified measurement framework.

R2-D's ~3% match for adr_min_pct is the cross-arc consistency check anchor; the methodological framework holds for that substrate.

---

## Sec 6 Cross-Variable Consistency Synthesis (Brief Amendment 4 per-variable narrative)

Per-variable narrative synthesis from [`compatibility_synthesis.md`](../../exports/research/v2-selection-mechanic-analysis-20260527T084319Z/compatibility_synthesis.md):

1. **vcp.tightness_range_factor (sp=1.005)**: V2 enriches per-ticker (D_filt=9.13, 66x baseline; ENRICHED); substrate marginal (T=15; MARGINAL); survival degraded (5.5%; DEGRADED). 137 canonical-filtered W primaries available -- the largest aggregate F across V2 substrates but still ~half of D2 baseline's F=71 per ticker amortized over a 30x smaller substrate.

2. **vcp.tightness_days_required (sp=1)**: V2 enriches per-ticker (D_filt=9.14, 66x baseline; ENRICHED); substrate marginal (T=7); survival suppressed (3.9%; SUPPRESSED). R2-A's prior rejecting Ruleset E verdict on this substrate (N=65 filtered W primaries; this investigation's recount = N=64; ~1-ticker discrepancy likely from D1 backtest's cohort-specific filter parameters) is consistent with substrate-size + survival-quality limitations rather than per-ticker productivity deficit.

3. **vcp.adr_min_pct (sp=2.0)**: V2 weakly enriches per-ticker (D_filt=1.00, 7.2x baseline; TYPICAL); substrate insufficient (T=4); survival suppressed (2.3%). R2-D's prior insufficient-sample finding on this substrate (N=4) is structural -- the low-ADR substrate produces materially fewer historical W patterns per ticker AND has the lowest survival rate among the 5 V2 substrates. Among the V2 binding variables, adr_min_pct is the cohort selection mechanism most likely to produce W-pattern-thin substrates by all three metric families simultaneously.

4. **vcp.proximity_max_pct (sp=7.5)**: V2 enriches per-ticker (D_filt=9.67, 70x baseline; ENRICHED); substrate insufficient (T=3); survival COMPARABLE to other comparison cohorts (12.0%). This V2 binding variable produces the strongest single-axis profile mismatch -- high per-ticker productivity + comparable survival but insufficient substrate size for defensible evaluation.

5. **vcp.orderliness_max_bar_ratio (sp=3.75)**: V2 enriches per-ticker (D_filt=3.00, 22x baseline; ENRICHED); substrate single-ticker (T=1; INSUFFICIENT); survival COMPARABLE (15.8%). The +1 max_delta_aplus binding signal is the weakest in the V2 sensitivity SUMMARY TABLE; the single-ticker substrate (LASR) cannot support per-ruleset evaluation independent of LASR-specific noise.

Cross-variable consistency claim: 4 of 5 V2 substrates land in the ENRICHED productivity band; 1 lands in TYPICAL. 0 of 5 land in DEPLETED. The dominant cross-variable signal under D_filt framing is **substrate enrichment**, not **substrate depletion**. The dominant cross-variable signal under survival-rate framing is **bimodal**: the two tightness-family variables + adr_min_pct show DEGRADED-to-SUPPRESSED survival; proximity_max_pct + orderliness_max_bar_ratio show COMPARABLE survival.

---

## Sec 7 R2-A + R2-D + D1 + D2 Backtest Carryover

The prior backtest arcs provide cross-arc context that this analytical investigation references but does NOT recompute:

- **D1 double_bottom_w walk-forward backtest** (`exports/research/double-bottom-w-backtest-20260525T123756Z/`): tightness_range_factor sp=1.005 cohort (D1's hand-curated +67 CSV) yielded the headline rejecting result that motivated investigation of whether V2 binding variables produce substrates compatible with Ruleset E deployment. D1's outcome was bounded by the substrate-size + survival-suppression limitations now characterized for tightness_range_factor at MARGINAL + DEGRADED.
- **D2 W-bottom ruleset comparison** (S&P 500 EXPANDED N=71 cohort): the bias-free baseline against which V2 substrates are characterized. D2's per-ruleset outcome (Ruleset E partial-positive on N=26 most-recent recency-filtered S&P 500 candidates per D2 Amendment 5) established the analytical reference for "what Ruleset E looks like on a substrate-size-sufficient bias-free cohort."
- **R2-A V2 tightness_days_required cohort backtest** (N=65): rejecting Ruleset E verdict on this substrate. This investigation's measurement (D_filt=9.14 ENRICHED; T=7 MARGINAL; survival=3.9% SUPPRESSED) characterizes the substrate as enriched-but-too-small + survival-suppressed -- supporting the cohort-validity-vs-verdict-criteria interpretation per gotcha #33 third canonical application: the rejecting verdict reflects substrate-size + survival-quality limitations, not low per-ticker W incidence.
- **R2-D V2 adr_min_pct cohort backtest** (N=4): insufficient-sample finding. This investigation's measurement (D_filt=1.00 TYPICAL; T=4 INSUFFICIENT; survival=2.3% SUPPRESSED) confirms the structural cause -- adr_min_pct's low-ADR substrate produces materially fewer historical W patterns AND has the lowest survival rate of the 5 V2 substrates.

The cross-arc finding is that V2-binding-variable cohort selection is **NOT systematically incompatible** with Ruleset E deployment in the sense of producing W-pattern-depleted substrates. V2 substrates ARE W-productive on a per-ticker basis (7-70x baseline). The constraint on V2 deployment is **substrate-size augmentation** + **survival-quality validation** -- the same constraints that would apply to ANY narrow cohort selection mechanism deployed against a 365-day-recency canonical filter.

---

## Sec 8 Compatibility Synthesis (per-variable narrative; NOT a single global label per Brief Amendment 4)

The investigation produces per-variable narrative synthesis rather than a single COMPATIBLE / PARTIALLY-COMPATIBLE / INCOMPATIBLE label (Brief Amendment 4 operator-paired LOCK):

**Compatibility narrative**: V2 OHLCV binding-variable cohort selection produces substrates that are systematically ENRICHED for W-pattern productivity on a per-ticker basis (D_filt = 7-70x bias-free baseline), but substrate SIZE is too small for defensible per-ruleset evaluation under the canonical filter (T<=15 in all 5 cases; T<5 in 3 of 5; baseline T=516). The "substrate thinness" framing in prior R2-A and R2-D findings docs was a function of small substrate size T, not low per-ticker W-pattern incidence -- V2 substrates produce W patterns in greater per-ticker abundance than the baseline.

R2-A's prior rejecting Ruleset E verdict on tightness_days_required substrate (N=65) and R2-D's insufficient-sample finding on adr_min_pct substrate (N=4) are NOT consequences of V2 substrates being W-pattern-depleted. Rather, they reflect: (a) too few V2-selected tickers to amortize per-ruleset evaluation noise, and (b) DEGRADED-to-SUPPRESSED canonical survival rates on the tightness-family V2 variables that may indicate the surviving W patterns have systematically different quality profiles.

V2 selection for production deployment of Ruleset E would benefit from substrate-size augmentation (broader watch->aplus flip aggregation across multiple binding variables OR longer recency window OR composite-threshold relaxation) before per-ruleset evaluation can discriminate cohort-specific rejecting outcomes from substrate-size-driven sampling noise.

For backward-compat the legacy F/T-only categorical label per pre-Amendment-4 brief Sec 1.7 yields **COMPATIBLE** under D_filt LOCK (0 below-baseline; 5 at-or-above-baseline). This label is preserved in the manifest for backward compat ONLY; the dominant analytical surface is the per-variable 3-axis profile above.

---

## Sec 9 Methodological Caveats + L-Style Limitations

**L-style limitations** (architectural caveats; not investigation-specific defects):

- **L4-style: D_raw + canonical_survival_rate UNAVAILABLE for D2 baseline.** The D2 baseline run (manifest 20260526T000409Z) emitted manifest.json + summary.md but NOT results.csv. The canonical_survival_rate baseline anchor cannot be computed from the V1 artifacts; the investigation surfaces survival rates for V2 substrates only. Per-V2-substrate survival rate is interpretable in absolute terms (5-19% range) but the comparison-to-baseline survival delta is not measurable in V1. Banked V2 candidate: re-run D2 EXPANDED with results.csv emission enabled (extends gotcha #28+29 OHLCV cache discipline family).

- **L5-style: V2 cohort raw_w_count counting methodology vs R2-A/R2-D narrative anchors.** The R2-A findings doc cites ~13% substrate density for tightness_days_required using a F/R_raw_c_0_5 framing; my measurement is 5.1%. The discrepancy likely reflects extraction-parameter divergence between this investigation's `extract_primary_verdicts_from_csv` invocation and R2-A's underlying raw_w_count methodology. The R2-D anchor (~3% for adr_min_pct) reproduces in this investigation (3.0%). Banked V2 candidate: reconcile R2-A's denominator definition + recompute against the unified measurement framework.

- **L6-style: sector resolution V1 SIMPLIFICATION.** All 5 V2 substrates show dominant_sector=UNKNOWN per V1 simplification (no finviz CSV passed). Banked V2 candidate: extend sector resolution to query the candidates table directly (per dispatch brief Sec 1.5 multi-source fallback). Sector mix is documented in the artifact CSVs but not used for the analytical synthesis.

- **L7-style: substrate characterization OHLCV reads.** Per gotcha #28 OHLCV cache discipline + brief Sec 6(d), this investigation reads legacy parquet archives via `pd.read_parquet` directly + sidesteps the V2 reader's Shape A logic + fetch-on-miss path. Pre-flight refresh state per operator greenlight 2026-05-26 PM covers the 18-ticker substrate set; DK both-exist Shape A staleness left as-is per gotcha #24 L4-caveat (investigation uses legacy reader). 90-day return + ATR + 52w proximity metrics require 91 / 21 / 252 BD of historical depth respectively (Codex chain #1 R1 + R4 BINDING enforcement).

- **L8-style: per-ruleset P&L NOT recomputed.** Per dispatch brief Sec 1.8: the investigation is ANALYTICAL not a backtest. Per-ruleset P&L outcomes were established by R2-A + R2-D + D1 + D2 backtest arcs and are referenced contextually but NOT recomputed. The investigation does NOT extend or modify the prior backtest verdicts.

**Cumulative gotchas applied:**

- #34 FIRST + SECOND canonical applications: BINDING_SIGNALS_TABLE cross-table verification (SUMMARY vs Sensitivity Matrix) + NON_WATCH_TRANSITION_GAP_TABLE LOCK
- #33 third canonical application REINFORCED: banned verdict terms not emitted; per-variable 3-axis profile tags are descriptive substrate-characterization labels
- #28 + #29 OHLCV cache discipline: archive-miss raises `CacheMissError`; weekend/holiday asof raises `AsofDateMissingError`
- #32 ASCII discipline: declared scope across all NEW Python + Markdown + CSV files
- #31 narrative artifact path/fact lag: post-fix sweep BINDING for any Codex chain #2 fix bundles

---

## Sec 10 V2 Candidates + Future Work

Per investigation greenlight + Codex chain #1 review:

1. **D2 baseline results.csv re-emission.** Re-run D2 EXPANDED with results.csv emission enabled to capture raw-density + canonical-survival-rate baseline anchor. Closes L4-style limitation above.

2. **R2-A raw_w_count methodology reconciliation.** Investigate the extraction-parameter divergence between this investigation's measurement (5.1% c>=0.5 survival on tightness_days_required substrate) and R2-A findings doc's "~13%" narrative anchor.

3. **Substrate-size augmentation experiments.** Aggregate watch->aplus flips across multiple V2 binding variables to construct a substrate-size-sufficient (T>=20) V2-style cohort for defensible per-ruleset evaluation. Test whether the cohort-specific R2-A rejecting outcome reproduces under a substrate-size-sufficient augmented cohort.

4. **Sector resolution V1 -> V2 hardening.** Extend sector resolution to query the candidates table directly per dispatch brief Sec 1.5 multi-source fallback.

5. **Pre-Codex review expansion candidate: substrate density metric disambiguation.** When a dispatch brief references prior-arc "density" numerical anchors, the brief MUST cite the exact denominator + numerator definitions used by the prior arc. Banked as Expansion #19 cumulative gotcha candidate per operator-paired LOCK 2026-05-27 (subject to post-merge housekeeping confirmation after Codex chain #2 convergence).

6. **Sibling-module strategy continuation.** The 3 NEW sibling cohort modules (v2_tightness_range_factor / v2_proximity_max_pct / v2_orderliness_max_bar_ratio) port the R2-A + R2-D template architecture. Common-parser refactor remains banked V2 candidate per sibling-module strategy LOCK.

7. **Immutable archive snapshot for V2-style readers.** Per gotcha #26 (archive bar-content TEMPORAL mutation): a future investigation that requires byte-identical archive contents between V1 persistence time and V2 invocation time should adopt immutable archive snapshots. This investigation reads the current legacy archive state and is not directly affected because all metrics are computed at investigation-current asof_dates (no V1 persisted state replay).

---

*End of V2-selection-mechanic analytical investigation study writeup. Smoke artifact at `exports/research/v2-selection-mechanic-analysis-20260527T084319Z/`. Codex chain #2 review pending; findings doc + return report follow at Slice 8. ZERO production swing/ writes; ZERO new Schwab API calls; ZERO Co-Authored-By trailer drift across the V2-selection-mechanic investigation commit chain.*
