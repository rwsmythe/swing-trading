# Historical-candidate source decision

**Date:** 2026-04-24
**Author:** Tranche B-research session 2a
**Purpose:** Pick the data source for the earnings-proximity-exclusion study's historical candidates. See study design at `../studies/earnings-proximity-exclusion.md`.

## Repo `candidates` table audit

Queried `%USERPROFILE%/swing-data/swing.db` read-only (URI mode `?mode=ro`).

- **Rows in `candidates`:** 1,220
- **Rows in `evaluation_runs`:** 14
- **Distinct `action_session_date` values:** 5 (2026-04-20, 2026-04-21, 2026-04-22, 2026-04-23, 2026-04-24)
- **Date range:** 2026-04-20 → 2026-04-24 (5 calendar days; 4 trading days — Apr 20 2026 is a Monday, Apr 24 a Friday)
- **Distinct A+ tickers (lifetime):** 1 (SLDB only)
- **A+ row count (lifetime, including duplicate per-run rows):** 3
- **Distinct (ticker, action_session_date) A+ pairs:** 2
- **`trades` table row count (real trades opened, all-time):** 1

## Statistical adequacy

Brief §4 T2 threshold is **≥120 distinct A+ trade signals across ≥60 trading days** to prefer Option A.

- Signal count: 2 vs. 120 — fails by **60×**.
- Date count: 4 trading days vs. 60 — fails by **15×**.

Option A is decisively insufficient. The repo's `candidates` table reflects roughly one week of live pipeline use post-Phase-3d shipping (operator's own walkthrough + a few nightly runs). It will not accumulate study-grade history on any timeline compatible with V2.1 §III.7's time budget — waiting for 60 trading days of live data equals ~3 months of continuous uninterrupted operator use, during which no study can start. That invalidates the goal of completing one decision-grade study early (V2.1 §V.A).

## Synthetic-replay sketch

Components needed for Option B (a minimum replay harness under `research/`):

### Inputs

