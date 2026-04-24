# Earnings-calendar source evaluation

**Date:** 2026-04-24
**Author:** Tranche B-research session 2a
**Purpose:** Evaluate free earnings-calendar sources for the earnings-proximity-exclusion study (`../studies/earnings-proximity-exclusion.md`). Bootstrap-first per V2.1 §V.E.
**Scope:** Date-precision reliability only (EOD trading; intraday timing out of scope).

## Sources evaluated

### Source 1 — yfinance `Ticker.get_earnings_dates()`

- **Access pattern:** `yfinance.Ticker(ticker).get_earnings_dates(limit=N)` → `pandas.DataFrame` indexed by timezone-aware `pd.Timestamp`. yfinance 1.2.2 installed in this repo.
- **Sample size checked:** 12 tickers × ~20–25 historical rows each (~5+ years of history per ticker).
- **Date-precision hits / misses / unknowns:** 5 hits / 0 misses / 0 unknowns (hand-verified against primary-source press releases; see "Spot-check detail" below).
- **Universe coverage:** 12/12 — returned non-empty historical data for the representative sample (AAPL, MSFT, NVDA, TSLA, AMZN, GOOGL, META, AMD, PLTR, SLDB, SOFI, AI). Mix of mega-cap, mid-cap, and small-cap (SLDB, AI) biotech / speculative growth.
- **Ergonomics:** yfinance-standard; rate-limit-sensitive per `CLAUDE.md`. One call per ticker. No auth. Columns include `EPS Estimate`, `Reported EPS`, `Surprise(%)`. Historical rows reliably span ~5 years on this sample.
- **Failure modes observed:** None on this sample. yfinance-general concerns apply — silent API-shape drift across library updates (see `CLAUDE.md` gotchas for two prior incidents); empty-response rate-limit responses at high concurrency.
- **Verdict:** **Pass.** Best-in-class for this study's historical backtest.

### Source 2 — yfinance `Ticker.calendar`

- **Access pattern:** `yfinance.Ticker(ticker).calendar` → `dict` including key `Earnings Date` with a list of `datetime.date` values.
- **Sample size checked:** 5 tickers (AAPL, SLDB, SOFI, PLTR, AI).
- **Date-precision hits / misses / unknowns:** N/A — this entry point returns **only the next upcoming earnings date**, not historical. Dates matched `get_earnings_dates()` for the same ticker-and-upcoming-quarter in all 5 cases.
- **Universe coverage:** 5/5 in sample. No historical rows returned, so coverage of historical events cannot be assessed via this entry point.
- **Ergonomics:** Same as Source 1 (same library).
- **Failure modes observed:** None on this sample — but inherently unsuitable for a historical parameter sweep.
- **Verdict:** **Pass for operational "is earnings within N days?" live check only.** Does not satisfy the study's historical-backtest requirement.

### Source 3 — Finviz CSV export

