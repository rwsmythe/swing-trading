# Study: Earnings-Proximity Exclusion Parameter Sweep

**Method record:** `../method-records/earnings-proximity-exclusion.md`
**Status:** designed; not yet run.
**Target duration:** one evening's work for data setup + one for analysis (per V2.1 §III.7 time budget).

## Question

Does excluding candidates within X trading days of scheduled earnings improve expectancy and/or reduce gap-risk drawdowns?

## Null hypothesis

Earnings proximity does not systematically affect expectancy or tail-loss magnitude; the exclusion is noise-at-best, cost-at-worst (reduces signal count without improving outcomes).

## Baseline

Current candidate pipeline output without any earnings-proximity filter (equivalent to `blackout_trading_days = 0`).

## Variants

Four treatment variants: `blackout_trading_days ∈ {3, 5, 7, 10}`. Optionally, if cheap to compute, also include a post-earnings cooling-off variant (e.g., skip the first 3 trading days after announcement).

## Data

- Historical candidate set: the repo's own `candidates` table (once it has enough history) OR a synthetic replay using yfinance EOD data + historical earnings calendar. Prefer historical candidates for verisimilitude.
- Earnings calendar source: evaluate ≥2 free sources (Phase-0 task) and commit to the one with better date accuracy. Free sources are known to be unreliable on before-market / after-market timing but adequate on date precision (per V2.1 §V.E, rebuttal Finding 2.20).
- Universe: same as current production evaluation (no broadening).

## Metrics

- Expectancy per signal (R-multiple).
- Gap-through rate (fraction of stopped trades where the stop was breached via gap rather than intraday move).
- Magnitude of gap-through losses (mean and max, normalized by initial risk).
- Signal volume reduction (how many trades does the rule prevent? — cost of the rule).

## Decision surface

One of: `reject` / `shadow` / `promote` / `defer`. If `promote`, name the chosen `blackout_trading_days` value. Tier assignment is governed by the survivorship-bias interpretation protocol below (added 2026-04-24), which maps observed-data signal strength to decision tier and adds `defer` as a fourth outcome for weak/null signals that survivorship bias renders ambiguous.

## Parity standard (per V2.1 §VII.B)

- Fixture identity: two synthetic test cases (one excluded ticker, one eligible ticker) must produce bit-identical exclusion flags under the method's computation function.
- Toleranced vendor-backed equivalence: on live calendar data, excluded/eligible classification must agree with a hand-checked spot set of ≥10 tickers × ≥3 calendar months. No claim of exactness against calendar vendors.

## Promotion payload (if `promote` is the decision)

- Candidate-row flag (`is_earnings_blackout BOOLEAN`) emitted by the evaluate step.
- Operator-UI warning badge on candidates within the blackout window (maps to Tranche B-ops B3 risk-warning work).
- Optional hard exclusion in the evaluate step, gated by a `swing.config.toml` flag (default off in shadow phase, configurable once promoted).

## Non-goals

- Intraday earnings-timing precision. EOD workflow does not require it.
- Optimizing X beyond the four candidate values. The grid is deliberately sparse — finer sensitivity analysis is a later-phase refinement, not this first study.
- Post-earnings gap-capture strategy. Out of scope; if interesting, it becomes its own method record later.

## Survivorship-bias interpretation protocol

*Added 2026-04-24; see Amendments.*

The replay uses the current RS universe against historical OHLCV (fixed-universe concession, per `../notes/historical-candidate-source-decision.md` §"Flagged but not resolved"). This is minimum-viable per V2.1 §V.E bootstrap-first but introduces survivorship bias with a shape specific to this study that requires interpretation discipline beyond the generic "common-mode cancels cross-variant" argument.

### Why survivorship bias is sharper here than for generic backtests

The primary metric is gap-through rate and magnitude. Gap-throughs are disproportionately concentrated in the population of tickers most likely to be ABSENT from a current-universe replay:

- Biotech Phase-3 failures clustering around PDUFA/earnings dates.
- Small-cap earnings-fraud revelations that trigger margin-call spirals.
- Guide-down catastrophes severe enough to cause eventual delisting.
- Failed SPACs, microcap accounting restatements, reverse-mergers that fell apart.

These are precisely the population the earnings-proximity exclusion is designed to protect against. Replaying only on survivors systematically understates the measured absolute gap-through rate in the exact direction that matters for the decision.

### Metric treatment

