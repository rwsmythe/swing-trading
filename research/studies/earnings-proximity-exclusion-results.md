# Earnings-Proximity Exclusion — Evidence Summary

**Method record:** `../method-records/earnings-proximity-exclusion.md`
**Study design:** `./earnings-proximity-exclusion.md`
**Status:** FINAL.
**Pre-registration commit:** `0e04079` (SHA prefix; full SHA in `git log`).
**Study-run commit (raw outputs):** `e5510a8`.
**Decision:** **`defer`**.

---

## Pre-registration

*This section was committed BEFORE the study runs (D1, commit `0e04079`). Subsequent sections were filled in D4 after D3's output (commit `e5510a8`) was observed. Pre-registration prevents post-hoc rationalization per the study design's Survivorship-bias interpretation protocol (`./earnings-proximity-exclusion.md` §"Survivorship-bias interpretation protocol", amended 2026-04-24).*

### Sample-size estimate

Arithmetic, recorded BEFORE any D3 output is viewed:

- **Universe:** 517 tickers (SPX + NASDAQ-100 constituents per `reference/rs-universe.csv` v2026-04-24-1).
- **Replay window:** 504 NYSE trading days (≈ 2 calendar years) ending on the last completed session before Session 2c runs.
- **Ticker-days:** 517 × 504 ≈ **260,568**.
- **Baseline A+ rate anchor:** Session 2a audit of the production `candidates` table (`../notes/historical-candidate-source-decision.md`) found **2 distinct (ticker, `action_session_date`) A+ pairs across 5 trading days with ~80 Finviz-filtered tickers per day**. That implies a point estimate of ~0.5 % A+ rate per ticker-day, with a Wilson 95 % CI on 2/400 of roughly [0.11 %, 1.81 %] — i.e., extremely uncertain.
- **Extrapolation to the replay:** Applying the anchor point estimate to 260,568 ticker-days yields ≈ **1,300 A+ signals expected across the full window**, with a CI-propagated plausible range of roughly **290 to 4,700 signals** (≈ 0.6 – 9.4 per trading day). The anchor rate is known to be biased — production is Finviz-pre-screened (tighter filter than raw SPX+NDX membership, but with explicit price-momentum elements the replay universe lacks). The propagated CI is wide enough that both a "signal-starved" result (~300 total) and a "signal-rich" result (~2,000+) are pre-registered as plausible.
- **Triggering attrition estimate:** Swing-trading literature and the advisory's stop semantics suggest ≈ 30 – 60 % of A+ signals trigger within the 10-bar scan. Midpoint: 40 %. **Expected triggered trades per variant (before X-filtering): ≈ 400 (range 90 – 1,900).**
- **Stopped-trade rate estimate:** Typical trend-following setups stop out 30 – 50 % of triggered trades. Midpoint: 35 %. **Expected stopped trades per variant: ≈ 140 (range 30 – 700).**
- **Gap-through event rate:** Plausible range 10 – 25 % of stopped trades at baseline X=0. **Expected gap-through events per variant: ≈ 15 – 40 (range low end 3 – 170).**

**Interpretation for power.** With an anchor-implied median expectation of ≈ 140 stopped trades per variant and ≈ 20 gap-through events per variant, the Wilson 95 % CI half-width on the gap-through rate is on the order of ±8 – 10 percentage points. That is wide enough that effect sizes below roughly 5 pp will not clear statistical-significance gates, independent of their tier mapping. Effect-size-driven tier assignment (below) does NOT require significance to hit "strong"; CIs are reported for transparency and to flag power-limited ambiguity.

**Anti-over-precision note.** The anchor is n=2 successes over 400 ticker-days from one week of live operation. Any point-estimate language in the above is an order-of-magnitude scaffold, not a prediction. The observed D3 signal count is free to be anywhere in the 290 – 4,700 range without invalidating the pre-registration. Observed values far outside that range (e.g., <100 or >10,000) will be flagged as a model-mismatch finding in Open Issues; they do NOT automatically change the pre-registered tier mappings.

### Decision-tier thresholds per metric

All thresholds are on the DELTA of the variant vs the X=0 baseline. Deltas are signed such that POSITIVE means the rule improved the outcome.

| Metric | Strong (`promote`) | Moderate (`shadow`) | Weak / null band (`defer`) | Negative (`reject`) |
|---|---|---|---|---|
| **Expectancy delta (R/trade)** | ≥ +0.10 R | +0.03 R to +0.10 R | −0.03 R to +0.03 R | < −0.03 R |
| **Gap-through rate reduction (pp)** | ≥ 5 pp | 2 pp to 5 pp | −1 pp to +2 pp | worsens by > 1 pp |
| **Gap-through magnitude reduction (R)** | ≥ 0.15 R | 0.05 R to 0.15 R | −0.05 R to +0.05 R | magnitude grows by > 0.05 R |
| **Signal-volume cost (% loss vs X=0)** | ≤ 15 % | 15 % to 30 % | 30 % to 50 % | > 50 % |

**Notes on calibration (recorded BEFORE results are seen):**

