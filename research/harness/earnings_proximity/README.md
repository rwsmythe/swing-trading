# Earnings-proximity replay harness

Synthetic-replay study harness for `research/studies/earnings-proximity-exclusion.md`.

## Run

Smoke-slice (2 tickers, 2 trading weeks, all 5 variants):

```bash
python -m research.harness.earnings_proximity.run \
    --tickers AAPL,SOFI \
    --window-days 10 \
    --variants 0,3,5,7,10 \
    --output-dir research/harness/earnings_proximity/smoke-out/
```

The full parameter sweep (~500 tickers × ~504 trading days × 5 variants)
is Session 2c's job. The smoke invocation above is a shape check only.

## Modules

- `fetchers.py` — OHLCV + earnings fetch with disk caching (no retry/backoff
  scaffolding — let yfinance errors propagate; cache is idempotent on re-run).
- `replay.py` — replay driver. Iterates trading days, builds batch + candidate
  contexts, calls `swing.evaluation.evaluator.evaluate_one`, emits A+ signals.
- `simulator.py` — trade-outcome simulator: next-bar trigger, intraday-low
  stop, gap-stop fill-at-open, time-cap. Emits R-multiple + gap-through flag.
- `variants.py` — earnings-proximity variant applicator. Filters A+ signals
  whose next earnings date is within `blackout_trading_days` trading days.
- `metrics.py` — aggregator: expectancy, gap-through rate, gap-magnitude,
  signal volume per variant.
- `provenance.py` — run manifest emission (git SHA, yfinance version,
  universe hash, variant list, cache hit/miss counts).
- `run.py` — CLI entrypoint + orchestration.

## Cache

OHLCV and earnings caches live OUTSIDE the repo at
`%USERPROFILE%/swing-data/research-cache/` per the CLAUDE.md Drive-sync
invariant. Subdirectories:

- `ohlcv/<TICKER>.parquet` — daily bars, indexed by date.
- `earnings/<TICKER>.json` — list of scheduled earnings dates + `fetched_ts`.

Cache is idempotent: an interrupted fetch leaves already-cached tickers
intact; re-running the harness resumes from where it stopped.

## Phase isolation

This harness imports READ-ONLY from `swing.evaluation`, `swing.recommendations`,
and `swing.config`. It does NOT:

- Write to `%USERPROFILE%/swing-data/swing.db`.
- Modify any file under `swing/`.
- Use `swing.web.ohlcv_cache` or `swing.web.price_cache` (those are
  request-scoped, HTTP-wired operational caches — unsuitable for replay).
