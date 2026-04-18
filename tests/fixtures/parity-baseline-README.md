# Parity Baseline

- Captured: 2026-04-17 (HST)
- Captured by: Phase 1 execution (Task 28)
- Universe mode: A (Wikipedia scrape)
- Universe version header: `2026-04-17-1`
- Universe ticker count: 517
- Fixtures included: finviz14Apr2026.csv, finviz15Apr2026.csv, finviz16Apr2026.csv
- Fixtures skipped (and why): none (finviz14Apr2026v2.csv was removed from source folder prior to execution)
- Parity status: active
- Notes:
  - Baseline captures only `watch`, `skip`, and `error` buckets — legacy evaluator did not produce A+ on any of these days.
  - Legacy evaluator did NOT include Trend Template; new evaluator's TT gate will demote many legacy-`watch` tickers to `skip`. Those divergences are expected and should be documented in `expected-diffs.yaml` after first parity run.
  - Ticker counts differ between fixtures (62 / 87 / 91 tickers across the 3 dates) because the Finviz screener universe changed day-to-day.
  - Each fixture has one legacy `error` row — likely a ticker with a data-fetch issue on that date.