- **Expectancy 0.10 R strong threshold.** A trend-template setup with initial-stop risk-per-share typically shows baseline expectancy in the 0.2 – 0.6 R range; a 0.10 R delta is a 15 – 50 % relative improvement — material at the operator level without being implausibly large.
- **Gap-through rate 5 pp strong threshold.** At a plausible baseline of ~15 – 25 % gap-through rate, 5 pp is a 20 – 33 % relative reduction — what an operator would notice in journaling.
- **Gap-through magnitude 0.15 R strong threshold.** A typical gap-through is roughly −1.5 R to −2.0 R (i.e., 0.5 – 1.0 R beyond stop). A 0.15 R magnitude reduction is 15 – 30 % of the typical overshoot, on the right order of magnitude to matter for drawdown.
- **Signal-volume 15 % strong threshold.** Quarterly earnings cadence means ~5 trading days per 63 are within X=5 of earnings per ticker, giving a naive ~8 % exclusion rate. 15 % accommodates clustering (earnings seasons) without licensing a pruning rule that quietly halves signal supply.
- **Deliberate asymmetry between "defer" and "reject."** The weak/null bands for expectancy and gap-through rate are intentionally narrow (±0.03 R, ±1 – 2 pp); the reject tier requires material harm, not just "not better." Survivorship bias understates benefit, so the anti-rationalization clause below routes weak/null to `defer` — only outright harm triggers `reject`.
- **Signal-volume is the only metric whose "negative" tier is based on magnitude rather than direction.** A positive expected-signal-volume delta (X=N yields MORE signals than X=0) is structurally impossible since X filtering is monotonically reductive. The "reject" band therefore measures severity of the rule's trade-off, not a sign flip.

### Combined tier-assignment rule

The four per-metric tiers above are resolved into a single variant-level decision as follows. The rule is pre-registered so the resolution of inter-metric conflicts (e.g., expectancy says Strong but signal-volume says Reject) is not an analyst judgment call after D3.

1. **Reject** (this variant): signal-volume cost > 50 % **OR** expectancy delta < −0.03 R with no compensating gap-metric improvement (neither gap-through-rate reduction nor gap-magnitude reduction reaches Moderate).
2. **Promote** (this variant): expectancy delta ≥ +0.10 R **AND** gap-through rate reduction ≥ 5 pp **AND** signal-volume cost ≤ 15 % **AND** Wilson 95 % CI lower bound on gap-through rate reduction > 0 pp (i.e., the reduction is statistically reliable as distinct from zero) **AND** all sensitivity checks pass (see below). If multiple X values qualify, pick the smallest X that meets all criteria, in the spirit of the "simplest rule that works" norm.
3. **Shadow** (this variant): at least ONE metric at Strong **AND** all other metrics at Moderate or better **AND** signal-volume cost ≤ 30 % — but does not meet the Promote bar (e.g., Strong present but Wilson LB on gap-through rate reduction straddles zero; or fails a sensitivity check).
4. **Defer** (this variant, and by default the study): all other outcomes — including the case where observed effects are within the Weak/null band for every metric, and the case where metrics straddle multiple tiers in ways that no pre-registered rule resolves cleanly. Survivorship-bias protocol's anti-rationalization clause is binding: when signals are ambiguous, the correct outcome is `defer`, NOT `reject`.

**Study-level decision.** If any single variant is promoted, the study result is `promote` (with the chosen X). If any variant is shadowed but none promoted, the study result is `shadow` (with the chosen X). If no variant meets promote or shadow but none meet reject, the study result is `defer`. If every variant is Reject, the study result is `reject`.

### Statistical-inference framework

Pre-registered before D3 runs:

