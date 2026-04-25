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

## Run details

- **Run timestamp:** 2026-04-25T08:10:24
- **Harness git SHA at run:** `56e0677` (post-D2 follow-up, includes the sector-extraction helper).
- **Universe:** `sp_1500`, post-dedupe equity count: **1,506**. Combined from iShares IVV (S&P 500) + IJH (S&P MidCap 400) + IJR (S&P SmallCap 600) holdings CSVs.
  - Source URLs (from `research.harness.earnings_proximity.universe_variants`): IVV (`/239726/...IVV_holdings`), IJH (`/239763/...IJH_holdings`), IJR (`/239774/...IJR_holdings`). Recorded in `universe_provenance_supplement.json` alongside the run manifest.
  - Snapshot: `~/swing-data/research-cache/universe-snapshots/sp_1500_2026-04-25.csv`, SHA-256 `3ebb5da7b3b9fa0b7d92b5f3c37de292f119bd46c8e836a5783f9b573ecdc5a2`. The snapshot CSV records each ticker's source sub-ETF URL.
  - All three iShares URLs were fetched within seconds of each other in a single `_load_or_fetch_ishares` call on 2026-04-25T07:34Z. Per-URL fetch timestamps are not tracked at the loader level; fetch-date skew across the three sub-ETFs is bounded by network round-trip time.
  - **Manifest provenance gap:** `run_manifest.json` records `universe_source_url: null` because the loader contract emits a single URL only for single-URL universes; `universe_provenance_supplement.json` closes this gap by enumerating all three URLs explicitly. Future loader work could add `source_urls` plural to the `UniverseVariant` dataclass; out of scope for this study.