- **Absolute metrics** (gap-through rate, gap-through magnitude, expectancy at baseline X=0): treat as **lower-bound estimates of true historical effect**. Report with a "survivorship-biased lower bound" caveat in Session 2c's evidence summary.
- **Relative metrics** (variant-vs-baseline deltas in expectancy, gap-through rate, gap-through magnitude): treat as **direction-trustworthy but magnitude-uncertain**. Most of the universe bias is common-mode across variants and cancels in cross-variant comparisons; the absolute magnitude of the benefit remains understated. Report without the absolute-number caveat but with a "magnitude likely understated" interpretation note.
- **Sample-size-driven significance** (p-values, confidence intervals): compute normally on the observed data. Survivorship bias does not invalidate statistical inference ON THE OBSERVED DATA; it limits the GENERALIZATION to the true historical population.

### Decision tiers

Session 2c's analyst chooses one of four tiers based on the observed data. Numerical thresholds for each tier (effect size + significance) must be **pre-registered** in `research/studies/earnings-proximity-exclusion-results.md` (the evidence summary document Session 2c will create) BEFORE the variant comparison is run, to prevent post-hoc rationalization.

- **Strong signal — `promote`.** Relative gap-through reduction at some X is both meaningfully large AND statistically significant at the pre-registered threshold. True effect is likely AT LEAST as large as observed (survivorship bias understates); acting on the observed conclusion is conservative. Name the chosen X.
- **Moderate signal — `shadow`.** Relative reduction is positive and plausibly meaningful but below strong-signal threshold, OR strong-signal effect is present but only in a narrow subset of variants (e.g., only at X=10). Deploy as operator-UI warning badge (non-exclusionary per promotion-payload spec); gather forward operational evidence before hard-promoting.
- **Weak or null signal — `defer`.** No meaningful reduction observed, OR observed reduction is within the noise band for the sample size. Do NOT reject outright — survivorship bias makes this outcome ambiguous (we cannot distinguish "rule doesn't help" from "rule helps but survivors underrepresent the helpable cases"). Queue a survivorship-aware second study (V2.1 §V.E-compliant paid data or time-boxed manually compiled delistings list) before final decision.
- **Negative signal — `reject`.** The rule materially harms expectancy (e.g., reduces signal volume without reducing gap-through, producing worse per-signal expectancy or worse risk-adjusted returns). Reject regardless of survivorship concerns — if the rule hurts on survivor-biased data, it is extremely unlikely to help on true data.

### What Session 2c's evidence summary MUST include

- A named "Survivorship bias" section citing this protocol.
- Absolute-metric reporting with explicit "survivorship-biased lower bound" caveats.
- Relative-metric reporting with "magnitude understated" interpretation notes.
- Pre-registered tier thresholds (recorded before the variant comparison runs) AND the observed values AND the resulting tier assignment.
- The final decision (reject / shadow / promote / defer) with explicit citation back to the tier it maps to.

### What Session 2c MUST NOT do

- Report absolute gap-through rate or expectancy without the caveat.
- Dismiss the fixed-universe concession with a generic "common-mode cancels, disregard" argument — that argument is weaker for this specific study's primary metric.
- Interpret a weak/null signal as evidence that earnings proximity doesn't matter. The correct interpretation of weak/null is "survivorship bias prevents distinguishing weak-effect from no-effect" — map to `defer`, not `reject`.
- Promote based on strong signal at ONLY one variant (e.g., X=10) without sensitivity checks on adjacent values (X=7, X=14 if computable) — overfitting risk.

## Amendments

- **2026-04-24 — Added Survivorship-bias interpretation protocol.** Session 2a decision memo flagged survivorship bias as a potential escalation if "materially affecting expectancy estimates." Mid-Session-2b discussion with orchestrator identified that for THIS study specifically (gap-through metric concentrated in delisted tickers), survivorship bias has a sharper shape than the generic case. Protocol is pre-registered to prevent post-hoc rationalization during Session 2c analysis. Also amended the Decision surface section to add `defer` as a fourth outcome tier and to cross-reference the protocol.
- **2026-04-24 — Forward-looking lesson from Session 2c (commits `0e04079` → `e5510a8` → `48320c8` → `3767639`): Filter-rule activation-rate sanity check.** Session 2c completed the study with `defer` outcome and discovered post-hoc that the variant filter was a structural no-op on the chosen universe — minimum signal-to-earnings gap was ~16 trading days, exceeding the widest blackout tested (X=10). The decision was correct under the pre-registered protocol (anti-rationalization clause held; defer reached via combined-rule default branch when gap metrics were non-estimable), but the study could not test what it was designed to test. Going forward, any filter-rule study (this one's future iterations or other filter-rule studies) should pre-register a rule-activation-rate sanity check: the most aggressive variant must filter ≥10% of signals for the variant comparison to be meaningful. If activation falls below threshold during a study run, the result is a study-design finding, not an efficacy finding, and the design should be re-evaluated before re-running. **This amendment captures a forward-looking lesson; it does not modify Session 2c's pre-registration or decision (both immutable per pre-registration discipline).**
