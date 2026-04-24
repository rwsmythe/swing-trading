---
key: earnings-proximity-exclusion
name: Earnings-Proximity Exclusion
layer: universe
status: specified
baseline_or_predecessor: none (candidate universe currently has no earnings-aware filter)
version: 0.1.0
last_updated: 2026-04-23
---

# Earnings-Proximity Exclusion

## Definition

The rule excludes a ticker from the candidate universe on a given `action_session_date` if its next scheduled earnings announcement falls within X trading days of that date. X is a tunable parameter; the study in `../studies/earnings-proximity-exclusion.md` validates values X ∈ {3, 5, 7, 10}. Origin: internal — derived from V2.1 §V.D candidate-study list (earnings-proximity exclusion) and motivated by overnight gap-risk exposure that daily-bar entry signals do not measure.

## Inputs

- Ticker's next scheduled earnings date — sourced from a free earnings-calendar provider (selection deferred to Phase 0 task; see `../phase-0-tasks.md`). Date precision required; intraday timing not required for the EOD workflow.
- `action_session_date` — from the current pipeline run, computed via the repo's two-date model (`action_session_for_run`); see `CLAUDE.md`.
- NYSE trading-day calendar — already used in the repo (see `swing/evaluation` and the `action_session_for_run` helper).

## Parameters

- `blackout_trading_days: int` — default `5`, valid range `[0, 21]`. `blackout_trading_days = 0` disables the exclusion (baseline).

## Outputs

Boolean flag per `(ticker, action_session_date)` pair. `True` = excluded; `False` = eligible.

## Operator explainability

- **One-sentence rationale:** "Don't enter within N trading days of earnings — the gap risk isn't priced into the setup."
- **One-paragraph explanation:** "Stocks that announce earnings within a short window of your entry expose you to overnight gap risk that the stop cannot defend against. The setup signals (MA stack, VCP tightness, RS rank) are all daily-bar signals; they say nothing about what the stock does between the close and the next day's open. Excluding candidates close to earnings keeps the signal-action loop on the same risk basis the setup was measured on."
- **FAQ:** "Doesn't this lock me out of the best post-earnings moves?" → "Post-earnings is outside the blackout window; this rule doesn't prevent post-earnings entries. It prevents pre-earnings entries where the announcement is imminent."

## Validation notes

This record is `specified` status. The study in `../studies/earnings-proximity-exclusion.md` validates the parameter choice. Known caveats (to be tested during the study):

- (a) Free earnings-calendar sources (yfinance, Yahoo, Finviz) are often unreliable on before-market / after-market timing; for EOD trading this matters less than date-precision, but the study's data-quality step must verify source reliability on dates not times.
- (b) Small-cap and OTC tickers may have sparse or missing calendar coverage, which will need a handling rule (default: if no scheduled earnings date is findable, do NOT exclude — treat absent-data as eligible, but flag for review).

## Changelog

- 2026-04-23 — v0.1.0 — initial record, status `specified`, pre-study.
