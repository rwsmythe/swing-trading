# Finviz-Pool Per-Criterion Binding-Constraint Analysis

**Date:** 2026-04-25
**Status:** Pre-registered (D1) — descriptive aggregation of operator-actual production data, no production-code recommendations.
**Companion to:** [`./candidate-sparsity-diagnostic.md`](candidate-sparsity-diagnostic.md) (predecessor — production-gated blocker methodology, broad-universe replays).
**Brief:** [`../../docs/finviz-pool-analysis-brief.md`](../../docs/finviz-pool-analysis-brief.md).

---

## Pre-registration (frozen at D1)

### Analytical question

> Across all production `evaluation_runs` ingested from operator-supplied Finviz CSVs (whose CSV files are still present on disk), what is the per-criterion **production-gated** blocker distribution; what is the watch:A+ bucket ratio; and what fraction of watch-bucket tickers have ONLY doctrine-defensible misses (i.e., are 'near-A+ defensible')?

### Strategic context (compressed)

The candidate-sparsity diagnostic ran the per-criterion binding-constraint analysis on broad replay universes (SPX+NDX, Russell 3000) and found `risk_feasibility` and `TT1_above_150_200` are the dominant production-gated blockers under the operator's effective sizing equity. **Neither study aggregated the per-criterion data on the operator's actual Finviz-pool input.** This study fills that gap. The operator's production database persists per-(ticker, criterion) results in `candidate_criteria` for every Finviz CSV ingested; this study reads those rows directly and applies the production-gated blocker re-aggregation that the predecessor study's R1 adversarial review established as the canonical metric.

The near-A+ defensible subset finding, in particular, is operationally relevant in the operator's settled stance (as recorded in `docs/orchestrator-context.md` Recent decisions, 2026-04-25) that sub-A+ trading is in actual practice and that hypothesis-tagged sub-optimal trades are acceptable as cost-of-development to generate evidence — but the study does NOT recommend trading specific candidates; the boundary it draws is descriptive only and the trade-outcome correlation is a future study (parallel Phase 3e hypothesis-labeling infrastructure ships separately).

### Scope

**In scope.** Aggregate per-criterion production-gated blocker counts, bucket distribution, watch:A+ ratio, near-A+ defensible/incompatible subset classification across all `evaluation_runs` rows whose `finviz_csv_path` resolves (by basename) to a still-present file in `data/finviz-inbox/` (top level or `rejected/` subdirectory). Pure read of existing production DB data; no harness re-run; no yfinance; no universe loaders; no production-code change. Phase isolation: `research/` only.

