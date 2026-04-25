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

---

## Run details (D3)

- **Production DB read:** `~/swing-data/swing.db` (ro, URI mode), 2026-04-25 ~20:45 UTC.
- **Harness git SHA at run time:** `bcc3bc43e96ed3ed5464394febe23aa8e0d14cfc` (D2 head).
- **Qualifying evaluation_runs:** 14 (`run_id ∈ {2..15}`).
- **Skipped evaluation_runs:** 1 (`run_id=1`, `finviz_csv_basename=finviz16Apr2026.csv`, reason=`csv_missing` — the file was rejected on 2026-04-19 and renamed with a timestamp suffix; literal-basename resolution does not find it).
- **action_session_date range:** 2026-04-20 → 2026-04-27.
- **Distinct Finviz CSVs across qualifying runs:** **6** (finviz19Apr2026.csv through finviz24Apr2026.csv). The 14 runs collapse to 6 distinct daily inputs because the operator pipeline was re-triggered multiple times per day (run-count per CSV: 19Apr=3, 20Apr=4, 21Apr=2, 22Apr=2, 23Apr=2, 24Apr=1). See §"Caveats and limitations" — the 14 evaluation_runs are NOT 14 independent observations.
- **Total evaluations across qualifying runs:** **1,209** (sum of `tickers_evaluated` over qualifying runs).
- **Total candidate rows read:** 1,209. **Total candidate_criteria rows read:** ~21,000 (varies by bucket; populated for non-error rows).

## Results — bucket distribution

| Bucket | Count | % of evaluations |
|---|---:|---:|
| `aplus` | 3 | 0.248 % |
| `watch` | 249 | 20.596 % |
| `skip` | 898 | 74.276 % |
| `error` | 45 | 3.722 % |
| `excluded` | 14 | 1.158 % |
| **Total** | **1,209** | 100 % |

**Watch:A+ ratio overall:** **83.0** (= 249 / 3).

**Per-run watch:A+ ratio** (defined only on runs with non-zero A+; full table in `per_run_summary.csv`):

| run_id | action_session_date | watch:A+ ratio |
|---:|---|---:|
| 9 | 2026-04-22 | 17.0 |
| 10 | 2026-04-22 | 17.0 |
| 12 | 2026-04-24 | 24.0 |
| (others) | (other dates) | undefined (zero A+) |

11 of 14 qualifying runs produced zero A+ candidates; the 3 runs that did all classified the same ticker (see Finding 4 below).

## Results — per-criterion production-gated blocker distribution

| Criterion | Count | % of evaluations |
|---|---:|---:|
| `<aplus>` | 3 | 0.248 % |
| **`proximity_20ma`** | **534** | **44.169 %** |
| `ma_stack_10_20_50` | 156 | 12.903 % |
| `TT2_150_above_200` | 146 | 12.076 % |
| `adr` | 124 | 10.256 % |
| `ma_short_rising` | 66 | 5.459 % |
| `<error>` | 59 | 4.880 % |
| `tightness` | 45 | 3.722 % |
| `risk_feasibility` | 28 | 2.316 % |
| `TT4_50_above_150_200` | 17 | 1.406 % |
| `prior_trend` | 13 | 1.075 % |
| `TT1_above_150_200` | 12 | 0.993 % |
| `TT3_200_rising` | 6 | 0.496 % |

Counts sum to 1,209 (denominator integrity verified via test). The `<aplus>` row count equals the `aplus` bucket count exactly — zero re-aggregation drift; `consistency_warnings` was empty.

The `<error>` row in the production-gated table (59) exceeds the `error` bucket count (45) by 14. The 14-row gap is the `excluded` bucket: excluded candidates also have empty `candidate_criteria`, so they are tagged `<error>` in the production-gated re-aggregation by the same "empty-criteria-tuple" rule. In bucket-level reporting, `error` and `excluded` remain distinct (45 + 14 = 59).

## Results — near-A+ defensible subset

**Count:** **15** rows = **6.024 %** of the watch bucket (15 / 249).

The full 15-row sample (defensible = every non-pass criterion is in `{TT8_rs_rank, risk_feasibility, proximity_20ma}`):