1. **Historical EOD OHLCV per ticker** across the universe, covering the study window (target ≥2 years; stretch 3 years). Source: yfinance `Ticker.history()` or `yf.download()` with the existing `threads=False` guard (`CLAUDE.md` gotcha). Cached to disk in `research/data/ohlcv-cache/` (parquet or CSV — implementer's call; do NOT use the `OhlcvCache` in `swing/web/` which is request-scoped and under Phase-isolation).
2. **Historical RS universe.** The repo's RS universe CSV under `data/` (loaded via `swing.evaluation.rs.load_universe`) is treated as a single constant set for the replay. Acknowledged simplification — the real universe drifted over time, but reconstructing historical Finviz-filtered universes is out of scope and would itself be a multi-week data project.
3. **Historical earnings dates per ticker** via yfinance `get_earnings_dates()` (see `earnings-calendar-sources.md` for the decision). Cached identically.
4. **NYSE trading calendar** via the repo's existing exchange-calendars dependency (`action_session_for_run`, `exchange_calendars` import — read-only from `swing/evaluation/dates.py`).

### Reusable from `swing/` (read-only per `CLAUDE.md` Phase isolation)

Inventoried by `wc -l`; totals under 1,800 LOC across the three relevant packages:

| Module | Purpose | LOC | Reuse? |
|---|---|---|---|
| `swing.evaluation.context` | `CandidateContext`, `BatchContext`, `MarketContext` dataclasses | 39 | Full |
| `swing.evaluation.dates` | `action_session_for_run`, NYSE-aware date helpers | 64 | Full |
| `swing.evaluation.evaluator` | `evaluate_one`, `evaluate_batch` — the A+ dispatcher | 112 | Full |
| `swing.evaluation.scoring` | `bucket_for` — aplus/watch/skip classification | 39 | Full |
| `swing.evaluation.rs` | `compute_rs`, `load_universe` | 87 | Full |
| `swing.evaluation.criteria._base` | Shared criterion helpers (`sma`, `adr_pct`, `Result`) | 114 | Full |
| `swing.evaluation.criteria.*` | 11 criterion files (trend-template, VCP, RS, ADR, tightness, pullback, risk-feasibility, etc.) | 324 | Full |
| `swing.recommendations.sizing` | `compute_shares`, `SizingResult` (position sizing) | 64 | Full |
| `swing.recommendations.build` | Entry-target + stop-basis assembly | 97 | Mostly — adaptor may need a thin wrapper for the replay's simulated equity |
| `swing.trades.equity` | Equity math helpers | 74 | Mostly |
| `swing.trades.advisory` | Advisory rules (trail-MA, exit-below-MA) | 123 | Partial — useful for exit simulation, not all branches needed |
| `swing.trades.entry` / `.exit` / `.stop_adjust` | Trade lifecycle services | 337 | Minor — these are DB-writing services; a replay needs the numeric logic, not the persistence |

Reusable straight: ~1,040 LOC out of ~1,800 LOC (~**58%** full-reuse).
Reusable with a thin adaptor (no duplication of logic): ~350 LOC more (**~77% total reuse with adaptors**).
Clears the brief's **≥70% reuse** bar for Option B preference.

### New logic required

- **Replay driver loop** (~80–120 LOC). Iterates trading dates, for each date loads per-ticker OHLCV slices, computes per-ticker 12-week returns (universe-wide), builds `BatchContext`, constructs `CandidateContext` per ticker, calls `evaluate_one`, filters to `bucket == "aplus"`, emits (ticker, date, entry_target, initial_stop, earnings_date_next).
- **Trade-outcome simulator** (~80–120 LOC). For each A+ signal, simulates forward bars: trigger on the next bar's high crossing the entry target; on trigger, walks forward until stop is hit (intraday-low-breaches-stop OR open-gap-below-stop) or a time-cap is reached. Emits R-multiple per trade plus a `gap_through` boolean and `gap_magnitude_r` when applicable.
- **Earnings-variant applicator** (~30 LOC). For each variant `blackout_trading_days ∈ {0, 3, 5, 7, 10}`, filters the A+ signal set to exclude ones where the next earnings date is within `N` trading days of the signal date. Produces 5 filtered trade lists.
- **Metrics aggregator** (~40 LOC). Expectancy (mean R), gap-through rate, gap-magnitude mean/max, signal count per variant. Emits a CSV or markdown table.

Total new logic: ~230–310 LOC. All pure Python, no infrastructure.

### Estimated effort — Session 2b

- Bulk-fetch OHLCV + earnings for the chosen universe (~100–200 tickers), first-run caching: 30–60 min (yfinance rate-limit bounded).
- Replay driver + trade simulator + variant applicator + metrics: 2–3 hours.
- Debug / edge cases (empty bars, insufficient-history tickers, weekend/holiday handling): 1 hour.

**Total estimate: 3.5–4.5 hours.** Fits the Session 2b budget in `phase-0-tasks.md` (3–4 hours nominal) with modest risk of spillover. If the first-run data fetch balloons past 60 minutes on yfinance rate limits, splitting Session 2b into 2b-a (harness scaffold + cache warm-up) and 2b-b (replay + metrics) is a reasonable contingency.

### Decision criteria checklist (brief §4 T2)

- [x] Option A insufficient (≥120 signals / ≥60 days threshold failed by 60×/15×).
- [x] Option B port-import sketch: ≥70% logic reusable from `swing/`.
- [x] Option B effort fits Session 2b time budget (3–4 hours with spillover contingency noted).
- [x] No paid-data trigger (V2.1 §V.E).

## Decision

**Option B — synthetic replay.**

## Rationale

The repo's `candidates` table has 2 A+ signals across 4 trading days — 60× below the decision threshold for signals and 15× below for days. Live accumulation would take roughly 3 months of uninterrupted operator use before the study could begin, which contradicts V2.1 §V.A's directive to produce one complete decision-grade study early.

The synthetic-replay path is viable because the A+ evaluation logic, position sizing, trade equity math, and NYSE calendar helpers are all already implemented as pure or near-pure functions in `swing/evaluation/`, `swing/recommendations/`, and `swing/trades/`. Measured by LOC, ≥77% of the code Session 2b needs can be reused read-only (~1,390 of ~1,800 LOC across the three relevant packages). The new code — replay driver, trade simulator, variant applicator, metrics aggregator — totals ~230–310 LOC and fits the Session 2b budget.

The one acknowledged verisimilitude concession is that the replay uses a fixed RS universe (the repo's current CSV) rather than reconstructing the historical Finviz-filtered universe at each date. Reconstructing that would itself require daily Finviz CSV snapshots across the replay window, which do not exist and cannot be retroactively recovered. The concession is acceptable because:

- The study's null hypothesis is about earnings proximity, not about universe construction.
- The four earnings-proximity variants all operate against the same universe, so universe drift is a common-mode effect (cancels out in cross-variant comparisons).
- A note on this limitation must appear in Session 2c's evidence summary.

## Implications for Session 2b (harness build)

1. **Script location.** Harness lives at `research/` (suggested path: `research/harness/earnings_proximity/run.py` with `__init__.py` gating a small support module). NOT under `swing/` (Phase-isolation invariant).
2. **Reuse pattern.** Imports from `swing.evaluation`, `swing.recommendations`, `swing.trades` are read-only; the harness must NOT write to any `swing/*` database tables and must NOT mutate `swing/` state. If a reused function requires a `Config` object, construct one in-harness rather than loading the operator's `swing.config.toml`.
3. **Data cache.** OHLCV and earnings caches go under `%USERPROFILE%/swing-data/research-cache/` (outside Drive per `CLAUDE.md` invariant), not under the Drive-synced `research/` directory. This keeps multi-gigabyte parquet/CSV out of Drive sync and avoids the `os.replace` cross-device failure mode documented in `CLAUDE.md`.
4. **Universe.** Use the repo's current RS universe CSV as the fixed replay universe. Record its `universe_version` hash (via existing `swing.evaluation.rs.universe_version_hash`) in the run manifest for provenance (V2.1 §IV.C).
5. **Window.** Target 2 years of trading days (~504 trading days). At ~500 tickers × 504 days × one OHLCV fetch per ticker on first run, batching via `yf.download()` multi-ticker mode (with `threads=False`) is strongly preferred over per-ticker `Ticker.history()` calls.
6. **Earnings-cache policy.** One `get_earnings_dates(limit=30)` call per ticker covers the full window + forward buffer. Cache JSON per ticker; skip recache within 24h.
7. **Absent-data semantics.** Method record `earnings-proximity-exclusion.md` mandates "no earnings date found → do NOT exclude, flag for review." Session 2b implements this; Session 2c reports the flagged-signal count.
8. **Provenance manifest.** Write a JSON run manifest alongside the metrics output: git SHA, run timestamp, yfinance version, universe hash, variant list, fetch-cache hit/miss counts, absent-data ticker count (per V2.1 §IV.C).
9. **Parity standard** (per study design and V2.1 §VII.B). Session 2b must include one synthetic fixture test (excluded vs. eligible pair) that produces bit-identical classification — this is the "fixture identity" half of the parity standard. The "toleranced vendor-backed equivalence" half is satisfied by the 5/5 spot-check already documented in `earnings-calendar-sources.md`.

## Flagged but not resolved (escalations)

- **Universe-drift disclosure.** Session 2c must disclose the fixed-universe concession in the evidence summary. Recommended wording: "Replay uses the current RS universe at all historical dates. A delisted-ticker pollution check (count of tickers in the universe that were delisted or inactive for part of the window) should be reported as a data-quality footnote."
- **Delistings handling.** V2.1 §V.E and the rebuttal-response §4 flag delistings as a known bootstrap risk. yfinance does carry delisted tickers with their historical bars, so the immediate study is not blocked. If the Session 2c evidence shows survivorship bias materially affecting expectancy estimates (e.g., by excluding wipeout trades), the orchestrator should revisit bootstrap posture per V2.1 §V.E's time-box.
- **Session 2b splittability.** If first-run data fetching exceeds 60 minutes due to yfinance rate limits, Session 2b may split into 2b-a (scaffold + cache warm-up) and 2b-b (replay + metrics). The orchestrator should expect that possibility and confirm whether the split is in-scope for the existing 3–4 hour budget or requires re-scoping.
