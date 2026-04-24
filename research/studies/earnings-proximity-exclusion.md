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

One of: `reject` / `shadow` / `promote`. If `promote`, name the chosen `blackout_trading_days` value.

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