| ticker | run_id | action_session_date | failed criteria |
|---|---:|---|---|
| SLDB | 11 | 2026-04-23 | proximity_20ma |
| SLDB | 5 | 2026-04-21 | proximity_20ma |
| SLDB | 6 | 2026-04-21 | proximity_20ma |
| SLDB | 7 | 2026-04-21 | proximity_20ma |
| SLDB | 8 | 2026-04-21 | proximity_20ma |
| UCTT | 5 | 2026-04-21 | proximity_20ma |
| UCTT | 6 | 2026-04-21 | proximity_20ma |
| UCTT | 7 | 2026-04-21 | proximity_20ma |
| UCTT | 8 | 2026-04-21 | proximity_20ma |
| SLDB | 2 | 2026-04-20 | proximity_20ma |
| SLDB | 3 | 2026-04-20 | proximity_20ma |
| SLDB | 4 | 2026-04-20 | proximity_20ma |
| UCTT | 2 | 2026-04-20 | proximity_20ma |
| UCTT | 3 | 2026-04-20 | proximity_20ma |
| UCTT | 4 | 2026-04-20 | proximity_20ma |

The 15 defensible rows cover **2 distinct tickers** (SLDB, UCTT) across **3 distinct action_session_dates** (2026-04-20, 2026-04-21, 2026-04-23); the multiplicity comes from per-day pipeline re-runs. Every defensible row has `proximity_20ma` as its sole non-pass criterion.

## Results — near-A+ doctrine-incompatible subset

**Count:** **234** rows = **93.976 %** of the watch bucket (234 / 249).

10-row sample (deterministic ordering: action_session_date DESC, ticker ASC; full sample in `near_aplus_incompatible_sample.csv`):

| ticker | run_id | action_session_date | failed criteria |
|---|---:|---|---|
| ALTO | 15 | 2026-04-27 | proximity_20ma | tightness |
| DAWN | 15 | 2026-04-27 | adr |
| DHC | 15 | 2026-04-27 | proximity_20ma | tightness |
| DNTH | 15 | 2026-04-27 | tightness |
| ELVN | 15 | 2026-04-27 | tightness | vcp_volume_contraction |
| GFS | 15 | 2026-04-27 | proximity_20ma | tightness |
| HPE | 15 | 2026-04-27 | proximity_20ma | tightness |
| KOD | 15 | 2026-04-27 | proximity_20ma | vcp_volume_contraction |
| PARR | 15 | 2026-04-27 | ma_stack_10_20_50 | vcp_volume_contraction |
| RLMD | 15 | 2026-04-27 | tightness |

These 10 rows are illustrative; the incompatible subset spans many distinct tickers across all action_session_dates (the sample's 04-27-only concentration is a sort-order artifact — DESC ordering puts the most recent date's rows first).

## Findings (descriptive, not prescriptive)

1. **`proximity_20ma` is the dominant production-gated blocker on the operator's Finviz pool, by a wide margin.** It accounts for **44.17 %** of evaluations (534 / 1,209). The next two blockers (`ma_stack_10_20_50` 12.90 %, `TT2_150_above_200` 12.08 %) together account for less than `proximity_20ma` alone. This profile is **markedly different** from the broad-universe candidate-sparsity diagnostic, where `TT1_above_150_200` (34–46 %) and `risk_feasibility` (1–19 %) dominated; on the Finviz pool, `TT1_above_150_200` is the production-gated blocker for only 12 evaluations (0.99 %). The descriptive read of this gap is that the operator's Finviz filter is selecting tickers that have already cleared the trend-template stack — what the production filter then prunes is the VCP-layer timing/extension test (`proximity_20ma`).

2. **`risk_feasibility` is rarely the production-gated blocker on the Finviz pool (28 evaluations, 2.32 %).** The Finviz pool's price/cap pre-screen appears to filter out candidates whose risk-per-share would exceed the operator's per-share budget at current sizing equity. This is in qualitative contrast to the candidate-sparsity diagnostic's broad-universe finding (`risk_feasibility` 6.91–18.62 % of evaluations under production gating at 1× capital). Note: `risk_feasibility` is a hard filter in production gating order, so non-zero `risk_feasibility` blocker counts here mean candidates whose risk-per-share exceeded the budget regardless of upstream criterion state.

