# S&P 1500 Universe Expansion Study

**Date:** 2026-04-25
**Companion to:** `./candidate-sparsity-diagnostic.md` (immediate predecessor; establishes the universe-variant comparison methodology this study extends).
**Brief:** `../../docs/sp1500-universe-study-brief.md`.
**Status:** Pre-registration (D1) — descriptive only; no production-code recommendations.

---

## Pre-registration

*This section is committed BEFORE D2 (loader + driver tests + supporting code), D3 (data run), and D4 (findings) per the discipline established in `./earnings-proximity-exclusion-results.md` §"Pre-registration" and `./harness-vs-production-parity.md` §"Pre-registration." The git history must show D1 → D2 → D3 → D4 ordering for the study to be honestly pre-registered. Subsequent sections (Run details, Results, Tier classification, Findings, …) will be appended in D4 only AFTER D3's outputs are inspected. The pre-registration sections below — Hypothesis, Decision tiers, Anti-rationalization clause, Liquidity reporting posture, Sample-size limitation, Surfaces NOT measured, Provenance commitments, Run procedure, Residual confounds — are frozen at D1 and will not be modified post-data.*

### Hypothesis statement

> Expanding the harness universe from SPX+NDX (~516 tickers) to the S&P Composite 1500 (~1,500 tickers — combining iShares IVV, IJH, IJR holdings) produces a meaningful A+ rate uplift at the operator's actual 1× capital ($7,500), with manageable data-quality and liquidity profile.

The candidate-sparsity diagnostic (Tranche C, 2026-04-24) measured A+ rates across 4 universe×capital cells. At constant 1× capital, Russell 3000 produced ~4.6× the SPX+NDX rate but came with materially worse data quality (54% absent earnings data), mid/small-cap survivorship-bias inheritance, and 14 yfinance OHLCV-fetch failures. **S&P 1500 is the measured middle ground** — adds the S&P MidCap 400 + S&P SmallCap 600 to SPX 500, avoiding the worst microcap problems while plausibly producing somewhere between 2× and 4× the SPX+NDX rate. This study verifies the rate uplift AND characterizes data-quality / liquidity / sector profile on this specific universe at the operator's 1× capital.

This study scopes to **S&P 1500 only**. It is not a comparison of every plausible universe variant; it is a focused test of a specific candidate. Findings will be descriptive; the operator decides whether to act.

### Pre-registered decision tiers (frozen at D1)

Computed across all (ticker, date) evaluations in the S&P 1500 1× run, compared against the diagnostic's existing SPX+NDX 1× baseline (5 A+ over 260,064 ticker-days = **0.00193 % per ticker-day**).

- **Tier 1 — Adopt-candidate.** A+ rate uplift ≥3× SPX+NDX baseline (i.e., ≥**0.00580 %** per ticker-day on S&P 1500) AND <30 % of A+ signals carry `absent_earnings_data=True`. Interpretation: S&P 1500 is a viable production-universe candidate; warrants operator decision on whether to switch and over what cadence (immediate, A/B comparison, etc.). Study findings will include sector + liquidity characterization to inform that decision.

- **Tier 2 — Mixed.** A+ rate uplift ≥2× but <3× SPX+NDX baseline (i.e., **0.00387 %** ≤ rate < **0.00580 %** per ticker-day) OR ≥3× rate uplift but with ≥30 % absent earnings data OR rate uplift in the 2–3× range with concerning sector concentration (defined: any single sector accounts for ≥40 % of A+ signals). Interpretation: meaningful uplift exists but at observable cost; operator decides whether tradeoff is acceptable for their workflow.

- **Tier 3 — Not viable.** A+ rate uplift <2× SPX+NDX baseline (i.e., rate < **0.00387 %** per ticker-day). Interpretation: S&P 1500 expansion doesn't deliver enough rate uplift to justify the noise of a larger universe. SPX+NDX remains the operational universe.

Tier evaluation procedure: compute the S&P 1500 A+ rate per ticker-day; compute the multiplier vs the 0.00193 % baseline; apply the absent-earnings-data and sector-concentration gates per the rules above. The two metrics (rate uplift; absent-data fraction; sector concentration) are evaluated independently against their thresholds; the resulting tier is a conjunction per the definitions above.

### Anti-rationalization clause