**Out of scope.** Production-code recommendations (this is descriptive only). Trade-outcome correlation (handled by parallel Phase 3e hypothesis-labeling change). Counterfactual Finviz-filter variations. Time-period or regime partitioning (the snapshot is whatever the operator's production history contains as of the run date). Per-sector or per-cap-tier breakdown (Finviz pool is small enough that conditional counts are statistically thin). Non-production-gated metric as primary (per candidate-sparsity diagnostic R1 Critical lesson, emitted-order conflates upstream-rerouted candidates).

### Doctrine-defensible miss set (frozen at D1)

The following criteria are designated "doctrine-defensible misses" — failing one of these alone (with all other criteria passing) does not necessarily mean "the setup doesn't exist"; it may instead represent an operationally-tractable circumstance with a doctrine-aligned response:

1. **`TT8_rs_rank`** — already a production `allowed_miss_name`. Listed for completeness; tickers failing only TT8 are A+ classified by production today (so will not appear in the watch bucket on TT8 alone — they will be A+).
2. **`risk_feasibility`** — capital-blocked; doctrine-aligned response is "smaller position than standard, OR pass and revisit at higher capital." Note: `risk_feasibility` is a hard-filter in production (`bucket_for`); a candidate that fails it is bucketed `skip`, not `watch`. `risk_feasibility` therefore cannot appear as a non-pass criterion on a watch-bucket candidate by construction. It is in the defensible set so the analytical structure can describe the production-gated blocker distribution coherently across all runs (where `risk_feasibility` is the dominant blocker on the `skip` side).
3. **`proximity_20ma`** — timing/extension miss; doctrine-aligned response is "wait for pullback to 20MA, then re-evaluate." Stage-for-re-entry, not trade-anyway.

All other criteria are designated "doctrine-incompatible misses" — failing them means the setup is not present (e.g., VCP not formed; trend not established; prior trend missing). These criteria are: `TT1_above_150_200`, `TT2_150_above_200`, `TT3_200_rising`, `TT4_50_above_150_200`, `TT5_above_50`, `TT6_above_52w_low_30pct`, `TT7_within_52w_high_25pct`, `ma_stack_10_20_50`, `ma_short_rising`, `prior_trend`, `adr`, `pullback`, `tightness`, `vcp_volume_contraction`, `orderliness`.

**Anti-rationalization.** The membership of the doctrine-defensible set is FROZEN at D1. Post-data, criteria may NOT be moved in or out of this set. If post-data analysis surfaces a finding like "tickers failing only `adr` look near-A+ in some way," that observation belongs in §"Open questions for the operator," NOT as a set-membership change. D5 adversarial-review fixes can clarify framing but cannot move set membership.

### Outputs (required, locked by pre-registration)

1. **Per-criterion production-gated blocker distribution.** Count and % of evaluations blocked by each criterion (per production gating order: `risk_feasibility` hard filter → trend-template gate → VCP fail-count thresholds). The `<aplus>` sentinel row is the count of evaluations that reached A+. Format mirrors candidate-sparsity diagnostic §"Per-criterion binding-constraint analysis (production-gated)."
2. **Bucket distribution.** Counts and % of evaluations falling into each bucket: `aplus`, `watch`, `skip`, `error`, `excluded`. Counts read directly from `candidates.bucket` (production-truth) and cross-checked against the production-gated blocker classification (`<aplus>` sentinel must equal `aplus` bucket count).
3. **Watch:A+ ratio.** Overall ratio AND per-run ratio (where defined; runs with zero A+ flagged with ratio = "undefined").
4. **Near-A+ defensible subset.** Count of `watch`-bucket tickers whose every non-pass criterion is in the doctrine-defensible miss set. Sample 10 tickers (or all if fewer) with: ticker, evaluation_run_id, action_session_date, list of failed criteria. Sample ordered deterministically (action_session_date DESC, ticker ASC) for reproducibility.
5. **Near-A+ doctrine-incompatible subset.** Count of `watch`-bucket tickers that have at least one non-pass criterion OUTSIDE the doctrine-defensible set. Sample 10 (or all if fewer) by the same ordering — for visibility on what falls into the "not defensible" pool, so the operator can sanity-check the boundary.
6. **Number of qualifying evaluation_runs included** (denominator transparency).
7. **Number of evaluation_runs SKIPPED** because their `finviz_csv_path` is no longer on disk; list which by id, action_session_date, basename.

### Run procedure (locked by pre-registration)

1. After D2 (aggregator + tests on synthetic fixtures) lands and tests pass, run the aggregation against the production DB.
2. Verify outputs are well-formed (CSV schemas; manifest fields). Do NOT interpret yet at D3.
3. Write D4 findings doc applying the frozen analytical structure to the data; do NOT modify the D1 sections of this document.

### Sample-size limitation

The number of qualifying evaluation_runs is whatever the operator's production history contains as of the run date. This is NOT a multi-month or regime-balanced sample; it is a snapshot of operator-actual production data to date. Findings are descriptive of THIS snapshot.

### Surfaces explicitly NOT analyzed

- Trade outcomes (handled by separate hypothesis-labeling Phase 3e infrastructure; future correlation study once labeled trades accumulate).
- Causal attribution between Finviz-filter design and per-criterion blocker patterns (would require counterfactual Finviz-filter variations, out of scope).
- Comparison to alternative universes (S&P 1500, Russell 3000 — handled by other studies in `research/studies/`).
- Per-sector or per-cap-tier breakdown of binding constraints (Finviz pool too small for statistically meaningful conditional counts).
- Non-production-gated metrics as primary. Per the candidate-sparsity diagnostic R1 Critical lesson, emitted-order blocker counts conflate upstream-rerouted candidates and would inflate apparent blocker distribution distortion. Emitted-order may appear as audit-trail secondary if useful.

### Provenance commitments

The D3 run manifest will record:

- Harness git SHA at run time (from `git rev-parse HEAD` AT the run, not at commit).
- Production DB path and timestamp of read.
- Number of qualifying evaluation_runs; list of (id, action_session_date, finviz_csv_basename) per qualifying run.
- Number of skipped evaluation_runs; list of (id, action_session_date, finviz_csv_basename, reason) per skipped run.
- Date range of `action_session_date` across qualifying runs.
- Number of total evaluations (= sum of `tickers_evaluated` over qualifying runs).
- Total candidates read; total `candidate_criteria` rows read.
- Doctrine-defensible miss set membership (frozen, copied verbatim from this document).
- Path-resolution rule: literal basename match against `data/finviz-inbox/` top-level, then `data/finviz-inbox/rejected/` subdirectory; if not found in either, classify as skipped (path-missing). Documented as a methodological choice; the rejected/ subdirectory in production renames files with a timestamp suffix, so a literal basename from a stored `finviz_csv_path` will typically NOT resolve in `rejected/` — runs whose CSVs have been rejected and renamed will appear in the skipped set.

---

(D2/D3/D4 sections appended in subsequent commits — D1 sections above are frozen.)