3. **The trend-template layer is collectively a smaller production-gated blocker on the Finviz pool than on broad universes.** Summing TT1+TT2+TT3+TT4 (excluded TT5/TT6/TT7 because they have zero blocker count on the Finviz pool, and TT8 is allowed-miss): 12 + 146 + 6 + 17 = **181 of 1,209 evaluations (14.97 %)** are blocked at the trend-template gate. Compare candidate-sparsity diagnostic Run A (SPX+NDX 1×): TT1 alone was 34.39 %. The difference is consistent with the Finviz filter pre-screening for trend-template structure; whether that pre-screening is "tight" or "loose" relative to the production criteria is not measured here.

4. **All 3 A+ candidates in this snapshot are the same ticker (SLDB) on 2 distinct action_session_dates (2026-04-22 and 2026-04-24).** Run 9 and Run 10 (both action_session_date 2026-04-22) classified SLDB as A+; Run 12 (action_session_date 2026-04-24) reclassified SLDB as A+. The watch:A+ ratio of 83.0 is therefore on a single-ticker A+ population.

5. **The near-A+ defensible subset is small in absolute terms (15 rows = 6.02 % of watch) and concentrated on 2 distinct tickers (SLDB, UCTT) across 3 distinct action_session_dates.** Per-row failed-criterion content is uniform: every defensible row has `proximity_20ma` as its sole non-pass criterion. The defensible subset's sample-size and concentration limit what the snapshot supports beyond the descriptive count. Note in particular: the sole A+ ticker in the snapshot (SLDB) appears as a defensible row on 4 prior days (2026-04-20, 2026-04-21, 2026-04-23) before reaching A+ on 2026-04-22 and 2026-04-24 — this trajectory (proximity-miss days followed by A+) is a single-ticker observation in this snapshot and is not a statistical pattern this study can characterize.

6. **The doctrine-incompatible subset (234 rows = 93.98 % of watch) is dominated by VCP-layer tightness/extension issues.** Reading the sampled rows: 10 of 10 sampled tickers have at least one of `tightness`, `proximity_20ma`, `vcp_volume_contraction`, `ma_stack_10_20_50`, `adr`. These are the VCP-fail-count thresholds talking — the watch bucket is by definition "1–2 VCP-layer fails," and the doctrine-incompatible subset is the watch population where at least one of those fails is in `DOCTRINE_INCOMPATIBLE_SET`. This is a tautology of the bucket-and-set definition, not an emergent pattern.