The tier boundaries (3×/2× rate uplift; 30 % earnings absence; 40 % sector concentration) are frozen at D1. If post-data results sit near a boundary (e.g., 2.95× rate uplift with 28 % earnings absence), the result IS what the frozen boundaries say it is; no boundary adjustment to push it across. The D4 findings writeup may discuss the proximity but the classification is what it is. D5+ adversarial-review fixes can clarify framing or correct factual errors but cannot move tier boundaries.

### Liquidity profile reporting (descriptive, not gating)

The study reports the avg daily $ volume distribution for A+ signals (median, 25th percentile, fraction below $500K/day, fraction below $1M/day). At the operator's 1× capital ($7,500 with ~10 % position size ≈ $750 trade), liquidity is unlikely to be a binding constraint, so this is descriptive — the operator can read the distribution and decide whether any execution-difficulty concerns warrant attention. **Liquidity does NOT affect tier classification.** Smuggling implicit gating language into D4 ("only X % are tradable" implies a gate) is an anti-rationalization violation.

### Sample-size limitation

Single 504-session window on S&P 1500 produces a single observation of the rate. For tighter inference, a multi-window or rolling-window characterization would be the named follow-on. The study's tier classification on this sample is descriptive of THIS WINDOW; it does NOT establish the rate stable across regimes. Wilson 95 % CIs will be reported on the rate; non-overlap with the SPX+NDX 1× CI [0.00083 %, 0.00453 %] is suggestive of a non-zero rate difference but is not a formal hypothesis test (Newcombe interval on the difference would be the proper instrument).

### Surfaces explicitly NOT measured

- Trade outcomes (expectancy, win rate, gap-through statistics). The harness's `simulate_trade` is not invoked. This study measures rate, not edge.
- Universe membership drift (S&P composite reconstitution timing; the snapshot is fixed at fetch date).
- Sector classification accuracy (uses iShares' reported sector field; may differ from production's GICS or other source). Reported as-fetched; not cross-validated.
- Pattern shape distribution among A+ signals (no flag/cup-with-handle/flat-base classifier in the harness yet; reference to `docs/phase3e-todo.md` §3e.6).
- 5× capital cell on S&P 1500. Operator deferred capital-driven workflow changes (per `docs/orchestrator-context.md` 2026-04-25 decision); 1× is the operationally relevant cell.
- Other universe variants (ITOT, MSCI USA Investable Market, Wilshire 5000). If S&P 1500 is borderline and another variant would be informative, the return report will FLAG; the study itself will not silently expand scope.
- Any production-code change (Phase 2 carve-out NOT granted).

### Provenance commitments

The D3 run manifest will record:

