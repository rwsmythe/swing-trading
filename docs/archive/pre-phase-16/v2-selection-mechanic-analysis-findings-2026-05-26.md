# V2-Selection-Mechanic Analysis -- Findings Doc

**Investigation:** ANALYTICAL / EXPLORATORY (NOT a backtest); examines WHY V2-binding-variable cohort selection produces W-pattern-thin substrates per cumulative cross-cohort finding (R2-A rejecting Ruleset E + R2-D inadequate-N finding vs D2 EXPANDED N=71 baseline).

**Study writeup (primary artifact):** [`research/studies/2026-05-26-v2-selection-mechanic-analysis.md`](../research/studies/2026-05-26-v2-selection-mechanic-analysis.md)
**Smoke artifact:** [`exports/research/v2-selection-mechanic-analysis-20260527T084319Z/`](../exports/research/v2-selection-mechanic-analysis-20260527T084319Z/)
**Return report:** [`docs/v2-selection-mechanic-analysis-return-report.md`](v2-selection-mechanic-analysis-return-report.md)
**Branch:** `applied-research-v2-selection-mechanic-investigation` at HEAD `9c6cea6` (Slice 6 Codex chain #2 converged); branched from `main` at `55d0f48`.

---

## Sec 1 Headline Finding

V2 OHLCV binding-variable cohort selection produces substrates that are systematically ENRICHED for W-pattern productivity on a per-ticker basis (D_filt = 7.2x-70x the D2 EXPANDED bias-free baseline of 0.138 W per ticker), but substrate SIZE is too small for defensible per-ruleset evaluation under the canonical filter (T<=15 in all 5 cases; T<5 in 3 of 5; baseline T=516). The cross-cohort "substrate thinness" framing in R2-A and R2-D findings docs was a function of small substrate size T, not low per-ticker W-pattern incidence.

Per Brief Amendment 4 the investigation produces per-variable 3-axis profile tags (productivity / substrate-size / survival-quality) rather than a single COMPATIBLE / PARTIALLY-COMPATIBLE / INCOMPATIBLE label:

| Variable | sweep_point | 3-axis profile |
|---|---|---|
| vcp.tightness_range_factor | 1.005 | ENRICHED + MARGINAL(T=15) + DEGRADED(5.5%) |
| vcp.tightness_days_required | 1.0 | ENRICHED + MARGINAL(T=7) + SUPPRESSED(3.9%) |
| vcp.adr_min_pct | 2.0 | TYPICAL + INSUFFICIENT(T=4) + SUPPRESSED(2.3%) |
| vcp.proximity_max_pct | 7.5 | ENRICHED + INSUFFICIENT(T=3) + COMPARABLE(12.0%) |
| vcp.orderliness_max_bar_ratio | 3.75 | ENRICHED + INSUFFICIENT(T=1) + COMPARABLE(15.8%) |

---

## Sec 2 Cross-Variable Density Delta Table

Per the smoke artifact at [`v2-selection-mechanic-analysis-20260527T084319Z/per_variable_signals.csv`](../exports/research/v2-selection-mechanic-analysis-20260527T084319Z/per_variable_signals.csv):

| Variable | T | R_raw(c=0) | R_raw(c>=0.5) | F | D_filt = F/T | D_filt / baseline | survival(c=0) | survival(c>=0.5) |
|---|---|---|---|---|---|---|---|---|
| **D2 EXPANDED baseline** | 516 | (n/a V1) | (n/a V1) | 71 | 0.138 | 1.0x | (n/a V1) | (n/a V1) |
| vcp.tightness_range_factor | 15 | 2482 | 1940 | 137 | 9.13 | 66x | 5.5% | 7.1% |
| vcp.tightness_days_required | 7 | 1643 | 1259 | 64 | 9.14 | 66x | 3.9% | 5.1% |
| vcp.adr_min_pct | 4 | 173 | 132 | 4 | 1.00 | 7.2x | 2.3% | 3.0% |
| vcp.proximity_max_pct | 3 | 242 | 173 | 29 | 9.67 | 70x | 12.0% | 16.8% |
| vcp.orderliness_max_bar_ratio | 1 | 19 | 16 | 3 | 3.00 | 22x | 15.8% | 18.8% |

D_raw_baseline + canonical_survival_rate_baseline UNAVAILABLE in V1 because D2 baseline run emitted manifest.json + summary.md but NOT results.csv (Option B fallback per operator greenlight 2026-05-26 PM; banked V2 candidate).

---

## Sec 3 Per-Variable Regime Fingerprint Table

Per [`substrate_characterization.csv`](../exports/research/v2-selection-mechanic-analysis-20260527T084319Z/substrate_characterization.csv) (median across the cohort):

| Variable | 90d return median (%) | ATR%(20d) median | 52w prox median (%) | Dominant sector |
|---|---|---|---|---|
| vcp.tightness_range_factor | 65.03 | 5.56 | 8.69 | UNKNOWN (V1 simplification) |
| vcp.tightness_days_required | 64.49 | 5.54 | 8.78 | UNKNOWN |
| vcp.adr_min_pct | 40.31 | 2.94 | 4.53 | UNKNOWN |
| vcp.proximity_max_pct | 42.86 | 6.42 | 8.02 | UNKNOWN |
| vcp.orderliness_max_bar_ratio | 100.56 | 8.62 | 13.04 | UNKNOWN |

Observations:
- Strong-uptrend bias across 4 of 5 V2 substrates (90d returns 40-100%)
- adr_min_pct substrate has materially LOWER volatility (ATR% 2.94 vs 5.5-8.6); structurally smaller W amplitudes
- orderliness_max_bar_ratio single-ticker substrate (LASR) has extreme metrics (90d return 100.56%); interpretation anecdotal

---

## Sec 4 R2-A + R2-D Carryover Synthesis

| Prior arc | Result | This investigation's interpretation |
|---|---|---|
| R2-A V2 tightness_days_required (N=65) | Rejecting Ruleset E verdict | Substrate at MARGINAL(T=7) + SUPPRESSED(3.9% survival); rejecting verdict reflects substrate-size + survival-quality limitations rather than W-depletion (D_filt=9.14 ENRICHED at 66x baseline) |
| R2-D V2 adr_min_pct (N=4) | Insufficient-sample finding | Substrate at INSUFFICIENT(T=4) + SUPPRESSED(2.3% survival); structural cause confirmed (low-ADR substrate produces fewer W patterns AND has lowest survival rate of 5 V2 substrates) |
| D1 tightness_range_factor sp=1.005 walk-forward backtest | Rejecting headline result | Substrate at MARGINAL(T=15) + DEGRADED(5.5% survival); consistent with the substrate-size limitations now characterized |
| D2 EXPANDED N=71 (S&P 500 bias-free) | Bias-free reference | The unbiased baseline against which V2 substrates are characterized; D_filt baseline = 71/516 = 0.138 |

Cross-arc finding: V2 substrates ARE W-productive per-ticker (7-70x baseline). The constraint on V2 deployment is substrate-size augmentation + survival-quality validation, NOT W-pattern depletion.

R2-A cross-arc consistency check: R2-A findings doc Sec 2.1 cited "~13% substrate density" (F/R_raw_c_0_5 framing). This investigation's measurement: 5.1%. ~2.5x discrepancy; L5-style limitation banked V2 candidate (likely extraction-parameter divergence between this investigation's `extract_primary_verdicts_from_csv` invocation + R2-A's underlying raw_w_count methodology). R2-D anchor (~3%) reproduces in this investigation (3.0%; match).

---

## Sec 5 Compatibility Verdict (Narrative; per Brief Amendment 4)

V2 OHLCV binding-variable cohort selection produces substrates that are systematically ENRICHED for W-pattern productivity on a per-ticker basis. The "substrate thinness" framing in prior R2-A and R2-D findings docs was a function of small substrate size T, not low per-ticker W-pattern incidence. R2-A's prior rejecting Ruleset E verdict on tightness_days_required substrate (N=65) and R2-D's insufficient-sample finding on adr_min_pct substrate (N=4) reflect substrate-size + survival-quality limitations rather than W-pattern depletion.

V2 selection for production deployment of Ruleset E would benefit from substrate-size augmentation (broader watch->aplus flip aggregation across multiple binding variables; longer recency window; or composite-threshold relaxation) before per-ruleset evaluation can discriminate cohort-specific rejecting outcomes from substrate-size-driven sampling noise.

Per gotcha #33 third canonical application LOCK: the investigation is ANALYTICAL not verdict-producing. The 3-axis profile tags + categorical labels ENRICHED/TYPICAL/DEPLETED/SUFFICIENT/MARGINAL/INSUFFICIENT/COMPARABLE/DEGRADED/SUPPRESSED are descriptive substrate-characterization labels; they are NOT verdict terminology. The four banned verdict-style labels (BANNED_VERDICT_TERMS in `synthesis.py`) are not emitted by the analytical synthesis (BINDING discriminating test).

---

## Sec 6 V2 Candidates Banked

1. **D2 baseline results.csv re-emission.** Re-run D2 EXPANDED with results.csv emission enabled to capture raw-density + canonical-survival-rate baseline anchor (closes L4-style limitation; UNAVAILABLE in V1 per Option B fallback).
2. **R2-A raw_w_count methodology reconciliation.** Investigate extraction-parameter divergence between this investigation's 5.1% measurement vs R2-A findings doc's ~13% narrative anchor for tightness_days_required (closes L5-style limitation).
3. **Substrate-size augmentation experiments.** Aggregate watch->aplus flips across multiple V2 binding variables to construct a substrate-size-sufficient (T>=20) V2-style cohort for defensible per-ruleset evaluation; test whether the cohort-specific R2-A rejecting outcome reproduces under a substrate-size-sufficient augmented cohort.
4. **Sector resolution V1 -> V2 hardening.** Extend sector resolution to query the candidates table directly per dispatch brief Sec 1.5 multi-source fallback (closes L6-style limitation; all 5 V2 substrates show dominant_sector=UNKNOWN in V1).
5. **Pre-Codex review Expansion #19 candidate:** substrate density metric disambiguation -- when a dispatch brief references prior-arc "density" numerical anchors, the brief MUST cite exact denominator + numerator definitions. Banked for post-merge CLAUDE.md gotcha discipline expansion.
6. **Common-parser refactor for sibling cohort modules.** R2-A + R2-D + v2_tightness_range_factor + v2_proximity_max_pct + v2_orderliness_max_bar_ratio share template architecture; common-parser refactor remains banked per sibling-module strategy LOCK.
7. **Immutable archive snapshot for V2-style readers** (per gotcha #26 family). Not directly affecting this investigation (no V1 persisted state replay), but a forward-binding candidate for future investigations that require byte-identical archive contents between V1 persistence + V2 invocation.
8. **Codex chain #2 Round 2 hedging-tightening (CLOSED at `9c6cea6`).** Pre-emptive language tightening on causal claims; already addressed in study writeup Sec 5.3.

---

## Sec 7 Codex MCP Review Summary

**Chain #1** (code review; slices 1-5; 5 rounds; converged at R5 NO_NEW_CRITICAL_MAJOR):

| Round | C | M | m | Action |
|---|---|---|---|---|
| R1 | 2 | 4 | 0 | All 6 closed in-place (`47f0912`) |
| R2 | 0 | 3 | 1 | All 4 closed (`24e79ef`); 3 R1-fix cascade regressions per gotcha #21 |
| R3 | 0 | 3 | 1 | 3 MAJOR closed (`9097f08`); 1 MINOR deferred V2 (sibling-module LOCK preserved) |
| R4 | 0 | 2 | 1 | All 3 closed (`e78fb77`) |
| R5 | 0 | 0 | 0 | CONVERGENCE |

Cumulative chain #1: 2 CRITICAL + 12 MAJOR + 3 MINOR (17 findings); 16 closed in-place; 1 MINOR banked V2 candidate.

**Chain #2** (study writeup methodology review; slice 6; 2 rounds; converged at R2 NO_NEW_CRITICAL_MAJOR):

| Round | C | M | m | Action |
|---|---|---|---|---|
| R1 | 0 | 3 | 1 | All 4 closed (`fcc5e37`); banned-term substrings + tightness_range_factor arithmetic + survival-range understatement |
| R2 | 0 | 0 | 1 | MINOR closed (`9c6cea6`); CONVERGENCE |

Cumulative chain #2: 0 CRITICAL + 3 MAJOR + 2 MINOR (5 findings); all 5 closed in-place.

**Total Codex chain ledger across both chains: 2 CRITICAL + 15 MAJOR + 5 MINOR (22 findings); 21 closed in-place; 1 MINOR banked V2.**

**43rd cumulative C.C lesson #6 validation slot spans BOTH chains (per operator-paired LOCK 2026-05-26 PM + 2026-05-27).**

---

## Sec 8 Discipline Preservation Summary

| Discipline | Status |
|---|---|
| ZERO production swing/ writes | Preserved |
| ZERO new Schwab API calls (L2 LOCK) | Preserved + REINFORCED via 5+ source-grep tests parametrized over NEW module set |
| ZERO yfinance imports at runtime (gotcha #28+29) | Preserved; OHLCV reads via `pd.read_parquet` directly + `CacheMissError` + `AsofDateMissingError` strict guards |
| Schema v21 unchanged | Preserved (zero migrations) |
| ASCII discipline (gotcha #32) | Declared scope + programmatic verification across module + test + narrative files |
| Banned verdict terms (gotcha #33) | Locked via discriminating test + Codex chain #2 R1 fix bundle (rephrased 2 prior-arc citations to abstract references) |
| Cross-table verification (gotcha #34 FIRST + SECOND canonical application) | BINDING_SIGNALS_TABLE + NON_WATCH_TRANSITION_GAP_TABLE LOCKed via programmatic test |
| Co-Authored-By trailer drift | ZERO across the V2-selection-mechanic investigation commit chain (~16 commits) |
| Sibling-module strategy LOCK | Preserved (3 NEW sibling cohort modules + REUSE R2-A + R2-D; no common-parser refactor) |

---

## Sec 9 L-Style Caveats

- **L4-style** (D2 baseline canonical_survival_rate UNAVAILABLE): D2 baseline run did not emit results.csv at baseline-run time; Option B fallback per orchestrator greenlight. Banked V2 candidate.
- **L5-style** (R2-A "~13%" narrative anchor reconciliation): this investigation's measurement (5.1% c>=0.5) is ~2.5x lower than R2-A findings doc's narrative anchor. Likely extraction-parameter divergence; banked V2 candidate for reconciliation.
- **L6-style** (sector resolution V1 SIMPLIFICATION): all 5 V2 substrates show dominant_sector=UNKNOWN; V1 simplification per operator-paired carve-out. Banked V2 candidate.
- **L7-style** (substrate characterization OHLCV reads): legacy parquet via `pd.read_parquet` directly + strict asof + sufficient-history guards (Codex chain #1 R1+R3+R4 hardening). Pre-flight refresh state per operator greenlight covers the 18-ticker substrate set.
- **L8-style** (per-ruleset P&L NOT recomputed): per dispatch brief Sec 1.8, the investigation is ANALYTICAL not a backtest. Per-ruleset P&L outcomes were established by R2-A + R2-D + D1 + D2 backtest arcs and are referenced contextually but NOT recomputed.

---

*End of V2-selection-mechanic investigation findings doc. Primary artifact at `research/studies/2026-05-26-v2-selection-mechanic-analysis.md`. Return report at `docs/v2-selection-mechanic-analysis-return-report.md`. ZERO production swing/ writes; ZERO new Schwab API calls; ZERO Co-Authored-By trailer drift across the investigation commit chain.*