- **Universe hash:** `0866d9cd596490ae7a706ad0577fbf35cabee293fd5ba38612e3b59088ae8511` (SHA-256 of newline-joined ticker list).
- **Universe nominal vs measured.** The S&P Composite 1500 nominally aggregates 500 + 400 + 600 = 1,500 issues. The 1,506 measured count reflects the iShares-tracking-fund's holdings on 2026-04-25, after equity-only filtering and dedupe across the three lists. Per the Russell 3000 precedent (2,579 vs nominal 3,000+), iShares-derived ticker counts are slightly off the index-direct count due to dual-class shares, share-class reclassifications, and recent rebalancing not yet reflected. Per-sub-ETF row counts in the snapshot CSV: IVV 503 unique equity rows, IJH 401 unique, IJR 602 unique (sums to 1,506 with no cross-sub-ETF duplicates observed at this fetch).
- **Window:** 2024-04-19 → 2026-04-23 (504 NYSE sessions). Same as the candidate-sparsity diagnostic baseline.
- **Capital:** $7,500 (1×, derived from `swing.config.toml` `[account]` via `max(starting_equity, risk_equity_floor)`). Identical to candidate-sparsity diagnostic Run A.
- **Cache stats:** OHLCV 1,499 hits / 8 misses (8 cold fetches; cache went from 2,595 files → 2,603); earnings 1,497 hits / 9 misses. Russell 3000's earlier cache warm-up covers most of S&P 1500; the cold residue is the small subset of SP1500 tickers not in Russell 3000's 2,579 holdings.
- **Evaluations / ticker-days:** 750,440 / 759,024 = 98.87 %. The 8,584 skipped ticker-days are tickers with < 200 bars of OHLCV history at the corresponding session (the harness's `_MIN_BARS_FOR_EVALUATION` floor).

## Results — rate

| Metric | Value |
|---|---:|
| A+ count | **35** |
| Evaluation count | 750,440 |
| Ticker-days (universe × sessions) | 759,024 |
| **Rate per ticker-day** | **0.00461 %** |
| Wilson 95 % CI on rate | [0.00332 %, 0.00641 %] |
| **Rate uplift vs SPX+NDX 1× baseline** | **2.39×** |

Baseline: SPX+NDX 1× (candidate-sparsity diagnostic Run A) — 5 A+ over 260,064 ticker-days = 0.00193 % per ticker-day, Wilson 95 % CI [0.00083 %, 0.00453 %].

**Statistical-inference framing.** The Wilson 95 % CIs of SPX+NDX 1× ([0.00083 %, 0.00453 %]) and S&P 1500 1× ([0.00332 %, 0.00641 %]) **overlap** in the interval [0.00332 %, 0.00453 %]. The disjoint-CI shortcut that the candidate-sparsity diagnostic invoked for the SPX+NDX-vs-Russell comparison (where CIs were disjoint) does not apply here. A formal Newcombe interval on (p_SP1500 − p_SPX+NDX) would be the proper test for whether the difference is robustly non-zero; that test is not run here. The point-estimate uplift of 2.39× is the value used for tier classification (per D1's pre-registered procedure, which uses point-estimate uplift, not a hypothesis test on the difference). Operator interpretation that treats 2.39× as a precise effect size on this single window is over-confident; the per-rate Wilson interval bounds inform how much sampling noise the point estimate carries.

For comparison context (NOT used in tier classification):
- Russell 3000 1× (candidate-sparsity diagnostic Run C): 112 A+ over 1,299,816 ticker-days = 0.00890 % per ticker-day. SP1500 sits between SPX+NDX (0.00193 %) and Russell 3000 (0.00890 %), consistent with the broadening-universe gradient.
- Session 2a production anchor (Finviz-filtered): ~0.5 % per ticker-day (n=2/400, Wilson CI [0.137 %, 1.806 %]). The residual gap from SP1500 1× (0.00461 %) to the production anchor remains ~108×.

## Results — per-criterion binding constraints (production-gated)

Per the candidate-sparsity diagnostic R1 Critical lesson, the **production-gated** blocker (production gating order: `risk_feasibility` hard filter → trend-template gate → VCP fail-count) is the primary metric. Counts below sum to the evaluation total; the `<aplus>` row is the count of (ticker, date) pairs that reached A+. Source: `binding_constraints_prod_gated.csv`.

| Criterion | Count | % of evaluations |
|---|---:|---:|
| `<aplus>` | 35 | 0.00466 % |
| TT1_above_150_200 | 319,193 | 42.53 % |
| TT2_150_above_200 | 86,590 | 11.54 % |
| **risk_feasibility** | **72,419** | **9.65 %** |
| TT5_above_50 | 65,533 | 8.73 % |
| ma_stack_10_20_50 | 45,118 | 6.01 % |
| adr | 44,426 | 5.92 % |
| proximity_20ma | 26,497 | 3.53 % |
| TT6_above_52w_low_30pct | 22,993 | 3.06 % |
| TT4_50_above_150_200 | 22,110 | 2.95 % |
| ma_short_rising | 16,931 | 2.26 % |
| TT3_200_rising | 14,135 | 1.88 % |
| prior_trend | 11,149 | 1.49 % |
| tightness | 2,470 | 0.33 % |
| TT7_within_52w_high_25pct | 679 | 0.090 % |
| vcp_volume_contraction | 144 | 0.019 % |
| orderliness | 18 | 0.0024 % |

The emitted-order audit-trail metric is preserved at `binding_constraints.csv`; it is not the primary metric per the diagnostic precedent.

`risk_feasibility` (production-gated, 1× capital) on S&P 1500 sits at 9.65 % — between Russell 3000 1× (6.91 %) and SPX+NDX 1× (18.62 %). This is consistent with the structural pattern observed in the candidate-sparsity diagnostic: at fixed 1× capital, risk_feasibility blocking shrinks as the universe widens (more low-priced names where the per-share risk budget binds less). This study does not run a 5× cell on S&P 1500 (out of scope per D1) so the capital-binding-shrinkage pattern is not measured directly.

## Results — sector breakdown of A+ signals

Sector source: iShares CSV `Sector` column at fetch date 2026-04-25, via `load_sp_1500_sector_map`. Tickers absent from the iShares sector map are bucketed as "Unknown."

| Sector | A+ count | % of A+ |
|---|---:|---:|
| Information Technology | 7 | 20.0 % |
| Consumer Discretionary | 6 | 17.1 % |
| Health Care | 6 | 17.1 % |
| Industrials | 5 | 14.3 % |
| Materials | 4 | 11.4 % |
| Energy | 2 | 5.7 % |
| Financials | 2 | 5.7 % |
| Real Estate | 2 | 5.7 % |
| Communication | 1 | 2.9 % |

Largest single sector: Information Technology at **20.0 %**, well below the D1 sector-concentration gate of 40 %. Nine of eleven nominal GICS sectors are represented in A+; Utilities and Consumer Staples produce zero A+ signals on this run. This study does not characterize how S&P 1500's sector composition compares to the universe sector composition (the iShares CSVs include sector weights for the universe; computing a "sector over- or under-indexing" ratio would require post-hoc joining; out of scope for this D4).

## Results — liquidity distribution of A+ signals

For each A+ (ticker, date), avg daily $ volume over the prior 20 NYSE sessions is computed from cached OHLCV (`Close * Volume`, mean over the trailing 20-bar window strictly prior to the A+ date).

| Statistic | Value |
|---|---:|
| Priced count | 35 / 35 |
| Unpriced count | 0 |
| Min | $15,732,160 |
| 25th percentile | $54,798,849 |
| **Median** | **$84,709,976** |
| 75th percentile | $144,212,370 |
| Max | $705,111,996 |
| Fraction below $500K/day | 0.0 % |
| Fraction below $1M/day | 0.0 % |

All 35 A+ signals are priced and have avg daily $ volume well above $1M. The minimum at $15.7M/day is two orders of magnitude above any plausible execution constraint at the operator's 1× capital ($7,500 with ~10 % position size ≈ $750 trade). Per the D1 pre-registration, liquidity is **descriptive, not gating**; this distribution informs the operator's awareness but does not affect tier classification.

## Results — data-quality characterization

| Metric | Value |
|---|---|
| A+ signals with `absent_earnings_data=True` | 17 / 35 = **48.6 %** |
| Universe size | 1,506 |
| OHLCV cache hit rate | 1,499 / 1,507 = 99.5 % |
| OHLCV cold-fetch successes | 8 (no fetch failures recorded) |
| Earnings cache hit rate | 1,497 / 1,506 = 99.4 % |
| Earnings cold-fetch successes | 9 |
| Skipped ticker-days (insufficient OHLCV history) | 8,584 / 759,024 = 1.13 % |

The 48.6 % absent-earnings-data fraction on A+ signals is comparable to Russell 3000's 54 % (Run C). yfinance's `Ticker.get_earnings_dates()` coverage is the dominant constraint, not the universe choice — adding the S&P MidCap 400 + S&P SmallCap 600 to SPX 500 inherits the same earnings-coverage gap that affects most non-large-cap names. **D1's Tier 1 gate is `<30 % absent earnings`; the measured 48.6 % fails this gate by a clear margin** even if the rate uplift had reached 3×.

No yfinance OHLCV-fetch failures were observed on this universe (compare: Russell 3000 had 14 fetch failures out of 2,579 tickers).

## Tier classification

Apply D1's frozen thresholds verbatim:

- **Rate uplift:** 2.39× ≥ 2× threshold (Tier 3 ruled out).
- **Rate uplift:** 2.39× < 3× threshold (Tier 1's rate gate fails).
- **Sector concentration:** 20 % largest single sector < 40 % threshold (no concentration override).

The rate-uplift result lands in the [2×, 3×) band, which is the primary Tier 2 cell per D1. The absent-earnings-data fraction (48.6 %) exceeds the Tier 1 gate of < 30 %, so the absent-data alternate path into Tier 2 ("≥3× uplift but ≥30 % absent earnings") is moot on this run. Sector concentration is well-distributed (no concentration override path triggered).

**Tier classification: Tier 2 — Mixed.**

The classification is unambiguous: the rate-uplift point estimate is squarely inside the [2×, 3×) band, with a sample-size-aware Wilson 95 % CI ([0.00332 %, 0.00641 %]) that does not reach the 0.00580 % Tier 1 lower-cutoff at its lower end (and reaches it only above its midpoint). Per D1's anti-rationalization clause, the result IS what the frozen thresholds say it is.

## Findings (descriptive, not prescriptive)

1. **S&P 1500 1× lands at Tier 2 — Mixed under D1's frozen thresholds.** Rate uplift 2.39× over the SPX+NDX 1× baseline (35 A+ over 759,024 ticker-days = 0.00461 % per ticker-day, vs baseline 0.00193 %). Sector concentration is benign (20 % maximum); absent-earnings-data fraction (48.6 %) is high enough to fail D1's Tier 1 < 30 % gate, but the rate-uplift gate is the binding constraint here, not the absent-data gate. Per-rate Wilson 95 % CI ([0.00332 %, 0.00641 %]) overlaps the SPX+NDX 1× CI ([0.00083 %, 0.00453 %]) in the interval [0.00332 %, 0.00453 %]; the disjoint-CI shortcut that justified the SPX+NDX-vs-Russell informal inference does not apply here. The 2.39× point estimate is the figure used for tier classification per D1's pre-registered procedure.

2. **Production-gated `risk_feasibility` blocker on S&P 1500 1× is 9.65 %, between SPX+NDX 1× (18.62 %) and Russell 3000 1× (6.91 %).** Consistent with the structural pattern from the candidate-sparsity diagnostic: at fixed 1× capital, risk_feasibility blocks fewer evaluations as the universe broadens to include lower-priced names where the per-share risk budget binds less often. This study does not run an S&P 1500 5× cell, so the capital-sensitivity transition (the diagnostic's headline finding for SPX+NDX and Russell) is not directly measured on S&P 1500.

3. **TT1 (above 150-day & 200-day MA) is the dominant production-gated blocker at 42.53 %.** Same shape as the candidate-sparsity diagnostic on SPX+NDX (34.39 %) and Russell 3000 (46.04 %). The trend-template stack (TT1–TT7) collectively binds ~73 % of S&P 1500 1× evaluations under production gating, similar to Russell 3000 1× at ~73 %; the trend-template gate dominates the rejection layer above the VCP layer.

4. **A+ signals span 9 of 11 GICS sectors with maximum concentration of 20 % (Information Technology).** Distinct from a "small-cap-tech-tilt" pattern. Consumer Discretionary (17.1 %) and Health Care (17.1 %) tie for second; Industrials (14.3 %) and Materials (11.4 %) round out the top five. Utilities and Consumer Staples are absent from A+ on this window. This is descriptive of the 35 A+ signals on this single run; sector composition over multiple windows or regimes is not characterized.

5. **Liquidity is uniformly strong across A+ signals.** Median avg daily $ volume on the prior 20 sessions is $84.7M; minimum is $15.7M; 0 % of A+ signals have avg daily $ vol below $1M. At the operator's ~$750 typical trade size, no A+ signal in this run is in any execution-difficulty regime that the operator would plausibly need to filter at production-ingest time.

6. **48.6 % of A+ signals carry `absent_earnings_data=True`.** Comparable to Russell 3000's 54 % on Run C; SPX+NDX produced 0 % on Runs A/B. yfinance's earnings coverage is the dominant constraint, not the specific universe choice between Russell 3000 and S&P 1500. Any production deployment of S&P 1500 would inherit this earnings-data gap on roughly half of A+ signals; the production earnings-proximity-exclusion logic would need to handle the absent-data case (Method record M-002 specifies absent-data → flag, do not exclude).

7. **Cache + fetch stats indicate near-fully-warm Russell-3000-derived cache.** Only 8 of 1,506 tickers triggered cold OHLCV fetches; 9 triggered cold earnings fetches. The S&P 1500 universe is essentially a subset of Russell 3000's holdings (with the small residual being recent S&P additions iShares' Russell ETF doesn't yet reflect, or share-class differences). This means the marginal fetch cost of the S&P 1500 expansion is small once the Russell 3000 cache is warm.

8. **Per-rate point-estimate comparison: SPX+NDX 1× → S&P 1500 1× → Russell 3000 1×.** Rates: 0.00193 % → 0.00461 % → 0.00890 % per ticker-day. Universe-size ratios: 516 → 1,506 → 2,579 tickers. Adding mid- and small-caps yields ~2.4× rate uplift; further extending to micro-cap-inclusive Russell 3000 yields another ~1.9× on top of S&P 1500. The marginal rate uplift per added ticker decreases as the universe broadens, but the data-quality cost (absent earnings, OHLCV fetch failures, survivorship-bias inheritance) increases. The S&P 1500 cell measures the middle of this curve at the operator's actual capital.

## What this study does NOT say

- This study does NOT recommend changing the production universe to S&P 1500 (or any other variant). Findings are descriptive; the operator decides what action, if any, the Tier 2 result motivates.
- This study does NOT make any claim about the **edge quality** of A+ candidates — only about their **rate** (count per ticker-day). No expectancy, win-rate, or gap-through statistics are computed. The harness's `simulate_trade` was deliberately not invoked.
- This study does NOT establish that the rate observed on S&P 1500 (0.00461 %) is stable across regimes. The single 504-session window is one observation; multi-window or rolling-window characterization is a separate study.
- This study does NOT formally test whether the S&P 1500 1× rate is significantly different from SPX+NDX 1× — Wilson CIs overlap; a formal Newcombe interval was not computed. The 2.39× point estimate is what D1's tier procedure consumes; whether it is robustly different from 1.0 is a separate question.
- This study does NOT measure capital-sensitivity on S&P 1500 (only the 1× cell was run, per D1).
- This study does NOT compare S&P 1500 to other plausible universe variants (ITOT, MSCI USA Investable Market, Wilshire 5000). If the operator wants those compared, it is a separate study.
- This study does NOT verify that the iShares-reported `Sector` field aligns with whatever sector taxonomy production might use for operator-facing display. The sector breakdown above uses iShares' reported sectors as-fetched.
- This study does NOT recompute universe membership at point-in-time per session; the 2026-04-25 snapshot is held constant across the entire 2024–2026 window.

## Caveats and limitations

- **Survivorship bias.** The replay uses iShares' current-roster IVV / IJH / IJR holdings as of 2026-04-25; delisted tickers from the 2024–2026 window are absent. Effect is plausibly larger on small-caps (IJR) than large-caps (IVV); the universe-composition direction this study reports is a lower bound on what an S&P-direct, point-in-time, delisting-aware version would show.
- **Fixed-universe at fetch date; no point-in-time membership reconstruction.** S&P committee adjustments are continuous but iShares' tracking ETFs lag. The 2026-04-25 fetch is applied to historical 2024–2026 data, over-including post-2024 entrants and under-including pre-2024 exits.
- **iShares-derived ticker list, not S&P-direct.** Authoritative S&P 1500 membership comes from S&P Global directly (paid feed); this study uses iShares tracking-fund holdings as a free, reproducible proxy. The 1,506 vs nominal 1,500 figure reflects iShares' fund composition at the fetch instant; no defect.
- **iShares per-URL fetch timestamps not tracked.** All three URLs were fetched within seconds of each other in a single `_load_or_fetch_ishares` call; if iShares published a fund composition update between the IVV fetch and the IJR fetch, the universe could be internally inconsistent. The bounded round-trip-time skew makes this unlikely to bind in practice; documented for transparency.
- **48.6 % absent earnings.** yfinance `Ticker.get_earnings_dates` coverage is materially worse for non-large-cap names. Any extension that depends on earnings-proximity filtering on S&P 1500 would inherit this gap; the D4 finding that this gap is comparable to Russell 3000 is itself only a single-window observation.
- **2-year window is a single regime.** The 2024-04 → 2026-04 window is one bull-market regime. Rate findings would not necessarily generalize to bear or volatile regimes; multi-regime characterization is hypothesis 4 from the brief, deferred.
- **Single-window sample for rate inference.** Wilson 95 % CIs on the rate are reported; CIs overlap with the SPX+NDX 1× baseline so the disjoint-CI heuristic doesn't apply. Tier classification uses point-estimate uplift per D1's pre-registered procedure, not a hypothesis test on rate difference. Operator interpretation that treats 2.39× as a precise effect size is over-confident; the rate-difference inference would require a Newcombe interval or similar instrument not run here.
- **Production-vs-replay parity is partial.** This study runs the same harness as the candidate-sparsity diagnostic; harness-vs-production parity was Tier 1 on n=80 watch/skip (Hypothesis 5, commit 110f7cc); A+-classification parity was not exercised empirically (eval 15 produced zero A+).
- **`current_equity` is config-derived, not DB-derived.** $7,500 from `swing.config.toml` `[account]`; operator's actual current equity may differ. Per the candidate-sparsity diagnostic precedent, the config-derived value is the reference.
- **Sector taxonomy is iShares-reported.** No cross-validation against GICS or a different production source.

## Open questions for the operator

These are open questions the findings might prompt; the study does not answer them. Each is phrased as a question, with no embedded methodology prescription.

- Does a Tier 2 result on S&P 1500 — 2.39× rate uplift, 48.6 % absent-earnings-data, 20 % maximum sector concentration, uniformly-strong liquidity — cross any threshold for a production-universe change? D1's Tier 2 framing was "meaningful uplift exists but at observable cost; operator decides whether tradeoff is acceptable."
- Is the absent-earnings-data fraction (48.6 %) acceptable given that the production earnings-proximity-exclusion rule is designed to flag-not-block on absent data (per Method record M-002)? Or does the high absent-data rate indicate a need for a richer earnings data source before any expansion is considered?
- If the rate uplift point estimate (2.39×) is operationally interesting but the per-rate Wilson CI is wide (and overlaps SPX+NDX 1×), would a multi-window characterization across 2024 / 2025 / 2026 partial windows tighten the inference enough to inform an adoption decision?
- The S&P 1500 sector breakdown shows Information Technology (20 %), Consumer Discretionary (17 %), Health Care (17 %) as the top three. Does this composition align with the operator's view of what an A+ feed should look like, or would any of the under-represented sectors (Utilities, Consumer Staples — both 0 % on this window) raise concern?
- Liquidity is uniformly strong on this run. If a future expansion to a wider universe (Russell 3000, or beyond) shows A+ signals with avg daily $ vol < $1M, would the operator want to filter at production-ingest time, or accept and decide per-candidate?
- The marginal rate uplift per added ticker decreases as the universe broadens (SPX+NDX → S&P 1500 → Russell 3000 yields 2.4× then ×1.9 on top). Is the diminishing-returns shape itself useful for thinking about where the universe-size sweet spot is for this strategy?
- Would a same-window Newcombe-interval test on (S&P 1500 1× rate − SPX+NDX 1× rate) provide enough additional confidence on the difference to justify it as a follow-on, or is the point-estimate uplift sufficient information given the single-window sample anyway?

## Run artifacts

| File | Contents | Committed? |
|---|---|---|
| `run_manifest.json` | Provenance: git SHA, universe metadata, capital, cache stats, summary counts | yes |
| `aplus_signals.csv` | 35 A+ signals (ticker, date, entry, stop, next-earnings, absent-data) | yes |
| `binding_constraints_prod_gated.csv` | **Primary** — production-gated blocker counts (`risk_feasibility` → trend-template → VCP) | yes |
| `binding_constraints.csv` | **Audit-trail** — emitted-order blocker counts | yes |
| `sp1500_findings.json` | Sidecar: sector breakdown, liquidity, Wilson CI, rate uplift (D4 quotes from this) | yes |
| `universe_provenance_supplement.json` | Three iShares CDN URLs + snapshot SHA-256 (closes the manifest's null `source_url` gap) | yes |
| `evaluations.csv` | Per-(ticker, date) per-criterion `pass`/`fail` results — 96 MB | **no** (in `diagnostic-out/.gitignore`; regenerable from manifest flags) |

Run directory: `research/harness/earnings_proximity/diagnostic-out/run_E_sp1500_1x/`.

Universe snapshot (cached locally, not in the repo):
- `~/swing-data/research-cache/universe-snapshots/sp_1500_2026-04-25.csv` — 1,506 tickers + per-row source URL.
- `~/swing-data/research-cache/universe-snapshots/sp_1500_2026-04-25_sectors.json` — ticker → sector mapping (used by the D4 aggregator).