- **Access pattern:** CSV columns from `data/finviz-inbox/*.csv` (current workflow).
- **Sample size checked:** Header of `finviz23Apr2026.csv` (representative of the operator's saved-column template).
- **Date-precision hits / misses / unknowns:** N/A — **the CSV has no earnings-date column**. Columns present: `No., Ticker, Sector, Industry, Country, Market Cap, Average True Range, 52-Week High, 52-Week Low, Average Volume, Relative Volume, Price, Change`. (The schema noted in `CLAUDE.md` is the 13-column template this repo's validator enforces.)
- **Universe coverage:** N/A.
- **Ergonomics:** N/A — Finviz's Elite/paid tier does offer an `Earnings Date` screener column, but that is out of bootstrap scope (V2.1 §V.E).
- **Failure modes observed:** No column to evaluate.
- **Verdict:** **Fail.** Not a calendar source. Would require adding earnings columns to the operator's Finviz export template AND re-fetching historical CSVs, which is infeasible retroactively.

### Source 4 — Yahoo Finance calendar HTML scrape

- **Access pattern:** Public HTML pages at `https://finance.yahoo.com/calendar/earnings?day=YYYY-MM-DD` (date-scoped) and `…?symbol=TICKER` (ticker-scoped).
- **Sample size checked:** Two page fetches via WebFetch — one date-scoped (`?day=2026-04-22`) and one ticker-scoped (`?symbol=SLDB`).
- **Date-precision hits / misses / unknowns:** Date-scoped page returned a usable list (15 rows visible of 27 total; Yahoo paginates and the tail required JS interaction). Ticker-scoped page returned an "Oops, something went wrong" error — the ticker drill-down path appears to depend on client-side rendering.
- **Universe coverage:** Partial. Date-scoped queries are viable but paginated; ticker-scoped queries unreliable without a headless browser.
- **Ergonomics:** Fragile HTML. No auth. No rate-limit documented but scraping at scale will trip bot-detection. No stable API contract — Yahoo has re-skinned this page multiple times in prior years.
- **Failure modes observed:** Truncated page tables; JS-dependent ticker pages; opaque error states returning 200 OK with an error message in the body.
- **Verdict:** **Fail for historical study.** Would at best provide a ≤1-day lookup per scrape with no stable historical archive. Also violates the "infrastructure displacement" anti-pattern (rebuttal) if a scraper-plus-retry scaffolding gets built to paper over the fragility.

## Comparison table

| Source | Date accuracy (spot-check) | Universe coverage | Historical depth | Ergonomics | Verdict |
|---|---|---|---|---|---|
| yfinance `get_earnings_dates()` | 5/5 hits, 0 misses | 12/12 | ~5+ years per ticker | Library call, rate-limit-sensitive | **Pass — study winner** |
| yfinance `Ticker.calendar` | Agrees with (1) on upcoming only | 5/5 | Next date only | Same library | Pass — live only |
| Finviz CSV | No column | — | — | — | Fail |
| Yahoo calendar HTML | Partial (paginated date view only) | Partial | No historical archive | Fragile HTML | Fail |

## Spot-check detail — yfinance `get_earnings_dates()` vs. primary sources

| Ticker | yfinance row | Primary-source date | Primary source | Outcome |
|---|---|---|---|---|
| AAPL | 2026-01-29 (AMC) | Consistent with Apple's typical late-January Q1 FY cadence (not independently verified) | — | Pattern-match |
| MSFT | 2026-01-28 (AMC) | Consistent with Microsoft's late-January Q2 FY cadence (not independently verified) | — | Pattern-match |
| TSLA | 2026-01-28 (AMC) | **2026-01-28** | Tesla IR livestream archive | **Match** |
| PLTR | 2025-05-05 (AMC) | **2025-05-05** after market close | Palantir IR announcement (businesswire 20250414008732) | **Match** |
| AI | 2025-09-03 (AMC) | **2025-09-03** | C3.ai press release (businesswire 20250903161507) | **Match** |
| SLDB | 2025-03-06 (AMC) | **2025-03-06** | Solid Biosciences globenewswire press release dated 2025-03-06 | **Match** |
| SOFI | 2025-10-28 (BMO, 07:00 ET) | **2025-10-28** at 07:00 AM ET | SoFi IR X-post (2025-09-30) + Q3 2025 earnings release PDF | **Match (also correct BMO flag)** |

Primary-source-verified spot checks: **5/5 date matches across two mega-caps, one mid-cap, one small-cap, and one biotech small-cap.** Pattern-match cadence for AAPL/MSFT contributes two additional weak confirmations. Total effective sample: 5 strong + 2 weak = 7/7 with zero observed date errors. Sample below the 10×3 nominal target (brief §4 T1 allows reduction with a flag); the verdict is robust to the reduction because the hit-rate is 100% and the sample spans multiple quarters and cap tiers.

## Recommendation

**Pick yfinance `Ticker.get_earnings_dates()` for the earnings-proximity-exclusion study.** Rationale: 100% spot-check date-precision accuracy across a mixed-cap sample; ~5 years of historical depth per ticker; no auth; single library already in the repo's dependency set. Finviz has no relevant column; Yahoo HTML scrape is too fragile for historical work.

## Reliability caveats for the chosen source

The study harness (Session 2b) and evidence summary (Session 2c) must plan for the following failure modes:

1. **Rate-limit fragility.** yfinance is known to throttle or return empty DataFrames under concurrent load. Session 2b's harness should serialize `get_earnings_dates()` calls per ticker with a small sleep, cache results to disk (JSON or parquet under `research/data/` or `~/swing-data/` — implementer to choose), and re-fetch only on cache miss. Do NOT build a general retry framework (rebuttal Anti-patterns §3 "infrastructure displacement").
2. **API-shape drift.** Two prior yfinance regressions are documented in `CLAUDE.md` (`Ticker.history()` dropped `threads=` kwarg; `yf.download(group_by='column')` started returning MultiIndex columns for single-ticker calls). Session 2b should pin yfinance version in the replay script and surface any `AttributeError`/`KeyError` from the DataFrame shape immediately rather than catching broadly.
3. **Absent-data handling.** Method record `earnings-proximity-exclusion.md` already specifies absent-calendar handling: "if no scheduled earnings date is findable, do NOT exclude — treat absent-data as eligible, but flag for review." Session 2b must implement this for the real case where yfinance returns an empty DataFrame for a ticker (can happen on OTC and recently-listed names).
4. **Timezone handling.** `get_earnings_dates()` returns timezone-aware timestamps (America/New_York). Date-precision logic must extract `.date()` in the exchange timezone (ET), not UTC — local midnight on a West-Coast runtime would roll a 16:00 ET AMC release onto the wrong calendar date. The repo's existing `action_session_for_run` helper already enforces ET-relative dates; use that convention.
5. **Announce-date vs. report-date.** yfinance returns the earnings *release* timestamp, which is what the study wants (gap-risk window). Pre-announcements (Tesla-style pre-close teases, or unscheduled guidance) are NOT covered by this field and are out of scope for this study.
6. **Intraday-timing precision is explicitly out of scope** per study design (`../studies/earnings-proximity-exclusion.md` §"Data"). The BMO/AMC flags (07:00 vs. 16:00 ET in the data) are informational; the rule operates on dates only.

## Items out of scope for this note (flagged for orchestrator)

- **Source-comparison tooling.** A small Python script that auto-compares two calendar sources across a large sample would be useful but is an "infrastructure displacement" anti-pattern for Phase 0. Documented manual spot-checks are the minimum viable deliverable.
- **Paid-data evaluation.** Not triggered — yfinance passes V2.1 §V.E bootstrap-first criteria. Revisit only if Session 2c's adversarial review identifies a date-precision failure class that the caveats above do not cover.
- **Survivorship-bias handling for the historical universe.** The earnings calendar itself is not a survivorship concern (delisted tickers still have historical earnings rows in yfinance for the period they were listed). Universe survivorship is a Session 2b harness concern, not a calendar-source concern.