- **Binomial proportions** (gap-through rate, gap-through rate REDUCTION as a delta vs baseline): **Wilson 95 % confidence interval.** For the delta between X=N and X=0, compute paired Wilson via the difference-of-proportions formula with the shared-denominator adjustment (stopped-trade counts per variant differ slightly because of trade-count drift across variants; use the individual Wilson CIs and report the delta with a Wilson-based interval on the difference rather than pooling).
- **Means** (expectancy in R; gap-through magnitude mean in R): **bootstrap 95 % confidence interval with N=10,000 resamples.** Paired bootstrap on the SIGNAL set for expectancy delta — same resample indices applied to X=0 and X=N's outcomes indexed by signal ID, which matches the harness's `outcomes_by_signal` structure.
- **Multiple-comparison handling:** **no Bonferroni / Holm correction applied.** Pre-registered rationale: the five variants (X ∈ {0, 3, 5, 7, 10}) are nested (X=10's excluded set ⊇ X=7's ⊇ X=5's ⊇ X=3's ⊇ X=0's empty set), not independent hypotheses. Pre-registration uses effect-size bands to assign tiers; confidence intervals are reported for transparency but the tier mapping does NOT require p < 0.05 / α<0.01 style significance gates to hit Strong. The only exception is the **Promote** bar, which requires Wilson CI lower bound > 0 on gap-through rate reduction — that is a "reliability check" on the headline Promote criterion, not a multiple-comparison gate.
- **Recommended posture confirmation.** Per brief §3 D1 item 3's recommended posture: effect-size-driven tier assignment with CIs reported alongside. Adopted verbatim.

### Sensitivity-check requirements (must be performed if any variant is Promoted)

1. **Adjacent-X monotonicity.** If X=5 is Promoted, report the deltas at X=3 and X=7 and confirm the effect is at least same-signed and of comparable order-of-magnitude. A X=5-only spike with X=3 and X=7 near null is overfitting.
2. **Temporal-subset consistency.** Split the window roughly in half (2024-04 – 2025-04 and 2025-04 – 2026-04) and confirm the promoted delta is same-signed in BOTH halves. Magnitude differences are expected; sign flips disqualify Promote.
3. **Absent-data robustness.** Confirm absent-earnings-data flagged signals are < 10 % of total signals. If ≥ 10 %, document and flag as a Promote caveat (method record: absent data → do not exclude, flag for review; excess absent-data fraction weakens the universe's applicability).
4. **Gap-through-event sample size.** Confirm the Promoted variant has ≥ 20 gap-through events in the stopped-trade set. Below 20, the Wilson CI widens to the point where the 5 pp Strong threshold becomes underpowered — flag and route to Shadow, not Promote.

If sensitivity checks fail, the variant is routed to Shadow or Defer depending on which check failed (monotonicity or temporal-subset sign → Defer; sample-size or absent-data → Shadow, with the caveat documented).

### Survivorship-bias protocol — pre-registered checkboxes

To be confirmed or deviated-from in D4:

- [x] Absolute metrics (gap-through rate, gap-through magnitude, expectancy at X=0) reported with explicit "survivorship-biased lower bound" caveats.
- [x] Relative metrics (variant-vs-baseline deltas) reported with "magnitude likely understated" interpretation notes — the true effect direction is trustworthy; the true effect size is likely larger than observed because the replay universe under-samples delisted/wipeout tickers where earnings-proximity risk is concentrated.
- [x] Observed-value-to-tier mapping performed per the table above, without mid-flight threshold revision.
- [x] All three named biases disclosed in Discussion: **(1) survivorship** (RS universe = current-roster only; delisted tickers absent), **(2) fixed-universe** (production's Finviz-filtered daily universe differs in composition from the replay's static SPX+NDX set), **(3) universe-staleness** (RS universe CSV was refreshed 2026-04-24 and applied uniformly across the 2024-04 – 2026-04 replay window, though membership drifted during that period).
- [x] Calendar-source reliability caveat disclosed: sample size 7 effective (5 strong matches + 2 pattern-matches), per `../notes/earnings-calendar-sources.md` §"Spot-check detail".

### Anti-rationalization clause

**Verbatim per brief §3 D1 item 6:** If observed results fall in the weak/null band per the pre-registered thresholds, the decision is `defer`, not `reject`. The survivorship-bias protocol's interpretation rule is binding. Separately: if observed results meet the Promote bar, the decision is `promote`; soft-pedaling a pre-registered strong signal into Shadow "to be safe" is the symmetric failure mode and is equally disallowed.

---

## Observed results

*Populated D4 after D3 (commit `e5510a8`) shipped raw outputs. Source: `research/harness/earnings_proximity/full-run-out/{metrics.csv, outcomes.csv, variant_membership.csv, run_manifest.json, analysis_summary.json}`.*

### Run scope

| Field | Pre-registered expectation | Observed |
|---|---|---|
| Universe size | 517 tickers (per Session 2a anchor) | **516 tickers** (pre-registration miscounted by 1) |
| Replay window | 504 NYSE trading days (~2 years) | **504 trading days, 2024-04-19 → 2026-04-23** |
| Ticker-days | ~260,568 | **~260,064** |
| Total A+ signals | ~1,300 (plausible 290 – 4,700) | **11** |
| Triggered trades per variant | ~400 (range 90 – 1,900) | **5** |
| Stopped trades per variant | ~140 (range 30 – 700) | **0** (all 5 triggered trades were time-capped) |
| Gap-through events per variant | ~20 (range 3 – 170) | **0** |
| Absent-earnings-data signals | undeclared | **0 (0 % of signals)** |

**Sample-size estimate error.** Observed 11 vs the pre-registered plausible-low-end of 290 — a **96.2 % undershoot**. This crosses the pre-registration's model-mismatch threshold ("Observed values far outside that range … will be flagged as a model-mismatch finding in Open Issues"). The undershoot does not change the pre-registered tier mappings; it is documented in Open Issues §"Observed signal volume vs anchor".

**Cache-stat note.** `run_manifest.json.cache_stats.ohlcv_misses=517` despite a fully-populated parquet cache. Cause: `fetchers._covers()` requires `idx_max ≥ end_inclusive_ts`, but the replay's fetch-window `end` extends ~30 sessions past the last available bar (yfinance only returns up to today). The check therefore always reports "not covered" and re-downloads. This is wasted bandwidth (~7 minutes per run) but does not affect correctness — the cache is union-merged each run. Flagged for the orchestrator in §"Open issues".

### Per-variant metrics table

All five variants returned IDENTICAL aggregated metrics because the variant filter `apply_variant(signals, X, calendar)` was a structural no-op: not a single one of the 11 A+ signals had a `next_earnings_date` within 10 trading days of its `signal_date` (the largest pre-registered X). Every signal therefore survived every variant's filter, with bit-identical `outcome_id` membership across X ∈ {0, 3, 5, 7, 10}.

**Note on uncomputable metrics.** With **0 stopped trades** in the sample (all 5 triggered trades hit the simulator's 10-bar time cap before reaching their initial stop), the gap-through-rate and gap-through-magnitude metrics are **not estimable** — the denominator (stopped-trade count) is zero, so the proportion and the magnitude mean are mathematically undefined, NOT exactly zero. The harness's `aggregate()` function returns `0.0` as a placeholder when the denominator is zero (per `metrics.py` docstring), but for evidence-summary purposes those entries below are reported as **`n/e`** (not estimable). Wilson and Newcombe CIs likewise do not apply when n=0; the column headers below avoid implying a CI framework where none exists for this run.

| X | Signal count | Trigger rate | Stopped trades | Expectancy R (n=5 raw trades — see note below; **survivorship-biased lower bound**) | Gap-through rate (if estimable; **survivorship-biased lower bound**) | Gap-through mag mean R (if estimable; **survivorship-biased lower bound**) | Signal-volume delta vs X=0 |
|---|---|---|---|---|---|---|---|
| 0 | 11 | 5 / 11 = 45.5 % | 0 | (descriptive only — see note) mean +0.2160 R from {−0.497, +0.604, +0.286, −0.417, +1.104} | **n/e** (n=0 stopped trades — denominator zero) | **n/e** (n=0 gap-through events) | — |
| 3 | 11 | 5 / 11 = 45.5 % | 0 | (descriptive only) same five trades — variant filter no-op | n/e | n/e | 0.0 % |
| 5 | 11 | 5 / 11 = 45.5 % | 0 | (descriptive only) same five trades | n/e | n/e | 0.0 % |
| 7 | 11 | 5 / 11 = 45.5 % | 0 | (descriptive only) same five trades | n/e | n/e | 0.0 % |
| 10 | 11 | 5 / 11 = 45.5 % | 0 | (descriptive only) same five trades | n/e | n/e | 0.0 % |

**Note on the n=5 expectancy.** The five-trade expectancy of **+0.2160 R** is the simple arithmetic mean of {−0.497, +0.604, +0.286, −0.417, +1.104}. A 95 % bootstrap CI of [−0.292, +0.740] was reported in `analysis_summary.json` for completeness, but **with n=5 that interval is descriptive at best** — bootstrap intervals on n=5 are highly discrete (only 252 distinct resample multisets) and dominated by resampling mechanics rather than real population structure. The interval is presented in `analysis_summary.json` per the pre-registered framework but is NOT load-bearing in this evidence summary; readers should treat the +0.216 mean as a five-trade-snapshot rather than a population estimate, and treat any uncertainty interval on it as too unstable to support inference. The five raw R-values are listed inline above to make this transparent.

CIs computed via `_compute_cis_session2c.py` (deterministic seed 20260424; 10,000 bootstrap resamples). Source: `analysis_summary.json`. The harness's `metrics.csv` shows literal 0.0 entries for the gap fields per its placeholder convention; readers should consult this row's `n/e` annotation rather than the literal CSV value.

**Headline survivorship caveat (in-line per protocol).** Each absolute headline number above is annotated as a "survivorship-biased lower bound." The X=0 expectancy of +0.216 R/trade is "≥ +0.216 R; true expectancy plausibly lower once delisted-ticker wipeout trades are restored." The gap-through rate is unobserved here (n/e), but the protocol's lower-bound rule would apply identically if it had been observable: any non-zero observed value would understate the true historical population's rate. The replay universe is 100 % current-roster (no delisted tickers); the population most likely to have produced gap-through losses (biotech PDUFA failures, accounting-fraud blow-ups, eventually-delisted small-caps) is structurally absent.

### Per-variant deltas vs X=0

Because all four X variants share **bit-identical outcome membership** with X=0 (every signal survived every filter; same `outcome_id` set), the per-variant deltas are **deterministically exactly zero** as a matter of identity, not as an estimate. Confidence intervals on those deltas are vacuous — the bootstrap procedure in `_compute_cis_session2c.py` resampled each arm independently, which on identical samples produces artificial spread that does NOT reflect any sampling variability in the actual estimand. The "[-0.745, +0.740]" intervals in `analysis_summary.json` are therefore reported here as **`vacuous`** rather than as legitimate uncertainty bounds.

| X | Expectancy Δ R | Gap-through rate Δ pp | Gap-through mag Δ R | Signal-volume loss % |
|---|---|---|---|---|
| 3 | **0.000** (deterministic; identical membership) | **n/e** (both arms n=0 stopped) | **n/e** | **0.0 %** |
| 5 | 0.000 (deterministic) | n/e | n/e | 0.0 % |
| 7 | 0.000 (deterministic) | n/e | n/e | 0.0 % |
| 10 | 0.000 (deterministic) | n/e | n/e | 0.0 % |

**Magnitude-likely-understated note (per protocol).** Even though the cross-variant deltas are deterministically zero on this sample, the protocol's "relative metrics direction-trustworthy but magnitude-uncertain" rule still applies in interpretation: the absence of any observable relative effect on the survivor population does NOT entail the absence of a true historical effect. The replay simply contained zero variant-distinguishable cases — there was nothing for the rule to operate on (see Discussion §"Why the rule did not activate"). The fact that the deltas are exact zeros is a structural property of the sample (no signal fell within any X window), not evidence about the rule's true effect.

### Absent-data audit

| Field | Observed |
|---|---|
| Total signals | 11 |
| Signals with earnings data | 11 |
| Signals with `absent_earnings_data=True` | 0 (0.0 %) |

The method-record's absent-data rule ("if no scheduled earnings date is findable, do NOT exclude — treat absent-data as eligible, but flag for review") was VERIFIED by code path but never EXERCISED by data. All 11 signals had non-empty earnings histories.

### Observed signal-and-earnings detail

For full transparency on why no variant filtered any signal, the trading-day gap from each signal to its `next_earnings_date` is below. Largest pre-registered X = 10 trading days; minimum observed gap = ~16 trading days.

| outcome_id | Ticker | Signal date | Next earnings | Calendar-day gap | Approx. trading-day gap | Excluded at any X? |
|---|---|---|---|---|---|---|
| 0 | VRT | 2024-05-30 | 2024-07-24 | 55 | ~38 | No |
| 1 | FIX | 2024-08-16 | 2024-10-24 | 69 | ~48 | No |
| 2 | INSM | 2024-08-29 | 2024-10-31 | 63 | ~44 | No |
| 3 | INSM | 2024-08-30 | 2024-10-31 | 62 | ~43 | No |
| 4 | STX | 2025-12-24 | 2026-01-27 | 34 | ~22 | No |
| 5 | FSLR | 2025-12-26 | 2026-02-24 | 60 | ~40 | No |
| 6 | COHR | 2025-12-30 | 2026-02-04 | 36 | ~25 | No |
| 7 | COHR | 2025-12-31 | 2026-02-04 | 35 | ~25 | No |
| 8 | FSLR | 2025-12-31 | 2026-02-24 | 55 | ~38 | No |
| 9 | LITE | 2025-12-31 | 2026-02-03 | 34 | ~22 | No |
| 10 | KLAC | 2026-04-07 | 2026-04-29 | 22 | ~16 | No |

The closest signal-to-earnings gap in the entire replay is KLAC at ~16 trading days — still 60 % outside the largest blackout window. The earnings-proximity filter would not have changed any decision on this dataset.

---

## Tier assignment

### Per-metric-per-variant tier mapping

Applying the pre-registered tier-threshold table (§Pre-registration "Decision-tier thresholds per metric") to the observed deltas:

| X | Expectancy Δ tier | Gap-rate Δ tier | Gap-mag Δ tier | Signal-volume tier | Variant tier (combined rule) |
|---|---|---|---|---|---|
| 3 | Δ = 0.0 R → **Weak/null** (band [-0.03, +0.03]) | Δ = 0 pp → **Weak/null** (band [-1, +2] pp) | Δ = 0 R → **Weak/null** (band [-0.05, +0.05]) | 0.0 % loss → fully within Strong band (≤ 15 %) | **Defer** (no Strong; no Reject; default branch of combined rule) |
| 5 | Weak/null | Weak/null | Weak/null | Strong-band volume cost | Defer |
| 7 | Weak/null | Weak/null | Weak/null | Strong-band volume cost | Defer |
| 10 | Weak/null | Weak/null | Weak/null | Strong-band volume cost | Defer |

**Combined-rule check, X=3 (representative of all four):**
- Reject? Signal-volume cost = 0 % (≤ 50 %); expectancy delta = 0 (not < −0.03). NOT reject.
- Promote? Expectancy delta = 0 (not ≥ +0.10). NOT promote.
- Shadow? No metric at Strong on the *delta-vs-baseline* dimension (signal-volume is "below cost ceiling" not "produces a benefit"). NOT shadow.
- Defer? Default branch when no other tier triggers. **Yes — defer.**

The signal-volume metric's "Strong" band reflects the ABSENCE of cost rather than the PRESENCE of benefit; it does not, on its own, constitute the "at least one Strong metric" required to hit Shadow. This reading is consistent with the pre-registration's explicit calibration note ("a positive expected-signal-volume delta… is structurally impossible since X filtering is monotonically reductive").

### Sensitivity checks (if any variant is a Promote candidate)

**Not applicable.** No variant is a Promote candidate; sensitivity checks do not apply. For completeness:

- **Adjacent-X monotonicity:** trivially passes (all deltas equal at zero by construction — identical variant membership).
- **Temporal-subset consistency:** per `analysis_summary.json` `temporal_subset_first_half` / `_second_half` (split midpoint 2025-12-24): first half has **4 signals (1 traded — single time-capped loss FIX at −0.497 R)**, second half has **7 signals (4 traded — mixed)**. All four variants identical within each half. **These per-half values are descriptive only; n=1 in the first half is far too small for any uncertainty interval (a CI on a single observation is the observation itself).** No promote → no sign-flip check meaningful.
- **Absent-data robustness:** 0 / 11 = 0.0 % < 10 % threshold. Trivially passes.
- **Gap-through-event sample size:** 0 events vs ≥ 20 threshold. **Fails.** Would route any candidate Promote variant to Shadow per the pre-registered rule — moot here since no variant reached Promote.

The temporal-subset numbers should NOT be read as evidence of regime-mix; they are sample-size-starved descriptive splits with a single trade in the first half and four in the second. Any narrative built from them would be over-fitting.

---

## Decision

**`defer`**

### Pre-registered basis (the decision rule that fires)

The combined tier-assignment rule (§Pre-registration) reaches `defer` via its **default branch** because none of Promote, Shadow, or Reject can trigger on the observed data:

- **Promote does not fire.** Promote requires `expectancy delta ≥ +0.10 R AND gap-through rate reduction ≥ 5 pp AND signal-volume cost ≤ 15 % AND Wilson 95 % CI lower bound on gap-rate reduction > 0 pp`. Observed expectancy delta is 0.000 (does not meet ≥ +0.10); observed gap-rate reduction is **n/e** because both arms have zero stopped trades (the rate is mathematically undefined, not a value that meets ≥ 5 pp). Promote cannot fire.
- **Shadow does not fire.** Shadow requires at least one Strong-band metric on the delta-vs-baseline dimension AND others ≥ Moderate AND signal-volume cost ≤ 30 %. No metric is at Strong: expectancy delta is at Weak/null (0.000 ∈ [−0.03, +0.03]); gap-rate and gap-magnitude deltas are non-estimable; signal-volume's Strong band reflects absence of cost, not presence of benefit, and does not satisfy "≥ 1 Strong metric on the delta dimension." Shadow cannot fire.
- **Reject does not fire.** Reject requires signal-volume cost > 50 % (observed 0.0 %; not met) **OR** expectancy delta < −0.03 R with no compensating gap improvement (observed 0.000; not met). Reject cannot fire.
- **Default branch → Defer.** The pre-registered combined rule routes "all other outcomes" to `defer`. This includes the case where the gap-side metrics are non-estimable and therefore cannot affirmatively place the variant in any tier above default.

The pre-registered **anti-rationalization clause** ("weak/null observed → defer, NEVER reject") is independently relevant for the *interpretation* of the non-estimable gap metrics: a reasonable reading of "rule could not be evaluated on this dataset because the rule's target population was absent" is not a license to call the result `reject`. But the formal trigger of `defer` rests on the default-branch routing of the combined rule, not on the anti-rationalization clause being dispositive on its own — observed expectancy is in the weak/null band, but the gap metrics are *outside* the band system entirely (non-estimable), and that distinction is preserved here.

This is the formal trigger and is not subject to analyst judgment.

**Citations:** §"Tier assignment" above (mechanically applies pre-registered thresholds → defer via default branch); pre-registered thresholds in §"Pre-registration" (commit `0e04079`); observed values from `metrics.csv` and `analysis_summary.json` (commit `e5510a8`); Survivorship-bias interpretation protocol in `./earnings-proximity-exclusion.md`.

### Post-hoc study-quality assessment (interpretation, NOT a decision rule)

The pre-registered rule is the trigger, but a reader interpreting `defer` operationally should know the following limitations of the underlying data. These are post-hoc observations about study quality — they did NOT pre-exist as decision criteria, and they do NOT change the tier assignment above. They DO inform what kind of follow-on study (if any) is warranted.

The study suffered from **three distinct failure modes**, each with a different fix:

1. **Zero rule-activation in the tested X-range.** Minimum observed signal-to-earnings gap = 16 trading days; largest pre-registered X = 10. The variant filter was a structural no-op on every signal. *Fix candidates: a different filter stack, a broader X grid, or a deliberately broadened universe where setups can crystallize closer to earnings.*

2. **Zero stopped trades.** All 5 triggered trades hit the simulator's 10-bar time cap before reaching their initial stop. The risk-side metrics (gap-through rate and magnitude) — the study's headline-motivating quantities — are mathematically undefined on this sample. *Fix candidates: a longer time cap, a tighter stop convention, a much larger sample, or a different setup type with quicker resolution.*

3. **Signal-volume undershoot vs anchor.** Observed 11 signals vs the pre-registered plausible-low of 290 — a 96.2 % undershoot. The anchor model (Session 2a) was Finviz-prefiltered; the replay was not. *Fix candidates: re-derive the anchor on an unfiltered SPX+NDX subset, or run the harness on the production daily-Finviz universe instead of the static RS roster.*

Each of (1)–(3) is a separate methodological failure that a redesigned study could address independently of the others.

### Why this is NOT `reject`

Three compounding factors push toward `defer` rather than `reject` once one steps past the formal pre-registered trigger:

1. **Survivorship-bias direction** — delisted-ticker exclusion under-samples the population the rule was designed to protect against; absolute and relative metrics on the survivor population are interpretation-limited per protocol.
2. **Non-identifiability for activation** — failure mode (1) above. The rule had no signals within any X window to filter; the data contains zero variant-distinguishable cases. This is a property of the SAMPLE, not evidence about the RULE.
3. **Implicit-exclusion hypothesis (speculative — NOT evidence).** A plausible mechanism for failure mode (1) — that the upstream trend-template + VCP filters already exclude pre-earnings tickers via correlated structural requirements — is offered in §Discussion as hypothesis-generation only. It is NOT pre-registered, NOT tested by the present analysis, and is NOT load-bearing for the decision; it is recorded so future sessions can design tests of it (e.g., compare A+ rate within vs outside earnings windows on a broader/looser-VCP universe). Treating this hypothesis as evidentiary support for `defer` would be HARK-ing.

The pre-registered combined tier rule and the anti-rationalization clause reach `defer` directly. The post-hoc study-quality assessment, items 1 and 2 of the "not reject" reasoning, and the implicit-exclusion hypothesis only explain *why* the data was uninformative; they do NOT change the formal decision.

---

## Discussion

### Why the rule did not activate — speculative hypothesis-generation only

The empirical fact: **the smallest signal-to-earnings gap among 11 A+ signals was ~16 trading days** (KLAC, with earnings 22 days out), comfortably outside the largest pre-registered blackout (X = 10 trading days). The earnings-proximity exclusion therefore had nothing to act on. This is a property of the realized sample, observed directly in the data.

A **plausible mechanistic hypothesis** (NOT pre-registered, NOT tested by the present analysis): the earnings-proximity exclusion rule is logically downstream of the trend-template and VCP filters. Both upstream filters require some form of orderly recent price structure — sustained MA stack, controlled drift toward pivot, low range-CV. Tickers approaching scheduled earnings tend to have elevated implied volatility and price-action distortion during the run-up window, which would often violate VCP tightness or trend-template's rising-MA requirement. If true, this would mean the upstream stack implicitly enforces earnings-proximity exclusion via correlated structural requirements.

**This is hypothesis-generation, not evidence.** The present study does NOT include the comparison that would test it (e.g., A+ rate within vs outside earnings windows on a relaxed-VCP universe; or a paired test with VCP-tightness ablated). A skeptical reviewer would correctly note that one observed n=11 sample where no signal happened to fall near earnings is also consistent with simple base-rate / sample-size starvation, with no implicit-exclusion mechanism at all.

Because this hypothesis is plausible AND testable AND would, if true, change the operational interpretation of the `defer` decision (the rule would be redundant with VCP rather than truly untested), it is recorded here for orchestrator awareness and as a candidate for a follow-on study. It is NOT used as load-bearing rationale for the present `defer` decision.

What the data DOES support:
- On THIS replay sample, the variant filter was a structural no-op.
- The rule MIGHT still be useful on a different universe (broader micro-cap inclusion, biotech-heavy filter, looser VCP) where setups can crystallize closer to earnings — but THIS study cannot say.
- Operator-UX value (a "X days to earnings" badge on candidates) is unaffected by this study and remains independently evaluable.

### Survivorship bias

Per the study design's Survivorship-bias interpretation protocol, the replay used the current SPX+NDX RS universe against historical OHLCV. Two specific consequences for THIS study's primary metric (gap-through rate and magnitude):

- **Delisted-ticker absence systematically under-samples the gap-prone population.** Biotech Phase-3 failures, accounting-restatement blow-ups, and microcap fraud cases — all of which cluster catastrophic gaps around scheduled earnings windows — would not appear in the replay even if they were SPX+NDX members during the window. None of those failure modes is well-represented in current SPX+NDX membership.
- **The protocol's "lower bound" treatment is binding.** The X=0 gap-through rate of 0.000 should be read as "≥ 0.000 in the true historical population" — uninformative as a lower bound when the observed value is at the floor. The observed expectancy of +0.216 R/trade similarly should be read as "≥ +0.216 R, possibly substantially less" once delisted catastrophes are restored.

### Fixed-universe concession

The replay uses a static SPX+NDX roster, not the production pipeline's daily Finviz-filtered subset. Two consequences:

- **Sample-size mismatch.** Production runs against ~80 Finviz-filtered tickers per day (Session 2a audit); the replay runs against 516 tickers per day. With the same filter stack and 6.5× more tickers, one might naively expect 6.5× more A+ signals. Instead, the replay produced *fewer* signals than the (small) production sample suggested per ticker-day. The most likely explanation: Finviz's screening already biases toward setups that the trend-template + VCP stack can readily classify A+, so cross-universe RS-rank competition is harsher in the replay than in production (a top-30 % RS rank against 516 tickers is a steeper bar than against 80 momentum-prefiltered tickers).
- **Distribution mismatch.** The Finviz screener applied in production has explicit price-action criteria (volume, ATR, % from highs) that the static SPX+NDX roster lacks. The replay over-represents low-momentum mega-caps relative to the production daily-candidate set. This may further depress A+ rates.

### Universe-staleness

The `reference/rs-universe.csv` v2026-04-24-1 is the universe that was current AT THE START of Session 2c. It was applied uniformly across the 2024-04 → 2026-04 replay window despite real SPX+NDX membership having drifted during that period. Session 2a's `historical-candidate-source-decision.md` already flagged this concession. On THIS study's outcomes, universe-staleness is unlikely to be the binding bias — the signal count is so low that even substantial membership drift would not plausibly bring it into the pre-registered range — but the concession is disclosed.

### Calendar-source reliability

`../notes/earnings-calendar-sources.md` documents the calendar-source spot-check at sample size 7 effective (5 strong matches + 2 pattern-matches across mega-cap, mid-cap, small-cap, and biotech samples). For the present study the reliability question is moot — every variant produced identical metrics, so calendar-date noise within ±1 day would not change any tier assignment. For any future study where the rule actually filters signals, that sample size is **below** the V2.1 §VII.B nominal "≥ 10 tickers × ≥ 3 calendar months" target and represents a known caveat. Re-spot-check before any subsequent earnings-proximity work that depends on calendar precision at the day boundary.

### Open issues

1. **Observed signal volume vs anchor: model-mismatch.** Pre-registered plausible range was 290 – 4,700 signals; observed 11 is 96 %+ below the lower bound. Two non-mutually-exclusive hypotheses:
   - (a) Production's anchor rate (n=2 / 400 ticker-days) is a poor estimator because the production universe is Finviz-pre-screened, which materially raises the conditional A+ rate per ticker-day relative to the unfiltered SPX+NDX roster.
   - (b) The replay's harness imports `swing/` filter stack with `current_equity = $100k` and `max_risk_pct = 0.5 %` (= $500/trade risk budget). High-priced tickers that need wider stops than ~$500-equivalent fail `risk_feasibility` even when otherwise A+. This may exclude a substantial fraction of mega-cap names from ever reaching A+ classification.
   - Either way, the anchor model is not load-bearing for this study's decision (`defer`), but should be re-derived BEFORE any future study that depends on signal-volume forecasting.
2. **No clean stops, no gap-through events.** All 5 triggered trades hit the 10-bar simulator time cap before stopping. Possible drivers: time cap too short for the typical pivot-to-stop distance on this universe; replay's stop placement (20-bar low) is too generous relative to typical bar volatility; or (most likely) the small sample is a fluke. The gap-through metric — the study's primary risk-side metric — was therefore not estimable on this sample. ANY future study where gap-through rate is the headline metric should confirm a non-trivial stopped-trade base before the run.
3. **Cache-coverage check rounding error.** `fetchers._covers()` always reports "not covered" when the requested fetch end is in the future (yfinance cannot return future bars). This caused a wasted ~7-minute re-download on the D3 retry. Cosmetic; flag for harness-side fix in a follow-on session.
4. **Pre-IPO NaN padding from yfinance batch download.** `yf.download(group_by='ticker')` returned 8 tickers (Q, SNDK, GEV, SOLV, VLTO, ARM, KVUE, FISV) with NaN-padded rows for dates before each ticker's IPO. Those rows survive the replay's `_slice_up_to` length check (`len(sliced) < 200` is row-count, not non-NaN-count) and crash `swing.evaluation.criteria.risk_feasibility` (`int(budget // NaN)` raises). Worked-around in the D3 driver via per-ticker `dropna(subset=["Open","High","Low","Close"])` BEFORE feeding to `replay()`. Permanent fix should land in `research/harness/earnings_proximity/fetchers.py` or `replay.py`; flagged for a follow-on session.
5. **Underpowered for the protocol's stated purpose.** The Survivorship-bias interpretation protocol envisions the analyst observing some non-zero variant-to-baseline delta and then interpreting its direction. With every observed delta exactly zero, the protocol's "direction-trustworthy" subclause has no direction to vouch for. Whether this "rule did not activate" outcome should re-route to a different study design (e.g., a deliberately broadened universe, or a different setup-filter stack) is an orchestrator decision, not a Session-2c finding to act on.
6. **Methodology concern surfaced during analysis (NOT amended into the study design per scope discipline).** The study design assumes the rule has "something to filter" — i.e., that A+ signals will sometimes fall within the blackout window. On this universe, that assumption was empirically false. A future iteration should pre-register a "rule-activation rate" metric (fraction of signals where any X filters them) and treat near-zero activation as a signal that the upstream filter stack already implements the rule implicitly. Documented here per brief §1 ("If the analysis surfaces a methodology concern that requires study-design amendment, document in the evidence summary's 'Open issues' and flag for orchestrator — do NOT amend mid-session.")
