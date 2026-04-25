# Earnings-Proximity Exclusion — Evidence Summary

**Method record:** `../method-records/earnings-proximity-exclusion.md`
**Study design:** `./earnings-proximity-exclusion.md`
**Status:** PRE-REGISTERED (observed values pending Session 2c D3 run); will become FINAL after D4.
**Pre-registration commit:** `<filled in after this commit lands>`
**Decision:** `<TBD — reject / shadow / promote / defer>`

---

## Pre-registration

*This section is committed BEFORE the study runs (D1). Subsequent sections are filled in D4 after D3's output is observed. Pre-registration prevents post-hoc rationalization per the study design's Survivorship-bias interpretation protocol (`./earnings-proximity-exclusion.md` §"Survivorship-bias interpretation protocol", amended 2026-04-24).*

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

- [ ] Absolute metrics (gap-through rate, gap-through magnitude, expectancy at X=0) reported with explicit "survivorship-biased lower bound" caveats.
- [ ] Relative metrics (variant-vs-baseline deltas) reported with "magnitude likely understated" interpretation notes — the true effect direction is trustworthy; the true effect size is likely larger than observed because the replay universe under-samples delisted/wipeout tickers where earnings-proximity risk is concentrated.
- [ ] Observed-value-to-tier mapping performed per the table above, without mid-flight threshold revision.
- [ ] All three named biases disclosed in Discussion: **(1) survivorship** (RS universe = current-roster only; delisted tickers absent), **(2) fixed-universe** (production's Finviz-filtered daily universe differs in composition from the replay's static SPX+NDX set), **(3) universe-staleness** (RS universe CSV was refreshed 2026-04-24 and applied uniformly across the 2024-04 – 2026-04 replay window, though membership drifted during that period).
- [ ] Calendar-source reliability caveat disclosed: sample size 7 effective (5 strong matches + 2 pattern-matches), per `../notes/earnings-calendar-sources.md` §"Spot-check detail".

### Anti-rationalization clause

**Verbatim per brief §3 D1 item 6:** If observed results fall in the weak/null band per the pre-registered thresholds, the decision is `defer`, not `reject`. The survivorship-bias protocol's interpretation rule is binding. Separately: if observed results meet the Promote bar, the decision is `promote`; soft-pedaling a pre-registered strong signal into Shadow "to be safe" is the symmetric failure mode and is equally disallowed.

---

## Observed results

*Populated in D4 after D3 ships.*

### Run scope

- **Universe size (actual):** `<TBD>` tickers.
- **Window (actual):** `<YYYY-MM-DD>` → `<YYYY-MM-DD>` (`<N>` trading days).
- **Total A+ signals emitted:** `<TBD>` (vs pre-registered expectation ~1,300, plausible 290–4,700).
- **Absent-earnings-data signals:** `<TBD>` (`<pct>` % of total).
- **Sample-size estimate error:** `<%>` vs pre-registered point estimate.

### Per-variant metrics table

| X | Signal count | Trigger rate | Stopped trades | Expectancy R (95 % CI) | Gap-through rate (95 % CI) | Gap-through mag mean R (95 % CI) | Signal-volume delta vs X=0 |
|---|---|---|---|---|---|---|---|
| 0 | `<TBD>` | | | | | | — |
| 3 | | | | | | | |
| 5 | | | | | | | |
| 7 | | | | | | | |
| 10 | | | | | | | |

### Per-variant deltas vs X=0

| X | Expectancy Δ R (95 % CI) | Gap-through rate Δ pp (95 % CI) | Gap-through mag Δ R (95 % CI) | Signal-volume loss % |
|---|---|---|---|---|
| 3 | | | | |
| 5 | | | | |
| 7 | | | | |
| 10 | | | | |

### Absent-data audit

`<TBD — absent-data count, percent of signals, per-variant breakdown; method-record rule verified>`

---

## Tier assignment

*Populated in D4.*

### Per-metric-per-variant tier mapping

| X | Expectancy tier | Gap-rate tier | Gap-mag tier | Signal-volume tier | Variant tier |
|---|---|---|---|---|---|
| 3 | | | | | |
| 5 | | | | | |
| 7 | | | | | |
| 10 | | | | | |

### Sensitivity checks (if any variant is a Promote candidate)

- Adjacent-X monotonicity: `<pass / fail with detail>`
- Temporal-subset consistency: `<pass / fail>`
- Absent-data robustness (< 10 % of signals): `<pass / fail>`
- Gap-through-event sample size (≥ 20 events): `<pass / fail>`

---

## Decision

*Populated in D4.*

**`<reject | shadow | promote (X=N) | defer>`**

Citation: §"Tier assignment" above; pre-registered thresholds in §"Pre-registration" (commit `<D1-SHA>`); observed values from `metrics.csv` (commit `<D3-SHA>`); Survivorship-bias interpretation protocol in `./earnings-proximity-exclusion.md`.

---

## Discussion

*Populated in D4 — see protocol checkboxes above for required content.*

### Survivorship bias

`<named section covering the protocol; see study design>`

### Fixed-universe concession

`<production uses Finviz-filtered daily set; replay uses static SPX+NDX roster>`

### Universe-staleness

`<2026-04-24 CSV applied uniformly across 2024-2026 window; membership drift not reconstructed>`

### Calendar-source reliability

`<7-effective-sample-size caveat per Session 2a notes>`

### Open issues

`<sample-size limits, methodology concerns surfaced during analysis, items flagged for orchestrator>`