7. **The 14 evaluation_runs collapse to 6 distinct CSV inputs.** The operator pipeline was re-triggered multiple times per day (4× on 2026-04-20, 3× on 2026-04-19's CSV, etc.). The 1,209-evaluation denominator is therefore **not** 14 independent daily observations; it is closer to 6 daily inputs × ~80 candidates each, with within-day variance from re-runs. Bucket and blocker counts reported here are sums over re-runs, NOT per-day averages.

8. **Run 5 (2026-04-20T15:18) had an anomalously high error rate** (45 errors of 83 candidates evaluated). Subsequent re-runs of the same CSV (runs 6, 7, 8) had 0 / 1 / 1 errors. The 45-error count in this snapshot is therefore concentrated in a single failed-then-retried run; it is NOT a steady-state error rate. Runs 6–8 are effectively the cleaner read of finviz20Apr2026.csv.

## What this study does NOT say

- This study does **NOT** test trade outcomes. The hypothesis-labeling Phase 3e infrastructure ships in parallel (commits on `main` while this study landed) and persists a `hypothesis_label` field on entry; outcome-by-hypothesis aggregation is a future study once labeled trades accumulate. No P&L, win-rate, expectancy, or gap-through statistic is computed here.
- This study does **NOT** recommend changing any A+ criterion threshold. The dominance of `proximity_20ma` as the production-gated blocker on the Finviz pool is a descriptive observation about the current filter-and-criteria interaction, NOT a basis for relaxing the proximity rule.
- This study does **NOT** recommend specific tickers be traded. The 15 defensible rows (concentrated in SLDB, UCTT) are a descriptive observation about which watch-bucket candidates have only doctrine-defensible misses on the snapshot dates; they are not a trade list.
- This study does **NOT** establish whether the near-A+ defensible candidates produce edge under hypothesis-tagged trading. That question requires labeled trade outcomes from the parallel Phase 3e infrastructure and a future correlation study.
- This study does **NOT** test whether the 6.02 % near-A+ defensible rate is "high" or "low" relative to any operator threshold. The descriptive count is what is reported; the threshold for "this rate is operationally interesting" is operator-set.
- This study does **NOT** test the Finviz filter design. The blocker-distribution profile reflects the joint output of Finviz pre-screening and the production criteria; the study does not isolate either component's contribution.
- This study does **NOT** compare to alternative universes (S&P 1500, Russell 3000) — those are handled by separate studies in `research/studies/`.
- This study does **NOT** partition findings by sector, market cap, time period, or regime — the Finviz pool is too small for statistically meaningful conditional counts on this snapshot.

## Caveats and limitations

- **Snapshot of operator history (8 calendar days, 6 distinct CSVs).** This is NOT a multi-month or regime-balanced sample. Findings describe THIS snapshot of operator-actual production data as of 2026-04-25; the production system continues to ingest new CSVs daily and the per-criterion blocker distribution will shift as the universe evolves.
- **The 14 evaluation_runs are not 14 independent observations.** They collapse to 6 distinct CSV inputs. Re-runs of the same CSV produce slight variation in candidate counts (mostly stable; outlier is run 5's 45-error event). All counts reported are sums over re-runs; no de-duplication was applied at the (CSV-basename, ticker) level.
- **All 3 A+ candidates are a single ticker (SLDB).** The watch:A+ ratio of 83.0 is therefore not a generalizable rate; it is the ratio observed in a snapshot whose A+ population is one ticker. The "per-run watch:A+ ratio" column in `per_run_summary.csv` is undefined for 11 of 14 runs (zero A+); the 3 defined values (17.0, 17.0, 24.0) are also single-ticker.
- **The 45 error-bucket evaluations are concentrated in one run (run 5).** Subsequent re-runs of the same CSV had 0 / 1 / 1 errors. The aggregated error rate (3.72 %) is therefore not a steady-state operator-observed error rate; it is dominated by one transient yfinance/fetch failure event.
- **Path resolution by literal basename is intentional, but slightly conservative.** The production rejected/-rotation policy renames files with a timestamp suffix; literal basenames from stored `finviz_csv_path` columns will typically NOT resolve in `rejected/`. One run (run_id=1, finviz16Apr2026.csv) is therefore skipped despite the underlying CSV being preserved (under a renamed filename) in `rejected/`. Including it would have required a stem-prefix matching rule that the brief did not specify; it is documented as a methodological choice in the manifest's `path_resolution_rule` field.
- **Doctrine-defensible miss set membership reflects the 2026-04-25 framework framing.** Specifically, the operator-stance documented in `docs/orchestrator-context.md` (Recent decisions, 2026-04-25) treats `proximity_20ma` as a stage-for-re-entry timing miss rather than a setup-doesn't-exist failure. If the framing evolves, future studies' D1 would re-pre-register the set; this snapshot is locked to the current framing.
- **The "operationally tractable" framing of `risk_feasibility` as defensible is not testable on the watch bucket.** Production's hard-filter on `risk_feasibility` ensures any candidate failing it is bucketed `skip`, not `watch`. Inclusion of `risk_feasibility` in `DEFENSIBLE_MISS_SET` therefore does NOT influence the watch-bucket near-A+ classification on this snapshot (zero watch rows have `risk_feasibility` as a non-pass criterion). The set membership remains as pre-registered for analytical-structure consistency across runs (e.g., a future study running on candidate-evaluation-tier data prior to bucket assignment would see `risk_feasibility` as the dominant blocker, and the descriptive vocabulary would need the same set).
- **Production-gated re-aggregation is itself a piece of research code with no production-side equivalent test.** It mirrors `swing.evaluation.scoring.bucket_for`'s decision order but is implemented separately in `research.harness.earnings_proximity.scripts.recompute_binding_prod_gated`. Existing harness fixture tests verify the equivalence on a small fixed universe; this study's zero-drift `consistency_warnings` count cross-checks the equivalence on the operator's actual production data (the `<aplus>` row count equals the `aplus` bucket count exactly, which is necessary-but-not-sufficient for full equivalence).
- **The defensible-subset finding is dominated by SLDB and UCTT as multi-day repeat appearances.** There are only 2 distinct (ticker, action_session_date) defensible pairs: (SLDB, 2026-04-20), (SLDB, 2026-04-21), (SLDB, 2026-04-23), (UCTT, 2026-04-20), (UCTT, 2026-04-21) = 5 distinct pairs. The 15-row count comes from per-day re-runs multiplying observations for the same (ticker, day). De-duplicated at (ticker, day): 5 defensible (ticker, day) pairs out of 116 distinct watch (ticker, day) pairs = 4.31 %.

## Open questions for the operator

These are open questions the findings might prompt; the study does not answer them. Each is phrased as a question, with no embedded study-design prescription — choice of how (or whether) to follow up is the operator's.

- Does the **44.17 % `proximity_20ma` blocker rate** on the Finviz pool cross any threshold the operator considers material — for example, surfacing a row-level "extended (proximity-20MA fail)" indicator in the dashboard, or a "stage for re-entry on pullback" workflow distinct from the current watch bucket?
- Does the **15 defensible rows / 2 tickers / 3 days** count cross the operator's threshold for hypothesis-tagged experimental trade-taking? The parallel Phase 3e hypothesis-labeling infrastructure is the mechanism for collecting evidence; this snapshot does NOT establish whether the evidence would be informative — it only counts the population that would be eligible.
- Is the **single-ticker A+ population (SLDB only)** in this 8-day snapshot reflective of normal Finviz-pool yield, or an artifact of the calendar window (low-volatility period; fewer A+ setups crossing the bar)? The snapshot does not partition by regime; a longer-window aggregation could be a follow-on once more daily CSVs accumulate.
- The 14 runs / 6 CSVs ratio reflects the operator pipeline being re-triggered multiple times per day. Is this **per-day re-run pattern** intentional (e.g., manual re-runs, retries) or symptomatic (e.g., transient failures triggering retries — c.f. run 5's 45 errors)? The study reports the run-count breakdown without interpretation.
- Is the **doctrine-defensible miss set frozen at D1** (`{TT8_rs_rank, risk_feasibility, proximity_20ma}`) the right one going forward, or do post-data observations (e.g., the empirical clustering of `proximity_20ma`-only-fails) suggest amendment for FUTURE studies' D1 (NOT this one — this study's set membership is locked)?
- Does **SLDB's trajectory** (proximity-miss days followed by A+ days) — observable as a single-ticker pattern in this snapshot — generalize across more tickers in a longer-window aggregation? This question is empirical; this snapshot's n=1 (one ticker, three before-days, two after-days) is too thin to test.

## Run artifacts

| File | Contents | Committed |
|---|---|---|
| `out/run_20260425/run_manifest.json` | Provenance: harness git SHA, DB path + read timestamp, qualifying/skipped run lists, action_session_date range, total evaluations, bucket/blocker counts, doctrine-defensible miss set membership, path-resolution rule, consistency warnings | yes |
| `out/run_20260425/per_criterion_blockers.csv` | Production-gated blocker counts per criterion + `<aplus>` sentinel + `<error>` row | yes |
| `out/run_20260425/bucket_distribution.csv` | Per-bucket counts + watch:A+ ratio | yes |
| `out/run_20260425/per_run_summary.csv` | Per-run watch:A+ ratio (undefined for zero-A+ runs) | yes |
| `out/run_20260425/near_aplus_defensible_sample.csv` | All 15 defensible rows | yes |
| `out/run_20260425/near_aplus_incompatible_sample.csv` | 10-row deterministic sample of incompatible rows | yes |