- Harness git SHA at the time of the D3 run (post-D2 commit).
- Universe metadata: source URLs (3 iShares CDN URLs for IVV / IJH / IJR), per-ETF fetch date, per-ETF ticker count, post-dedupe ticker count, post-equity-filter ticker count, SHA-256 of the combined universe ticker list.
- Capital: $7,500 (operator's `max(starting_equity, risk_equity_floor)`) at multiplier 1.0 → effective_equity $7,500.
- Window: 2024-04-19 → 2026-04-23 (504 NYSE sessions).
- Cache stats: yfinance OHLCV hits/misses; earnings hits/misses.
- A+ count, evaluation count, per-criterion production-gated blocker counts (computed via `recompute_binding_prod_gated.py` per the candidate-sparsity diagnostic R1 Critical lesson; emitted-order counts preserved as audit trail).
- Sector breakdown of A+ signals (sector source: iShares CSV `Sector` column at fetch date).
- Liquidity distribution of A+ signals (avg daily $ volume per A+ ticker over the prior 20 sessions of each A+ date, computed from cached OHLCV).
- Data-quality stats: fraction of A+ signals with `absent_earnings_data=True`; tickers in the universe with yfinance OHLCV-fetch failures; tickers with insufficient OHLCV history at evaluation time (skipped per `_MIN_BARS_FOR_EVALUATION`).

If iShares URLs publish an update mid-fetch (each ETF's holdings page may be refreshed independently), the per-ETF fetch dates will diverge; the manifest will surface this and the D4 writeup will flag if the universe is internally inconsistent.

### Run procedure (locked by pre-registration)

1. After D2 lands and tests pass, run the diagnostic-style driver against `sp_1500 × 1×`. The existing driver (`research/harness/earnings_proximity/scripts/diagnostic_run.py`) already supports `--universe sp_1500`; D2 work is the additive supporting-code (sector-data extraction for D4 reporting, plus tests).
2. Inspect output WITHOUT computing tier classification first — verify the run completed without errors, manifest is written, output schema is correct, cache hit rates are reasonable.
3. Run `recompute_binding_prod_gated.py` against the run directory to produce `binding_constraints_prod_gated.csv` (the primary metric per the diagnostic R1 Critical lesson).
4. Compute tier classification per the frozen thresholds above.
5. Write D4 findings doc; do NOT modify D1's pre-registration sections — they are frozen.

### Residual confounds, acknowledged at D1

These are confounds the study inherits and cannot eliminate. They are documented here so any near-boundary tier classification can be interpreted in the right frame:

- **Survivorship bias.** The replay uses current-roster IVV / IJH / IJR holdings as of fetch date. Delisted tickers are absent. Effect is plausibly larger on small-caps (IJR) than on large-caps (IVV); the universe-composition direction this study reports is a lower bound on what an FTSE-faithful, point-in-time, delisting-aware version would show.
- **Fixed-universe at fetch date; no point-in-time membership reconstruction.** S&P 500/400/600 index reconstitution is continuous (S&P committee adjustments) but iShares' tracking ETFs lag. The 2026-04-25 fetch is applied to historical 2024–2026 data, over-including post-2024 entrants and under-including pre-2024 exits.
- **iShares-derived ticker list, not S&P-direct.** Authoritative S&P composite membership comes from S&P Global directly (paid feed); this study uses iShares tracking-fund holdings as a free, reproducible proxy. Any shortfall vs the nominal 1,500 figure will be reported in D4 and is not in itself a defect; the diagnostic uses the same iShares-derived approach for Russell 3000 (2,579 of nominal 3,000+).
- **Earnings-calendar coverage variability across cap tiers.** yfinance `Ticker.get_earnings_dates()` coverage drops on smaller-cap names (Russell 3000 saw 54 % absent on Run C; SPX+NDX saw 0 %). The S&P 1500 includes ~1,000 mid/small-caps; the absent-data rate will likely be intermediate. The 30 % gate is calibrated against a plausible mid/small-cap absence rate; if absence is dramatically higher than expected, the Tier 1 gate is automatically failed.
- **`current_equity` is config-derived, not DB-derived.** `swing.config.toml`'s `[account]` section gives $7,500 (`max(starting_equity=$1,200, risk_equity_floor=$7,500)`); operator's actual current equity may differ by realized P&L and cash movements. Per the candidate-sparsity diagnostic precedent, the config-derived value is the reference for "operator capital" until the operator instructs otherwise.
- **Cache-warm assumption.** Russell 3000's run already cached most S&P 1500 tickers (~1,500 of 2,579); cold S&P 1500 names are a strict subset. yfinance throughput at run time may still be a constraint; cold-fetch failures are recorded as data-quality observations and tickers that cannot be priced are skipped silently in evaluation.

---

## Run details (D4 — appended post-D3)

*This section is intentionally empty at D1; will be filled at D4.*

## Results — rate (D4 — appended post-D3)

*This section is intentionally empty at D1; will be filled at D4.*

## Results — per-criterion binding constraints (production-gated) (D4 — appended post-D3)

*This section is intentionally empty at D1; will be filled at D4.*

## Results — sector breakdown of A+ signals (D4 — appended post-D3)

*This section is intentionally empty at D1; will be filled at D4.*

## Results — liquidity distribution of A+ signals (D4 — appended post-D3)

*This section is intentionally empty at D1; will be filled at D4.*

## Results — data-quality characterization (D4 — appended post-D3)

*This section is intentionally empty at D1; will be filled at D4.*

## Tier classification (D4 — appended post-D3)

*This section is intentionally empty at D1; will be filled at D4.*

## Findings (descriptive, not prescriptive) (D4 — appended post-D3)

*This section is intentionally empty at D1; will be filled at D4.*

## What this study does NOT say (D4 — appended post-D3)

*This section is intentionally empty at D1; will be filled at D4.*

## Caveats and limitations (D4 — appended post-D3)

*This section is intentionally empty at D1; will be filled at D4.*

## Open questions for the operator (D4 — appended post-D3)

*This section is intentionally empty at D1; will be filled at D4.*

## Run artifacts (D4 — appended post-D3)

*This section is intentionally empty at D1; will be filled at D4.*
